# Local Docling PDF models

## Why they are required

MedPlat uses Docling as the primary PDF structure parser and PyMuPDF for physical-page enrichment.
Docling's standard PDF pipeline needs layout-model artifacts and, because table-structure recognition
is enabled, the accurate TableFormer artifacts. These files are not Python package data.

The installed and verified command belongs to Docling 2.117.0:

```bash
docling-tools models download \
  --output-dir "$PWD/data/docling-models" \
  layout tableformer
```

This command downloads no OCR model. The destination is explicit, outside `pdfsrc`, and Git-ignored.
It is never run by tests, application startup, environment diagnostics, or document parsing.

## Configuration and precedence

Set an absolute artifact root:

```bash
export DOCLING_ARTIFACTS_PATH="$PWD/data/docling-models"
```

For one invocation, `parse-document --docling-artifacts-path PATH` takes precedence over the
environment. There is no third implicit source: MedPlat does not search arbitrary global caches and
does not fall back to downloading.

The configured path is expanded with `Path.expanduser()` and resolved before use. It must be the
parent containing these official repository folders:

```text
docling-model-artifacts/
├── docling-project--docling-layout-heron/
│   ├── config.json
│   ├── preprocessor_config.json
│   └── model.safetensors
└── docling-project--docling-models/
    └── model_artifacts/tableformer/accurate/
        ├── tm_config.json
        └── tableformer_*.safetensors
```

MedPlat checks that every listed required file exists and is nonempty before initializing the PDF
pipeline. The downloaded `fast` TableFormer variant may also be present, but the configured pipeline
uses `accurate`.

## Offline behavior and diagnostics

Normal PDF parsing passes the validated root explicitly to `PdfPipelineOptions.artifacts_path`,
disables Docling remote services and external plugins, and sets Hugging Face and Transformers
offline modes (including the already-imported Hugging Face process flag) before model initialization.
OCR, picture description, picture classification, chart
extraction, code enrichment, and formula enrichment are disabled. Table-structure recognition is
enabled. Native backend text is forced through Docling's own standard pipeline to avoid losing
extractable PDF text; PyMuPDF enrichment does not create a second copy.

For slide-like PDFs where Docling emits no text for an entire physical page despite reliable PDF
backend text, normalization retains PyMuPDF's exact text blocks once as `unknown` blocks with real
coordinates and a warning. This narrow fallback invents no semantic structure and is disabled for
every page where Docling supplied any text.

Run the doctor without parsing or downloading:

```bash
medparse check-environment
```

It checks Python and required package versions, configuration, model structure, local-only mode,
OCR state, output writability, and the read-only source policy. Exit status is zero only when the PDF
environment is ready.

Common categories:

| Category | Meaning | Remediation |
|---|---|---|
| `docling_artifacts_not_configured` | No CLI path or environment value | Set `DOCLING_ARTIFACTS_PATH` |
| `docling_artifacts_path_missing` | Configured path does not exist | Correct the path or run the official download |
| `docling_artifacts_invalid` | Path is a file or not an official artifact root | Point to the directory containing both repository folders |
| `docling_required_model_missing` | Required configuration or weights are absent/empty | Re-run the official command for `layout tableformer` |
| `docling_model_initialization_failed` | Valid-looking files could not initialize | Check compatibility with installed Docling 2.117.0 |
| `pdf_parse_failed` | Models initialized but the source conversion failed | Inspect the concise error and source readability |
| `ocr_required_but_disabled` | One or more image pages lack enough extractable text | Defer the document until a later approved OCR milestone |

PPTX and DOCX use Docling's native Office backends through a separate lazy converter. They do not
need the PDF layout or TableFormer artifacts, which is why they may work while PDF readiness fails.

## Safe verification

Inspect one selected PDF without structured parsing:

```bash
medparse inspect-document "pdfsrc/path/to/selected.pdf"
```

After the doctor succeeds, parse only that selected source:

```bash
medparse parse-document "pdfsrc/path/to/selected.pdf" --output data/processed
medparse validate-output data/processed/<sha256>/document.json
```

Never use `--force` unless a matching output is known to be incomplete or intentionally replaced.
OCR remains disabled. A `requires_ocr` result is technically incomplete and must not be described as
ready for generation.

Generated results are content-addressed. To remove one generated result without touching its source,
delete only the exact reviewed directory under `data/processed/<sha256>/`. Never remove or reorganize
anything under `pdfsrc`.

Local OCR derivatives are produced separately by OCRmyPDF/Tesseract as documented in
[ocr.md](ocr.md). Docling never performs a second OCR pass: when parsing an accepted derivative,
`PdfPipelineOptions.do_ocr` remains false and the same local layout/TableFormer artifacts are used.
