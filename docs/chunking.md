# Semantic document chunking

Milestone 3 consumes only a schema-valid canonical `document.json`. It never imports Docling,
PyMuPDF, or raw-format parsers and never reads PDF, PPTX, or DOCX source files.

## Algorithm and boundary priority

Canonical blocks are ordered by reading order, navigation-unit order, and stable block-ID fallback.
Repeated administrative furniture is excluded from chunk construction without changing the
canonical document. The builder then applies these boundaries:

1. retain complete sections when they fit the soft maximum;
2. use canonical subsections as separate structural units;
3. split large units between blocks;
4. split oversized paragraphs at sentence, line, then word boundaries only as a last resort;
5. keep tables, formulas, captions, figures, and individual list items atomic;
6. keep figure/table captions and an immediate explanatory paragraph with their object when they
   fit;
7. keep short lists together and split long lists only between items;
8. merge a small trailing chunk only with a related neighbor from the same structural unit.

Top-level sections are never combined merely to reach a size target. PPTX slides remain distinct.
A PDF section may span pages and retains every reference. DOCX uses `location_type = document` with
null page values.

When canonical sections are absent, headings become provisional boundaries and page/slide
continuity limits grouping. Such chunks carry weak structural confidence and the collection records
a warning. Content that still lacks placement becomes `orphan_content`.

## Sizing

| Setting | Characters |
|---|---:|
| Target | 4,000 |
| Soft maximum | 6,000 |
| Hard maximum | 10,000 |
| Minimum useful | 250 |
| Context per side | 500 |

Character count is authoritative. Estimated tokens use `ceil(character_count / 4)` and are marked
approximate; no tokenizer dependency is used. An indivisible table, formula, list item,
figure/caption group, or other atomic block may exceed the hard maximum. It remains intact, gets an
`atomic_oversize` marker, and records a warning.

## Deterministic identity and text normalization

Chunk IDs are SHA-256 hashes of chunk schema version, document ID, canonical/provisional section
identity, ordered block IDs, chunk type, stable source-order index, and paragraph-fragment index.
No UUID enters a document-derived identifier.

Normalized text uses Unicode NFC, normalized line endings, collapsed horizontal whitespace,
trimmed lines, and stable blank-line paragraph separators. It does not translate, case-fold, remove
accents, reinterpret abbreviations, alter formulas, or rewrite medical terminology. Original text
remains separate. Unchanged canonical input and configuration produce the same IDs, ordering, text,
associations, and derived timestamps.

## Context construction

Each chunk records exact document title, canonical section path, parent headings, local heading, and
at most 500 characters of preceding or following source text. Neighbor context is attached only
within the same canonical section or same reliable unsectioned location. Context remains metadata,
is not copied into chunk text, and is never generated or summarized.

## Tables, figures, formulas, and lists

Tables prefer explicit table-block references, then exact captions, then a unique same-location
chunk. Structured rows, columns, spans, headers, IDs, and source references remain available; chunk
text contains only a deterministic readable rendering.

Assets prefer explicit figure-block IDs, exact captions, reliable spatial proximity with matching
coordinate origins, then a unique same-location chunk. The builder never attaches an asset to every
chunk on a page. Ambiguous assets stay in the asset pool and are listed as unassociated. No OCR,
vision analysis, or medical image interpretation occurs.

Formulas remain unchanged in `formula_context` chunks. Lists retain item order and never split an
individual item. Captions stay with figures or tables only when canonical relationships and reading
order support it.

## Repeated furniture and exact duplicates

Repeated canonical headers/footers and administrative page-number furniture are excluded by
default. Every exclusion records block ID, reason, normalized-text hash, and source reference.
Substantive footnotes remain.

Exact duplicate detection compares normalized chunk-text SHA-256 hashes only. The first source-order
chunk remains canonical. Duplicate relationships retain removed chunk IDs and every duplicate source
reference; the canonical chunk also carries those references. There is no fuzzy, semantic,
embedding-based, or cross-document deduplication.

## Output formats and atomicity

`chunks.json` is a validated `ChunkCollection`. `chunks.jsonl` contains exactly one validated
`DocumentChunk` JSON object per non-empty line without a wrapping array. `chunks.md` is a review
view. `chunking-report.json` contains configuration, statistics, exclusions, duplicates,
unassociated IDs, warnings, errors, and output paths.

`ai-ready-dataset.json` packages all validated chunks, full canonical table and asset pools,
unassociated objects, exclusions, exact duplicates, statistics, configuration, schema versions, and
provenance. It contains no questions, answers, summaries, diagnoses, embeddings, or model output.

Each chunk has backward-compatible `eligible_for_generation` and
`generation_exclusion_reasons` fields. Empty normalized text, an uncaptioned figure without
explanation, administrative-only content, or missing source references causes exclusion. Short text
alone does not. Excluded chunks remain in review output and statistics. An OCR canonical variant
whose quality is not `accepted` or `accepted_with_warnings` is rejected before chunk construction.

Builders write sibling temporary directories, validate every JSON model and JSONL line, then rename
complete directories into place. Failure removes temporary output. Forced replacement preserves and
restores prior successful output if finalization fails. Existing output is protected by default;
canonical files and source documents are never modified.

## Consumption and known limitations

Future generators should select chunks by deterministic ID, resolve structured tables/assets by
linked IDs, and preserve source references in draft output. They must not turn short neighbor context
into uncited evidence or create ungrounded medical claims.

Chunking uses document structure, not medical semantics. Canonical files without sections have weak
hierarchy. Captions, coordinates, or relationships missing upstream remain missing. Exact duplicate
detection does not find paraphrases, and unassociated objects are deliberately not guessed.

Batch resume validates both `chunks.json` and its canonical document identity before reuse. Dataset
completion additionally requires at least one eligible chunk and nonzero source-reference coverage;
otherwise the document remains reviewable but is not marked generation-ready.
