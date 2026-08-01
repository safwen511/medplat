"""Canonical parsing of accepted OCR derivatives with original-source identity."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from ingestion.config import DoclingSettings
from ingestion.normalization.models import SCHEMA_VERSION, TechnicalSuitability
from ingestion.ocr.models import OCRQualityOutcome
from ingestion.ocr.validation import validate_derivative_file
from ingestion.output import write_json_atomic
from ingestion.pipeline import ParseResult, parse_document


def processing_variant_id(derivative_id: str) -> str:
    stable = f"ocr-processing-v1\n{SCHEMA_VERSION}\n{derivative_id}"
    return sha256(stable.encode("utf-8")).hexdigest()


def parse_ocr_derivative(
    metadata_path: Path,
    *,
    source_root: Path = Path("pdfsrc"),
    output_root: Path = Path("data/processed"),
    docling_settings: DoclingSettings | None = None,
    force: bool = False,
) -> ParseResult:
    derivative, ocr_report = validate_derivative_file(metadata_path, source_root=source_root)
    accepted = {OCRQualityOutcome.ACCEPTED, OCRQualityOutcome.ACCEPTED_WITH_WARNINGS}
    if derivative.validation_status not in accepted:
        raise ValueError(
            f"Rejected OCR derivative cannot be parsed downstream: "
            f"{derivative.validation_status.value}."
        )
    source = source_root / derivative.source_relative_path
    derivative_pdf = metadata_path.parent / "document-ocr.pdf"
    variant_id = processing_variant_id(derivative.derivative_id)
    suitability = (
        TechnicalSuitability.READY_FOR_CHUNKING
        if derivative.validation_status is OCRQualityOutcome.ACCEPTED
        else TechnicalSuitability.READY_WITH_WARNINGS
    )
    provenance: dict[str, object] = {
        "processing_variant_id": variant_id,
        "derivative_provenance": {
            "derivative_id": derivative.derivative_id,
            "derivative_sha256": derivative.derivative_sha256,
            "derivation_type": derivative.derivation_type,
            "ocr_languages": derivative.language_codes,
            "ocr_tool": derivative.tool_name,
            "ocr_tool_version": derivative.tool_version,
            "derivative_relative_path": derivative.derivative_relative_path,
            "quality_outcome": derivative.validation_status.value,
            "physical_page_mapping": "identity_1_based",
            "original_source_sha256": derivative.source_sha256,
            "original_source_relative_path": derivative.source_relative_path,
        },
    }
    result = parse_document(
        derivative_pdf,
        source_root=source_root,
        output_root=output_root,
        force=force,
        docling_settings=docling_settings,
        source_identity_path=source,
        source_sha256_override=derivative.source_sha256,
        source_relative_path_override=derivative.source_relative_path,
        additional_metadata=provenance,
        output_relative_path=Path(derivative.source_sha256) / "variants" / variant_id,
        technical_suitability_override=suitability,
    )
    blocks_after = sum(len(page.blocks) for page in result.document.pages)
    ocr_report.quality_metrics.canonical_blocks_after = blocks_after
    report_path = metadata_path.parent / "ocr-report.json"
    write_json_atomic(report_path, ocr_report.model_dump(mode="json"))
    return result
