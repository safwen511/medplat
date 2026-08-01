"""Versioned AI-ready dataset schema without generated learning content."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from ingestion.chunking.models import (
    CHUNK_SCHEMA_VERSION,
    ChunkingConfiguration,
    DocumentChunk,
    ExactDuplicate,
    ExcludedBlock,
    ProcessingStatistics,
)
from ingestion.normalization.models import (
    SCHEMA_VERSION,
    CanonicalModel,
    DocumentType,
    NormalizedAsset,
    NormalizedTable,
)

DATASET_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"


class AIReadyDataset(CanonicalModel):
    dataset_schema_version: Literal["1.0.0"] = DATASET_SCHEMA_VERSION
    chunk_schema_version: Literal["1.0.0"] = CHUNK_SCHEMA_VERSION
    canonical_document_schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_relative_path: str
    document_type: DocumentType
    document_title: str | None = None
    language: str | None = None
    generation_timestamp: datetime
    chunking_configuration: ChunkingConfiguration
    chunk_count: int = Field(ge=0)
    chunks: list[DocumentChunk]
    tables: list[NormalizedTable]
    assets: list[NormalizedAsset]
    excluded_blocks: list[ExcludedBlock]
    exact_duplicates: list[ExactDuplicate]
    unassociated_tables: list[NormalizedTable]
    unassociated_assets: list[NormalizedAsset]
    warnings: list[str]
    errors: list[str]
    processing_statistics: ProcessingStatistics
    provenance_metadata: dict[str, Any]

    @model_validator(mode="after")
    def validate_dataset(self) -> AIReadyDataset:
        if self.chunk_count != len(self.chunks):
            raise ValueError("dataset chunk_count does not match chunks")
        if any(chunk.document_id != self.document_id for chunk in self.chunks):
            raise ValueError("dataset contains a chunk from another document")
        if len({chunk.chunk_id for chunk in self.chunks}) != len(self.chunks):
            raise ValueError("dataset contains duplicate chunk IDs")
        known_tables = {table.table_id for table in self.tables}
        known_assets = {asset.asset_id for asset in self.assets}
        if any(
            table_id not in known_tables for chunk in self.chunks for table_id in chunk.table_ids
        ):
            raise ValueError("chunk references a table absent from the dataset")
        if any(
            asset_id not in known_assets for chunk in self.chunks for asset_id in chunk.asset_ids
        ):
            raise ValueError("chunk references an asset absent from the dataset")
        if self.processing_statistics.total_chunks != self.chunk_count:
            raise ValueError("dataset statistics do not match chunks")
        return self
