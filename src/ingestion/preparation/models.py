"""Strict artifacts for clean and contextually reconstructed course text."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PREPARATION_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
CLEANING_VERSION = "medplat-course-cleaning-v2"
RECONSTRUCTION_VERSION = "medplat-course-reconstruction-v5"
PROMPT_VERSION = "medplat-course-reconstruction-plan-prompt-v2"


class PreparationModel(BaseModel):
    """Forbid accidental persistence of undeclared preparation fields."""

    model_config = ConfigDict(extra="forbid")


class LocationMarkerMode(str, Enum):
    KEEP = "keep"
    COMPACT = "compact"
    REMOVE = "remove"


class ReadinessStatus(str, Enum):
    READY = "ready"
    READY_WITH_NOISE = "ready_with_noise"
    PARTIALLY_RECONSTRUCTABLE = "partially_reconstructable"
    IMAGE_DEPENDENT = "image_dependent"
    UNUSABLE = "unusable"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class PreparationStatus(str, Enum):
    CLEANED = "cleaned"
    CLEANED_WITH_WARNINGS = "cleaned_with_warnings"
    RECONSTRUCTED = "reconstructed"
    RECONSTRUCTED_WITH_WARNINGS = "reconstructed_with_warnings"
    UNCHANGED_CLEAN = "unchanged_clean"
    IMAGE_DEPENDENT = "image_dependent"
    PARTIALLY_RECONSTRUCTABLE = "partially_reconstructable"
    UNUSABLE = "unusable"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    MODEL_UNAVAILABLE = "model_unavailable"
    MODEL_FAILURE = "model_failure"
    VALIDATION_FAILURE = "validation_failure"
    SKIPPED_CURRENT = "skipped_current"
    FAILED = "failed"


class TransformationType(str, Enum):
    PARAGRAPH_REASSEMBLY = "paragraph_reassembly"
    HEADING_RECONSTRUCTION = "heading_reconstruction"
    BULLET_REORGANIZATION = "bullet_reorganization"
    TABLE_REORGANIZATION = "table_reorganization"
    DUPLICATE_SUPPRESSION = "duplicate_suppression"
    SPLIT_WORD_REPAIR = "split_word_repair"
    FRAGMENT_REPAIR = "fragment_repair"
    METADATA_CLASSIFICATION = "metadata_classification"
    IMAGE_DEPENDENCY_ANNOTATION = "image_dependency_annotation"


class MetadataClass(str, Enum):
    COURSE_TITLE = "course_title"
    TEACHER_NAME = "teacher_name"
    INSTITUTION = "institution"
    ACADEMIC_YEAR = "academic_year"
    REPEATED_HEADER = "repeated_header"
    REPEATED_FOOTER = "repeated_footer"
    BODY_CONTENT = "body_content"
    UNCERTAIN_METADATA = "uncertain_metadata"


class ReviewVerdict(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"
    POSSIBLE_EXTRACTION_ERROR = "possible_extraction_error"
    EXTERNAL_MEDICAL_OBSERVATION = "external_medical_observation"


class PreparationConfiguration(BaseModel):
    """Validated configuration for a sequential complete-tree preparation run."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    input_root: Path = Path("data/yahyaouisalsa-text")
    clean_output_root: Path = Path("data/yahyaouisalsa-clean")
    reconstructed_output_root: Path = Path("data/yahyaouisalsa-reconstructed")
    report_output_root: Path = Path("data/reports/yahyaouisalsa-preparation")
    file: Path | None = None
    limit: int | None = Field(default=None, ge=1)
    dry_run: bool = False
    resume: bool = False
    overwrite: bool = False
    generator_model: str = "gemma3:12b"
    reviewer_model: str | None = "auto-medgemma-4b"
    disable_model_reconstruction: bool = False
    disable_medgemma_review: bool = False
    location_markers: LocationMarkerMode = LocationMarkerMode.COMPACT
    context_budget: int = Field(default=8192, ge=4096, le=32768)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    seed: int = 42
    timeout_seconds: float = Field(default=300.0, gt=0)
    maximum_retries: int = Field(default=2, ge=0, le=10)
    jobs: int = Field(default=1, ge=1)
    ollama_base_url: str = "http://127.0.0.1:11434"

    @model_validator(mode="after")
    def validate_options(self) -> PreparationConfiguration:
        if self.jobs != 1:
            raise ValueError("Course-text preparation is sequential; --jobs must be 1.")
        if self.resume and self.overwrite:
            raise ValueError("--resume and --overwrite cannot be used together.")
        if self.file is not None and self.file.is_absolute():
            raise ValueError("--file must be a source-relative path below --input.")
        if self.file is not None and ".." in self.file.parts:
            raise ValueError("--file cannot traverse outside --input.")
        return self


class ModelIdentity(PreparationModel):
    tag: str
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    parameter_size: str | None = None
    quantization: str | None = None


class SourceSpan(PreparationModel):
    span_id: str = Field(pattern=r"^span-[0-9]{6}$")
    location_id: str = Field(pattern=r"^location-[0-9]{6}$")
    location_type: Literal["page", "slide", "document", "source"]
    location_number: int | None = Field(default=None, ge=1)
    raw_start: int = Field(ge=0)
    raw_end: int = Field(ge=0)
    cleaned_start: int = Field(ge=0)
    cleaned_end: int = Field(ge=0)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    classification: MetadataClass = MetadataClass.BODY_CONTENT
    retained: bool = True

    @model_validator(mode="after")
    def validate_offsets(self) -> SourceSpan:
        if self.raw_end < self.raw_start or self.cleaned_end < self.cleaned_start:
            raise ValueError("Span offsets must be ordered.")
        return self


class LocationReadiness(PreparationModel):
    location_id: str
    location_type: Literal["page", "slide", "document", "source"]
    location_number: int | None = None
    raw_character_count: int = Field(ge=0)
    cleaned_character_count: int = Field(ge=0)
    alphabetic_ratio: float = Field(ge=0.0, le=1.0)
    duplicate_burden: int = Field(ge=0)
    status: ReadinessStatus
    reason_codes: list[str] = Field(default_factory=list)
    model_eligible: bool


class DeterministicTransformation(PreparationModel):
    transformation_id: str
    transformation_type: TransformationType
    raw_span_ids: list[str]
    original_text: str
    cleaned_text: str
    reason: str


class CleaningSidecar(PreparationModel):
    schema_version: Literal["1.0.0"] = PREPARATION_SCHEMA_VERSION
    cleaning_version: str = CLEANING_VERSION
    cleaning_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_relative_path: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_extracted_text_relative_path: str
    raw_extracted_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cleaned_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text_export_schema_version: str
    extraction_status: str
    extraction_tool: str
    document_type: str
    exported_at: str
    location_markers: LocationMarkerMode
    metadata_header: dict[str, str]
    detected_language: str
    detected_title: str | None = None
    teacher_names: list[str] = Field(default_factory=list)
    institutions: list[str] = Field(default_factory=list)
    academic_years: list[str] = Field(default_factory=list)
    spans: list[SourceSpan]
    transformations: list[DeterministicTransformation]
    removed_duplicates: list[str] = Field(default_factory=list)
    retained_duplicates: list[str] = Field(default_factory=list)
    repeated_headers: list[str] = Field(default_factory=list)
    repeated_footers: list[str] = Field(default_factory=list)
    readiness_status: ReadinessStatus
    location_readiness: list[LocationReadiness]
    warnings: list[str] = Field(default_factory=list)
    cleaned_character_count: int = Field(ge=0)


class ModelTransformation(PreparationModel):
    transformation_id: str
    transformation_type: TransformationType
    raw_span_ids: list[str]
    cleaned_span_ids: list[str]
    original_text: str
    reconstructed_text: str
    support_basis: str
    confidence: float = Field(ge=0.0, le=1.0)
    model_identity: ModelIdentity
    validation_status: Literal["accepted", "rejected", "needs_human_review"]


class ReviewerFinding(PreparationModel):
    transformation_id: str | None = None
    verdict: ReviewVerdict
    source_span_ids: list[str]
    message: str


class ValidationIssue(PreparationModel):
    code: str
    message: str
    severity: Literal["warning", "error"]
    section_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class SectionState(PreparationModel):
    section_id: str
    span_ids: list[str]
    source_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: PreparationStatus
    generator_attempt_count: int = Field(ge=0)
    reviewer_attempt_count: int = Field(ge=0)
    runtime_seconds: float = Field(ge=0.0)
    reconstructed_start: int = Field(default=0, ge=0)
    reconstructed_end: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_reconstructed_offsets(self) -> SectionState:
        if self.reconstructed_end < self.reconstructed_start:
            raise ValueError("Reconstructed section offsets must be ordered.")
        return self


class ReconstructionPlanGroup(PreparationModel):
    group_id: str
    transformation_type: TransformationType | None = None
    span_ids: list[str] = Field(min_length=1)
    join_with: Literal["space", "line", "blank_line"]
    support_basis: str
    confidence: float = Field(ge=0.0, le=1.0)


class ReconstructionDraft(PreparationModel):
    groups: list[ReconstructionPlanGroup] = Field(min_length=1)
    unresolved_span_ids: list[str]
    image_dependency_span_ids: list[str]


class ReviewDraftFinding(PreparationModel):
    transformation_id: str | None = None
    verdict: ReviewVerdict
    source_span_ids: list[str]
    message: str


class ReviewDraft(PreparationModel):
    findings: list[ReviewDraftFinding]


class ReconstructionSidecar(PreparationModel):
    schema_version: Literal["1.0.0"] = PREPARATION_SCHEMA_VERSION
    reconstruction_version: str = RECONSTRUCTION_VERSION
    reconstruction_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_relative_path: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_extracted_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cleaned_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reconstructed_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generator_model: ModelIdentity | None = None
    reviewer_model: ModelIdentity | None = None
    ollama_version: str | None = None
    prompt_version: str = PROMPT_VERSION
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_status: ReadinessStatus
    detected_language: str
    detected_title: str | None = None
    teacher_names: list[str] = Field(default_factory=list)
    institutions: list[str] = Field(default_factory=list)
    deterministic_transformations: list[DeterministicTransformation]
    model_transformations: list[ModelTransformation]
    repaired_fragments: list[str] = Field(default_factory=list)
    unresolved_fragments: list[str] = Field(default_factory=list)
    removed_duplicates: list[str] = Field(default_factory=list)
    retained_duplicates: list[str] = Field(default_factory=list)
    image_dependent_locations: list[str] = Field(default_factory=list)
    reviewer_findings: list[ReviewerFinding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    sections: list[SectionState]
    runtime_seconds: float = Field(ge=0.0)
    retry_count: int = Field(ge=0)
    final_status: PreparationStatus


class PreparationManifestEntry(PreparationModel):
    source_relative_path: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_relative_path: str
    sidecar_relative_path: str
    status: PreparationStatus
    readiness_status: ReadinessStatus | None = None
    artifact_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    sidecar_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    character_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    error: str | None = None


class PreparationManifest(PreparationModel):
    schema_version: Literal["1.0.0"] = PREPARATION_SCHEMA_VERSION
    kind: Literal["cleaning", "reconstruction"]
    run_id: str = Field(pattern=r"^[0-9a-f]{24}$")
    generated_at: datetime
    input_root: str
    output_root: str
    entries: list[PreparationManifestEntry]


class PreparationRunReport(PreparationModel):
    schema_version: Literal["1.0.0"] = PREPARATION_SCHEMA_VERSION
    run_id: str = Field(pattern=r"^[0-9a-f]{24}$")
    started_at: datetime
    completed_at: datetime
    dry_run: bool
    input_root: str
    clean_output_root: str
    reconstructed_output_root: str
    report_output_root: str
    total_raw_text_files: int = Field(ge=0)
    total_cleaned_files: int = Field(ge=0)
    total_reconstructed_files: int = Field(ge=0)
    status_counts: dict[str, int]
    readiness_counts: dict[str, int]
    files_with_metadata_removed: int = Field(ge=0)
    duplicate_blocks_suppressed: int = Field(ge=0)
    split_words_repaired: int = Field(ge=0)
    fragment_repairs: int = Field(ge=0)
    suspicious_additions_rejected: int = Field(ge=0)
    cleaning_duration_seconds: float = Field(ge=0.0)
    readiness_duration_seconds: float = Field(ge=0.0)
    reconstruction_duration_seconds: float = Field(ge=0.0)
    total_duration_seconds: float = Field(ge=0.0)
    generator_model: ModelIdentity | None = None
    reviewer_model: ModelIdentity | None = None
    ollama_version: str | None = None
    hardware_usage: dict[str, Any] = Field(default_factory=dict)
    source_immutable: bool
    source_changes: list[str] = Field(default_factory=list)
    no_study_material_generated: bool = True


class PreparationRunResult(PreparationModel):
    cleaning_manifest: PreparationManifest
    reconstruction_manifest: PreparationManifest
    report: PreparationRunReport
    report_directory: Path | None = None
