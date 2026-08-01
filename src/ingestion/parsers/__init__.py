"""Document parser plugins supplied by the first milestone."""

from ingestion.parsers.base import (
    DocumentParser,
    ParserRegistry,
    StructuredDocumentParser,
    StructuredParserRegistry,
)
from ingestion.parsers.docling_parser import (
    DoclingStructuredParser,
    UnsupportedFormatError,
    UnsupportedStructuredParser,
)
from ingestion.parsers.pdf import PdfParser
from ingestion.parsers.unsupported import UnsupportedParser

__all__ = [
    "DoclingStructuredParser",
    "DocumentParser",
    "ParserRegistry",
    "PdfParser",
    "StructuredDocumentParser",
    "StructuredParserRegistry",
    "UnsupportedFormatError",
    "UnsupportedParser",
    "UnsupportedStructuredParser",
]
