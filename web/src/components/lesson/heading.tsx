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

export function headingClass(level: number) {
  if (level <= 2) return "text-[1.625rem] leading-snug text-foreground sm:text-[1.75rem]";
  if (level === 3) return "text-[1.3125rem] leading-snug text-foreground";
  return "font-sans text-[1em] font-semibold text-foreground";
}

export function sectionSpacing(level: number) {
  if (level <= 2) return "mt-16 first:mt-8";
  if (level === 3) return "mt-10";
  return "mt-8";
}
