# MedPlat — where things stand (2026-10-19)

## Content (Faculté de Médecine de Sfax)
Built with Claude Opus 5.5 (Message Batches), every claim cited to a source page and checked.

| Year | Pôle | Courses published | Exercises |
|---|---|---|---|
| DCEM1 | A (cardio, pharmaco, pneumo, uro-néphro) | 120 / 124 | 855 (93 courses) |
| DCEM2 | C (8 certifs) | 136 / 155 | 893 (96 courses) |
| both | B / D (wave 0 extras) | 4 | 0 |

- Spend so far: about $96.4 of API credit (wave 0 ~$9.2, wave 1 ~$87.2).
- Still to do with the next credit: exercises for ~71 published courses (~$7), the 11 courses
  that failed their checks, the rest of Pôle C (11 courses), other pôles.
- Generated files live in `data/` and `web/content/` (not in Git). Backup:
  `data/backups/generated-content-2026-10-19.tar.gz` (lessons, exercises, run records, catalogs,
  web content). Copy it off this machine.

## Pipeline (scripts/)
`wave.py` chains `reconstruct_lessons.py` → `repair_lessons.py` → `generate_exercises.py` →
`export_web_content.py`, each paid step capped by `--max-usd`; submits are scoped to the lessons
they name. Paid runs need the owner's explicit go.

## Website (web/, Next.js 16)
- Design: `docs/design.md` (study console, dark first, Space Grotesk + IBM Plex Sans).
- Done: tokens and panels, home with flipping certif folders, certif pages with course cards,
  Mon espace dashboard, quiz with "Voir le cours" references, welcome slideshow.
- Beta access: personal codes (repo-root `vip` file and `MEDPLAT_VIP`, never committed), visit
  memory, sign-out, "Bon retour" banner.
- Progress is stored in the browser (localStorage) until accounts (Supabase) are set up.

## Deploy
- Vercel project `medplat`, live at https://medplat-bay.vercel.app (production).
- Deployed as a prebuilt upload from `web/` because content and figures are not in Git:
  `web/scripts/deploy.sh --prod` (or without `--prod` for a private preview). It forces IPv4
  (this network's IPv6 is broken), uploads one archive (the free plan refuses >5000 file
  uploads/day) and leaves the figures out while `NEXT_PUBLIC_SHOW_FIGURES` is not `true`.
- Secrets in Vercel env: `MEDPLAT_VIP`, `MEDPLAT_ACCESS_SECRET` (preview + production).

## Testers
Ala Arfa (DCEM2, Pôle C), Salsabil Yahyaoui (DCEM1, Pôle A). The owner sends links and codes.
