# UI rework to docs/design.md — shared brief

The owner wrote /home/flint/projects/medplat/docs/design.md and made it the rule (CLAUDE.md:
"Before any frontend work, read and follow docs/design.md"). READ IT FIRST AND FOLLOW IT EXACTLY.
It supersedes web/DESIGN-CARDS.md (the 3D trading-card look is now forbidden: gradients, glow,
shimmer, tilt, grids of identical cards with icons, badges everywhere, several accent colours).

Already done for you (do not change): src/app/globals.css tokens (warm off-white / deep warm gray,
ONE accent = `primary` (deep muted teal), muted `correct`/`wrong` for answer feedback only,
`highyield` is now just the muted text colour, radius 12px via `rounded-card`), fonts in
src/app/layout.tsx: Source Serif 4 for h1–h3 (globals.css applies it), Public Sans for body.

What stays (owner's product wishes), expressed calmly:
- Study vs personal space: "Étudier", "Mon espace", "Connecter (bientôt)".
- Progress / mastery per lesson (Non lu → Lu → Révisé 1× → Révisé 2× → Maîtrisé, resettable to
  Non lu): shown with words and at most a thin progress mark, never gold frames or glow.
- High-yield ("tombe souvent à l'examen"): a quiet text marker in muted ink, never a badge pile.
- Lesson features (citations to sources, figures, highlights, error report), quiz features (all
  types, 3-step hints, explanations, timing, summary), mini-games: keep them, make them quiet.

Rules to apply everywhere (from design.md, made concrete):
- Tablet-first, then phone, then desktop; tap targets >= 48px; works in landscape.
- Reading and quiz content max ~640px wide, centred, generous margins; spacing on a 4/8px scale.
- One primary action per screen (accent button); secondary actions are text links.
- At most ONE surface (card) per screen; never boxes inside boxes; hierarchy from type and space,
  not borders/shadows/colour. Hairline 1px borders only when needed. No shadows except one very
  soft one on the single card.
- No gradients, no purple, no glassmorphism, no coloured section backgrounds, no emoji.
- Lucide thin icons, sparingly. Motion 150–200ms, purposeful only, respect reduced motion.
- Empty states / errors: one short friendly sentence + one action. All UI text in French.
- Persistent discreet beta label: "Bêta · gratuit · non relu par un médecin".

Shared rules for helpers: only edit your own area (listed in your task). Node:
`export PATH="$HOME/.local/opt/node/bin:$PATH"`. Must pass from web/: `npx next typegen && npx tsc
--noEmit`, `npx eslint src`, `npm run build`. The owner's dev server runs on :3000 — do not stop it;
use your own port for screenshots (given in your task) and stop it after. Firefox is a snap: use a
profile and output folder under $HOME/snap/firefox/common/<your-name>/. Check tablet (1024x768 and
768x1024), phone (390x844) and desktop, light and dark. Final answer: files changed, what each
screen now looks like, anything you could not do, shared changes you need. Compact.
