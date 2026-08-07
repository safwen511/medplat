"""Deterministic text-readiness and missing-layout classification."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ingestion.preparation.models import LocationReadiness, ReadinessStatus
from ingestion.preparation.parsing import RawExport, RawLocation

_SCANNER = re.compile(r"\b(?:CamScanner|Scanned\s+with|scanner)\b", re.IGNORECASE)
_CAPTION = re.compile(r"\b(?:figure|fig\.|sch[ée]ma|image|radiographie|scanner|photo)\s*\d*", re.I)
_FLOW = re.compile(r"\b(?:arbre|algorithme|conduite\s+[àa]\s+tenir|cause\s+[ée]vidente)\b", re.I)
_AMBIGUOUS_NUMBER = re.compile(r"\b\d+\s{2,}(?:e\s*)?\d+\b", re.I)
_BROKEN_FONT = re.compile(
    r"(?:&[A-Za-z]{3,}|�|\u0000|\b[A-Za-z]\s+[A-Za-z]\s+[A-Za-z]\s+[A-Za-z]\b)"
)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_MALFORMED_HEADING = re.compile(r"^(?:I{1,4}|IV|V|VI{0,3}|IX|X)(?=[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ])")


@dataclass(frozen=True)
class ReadinessResult:
    document_status: ReadinessStatus
    locations: tuple[LocationReadiness, ...]
    warnings: tuple[str, ...]


def _alpha_ratio(value: str) -> float:
    retained = [character for character in value if not character.isspace()]
    if not retained:
        return 0.0
    return sum(character.isalpha() for character in retained) / len(retained)


def _single_character_word_ratio(value: str) -> float:
    words = _WORD.findall(value)
    if not words:
        return 1.0
    return sum(len(word) == 1 for word in words) / len(words)


def _symbol_ratio(value: str) -> float:
    retained = [character for character in value if not character.isspace()]
    if not retained:
        return 0.0
    symbols = sum(unicodedata.category(character).startswith(("S", "C")) for character in retained)
    return symbols / len(retained)


def assess_location(
    location: RawLocation,
    cleaned_text: str,
    *,
    duplicate_burden: int,
) -> LocationReadiness:
    """Classify one physical or logical source location without model inference."""
    raw = location.text
    meaningful = _SCANNER.sub("", cleaned_text).strip(" -|\n\t")
    alphabetic_ratio = _alpha_ratio(meaningful)
    reasons: list[str] = []
    status = ReadinessStatus.READY

    if _SCANNER.search(raw):
        reasons.append("scanner_watermark")
    if not meaningful or len(meaningful) < 20:
        reasons.append("sparse_or_empty_location")
        status = (
            ReadinessStatus.IMAGE_DEPENDENT
            if _SCANNER.search(raw) or _CAPTION.search(raw)
            else ReadinessStatus.UNUSABLE
        )
    elif len(meaningful) < 80:
        letters = [character for character in meaningful if character.isalpha()]
        uppercase_ratio = (
            sum(character.isupper() for character in letters) / len(letters) if letters else 0.0
        )
        if len(location.blocks) <= 2 and uppercase_ratio >= 0.5:
            reasons.append("title_only_location")
        else:
            reasons.append("sparse_location")
            status = ReadinessStatus.PARTIALLY_RECONSTRUCTABLE

    words = _WORD.findall(meaningful)
    if meaningful and (
        alphabetic_ratio < 0.35
        or _single_character_word_ratio(meaningful) > 0.35
        or _symbol_ratio(meaningful) > 0.2
        or (len(meaningful) < 100 and len(words) < 12 and max(map(len, words), default=0) < 5)
    ):
        reasons.append("probable_ocr_gibberish")
        status = (
            ReadinessStatus.UNUSABLE if len(words) < 12 else ReadinessStatus.HUMAN_REVIEW_REQUIRED
        )
    if _BROKEN_FONT.search(raw):
        reasons.append("broken_font_or_character_mapping")
        status = ReadinessStatus.HUMAN_REVIEW_REQUIRED
    if _AMBIGUOUS_NUMBER.search(raw):
        reasons.append("ambiguous_numerical_notation")
        if status is ReadinessStatus.READY:
            status = ReadinessStatus.READY_WITH_NOISE
    if _CAPTION.search(raw) and len(meaningful) < 500:
        reasons.append("caption_without_recoverable_visual_content")
        if status in {ReadinessStatus.READY, ReadinessStatus.READY_WITH_NOISE}:
            status = ReadinessStatus.IMAGE_DEPENDENT
    nonempty_lines = [line.strip() for line in raw.splitlines() if line.strip()]
    short_lines = [line for line in nonempty_lines if len(line) <= 24]
    bullet_lines = [line for line in nonempty_lines if line.startswith(("-", "•", ""))]
    long_lines = [line for line in nonempty_lines if len(line) >= 80]
    likely_spatial = (
        len(short_lines) >= 10 and not long_lines and len(bullet_lines) * 2 < len(nonempty_lines)
    )
    if _FLOW.search(raw) or likely_spatial:
        reasons.append("probable_flattened_flowchart_or_spatial_layout")
        if status is ReadinessStatus.READY:
            status = ReadinessStatus.PARTIALLY_RECONSTRUCTABLE
    if "===== TABLE" in raw and not any("|" in line for line in raw.splitlines()):
        reasons.append("empty_or_detached_table")
        if status is ReadinessStatus.READY:
            status = ReadinessStatus.READY_WITH_NOISE
    if duplicate_burden:
        reasons.append("duplicate_extraction_burden")
        if status is ReadinessStatus.READY:
            status = ReadinessStatus.READY_WITH_NOISE
    block_values = [" ".join(block.text.split()) for block in location.blocks if block.text.strip()]
    broken_fragments = sum(
        len(left) >= 25
        and not left.startswith(("-", "===== TABLE"))
        and not left.endswith((".", ":", ";", "?", "!", ")"))
        and bool(right)
        and right[0].islower()
        for left, right in zip(block_values, block_values[1:], strict=False)
    )
    if broken_fragments >= 2:
        reasons.append("broken_sentence_fragments")
        if status is ReadinessStatus.READY:
            status = ReadinessStatus.READY_WITH_NOISE
    if any(_MALFORMED_HEADING.search(value) for value in block_values):
        reasons.append("malformed_heading")
        if status is ReadinessStatus.READY:
            status = ReadinessStatus.READY_WITH_NOISE

    model_eligible = status not in {ReadinessStatus.UNUSABLE, ReadinessStatus.IMAGE_DEPENDENT}
    return LocationReadiness(
        location_id=location.location_id,
        location_type=location.location_type,  # type: ignore[arg-type]
        location_number=location.location_number,
        raw_character_count=len(raw),
        cleaned_character_count=len(cleaned_text),
        alphabetic_ratio=round(alphabetic_ratio, 6),
        duplicate_burden=duplicate_burden,
        status=status,
        reason_codes=sorted(set(reasons)),
        model_eligible=model_eligible,
    )


def assess_document(
    raw: RawExport,
    cleaned_by_location: dict[str, str],
    duplicate_burden_by_location: dict[str, int],
) -> ReadinessResult:
    """Aggregate location readiness while retaining useful parts of mixed documents."""
    locations = tuple(
        assess_location(
            location,
            cleaned_by_location.get(location.location_id, ""),
            duplicate_burden=duplicate_burden_by_location.get(location.location_id, 0),
        )
        for location in raw.locations
    )
    statuses = {location.status for location in locations}
    useful = sum(location.model_eligible for location in locations)
    if not locations or all(status is ReadinessStatus.UNUSABLE for status in statuses):
        document_status = ReadinessStatus.UNUSABLE
    elif useful == 0 and ReadinessStatus.IMAGE_DEPENDENT in statuses:
        document_status = ReadinessStatus.IMAGE_DEPENDENT
    elif ReadinessStatus.HUMAN_REVIEW_REQUIRED in statuses:
        document_status = ReadinessStatus.HUMAN_REVIEW_REQUIRED
    elif statuses.intersection({ReadinessStatus.UNUSABLE, ReadinessStatus.IMAGE_DEPENDENT}):
        document_status = ReadinessStatus.PARTIALLY_RECONSTRUCTABLE
    elif ReadinessStatus.PARTIALLY_RECONSTRUCTABLE in statuses:
        document_status = ReadinessStatus.PARTIALLY_RECONSTRUCTABLE
    elif ReadinessStatus.READY_WITH_NOISE in statuses:
        document_status = ReadinessStatus.READY_WITH_NOISE
    else:
        document_status = ReadinessStatus.READY
    warning_codes = sorted({reason for location in locations for reason in location.reason_codes})
    return ReadinessResult(
        document_status=document_status,
        locations=locations,
        warnings=tuple(warning_codes),
    )
