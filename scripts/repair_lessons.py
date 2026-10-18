"""Repair the few failing units of lesson drafts, instead of regenerating whole lessons.

For each draft of a reconstruction run that failed validation, one small request carries only the
failing units (a missing citation, a number absent from the cited pages, a bad page) with their
neighbouring lines and the text of the source pages cited around them. Claude returns a
replacement for each failing unit (structured output); the fixes are applied to a copy, the lesson
is validated again, and it is published when it passes (runs named test-* never publish). The
draft before repair is kept as lesson.before-repair.md. Bounded: one repair attempt per draft.

    plan     list failing drafts and estimate the cost (free)
    submit   send the repair requests (SPENDS MONEY; needs --yes and --max-usd)
    collect  apply returned fixes, validate, publish passing lessons

Usage: python scripts/repair_lessons.py --year dcem2 --run v2 plan
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from validate_lesson import CITATION, load_pages, validate

from ingestion.claude_batch import (
    BatchRun,
    check_budget,
    custom_id,
    estimate_usd,
    load_api_key,
    message_text,
)
from ingestion.library import PROJECT_ROOT, Year, get_year

MODEL = "claude-opus-5-5"
CONTEXT_LINES = 4
PAGE_BUDGET = 40_000  # characters of cited source pages per lesson request
ERROR = re.compile(r"^line (\d+): (.*)$")

SYSTEM = """Tu corriges quelques lignes d'un cours de médecine reconstruit à partir de sources. \
Un validateur automatique a rejeté ces lignes. Pour chaque ligne, renvoie une version corrigée.

Règles impératives
- N'ajoute aucune information absente des pages sources fournies ; garde le sens de la ligne.
- Chaque ligne corrigée se termine par une ou plusieurs citations [S1 p.12], [S2 p.3; S3 slide 4] \
qui renvoient à des pages fournies contenant réellement l'information.
- Tout nombre de la ligne doit figurer tel quel, avec la même unité, sur une page citée. Si un \
nombre n'apparaît sur aucune page fournie, retire-le (ou la partie de phrase qui le porte).
- Une ligne qui n'est qu'un intitulé (sans information) devient un titre Markdown (### ...).
- Garde la forme Markdown de la ligne (puce « - », ligne de tableau « | … | », paragraphe).
- Si la ligne ne peut pas être justifiée par les pages fournies, renvoie une chaîne vide : elle \
sera supprimée.
Réponds uniquement avec l'objet JSON demandé."""

SCHEMA = {
    "type": "object",
    "properties": {
        "fixes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"line": {"type": "integer"}, "text": {"type": "string"}},
                "required": ["line", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["fixes"],
    "additionalProperties": False,
}


def run_for(year: Year, run: str) -> BatchRun:
    return BatchRun(year.runs / "reconstruct" / f"{run}-linefix")


def drafts_dir(year: Year, run: str) -> Path:
    return year.runs / "reconstruct" / run / "drafts"


def failing_units(draft: Path) -> list[tuple[int, int, str]]:
    """(first line, last line, error) per failing unit, 1-based lines of lesson.md."""
    metadata = json.loads((draft / "lesson.json").read_text(encoding="utf-8"))
    lines = (draft / "lesson.md").read_text(encoding="utf-8").splitlines()
    units = []
    for error in metadata.get("validation", {}).get("errors", []):
        match = ERROR.match(error)
        if not match:
            continue
        first = int(match.group(1))
        # Locate the unit by its text when the reported line is off by one or two.
        excerpt = match.group(2).split(": ", 1)[-1][:40].strip()
        for candidate in (first, first - 1, first + 1, first - 2, first + 2):
            if 1 <= candidate <= len(lines) and excerpt[:25] in lines[candidate - 1]:
                first = candidate
                break
        last = first
        while (
            last < len(lines)
            and lines[last].strip()
            and not lines[last].lstrip().startswith(("-", "|", "#", "*"))
            and not lines[first - 1].lstrip().startswith(("-", "|"))
        ):
            last += 1  # a paragraph continues until the next blank line or block
        units.append((first, last, match.group(2)))
    return units


def request_text(draft: Path) -> str:
    metadata = json.loads((draft / "lesson.json").read_text(encoding="utf-8"))
    lines = (draft / "lesson.md").read_text(encoding="utf-8").splitlines()
    units = failing_units(draft)
    cited: set[tuple[str, int]] = set()
    blocks = []
    for first, last, error in units:
        start, end = max(1, first - CONTEXT_LINES), min(len(lines), last + CONTEXT_LINES)
        context = "\n".join(lines[start - 1 : end])
        for key, _kind, a, b in CITATION.findall(context):
            for page in range(int(a), int(b or a) + 1):
                cited.add((key, page))
        target = "\n".join(lines[first - 1 : last])
        blocks.append(
            f'<ligne numero="{first}">\nErreur : {error}\nLigne à corriger :\n{target}\n'
            f"Contexte :\n{context}\n</ligne>"
        )
    pages_text, budget = [], PAGE_BUDGET
    for key, page in sorted(cited):
        source = metadata["sources"].get(key)
        if not source or budget <= 0:
            continue
        pages = load_pages(PROJECT_ROOT / source["text_root"] / source["text_relative_path"])
        if page in pages:
            excerpt = pages[page][: min(4000, budget)]
            budget -= len(excerpt)
            pages_text.append(f'<page source="{key}" numero="{page}">\n{excerpt}\n</page>')
    return (
        f"Cours : {metadata['title']}\n\nPages sources citées autour des lignes :\n"
        + "\n\n".join(pages_text)
        + "\n\nLignes rejetées :\n"
        + "\n\n".join(blocks)
        + '\n\nRenvoie {"fixes": [{"line": <numero>, "text": "<ligne corrigée>"}]}.'
    )


def candidates(year: Year, run: str) -> list[Path]:
    selected = []
    for path in sorted(drafts_dir(year, run).glob("*/lesson.json")):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        published = (year.lessons / metadata["lesson_id"] / "lesson.md").is_file()
        if metadata.get("validation", {}).get("errors") and (
            run.startswith("test-") or not published
        ):
            selected.append(path.parent)
    return selected


def estimate(drafts: list[Path], model: str) -> float:
    characters = sum(len(request_text(draft)) for draft in drafts)
    return estimate_usd(model, int(characters / 2.3) + 800 * len(drafts), 2500 * len(drafts))


def apply_fixes(draft: Path, fixes: list[dict[str, Any]]) -> None:
    lesson = draft / "lesson.md"
    backup = draft / "lesson.before-repair.md"
    if not backup.is_file():
        shutil.copyfile(lesson, backup)
    lines = backup.read_text(encoding="utf-8").splitlines()
    spans = {first: last for first, last, _error in failing_units_from(backup, draft)}
    for fix in sorted(fixes, key=lambda item: -item["line"]):
        first = fix["line"]
        if first not in spans:
            continue
        lines[first - 1 : spans[first]] = [fix["text"]] if fix["text"].strip() else []
    lesson.write_text("\n".join(lines) + "\n", encoding="utf-8")


def failing_units_from(markdown: Path, draft: Path) -> list[tuple[int, int, str]]:
    """Failing units computed against the pre-repair markdown (the errors refer to it)."""
    current = draft / "lesson.md"
    if markdown == current:
        return failing_units(draft)
    saved = current.read_text(encoding="utf-8")
    try:
        current.write_text(markdown.read_text(encoding="utf-8"), encoding="utf-8")
        return failing_units(draft)
    finally:
        current.write_text(saved, encoding="utf-8")


def collect(year: Year, run: str) -> int:
    batch = run_for(year, run)
    print(batch.collect(client()))
    planned = {item["custom_id"]: item for item in batch.items()}
    fixed = still = published = 0
    for custom, record in batch.latest().items():
        if record["type"] != "succeeded" or record["stop_reason"] != "end_turn":
            continue
        draft = Path(planned[custom]["draft"])
        if (draft / "lesson.before-repair.md").is_file():
            continue  # already applied
        apply_fixes(draft, json.loads(message_text(record))["fixes"])
        report = validate(draft)
        metadata = json.loads((draft / "lesson.json").read_text(encoding="utf-8"))
        metadata["validation"] = {
            "units": report.units,
            "cited": report.cited,
            "errors": report.errors,
            "student_only": len(report.student_only),
            "repaired": True,
        }
        (draft / "lesson.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if report.errors:
            still += 1
            print(f"still failing {metadata['lesson_id']}: {report.errors[:3]}")
            continue
        fixed += 1
        if not run.startswith("test-"):
            target = year.lessons / metadata["lesson_id"]
            target.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(draft / "lesson.md", target / "lesson.md")
            shutil.copyfile(draft / "lesson.json", target / "lesson.json")
            published += 1
    print(f"repaired {fixed} drafts ({published} published); {still} still failing")
    return 0


def client() -> Any:
    if not load_api_key():
        raise SystemExit("ANTHROPIC_API_KEY is not set (put it in .env).")
    import anthropic

    return anthropic.Anthropic()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", required=True)
    parser.add_argument("--run", required=True, help="reconstruction run whose drafts to repair")
    parser.add_argument("--model", default=MODEL)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    submit = sub.add_parser("submit")
    submit.add_argument("--yes", action="store_true")
    submit.add_argument("--max-usd", type=float)
    sub.add_parser("collect")
    args = parser.parse_args()
    year = get_year(args.year)
    drafts = candidates(year, args.run)
    if args.command == "collect":
        return collect(year, args.run)
    cost = estimate(drafts, args.model)
    for draft in drafts:
        print(f"  {draft.name}: {len(failing_units(draft))} failing units")
    print(f"{len(drafts)} drafts to repair; estimate ({args.model}, batch): ~${cost:.2f}")
    if args.command == "plan":
        return 0
    if not args.yes:
        raise SystemExit("submit spends money: re-run with --yes after the owner's go.")
    batch = run_for(year, args.run)
    batch.plan(
        [
            {
                "custom_id": custom_id("lf", f"{draft}|{(draft / 'lesson.md').read_text()}"),
                "draft": str(draft),
            }
            for draft in drafts
        ]
    )
    pending = [Path(item["draft"]) for item in batch.pending()]
    check_budget(estimate(pending, args.model), args.max_usd)

    def params(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": args.model,
            "max_tokens": 16000,
            "output_config": {
                "effort": "medium",
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
            "system": SYSTEM,
            "messages": [{"role": "user", "content": request_text(Path(item["draft"]))}],
        }

    print(f"submitted {batch.submit(client(), params)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
