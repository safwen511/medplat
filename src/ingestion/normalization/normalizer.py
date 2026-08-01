"""Convert a Docling tree into the project-owned canonical schema."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-untyped]

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
    TechnicalSuitability,
)

LABEL_TO_BLOCK = {
    "title": BlockType.TITLE,
    "section_header": BlockType.HEADING,
    "paragraph": BlockType.PARAGRAPH,
    "text": BlockType.PARAGRAPH,
    "list_item": BlockType.LIST_ITEM,
    "table": BlockType.TABLE,
    "picture": BlockType.FIGURE,
    "chart": BlockType.FIGURE,
    "caption": BlockType.CAPTION,
    "formula": BlockType.FORMULA,
    "code": BlockType.CODE,
    "footnote": BlockType.FOOTNOTE,
    "page_header": BlockType.HEADER,
    "page_footer": BlockType.FOOTER,
}


def _location_type(document_type: DocumentType) -> LocationType:
    return {
        DocumentType.PDF: LocationType.PAGE,
        DocumentType.POWERPOINT: LocationType.SLIDE,
        DocumentType.WORD: LocationType.DOCUMENT,
    }[document_type]


def _bbox(value: Any) -> BoundingBox | None:
    if value is None:
        return None
    origin = getattr(getattr(value, "coord_origin", None), "value", "unknown")
    return BoundingBox(
        left=float(value.l),
        top=float(value.t),
        right=float(value.r),
        bottom=float(value.b),
        coordinate_origin=str(origin),
    )


def _provenance(item: Any, document_type: DocumentType) -> tuple[int | None, BoundingBox | None]:
    if document_type is DocumentType.WORD:
        return None, None
    provenance = getattr(item, "prov", [])
    if not provenance:
        return None, None
    first = provenance[0]
    return int(first.page_no), _bbox(first.bbox)


def _caption(document: Any, item: Any) -> str | None:
    captions = getattr(item, "captions", [])
    if not captions:
        return None
    try:
        text = getattr(captions[0].resolve(document), "text", None)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return None
    return str(text) if text else None


def _source_reference(
    relative_path: str,
    location_type: LocationType,
    number: int | None,
    block_id: str | None,
    bounding_box: BoundingBox | None,
    excerpt: str | None,
) -> SourceReference:
    return SourceReference(
        source_relative_path=relative_path,
        location_type=location_type,
        page_or_slide_number=number,
        block_id=block_id,
        bounding_box=bounding_box,
        source_excerpt=excerpt,
    )


def _make_pages(
    document: Any, document_type: DocumentType, source_path: Path
) -> list[NormalizedPage]:
    location_type = _location_type(document_type)
    if document_type is DocumentType.WORD:
        return [NormalizedPage(number=None, location_type=location_type)]
    if document_type is DocumentType.PDF:
        with fitz.open(source_path) as pdf:
            return [
                NormalizedPage(
                    number=number,
                    location_type=location_type,
                    width=float(page.rect.width),
                    height=float(page.rect.height),
                )
                for number, page in enumerate(pdf, start=1)
            ]
    pages: list[NormalizedPage] = []
    for number, page in sorted(getattr(document, "pages", {}).items()):
        size = getattr(page, "size", None)
        pages.append(
            NormalizedPage(
                number=int(number),
                location_type=location_type,
                width=float(size.width) if size is not None else None,
                height=float(size.height) if size is not None else None,
            )
        )
    return pages


def _table_cells(item: Any) -> list[NormalizedTableCell]:
    return [
        NormalizedTableCell(
            row=int(cell.start_row_offset_idx),
            column=int(cell.start_col_offset_idx),
            row_span=int(cell.row_span),
            column_span=int(cell.col_span),
            text=str(cell.text),
            is_column_header=bool(cell.column_header),
            is_row_header=bool(cell.row_header),
        )
        for cell in item.data.table_cells
    ]


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _pdf_text_candidates(page: Any) -> list[tuple[str, str, BoundingBox]]:
    candidates: list[tuple[str, str, BoundingBox]] = []
    for raw in page.get_text("blocks", sort=True):
        source_text = str(raw[4]).strip()
        normalized = _normalized_text(source_text)
        if normalized:
            candidates.append(
                (
                    source_text,
                    normalized,
                    BoundingBox(
                        left=float(raw[0]),
                        top=float(raw[1]),
                        right=float(raw[2]),
                        bottom=float(raw[3]),
                        coordinate_origin="TOPLEFT",
                    ),
                )
            )
    return candidates


def _reconcile_pdf_text(
    source_path: Path,
    source_relative_path: str,
    pages: list[NormalizedPage],
    warnings: list[str],
) -> tuple[list[NormalizedAsset], dict[str, Any]]:
    """Match canonical text to PyMuPDF blocks; never add duplicate text."""
    assets: list[NormalizedAsset] = []
    low_text_image_pages: list[int] = []
    total_extractable_characters = 0
    next_reading_order = max(
        (block.reading_order for page in pages for block in page.blocks), default=0
    )
    with fitz.open(source_path) as pdf:
        by_number = {page.number: page for page in pages}
        for page_number, pdf_page in enumerate(pdf, start=1):
            page = by_number[page_number]
            page.width = float(pdf_page.rect.width)
            page.height = float(pdf_page.rect.height)
            candidates = _pdf_text_candidates(pdf_page)
            extractable_characters = len(pdf_page.get_text("text"))
            total_extractable_characters += extractable_characters
            page_images = pdf_page.get_images(full=True)
            if extractable_characters < 100 and page_images:
                low_text_image_pages.append(page_number)
            if not any(block.text and block.text.strip() for block in page.blocks) and candidates:
                for index, (source_text, _normalized, candidate_bbox) in enumerate(
                    candidates, start=1
                ):
                    next_reading_order += 1
                    block_id = f"block-pymupdf-{page_number:04d}-{index:04d}"
                    reference = SourceReference(
                        source_relative_path=source_relative_path,
                        location_type=LocationType.PAGE,
                        page_or_slide_number=page_number,
                        block_id=block_id,
                        bounding_box=candidate_bbox,
                        source_excerpt=source_text,
                    )
                    page.blocks.append(
                        NormalizedBlock(
                            block_id=block_id,
                            block_type=BlockType.UNKNOWN,
                            text=source_text,
                            page_or_slide_number=page_number,
                            reading_order=next_reading_order,
                            bounding_box=candidate_bbox,
                            source_reference=reference,
                            metadata={"pymupdf_text_fallback": True},
                        )
                    )
                warnings.append(
                    "Docling supplied no text on page "
                    f"{page_number}; retained {len(candidates)} PyMuPDF source text block(s) "
                    "without inferred structure."
                )
            for block in page.blocks:
                if not block.text or block.block_type in {BlockType.TABLE, BlockType.FIGURE}:
                    continue
                if block.metadata.get("pymupdf_text_fallback") is True:
                    continue
                target = _normalized_text(block.text)
                scored = sorted(
                    (
                        (
                            SequenceMatcher(None, target, candidate_text).ratio(),
                            index,
                            candidate_bbox,
                        )
                        for index, (_source, candidate_text, candidate_bbox) in enumerate(
                            candidates
                        )
                    ),
                    reverse=True,
                    key=lambda value: (value[0], -value[1]),
                )
                best = scored[0] if scored else None
                runner_up = scored[1][0] if len(scored) > 1 else 0.0
                if best is not None and best[0] >= 0.82 and best[0] - runner_up >= 0.05:
                    block.bounding_box = best[2]
                    block.source_reference.bounding_box = best[2]
                else:
                    block.bounding_box = None
                    block.source_reference.bounding_box = None
                    warnings.append(
                        f"No reliable PyMuPDF coordinate match for {block.block_id} on page "
                        f"{page_number}."
                    )

            seen_xrefs: set[int] = set()
            for image in page_images:
                xref = int(image[0])
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                asset_id = f"asset-{len(assets) + 1:06d}"
                rectangles = pdf_page.get_image_rects(xref)
                rectangle = rectangles[0] if rectangles else None
                bounding_box = (
                    BoundingBox(
                        left=float(rectangle.x0),
                        top=float(rectangle.y0),
                        right=float(rectangle.x1),
                        bottom=float(rectangle.y1),
                        coordinate_origin="TOPLEFT",
                    )
                    if rectangle is not None
                    else None
                )
                assets.append(
                    NormalizedAsset(
                        asset_id=asset_id,
                        asset_type=AssetType.IMAGE,
                        source_page_or_slide=page_number,
                        original_object_reference=f"pdf-xref:{xref}",
                        bounding_box=bounding_box,
                        metadata={
                            "width": int(image[2]),
                            "height": int(image[3]),
                            "bits_per_component": int(image[4]),
                        },
                    )
                )
                page.asset_references.append(asset_id)
    canonical_character_count = sum(
        len(block.text) for page in pages for block in page.blocks if block.text is not None
    )
    if low_text_image_pages:
        suitability = TechnicalSuitability.REQUIRES_OCR
        warnings.append(
            "ocr_required_but_disabled: "
            f"{len(low_text_image_pages)} low-text image page(s) require OCR; affected pages: "
            f"{', '.join(str(number) for number in low_text_image_pages)}."
        )
    elif total_extractable_characters == 0 or canonical_character_count == 0:
        suitability = TechnicalSuitability.UNSUITABLE
        warnings.append(
            "PDF normalization produced no canonical text; output is technically unsuitable."
        )
    else:
        suitability = TechnicalSuitability.READY_FOR_CHUNKING
    quality: dict[str, Any] = {
        "technical_suitability": suitability.value,
        "physical_page_count": len(pages),
        "extractable_character_count": total_extractable_characters,
        "canonical_text_character_count": canonical_character_count,
        "low_text_image_page_threshold_characters": 100,
        "low_text_image_page_count": len(low_text_image_pages),
        "low_text_image_pages": low_text_image_pages,
        "ocr_enabled": False,
    }
    return assets, quality


def _canonical_text_character_count(
    pages: list[NormalizedPage], tables: list[NormalizedTable]
) -> int:
    """Count non-whitespace canonical text without interpreting its meaning."""
    block_characters = sum(
        len(block.text.strip()) for page in pages for block in page.blocks if block.text is not None
    )
    table_characters = sum(
        len(cell.text.strip()) for table in tables for cell in table.cells if cell.text is not None
    )
    return block_characters + table_characters


def infer_office_technical_suitability(
    document: NormalizedDocument,
) -> TechnicalSuitability | None:
    """Infer extraction-only suitability for validated Office canonical documents."""
    if document.document_type not in {DocumentType.POWERPOINT, DocumentType.WORD}:
        return None
    character_count = _canonical_text_character_count(document.pages, document.tables)
    if character_count == 0:
        return TechnicalSuitability.UNSUITABLE
    if document.processing.warnings:
        return TechnicalSuitability.READY_WITH_WARNINGS
    return TechnicalSuitability.READY_FOR_CHUNKING


def normalize_docling_document(
    document: Any,
    *,
    source_path: Path,
    source_relative_path: str,
    sha256: str,
    mime_type: str | None,
    document_type: DocumentType,
    parser_name: str,
    parser_version: str | None,
    initial_warnings: tuple[str, ...] = (),
    source_filename: str | None = None,
    additional_metadata: dict[str, Any] | None = None,
) -> NormalizedDocument:
    """Normalize a Docling document without exposing Docling types in the result."""
    location_type = _location_type(document_type)
    warnings = list(initial_warnings)
    pages = _make_pages(document, document_type, source_path)
    if not pages and document_type is not DocumentType.WORD:
        warnings.append("The parser supplied no page or slide map.")

    page_map = {page.number: page for page in pages}
    sections: list[NormalizedSection] = []
    tables: list[NormalizedTable] = []
    assets: list[NormalizedAsset] = []
    extraction_quality: dict[str, Any] | None = None
    section_stack: list[NormalizedSection] = []
    title: str | None = None
    reading_order = 0

    for item, _tree_level in document.iterate_items():
        label_object = getattr(item, "label", None)
        label = str(getattr(label_object, "value", label_object or "unknown"))
        if label not in LABEL_TO_BLOCK:
            continue
        reading_order += 1
        block_id = f"block-{reading_order:06d}"
        number, bounding_box = _provenance(item, document_type)
        text_value = getattr(item, "text", None)
        text = str(text_value) if text_value not in {None, ""} else None
        block_type = LABEL_TO_BLOCK[label]

        if block_type is BlockType.HEADING:
            level = max(1, int(getattr(item, "level", 1)))
            while section_stack and section_stack[-1].level >= level:
                section_stack.pop()
            section = NormalizedSection(
                section_id=f"section-{len(sections) + 1:06d}",
                title=text or "",
                level=level,
                parent_section_id=section_stack[-1].section_id if section_stack else None,
                first_page_or_slide=number,
                last_page_or_slide=number,
            )
            sections.append(section)
            section_stack.append(section)

        parent_section = section_stack[-1] if section_stack else None
        if block_type is BlockType.TITLE and title is None and text is not None:
            title = text

        metadata: dict[str, Any] = {"docling_self_ref": str(item.self_ref)}
        if block_type is BlockType.TABLE:
            table_id = f"table-{len(tables) + 1:06d}"
            caption = _caption(document, item)
            table_reference = _source_reference(
                source_relative_path,
                location_type,
                number,
                block_id,
                bounding_box,
                caption,
            )
            tables.append(
                NormalizedTable(
                    table_id=table_id,
                    page_or_slide_number=number,
                    caption=caption,
                    row_count=int(item.data.num_rows),
                    column_count=int(item.data.num_cols),
                    cells=_table_cells(item),
                    bounding_box=bounding_box,
                    source_reference=table_reference,
                    metadata={"docling_self_ref": str(item.self_ref)},
                )
            )
            metadata["table_id"] = table_id
        elif block_type is BlockType.FIGURE:
            asset_id = f"asset-docling-{len(assets) + 1:06d}"
            assets.append(
                NormalizedAsset(
                    asset_id=asset_id,
                    asset_type=AssetType.CHART if label == "chart" else AssetType.FIGURE,
                    source_page_or_slide=number,
                    original_object_reference=str(item.self_ref),
                    caption=_caption(document, item),
                    bounding_box=bounding_box,
                )
            )
            metadata["asset_id"] = asset_id

        reference = _source_reference(
            source_relative_path,
            location_type,
            number,
            block_id,
            bounding_box,
            text,
        )
        block = NormalizedBlock(
            block_id=block_id,
            block_type=block_type,
            text=text,
            page_or_slide_number=number,
            reading_order=reading_order,
            bounding_box=bounding_box,
            parent_section_id=parent_section.section_id if parent_section else None,
            source_reference=reference,
            metadata=metadata,
        )
        if parent_section is not None:
            for containing_section in section_stack:
                containing_section.ordered_block_references.append(block_id)
            if number is not None:
                for containing_section in section_stack:
                    if containing_section.first_page_or_slide is None:
                        containing_section.first_page_or_slide = number
                    containing_section.last_page_or_slide = number

        target_page = page_map.get(number)
        if target_page is None and pages:
            target_page = pages[0]
            if document_type is not DocumentType.WORD:
                warnings.append(f"{block_id} has no reliable page or slide association.")
        if target_page is not None:
            target_page.blocks.append(block)
            referenced_asset_id = metadata.get("asset_id")
            if isinstance(referenced_asset_id, str):
                target_page.asset_references.append(referenced_asset_id)

    if title is None:
        warnings.append("No reliable document title was supplied by the parser.")
    if document_type is DocumentType.WORD:
        warnings.append("DOCX physical pagination is unavailable; location_type is document.")

    if document_type is DocumentType.PDF:
        pdf_assets, extraction_quality = _reconcile_pdf_text(
            source_path, source_relative_path, pages, warnings
        )
        offset = len(assets)
        for index, asset in enumerate(pdf_assets, start=1):
            old_id = asset.asset_id
            asset.asset_id = f"asset-pdf-{offset + index:06d}"
            for page in pages:
                page.asset_references = [
                    asset.asset_id if reference == old_id else reference
                    for reference in page.asset_references
                ]
        assets.extend(pdf_assets)
    elif document_type in {DocumentType.POWERPOINT, DocumentType.WORD}:
        canonical_character_count = _canonical_text_character_count(pages, tables)
        if canonical_character_count == 0:
            suitability = TechnicalSuitability.UNSUITABLE
            warnings.append(
                "Office normalization produced no meaningful canonical text; "
                "output is technically unsuitable."
            )
        elif warnings:
            suitability = TechnicalSuitability.READY_WITH_WARNINGS
        else:
            suitability = TechnicalSuitability.READY_FOR_CHUNKING
        extraction_quality = {
            "technical_suitability": suitability.value,
            "canonical_text_character_count": canonical_character_count,
        }

    document_metadata: dict[str, Any] = {
        "docling_schema_version": str(getattr(document, "version", "unknown"))
    }
    if extraction_quality is not None:
        if (
            extraction_quality["technical_suitability"]
            == TechnicalSuitability.READY_FOR_CHUNKING.value
            and warnings
        ):
            extraction_quality["technical_suitability"] = (
                TechnicalSuitability.READY_WITH_WARNINGS.value
            )
        document_metadata["extraction_quality"] = extraction_quality
    if additional_metadata:
        document_metadata.update(additional_metadata)
    page_or_slide_count = None if document_type is DocumentType.WORD else len(pages)
    return NormalizedDocument(
        document_id=sha256,
        sha256=sha256,
        source_relative_path=source_relative_path,
        source_filename=source_filename or source_path.name,
        source_extension=source_path.suffix.lower(),
        source_mime_type=mime_type,
        title=title,
        document_type=document_type,
        language=None,
        page_or_slide_count=page_or_slide_count,
        metadata=document_metadata,
        sections=sections,
        pages=pages,
        tables=tables,
        assets=assets,
        processing=ProcessingInformation(
            parser_name=parser_name,
            parser_version=parser_version,
            warnings=warnings,
        ),
    )
