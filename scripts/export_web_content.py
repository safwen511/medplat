"""Export the static website content of one year from the pipeline outputs.

Writes web/content/<faculty>/<year>/:
- index.json                certifs -> modules -> lessons, with availability and exam counts
- lessons/<lesson_id>.json  validated lesson markdown, source labels, figures on cited pages
- exercises/<lesson_id>.json  exercises from data/<year>/exercises/<lesson_id>.json, if any
and copies the figures of cited pages to web/public/figures/<source-sha256>/.

Only lessons that pass scripts/validate_lesson.py are exported; everything stays labelled with
its review status. Usage: python scripts/export_web_content.py --year dcem2
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from validate_lesson import CITATION, validate

from ingestion.library import PROJECT_ROOT, Year, get_year
from ingestion.output import write_json_atomic

WEB = PROJECT_ROOT / "web"
FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def lesson_summary(
    lesson: dict[str, Any], year: Year, exam_counts: dict[str, int]
) -> dict[str, Any]:
    lesson_id = lesson["lesson_id"]
    exercises = year.data / "exercises" / f"{lesson_id}.json"
    count = len(json.loads(exercises.read_text())["items"]) if exercises.is_file() else 0
    return {
        "id": lesson_id,
        "title": lesson["title"],
        "order": lesson.get("order") or 0,
        "aliases": lesson.get("aliases", []),
        "available": (year.lessons / lesson_id / "lesson.md").is_file(),
        "exerciseCount": count,
        "pastExamCount": exam_counts.get(lesson_id, 0),
    }


def cited_pages(markdown: str) -> set[tuple[str, int]]:
    pages = set()
    for key, _kind, start, end in CITATION.findall(markdown):
        for page in range(int(start), int(end or start) + 1):
            pages.add((key, page))
    return pages


def export_lesson(
    year: Year,
    lesson_id: str,
    certif: dict[str, Any],
    module: dict[str, Any],
    figures: dict[str, Any],
    out: Path,
    lessons_root: Path | None = None,
    exercises_root: Path | None = None,
    allow_errors: bool = False,
) -> bool:
    directory = (lessons_root or year.lessons) / lesson_id
    report = validate(directory)
    if report.errors and not allow_errors:
        print(f"skip {lesson_id}: {len(report.errors)} validation errors")
        return False
    metadata = json.loads((directory / "lesson.json").read_text(encoding="utf-8"))
    markdown = FRONT_MATTER.sub("", (directory / "lesson.md").read_text(encoding="utf-8")).lstrip()
    lesson_figures = []
    for key, page in sorted(cited_pages(markdown)):
        source = metadata["sources"].get(key)
        entry = figures.get(source["path"]) if source else None
        for figure in (entry or {}).get("figures", []):
            if figure["page"] != page:
                continue
            sha = entry["source_sha256"]
            target = WEB / "public" / "figures" / sha / figure["file"]
            if not target.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(year.data / "figures" / sha / figure["file"], target)
            lesson_figures.append(
                {
                    "source": key,
                    "page": page,
                    "src": f"/figures/{sha}/{figure['file']}",
                    "width": figure["width"],
                    "height": figure["height"],
                }
            )
    write_json_atomic(
        out / "lessons" / f"{lesson_id}.json",
        {
            "id": lesson_id,
            "title": metadata["title"],
            "certif": certif["certif_slug"],
            "certifTitle": certif["certif"],
            "module": module["module"],
            "status": metadata["status"],
            "markdown": markdown,
            "sources": [
                {"key": key, "label": source["label"], "role": source["role"]}
                for key, source in metadata["sources"].items()
            ],
            "figures": lesson_figures,
            "validationErrors": report.errors,
        },
    )
    exercises = (exercises_root or year.data / "exercises") / f"{lesson_id}.json"
    if exercises.is_file():
        shutil.copyfile(exercises, out / "exercises" / f"{lesson_id}.json")
    return True


def export_comparison(year: Year, run: str) -> int:
    """Validated drafts of a comparison run, for /dev/comparer (never part of the site)."""
    out = WEB / "content" / "_compare" / year.faculty_slug / year.id / run
    for sub in ("lessons", "exercises"):
        shutil.rmtree(out / sub, ignore_errors=True)
        (out / sub).mkdir(parents=True)
    catalog = json.loads((year.catalog / "catalog.json").read_text(encoding="utf-8"))
    manifest = year.data / "figures" / "manifest.json"
    figures = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
    drafts = year.runs / "reconstruct" / run / "drafts"
    exercises_root = year.runs / "exercises" / run / "exercises"
    exported = 0
    for certif in catalog["certifs"]:
        for module in certif["modules"]:
            for lesson in module["lessons"]:
                if (drafts / lesson["lesson_id"] / "lesson.md").is_file():
                    exported += export_lesson(
                        year,
                        lesson["lesson_id"],
                        certif,
                        module,
                        figures,
                        out,
                        drafts,
                        exercises_root,
                        allow_errors=True,  # comparison only: drafts are shown with their errors
                    )
    print(f"{year.id} comparison run {run}: {exported} lessons -> {out}")
    return 0


def main(year: Year) -> int:
    out = WEB / "content" / year.faculty_slug / year.id
    for sub in ("lessons", "exercises"):
        shutil.rmtree(out / sub, ignore_errors=True)
        (out / sub).mkdir(parents=True)
    catalog = json.loads((year.catalog / "catalog.json").read_text(encoding="utf-8"))
    manifest = year.data / "figures" / "manifest.json"
    figures = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
    exam_counts: dict[str, int] = {}
    for certif in catalog["certifs"]:
        for assessment in certif.get("assessments", []):
            for lesson_id in assessment.get("lesson_ids", []):
                exam_counts[lesson_id] = exam_counts.get(lesson_id, 0) + 1
    certifs = []
    exported = 0
    for certif in catalog["certifs"]:
        modules = []
        for module in certif["modules"]:
            lessons = sorted(
                (lesson_summary(lesson, year, exam_counts) for lesson in module["lessons"]),
                key=lambda lesson: lesson["order"],
            )
            for lesson in lessons:
                if lesson["available"]:
                    lesson["available"] = export_lesson(
                        year, lesson["id"], certif, module, figures, out
                    )
                    exported += lesson["available"]
            modules.append(
                {"slug": module["module_slug"], "title": module["module"], "lessons": lessons}
            )
        certifs.append(
            {
                "slug": certif["certif_slug"],
                "title": certif["certif"],
                "pole": certif["pole"],
                "modules": modules,
                "pastExams": len(certif.get("assessments", [])),
            }
        )
    write_json_atomic(
        out / "index.json",
        {
            "faculty": year.faculty_slug,
            "facultyLabel": year.faculty,
            "year": year.id,
            "yearLabel": year.label,
            "certifs": certifs,
        },
    )
    total = sum(len(m["lessons"]) for c in certifs for m in c["modules"])
    print(f"{year.id}: {len(certifs)} certifs, {total} lessons, {exported} exported -> {out}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", required=True, help="year id from library.toml")
    parser.add_argument("--compare-run", help="export a comparison run's drafts for /dev/comparer")
    arguments = parser.parse_args()
    selected = get_year(arguments.year)
    if arguments.compare_run:
        sys.exit(export_comparison(selected, arguments.compare_run))
    sys.exit(main(selected))
