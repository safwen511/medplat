"use client";

import { cn } from "@/lib/utils";

import { TierFill } from "./tier-frame";
import { TIER_LABELS, TIERS, type Tier } from "./tiers";

/**
 * Status stepper Non lu → Lu → Révisé 1× → Révisé 2× → Maîtrisé. Every step can be chosen
 * directly, including going back to "Non lu".
 */
export function TierStepper({
  tier,
  lessonTitle,
  onChange,
  disabled = false,
  className,
}: {
  tier: Tier;
  lessonTitle: string;
  onChange: (tier: Tier) => void;
  disabled?: boolean;
  className?: string;
}) {
  const position = TIERS.indexOf(tier);
  const focusRing = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <div className="flex items-center gap-1" role="group" aria-label={`Statut de « ${lessonTitle} »`}>
        {TIERS.map((step, index) => {
          const current = step === tier;
          const label = TIER_LABELS[step];
          if (step === "non_lu")
            return (
              <button
                key={step}
                type="button"
                disabled={disabled}
                aria-pressed={current}
                aria-label={label}
                title={label}
                onClick={() => onChange(step)}
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full disabled:opacity-40",
                  focusRing,
                )}
              >
                <span
                  className={cn(
                    "block size-3.5 rounded-full border-2 transition-colors",
                    current ? "border-foreground bg-foreground/15" : "border-muted/60 hover:border-foreground",
                  )}
                />
              </button>
            );
          return (
            <button
              key={step}
              type="button"
              disabled={disabled}
              aria-pressed={current}
              aria-label={label}
              title={label}
              onClick={() => onChange(step)}
              className={cn("group flex h-6 min-w-0 flex-1 items-center rounded-full disabled:opacity-40", focusRing)}
            >
              <TierFill
                tier={index <= position ? step : "non_lu"}
                className={cn(
                  "block h-2 w-full rounded-full transition-[height] group-hover:h-2.5",
                  index > position && "ring-1 ring-border ring-inset",
                  current && "h-2.5 ring-2 ring-foreground/25 ring-offset-1 ring-offset-surface",
                )}
              />
            </button>
          );
        })}
      </div>
      <p className="flex items-baseline justify-between gap-2 text-[11px] text-muted" aria-live="polite">
        <span>Statut</span>
        <span className="font-semibold text-foreground">{TIER_LABELS[tier]}</span>
      </p>
    </div>
  );
}
