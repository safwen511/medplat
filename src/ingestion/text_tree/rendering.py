"""Deterministic plain-text rendering for normalized documents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ingestion.normalization.models import (
    BlockType,
    DocumentType,
    NormalizedBlock,
    NormalizedDocument,
)
from ingestion.text_tree.models import TEXT_EXPORT_SCHEMA_VERSION, ExportStatus


@dataclass(frozen=True)
class RenderedBody:
    """Rendered body plus semantic text and navigation-unit counts."""

    text: str
    text_character_count: int
    page_or_slide_count: int | None


def _line_endings(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _render_table(document: NormalizedDocument, table_id: str, number: int) -> tuple[str, int]:
    table = next((item for item in document.tables if item.table_id == table_id), None)
    if table is None:
        return "", 0
    grid = [["" for _ in range(table.column_count)] for _ in range(table.row_count)]
    character_count = 0
    for cell in sorted(table.cells, key=lambda item: (item.row, item.column)):
        if cell.row >= table.row_count or cell.column >= table.column_count:
            continue
        value = _line_endings(cell.text).replace("\n", " ")
        grid[cell.row][cell.column] = value
        character_count += len(cell.text)
    lines = [f"===== TABLE {number} ====="]
    if table.caption:
        lines.extend([_line_endings(table.caption), ""])
        character_count += len(table.caption)
    lines.extend(" | ".join(row) for row in grid)
    return "\n".join(lines), character_count


def _render_blocks(
    document: NormalizedDocument,
    blocks: list[NormalizedBlock],
    table_numbers: dict[str, int],
) -> tuple[str, int]:
    rendered: list[str] = []
    character_count = 0
    for block in blocks:
        block_type = block.block_type
        if block_type is BlockType.TABLE:
            table_id = block.metadata.get("table_id")
            if isinstance(table_id, str):
                table_text, table_characters = _render_table(
                    document, table_id, table_numbers[table_id]
                )
                if table_text:
                    rendered.append(table_text)
                    character_count += table_characters
            continue
        text = block.text
        if not isinstance(text, str) or not text:
            continue
        normalized = _line_endings(text)
        if block_type is BlockType.LIST_ITEM:
            normalized = f"- {normalized}"
        rendered.append(normalized)
        character_count += len(text)
    return "\n\n".join(rendered), character_count


def render_normalized_document(
    document: NormalizedDocument, *, notes_by_slide: dict[int, str] | None = None
) -> RenderedBody:
    """Render canonical blocks in their retained reading and navigation order."""
    notes = notes_by_slide or {}
    table_numbers = {table.table_id: index for index, table in enumerate(document.tables, start=1)}
    sections: list[str] = []
    total_characters = 0
    if document.document_type is DocumentType.PDF:
        for page in document.pages:
            blocks = sorted(page.blocks, key=lambda item: item.reading_order)
            content, characters = _render_blocks(document, list(blocks), table_numbers)
            total_characters += characters
            sections.append(f"===== PAGE {page.number} =====\n\n{content}".rstrip())
        count: int | None = len(document.pages)
    elif document.document_type is DocumentType.POWERPOINT:
        for page in document.pages:
            blocks = sorted(page.blocks, key=lambda item: item.reading_order)
            title_blocks = [item for item in blocks if item.block_type is BlockType.TITLE]
            content_blocks = [item for item in blocks if item.block_type is not BlockType.TITLE]
            title, title_characters = _render_blocks(document, title_blocks, table_numbers)
            content, content_characters = _render_blocks(document, content_blocks, table_numbers)
            note = _line_endings(notes.get(int(page.number or 0), ""))
            total_characters += title_characters + content_characters + len(note)
            sections.append(
                f"===== SLIDE {page.number} =====\n\n"
                f"TITLE:\n{title}\n\nCONTENT:\n{content}\n\nNOTES:\n{note}".rstrip()
            )
        count = len(document.pages)
    elif document.document_type is DocumentType.WORD:
        blocks = sorted(
            (block for page in document.pages for block in page.blocks),
            key=lambda item: item.reading_order,
        )
        content, total_characters = _render_blocks(document, list(blocks), table_numbers)
        sections.append(f"===== DOCUMENT CONTENT =====\n\n{content}".rstrip())
        count = None
    else:  # pragma: no cover - the canonical model currently prevents this branch.
        raise ValueError(f"Unsupported normalized document type: {document.document_type}")
    return RenderedBody(
        text="\n\n".join(sections).rstrip() + "\n",
        text_character_count=total_characters,
        page_or_slide_count=count,
    )


def render_source_text(value: str) -> RenderedBody:
    """Render decoded source text with line-ending normalization only."""
    normalized = _line_endings(value)
    body = f"===== SOURCE TEXT =====\n\n{normalized}"
    return RenderedBody(text=body, text_character_count=len(normalized), page_or_slide_count=None)


def render_export(
    *,
    source_filename: str,
    source_relative_path: str,
    source_extension: str,
    source_sha256: str,
    document_type: str,
    status: ExportStatus,
    extraction_tool: str,
    exported_at: datetime,
    body: RenderedBody,
) -> str:
    """Prepend the exact, ordered metadata header to one successful body."""
    if status not in {ExportStatus.EXPORTED, ExportStatus.EXPORTED_WITH_WARNINGS}:
        raise ValueError("Only successful extraction states may be rendered to .txt.")
    header = [
        f"SOURCE_FILE: {source_filename}",
        f"SOURCE_RELATIVE_PATH: {source_relative_path}",
        f"SOURCE_EXTENSION: {source_extension}",
        f"SOURCE_SHA256: {source_sha256}",
        f"DOCUMENT_TYPE: {document_type}",
        f"EXTRACTION_STATUS: {status.value}",
        f"EXTRACTION_TOOL: {extraction_tool}",
        f"EXPORTED_AT: {exported_at.isoformat()}",
        f"TEXT_EXPORT_SCHEMA_VERSION: {TEXT_EXPORT_SCHEMA_VERSION}",
    ]
    return "\n".join(header) + "\n\n" + body.text
