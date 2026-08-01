"""Versioned schemas for deterministic, source-grounded document chunks."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Any, Literal

from pydantic import Field, model_validator

from ingestion.normalization.models import (
    CanonicalModel,
    DocumentType,
    LocationType,
    NormalizedAsset,
    NormalizedTable,
    SourceReference,
)

CHUNK_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
CHUNKER_VERSION: Literal["1.0.0"] = "1.0.0"


class ChunkType(str, Enum):
    SECTION = "section"
    SUBSECTION = "subsection"
    PARAGRAPH_GROUP = "paragraph_group"
    LIST = "list"
    TABLE_CONTEXT = "table_context"
    FIGURE_CONTEXT = "figure_context"
    FORMULA_CONTEXT = "formula_context"
    DOCUMENT_PREAMBLE = "document_preamble"
    ORPHAN_CONTENT = "orphan_content"


class ChunkingConfiguration(CanonicalModel):
    target_characters: int = Field(default=4000, gt=0)
    soft_max_characters: int = Field(default=6000, gt=0)
    hard_max_characters: int = Field(default=10000, gt=0)
    minimum_characters: int = Field(default=250, ge=0)
    maximum_context_characters_per_side: int = Field(default=500, ge=0)

    @model_validator(mode="after")
    def validate_limits(self) -> ChunkingConfiguration:
        if not (
            self.minimum_characters
            <= self.target_characters
            <= self.soft_max_characters
            <= self.hard_max_characters
        ):
            raise ValueError(
                "chunk sizes must satisfy minimum <= target <= soft maximum <= hard maximum"
            )
        return self


class ExcludedBlock(CanonicalModel):
    block_id: str
    reason: str
    normalized_text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_reference: SourceReference


class ExactDuplicate(CanonicalModel):
    canonical_chunk_id: str
    duplicate_chunk_id: str
    normalized_text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    duplicate_source_references: list[SourceReference]


class DocumentChunk(CanonicalModel):
    schema_version: Literal["1.0.0"] = CHUNK_SCHEMA_VERSION
    chunk_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_relative_path: str
    source_filename: str
    document_type: DocumentType
    document_title: str | None = None
    section_id: str | None = None
    section_path: list[str] = Field(default_factory=list)
    section_title: str | None = None
    parent_section_titles: list[str] = Field(default_factory=list)
    chunk_index: int = Field(ge=0)
    chunk_type: ChunkType
    text: str
    normalized_text: str
    normalized_text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    token_estimate: int = Field(ge=0)
    character_count: int = Field(ge=0)
    block_ids: list[str]
    page_or_slide_start: int | None = Field(default=None, ge=1)
    page_or_slide_end: int | None = Field(default=None, ge=1)
    location_type: LocationType
    source_references: list[SourceReference]
    table_ids: list[str] = Field(default_factory=list)
    asset_ids: list[str] = Field(default_factory=list)
    preceding_context: str | None = None
    following_context: str | None = None
    duplicate_source_references: list[SourceReference] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    eligible_for_generation: bool = True
    generation_exclusion_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_chunk(self) -> DocumentChunk:
        if self.character_count != len(self.text):
            raise ValueError("character_count does not match original chunk text")
        if self.token_estimate != (self.character_count + 3) // 4:
            raise ValueError("token_estimate does not match documented approximation")
        if self.normalized_text_hash != sha256(self.normalized_text.encode("utf-8")).hexdigest():
            raise ValueError("normalized_text_hash does not match normalized_text")
        if len(self.block_ids) != len(set(self.block_ids)):
            raise ValueError("chunk contains duplicate block IDs")
        if any(
            reference.source_relative_path != self.source_relative_path
            for reference in self.source_references
        ):
            raise ValueError("chunk source reference points to another source path")
        if any(
            reference.block_id not in self.block_ids
            for reference in self.source_references
            if reference.block_id is not None
        ):
            raise ValueError("chunk source reference points to a block outside the chunk")
        if self.location_type is LocationType.DOCUMENT and (
            self.page_or_slide_start is not None or self.page_or_slide_end is not None
        ):
            raise ValueError("document-location chunks cannot contain invented page numbers")
        if (
            self.page_or_slide_start is not None
            and self.page_or_slide_end is not None
            and self.page_or_slide_start > self.page_or_slide_end
        ):
            raise ValueError("chunk location range is reversed")
        return self


class ProcessingStatistics(CanonicalModel):
    total_canonical_blocks: int = Field(ge=0)
    included_blocks: int = Field(ge=0)
    excluded_blocks: int = Field(ge=0)
    total_chunks: int = Field(ge=0)
    chunks_by_type: dict[str, int]
    minimum_chunk_size: int = Field(ge=0)
    maximum_chunk_size: int = Field(ge=0)
    average_chunk_size: float = Field(ge=0)
    estimated_token_total: int = Field(ge=0)
    source_reference_coverage: float = Field(ge=0, le=1)
    chunks_with_no_source_references: int = Field(ge=0)
    associated_tables: int = Field(ge=0)
    unassociated_tables: int = Field(ge=0)
    associated_assets: int = Field(ge=0)
    unassociated_assets: int = Field(ge=0)
    duplicate_chunk_count: int = Field(ge=0)
    warnings_count: int = Field(ge=0)
    errors_count: int = Field(ge=0)
    eligible_for_generation: int = Field(default=0, ge=0)
    excluded_from_generation: int = Field(default=0, ge=0)
    generation_exclusion_reasons: dict[str, int] = Field(default_factory=dict)


class ChunkCollection(CanonicalModel):
    schema_version: Literal["1.0.0"] = CHUNK_SCHEMA_VERSION
    document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_relative_path: str
    document_type: DocumentType
    document_title: str | None = None
    chunking_configuration: ChunkingConfiguration
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    chunk_count: int = Field(ge=0)
    chunks: list[DocumentChunk]
    tables: list[NormalizedTable] = Field(default_factory=list)
    assets: list[NormalizedAsset] = Field(default_factory=list)
    excluded_blocks: list[ExcludedBlock] = Field(default_factory=list)
    exact_duplicates: list[ExactDuplicate] = Field(default_factory=list)
    unassociated_table_ids: list[str] = Field(default_factory=list)
    unassociated_asset_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    processing_statistics: ProcessingStatistics

    @model_validator(mode="after")
    def validate_collection(self) -> ChunkCollection:
        if self.chunk_count != len(self.chunks):
            raise ValueError("chunk_count does not match chunks")
        chunk_ids = [chunk.chunk_id for chunk in self.chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("chunk collection contains duplicate chunk IDs")
        if any(chunk.document_id != self.document_id for chunk in self.chunks):
            raise ValueError("chunk belongs to another document")
        if [chunk.chunk_index for chunk in self.chunks] != list(range(len(self.chunks))):
            raise ValueError("chunk indexes must be contiguous and ordered")
        known_chunks = set(chunk_ids)
        known_tables = {table.table_id for table in self.tables}
        known_assets = {asset.asset_id for asset in self.assets}
        if any(
            table_id not in known_tables for chunk in self.chunks for table_id in chunk.table_ids
        ):
            raise ValueError("chunk references a table absent from the collection")
        if any(
            asset_id not in known_assets for chunk in self.chunks for asset_id in chunk.asset_ids
        ):
            raise ValueError("chunk references an asset absent from the collection")
        if not set(self.unassociated_table_ids).issubset(known_tables):
            raise ValueError("unassociated table ID is absent from the collection")
        if not set(self.unassociated_asset_ids).issubset(known_assets):
            raise ValueError("unassociated asset ID is absent from the collection")
        if any(
            duplicate.canonical_chunk_id not in known_chunks for duplicate in self.exact_duplicates
        ):
            raise ValueError("duplicate relationship references a missing canonical chunk")
        duplicate_ids = [duplicate.duplicate_chunk_id for duplicate in self.exact_duplicates]
        if len(duplicate_ids) != len(set(duplicate_ids)) or known_chunks.intersection(
            duplicate_ids
        ):
            raise ValueError("duplicate chunk relationships are inconsistent")
        if self.processing_statistics.total_chunks != self.chunk_count:
            raise ValueError("processing statistics do not match chunk count")
        if (
            self.processing_statistics.included_blocks + self.processing_statistics.excluded_blocks
            != self.processing_statistics.total_canonical_blocks
        ):
            raise ValueError("block statistics do not account for every canonical block")
        if (
            self.processing_statistics.associated_tables
            + self.processing_statistics.unassociated_tables
            != len(self.tables)
        ):
            raise ValueError("table statistics do not match collection")
        if (
            self.processing_statistics.associated_assets
            + self.processing_statistics.unassociated_assets
            != len(self.assets)
        ):
            raise ValueError("asset statistics do not match collection")
        return self


class ChunkingReport(CanonicalModel):
    schema_version: Literal["1.0.0"] = CHUNK_SCHEMA_VERSION
    chunker_version: Literal["1.0.0"] = CHUNKER_VERSION
    start_time: datetime
    completion_time: datetime
    status: Literal["success", "partial_success"]
    configuration: ChunkingConfiguration
    statistics: ProcessingStatistics
    exclusions: list[ExcludedBlock]
    exact_duplicates: list[ExactDuplicate]
    unassociated_table_ids: list[str]
    unassociated_asset_ids: list[str]
    warnings: list[str]
    errors: list[str]
    output_paths: list[str]
