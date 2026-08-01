"""Versioned schemas for local OCR decisions and derivatives."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import Field, model_validator

from ingestion.normalization.models import CanonicalModel

DERIVATIVE_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"


class OCREligibility(str, Enum):
    NOT_NEEDED = "ocr_not_needed"
    RECOMMENDED = "ocr_recommended"
    REQUIRED = "ocr_required"
    NOT_SUPPORTED = "ocr_not_supported"
    BLOCKED = "ocr_blocked"
    FAILED = "ocr_failed"
    COMPLETED = "ocr_completed"


class OCRQualityOutcome(str, Enum):
    ACCEPTED = "accepted"
    ACCEPTED_WITH_WARNINGS = "accepted_with_warnings"
    NO_MATERIAL_IMPROVEMENT = "no_material_improvement"
    DEGRADED = "degraded"
    INVALID = "invalid"
    FAILED = "failed"


class OCRSuitability(str, Enum):
    READY_FOR_CHUNKING = "ready_for_chunking"
    READY_WITH_WARNINGS = "ready_with_warnings"
    REQUIRES_OCR = "requires_ocr"
    UNSUITABLE = "unsuitable"
    FAILED = "failed"


class OCRConfiguration(CanonicalModel):
    language_codes: list[str]
    deskew: bool = False
    rotate_pages: bool = False
    clean: bool = False
    force_ocr: bool = False
    skip_text: bool = True
    timeout_seconds: int = Field(default=300, ge=1)
    jobs: int = Field(default=1, ge=1, le=4)
    output_type: Literal["pdf"] = "pdf"
    optimization_level: Literal[0] = 0

    @model_validator(mode="after")
    def validate_configuration(self) -> OCRConfiguration:
        allowed = {"fra", "eng", "ara", "deu"}
        if not self.language_codes:
            raise ValueError("At least one OCR language is required.")
        if len(self.language_codes) != len(set(self.language_codes)):
            raise ValueError("OCR languages must not contain duplicates.")
        invalid = sorted(set(self.language_codes) - allowed)
        if invalid:
            raise ValueError(f"Unsupported OCR language codes: {', '.join(invalid)}")
        if self.force_ocr and self.skip_text:
            raise ValueError("--force-ocr and --skip-text are mutually exclusive.")
        return self


class OCREnvironmentReport(CanonicalModel):
    ready: bool
    ocrmypdf_version: str | None = None
    tesseract_version: str | None = None
    qpdf_version: str | None = None
    ghostscript_version: str | None = None
    installed_languages: list[str] = Field(default_factory=list)
    requested_languages: list[str] = Field(default_factory=list)
    missing_tools: list[str] = Field(default_factory=list)
    missing_languages: list[str] = Field(default_factory=list)
    derivative_output_writable: bool = False
    source_library_policy: str
    ocr_default_state: Literal["explicit_only"] = "explicit_only"
    warnings: list[str] = Field(default_factory=list)


class OCREvaluation(CanonicalModel):
    eligibility: OCREligibility
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_relative_path: str
    page_count: int | None = Field(default=None, ge=0)
    total_extractable_characters: int | None = Field(default=None, ge=0)
    text_characters_by_page: list[int] = Field(default_factory=list)
    low_text_pages: list[int] = Field(default_factory=list)
    image_heavy_pages: list[int] = Field(default_factory=list)
    image_count: int = Field(default=0, ge=0)
    encrypted: bool | None = None
    reason: str
    language_input_required: bool = True


class OCRQualityMetrics(CanonicalModel):
    source_text_character_count: int = Field(ge=0)
    derivative_text_character_count: int = Field(ge=0)
    source_text_characters_by_page: list[int]
    derivative_text_characters_by_page: list[int]
    low_text_pages_before: list[int]
    low_text_pages_after: list[int]
    image_heavy_pages: list[int]
    percentage_improvement: float | None = None
    page_count_equal: bool
    derivative_pdf_valid: bool
    physical_page_mapping_preserved: bool
    canonical_blocks_before: int | None = Field(default=None, ge=0)
    canonical_blocks_after: int | None = Field(default=None, ge=0)
    material_improvement_minimum_characters: int = 50
    material_improvement_minimum_percent: float = 25.0
    meaningful_text_retention_ratio: float = 0.9


class SourceRelationship(CanonicalModel):
    relationship_type: Literal["ocr_derivative_of"] = "ocr_derivative_of"
    original_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    original_source_relative_path: str
    page_mapping: Literal["identity_1_based"] = "identity_1_based"


class DocumentDerivative(CanonicalModel):
    schema_version: Literal["1.0.0"] = DERIVATIVE_SCHEMA_VERSION
    derivative_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivation_type: Literal["ocr_pdf"] = "ocr_pdf"
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_relative_path: str
    source_filename: str
    source_size_bytes: int = Field(ge=0)
    derivative_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivative_relative_path: str
    derivative_size_bytes: int = Field(ge=0)
    created_at: datetime
    tool_name: Literal["OCRmyPDF"] = "OCRmyPDF"
    tool_version: str
    configuration: OCRConfiguration
    language_codes: list[str]
    page_count: int = Field(ge=0)
    source_relationship: SourceRelationship
    validation_status: OCRQualityOutcome
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OCRProcessingReport(CanonicalModel):
    schema_version: Literal["1.0.0"] = DERIVATIVE_SCHEMA_VERSION
    derivative_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    start_time: datetime
    completion_time: datetime
    duration_seconds: float = Field(ge=0)
    source_file: str
    output_file: str
    ocrmypdf_version: str
    tesseract_version: str
    requested_languages: list[str]
    installed_language_validation: bool
    source_page_count: int = Field(ge=0)
    derivative_page_count: int = Field(ge=0)
    source_text_character_count: int = Field(ge=0)
    derivative_text_character_count: int = Field(ge=0)
    source_text_characters_by_page: list[int]
    derivative_text_characters_by_page: list[int]
    low_text_pages_before: list[int]
    low_text_pages_after: list[int]
    image_heavy_pages: list[int]
    skipped_pages: list[int]
    rotated_pages: list[int]
    deskew_enabled: bool
    clean_enabled: bool
    force_ocr_enabled: bool
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    return_code: int
    quality_decision: OCRQualityOutcome
    suitability_status: OCRSuitability
    quality_metrics: OCRQualityMetrics
    output_paths: list[str]
