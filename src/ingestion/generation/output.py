"""Protected directory-level atomic persistence for generated content."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from ingestion.generation.models import (
    FailureReport,
    GeneratedContentBatch,
    GenerationReport,
    GenerationRequest,
    GenerationValidationReport,
    GroundingReport,
    RawProviderResponseRecord,
    ReviewStatus,
)
from ingestion.generation.providers.base import ProviderResult


class GenerationOutputExistsError(FileExistsError):
    """Generated or reviewed content is immutable and cannot be overwritten."""


class GenerationFailureOutputExistsError(FileExistsError):
    """A failed attempt is append-only and cannot be overwritten."""


def generation_output_directory(output_root: Path, document_id: str, generation_id: str) -> Path:
    return output_root / document_id / "qcm" / generation_id


def generation_failure_directory(
    failure_root: Path, document_id: str, generation_id: str, attempt_id: str
) -> Path:
    return failure_root / document_id / "qcm" / generation_id / attempt_id


def _write_model(path: Path, value: BaseModel) -> None:
    path.write_text(value.model_dump_json(indent=2) + "\n", encoding="utf-8")


def write_generation_output(
    request: GenerationRequest,
    provider_result: ProviderResult,
    content: GeneratedContentBatch,
    grounding: GroundingReport,
    validation: GenerationValidationReport,
    report: GenerationReport,
    *,
    output_root: Path,
) -> Path:
    """Write a complete generation only after all models have validated."""
    if any(
        question.medical_review.status is not ReviewStatus.UNREVIEWED
        for question in content.qcm_questions
    ):
        raise ValueError("Generation output may contain only unreviewed drafts.")
    final = generation_output_directory(
        output_root, request.source.document_id, request.generation_id
    )
    if final.exists():
        raise GenerationOutputExistsError(f"Generation output already exists: {final}")
    final.parent.mkdir(parents=True, exist_ok=True)
    temporary = final.parent / f".{final.name}.{uuid4().hex}.tmp"
    temporary.mkdir()
    try:
        _write_model(temporary / "request.json", request)
        _write_model(temporary / "selected-sources.json", request.source)
        (temporary / "raw-provider-response.json").write_text(
            json.dumps(provider_result.raw_envelope, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        _write_model(temporary / "generated-content.json", content)
        _write_model(temporary / "grounding-report.json", grounding)
        _write_model(temporary / "validation-report.json", validation)
        _write_model(temporary / "generation-report.json", report)
        GenerationRequest.model_validate_json((temporary / "request.json").read_text())
        GeneratedContentBatch.model_validate_json(
            (temporary / "generated-content.json").read_text()
        )
        final.parent.mkdir(parents=True, exist_ok=True)
        temporary.rename(final)
        return final
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def write_generation_failure(
    request: GenerationRequest,
    raw_response: RawProviderResponseRecord,
    validation: GenerationValidationReport,
    grounding: GroundingReport,
    failure: FailureReport,
    *,
    failure_root: Path,
) -> Path:
    """Atomically persist diagnostics without creating successful generated content."""
    final = generation_failure_directory(
        failure_root,
        request.source.document_id,
        request.generation_id,
        failure.attempt_id,
    )
    if final.exists():
        raise GenerationFailureOutputExistsError(f"Failed attempt already exists: {final}")
    final.parent.mkdir(parents=True, exist_ok=True)
    temporary = final.parent / f".{final.name}.{uuid4().hex}.tmp"
    temporary.mkdir()
    try:
        _write_model(temporary / "request.json", request)
        _write_model(temporary / "selected-sources.json", request.source)
        _write_model(temporary / "raw-provider-response.json", raw_response)
        _write_model(temporary / "validation-report.json", validation)
        _write_model(temporary / "grounding-report.json", grounding)
        _write_model(temporary / "failure-report.json", failure)

        GenerationRequest.model_validate_json((temporary / "request.json").read_text())
        RawProviderResponseRecord.model_validate_json(
            (temporary / "raw-provider-response.json").read_text()
        )
        GenerationValidationReport.model_validate_json(
            (temporary / "validation-report.json").read_text()
        )
        GroundingReport.model_validate_json((temporary / "grounding-report.json").read_text())
        FailureReport.model_validate_json((temporary / "failure-report.json").read_text())
        if (temporary / "generated-content.json").exists():
            raise ValueError("Failed attempt must not contain generated-content.json.")
        temporary.rename(final)
        return final
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
