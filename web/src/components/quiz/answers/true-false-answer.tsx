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
              "relative flex h-24 items-center justify-center gap-2 rounded-card border-2 text-lg font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:h-28",
              !revealed && "hover:border-primary/60 active:scale-[0.98]",
              !revealed && chosen && "border-primary bg-primary-soft text-primary shadow-sm",
              !revealed && !chosen && "border-border bg-surface text-foreground",
              revealed && markClasses[state],
              revealed && state === "neutral" && "opacity-60",
            )}
          >
            {choice ? "Vrai" : "Faux"}
            {revealed && <Mark state={state} className="absolute right-3 top-3" />}
          </button>
        );
      })}
    </div>
  );
}
