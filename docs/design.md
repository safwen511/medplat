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

## Three zones
0. **Landing** (public home): the most expressive page. Hero with a hand of course cards that
   tilts and fans with a hovering pointer (tap on touch), real published figures counting up,
   playable demos (sourced sentence, a QCM, the progress view), one call to action.
1. **Navigation zone** (home, certifs, courses, Mon espace): expressive. 3D cards with tilt on
   hover, flip animations, per-certif colour identity, depth shadow, glow on focus and hover.
2. **Quiz zone**: calm and focused. Minimal motion, maximum readability. The quiz logic and layout
   stay; only the tokens change (surfaces, type, colours).

## Theme
- **Dark mode is the primary design** (light mode kept and maintained).
- Dark background: deep ink `#05070c` with a faint aurora at the top of the page, never pure
  #000. Light background: cool off-white `#f5f6f8`.
- Accent: mint-teal (`--primary`, `#5fd3c6` dark / `#0d8a7e` light). Borders are hairlines
  (white or ink at 6–14 % alpha), not solid blue lines.
- Subtle glow and depth; never neon overload. Glow marks focus, hover and the current selection.
- Per-certif colour identity in the navigation zone (one hue per certif, contrast-checked in
  both themes). The quiz zone uses one accent plus muted correct/incorrect colours.

## Surfaces and separation (3 levels)
1. Page background.
2. **Panels** (`.panel`): slightly lighter, hairline border, 22px radius, a faint top light.
   Reserved for heroes (greeting, certif header, profile), forms and focused tools (quiz).
   Lists and grids sit on the page as **open sections**: eyebrow + title + optional action over a
   hairline (`SectionHeader`). No wall of identical boxes.
3. **Cards** (certif folders, course cards, stat tiles, list rows) with depth on hover.
- Consistent vertical rhythm between sections: 48–64px. Spacing on a 4/8px scale.
- Never a bare wall of text: a page is a column of titled panels.

## Numbers are visual
Key numbers are never inside sentences. Use stat tiles (big number + small label), progress
rings (goal, mastery) and progress bars (per certif). Sentences may explain, not carry, numbers.

## Motion and input
- Presets in `src/lib/motion.ts`: `SPRING` (indicators, tabs), `SPRING_SOFT` (cards, sheets),
  `EASE_OUT` for entrances, `PRESS` (scale 0.97) for taps. Interface transitions 150–300ms;
  entrances of content up to ~600ms. Transform and opacity only; never width/height/top/left.
- Navigation indicators slide (`layoutId`): header pill, study tabs underline, tab bar pill,
  certif module tabs (with scroll spy).
- Pages fade in through the Web Animations API (`app/template.tsx`), no lasting fill: a finished
  CSS animation stays a stacking context in Chrome and trapped fixed overlays.
- Above the fold, entrances use the CSS `.rise-in` class (visible before JavaScript); below the
  fold, `<Reveal>` (once, on scroll). Loading states use `<Skeleton>` (sheen).
- **Hover means a hovering pointer**: Tailwind's `hover:` is redefined on `(any-hover: hover)`,
  so a mouse *or a stylus hovering above a tablet* gets hover effects, and touch never gets
  sticky hover. The 3D tilt follows mouse and pen (`pointerType !== "touch"`).
- Every hover effect has a tap equivalent (tap to flip, tap to fan the hero cards, tap a source
  chip). Never put information behind hover only.
- `MotionConfig reducedMotion="user"`: with reduced motion, no tilt, no slides, instant swaps.
- Quiz zone: only feedback transitions (answer state, press feedback, next question).
- No smooth-scroll hijacking (Lenis) and no WebGL: native scrolling is better with a pen and on
  mid-range Android tablets.

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
Titles balanced, tight tracking (-0.02em, h1 -0.032em); `.eyebrow` labels (display face, spaced
capitals) above titles; `.numeral` for figures (tabular). Lesson pages: ~40rem column, accent list
markers, framed tables, reading progress line under the header.

## Brand
Logo mark: a file folder whose edge is a heartbeat (`components/layout/logo.tsx`). Glass header
and tab bar (translucent background, backdrop blur).

## Access (beta)
- Testers enter a personal access code (no e-mail login for now). A valid code opens the site and
  shows a personal welcome (name, how the site works, what exists, what is coming). Codes are never
  shipped to the browser and never committed.
- The welcome is a full-screen slideshow of big fading messages (Suivant / Retour, dots, arrow keys,
  swipe), shown once per device. Returning testers skip the code page and the welcome; each new
  browser session counts a visit and shows a short "Bon retour" banner that fades out.

## Forbidden
- Copied assets, frames, fonts or art from any game.
- Pure black backgrounds, neon overload, glow on everything.
- Key numbers buried in sentences; walls of identical boxes; a bare page without titled sections.
- Animations of layout properties (width, height, top/left); interface transitions longer than 300ms (content entrances up to ~600ms).
