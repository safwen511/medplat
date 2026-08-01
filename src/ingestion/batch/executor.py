"""Sequential, failure-isolated execution of validated batch plans."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

from ingestion.batch.models import (
    BatchDocumentStatus,
    BatchFailure,
    BatchPlan,
    BatchReport,
    BatchStage,
    DocumentBatchReport,
    DocumentBatchState,
    OCRRoute,
    ParserRoute,
    PlannedDocument,
)
from ingestion.batch.reporting import build_report, persist_report
from ingestion.batch.resume import should_execute
from ingestion.batch.state import (
    load_or_initialize_state,
    persist_document_state,
    persist_plan,
    persist_state,
)
from ingestion.batch.validation import READY, inspect_existing_outputs
from ingestion.chunking.builder import build_chunk_collection
from ingestion.chunking.models import ChunkCollection
from ingestion.chunking.validation import validate_chunk_collection_file
from ingestion.config import DoclingSettings
from ingestion.datasets.builder import build_ai_ready_dataset
from ingestion.datasets.models import AIReadyDataset
from ingestion.datasets.output import write_chunk_outputs, write_dataset_output
from ingestion.datasets.validation import validate_dataset_file
from ingestion.hashing import sha256_file
from ingestion.normalization.models import NormalizedDocument
from ingestion.normalization.validation import validate_document_file
from ingestion.ocr.environment import check_ocr_environment
from ingestion.ocr.models import OCRConfiguration, OCRQualityOutcome
from ingestion.ocr.parsing import parse_ocr_derivative, processing_variant_id
from ingestion.ocr.service import OCRDerivativeResult, create_ocr_derivative
from ingestion.ocr.validation import validate_derivative_file
from ingestion.pipeline import parse_document

ACCEPTED = {OCRQualityOutcome.ACCEPTED, OCRQualityOutcome.ACCEPTED_WITH_WARNINGS}


def execute_batch(plan: BatchPlan, *, persist: bool = True) -> BatchReport:
    """Execute one deterministic plan sequentially; dry runs never write."""
    started = datetime.now(timezone.utc)
    if plan.configuration.dry_run:
        dry_reports = [_dry_run_report(item) for item in plan.documents]
        return build_report(
            plan, dry_reports, started=started, completed=datetime.now(timezone.utc)
        )

    _preflight(plan)

    state = load_or_initialize_state(plan)
    if persist:
        persist_plan(plan)
        persist_state(plan, state)
    reports: list[DocumentBatchReport] = []
    stop = False
    for planned, document_state in zip(plan.documents, state.documents, strict=True):
        if stop:
            reports.append(_skipped_report(planned, document_state, "not_started_after_failure"))
            continue
        execute, reason = should_execute(planned, document_state, plan.configuration)
        if not execute:
            reports.append(_skipped_report(planned, document_state, reason or "skipped"))
            continue
        if plan.configuration.retry_failures:
            document_state.retry_count += 1
        try:
            report = _execute_document(plan, planned, document_state, persist=persist)
        except KeyboardInterrupt:
            document_state.status = BatchDocumentStatus.INTERRUPTED
            document_state.updated_at = datetime.now(timezone.utc)
            if persist:
                persist_document_state(plan, document_state)
                persist_state(plan, state)
            raise
        except Exception as exc:
            failure = BatchFailure(
                source_relative_path=planned.source_relative_path,
                sequence_number=planned.sequence_number,
                stage=document_state.last_completed_stage,
                error_category=type(exc).__name__,
                message=str(exc),
                diagnostic=f"{type(exc).__module__}.{type(exc).__name__}",
                retryable=True,
                existing_valid_artifacts=_existing_paths(planned),
                next_recommended_action=(
                    "Review the concise error, then use --retry-failures if corrected."
                ),
            )
            document_state.status = BatchDocumentStatus.FAILED
            document_state.failure = failure
            document_state.updated_at = datetime.now(timezone.utc)
            report = _failed_report(planned, document_state, failure)
            if not plan.configuration.continue_on_error:
                stop = True
        reports.append(report)
        if persist:
            persist_document_state(plan, document_state)
            persist_state(plan, state)

    completed = datetime.now(timezone.utc)
    batch_report = build_report(plan, reports, started=started, completed=completed)
    if persist:
        persist_report(plan, batch_report)
    return batch_report


def _preflight(plan: BatchPlan) -> None:
    actionable = [
        item
        for item in plan.documents
        if item.parser_route is not ParserRoute.UNSUPPORTED
        and item.skip_reason != "already_complete"
    ]
    if any(item.parser_route is ParserRoute.PDF for item in actionable):
        DoclingSettings.from_sources().validate_pdf_artifacts()
    if plan.configuration.ocr_enabled and any(
        item.ocr_route in {OCRRoute.SAFE_FIRST, OCRRoute.SAFE_THEN_FORCE_ALLOWED}
        for item in actionable
    ):
        environment = check_ocr_environment(
            plan.configuration.ocr_languages,
            plan.configuration.derived_output_root,
        )
        if not environment.ready:
            raise RuntimeError(
                "OCR is enabled but the local OCR environment is not ready; "
                "run check-ocr-environment with the configured languages."
            )


def _execute_document(
    plan: BatchPlan,
    planned: PlannedDocument,
    state: DocumentBatchState,
    *,
    persist: bool,
) -> DocumentBatchReport:
    configuration = plan.configuration
    source = configuration.input_root / planned.source_relative_path
    if not source.is_file() or sha256_file(source) != planned.sha256:
        raise ValueError("Source path or SHA-256 changed after batch planning.")
    state.status = BatchDocumentStatus.RUNNING
    durations: dict[str, float] = {}
    warnings = list(planned.current_output_state.validation_warnings)
    state.failure = None
    _checkpoint(plan, state, BatchStage.INSPECTED, persist)

    output_state = inspect_existing_outputs(
        output_root=configuration.output_root,
        source_sha256=planned.sha256,
        source_relative_path=planned.source_relative_path,
        source_root=configuration.input_root,
    )
    canonical_path = Path(output_state.canonical_path) if output_state.canonical_path else None
    if canonical_path is None or configuration.force_rebuild:
        started = monotonic()
        result = parse_document(
            source,
            source_root=configuration.input_root,
            output_root=configuration.output_root,
            force=configuration.force_rebuild
            or (configuration.output_root / planned.sha256).exists(),
            docling_settings=DoclingSettings.from_sources(),
        )
        durations["parse"] = monotonic() - started
        canonical_path = result.output_directory / "document.json"
        warnings.extend(result.report.warnings)
        suitability = (
            result.report.technical_suitability.value
            if result.report.technical_suitability
            else None
        )
        _checkpoint(plan, state, BatchStage.PARSED, persist)
    else:
        suitability = output_state.suitability

    started = monotonic()
    document = validate_document_file(canonical_path)
    durations["canonical_validation"] = monotonic() - started
    _checkpoint(plan, state, BatchStage.CANONICAL_VALIDATED, persist)

    derivative_path: Path | None = None
    safe_attempted = safe_accepted = force_attempted = force_accepted = False
    if suitability not in READY:
        if planned.parser_route is not ParserRoute.PDF:
            raise ValueError(f"Canonical extraction is not suitable for chunking: {suitability}")
        if not configuration.ocr_enabled:
            state.status = BatchDocumentStatus.REQUIRES_OCR
            return _result_report(
                planned,
                state,
                suitability="requires_ocr",
                canonical_path=canonical_path,
                warnings=warnings,
                durations=durations,
                skipped_reason="ocr_disabled",
            )
        safe_attempted = True
        started = monotonic()
        safe = _get_or_create_derivative(
            source,
            plan,
            OCRConfiguration(
                language_codes=configuration.ocr_languages,
                timeout_seconds=configuration.ocr_timeout_seconds,
                jobs=1,
                skip_text=True,
            ),
        )
        durations["safe_ocr"] = monotonic() - started
        _checkpoint(plan, state, BatchStage.DERIVATIVE_CREATED, persist)
        derivative, _ = validate_derivative_file(
            safe.directory / "derivative.json", source_root=configuration.input_root
        )
        _checkpoint(plan, state, BatchStage.DERIVATIVE_VALIDATED, persist)
        chosen = safe
        safe_accepted = derivative.validation_status in ACCEPTED
        if not safe_accepted:
            if planned.ocr_route is not OCRRoute.SAFE_THEN_FORCE_ALLOWED:
                state.status = BatchDocumentStatus.REQUIRES_OCR
                return _result_report(
                    planned,
                    state,
                    suitability="requires_ocr",
                    canonical_path=canonical_path,
                    derivative_path=safe.directory / "derivative.json",
                    warnings=warnings,
                    durations=durations,
                    skipped_reason=derivative.validation_status.value,
                    safe_ocr_attempted=True,
                )
            force_attempted = True
            started = monotonic()
            chosen = _get_or_create_derivative(
                source,
                plan,
                OCRConfiguration(
                    language_codes=configuration.ocr_languages,
                    timeout_seconds=configuration.ocr_timeout_seconds,
                    jobs=1,
                    force_ocr=True,
                    skip_text=False,
                ),
            )
            durations["force_ocr"] = monotonic() - started
            derivative, _ = validate_derivative_file(
                chosen.directory / "derivative.json", source_root=configuration.input_root
            )
            force_accepted = derivative.validation_status in ACCEPTED
            if not force_accepted:
                state.status = BatchDocumentStatus.REQUIRES_OCR
                return _result_report(
                    planned,
                    state,
                    suitability="requires_ocr",
                    canonical_path=canonical_path,
                    derivative_path=chosen.directory / "derivative.json",
                    warnings=warnings,
                    durations=durations,
                    skipped_reason=derivative.validation_status.value,
                    safe_ocr_attempted=True,
                    force_ocr_attempted=True,
                )
        derivative_path = chosen.directory / "derivative.json"
        variant_id = processing_variant_id(chosen.derivative.derivative_id)
        expected = (
            configuration.output_root / planned.sha256 / "variants" / variant_id / "document.json"
        )
        if expected.is_file() and not configuration.force_rebuild:
            canonical_path = expected
        else:
            started = monotonic()
            parsed = parse_ocr_derivative(
                derivative_path,
                source_root=configuration.input_root,
                output_root=configuration.output_root,
                docling_settings=DoclingSettings.from_sources(),
                force=configuration.force_rebuild or expected.parent.exists(),
            )
            durations["derivative_parse"] = monotonic() - started
            canonical_path = parsed.output_directory / "document.json"
            warnings.extend(parsed.report.warnings)
        document = validate_document_file(canonical_path)
        output_state = inspect_existing_outputs(
            output_root=configuration.output_root,
            source_sha256=planned.sha256,
            source_relative_path=planned.source_relative_path,
            source_root=configuration.input_root,
        )
        suitability = output_state.suitability
        if suitability not in READY:
            raise ValueError(
                "Accepted OCR derivative canonical output is not suitable for chunking."
            )

    collection, chunks_path = _ensure_chunks(canonical_path, document, configuration.force_rebuild)
    _checkpoint(plan, state, BatchStage.CHUNKS_BUILT, persist)
    validate_chunk_collection_file(chunks_path)
    _checkpoint(plan, state, BatchStage.CHUNKS_VALIDATED, persist)
    dataset, dataset_path = _ensure_dataset(
        canonical_path, document, collection, configuration.force_rebuild
    )
    _checkpoint(plan, state, BatchStage.DATASET_BUILT, persist)
    validate_dataset_file(dataset_path)
    _checkpoint(plan, state, BatchStage.DATASET_VALIDATED, persist)
    eligible = sum(chunk.eligible_for_generation for chunk in dataset.chunks)
    if eligible < 1 or dataset.processing_statistics.source_reference_coverage <= 0:
        raise ValueError("Dataset has no eligible source-grounded chunk.")
    _checkpoint(plan, state, BatchStage.COMPLETE, persist)
    status = (
        BatchDocumentStatus.SUCCEEDED_WITH_WARNINGS
        if warnings
        or collection.warnings
        or dataset.warnings
        or suitability == "ready_with_warnings"
        else BatchDocumentStatus.SUCCEEDED
    )
    state.status = status
    return _result_report(
        planned,
        state,
        suitability=suitability,
        canonical_path=canonical_path,
        derivative_path=derivative_path,
        chunk_path=chunks_path,
        dataset_path=dataset_path,
        warnings=list(dict.fromkeys([*warnings, *collection.warnings, *dataset.warnings])),
        durations=durations,
        eligible=eligible,
        excluded=len(dataset.chunks) - eligible,
        safe_ocr_attempted=safe_attempted,
        safe_ocr_accepted=safe_accepted,
        force_ocr_attempted=force_attempted,
        force_ocr_accepted=force_accepted,
    )


def _get_or_create_derivative(
    source: Path, plan: BatchPlan, configuration: OCRConfiguration
) -> OCRDerivativeResult:
    parent = plan.configuration.derived_output_root / sha256_file(source) / "ocr"
    if parent.is_dir():
        for metadata in sorted(parent.glob("*/derivative.json"), key=lambda path: path.as_posix()):
            try:
                derivative, report = validate_derivative_file(
                    metadata, source_root=plan.configuration.input_root
                )
            except (OSError, ValueError):
                continue
            if derivative.configuration == configuration:
                return OCRDerivativeResult(derivative, report, metadata.parent)
    return create_ocr_derivative(
        source,
        configuration,
        output_root=plan.configuration.derived_output_root,
        source_root=plan.configuration.input_root,
    )


def _ensure_chunks(
    canonical_path: Path, document: NormalizedDocument, force: bool
) -> tuple[ChunkCollection, Path]:
    path = canonical_path.parent / "chunks" / "chunks.json"
    if path.is_file() and not force:
        try:
            return validate_chunk_collection_file(path), path
        except (OSError, ValueError):
            pass
    collection = build_chunk_collection(document)
    directory = write_chunk_outputs(canonical_path, collection, force=force or path.parent.exists())
    return collection, directory / "chunks.json"


def _ensure_dataset(
    canonical_path: Path,
    document: NormalizedDocument,
    collection: ChunkCollection,
    force: bool,
) -> tuple[AIReadyDataset, Path]:
    path = canonical_path.parent / "datasets" / "ai-ready-dataset.json"
    if path.is_file() and not force:
        try:
            return validate_dataset_file(path), path
        except (OSError, ValueError):
            pass
    dataset = build_ai_ready_dataset(document, collection)
    directory = write_dataset_output(canonical_path, dataset, force=force or path.parent.exists())
    return dataset, directory / "ai-ready-dataset.json"


def _checkpoint(
    plan: BatchPlan, state: DocumentBatchState, stage: BatchStage, persist: bool
) -> None:
    state.last_completed_stage = stage
    if stage not in state.stages_completed:
        state.stages_completed.append(stage)
    state.updated_at = datetime.now(timezone.utc)
    if persist:
        persist_document_state(plan, state)


def _dry_run_report(planned: PlannedDocument) -> DocumentBatchReport:
    status = (
        BatchDocumentStatus.UNSUPPORTED
        if planned.parser_route is ParserRoute.UNSUPPORTED
        else BatchDocumentStatus.SKIPPED
    )
    return DocumentBatchReport(
        sequence_number=planned.sequence_number,
        source_relative_path=planned.source_relative_path,
        source_sha256=planned.sha256,
        extension=planned.extension,
        classification=planned.inspection_classification,
        parser_route=planned.parser_route,
        ocr_route=planned.ocr_route,
        planned_actions=planned.planned_actions,
        stages_completed=[BatchStage.DISCOVERED, BatchStage.INSPECTED],
        final_status=status,
        suitability=planned.current_output_state.suitability,
        generation_ready=planned.current_output_state.generation_ready,
        canonical_output_path=planned.current_output_state.canonical_path,
        derivative_path=planned.current_output_state.derivative_path,
        chunk_path=planned.current_output_state.chunk_path,
        dataset_path=planned.current_output_state.dataset_path,
        warnings=planned.current_output_state.validation_warnings,
        skipped_reason=planned.skip_reason or "dry_run",
    )


def _skipped_report(
    planned: PlannedDocument, state: DocumentBatchState, reason: str
) -> DocumentBatchReport:
    report = _dry_run_report(planned)
    report.final_status = (
        BatchDocumentStatus.UNSUPPORTED
        if reason == "unsupported_for_parsing"
        else BatchDocumentStatus.SKIPPED
    )
    report.stages_completed = state.stages_completed
    report.skipped_reason = reason
    return report


def _result_report(
    planned: PlannedDocument,
    state: DocumentBatchState,
    *,
    suitability: str | None,
    canonical_path: Path,
    warnings: list[str],
    durations: dict[str, float],
    derivative_path: Path | None = None,
    chunk_path: Path | None = None,
    dataset_path: Path | None = None,
    skipped_reason: str | None = None,
    eligible: int | None = None,
    excluded: int | None = None,
    safe_ocr_attempted: bool = False,
    safe_ocr_accepted: bool = False,
    force_ocr_attempted: bool = False,
    force_ocr_accepted: bool = False,
) -> DocumentBatchReport:
    return DocumentBatchReport(
        sequence_number=planned.sequence_number,
        source_relative_path=planned.source_relative_path,
        source_sha256=planned.sha256,
        extension=planned.extension,
        classification=planned.inspection_classification,
        parser_route=planned.parser_route,
        ocr_route=planned.ocr_route,
        planned_actions=planned.planned_actions,
        stages_completed=state.stages_completed,
        final_status=state.status,
        suitability=suitability,
        generation_ready=state.status
        in {BatchDocumentStatus.SUCCEEDED, BatchDocumentStatus.SUCCEEDED_WITH_WARNINGS},
        canonical_output_path=str(canonical_path),
        derivative_path=str(derivative_path) if derivative_path else None,
        chunk_path=str(chunk_path) if chunk_path else None,
        dataset_path=str(dataset_path) if dataset_path else None,
        warnings=warnings,
        durations_by_stage=durations,
        retries=state.retry_count,
        skipped_reason=skipped_reason,
        eligible_chunk_count=eligible,
        excluded_chunk_count=excluded,
        safe_ocr_attempted=safe_ocr_attempted,
        safe_ocr_accepted=safe_ocr_accepted,
        force_ocr_attempted=force_ocr_attempted,
        force_ocr_accepted=force_ocr_accepted,
    )


def _failed_report(
    planned: PlannedDocument, state: DocumentBatchState, failure: BatchFailure
) -> DocumentBatchReport:
    report = _dry_run_report(planned)
    report.final_status = BatchDocumentStatus.FAILED
    report.stages_completed = state.stages_completed
    report.errors = [f"{failure.error_category}: {failure.message}"]
    report.retries = state.retry_count
    report.skipped_reason = None
    return report


def _existing_paths(planned: PlannedDocument) -> list[str]:
    state = planned.current_output_state
    return [
        path
        for path in (
            state.canonical_path,
            state.derivative_path,
            state.chunk_path,
            state.dataset_path,
        )
        if path is not None
    ]
