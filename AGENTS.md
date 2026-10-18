# MedPlat

MedPlat turns per-year medical course libraries (Faculté de Médecine de Sfax) into
source-grounded lessons and exercises for a student revision website. The project owner is an
engineer, not a physician: every generated medical text stays a draft until a human medical
reviewer accepts it.

## Layout

- `library.toml`: configured years (`dcem1` = 3e année, `dcem2` = 4e année) and the Docling
  model path. Add a year by adding an entry; code resolves paths through `ingestion.library`.
- `library/<year>/`: original course files. Read-only.
- `data/<year>/`: everything derived — `text/`, `text-office/`, `office/`, `ocr/`, `reports/`,
  `catalog/`, `lessons/`. `data/models/docling/` holds local Docling artifacts.
- `src/ingestion/`: extraction library and the `medparse` CLI.
- `scripts/`: catalog and lesson stages (`build_inventory`, `merge_catalog`,
  `convert_office`, `validate_lesson`, ...), each taking `--year`.
- `web/`: the student website (Next.js); `supabase/migrations/`: its database schema as SQL.
- `docs/`: stage specifications. Tests in `tests/`.

`library/` and `data/` are Git-ignored and must never be committed. The former local-Ollama
pipeline is archived under the Git tag `archive/local-pipeline`; do not restore it.

## Stages

1. **Extract** (`medparse extract-text-tree --year <id>`): mirrors every file of
   `library/<year>` to `data/<year>/text` with validated headers and `===== PAGE n =====` /
   `===== SLIDE n =====` separators. PDF via local Docling + PyMuPDF; PPTX via Docling Office;
   legacy `.ppt`/`.ppsx` via LibreOffice `.pptx` derivatives and `.doc`/`.docx` via LibreOffice PDF
   derivatives, so Word content has citable pages (`scripts/convert_office.py`, output in
   `text-office/`, preferred by the inventory). Unsupported, empty, and OCR-needing files stay visible in
   the manifest with no placeholder output. Sequential, resumable, dry-run first.
2. **Catalog** (`scripts/build_inventory.py`, then classification into
   `data/<year>/catalog/certifs/*.json`, then `scripts/merge_catalog.py`): every file is classified
   exactly once — as a lesson source with a role (`official_slides`, `official_polycopie`,
   `student_summary`, `tips`, `tutorial`, `reference_book`), an assessment, or an exclusion with a
   reason. Folder names guide classification; they are never medical evidence. See
   `docs/catalog-classification.md`.
3. **Reconstruct** (`data/<year>/lessons/<lesson_id>/lesson.md` + `lesson.json`): rebuild a lesson
   from its catalogued faculty sources only, in the faculty's course structure (definition and
   epidemiology, etiology, physiopathology, diagnosis, treatment). Content rarely tested in past
   exams is folded, never deleted; sections tested by the catalogued assessments are marked
   high-yield. Reference books are not reconstruction sources unless the owner decides otherwise;
   they serve the chatbot. Figures from cited source pages may illustrate a lesson unit.
4. **Generate** exercises from validated lessons. Authorized types: QCM (single answer), QRM
   (multiple answers), vrai/faux, fill-in-the-blank, matching, ordering, categorizing, numeric,
   short answer, and image-based items. Default budget about 10 items per lesson, weighted toward
   high-yield sections. Each item carries a 3-step hint ladder (what is asked, what to eliminate,
   the rule) and a cited explanation.
5. **Website** (`web/`): Next.js on Vercel. Lessons and exercises are pre-generated static
   content; user data (profile, attempts with timing, lesson progress, highlights, error reports)
   lives in Supabase Postgres behind row-level security, with Google sign-in through Supabase
   Auth. Faculty is part of every route and record (`/<faculty>/<year>/...`) so further faculties
   can be added. One server-side chatbot route grounded in the current lesson. Mini-games reuse
   the exercise pool.

## Source-grounding rules (reconstruction, generation, chatbot)

- Source-only: reorganize and rephrase retained source content; never add outside medical facts,
  correct, or reinterpret source values.
- Precedence: `official_slides` > `official_polycopie` > `student_summary`/`tips`/`tutorial`;
  `reference_book` only where the catalog marks it as a lesson source.
- Every content unit (paragraph, list item, table row) carries citations such as
  `[S1 p.10; S2 p.270-271]` or `[S3 slide 5]` that resolve to existing source pages.
- Every number must occur on a cited page (unit-aware). `scripts/validate_lesson.py` enforces
  this; a lesson or exercise that fails validation is never published.
- Conflicts between sources go in a "Points à vérifier par le relecteur médical" section; they are
  never silently resolved. Content supported only by student material is flagged.
- Exercises cite the lesson units and source pages they test. Distractors may not introduce
  unsupported numbers.
- Status is `draft_unreviewed` until an explicit human review is recorded. No automatic process
  may mark content medically validated. Technical validation never implies medical correctness.

## External AI

The Claude API (Anthropic SDK) is authorized for lesson reconstruction, exercise generation,
vision transcription of scanned or image-only pages, and the website chatbot.

- Key from `ANTHROPIC_API_KEY` (in `.env`, Git-ignored, or the hosting provider's secret store);
  never in code, logs, the repo, or the browser.
- Bulk work uses the Message Batches API with prompt caching. Runs are bounded, resumable, and
  record model, request identity, token usage, and estimated cost per item.
- Raw responses and failed attempts are kept append-only for audit; failed output never replaces
  a validated artifact. A validation-guided retry is bounded and may not weaken validation.
- Do not run paid API batches without the owner's explicit go for that run.

## Not implemented

Do not add without the owner's explicit request: application backend logic beyond Supabase (with
its row-level security) and the chatbot route, payments, leaderboards or other cross-user data,
embeddings or vector search, flashcards, clinical case generation, AI-generated medical images,
or automated medical review/publication. Supabase keys: only the public URL and anon key reach the
browser; the service-role key never enters the repo, logs, or client code.

## Library and artifact safety

- `library/` is read-only: never rename, move, overwrite, or delete original course files, and
  never write generated files into it.
- Derivatives (OCR, Office) are content-addressed by source SHA-256 with provenance; citations
  always point to the original source-relative path and physical page.
- Resume validates hashes and content; directory existence alone never means success.
- Validated lessons and reviewed artifacts are not overwritten without an explicit, scoped rebuild.
- Aggregate reports stay concise and must not embed large extracted medical passages.

## Implementation requirements

Use pathlib, Pydantic, Typer, Rich, type hints, incremental SHA-256 hashing, and atomic writes.
Match the surrounding code style. Before completion run:

- `ruff check .`
- `ruff format --check .`
- `mypy src/ingestion`
- `pytest`
