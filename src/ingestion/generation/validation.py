"""Technical validation for source-grounded generated QCM drafts."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from ingestion.datasets.models import AIReadyDataset
from ingestion.generation.evidence import EvidenceResolutionError, resolve_chunk_evidence_span
from ingestion.generation.models import (
    GeneratedContentBatch,
    GenerationRequest,
    GenerationValidationReport,
    GroundingReport,
    IssueSeverity,
    QCMQuestion,
    ReportStatus,
    ReviewStatus,
    ValidationIssue,
)

_WORD = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
_NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?\b")
_SOURCE_CORRECTION_PHRASES = (
    "likely a typo",
    "probable typo",
    "should be interpreted as",
    "likely an error",
    "erreur probable",
    "coquille probable",
    "doit être interprété",
    "doit etre interprete",
    "semble être une erreur",
    "semble etre une erreur",
)
_STOP_WORDS = {
    "avec",
    "dans",
    "des",
    "elle",
    "est",
    "les",
    "leur",
    "mais",
    "pour",
    "que",
    "qui",
    "sont",
    "sur",
    "une",
}


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def _tokens(value: str) -> set[str]:
    return {
        token for token in _WORD.findall(_normalized(value).casefold()) if token not in _STOP_WORDS
    }


def _reference_key(value: object) -> str:
    from ingestion.normalization.models import SourceReference

    reference = SourceReference.model_validate(value)
    return reference.model_dump_json(exclude_none=False)


def _question_claim(question: QCMQuestion) -> str:
    correct = set(question.correct_answer.choice_ids)
    answers = [choice.text for choice in question.choices if choice.choice_id in correct]
    return " ".join([*answers, question.explanation.text])


def _all_claim_text(question: QCMQuestion) -> str:
    return " ".join(
        [question.stem, *(choice.text for choice in question.choices), question.explanation.text]
    )


def _near_duplicate(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union) if union else 1.0


def _status(issues: Iterable[ValidationIssue]) -> ReportStatus:
    values = list(issues)
    if any(issue.severity is IssueSeverity.ERROR for issue in values):
        return ReportStatus.FAILED
    if values:
        return ReportStatus.NEEDS_REVISION
    return ReportStatus.SUCCESS


def validate_generated_content(
    batch: GeneratedContentBatch,
    request: GenerationRequest,
    dataset: AIReadyDataset,
    *,
    insufficient_evidence: bool = False,
    shortfall_reason: str | None = None,
) -> tuple[GroundingReport, GenerationValidationReport]:
    """Validate structure, provenance, evidence quotations, and lexical source support.

    These checks establish technical traceability only. They do not establish medical
    correctness, clinical validity, or publication fitness.
    """
    grounding_issues: list[ValidationIssue] = []
    validation_issues: list[ValidationIssue] = []
    needs_revision: set[str] = set()
    chunks = {chunk.chunk_id: chunk for chunk in dataset.chunks}
    selected_ids = {chunk.chunk_id for chunk in request.source.selected_chunks}
    excluded_ids = set(request.source.excluded_chunk_ids)

    if batch.generation_id != request.generation_id or batch.request_id != request.generation_id:
        validation_issues.append(
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="generation_identity_mismatch",
                message="Generated content does not match its request identity.",
            )
        )
    if batch.document_id != dataset.document_id or batch.source_sha256 != dataset.source_sha256:
        validation_issues.append(
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="document_identity_mismatch",
                message="Generated batch source identity does not match the validated dataset.",
            )
        )
    actual_count = len(batch.qcm_questions)
    requested_count = request.configuration.count
    valid_shortfall = (
        actual_count < requested_count
        and actual_count > 0
        and insufficient_evidence
        and bool((shortfall_reason or "").strip())
    )
    if valid_shortfall:
        validation_issues.append(
            ValidationIssue(
                severity=IssueSeverity.WARNING,
                code="insufficient_grounded_questions",
                message="Provider explicitly returned fewer grounded questions than requested.",
                details={
                    "expected_count": requested_count,
                    "actual_count": actual_count,
                    "shortfall_reason": shortfall_reason,
                },
            )
        )
        needs_revision.update(question.question_id for question in batch.qcm_questions)
    elif actual_count != requested_count:
        validation_issues.append(
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="question_count_mismatch",
                message="Provider output count does not match the generation request.",
                details={
                    "expected_count": requested_count,
                    "actual_count": actual_count,
                    "insufficient_evidence": insufficient_evidence,
                    "shortfall_reason": shortfall_reason,
                },
            )
        )
    if insufficient_evidence and not valid_shortfall:
        validation_issues.append(
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="invalid_shortfall_declaration",
                message=(
                    "The provider shortfall declaration contradicts the returned question count."
                ),
                details={
                    "expected_count": requested_count,
                    "actual_count": actual_count,
                    "shortfall_reason": shortfall_reason,
                },
            )
        )
    if not insufficient_evidence and shortfall_reason is not None:
        validation_issues.append(
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="invalid_shortfall_declaration",
                message="A shortfall reason requires insufficient_evidence=true.",
                details={"shortfall_reason": shortfall_reason},
            )
        )
    actual_difficulty_distribution = {
        difficulty: sum(question.difficulty is difficulty for question in batch.qcm_questions)
        for difficulty in request.configuration.difficulty_distribution
    }
    distribution_matches = (
        all(
            actual_difficulty_distribution[difficulty] <= expected
            for difficulty, expected in request.configuration.difficulty_distribution.items()
        )
        if valid_shortfall
        else actual_difficulty_distribution == request.configuration.difficulty_distribution
    )
    if not distribution_matches:
        validation_issues.append(
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="difficulty_distribution_mismatch",
                message="Generated difficulty counts do not match the generation request.",
                details={
                    "expected_distribution": {
                        key.value: value
                        for key, value in request.configuration.difficulty_distribution.items()
                    },
                    "actual_distribution": {
                        key.value: value for key, value in actual_difficulty_distribution.items()
                    },
                },
            )
        )

    stems: list[tuple[str, str]] = []
    for question in batch.qcm_questions:
        question_id = question.question_id
        if question.medical_review.status is not ReviewStatus.UNREVIEWED:
            validation_issues.append(
                ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="invalid_initial_review_state",
                    message="New generated content must be unreviewed.",
                    question_id=question_id,
                )
            )
        if (
            question.source_document_id != dataset.document_id
            or question.source_sha256 != dataset.source_sha256
        ):
            grounding_issues.append(
                ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="question_source_identity_mismatch",
                    message="Question source identity differs from the validated dataset.",
                    question_id=question_id,
                )
            )
        cited_ids = set(question.source_chunk_ids)
        for chunk_id in sorted(cited_ids):
            if chunk_id not in chunks:
                grounding_issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="nonexistent_chunk_reference",
                        message="A cited chunk does not exist in the validated dataset.",
                        question_id=question_id,
                        chunk_ids=[chunk_id],
                        details={"cited_chunk_id": chunk_id},
                    )
                )
                continue
            chunk = chunks[chunk_id]
            if not chunk.eligible_for_generation or chunk_id in excluded_ids:
                grounding_issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="excluded_chunk_used",
                        message="An excluded or ineligible chunk was used as evidence.",
                        question_id=question_id,
                        chunk_ids=[chunk_id],
                        details={
                            "eligible_for_generation": chunk.eligible_for_generation,
                            "generation_exclusion_reasons": chunk.generation_exclusion_reasons,
                        },
                    )
                )
            if chunk_id not in selected_ids:
                grounding_issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="unselected_chunk_used",
                        message="Evidence must come from the deterministic selected source set.",
                        question_id=question_id,
                        chunk_ids=[chunk_id],
                        details={"selected_chunk_ids": sorted(selected_ids)},
                    )
                )
        if len(question.explanation.evidence) != 1:
            grounding_issues.append(
                ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="incoherent_evidence_span",
                    message="Each generated question must contain exactly one evidence span.",
                    question_id=question_id,
                    chunk_ids=sorted(cited_ids),
                    details={"evidence_span_count": len(question.explanation.evidence)},
                )
            )

        retained_evidence: list[str] = []
        for evidence in question.explanation.evidence:
            if evidence.chunk_id not in cited_ids or evidence.chunk_id not in chunks:
                grounding_issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="invalid_evidence_chunk",
                        message="Evidence cites a nonexistent or undeclared source chunk.",
                        question_id=question_id,
                        chunk_ids=[evidence.chunk_id],
                        details={"quotation": evidence.quotation},
                    )
                )
                continue
            if cited_ids != {evidence.chunk_id}:
                grounding_issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="invalid_evidence_chunk",
                        message="Question chunk provenance must identify only its evidence chunk.",
                        question_id=question_id,
                        chunk_ids=sorted(cited_ids),
                        details={"evidence_chunk_id": evidence.chunk_id},
                    )
                )
            chunk = chunks[evidence.chunk_id]
            known_reference_keys = {
                _reference_key(reference) for reference in chunk.source_references
            }
            actual_reference_keys = [
                _reference_key(reference) for reference in question.source_references
            ]
            unknown_references = [
                key for key in actual_reference_keys if key not in known_reference_keys
            ]
            block_ids = [
                reference.block_id
                for reference in question.source_references
                if reference.block_id is not None
            ]
            if unknown_references or len(block_ids) != len(question.source_references):
                grounding_issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="source_reference_mismatch",
                        message=(
                            "Evidence source references are not exact references from its chunk."
                        ),
                        question_id=question_id,
                        chunk_ids=[evidence.chunk_id],
                        details={"unknown_source_references": unknown_references},
                    )
                )
                continue
            try:
                resolved = resolve_chunk_evidence_span(chunk, block_ids)
            except EvidenceResolutionError as exc:
                grounding_issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="source_reference_mismatch",
                        message=str(exc),
                        question_id=question_id,
                        chunk_ids=[evidence.chunk_id],
                        details={"resolution_code": exc.code, **exc.details},
                    )
                )
                continue
            expected_reference_keys = [
                _reference_key(reference) for reference in resolved.source_references
            ]
            if actual_reference_keys != expected_reference_keys:
                grounding_issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="source_reference_mismatch",
                        message=(
                            "Evidence source references differ from the resolved retained span."
                        ),
                        question_id=question_id,
                        chunk_ids=[evidence.chunk_id],
                    )
                )
                continue
            if evidence.quotation != resolved.quotation:
                grounding_issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="evidence_quotation_mismatch",
                        message="Evidence quotation differs from its exact retained evidence span.",
                        question_id=question_id,
                        chunk_ids=[evidence.chunk_id],
                        details={
                            "quotation": evidence.quotation,
                            "expected_quotation": resolved.quotation,
                        },
                    )
                )
            else:
                retained_evidence.append(_normalized(resolved.quotation))

        claim = _question_claim(question)
        all_claim_text = _all_claim_text(question)
        evidence_text = " ".join(retained_evidence)
        unsupported_numbers = sorted(
            set(_NUMBER.findall(all_claim_text)) - set(_NUMBER.findall(evidence_text))
        )
        if unsupported_numbers:
            grounding_issues.append(
                ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="unsupported_numeric_claim",
                    message=(
                        "A number in the stem, choices, or explanation is absent from exact "
                        "evidence."
                    ),
                    question_id=question_id,
                    chunk_ids=sorted(cited_ids),
                    details={"unsupported_numbers": unsupported_numbers},
                )
            )
        normalized_claim_text = _normalized(all_claim_text).casefold()
        correction_phrases = [
            phrase for phrase in _SOURCE_CORRECTION_PHRASES if phrase in normalized_claim_text
        ]
        if correction_phrases:
            grounding_issues.append(
                ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="source_correction_language",
                    message="Generated content attempts to correct or reinterpret the source.",
                    question_id=question_id,
                    chunk_ids=sorted(cited_ids),
                    details={"matched_phrases": correction_phrases},
                )
            )
        claim_tokens = _tokens(claim)
        evidence_tokens = _tokens(evidence_text)
        lexical_support = (
            len(claim_tokens & evidence_tokens) / len(claim_tokens) if claim_tokens else 0
        )
        if retained_evidence and lexical_support < 0.35:
            grounding_issues.append(
                ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    code="low_lexical_support",
                    message=(
                        "Answer and explanation have low lexical overlap with retained evidence; "
                        "human revision is required. This is not a medical-correctness judgment."
                    ),
                    question_id=question_id,
                    chunk_ids=sorted(cited_ids),
                    details={"lexical_support": lexical_support, "threshold": 0.35},
                )
            )
            needs_revision.add(question_id)

        normalized_stem = _normalized(question.stem).casefold()
        for prior_id, prior_stem in stems:
            if normalized_stem == prior_stem:
                validation_issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="duplicate_question",
                        message="Generated questions have identical normalized stems.",
                        question_id=question_id,
                        details={"duplicate_of_question_id": prior_id},
                    )
                )
            elif _near_duplicate(normalized_stem, prior_stem) >= 0.85:
                validation_issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.WARNING,
                        code="near_duplicate_question",
                        message=f"Question is near-duplicate of {prior_id}.",
                        question_id=question_id,
                        details={
                            "near_duplicate_of_question_id": prior_id,
                            "similarity_threshold": 0.85,
                        },
                    )
                )
                needs_revision.add(question_id)
        stems.append((question_id, normalized_stem))

    all_issues = [*grounding_issues, *validation_issues]
    error_questions = {
        issue.question_id
        for issue in grounding_issues
        if issue.severity is IssueSeverity.ERROR and issue.question_id is not None
    }
    grounding = GroundingReport(
        generation_id=request.generation_id,
        status=_status(grounding_issues),
        grounded_question_count=len(batch.qcm_questions) - len(error_questions),
        needs_revision_question_ids=sorted(needs_revision),
        issues=grounding_issues,
    )
    validation = GenerationValidationReport(
        generation_id=request.generation_id,
        status=_status(all_issues),
        issue_count=len(all_issues),
        issues=all_issues,
    )
    return grounding, validation
