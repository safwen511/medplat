# MedPlat — website

Next.js 16 (App Router, Cache Components), Tailwind CSS 4, Radix UI primitives, Supabase (Google
sign-in + Postgres with row-level security). Course content is static JSON exported from the
pipeline; only per-student data (profile, answers, fiche de suivi, highlights, error reports)
lives in Supabase. Without Supabase keys the site runs in demo mode (progress in the browser).

## Run locally

```bash
export PATH="$HOME/.local/opt/node/bin:$PATH"   # Node 24 LTS (user install)
cd web && npm install
# content: exported from the pipeline (Git-ignored)
(cd .. && .venv/bin/python scripts/export_web_content.py --year dcem1 \
       && .venv/bin/python scripts/export_web_content.py --year dcem2)
npm run dev        # http://localhost:3000 ; /dev/quiz shows every question type
```

## Supabase

1. Create a project (region Frankfurt or Paris) and a Google OAuth client (Google Cloud Console,
   redirect URI `https://<project>.supabase.co/auth/v1/callback`); paste the Google client ID and
   secret in Supabase → Authentication → Providers → Google.
2. Supabase → Authentication → URL configuration: site URL `http://localhost:3000` (add the Vercel
   URLs when deploying).
3. `web/.env.local` (Git-ignored):
   ```
   NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon / publishable key>
   ```
   Never put the service-role key in this repo or in the browser.
4. Apply the schema from the repo root: `npx supabase login`, `npx supabase link --project-ref
   <ref>`, `npx supabase db push` (migrations in `supabase/migrations/`).

## Layout

- `src/app/` routes: `/`, `/connexion`, `/onboarding`, `/<faculty>/<year>` (certifs),
  `/<faculty>/<year>/<certif>` (fiche de suivi), `/<faculty>/<year>/lecon/<lessonId>`,
  `/<faculty>/<year>/quiz` (quiz + mini-games), `/<faculty>/<year>/progression`.
- `src/lib/content/` content contract (`types.ts`) and loader; `src/lib/progress/` per-student
  store (Supabase or browser); `src/lib/supabase/` clients; `src/proxy.ts` session refresh.
- `src/components/{lesson,quiz,dashboard,ui}`.

Checks: `npx next typegen && npx tsc --noEmit`, `npx eslint src`, `npm run build`.
