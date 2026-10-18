from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from reconstruct_lessons import slice_pages  # noqa: E402

TEXT = "HEADER\n\n" + "\n\n".join(f"===== PAGE {n} =====\n\npage {n} text" for n in range(1, 8))


def test_slice_pages_keeps_listed_ranges_with_their_separators() -> None:
    sliced = slice_pages(TEXT, "PAGE 2-3, 6")
    assert "===== PAGE 2 =====" in sliced and "page 3 text" in sliced
    assert "page 6 text" in sliced
    assert "page 1 text" not in sliced and "page 4 text" not in sliced
    assert "HEADER" not in sliced


def test_slice_pages_without_locations_keeps_every_page_and_slides() -> None:
    assert slice_pages(TEXT, None).count("=====") == 14
    slides = "===== SLIDE 1 =====\n\na\n\n===== SLIDE 2 =====\n\nb"
    assert slice_pages(slides, "SLIDE 2") == "===== SLIDE 2 =====\n\nb"
