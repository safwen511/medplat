"""Typed data contracts for deterministic mirrored text exports."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TEXT_EXPORT_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
SUPPORTED_TEXT_EXPORT_EXTENSIONS = frozenset({".pdf", ".pptx", ".docx", ".txt"})


class TextExportModel(BaseModel):
    """Strict base model for persisted text-export artifacts."""

    model_config = ConfigDict(extra="forbid")


class ExportStatus(str, Enum):
    """Terminal and planning states for one discovered source."""

    PLANNED = "planned"
    EXPORTED = "exported"
    EXPORTED_WITH_WARNINGS = "exported_with_warnings"
    SKIPPED_CURRENT = "skipped_current"
    UNSUPPORTED = "unsupported"
    REQUIRES_OCR = "requires_ocr"
    EMPTY = "empty"
    FAILED = "failed"


class TextExportConfiguration(BaseModel):
    """Validated runtime configuration for one text-tree run."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    input_root: Path = Path("yahyaouisalsa")
    output_root: Path = Path("data/yahyaouisalsa-text")
    report_output_root: Path = Path("data/reports/yahyaouisalsa-text")
    docling_artifacts_path: Path | None = None
    derived_root: Path = Path("data/derived")
    resume: bool = False
    overwrite: bool = False
    dry_run: bool = False
    limit: int | None = Field(default=None, ge=1)
    extensions: tuple[str, ...] = tuple(sorted(SUPPORTED_TEXT_EXPORT_EXTENSIONS))
    jobs: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_options(self) -> TextExportConfiguration:
        if self.jobs != 1:
            raise ValueError("Text-tree extraction is sequential; --jobs must be 1.")
        if self.resume and self.overwrite:
            raise ValueError("--resume and --overwrite cannot be used together.")
        normalized: list[str] = []
        for raw in self.extensions:
            extension = raw.strip().casefold()
            if not extension:
                raise ValueError("--extensions values must not be empty.")
            if not extension.startswith("."):
                extension = f".{extension}"
            if extension not in SUPPORTED_TEXT_EXPORT_EXTENSIONS:
                raise ValueError(f"Unsupported requested extension: {extension}")
            if extension not in normalized:
                normalized.append(extension)
        if not normalized:
            raise ValueError("Select at least one supported extension.")
        self.extensions = tuple(sorted(normalized))
        return self


class TextExportEntry(TextExportModel):
    """Manifest state for one discovered regular source file."""

    source_relative_path: str
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_size_bytes: int = Field(ge=0)
    extension: str
    output_relative_path: str | None = None
    export_status: ExportStatus
    extraction_tool: str | None = None
    text_character_count: int = Field(default=0, ge=0)
    page_or_slide_count: int | None = Field(default=None, ge=0)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    export_identity: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    output_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class TextExportManifest(TextExportModel):
    """Deterministically ordered state for the complete source tree."""

    schema_version: Literal["1.0.0"] = TEXT_EXPORT_SCHEMA_VERSION
    run_id: str = Field(pattern=r"^[0-9a-f]{24}$")
    generated_at: datetime
    input_root: str
    output_root: str
    entries: list[TextExportEntry]


class SourceChange(TextExportModel):
    """One source-tree mutation observed during a run."""

    source_relative_path: str
    change: Literal["added", "removed", "modified", "directory_added", "directory_removed"]


class TextTreeRunReport(TextExportModel):
    """Concise aggregate report for one extraction or dry-run plan."""

    schema_version: Literal["1.0.0"] = TEXT_EXPORT_SCHEMA_VERSION
    run_id: str = Field(pattern=r"^[0-9a-f]{24}$")
    started_at: datetime
    completed_at: datetime
    duration_seconds: float = Field(ge=0)
    dry_run: bool
    input_root: str
    output_root: str
    report_output_root: str
    discovered_count: int = Field(ge=0)
    supported_count: int = Field(ge=0)
    planned_count: int = Field(ge=0)
    exported_count: int = Field(ge=0)
    exported_with_warnings_count: int = Field(ge=0)
    skipped_current_count: int = Field(ge=0)
    requires_ocr_count: int = Field(ge=0)
    unsupported_count: int = Field(ge=0)
    empty_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    proposed_text_output_count: int = Field(ge=0)
    collision_count: int = Field(ge=0)
    total_source_bytes: int = Field(ge=0)
    total_exported_characters: int = Field(ge=0)
    source_immutable: bool
    source_changes: list[SourceChange] = Field(default_factory=list)
