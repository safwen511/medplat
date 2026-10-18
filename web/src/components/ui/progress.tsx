import { cn } from "@/lib/utils";

export function Progress({
  value,
  className,
  tone = "primary",
  label,
}: {
  value: number; // 0..100
  className?: string;
  tone?: "primary" | "correct" | "highyield";
  label?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const color = { primary: "bg-primary", correct: "bg-correct", highyield: "bg-highyield" }[tone];
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      aria-label={label}
      className={cn("h-2 w-full overflow-hidden rounded-full bg-surface-muted", className)}
    >
      <div className={cn("h-full rounded-full transition-[width]", color)} style={{ width: `${clamped}%` }} />
    </div>
  );
}
