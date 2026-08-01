"""Section-aware chunk boundary selection from validated canonical documents."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from hashlib import sha256

from ingestion.chunking.assets import associate_tables_and_assets
from ingestion.chunking.context import apply_neighbor_context, section_titles
from ingestion.chunking.models import (
    CHUNK_SCHEMA_VERSION,
    ChunkCollection,
    ChunkingConfiguration,
    ChunkType,
    DocumentChunk,
    ExactDuplicate,
    ExcludedBlock,
    ProcessingStatistics,
)
from ingestion.chunking.sizing import (
    estimate_tokens,
    normalize_text,
    normalized_text_hash,
    split_oversized_paragraph,
)
from ingestion.normalization.models import (
    BlockType,
    LocationType,
    NormalizedBlock,
    NormalizedDocument,
    NormalizedSection,
    NormalizedTable,
    SourceReference,
)


@dataclass
class _Atom:
    blocks: list[NormalizedBlock]
    forced_type: ChunkType | None = None
    text_override: str | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class _StructuralUnit:
    key: tuple[str | None, int | None]
    section_id: str | None
    provisional_title: str | None
    atoms: list[_Atom] = field(default_factory=list)


def build_chunk_collection(
    document: NormalizedDocument,
    configuration: ChunkingConfiguration | None = None,
) -> ChunkCollection:
    """Build deterministic chunks using only an already validated canonical model."""
    derivative = document.metadata.get("derivative_provenance")
    if isinstance(derivative, dict) and derivative.get("quality_outcome") not in {
        "accepted",
        "accepted_with_warnings",
    }:
        raise ValueError("Rejected OCR canonical output cannot be chunked.")
    config = configuration or ChunkingConfiguration()
    sections = {section.section_id: section for section in document.sections}
    tables = {table.table_id: table for table in document.tables}
    all_blocks = _ordered_blocks(document)
    included, excluded = _exclude_repeated_furniture(all_blocks)
    block_by_id = {block.block_id: block for block in included}
    warnings: list[str] = []
    if not document.sections:
        warnings.append(
            "No reliable canonical section hierarchy; headings and locations are "
            "provisional boundaries."
        )

    atoms = _build_atoms(included, tables, document, config)
    units = _structural_units(atoms, bool(document.sections))
    candidates: list[DocumentChunk] = []
    for unit in units:
        candidates.extend(
            _chunks_from_unit(
                document,
                unit,
                sections,
                tables,
                config,
                start_index=len(candidates),
            )
        )

    unassociated_tables, unassociated_assets, association_warnings = associate_tables_and_assets(
        document, candidates, block_by_id
    )
    warnings.extend(association_warnings)
    chunks, duplicates = _deduplicate_chunks(candidates)
    for index, chunk in enumerate(chunks):
        chunk.chunk_index = index
    apply_neighbor_context(chunks, config.maximum_context_characters_per_side)
    for chunk in chunks:
        chunk.table_ids = sorted(set(chunk.table_ids))
        chunk.asset_ids = sorted(set(chunk.asset_ids))
        _set_generation_eligibility(chunk, block_by_id)

    if not chunks:
        warnings.append("No meaningful canonical content was available for chunk construction.")
    warnings.extend(warning for chunk in chunks for warning in chunk.warnings)
    warnings = list(dict.fromkeys(warnings))
    statistics = _statistics(
        all_blocks=all_blocks,
        chunks=chunks,
        excluded=excluded,
        table_count=len(document.tables),
        asset_count=len(document.assets),
        unassociated_table_count=len(unassociated_tables),
        unassociated_asset_count=len(unassociated_assets),
        duplicate_count=len(duplicates),
        warnings=warnings,
    )
    return ChunkCollection(
        document_id=document.document_id,
        source_sha256=document.sha256,
        source_relative_path=document.source_relative_path,
        document_type=document.document_type,
        document_title=document.title,
        chunking_configuration=config,
        generated_at=document.processing.normalized_at,
        chunk_count=len(chunks),
        chunks=chunks,
        tables=document.tables,
        assets=document.assets,
        excluded_blocks=excluded,
        exact_duplicates=duplicates,
        unassociated_table_ids=unassociated_tables,
        unassociated_asset_ids=unassociated_assets,
        warnings=warnings,
        errors=[],
        processing_statistics=statistics,
    )


def _set_generation_eligibility(chunk: DocumentChunk, blocks: dict[str, NormalizedBlock]) -> None:
    reasons: list[str] = []
    if not chunk.normalized_text:
        reasons.append("empty_normalized_text")
    if not chunk.source_references:
        reasons.append("missing_source_references")
    chunk_blocks = [blocks[block_id] for block_id in chunk.block_ids if block_id in blocks]
    if chunk_blocks and all(
        block.block_type in {BlockType.HEADER, BlockType.FOOTER} for block in chunk_blocks
    ):
        reasons.append("administrative_furniture_only")
    if chunk.chunk_type is ChunkType.FIGURE_CONTEXT and not chunk.normalized_text:
        reasons.append("uncaptioned_asset_without_explanation")
    chunk.generation_exclusion_reasons = reasons
    chunk.eligible_for_generation = not reasons


def _ordered_blocks(document: NormalizedDocument) -> list[NormalizedBlock]:
    positioned = [
        (block.reading_order, page_index, block_index, block.block_id, block)
        for page_index, page in enumerate(document.pages)
        for block_index, block in enumerate(page.blocks)
    ]
    positioned.sort(key=lambda item: item[:4])
    return [item[4] for item in positioned]


def _exclude_repeated_furniture(
    blocks: list[NormalizedBlock],
) -> tuple[list[NormalizedBlock], list[ExcludedBlock]]:
    furniture = {BlockType.HEADER, BlockType.FOOTER}
    locations_by_text: dict[str, set[int | None]] = defaultdict(set)
    for block in blocks:
        normalized = normalize_text(block.text or "")
        if block.block_type in furniture and normalized:
            locations_by_text[normalized].add(block.page_or_slide_number)
    included: list[NormalizedBlock] = []
    excluded: list[ExcludedBlock] = []
    page_number_pattern = re.compile(r"^(?:page\s*)?\d+(?:\s*/\s*\d+)?$", re.IGNORECASE)
    for block in blocks:
        normalized = normalize_text(block.text or "")
        reason: str | None = None
        if block.block_type in furniture and normalized:
            if len(locations_by_text[normalized]) >= 2:
                reason = "repeated administrative header or footer"
            elif page_number_pattern.fullmatch(normalized):
                reason = "administrative page-number header or footer"
        if reason is None:
            included.append(block)
        else:
            excluded.append(
                ExcludedBlock(
                    block_id=block.block_id,
                    reason=reason,
                    normalized_text_hash=normalized_text_hash(normalized),
                    source_reference=block.source_reference,
                )
            )
    return included, excluded


def _build_atoms(
    blocks: list[NormalizedBlock],
    tables: dict[str, NormalizedTable],
    document: NormalizedDocument,
    config: ChunkingConfiguration,
) -> list[_Atom]:
    atoms: list[_Atom] = []
    index = 0
    structural = {
        BlockType.TABLE: ChunkType.TABLE_CONTEXT,
        BlockType.FIGURE: ChunkType.FIGURE_CONTEXT,
        BlockType.FORMULA: ChunkType.FORMULA_CONTEXT,
    }
    while index < len(blocks):
        block = blocks[index]
        if (
            block.block_type is BlockType.PARAGRAPH
            and len(block.text or "") > config.hard_max_characters
        ):
            fragments = split_oversized_paragraph(block.text or "", config.hard_max_characters)
            if len(fragments) > 1:
                for fragment_index, fragment in enumerate(fragments):
                    atoms.append(
                        _Atom(
                            blocks=[block],
                            text_override=fragment,
                            warnings=[
                                f"Oversized paragraph {block.block_id} was split at "
                                "textual boundaries."
                            ],
                            metadata={
                                "paragraph_fragment_index": fragment_index,
                                "paragraph_fragment_count": len(fragments),
                            },
                        )
                    )
                index += 1
                continue
        if block.block_type is BlockType.CAPTION and index + 1 < len(blocks):
            following = blocks[index + 1]
            if following.block_type in structural and _same_scope(block, following):
                atoms.append(
                    _Atom(
                        blocks=[block, following],
                        forced_type=structural[following.block_type],
                    )
                )
                index += 2
                continue
        if block.block_type in structural:
            grouped = [block]
            if index + 1 < len(blocks):
                following = blocks[index + 1]
                if following.block_type is BlockType.CAPTION and _same_scope(block, following):
                    grouped.append(following)
                    index += 1
            if index + 1 < len(blocks):
                explanation = blocks[index + 1]
                proposed = grouped + [explanation]
                if (
                    explanation.block_type is BlockType.PARAGRAPH
                    and _same_scope(block, explanation)
                    and len(_render_blocks(proposed, tables, document))
                    <= config.soft_max_characters
                ):
                    grouped.append(explanation)
                    index += 1
            if atoms:
                preceding = atoms[-1]
                if (
                    preceding.forced_type is None
                    and len(preceding.blocks) == 1
                    and preceding.blocks[0].block_type in {BlockType.HEADING, BlockType.PARAGRAPH}
                    and _same_scope(preceding.blocks[0], block)
                    and len(_render_blocks([*preceding.blocks, *grouped], tables, document))
                    <= config.soft_max_characters
                ):
                    atoms.pop()
                    grouped = [*preceding.blocks, *grouped]
            atoms.append(_Atom(blocks=grouped, forced_type=structural[block.block_type]))
            index += 1
            continue
        forced = ChunkType.LIST if block.block_type is BlockType.LIST_ITEM else None
        atoms.append(_Atom(blocks=[block], forced_type=forced))
        index += 1
    return atoms


def _same_scope(left: NormalizedBlock, right: NormalizedBlock) -> bool:
    return (
        left.parent_section_id == right.parent_section_id
        and left.page_or_slide_number == right.page_or_slide_number
    )


def _structural_units(atoms: list[_Atom], has_sections: bool) -> list[_StructuralUnit]:
    units: list[_StructuralUnit] = []
    provisional_number = 0
    provisional_title: str | None = None
    for atom in atoms:
        first = atom.blocks[0]
        if not has_sections and first.block_type is BlockType.HEADING:
            provisional_number += 1
            provisional_title = first.text
        elif not has_sections and first.block_type is BlockType.TITLE:
            provisional_title = first.text
        section_id = first.parent_section_id
        structural_id = section_id
        if structural_id is None and provisional_number:
            structural_id = f"provisional-{provisional_number}"
        location_key = (
            first.page_or_slide_number
            if section_id is None or first.source_reference.location_type is LocationType.SLIDE
            else None
        )
        key = (structural_id, location_key)
        if not units or units[-1].key != key:
            local_title = (
                first.text
                if first.block_type in {BlockType.TITLE, BlockType.HEADING}
                else provisional_title
                if provisional_number
                else None
            )
            units.append(
                _StructuralUnit(
                    key=key,
                    section_id=section_id,
                    provisional_title=local_title if section_id is None else None,
                )
            )
        elif units[-1].provisional_title is None and first.block_type in {
            BlockType.TITLE,
            BlockType.HEADING,
        }:
            units[-1].provisional_title = first.text
        units[-1].atoms.append(atom)
    return units


def _chunks_from_unit(
    document: NormalizedDocument,
    unit: _StructuralUnit,
    sections: dict[str, NormalizedSection],
    tables: dict[str, NormalizedTable],
    config: ChunkingConfiguration,
    start_index: int,
) -> list[DocumentChunk]:
    complete_text = _render_atoms(unit.atoms, tables, document)
    if len(complete_text) <= config.soft_max_characters and not any(
        atom.forced_type
        in {
            ChunkType.TABLE_CONTEXT,
            ChunkType.FIGURE_CONTEXT,
            ChunkType.FORMULA_CONTEXT,
        }
        for atom in unit.atoms
    ):
        return [
            _make_chunk(
                document,
                unit,
                unit.atoms,
                sections,
                tables,
                config,
                start_index,
                _default_chunk_type(document, unit, sections, unit.atoms),
            )
        ]

    groups: list[tuple[list[_Atom], ChunkType | None]] = []
    regular: list[_Atom] = []
    list_run: list[_Atom] = []

    def flush_regular() -> None:
        nonlocal regular
        if regular:
            groups.extend((part, None) for part in _pack_atoms(regular, tables, document, config))
            regular = []

    def flush_list() -> None:
        nonlocal list_run
        if list_run:
            groups.extend(
                (part, ChunkType.LIST) for part in _pack_atoms(list_run, tables, document, config)
            )
            list_run = []

    for atom in unit.atoms:
        if atom.forced_type is ChunkType.LIST:
            flush_regular()
            list_run.append(atom)
        elif atom.forced_type is not None:
            flush_regular()
            flush_list()
            groups.append(([atom], atom.forced_type))
        else:
            flush_list()
            regular.append(atom)
    flush_regular()
    flush_list()

    chunks: list[DocumentChunk] = []
    for group_index, (atoms, forced_type) in enumerate(groups):
        chunk_type = forced_type
        if chunk_type is None:
            chunk_type = (
                _default_chunk_type(document, unit, sections, atoms)
                if group_index == 0
                else ChunkType.PARAGRAPH_GROUP
            )
        chunks.append(
            _make_chunk(
                document,
                unit,
                atoms,
                sections,
                tables,
                config,
                start_index + len(chunks),
                chunk_type,
            )
        )
    return chunks


def _pack_atoms(
    atoms: list[_Atom],
    tables: dict[str, NormalizedTable],
    document: NormalizedDocument,
    config: ChunkingConfiguration,
) -> list[list[_Atom]]:
    packed: list[list[_Atom]] = []
    current: list[_Atom] = []
    for atom in atoms:
        proposed = current + [atom]
        proposed_size = len(_render_atoms(proposed, tables, document))
        if current and proposed_size > config.soft_max_characters:
            current_size = len(_render_atoms(current, tables, document))
            if (
                current_size >= config.minimum_characters
                or proposed_size > config.hard_max_characters
            ):
                packed.append(current)
                current = [atom]
            else:
                current = proposed
        else:
            current = proposed
    if current:
        packed.append(current)
    if len(packed) >= 2:
        final_size = len(_render_atoms(packed[-1], tables, document))
        combined = len(_render_atoms([*packed[-2], *packed[-1]], tables, document))
        if final_size < config.minimum_characters and combined <= config.soft_max_characters:
            packed[-2].extend(packed.pop())
    return packed


def _default_chunk_type(
    document: NormalizedDocument,
    unit: _StructuralUnit,
    sections: dict[str, NormalizedSection],
    atoms: list[_Atom],
) -> ChunkType:
    if unit.section_id is not None:
        section = sections[unit.section_id]
        return ChunkType.SECTION if section.level == 1 else ChunkType.SUBSECTION
    atom_block_ids = {block.block_id for atom in atoms for block in atom.blocks}
    ordered = _ordered_blocks(document)
    if (
        ordered
        and ordered[0].block_id in atom_block_ids
        and any(block.block_type is BlockType.TITLE for atom in atoms for block in atom.blocks)
    ):
        return ChunkType.DOCUMENT_PREAMBLE
    if unit.provisional_title is not None:
        return ChunkType.SECTION
    return ChunkType.ORPHAN_CONTENT


def _make_chunk(
    document: NormalizedDocument,
    unit: _StructuralUnit,
    atoms: list[_Atom],
    sections: dict[str, NormalizedSection],
    tables: dict[str, NormalizedTable],
    config: ChunkingConfiguration,
    chunk_index: int,
    chunk_type: ChunkType,
) -> DocumentChunk:
    blocks = [block for atom in atoms for block in atom.blocks]
    block_ids = list(dict.fromkeys(block.block_id for block in blocks))
    text = _render_atoms(atoms, tables, document)
    normalized = normalize_text(text)
    references = _unique_references(block.source_reference for block in blocks)
    locations = sorted(
        {
            reference.page_or_slide_number
            for reference in references
            if reference.page_or_slide_number is not None
        }
    )
    location_types = [reference.location_type for reference in references]
    location_type = location_types[0] if location_types else _document_location(document)
    path, parents = section_titles(unit.section_id, sections)
    section_title = (
        sections[unit.section_id].title if unit.section_id is not None else unit.provisional_title
    )
    warnings = [warning for atom in atoms for warning in atom.warnings]
    metadata: dict[str, object] = {
        "token_estimate_is_approximate": True,
        "sizing_metric": "characters",
        "structural_confidence": "canonical" if unit.section_id else "weak",
    }
    for atom in atoms:
        metadata.update(atom.metadata)
    indivisible = len(atoms) == 1 and (
        atoms[0].forced_type
        in {
            ChunkType.LIST,
            ChunkType.TABLE_CONTEXT,
            ChunkType.FIGURE_CONTEXT,
            ChunkType.FORMULA_CONTEXT,
        }
        or len(atoms[0].blocks) == 1
    )
    if len(text) > config.hard_max_characters and indivisible:
        metadata["atomic_oversize"] = True
        warnings.append(
            "Indivisible atomic content exceeds the configured hard maximum and was kept intact."
        )
    payload = json.dumps(
        {
            "schema": CHUNK_SCHEMA_VERSION,
            "document": document.document_id,
            "section": unit.section_id or unit.key[0],
            "blocks": block_ids,
            "type": chunk_type.value,
            "stable_index": chunk_index,
            "fragment": metadata.get("paragraph_fragment_index"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    chunk_id = sha256(payload.encode("utf-8")).hexdigest()
    return DocumentChunk(
        chunk_id=chunk_id,
        document_id=document.document_id,
        source_sha256=document.sha256,
        source_relative_path=document.source_relative_path,
        source_filename=document.source_filename,
        document_type=document.document_type,
        document_title=document.title,
        section_id=unit.section_id,
        section_path=path,
        section_title=section_title,
        parent_section_titles=parents,
        chunk_index=chunk_index,
        chunk_type=chunk_type,
        text=text,
        normalized_text=normalized,
        normalized_text_hash=normalized_text_hash(text),
        token_estimate=estimate_tokens(len(text)),
        character_count=len(text),
        block_ids=block_ids,
        page_or_slide_start=locations[0] if locations else None,
        page_or_slide_end=locations[-1] if locations else None,
        location_type=location_type,
        source_references=references,
        warnings=warnings,
        metadata=metadata,
    )


def _render_atoms(
    atoms: list[_Atom], tables: dict[str, NormalizedTable], document: NormalizedDocument
) -> str:
    parts = [
        atom.text_override
        if atom.text_override is not None
        else _render_blocks(atom.blocks, tables, document)
        for atom in atoms
    ]
    return "\n\n".join(part for part in parts if part).strip()


def _render_blocks(
    blocks: list[NormalizedBlock],
    tables: dict[str, NormalizedTable],
    document: NormalizedDocument,
) -> str:
    parts: list[str] = []
    generated_captions: set[str] = set()
    assets = {asset.asset_id: asset for asset in document.assets}
    for block in blocks:
        if block.block_type is BlockType.TABLE:
            table_id = block.metadata.get("table_id")
            table = tables.get(table_id) if isinstance(table_id, str) else None
            if table is not None:
                parts.append(_render_table(table))
                if table.caption:
                    generated_captions.add(normalize_text(table.caption))
        elif block.block_type is BlockType.FIGURE and not block.text:
            asset_id = block.metadata.get("asset_id")
            asset = assets.get(asset_id) if isinstance(asset_id, str) else None
            if asset is not None and asset.caption:
                parts.append(asset.caption)
                generated_captions.add(normalize_text(asset.caption))
        elif (
            block.block_type is BlockType.CAPTION
            and block.text
            and normalize_text(block.text) in generated_captions
        ):
            continue
        elif block.text:
            parts.append(block.text)
    return "\n\n".join(part for part in parts if part).strip()


def _render_table(table: NormalizedTable) -> str:
    matrix = [["" for _ in range(table.column_count)] for _ in range(table.row_count)]
    for cell in sorted(table.cells, key=lambda value: (value.row, value.column)):
        if cell.row < table.row_count and cell.column < table.column_count:
            matrix[cell.row][cell.column] = cell.text
    rows = [" | ".join(row) for row in matrix]
    if table.caption:
        return "\n".join([table.caption, *rows])
    return "\n".join(rows)


def _unique_references(references: Iterable[SourceReference]) -> list[SourceReference]:
    unique: dict[str, SourceReference] = {}
    for reference in references:
        key = reference.model_dump_json()
        unique.setdefault(key, reference)
    return list(unique.values())


def _document_location(document: NormalizedDocument) -> LocationType:
    return document.pages[0].location_type if document.pages else LocationType.DOCUMENT


def _deduplicate_chunks(
    candidates: list[DocumentChunk],
) -> tuple[list[DocumentChunk], list[ExactDuplicate]]:
    retained: list[DocumentChunk] = []
    duplicates: list[ExactDuplicate] = []
    by_hash: dict[str, DocumentChunk] = {}
    for candidate in candidates:
        if not candidate.normalized_text:
            retained.append(candidate)
            continue
        canonical = by_hash.get(candidate.normalized_text_hash)
        if canonical is None:
            by_hash[candidate.normalized_text_hash] = candidate
            retained.append(candidate)
            continue
        duplicate_references = _unique_references(
            [*candidate.source_references, *candidate.duplicate_source_references]
        )
        canonical.duplicate_source_references = _unique_references(
            [*canonical.duplicate_source_references, *duplicate_references]
        )
        canonical.table_ids.extend(candidate.table_ids)
        canonical.asset_ids.extend(candidate.asset_ids)
        duplicates.append(
            ExactDuplicate(
                canonical_chunk_id=canonical.chunk_id,
                duplicate_chunk_id=candidate.chunk_id,
                normalized_text_hash=candidate.normalized_text_hash,
                duplicate_source_references=duplicate_references,
            )
        )
    return retained, duplicates


def _statistics(
    *,
    all_blocks: list[NormalizedBlock],
    chunks: list[DocumentChunk],
    excluded: list[ExcludedBlock],
    table_count: int,
    asset_count: int,
    unassociated_table_count: int,
    unassociated_asset_count: int,
    duplicate_count: int,
    warnings: list[str],
) -> ProcessingStatistics:
    sizes = [chunk.character_count for chunk in chunks]
    with_references = sum(bool(chunk.source_references) for chunk in chunks)
    exclusion_reasons = Counter(
        reason for chunk in chunks for reason in chunk.generation_exclusion_reasons
    )
    return ProcessingStatistics(
        total_canonical_blocks=len(all_blocks),
        included_blocks=len(all_blocks) - len(excluded),
        excluded_blocks=len(excluded),
        total_chunks=len(chunks),
        chunks_by_type=dict(sorted(Counter(chunk.chunk_type.value for chunk in chunks).items())),
        minimum_chunk_size=min(sizes, default=0),
        maximum_chunk_size=max(sizes, default=0),
        average_chunk_size=sum(sizes) / len(sizes) if sizes else 0.0,
        estimated_token_total=sum(chunk.token_estimate for chunk in chunks),
        source_reference_coverage=with_references / len(chunks) if chunks else 0.0,
        chunks_with_no_source_references=len(chunks) - with_references,
        associated_tables=table_count - unassociated_table_count,
        unassociated_tables=unassociated_table_count,
        associated_assets=asset_count - unassociated_asset_count,
        unassociated_assets=unassociated_asset_count,
        duplicate_chunk_count=duplicate_count,
        warnings_count=len(warnings),
        errors_count=0,
        eligible_for_generation=sum(chunk.eligible_for_generation for chunk in chunks),
        excluded_from_generation=sum(not chunk.eligible_for_generation for chunk in chunks),
        generation_exclusion_reasons=dict(sorted(exclusion_reasons.items())),
    )
