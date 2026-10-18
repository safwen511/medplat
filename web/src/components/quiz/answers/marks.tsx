import { Check, X } from "lucide-react";

import { cn } from "@/lib/utils";

/** Feedback state of one answer unit after submission. "missed" = expected but not given. */
export type MarkState = "correct" | "wrong" | "missed" | "neutral";

export const markClasses: Record<MarkState, string> = {
  correct: "border-correct bg-correct-soft text-foreground",
  wrong: "border-wrong bg-wrong-soft text-foreground",
  missed: "border-dashed border-correct bg-surface text-foreground",
  neutral: "border-border bg-surface text-muted",
};

const labels: Record<MarkState, string> = {
  correct: "Correct",
  wrong: "Incorrect",
  missed: "Attendu",
  neutral: "",
};

/** Check / X icon that always accompanies the correct / wrong colors (never color alone). */
export function Mark({ state, className }: { state: MarkState; className?: string }) {
  if (state === "neutral") return null;
  const good = state !== "wrong";
  const Icon = good ? Check : X;
  return (
    <span
      className={cn(
        "inline-flex size-6 shrink-0 items-center justify-center rounded-full",
        state === "correct" && "bg-correct text-surface",
        state === "missed" && "border-2 border-correct text-correct",
        state === "wrong" && "bg-wrong text-surface",
        className,
      )}
    >
      <Icon className="size-3.5" strokeWidth={3} aria-hidden />
      <span className="sr-only">{labels[state]}</span>
    </span>
  );
}

export function markOf(expected: boolean, given: boolean): MarkState {
  if (expected && given) return "correct";
  if (expected) return "missed";
  if (given) return "wrong";
  return "neutral";
}
