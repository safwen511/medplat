"""Canonical output validation and summary helpers."""

from __future__ import annotations

from pathlib import Path

from ingestion.normalization.models import DocumentType, NormalizedDocument


def validate_document_file(path: Path) -> NormalizedDocument:
    """Load and validate one canonical JSON document."""
    return NormalizedDocument.model_validate_json(path.read_text(encoding="utf-8"))


def validation_summary(document: NormalizedDocument) -> dict[str, str | int | None]:
    """Return stable counts used by the validate-output CLI."""
    blocks = sum(len(page.blocks) for page in document.pages)
    return {
        "schema_version": document.schema_version,
        "document_type": document.document_type.value,
        "source_path": document.source_relative_path,
        "page_count": (
            document.page_or_slide_count if document.document_type is DocumentType.PDF else None
        ),
        "slide_count": (
            document.page_or_slide_count
            if document.document_type is DocumentType.POWERPOINT
            else None
        ),
        "section_count": len(document.sections),
        "block_count": blocks,
        "table_count": len(document.tables),
        "asset_count": len(document.assets),
    }
