"""Explicit OCRmyPDF execution and deterministic quality comparison."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import fitz  # type: ignore[import-untyped]

from ingestion.hashing import sha256_file
from ingestion.normalization.validation import validate_document_file
from ingestion.ocr.environment import check_ocr_environment
from ingestion.ocr.evaluator import LOW_TEXT_CHARACTERS, evaluate_ocr
from ingestion.ocr.models import (
    DERIVATIVE_SCHEMA_VERSION,
    DocumentDerivative,
    OCRConfiguration,
    OCREligibility,
    OCRProcessingReport,
    OCRQualityMetrics,
    OCRQualityOutcome,
    OCRSuitability,
    SourceRelationship,
)


class OCRExecutionError(RuntimeError):
    """Safe, concise OCR execution failure."""


@dataclass(frozen=True)
class OCRDerivativeResult:
    derivative: DocumentDerivative
    report: OCRProcessingReport
    directory: Path


@dataclass(frozen=True)
class PDFMetrics:
    page_count: int
    characters: list[int]
    images: list[int]


def deterministic_derivative_id(
    source_sha256: str, configuration: OCRConfiguration, tool_version: str
) -> str:
    payload = {
        "schema_version": DERIVATIVE_SCHEMA_VERSION,
        "source_sha256": source_sha256,
        "configuration": configuration.model_dump(mode="json"),
        "tool_version": tool_version,
    }
    stable = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(stable.encode("utf-8")).hexdigest()


def create_ocr_derivative(
    source: Path,
    configuration: OCRConfiguration,
    *,
    output_root: Path = Path("data/derived"),
    source_root: Path = Path("pdfsrc"),
    force: bool = False,
) -> OCRDerivativeResult:
    """Create one local derivative through an atomic sibling directory."""
    _ensure_output_safe(output_root, source_root)
    environment = check_ocr_environment(configuration.language_codes, output_root)
    if not environment.ready or environment.ocrmypdf_version is None:
        raise OCRExecutionError(
            "OCR environment is not ready; run check-ocr-environment for remediation."
        )
    evaluation = evaluate_ocr(source, source_root=source_root)
    allowed = {OCREligibility.RECOMMENDED, OCREligibility.REQUIRED}
    if evaluation.eligibility not in allowed and not configuration.force_ocr:
        raise OCRExecutionError(
            f"OCR eligibility is {evaluation.eligibility.value}: {evaluation.reason}"
        )
    if evaluation.source_sha256 is None or evaluation.page_count is None:
        raise OCRExecutionError("OCR source inspection did not produce a stable identity.")
    source_digest = evaluation.source_sha256
    derivative_id = deterministic_derivative_id(
        source_digest, configuration, environment.ocrmypdf_version
    )
    parent = output_root / source_digest / "ocr"
    final = parent / derivative_id
    temporary = parent / f".{derivative_id}.{uuid4().hex}.tmp"
    backup = parent / f".{derivative_id}.{uuid4().hex}.backup"
    if final.exists() and not force:
        raise FileExistsError(
            f"OCR derivative already exists for {derivative_id}; use --force to replace it."
        )
    parent.mkdir(parents=True, exist_ok=True)
    temporary.mkdir()
    started = datetime.now(timezone.utc)
    output_pdf = temporary / "document-ocr.pdf"
    log_path = temporary / "logs" / "ocrmypdf.log"
    log_path.parent.mkdir()
    command = _ocrmypdf_command(source, output_pdf, configuration)
    try:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=configuration.timeout_seconds + 30,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OCRExecutionError(
                f"OCRmyPDF exceeded the {configuration.timeout_seconds}-second timeout."
            ) from exc
        log_path.write_text(
            (completed.stdout or "")
            + ("\n" if completed.stdout else "")
            + (completed.stderr or ""),
            encoding="utf-8",
        )
        if completed.returncode != 0 or not output_pdf.is_file():
            raise OCRExecutionError(
                f"OCRmyPDF failed with return code {completed.returncode}; "
                "see the concise CLI error."
            )
        source_metrics = _pdf_metrics(source)
        derivative_metrics = _pdf_metrics(output_pdf)
        quality, quality_warnings = _quality_metrics(
            source_metrics, derivative_metrics, evaluation.image_heavy_pages
        )
        quality.canonical_blocks_before = _canonical_block_count(source_digest)
        outcome = _quality_outcome(quality)
        completed_at = datetime.now(timezone.utc)
        recorded_pdf = (final / "document-ocr.pdf").resolve()
        try:
            derivative_relative = recorded_pdf.relative_to(Path.cwd().resolve()).as_posix()
        except ValueError:
            derivative_relative = recorded_pdf.relative_to(output_root.resolve().parent).as_posix()
        warnings = list(quality_warnings)
        if configuration.skip_text and any(source_metrics.characters):
            warnings.append("OCRmyPDF skip-text policy skipped pages containing existing text.")
        suitability = {
            OCRQualityOutcome.ACCEPTED: OCRSuitability.READY_FOR_CHUNKING,
            OCRQualityOutcome.ACCEPTED_WITH_WARNINGS: OCRSuitability.READY_WITH_WARNINGS,
            OCRQualityOutcome.NO_MATERIAL_IMPROVEMENT: OCRSuitability.REQUIRES_OCR,
            OCRQualityOutcome.DEGRADED: OCRSuitability.UNSUITABLE,
            OCRQualityOutcome.INVALID: OCRSuitability.UNSUITABLE,
            OCRQualityOutcome.FAILED: OCRSuitability.FAILED,
        }[outcome]
        derivative = DocumentDerivative(
            derivative_id=derivative_id,
            source_sha256=source_digest,
            source_relative_path=evaluation.source_relative_path,
            source_filename=source.name,
            source_size_bytes=source.stat().st_size,
            derivative_sha256=sha256_file(output_pdf),
            derivative_relative_path=derivative_relative,
            derivative_size_bytes=output_pdf.stat().st_size,
            created_at=completed_at,
            tool_version=environment.ocrmypdf_version,
            configuration=configuration,
            language_codes=configuration.language_codes,
            page_count=derivative_metrics.page_count,
            source_relationship=SourceRelationship(
                original_source_sha256=source_digest,
                original_source_relative_path=evaluation.source_relative_path,
            ),
            validation_status=outcome,
            warnings=warnings,
            metadata={"quality_metrics": quality.model_dump(mode="json")},
        )
        report = OCRProcessingReport(
            derivative_id=derivative_id,
            start_time=started,
            completion_time=completed_at,
            duration_seconds=(completed_at - started).total_seconds(),
            source_file=evaluation.source_relative_path,
            output_file=derivative_relative,
            ocrmypdf_version=environment.ocrmypdf_version,
            tesseract_version=environment.tesseract_version or "unknown",
            requested_languages=configuration.language_codes,
            installed_language_validation=True,
            source_page_count=source_metrics.page_count,
            derivative_page_count=derivative_metrics.page_count,
            source_text_character_count=sum(source_metrics.characters),
            derivative_text_character_count=sum(derivative_metrics.characters),
            source_text_characters_by_page=source_metrics.characters,
            derivative_text_characters_by_page=derivative_metrics.characters,
            low_text_pages_before=quality.low_text_pages_before,
            low_text_pages_after=quality.low_text_pages_after,
            image_heavy_pages=evaluation.image_heavy_pages,
            skipped_pages=(
                [
                    index
                    for index, count in enumerate(source_metrics.characters, start=1)
                    if count > 0
                ]
                if configuration.skip_text
                else []
            ),
            rotated_pages=[],
            deskew_enabled=configuration.deskew,
            clean_enabled=configuration.clean,
            force_ocr_enabled=configuration.force_ocr,
            warnings=warnings,
            errors=[],
            return_code=completed.returncode,
            quality_decision=outcome,
            suitability_status=suitability,
            quality_metrics=quality,
            output_paths=[
                str(final / "document-ocr.pdf"),
                str(final / "derivative.json"),
                str(final / "ocr-report.json"),
                str(final / "logs" / "ocrmypdf.log"),
            ],
        )
        (temporary / "derivative.json").write_text(
            derivative.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        (temporary / "ocr-report.json").write_text(
            report.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        _validate_temporary(temporary, derivative, report, source)
        if sha256_file(source) != source_digest:
            raise OCRExecutionError(
                "Original source changed during OCR; derivative was not finalized."
            )
        _finalize(temporary, final, backup)
        return OCRDerivativeResult(derivative=derivative, report=report, directory=final)
    except Exception:
        _restore_or_cleanup(temporary, final, backup)
        raise


def _ocrmypdf_command(source: Path, output_pdf: Path, configuration: OCRConfiguration) -> list[str]:
    command = [
        "ocrmypdf",
        "--language",
        "+".join(configuration.language_codes),
        "--output-type",
        configuration.output_type,
        "--optimize",
        str(configuration.optimization_level),
        "--jobs",
        str(configuration.jobs),
        "--tesseract-timeout",
        str(configuration.timeout_seconds),
    ]
    if configuration.skip_text:
        command.append("--skip-text")
    if configuration.force_ocr:
        command.append("--force-ocr")
    if configuration.deskew:
        command.append("--deskew")
    if configuration.rotate_pages:
        command.append("--rotate-pages")
    if configuration.clean:
        command.append("--clean")
    command.extend([str(source), str(output_pdf)])
    return command


def _pdf_metrics(path: Path) -> PDFMetrics:
    with fitz.open(path) as pdf:
        if pdf.needs_pass:
            raise OCRExecutionError("Derivative PDF is unexpectedly encrypted.")
        characters = [len(page.get_text("text")) for page in pdf]
        images = [len(page.get_images(full=True)) for page in pdf]
        return PDFMetrics(page_count=pdf.page_count, characters=characters, images=images)


def _quality_metrics(
    source: PDFMetrics, derivative: PDFMetrics, image_heavy_pages: list[int]
) -> tuple[OCRQualityMetrics, list[str]]:
    source_chars = source.characters
    derivative_chars = derivative.characters
    before = [
        number
        for number in image_heavy_pages
        if number <= len(source_chars) and source_chars[number - 1] < LOW_TEXT_CHARACTERS
    ]
    after = [
        number
        for number in image_heavy_pages
        if number <= len(derivative_chars) and derivative_chars[number - 1] < LOW_TEXT_CHARACTERS
    ]
    source_total = sum(source_chars)
    derivative_total = sum(derivative_chars)
    percentage = ((derivative_total - source_total) / source_total) * 100 if source_total else None
    equal = source.page_count == derivative.page_count
    warnings: list[str] = []
    if after:
        warnings.append(f"Low-text pages remain after OCR: {', '.join(map(str, after))}.")
    return (
        OCRQualityMetrics(
            source_text_character_count=source_total,
            derivative_text_character_count=derivative_total,
            source_text_characters_by_page=source_chars,
            derivative_text_characters_by_page=derivative_chars,
            low_text_pages_before=before,
            low_text_pages_after=after,
            image_heavy_pages=image_heavy_pages,
            percentage_improvement=percentage,
            page_count_equal=equal,
            derivative_pdf_valid=True,
            physical_page_mapping_preserved=equal,
        ),
        warnings,
    )


def _quality_outcome(metrics: OCRQualityMetrics) -> OCRQualityOutcome:
    if not metrics.derivative_pdf_valid or not metrics.page_count_equal:
        return OCRQualityOutcome.INVALID
    if (
        metrics.derivative_text_character_count
        < metrics.source_text_character_count * metrics.meaningful_text_retention_ratio
    ):
        return OCRQualityOutcome.DEGRADED
    gain = metrics.derivative_text_character_count - metrics.source_text_character_count
    material = gain >= metrics.material_improvement_minimum_characters or (
        metrics.percentage_improvement is not None
        and metrics.percentage_improvement >= metrics.material_improvement_minimum_percent
    )
    if not material:
        return OCRQualityOutcome.NO_MATERIAL_IMPROVEMENT
    return (
        OCRQualityOutcome.ACCEPTED_WITH_WARNINGS
        if metrics.low_text_pages_after
        else OCRQualityOutcome.ACCEPTED
    )


def _canonical_block_count(source_sha256: str) -> int | None:
    path = Path("data/processed") / source_sha256 / "document.json"
    if not path.is_file():
        return None
    try:
        document = validate_document_file(path)
    except (OSError, ValueError):
        return None
    return sum(len(page.blocks) for page in document.pages)


def _validate_temporary(
    directory: Path,
    derivative: DocumentDerivative,
    report: OCRProcessingReport,
    source: Path,
) -> None:
    DocumentDerivative.model_validate_json(
        (directory / "derivative.json").read_text(encoding="utf-8")
    )
    OCRProcessingReport.model_validate_json(
        (directory / "ocr-report.json").read_text(encoding="utf-8")
    )
    if sha256_file(directory / "document-ocr.pdf") != derivative.derivative_sha256:
        raise OCRExecutionError("Persisted derivative hash validation failed.")
    if sha256_file(source) != derivative.source_sha256:
        raise OCRExecutionError("Original source hash validation failed.")
    if report.source_page_count != report.derivative_page_count:
        raise OCRExecutionError("OCR derivative changed physical page count.")


def _ensure_output_safe(output_root: Path, source_root: Path) -> None:
    output = output_root.resolve()
    source = source_root.resolve()
    if output == source or output.is_relative_to(source):
        raise ValueError("OCR derivatives must never be written inside pdfsrc.")


def _finalize(temporary: Path, final: Path, backup: Path) -> None:
    if final.exists():
        final.rename(backup)
    temporary.rename(final)
    if backup.exists():
        shutil.rmtree(backup)


def _restore_or_cleanup(temporary: Path, final: Path, backup: Path) -> None:
    if temporary.exists():
        shutil.rmtree(temporary)
    if backup.exists() and not final.exists():
        backup.rename(final)
