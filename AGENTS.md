# MedPlat Local Document Ingestion

## Completed architecture

This repository implements a local, read-only document ingestion pipeline through AI-ready dataset
packaging. The completed layers are:

- recursive document-library inspection and manifest reporting;
- plugin-based structured parsing for PDF, PPTX, and DOCX;
- explicitly configured local Docling layout and table artifacts for PDF parsing;
- PyMuPDF PDF inspection, text reconciliation, coordinates, and asset enrichment;
- canonical `document.json`, `document.md`, and processing-report normalization;
- canonical schema and provenance validation;
- explicit local OCRmyPDF/Tesseract derivatives with quality validation;
- deterministic, source-grounded chunking with table and asset association;
- AI-ready dataset packaging from validated canonical documents and chunks; and
- deterministic, bounded, sequential, resumable batch planning and processing.

AI-ready datasets are technical ingestion outputs. They do not assert medical correctness or
medical validation, and this repository does not generate medical content.

## Not implemented

Do not implement these without a later milestone that explicitly authorizes them:

- website or frontend;
- application backend or public API;
- Azure or Supabase integration;
- authentication;
- external AI parsing or generation;
- AI summarization;
- embeddings or vector indexing;
- flashcards;
- QCM or question generation;
- clinical case generation; or
- automated medical review or publication.

## Project paths

- Document library root: `pdfsrc`
- Python source: `src/ingestion`
- Tests: `tests`
- Inspection and batch reports: `data/reports`
- Canonical, chunk, and dataset output: `data/processed`
- OCR derivatives: `data/derived`
- Local Docling artifacts: `data/docling-models`

Generated output and local model directories must remain outside `pdfsrc` and must not be committed.

## Inspection support

The document library may contain nested directories with any combination of:

- PDF (`.pdf`)
- Microsoft Word (`.docx`, `.doc`)
- Microsoft PowerPoint (`.pptx`, `.ppt`)
- Microsoft Excel (`.xlsx`, `.xls`)
- OpenDocument Text (`.odt`)
- OpenDocument Presentation (`.odp`)
- EPUB (`.epub`)
- Markdown (`.md`)
- HTML (`.html`)
- Plain Text (`.txt`)
- Rich Text (`.rtf`)
- PNG (`.png`)
- JPEG (`.jpg`, `.jpeg`)
- TIFF (`.tiff`)
- BMP (`.bmp`)
- WEBP (`.webp`)

Scan recursively, inspect supported library formats, and report unsupported files without parsing
them. Preserve every original source-relative path.

## Structured parsing support

- PDF: Docling with an explicitly configured, validated local artifact root, enriched by PyMuPDF.
- PPTX: Docling Office parsing with slide provenance; no PDF conversion.
- DOCX: Docling Office parsing with document-level locations and null physical pagination when
  pagination is unavailable; no invented page numbers.
- Legacy `.ppt` and `.doc` and all other formats: inspection and unsupported reporting only.

The parser registry exposes a common interface. Parser-specific objects must not cross the canonical
normalization boundary.

## Inspection outputs

For every inspected document collect, where applicable:

- relative path, filename, extension, and MIME type;
- file size and incremental SHA-256;
- readable and encrypted status;
- page, slide, worksheet, and image counts;
- extractable character count and average characters per page or slide;
- document classification and OCR recommendation; and
- concise error information.

Allowed inspection classifications are:

- `native_text`
- `mixed`
- `likely_scanned`
- `encrypted`
- `unreadable`
- `unsupported`

Inspection reports are:

- `data/reports/library-manifest.json`
- `data/reports/library-manifest.csv`
- `data/reports/duplicate-files.json`
- `data/reports/inspection-errors.json`
- `data/reports/unsupported-files.json`

## Canonical normalization and suitability

Canonical schema version `1.0.0` is the current downstream boundary. Preserve source SHA-256,
source-relative paths, document type, page or slide locations, nullable DOCX pagination, block IDs,
tables, assets, coordinates when reliable, and source references.

Technical suitability describes extraction quality only:

- `ready_for_chunking`: meaningful canonical text exists with no extraction warnings;
- `ready_with_warnings`: meaningful canonical text exists with extraction warnings;
- `requires_ocr`: a PDF has low-text image pages requiring explicit OCR;
- `unsuitable`: no meaningful canonical text is available.

Technical suitability never means that medical claims are correct or medically validated.

## Local Docling model policy

PDF parsing requires an explicitly configured and validated local Docling artifact root. Parsing
must not download models, contact a remote model registry, or silently use an implicit cache. Only
the PDF parser initializes PDF layout and table models. PPTX and DOCX parsing must not require the
PDF model artifacts.

Environment checks may validate configuration without opening or parsing source documents.

## OCR derivative policy

OCR is an explicit local operation and is disabled by default. OCRmyPDF and Tesseract create a
content-addressed derivative under `data/derived`; they never alter the original PDF. Safe skip-text
OCR and force OCR are separate explicit choices with separate derivative identities.

Every derivative must preserve:

- original source SHA-256 and source-relative path;
- derivative SHA-256 and configuration;
- physical one-based page mapping;
- tool and language provenance; and
- an explicit quality outcome.

Only accepted derivatives may be parsed into canonical variants. Rejected or no-improvement
derivatives must stop before chunking and dataset construction.

## Chunking and AI-ready datasets

Chunking accepts only validated canonical `document.json`; it must not reopen raw sources. Chunking
is deterministic and structural, not medical-semantic. Preserve section context, exact source
references, tables, assets, duplicates, and uncertain associations. Do not force an asset or table
association without reliable evidence.

Dataset construction accepts only a validated canonical document and validated chunks. Dataset
readiness requires at least one eligible grounded chunk and nonzero source-reference coverage.
Dataset readiness is technical only and is not approval for medical generation or publication.

## Controlled batch processing

- Full-library processing requires explicit authorization.
- Normal controlled batches require a deterministic bounded selection.
- Limits above the normal bound require explicit large-batch acknowledgement.
- Execution is sequential with `jobs=1`.
- OCR is disabled unless explicitly enabled.
- Force OCR additionally requires explicit authorization.
- Continue processing unrelated documents when one document fails by default.
- Persist atomic plan, state, per-document, failure, skipped, and aggregate reports.
- Aggregate reports must stay concise and must not include large extracted medical passages.

Resume must validate source hashes, canonical schema and provenance, accepted derivative identity,
chunks, datasets, and generation-readiness evidence. Directory existence alone never indicates
success. Missing or invalid downstream artifacts resume from the nearest validated stage.

## CLI

The local CLI includes:

- `medparse inspect-library`
- `medparse inspect-document`
- `medparse check-environment`
- `medparse parse-document`
- `medparse parse-sample`
- `medparse validate-output`
- `medparse check-ocr-environment`
- `medparse evaluate-ocr`
- `medparse create-ocr-derivative`
- `medparse validate-derivative`
- `medparse parse-ocr-derivative`
- `medparse build-chunks`
- `medparse validate-chunks`
- `medparse inspect-chunk`
- `medparse build-dataset`
- `medparse validate-dataset`
- `medparse plan-library`
- `medparse process-library`

Planning and dry-run modes must not parse documents, initialize models unnecessarily, perform OCR,
or create processing output.

## Implementation requirements

Use pathlib, Pydantic, Typer, Rich, incremental SHA-256 hashing, type hints, structured logging, and
atomic output writes. Preserve the parser plugin boundary and continue processing unrelated files
when one document fails.

Before completion run:

- `ruff check .`
- `ruff format --check .`
- `mypy src/ingestion`
- `pytest`

## Library and artifact safety

- Scan the source library recursively.
- Treat `pdfsrc` as read-only.
- Never rename, move, overwrite, or delete source documents.
- Never write generated files into the document library.
- Never commit source documents or generated processing artifacts.
- Existing successful canonical documents, derivatives, chunks, datasets, and reports are immutable
  unless an explicit, scoped rebuild is authorized.

## Permanent downstream rules

- Downstream systems must consume canonical documents or validated chunks; they must not parse raw
  source files directly.
- Canonical `document.json`, `document.md`, and processing reports are immutable inputs to downstream
  stages.
- Page, slide, block, table, asset, and source-relative-path provenance must be preserved.
- Generated medical content must preserve source references and default to draft status.
- No generated medical claim may exist without traceable source grounding.
- No external AI API may be used unless a later milestone explicitly configures and authorizes it.
- PDF parsing must use an explicitly configured, validated local Docling artifact root. It must not
  download models during parsing or silently fall back to a remote model registry.
- OCR must be an explicit local operation. Original source documents are immutable, and OCR output
  is always a separately validated derivative with preserved provenance.
- Rejected OCR output must never proceed to chunks, datasets, or learning-content generation.
- Citations from OCR-derived canonical output must retain the original source-relative path and
  physical page number, not point only to the derivative.
- Full-library processing requires explicit authorization; controlled batches use deterministic
  ordering and a bounded explicit selection by default.
- Resume must validate canonical, derivative, chunk, and dataset artifacts. Directory existence
  alone never means success.
- OCR and force OCR remain separate explicit batch choices. Failed documents must not block
  unrelated documents by default.
- Aggregate processing reports must remain concise and must not include large medical text.
- Source files remain immutable throughout planning, retries, resume, and batch execution.
