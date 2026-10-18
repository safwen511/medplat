"use client";

import { AnimatePresence, motion } from "motion/react";

export const HINT_LABELS = ["Que demande la question ?", "Qu'éliminer ?", "La règle du cours"] as const;

/** The revealed hints, as quiet text. The "Un indice ?" link lives in the question's action row. */
export function HintList({ hints, used }: { hints: readonly string[]; used: number }) {
  return (
    <AnimatePresence initial={false}>
      {hints.slice(0, used).map((hint, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="overflow-hidden"
        >
          <p className="border-l border-border pl-4 text-base leading-relaxed">
            <span className="block text-sm text-muted">
              Indice {i + 1} · {HINT_LABELS[i]}
            </span>
            {hint}
          </p>
        </motion.div>
      ))}
    </AnimatePresence>
  );
}

export function availableHints(hints: readonly string[]) {
  return hints.filter((hint) => hint.trim() !== "").length;
}

/** Quiet text link revealing the next hint, one at a time (at most three). */
export function HintLink({ used, available, onReveal }: { used: number; available: number; onReveal: () => void }) {
  if (used >= available) return null;
  return (
    <button
      type="button"
      onClick={onReveal}
      className="-mx-1 min-h-12 self-start rounded-card px-1 text-left text-base text-muted underline decoration-border underline-offset-4 hover:text-foreground hover:decoration-current focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {used === 0 ? "Un indice ?" : "Un autre indice ?"}
    </button>
  );
}
