"""Run one production wave for a pole: rebuild lessons, repair, generate questions, export.

A wave picks, in every certif of the pole, the next N lessons not published yet (lessons with a
usable official source first, then most past exams, then course order), and chains the stages:

    reconstruct_lessons.py --run v2 submit  → wait → collect (publishes passing lessons)
    repair_lessons.py      --run v2 submit  → wait → collect (publishes repaired lessons)
    generate_exercises.py           submit  → wait → collect (data/<year>/exercises)
    export_web_content.py

Every paid step is capped by what is left of --max-usd for the whole wave (real spend is read from
the run records of the wave's own lessons). Resumable: re-running the same command continues
where it stopped.
Usage: python scripts/wave.py --year dcem1 --pole A --per-certif 1 --max-usd 3
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from ingestion.claude_batch import BatchRun, total_spent
from ingestion.library import PROJECT_ROOT, Year, get_year

PYTHON = str(PROJECT_ROOT / ".venv" / "bin" / "python")
OFFICIAL = {"official_slides", "official_polycopie"}
RUN = "v2"
POLL_SECONDS = 120


def pick(year: Year, pole: str, per_certif: int) -> list[str]:
    catalog = json.loads((year.catalog / "catalog.json").read_text(encoding="utf-8"))
    exams: dict[str, int] = {}
    for certif in catalog["certifs"]:
        for assessment in certif.get("assessments", []):
            for lesson_id in assessment.get("lesson_ids", []):
                exams[lesson_id] = exams.get(lesson_id, 0) + 1
    drafts = year.runs / "reconstruct" / RUN / "drafts"
    chosen = []
    for certif in catalog["certifs"]:
        if certif["pole"] != pole:
            continue
        ranked = []
        for module in certif["modules"]:
            for lesson in module["lessons"]:
                lesson_id = lesson["lesson_id"]
                usable = [s for s in lesson["sources"] if s["usable_for_reconstruction"]]
                if not usable or (year.lessons / lesson_id / "lesson.md").is_file():
                    continue
                if (drafts / lesson_id / "lesson.before-repair.md").is_file():
                    continue  # rebuilt and repaired once already: needs a human look
                official = any(source["role"] in OFFICIAL for source in usable)
                ranked.append(
                    (not official, -exams.get(lesson_id, 0), lesson.get("order") or 999, lesson_id)
                )
        chosen += [lesson_id for *_rest, lesson_id in sorted(ranked)[:per_certif]]
    return chosen


def spent_on(year: Year, lessons: set[str]) -> float:
    """Real cost recorded so far for these lessons: rebuild, line repair and questions."""
    total = 0.0
    for name, key in (
        (f"reconstruct/{RUN}", "lesson_id"),
        (f"reconstruct/{RUN}-linefix", "draft"),
        ("exercises/v1", "lesson_id"),
    ):
        batch_run = BatchRun(year.runs / name)
        owner = {
            item["custom_id"]: Path(item[key]).name if key == "draft" else item[key]
            for item in batch_run.items()
        }
        total += sum(
            record.get("cost_usd") or 0.0
            for record in batch_run.results()
            if owner.get(record["custom_id"]) in lessons
        )
    return total


def run(args: list[str], cap: float | None = None) -> None:
    command = [PYTHON, *args]
    if cap is not None:
        command += ["--yes", "--max-usd", f"{cap:.2f}"]
    print("$", " ".join(command[1:]), flush=True)
    subprocess.run(command, check=True, cwd=PROJECT_ROOT)


def wait(batch_run: BatchRun, collect: list[str]) -> None:
    """Collect (free) until nothing of this run is in flight."""
    while True:
        run(collect)
        if not batch_run.in_flight():
            return
        time.sleep(POLL_SECONDS)


def main(year: Year, pole: str, per_certif: int, max_usd: float, lessons: list[str] | None) -> int:
    selected = lessons or pick(year, pole, per_certif)
    left = lambda: max_usd - spent_on(year, set(selected))  # noqa: E731
    print(f"wave {year.id} pôle {pole}: {len(selected)} lessons, budget ${max_usd:.2f}")
    if not selected:
        return 0
    ids = ",".join(selected)
    y = ["--year", year.id]

    run(["scripts/reconstruct_lessons.py", *y, "--run", RUN, "submit", "--lessons", ids], left())
    wait(
        BatchRun(year.runs / "reconstruct" / RUN),
        ["scripts/reconstruct_lessons.py", *y, "--run", RUN, "collect"],
    )

    repair = BatchRun(year.runs / "reconstruct" / f"{RUN}-linefix")
    run(["scripts/repair_lessons.py", *y, "--run", RUN, "submit"], left())
    if repair.in_flight():
        wait(repair, ["scripts/repair_lessons.py", *y, "--run", RUN, "collect"])

    published = [
        lesson_id for lesson_id in selected if (year.lessons / lesson_id / "lesson.md").is_file()
    ]
    if published:
        run(
            ["scripts/generate_exercises.py", *y, "submit", "--lessons", ",".join(published)],
            left(),
        )
        wait(
            BatchRun(year.runs / "exercises" / "v1"),
            ["scripts/generate_exercises.py", *y, "collect"],
        )
    run(["scripts/export_web_content.py", *y])
    missing = sorted(set(selected) - set(published))
    print(
        f"wave done: {len(published)}/{len(selected)} lessons published with questions; "
        f"spent ${spent_on(year, set(selected)):.2f} (all runs: ${total_spent():.2f})"
        + (f"; needs a look: {missing}" if missing else "")
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", required=True)
    parser.add_argument("--pole", required=True)
    parser.add_argument("--per-certif", type=int, default=1)
    parser.add_argument("--max-usd", type=float, required=True, help="budget for the whole wave")
    parser.add_argument("--lessons", help="explicit comma-separated lesson ids instead of picking")
    arguments = parser.parse_args()
    sys.exit(
        main(
            get_year(arguments.year),
            arguments.pole,
            arguments.per_certif,
            arguments.max_usd,
            arguments.lessons.split(",") if arguments.lessons else None,
        )
    )
