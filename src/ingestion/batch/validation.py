"""Validation of existing pipeline artifacts before batch reuse."""

from __future__ import annotations

import json
from pathlib import Path

from ingestion.batch.models import BatchStage, ExistingOutputState
from ingestion.chunking.validation import validate_chunk_collection_file
from ingestion.datasets.validation import validate_dataset_file
from ingestion.normalization.models import TechnicalSuitability
from ingestion.normalization.normalizer import infer_office_technical_suitability
from ingestion.normalization.validation import validate_document_file
from ingestion.ocr.validation import validate_derivative_file

READY = {
    TechnicalSuitability.READY_FOR_CHUNKING.value,
    TechnicalSuitability.READY_WITH_WARNINGS.value,
}
ACCEPTED_OCR = {"accepted", "accepted_with_warnings"}


def inspect_existing_outputs(
    *,
    output_root: Path,
    source_sha256: str,
    source_relative_path: str,
    source_root: Path = Path("pdfsrc"),
) -> ExistingOutputState:
    """Return the furthest genuinely validated artifact state for one source."""
    source_directory = output_root / source_sha256
    candidates = [source_directory / "document.json"]
    variants = source_directory / "variants"
    if variants.is_dir():
        candidates.extend(
            sorted(variants.glob("*/document.json"), key=lambda path: path.as_posix())
        )
    states = [
        _validate_canonical_candidate(path, source_sha256, source_relative_path, source_root)
        for path in candidates
        if path.is_file()
    ]
    if not states:
        return ExistingOutputState()
    return max(
        states,
        key=lambda state: (
            state.complete,
            _stage_rank(state.last_valid_stage),
            state.canonical_path or "",
        ),
    )


def _validate_canonical_candidate(
    path: Path, source_sha256: str, source_relative_path: str, source_root: Path
) -> ExistingOutputState:
    warnings: list[str] = []
    try:
        document = validate_document_file(path)
    except (OSError, ValueError) as exc:
        return ExistingOutputState(validation_warnings=[f"Invalid canonical output: {exc}"])
    if document.sha256 != source_sha256 or document.document_id != source_sha256:
        return ExistingOutputState(validation_warnings=["Canonical source SHA-256 mismatch."])
    if document.source_relative_path != source_relative_path:
        return ExistingOutputState(validation_warnings=["Canonical source-relative path mismatch."])

    derivative = document.metadata.get("derivative_provenance")
    derivative_path: str | None = None
    if isinstance(derivative, dict):
        if derivative.get("quality_outcome") not in ACCEPTED_OCR:
            return ExistingOutputState(
                canonical_path=str(path),
                last_valid_stage=BatchStage.CANONICAL_VALIDATED,
                validation_warnings=["Canonical OCR provenance is rejected."],
            )
        if derivative.get("original_source_sha256") != source_sha256:
            return ExistingOutputState(
                validation_warnings=["Canonical OCR provenance source mismatch."]
            )
        raw_derivative_path = derivative.get("derivative_relative_path")
        derivative_path = str(raw_derivative_path) if raw_derivative_path else None
        if derivative_path is None:
            return ExistingOutputState(
                validation_warnings=["Canonical OCR provenance lacks a derivative path."]
            )
        pdf_path = Path(derivative_path)
        if not pdf_path.is_absolute():
            pdf_path = Path.cwd() / pdf_path
        try:
            validated_derivative, _ = validate_derivative_file(
                pdf_path.parent / "derivative.json", source_root=source_root
            )
        except (OSError, ValueError) as exc:
            return ExistingOutputState(
                validation_warnings=[f"OCR derivative validation failed: {exc}"]
            )
        if validated_derivative.derivative_id != derivative.get(
            "derivative_id"
        ) or validated_derivative.derivative_sha256 != derivative.get("derivative_sha256"):
            return ExistingOutputState(
                validation_warnings=["Canonical OCR derivative identity mismatch."]
            )

    quality = document.metadata.get("extraction_quality", {})
    suitability = quality.get("technical_suitability") if isinstance(quality, dict) else None
    report_path = path.parent / "processing-report.json"
    if report_path.is_file():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            suitability = report.get("technical_suitability") or suitability
            warnings.extend(str(item) for item in report.get("warnings", []))
        except (OSError, json.JSONDecodeError, TypeError):
            warnings.append("Processing report is invalid or unreadable.")
    if suitability is None:
        inferred = infer_office_technical_suitability(document)
        if inferred is not None:
            suitability = inferred.value
            warnings.append(
                "Technical suitability was inferred from validated Office canonical content "
                "for backward-compatible resume."
            )

    state = ExistingOutputState(
        canonical_path=str(path),
        derivative_path=derivative_path,
        last_valid_stage=BatchStage.CANONICAL_VALIDATED,
        suitability=str(suitability) if suitability is not None else None,
        validation_warnings=warnings,
    )
    if state.suitability not in READY:
        return state

    chunks_path = path.parent / "chunks" / "chunks.json"
    try:
        collection = validate_chunk_collection_file(chunks_path)
        if collection.document_id != source_sha256 or collection.source_sha256 != source_sha256:
            raise ValueError("Chunk provenance mismatch.")
    except (OSError, ValueError) as exc:
        state.validation_warnings.append(f"Chunks require rebuild: {exc}")
        return state
    state.chunk_path = str(chunks_path)
    state.last_valid_stage = BatchStage.CHUNKS_VALIDATED

    dataset_path = path.parent / "datasets" / "ai-ready-dataset.json"
    try:
        dataset = validate_dataset_file(dataset_path)
        if dataset.document_id != source_sha256 or dataset.source_sha256 != source_sha256:
            raise ValueError("Dataset provenance mismatch.")
        if dataset.source_relative_path != source_relative_path:
            raise ValueError("Dataset source-relative path mismatch.")
    except (OSError, ValueError) as exc:
        state.validation_warnings.append(f"Dataset requires rebuild: {exc}")
        return state
    state.dataset_path = str(dataset_path)
    state.last_valid_stage = BatchStage.DATASET_VALIDATED
    eligible = sum(chunk.eligible_for_generation for chunk in dataset.chunks)
    coverage = dataset.processing_statistics.source_reference_coverage
    state.generation_ready = eligible > 0 and coverage > 0
    if not state.generation_ready:
        state.validation_warnings.append(
            "Validated dataset is not generation-ready: at least one eligible, "
            "grounded chunk is required."
        )
        return state
    state.complete = True
    state.last_valid_stage = BatchStage.COMPLETE
    return state


def _stage_rank(stage: BatchStage) -> int:
    return list(BatchStage).index(stage)
