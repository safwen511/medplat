"""Validated atomic persistence for canonical documents."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import fitz  # type: ignore[import-untyped]

from ingestion.normalization.models import (
    NormalizedDocument,
    ProcessingReport,
    ProcessingStatus,
)
from ingestion.normalization.validation import validate_document_file


class OutputExistsError(FileExistsError):
    """Raised when a successful document output is protected from overwrite."""


class UnsafeOutputError(ValueError):
    """Raised when generated output would be written into the source library."""


def ensure_output_outside_source(output_root: Path, source_root: Path) -> None:
    """Reject output roots equal to or nested below the read-only source root."""
    output = output_root.resolve()
    source = source_root.resolve()
    if output == source or output.is_relative_to(source):
        raise UnsafeOutputError("Output must be outside the read-only source directory.")


def _markdown(document: NormalizedDocument) -> str:
    lines = [f"# {document.title or document.source_filename}", ""]
    for page in document.pages:
        if page.location_type.value == "page":
            lines.extend([f"## Page {page.number}", ""])
        elif page.location_type.value == "slide":
            lines.extend([f"## Slide {page.number}", ""])
        for block in page.blocks:
            if not block.text:
                continue
            if block.block_type.value == "heading":
                lines.extend([f"### {block.text}", ""])
            elif block.block_type.value == "list_item":
                lines.append(f"- {block.text}")
            elif block.block_type.value == "title":
                lines.extend([f"## {block.text}", ""])
            else:
                lines.extend([block.text, ""])
    return "\n".join(lines).rstrip() + "\n"


def _materialize_pdf_assets(
    source_path: Path, document: NormalizedDocument, assets_directory: Path
) -> None:
    with fitz.open(source_path) as pdf:
        for asset in document.assets:
            reference = asset.original_object_reference
            if not reference or not reference.startswith("pdf-xref:"):
                continue
            xref = int(reference.partition(":")[2])
            image = pdf.extract_image(xref)
            extension = str(image.get("ext", "bin"))
            relative_path = Path("assets") / f"{asset.asset_id}.{extension}"
            payload = bytes(image["image"])
            (assets_directory / relative_path.name).write_bytes(payload)
            asset.extracted_relative_path = relative_path.as_posix()
            asset.sha256 = sha256(payload).hexdigest()
            asset.mime_type = f"image/{'jpeg' if extension == 'jpg' else extension}"


def _render_pdf_previews(source_path: Path, previews_directory: Path) -> None:
    with fitz.open(source_path) as pdf:
        for number, page in enumerate(pdf, start=1):
            page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False).save(
                previews_directory / f"page-{number:04d}.png"
            )


def write_normalized_output(
    document: NormalizedDocument,
    report: ProcessingReport,
    *,
    source_path: Path,
    source_root: Path,
    output_root: Path,
    extract_assets: bool = False,
    render_previews: bool = False,
    force: bool = False,
    output_relative_path: Path | None = None,
) -> Path:
    """Persist a successful result with validation and directory-level atomicity."""
    ensure_output_outside_source(output_root, source_root)
    output_root.mkdir(parents=True, exist_ok=True)
    relative_output = output_relative_path or Path(document.document_id)
    if relative_output.is_absolute() or ".." in relative_output.parts:
        raise UnsafeOutputError("Canonical output path must remain below the output root.")
    final_directory = output_root / relative_output
    if not final_directory.resolve().is_relative_to(output_root.resolve()):
        raise UnsafeOutputError("Canonical output path escaped the output root.")
    final_directory.parent.mkdir(parents=True, exist_ok=True)
    if final_directory.exists() and not force:
        raise OutputExistsError(
            f"Output already exists for {document.document_id}; use --force to replace it."
        )

    temporary = final_directory.parent / f".{final_directory.name}.{uuid4().hex}.tmp"
    backup = final_directory.parent / f".{final_directory.name}.{uuid4().hex}.backup"
    temporary.mkdir()
    try:
        assets_directory = temporary / "assets"
        previews_directory = temporary / "previews"
        assets_directory.mkdir()
        previews_directory.mkdir()
        unsupported = list(report.unsupported_features)
        if extract_assets:
            if document.source_extension == ".pdf":
                _materialize_pdf_assets(source_path, document, assets_directory)
            else:
                unsupported.append(
                    "Asset materialization is currently implemented only for PDF embedded images."
                )
        if render_previews:
            if document.source_extension == ".pdf":
                _render_pdf_previews(source_path, previews_directory)
            else:
                unsupported.append("Preview rendering is currently implemented only for PDF.")

        intended_paths = [
            str(final_directory / "document.json"),
            str(final_directory / "document.md"),
            str(final_directory / "processing-report.json"),
        ]
        report.output_paths = intended_paths
        report.unsupported_features = unsupported
        report.completion_time = datetime.now(timezone.utc)
        (temporary / "document.json").write_text(
            document.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        (temporary / "document.md").write_text(_markdown(document), encoding="utf-8")
        (temporary / "processing-report.json").write_text(
            report.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )

        validated = validate_document_file(temporary / "document.json")
        if validated.document_id != document.document_id:
            raise ValueError("Persisted document ID changed during validation.")
        ProcessingReport.model_validate_json(
            (temporary / "processing-report.json").read_text(encoding="utf-8")
        )
        if report.status not in {ProcessingStatus.SUCCESS, ProcessingStatus.PARTIAL_SUCCESS}:
            raise ValueError("Only successful results may be finalized.")

        if final_directory.exists():
            final_directory.rename(backup)
        temporary.rename(final_directory)
        if backup.exists():
            shutil.rmtree(backup)
        return final_directory
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup.exists() and not final_directory.exists():
            backup.rename(final_directory)
        raise


def write_json_atomic(path: Path, payload: object) -> None:
    """Write a standalone JSON report through a same-directory temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
