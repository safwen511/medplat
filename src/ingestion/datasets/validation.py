"""AI-ready dataset validation and summary helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ingestion.datasets.models import AIReadyDataset


def validate_dataset_file(path: Path) -> AIReadyDataset:
    """Load and validate the complete dataset package."""
    return AIReadyDataset.model_validate_json(path.read_text(encoding="utf-8"))


def dataset_validation_summary(dataset: AIReadyDataset) -> dict[str, Any]:
    return {
        "dataset_schema_version": dataset.dataset_schema_version,
        "chunk_schema_version": dataset.chunk_schema_version,
        "document_id": dataset.document_id,
        "chunk_count": dataset.chunk_count,
        "source_reference_coverage": (dataset.processing_statistics.source_reference_coverage),
        "excluded_block_count": len(dataset.excluded_blocks),
        "duplicate_count": len(dataset.exact_duplicates),
        "unassociated_table_count": len(dataset.unassociated_tables),
        "unassociated_asset_count": len(dataset.unassociated_assets),
        "warnings": len(dataset.warnings),
        "errors": len(dataset.errors),
    }
