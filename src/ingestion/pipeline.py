"""Structured parsing orchestration and representative batch selection."""

from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ingestion.config import DoclingSettings
from ingestion.hashing import sha256_file
from ingestion.models import DocumentClassification
from ingestion.normalization.models import (
    BatchDocumentResult,
    BatchProcessingReport,
    DocumentType,
    NormalizedDocument,
    ProcessingReport,
    ProcessingStatus,
    TechnicalSuitability,
)
from ingestion.normalization.normalizer import normalize_docling_document
from ingestion.output import (
    ensure_output_outside_source,
    write_json_atomic,
    write_normalized_output,
)
from ingestion.parsers import (
    DoclingStructuredParser,
    StructuredParserRegistry,
    UnsupportedStructuredParser,
)
from ingestion.scanner import discover_documents, inspect_path

SUPPORTED_PARSE_EXTENSIONS = frozenset({".pdf", ".pptx", ".docx"})


@dataclass(frozen=True)
class ParseResult:
    document: NormalizedDocument
    report: ProcessingReport
    output_directory: Path


def default_structured_registry(
    settings: DoclingSettings | None = None,
) -> StructuredParserRegistry:
    registry = StructuredParserRegistry(fallback=UnsupportedStructuredParser())
    registry.register(DoclingStructuredParser(settings=settings))
    return registry


def document_type_for(extension: str) -> DocumentType:
    try:
        return {
            ".pdf": DocumentType.PDF,
            ".pptx": DocumentType.POWERPOINT,
            ".docx": DocumentType.WORD,
        }[extension.lower()]
    except KeyError as exc:
        message = f"Unsupported structured document format: {extension or '(none)'}"
        raise ValueError(message) from exc


def relative_source_path(path: Path, source_root: Path) -> str:
    """Preserve a source-root-relative POSIX path without inventing hierarchy."""
    try:
        return path.resolve().relative_to(source_root.resolve()).as_posix()
    except ValueError:
        return path.name


def parse_document(
    path: Path,
    *,
    source_root: Path,
    output_root: Path,
    extract_assets: bool = False,
    render_previews: bool = False,
    force: bool = False,
    registry: StructuredParserRegistry | None = None,
    docling_settings: DoclingSettings | None = None,
    source_identity_path: Path | None = None,
    source_sha256_override: str | None = None,
    source_relative_path_override: str | None = None,
    additional_metadata: dict[str, object] | None = None,
    output_relative_path: Path | None = None,
    technical_suitability_override: TechnicalSuitability | None = None,
) -> ParseResult:
    """Parse, normalize, validate, and atomically persist exactly one source."""
    if not path.is_file():
        raise FileNotFoundError(f"Source document does not exist: {path}")
    document_type = document_type_for(path.suffix)
    identity_path = source_identity_path or path
    digest = source_sha256_override or sha256_file(path)
    started = datetime.now(timezone.utc)
    parser = (registry or default_structured_registry(docling_settings)).parser_for(path.suffix)
    parsed = parser.parse(path)
    mime_type, _ = mimetypes.guess_type(path.name)
    normalized = normalize_docling_document(
        parsed.document,
        source_path=path,
        source_relative_path=(
            source_relative_path_override or relative_source_path(identity_path, source_root)
        ),
        sha256=digest,
        mime_type=mime_type,
        document_type=document_type,
        parser_name=parsed.parser_name,
        parser_version=parsed.parser_version,
        initial_warnings=parsed.warnings,
        source_filename=identity_path.name,
        additional_metadata=additional_metadata,
    )
    status = (
        ProcessingStatus.PARTIAL_SUCCESS
        if normalized.processing.warnings
        else ProcessingStatus.SUCCESS
    )
    quality = normalized.metadata.setdefault("extraction_quality", {})
    suitability_value = quality.get("technical_suitability")
    suitability = technical_suitability_override or (
        TechnicalSuitability(suitability_value) if isinstance(suitability_value, str) else None
    )
    if (
        status is ProcessingStatus.PARTIAL_SUCCESS
        and suitability is TechnicalSuitability.READY_FOR_CHUNKING
    ):
        suitability = TechnicalSuitability.READY_WITH_WARNINGS
    if technical_suitability_override is not None:
        assert suitability is not None
        quality["technical_suitability"] = suitability.value
    report = ProcessingReport(
        parser_name=parsed.parser_name,
        parser_version=parsed.parser_version,
        start_time=started,
        completion_time=datetime.now(timezone.utc),
        status=status,
        warnings=normalized.processing.warnings,
        unsupported_features=[
            "OCR is disabled.",
            "Speaker notes are included only when Docling exposes them reliably.",
        ],
        model_provenance=parsed.provenance or {},
        technical_suitability=suitability,
    )
    final_directory = write_normalized_output(
        normalized,
        report,
        source_path=path,
        source_root=source_root,
        output_root=output_root,
        extract_assets=extract_assets,
        render_previews=render_previews,
        force=force,
        output_relative_path=output_relative_path,
    )
    return ParseResult(normalized, report, final_directory)


def _reported_classifications(input_root: Path) -> dict[str, str]:
    report_path = Path("data/reports/library-manifest.json")
    if input_root.resolve() != Path("pdfsrc").resolve() or not report_path.is_file():
        return {}
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        return {
            str(item["relative_path"]): str(item["classification"])
            for item in payload.get("documents", [])
        }
    except (OSError, TypeError, ValueError, KeyError):
        return {}


def select_representative_documents(input_root: Path, limit: int) -> list[Path]:
    """Choose native PDF, image-heavy PDF, and Office sources when available."""
    supported = [
        path
        for path in discover_documents(input_root)
        if path.suffix.lower() in SUPPORTED_PARSE_EXTENSIONS
    ]
    classifications = _reported_classifications(input_root)
    if not classifications:
        pdf_candidates = sorted(
            (path for path in supported if path.suffix.lower() == ".pdf"),
            key=lambda path: (path.stat().st_size, path.relative_to(input_root).as_posix()),
        )[:12]
        classifications = {
            result.relative_path: result.classification.value
            for result in (inspect_path(path, input_root) for path in pdf_candidates)
        }

    selected: list[Path] = []

    def add_first(candidates: list[Path]) -> None:
        if len(selected) >= limit:
            return
        for candidate in candidates:
            if candidate not in selected:
                selected.append(candidate)
                return

    pdfs = [path for path in supported if path.suffix.lower() == ".pdf"]
    add_first(
        sorted(
            (
                path
                for path in pdfs
                if classifications.get(path.relative_to(input_root).as_posix())
                == DocumentClassification.NATIVE_TEXT.value
            ),
            key=lambda path: path.stat().st_size,
        )
    )
    add_first(
        sorted(
            (
                path
                for path in pdfs
                if classifications.get(path.relative_to(input_root).as_posix())
                in {
                    DocumentClassification.MIXED.value,
                    DocumentClassification.LIKELY_SCANNED.value,
                }
            ),
            key=lambda path: path.stat().st_size,
        )
    )
    add_first(
        sorted(
            (path for path in supported if path.suffix.lower() in {".pptx", ".docx"}),
            key=lambda path: (path.stat().st_size, path.relative_to(input_root).as_posix()),
        )
    )
    for path in sorted(supported, key=lambda item: (item.stat().st_size, str(item))):
        add_first([path])
    return selected[:limit]


def parse_sample(
    *,
    input_root: Path,
    output_root: Path,
    limit: int,
    force: bool = False,
    registry: StructuredParserRegistry | None = None,
    selected_paths: list[Path] | None = None,
) -> BatchProcessingReport:
    """Parse a bounded representative batch while isolating document failures."""
    ensure_output_outside_source(output_root, input_root)
    started = datetime.now(timezone.utc)
    selected = selected_paths or select_representative_documents(input_root, limit)
    results: list[BatchDocumentResult] = []
    parser_registry = registry or default_structured_registry()
    for path in selected:
        relative = path.relative_to(input_root).as_posix()
        try:
            result = parse_document(
                path,
                source_root=input_root,
                output_root=output_root,
                force=force,
                registry=parser_registry,
            )
            results.append(
                BatchDocumentResult(
                    source_relative_path=relative,
                    status=result.report.status,
                    document_id=result.document.document_id,
                    output_directory=str(result.output_directory),
                )
            )
        except Exception as exc:
            results.append(
                BatchDocumentResult(
                    source_relative_path=relative,
                    status=ProcessingStatus.FAILED,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    report = BatchProcessingReport(
        input_root=str(input_root),
        start_time=started,
        completion_time=datetime.now(timezone.utc),
        selected_relative_paths=[path.relative_to(input_root).as_posix() for path in selected],
        results=results,
    )
    write_json_atomic(output_root / "batch-processing-report.json", report.model_dump(mode="json"))
    return report
