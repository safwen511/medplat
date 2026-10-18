"use client";

import { ChevronDown } from "lucide-react";

import type { LessonStatus } from "@/lib/progress/store";
import { cn } from "@/lib/utils";

import { STATUS_LABELS, STEPS, statusOf, stepOf, type Step } from "./data";

/**
 * The lesson's follow-up step as a quiet word; tapping it opens the native list
 * (Non lu, Lu, Révisé 1×, Révisé 2×, Maîtrisé), forward or back. Choosing "Non lu"
 * calls onChange(null), which clears the follow-up record.
 */
export function StatusControl({
  status,
  lessonTitle,
  onChange,
  className,
}: {
  status: LessonStatus | null;
  lessonTitle: string;
  onChange: (status: LessonStatus | null) => void;
  className?: string;
}) {
  const step = stepOf(status);
  return (
    <span className={cn("relative inline-flex shrink-0", className)}>
      <select
        value={step}
        onChange={(event) => onChange(statusOf(event.target.value as Step))}
        aria-label={`Statut de « ${lessonTitle} »`}
        className={cn(
          "h-12 cursor-pointer appearance-none rounded-card bg-transparent py-0 pr-7 pl-3 text-right text-sm transition-colors duration-150",
          "hover:bg-surface-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
          step === "non_lu" ? "text-muted" : "text-foreground",
        )}
      >
        {STEPS.map((item) => (
          <option key={item} value={item} className="bg-surface text-foreground">
            {STATUS_LABELS[item]}
          </option>
        ))}
      </select>
      <ChevronDown
        className="pointer-events-none absolute top-1/2 right-2 size-3.5 -translate-y-1/2 text-muted"
        strokeWidth={1.5}
        aria-hidden
      />
    </span>
  );
}
