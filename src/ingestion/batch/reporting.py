"""Deterministic aggregate batch reporting without source content."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from ingestion.batch.models import (
    BatchDocumentStatus,
    BatchPlan,
    BatchReport,
    BatchStage,
    DocumentBatchReport,
)
from ingestion.batch.state import batch_directory
from ingestion.output import write_json_atomic


def build_report(
    plan: BatchPlan,
    documents: list[DocumentBatchReport],
    *,
    started: datetime,
    completed: datetime,
) -> BatchReport:
    ordered = sorted(documents, key=lambda item: item.sequence_number)
    statuses = Counter(item.final_status.value for item in ordered)
    extensions = Counter(item.extension for item in ordered)
    routes = Counter(item.parser_route.value for item in ordered)
    suitability = Counter(item.suitability or "unknown" for item in ordered)
    final_stages = Counter(
        (item.stages_completed[-1].value if item.stages_completed else BatchStage.DISCOVERED.value)
        for item in ordered
    )
    run_id = sha256(f"{plan.batch_id}\n{started.isoformat()}".encode()).hexdigest()
    return BatchReport(
        batch_id=plan.batch_id,
        run_id=run_id,
        configuration=plan.configuration,
        start_time=started,
        completion_time=completed,
        duration_seconds=max(0.0, (completed - started).total_seconds()),
        selected_count=len(ordered),
        processed_count=sum(
            item.final_status not in {BatchDocumentStatus.SKIPPED, BatchDocumentStatus.UNSUPPORTED}
            for item in ordered
        ),
        complete_count=statuses[BatchDocumentStatus.SUCCEEDED.value],
        complete_with_warnings_count=statuses[BatchDocumentStatus.SUCCEEDED_WITH_WARNINGS.value],
        skipped_count=statuses[BatchDocumentStatus.SKIPPED.value],
        already_complete_count=sum(item.skipped_reason == "already_complete" for item in ordered),
        unsupported_count=statuses[BatchDocumentStatus.UNSUPPORTED.value],
        requires_ocr_count=statuses[BatchDocumentStatus.REQUIRES_OCR.value],
        ocr_attempted_count=sum(
            item.safe_ocr_attempted or item.force_ocr_attempted for item in ordered
        ),
        safe_ocr_accepted_count=sum(item.safe_ocr_accepted for item in ordered),
        force_ocr_attempted_count=sum(item.force_ocr_attempted for item in ordered),
        force_ocr_accepted_count=sum(item.force_ocr_accepted for item in ordered),
        failed_count=statuses[BatchDocumentStatus.FAILED.value],
        interrupted_count=statuses[BatchDocumentStatus.INTERRUPTED.value],
        counts_by_source_extension=dict(sorted(extensions.items())),
        counts_by_parser_route=dict(sorted(routes.items())),
        counts_by_suitability=dict(sorted(suitability.items())),
        counts_by_final_stage=dict(sorted(final_stages.items())),
        total_source_bytes=sum(planned.file_size for planned in plan.documents),
        total_processing_time=sum(sum(item.durations_by_stage.values()) for item in ordered),
        documents=ordered,
        warnings=plan.warnings,
        errors=[error for item in ordered for error in item.errors],
    )


def persist_report(plan: BatchPlan, report: BatchReport) -> Path:
    directory = batch_directory(plan)
    path = directory / "batch-report.json"
    write_json_atomic(path, report.model_dump(mode="json"))
    failures = [
        item.model_dump(mode="json")
        for item in report.documents
        if item.final_status is BatchDocumentStatus.FAILED
    ]
    skipped = [
        item.model_dump(mode="json")
        for item in report.documents
        if item.final_status in {BatchDocumentStatus.SKIPPED, BatchDocumentStatus.UNSUPPORTED}
    ]
    write_json_atomic(directory / "failures.json", failures)
    write_json_atomic(directory / "skipped.json", skipped)
    return path
