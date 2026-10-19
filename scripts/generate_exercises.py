"""Generate exercises for validated lessons with Claude (Batches API, structured outputs).

About 10 items per lesson, weighted toward sections marked {examen}: 3 QCM, 2 QRM, 2 vrai/faux,
1 texte à trous, 1 association/ordre/catégories, 1 numérique (or another QCM). Every item has a
3-step hint ladder and a cited explanation. Each item is checked locally before it is kept:
shape (answers refer to real options, hint ladder complete), citations resolve to lesson sources
and existing pages, and every number (stem, options including distractors, answers, explanation)
occurs on a cited page. Rejected items are kept in the output file for audit, never shown.
Image-based items come later, after the figure labelling pass.

    plan     select lessons and estimate the cost (free)
    submit   send pending lessons (SPENDS MONEY; needs --yes)
    collect  fetch results, validate items, write data/<year>/exercises/<lesson_id>.json
    status   show the run state

Usage: python scripts/generate_exercises.py --year dcem1 plan [--lessons GLOB] [--limit N]
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

from validate_lesson import CITATION, claimed_numbers, load_pages, normalize, numbers, validate

from ingestion.claude_batch import (
    BatchRun,
    check_budget,
    custom_id,
    estimate_usd,
    load_api_key,
    message_text,
)
from ingestion.library import PROJECT_ROOT, Year, get_year
from ingestion.output import write_json_atomic

MODEL = "claude-opus-5-5"
EFFORT = "medium"
CHARS_PER_TOKEN = 2.3  # measured on French course text (step 0)
FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
BLANK = re.compile(r"\{\{(\w+)\}\}")


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


TEXT = {"type": "string"}
OPTIONS = {"type": "array", "items": _object({"id": TEXT, "text": TEXT})}
KINDS = [
    "qcm",
    "qrm",
    "vrai_faux",
    "texte_a_trous",
    "association",
    "ordre",
    "categories",
    "numerique",
]
# One flat item shape for every type (a union of per-type shapes compiles to a grammar the API
# rejects as too large); decode() turns it into the typed item checked below.
SCHEMA = _object(
    {
        "items": {
            "type": "array",
            "items": _object(
                {
                    "type": {"type": "string", "enum": KINDS},
                    "stem": TEXT,
                    "options": OPTIONS,
                    "options_b": OPTIONS,
                    "answers": {"type": "array", "items": TEXT},
                    "text": TEXT,
                    "unit": TEXT,
                    "tolerance": {"type": "number"},
                    "hints": {"type": "array", "items": TEXT},
                    "explanation": TEXT,
                    "citations": TEXT,
                    "high_yield": {"type": "boolean"},
                    "difficulty": {"type": "integer", "enum": [1, 2, 3]},
                }
            ),
        }
    }
)


def _pairs(answers: list[str], left: str, right: str) -> list[dict[str, str]]:
    pairs = []
    for answer in answers:
        first, separator, second = answer.partition(":")
        if not separator:
            raise ValueError(f"expected 'a:b', got {answer!r}")
        pairs.append({left: first.strip(), right: second.strip()})
    return pairs


def decode(flat: dict[str, Any]) -> dict[str, Any]:
    """The flat structured-output item as a typed item (raises ValueError when malformed)."""
    item = {
        key: flat[key]
        for key in ("type", "stem", "hints", "explanation", "citations", "high_yield", "difficulty")
    }
    kind, answers = flat["type"], flat["answers"]
    if kind == "qcm":
        item |= {"options": flat["options"], "answer": answers[0] if answers else ""}
    elif kind == "qrm":
        item |= {"options": flat["options"], "answer": answers}
    elif kind == "vrai_faux":
        if not answers or answers[0].strip().lower() not in {"vrai", "faux"}:
            raise ValueError("vrai_faux answer must be 'vrai' or 'faux'")
        item |= {"answer": answers[0].strip().lower() == "vrai"}
    elif kind == "texte_a_trous":
        blanks = []
        for answer in answers:
            key, separator, accepted = answer.partition("=")
            if not separator:
                raise ValueError(f"expected 'n=réponse|variante', got {answer!r}")
            blanks.append(
                {
                    "id": key.strip(),
                    "accepted": [a.strip() for a in accepted.split("|") if a.strip()],
                }
            )
        item |= {"text": flat["text"], "blanks": blanks}
    elif kind == "association":
        item |= {
            "left": flat["options"],
            "right": flat["options_b"],
            "pairs": _pairs(answers, "left", "right"),
        }
    elif kind == "ordre":
        item |= {"items": flat["options"], "order": answers}
    elif kind == "categories":
        item |= {
            "items": flat["options"],
            "categories": flat["options_b"],
            "mapping": _pairs(answers, "item", "category"),
        }
    elif kind == "numerique":
        if not answers:
            raise ValueError("numerique needs a value")
        item |= {
            "value": float(answers[0].replace(",", ".")),
            "tolerance": flat["tolerance"],
            "unit": flat["unit"],
        }
    return item


SYSTEM = """Tu écris des exercices de révision pour des étudiants en médecine (Faculté de Médecine \
de Sfax) à partir d'un cours déjà rédigé et cité. Le cours est la seule source autorisée.

Règles impératives
- N'utilise que des informations présentes dans le cours fourni ; n'ajoute aucun fait extérieur.
- Chaque exercice a un champ "citations" qui reprend les citations du cours (par exemple \
"[S1 p.12; S2 p.30]") des éléments qu'il teste ; l'explication se termine aussi par ces citations.
- Tout nombre écrit dans l'énoncé, les propositions (y compris les distracteurs), les réponses ou \
l'explication doit figurer, avec la même unité, dans les éléments cités. Un distracteur chiffré \
reprend donc une autre valeur réellement présente dans ces éléments (autre ligne du tableau…), \
jamais une valeur inventée.
- Distracteurs plausibles mais clairement faux d'après le cours ; pas de « toutes les réponses \
ci-dessus » ; pas de négations doubles.

Répartition (10 exercices) : 3 "qcm" (une seule bonne réponse, 4 ou 5 propositions), 2 "qrm" \
(plusieurs bonnes réponses, 5 propositions), 2 "vrai_faux", 1 "texte_a_trous", 1 exercice \
"association", "ordre" ou "categories" (le plus adapté au cours : ordre pour des étapes, \
association pour médicament ↔ effet, catégories pour classer), 1 "numerique" si le cours contient \
une valeur clé (sinon un "qcm" de plus). Privilégie les sections dont le titre porte {examen} \
(high_yield = true pour les exercices qui les testent).

Format de chaque exercice (tous les champs sont toujours présents ; mets "" , [] ou 0 quand un \
champ ne sert pas au type) :
- qcm / qrm : "options" = propositions [{"id": "A", "text": …}] ; "answers" = identifiants des \
bonnes réponses (un seul pour qcm).
- vrai_faux : "stem" est l'affirmation ; "answers" = ["vrai"] ou ["faux"].
- texte_a_trous : "text" contient {{1}}, {{2}}… ; "answers" = ["1=terme|variante", "2=terme"] \
(réponses acceptées séparées par |).
- association : "options" = colonne de gauche (ids l1, l2…), "options_b" = colonne de droite \
(r1, r2…) ; "answers" = ["l1:r2", "l2:r1", …].
- ordre : "options" = étapes (ids i1, i2…) ; "answers" = les ids dans le bon ordre.
- categories : "options" = éléments (i1…), "options_b" = catégories (c1…) ; \
"answers" = ["i1:c2", …].
- numerique : "answers" = ["valeur"], "unit" = unité, "tolerance" = écart accepté (souvent 0).

Indices ("hints", exactement 3, du plus général au plus précis, sans donner la réponse) :
1. Que demande vraiment la question (mot-clé, piège de l'énoncé) ;
2. Ce qu'on peut éliminer et pourquoi ;
3. La règle du cours qui permet de conclure.
Explication : pourquoi la bonne réponse est juste et, en une phrase, pourquoi les principaux \
distracteurs sont faux ; puis le schéma de raisonnement à retenir (« devant …, penser à … »).
Difficulté : 1 = connaissance directe, 2 = compréhension, 3 = raisonnement.
Les propositions sont mélangées à l'affichage : dans l'énoncé, les indices et l'explication, ne \
désigne jamais une proposition par sa lettre ; reprends son contenu.
Rédige en français."""


def run_for(year: Year, name: str = "v1") -> BatchRun:
    """Runs named test-* write their exercises inside the run only."""
    return BatchRun(year.runs / "exercises" / name)


def output_dir(year: Year, name: str) -> Path:
    if name.startswith("test-"):
        return run_for(year, name).root / "exercises"
    return year.data / "exercises"


def estimate_lessons(year: Year, model: str, lesson_ids: list[str]) -> float:
    characters = sum(len(lesson_markdown(year, lesson_id)) for lesson_id in lesson_ids)
    input_tokens = int(characters / CHARS_PER_TOKEN) + len(lesson_ids) * 1500
    output_tokens = len(lesson_ids) * 9000  # 10 items with hints and explanations + thinking
    return estimate_usd(model, input_tokens, output_tokens)


def lessons(year: Year, patterns: list[str] | None, regenerate: bool, out: Path) -> list[str]:
    selected = []
    for path in sorted(year.lessons.glob("*/lesson.md")):
        lesson_id = path.parent.name
        if patterns and not any(fnmatch.fnmatch(lesson_id, p) for p in patterns):
            continue
        if (out / f"{lesson_id}.json").is_file() and not regenerate:
            continue
        selected.append(lesson_id)
    return selected


def lesson_markdown(year: Year, lesson_id: str) -> str:
    text = (year.lessons / lesson_id / "lesson.md").read_text(encoding="utf-8")
    return FRONT_MATTER.sub("", text).strip()


def params(year: Year, model: str) -> Any:
    def build(item: dict[str, Any]) -> dict[str, Any]:
        markdown = lesson_markdown(year, item["lesson_id"])
        return {
            "model": model,
            "max_tokens": 32000,
            "output_config": {
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
            "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            "messages": [
                {
                    "role": "user",
                    "content": f'<cours lesson_id="{item["lesson_id"]}">\n{markdown}\n</cours>\n\n'
                    "Écris les 10 exercices de ce cours.",
                }
            ],
        }

    return build


# Local validation ------------------------------------------------------------------------------


def _pages_text(lesson_dir: Path, citations: str) -> tuple[str, list[str]]:
    metadata = json.loads((lesson_dir / "lesson.json").read_text(encoding="utf-8"))
    errors, texts = [], []
    found = CITATION.findall(citations)
    if not found:
        return "", ["no citation"]
    for key, _kind, start, end in found:
        source = metadata["sources"].get(key)
        if source is None:
            errors.append(f"unknown source {key}")
            continue
        pages = load_pages(PROJECT_ROOT / source["text_root"] / source["text_relative_path"])
        for page in range(int(start), int(end or start) + 1):
            if page not in pages:
                errors.append(f"{key} has no page {page}")
            else:
                texts.append(pages[page])
    return "\n".join(texts), errors


def _texts(item: dict[str, Any]) -> list[str]:
    texts = [item["stem"], item["explanation"], *item["hints"]]
    for key in ("options", "left", "right", "items", "categories"):
        texts += [option["text"] for option in item.get(key, [])]
    if item["type"] == "texte_a_trous":
        texts.append(item["text"])
        texts += [answer for blank in item["blanks"] for answer in blank["accepted"]]
    if item["type"] == "numerique":
        texts.append(f"{item['value']:g} {item['unit']}")
    return texts


def check(lesson_dir: Path, item: dict[str, Any]) -> list[str]:
    errors = []
    if len(item["hints"]) != 3:
        errors.append("hint ladder must have 3 steps")
    ids = {option["id"] for option in item.get("options", [])}
    kind = item["type"]
    if kind in {"qcm", "image"} and item["answer"] not in ids:
        errors.append("answer is not an option")
    if kind == "qrm" and (not item["answer"] or not set(item["answer"]) <= ids):
        errors.append("qrm answers must be options")
    if kind == "texte_a_trous":
        blanks = set(BLANK.findall(item["text"]))
        if not blanks or blanks != {blank["id"] for blank in item["blanks"]}:
            errors.append("blanks do not match the {{n}} markers")
    if kind == "association":
        left, right = {o["id"] for o in item["left"]}, {o["id"] for o in item["right"]}
        pairs = {pair["left"]: pair["right"] for pair in item["pairs"]}
        if set(pairs) != left or not set(pairs.values()) <= right:
            errors.append("pairs must cover every left item with a right item")
    if kind == "ordre" and sorted(item["order"]) != sorted(o["id"] for o in item["items"]):
        errors.append("order must be a permutation of the items")
    if kind == "categories":
        mapping = {entry["item"]: entry["category"] for entry in item["mapping"]}
        if set(mapping) != {o["id"] for o in item["items"]} or not set(mapping.values()) <= {
            o["id"] for o in item["categories"]
        }:
            errors.append("mapping must place every item in a category")
    page_text, citation_errors = _pages_text(lesson_dir, item["citations"])
    errors += citation_errors
    if page_text:
        available = numbers(page_text)
        for text in _texts(item):
            missing = sorted(claimed_numbers(CITATION.sub("", normalize(text))) - available)
            if missing:
                errors.append(f"numbers not in cited pages {missing}: {text[:80]}")
    return errors


def to_web(lesson_id: str, index: int, item: dict[str, Any]) -> dict[str, Any]:
    """Convert a validated item to the website's Exercise shape (web/src/lib/content/types.ts)."""
    base = {
        "id": f"{lesson_id}#q{index}",
        "lessonId": lesson_id,
        "type": item["type"],
        "stem": item["stem"],
        "hints": item["hints"],
        "explanation": item["explanation"],
        "citations": item["citations"],
        "highYield": item["high_yield"],
        "difficulty": item["difficulty"],
    }
    kind = item["type"]
    if kind in {"qcm", "qrm"}:
        base |= {"options": item["options"], "answer": item["answer"]}
    elif kind == "vrai_faux":
        base |= {"answer": item["answer"]}
    elif kind == "texte_a_trous":
        base |= {"text": item["text"], "blanks": {b["id"]: b["accepted"] for b in item["blanks"]}}
    elif kind == "association":
        base |= {
            "left": item["left"],
            "right": item["right"],
            "pairs": {p["left"]: p["right"] for p in item["pairs"]},
        }
    elif kind == "ordre":
        base |= {"items": item["items"], "order": item["order"]}
    elif kind == "categories":
        base |= {
            "categories": item["categories"],
            "items": item["items"],
            "mapping": {m["item"]: m["category"] for m in item["mapping"]},
        }
    elif kind == "numerique":
        base |= {"value": item["value"], "tolerance": item["tolerance"], "unit": item["unit"]}
    return base


def collect(year: Year, name: str) -> int:
    run = run_for(year, name)
    print(run.collect(client()))
    planned = {item["custom_id"]: item for item in run.items()}
    written = kept = rejected = 0
    for custom, record in run.latest().items():
        if record["type"] != "succeeded" or record["stop_reason"] != "end_turn":
            continue
        lesson_id = planned[custom]["lesson_id"]
        target = output_dir(year, name) / f"{lesson_id}.json"
        if target.is_file() and json.loads(target.read_text())["generation"]["custom_id"] == custom:
            continue
        lesson_dir = year.lessons / lesson_id
        if validate(lesson_dir).errors:
            print(f"skip {lesson_id}: lesson no longer validates")
            continue
        items = json.loads(message_text(record))["items"]
        good, bad = [], []
        for flat in items:
            try:
                item = decode(flat)
            except (ValueError, KeyError, IndexError) as error:
                bad.append({"item": flat, "errors": [f"malformed: {error}"]})
                continue
            errors = check(lesson_dir, item)
            if errors:
                bad.append({"item": flat, "errors": errors})
            else:
                good.append(to_web(lesson_id, len(good) + 1, item))
        write_json_atomic(
            target,
            {
                "lessonId": lesson_id,
                "status": "draft_unreviewed",
                "generation": {
                    "model": record["model"],
                    "run": run.root.name,
                    "custom_id": custom,
                    "date": datetime.now(timezone.utc).date().isoformat(),
                },
                "items": good,
                "rejected": bad,
            },
        )
        written += 1
        kept += len(good)
        rejected += len(bad)
    print(f"wrote {written} lessons: {kept} exercises kept, {rejected} rejected")
    return 0


def client() -> Any:
    if not load_api_key():
        raise SystemExit("ANTHROPIC_API_KEY is not set (put it in .env).")
    import anthropic

    return anthropic.Anthropic()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", required=True, help="year id from library.toml")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--run", default="v1", help="run name; test-* runs keep their output")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "submit"):
        command = sub.add_parser(name)
        command.add_argument("--lessons", help="comma-separated lesson ids or glob patterns")
        command.add_argument("--limit", type=int)
        command.add_argument("--regenerate", action="store_true")
        if name == "submit":
            command.add_argument("--yes", action="store_true", help="confirm spending money")
            command.add_argument("--max-usd", type=float, help="refuse above this estimate")
    sub.add_parser("collect")
    sub.add_parser("status")
    args = parser.parse_args()
    year = get_year(args.year)
    if args.command in {"plan", "submit"}:
        patterns = args.lessons.split(",") if args.lessons else None
        selected = lessons(year, patterns, args.regenerate, output_dir(year, args.run))
        selected = selected[: args.limit] if args.limit else selected
        cost = estimate_lessons(year, args.model, selected)
        print(f"{len(selected)} lessons; estimate ({args.model}, batch): ~${cost:.2f}")
        if args.command == "plan":
            return 0
        if not args.yes:
            raise SystemExit("submit spends money: re-run with --yes after the owner's go.")
        run = run_for(year, args.run)
        planned = [
            {
                "custom_id": custom_id("x2", f"{lesson_id}|{lesson_markdown(year, lesson_id)}"),
                "lesson_id": lesson_id,
            }
            for lesson_id in selected
        ]
        run.plan(planned)
        only = {item["custom_id"] for item in planned}
        pending = [item["lesson_id"] for item in run.pending(only=only)]
        check_budget(estimate_lessons(year, args.model, pending), args.max_usd)
        print(f"submitted {run.submit(client(), params(year, args.model), only=only)}")
        print(json.dumps(run.summary(), indent=2))
    elif args.command == "collect":
        return collect(year, args.run)
    else:
        print(json.dumps(run_for(year, args.run).summary(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
