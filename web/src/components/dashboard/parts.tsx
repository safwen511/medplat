import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** A thin, quiet progress line (muted ink on a hairline track). Decorative unless labelled. */
export function ProgressLine({ value, label, className }: { value: number; label?: string; className?: string }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      className={cn("h-0.5 w-full overflow-hidden rounded-full bg-border", className)}
      {...(label
        ? {
            role: "progressbar",
            "aria-label": label,
            "aria-valuemin": 0,
            "aria-valuemax": 100,
            "aria-valuenow": Math.round(clamped),
          }
        : { "aria-hidden": true })}
    >
      <div className="h-full rounded-full bg-muted transition-[width] duration-200" style={{ width: `${clamped}%` }} />
    </div>
  );
}

/** Placeholder lines while the student's data loads: quiet, no boxes. */
export function LoadingLines({ count = 3 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-3" aria-busy="true" aria-label="Chargement">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="h-4 animate-pulse rounded-full bg-surface-muted" style={{ width: `${80 - i * 15}%` }} />
      ))}
    </div>
  );
}

/** The single reading column of every dashboard screen. */
export function Column({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("mx-auto flex w-full max-w-[640px] flex-col py-4 sm:py-8", className)}>{children}</div>;
}
