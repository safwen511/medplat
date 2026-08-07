# Folder-aware courses and QCM coverage

Course schema version `1.0.0` is independent of canonical, chunk, dataset, and generation schemas.
The course layer consumes only validated AI-ready datasets and existing finalized generation
artifacts. It never scans or parses `pdfsrc`.

## Course taxonomy

Every source-relative parent-directory segment is preserved in `folder_path`. Section headings from
the validated chunk are appended to form `taxonomy_path`. Folder and section labels organize the
course, but they are not medical evidence and may never support a generated claim.

One `KnowledgeUnit` references one existing dataset chunk. It records stable identities, taxonomy,
size, eligibility, source references, and exclusion reasons without altering the chunk or dataset.
Course identity is a deterministic digest of the course schema version, explicit name, source-root
folder, knowledge-unit strategy, document identities, dataset hashes, and source-relative paths.

The initial `qcm-substantive-chunk-v1` strategy treats generation-eligible chunks shorter than 100
characters as context-only rather than standalone QCM units. They remain inventoried with the
explicit `qcm_unit_below_minimum_characters:100` exclusion reason. This technical gate prevents
titles and isolated headings from consuming a question slot; it does not assess medical importance.

## Coverage ledger

`qcm-coverage.json` records one state per knowledge unit:

- `pending`: eligible and not yet represented by a finalized QCM artifact;
- `selected`: reserved for a finalized execution plan;
- `covered_by_valid_qcm`: represented by an explicitly human-accepted QCM;
- `needs_revision`: represented only by draft or revision-required QCMs;
- `insufficient_for_qcm`: a bounded attempt established an explicit shortfall;
- `failed`: generation or human review rejected the available QCM; or
- `excluded`: the source dataset marked the chunk generation-ineligible.

Existing finalized QCM artifacts seed the ledger. Draft/unreviewed questions count as
`needs_revision`, never as completed coverage. Only accepted human review can produce
`covered_by_valid_qcm`. Folder names, selected prompt inclusion, and technical validation alone do
not establish coverage or medical correctness.

## Artifacts

```text
data/courses/<course-id>/
  course-catalog.json
  knowledge-units.json
  qcm-coverage.json
```

The directory is finalized atomically and is immutable. It references existing datasets and
generation IDs; it does not modify them. `data/courses/` is Git-ignored.

Build a single-document course catalog:

```bash
medparse build-course-catalog \
  data/processed/<document-id>/datasets/ai-ready-dataset.json \
  --course-name "Cancer du rein"
```

Plan the next five QCMs from untouched eligible units:

```bash
medparse plan-course-qcm data/courses/<course-id> \
  --count 5 --max-source-characters 12000 --max-source-tokens 3000
```

Planning is read-only. It selects only `pending` units in deterministic document/chunk order,
records exact chunk and source references, honors source budgets, makes no provider request, and
writes nothing. Course-plan execution and other content types are separate later milestones.
