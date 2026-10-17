# MedPlat

Turns Tunisian medical-school course libraries (Faculté de Médecine de Sfax, per study year) into
source-grounded lessons and exercises for a student revision website.

Pipeline, per year:

1. **Extract** — mirror every original file to UTF-8 text with page/slide separators (Docling +
   PyMuPDF; LibreOffice for legacy `.ppt`/`.ppsx`; explicit local OCR derivatives).
2. **Catalog** — inventory every file with a text-quality score, then classify files into
   pole → certif → module → lesson, with source roles (official slides, polycopié, student summary…).
3. **Reconstruct** — rebuild each lesson from its sources only, every statement citing its source
   page (`[S1 p.10]`), checked by a deterministic grounding validator.
4. **Generate** *(next)* — exercises (QCM, QRM, vrai/faux, …) from validated lessons.
5. **Website** *(next)* — static site plus a lesson-grounded chatbot.

Everything generated is a draft until a human medical reviewer accepts it. The validator checks
traceability (citations, cited pages, numbers), never medical correctness.

## Layout

```
library.toml          years: id, label, source folder; Docling model path
library/<year>/       original course files, read-only, Git-ignored
data/<year>/          everything derived, Git-ignored
  text/               mirrored text exports (+ export-manifest.json)
  text-office/        text of legacy .ppt/.ppsx via .pptx derivatives
  office/             LibreOffice derivatives, content-addressed by source SHA-256
  ocr/                OCR derivatives, content-addressed
  reports/            extraction run reports
  catalog/            inventory, per-certif classification, catalog.json
  lessons/<id>/       lesson.md + lesson.json
data/models/docling/  local Docling layout/table models
src/ingestion/        extraction library and `medparse` CLI
scripts/              catalog and lesson stages
docs/                 stage specifications
```

Configured years: `dcem1` (3e année) and `dcem2` (4e année).

## Setup

```bash
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
docling-tools models download --output-dir "$PWD/data/models/docling" layout tableformer
medparse check-environment --docling-artifacts-path data/models/docling
```

LibreOffice (`soffice`) is needed for legacy Office conversion; OCRmyPDF and Tesseract for OCR.

## Commands

```bash
# 1. Extract (review the dry run first; --resume skips validated outputs)
medparse extract-text-tree --year dcem2 --dry-run
medparse extract-text-tree --year dcem2 --resume
python scripts/convert_legacy_office.py --year dcem2   # after the inventory exists

# 2. Catalog
python scripts/build_inventory.py --year dcem2
python scripts/merge_catalog.py --year dcem2           # after data/dcem2/catalog/certifs/*.json

# 3. Validate a reconstructed lesson
python scripts/validate_lesson.py data/dcem1/lessons/<lesson_id>
```

Other `medparse` commands: `inspect-library`, `inspect-document`, `parse-document`,
`parse-sample`, `validate-output`, `check-ocr-environment`, `evaluate-ocr`,
`create-ocr-derivative`, `validate-derivative`, `parse-ocr-derivative`.

The previous local-Ollama pipeline (chunking, datasets, batch processing, QCM drafting) is kept
in Git history under the tag `archive/local-pipeline`.

## Checks

```bash
ruff check . && ruff format --check . && mypy src/ingestion && pytest
```

See [docs/text-tree-extraction.md](docs/text-tree-extraction.md),
[docs/catalog-classification.md](docs/catalog-classification.md),
[docs/ocr.md](docs/ocr.md), and [docs/docling-models.md](docs/docling-models.md).
