# Document normalization

The structured ingestion schema is versioned independently of Docling. Version `1.0.0` is the
first canonical representation and is implemented by Pydantic models in
`ingestion.normalization.models`. Downstream systems must import those models, never Docling types.
This keeps citations, search, learning-content generation, and future database imports stable when
the source parser changes.

## Canonical model

`NormalizedDocument` owns source identity, a SHA-256 document ID, source-relative path, document
type, nullable language and title, navigation units, sections, tables, assets, metadata, and
processing information. A document contains:

- `NormalizedPage`: one physical PDF page, PowerPoint slide, or unpaginated Word document unit.
- `NormalizedBlock`: ordered title, heading, paragraph, list, table, figure, caption, formula, code,
  footnote, header, footer, or unknown content.
- `NormalizedSection`: explicit parser-provided heading hierarchy and ordered block references.
- `NormalizedTable`: stable zero-based cells with row/column offsets and spans.
- `NormalizedAsset`: figures, charts, and PDF embedded images, whether or not materialized.
- `SourceReference`: source path, location semantics, location number, block ID, coordinates, and an
  excerpt only when the parser supplied text.

Unknown metadata stays in JSON-compatible `metadata` dictionaries. The canonical schema never
serializes a Docling class.

## Location semantics

- PDF uses `location_type = page`. Every navigation unit has a physical page number starting at 1.
- PPTX uses `location_type = slide`. Every navigation unit has a slide number starting at 1; these
  are not described as PDF pages.
- DOCX uses one `location_type = document` unit. Its number and every block/table page association
  are null because Docling's Word backend does not provide reliable physical pagination.

Unavailable titles, captions, hierarchy, coordinates, language, and excerpts remain null. The
normalizer records warnings where the missing information affects navigation or interpretation.

## Docling mapping

Docling is the primary structured parser for `.pdf`, `.pptx`, and `.docx`. OCR, remote services,
picture description, code enrichment, and formula enrichment are disabled. Docling labels map to
canonical block types; provenance maps to source locations and bounding boxes; section-header levels
build the hierarchy; table cells map to stable cells; and pictures/charts map to asset records.
Docling object references may be retained as opaque strings in metadata, but no consumer needs a
Docling import.

PDF model initialization is lazy and local-only. The PDF adapter validates
`DOCLING_ARTIFACTS_PATH` (or the one-invocation CLI override) before initializing Docling's standard
pipeline, then passes that root through `PdfPipelineOptions.artifacts_path`. It also sets Hugging
Face and Transformers offline modes, so a normal parse cannot acquire missing models silently.
The pipeline enables `force_backend_text` so reliable native PDF text from Docling's PDF backend is
retained while layout remains Docling-controlled; PyMuPDF still never injects duplicate text.
PPTX and DOCX use a separate lazy Office converter and therefore remain usable when PDF artifacts
are not configured.

The non-OCR PDF quality check marks a page as a low-text image page when PyMuPDF finds at least one
embedded image and fewer than 100 extractable characters. Any such page gives the document
`requires_ocr`; zero canonical text (or zero backend-extractable text) is `unsuitable`; otherwise warnings produce
`ready_with_warnings` and warning-free output is `ready_for_chunking`. These statuses describe
technical extraction only, never medical correctness. Affected page numbers and counts are stored
under canonical metadata without changing schema version `1.0.0`.

Legacy `.pdf` inspection remains a separate read-only concern. `.ppt`, `.doc`, images, text files,
and other discovered formats remain visible there with `unsupported_for_parsing`; they are never
passed to the structured converter.

## PDF coordinate reconciliation

Docling supplies semantic reading order and is the normal source of canonical text. For each
Docling text block, reconciliation:

1. restricts candidates to the same physical page;
2. normalizes whitespace and case;
3. scores PyMuPDF text blocks with deterministic sequence similarity;
4. breaks equal scores by PyMuPDF reading order; and
5. accepts only a score of at least `0.82` with at least `0.05` separation from the runner-up.

Accepted coordinates use PyMuPDF's top-left physical-page coordinate system. If a match is missing
or ambiguous, the Docling block remains, coordinates are set to null, and a processing warning is
added. Page dimensions, page count, and embedded-image xref metadata come from PyMuPDF. This policy
preserves semantics without blindly duplicating Docling and PyMuPDF text.

There is one deterministic reliability fallback: if Docling supplies no text whatsoever for a
physical page but PyMuPDF exposes nonempty source text blocks, those blocks are retained once as
`unknown` canonical blocks with their exact source coordinates and an explicit warning. No heading,
paragraph type, section, caption, or hierarchy is inferred. The fallback never runs on a page that
already contains Docling text, so it cannot create a second copy.

## Output and atomicity

Each successful result is content-addressed:

```text
data/processed/<sha256>/
├── document.json
├── document.md
├── processing-report.json
├── assets/
└── previews/
```

The directories for assets and previews are empty unless the corresponding feature is requested.
PDF embedded images and PDF page previews are currently materializable; Office materialization is
reported as unsupported rather than guessed.

Writers reject output inside the source root. They build a same-filesystem temporary directory,
write every artifact, validate `document.json` and `processing-report.json`, and rename the complete
directory into place. Temporary output is removed after failure. Existing output is protected unless
`--force` is explicit; forced replacement temporarily retains the prior directory and restores it if
finalization fails.

Processing reports record non-sensitive model provenance: Docling version, parser backend, artifact
identifiers, local-only state, OCR state, and table-structure state. They do not include model
binaries or require exposing an absolute cache path.

Accepted OCR derivatives are parsed through the same Docling/PyMuPDF normalizer with Docling OCR
still disabled. The parser input is the derivative, but canonical identity, filename,
source-relative path, SHA-256, source references, and page numbers belong to the immutable original.
Metadata adds the derivative identity/hash, OCR configuration/version, quality outcome, identity
page mapping, and deterministic processing-variant ID. Variants are stored under
`data/processed/<original-sha>/variants/<variant-id>/`.

## Adding a parser

Implement `StructuredDocumentParser`, declare lower-case extensions, and register it with
`StructuredParserRegistry`. Keep format interpretation in the parser adapter and add a conversion
into the canonical models in the normalization layer. Discovery, hashing, validation, output, and
batch behavior should not change when a format is added.

## Batch reuse

The batch layer calls the canonical validator before reusing `document.json`. It checks document ID,
source SHA-256, source-relative path, technical suitability, and accepted derivative provenance when
present. A directory or JSON filename without those checks does not constitute normalized success.
