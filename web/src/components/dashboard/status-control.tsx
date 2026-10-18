"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import type { LessonStatus } from "@/lib/progress/store";
import { cn } from "@/lib/utils";

import { STATUS_LABELS, STATUS_STEPS } from "./data";

const TONE: Record<LessonStatus | "non_lu", string> = {
  non_lu: "bg-surface-muted text-muted",
  lu: "bg-primary-soft text-primary",
  revise_1: "bg-primary-soft text-primary",
  revise_2: "bg-primary-soft text-primary",
  maitrise: "bg-primary text-primary-foreground",
};

/**
 * Steps a lesson through Lu -> Révisé 1× -> Révisé 2× -> Maîtrisé. "Non lu" is the absence of a
 * record, so once a status is saved the control can move back only as far as "Lu".
 */
export function StatusControl({
  status,
  lessonTitle,
  onChange,
}: {
  status: LessonStatus | null;
  lessonTitle: string;
  onChange: (status: LessonStatus) => void;
}) {
  const position = status ? STATUS_STEPS.indexOf(status) : -1;
  const key = status ?? "non_lu";
  const previous = position > 0 ? STATUS_STEPS[position - 1] : null;
  const next = position < STATUS_STEPS.length - 1 ? STATUS_STEPS[position + 1] : null;

  const stepButton =
    "inline-flex size-8 items-center justify-center rounded-md text-muted transition-colors hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-30";

  return (
    <div className="inline-flex items-center gap-0.5" role="group" aria-label={`Statut de « ${lessonTitle} »`}>
      <button
        type="button"
        className={stepButton}
        disabled={!previous}
        onClick={() => previous && onChange(previous)}
        aria-label={previous ? `Revenir à « ${STATUS_LABELS[previous]} »` : "Statut précédent indisponible"}
      >
        <ChevronLeft className="size-4" aria-hidden />
      </button>
      <span
        className={cn(
          "inline-flex h-7 min-w-24 items-center justify-center rounded-full px-3 text-xs font-medium tabular-nums",
          TONE[key],
        )}
        aria-live="polite"
      >
        {STATUS_LABELS[key]}
      </span>
      <button
        type="button"
        className={stepButton}
        disabled={!next}
        onClick={() => next && onChange(next)}
        aria-label={next ? `Passer à « ${STATUS_LABELS[next]} »` : "Statut maximal atteint"}
      >
        <ChevronRight className="size-4" aria-hidden />
      </button>
    </div>
  );
}
