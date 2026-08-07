"""Read-only discovery and structural parsing of mirrored text exports."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ingestion.hashing import sha256_file
from ingestion.text_tree.models import ExportStatus, TextExportEntry, TextExportManifest
from ingestion.text_tree.validation import HEADER_KEYS, parse_metadata_header

_LOCATION_MARKER = re.compile(r"^===== (PAGE|SLIDE) ([1-9][0-9]*) =====\s*$", re.MULTILINE)
_SINGLE_MARKERS = {
    "===== DOCUMENT CONTENT =====": "document",
    "===== SOURCE TEXT =====": "source",
}


@dataclass(frozen=True)
class RawBlock:
    text: str
    raw_start: int
    raw_end: int


@dataclass(frozen=True)
class RawLocation:
    location_id: str
    location_type: str
    location_number: int | None
    original_marker: str
    raw_start: int
    raw_end: int
    text: str
    blocks: tuple[RawBlock, ...]


@dataclass(frozen=True)
class RawExport:
    path: Path
    relative_path: str
    raw_text_sha256: str
    header: dict[str, str]
    body_start: int
    body: str
    locations: tuple[RawLocation, ...]
    manifest_entry: TextExportEntry


def load_export_manifest(input_root: Path) -> TextExportManifest:
    """Load the required upstream manifest from the immutable export root."""
    path = input_root / "export-manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"Text export manifest is missing: {path}")
    manifest = TextExportManifest.model_validate_json(path.read_text(encoding="utf-8"))
    if Path(manifest.output_root).resolve() != input_root.resolve():
        raise ValueError("Text export manifest output root does not match --input.")
    return manifest


def discover_exports(
    input_root: Path,
    manifest: TextExportManifest,
    *,
    selected_file: Path | None,
    limit: int | None,
) -> list[tuple[Path, TextExportEntry]]:
    """Discover validated successful UTF-8 exports in stable path order."""
    eligible_statuses = {
        ExportStatus.EXPORTED,
        ExportStatus.EXPORTED_WITH_WARNINGS,
        ExportStatus.SKIPPED_CURRENT,
    }
    by_output = {
        entry.output_relative_path: entry
        for entry in manifest.entries
        if entry.output_relative_path is not None and entry.export_status in eligible_statuses
    }
    discovered: list[tuple[Path, TextExportEntry]] = []
    for path in sorted(
        input_root.rglob("*.txt"), key=lambda value: value.relative_to(input_root).as_posix()
    ):
        if not path.is_file():
            continue
        relative = path.relative_to(input_root).as_posix()
        if selected_file is not None and relative != selected_file.as_posix():
            continue
        entry = by_output.get(relative)
        if entry is None:
            raise ValueError(f"Text export is not a successful manifest entry: {relative}")
        if entry.output_sha256 is None or sha256_file(path) != entry.output_sha256:
            raise ValueError(f"Text export hash does not match the upstream manifest: {relative}")
        discovered.append((path, entry))
    if selected_file is not None and not discovered:
        raise FileNotFoundError(f"Selected text export does not exist: {selected_file.as_posix()}")
    return discovered[:limit] if limit is not None else discovered


def _body_offset(value: str) -> int:
    offset = 0
    lines = value.splitlines(keepends=True)
    if len(lines) <= len(HEADER_KEYS):
        raise ValueError("Text export is shorter than its metadata header.")
    for line in lines[: len(HEADER_KEYS) + 1]:
        offset += len(line)
    return offset


def _blocks(text: str, absolute_start: int) -> tuple[RawBlock, ...]:
    values: list[RawBlock] = []
    cursor = 0
    for separator in re.finditer(r"\n[ \t]*\n+", text):
        part = text[cursor : separator.start()]
        if part.strip():
            left = len(part) - len(part.lstrip("\n"))
            right = len(part.rstrip("\n"))
            values.append(
                RawBlock(
                    text=part[left:right],
                    raw_start=absolute_start + cursor + left,
                    raw_end=absolute_start + cursor + right,
                )
            )
        cursor = separator.end()
    part = text[cursor:]
    if part.strip():
        left = len(part) - len(part.lstrip("\n"))
        right = len(part.rstrip("\n"))
        values.append(
            RawBlock(
                text=part[left:right],
                raw_start=absolute_start + cursor + left,
                raw_end=absolute_start + cursor + right,
            )
        )
    return tuple(values)


def _parse_locations(body: str, body_start: int) -> tuple[RawLocation, ...]:
    markers = list(_LOCATION_MARKER.finditer(body))
    locations: list[RawLocation] = []
    if markers:
        prefix = body[: markers[0].start()].strip()
        if prefix:
            raise ValueError("Text export has content before its first page or slide marker.")
        for index, marker in enumerate(markers, start=1):
            content_start = marker.end()
            while content_start < len(body) and body[content_start] == "\n":
                content_start += 1
            content_end = markers[index].start() if index < len(markers) else len(body)
            content = body[content_start:content_end].rstrip("\n")
            kind = marker.group(1).casefold()
            number = int(marker.group(2))
            locations.append(
                RawLocation(
                    location_id=f"location-{index:06d}",
                    location_type=kind,
                    location_number=number,
                    original_marker=marker.group(0).strip(),
                    raw_start=body_start + content_start,
                    raw_end=body_start + content_end,
                    text=content,
                    blocks=_blocks(content, body_start + content_start),
                )
            )
        return tuple(locations)

    stripped = body.lstrip("\n")
    leading = len(body) - len(stripped)
    for single_marker, kind in _SINGLE_MARKERS.items():
        if stripped.startswith(single_marker):
            content_start = leading + len(single_marker)
            while content_start < len(body) and body[content_start] == "\n":
                content_start += 1
            content = body[content_start:].rstrip("\n")
            return (
                RawLocation(
                    location_id="location-000001",
                    location_type=kind,
                    location_number=None,
                    original_marker=single_marker,
                    raw_start=body_start + content_start,
                    raw_end=body_start + len(body),
                    text=content,
                    blocks=_blocks(content, body_start + content_start),
                ),
            )
    raise ValueError("Text export has no recognized page, slide, document, or source marker.")


def parse_raw_export(path: Path, input_root: Path, entry: TextExportEntry) -> RawExport:
    """Parse one immutable UTF-8 export and retain character-offset provenance."""
    payload = path.read_bytes()
    try:
        value = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Text export is not UTF-8: {path}") from exc
    header, _ = parse_metadata_header(value)
    if entry.source_sha256 is None:
        raise ValueError("Successful export manifest entry has no source SHA-256.")
    expected = {
        "SOURCE_RELATIVE_PATH": entry.source_relative_path,
        "SOURCE_SHA256": entry.source_sha256,
        "SOURCE_EXTENSION": entry.extension,
    }
    for key, expected_value in expected.items():
        if header[key] != expected_value:
            raise ValueError(f"Text export {key} does not match its manifest entry.")
    start = _body_offset(value)
    body = value[start:]
    relative = path.relative_to(input_root).as_posix()
    return RawExport(
        path=path,
        relative_path=relative,
        raw_text_sha256=sha256_file(path),
        header=header,
        body_start=start,
        body=body,
        locations=_parse_locations(body, start),
        manifest_entry=entry,
    )
