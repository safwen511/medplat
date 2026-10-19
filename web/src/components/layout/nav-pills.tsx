"use client";

import { motion } from "motion/react";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

export interface PillItem {
  key: string;
  href: string;
  label: ReactNode;
  active: boolean;
  onClick?: () => void;
}

const focusRing = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/**
 * Navigation links with one sliding indicator. A mouse or a hovering stylus moves a soft pill
 * along the links; it rests on the current page. Touch never sets the hover state.
 * `variant="underline"`: a thin accent line instead of a pill (secondary tabs).
 */
export function NavPills({
  group,
  items,
  label,
  variant = "pill",
  className,
}: {
  group: string;
  items: PillItem[];
  label: string;
  variant?: "pill" | "underline";
  className?: string;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const current = items.find((item) => item.active)?.key ?? null;
  const pill = variant === "pill" ? (hovered ?? current) : null;

  return (
    <nav aria-label={label} className={className}>
      <ul className="flex items-center gap-0.5" onPointerLeave={() => setHovered(null)}>
        {items.map((item) => (
          <li key={item.key} className="relative shrink-0">
            {pill === item.key && (
              <motion.span
                layoutId={`${group}-pill`}
                transition={SPRING}
                aria-hidden
                className={cn(
                  "absolute inset-x-0 inset-y-2 rounded-full",
                  item.active ? "bg-surface-muted shadow-[var(--highlight)]" : "bg-surface-muted/60",
                )}
              />
            )}
            {variant === "underline" && item.active && (
              <motion.span
                layoutId={`${group}-line`}
                transition={SPRING}
                aria-hidden
                className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-primary"
              />
            )}
            <Link
              href={item.href}
              onClick={item.onClick}
              aria-current={item.active ? "page" : undefined}
              onPointerEnter={(event) => event.pointerType !== "touch" && setHovered(item.key)}
              className={cn(
                "relative z-10 flex h-12 items-center gap-1.5 rounded-full px-3.5 text-[0.9375rem] transition-colors duration-150",
                item.active ? "text-foreground" : "text-muted hover:text-foreground",
                variant === "underline" && "text-sm",
                focusRing,
              )}
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
