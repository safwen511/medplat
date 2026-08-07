"""Sequential orchestration for deterministic mirrored text-tree exports."""

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from ingestion.config import DoclingSettings
from ingestion.hashing import sha256_file
from ingestion.output import ensure_output_outside_source, write_json_atomic, write_text_atomic
from ingestion.text_tree.discovery import (
    DiscoveredSource,
    OutputPlan,
    SourceSnapshot,
    plan_output_paths,
    safe_output_path,
    snapshot_source_tree,
)
from ingestion.text_tree.extraction import (
    AcceptedDerivative,
    ExtractionResult,
    LocalTextExtractor,
    PDFTechnicalInspection,
    find_accepted_derivative,
    inspect_pdf_technically,
)
from ingestion.text_tree.models import (
    SUPPORTED_TEXT_EXPORT_EXTENSIONS,
    TEXT_EXPORT_SCHEMA_VERSION,
    ExportStatus,
    SourceChange,
    TextExportConfiguration,
    TextExportEntry,
    TextExportManifest,
    TextTreeRunReport,
)
from ingestion.text_tree.rendering import render_export
from ingestion.text_tree.validation import validate_text_export


@dataclass(frozen=True)
class TextTreeRunResult:
    """In-memory result returned for both dry runs and persisted runs."""

    manifest: TextExportManifest
    report: TextTreeRunReport
    collisions: dict[str, tuple[str, ...]]
    report_directory: Path | None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_hash(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return sha256(encoded).hexdigest()


def _run_id(
    configuration: TextExportConfiguration, snapshot: SourceSnapshot, outputs: OutputPlan
) -> str:
    payload = {
        "strategy": "medplat-text-tree-v1",
        "schema_version": TEXT_EXPORT_SCHEMA_VERSION,
        "input_root": str(configuration.input_root.resolve()),
        "output_root": str(configuration.output_root.resolve()),
        "extensions": configuration.extensions,
        "limit": configuration.limit,
        "files": [
            {
                "path": item.relative_path,
                "sha256": item.sha256,
                "size": item.size_bytes,
                "output": outputs.output_by_source.get(item.relative_path),
            }
            for item in snapshot.files
        ],
    }
    return _stable_hash(payload)[:24]


def _export_identity(source: DiscoveredSource, output_relative_path: str) -> str | None:
    if source.sha256 is None:
        return None
    return _stable_hash(
        {
            "strategy": "medplat-text-tree-export-v1",
            "schema_version": TEXT_EXPORT_SCHEMA_VERSION,
            "source_relative_path": source.relative_path,
            "source_sha256": source.sha256,
            "source_extension": source.extension,
            "output_relative_path": output_relative_path,
        }
    )


def _document_type(extension: str) -> str:
    return {
        ".pdf": "pdf",
        ".pptx": "powerpoint",
        ".docx": "word",
        ".txt": "text",
    }[extension]


def _validate_disjoint_roots(configuration: TextExportConfiguration) -> None:
    input_root = configuration.input_root.resolve()
    output_root = configuration.output_root.resolve()
    report_root = configuration.report_output_root.resolve()
    ensure_output_outside_source(output_root, input_root)
    ensure_output_outside_source(report_root, input_root)
    if input_root.is_relative_to(output_root) or input_root.is_relative_to(report_root):
        raise ValueError("Input, output, and report roots must be disjoint.")


def _load_previous_manifest(configuration: TextExportConfiguration) -> TextExportManifest | None:
    if not configuration.resume:
        return None
    path = configuration.output_root / "export-manifest.json"
    if not path.is_file():
        return None
    try:
        manifest = TextExportManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError):
        return None
    if (
        Path(manifest.input_root).resolve() != configuration.input_root.resolve()
        or Path(manifest.output_root).resolve() != configuration.output_root.resolve()
    ):
        return None
    return manifest


def _source_name_is_header_safe(source: DiscoveredSource) -> bool:
    return "\n" not in source.relative_path and "\r" not in source.relative_path


def _prior_entry_current(
    source: DiscoveredSource,
    output_relative_path: str,
    configuration: TextExportConfiguration,
    previous: TextExportEntry | None,
) -> tuple[bool, str | None]:
    if previous is None:
        return False, None
    if (
        previous.source_relative_path != source.relative_path
        or previous.source_sha256 != source.sha256
        or previous.output_relative_path != output_relative_path
        or previous.output_sha256 is None
        or previous.export_status
        not in {
            ExportStatus.EXPORTED,
            ExportStatus.EXPORTED_WITH_WARNINGS,
            ExportStatus.SKIPPED_CURRENT,
        }
    ):
        return False, "Existing manifest entry does not match the current source identity."
    output_path = safe_output_path(configuration.output_root, output_relative_path)
    if not output_path.is_file() or source.sha256 is None:
        return False, "Existing output is missing or its source hash is unavailable."
    try:
        validate_text_export(
            output_path,
            output_root=configuration.output_root,
            source_filename=source.path.name,
            source_relative_path=source.relative_path,
            source_extension=source.extension,
            source_sha256=source.sha256,
            document_type=_document_type(source.extension),
            page_or_slide_count=previous.page_or_slide_count,
            expected_output_sha256=previous.output_sha256,
        )
    except (OSError, ValueError) as exc:
        return False, f"Existing output failed resume validation: {type(exc).__name__}: {exc}"
    return True, None


def _base_entry(
    source: DiscoveredSource,
    outputs: OutputPlan,
    *,
    status: ExportStatus,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> TextExportEntry:
    output_relative_path = outputs.output_by_source.get(source.relative_path)
    return TextExportEntry(
        source_relative_path=source.relative_path,
        source_sha256=source.sha256,
        source_size_bytes=source.size_bytes,
        extension=source.extension,
        output_relative_path=output_relative_path,
        export_status=status,
        warnings=warnings or [],
        errors=errors or [],
        export_identity=(
            _export_identity(source, output_relative_path)
            if output_relative_path is not None
            else None
        ),
    )


def _updated_entry(entry: TextExportEntry, **changes: object) -> TextExportEntry:
    return TextExportEntry.model_validate({**entry.model_dump(), **changes})


def _compare_snapshots(before: SourceSnapshot, after: SourceSnapshot) -> list[SourceChange]:
    changes: list[SourceChange] = []
    before_directories = set(before.directories)
    after_directories = set(after.directories)
    changes.extend(
        SourceChange(source_relative_path=path, change="directory_removed")
        for path in sorted(before_directories - after_directories)
    )
    changes.extend(
        SourceChange(source_relative_path=path, change="directory_added")
        for path in sorted(after_directories - before_directories)
    )
    before_files = {item.relative_path: item for item in before.files}
    after_files = {item.relative_path: item for item in after.files}
    changes.extend(
        SourceChange(source_relative_path=path, change="removed")
        for path in sorted(before_files.keys() - after_files.keys())
    )
    changes.extend(
        SourceChange(source_relative_path=path, change="added")
        for path in sorted(after_files.keys() - before_files.keys())
    )
    for path in sorted(before_files.keys() & after_files.keys()):
        old = before_files[path]
        new = after_files[path]
        if old.sha256 != new.sha256 or old.size_bytes != new.size_bytes:
            changes.append(SourceChange(source_relative_path=path, change="modified"))
    return changes


def _write_validated_export(
    source: DiscoveredSource,
    result: ExtractionResult,
    configuration: TextExportConfiguration,
    output_relative_path: str,
    exported_at: datetime,
) -> str:
    if source.sha256 is None or result.body is None or result.extraction_tool is None:
        raise ValueError("Successful extraction is missing required output material.")
    output_path = safe_output_path(configuration.output_root, output_relative_path)
    if output_path.exists() and not (configuration.resume or configuration.overwrite):
        raise FileExistsError(f"Output already exists: {output_path}; use --resume or --overwrite.")
    value = render_export(
        source_filename=source.path.name,
        source_relative_path=source.relative_path,
        source_extension=source.extension,
        source_sha256=source.sha256,
        document_type=result.document_type,
        status=result.status,
        extraction_tool=result.extraction_tool,
        exported_at=exported_at,
        body=result.body,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    staged = output_path.with_name(f".{output_path.name}.{uuid4().hex}.staged")
    try:
        write_text_atomic(staged, value)
        digest = validate_text_export(
            staged,
            output_root=configuration.output_root,
            source_filename=source.path.name,
            source_relative_path=source.relative_path,
            source_extension=source.extension,
            source_sha256=source.sha256,
            document_type=result.document_type,
            page_or_slide_count=result.body.page_or_slide_count,
        )
        if sha256_file(source.path) != source.sha256:
            raise ValueError("Source changed during extraction; staged output was not finalized.")
        staged.replace(output_path)
        return digest
    finally:
        if staged.exists():
            staged.unlink()


def _plan_selected_sources(
    snapshot: SourceSnapshot, configuration: TextExportConfiguration
) -> set[str]:
    eligible = [
        source
        for source in snapshot.files
        if source.extension in SUPPORTED_TEXT_EXPORT_EXTENSIONS
        and source.extension in configuration.extensions
    ]
    if configuration.limit is not None:
        eligible = eligible[: configuration.limit]
    return {source.relative_path for source in eligible}


def _status_counts(entries: list[TextExportEntry]) -> Counter[ExportStatus]:
    return Counter(entry.export_status for entry in entries)


def _persist_reports(
    manifest: TextExportManifest,
    report: TextTreeRunReport,
    configuration: TextExportConfiguration,
) -> Path:
    write_json_atomic(
        configuration.output_root / "export-manifest.json", manifest.model_dump(mode="json")
    )
    directory = configuration.report_output_root / report.run_id
    write_json_atomic(directory / "run-report.json", report.model_dump(mode="json"))
    groups = {
        "failures.json": {ExportStatus.FAILED},
        "unsupported.json": {ExportStatus.UNSUPPORTED},
        "requires-ocr.json": {ExportStatus.REQUIRES_OCR},
        "skipped.json": {ExportStatus.SKIPPED_CURRENT, ExportStatus.PLANNED},
    }
    for filename, statuses in groups.items():
        payload = [
            entry.model_dump(mode="json")
            for entry in manifest.entries
            if entry.export_status in statuses
        ]
        write_json_atomic(directory / filename, payload)
    return directory


def extract_text_tree(
    configuration: TextExportConfiguration,
    *,
    now: Callable[[], datetime] = _utc_now,
    monotonic: Callable[[], float] = time.monotonic,
) -> TextTreeRunResult:
    """Plan or execute one complete sequential text-tree run."""
    _validate_disjoint_roots(configuration)
    started_at = now()
    started_clock = monotonic()
    before = snapshot_source_tree(configuration.input_root)
    outputs = plan_output_paths(before.files)
    run_id = _run_id(configuration, before, outputs)
    selected = _plan_selected_sources(before, configuration)
    previous_manifest = _load_previous_manifest(configuration)
    previous_by_path = (
        {entry.source_relative_path: entry for entry in previous_manifest.entries}
        if previous_manifest is not None
        else {}
    )
    entries: list[TextExportEntry] = []
    inspections: dict[str, PDFTechnicalInspection] = {}
    derivatives: dict[str, AcceptedDerivative | None] = {}
    derivative_warnings: dict[str, tuple[str, ...]] = {}

    extractor: LocalTextExtractor | None = None
    if not configuration.dry_run:
        settings = DoclingSettings.from_sources(configuration.docling_artifacts_path)
        extractor = LocalTextExtractor(settings)
        configuration.output_root.mkdir(parents=True, exist_ok=True)
        for relative_directory in before.directories:
            safe_output_path(configuration.output_root, relative_directory).mkdir(
                parents=True, exist_ok=True
            )

    for source in before.files:
        if source.extension not in SUPPORTED_TEXT_EXPORT_EXTENSIONS:
            entries.append(_base_entry(source, outputs, status=ExportStatus.UNSUPPORTED))
            continue
        if source.error is not None or source.sha256 is None:
            entries.append(
                _base_entry(
                    source,
                    outputs,
                    status=ExportStatus.FAILED,
                    errors=[source.error or "Source SHA-256 is unavailable."],
                )
            )
            continue
        if not _source_name_is_header_safe(source):
            entries.append(
                _base_entry(
                    source,
                    outputs,
                    status=ExportStatus.FAILED,
                    errors=["Source path contains a control or formatting character."],
                )
            )
            continue
        if source.relative_path not in selected:
            reason = (
                "Excluded by --extensions."
                if source.extension not in configuration.extensions
                else "Excluded by --limit."
            )
            entries.append(
                _base_entry(source, outputs, status=ExportStatus.PLANNED, warnings=[reason])
            )
            continue

        output_relative_path = outputs.output_by_source[source.relative_path]
        if configuration.resume:
            current, resume_warning = _prior_entry_current(
                source,
                output_relative_path,
                configuration,
                previous_by_path.get(source.relative_path),
            )
            if current:
                previous = previous_by_path[source.relative_path]
                entries.append(
                    _updated_entry(
                        _base_entry(source, outputs, status=ExportStatus.SKIPPED_CURRENT),
                        extraction_tool=previous.extraction_tool,
                        text_character_count=previous.text_character_count,
                        page_or_slide_count=previous.page_or_slide_count,
                        warnings=["Existing output passed complete resume validation."],
                        output_sha256=previous.output_sha256,
                    )
                )
                continue
        else:
            resume_warning = None

        if source.extension == ".pdf":
            inspection = inspect_pdf_technically(source, configuration.input_root)
            inspections[source.relative_path] = inspection
            derivative: AcceptedDerivative | None = None
            warnings: tuple[str, ...] = ()
            if (
                inspection.readable
                and not inspection.encrypted
                and (inspection.character_count or 0) == 0
            ):
                derivative, warnings = find_accepted_derivative(
                    source,
                    input_root=configuration.input_root,
                    derived_root=configuration.derived_root,
                )
            derivatives[source.relative_path] = derivative
            derivative_warnings[source.relative_path] = warnings
            if not inspection.readable or inspection.encrypted:
                message = inspection.error or (
                    "Encrypted PDF cannot be extracted."
                    if inspection.encrypted
                    else "PDF is unreadable."
                )
                entries.append(
                    _base_entry(
                        source,
                        outputs,
                        status=ExportStatus.FAILED,
                        errors=[message],
                    )
                )
                continue
            if (inspection.character_count or 0) == 0 and derivative is None:
                planned_warnings = list(warnings)
                if resume_warning:
                    planned_warnings.append(resume_warning)
                entries.append(
                    _updated_entry(
                        _base_entry(
                            source,
                            outputs,
                            status=ExportStatus.REQUIRES_OCR,
                            warnings=planned_warnings,
                        ),
                        extraction_tool="PyMuPDF inspection",
                        page_or_slide_count=inspection.page_count,
                    )
                )
                continue

        if configuration.dry_run:
            planning_warnings = [resume_warning] if resume_warning else []
            if derivatives.get(source.relative_path) is not None:
                planning_warnings.append(
                    "A validated accepted OCR derivative is available for extraction."
                )
            planning_warnings.extend(derivative_warnings.get(source.relative_path, ()))
            entries.append(
                _base_entry(
                    source,
                    outputs,
                    status=ExportStatus.PLANNED,
                    warnings=planning_warnings,
                )
            )
            continue

        assert extractor is not None
        result = extractor.extract(
            source,
            input_root=configuration.input_root,
            pdf_inspection=inspections.get(source.relative_path),
            accepted_derivative=derivatives.get(source.relative_path),
            derivative_warnings=derivative_warnings.get(source.relative_path, ()),
        )
        result_warnings = list(result.warnings)
        if resume_warning:
            result_warnings.append(resume_warning)
        if result.status not in {ExportStatus.EXPORTED, ExportStatus.EXPORTED_WITH_WARNINGS}:
            entries.append(
                _updated_entry(
                    _base_entry(
                        source,
                        outputs,
                        status=result.status,
                        warnings=result_warnings,
                        errors=list(result.errors),
                    ),
                    extraction_tool=result.extraction_tool,
                    text_character_count=(
                        result.body.text_character_count if result.body is not None else 0
                    ),
                    page_or_slide_count=(
                        result.body.page_or_slide_count if result.body is not None else None
                    ),
                )
            )
            continue
        try:
            output_digest = _write_validated_export(
                source,
                result,
                configuration,
                output_relative_path,
                now(),
            )
        except (OSError, ValueError) as exc:
            entries.append(
                _base_entry(
                    source,
                    outputs,
                    status=ExportStatus.FAILED,
                    warnings=result_warnings,
                    errors=[f"{type(exc).__name__}: {exc}"],
                )
            )
            continue
        assert result.body is not None
        entries.append(
            _updated_entry(
                _base_entry(
                    source,
                    outputs,
                    status=result.status,
                    warnings=result_warnings,
                ),
                extraction_tool=result.extraction_tool,
                text_character_count=result.body.text_character_count,
                page_or_slide_count=result.body.page_or_slide_count,
                output_sha256=output_digest,
            )
        )

    after = snapshot_source_tree(configuration.input_root)
    source_changes = _compare_snapshots(before, after)
    completed_at = now()
    counts = _status_counts(entries)
    proposed_count = sum(
        entry.export_status
        in {
            ExportStatus.PLANNED,
            ExportStatus.EXPORTED,
            ExportStatus.EXPORTED_WITH_WARNINGS,
            ExportStatus.SKIPPED_CURRENT,
        }
        for entry in entries
        if entry.output_relative_path is not None
    )
    manifest = TextExportManifest(
        run_id=run_id,
        generated_at=completed_at,
        input_root=str(configuration.input_root.resolve()),
        output_root=str(configuration.output_root.resolve()),
        entries=entries,
    )
    report = TextTreeRunReport(
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=max(0.0, monotonic() - started_clock),
        dry_run=configuration.dry_run,
        input_root=str(configuration.input_root.resolve()),
        output_root=str(configuration.output_root.resolve()),
        report_output_root=str(configuration.report_output_root.resolve()),
        discovered_count=len(entries),
        supported_count=sum(
            entry.extension in SUPPORTED_TEXT_EXPORT_EXTENSIONS for entry in entries
        ),
        planned_count=counts[ExportStatus.PLANNED],
        exported_count=counts[ExportStatus.EXPORTED],
        exported_with_warnings_count=counts[ExportStatus.EXPORTED_WITH_WARNINGS],
        skipped_current_count=counts[ExportStatus.SKIPPED_CURRENT],
        requires_ocr_count=counts[ExportStatus.REQUIRES_OCR],
        unsupported_count=counts[ExportStatus.UNSUPPORTED],
        empty_count=counts[ExportStatus.EMPTY],
        failed_count=counts[ExportStatus.FAILED],
        proposed_text_output_count=proposed_count,
        collision_count=len(outputs.collisions),
        total_source_bytes=sum(entry.source_size_bytes for entry in entries),
        total_exported_characters=sum(
            entry.text_character_count
            for entry in entries
            if entry.export_status
            in {
                ExportStatus.EXPORTED,
                ExportStatus.EXPORTED_WITH_WARNINGS,
                ExportStatus.SKIPPED_CURRENT,
            }
        ),
        source_immutable=not source_changes,
        source_changes=source_changes,
    )
    report_directory = None
    if not configuration.dry_run:
        report_directory = _persist_reports(manifest, report, configuration)
    return TextTreeRunResult(
        manifest=manifest,
        report=report,
        collisions=outputs.collisions,
        report_directory=report_directory,
    )
