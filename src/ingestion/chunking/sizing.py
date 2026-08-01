"""Deterministic text normalization and chunk-size utilities."""

from __future__ import annotations

import math
import re
import unicodedata
from hashlib import sha256


def normalize_text(text: str) -> str:
    """Normalize representation without changing terminology, case, or accents."""
    value = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", value):
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in paragraph.split("\n")]
        collapsed = " ".join(line for line in lines if line)
        if collapsed:
            paragraphs.append(collapsed)
    return "\n\n".join(paragraphs).strip()


def normalized_text_hash(text: str) -> str:
    return sha256(normalize_text(text).encode("utf-8")).hexdigest()


def estimate_tokens(character_count: int) -> int:
    """Estimate tokens without a tokenizer: ceil(character_count / 4)."""
    return math.ceil(character_count / 4)


def short_leading_context(text: str, maximum: int) -> str | None:
    normalized = normalize_text(text)
    if not normalized or maximum == 0:
        return None
    if len(normalized) <= maximum:
        return normalized
    boundary = normalized.rfind(" ", 0, maximum + 1)
    return normalized[: boundary if boundary > 0 else maximum].rstrip()


def short_trailing_context(text: str, maximum: int) -> str | None:
    normalized = normalize_text(text)
    if not normalized or maximum == 0:
        return None
    if len(normalized) <= maximum:
        return normalized
    start = len(normalized) - maximum
    boundary = normalized.find(" ", start)
    return normalized[boundary + 1 if boundary >= 0 else start :].lstrip()


def split_oversized_paragraph(text: str, hard_maximum: int) -> list[str]:
    """Split only at sentence/line/word boundaries as a last resort."""
    normalized_lines = text.replace("\r\n", "\n").replace("\r", "\n")
    sentences = [part for part in re.split(r"(?<=[.!?])\s+|\n+", normalized_lines.strip()) if part]
    if not sentences:
        return []
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > hard_maximum:
            if current:
                pieces.append(current)
                current = ""
            words = sentence.split(" ")
            word_group = ""
            for word in words:
                candidate = f"{word_group} {word}".strip()
                if word_group and len(candidate) > hard_maximum:
                    pieces.append(word_group)
                    word_group = word
                else:
                    word_group = candidate
            if word_group:
                pieces.append(word_group)
            continue
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > hard_maximum:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces
