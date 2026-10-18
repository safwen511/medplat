"""Spacing-insensitive text coverage, used to detect source text missing from an export.

Word segmentation differs between PDF text readers (OCR text layers often glue words together),
so text is compared as compact letter/digit strings cut into fixed-size pieces.
"""

from __future__ import annotations

import unicodedata

PIECE = 8


def compact(value: str) -> str:
    """Case-folded letters and digits only, without whitespace or punctuation."""
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value).casefold()
        if character.isalnum()
    )


def missing_share(text: str, covered: str) -> float | None:
    """Share of the text's pieces absent from the compact covered text; None if too short."""
    value = compact(text)
    if len(value) < PIECE * 2:
        return None
    pieces = [value[index : index + PIECE] for index in range(0, len(value) - PIECE + 1, PIECE)]
    return sum(piece not in covered for piece in pieces) / len(pieces)
