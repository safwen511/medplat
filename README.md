# MedPlat local document ingestion

This repository provides local, read-only document inspection, structured normalization, explicit
OCR derivatives, deterministic chunking, and AI-ready dataset packaging. It does not implement
cloud integrations, AI content generation, embeddings, or the website.

Structured parsing supports PDF, PPTX, and DOCX through Docling. PDF navigation and coordinates are
enriched with PyMuPDF. Other formats remain visible to inspection and are marked
`unsupported_for_parsing`; legacy `.ppt` and `.doc` files are never parsed.

PDF parsing is local-only and requires an explicit Docling model artifact root. PPTX and DOCX do not
require these PDF models.

## Local PDF model setup

Docling 2.117.0 provides the official model helper. Download only the layout and TableFormer models;
OCR models are intentionally excluded:

```bash
docling-tools models download \
  --output-dir "$PWD/data/docling-models" \
  layout tableformer
export DOCLING_ARTIFACTS_PATH="$PWD/data/docling-models"
```

The project-local destination is Git-ignored. A different absolute destination is also valid. Check
the environment without parsing a document or downloading anything:

```bash
medparse check-environment
```

See [docs/docling-models.md](docs/docling-models.md) for expected directory semantics and error
remediation.

## Commands

Plan or dry-run a controlled representative batch without parsing documents:

```bash
medparse plan-library --input pdfsrc --limit 10 --selection representative \
  --enable-ocr --ocr-languages fra
medparse process-library --input pdfsrc --output data/processed \
  --derived-output data/derived --limit 10 --selection representative \
  --jobs 1 --resume --enable-ocr --ocr-languages fra --dry-run
```

Batch execution is sequential and accepts only `--jobs 1`. OCR is disabled unless explicitly
enabled, and force OCR additionally requires `--allow-force-ocr`. Existing output is reused only
after schema, source-hash, provenance, suitability, chunk, and dataset validation. See
[docs/batch-processing.md](docs/batch-processing.md).

Check local OCR tools and explicitly evaluate one PDF without creating output:

```bash
medparse check-ocr-environment --languages fra
medparse evaluate-ocr "pdfsrc/path/to/selected.pdf"
```

Create and validate a safe skip-text derivative, then parse it only when accepted:

```bash
medparse create-ocr-derivative "pdfsrc/path/to/selected.pdf" \
  --languages fra --output data/derived
medparse validate-derivative data/derived/<source-sha>/ocr/<derivative-id>/derivative.json
medparse parse-ocr-derivative \
  data/derived/<source-sha>/ocr/<derivative-id>/derivative.json \
  --output data/processed
```

Canonical OCR variants are isolated under
`data/processed/<source-sha>/variants/<processing-variant-id>/`. See
[docs/ocr.md](docs/ocr.md).

Inspect without structured parsing:

```bash
medparse inspect-document pdfsrc/path/to/document.pdf
medparse inspect-library --input pdfsrc --output data/reports --limit 10
```

Safely normalize one selected source:

```bash
medparse parse-document "pdfsrc/path/to/selected-document.pdf" --output data/processed
```

An explicit CLI path overrides the environment for that invocation:

```bash
medparse parse-document "pdfsrc/path/to/selected-document.pdf" \
  --docling-artifacts-path /absolute/path/to/docling-model-artifacts
```

Asset extraction and PDF previews are opt-in. Existing successful output is protected unless
`--force` is supplied:

```bash
medparse parse-document "pdfsrc/path/to/selected-document.pdf" \
  --output data/processed --extract-assets --render-previews
```

Select and normalize at most three representative real documents. `--input` is mandatory:

```bash
medparse parse-sample --input pdfsrc --output data/processed --limit 3
```

Limits above three require the explicit `--allow-large-batch` acknowledgement. Individual failures
do not stop the batch, and `batch-processing-report.json` records every result.

Validate canonical output:

```bash
medparse validate-output data/processed/<sha256>/document.json
```

Build deterministic chunks from validated canonical JSON only:

```bash
medparse build-chunks data/processed/<sha256>/document.json
medparse validate-chunks data/processed/<sha256>/chunks/chunks.json
```

Inspect one chunk without reading the raw source document:

```bash
medparse inspect-chunk data/processed/<sha256>/chunks/chunks.json <chunk-id>
```

Build and validate the AI-ready dataset package:

```bash
medparse build-dataset data/processed/<sha256>/document.json
medparse validate-dataset data/processed/<sha256>/datasets/ai-ready-dataset.json
```

Chunk and dataset outputs are protected from overwrite. Use `--force` only for an intentional,
atomic rebuild.

## Output

Successful results are written outside `pdfsrc` under `data/processed/<sha256>/`. `document.json` is
the canonical versioned model, `document.md` is a human-readable inspection view, and
`processing-report.json` records parser/version, timing, warnings, errors, unsupported features, and
output paths. See [docs/normalization.md](docs/normalization.md) for normalization,
[docs/chunking.md](docs/chunking.md) for learning-unit construction, and
[docs/architecture.md](docs/architecture.md) for system boundaries.

## Known limitations

- OCR never runs automatically. Safe skip-text OCR may produce no improvement on a page that already
  contains sparse text; force-OCR requires a separate explicit decision.
- Docling's PDF layout and accurate TableFormer models must already exist at the explicitly
  configured artifact root. Parsing never downloads them and source content is never sent to an
  external service.
- A PDF page with embedded images and fewer than 100 extractable characters is marked as requiring
  OCR. OCR remains disabled, and such output must not be treated as generation-ready.
- DOCX has no invented physical pagination.
- Speaker notes are retained only if Docling exposes them reliably.
- Asset extraction and preview rendering currently materialize PDF content only.
- Ambiguous PDF text-coordinate matches deliberately retain text with null coordinates and a
  warning.
- Chunking is structural rather than medical-semantic: it does not identify diagnoses, treatments,
  questions, answers, or other interpreted concepts.
- Assets without explicit, caption, unique-location, or reliable spatial evidence remain
  unassociated rather than being forced into a chunk.
