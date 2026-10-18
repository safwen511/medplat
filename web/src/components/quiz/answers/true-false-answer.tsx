"use client";

import { cn } from "@/lib/utils";

import { Mark, markClasses, markOf } from "./marks";

/** Two big buttons. `expected` is only passed once the answer is revealed. */
export function TrueFalseButtons({
  value,
  onPick,
  expected,
  disabled,
}: {
  value: boolean | null;
  onPick: (value: boolean) => void;
  expected?: boolean;
  disabled?: boolean;
}) {
  const revealed = expected !== undefined;
  return (
    <div role="radiogroup" aria-label="Vrai ou faux" className="grid grid-cols-2 gap-3">
      {[true, false].map((choice) => {
        const chosen = value === choice;
        const state = revealed ? markOf(expected === choice, chosen) : "neutral";
        return (
          <button
            key={String(choice)}
            type="button"
            role="radio"
            aria-checked={chosen}
            aria-disabled={revealed || disabled}
            onClick={() => !revealed && !disabled && onPick(choice)}
            className={cn(
              "flex h-16 items-center justify-center gap-2 rounded-card border text-lg font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              !revealed && chosen && "border-primary bg-primary-soft text-primary",
              !revealed && !chosen && "border-border bg-surface text-foreground hover:border-muted/50",
              revealed && markClasses[state],
            )}
          >
            {choice ? "Vrai" : "Faux"}
            {revealed && <Mark state={state} />}
          </button>
        );
      })}
    </div>
  );
}
