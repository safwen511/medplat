# Course catalog classification (stage 1)

Stage 1 turns the mirrored text export of `library/<year>` into a lesson-level catalog that drives
reconstruction (stage 2), exercise generation (stage 3), and website navigation (stage 4).

## Inputs

- `data/<year>/catalog/inventory.json`: deterministic inventory built by `scripts/build_inventory.py`
  from `data/<year>/text/export-manifest.json` and the exported `.txt` files. It carries the
  normalized folder taxonomy, title hints, exact-duplicate detection, and a text-quality score.
- `data/<year>/catalog/digests/<certif>.md`: per-certif view of the inventory.
- Exported text under `data/<year>/text/`. Page and slide separators look like
  `===== PAGE 12 =====` and `===== SLIDE 4 =====`.

The read-only `library/<year>` source tree is never opened by this stage.

### Text quality

`text_quality_score` is the fraction of a file's words (3+ letters, accent-folded) that occur in at
least four documents of the corpus. Failed OCR of handwriting produces document-unique garbage, so:
`good` >= 0.85, `noisy` >= 0.65, otherwise `unusable`; `empty` means fewer than 50 words.

## Taxonomy

```
pole -> certif -> module -> lesson -> sources
```

- **Folder segments are hints, not truth.** Material-type folders (`Diapos`, `Poly`, `Résumé`, ...)
  are often wrong; classify each file by its content.
- **Official numbered slide decks** (`1 - ...`, `2 - ...`) define the lesson backbone and order.
- **A lesson is a canonical topic**, not a file. Slides, polycopié, and several student summaries of
  the same topic are sources of one lesson.

## Output: `data/<year>/catalog/certifs/<certif-slug>.json`

```json
{
  "schema_version": "0.1.0",
  "pole": "A",
  "certif": "Certificat de cardiologie",
  "certif_slug": "a-cardio",
  "modules": [
    {
      "module": "Cardiologie",
      "module_slug": "cardiologie",
      "lessons": [
        {
          "lesson_id": "a-cardio.cardiologie.insuffisance-cardiaque",
          "title": "Insuffisance cardiaque",
          "order": 12,
          "aliases": ["IC"],
          "sources": [
            {
              "path": "<source_relative_path from inventory>",
              "role": "official_slides | official_polycopie | student_summary | tips | tutorial | reference_book",
              "author": "Mohamed Abid | null",
              "coverage": "full | partial",
              "locations": "null for whole file, or 'PAGE 12-30' / 'SLIDE 4-20' for a part",
              "text_quality": "good | noisy | unusable | empty",
              "usable_for_reconstruction": true,
              "notes": "short, optional"
            }
          ]
        }
      ]
    }
  ],
  "assessments": [
    {
      "path": "...",
      "kind": "exam_paper | exam_with_answers | qcm_bank | qe_bank | clinical_cases | self_assessment",
      "session": "Mai 2023 | null",
      "has_answers": true,
      "lesson_ids": ["..."],
      "text_quality": "good",
      "notes": "short, optional"
    }
  ],
  "excluded": [{"path": "...", "reason": "duplicate_of:<path> | unusable_text | unsupported_format | empty | off_topic"}],
  "open_questions": ["short questions a human must decide"]
}
```

Rules:

- Every inventory record of the certif appears exactly once: as a lesson source, as an assessment,
  or in `excluded`. A multi-lesson compilation may appear as a source of several lessons, with
  `locations` per lesson.
- Exact duplicates go to `excluded` with `duplicate_of:<path>`.
- Unsupported formats (`.ppt`, `.ppsx`, images) stay visible as `excluded` with
  `unsupported_format`, but if their filename clearly names a lesson, create or reference the
  lesson so it is not lost (an official `.ppt` may be the only slide source).
- `usable_for_reconstruction` is false for `unusable`/`empty` text.
- Classification describes structure only; it makes no medical claim.
