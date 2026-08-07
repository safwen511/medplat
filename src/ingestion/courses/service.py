"""Deterministic construction and planning for folder-aware courses."""

from __future__ import annotations

import json
import posixpath
from collections import Counter
from hashlib import sha256
from pathlib import Path, PurePosixPath

from ingestion.courses.models import (
    COURSE_SCHEMA_VERSION,
    KNOWLEDGE_UNIT_STRATEGY_VERSION,
    CourseCatalog,
    CourseCoverageLedger,
    CourseDocument,
    CourseQCMPlan,
    CoverageRecord,
    CoverageStatus,
    KnowledgeUnit,
    KnowledgeUnitCollection,
    QCMPlanUnit,
)
from ingestion.datasets.models import AIReadyDataset
from ingestion.datasets.validation import validate_dataset_file
from ingestion.generation.models import (
    GeneratedContentBatch,
    GenerationValidationReport,
    ReviewStatus,
)
from ingestion.hashing import sha256_file


class CourseError(RuntimeError):
    """A course artifact or plan is invalid."""


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _normalized_course_root(
    dataset_paths: list[tuple[Path, AIReadyDataset]], root: str | None
) -> str:
    parents = [
        str(PurePosixPath(dataset.source_relative_path).parent) for _, dataset in dataset_paths
    ]
    selected = root.strip("/") if root is not None else posixpath.commonpath(parents)
    if (
        not selected
        or selected == "."
        or PurePosixPath(selected).is_absolute()
        or ".." in PurePosixPath(selected).parts
    ):
        raise CourseError("Course root must be a nonempty source-relative folder path.")
    prefix = selected + "/"
    if any(not dataset.source_relative_path.startswith(prefix) for _, dataset in dataset_paths):
        raise CourseError("Every dataset source path must be inside the selected course root.")
    return selected


def _load_datasets(dataset_paths: list[Path]) -> list[tuple[Path, AIReadyDataset]]:
    if not dataset_paths:
        raise CourseError("At least one validated dataset is required.")
    loaded: list[tuple[Path, AIReadyDataset]] = []
    for path in dataset_paths:
        dataset = validate_dataset_file(path)
        if dataset.errors:
            raise CourseError(f"Dataset contains errors: {path}")
        if dataset.processing_statistics.source_reference_coverage <= 0:
            raise CourseError(f"Dataset has no source-reference coverage: {path}")
        loaded.append((path, dataset))
    loaded.sort(key=lambda item: item[1].source_relative_path)
    if len({dataset.document_id for _, dataset in loaded}) != len(loaded):
        raise CourseError("Course dataset list contains duplicate documents.")
    return loaded


def build_course_catalog(
    dataset_paths: list[Path],
    *,
    course_name: str,
    course_root: str | None = None,
) -> tuple[CourseCatalog, KnowledgeUnitCollection]:
    """Build deterministic course and unit artifacts without opening source documents."""
    if not course_name.strip():
        raise CourseError("Course name must be nonempty.")
    loaded = _load_datasets(dataset_paths)
    normalized_root = _normalized_course_root(loaded, course_root)
    document_identity = [
        {
            "document_id": dataset.document_id,
            "dataset_sha256": sha256_file(path),
            "source_relative_path": dataset.source_relative_path,
        }
        for path, dataset in loaded
    ]
    course_id = _digest(
        {
            "course_schema_version": COURSE_SCHEMA_VERSION,
            "knowledge_unit_strategy_version": KNOWLEDGE_UNIT_STRATEGY_VERSION,
            "course_name": course_name.strip(),
            "course_root": normalized_root,
            "documents": document_identity,
        }
    )
    documents: list[CourseDocument] = []
    units: list[KnowledgeUnit] = []
    for path, dataset in loaded:
        source_path = PurePosixPath(dataset.source_relative_path)
        folder_path = list(source_path.parent.parts)
        eligible_count = sum(
            chunk.eligible_for_generation and chunk.character_count >= 100
            for chunk in dataset.chunks
        )
        excluded_count = len(dataset.chunks) - eligible_count
        documents.append(
            CourseDocument(
                document_id=dataset.document_id,
                source_sha256=dataset.source_sha256,
                source_relative_path=dataset.source_relative_path,
                folder_path=folder_path,
                filename=source_path.name,
                document_title=dataset.document_title,
                dataset_path=str(path),
                dataset_sha256=sha256_file(path),
                dataset_schema_version=dataset.dataset_schema_version,
                eligible_unit_count=eligible_count,
                excluded_unit_count=excluded_count,
            )
        )
        for chunk in sorted(dataset.chunks, key=lambda item: (item.chunk_index, item.chunk_id)):
            unit_id = _digest(
                {
                    "course_schema_version": COURSE_SCHEMA_VERSION,
                    "course_id": course_id,
                    "document_id": dataset.document_id,
                    "chunk_id": chunk.chunk_id,
                }
            )
            eligible_for_qcm = chunk.eligible_for_generation and chunk.character_count >= 100
            reasons = list(chunk.generation_exclusion_reasons)
            if chunk.eligible_for_generation and chunk.character_count < 100:
                reasons.append("qcm_unit_below_minimum_characters:100")
            if not eligible_for_qcm and not reasons:
                reasons = ["dataset_chunk_ineligible"]
            units.append(
                KnowledgeUnit(
                    unit_id=unit_id,
                    course_id=course_id,
                    document_id=dataset.document_id,
                    source_sha256=dataset.source_sha256,
                    source_relative_path=dataset.source_relative_path,
                    folder_path=folder_path,
                    section_path=chunk.section_path,
                    taxonomy_path=[*folder_path, *chunk.section_path],
                    chunk_id=chunk.chunk_id,
                    chunk_index=chunk.chunk_index,
                    chunk_type=chunk.chunk_type.value,
                    normalized_text_hash=chunk.normalized_text_hash,
                    character_count=chunk.character_count,
                    token_estimate=chunk.token_estimate,
                    source_references=chunk.source_references,
                    eligible_for_qcm=eligible_for_qcm,
                    exclusion_reasons=reasons,
                )
            )
    catalog = CourseCatalog(
        course_id=course_id,
        course_name=course_name.strip(),
        course_root=normalized_root,
        taxonomy_labels=list(PurePosixPath(normalized_root).parts),
        document_count=len(documents),
        documents=documents,
        knowledge_unit_count=len(units),
        eligible_unit_count=sum(unit.eligible_for_qcm for unit in units),
        excluded_unit_count=sum(not unit.eligible_for_qcm for unit in units),
    )
    collection = KnowledgeUnitCollection(course_id=course_id, unit_count=len(units), units=units)
    return catalog, collection


def _coverage_priority(status: CoverageStatus) -> int:
    return {
        CoverageStatus.PENDING: 0,
        CoverageStatus.SELECTED: 1,
        CoverageStatus.FAILED: 2,
        CoverageStatus.INSUFFICIENT_FOR_QCM: 3,
        CoverageStatus.NEEDS_REVISION: 4,
        CoverageStatus.COVERED_BY_VALID_QCM: 5,
        CoverageStatus.EXCLUDED: 6,
    }[status]


def _generated_coverage(
    units: KnowledgeUnitCollection,
    generation_root: Path,
) -> dict[str, CoverageRecord]:
    by_chunk = {unit.chunk_id: unit for unit in units.units}
    records: dict[str, CoverageRecord] = {}
    document_ids = sorted({unit.document_id for unit in units.units})
    for document_id in document_ids:
        document_root = generation_root / document_id / "qcm"
        if not document_root.exists():
            continue
        for generation_directory in sorted(
            path for path in document_root.iterdir() if path.is_dir()
        ):
            content_path = generation_directory / "generated-content.json"
            validation_path = generation_directory / "validation-report.json"
            if not content_path.is_file() or not validation_path.is_file():
                raise CourseError(
                    f"Incomplete successful generation directory: {generation_directory}"
                )
            content = GeneratedContentBatch.model_validate_json(
                content_path.read_text(encoding="utf-8")
            )
            report = GenerationValidationReport.model_validate_json(
                validation_path.read_text(encoding="utf-8")
            )
            if content.document_id != document_id or content.source_sha256 != document_id:
                raise CourseError(f"Generation document identity mismatch: {generation_directory}")
            if report.generation_id != content.generation_id:
                raise CourseError(
                    f"Generation validation identity mismatch: {generation_directory}"
                )
            for question in content.qcm_questions:
                for chunk_id in question.source_chunk_ids:
                    unit = by_chunk.get(chunk_id)
                    if unit is None or unit.document_id != document_id:
                        raise CourseError(
                            "Generated question references a chunk outside the course."
                        )
                    if question.medical_review.status is ReviewStatus.ACCEPTED:
                        status = CoverageStatus.COVERED_BY_VALID_QCM
                        reason = "accepted_human_reviewed_qcm"
                    elif question.medical_review.status is ReviewStatus.REJECTED:
                        status = CoverageStatus.FAILED
                        reason = "generated_qcm_rejected_by_human_review"
                    else:
                        status = CoverageStatus.NEEDS_REVISION
                        reason = "generated_qcm_requires_human_review"
                    existing = records.get(unit.unit_id)
                    if existing is None:
                        records[unit.unit_id] = CoverageRecord(
                            unit_id=unit.unit_id,
                            document_id=unit.document_id,
                            chunk_id=unit.chunk_id,
                            status=status,
                            generation_ids=[content.generation_id],
                            question_ids=[question.question_id],
                            reasons=[reason],
                        )
                        continue
                    selected_status = max((existing.status, status), key=_coverage_priority)
                    records[unit.unit_id] = existing.model_copy(
                        update={
                            "status": selected_status,
                            "generation_ids": sorted(
                                {*existing.generation_ids, content.generation_id}
                            ),
                            "question_ids": sorted({*existing.question_ids, question.question_id}),
                            "reasons": sorted({*existing.reasons, reason}),
                        }
                    )
    return records


def build_coverage_ledger(
    units: KnowledgeUnitCollection,
    *,
    generation_root: Path = Path("data/generated"),
) -> CourseCoverageLedger:
    """Build a deterministic snapshot from dataset eligibility and existing QCM artifacts."""
    generated = _generated_coverage(units, generation_root)
    records: list[CoverageRecord] = []
    for unit in units.units:
        existing = generated.get(unit.unit_id)
        if existing is not None:
            records.append(existing)
        elif unit.eligible_for_qcm:
            records.append(
                CoverageRecord(
                    unit_id=unit.unit_id,
                    document_id=unit.document_id,
                    chunk_id=unit.chunk_id,
                    status=CoverageStatus.PENDING,
                )
            )
        else:
            records.append(
                CoverageRecord(
                    unit_id=unit.unit_id,
                    document_id=unit.document_id,
                    chunk_id=unit.chunk_id,
                    status=CoverageStatus.EXCLUDED,
                    reasons=unit.exclusion_reasons,
                )
            )
    counts = Counter(record.status for record in records)
    return CourseCoverageLedger(
        course_id=units.course_id,
        record_count=len(records),
        status_counts=dict(sorted(counts.items(), key=lambda item: item[0].value)),
        records=records,
    )


def build_course_qcm_plan(
    catalog: CourseCatalog,
    units: KnowledgeUnitCollection,
    ledger: CourseCoverageLedger,
    *,
    requested_count: int,
    maximum_source_characters: int,
    maximum_source_tokens: int,
    proposed_plan_root: Path,
) -> CourseQCMPlan:
    """Select uncovered eligible knowledge units without a provider request or write."""
    if requested_count < 1:
        raise CourseError("Requested QCM count must be positive.")
    if maximum_source_characters < 1 or maximum_source_tokens < 1:
        raise CourseError("Course QCM source budgets must be positive.")
    if not (catalog.course_id == units.course_id == ledger.course_id):
        raise CourseError("Course artifacts have mismatched identities.")
    unit_ids = {unit.unit_id for unit in units.units}
    if unit_ids != {record.unit_id for record in ledger.records}:
        raise CourseError("Coverage ledger does not match knowledge units.")
    documents = {document.document_id: document for document in catalog.documents}
    records = {record.unit_id: record for record in ledger.records}
    ordered = sorted(
        units.units,
        key=lambda unit: (unit.source_relative_path, unit.chunk_index, unit.chunk_id),
    )
    selected: list[QCMPlanUnit] = []
    unselected: dict[str, str] = {}
    characters = 0
    tokens = 0
    for unit in ordered:
        record = records[unit.unit_id]
        if record.status is not CoverageStatus.PENDING:
            unselected[unit.unit_id] = f"coverage_status:{record.status.value}"
            continue
        if len(selected) >= requested_count:
            unselected[unit.unit_id] = "requested_count_reached"
            continue
        if (
            characters + unit.character_count > maximum_source_characters
            or tokens + unit.token_estimate > maximum_source_tokens
        ):
            unselected[unit.unit_id] = "source_budget_exceeded"
            continue
        document = documents[unit.document_id]
        selected.append(
            QCMPlanUnit(
                unit_id=unit.unit_id,
                document_id=unit.document_id,
                dataset_path=document.dataset_path,
                chunk_id=unit.chunk_id,
                chunk_index=unit.chunk_index,
                taxonomy_path=unit.taxonomy_path,
                character_count=unit.character_count,
                token_estimate=unit.token_estimate,
                source_references=unit.source_references,
            )
        )
        characters += unit.character_count
        tokens += unit.token_estimate
    identity = {
        "course_schema_version": COURSE_SCHEMA_VERSION,
        "course_id": catalog.course_id,
        "requested_question_count": requested_count,
        "maximum_source_characters": maximum_source_characters,
        "maximum_source_tokens": maximum_source_tokens,
        "selected_unit_ids": [unit.unit_id for unit in selected],
        "coverage": [
            {"unit_id": record.unit_id, "status": record.status.value} for record in ledger.records
        ],
    }
    plan_id = _digest(identity)
    counts = Counter(record.status for record in ledger.records)
    return CourseQCMPlan(
        plan_id=plan_id,
        course_id=catalog.course_id,
        requested_question_count=requested_count,
        planned_question_count=len(selected),
        maximum_source_characters=maximum_source_characters,
        maximum_source_tokens=maximum_source_tokens,
        eligible_unit_count=catalog.eligible_unit_count,
        pending_unit_count=counts[CoverageStatus.PENDING],
        already_attempted_unit_count=sum(
            counts[status]
            for status in (
                CoverageStatus.SELECTED,
                CoverageStatus.COVERED_BY_VALID_QCM,
                CoverageStatus.NEEDS_REVISION,
                CoverageStatus.INSUFFICIENT_FOR_QCM,
                CoverageStatus.FAILED,
            )
        ),
        excluded_unit_count=counts[CoverageStatus.EXCLUDED],
        selected_character_count=characters,
        selected_token_estimate=tokens,
        selected_units=selected,
        unselected_reasons=dict(sorted(unselected.items())),
        proposed_plan_path=str(proposed_plan_root / "plans" / "qcm" / f"{plan_id}.json"),
    )


def load_course_artifacts(
    course_directory: Path,
) -> tuple[CourseCatalog, KnowledgeUnitCollection, CourseCoverageLedger]:
    catalog = CourseCatalog.model_validate_json(
        (course_directory / "course-catalog.json").read_text(encoding="utf-8")
    )
    units = KnowledgeUnitCollection.model_validate_json(
        (course_directory / "knowledge-units.json").read_text(encoding="utf-8")
    )
    ledger = CourseCoverageLedger.model_validate_json(
        (course_directory / "qcm-coverage.json").read_text(encoding="utf-8")
    )
    if not (catalog.course_id == units.course_id == ledger.course_id):
        raise CourseError("Persisted course artifacts have mismatched identities.")
    return catalog, units, ledger
