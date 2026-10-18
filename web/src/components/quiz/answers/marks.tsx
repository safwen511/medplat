import { Check, X } from "lucide-react";

import { cn } from "@/lib/utils";

/** Feedback state of one answer unit after submission. "missed" = expected but not given. */
export type MarkState = "correct" | "wrong" | "missed" | "neutral";

/** Row styles after submission: muted green / red, only ever paired with a Mark icon. */
export const markClasses: Record<MarkState, string> = {
  correct: "border-correct/60 bg-correct-soft text-foreground",
  wrong: "border-wrong/60 bg-wrong-soft text-foreground",
  missed: "border-dashed border-correct/70 bg-transparent text-foreground",
  neutral: "border-border bg-transparent text-muted",
};

const labels: Record<MarkState, string> = {
  correct: "Correct",
  wrong: "Incorrect",
  missed: "Attendu",
  neutral: "",
};

/** Thin check / cross that always accompanies the correct / wrong colours (never colour alone). */
export function Mark({ state, className }: { state: MarkState; className?: string }) {
  if (state === "neutral") return null;
  const Icon = state === "wrong" ? X : Check;
  return (
    <span
      className={cn(
        "inline-flex size-6 shrink-0 items-center justify-center",
        state === "wrong" ? "text-wrong" : "text-correct",
        className,
      )}
    >
      <Icon className="size-5" strokeWidth={2} aria-hidden />
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
