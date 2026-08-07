"""Explicit human review transitions for generated content."""

from __future__ import annotations

from pathlib import Path

from ingestion.generation.models import (
    GeneratedContentBatch,
    HumanReviewState,
    ReviewDecision,
    ReviewStatus,
)
from ingestion.output import write_json_atomic


class ReviewTransitionError(ValueError):
    """A requested review transition is invalid or would overwrite reviewed content."""


def review_content(
    generation_directory: Path,
    *,
    decision: ReviewStatus,
    reviewer: str,
    notes: str | None = None,
    question_id: str | None = None,
) -> GeneratedContentBatch:
    """Apply one terminal human decision to one or all unreviewed questions."""
    if decision is ReviewStatus.UNREVIEWED:
        raise ReviewTransitionError("A review decision cannot be unreviewed.")
    path = generation_directory / "generated-content.json"
    batch = GeneratedContentBatch.model_validate_json(path.read_text(encoding="utf-8"))
    targets = [
        question
        for question in batch.qcm_questions
        if question_id is None or question.question_id == question_id
    ]
    if not targets:
        raise ReviewTransitionError("No matching generated question was found.")
    if any(question.medical_review.status is not ReviewStatus.UNREVIEWED for question in targets):
        raise ReviewTransitionError("Accepted, rejected, and needs_revision states are terminal.")
    review_decision = ReviewDecision(decision=decision, reviewer=reviewer, notes=notes)
    target_ids = {question.question_id for question in targets}
    updated_questions = [
        question.model_copy(
            update={
                "medical_review": HumanReviewState(
                    status=decision,
                    decisions=[review_decision],
                )
            }
        )
        if question.question_id in target_ids
        else question
        for question in batch.qcm_questions
    ]
    updated = batch.model_copy(update={"qcm_questions": updated_questions})
    updated = GeneratedContentBatch.model_validate(updated.model_dump(mode="json"))
    write_json_atomic(path, updated.model_dump(mode="json"))
    return updated
