# MedPlat Local Document Ingestion

## Completed architecture

This repository implements a local, read-only document ingestion pipeline through AI-ready dataset
packaging plus local source-grounded draft QCM generation. The completed layers are:

- recursive document-library inspection and manifest reporting;
- plugin-based structured parsing for PDF, PPTX, and DOCX;
- explicitly configured local Docling layout and table artifacts for PDF parsing;
- PyMuPDF PDF inspection, text reconciliation, coordinates, and asset enrichment;
- canonical `document.json`, `document.md`, and processing-report normalization;
- canonical schema and provenance validation;
- explicit local OCRmyPDF/Tesseract derivatives with quality validation;
- deterministic, source-grounded chunking with table and asset association;
- deterministic cleaning, readiness classification, and source-constrained local reconstruction of
  mirrored course-text exports;
- AI-ready dataset packaging from validated canonical documents and chunks; and
- deterministic, bounded, sequential, resumable batch planning and processing;
- deterministic generation planning from validated, eligible dataset chunks;
- folder-aware course cataloging, chunk-level knowledge-unit inventory, and read-only QCM coverage
  planning;
- loopback-only Ollama structured QCM drafting behind a provider abstraction;
- technical grounding, quotation, provenance, and duplicate validation; and
- explicit terminal human review states and accepted-only question-bank export.

AI-ready datasets are technical ingestion outputs. They do not assert medical correctness or
medical validation. Generated QCMs are always drafts and unreviewed until an explicit human review
decision is recorded. Technical grounding checks do not assert medical correctness.

## Not implemented

Do not implement these without a later milestone that explicitly authorizes them:

- website or frontend;
- application backend or public API;
- Azure or Supabase integration;
- authentication;
- external or cloud AI parsing or generation;
- AI summarization;
- embeddings or vector indexing;
- flashcards;
- question generation other than the explicitly enabled local QCM route;
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
- Local generated drafts and reviews: `data/generated`

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

## Local source-grounded QCM generation

Generation schema version `1.0.0` is independent from canonical, chunk, and dataset schema
versions. Generation consumes only an explicitly selected, validated `AIReadyDataset`. It selects a
bounded, deterministic subset of generation-eligible chunks, records selected and excluded chunk
IDs, and sends only retained source text to an explicitly configured loopback Ollama endpoint.

Only QCM generation is enabled. Schemas for flashcards, summaries, learning objectives, true/false
questions, revision quizzes, and clinical cases are reserved data contracts and do not authorize or
provide working generation routes.

The private provider response identifies exactly one evidence span per question by selected
`chunk_id` and source-reference block identifiers. New Ollama output is constrained to exactly one
block ID per evidence entry, while materialization retains schema-compatible validation of existing
contiguous multi-block spans. The model does not supply the retained quotation. MedPlat resolves the
identifiers against the selected dataset chunk, slices the exact retained chunk substring, and
copies only the canonical source references in that span. Unknown, duplicate, reordered,
noncontiguous, excluded, ineligible, or unselected evidence identifiers fail; there is no fuzzy
quotation matching.

In `source_only` mode the supplied source is authoritative. Generated text must not correct,
replace, dispute, or reinterpret source values. Every medical number in the stem, every choice
including distractors, and the explanation must occur in the resolved evidence span; choice keys
are identifiers and are not scanned as claims. Source-correction language and unsupported numbers
are fatal. Low lexical overlap remains a nonfatal `needs_revision` warning and is not evidence for
or against medical correctness. A provider may return fewer than the requested questions only by
setting `insufficient_evidence=true` with a nonempty reason; a valid nonempty shortfall is retained
as `needs_revision`, while empty, undeclared, excessive, or contradictory counts fail.

Ollama configuration is explicit or environment-driven, has no API key, and is restricted to plain
HTTP on `localhost` or a literal loopback address. The implementation must never pull models,
install packages, contact cloud APIs, or send source text outside the computer. Tests use only a
deterministic mock provider and fixtures, with no sockets or source-library access.

Generation output is an atomic, protected directory under
`data/generated/<document-id>/qcm/<generation-id>/`. New questions are always `draft` and
`unreviewed`; no automatic process may mark content medically validated. Reviewed generations are
never overwritten. Accepted and rejected decisions are terminal, and exports include only
explicitly accepted questions.

Invalid attempts are retained atomically and append-only under `data/generated-failures` with the
exact local provider response, source selection, validation and grounding reports, and failure
metadata. They never contain `generated-content.json` and never appear under `data/generated`.

Grounding or structural failures may receive a bounded deterministic validation-guided retry,
configured separately from provider transport retries. Every invalid provider response must be
finalized as its own append-only failed attempt before retrying. The corrective request preserves
the source selection, dynamic chunk/block constraints, model, and source-only policy, but each
provider call targets only the first fatal ordinal and includes only that ordinal's exact retained
evidence span. It contains question identifiers, validation issue codes, unsupported numbers,
affected evidence-span IDs and text, and concise correction rules. It must never
change source values, add outside knowledge, or weaken validation. MedPlat deterministically keeps
untargeted questions and composes model-authored replacements without editing them. Successful
output is finalized only after the complete composed batch validates. Failed-attempt and successful-report
lineage records the parent attempt, validation retry sequence, supplied issue codes, and whether the
question count changed. Low lexical support remains a nonfatal, reviewable technical signal and
does not establish medical correctness.

Corrective retries are scoped sequentially to one fatal question ordinal in the materialized working
batch. Their private dynamic schema permits only that ordinal, its initial evidence chunk and block,
and the initial difficulty when the original distribution validated. An affected
question may select another valid single-block span within that chunk. Missing replacements require
an explicit shortfall; empty composed batches are invalid. Successful replacements remain in the
working batch across later retries, while untargeted questions remain unchanged. Evidence,
difficulty, or unrequested-ordinal scope violations are fatal and may not be silently repaired.
For an unsupported numeric claim, the corrective schema fixes the exact current evidence span and
constrains digits in the stem, all choice texts, and explanation to numeric tokens present in that
span. Choice identifiers are excluded. Numeric structured-output constraints supplement rather
than replace the fatal numeric validator and never authorize approximate or external values.
Targeted Ollama schemas are fully inlined and avoid `$ref`, `allOf`, and regex lookahead. Numeric
patterns reject Arabic-Indic, Persian, and full-width digit substitutions so constrained correction
output remains bounded to retained ASCII numeric tokens.
Corrective chat instructions include a compact private response skeleton because Ollama's `format`
schema is not visible as model-facing chat content. The skeleton must not duplicate source text or
invent evidence identifiers.
If a targeted correction reaches Ollama's output limit, persist the malformed attempt unchanged,
discard all of its content, and remove only the unresolved original draft question through the
explicit shortfall contract. Revalidate the remaining batch; never salvage a JSON prefix, accept a
partial correction, or finalize an empty or otherwise invalid batch.

## Folder-aware course coverage

Course schema version `1.0.0` is independent from canonical, chunk, dataset, and generation schema
versions. Course construction consumes only explicitly selected validated datasets and finalized
generation artifacts. It must not scan, reopen, or parse `pdfsrc`.

Preserve every source-relative folder segment and validated chunk section path as curriculum
taxonomy. Folder and section names guide navigation and planning only; they are never medical
evidence. Each knowledge unit references one immutable dataset chunk and retains its identity,
eligibility, size, exclusions, and source references.
The `qcm-substantive-chunk-v1` strategy inventories but excludes chunks shorter than 100 characters
from standalone QCM planning as context-only. This deterministic technical threshold is not a
medical-importance judgment.

The QCM coverage ledger records `pending`, `selected`, `covered_by_valid_qcm`, `needs_revision`,
`insufficient_for_qcm`, `failed`, or `excluded` for every unit. Draft and unreviewed QCMs are
`needs_revision`; only an explicitly human-accepted QCM may establish `covered_by_valid_qcm`.
Read-only planning selects only pending units in deterministic document/chunk order under explicit
budgets. It makes no Ollama request and writes nothing. Course artifacts under `data/courses` are
atomically finalized, immutable, Git-ignored, and must not mutate datasets or generation outputs.

## Mirrored local text-tree extraction

The `yahyaouisalsa` tree is a filtered read-only course source. `extract-text-tree` recursively
discovers and hashes every regular file, preserves its exact source-relative hierarchy and Unicode
path spelling, and plans output below `data/yahyaouisalsa-text`. Execution is deterministic and
sequential with `jobs=1`.

PDF, PPTX, DOCX, and TXT are supported. Legacy PPT, PPSX, images, and other formats are reported
without parsing. PDF extraction uses the explicitly configured local Docling artifacts and
PyMuPDF. OCR is never invoked by this workflow. An existing OCR derivative may be used only when
its source-relative path and SHA-256 match, derivative validation succeeds, and its quality outcome
is explicitly accepted.

Only `exported` and `exported_with_warnings` entries create UTF-8 `.txt` files. `requires_ocr`,
`empty`, `unsupported`, and `failed` entries create no placeholder output and remain visible in the
manifest and concise run reports. Resume requires validated headers, source identity, schema,
navigation separators, and output hash; existence alone is never success. Dry-run creates no
files, reports, manifests, derivatives, or directories and never initializes Docling.

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
- `medparse plan-generation`
- `medparse generate-content`
- `medparse validate-generation`
- `medparse review-content`
- `medparse export-question-bank`
- `medparse build-course-catalog`
- `medparse plan-course-qcm`
- `medparse extract-text-tree`
- `medparse prepare-course-text-tree`

Planning and dry-run modes must not parse documents, initialize models unnecessarily, perform OCR,
contact Ollama, or create processing or generation output.

Course-text preparation is a separate derived-text boundary. It reads only validated mirrored text
exports, writes clean and reconstructed artifacts outside the export root, preserves page/slide span
provenance in sidecars, and runs sequentially. Deterministic cleaning never changes medical facts or
numbers. Local reconstruction may reorganize only retained source wording. Unsupported additions,
model disagreements, missing images, and ambiguous numerical layout require source-preserving
fallback or human review. This route never generates questions, summaries, flashcards, cases,
answer keys, or student learning objectives.

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
- Treat `yahyaouisalsa` as read-only.
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
