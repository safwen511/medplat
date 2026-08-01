"""Deterministic discovery, inspection reuse, selection, and batch planning."""

from __future__ import annotations

import fnmatch
import json
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

from pydantic import ValidationError

from ingestion.batch.models import (
    BATCH_SCHEMA_VERSION,
    BatchConfiguration,
    BatchPlan,
    ExistingOutputState,
    OCRRoute,
    ParserRoute,
    PlannedDocument,
    SelectionMode,
)
from ingestion.batch.router import ocr_route, parser_route
from ingestion.batch.validation import inspect_existing_outputs
from ingestion.hashing import sha256_file
from ingestion.models import DocumentClassification, DocumentInspection, LibraryReport
from ingestion.scanner import discover_documents, inspect_path


def build_batch_plan(configuration: BatchConfiguration) -> BatchPlan:
    """Inspect safely and produce a deterministic plan without parsing documents."""
    root = configuration.input_root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Document library does not exist: {root}")
    _validate_output_roots(configuration, root)
    manifest, manifest_warning = _load_manifest(configuration.manifest_path, root)
    manifest_by_path = {item.relative_path: item for item in manifest.documents} if manifest else {}

    inspections: list[DocumentInspection] = []
    warnings = [manifest_warning] if manifest_warning else []
    for path in discover_documents(root):
        relative = path.relative_to(root).as_posix()
        if not _included(path, relative, configuration):
            continue
        cached = manifest_by_path.get(relative)
        if cached is not None and _manifest_entry_current(cached, path):
            inspection = cached
        else:
            if cached is not None:
                warnings.append(f"Stale manifest entry re-inspected: {relative}")
            inspection = inspect_path(path, root)
        if inspection.sha256 is None or inspection.file_size is None:
            warnings.append(f"Inspection lacks stable file identity and was excluded: {relative}")
            continue
        inspections.append(inspection)

    ordered = sorted(inspections, key=_order_key)
    selected = _select(ordered, configuration.selection, configuration.limit)
    documents: list[PlannedDocument] = []
    for sequence, inspection in enumerate(selected, start=1):
        route = parser_route(inspection)
        ocr = ocr_route(inspection, configuration)
        state = inspect_existing_outputs(
            output_root=configuration.output_root,
            source_sha256=inspection.sha256 or "",
            source_relative_path=inspection.relative_path,
            source_root=root,
        )
        actions, skip_reason = _planned_actions(route, ocr, state, configuration)
        documents.append(
            PlannedDocument(
                sequence_number=sequence,
                source_relative_path=inspection.relative_path,
                extension=inspection.extension,
                mime_type=inspection.mime_type,
                file_size=inspection.file_size or 0,
                sha256=inspection.sha256 or "",
                inspection_classification=inspection.classification.value,
                parser_route=route,
                ocr_route=ocr,
                current_output_state=state,
                planned_actions=actions,
                skip_reason=skip_reason,
                retry_eligible=route is not ParserRoute.UNSUPPORTED,
            )
        )
    batch_id = _batch_id(configuration, documents)
    return BatchPlan(
        batch_id=batch_id,
        input_root=str(root),
        output_root=str(configuration.output_root.resolve()),
        derived_output_root=str(configuration.derived_output_root.resolve()),
        manifest_path=str(configuration.manifest_path) if configuration.manifest_path else None,
        configuration=configuration,
        deterministic_document_order=[item.source_relative_path for item in documents],
        selected_document_count=len(documents),
        skipped_document_count=sum(item.skip_reason is not None for item in documents),
        documents=documents,
        warnings=list(dict.fromkeys(warnings)),
    )


def _load_manifest(path: Path | None, root: Path) -> tuple[LibraryReport | None, str | None]:
    if path is None:
        return None, None
    if not path.is_file():
        return None, f"Manifest not found; using live inspection: {path}"
    try:
        report = LibraryReport.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as exc:
        return None, f"Manifest invalid; using live inspection: {exc}"
    if Path(report.input_root).resolve() != root:
        return None, "Manifest source root does not match --input; using live inspection."
    return report, None


def _manifest_entry_current(entry: DocumentInspection, path: Path) -> bool:
    return (
        entry.file_size == path.stat().st_size
        and entry.sha256 is not None
        and sha256_file(path) == entry.sha256
    )


def _included(path: Path, relative: str, configuration: BatchConfiguration) -> bool:
    extension = path.suffix.lower()
    if configuration.include_extensions and extension not in configuration.include_extensions:
        return False
    if any(fnmatch.fnmatch(relative, pattern) for pattern in configuration.exclude_patterns):
        return False
    maximum = configuration.maximum_source_file_size
    return maximum is None or path.stat().st_size <= maximum


def _order_key(inspection: DocumentInspection) -> tuple[str, int, str]:
    priority = {".pdf": 0, ".pptx": 1, ".docx": 2}.get(inspection.extension, 9)
    return (inspection.relative_path.casefold(), priority, inspection.sha256 or "")


def _select(
    ordered: list[DocumentInspection], mode: SelectionMode, limit: int | None
) -> list[DocumentInspection]:
    maximum = len(ordered) if limit is None else limit
    if mode is SelectionMode.ORDERED:
        return ordered[:maximum]
    predicates: tuple[Callable[[DocumentInspection], bool], ...] = (
        lambda item: (
            item.extension == ".pdf" and item.classification is DocumentClassification.NATIVE_TEXT
        ),
        lambda item: (
            item.extension == ".pdf" and item.classification is DocumentClassification.MIXED
        ),
        lambda item: item.extension == ".pptx",
        lambda item: item.extension == ".docx",
        lambda item: (
            item.extension == ".pdf"
            and item.classification is DocumentClassification.LIKELY_SCANNED
        ),
        lambda item: parser_route(item) is ParserRoute.UNSUPPORTED,
    )
    selected: list[DocumentInspection] = []
    selected_paths: set[str] = set()
    for predicate in predicates:
        match = next((item for item in ordered if predicate(item)), None)
        if match is not None and match.relative_path not in selected_paths:
            selected.append(match)
            selected_paths.add(match.relative_path)
        if len(selected) == maximum:
            return selected
    for item in ordered:
        if item.relative_path not in selected_paths:
            selected.append(item)
            selected_paths.add(item.relative_path)
        if len(selected) == maximum:
            break
    return selected


def _planned_actions(
    route: ParserRoute,
    ocr: OCRRoute,
    state: ExistingOutputState,
    configuration: BatchConfiguration,
) -> tuple[list[str], str | None]:
    if route is ParserRoute.UNSUPPORTED:
        return ["report_unsupported"], "unsupported_for_parsing"
    if state.complete and configuration.resume and not configuration.force_rebuild:
        return ["validate_existing_outputs", "skip_already_complete"], "already_complete"
    actions = ["validate_source_hash"]
    if state.canonical_path is None or configuration.force_rebuild:
        actions.extend(["parse", "validate_canonical"])
    else:
        actions.append("reuse_valid_canonical")
    if route is ParserRoute.PDF and ocr is not OCRRoute.NONE:
        actions.append("evaluate_technical_suitability")
        if ocr is OCRRoute.DISABLED:
            actions.append("record_requires_ocr_if_needed")
        else:
            actions.extend(["safe_ocr_if_required", "validate_derivative"])
            if ocr is OCRRoute.SAFE_THEN_FORCE_ALLOWED:
                actions.append("force_ocr_if_safe_ocr_rejected")
    actions.extend(
        ["build_or_reuse_chunks", "validate_chunks", "build_or_reuse_dataset", "validate_dataset"]
    )
    return actions, None


def _batch_id(configuration: BatchConfiguration, documents: list[PlannedDocument]) -> str:
    manifest_identity = None
    if configuration.manifest_path and configuration.manifest_path.is_file():
        manifest_identity = sha256_file(configuration.manifest_path)
    payload = {
        "schema_version": BATCH_SCHEMA_VERSION,
        "input_root": str(configuration.input_root.resolve()),
        "output_root": str(configuration.output_root.resolve()),
        "derived_output_root": str(configuration.derived_output_root.resolve()),
        "selected_paths": [item.source_relative_path for item in documents],
        "source_hashes": [item.sha256 for item in documents],
        "ocr_enabled": configuration.ocr_enabled,
        "ocr_languages": configuration.ocr_languages,
        "allow_force_ocr": configuration.allow_force_ocr,
        "force_rebuild": configuration.force_rebuild,
        "selection": configuration.selection.value,
        "manifest_identity": manifest_identity,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def _validate_output_roots(configuration: BatchConfiguration, source_root: Path) -> None:
    for label, path in (
        ("output", configuration.output_root),
        ("derived output", configuration.derived_output_root),
        ("reports", configuration.reports_root),
    ):
        resolved = path.resolve()
        if resolved == source_root or resolved.is_relative_to(source_root):
            raise ValueError(f"Batch {label} must not be inside the source library.")
