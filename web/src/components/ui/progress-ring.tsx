import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Circular progress (goal, mastery). value 0..100; the centre shows `children` or the percent. */
export function ProgressRing({
  value,
  size = 112,
  stroke = 10,
  label,
  children,
  tone = "primary",
  className,
}: {
  value: number;
  size?: number;
  stroke?: number;
  label: string;
  children?: ReactNode;
  tone?: "primary" | "correct" | "highyield";
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const color = { primary: "var(--primary)", correct: "var(--correct)", highyield: "var(--highyield)" }[tone];
  return (
    <div
      role="img"
      aria-label={`${label} : ${Math.round(clamped)} %`}
      className={cn("relative inline-flex shrink-0 items-center justify-center", className)}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--surface-muted)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - clamped / 100)}
          style={{
            transition: "stroke-dashoffset var(--dur-slow) var(--ease-out)",
            filter: `drop-shadow(0 0 6px ${color})`,
          }}
        />
      </svg>
      <span className="numeral absolute text-2xl font-semibold">
        {children ?? `${Math.round(clamped)} %`}
      </span>
    </div>
  );
}
