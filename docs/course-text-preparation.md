# Course-text preparation

`medparse prepare-course-text-tree` converts validated mirrored text exports into two new immutable
derived views without modifying the exports or original course documents.

## Boundaries

The input is `data/yahyaouisalsa-text` and its validated `export-manifest.json`. The deterministic
tree is written to `data/yahyaouisalsa-clean`; contextual reconstruction is written to
`data/yahyaouisalsa-reconstructed`; reports live under
`data/reports/yahyaouisalsa-preparation/<run-id>`. Relative paths and Unicode filenames are retained
without normalization.

The route never opens original PDFs or Office documents, performs OCR, contacts a cloud service, or
generates questions, summaries, flashcards, quizzes, cases, answer keys, or student objectives.

## Stages

1. Validate each input file against the upstream manifest and metadata header.
2. Parse page, slide, document, table, and paragraph structure with character offsets.
3. Remove the extraction header from readable text, normalize conservative presentation defects,
   compact location markers, suppress only strict duplicates, and write a cleaning sidecar.
4. Classify every location and document as ready, noisy, partially reconstructable, image-dependent,
   unusable, or requiring human review.
5. Skip local reconstruction for already coherent mechanical results. Otherwise, send bounded natural
   sections sequentially to Gemma 3 with exact source span IDs.
6. Reject unsupported numbers, units, vocabulary, omissions, negation changes, modal changes, or
   unknown span references. Rejected sections retain the cleaned source.
7. After Gemma is unloaded, MedGemma may classify accepted transformations. It cannot rewrite text.
   Unsupported or ambiguous review falls back to the complete clean source and requires human review.
8. Validate UTF-8, hashes, containment, sidecars, resume identities, and source immutability.

## CLI

Full dry-run, with no writes or inference:

```bash
medparse prepare-course-text-tree \
  --input data/yahyaouisalsa-text \
  --clean-output data/yahyaouisalsa-clean \
  --reconstructed-output data/yahyaouisalsa-reconstructed \
  --report-output data/reports/yahyaouisalsa-preparation \
  --dry-run \
  --jobs 1
```

Full resumable execution:

```bash
medparse prepare-course-text-tree \
  --input data/yahyaouisalsa-text \
  --clean-output data/yahyaouisalsa-clean \
  --reconstructed-output data/yahyaouisalsa-reconstructed \
  --generator-model gemma3:12b \
  --reviewer-model auto-medgemma-4b \
  --location-markers compact \
  --context-budget 8192 \
  --temperature 0 \
  --seed 42 \
  --resume \
  --jobs 1
```

Use `--disable-model-reconstruction` for deterministic clean and source-preserving reconstructed
views only. Use `--disable-medgemma-review` to retain deterministic validation without the optional
second-model review. `--file` and `--limit` provide bounded diagnostics. `--resume` and `--overwrite`
are mutually exclusive, and values greater than one for `--jobs` are rejected.

## Provenance and validation

`<name>.cleaning.json` retains the export metadata, source and export hashes, raw/clean offsets,
location identities, metadata classification, deterministic transformations, duplicate decisions,
and readiness findings. `<name>.reconstruction.json` adds exact model tags and digests, Ollama and
prompt identities, per-section resume state, model transformations, reviewer classifications,
lexical audits, unresolved fragments, image-dependent locations, timings, retries, and final status.

Readable `.txt` files contain course text and explicit source-review markers only. Hashes and pipeline
metadata are confined to sidecars and manifests. File existence is never sufficient for resume:
source, configuration, model, prompt, schema, output, and sidecar identities must all validate.

## Missing content

The route never guesses an unseen image, lost superscript, dose, classification, flowchart edge, or
table cell. Insufficient extraction is retained and marked with one of:

```text
[Texte incomplet ou illisible dans la source extraite]

[Contenu probablement dépendant d’une image — consulter le document original]
```

These markers are presentation annotations, not medical content.
