# Controlled library processing

The batch layer orchestrates existing inspection, parsing, normalization, OCR, chunking, and dataset
services. It does not implement a second parser or downstream data model. Sources remain immutable,
and every downstream artifact is validated before reuse.

## Architecture

```text
recursive discovery -> inspection/manifest validation -> deterministic plan
    -> existing-artifact validation -> sequential route execution
    -> atomic per-document state -> deterministic aggregate report
```

Plans contain only source-relative paths, hashes, metadata, routes, actions, and validated output
state. Absolute source paths are reconstructed from the configured input root at runtime and are not
stored per document.

## Commands

Plan without parsing, OCR, model initialization, or output creation:

```bash
medparse plan-library --input pdfsrc --limit 10 --selection representative \
  --enable-ocr --ocr-languages fra
```

Use `--write-plan` only when a persisted plan is wanted. Otherwise planning writes nothing.

Dry-run the same selection without document-processing writes:

```bash
medparse process-library --input pdfsrc --output data/processed \
  --derived-output data/derived --limit 10 --selection representative \
  --jobs 1 --resume --enable-ocr --ocr-languages fra --dry-run
```

Real execution requires a limit unless `--allow-full-library` is explicit. Limits above ten require
`--allow-large-batch`. This milestone supports only `--jobs 1`; larger values are rejected rather
than pretending unsafe concurrency exists.

## Planning and identity

Ordered selection sorts by normalized case-insensitive source-relative path, then stable extension
priority, then SHA-256. Representative selection chooses the first deterministic candidate from:

1. native-text PDF;
2. mixed PDF;
3. PPTX;
4. DOCX;
5. likely-scanned PDF;
6. unsupported format;
7. remaining ordered documents until the limit.

Unavailable categories are skipped. The batch ID hashes schema version, resolved roots, selected
paths and source hashes, OCR policy, force policy, selection mode, and manifest identity. Run IDs may
vary by start time; plan IDs do not.

When a manifest is supplied, its Pydantic schema and source root are checked. Each reused entry must
still match file size and SHA-256. Stale or invalid entries are re-inspected through the existing
inspection layer. Without a manifest, live inspection is used without automatically creating one.

## Routing

- PDF: normal local Docling parsing first. Suitable canonical output proceeds downstream. Output
  marked `requires_ocr` stops unless OCR is explicitly enabled.
- PPTX: native Docling path preserving slide references; no PDF conversion.
- DOCX: native Docling path with document locations and null physical pagination; no PDF conversion.
- Other extensions: `unsupported_for_parsing`, reported without parser execution.

Local Docling artifacts are preflighted only when an actionable PDF route exists. PPTX/DOCX-only
batches do not require PDF models. OCR tools and language packs are checked only when OCR is enabled
and a selected PDF may take an OCR route.

## OCR policy

OCR is disabled by default. When explicitly enabled, a technically unsuitable PDF uses the existing
safe skip-text derivative service first. Accepted derivatives continue through the existing
derivative parser. Rejected or no-material-improvement derivatives stop downstream processing.

Force OCR is attempted only with both `--enable-ocr` and `--allow-force-ocr`. It uses a distinct
configuration-derived identity and never overwrites the safe derivative. Rejected derivatives are
never reused as successful output.

## State and resume

State is stored under `data/reports/batches/<batch-id>/`:

```text
batch-plan.json
batch-state.json
batch-report.json
failures.json
skipped.json
documents/<sequence>-<sha-prefix>.json
```

Writes are atomic. Per-document statuses are `planned`, `running`, `succeeded`,
`succeeded_with_warnings`, `requires_ocr`, `skipped`, `unsupported`, `failed`, and `interrupted`.
Stages are:

```text
discovered -> inspected -> parsed -> canonical_validated
           -> derivative_created -> derivative_validated
           -> chunks_built -> chunks_validated
           -> dataset_built -> dataset_validated -> complete
```

Not every route uses derivative stages. On every new plan or resume, current artifacts are validated
again. Missing or invalid datasets resume from validated chunks; invalid chunks resume from the
canonical document; invalid provenance invalidates the candidate. Directory presence alone is never
success.

`--retry-failures` selects only failed or interrupted entries. The default maximum retry count is
one. Unsupported entries, OCR-required entries while OCR is disabled, and already-complete entries
are not retried. There is no retry loop.

## Completion and generation readiness

A document is complete only when canonical JSON, source identity, suitability, OCR provenance when
present, chunks, and dataset all validate. At least one chunk must be eligible for generation and
source-reference coverage must be nonzero. These checks indicate technical readiness only, never
medical validation.

## Failure isolation and reporting

With the default `--continue-on-error`, a concise per-document failure is persisted and unrelated
documents continue. `--stop-on-error` finalizes state and leaves later entries not started. Reports
contain routes, stages, paths, durations, counts, warnings, concise errors, retries, and eligibility
statistics. They never contain large extracted medical passages.

## Recovery, safe progression, and limitations

Resume with the same stable configuration. Use `--retry-failures` only after correcting a problem.
Use `--force` only for an intentional rebuild of selected document outputs; unrelated OCR variants
are preserved. Never delete or reorganize `pdfsrc`.

Review a dry run, process 10 documents with one worker, then review reports before progressing to 50,
100, or the full library. Full-library execution always requires explicit authorization.

This milestone intentionally provides sequential execution only. Parser timeout is recorded in the
typed configuration but cannot safely interrupt in-process Docling work; process-isolated workers are
needed before enforcing hard parser cancellation or concurrency. OCR timeout is enforced by the
existing OCR service.
