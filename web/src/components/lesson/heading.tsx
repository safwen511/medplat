// Shared, server-safe lesson heading styles (used by server sections and foldable sections).

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

export function headingClass(level: number) {
  if (level <= 2) return "text-xl font-semibold tracking-tight text-foreground sm:text-2xl";
  if (level === 3) return "text-lg font-semibold text-foreground";
  return "font-sans text-base font-semibold text-foreground";
}

export function sectionSpacing(level: number) {
  if (level <= 2) return "mt-12 first:mt-6";
  if (level === 3) return "mt-8";
  return "mt-6";
}
