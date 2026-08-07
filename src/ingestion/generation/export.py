"""Export only explicitly accepted QCM content."""

from __future__ import annotations

from pathlib import Path

from ingestion.generation.models import GeneratedContentBatch, ReviewStatus
from ingestion.output import write_json_atomic


class QuestionBankExistsError(FileExistsError):
    """Question-bank exports are protected from accidental overwrite."""


def export_question_bank(generation_directories: list[Path], output_path: Path) -> int:
    """Atomically export accepted questions from validated generation directories."""
    if output_path.exists():
        raise QuestionBankExistsError(f"Question-bank export already exists: {output_path}")
    accepted: list[dict[str, object]] = []
    for directory in generation_directories:
        batch = GeneratedContentBatch.model_validate_json(
            (directory / "generated-content.json").read_text(encoding="utf-8")
        )
        accepted.extend(
            question.model_dump(mode="json")
            for question in batch.qcm_questions
            if question.medical_review.status is ReviewStatus.ACCEPTED
        )
    write_json_atomic(
        output_path,
        {
            "generation_schema_version": "1.0.0",
            "content_type": "qcm",
            "accepted_question_count": len(accepted),
            "questions": accepted,
        },
    )
    return len(accepted)
