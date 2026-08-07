# Local source-grounded QCM generation

The generation layer consumes one explicitly selected, validated AI-ready dataset. It never opens
the original source document, canonical document, OCR derivative, or chunk file. Generation schema
version `1.0.0` is independent of the ingestion schemas.

## Flow and invariants

1. Validate the dataset and its embedded chunks.
2. Deterministically select unique, generation-eligible chunks within source budgets.
3. Construct a source-only prompt with chunk IDs, exact references, retained text, language,
   difficulty distribution, question type, count, and structured response schema.
4. Ask a configured local provider for a QCM draft containing evidence identifiers, not quotation
   text.
5. Resolve each question's one selected chunk and contiguous source-reference block span, then copy
   the exact retained chunk substring and only that span's canonical references.
6. Assign deterministic generation, question, and choice IDs.
7. Validate identities, eligibility, evidence spans, answers, every medical number, source-correction
   language, duplicates, and technical lexical support.
8. Atomically persist only draft/unreviewed content that passes required checks.
9. Require explicit human review before accepted-only export.

Only single-answer and multiple-answer QCMs are enabled. Other generated-content Pydantic models are
reserved contracts only. They have no CLI generation route.

Every QCM records the source document ID and SHA-256, selected chunk IDs, exact canonical source
references, verbatim evidence materialized by MedPlat, provider/model metadata, draft status, and
human-review state. The model is never trusted to author the retained quotation or invent canonical
references. An excluded, ineligible, nonexistent, unselected, or document-mismatched chunk fails
validation.

## Private provider contract and evidence resolution

The persisted generation schema remains version `1.0.0`; finalized `EvidenceCitation` remains a
`chunk_id` plus a materialized `quotation`. The private structured provider response uses:

```json
{
  "questions": [
    {
      "topic": "...",
      "difficulty": "easy|medium|hard",
      "stem": "...",
      "choices": [{"key": "a", "text": "..."}],
      "correct_choice_keys": ["a"],
      "explanation": "...",
      "evidence": [{
        "chunk_id": "<sha256>",
        "source_reference_block_ids": ["block-000001"]
      }]
    }
  ],
  "insufficient_evidence": false,
  "shortfall_reason": null
}
```

Each question requires exactly one evidence entry. Block IDs must exist in the selected chunk, be
unique, preserve canonical source-reference order, and occupy consecutive positions in that order.
The current Ollama provider schema restricts new model output to exactly one block ID per evidence
entry, which makes contiguity structural rather than model-interpreted. The materializer retains
multi-block contiguous-span support for schema compatibility and validation of existing artifacts.
MedPlat locates each retained source excerpt sequentially in the chunk text and slices from the
first excerpt start through the last excerpt end, preserving intervening retained separators. Only
boundary whitespace trimmed during deterministic chunk construction is ignored while locating an
excerpt; the quotation itself is always an exact slice of retained chunk text. Unknown, duplicate,
reordered, excluded, or noncontiguous identifiers are rejected. No fuzzy matching is performed.

For each request, MedPlat also derives the JSON schema supplied through Ollama's `format` field.
The `ProviderEvidenceDraft` definition is a deterministic `oneOf` with one object branch per
selected chunk. Each branch has this shape:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["chunk_id", "source_reference_block_ids"],
  "properties": {
    "chunk_id": {"type": "string", "enum": ["<this-selected-chunk-id>"]},
    "source_reference_block_ids": {
      "type": "array",
      "minItems": 1,
      "maxItems": 1,
      "items": {
        "type": "string",
        "enum": ["<only-block-ids-from-this-chunk>"]
      }
    }
  }
}
```

Branches are ordered by chunk ID, null block IDs are omitted, and block enums preserve retained
source-reference order. Planning fails if any selected chunk has no usable block ID. Consequently,
a chunk from one branch cannot be combined with a block belonging to another branch. The schema is
only an output constraint: materialization independently retains all eligibility, identifier,
ordering, contiguity, and exact-span checks and never repairs a provider mismatch.

The provider may return fewer than requested only when the response is nonempty,
`insufficient_evidence` is true, and `shortfall_reason` is nonempty. That explicit shortfall creates
an `insufficient_grounded_questions` warning and marks returned questions `needs_revision`. More
than requested, an undeclared or contradictory shortfall, and every empty batch are fatal.

## Validation-guided retry

Validation-guided retries are separate from Ollama HTTP transport retries. The environment variable
`MEDPARSE_OLLAMA_VALIDATION_RETRY_COUNT` or CLI option `--validation-retry-count` controls the
bounded number of targeted corrective provider calls; the default is one. `--retry-count` continues
to control only transport attempts inside each provider call.

After an invalid provider response, MedPlat atomically finalizes that exact response. A materialized
batch with question-specific fatal validation issues may then receive a targeted retry. The retry
keeps the original source selection and model configuration but sends one fatal question ordinal
per provider call using a compact request-specific correction schema. It sends only deterministic
correction data:

- question ordinal or stable temporary key;
- validation issue codes;
- unsupported numbers, when reported;
- the affected chunk and source-reference block IDs plus their already-retained exact evidence
  text, when materialization succeeded; and
- concise instructions to return only the requested question replacements.

The previous answer text, unrelated selected chunks, and unrelated failure metadata are not added.
The model is not asked to defend its answer. It may remove unsupported
numeric distractors, substitute nonnumeric distractors grounded in the same evidence, align wording
to the evidence, remove correction language, or declare a valid grounded shortfall. It may not
change source values, add outside medical knowledge, or change evidence merely to rescue an
unsupported claim. The private correction response is:

```json
{
  "question_replacements": [
    {
      "question_ordinal": 1,
      "replacement": {"...": "complete ProviderQCMQuestionDraft"}
    }
  ],
  "insufficient_evidence": false,
  "shortfall_reason": null
}
```

Its dynamic schema has exactly one requested ordinal branch. The branch constrains the ordinal, the
original evidence chunk and block, and—when the initial distribution was valid—the original
difficulty. Mock providers can bypass the schema, so materialization independently checks
the same invariants. Missing requested replacements require an explicit nonempty shortfall and are
removed deterministically; an empty composed batch is forbidden.

MedPlat composes accepted replacements into the last materialized working batch. Questions not
targeted by a fatal issue remain byte-for-byte unchanged, and a successful replacement from an
earlier retry remains in place during later retries. This is deterministic assembly, not editing of
model-authored medical text. The complete composed batch then passes every normal validator.

For `unsupported_numeric_claim`, the targeted schema is additionally bound to the exact current
evidence span. MedPlat extracts the same exact numeric tokens used by validation and adds a JSON
Schema pattern to the replacement stem, every choice text, and explanation. Digits are permitted
only when they form a retained evidence token; choice keys are outside this constraint. The model
may therefore use evidence-supported numbers or nonnumeric grounded distractors, but cannot emit a
new numeric distractor through structured output. The ordinary `unsupported_numeric_claim` check
remains the final backstop, and explicit shortfall remains available when no grounded replacement
can be produced.

The targeted schema is fully inlined for Ollama constrained decoding. It avoids `$ref`, `allOf`,
and regex lookahead so an unsupported schema composition cannot degrade into unconstrained text
generation. Its numeric patterns also reject Arabic-Indic, Persian, and full-width digit
substitutions; retained numeric tokens remain ASCII-exact and the normal validator remains
authoritative.

Because the Ollama `format` schema is not itself visible as chat content, the final corrective
message also carries a compact field-name skeleton. It requires ASCII JSON integer syntax and
explicitly rejects legacy shapes such as `options`, `answers`, `correct_answer`, `source_id`, or a
second full request object. The skeleton itself duplicates no source text; the only source passage
in the corrective prompt is the compact exact evidence record for its one target ordinal.

Every failed retry is append-only. Failure reports and a successful retry's generation report add
the following backward-compatible lineage fields while retaining generation schema version
`1.0.0`:

```json
{
  "parent_attempt_id": "<sha256-or-null>",
  "validation_retry_sequence": 1,
  "retry_issue_codes": ["unsupported_numeric_claim"],
  "question_count_changed": false
}
```

If a targeted correction exhausts Ollama's configured output budget (`done_reason=length`) before
forming one valid JSON object, MedPlat first persists that exact malformed attempt. It never parses
a prefix, salvages a partial question, or copies any of its medical text. The unresolved original
draft question is then removed under the explicit shortfall contract and the remaining working
batch is revalidated. A later fatal ordinal may consume the next bounded validation retry. If the
remaining batch validates, it is finalized as `needs_revision` with
`insufficient_grounded_questions`; the successful raw-provider artifact remains the last
successfully materialized provider response, while every output-limited correction remains only in
the append-only failure tree. An empty batch or remaining fatal issue still fails.

The initial attempt has sequence zero and no parent. Each corrective attempt names the immediately
preceding failed attempt. Timing and provider transport-attempt metadata remain recorded in the
existing fields. If transport retries are exhausted, MedPlat persists that provider failure and
does not consume another validation-guided retry. No successful directory is created until the
complete composed batch has no fatal validation issue. Nonfatal signals such as `low_lexical_support`
remain visible as `needs_revision` and require human review; they do not prove medical error or
correctness.

An affected question may move only to another single-block span inside its initial chunk.
Unexpected ordinals, evidence-chunk movement, or constrained difficulty changes fail with
`retry_unrequested_question_change`, `retry_evidence_chunk_changed`, or
`retry_difficulty_changed`. Prior answer text is not copied into corrective messages.

## Source-only checks

The supplied source is authoritative: the provider must not correct, replace, dispute, or
reinterpret its values. Phrases such as “likely a typo”, “probable typo”, “should be interpreted
as”, “likely an error”, “erreur probable”, “coquille probable”, and “doit être interprété” are fatal
in stems, choices, or explanations. If the evidence says `50%`, generated content must retain
`50%`.

Numeric validation scans the stem, every choice including distractors, and the explanation. Each
medical number must occur in the exact MedPlat-materialized evidence span. Choice keys and
alphabetic labels such as A, B, C, and D are not scanned. Unsupported numeric claims remain fatal;
there is no approximate evidence acceptance. Low lexical support remains a nonfatal
`needs_revision` warning and does not establish medical correctness.

Lexical overlap and exact quotation checks measure technical source support. Low overlap marks
content `needs_revision`; it does not prove or disprove medical correctness. Content is never
automatically marked medically validated.

## Commands

`plan-generation` validates and displays selection, counts, references, estimates, endpoint, model,
and proposed destination. It calls no provider and writes nothing.

`generate-content` requires an explicit dataset, model, content type, and count. `--dry-run` has the
same no-call/no-write behavior as planning. Real output is protected from overwrite under:

```text
data/generated/<document-id>/qcm/<generation-id>/
  request.json
  selected-sources.json
  raw-provider-response.json
  generated-content.json
  grounding-report.json
  validation-report.json
  generation-report.json
```

`validate-generation` revalidates against the recorded dataset. `review-content` records an explicit
terminal decision. `export-question-bank` creates a protected JSON export containing only accepted
questions.

## Failed attempts

A failed provider response, structured parse, materialization, provenance check, or grounding check
never creates a successful generation directory. Diagnostics are finalized atomically and
append-only under:

```text
data/generated-failures/<document-id>/qcm/<generation-id>/<attempt-id>/
  request.json
  selected-sources.json
  raw-provider-response.json
  validation-report.json
  grounding-report.json
  failure-report.json
```

The response record retains the exact HTTP response text when one exists, plus the separately parsed
provider envelope. Invalid attempts never contain `generated-content.json`. The CLI reports only the
failure path and concise issue codes; it does not print source text.
