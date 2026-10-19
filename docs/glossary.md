# Lesson glossary (Arabic lens)

One file per lesson: `web/content/<faculty>/<year>/glossary/<lesson_id>.json`, written by the
pipeline (step to be built: from the published lesson, pick the medical terms a student may not
know, give a simple French definition and an indicative Arabic translation). The browser never
calls an API.

```json
[
  { "term": "insuffisance cardiaque", "fr_definition": "Incapacité du cœur à …", "ar": "قصور القلب" }
]
```

- `term`: exactly as written in the lesson (case and accents ignored when matching; whole words).
- `fr_definition`: one plain sentence, no citation codes.
- `ar`: the usual Arabic medical term (Modern Standard Arabic), no transliteration.

Until the pipeline exists, `web/fixtures/glossary/` holds hand-written fixtures (committed) that
the loader uses when a lesson has no exported glossary. The UI labels every card "Traduction
indicative": translations are not reviewed by a doctor yet.
