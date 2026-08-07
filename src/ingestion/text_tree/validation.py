"""Validation and resume checks for finalized UTF-8 text exports."""

from __future__ import annotations

import re
from pathlib import Path

from ingestion.hashing import sha256_file
from ingestion.text_tree.models import TEXT_EXPORT_SCHEMA_VERSION, ExportStatus

HEADER_KEYS = (
    "SOURCE_FILE",
    "SOURCE_RELATIVE_PATH",
    "SOURCE_EXTENSION",
    "SOURCE_SHA256",
    "DOCUMENT_TYPE",
    "EXTRACTION_STATUS",
    "EXTRACTION_TOOL",
    "EXPORTED_AT",
    "TEXT_EXPORT_SCHEMA_VERSION",
)


def parse_metadata_header(value: str) -> tuple[dict[str, str], str]:
    """Parse the exact ordered nine-line header and return its body."""
    lines = value.splitlines()
    if len(lines) < len(HEADER_KEYS) + 2:
        raise ValueError("Text export is missing its metadata header or content body.")
    header: dict[str, str] = {}
    for index, key in enumerate(HEADER_KEYS):
        prefix = f"{key}:"
        if not lines[index].startswith(prefix):
            raise ValueError(f"Text export header field {index + 1} must be {key}.")
        header[key] = lines[index][len(prefix) :].lstrip()
    if lines[len(HEADER_KEYS)] != "":
        raise ValueError("Text export metadata header must be followed by a blank line.")
    body = "\n".join(lines[len(HEADER_KEYS) + 1 :]) + "\n"
    return header, body


def _validate_success_body(body: str, document_type: str) -> None:
    labels = {
        "pdf": set(),
        "powerpoint": {"TITLE:", "CONTENT:", "NOTES:"},
        "word": {"===== DOCUMENT CONTENT ====="},
        "text": {"===== SOURCE TEXT ====="},
    }[document_type]
    retained: list[str] = []
    for line in body.splitlines():
        if line in labels:
            continue
        if document_type != "text" and re.fullmatch(
            r"===== (PAGE|SLIDE|TABLE) [1-9][0-9]* =====", line
        ):
            continue
        retained.append(line)
    if not "\n".join(retained).strip():
        raise ValueError("Successful text export contains no extracted source text.")


def validate_text_export(
    path: Path,
    *,
    output_root: Path,
    source_filename: str,
    source_relative_path: str,
    source_extension: str,
    source_sha256: str,
    document_type: str,
    page_or_slide_count: int | None,
    expected_output_sha256: str | None = None,
) -> str:
    """Validate UTF-8, metadata, navigation separators, containment, and hash."""
    root = output_root.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Text export path escaped the configured output root.")
    payload = path.read_bytes()
    try:
        value = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Text export is not valid UTF-8.") from exc
    header, body = parse_metadata_header(value)
    expected = {
        "SOURCE_FILE": source_filename,
        "SOURCE_RELATIVE_PATH": source_relative_path,
        "SOURCE_EXTENSION": source_extension,
        "SOURCE_SHA256": source_sha256,
        "DOCUMENT_TYPE": document_type,
        "TEXT_EXPORT_SCHEMA_VERSION": TEXT_EXPORT_SCHEMA_VERSION,
    }
    for key, expected_value in expected.items():
        if header[key] != expected_value:
            raise ValueError(f"Text export {key} does not match its source identity.")
    if header["EXTRACTION_STATUS"] not in {
        ExportStatus.EXPORTED.value,
        ExportStatus.EXPORTED_WITH_WARNINGS.value,
    }:
        raise ValueError("Only successful extraction states may have a text export.")
    if not header["EXTRACTION_TOOL"] or not header["EXPORTED_AT"]:
        raise ValueError("Text export tool and timestamp metadata must be nonempty.")
    _validate_success_body(body, document_type)
    if document_type == "pdf":
        numbers = [int(value) for value in re.findall(r"^===== PAGE ([0-9]+) =====$", body, re.M)]
        if page_or_slide_count is None or numbers != list(range(1, page_or_slide_count + 1)):
            raise ValueError("PDF page separators do not match the reported page count.")
    elif document_type == "powerpoint":
        numbers = [int(value) for value in re.findall(r"^===== SLIDE ([0-9]+) =====$", body, re.M)]
        if page_or_slide_count is None or numbers != list(range(1, page_or_slide_count + 1)):
            raise ValueError("PPTX slide separators do not match the reported slide count.")
    elif document_type == "word":
        if body.count("===== DOCUMENT CONTENT =====") != 1:
            raise ValueError("DOCX export must contain one document-content separator.")
    elif document_type == "text":
        if body.count("===== SOURCE TEXT =====") != 1:
            raise ValueError("TXT export must contain one source-text separator.")
    digest = sha256_file(path)
    if expected_output_sha256 is not None and digest != expected_output_sha256:
        raise ValueError("Text export SHA-256 does not match the manifest.")
    return digest
