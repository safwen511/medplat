"""Conservative deterministic cleaning with reversible source-span provenance."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256

from ingestion.preparation.models import (
    CLEANING_VERSION,
    PREPARATION_SCHEMA_VERSION,
    CleaningSidecar,
    DeterministicTransformation,
    LocationMarkerMode,
    MetadataClass,
    SourceSpan,
    TransformationType,
)
from ingestion.preparation.parsing import RawBlock, RawExport, RawLocation
from ingestion.preparation.readiness import assess_document

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACE = re.compile(r"[ \t\u00a0]+")
_BLANKS = re.compile(r"\n{3,}")
_BULLET = re.compile(r"^(?:[-–—•●▪▫◦‣⁃❖✓]+|[-–—]?\s*[])\s*")
_SPLIT_WORD = re.compile(r"(?<=\w)-\s*\n\s*(?=[a-zà-öø-ÿ])", re.UNICODE)
_TABLE_MARKER = re.compile(r"^===== TABLE ([1-9][0-9]*) =====$")
_TEACHER = re.compile(r"\b(?:Pr(?:of(?:esseur)?)?\.?|Dr\.?)\s+[A-ZÀ-ÖØ-Þ]", re.I)
_INSTITUTION = re.compile(
    r"\b(?:facult[ée]|universit[ée]|h[oô]pital|chu\b|service\s+de|minist[eè]re|centre\s+r[ée]gional)",
    re.I,
)
_YEAR = re.compile(r"\b(?:19|20)\d{2}\s*[-–/]\s*(?:19|20)?\d{2}\b")
_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_SCANNER_ONLY = re.compile(r"^(?:CamScanner|Scanned\s+with\s+CamScanner)$", re.I)


@dataclass
class _Paragraph:
    raw_block: RawBlock
    location: RawLocation
    text: str
    classification: MetadataClass = MetadataClass.BODY_CONTENT
    retained: bool = True
    reason: str | None = None
    transformation_type: TransformationType | None = None
    span_id: str = ""
    cleaned_start: int = 0
    cleaned_end: int = 0


@dataclass(frozen=True)
class CleanedArtifact:
    text: str
    sidecar: CleaningSidecar


def _stable_hash(payload: object) -> str:
    value = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(value.encode("utf-8")).hexdigest()


def _normalized_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _normalize_block(value: str) -> tuple[str, TransformationType | None, str | None]:
    original = value
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\u0085", "\n").replace("\u2028", "\n").replace("\u2029", "\n")
    value = _CONTROL.sub("", value)
    repaired = _SPLIT_WORD.sub("", value)
    split_repaired = repaired != value
    value = repaired
    normalized_lines: list[str] = []
    for line in value.splitlines():
        line = _SPACE.sub(" ", line).strip()
        bullet = _BULLET.match(line)
        if bullet is not None:
            line = "- " + line[bullet.end() :].lstrip()
        normalized_lines.append(line)
    if any("|" in line for line in normalized_lines) or any(
        line.startswith("- ") for line in normalized_lines
    ):
        value = "\n".join(line for line in normalized_lines if line)
    else:
        value = " ".join(line for line in normalized_lines if line)
    value = value.strip()
    if value == original:
        return value, None, None
    if split_repaired:
        return (
            value,
            TransformationType.SPLIT_WORD_REPAIR,
            "Exact line-end split-word recombination.",
        )
    return (
        value,
        TransformationType.PARAGRAPH_REASSEMBLY,
        "Whitespace and intra-block line normalization.",
    )


def _classification(text: str, ordinal: int) -> MetadataClass:
    if _TEACHER.search(text) or re.search(r"\bAuteur\s*:", text, re.I):
        return MetadataClass.TEACHER_NAME
    if _INSTITUTION.search(text):
        return MetadataClass.INSTITUTION
    if _YEAR.search(text):
        return MetadataClass.ACADEMIC_YEAR
    stripped = text.strip(" :-")
    if (
        ordinal < 18
        and 3 <= len(stripped) <= 180
        and not stripped.startswith("-")
        and not stripped.endswith((".", ";"))
        and sum(character.isalpha() for character in stripped) >= 3
    ):
        return MetadataClass.COURSE_TITLE
    return MetadataClass.BODY_CONTENT


def _boundary_duplicates(paragraphs: list[_Paragraph]) -> tuple[set[str], set[str]]:
    by_location: dict[str, list[_Paragraph]] = {}
    for paragraph in paragraphs:
        if paragraph.text and not _TABLE_MARKER.fullmatch(paragraph.text):
            by_location.setdefault(paragraph.location.location_id, []).append(paragraph)
    header_counts: Counter[str] = Counter()
    footer_counts: Counter[str] = Counter()
    for values in by_location.values():
        header_counts.update(
            {_normalized_key(item.text) for item in values[:4] if len(item.text) < 220}
        )
        footer_counts.update(
            {_normalized_key(item.text) for item in values[-2:] if len(item.text) < 220}
        )
    threshold = max(2, (len(by_location) + 1) // 2)
    return (
        {value for value, count in header_counts.items() if count >= threshold and value},
        {value for value, count in footer_counts.items() if count >= threshold and value},
    )


def _table_duplicate_candidates(values: list[_Paragraph]) -> set[int]:
    """Return only strict expanded copies whose tokens are wholly represented in a nearby table."""
    suppress: set[int] = set()
    for index, paragraph in enumerate(values):
        if "|" not in paragraph.text or index == 0:
            continue
        table_tokens = Counter(token.casefold() for token in _WORD.findall(paragraph.text))
        if sum(table_tokens.values()) < 4:
            continue
        for candidate_index in range(index + 1, min(len(values), index + 9)):
            candidate = values[candidate_index]
            if "|" in candidate.text or _TABLE_MARKER.fullmatch(candidate.text):
                break
            candidate_tokens = Counter(token.casefold() for token in _WORD.findall(candidate.text))
            if sum(candidate_tokens.values()) < 4:
                continue
            if all(table_tokens[token] >= count for token, count in candidate_tokens.items()):
                suppress.add(candidate_index)
    return suppress


def _location_marker(location: RawLocation, mode: LocationMarkerMode) -> str | None:
    if mode is LocationMarkerMode.REMOVE or location.location_type in {"document", "source"}:
        return None
    if mode is LocationMarkerMode.KEEP:
        return location.original_marker
    label = "Page" if location.location_type == "page" else "Slide"
    return f"[{label} {location.location_number}]"


def _language(value: str) -> str:
    arabic = sum("\u0600" <= character <= "\u06ff" for character in value)
    latin = sum("LATIN" in unicodedata.name(character, "") for character in value)
    if arabic and latin:
        return "fr+ar"
    return "ar" if arabic else "fr"


def clean_export(raw: RawExport, marker_mode: LocationMarkerMode) -> CleanedArtifact:
    """Create readable deterministic text and a complete cleaning provenance sidecar."""
    paragraphs: list[_Paragraph] = []
    for location in raw.locations:
        for block in location.blocks:
            normalized, transformation_type, reason = _normalize_block(block.text)
            for field_label in ("TITLE:", "CONTENT:", "NOTES:"):
                if normalized == field_label or normalized.startswith(field_label + " "):
                    normalized = normalized.removeprefix(field_label).strip()
                    transformation_type = TransformationType.METADATA_CLASSIFICATION
                    reason = "Removed an extraction-only PowerPoint field label."
                    break
            if _SCANNER_ONLY.fullmatch(normalized):
                normalized = ""
                transformation_type = TransformationType.METADATA_CLASSIFICATION
                reason = "Removed a scanner watermark with no course content."
            paragraphs.append(
                _Paragraph(
                    raw_block=block,
                    location=location,
                    text=normalized,
                    transformation_type=transformation_type,
                    reason=reason,
                )
            )

    header_keys, footer_keys = _boundary_duplicates(paragraphs)
    seen_boundary: set[tuple[str, str]] = set()
    location_values: dict[str, list[_Paragraph]] = {}
    for ordinal, paragraph in enumerate(paragraphs):
        paragraph.span_id = f"span-{ordinal + 1:06d}"
        paragraph.classification = _classification(paragraph.text, ordinal)
        key = _normalized_key(paragraph.text)
        boundary_type: str | None = None
        if key in header_keys:
            boundary_type = "header"
        elif key in footer_keys:
            boundary_type = "footer"
        if boundary_type is not None:
            occurrence = (boundary_type, key)
            if occurrence in seen_boundary:
                paragraph.classification = (
                    MetadataClass.REPEATED_HEADER
                    if boundary_type == "header"
                    else MetadataClass.REPEATED_FOOTER
                )
                paragraph.retained = False
                paragraph.reason = f"Suppressed an exact repeated {boundary_type}."
                paragraph.transformation_type = TransformationType.DUPLICATE_SUPPRESSION
            else:
                seen_boundary.add(occurrence)
        location_values.setdefault(paragraph.location.location_id, []).append(paragraph)

    for values in location_values.values():
        previous_key: str | None = None
        strict_table_duplicates = _table_duplicate_candidates(values)
        for index, paragraph in enumerate(values):
            key = _normalized_key(paragraph.text)
            if paragraph.retained and key and key == previous_key:
                paragraph.retained = False
                paragraph.reason = "Suppressed an exact adjacent duplicate."
                paragraph.transformation_type = TransformationType.DUPLICATE_SUPPRESSION
            elif paragraph.retained and index in strict_table_duplicates:
                paragraph.retained = False
                paragraph.reason = (
                    "Suppressed an exact expanded copy represented in the nearby table."
                )
                paragraph.transformation_type = TransformationType.DUPLICATE_SUPPRESSION
            if paragraph.retained and key:
                previous_key = key

    output_parts: list[str] = []
    offset = 0
    for location in raw.locations:
        marker = _location_marker(location, marker_mode)
        if marker is not None:
            if output_parts:
                output_parts.append("\n\n")
                offset += 2
            output_parts.append(marker)
            offset += len(marker)
        for paragraph in location_values.get(location.location_id, []):
            if not paragraph.retained or not paragraph.text:
                paragraph.cleaned_start = offset
                paragraph.cleaned_end = offset
                continue
            if output_parts and not output_parts[-1].endswith("\n\n"):
                output_parts.append("\n\n")
                offset += 2
            paragraph.cleaned_start = offset
            output_parts.append(paragraph.text)
            offset += len(paragraph.text)
            paragraph.cleaned_end = offset
    cleaned = _BLANKS.sub("\n\n", "".join(output_parts)).strip() + "\n"

    cleaned_by_location: dict[str, str] = {}
    duplicate_burden: dict[str, int] = {}
    for location_id, values in location_values.items():
        cleaned_by_location[location_id] = "\n\n".join(
            item.text for item in values if item.retained and item.text
        )
        duplicate_burden[location_id] = sum(
            item.transformation_type is TransformationType.DUPLICATE_SUPPRESSION for item in values
        )
    readiness = assess_document(raw, cleaned_by_location, duplicate_burden)

    spans = [
        SourceSpan(
            span_id=paragraph.span_id,
            location_id=paragraph.location.location_id,
            location_type=paragraph.location.location_type,  # type: ignore[arg-type]
            location_number=paragraph.location.location_number,
            raw_start=paragraph.raw_block.raw_start,
            raw_end=paragraph.raw_block.raw_end,
            cleaned_start=paragraph.cleaned_start,
            cleaned_end=paragraph.cleaned_end,
            source_sha256=raw.header["SOURCE_SHA256"],
            classification=paragraph.classification,
            retained=paragraph.retained and bool(paragraph.text),
        )
        for paragraph in paragraphs
    ]
    transformations = [
        DeterministicTransformation(
            transformation_id=f"clean-{index:06d}",
            transformation_type=paragraph.transformation_type,
            raw_span_ids=[paragraph.span_id],
            original_text=paragraph.raw_block.text,
            cleaned_text=paragraph.text if paragraph.retained else "",
            reason=paragraph.reason or "Deterministic normalization.",
        )
        for index, paragraph in enumerate(paragraphs, start=1)
        if paragraph.transformation_type is not None
    ]
    removed_duplicates = [
        paragraph.span_id
        for paragraph in paragraphs
        if paragraph.transformation_type is TransformationType.DUPLICATE_SUPPRESSION
        and not paragraph.retained
    ]
    title = next(
        (
            paragraph.text
            for paragraph in paragraphs
            if paragraph.retained and paragraph.classification is MetadataClass.COURSE_TITLE
        ),
        None,
    )
    teachers = list(
        dict.fromkeys(
            paragraph.text
            for paragraph in paragraphs
            if paragraph.retained and paragraph.classification is MetadataClass.TEACHER_NAME
        )
    )
    institutions = list(
        dict.fromkeys(
            paragraph.text
            for paragraph in paragraphs
            if paragraph.retained and paragraph.classification is MetadataClass.INSTITUTION
        )
    )
    years = list(
        dict.fromkeys(
            match.group(0) for paragraph in paragraphs for match in _YEAR.finditer(paragraph.text)
        )
    )
    identity_payload = {
        "strategy": CLEANING_VERSION,
        "schema_version": PREPARATION_SCHEMA_VERSION,
        "raw_text_sha256": raw.raw_text_sha256,
        "source_sha256": raw.header["SOURCE_SHA256"],
        "relative_path": raw.relative_path,
        "location_markers": marker_mode.value,
    }
    sidecar = CleaningSidecar(
        cleaning_identity=_stable_hash(identity_payload),
        source_relative_path=raw.header["SOURCE_RELATIVE_PATH"],
        source_sha256=raw.header["SOURCE_SHA256"],
        raw_extracted_text_relative_path=raw.relative_path,
        raw_extracted_text_sha256=raw.raw_text_sha256,
        cleaned_text_sha256=sha256(cleaned.encode("utf-8")).hexdigest(),
        text_export_schema_version=raw.header["TEXT_EXPORT_SCHEMA_VERSION"],
        extraction_status=raw.header["EXTRACTION_STATUS"],
        extraction_tool=raw.header["EXTRACTION_TOOL"],
        document_type=raw.header["DOCUMENT_TYPE"],
        exported_at=raw.header["EXPORTED_AT"],
        location_markers=marker_mode,
        metadata_header=raw.header,
        detected_language=_language(cleaned),
        detected_title=title,
        teacher_names=teachers,
        institutions=institutions,
        academic_years=years,
        spans=spans,
        transformations=transformations,
        removed_duplicates=removed_duplicates,
        retained_duplicates=[],
        repeated_headers=sorted(header_keys),
        repeated_footers=sorted(footer_keys),
        readiness_status=readiness.document_status,
        location_readiness=list(readiness.locations),
        warnings=list(readiness.warnings),
        cleaned_character_count=len(cleaned),
    )
    return CleanedArtifact(text=cleaned, sidecar=sidecar)
