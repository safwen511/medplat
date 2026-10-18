# MedPlat design rules

## Feeling
Calm, quiet, confident. Inspired by the restraint of WeTransfer and the Claude login page:
one clear action per screen, generous empty space, nothing competing for attention.
Students use this under exam stress, so the interface must lower stress, not add to it.

## Users and devices
Tunisian medical students (DCEM1/DCEM2), revising mostly on tablets (often with a pen) and phones.
Design tablet-first, then phone, then desktop. Tap targets at least 48px. Works in landscape.
All UI text is in French.

## Layout
- One primary action per screen. Secondary actions are text links, not buttons.
- Content width: max ~640px for reading and quizzes, centered, lots of margin around it.
- Spacing on a 4/8px scale only. Prefer more space over more elements.
- Never nest boxes inside boxes. At most one surface (card) per screen; everything else sits on the page.
- No dashboards full of tiles. No grids of identical cards with icons.

## Color
- Warm off-white background in light mode, deep warm gray in dark mode (support both).
- Text: near-black, not pure #000. Secondary text: one muted gray.
- ONE accent color, used only for the primary action and the current selection.
- Correct / incorrect: a muted green and a muted red, used only for answer feedback.
- No gradients. No purple. No glassmorphism. No colored backgrounds behind sections.

## Typography
- Headings: a refined serif (e.g. "Source Serif 4" or "Fraunces"); body: a clean humanist sans
  (e.g. "Public Sans"). Never Inter, Roboto, Arial, or system defaults as the brand font.
- Few sizes: page title, section title, body, small. Body text 17–18px on tablets.
- Typography and space create hierarchy, not borders, shadows, or color.

## Details
- Borders: 1px hairlines in a soft gray, only when needed. Shadows: none, or one very soft shadow
  on the single card. Corner radius: one value used everywhere (e.g. 12px).
- Icons: a single thin line icon set (e.g. Lucide), used sparingly. No emoji in the UI.
- Motion: short (150–200ms), purposeful (feedback on answer, screen transitions). No decorative
  animations, no bounce, no parallax.
- Empty states and errors: one short, friendly sentence plus one action.

## Quiz screen (the core of the product)
- One question per screen. Question in large, readable text; options as large full-width tap rows.
- After answering: show correct/incorrect inline, the short explanation, then a single "Suivant" button.
- Progress shown as a thin bar and "Question 4 / 30". Nothing else on screen.
- Small "Signaler une erreur" text link under the explanation.
- Persistent beta label, discreet: "Bêta · gratuit · non relu par un médecin".

## Forbidden
Generic AI-template looks: hero sections with gradients, rows of feature cards with icons,
badges everywhere, stacked shadows, multiple accent colors, centered marketing copy with emoji.
If a choice looks like a default template, choose differently and explain why.
