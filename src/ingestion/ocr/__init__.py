"""Explicit local OCR derivative services."""

from ingestion.ocr.models import (
    DERIVATIVE_SCHEMA_VERSION,
    DocumentDerivative,
    OCRConfiguration,
    OCREligibility,
    OCRQualityOutcome,
    OCRSuitability,
)

__all__ = [
    "DERIVATIVE_SCHEMA_VERSION",
    "DocumentDerivative",
    "OCRConfiguration",
    "OCREligibility",
    "OCRQualityOutcome",
    "OCRSuitability",
]
