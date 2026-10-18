import { cn } from "@/lib/utils";

/**
 * Compact ring showing a percentage (0..100) or "—" when there is no value yet. The label is
 * given to assistive tech; the ring itself is decorative.
 */
export function ProgressRing({
  value,
  label,
  size = 30,
  stroke = 3,
  className,
  tone = "primary",
}: {
  value: number | null;
  label: string;
  size?: number;
  stroke?: number;
  className?: string;
  tone?: "primary" | "onHue";
}) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = value === null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <span
      role="img"
      aria-label={value === null ? `${label} : pas encore de réponse` : `${label} : ${value} %`}
      className={cn("relative inline-flex shrink-0 items-center justify-center", className)}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className={tone === "onHue" ? "stroke-white/25" : "stroke-border"}
        />
        {value !== null && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - clamped / 100)}
            className={cn("transition-[stroke-dashoffset] duration-500", tone === "onHue" ? "stroke-white" : "stroke-primary")}
          />
        )}
      </svg>
      <span
        className={cn(
          "absolute text-[9px] font-semibold tabular-nums",
          tone === "onHue" ? "text-white" : value === null ? "text-muted" : "text-foreground",
        )}
        aria-hidden
      >
        {value === null ? "—" : value}
      </span>
    </span>
  );
}
