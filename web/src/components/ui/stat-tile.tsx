import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Level-3 card: one big number and a small label. Numbers never sit inside sentences. */
export function StatTile({
  value,
  label,
  hint,
  icon,
  className,
}: {
  value: ReactNode;
  label: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-1 rounded-card border border-border bg-surface p-5 shadow-depth-1",
        className,
      )}
    >
      <div className="flex items-center gap-2 text-sm text-muted">
        {icon}
        <span>{label}</span>
      </div>
      <span className="numeral text-4xl leading-tight font-semibold text-foreground">{value}</span>
      {hint && <span className="text-sm text-muted">{hint}</span>}
    </div>
  );
}
