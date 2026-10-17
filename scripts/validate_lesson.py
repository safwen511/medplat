"""Deterministic source-grounding validator for a reconstructed lesson.

A lesson directory contains:
- lesson.json: metadata with a `sources` map such as
  {"S1": {"text_root", "text_relative_path", "role", ...}}
- lesson.md: the reconstructed course. Every content unit (paragraph, list item, table row) carries
  citations such as [S1 p.10], [S2 p.270-271; S3 p.2] or [S4 slide 5].

Checks:
- every content unit has at least one citation, and every cited source/page exists;
- every number in a unit occurs in the text of at least one of its cited pages (after
  normalizing decimal commas and thousands spaces);
- units supported only by student summaries are reported, not rejected.

This checks traceability only. It never establishes medical correctness.
Usage: python scripts/validate_lesson.py data/<year>/lessons/<lesson_id>
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from ingestion.library import PROJECT_ROOT as ROOT

CITATION_BLOCK = re.compile(r"\[((?:S\d+\s+(?:p|slide)\.?\s*\d+(?:-\d+)?(?:\s*[;,]\s*)?)+)\]")
CITATION = re.compile(r"(S\d+)\s+(p|slide)\.?\s*(\d+)(?:-(\d+))?")
NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)?(?!\d)")
PAGE_SEPARATOR = re.compile(r"^===== (PAGE|SLIDE) (\d+) =====$", re.MULTILINE)
OFFICIAL_ROLES = {"official_slides", "official_polycopie"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace(" ", " ")
    text = re.sub(r"(?<=\d) (?=\d{3}(?!\d))", "", text)
    return re.sub(r"(?<=\d),(?=\d)", ".", text)


# A unit is a slash compound (mg/kg/j, mmol/l) whose first segment is a known unit.
UNIT = re.compile(r"\s*([a-zµ°%]+(?:/[a-z0-9µ]+)*)", re.IGNORECASE)
UNIT_BASES = {
    "mg", "g", "µg", "µmol", "mmol", "ng", "ml", "l", "ui", "h", "heure", "heures", "min",
    "minutes", "j", "jour", "jours", "semaine", "semaines", "mois", "an", "ans", "%", "°", "°c",
    "cas", "élément", "éléments", "gouttes",
}  # fmt: skip
UNIT_ALIASES = {
    "jour": "j",
    "jours": "j",
    "heure": "h",
    "heures": "h",
    "minutes": "min",
    "semaine": "semaines",
    "an": "ans",
    "élément": "éléments",
    "°c": "°",
}


def _unit(normalized: str, end: int) -> str | None:
    match = UNIT.match(normalized, end)
    if not match:
        return None
    segments = match.group(1).lower().split("/")
    if segments[0] not in UNIT_BASES:
        return None
    return "/".join(UNIT_ALIASES.get(segment, segment) for segment in segments)


def numbers(text: str) -> set[str]:
    """Numbers, each also keyed with its unit when one follows (e.g. '12', '12 mg')."""
    normalized = normalize(text)
    found: set[str] = set()
    for match in NUMBER.finditer(normalized):
        found.add(match.group(0))
        unit = _unit(normalized, match.end())
        if unit:
            found.add(f"{match.group(0)} {unit}")
    return found


def claimed_numbers(text: str) -> set[str]:
    """The strictest form of each number in a claim: with its unit when it has one."""
    all_forms = numbers(text)
    with_unit = {form.split(" ")[0] for form in all_forms if " " in form}
    return {form for form in all_forms if " " in form or form not in with_unit}


def load_pages(path: Path) -> dict[int, str]:
    text = path.read_text(encoding="utf-8")
    matches = list(PAGE_SEPARATOR.finditer(text))
    return {
        int(match.group(2)): text[
            match.end() : matches[index + 1].start() if index + 1 < len(matches) else len(text)
        ]
        for index, match in enumerate(matches)
    }


@dataclass
class Unit:
    line: int
    text: str
    citations: list[tuple[str, int, int]] = field(default_factory=list)


def content_units(markdown: str) -> list[Unit]:
    """Paragraphs, list items, and table rows; headings, separators, and notes are skipped."""
    units: list[Unit] = []
    paragraph: list[str] = []
    start = 0

    def flush() -> None:
        if paragraph:
            units.append(Unit(start, " ".join(paragraph)))
            paragraph.clear()

    lines = markdown.splitlines()
    separator = re.compile(r"\|?[\s:|-]+\|?")
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        is_table_header = (
            line.startswith("|")
            and number < len(lines)
            and separator.fullmatch(lines[number].strip())
        )
        if not line or line.startswith(("#", ">")) or separator.fullmatch(line) or is_table_header:
            flush()
            continue
        if line.startswith(("- ", "* ", "|")):
            flush()
            units.append(Unit(number, line))
            continue
        if not paragraph:
            start = number
        paragraph.append(line)
    flush()
    return units


@dataclass
class Report:
    units: int
    cited: int
    errors: list[str]
    student_only: list[str]


def validate(lesson_dir: Path) -> Report:
    meta = json.loads((lesson_dir / "lesson.json").read_text(encoding="utf-8"))
    sources = meta["sources"]
    pages = {
        key: load_pages(ROOT / source["text_root"] / source["text_relative_path"])
        for key, source in sources.items()
    }
    markdown = (lesson_dir / "lesson.md").read_text(encoding="utf-8")
    # Front matter before the first heading is metadata, not content.
    body = markdown[markdown.index("\n#") :] if not markdown.startswith("#") else markdown
    offset = markdown[: len(markdown) - len(body)].count("\n")

    errors: list[str] = []
    student_only: list[str] = []
    units = content_units(body)
    for unit in units:
        where = f"line {unit.line + offset}"
        blocks = CITATION_BLOCK.findall(unit.text)
        for block in blocks:
            for key, _kind, first, last in CITATION.findall(block):
                unit.citations.append((key, int(first), int(last or first)))
        if not unit.citations:
            errors.append(f"{where}: no citation: {unit.text[:90]}")
            continue
        cited_text = ""
        for key, first, last in unit.citations:
            if key not in pages:
                errors.append(f"{where}: unknown source {key}")
                continue
            for page in range(first, last + 1):
                if page not in pages[key]:
                    errors.append(f"{where}: {key} has no page/slide {page}")
                else:
                    cited_text += pages[key][page]
        claim = CITATION_BLOCK.sub(" ", unit.text)
        missing = sorted(claimed_numbers(claim) - numbers(cited_text))
        if missing:
            errors.append(f"{where}: numbers not in cited pages {missing}: {claim[:90]}")
        if not any(
            sources[key]["role"] in OFFICIAL_ROLES for key, _, _ in unit.citations if key in sources
        ):
            student_only.append(f"line {unit.line + offset}: {claim.strip()[:110]}")

    cited = sum(1 for unit in units if unit.citations)
    return Report(len(units), cited, errors, student_only)


def main(lesson_dir: Path) -> int:
    report = validate(lesson_dir)
    print(
        f"{report.units} content units, {report.cited} cited, {len(report.errors)} errors, "
        f"{len(report.student_only)} student-only"
    )
    for error in report.errors:
        print(f"ERROR {error}")
    if report.student_only:
        print("\nSupported only by student summaries (reviewer attention):")
        for item in report.student_only:
            print(f"  {item}")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
