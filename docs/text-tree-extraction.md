# Mirrored text-tree extraction

`medparse extract-text-tree` creates a faithful UTF-8 plain-text view of an explicitly selected
local document tree. It is independent of canonical documents, chunks, datasets, generated QCMs,
and course artifacts.

## Safety and scope

The input tree is read-only. Discovery does not follow symlinks, every regular file is hashed with
incremental SHA-256, and output and report roots must be disjoint from the source. Relative path
segments and Unicode spelling are retained exactly; paths are not Unicode-normalized. A complete
post-run snapshot is compared with the initial snapshot.

Supported formats are PDF, PPTX, DOCX, and TXT. Legacy `.ppt`, `.ppsx`, images, and other formats
are reported as unsupported and skipped. Execution accepts only `--jobs 1` and continues after an
individual failure.

Only `exported` and `exported_with_warnings` sources create `.txt` files. `requires_ocr`, `empty`,
`unsupported`, and `failed` sources create no placeholder file.

## Planning and execution

Run a zero-write full-tree plan:

```bash
medparse extract-text-tree \
  --input yahyaouisalsa \
  --output data/yahyaouisalsa-text \
  --report-output data/reports/yahyaouisalsa-text \
  --docling-artifacts-path data/docling-models \
  --resume --jobs 1 --dry-run
```

Dry-run performs deterministic discovery and hashing plus the minimum PyMuPDF PDF inspection needed
to identify unreadable, encrypted, or zero-text PDFs. It does not initialize Docling, parse Office
content, invoke OCR, create directories, or write manifests or reports.

After reviewing the plan, the corresponding real command is:

```bash
medparse extract-text-tree \
  --input yahyaouisalsa \
  --output data/yahyaouisalsa-text \
  --report-output data/reports/yahyaouisalsa-text \
  --docling-artifacts-path data/docling-models \
  --resume --jobs 1
```

`--limit` selects the first deterministic supported candidates after complete discovery.
`--extensions` is repeatable and also accepts comma-separated values. `--overwrite` regenerates all
selected successful outputs and cannot be combined with `--resume`.

## Extraction behavior

- PDF is extracted page by page through the existing local-only Docling parser and PyMuPDF
  reconciliation. Physical page separators are always retained. A zero-text PDF is
  `requires_ocr` unless a derivative has the exact relative path and SHA-256, passes derivative
  validation, and has an explicitly accepted quality outcome. OCR is never run automatically.
- PPTX uses Docling Office parsing and retains slide order, titles, content, lists, tables, and
  reliably exposed speaker notes. Office parsing does not initialize PDF models.
- DOCX uses Docling Office parsing and retains document reading order, headings, paragraphs, lists,
  captions, and tables. It does not invent physical page numbers.
- TXT is decoded as UTF-8 or a BOM-declared Unicode encoding, normalized to UTF-8, and has only line
  endings normalized. Invalid unknown encodings fail explicitly.

Tables are rendered as deterministic pipe-separated rows at their retained reading position.
Medical text is never summarized, interpreted, corrected, or supplemented.

## Output and state

Successful output mirrors the source path and changes only its final extension:

```text
yahyaouisalsa/Pole A/Urologie/Cancer du rein.pdf
data/yahyaouisalsa-text/Pole A/Urologie/Cancer du rein.txt
```

If supported files in one folder map to the same name, every member receives a deterministic
`__<extension>` suffix; a short source hash resolves any remaining ambiguity.

Each text export starts with the required ordered metadata header. Before atomic finalization it is
validated for UTF-8, metadata identity, schema version, source path and SHA-256, nonempty extracted
text, navigation separators, and root containment.

The state manifest is:

```text
data/yahyaouisalsa-text/export-manifest.json
```

Run reports are written to:

```text
data/reports/yahyaouisalsa-text/<run-id>/
  run-report.json
  failures.json
  unsupported.json
  requires-ocr.json
  skipped.json
```

The run ID and export identities are deterministic hashes of the schema, configuration, ordered
source identities, and output plan. Report timestamps and duration describe the execution and are
not identity inputs.

With `--resume`, an existing output is reused only when its source-relative path and SHA-256,
manifest identity, schema header, metadata header, navigation separators, and output SHA-256 all
validate. A stale or corrupt output is regenerated atomically. Directory or file existence alone
never represents success.
