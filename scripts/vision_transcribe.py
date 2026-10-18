"""Transcribe scanned and image-only course pages with Claude vision, through the Batches API.

Targets (from data/<year>/catalog/inventory.json): PDFs that require OCR, images (exam photos),
and exported PDFs whose text layer is empty (or, with --quality, noisy/unusable text such as
handwriting OCR). Files the catalog excludes as duplicates or off-topic are skipped. Each page is
rendered locally (PyMuPDF, long edge 1568 px) and sent as one request asking for a literal
transcription: no interpretation, no added content, figures only marked by type.

    plan     list target pages and estimate the cost (free, no API call, writes nothing)
    submit   record the current targets and send pending pages as Message Batches
             (SPENDS MONEY; needs --yes)
    collect  fetch the results of ended batches
    export   write complete transcriptions to data/<year>/text-vision/ (standard text format)
    status   show the run state

Usage: python scripts/vision_transcribe.py --year dcem2 plan [--limit N]
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz

from ingestion.claude_batch import BatchRun, custom_id, estimate_usd, load_api_key, message_text
from ingestion.library import Year, get_year
from ingestion.output import write_json_atomic, write_text_atomic
from ingestion.text_tree.models import ExportStatus
from ingestion.text_tree.rendering import RenderedBody, render_export

MODEL = "claude-opus-5-5"
LONG_EDGE = 1568
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
# Planning assumptions for the estimate: output tokens per page, including low-effort thinking.
ESTIMATED_OUTPUT_TOKENS = 1000
SYSTEM = """Tu transcris des pages de cours de médecine (Faculté de Médecine de Sfax) à partir \
d'images : diapositives, polycopiés, résumés d'étudiants, examens, parfois manuscrits.

Règles :
- Transcris tout le texte visible, fidèlement, dans l'ordre de lecture, dans la langue et \
l'orthographe d'origine. Ne corrige pas, ne complète pas, n'interprète pas, n'ajoute aucune \
information médicale.
- Titres sur leur propre ligne ; listes avec « - » ; tableaux en tableau Markdown (| a | b |).
- Texte manuscrit : transcris-le s'il est lisible ; un passage illisible devient [illisible].
- Images, radiographies, photos, schémas : une ligne [Figure: <type>] où <type> est \
radiographie, imagerie, photo clinique, schéma, graphique, tableau en image ou logo. Ne décris \
pas leur contenu ; transcris seulement le texte écrit dessus (légendes, flèches, étiquettes).
- Questions d'examen : garde la numérotation, les propositions (A, B, C…) et les réponses ou \
corrections si elles sont écrites sur la page.
- Page sans texte : réponds seulement [Page vide].
Réponds uniquement par la transcription, sans commentaire."""


def run_for(year: Year) -> BatchRun:
    return BatchRun(year.runs / "vision" / "v1")


def excluded_paths(year: Year) -> set[str]:
    skipped = set()
    for path in (year.catalog / "certifs").glob("*.json"):
        for item in json.loads(path.read_text(encoding="utf-8")).get("excluded", []):
            if item["reason"].startswith(("duplicate_of", "off_topic")):
                skipped.add(item["path"])
    return skipped


def targets(year: Year, qualities: set[str]) -> list[dict[str, Any]]:
    """One planned item per page of every target source."""
    records = json.loads((year.catalog / "inventory.json").read_text())["records"]
    skipped = excluded_paths(year)
    items = []
    for record in records:
        path = record["source_relative_path"]
        extension = record["extension"].lower()
        if path in skipped or record["exact_duplicate_of"]:
            continue
        is_image = extension in IMAGE_EXTENSIONS
        scanned = extension == ".pdf" and record["export_status"] == "requires_ocr"
        poor_text = (
            extension == ".pdf"
            and record["export_status"].startswith(("exported", "skipped_current"))
            and record["text_quality"] in qualities
        )
        if not (is_image or scanned or poor_text):
            continue
        with fitz.open(year.source / path) as document:
            pages = document.page_count
        for page in range(1, pages + 1):
            items.append(
                {
                    "custom_id": custom_id("v", f"{record['source_sha256']}:{page}"),
                    "source_relative_path": path,
                    "source_sha256": record["source_sha256"],
                    "page": page,
                    "page_count": pages,
                }
            )
    return items


def render_page(year: Year, item: dict[str, Any]) -> tuple[bytes, int]:
    """JPEG of one page with its long edge at LONG_EDGE pixels, plus its image-token estimate."""
    with fitz.open(year.source / item["source_relative_path"]) as document:
        page = document[item["page"] - 1]
        zoom = LONG_EDGE / max(page.rect.width, page.rect.height)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csRGB)
        return pixmap.tobytes("jpeg", jpg_quality=85), pixmap.width * pixmap.height // 750


def build(year: Year, model: str) -> Any:
    def params(item: dict[str, Any]) -> dict[str, Any]:
        image, _tokens = render_page(year, item)
        return {
            "model": model,
            "max_tokens": 8000,
            "output_config": {"effort": "low"},
            "system": SYSTEM,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": base64.standard_b64encode(image).decode("ascii"),
                            },
                        },
                        {
                            "type": "text",
                            "text": f"Page {item['page']} sur {item['page_count']}. "
                            "Transcris cette page.",
                        },
                    ],
                }
            ],
        }

    return params


def plan(year: Year, qualities: set[str], model: str) -> int:
    items = targets(year, qualities)
    sources = {item["source_relative_path"] for item in items}
    image_tokens = per_page = 0
    for item in items:
        # Exact for the rendered size; rendering every page is slow, so sample per source.
        if item["page"] == 1:
            _image, tokens = render_page(year, item)
            per_page = tokens
        image_tokens += per_page
    input_tokens = image_tokens + len(items) * 450
    output_tokens = len(items) * ESTIMATED_OUTPUT_TOKENS
    known = {item["custom_id"] for item in run_for(year).items()}
    new = sum(item["custom_id"] not in known for item in items)
    print(f"{len(items)} pages in {len(sources)} sources ({new} not yet in the run)")
    print(
        f"estimate ({model}, batch): ~{input_tokens:,} input + ~{output_tokens:,} output tokens "
        f"= ~${estimate_usd(model, input_tokens, output_tokens):.2f} for all pages"
    )
    return 0


def client() -> Any:
    if not load_api_key():
        raise SystemExit("ANTHROPIC_API_KEY is not set (put it in .env).")
    import anthropic

    return anthropic.Anthropic()


def export(year: Year) -> int:
    run = run_for(year)
    latest = run.latest()
    by_source: dict[str, list[dict[str, Any]]] = {}
    for item in run.items():
        by_source.setdefault(item["source_relative_path"], []).append(item)
    manifest_path = year.text_vision / "vision-export-manifest.json"
    entries = []
    incomplete = 0
    for source, items in sorted(by_source.items()):
        items.sort(key=lambda item: item["page"])
        records = [latest.get(item["custom_id"]) for item in items]
        complete = len(items) == items[0]["page_count"] and all(
            record and record["type"] == "succeeded" and record["stop_reason"] == "end_turn"
            for record in records
        )
        if not complete:
            incomplete += 1
            continue
        pages = [message_text(record).strip() for record in records if record]
        text = "\n\n".join(
            f"===== PAGE {item['page']} =====\n\n{page}".rstrip()
            for item, page in zip(items, pages, strict=True)
        )
        models = sorted({record["model"] for record in records if record})
        relative = str(Path(source).with_suffix(".txt"))
        characters = sum(len(page) for page in pages if page != "[Page vide]")
        write_text_atomic(
            year.text_vision / relative,
            render_export(
                source_filename=Path(source).name,
                source_relative_path=source,
                source_extension=Path(source).suffix,
                source_sha256=items[0]["source_sha256"],
                document_type="pdf",
                status=ExportStatus.EXPORTED_WITH_WARNINGS,
                extraction_tool=f"claude-vision/{'+'.join(models)}",
                exported_at=datetime.now(timezone.utc),
                body=RenderedBody(
                    text=text + "\n", text_character_count=characters, page_or_slide_count=None
                ),
            ),
        )
        entries.append(
            {
                "source_relative_path": source,
                "source_sha256": items[0]["source_sha256"],
                "status": "exported_with_warnings",
                "output_relative_path": relative,
                "text_character_count": characters,
                "page_or_slide_count": len(items),
                "models": models,
                "warnings": [
                    "Transcribed by Claude vision from page images; verify against the source."
                ],
            }
        )
    write_json_atomic(manifest_path, {"entries": entries})
    print(f"exported {len(entries)} sources; {incomplete} incomplete -> {manifest_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", required=True, help="year id from library.toml")
    parser.add_argument("--model", default=MODEL)
    sub = parser.add_subparsers(dest="command", required=True)
    quality_help = "comma-separated text qualities of exported PDFs to include (empty,unusable)"
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--quality", default="empty", help=quality_help)
    submit_parser = sub.add_parser("submit")
    submit_parser.add_argument("--quality", default="empty", help=quality_help)
    submit_parser.add_argument("--limit", type=int, help="submit at most N pending pages")
    submit_parser.add_argument("--yes", action="store_true", help="confirm spending money")
    sub.add_parser("collect")
    sub.add_parser("export")
    sub.add_parser("status")
    args = parser.parse_args()
    year = get_year(args.year)
    run = run_for(year)
    if args.command == "plan":
        return plan(year, set(args.quality.split(",")), args.model)
    if args.command == "submit":
        if not args.yes:
            raise SystemExit("submit spends money: re-run with --yes after the owner's go.")
        run.plan(targets(year, set(args.quality.split(","))))
        batches = run.submit(client(), build(year, args.model), limit=args.limit)
        print(f"submitted {len(batches)} batch(es): {', '.join(batches) or '-'}")
    elif args.command == "collect":
        print(run.collect(client()))
    elif args.command == "export":
        return export(year)
    print(json.dumps(run.summary(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
