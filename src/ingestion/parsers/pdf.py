"""PDF inspection implemented with PyMuPDF."""

from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore[import-untyped]

from ingestion.models import (
    DocumentClassification,
    DocumentInspection,
    ErrorInformation,
    FileMetadata,
    ParsingEligibility,
)
from ingestion.parsers.base import DocumentParser


class PdfParser(DocumentParser):
    """Extract inspection-level PDF characteristics without altering the file."""

    @property
    def extensions(self) -> frozenset[str]:
        return frozenset({".pdf"})

    def inspect(self, path: Path, metadata: FileMetadata) -> DocumentInspection:
        try:
            with fitz.open(path) as document:
                page_count = document.page_count
                encrypted = bool(document.needs_pass)
                if encrypted:
                    return DocumentInspection(
                        **metadata.model_dump(),
                        readable=True,
                        encrypted=True,
                        page_count=page_count,
                        image_count=None,
                        extractable_character_count=None,
                        average_characters_per_page_or_slide=None,
                        classification=DocumentClassification.ENCRYPTED,
                        parsing_eligibility=ParsingEligibility.SUPPORTED,
                        ocr_recommended=None,
                    )

                character_count = 0
                image_count = 0
                for page in document:
                    character_count += len(page.get_text("text"))
                    image_count += len(page.get_images(full=True))

                average = character_count / page_count if page_count else 0.0
                if character_count == 0:
                    classification = DocumentClassification.LIKELY_SCANNED
                elif image_count:
                    classification = DocumentClassification.MIXED
                else:
                    classification = DocumentClassification.NATIVE_TEXT

                return DocumentInspection(
                    **metadata.model_dump(),
                    readable=True,
                    encrypted=False,
                    page_count=page_count,
                    image_count=image_count,
                    extractable_character_count=character_count,
                    average_characters_per_page_or_slide=average,
                    classification=classification,
                    parsing_eligibility=ParsingEligibility.SUPPORTED,
                    ocr_recommended=classification is DocumentClassification.LIKELY_SCANNED,
                )
        except Exception as exc:  # PyMuPDF raises several format-specific exception types.
            return DocumentInspection(
                **metadata.model_dump(),
                readable=False,
                encrypted=None,
                classification=DocumentClassification.UNREADABLE,
                parsing_eligibility=ParsingEligibility.SUPPORTED,
                ocr_recommended=None,
                error=ErrorInformation(error_type=type(exc).__name__, message=str(exc)),
            )
