"""Independent versioned schemas for course knowledge coverage."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from ingestion.normalization.models import CanonicalModel, SourceReference

COURSE_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
KNOWLEDGE_UNIT_STRATEGY_VERSION: Literal["qcm-substantive-chunk-v1"] = "qcm-substantive-chunk-v1"


class CoverageStatus(str, Enum):
    PENDING = "pending"
    SELECTED = "selected"
    COVERED_BY_VALID_QCM = "covered_by_valid_qcm"
    NEEDS_REVISION = "needs_revision"
    INSUFFICIENT_FOR_QCM = "insufficient_for_qcm"
    FAILED = "failed"
    EXCLUDED = "excluded"


class CourseDocument(CanonicalModel):
    document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_relative_path: str
    folder_path: list[str]
    filename: str
    document_title: str | None = None
    dataset_path: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_schema_version: str
    eligible_unit_count: int = Field(ge=0)
    excluded_unit_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_identity(self) -> CourseDocument:
        if self.document_id != self.source_sha256:
            raise ValueError("Course document identity must match source SHA-256.")
        return self


class CourseCatalog(CanonicalModel):
    course_schema_version: Literal["1.0.0"] = COURSE_SCHEMA_VERSION
    course_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    knowledge_unit_strategy_version: Literal["qcm-substantive-chunk-v1"] = (
        KNOWLEDGE_UNIT_STRATEGY_VERSION
    )
    course_name: str = Field(min_length=1)
    course_root: str
    taxonomy_labels: list[str]
    document_count: int = Field(ge=1)
    documents: list[CourseDocument] = Field(min_length=1)
    knowledge_unit_count: int = Field(ge=1)
    eligible_unit_count: int = Field(ge=0)
    excluded_unit_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> CourseCatalog:
        if self.document_count != len(self.documents):
            raise ValueError("Course document count does not match documents.")
        if len({document.document_id for document in self.documents}) != len(self.documents):
            raise ValueError("Course contains duplicate documents.")
        if self.knowledge_unit_count != self.eligible_unit_count + self.excluded_unit_count:
            raise ValueError("Course knowledge-unit counts are inconsistent.")
        if self.eligible_unit_count != sum(
            document.eligible_unit_count for document in self.documents
        ):
            raise ValueError("Course eligible-unit count does not match documents.")
        if self.excluded_unit_count != sum(
            document.excluded_unit_count for document in self.documents
        ):
            raise ValueError("Course excluded-unit count does not match documents.")
        return self


class KnowledgeUnit(CanonicalModel):
    course_schema_version: Literal["1.0.0"] = COURSE_SCHEMA_VERSION
    unit_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    course_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_relative_path: str
    folder_path: list[str]
    section_path: list[str]
    taxonomy_path: list[str]
    chunk_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_index: int = Field(ge=0)
    chunk_type: str
    normalized_text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    character_count: int = Field(ge=0)
    token_estimate: int = Field(ge=0)
    source_references: list[SourceReference]
    eligible_for_qcm: bool
    exclusion_reasons: list[str]

    @model_validator(mode="after")
    def validate_unit(self) -> KnowledgeUnit:
        if self.document_id != self.source_sha256:
            raise ValueError("Knowledge-unit document identity must match source SHA-256.")
        if self.eligible_for_qcm and self.exclusion_reasons:
            raise ValueError("Eligible knowledge units cannot have exclusion reasons.")
        if not self.eligible_for_qcm and not self.exclusion_reasons:
            raise ValueError("Excluded knowledge units require a reason.")
        return self


class KnowledgeUnitCollection(CanonicalModel):
    course_schema_version: Literal["1.0.0"] = COURSE_SCHEMA_VERSION
    course_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    unit_count: int = Field(ge=1)
    units: list[KnowledgeUnit] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_units(self) -> KnowledgeUnitCollection:
        if self.unit_count != len(self.units):
            raise ValueError("Knowledge-unit count does not match units.")
        if len({unit.unit_id for unit in self.units}) != len(self.units):
            raise ValueError("Knowledge units must be unique.")
        if any(unit.course_id != self.course_id for unit in self.units):
            raise ValueError("Knowledge unit belongs to another course.")
        return self


class CoverageRecord(CanonicalModel):
    unit_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: CoverageStatus
    generation_ids: list[str] = Field(default_factory=list)
    question_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class CourseCoverageLedger(CanonicalModel):
    course_schema_version: Literal["1.0.0"] = COURSE_SCHEMA_VERSION
    course_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    record_count: int = Field(ge=1)
    status_counts: dict[CoverageStatus, int]
    records: list[CoverageRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_records(self) -> CourseCoverageLedger:
        if self.record_count != len(self.records):
            raise ValueError("Coverage record count does not match records.")
        if len({record.unit_id for record in self.records}) != len(self.records):
            raise ValueError("Coverage records must have unique unit IDs.")
        actual = {status: 0 for status in CoverageStatus}
        for record in self.records:
            actual[record.status] += 1
        if {status: count for status, count in self.status_counts.items() if count} != {
            status: count for status, count in actual.items() if count
        }:
            raise ValueError("Coverage status counts do not match records.")
        return self


class QCMPlanUnit(CanonicalModel):
    unit_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_path: str
    chunk_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_index: int = Field(ge=0)
    taxonomy_path: list[str]
    character_count: int = Field(ge=0)
    token_estimate: int = Field(ge=0)
    source_references: list[SourceReference]


class CourseQCMPlan(CanonicalModel):
    course_schema_version: Literal["1.0.0"] = COURSE_SCHEMA_VERSION
    plan_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    course_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_type: Literal["qcm"] = "qcm"
    requested_question_count: int = Field(ge=1)
    planned_question_count: int = Field(ge=0)
    maximum_source_characters: int = Field(gt=0)
    maximum_source_tokens: int = Field(gt=0)
    eligible_unit_count: int = Field(ge=0)
    pending_unit_count: int = Field(ge=0)
    already_attempted_unit_count: int = Field(ge=0)
    excluded_unit_count: int = Field(ge=0)
    selected_character_count: int = Field(ge=0)
    selected_token_estimate: int = Field(ge=0)
    selected_units: list[QCMPlanUnit]
    unselected_reasons: dict[str, str]
    proposed_plan_path: str
    provider_request: Literal["none"] = "none"
    writes: Literal["none"] = "none"

    @model_validator(mode="after")
    def validate_plan(self) -> CourseQCMPlan:
        if self.planned_question_count != len(self.selected_units):
            raise ValueError("Planned question count does not match selected units.")
        if len({unit.unit_id for unit in self.selected_units}) != len(self.selected_units):
            raise ValueError("Course QCM plan contains duplicate knowledge units.")
        if self.planned_question_count > self.requested_question_count:
            raise ValueError("Course QCM plan exceeds requested count.")
        return self
