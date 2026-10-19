# MedPlat design rules — "futuristic study console"

## Feeling
A study console: dark, deep and precise, with a sense of progress and play in navigation and
total calm in the quiz. Inspired by game loading-screen cards (portrait cards, rank, identity),
but every asset, frame and illustration is our own. Students revise under exam stress: the
navigation motivates, the quiz focuses.

## Users and devices
Tunisian medical students (DCEM1/DCEM2), revising mostly on tablets (often with a pen) and phones,
including mid-range Android tablets. Tablet-first, then phone, then desktop. Tap targets >= 48px.
Works in landscape. All UI text is in French (accents everywhere).

## Two zones
1. **Navigation zone** (home, certifs, courses, Mon espace): expressive. 3D cards with tilt on
   hover, flip animations, per-certif colour identity, depth shadow, glow on focus and hover.
2. **Quiz zone**: calm and focused. Minimal motion, maximum readability. The quiz logic and layout
   stay; only the tokens change (surfaces, type, colours).

## Theme
- **Dark mode is the primary design** (light mode kept and maintained).
- Dark background: deep blue-black, never pure #000. Light background: cool off-white.
- Subtle glow and depth; never neon overload. Glow marks focus, hover and the current selection.
- Per-certif colour identity in the navigation zone (one hue per certif, contrast-checked in
  both themes). The quiz zone uses one accent plus muted correct/incorrect colours.

## Surfaces and separation (3 levels)
1. Page background.
2. **Section panels**: slightly lighter than the page, 1px subtle border, 16–20px radius,
   generous padding (24–32px). Every section of every page sits in its own panel with a clear
   title row (title left, optional action right).
3. **Cards on panels** (certif folders, course cards, stat tiles).
- Consistent vertical rhythm between sections: 48–64px. Spacing on a 4/8px scale.
- Never a bare wall of text: a page is a column of titled panels.

## Numbers are visual
Key numbers are never inside sentences. Use stat tiles (big number + small label), progress
rings (goal, mastery) and progress bars (per certif). Sentences may explain, not carry, numbers.

## Motion and touch
- Every hover effect has a tap equivalent (tap to flip, press state on press).
- Animations 150–300ms; transform and opacity only (GPU-friendly); smooth on mid-range Android.
- Respect `prefers-reduced-motion`: no tilt, no flip animation (instant swap), no glow pulses.
- Quiz zone: only feedback transitions (answer state, next question).

## Typography
- One display face for headings and numbers, one body face for text (pairing chosen on
  /styleguide). Few sizes: page title, panel title, body, small, and a large numeral style for
  stat tiles. Body 17–18px on tablets.

## Content rules (product decisions)
- Courses stay readable (lesson pages, "Lire" buttons, reading progress) and each course leads to
  its exercises.
- In quiz explanations, raw citation codes ("[S1 p.6]") are removed from the text and replaced by
  a small line under the explanation: "Voir le cours : <titre>, p. 6" (linking to the course).
- Keep "Signaler une erreur" on every question and the persistent beta label
  ("Bêta · gratuit · non relu par un médecin").
- Empty or missing values say what to do: e.g. no exam date → "Ajoute la date de ton certif".

## Typography (chosen)
Display: **Space Grotesk** (titles, numbers, stat tiles). Body: **IBM Plex Sans**.

## Access (beta)
- Testers enter a personal access code (no e-mail login for now). A valid code opens the site and
  shows a personal welcome (name, how the site works, what exists, what is coming). Codes are never
  shipped to the browser and never committed.

## Forbidden
- Copied assets, frames, fonts or art from any game.
- Pure black backgrounds, neon overload, glow on everything.
- Key numbers buried in sentences; pages without panels.
- Animations of layout properties (width, height, top/left) or longer than 300ms.
