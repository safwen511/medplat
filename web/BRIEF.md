# MedPlat web — brief for component work

Working directory: /home/flint/projects/medplat/web. Node is at $HOME/.local/opt/node/bin (prepend it to PATH).
Read first: web/AGENTS.md (this Next.js version differs from your training data: read the relevant
guide in node_modules/next/dist/docs/ before writing code), then these existing files:
src/app/globals.css (design tokens), src/components/ui/* (button, card, badge, progress, dialog),
src/lib/utils.ts, src/lib/content/types.ts (content contract), src/lib/content/load.ts,
src/lib/progress/store.ts and provider.tsx (useProgress(): store with attempts, lesson progress,
highlights, error reports, profile), and the routes in src/app/[faculty]/[year]/**.

Product: a revision site for Tunisian medical students (Faculté de Médecine de Sfax, DCEM1/DCEM2).
UI language: French. Feel: simple, smooth, professional, healthcare + "professional playground".
Colors only through the tokens (bg-primary, text-muted, bg-correct-soft, text-wrong, bg-highyield-soft,
rounded-card, border-border, bg-surface, bg-surface-muted ...). Correct/wrong are ALWAYS paired with
an icon (lucide Check / X), never color alone. Dark mode works through the tokens. Mobile first:
students use phones. Accessible: keyboard operable, labels, aria where needed.

Libraries already installed (do not add others): react 19, next 16 (App Router, Cache Components on),
react-markdown + remark-gfm, @dnd-kit/core + sortable + utilities, recharts, lucide-react, motion
(import from "motion/react"), next-themes, @radix-ui/react-dialog/tabs/tooltip/slot,
class-variance-authority, clsx, tailwind-merge, @supabase/*.

Rules:
- Only create/modify files inside your own area (named in your task). If you need a change in a
  shared file (ui kit, types, store, routes), do not make it: describe it in your final report.
  Exception: you may add new primitives under src/components/ui/<new-file>.tsx if your area needs one.
- Never invent medical content. For development fixtures use obviously generic placeholder text
  ("Question de démonstration", "Proposition A"...).
- Must pass, from web/: `npx next typegen && npx tsc --noEmit`, `npx eslint src`, `npm run build`.
- Final answer: what you built (files), how it behaves, anything left undone, shared-file changes
  you need. Compact.
