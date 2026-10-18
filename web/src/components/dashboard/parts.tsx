import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function PoleBadge({ pole, className }: { pole: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 min-w-6 items-center justify-center rounded-md bg-primary-soft px-1.5 text-xs font-semibold text-primary",
        className,
      )}
    >
      <span className="sr-only">Pôle </span>
      {pole}
    </span>
  );
}

export function StatTile({
  label,
  value,
  detail,
  icon,
  className,
}: {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("flex flex-col gap-1 p-4", className)}>
      <span className="flex items-center gap-1.5 text-xs font-medium text-muted [&_svg]:size-3.5">
        {icon}
        {label}
      </span>
      <span className="text-2xl font-semibold tabular-nums">{value}</span>
      {detail && <span className="text-xs text-muted">{detail}</span>}
    </Card>
  );
}

/** Labelled progress bar: the visible label names the bar for assistive tech. */
export function LabelledProgress({
  id,
  label,
  value,
  detail,
  tone = "primary",
}: {
  id: string;
  label: string;
  value: number;
  detail: string;
  tone?: "primary" | "correct" | "highyield";
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const color = { primary: "bg-primary", correct: "bg-correct", highyield: "bg-highyield" }[tone];
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span id={id} className="font-medium">
          {label}
        </span>
        <span className="text-xs text-muted tabular-nums">{detail}</span>
      </div>
      <div
        role="progressbar"
        aria-labelledby={id}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(clamped)}
        className="h-2 w-full overflow-hidden rounded-full bg-surface-muted"
      >
        <div className={cn("h-full rounded-full transition-[width]", color)} style={{ width: `${clamped}%` }} />
      </div>
    </div>
  );
}

export function LoadingBlocks({ count = 3 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Chargement">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="h-28 animate-pulse rounded-card bg-surface-muted" />
      ))}
    </div>
  );
}
