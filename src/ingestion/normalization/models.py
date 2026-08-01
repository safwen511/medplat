"""Versioned canonical schemas for all structured source formats."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"


class CanonicalModel(BaseModel):
    """Strict base class used by every persisted canonical model."""

    model_config = ConfigDict(extra="forbid")


class DocumentType(str, Enum):
    PDF = "pdf"
    POWERPOINT = "powerpoint"
    WORD = "word"


class LocationType(str, Enum):
    PAGE = "page"
    SLIDE = "slide"
    DOCUMENT = "document"


class BlockType(str, Enum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"
    FORMULA = "formula"
    CODE = "code"
    FOOTNOTE = "footnote"
    HEADER = "header"
    FOOTER = "footer"
    UNKNOWN = "unknown"


class AssetType(str, Enum):
    IMAGE = "image"
    FIGURE = "figure"
    CHART = "chart"
    UNKNOWN = "unknown"


class ProcessingStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    SKIPPED = "skipped"


class TechnicalSuitability(str, Enum):
    READY_FOR_CHUNKING = "ready_for_chunking"
    READY_WITH_WARNINGS = "ready_with_warnings"
    REQUIRES_OCR = "requires_ocr"
    UNSUITABLE = "unsuitable"
    FAILED = "failed"


class BoundingBox(CanonicalModel):
    left: float
    top: float
    right: float
    bottom: float
    coordinate_origin: str


class SourceReference(CanonicalModel):
    source_relative_path: str
    location_type: LocationType
    page_or_slide_number: int | None = Field(default=None, ge=1)
    block_id: str | None = None
    bounding_box: BoundingBox | None = None
    source_excerpt: str | None = None


class NormalizedBlock(CanonicalModel):
    block_id: str
    block_type: BlockType
    text: str | None = None
    page_or_slide_number: int | None = Field(default=None, ge=1)
    reading_order: int = Field(ge=0)
    bounding_box: BoundingBox | None = None
    parent_section_id: str | None = None
    source_reference: SourceReference
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedSection(CanonicalModel):
    section_id: str
    title: str
    level: int = Field(ge=1)
    parent_section_id: str | None = None
    first_page_or_slide: int | None = Field(default=None, ge=1)
    last_page_or_slide: int | None = Field(default=None, ge=1)
    ordered_block_references: list[str] = Field(default_factory=list)


class NormalizedTableCell(CanonicalModel):
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    row_span: int = Field(default=1, ge=1)
    column_span: int = Field(default=1, ge=1)
    text: str
    is_column_header: bool = False
    is_row_header: bool = False


class NormalizedTable(CanonicalModel):
    table_id: str
    page_or_slide_number: int | None = Field(default=None, ge=1)
    caption: str | None = None
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    cells: list[NormalizedTableCell]
    bounding_box: BoundingBox | None = None
    source_reference: SourceReference
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedAsset(CanonicalModel):
    asset_id: str
    asset_type: AssetType
    source_page_or_slide: int | None = Field(default=None, ge=1)
    original_object_reference: str | None = None
    extracted_relative_path: str | None = None
    caption: str | None = None
    bounding_box: BoundingBox | None = None
    mime_type: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedPage(CanonicalModel):
    number: int | None = Field(default=None, ge=1)
    label: str | None = None
    location_type: LocationType
    width: float | None = Field(default=None, gt=0)
    height: float | None = Field(default=None, gt=0)
    blocks: list[NormalizedBlock] = Field(default_factory=list)
    asset_references: list[str] = Field(default_factory=list)


class ProcessingInformation(CanonicalModel):
    parser_name: str
    parser_version: str | None = None
    normalized_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    warnings: list[str] = Field(default_factory=list)


class NormalizedDocument(CanonicalModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_relative_path: str
    source_filename: str
    source_extension: str
    source_mime_type: str | None = None
    title: str | None = None
    document_type: DocumentType
    language: str | None = None
    page_or_slide_count: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    sections: list[NormalizedSection] = Field(default_factory=list)
    pages: list[NormalizedPage] = Field(default_factory=list)
    tables: list[NormalizedTable] = Field(default_factory=list)
    assets: list[NormalizedAsset] = Field(default_factory=list)
    processing: ProcessingInformation

    @model_validator(mode="after")
    def validate_relationships(self) -> NormalizedDocument:
        expected_location = {
            DocumentType.PDF: LocationType.PAGE,
            DocumentType.POWERPOINT: LocationType.SLIDE,
            DocumentType.WORD: LocationType.DOCUMENT,
        }[self.document_type]
        if any(page.location_type is not expected_location for page in self.pages):
            raise ValueError("page location_type does not match document_type")
        if self.document_type is DocumentType.WORD and any(
            page.number is not None for page in self.pages
        ):
            raise ValueError("DOCX physical page numbers must be null")
        if self.document_type is not DocumentType.WORD and any(
            page.number is None for page in self.pages
        ):
            raise ValueError("PDF pages and PowerPoint slides must be numbered")
        if self.document_type is not DocumentType.WORD and self.page_or_slide_count != len(
            self.pages
        ):
            raise ValueError("page_or_slide_count does not match navigation units")

        blocks = [block for page in self.pages for block in page.blocks]
        block_ids = [block.block_id for block in blocks]
        section_ids = [section.section_id for section in self.sections]
        table_ids = [table.table_id for table in self.tables]
        asset_ids = [asset.asset_id for asset in self.assets]
        for values, label in (
            (block_ids, "block"),
            (section_ids, "section"),
            (table_ids, "table"),
            (asset_ids, "asset"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label} identifiers")
        known_blocks = set(block_ids)
        known_sections = set(section_ids)
        known_assets = set(asset_ids)
        if any(
            reference not in known_blocks
            for section in self.sections
            for reference in section.ordered_block_references
        ):
            raise ValueError("section references an unknown block")
        if any(
            section.parent_section_id not in known_sections
            for section in self.sections
            if section.parent_section_id is not None
        ):
            raise ValueError("section references an unknown parent section")
        if any(
            block.parent_section_id not in known_sections
            for block in blocks
            if block.parent_section_id is not None
        ):
            raise ValueError("block references an unknown section")
        if any(
            reference not in known_assets
            for page in self.pages
            for reference in page.asset_references
        ):
            raise ValueError("page references an unknown asset")
        return self


class ProcessingReport(CanonicalModel):
    parser_name: str
    parser_version: str | None = None
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    start_time: datetime
    completion_time: datetime
    status: ProcessingStatus
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    unsupported_features: list[str] = Field(default_factory=list)
    output_paths: list[str] = Field(default_factory=list)
    model_provenance: dict[str, Any] = Field(default_factory=dict)
    technical_suitability: TechnicalSuitability | None = None


class BatchDocumentResult(CanonicalModel):
    source_relative_path: str
    status: ProcessingStatus
    document_id: str | None = None
    output_directory: str | None = None
    error: str | None = None


class BatchProcessingReport(CanonicalModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    input_root: str
    start_time: datetime
    completion_time: datetime
    selected_relative_paths: list[str]
    results: list[BatchDocumentResult]
