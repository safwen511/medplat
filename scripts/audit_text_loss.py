"""Find PDF pages whose text export lost text present in the PDF's own text layer.

For every exported PDF (direct, OCR derivative, or LibreOffice PDF derivative of a Word file) each
text line of each physical page of the PDF that was parsed is checked against the matching
`===== PAGE n =====` section of the export, ignoring spacing and punctuation. Pages with lost
lines are listed in data/<year>/reports/text-loss.json with counts and short line excerpts.
Usage: python scripts/audit_text_loss.py --year dcem2
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import fitz

from ingestion.library import Year, get_year
from ingestion.normalization.coverage import compact, missing_share
from ingestion.output import write_json_atomic

PAGE_SEPARATOR = re.compile(r"^===== PAGE (\d+) =====$", re.MULTILINE)
MARKER = re.compile(r"^===== .* =====$", re.MULTILINE)
EXPORTED = {"exported", "exported_with_warnings", "skipped_current"}
# A line counts as lost when this share of it is absent from its page's export (the normalizer
# recovers lines at the same threshold).
LOST_LINE_SHARE = 0.5


def export_pages(path: Path) -> dict[int, str]:
    text = path.read_text(encoding="utf-8")
    matches = list(PAGE_SEPARATOR.finditer(text))
    return {
        int(match.group(1)): MARKER.sub(
            "", text[match.end() : matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        )
        for i, match in enumerate(matches)
    }


def parsed_pdfs(year: Year) -> list[tuple[str, Path, Path]]:
    """(source path, PDF that was parsed, text export) for every exported PDF-route source."""
    items = []
    manifest = json.loads((year.text / "export-manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["entries"]:
        if entry["extension"].lower() != ".pdf" or entry["export_status"] not in EXPORTED:
            continue
        pdf = year.source / entry["source_relative_path"]
        if "OCRmyPDF" in (entry["extraction_tool"] or ""):
            candidates = sorted((year.ocr / entry["source_sha256"]).glob("ocr/*/document-ocr.pdf"))
            if not candidates:
                continue
            pdf = candidates[0]
        text = year.text / entry["output_relative_path"]
        items.append((entry["source_relative_path"], pdf, text))
    office = year.text_office / "derived-export-manifest.json"
    if office.is_file():
        for entry in json.loads(office.read_text(encoding="utf-8"))["entries"]:
            derivative = year.office / entry["source_sha256"] / "derivative.pdf"
            if entry.get("output_relative_path") and derivative.is_file():
                text = year.text_office / entry["output_relative_path"]
                items.append((entry["source_relative_path"], derivative, text))
    return items


def audit(source: str, pdf_path: Path, text_path: Path) -> dict[str, object] | None:
    exported = export_pages(text_path)
    flagged = []
    total_lost = 0
    with fitz.open(pdf_path) as pdf:
        for number, page in enumerate(pdf, start=1):
            covered = compact(exported.get(number, ""))
            lost = []
            for line in page.get_text("text").splitlines():
                share = missing_share(line, covered)
                if share is not None and share >= LOST_LINE_SHARE:
                    lost.append(line.strip())
            if lost:
                characters = sum(len(compact(line)) for line in lost)
                total_lost += characters
                flagged.append(
                    {
                        "page": number,
                        "lost_lines": len(lost),
                        "lost_characters": characters,
                        "sample": [line[:60] for line in lost[:3]],
                    }
                )
    if not flagged:
        return None
    return {
        "source_relative_path": source,
        "parsed_pdf": str(pdf_path),
        "flagged_pages": len(flagged),
        "lost_characters": total_lost,
        "pages": flagged,
    }


def main(year: Year) -> int:
    results = []
    sources = parsed_pdfs(year)
    for source, pdf_path, text_path in sources:
        result = audit(source, pdf_path, text_path)
        if result is not None:
            results.append(result)
    results.sort(key=lambda item: -int(str(item["lost_characters"])))
    report = year.reports / "text-loss.json"
    write_json_atomic(report, {"audited_pdfs": len(sources), "files": results})
    pages = sum(int(str(item["flagged_pages"])) for item in results)
    print(f"{len(sources)} PDFs audited, {len(results)} with {pages} flagged pages -> {report}")
    for item in results[:25]:
        print(
            f"{item['lost_characters']:>7} chars {item['flagged_pages']:>4} pages  "
            f"{item['source_relative_path']}"
        )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", required=True, help="year id from library.toml")
    sys.exit(main(get_year(parser.parse_args().year)))
