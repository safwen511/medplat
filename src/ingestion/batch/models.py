"""Versioned schemas for deterministic batch plans, state, and reports."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from ingestion.normalization.models import CanonicalModel

BATCH_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
SAFE_BATCH_LIMIT = 10


class SelectionMode(str, Enum):
    ORDERED = "ordered"
    REPRESENTATIVE = "representative"


class ParserRoute(str, Enum):
    PDF = "pdf"
    PPTX = "pptx"
    DOCX = "docx"
    UNSUPPORTED = "unsupported"


class OCRRoute(str, Enum):
    NONE = "none"
    DISABLED = "disabled"
    SAFE_FIRST = "safe_first"
    SAFE_THEN_FORCE_ALLOWED = "safe_then_force_allowed"


class BatchStage(str, Enum):
    DISCOVERED = "discovered"
    INSPECTED = "inspected"
    PARSED = "parsed"
    CANONICAL_VALIDATED = "canonical_validated"
    DERIVATIVE_CREATED = "derivative_created"
    DERIVATIVE_VALIDATED = "derivative_validated"
    CHUNKS_BUILT = "chunks_built"
    CHUNKS_VALIDATED = "chunks_validated"
    DATASET_BUILT = "dataset_built"
    DATASET_VALIDATED = "dataset_validated"
    COMPLETE = "complete"


class BatchDocumentStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    SUCCEEDED_WITH_WARNINGS = "succeeded_with_warnings"
    REQUIRES_OCR = "requires_ocr"
    SKIPPED = "skipped"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class BatchConfiguration(CanonicalModel):
    input_root: Path
    output_root: Path = Path("data/processed")
    derived_output_root: Path = Path("data/derived")
    reports_root: Path = Path("data/reports/batches")
    limit: int | None = Field(default=None, ge=1)
    jobs: int = Field(default=1, ge=1)
    resume: bool = True
    retry_failures: bool = False
    maximum_retries: int = Field(default=1, ge=0, le=10)
    dry_run: bool = False
    force_rebuild: bool = False
    ocr_enabled: bool = False
    ocr_languages: list[str] = Field(default_factory=list)
    allow_force_ocr: bool = False
    parser_timeout_seconds: int = Field(default=900, ge=1)
    ocr_timeout_seconds: int = Field(default=300, ge=1)
    continue_on_error: bool = True
    manifest_path: Path | None = None
    include_extensions: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    maximum_source_file_size: int | None = Field(default=None, ge=1)
    selection: SelectionMode = SelectionMode.ORDERED
    allow_full_library: bool = False
    allow_large_batch: bool = False

    @model_validator(mode="after")
    def validate_safe_configuration(self) -> BatchConfiguration:
        if self.jobs != 1:
            raise ValueError(
                "This milestone supports only --jobs 1; run sequentially or wait for "
                "process-isolated concurrency support."
            )
        if self.limit is None and not self.allow_full_library:
            raise ValueError("A --limit is required unless --allow-full-library is explicit.")
        if self.limit is not None and self.limit > SAFE_BATCH_LIMIT and not self.allow_large_batch:
            raise ValueError(
                f"Limits above {SAFE_BATCH_LIMIT} require explicit --allow-large-batch."
            )
        if self.ocr_enabled and not self.ocr_languages:
            raise ValueError("--ocr-languages is required when --enable-ocr is supplied.")
        if self.allow_force_ocr and not self.ocr_enabled:
            raise ValueError("--allow-force-ocr requires --enable-ocr.")
        self.include_extensions = sorted(
            {
                value.lower() if value.startswith(".") else f".{value.lower()}"
                for value in self.include_extensions
            }
        )
        self.ocr_languages = list(
            dict.fromkeys(language.lower() for language in self.ocr_languages)
        )
        return self


class ExistingOutputState(CanonicalModel):
    canonical_path: str | None = None
    chunk_path: str | None = None
    dataset_path: str | None = None
    derivative_path: str | None = None
    last_valid_stage: BatchStage = BatchStage.INSPECTED
    complete: bool = False
    suitability: str | None = None
    generation_ready: bool = False
    validation_warnings: list[str] = Field(default_factory=list)


class PlannedDocument(CanonicalModel):
    sequence_number: int = Field(ge=1)
    source_relative_path: str
    extension: str
    mime_type: str | None = None
    file_size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    inspection_classification: str
    parser_route: ParserRoute
    ocr_route: OCRRoute
    current_output_state: ExistingOutputState
    planned_actions: list[str] = Field(default_factory=list)
    skip_reason: str | None = None
    retry_eligible: bool = False


class BatchPlan(CanonicalModel):
    schema_version: Literal["1.0.0"] = BATCH_SCHEMA_VERSION
    batch_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_root: str
    output_root: str
    derived_output_root: str
    manifest_path: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    configuration: BatchConfiguration
    deterministic_document_order: list[str]
    selected_document_count: int = Field(ge=0)
    skipped_document_count: int = Field(ge=0)
    documents: list[PlannedDocument]
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class BatchFailure(CanonicalModel):
    source_relative_path: str
    sequence_number: int
    stage: BatchStage
    error_category: str
    message: str
    diagnostic: str | None = None
    retryable: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    existing_valid_artifacts: list[str] = Field(default_factory=list)
    next_recommended_action: str


class DocumentBatchState(CanonicalModel):
    sequence_number: int
    source_relative_path: str
    source_sha256: str
    status: BatchDocumentStatus = BatchDocumentStatus.PLANNED
    last_completed_stage: BatchStage = BatchStage.INSPECTED
    stages_completed: list[BatchStage] = Field(
        default_factory=lambda: [BatchStage.DISCOVERED, BatchStage.INSPECTED]
    )
    retry_count: int = Field(default=0, ge=0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    failure: BatchFailure | None = None


class BatchState(CanonicalModel):
    schema_version: Literal["1.0.0"] = BATCH_SCHEMA_VERSION
    batch_id: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    documents: list[DocumentBatchState]


class DocumentBatchReport(CanonicalModel):
    sequence_number: int
    source_relative_path: str
    source_sha256: str
    extension: str
    classification: str
    parser_route: ParserRoute
    ocr_route: OCRRoute
    planned_actions: list[str]
    stages_completed: list[BatchStage]
    final_status: BatchDocumentStatus
    suitability: str | None = None
    generation_ready: bool = False
    canonical_output_path: str | None = None
    derivative_path: str | None = None
    chunk_path: str | None = None
    dataset_path: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    durations_by_stage: dict[str, float] = Field(default_factory=dict)
    retries: int = 0
    skipped_reason: str | None = None
    eligible_chunk_count: int | None = None
    excluded_chunk_count: int | None = None
    safe_ocr_attempted: bool = False
    safe_ocr_accepted: bool = False
    force_ocr_attempted: bool = False
    force_ocr_accepted: bool = False


class BatchReport(CanonicalModel):
    schema_version: Literal["1.0.0"] = BATCH_SCHEMA_VERSION
    batch_id: str
    run_id: str
    configuration: BatchConfiguration
    start_time: datetime
    completion_time: datetime
    duration_seconds: float = Field(ge=0)
    selected_count: int
    processed_count: int
    complete_count: int
    complete_with_warnings_count: int
    skipped_count: int
    already_complete_count: int
    unsupported_count: int
    requires_ocr_count: int
    ocr_attempted_count: int
    safe_ocr_accepted_count: int
    force_ocr_attempted_count: int
    force_ocr_accepted_count: int
    failed_count: int
    interrupted_count: int
    counts_by_source_extension: dict[str, int]
    counts_by_parser_route: dict[str, int]
    counts_by_suitability: dict[str, int]
    counts_by_final_stage: dict[str, int]
    total_source_bytes: int
    total_processing_time: float
    documents: list[DocumentBatchReport]
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
