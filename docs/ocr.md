# Explicit local OCR derivatives

## Architecture and immutability

OCR is a separate, explicit preprocessing stage. Opening or parsing a PDF never invokes OCR. The
original under `pdfsrc` is hashed before and after execution and is never used as OCRmyPDF's output.
OCRmyPDF and Tesseract run locally; no cloud OCR, external API, or vision model is used.

```text
original PDF -> eligibility -> OCR derivative -> validation -> quality gate
             -> accepted derivative -> Docling (OCR disabled) -> canonical variant -> chunks/dataset
```

Required tools are OCRmyPDF, Tesseract, qpdf, and Ghostscript. Supported explicit Tesseract codes are
`fra`, `eng`, `ara`, and `deu`; every requested installed pack is checked. Languages are never
inferred from filenames or sparse text.

## Commands and safe defaults

```bash
medparse check-ocr-environment --languages fra
medparse evaluate-ocr "pdfsrc/path/to/file.pdf"
medparse create-ocr-derivative "pdfsrc/path/to/file.pdf" --languages fra
medparse validate-derivative data/derived/<source-sha>/ocr/<id>/derivative.json
medparse parse-ocr-derivative data/derived/<source-sha>/ocr/<id>/derivative.json
```

Defaults are `--skip-text`, one job, 300-second timeout, PDF output, optimization level zero, and no
deskew, rotation, cleaning, downsampling, or force-OCR. `--force-ocr` and `--skip-text` are mutually
exclusive. Force-OCR rasterizes text/vector content and is never retried automatically.

## Eligibility

A low-text image page has at least one embedded image and fewer than 100 extractable characters. At
least half the pages meeting that condition is `ocr_required`; a smaller nonzero share is
`ocr_recommended`; no qualifying page is `ocr_not_needed`. Non-PDF, damaged, unreadable, or encrypted
input is blocked. These are technical rules, not medical semantics.

## Identity and output

The derivative ID is SHA-256 over schema `1.0.0`, original SHA-256, normalized OCR configuration,
and OCRmyPDF version. Configuration variants cannot overwrite one another:

```text
data/derived/<source-sha256>/ocr/<derivative-id>/
├── document-ocr.pdf
├── derivative.json
├── ocr-report.json
└── logs/ocrmypdf.log
```

Writers use a temporary sibling, validate models/files/hashes/page counts, recheck the original hash,
and rename only a complete result. Existing output is protected unless `--force` is explicit.

## Quality gate

The derivative must open, remain unencrypted, preserve page count and 1-based physical mapping, and
retain at least 90% of source text. Material improvement means at least 50 additional characters or
at least 25% more extractable text. Outcomes are `accepted`, `accepted_with_warnings`,
`no_material_improvement`, `degraded`, `invalid`, or `failed`. OCRmyPDF return code zero alone never
establishes acceptance. Rejected output remains reviewable but cannot be parsed into chunks/datasets.

## Provenance and generation eligibility

The original SHA-256 remains the logical document ID. Accepted derivatives receive a deterministic
processing-variant ID under `data/processed/<source-sha>/variants/<variant-id>/`. Canonical metadata
records the provenance chain, while every citation retains the original source-relative path and
physical page.

Chunks with empty text, uncaptioned unexplained assets, administrative-only content, or missing
references remain reviewable with `eligible_for_generation=false` and explicit reasons. Short
meaningful content remains eligible.

## Cleanup

Remove only the exact reviewed derivative directory or exact canonical variant directory. Never
remove or alter the corresponding original under `pdfsrc`. OCR remains explicit because derivative
quality must be inspected and OCR can change document representation even when execution succeeds.

## Controlled batches

Batch OCR is off by default. `--enable-ocr` requires explicit languages and always tries the safe
skip-text configuration first. A rejected safe derivative stops unless `--allow-force-ocr` is also
explicit. Existing derivatives are reused only after hash, page-count, quality, and original-source
provenance validation; configuration variants remain separate.
