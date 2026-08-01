"""Validation and review summaries for chunk artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ingestion.chunking.models import ChunkCollection, DocumentChunk
from ingestion.normalization.models import LocationType


def validate_chunk_collection_file(path: Path) -> ChunkCollection:
    """Load and validate a current chunk collection."""
    return ChunkCollection.model_validate_json(path.read_text(encoding="utf-8"))


def validate_chunks_jsonl(path: Path) -> list[DocumentChunk]:
    """Validate every non-empty JSONL line as exactly one chunk object."""
    chunks: list[DocumentChunk] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"Blank JSONL record at line {line_number}")
        try:
            value: Any = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("record is not a JSON object")
            chunks.append(DocumentChunk.model_validate(value))
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise ValueError(f"Invalid JSONL record at line {line_number}: {exc}") from exc
    return chunks


def chunk_validation_summary(collection: ChunkCollection) -> dict[str, Any]:
    """Return the requested structural and coverage checks."""
    chunk_ids = [chunk.chunk_id for chunk in collection.chunks]
    page_locations = {
        reference.page_or_slide_number
        for chunk in collection.chunks
        for reference in chunk.source_references
        if reference.location_type is LocationType.PAGE
        and reference.page_or_slide_number is not None
    }
    slide_locations = {
        reference.page_or_slide_number
        for chunk in collection.chunks
        for reference in chunk.source_references
        if reference.location_type is LocationType.SLIDE
        and reference.page_or_slide_number is not None
    }
    soft_limit = collection.chunking_configuration.soft_max_characters
    hard_limit = collection.chunking_configuration.hard_max_characters
    exceeding = [chunk for chunk in collection.chunks if chunk.character_count > soft_limit]
    exceeding_hard = [chunk for chunk in collection.chunks if chunk.character_count > hard_limit]
    atomic_oversize = [chunk for chunk in exceeding_hard if chunk.metadata.get("atomic_oversize")]
    meaningful = [chunk for chunk in collection.chunks if chunk.normalized_text]
    return {
        "chunk_schema_version": collection.schema_version,
        "document_id": collection.document_id,
        "chunk_count": collection.chunk_count,
        "unique_chunk_id_count": len(set(chunk_ids)),
        "duplicate_chunk_id_count": len(chunk_ids) - len(set(chunk_ids)),
        "source_reference_coverage": collection.processing_statistics.source_reference_coverage,
        "page_coverage": len(page_locations),
        "slide_coverage": len(slide_locations),
        "chunks_exceeding_configured_limits": len(exceeding),
        "chunks_exceeding_hard_maximum": len(exceeding_hard),
        "atomic_oversize_chunks": len(atomic_oversize),
        "chunks_without_meaningful_text": collection.chunk_count - len(meaningful),
        "unassociated_tables": len(collection.unassociated_table_ids),
        "unassociated_assets": len(collection.unassociated_asset_ids),
        "exact_duplicate_count": len(collection.exact_duplicates),
        "warnings": len(collection.warnings),
        "errors": len(collection.errors),
    }
