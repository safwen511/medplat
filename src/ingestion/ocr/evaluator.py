"""Deterministic, non-semantic OCR eligibility evaluation."""

from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore[import-untyped]

from ingestion.hashing import sha256_file
from ingestion.ocr.models import OCREligibility, OCREvaluation

LOW_TEXT_CHARACTERS = 100


def evaluate_ocr(path: Path, *, source_root: Path = Path("pdfsrc")) -> OCREvaluation:
    relative = _relative(path, source_root)
    if path.suffix.lower() != ".pdf":
        return OCREvaluation(
            eligibility=OCREligibility.NOT_SUPPORTED,
            source_relative_path=relative,
            reason="OCR derivatives are supported only for PDF sources.",
        )
    if not path.is_file():
        return OCREvaluation(
            eligibility=OCREligibility.BLOCKED,
            source_relative_path=relative,
            reason="Source PDF does not exist.",
        )
    try:
        with fitz.open(path) as pdf:
            if pdf.needs_pass:
                return OCREvaluation(
                    eligibility=OCREligibility.BLOCKED,
                    source_sha256=sha256_file(path),
                    source_relative_path=relative,
                    page_count=pdf.page_count,
                    encrypted=True,
                    reason="Encrypted PDF cannot be OCRed without credentials.",
                )
            characters = [len(page.get_text("text")) for page in pdf]
            images = [len(page.get_images(full=True)) for page in pdf]
    except Exception as exc:
        return OCREvaluation(
            eligibility=OCREligibility.BLOCKED,
            source_sha256=sha256_file(path),
            source_relative_path=relative,
            reason=f"PDF is unreadable ({type(exc).__name__}).",
        )
    image_heavy = [index for index, count in enumerate(images, start=1) if count > 0]
    low_text = [
        index
        for index, (count, image_count) in enumerate(zip(characters, images, strict=True), start=1)
        if count < LOW_TEXT_CHARACTERS and image_count > 0
    ]
    ratio = len(low_text) / len(characters) if characters else 0.0
    if low_text and ratio >= 0.5:
        eligibility = OCREligibility.REQUIRED
        reason = "At least half of physical pages are low-text pages containing images."
    elif low_text:
        eligibility = OCREligibility.RECOMMENDED
        reason = "One or more low-text image pages may benefit from OCR."
    else:
        eligibility = OCREligibility.NOT_NEEDED
        reason = "No low-text image page meets the deterministic OCR threshold."
    return OCREvaluation(
        eligibility=eligibility,
        source_sha256=sha256_file(path),
        source_relative_path=relative,
        page_count=len(characters),
        total_extractable_characters=sum(characters),
        text_characters_by_page=characters,
        low_text_pages=low_text,
        image_heavy_pages=image_heavy,
        image_count=sum(images),
        encrypted=False,
        reason=reason,
    )


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name
