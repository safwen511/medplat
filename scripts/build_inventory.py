"""Build a deterministic file inventory of the mirrored course text export.

Reads only data/<year>/text/export-manifest.json, the exported `.txt` files, and the
text-office derivative manifest. Never opens the read-only library/<year> source tree.

Usage: python scripts/build_inventory.py --year dcem1
Outputs (under data/<year>/catalog/):
- inventory.json: one record per source file with normalized taxonomy and title hints
- inventory-digest.txt: compact human/LLM-readable listing grouped by discipline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from ingestion.library import PROJECT_ROOT, Year, get_year

# Google Drive zip suffixes such as "-20260802T083016Z-1-001".
_DRIVE_SUFFIX = re.compile(r"-\d{8}T\d{6}Z-\d+-\d+$")
_LEADING_NUMBER = re.compile(r"^\s*\d+\s*[-.]\s*")

MATERIAL_TYPES = {
    "diapos": "slides",
    "poly": "polycopie",
    "polycope": "polycopie",
    "poly nephro": "polycopie",
    "resume": "summary",
    "resumes": "summary",
    "resumes + qe": "summary",
    "astuces": "tips",
    "td": "tutorial",
    "examens": "exams",
    "generalites": "general",
}

# Folder segments that only repeat structure and carry no taxonomy.
_STRUCTURAL = {"2-pole b", "certif uro - nephro"}


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()


def _clean_segment(segment: str) -> str:
    return _DRIVE_SUFFIX.sub("", unicodedata.normalize("NFC", segment)).strip()


def normalized_segments(relative_path: str) -> list[str]:
    """Folder segments without Drive suffixes, consecutive repeats, or structural wrappers."""
    segments: list[str] = []
    for raw in Path(relative_path).parts[:-1]:
        segment = _clean_segment(raw)
        if segments and _fold(segment) == _fold(segments[-1]):
            continue
        if _fold(segment) in _STRUCTURAL:
            continue
        segments.append(segment)
    return segments


def classify(segments: list[str]) -> dict[str, str | None]:
    pole = segments[0] if segments else None
    certif = segments[1] if len(segments) > 1 else None
    material = None
    material_index = None
    for index, segment in enumerate(segments):
        folded = _LEADING_NUMBER.sub("", _fold(segment))
        if folded in MATERIAL_TYPES:
            material = MATERIAL_TYPES[folded]
            material_index = index
            break
    end = material_index if material_index is not None else len(segments)
    discipline_parts = segments[2:end]
    discipline = discipline_parts[0] if discipline_parts else None
    subfolder = segments[material_index + 1 :] if material_index is not None else []
    return {
        "pole": pole,
        "certif": certif,
        "discipline": discipline,
        "material_type": material,
        "author_or_subfolder": " / ".join(subfolder) or None,
    }


def title_hints(text: str, limit: int = 4) -> list[str]:
    """First distinct slide titles, or first substantive lines for documents."""
    body = text.split("\n\n", 1)[1] if text.startswith("SOURCE_FILE:") else text
    hints: list[str] = []
    titles = re.findall(r"TITLE:\n(.+)", body)
    candidates = titles or [line for line in body.splitlines()]
    for line in candidates:
        line = line.strip()
        if (
            len(line) < 4
            or line.startswith("=====")
            or line.isupper()
            and line.endswith(":")
            or re.fullmatch(r"[\d\W]+", line)
        ):
            continue
        if line not in hints:
            hints.append(line[:120])
        if len(hints) >= limit:
            break
    return hints


_WORD = re.compile(r"[^\W\d_]{3,}", re.UNICODE)


def _words(text: str) -> list[str]:
    body = text.split("\n\n", 1)[1] if text.startswith("SOURCE_FILE:") else text
    return [_fold(word) for word in _WORD.findall(body)]


def build_vocabulary(texts: list[str], min_documents: int = 4) -> set[str]:
    """Words seen in several documents; OCR garbage is overwhelmingly document-unique."""
    document_frequency: dict[str, int] = defaultdict(int)
    for text in texts:
        for word in set(_words(text)):
            document_frequency[word] += 1
    return {word for word, count in document_frequency.items() if count >= min_documents}


def text_quality(text: str, vocabulary: set[str]) -> tuple[float | None, str]:
    words = _words(text)
    if len(words) < 50:
        return None, "empty"
    score = sum(word in vocabulary for word in words) / len(words)
    label = "good" if score >= 0.85 else "noisy" if score >= 0.65 else "unusable"
    return round(score, 3), label


def main(year: Year) -> int:
    export_root = year.text
    text_root = str(year.text.relative_to(PROJECT_ROOT))
    # Text exported from validated LibreOffice .pptx derivatives of legacy .ppt/.ppsx sources.
    office_text_root = str(year.text_office.relative_to(PROJECT_ROOT))
    output_root = year.catalog
    manifest = json.loads((export_root / "export-manifest.json").read_text(encoding="utf-8"))
    derived_manifest = year.text_office / "derived-export-manifest.json"
    derived = {}
    if derived_manifest.is_file():
        for item in json.loads(derived_manifest.read_text(encoding="utf-8"))["entries"]:
            if item.get("output_relative_path"):
                derived[item["source_relative_path"]] = item
    for entry in manifest["entries"]:
        item = derived.get(entry["source_relative_path"])
        if item and item["source_sha256"] == entry["source_sha256"]:
            entry.update(
                export_status="exported_from_derivative",
                output_relative_path=item["output_relative_path"],
                text_character_count=item["text_character_count"],
                page_or_slide_count=item["page_or_slide_count"],
                text_root=office_text_root,
            )
    texts: dict[str, str] = {}
    for entry in manifest["entries"]:
        root = PROJECT_ROOT / entry["text_root"] if entry.get("text_root") else export_root
        text_path = entry.get("output_relative_path")
        if text_path and entry["export_status"] != "unsupported" and (root / text_path).is_file():
            texts[entry["source_relative_path"]] = (root / text_path).read_text(encoding="utf-8")
    vocabulary = build_vocabulary(list(texts.values()))
    records = []
    for entry in sorted(manifest["entries"], key=lambda e: e["source_relative_path"]):
        relative_path = entry["source_relative_path"]
        segments = normalized_segments(relative_path)
        text_path = entry.get("output_relative_path")
        text = texts.get(relative_path)
        hints = title_hints(text) if text else []
        quality_score, quality = text_quality(text, vocabulary) if text else (None, "empty")
        records.append(
            {
                "source_relative_path": relative_path,
                "source_sha256": entry["source_sha256"],
                "filename": Path(relative_path).name,
                "extension": entry["extension"],
                "export_status": entry["export_status"],
                "text_root": entry.get("text_root", text_root),
                "text_relative_path": text_path,
                "characters": entry.get("text_character_count"),
                "pages_or_slides": entry.get("page_or_slide_count"),
                "segments": segments,
                **classify(segments),
                "title_hints": hints,
                "text_quality_score": quality_score,
                "text_quality": quality,
            }
        )

    seen: dict[str, str] = {}
    for record in records:
        first = seen.setdefault(record["source_sha256"], record["source_relative_path"])
        record["exact_duplicate_of"] = None if first == record["source_relative_path"] else first

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "inventory.json").write_text(
        json.dumps({"schema_version": "0.1.0", "records": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for record in records:
        key = (record["pole"] or "?", record["certif"] or "?", record["discipline"] or "-")
        grouped[key].append(record)
    lines: list[str] = []
    for (pole, certif, discipline), items in sorted(grouped.items()):
        lines.append(f"\n## {pole} > {certif} > {discipline}  ({len(items)} files)")
        for record in items:
            flags = []
            if record["export_status"] not in {
                "skipped_current",
                "exported",
                "exported_with_warnings",
                "exported_from_derivative",
            }:
                flags.append(record["export_status"])
            if record["exact_duplicate_of"]:
                flags.append("DUP")
            if record["text_quality"] != "good":
                flags.append(f"Q={record['text_quality']}:{record['text_quality_score']}")
            sub = f" [{record['author_or_subfolder']}]" if record["author_or_subfolder"] else ""
            size = f"{record['characters'] or 0}c/{record['pages_or_slides'] or 0}p"
            hint = " | ".join(record["title_hints"][:3])
            lines.append(
                f"{record['material_type'] or '?':9} {record['filename']}{sub} ({size})"
                f"{' ' + ','.join(flags) if flags else ''} :: {hint}"
            )
    (output_root / "inventory-digest.txt").write_text(
        "\n".join(lines).strip() + "\n", encoding="utf-8"
    )
    print(f"{len(records)} records, {len(grouped)} discipline groups -> {output_root}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", required=True, help="year id from library.toml")
    sys.exit(main(get_year(parser.parse_args().year)))
