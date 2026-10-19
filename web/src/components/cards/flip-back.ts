import type { KeyboardEvent, MouseEvent } from "react";

const INTERACTIVE = "a, button, input, select, textarea, label, [role='radio'], [role='checkbox'], [role='slider']";

/** On a card's back: a tap anywhere but on a control turns the card face up again. */
export function tapToFlipBack(event: MouseEvent<HTMLElement>, back: () => void) {
  if (!(event.target as HTMLElement).closest(INTERACTIVE)) back();
}

/** On a card's back: Escape turns the card face up again. */
export function escapeToFlipBack(event: KeyboardEvent<HTMLElement>, back: () => void) {
  if (event.key !== "Escape") return;
  event.stopPropagation();
  back();
}
