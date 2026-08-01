"""Validation of finalized OCR derivatives and provenance."""

from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore[import-untyped]

from ingestion.hashing import sha256_file
from ingestion.ocr.models import DocumentDerivative, OCRProcessingReport


def validate_derivative_file(
    metadata_path: Path, *, source_root: Path = Path("pdfsrc")
) -> tuple[DocumentDerivative, OCRProcessingReport]:
    derivative = DocumentDerivative.model_validate_json(metadata_path.read_text(encoding="utf-8"))
    directory = metadata_path.parent
    pdf_path = directory / "document-ocr.pdf"
    report_path = directory / "ocr-report.json"
    if not pdf_path.is_file() or not report_path.is_file():
        raise ValueError("Derivative output is incomplete.")
    report = OCRProcessingReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    source = source_root / derivative.source_relative_path
    if not source.is_file() or sha256_file(source) != derivative.source_sha256:
        raise ValueError("Original source hash or path no longer matches derivative provenance.")
    if sha256_file(pdf_path) != derivative.derivative_sha256:
        raise ValueError("OCR derivative SHA-256 does not match derivative metadata.")
    with fitz.open(source) as source_pdf, fitz.open(pdf_path) as derived_pdf:
        if derived_pdf.needs_pass:
            raise ValueError("OCR derivative is encrypted.")
        if (
            source_pdf.page_count != derived_pdf.page_count
            or derived_pdf.page_count != derivative.page_count
        ):
            raise ValueError("OCR derivative physical page count does not match the original.")
    if report.derivative_id != derivative.derivative_id:
        raise ValueError("OCR report belongs to another derivative.")
    return derivative, report
