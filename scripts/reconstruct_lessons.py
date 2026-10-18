"""Rebuild catalogued lessons from their faculty sources with Claude, through the Batches API.

Each lesson request carries the lesson's usable sources (sliced to their catalogued page ranges,
labelled S1..Sn by precedence) and, as a signal only, short past-exam excerpts linked to the lesson.
Reference books are left out unless --with-books. Responses are written as drafts in the run
directory, checked with scripts/validate_lesson.py, and only passing lessons are published to
data/<year>/lessons/<lesson_id>/. Failing drafts get at most one validation-guided repair request.

    plan     select lessons and estimate the cost (free, writes nothing)
    submit   send pending lessons (SPENDS MONEY; needs --yes)
    collect  fetch ended batches, validate drafts, publish passing lessons
    repair   send one repair request per failing draft (SPENDS MONEY; needs --yes)
    status   show the run state

Usage: python scripts/reconstruct_lessons.py --year dcem1 plan [--lessons ID,ID] [--limit N]
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_lesson import validate

from ingestion.claude_batch import (
    BatchRun,
    check_budget,
    custom_id,
    estimate_usd,
    load_api_key,
    message_text,
)
from ingestion.library import PROJECT_ROOT, Year, get_year
from ingestion.output import write_json_atomic, write_text_atomic

MODEL = "claude-opus-5-5"
EFFORT = "high"
MAX_TOKENS = 64000
ROLE_ORDER = [
    "official_slides",
    "official_polycopie",
    "tips",
    "student_summary",
    "tutorial",
    "reference_book",
]
ROLE_LABELS = {
    "official_slides": "Diapositives officielles",
    "official_polycopie": "Polycopié officiel",
    "tips": "Fiche de révision",
    "student_summary": "Résumé étudiant",
    "tutorial": "Support complémentaire",
    "reference_book": "Livre de référence",
}
EXAM_KINDS = {"exam_paper", "exam_with_answers", "qcm_bank", "qe_bank", "self_assessment"}
EXAM_MAX_LESSONS = 4  # only papers that target few lessons are informative for one lesson
EXAM_BUDGET = 20_000  # characters of exam excerpts per lesson
CHARS_PER_TOKEN = 2.3  # measured on French course text (step 0), for estimates only
SEPARATOR = re.compile(r"^===== (PAGE|SLIDE) (\d+) =====$", re.MULTILINE)
RANGE = re.compile(r"(\d+)(?:-(\d+))?")
POLICY = (
    "source-only: reorganize and rephrase retained source content; no outside facts; every "
    "content unit cites source pages; conflicts listed, never silently resolved"
)

SYSTEM = """Tu reconstruis un cours de médecine pour les étudiants de la Faculté de Médecine de \
Sfax, uniquement à partir des sources fournies. Le cours sera relu par un médecin avant \
publication ; ton travail est d'être fidèle aux sources et facile à réviser.

Règles de fond (impératives)
1. Sources uniquement : réorganise et reformule le contenu des sources. N'ajoute aucun fait \
médical extérieur, ne corrige rien, ne réinterprète aucune valeur. Si une information manque, ne \
la comble pas.
2. Priorité : diapositives officielles > polycopié officiel > fiches et résumés d'étudiants. Les \
résumés complètent ; un élément présent seulement dans un résumé reste, avec sa citation.
3. Citations : chaque paragraphe, chaque élément de liste et chaque ligne de tableau se termine \
par une ou plusieurs citations, par exemple [S1 p.12], [S2 p.30-31; S3 p.2] ou [S4 slide 5]. Les \
numéros sont ceux des séparateurs « ===== PAGE n ===== » et « ===== SLIDE n ===== » des sources \
(utilise « slide » pour les sources à SLIDE). Ne cite que des pages qui contiennent réellement \
l'information. Un validateur automatique rejette le cours entier si une seule ligne de contenu \
n'a pas de citation : la phrase qui introduit une liste, chaque élément de liste (même court, \
même dans une sous-liste) et chaque ligne de tableau portent leur propre citation, à la fin de la \
ligne. Un intitulé s'écrit comme titre (### ou ####), jamais comme ligne en gras isolée. Exemple :
La prise en charge comporte trois volets : [S2 p.4]
- le traitement symptomatique ; [S2 p.4]
- l'antibiothérapie adaptée au germe ; [S1 slide 12; S2 p.4]
- le traitement de la porte d'entrée. [S2 p.5]
4. Chiffres : tout nombre écrit dans le cours figure tel quel, avec la même unité, sur une page \
citée de cet élément. N'arrondis pas, ne convertis pas, ne calcule pas.
5. Désaccords entre sources : ne tranche jamais. Liste-les dans la section finale \
« ## Points à vérifier par le relecteur médical », avec les citations des deux côtés. Signale \
aussi là les contenus manifestement perdus (texte d'images non extrait, page illisible).

Forme
- Structure habituelle des cours de la faculté, dans cet ordre quand le sujet s'y prête : \
Objectifs (si la source les donne), Définition et généralités, Épidémiologie, Étiologies et \
facteurs de risque, Physiopathologie, Diagnostic (clinique, examens complémentaires, formes, \
diagnostic différentiel), Évolution et complications, Traitement, Prévention, Suivi. Pour un \
sujet qui n'est pas une maladie (vaccination, examen du nouveau-né, technique…), suis la \
structure de la source officielle.
- Clair et concis : titres et sous-titres, listes courtes, tableaux pour comparer (germes, \
critères, posologies), termes clés en **gras**. Pas de longs paragraphes, pas de redites.
- Rendement d'examen : des extraits d'examens passés peuvent être fournis. Ils ne sont \
jamais une source de contenu ni de citation ; ils indiquent seulement ce qui est interrogé. \
Ajoute « {examen} » à la fin du titre (## ou ###) de chaque section clairement interrogée par \
ces extraits. Ajoute « {plié} » à la fin du titre des sections secondaires rarement utiles à \
l'examen (historique, épidémiologie détaillée, données anecdotiques) : elles seront repliées \
par défaut, ne les supprime jamais.

Format de la réponse : uniquement le cours en Markdown, en français, sans commentaire.
---
lesson_id: <identifiant>
statut: brouillon — non relu par un médecin
sources: <rappel court de S1…Sn>
---

# <Titre>

> Cours reconstruit à partir des seules sources citées. Chaque élément renvoie à sa page source.

…sections…

## Points à vérifier par le relecteur médical

- … [citations]
(ou, s'il n'y a rien : « > Aucun désaccord relevé entre les sources. »)"""


def run_for(year: Year, repair: bool = False, name: str = "v1") -> BatchRun:
    """Runs named test-* are comparison runs: they keep validated drafts and never publish."""
    return BatchRun(year.runs / "reconstruct" / (f"{name}-repair" if repair else name))


def estimate_items(model: str, items: list[dict[str, Any]]) -> float:
    input_tokens = int(sum(item["input_characters"] for item in items) / CHARS_PER_TOKEN)
    # Measured on the step 0 test (Opus 5.5 / Sonnet 5.5, effort high): output, thinking
    # included, is about 0.6x the input tokens plus a few thousand per lesson.
    output_tokens = int(input_tokens * 0.6) + len(items) * 4000
    return estimate_usd(model, input_tokens, output_tokens)


def load_text(record: dict[str, Any]) -> str | None:
    if not record.get("text_relative_path"):
        return None
    path = PROJECT_ROOT / record["text_root"] / record["text_relative_path"]
    return path.read_text(encoding="utf-8") if path.is_file() else None


def slice_pages(text: str, locations: str | None) -> str:
    """Keep the separator-delimited pages listed in `locations` (all pages when None)."""
    matches = list(SEPARATOR.finditer(text))
    if not matches:
        return text
    wanted: set[int] | None = None
    if locations:
        wanted = set()
        for start, end in RANGE.findall(locations):
            wanted.update(range(int(start), int(end or start) + 1))
    parts = []
    for index, match in enumerate(matches):
        if wanted is None or int(match.group(2)) in wanted:
            stop = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            parts.append(text[match.start() : stop].rstrip())
    return "\n\n".join(parts)


def source_label(source: dict[str, Any]) -> str:
    label = ROLE_LABELS[source["role"]]
    if source.get("author"):
        label += f" — {source['author']}"
    label += f" — « {Path(source['path']).stem} »"
    if source.get("locations"):
        label += f", {source['locations'].lower().replace('page ', 'p. ')}"
    return label


def lesson_inputs(
    lesson: dict[str, Any], inventory: dict[str, dict[str, Any]], with_books: bool
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Ordered S1..Sn sources with their sliced text, plus the sources left out and why."""
    chosen: list[dict[str, Any]] = []
    left_out = []
    for source in lesson["sources"]:
        if source["role"] == "reference_book" and not with_books:
            left_out.append({"path": source["path"], "reason": "reference book (chatbot only)"})
        elif not source["usable_for_reconstruction"]:
            left_out.append({"path": source["path"], "reason": source.get("notes") or "unusable"})
        else:
            chosen.append(source)
    chosen.sort(key=lambda source: ROLE_ORDER.index(source["role"]))
    sources = {}
    for number, source in enumerate(chosen, start=1):
        record = inventory[source["path"]]
        text = load_text(record)
        if text is None:
            left_out.append({"path": source["path"], "reason": "no exported text"})
            continue
        sources[f"S{number}"] = {
            "path": source["path"],
            "role": source["role"],
            "source_sha256": record["source_sha256"],
            "text_root": record["text_root"],
            "text_relative_path": record["text_relative_path"],
            "locations": source.get("locations"),
            "label": source_label(source),
            "text": slice_pages(text, source.get("locations")),
        }
    return sources, left_out


def exam_excerpts(
    lesson_id: str, assessments: list[dict[str, Any]], inventory: dict[str, dict[str, Any]]
) -> str:
    excerpts = []
    budget = EXAM_BUDGET
    for assessment in assessments:
        if (
            lesson_id not in assessment.get("lesson_ids", [])
            or len(assessment["lesson_ids"]) > EXAM_MAX_LESSONS
            or assessment["kind"] not in EXAM_KINDS
        ):
            continue
        text = load_text(inventory[assessment["path"]])
        if not text or budget <= 0:
            continue
        body = SEPARATOR.split(text, maxsplit=1)
        body_text = text[text.find("=====") :] if len(body) > 1 else text
        excerpt = body_text[: min(8000, budget)]
        budget -= len(excerpt)
        session = assessment.get("session") or Path(assessment["path"]).stem
        excerpts.append(f'<examen session="{session}">\n{excerpt}\n</examen>')
    return "\n\n".join(excerpts)


def catalog_lessons(year: Year) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    catalog = json.loads((year.catalog / "catalog.json").read_text(encoding="utf-8"))
    return [
        (certif, module, lesson)
        for certif in catalog["certifs"]
        for module in certif["modules"]
        for lesson in module["lessons"]
    ]


def select(year: Year, patterns: list[str] | None, rebuild: bool = False) -> list[dict[str, Any]]:
    inventory = {
        r["source_relative_path"]: r
        for r in json.loads((year.catalog / "inventory.json").read_text())["records"]
    }
    assessments = [
        a
        for certif in json.loads((year.catalog / "catalog.json").read_text())["certifs"]
        for a in certif.get("assessments", [])
    ]
    items = []
    for certif, module, lesson in catalog_lessons(year):
        if patterns and not any(fnmatch.fnmatch(lesson["lesson_id"], p) for p in patterns):
            continue
        existing = year.lessons / lesson["lesson_id"] / "lesson.json"
        if existing.is_file():
            metadata = json.loads(existing.read_text(encoding="utf-8"))
            if metadata.get("medical_review") or metadata.get("status") != "draft_unreviewed":
                continue  # reviewed artifacts are never overwritten
            if not rebuild:
                continue  # validated lessons are rebuilt only on an explicit, scoped --rebuild
        items.append(
            {
                "lesson_id": lesson["lesson_id"],
                "title": lesson["title"],
                "aliases": lesson.get("aliases", []),
                "certif": certif["certif"],
                "certif_slug": certif["certif_slug"],
                "module": module["module"],
                "_lesson": lesson,
                "_inventory": inventory,
                "_assessments": assessments,
            }
        )
    return items


def prompt(item: dict[str, Any], with_books: bool) -> tuple[str, dict[str, Any], list[Any]]:
    sources, left_out = lesson_inputs(item["_lesson"], item["_inventory"], with_books)
    exams = exam_excerpts(item["lesson_id"], item["_assessments"], item["_inventory"])
    listing = "\n".join(f"- {key} : {source['label']}" for key, source in sources.items())
    blocks = "\n\n".join(
        f'<source id="{key}" role="{source["role"]}">\n{source["text"]}\n</source>'
        for key, source in sources.items()
    )
    aliases = f" (aussi : {', '.join(item['aliases'])})" if item["aliases"] else ""
    text = (
        f"Leçon : « {item['title']} »{aliases}\nlesson_id : {item['lesson_id']}\n"
        f"Certificat : {item['certif']} — module {item['module']}\n\nSources :\n{listing}\n\n"
        f"{blocks}\n\n"
        + (f"<examens_passes>\n{exams}\n</examens_passes>\n\n" if exams else "")
        + f"Reconstruis le cours « {item['title']} »."
    )
    return text, sources, left_out


def planned(item: dict[str, Any], with_books: bool) -> dict[str, Any]:
    text, sources, _left_out = prompt(item, with_books)
    key = item["lesson_id"] + "|" + "|".join(s["source_sha256"] for s in sources.values())
    return {
        "custom_id": custom_id("r", key),
        "lesson_id": item["lesson_id"],
        "with_books": with_books,
        "input_characters": len(text) + len(SYSTEM),
        "sources": len(sources),
    }


def request_params(model: str, user_text: str) -> dict[str, Any]:
    return {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "output_config": {"effort": EFFORT},
        "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": user_text}],
    }


def by_id(year: Year) -> dict[str, dict[str, Any]]:
    return {item["lesson_id"]: item for item in select(year, None, rebuild=True)}


def write_lesson(
    directory: Path, item: dict[str, Any], markdown: str, record: dict[str, Any], run: str
) -> dict[str, Any]:
    _text, sources, left_out = prompt(item, item.get("_with_books", False))
    metadata = {
        "schema_version": "0.1.0",
        "lesson_id": item["lesson_id"],
        "title": item["title"],
        "certif_slug": item["certif_slug"],
        "module": item["module"],
        "status": "draft_unreviewed",
        "medical_review": None,
        "reconstruction": {
            "method": "claude-batch",
            "model": record["model"],
            "run": run,
            "custom_id": record["custom_id"],
            "date": datetime.now(timezone.utc).date().isoformat(),
            "policy": POLICY,
            "precedence": " > ".join(ROLE_ORDER[:4]),
        },
        "excluded_sources": left_out,
        "sources": {
            key: {name: value for name, value in source.items() if name != "text"}
            for key, source in sources.items()
        },
    }
    write_json_atomic(directory / "lesson.json", metadata)
    write_text_atomic(directory / "lesson.md", markdown.strip() + "\n")
    return metadata


def collect(year: Year, client: Any, repair: bool, name: str) -> int:
    run = run_for(year, repair, name)
    publish = not name.startswith("test-")
    print(run.collect(client))
    items = by_id(year)
    planned_items = {item["custom_id"]: item for item in run.items()}
    drafts = run.root / "drafts"
    published = failed = 0
    for custom, record in run.latest().items():
        if record["type"] != "succeeded" or record["stop_reason"] != "end_turn":
            continue
        lesson_id = planned_items[custom]["lesson_id"]
        target = year.lessons / lesson_id
        published_from = (
            json.loads((target / "lesson.json").read_text(encoding="utf-8")).get(
                "reconstruction", {}
            )
            if (target / "lesson.json").is_file()
            else {}
        )
        if publish and (published_from.get("custom_id"), published_from.get("run")) == (
            custom,
            run.root.name,
        ):
            continue  # already published from this result
        draft = drafts / lesson_id
        item = items[lesson_id] | {"_with_books": planned_items[custom]["with_books"]}
        metadata = write_lesson(draft, item, message_text(record), record, run.root.name)
        report = validate(draft)
        metadata["validation"] = {
            "units": report.units,
            "cited": report.cited,
            "errors": report.errors,
            "student_only": len(report.student_only),
        }
        write_json_atomic(draft / "lesson.json", metadata)
        if report.errors:
            failed += 1
            continue
        if not publish:
            continue  # comparison runs keep validated drafts only
        write_lesson(target, item, message_text(record), record, run.root.name)
        write_json_atomic(target / "lesson.json", metadata)
        published += 1
    passed = len(list(drafts.glob("*/lesson.json"))) - failed if not publish else published
    print(
        f"{'published' if publish else 'validated drafts (not published)'} {passed}; "
        f"{failed} drafts failed validation ({drafts})"
    )
    return 0


def repair_items(year: Year, name: str) -> list[dict[str, Any]]:
    """One repair item per failing draft of a run that has no published lesson."""
    drafts = run_for(year, name=name).root / "drafts"
    items = []
    for path in sorted(drafts.glob("*/lesson.json")):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        errors = metadata.get("validation", {}).get("errors")
        published = year.lessons / metadata["lesson_id"] / "lesson.json"
        if errors and (name.startswith("test-") or not published.is_file()):
            draft_chars = len((path.parent / "lesson.md").read_text(encoding="utf-8"))
            items.append(
                {
                    "custom_id": custom_id("rr", metadata["reconstruction"]["custom_id"]),
                    "lesson_id": metadata["lesson_id"],
                    "with_books": False,
                    "draft": str(path.parent),
                    "input_characters": draft_chars * 3,  # sources + draft, for the estimate
                }
            )
    return items


def build(year: Year, model: str, repair: bool) -> Any:
    items = by_id(year)

    def params(planned_item: dict[str, Any]) -> dict[str, Any]:
        item = items[planned_item["lesson_id"]]
        text, _sources, _left_out = prompt(item, planned_item["with_books"])
        if repair:
            draft = Path(planned_item["draft"])
            errors = json.loads((draft / "lesson.json").read_text())["validation"]["errors"]
            text += (
                "\n\nVoici ta version précédente, refusée par le validateur automatique :\n"
                f"<brouillon>\n{(draft / 'lesson.md').read_text(encoding='utf-8')}\n</brouillon>\n"
                "Erreurs du validateur :\n"
                + "\n".join(f"- {error}" for error in errors[:200])
                + "\n\nCorrige ces erreurs (citation manquante, page inexistante, nombre absent "
                "des pages citées : cite la bonne page ou retire le nombre) et renvoie le cours "
                "complet corrigé, mêmes règles."
            )
        return request_params(model, text)

    return params


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", required=True, help="year id from library.toml")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--run", default="v1", help="run name; test-* runs never publish")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "submit"):
        command = sub.add_parser(name)
        command.add_argument("--lessons", help="comma-separated lesson ids or glob patterns")
        command.add_argument("--limit", type=int, help="at most N lessons")
        command.add_argument("--with-books", action="store_true", help="include reference books")
        command.add_argument(
            "--rebuild", action="store_true", help="also rebuild the selected published lessons"
        )
        if name == "submit":
            command.add_argument("--yes", action="store_true", help="confirm spending money")
            command.add_argument("--max-usd", type=float, help="refuse above this estimate")
    repair_parser = sub.add_parser("repair")
    repair_parser.add_argument("--yes", action="store_true", help="confirm spending money")
    repair_parser.add_argument("--max-usd", type=float, help="refuse above this estimate")
    collect_parser = sub.add_parser("collect")
    collect_parser.add_argument("--repair", action="store_true", help="collect the repair run")
    sub.add_parser("status")
    args = parser.parse_args()
    year = get_year(args.year)

    if args.command in {"plan", "submit"}:
        patterns = args.lessons.split(",") if args.lessons else None
        if args.rebuild and not patterns:
            raise SystemExit("--rebuild must be scoped with --lessons.")
        selected = select(year, patterns, args.rebuild)
        items = [planned(item, args.with_books) for item in selected]
        items = items[: args.limit] if args.limit else items
        input_tokens = int(sum(item["input_characters"] for item in items) / CHARS_PER_TOKEN)
        cost = estimate_items(args.model, items)
        print(
            f"{len(items)} lessons, ~{input_tokens:,} input tokens; estimate ({args.model}, "
            f"batch, effort {EFFORT}): ~${cost:.2f}"
        )
        empty = [item["lesson_id"] for item in items if item["sources"] == 0]
        if empty:
            print(f"{len(empty)} lessons have no usable source and will be skipped")
        items = [item for item in items if item["sources"] > 0]
        if args.command == "plan":
            return 0
        if not args.yes:
            raise SystemExit("submit spends money: re-run with --yes after the owner's go.")
        run = run_for(year, name=args.run)
        run.plan(items)
        check_budget(estimate_items(args.model, run.pending()), args.max_usd)
        batches = run.submit(client(), build(year, args.model, False))
        print(f"submitted {len(batches)} batch(es)")
        print(json.dumps(run.summary(), indent=2))
    elif args.command == "repair":
        if not args.yes:
            raise SystemExit("repair spends money: re-run with --yes after the owner's go.")
        run = run_for(year, repair=True, name=args.run)
        run.plan(repair_items(year, args.run))
        check_budget(estimate_items(args.model, run.pending()), args.max_usd)
        batches = run.submit(client(), build(year, args.model, True))
        print(f"submitted {len(batches)} repair batch(es)")
        print(json.dumps(run.summary(), indent=2))
    elif args.command == "collect":
        return collect(year, client(), args.repair, args.run)
    else:
        for repair in (False, True):
            print(json.dumps(run_for(year, repair, args.run).summary(), indent=2))
    return 0


def client() -> Any:
    if not load_api_key():
        raise SystemExit("ANTHROPIC_API_KEY is not set (put it in .env).")
    import anthropic

    return anthropic.Anthropic()


if __name__ == "__main__":
    sys.exit(main())
