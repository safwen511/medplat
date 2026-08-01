"""Pydantic models shared by scanners, parsers, and report writers."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DocumentClassification(str, Enum):
    """Inspection outcomes supported by the first milestone."""

    NATIVE_TEXT = "native_text"
    MIXED = "mixed"
    LIKELY_SCANNED = "likely_scanned"
    ENCRYPTED = "encrypted"
    UNREADABLE = "unreadable"
    UNSUPPORTED_FOR_NOW = "unsupported_for_now"


class ParsingEligibility(str, Enum):
    """Whether structured parsing is available in the current milestone."""

    SUPPORTED = "supported"
    UNSUPPORTED_FOR_PARSING = "unsupported_for_parsing"


class ErrorInformation(BaseModel):
    """A serializable error that does not interrupt a library scan."""

    model_config = ConfigDict(extra="forbid")

    error_type: str
    message: str


class FileMetadata(BaseModel):
    """Format-independent metadata collected before parsing."""

    model_config = ConfigDict(extra="forbid")

    relative_path: str
    filename: str
    extension: str
    detected_type: str
    mime_type: str | None = None
    file_size: int | None = None
    sha256: str | None = None


class DocumentInspection(FileMetadata):
    """One document's normalized inspection result."""

    readable: bool
    encrypted: bool | None = None
    page_count: int | None = None
    slide_count: int | None = None
    worksheet_count: int | None = None
    image_count: int | None = None
    extractable_character_count: int | None = None
    average_characters_per_page_or_slide: float | None = None
    classification: DocumentClassification
    parsing_eligibility: ParsingEligibility = ParsingEligibility.UNSUPPORTED_FOR_PARSING
    ocr_recommended: bool | None = None
    error: ErrorInformation | None = None


class DuplicateGroup(BaseModel):
    """Files sharing the same SHA-256 digest."""

    model_config = ConfigDict(extra="forbid")

    sha256: str
    file_size: int
    relative_paths: list[str]


class LibraryReport(BaseModel):
    """Top-level JSON manifest for an inspected library."""

    model_config = ConfigDict(extra="forbid")

    input_root: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    discovered_count: int
    inspected_count: int
    documents: list[DocumentInspection]


class ErrorReportEntry(BaseModel):
    """Flattened failed-document entry for inspection-errors.json."""

    model_config = ConfigDict(extra="forbid")

    relative_path: str
    error: ErrorInformation
