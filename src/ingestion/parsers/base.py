"""Common parser contract and extension-based plugin registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ingestion.models import DocumentInspection, FileMetadata


class DocumentParser(ABC):
    """Interface implemented by every current and future parser plugin."""

    @property
    @abstractmethod
    def extensions(self) -> frozenset[str]:
        """Return lower-case extensions, including their leading dots."""

    @abstractmethod
    def inspect(self, path: Path, metadata: FileMetadata) -> DocumentInspection:
        """Inspect one path and return the normalized result."""


@dataclass(frozen=True)
class ParsedSource:
    """Internal bridge from a source parser to the canonical normalizer."""

    document: Any
    parser_name: str
    parser_version: str | None
    warnings: tuple[str, ...] = ()
    provenance: dict[str, Any] | None = None


class StructuredDocumentParser(ABC):
    """Shared structured-parser plugin interface."""

    @property
    @abstractmethod
    def extensions(self) -> frozenset[str]:
        """Return lower-case supported extensions."""

    @abstractmethod
    def parse(self, path: Path) -> ParsedSource:
        """Parse one supported source into an internal structured tree."""


class ParserRegistry:
    """Select parser plugins without coupling the scanner to file formats."""

    def __init__(self, fallback: DocumentParser) -> None:
        self._fallback = fallback
        self._parsers: dict[str, DocumentParser] = {}

    def register(self, parser: DocumentParser) -> None:
        """Register one parser for each extension it declares."""
        for extension in parser.extensions:
            normalized = extension.lower()
            if normalized in self._parsers:
                raise ValueError(f"A parser is already registered for {normalized}")
            self._parsers[normalized] = parser

    def parser_for(self, extension: str) -> DocumentParser:
        """Return a matching plugin or the non-parsing fallback."""
        return self._parsers.get(extension.lower(), self._fallback)


class StructuredParserRegistry:
    """Registry for structured parsing plugins."""

    def __init__(self, fallback: StructuredDocumentParser) -> None:
        self._fallback = fallback
        self._parsers: dict[str, StructuredDocumentParser] = {}

    def register(self, parser: StructuredDocumentParser) -> None:
        for extension in parser.extensions:
            normalized = extension.lower()
            if normalized in self._parsers:
                raise ValueError(f"A structured parser is already registered for {normalized}")
            self._parsers[normalized] = parser

    def parser_for(self, extension: str) -> StructuredDocumentParser:
        return self._parsers.get(extension.lower(), self._fallback)
