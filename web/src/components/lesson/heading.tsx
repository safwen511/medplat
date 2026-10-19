// Shared, server-safe lesson heading styles (serif from globals.css for h2/h3) (used by server sections and foldable sections).

import type { ReactNode } from "react";

export function SectionHeading({
  level,
  className,
  children,
}: {
  level: number;
  className?: string;
  children: ReactNode;
}) {
  if (level <= 2) return <h2 className={className}>{children}</h2>;
  if (level === 3) return <h3 className={className}>{children}</h3>;
  return <h4 className={className}>{children}</h4>;
}

/**
 * Hierarchy a student can read at a glance: H2 large, bold, in the accent colour with a bar;
 * H3 medium, bold, in ink; H4 a small-capitals label.
 */
export function headingClass(level: number) {
  if (level <= 2)
    return "border-l-[3px] border-primary pl-4 text-[1.55em] leading-tight font-bold tracking-[-0.02em] text-primary";
  if (level === 3) return "text-[1.22em] leading-snug font-bold text-foreground";
  return "font-heading text-[0.8em] font-semibold tracking-[0.12em] text-muted uppercase";
}

export function sectionSpacing(level: number) {
  if (level <= 2) return "mt-20 first:mt-10";
  if (level === 3) return "mt-10";
  return "mt-8";
}
