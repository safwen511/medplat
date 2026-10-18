"use client";

import type { ReactNode } from "react";

// Small quiet primitives shared by the quiz screens.

/** Thin progress line: muted ink on a hairline track (the accent stays for actions). */
export function ThinBar({ value, label = "Progression de la série" }: { value: number; label?: string }) {
  const clamped = Math.max(0, Math.min(1, value));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped * 100)}
      className="h-0.5 w-full overflow-hidden rounded-full bg-border"
    >
      <div
        className="h-full origin-left bg-muted transition-transform duration-200 ease-out"
        style={{ transform: `scaleX(${clamped})` }}
      />
    </div>
  );
}

/** A secondary action as a text link (design rule: one button per screen). */
export function TextAction({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="min-h-12 -mx-1 rounded-card px-1 text-left text-base text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-current focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {children}
    </button>
  );
}
