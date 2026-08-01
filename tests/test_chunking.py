from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from ingestion.chunking.builder import build_chunk_collection
from ingestion.chunking.models import (
    ChunkCollection,
    ChunkingConfiguration,
    ChunkType,
    DocumentChunk,
)
from ingestion.chunking.validation import (
    validate_chunk_collection_file,
    validate_chunks_jsonl,
)
from ingestion.datasets.output import (
    DerivedOutputExistsError,
    write_chunk_outputs,
)
from ingestion.normalization.models import (
    AssetType,
    BlockType,
    BoundingBox,
    DocumentType,
    LocationType,
    NormalizedAsset,
    NormalizedBlock,
    NormalizedDocument,
    NormalizedPage,
    NormalizedSection,
    NormalizedTable,
    NormalizedTableCell,
    ProcessingInformation,
    SourceReference,
)

DOCUMENT_ID = "a" * 64
SOURCE_PATH = "course/lesson.pptx"
FIXED_TIME = datetime(2025, 1, 1, tzinfo=timezone.utc)


def block(
    identifier: str,
    block_type: BlockType,
    text: str | None,
    order: int,
    *,
    location: int | None = 1,
    location_type: LocationType = LocationType.SLIDE,
    section_id: str | None = None,
    metadata: dict[str, object] | None = None,
    box_top: float | None = None,
) -> NormalizedBlock:
    box = (
        BoundingBox(
            left=10,
            top=box_top,
            right=200,
            bottom=box_top + 20,
            coordinate_origin="TOPLEFT",
        )
        if box_top is not None
        else None
    )
    reference = SourceReference(
        source_relative_path=SOURCE_PATH,
        location_type=location_type,
        page_or_slide_number=location,
        block_id=identifier,
        bounding_box=box,
        source_excerpt=text,
    )
    return NormalizedBlock(
        block_id=identifier,
        block_type=block_type,
        text=text,
        page_or_slide_number=location,
        reading_order=order,
        bounding_box=box,
        parent_section_id=section_id,
        source_reference=reference,
        metadata=metadata or {},
    )


def section(
    identifier: str,
    title: str,
    level: int,
    blocks: list[str],
    parent: str | None = None,
) -> NormalizedSection:
    return NormalizedSection(
        section_id=identifier,
        title=title,
        level=level,
        parent_section_id=parent,
        first_page_or_slide=1,
        last_page_or_slide=2,
        ordered_block_references=blocks,
    )


def document(
    pages: list[list[NormalizedBlock]],
    *,
    document_type: DocumentType = DocumentType.POWERPOINT,
    sections: list[NormalizedSection] | None = None,
    tables: list[NormalizedTable] | None = None,
    assets: list[NormalizedAsset] | None = None,
) -> NormalizedDocument:
    location_type = {
        DocumentType.PDF: LocationType.PAGE,
        DocumentType.POWERPOINT: LocationType.SLIDE,
        DocumentType.WORD: LocationType.DOCUMENT,
    }[document_type]
    normalized_pages = [
        NormalizedPage(
            number=None if document_type is DocumentType.WORD else index,
            location_type=location_type,
            blocks=page_blocks,
        )
        for index, page_blocks in enumerate(pages, start=1)
    ]
    extension = {
        DocumentType.PDF: ".pdf",
        DocumentType.POWERPOINT: ".pptx",
        DocumentType.WORD: ".docx",
    }[document_type]
    return NormalizedDocument(
        document_id=DOCUMENT_ID,
        sha256=DOCUMENT_ID,
        source_relative_path=SOURCE_PATH,
        source_filename=f"lesson{extension}",
        source_extension=extension,
        document_type=document_type,
        title="Course title",
        page_or_slide_count=(None if document_type is DocumentType.WORD else len(pages)),
        sections=sections or [],
        pages=normalized_pages,
        tables=tables or [],
        assets=assets or [],
        processing=ProcessingInformation(
            parser_name="fixture",
            parser_version="1",
            normalized_at=FIXED_TIME,
        ),
    )


def simple_nested_document() -> NormalizedDocument:
    blocks = [
        block("b1", BlockType.TITLE, "Course title", 1, section_id=None),
        block("b2", BlockType.HEADING, "Main section", 2, section_id="s1"),
        block("b3", BlockType.PARAGRAPH, "Main explanatory text.", 3, section_id="s1"),
        block("b4", BlockType.HEADING, "Nested section", 4, section_id="s2"),
        block("b5", BlockType.PARAGRAPH, "Nested explanatory text.", 5, section_id="s2"),
    ]
    sections = [
        section("s1", "Main section", 1, ["b2", "b3", "b4", "b5"]),
        section("s2", "Nested section", 2, ["b4", "b5"], parent="s1"),
    ]
    return document([blocks], sections=sections)


def test_deterministic_ids_order_and_output_without_mutation() -> None:
    source = simple_nested_document()
    before = copy.deepcopy(source.model_dump(mode="json"))

    first = build_chunk_collection(source)
    second = build_chunk_collection(source)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert [chunk.chunk_id for chunk in first.chunks] == [chunk.chunk_id for chunk in second.chunks]
    assert [chunk.normalized_text for chunk in first.chunks] == [
        chunk.normalized_text for chunk in second.chunks
    ]
    assert source.model_dump(mode="json") == before


def test_section_and_subsection_boundaries_are_preserved() -> None:
    collection = build_chunk_collection(simple_nested_document())

    section_ids = [chunk.section_id for chunk in collection.chunks]
    assert "s1" in section_ids
    assert "s2" in section_ids
    nested = next(chunk for chunk in collection.chunks if chunk.section_id == "s2")
    assert nested.chunk_type is ChunkType.SUBSECTION
    assert nested.section_path == ["Main section", "Nested section"]
    assert nested.parent_section_titles == ["Main section"]


def test_long_section_splits_at_blocks_and_respects_hard_limit() -> None:
    blocks = [
        block("h", BlockType.HEADING, "Long section", 1, section_id="s1"),
        *[
            block(
                f"p{index}",
                BlockType.PARAGRAPH,
                f"Paragraph {index}. " + "x" * 85,
                index + 1,
                section_id="s1",
            )
            for index in range(1, 7)
        ],
    ]
    source = document(
        [blocks],
        sections=[section("s1", "Long section", 1, [value.block_id for value in blocks])],
    )
    config = ChunkingConfiguration(
        target_characters=120,
        soft_max_characters=180,
        hard_max_characters=220,
        minimum_characters=20,
    )

    collection = build_chunk_collection(source, config)

    assert len(collection.chunks) > 1
    assert all(chunk.character_count <= 220 for chunk in collection.chunks)
    assert [block_id for chunk in collection.chunks for block_id in chunk.block_ids] == [
        value.block_id for value in blocks
    ]


def test_minimum_size_tail_merges_with_same_section_neighbor() -> None:
    blocks = [
        block("p1", BlockType.PARAGRAPH, "a" * 120, 1, section_id="s1"),
        block("p2", BlockType.PARAGRAPH, "b" * 120, 2, section_id="s1"),
        block("p3", BlockType.PARAGRAPH, "small tail", 3, section_id="s1"),
    ]
    source = document(
        [blocks],
        sections=[section("s1", "One", 1, [value.block_id for value in blocks])],
    )
    config = ChunkingConfiguration(
        target_characters=100,
        soft_max_characters=150,
        hard_max_characters=200,
        minimum_characters=30,
    )

    collection = build_chunk_collection(source, config)

    assert len(collection.chunks) == 2
    assert collection.chunks[-1].block_ids == ["p2", "p3"]


def test_heading_fallback_and_orphan_content_report_weak_structure() -> None:
    source = document(
        [
            [
                block("orphan", BlockType.PARAGRAPH, "Unplaced preamble.", 1),
                block("heading", BlockType.HEADING, "Provisional heading", 2),
                block("body", BlockType.PARAGRAPH, "Provisional body.", 3),
            ]
        ]
    )

    collection = build_chunk_collection(source)

    assert collection.chunks[0].chunk_type is ChunkType.ORPHAN_CONTENT
    assert collection.chunks[1].section_title == "Provisional heading"
    assert collection.chunks[1].metadata["structural_confidence"] == "weak"
    assert any(
        "No reliable canonical section hierarchy" in warning for warning in collection.warnings
    )


def test_pdf_section_spanning_pages_preserves_all_locations_and_references() -> None:
    first = block(
        "p1",
        BlockType.PARAGRAPH,
        "Page one.",
        1,
        location=1,
        location_type=LocationType.PAGE,
        section_id="s1",
    )
    second = block(
        "p2",
        BlockType.PARAGRAPH,
        "Page two.",
        2,
        location=2,
        location_type=LocationType.PAGE,
        section_id="s1",
    )
    source = document(
        [[first], [second]],
        document_type=DocumentType.PDF,
        sections=[section("s1", "Spanning", 1, ["p1", "p2"])],
    )

    collection = build_chunk_collection(source)
    chunk = collection.chunks[0]

    assert chunk.page_or_slide_start == 1
    assert chunk.page_or_slide_end == 2
    assert {reference.page_or_slide_number for reference in chunk.source_references} == {1, 2}


def test_oversized_paragraph_splits_only_at_textual_boundaries() -> None:
    text = " ".join(f"Sentence {index} has source text." for index in range(30))
    source = document([[block("p1", BlockType.PARAGRAPH, text, 1)]])
    config = ChunkingConfiguration(
        target_characters=100,
        soft_max_characters=140,
        hard_max_characters=180,
        minimum_characters=10,
    )

    collection = build_chunk_collection(source, config)

    assert len(collection.chunks) > 1
    assert all(chunk.character_count <= 180 for chunk in collection.chunks)
    assert all(chunk.block_ids == ["p1"] for chunk in collection.chunks)
    assert any("split at textual boundaries" in warning for warning in collection.warnings)


def test_figure_caption_and_explanation_stay_together() -> None:
    asset = NormalizedAsset(
        asset_id="asset-1",
        asset_type=AssetType.FIGURE,
        source_page_or_slide=1,
        caption="Source figure caption",
    )
    blocks = [
        block(
            "f1",
            BlockType.FIGURE,
            None,
            1,
            metadata={"asset_id": "asset-1"},
        ),
        block("c1", BlockType.CAPTION, "Source figure caption", 2),
        block("p1", BlockType.PARAGRAPH, "Nearby source explanation.", 3),
    ]
    source = document([blocks], assets=[asset])

    collection = build_chunk_collection(source)

    figure = next(
        chunk for chunk in collection.chunks if chunk.chunk_type is ChunkType.FIGURE_CONTEXT
    )
    assert figure.block_ids == ["f1", "c1", "p1"]
    assert figure.asset_ids == ["asset-1"]
    assert figure.text.count("Source figure caption") == 1


def test_table_context_preserves_structured_table_and_nearby_text() -> None:
    table = NormalizedTable(
        table_id="table-1",
        page_or_slide_number=1,
        caption="Source table caption",
        row_count=2,
        column_count=2,
        cells=[
            NormalizedTableCell(row=0, column=0, text="A"),
            NormalizedTableCell(row=0, column=1, text="B"),
            NormalizedTableCell(row=1, column=0, text="1"),
            NormalizedTableCell(row=1, column=1, text="2"),
        ],
        source_reference=SourceReference(
            source_relative_path=SOURCE_PATH,
            location_type=LocationType.SLIDE,
            page_or_slide_number=1,
            block_id="t1",
        ),
    )
    blocks = [
        block("lead", BlockType.PARAGRAPH, "Table lead-in.", 1, section_id="s1"),
        block(
            "t1",
            BlockType.TABLE,
            None,
            2,
            section_id="s1",
            metadata={"table_id": "table-1"},
        ),
        block("tc", BlockType.CAPTION, "Source table caption", 3, section_id="s1"),
        block("exp", BlockType.PARAGRAPH, "Table explanation.", 4, section_id="s1"),
    ]
    source = document(
        [blocks],
        sections=[section("s1", "Tables", 1, [value.block_id for value in blocks])],
        tables=[table],
    )

    collection = build_chunk_collection(source)

    table_chunk = next(
        chunk for chunk in collection.chunks if chunk.chunk_type is ChunkType.TABLE_CONTEXT
    )
    assert table_chunk.table_ids == ["table-1"]
    assert table_chunk.block_ids == ["lead", "t1", "tc", "exp"]
    assert collection.tables[0].cells[3].text == "2"
    assert table_chunk.preceding_context is None


def test_formula_and_long_list_use_atomic_structural_boundaries() -> None:
    blocks = [
        block("formula", BlockType.FORMULA, "CO = HR × SV", 1, section_id="s1"),
        *[
            block(
                f"li{index}",
                BlockType.LIST_ITEM,
                f"List item {index} " + "x" * 55,
                index + 1,
                section_id="s1",
            )
            for index in range(1, 6)
        ],
    ]
    source = document(
        [blocks],
        sections=[section("s1", "Formula and list", 1, [value.block_id for value in blocks])],
    )
    config = ChunkingConfiguration(
        target_characters=90,
        soft_max_characters=130,
        hard_max_characters=180,
        minimum_characters=10,
    )

    collection = build_chunk_collection(source, config)

    assert any(chunk.chunk_type is ChunkType.FORMULA_CONTEXT for chunk in collection.chunks)
    list_chunks = [chunk for chunk in collection.chunks if chunk.chunk_type is ChunkType.LIST]
    assert len(list_chunks) >= 2
    flattened = [block_id for chunk in list_chunks for block_id in chunk.block_ids]
    assert flattened == [f"li{index}" for index in range(1, 6)]


def test_indivisible_oversized_table_is_retained_with_warning() -> None:
    table = NormalizedTable(
        table_id="huge",
        page_or_slide_number=1,
        row_count=1,
        column_count=1,
        cells=[NormalizedTableCell(row=0, column=0, text="x" * 300)],
        source_reference=SourceReference(
            source_relative_path=SOURCE_PATH,
            location_type=LocationType.SLIDE,
            page_or_slide_number=1,
            block_id="t1",
        ),
    )
    source = document(
        [[block("t1", BlockType.TABLE, None, 1, metadata={"table_id": "huge"})]],
        tables=[table],
    )
    config = ChunkingConfiguration(
        target_characters=50,
        soft_max_characters=80,
        hard_max_characters=100,
        minimum_characters=10,
    )

    collection = build_chunk_collection(source, config)
    chunk = collection.chunks[0]

    assert chunk.character_count > 100
    assert chunk.metadata["atomic_oversize"] is True
    assert any("Indivisible atomic content" in warning for warning in chunk.warnings)


def test_repeated_headers_footers_excluded_but_footnotes_retained() -> None:
    pages = [
        [
            block("h1", BlockType.HEADER, "University", 1, location=1),
            block("p1", BlockType.PARAGRAPH, "First page content.", 2, location=1),
            block("f1", BlockType.FOOTER, "1", 3, location=1),
        ],
        [
            block("h2", BlockType.HEADER, "University", 4, location=2),
            block("p2", BlockType.PARAGRAPH, "Second page content.", 5, location=2),
            block("note", BlockType.FOOTNOTE, "Meaningful footnote.", 6, location=2),
            block("f2", BlockType.FOOTER, "2", 7, location=2),
        ],
    ]

    collection = build_chunk_collection(document(pages))

    assert {value.block_id for value in collection.excluded_blocks} == {"h1", "h2", "f1", "f2"}
    assert any("Meaningful footnote." in chunk.text for chunk in collection.chunks)


def test_exact_duplicates_retain_all_source_provenance() -> None:
    source = document(
        [
            [block("p1", BlockType.PARAGRAPH, "Repeated exact content.", 1, location=1)],
            [block("p2", BlockType.PARAGRAPH, "Repeated   exact content.", 2, location=2)],
        ]
    )

    collection = build_chunk_collection(source)

    assert collection.chunk_count == 1
    assert len(collection.exact_duplicates) == 1
    canonical = collection.chunks[0]
    assert canonical.duplicate_source_references[0].block_id == "p2"
    assert canonical.duplicate_source_references[0].page_or_slide_number == 2


def test_docx_null_pagination_and_multislide_coverage() -> None:
    docx_block = block(
        "d1",
        BlockType.PARAGRAPH,
        "Word content.",
        1,
        location=None,
        location_type=LocationType.DOCUMENT,
    )
    docx_collection = build_chunk_collection(
        document([[docx_block]], document_type=DocumentType.WORD)
    )
    assert docx_collection.chunks[0].location_type is LocationType.DOCUMENT
    assert docx_collection.chunks[0].page_or_slide_start is None

    slides = document(
        [
            [block("s1", BlockType.PARAGRAPH, "Slide one.", 1, location=1)],
            [block("s2", BlockType.PARAGRAPH, "Slide two.", 2, location=2)],
        ]
    )
    slide_collection = build_chunk_collection(slides)
    assert {chunk.page_or_slide_start for chunk in slide_collection.chunks} == {1, 2}


def test_unassociated_objects_are_reported_without_forced_links() -> None:
    blocks = [
        block("p1", BlockType.PARAGRAPH, "Section one.", 1, section_id="s1"),
        block("p2", BlockType.PARAGRAPH, "Section two.", 2, section_id="s2"),
    ]
    sections = [
        section("s1", "One", 1, ["p1"]),
        section("s2", "Two", 1, ["p2"]),
    ]
    table = NormalizedTable(
        table_id="orphan-table",
        page_or_slide_number=1,
        row_count=0,
        column_count=0,
        cells=[],
        source_reference=SourceReference(
            source_relative_path=SOURCE_PATH,
            location_type=LocationType.SLIDE,
            page_or_slide_number=1,
        ),
    )
    asset = NormalizedAsset(
        asset_id="orphan-asset",
        asset_type=AssetType.IMAGE,
        source_page_or_slide=1,
    )

    collection = build_chunk_collection(
        document([blocks], sections=sections, tables=[table], assets=[asset])
    )

    assert collection.unassociated_table_ids == ["orphan-table"]
    assert collection.unassociated_asset_ids == ["orphan-asset"]
    assert all(not chunk.table_ids and not chunk.asset_ids for chunk in collection.chunks)


def test_invalid_source_reference_and_duplicate_chunk_ids_fail_validation() -> None:
    collection = build_chunk_collection(simple_nested_document())
    chunk_payload = collection.chunks[0].model_dump(mode="json")
    chunk_payload["source_references"][0]["block_id"] = "outside"
    with pytest.raises(ValidationError):
        DocumentChunk.model_validate(chunk_payload)

    payload = collection.model_dump(mode="json")
    payload["chunks"].append(copy.deepcopy(payload["chunks"][0]))
    payload["chunk_count"] += 1
    payload["chunks"][-1]["chunk_index"] = payload["chunk_count"] - 1
    with pytest.raises(ValidationError):
        ChunkCollection.model_validate(payload)


def test_jsonl_validity_atomic_cleanup_overwrite_and_pdfsrc_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical_dir = tmp_path / DOCUMENT_ID
    canonical_dir.mkdir()
    canonical_path = canonical_dir / "document.json"
    canonical_path.write_text(simple_nested_document().model_dump_json(), encoding="utf-8")
    collection = build_chunk_collection(simple_nested_document())

    output = write_chunk_outputs(canonical_path, collection)
    assert [chunk.chunk_id for chunk in validate_chunks_jsonl(output / "chunks.jsonl")] == [
        chunk.chunk_id for chunk in collection.chunks
    ]
    assert validate_chunk_collection_file(output / "chunks.json").chunk_count == len(
        collection.chunks
    )
    with pytest.raises(DerivedOutputExistsError):
        write_chunk_outputs(canonical_path, collection)

    write_chunk_outputs(canonical_path, collection, force=True)
    original_validator = validate_chunk_collection_file

    def fail_validation(_path: Path) -> ChunkCollection:
        raise ValueError("interrupted validation")

    monkeypatch.setattr("ingestion.datasets.output.validate_chunk_collection_file", fail_validation)
    with pytest.raises(ValueError, match="interrupted validation"):
        write_chunk_outputs(canonical_path, collection, force=True)
    assert original_validator(output / "chunks.json").chunk_count == collection.chunk_count
    assert not list(canonical_dir.glob(".chunks.*.tmp"))

    with pytest.raises(ValueError, match="pdfsrc"):
        write_chunk_outputs(Path("pdfsrc/fake/document.json"), collection)


def test_chunker_has_no_raw_parser_dependency() -> None:
    builder_source = Path("src/ingestion/chunking/builder.py").read_text(encoding="utf-8")
    assert "ingestion.parsers" not in builder_source
    assert "docling" not in builder_source.casefold()
    assert "fitz" not in builder_source.casefold()
