"""JSON and CSV report generation."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from ingestion.models import (
    DocumentClassification,
    DocumentInspection,
    DuplicateGroup,
    ErrorReportEntry,
    LibraryReport,
)

MANIFEST_JSON = "library-manifest.json"
MANIFEST_CSV = "library-manifest.csv"
DUPLICATES_JSON = "duplicate-files.json"
ERRORS_JSON = "inspection-errors.json"
UNSUPPORTED_JSON = "unsupported-files.json"


def duplicate_groups(report: LibraryReport) -> list[DuplicateGroup]:
    """Return deterministic groups of documents with identical content."""
    grouped: dict[str, list[str]] = defaultdict(list)
    sizes: dict[str, int] = {}
    for document in report.documents:
        if document.sha256 is not None and document.file_size is not None:
            grouped[document.sha256].append(document.relative_path)
            sizes[document.sha256] = document.file_size
    return [
        DuplicateGroup(
            sha256=digest,
            file_size=sizes[digest],
            relative_paths=sorted(paths),
        )
        for digest, paths in sorted(grouped.items())
        if len(paths) > 1
    ]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_reports(report: LibraryReport, output: Path) -> list[Path]:
    """Write the manifest and its derived reports, returning their paths."""
    output.mkdir(parents=True, exist_ok=True)
    manifest_json = output / MANIFEST_JSON
    manifest_csv = output / MANIFEST_CSV
    duplicates_json = output / DUPLICATES_JSON
    errors_json = output / ERRORS_JSON
    unsupported_json = output / UNSUPPORTED_JSON

    _write_json(manifest_json, report.model_dump(mode="json"))
    rows = [document.model_dump(mode="json") for document in report.documents]
    fieldnames = list(rows[0]) if rows else list(DocumentInspection.model_fields)
    with manifest_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            error = row.get("error")
            if isinstance(error, dict):
                row["error"] = json.dumps(error, ensure_ascii=False)
            writer.writerow(row)

    _write_json(
        duplicates_json,
        [group.model_dump(mode="json") for group in duplicate_groups(report)],
    )
    errors = [
        ErrorReportEntry(relative_path=document.relative_path, error=document.error)
        for document in report.documents
        if document.error is not None
    ]
    _write_json(errors_json, [entry.model_dump(mode="json") for entry in errors])
    unsupported = [
        document.model_dump(mode="json")
        for document in report.documents
        if document.classification is DocumentClassification.UNSUPPORTED_FOR_NOW
    ]
    _write_json(unsupported_json, unsupported)
    return [manifest_json, manifest_csv, duplicates_json, errors_json, unsupported_json]
