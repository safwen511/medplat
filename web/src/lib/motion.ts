// Motion presets shared by every component (docs/design.md, "Motion"). Springs for things the
// hand moves (indicators, cards, presses), one easing curve for things that appear.

export const EASE_OUT = [0.22, 1, 0.36, 1] as const;

/** Snappy, no overshoot: navigation indicators, tabs, toggles. */
export const SPRING = { type: "spring", stiffness: 420, damping: 38, mass: 0.7 } as const;

/** Softer, a hint of life: cards lifting, sheets, larger surfaces. */
export const SPRING_SOFT = { type: "spring", stiffness: 260, damping: 28, mass: 0.9 } as const;

/** Press feedback for tappable surfaces. */
export const PRESS = { scale: 0.97 } as const;

/** Entrance of a block: rise and fade, staggered by the caller with `delay`. */
export function rise(delay = 0) {
  return {
    initial: { opacity: 0, y: 14 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.5, ease: EASE_OUT, delay },
  } as const;
}
