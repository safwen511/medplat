"""Merge per-certif classification files into one validated course catalog.

Inputs: data/<year>/catalog/inventory.json and data/<year>/catalog/certifs/*.json (see
docs/catalog-classification.md). Outputs: data/<year>/catalog/catalog.json and catalog-summary.md.
Exits nonzero when validation fails. Usage: python scripts/merge_catalog.py --year dcem1
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from ingestion.library import get_year

SOURCE_ROLES = {
    "official_slides",
    "official_polycopie",
    "student_summary",
    "tips",
    "tutorial",
    "reference_book",
}
ASSESSMENT_KINDS = {
    "exam_paper",
    "exam_with_answers",
    "qcm_bank",
    "qe_bank",
    "clinical_cases",
    "self_assessment",
}
QUALITIES = {"good", "noisy", "unusable", "empty"}


def validate(certifs: list[dict], inventory: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    seen: Counter[str] = Counter()
    lesson_ids: Counter[str] = Counter()
    for certif in certifs:
        slug = certif.get("certif_slug", "?")
        for module in certif.get("modules", []):
            for lesson in module.get("lessons", []):
                lesson_id = lesson.get("lesson_id", "")
                lesson_ids[lesson_id] += 1
                if not lesson_id.startswith(f"{slug}."):
                    errors.append(f"{lesson_id}: lesson_id must start with '{slug}.'")
                if not lesson.get("title"):
                    errors.append(f"{lesson_id}: missing title")
                for source in lesson.get("sources", []):
                    seen[source.get("path", "")] += 1
                    if source.get("role") not in SOURCE_ROLES:
                        errors.append(f"{lesson_id}: bad role {source.get('role')!r}")
                    if source.get("text_quality") not in QUALITIES:
                        errors.append(
                            f"{lesson_id}: bad text_quality {source.get('text_quality')!r}"
                        )
        for assessment in certif.get("assessments", []):
            seen[assessment.get("path", "")] += 1
            if assessment.get("kind") not in ASSESSMENT_KINDS:
                errors.append(f"{slug}: bad assessment kind {assessment.get('kind')!r}")
        for excluded in certif.get("excluded", []):
            seen[excluded.get("path", "")] += 1

    errors += [f"duplicate lesson_id {lesson_id}" for lesson_id, n in lesson_ids.items() if n > 1]
    errors += [f"unknown path {path}" for path in seen if path not in inventory]
    errors += [f"unclassified path {path}" for path in inventory if path not in seen]
    all_lessons = set(lesson_ids)
    for certif in certifs:
        for assessment in certif.get("assessments", []):
            errors += [
                f"assessment {assessment['path']} references unknown lesson {lesson_id}"
                for lesson_id in assessment.get("lesson_ids", [])
                if lesson_id not in all_lessons
            ]
    return errors


def summary(certifs: list[dict]) -> str:
    lines = ["# Course catalog summary", ""]
    for certif in certifs:
        lessons = [lesson for module in certif["modules"] for lesson in module["lessons"]]
        lines.append(
            f"## {certif['pole']} · {certif['certif']} — {len(certif['modules'])} modules, "
            f"{len(lessons)} lessons, {len(certif.get('assessments', []))} assessments, "
            f"{len(certif.get('excluded', []))} excluded"
        )
        for module in certif["modules"]:
            lines.append(f"\n### {module['module']}\n")
            for lesson in sorted(
                module["lessons"],
                key=lambda item: (item.get("order") is None, item.get("order") or 0),
            ):
                roles = Counter(source["role"] for source in lesson["sources"])
                usable = sum(
                    source.get("usable_for_reconstruction", False) for source in lesson["sources"]
                )
                order = lesson.get("order")
                role_text = ", ".join(f"{count} {role}" for role, count in sorted(roles.items()))
                lines.append(
                    f"- {order if order is not None else '–'}. {lesson['title']} "
                    f"({role_text}; {usable} usable)"
                )
        if certif.get("open_questions"):
            lines.append("\n**Open questions**\n")
            lines += [f"- {question}" for question in certif["open_questions"]]
        lines.append("")
    return "\n".join(lines)


def main(catalog_root: Path) -> int:
    records = json.loads((catalog_root / "inventory.json").read_text(encoding="utf-8"))["records"]
    inventory = {record["source_relative_path"]: record for record in records}
    certifs = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((catalog_root / "certifs").glob("*.json"))
    ]
    errors = validate(certifs, inventory)
    if errors:
        print(f"{len(errors)} validation errors:")
        for error in errors[:200]:
            print(f"  - {error}")
        return 1

    for certif in certifs:
        for module in certif["modules"]:
            for lesson in module["lessons"]:
                for source in lesson["sources"]:
                    record = inventory[source["path"]]
                    source["text_root"] = record["text_root"]
                    source["text_relative_path"] = record["text_relative_path"]
                    source["source_sha256"] = record["source_sha256"]
    catalog = {"schema_version": "0.1.0", "certifs": certifs}
    (catalog_root / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (catalog_root / "catalog-summary.md").write_text(summary(certifs), encoding="utf-8")
    lessons = sum(len(module["lessons"]) for certif in certifs for module in certif["modules"])
    print(f"OK: {len(certifs)} certifs, {lessons} lessons, {len(inventory)} files classified")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", required=True, help="year id from library.toml")
    sys.exit(main(get_year(parser.parse_args().year).catalog))
