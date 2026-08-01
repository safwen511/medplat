"""Recursive, failure-isolated document discovery and inspection."""

from __future__ import annotations

import logging
import mimetypes
from collections.abc import Iterable
from pathlib import Path

from ingestion.hashing import sha256_file
from ingestion.models import (
    DocumentClassification,
    DocumentInspection,
    ErrorInformation,
    FileMetadata,
    LibraryReport,
)
from ingestion.parsers import ParserRegistry, PdfParser, UnsupportedParser

LOGGER = logging.getLogger(__name__)

DOCUMENT_TYPES = {
    ".pdf": "PDF",
    ".docx": "Microsoft Word",
    ".doc": "Microsoft Word",
    ".pptx": "Microsoft PowerPoint",
    ".ppt": "Microsoft PowerPoint",
    ".xlsx": "Microsoft Excel",
    ".xls": "Microsoft Excel",
    ".odt": "OpenDocument Text",
    ".odp": "OpenDocument Presentation",
    ".epub": "EPUB",
    ".md": "Markdown",
    ".html": "HTML",
    ".htm": "HTML",
    ".txt": "Plain Text",
    ".rtf": "Rich Text",
    ".png": "PNG image",
    ".jpg": "JPEG image",
    ".jpeg": "JPEG image",
    ".tif": "TIFF image",
    ".tiff": "TIFF image",
    ".bmp": "BMP image",
    ".webp": "WEBP image",
}


def default_registry() -> ParserRegistry:
    """Build the milestone parser registry."""
    registry = ParserRegistry(fallback=UnsupportedParser())
    registry.register(PdfParser())
    return registry


def discover_documents(root: Path) -> list[Path]:
    """Discover regular files recursively in deterministic relative-path order."""
    if not root.is_dir():
        raise NotADirectoryError(f"Document library does not exist or is not a directory: {root}")
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and not path.is_symlink()),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _metadata(path: Path, root: Path) -> FileMetadata:
    extension = path.suffix.lower()
    mime_type, _ = mimetypes.guess_type(path.name)
    return FileMetadata(
        relative_path=path.relative_to(root).as_posix(),
        filename=path.name,
        extension=extension,
        detected_type=DOCUMENT_TYPES.get(extension, "Unknown"),
        mime_type=mime_type,
        file_size=path.stat().st_size,
        sha256=sha256_file(path),
    )


def _failed_metadata(path: Path, root: Path, exc: Exception) -> DocumentInspection:
    extension = path.suffix.lower()
    mime_type, _ = mimetypes.guess_type(path.name)
    return DocumentInspection(
        relative_path=path.relative_to(root).as_posix(),
        filename=path.name,
        extension=extension,
        detected_type=DOCUMENT_TYPES.get(extension, "Unknown"),
        mime_type=mime_type,
        readable=False,
        classification=DocumentClassification.UNREADABLE,
        error=ErrorInformation(error_type=type(exc).__name__, message=str(exc)),
    )


def inspect_path(
    path: Path, root: Path, registry: ParserRegistry | None = None
) -> DocumentInspection:
    """Inspect one path while converting every file-specific failure into data."""
    parser_registry = registry or default_registry()
    try:
        metadata = _metadata(path, root)
        return parser_registry.parser_for(metadata.extension).inspect(path, metadata)
    except Exception as exc:
        LOGGER.error("Document inspection failed: %s", path, exc_info=True)
        return _failed_metadata(path, root, exc)


def inspect_library(
    root: Path, limit: int | None = None, registry: ParserRegistry | None = None
) -> LibraryReport:
    """Inspect a recursive library, optionally stopping after *limit* files."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")
    paths = discover_documents(root)
    selected: Iterable[Path] = paths if limit is None else paths[:limit]
    parser_registry = registry or default_registry()
    documents = [inspect_path(path, root, parser_registry) for path in selected]
    return LibraryReport(
        input_root=str(root),
        discovered_count=len(paths),
        inspected_count=len(documents),
        documents=documents,
    )
