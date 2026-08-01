"""Metadata-only fallback for formats not parsed in this milestone."""

from pathlib import Path

from ingestion.models import (
    DocumentClassification,
    DocumentInspection,
    FileMetadata,
    ParsingEligibility,
)
from ingestion.parsers.base import DocumentParser


class UnsupportedParser(DocumentParser):
    """Record a document without opening or interpreting its contents."""

    @property
    def extensions(self) -> frozenset[str]:
        return frozenset()

    def inspect(self, path: Path, metadata: FileMetadata) -> DocumentInspection:
        del path
        return DocumentInspection(
            **metadata.model_dump(),
            readable=True,
            encrypted=None,
            classification=DocumentClassification.UNSUPPORTED_FOR_NOW,
            parsing_eligibility=(
                ParsingEligibility.SUPPORTED
                if metadata.extension in {".pptx", ".docx"}
                else ParsingEligibility.UNSUPPORTED_FOR_PARSING
            ),
            ocr_recommended=None,
        )
