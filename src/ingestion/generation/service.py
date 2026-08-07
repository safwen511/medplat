"""Planning and orchestration for local source-grounded QCM generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ingestion.datasets.models import AIReadyDataset
from ingestion.datasets.validation import validate_dataset_file
from ingestion.generation.evidence import EvidenceResolutionError, resolve_provider_evidence
from ingestion.generation.models import (
    ContentType,
    CorrectAnswer,
    EvidenceCitation,
    Explanation,
    FailureReport,
    FailureStage,
    GeneratedContentBatch,
    GenerationConfiguration,
    GenerationReport,
    GenerationRequest,
    GenerationStatus,
    GenerationValidationReport,
    GroundingReport,
    HumanReviewState,
    IssueSeverity,
    ProviderKind,
    ProviderMetadata,
    ProviderQCMCorrectionResponse,
    ProviderQCMQuestionDraft,
    ProviderQCMResponse,
    QCMChoice,
    QCMQuestion,
    RawProviderResponseRecord,
    ReportStatus,
    ValidationIssue,
)
from ingestion.generation.output import (
    GenerationOutputExistsError,
    generation_failure_directory,
    generation_output_directory,
    write_generation_failure,
    write_generation_output,
)
from ingestion.generation.prompts import (
    build_qcm_correction_schema,
    build_qcm_corrective_messages,
    build_qcm_messages,
    build_qcm_response_schema,
    prompt_size,
)
from ingestion.generation.providers.base import (
    GenerationProvider,
    GenerationProviderError,
    ProviderResult,
)
from ingestion.generation.selection import select_generation_source
from ingestion.generation.validation import validate_generated_content
from ingestion.output import ensure_output_outside_source


class GenerationError(RuntimeError):
    """A clean generation failure that must not create finalized output."""


class GenerationFailure(GenerationError):
    """A generation failure whose local diagnostic bundle was finalized."""

    def __init__(self, message: str, failure_directory: Path, issue_codes: list[str]) -> None:
        super().__init__(message)
        self.failure_directory = failure_directory
        self.issue_codes = issue_codes


class GenerationStageError(GenerationError):
    """A classified pre-grounding generation failure."""

    def __init__(
        self,
        message: str,
        *,
        stage: FailureStage,
        code: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class GenerationPlan:
    dataset: AIReadyDataset
    request: GenerationRequest
    messages: list[dict[str, str]]
    provider_response_schema: dict[str, Any]
    proposed_output_directory: Path


@dataclass(frozen=True)
class GenerationResult:
    output_directory: Path
    content: GeneratedContentBatch
    grounding_report: GroundingReport
    validation_report: GenerationValidationReport
    generation_report: GenerationReport


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def build_generation_plan(
    dataset_path: Path,
    configuration: GenerationConfiguration,
    *,
    output_root: Path = Path("data/generated"),
) -> GenerationPlan:
    """Build a deterministic, read-only generation plan without a provider request."""
    if configuration.content_type is not ContentType.QCM:
        raise GenerationError("Only QCM generation is enabled in this milestone.")
    for protected_root in (
        Path("pdfsrc"),
        Path("data/processed"),
        Path("data/derived"),
        Path("data/reports"),
        Path("data/docling-models"),
    ):
        ensure_output_outside_source(output_root, protected_root)
    dataset = validate_dataset_file(dataset_path)
    if dataset.errors:
        raise GenerationError("Dataset contains validation errors and is not generation-ready.")
    if dataset.processing_statistics.source_reference_coverage <= 0:
        raise GenerationError("Dataset has no source-reference coverage.")
    source = select_generation_source(dataset, dataset_path, configuration)
    provider_response_schema = build_qcm_response_schema(source)
    messages = build_qcm_messages(configuration, source)
    prompt_characters, prompt_tokens = prompt_size(messages)
    source = source.model_copy(
        update={
            "prompt_character_estimate": prompt_characters,
            "prompt_token_estimate": prompt_tokens,
        }
    )
    if prompt_tokens + configuration.maximum_output_tokens > configuration.context_size:
        raise GenerationError(
            "Estimated prompt plus maximum output exceeds the configured context size."
        )
    messages = build_qcm_messages(configuration, source)
    prompt_hash = _digest(_stable_json(messages))
    identity = {
        "generation_schema_version": "1.0.0",
        "configuration": configuration.model_dump(mode="json"),
        "source_document_id": source.document_id,
        "dataset_sha256": source.dataset_sha256,
        "selected_chunk_ids": [chunk.chunk_id for chunk in source.selected_chunks],
        "prompt_sha256": prompt_hash,
    }
    generation_id = _digest(_stable_json(identity))
    request = GenerationRequest(
        generation_id=generation_id,
        configuration=configuration,
        source=source,
        prompt_sha256=prompt_hash,
    )
    return GenerationPlan(
        dataset=dataset,
        request=request,
        messages=messages,
        provider_response_schema=provider_response_schema,
        proposed_output_directory=generation_output_directory(
            output_root, dataset.document_id, generation_id
        ),
    )


def _provider_metadata(
    configuration: GenerationConfiguration, result: ProviderResult
) -> ProviderMetadata:
    return ProviderMetadata(
        provider=configuration.provider,
        model=configuration.model,
        base_url=(
            configuration.base_url if configuration.provider is ProviderKind.OLLAMA else None
        ),
        attempt_count=result.attempt_count,
        seed=configuration.seed,
        temperature=configuration.temperature,
        context_size=configuration.context_size,
        maximum_output_tokens=configuration.maximum_output_tokens,
        raw_response_sha256=sha256(result.raw_response_text.encode("utf-8")).hexdigest(),
        provider_version=result.provider_version,
    )


def _failed_provider_metadata(
    configuration: GenerationConfiguration, error: GenerationProviderError
) -> ProviderMetadata | None:
    if error.raw_response_text is None:
        return None
    return ProviderMetadata(
        provider=configuration.provider,
        model=configuration.model,
        base_url=(
            configuration.base_url if configuration.provider is ProviderKind.OLLAMA else None
        ),
        attempt_count=error.attempt_count,
        seed=configuration.seed,
        temperature=configuration.temperature,
        context_size=configuration.context_size,
        maximum_output_tokens=configuration.maximum_output_tokens,
        raw_response_sha256=sha256(error.raw_response_text.encode("utf-8")).hexdigest(),
        provider_version=error.provider_version,
    )


def _pydantic_error_details(error: ValidationError) -> dict[str, object]:
    serialized = json.dumps(error.errors(include_url=False), ensure_ascii=False, default=str)
    value = json.loads(serialized)
    assert isinstance(value, list)
    return {"pydantic_errors": value}


def _raw_response_record(
    *,
    raw_response_text: str | None,
    raw_envelope: dict[str, object] | None,
    content: str | None,
    http_status: int | None,
) -> RawProviderResponseRecord:
    return RawProviderResponseRecord(
        exact_raw_http_response_text=raw_response_text,
        parsed_provider_envelope=raw_envelope,
        provider_content=content,
        http_status=http_status,
    )


def _is_json_text(value: str | None) -> bool:
    if value is None:
        return False
    try:
        json.loads(value)
    except json.JSONDecodeError:
        return False
    return True


def _empty_grounding_report(request: GenerationRequest) -> GroundingReport:
    return GroundingReport(
        generation_id=request.generation_id,
        status=ReportStatus.FAILED,
        grounded_question_count=0,
        needs_revision_question_ids=[],
        issues=[],
    )


_STRUCTURAL_CODES = {
    "malformed_provider_json",
    "invalid_provider_schema",
    "invalid_correction_schema",
    "incomplete_correction_response",
    "empty_corrected_batch",
    "duplicate_choice_keys",
    "invalid_correct_answer_keys",
    "invalid_materialized_qcm",
    "generation_identity_mismatch",
    "document_identity_mismatch",
    "question_count_mismatch",
    "difficulty_distribution_mismatch",
    "insufficient_grounded_questions",
    "invalid_shortfall_declaration",
    "invalid_initial_review_state",
    "duplicate_question",
    "near_duplicate_question",
    "retry_difficulty_changed",
    "retry_unrequested_question_change",
}
_PROVENANCE_CODES = {
    "provider_cited_unselected_chunk",
    "excluded_evidence_chunk",
    "unknown_evidence_block_ids",
    "duplicate_evidence_block_ids",
    "reordered_evidence_block_ids",
    "noncontiguous_evidence_block_ids",
    "missing_evidence_source_excerpt",
    "evidence_span_unmaterializable",
    "question_source_identity_mismatch",
    "nonexistent_chunk_reference",
    "excluded_chunk_used",
    "unselected_chunk_used",
    "source_reference_mismatch",
    "invalid_evidence_chunk",
    "retry_evidence_chunk_changed",
}
_GROUNDING_CODES = {
    "evidence_quotation_mismatch",
    "unsupported_numeric_claim",
    "source_correction_language",
    "low_lexical_support",
}


def _attempt_id(
    request: GenerationRequest,
    *,
    provider_attempt_count: int,
    started_at: datetime,
    raw_response_text: str | None,
    exception: Exception,
) -> tuple[str, str | None, str]:
    raw_hash = (
        sha256(raw_response_text.encode("utf-8")).hexdigest()
        if raw_response_text is not None
        else None
    )
    exception_fingerprint = _digest(
        f"{type(exception).__module__}.{type(exception).__qualname__}:{exception}"
    )
    identity = {
        "generation_id": request.generation_id,
        "provider_attempt_sequence": provider_attempt_count,
        "raw_response_sha256": raw_hash,
        "exception_fingerprint": exception_fingerprint if raw_hash is None else None,
        "attempt_started_at": started_at.isoformat(),
    }
    return _digest(_stable_json(identity)), raw_hash, exception_fingerprint


def _persist_failure(
    *,
    plan: GenerationPlan,
    started_at: datetime,
    stage: FailureStage,
    code: str,
    exception: Exception,
    provider_attempt_count: int,
    raw_response: RawProviderResponseRecord,
    provider_metadata: ProviderMetadata | None,
    validation: GenerationValidationReport,
    grounding: GroundingReport,
    failure_output_root: Path,
    parent_attempt_id: str | None = None,
    validation_retry_sequence: int = 0,
    retry_issue_codes: list[str] | None = None,
    question_count_changed: bool | None = None,
) -> GenerationFailure:
    completed_at = datetime.now(timezone.utc)
    attempt_id, raw_hash, exception_fingerprint = _attempt_id(
        plan.request,
        provider_attempt_count=provider_attempt_count,
        started_at=started_at,
        raw_response_text=raw_response.exact_raw_http_response_text,
        exception=exception,
    )
    issues = validation.issues
    failure_directory = generation_failure_directory(
        failure_output_root,
        plan.request.source.document_id,
        plan.request.generation_id,
        attempt_id,
    )
    output_paths = [
        str(failure_directory / name)
        for name in (
            "request.json",
            "selected-sources.json",
            "raw-provider-response.json",
            "validation-report.json",
            "grounding-report.json",
            "failure-report.json",
        )
    ]
    report = FailureReport(
        generation_id=plan.request.generation_id,
        attempt_id=attempt_id,
        document_id=plan.request.source.document_id,
        source_sha256=plan.request.source.source_sha256,
        started_at=started_at,
        completed_at=completed_at,
        failure_stage=stage,
        failure_code=code,
        failure_message=str(exception),
        exception_type=f"{type(exception).__module__}.{type(exception).__qualname__}",
        exception_fingerprint=exception_fingerprint,
        provider_metadata=provider_metadata,
        provider_attempt_count=provider_attempt_count,
        http_status=raw_response.http_status,
        raw_response_sha256=raw_hash,
        raw_response_is_json=_is_json_text(raw_response.exact_raw_http_response_text),
        structural_issue_count=sum(issue.code in _STRUCTURAL_CODES for issue in issues),
        provenance_issue_count=sum(issue.code in _PROVENANCE_CODES for issue in issues),
        grounding_issue_count=sum(issue.code in _GROUNDING_CODES for issue in issues),
        output_paths=output_paths,
        parent_attempt_id=parent_attempt_id,
        validation_retry_sequence=validation_retry_sequence,
        retry_issue_codes=retry_issue_codes or [],
        question_count_changed=question_count_changed,
    )
    finalized = write_generation_failure(
        plan.request,
        raw_response,
        validation,
        grounding,
        report,
        failure_root=failure_output_root,
    )
    return GenerationFailure(
        str(exception),
        failure_directory=finalized,
        issue_codes=sorted({issue.code for issue in validation.issues}),
    )


def _materialize_question(
    draft: ProviderQCMQuestionDraft,
    *,
    index: int,
    request: GenerationRequest,
    metadata: ProviderMetadata,
) -> QCMQuestion:
    if request.configuration.qcm_type is None:
        raise GenerationStageError(
            "QCM generation request lacks a QCM type.",
            stage=FailureStage.MATERIALIZATION,
            code="missing_qcm_type",
        )
    keys = [choice.key for choice in draft.choices]
    if len(keys) != len(set(keys)):
        raise GenerationStageError(
            "Provider returned duplicate choice keys.",
            stage=FailureStage.MATERIALIZATION,
            code="duplicate_choice_keys",
            details={"choice_keys": keys},
        )
    if len(draft.correct_choice_keys) != len(set(draft.correct_choice_keys)) or not set(
        draft.correct_choice_keys
    ).issubset(keys):
        raise GenerationStageError(
            "Provider returned missing or invalid correct-answer keys.",
            stage=FailureStage.MATERIALIZATION,
            code="invalid_correct_answer_keys",
            details={
                "choice_keys": keys,
                "correct_choice_keys": draft.correct_choice_keys,
            },
        )
    question_id = _digest(f"{request.generation_id}:qcm:{index}")
    key_to_id = {
        choice.key: _digest(f"{question_id}:choice:{choice_index}")
        for choice_index, choice in enumerate(draft.choices)
    }
    try:
        span = resolve_provider_evidence(request.source, draft.evidence[0])
    except EvidenceResolutionError as exc:
        raise GenerationStageError(
            str(exc),
            stage=FailureStage.MATERIALIZATION,
            code=exc.code,
            details=exc.details,
        ) from exc
    return QCMQuestion(
        question_id=question_id,
        question_type=request.configuration.qcm_type,
        language=request.configuration.language,
        topic=draft.topic,
        difficulty=draft.difficulty,
        stem=draft.stem,
        choices=[
            QCMChoice(choice_id=key_to_id[choice.key], text=choice.text) for choice in draft.choices
        ],
        correct_answer=CorrectAnswer(
            choice_ids=[key_to_id[key] for key in draft.correct_choice_keys]
        ),
        explanation=Explanation(
            text=draft.explanation,
            evidence=[EvidenceCitation(chunk_id=span.chunk_id, quotation=span.quotation)],
        ),
        source_document_id=request.source.document_id,
        source_sha256=request.source.source_sha256,
        source_chunk_ids=[span.chunk_id],
        source_references=span.source_references,
        provider_metadata=metadata,
        generation_status=GenerationStatus.DRAFT,
        medical_review=HumanReviewState(),
    )


def _parse_provider_content(
    result: ProviderResult, request: GenerationRequest, metadata: ProviderMetadata
) -> tuple[GeneratedContentBatch, ProviderQCMResponse]:
    try:
        response = ProviderQCMResponse.model_validate_json(result.content)
    except ValidationError as exc:
        codes = {str(item.get("type")) for item in exc.errors(include_url=False)}
        code = "malformed_provider_json" if "json_invalid" in codes else "invalid_provider_schema"
        raise GenerationStageError(
            "Provider returned malformed structured QCM JSON.",
            stage=FailureStage.STRUCTURED_PARSING,
            code=code,
            details=_pydantic_error_details(exc),
        ) from exc
    try:
        questions = [
            _materialize_question(draft, index=index, request=request, metadata=metadata)
            for index, draft in enumerate(response.questions)
        ]
        return (
            GeneratedContentBatch(
                generation_id=request.generation_id,
                request_id=request.generation_id,
                content_type=ContentType.QCM,
                document_id=request.source.document_id,
                source_sha256=request.source.source_sha256,
                qcm_questions=questions,
            ),
            response,
        )
    except GenerationStageError:
        raise
    except ValidationError as exc:
        raise GenerationStageError(
            "Provider QCM content failed materialization.",
            stage=FailureStage.MATERIALIZATION,
            code="invalid_materialized_qcm",
            details=_pydantic_error_details(exc),
        ) from exc


def _targeted_retry_ordinals(
    request: GenerationRequest,
    validation: GenerationValidationReport,
) -> list[int]:
    question_ordinals = {
        _digest(f"{request.generation_id}:qcm:{index}"): index + 1
        for index in range(request.configuration.count)
    }
    return sorted(
        {
            question_ordinals[issue.question_id]
            for issue in validation.issues
            if issue.severity is IssueSeverity.ERROR and issue.question_id in question_ordinals
        }
    )


def _correction_issues(
    request: GenerationRequest,
    validation: GenerationValidationReport,
    target_ordinals: list[int],
) -> list[ValidationIssue]:
    target_ids = {
        _digest(f"{request.generation_id}:qcm:{ordinal - 1}") for ordinal in target_ordinals
    }
    return [
        issue
        for issue in validation.issues
        if issue.question_id is None or issue.question_id in target_ids
    ]


def _provider_hit_output_limit(result: ProviderResult) -> bool:
    return result.raw_envelope.get("done_reason") == "length"


def _drop_unresolved_target(
    request: GenerationRequest,
    working_content: GeneratedContentBatch,
    target_ordinals: list[int],
) -> tuple[GeneratedContentBatch, str]:
    target_ids = {
        _digest(f"{request.generation_id}:qcm:{ordinal - 1}") for ordinal in target_ordinals
    }
    questions = [
        question
        for question in working_content.qcm_questions
        if question.question_id not in target_ids
    ]
    if not questions:
        raise GenerationStageError(
            "Output-limited correction shortfall would create an empty batch.",
            stage=FailureStage.MATERIALIZATION,
            code="empty_corrected_batch",
        )
    ordinals = ", ".join(str(ordinal) for ordinal in sorted(target_ordinals))
    reason = (
        "Local provider exhausted its bounded output while correcting question ordinal(s) "
        f"{ordinals}; malformed correction content was discarded."
    )
    return working_content.model_copy(update={"qcm_questions": questions}), reason


def _parse_provider_correction(
    result: ProviderResult,
    request: GenerationRequest,
    metadata: ProviderMetadata,
    working_content: GeneratedContentBatch,
    initial_content: GeneratedContentBatch,
    target_ordinals: list[int],
    *,
    enforce_difficulty: bool,
) -> tuple[GeneratedContentBatch, ProviderQCMCorrectionResponse]:
    try:
        response = ProviderQCMCorrectionResponse.model_validate_json(result.content)
    except ValidationError as exc:
        codes = {str(item.get("type")) for item in exc.errors(include_url=False)}
        code = "malformed_provider_json" if "json_invalid" in codes else "invalid_correction_schema"
        raise GenerationStageError(
            "Provider returned malformed targeted QCM correction JSON.",
            stage=FailureStage.STRUCTURED_PARSING,
            code=code,
            details=_pydantic_error_details(exc),
        ) from exc

    target_set = set(target_ordinals)
    replacement_ordinals = {
        replacement.question_ordinal for replacement in response.question_replacements
    }
    unexpected = sorted(replacement_ordinals - target_set)
    missing = sorted(target_set - replacement_ordinals)
    if unexpected:
        raise GenerationStageError(
            "Corrective response contains an unrequested question ordinal.",
            stage=FailureStage.MATERIALIZATION,
            code="retry_unrequested_question_change",
            details={"unexpected_question_ordinals": unexpected},
        )
    if missing and not response.insufficient_evidence:
        raise GenerationStageError(
            "Corrective response omitted required question replacements without a shortfall.",
            stage=FailureStage.MATERIALIZATION,
            code="incomplete_correction_response",
            details={"missing_question_ordinals": missing},
        )
    if response.insufficient_evidence and not missing:
        raise GenerationStageError(
            "Corrective shortfall declaration did not omit an unresolved question.",
            stage=FailureStage.MATERIALIZATION,
            code="invalid_shortfall_declaration",
        )

    initial_by_id = {question.question_id: question for question in initial_content.qcm_questions}
    working_by_id = {question.question_id: question for question in working_content.qcm_questions}
    for item in response.question_replacements:
        ordinal = item.question_ordinal
        question_id = _digest(f"{request.generation_id}:qcm:{ordinal - 1}")
        expected = initial_by_id[question_id]
        replacement = _materialize_question(
            item.replacement,
            index=ordinal - 1,
            request=request,
            metadata=metadata,
        )
        expected_chunk_id = expected.explanation.evidence[0].chunk_id
        actual_chunk_id = replacement.explanation.evidence[0].chunk_id
        if actual_chunk_id != expected_chunk_id:
            raise GenerationStageError(
                "Targeted correction moved a question to another evidence chunk.",
                stage=FailureStage.MATERIALIZATION,
                code="retry_evidence_chunk_changed",
                details={
                    "question_ordinal": ordinal,
                    "expected_chunk_id": expected_chunk_id,
                    "actual_chunk_id": actual_chunk_id,
                },
            )
        if enforce_difficulty and replacement.difficulty is not expected.difficulty:
            raise GenerationStageError(
                "Targeted correction changed an ordinal's already-valid difficulty.",
                stage=FailureStage.MATERIALIZATION,
                code="retry_difficulty_changed",
                details={
                    "question_ordinal": ordinal,
                    "expected_difficulty": expected.difficulty.value,
                    "actual_difficulty": replacement.difficulty.value,
                },
            )
        working_by_id[question_id] = replacement

    for ordinal in missing:
        working_by_id.pop(_digest(f"{request.generation_id}:qcm:{ordinal - 1}"), None)
    ordered_questions = [
        working_by_id[question_id]
        for index in range(request.configuration.count)
        if (question_id := _digest(f"{request.generation_id}:qcm:{index}")) in working_by_id
    ]
    if not ordered_questions:
        raise GenerationStageError(
            "Targeted correction shortfall would create an empty batch.",
            stage=FailureStage.MATERIALIZATION,
            code="empty_corrected_batch",
        )
    return working_content.model_copy(update={"qcm_questions": ordered_questions}), response


def generate_content(
    dataset_path: Path,
    configuration: GenerationConfiguration,
    provider: GenerationProvider,
    *,
    output_root: Path = Path("data/generated"),
    failure_output_root: Path = Path("data/generated-failures"),
) -> GenerationResult:
    """Generate, validate, and atomically persist only draft/unreviewed QCM content."""
    plan = build_generation_plan(dataset_path, configuration, output_root=output_root)
    if plan.proposed_output_directory.exists():
        raise GenerationOutputExistsError(
            f"Generation output already exists: {plan.proposed_output_directory}"
        )
    for protected_root in (
        Path("pdfsrc"),
        Path("data/processed"),
        Path("data/derived"),
        Path("data/reports"),
        Path("data/docling-models"),
        output_root,
    ):
        ensure_output_outside_source(failure_output_root, protected_root)
    generation_started = datetime.now(timezone.utc)
    messages = plan.messages
    provider_response_schema = plan.provider_response_schema
    parent_attempt_id: str | None = None
    retry_issue_codes: list[str] = []
    previous_question_count: int | None = None
    question_count_changed: bool | None = None
    initial_content: GeneratedContentBatch | None = None
    working_content: GeneratedContentBatch | None = None
    accepted_provider_result: ProviderResult | None = None
    accepted_provider_metadata: ProviderMetadata | None = None
    target_ordinals: list[int] = []
    enforce_initial_difficulty = False
    operational_shortfall_reasons: list[str] = []

    for validation_retry_sequence in range(configuration.validation_retry_count + 1):
        attempt_started = datetime.now(timezone.utc)
        try:
            provider_result = provider.generate(
                messages,
                configuration,
                provider_response_schema,
            )
        except GenerationProviderError as exc:
            raw_response = _raw_response_record(
                raw_response_text=exc.raw_response_text,
                raw_envelope=exc.raw_envelope,
                content=exc.content,
                http_status=exc.http_status,
            )
            issue = ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="provider_response_failure",
                message=str(exc),
                details={"http_status": exc.http_status},
            )
            validation = GenerationValidationReport(
                generation_id=plan.request.generation_id,
                status=ReportStatus.FAILED,
                issue_count=1,
                issues=[issue],
            )
            raise _persist_failure(
                plan=plan,
                started_at=attempt_started,
                stage=FailureStage.PROVIDER_RESPONSE,
                code=issue.code,
                exception=exc,
                provider_attempt_count=exc.attempt_count,
                raw_response=raw_response,
                provider_metadata=_failed_provider_metadata(configuration, exc),
                validation=validation,
                grounding=_empty_grounding_report(plan.request),
                failure_output_root=failure_output_root,
                parent_attempt_id=parent_attempt_id,
                validation_retry_sequence=validation_retry_sequence,
                retry_issue_codes=retry_issue_codes,
            ) from exc

        metadata = _provider_metadata(configuration, provider_result)
        raw_response = _raw_response_record(
            raw_response_text=provider_result.raw_response_text,
            raw_envelope=provider_result.raw_envelope,
            content=provider_result.content,
            http_status=provider_result.http_status,
        )
        content: GeneratedContentBatch | None = None
        structured_response: ProviderQCMResponse | ProviderQCMCorrectionResponse | None = None
        grounding = _empty_grounding_report(plan.request)
        try:
            if validation_retry_sequence == 0:
                content, structured_response = _parse_provider_content(
                    provider_result, plan.request, metadata
                )
            else:
                assert working_content is not None and initial_content is not None
                content, structured_response = _parse_provider_correction(
                    provider_result,
                    plan.request,
                    metadata,
                    working_content,
                    initial_content,
                    target_ordinals,
                    enforce_difficulty=enforce_initial_difficulty,
                )
        except GenerationStageError as exc:
            issue = ValidationIssue(
                severity=IssueSeverity.ERROR,
                code=exc.code,
                message=str(exc),
                chunk_ids=([str(exc.details["chunk_id"])] if "chunk_id" in exc.details else []),
                details=exc.details,
            )
            validation = GenerationValidationReport(
                generation_id=plan.request.generation_id,
                status=ReportStatus.FAILED,
                issue_count=1,
                issues=[issue],
            )
            failed = _persist_failure(
                plan=plan,
                started_at=attempt_started,
                stage=exc.stage,
                code=exc.code,
                exception=exc,
                provider_attempt_count=provider_result.attempt_count,
                raw_response=raw_response,
                provider_metadata=metadata,
                validation=validation,
                grounding=grounding,
                failure_output_root=failure_output_root,
                parent_attempt_id=parent_attempt_id,
                validation_retry_sequence=validation_retry_sequence,
                retry_issue_codes=retry_issue_codes,
            )
            if (
                validation_retry_sequence > 0
                and working_content is not None
                and initial_content is not None
                and target_ordinals
                and _provider_hit_output_limit(provider_result)
            ):
                working_content, shortfall_reason = _drop_unresolved_target(
                    plan.request,
                    working_content,
                    target_ordinals,
                )
                operational_shortfall_reasons.append(shortfall_reason)
                grounding, validation = validate_generated_content(
                    working_content,
                    plan.request,
                    plan.dataset,
                    insufficient_evidence=True,
                    shortfall_reason=" ".join(operational_shortfall_reasons),
                )
                parent_attempt_id = failed.failure_directory.name
                retry_issue_codes = sorted({item.code for item in validation.issues})
                previous_question_count = len(working_content.qcm_questions)
                if validation.status is not ReportStatus.FAILED:
                    content = working_content
                    retry_issue_codes = sorted(set(retry_issue_codes) | {exc.code})
                    question_count_changed = True
                    finished = datetime.now(timezone.utc)
                    break
                target_ordinals = _targeted_retry_ordinals(plan.request, validation)[:1]
                if not target_ordinals or (
                    validation_retry_sequence >= configuration.validation_retry_count
                ):
                    raise failed from exc
                supplied_issues = _correction_issues(
                    plan.request,
                    validation,
                    target_ordinals,
                )
                retry_issue_codes = sorted({item.code for item in supplied_issues})
                messages = build_qcm_corrective_messages(
                    supplied_issues,
                    working_content,
                    retry_sequence=validation_retry_sequence + 1,
                    target_ordinals=target_ordinals,
                )
                numeric_target_ordinals = {
                    ordinal
                    for ordinal in target_ordinals
                    if any(
                        issue.code == "unsupported_numeric_claim"
                        and issue.question_id
                        == _digest(f"{plan.request.generation_id}:qcm:{ordinal - 1}")
                        for issue in supplied_issues
                    )
                }
                provider_response_schema = build_qcm_correction_schema(
                    plan.request.source,
                    initial_content,
                    working_content,
                    target_ordinals,
                    enforce_difficulty=enforce_initial_difficulty,
                    numeric_target_ordinals=numeric_target_ordinals,
                )
                continue
            if (
                validation_retry_sequence >= configuration.validation_retry_count
                or working_content is None
                or initial_content is None
            ):
                raise failed from exc
            retry_issue_codes = sorted({item.code for item in validation.issues})
            parent_attempt_id = failed.failure_directory.name
            messages = build_qcm_corrective_messages(
                validation.issues,
                working_content,
                retry_sequence=validation_retry_sequence + 1,
                target_ordinals=target_ordinals,
            )
            continue

        assert content is not None and structured_response is not None
        accepted_provider_result = provider_result
        accepted_provider_metadata = metadata
        current_question_count = len(content.qcm_questions)
        question_count_changed = (
            current_question_count != previous_question_count
            if previous_question_count is not None
            else None
        )
        grounding, validation = validate_generated_content(
            content,
            plan.request,
            plan.dataset,
            insufficient_evidence=(
                structured_response.insufficient_evidence or bool(operational_shortfall_reasons)
            ),
            shortfall_reason=(
                " ".join(operational_shortfall_reasons)
                if operational_shortfall_reasons
                else structured_response.shortfall_reason
            ),
        )
        if validation.status is ReportStatus.FAILED:
            if initial_content is None:
                initial_content = content
                enforce_initial_difficulty = not any(
                    issue.code == "difficulty_distribution_mismatch" for issue in validation.issues
                )
            working_content = content
            validation_failure = GenerationStageError(
                "Generated content failed grounding or provenance validation.",
                stage=FailureStage.CONTENT_VALIDATION,
                code="content_validation_failed",
            )
            failed = _persist_failure(
                plan=plan,
                started_at=attempt_started,
                stage=FailureStage.CONTENT_VALIDATION,
                code=validation_failure.code,
                exception=validation_failure,
                provider_attempt_count=provider_result.attempt_count,
                raw_response=raw_response,
                provider_metadata=metadata,
                validation=validation,
                grounding=grounding,
                failure_output_root=failure_output_root,
                parent_attempt_id=parent_attempt_id,
                validation_retry_sequence=validation_retry_sequence,
                retry_issue_codes=retry_issue_codes,
                question_count_changed=question_count_changed,
            )
            if validation_retry_sequence >= configuration.validation_retry_count:
                raise failed from validation_failure
            target_ordinals = _targeted_retry_ordinals(plan.request, validation)
            if not target_ordinals:
                raise failed from validation_failure
            target_ordinals = target_ordinals[:1]
            supplied_issues = _correction_issues(
                plan.request,
                validation,
                target_ordinals,
            )
            retry_issue_codes = sorted({item.code for item in supplied_issues})
            parent_attempt_id = failed.failure_directory.name
            previous_question_count = current_question_count
            messages = build_qcm_corrective_messages(
                supplied_issues,
                content,
                retry_sequence=validation_retry_sequence + 1,
                target_ordinals=target_ordinals,
            )
            assert initial_content is not None
            numeric_target_ordinals = {
                ordinal
                for ordinal in target_ordinals
                if any(
                    issue.code == "unsupported_numeric_claim"
                    and issue.question_id
                    == _digest(f"{plan.request.generation_id}:qcm:{ordinal - 1}")
                    for issue in supplied_issues
                )
            }
            provider_response_schema = build_qcm_correction_schema(
                plan.request.source,
                initial_content,
                content,
                target_ordinals,
                enforce_difficulty=enforce_initial_difficulty,
                numeric_target_ordinals=numeric_target_ordinals,
            )
            continue

        finished = datetime.now(timezone.utc)
        break
    else:  # pragma: no cover - the bounded loop always returns, breaks, or raises
        raise AssertionError("Validation retry loop terminated unexpectedly.")

    assert accepted_provider_result is not None
    assert accepted_provider_metadata is not None

    paths = [
        str(plan.proposed_output_directory / name)
        for name in (
            "request.json",
            "selected-sources.json",
            "raw-provider-response.json",
            "generated-content.json",
            "grounding-report.json",
            "validation-report.json",
            "generation-report.json",
        )
    ]
    report = GenerationReport(
        generation_id=plan.request.generation_id,
        start_time=generation_started,
        completion_time=finished,
        status=validation.status,
        provider_metadata=accepted_provider_metadata,
        requested_count=configuration.count,
        generated_count=len(content.qcm_questions),
        selected_chunk_ids=[chunk.chunk_id for chunk in plan.request.source.selected_chunks],
        warnings=[
            issue.message for issue in validation.issues if issue.severity.value == "warning"
        ],
        errors=[],
        output_paths=paths,
        parent_attempt_id=parent_attempt_id,
        validation_retry_sequence=validation_retry_sequence,
        retry_issue_codes=retry_issue_codes,
        question_count_changed=question_count_changed,
    )
    output_directory = write_generation_output(
        plan.request,
        accepted_provider_result,
        content,
        grounding,
        validation,
        report,
        output_root=output_root,
    )
    return GenerationResult(output_directory, content, grounding, validation, report)
