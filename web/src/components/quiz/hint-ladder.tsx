"use client";

import { Lightbulb } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";

import { Button } from "@/components/ui/button";

export const HINT_LABELS = ["Que demande la question ?", "Qu'éliminer ?", "La règle du cours"] as const;

/** Progressive hints: each press reveals the next rung of the ladder. */
export function HintLadder({
  hints,
  used,
  onReveal,
  disabled,
}: {
  hints: readonly string[];
  used: number;
  onReveal: () => void;
  disabled: boolean;
}) {
  const available = hints.filter((hint) => hint.trim() !== "").length;
  if (available === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <AnimatePresence initial={false}>
        {hints.slice(0, used).map((hint, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="rounded-card border border-highyield/30 bg-highyield-soft px-4 py-3 text-sm">
              <p className="mb-0.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-highyield">
                <Lightbulb className="size-3.5" aria-hidden />
                Indice {i + 1} · {HINT_LABELS[i]}
              </p>
              <p className="text-foreground">{hint}</p>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
      {used < available && !disabled && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onReveal}
          className="h-auto min-h-8 self-start whitespace-normal py-1.5 text-left text-highyield"
        >
          <Lightbulb aria-hidden />
          <span>
            <span className="font-semibold">Indice {used + 1}/{available}</span>
            <span className="text-muted"> · {HINT_LABELS[used]}</span>
          </span>
        </Button>
      )}
    </div>
  );
}
