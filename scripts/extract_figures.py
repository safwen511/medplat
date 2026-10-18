"""Extract figures from the PDF pages of lesson sources, so lessons can show them by citation.

For every PDF used as a lesson source (slides, polycopié, summaries; reference books and scans
excluded), each embedded image is rendered together with what is drawn over it (labels,
arrows) by clipping the page to the image's box. Tiny images, page-filling scan backgrounds and
decoration repeated on many pages (logos, slide templates) are skipped. Figures are written to
data/<year>/figures/<source-sha256>/p<page>-<n>.jpg and listed in data/<year>/figures/manifest.json
with their source path and physical page: a lesson unit citing [S2 p.12] can show the figures of
its S2 source on page 12. Local and free. Resumable: sources already in the manifest with the
same SHA-256 are skipped.

Usage: python scripts/extract_figures.py --year dcem2 [--limit N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import fitz

from ingestion.library import Year, get_year
from ingestion.output import write_json_atomic

ROLES = {"official_slides", "official_polycopie", "student_summary", "tips", "tutorial"}
MIN_SIDE_POINTS = 60  # smaller boxes are icons and bullets
MIN_PAGE_SHARE = 0.02  # of the page area
MAX_PAGE_SHARE = 0.92  # page-filling images are scan or template backgrounds
DECORATION_PAGES = 3  # an image repeated on at least this many pages ...
DECORATION_SHARE = 0.25  # ... and on this share of the pages is decoration
LONG_EDGE = 1200  # pixels of the rendered figure
GAP = 6  # points: boxes closer than this belong to one figure
MAX_PLACEMENTS = 200  # image placements on one page above which the page is one picture


def lesson_sources(year: Year) -> dict[str, dict[str, Any]]:
    """Inventory records of the PDFs used as lesson sources."""
    inventory = {
        r["source_relative_path"]: r
        for r in json.loads((year.catalog / "inventory.json").read_text())["records"]
    }
    catalog = json.loads((year.catalog / "catalog.json").read_text(encoding="utf-8"))
    selected = {}
    for certif in catalog["certifs"]:
        for module in certif["modules"]:
            for lesson in module["lessons"]:
                for source in lesson["sources"]:
                    record = inventory[source["path"]]
                    if (
                        source["role"] in ROLES
                        and record["extension"].lower() == ".pdf"
                        and record["export_status"] != "requires_ocr"
                    ):
                        selected[source["path"]] = record
    return selected


def image_digest(document: fitz.Document, xref: int) -> str:
    return hashlib.sha256(document.extract_image(xref)["image"]).hexdigest()


def clusters(boxes: list[tuple[fitz.Rect, float]]) -> list[tuple[fitz.Rect, float]]:
    """Merge image boxes that overlap or nearly touch: one diagram made of several images."""
    if len(boxes) > MAX_PLACEMENTS:
        # A page tiled from hundreds of image fragments is one picture; pairwise merging of
        # that many boxes would not finish.
        union = fitz.Rect(boxes[0][0])
        for box, _ppp in boxes[1:]:
            union |= box
        return [(union, max(ppp for _box, ppp in boxes))]
    merged = [(fitz.Rect(box), ppp) for box, ppp in boxes]
    changed = True
    while changed:
        changed = False
        for i in range(len(merged)):
            for j in range(i + 1, len(merged)):
                (a, ppp_a), (b, ppp_b) = merged[i], merged[j]
                grown = fitz.Rect(a.x0 - GAP, a.y0 - GAP, a.x1 + GAP, a.y1 + GAP)
                if grown.intersects(b):
                    merged[i] = (a | b, max(ppp_a, ppp_b))
                    del merged[j]
                    changed = True
                    break
            if changed:
                break
    return merged


def figures(path: Path, out_dir: Path) -> list[dict[str, Any]]:
    found = []
    with fitz.open(path) as document:
        placements: dict[int, list[tuple[str, fitz.Rect, float]]] = {}
        pages_per_digest: dict[str, set[int]] = {}
        digest_of: dict[int, str] = {}
        for page in document:
            number = page.number + 1
            for image in page.get_images(full=True):
                xref, pixel_width = int(image[0]), int(image[2])
                if xref not in digest_of:
                    digest_of[xref] = image_digest(document, xref)
                for rect in page.get_image_rects(xref):
                    box = rect & page.rect
                    if box.is_empty:
                        continue
                    ppp = pixel_width / max(rect.width, 1.0)  # native pixels per point
                    placements.setdefault(number, []).append((digest_of[xref], box, ppp))
                    pages_per_digest.setdefault(digest_of[xref], set()).add(number)
        decoration = {
            digest
            for digest, pages in pages_per_digest.items()
            if len(pages) >= DECORATION_PAGES
            and len(pages) / document.page_count >= DECORATION_SHARE
        }
        for number, placed in sorted(placements.items()):
            page = document[number - 1]
            kept = [(box, ppp) for digest, box, ppp in placed if digest not in decoration]
            index = 0
            for box, ppp in sorted(clusters(kept), key=lambda item: (item[0].y0, item[0].x0)):
                share = box.get_area() / page.rect.get_area()
                if (
                    min(box.width, box.height) < MIN_SIDE_POINTS
                    or not MIN_PAGE_SHARE <= share <= MAX_PAGE_SHARE
                ):
                    continue
                index += 1
                # Render overlaid labels sharply, but never upscale the image itself much.
                zoom = min(LONG_EDGE / max(box.width, box.height), max(2.0, 1.5 * ppp))
                pixmap = page.get_pixmap(
                    matrix=fitz.Matrix(zoom, zoom), clip=box, colorspace=fitz.csRGB
                )
                name = f"p{number}-{index}.jpg"
                out_dir.mkdir(parents=True, exist_ok=True)
                partial = out_dir / f"{name}.partial"
                partial.write_bytes(pixmap.tobytes("jpeg", jpg_quality=82))
                partial.replace(out_dir / name)
                found.append(
                    {
                        "page": number,
                        "file": name,
                        "width": pixmap.width,
                        "height": pixmap.height,
                        "bbox": [round(v, 1) for v in (box.x0, box.y0, box.x1, box.y1)],
                        "page_share": round(share, 3),
                    }
                )
    return found


def main(year: Year, limit: int | None) -> int:
    root = year.data / "figures"
    manifest_path = root / "manifest.json"
    manifest: dict[str, Any] = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    )
    sources = lesson_sources(year)
    todo = [
        (path, record)
        for path, record in sorted(sources.items())
        if manifest.get(path, {}).get("source_sha256") != record["source_sha256"]
    ]
    for done, (path, record) in enumerate(todo[:limit] if limit else todo, start=1):
        try:
            found = figures(year.source / path, root / record["source_sha256"])
            manifest[path] = {"source_sha256": record["source_sha256"], "figures": found}
        except Exception as exc:  # keep going; the failure is recorded and retried next run
            manifest[path] = {"source_sha256": None, "error": f"{type(exc).__name__}: {exc}"}
        if done % 25 == 0:
            write_json_atomic(manifest_path, manifest)
    write_json_atomic(manifest_path, manifest)
    total = sum(len(entry.get("figures", [])) for entry in manifest.values())
    with_figures = sum(bool(entry.get("figures")) for entry in manifest.values())
    errors = sum("error" in entry for entry in manifest.values())
    print(
        f"{len(manifest)} sources: {total} figures in {with_figures} sources, {errors} errors "
        f"-> {manifest_path}"
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", required=True, help="year id from library.toml")
    parser.add_argument("--limit", type=int, help="process at most N sources")
    arguments = parser.parse_args()
    sys.exit(main(get_year(arguments.year), arguments.limit))
