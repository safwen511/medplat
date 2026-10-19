"use client";

import { motion } from "motion/react";
import Link from "next/link";

import { PRESS, SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

import type { Section, SectionId } from "./nav";

// Shown on phones and tablets held in portrait (below the lg breakpoint). The bar is fixed, so the
// page reserves its height (plus the iPhone home-indicator area) to keep the end of every page
// reachable. React hoists this <style> into <head>.
const RESERVE_SPACE = `@media (width < 64rem) and (orientation: portrait) {
  body { padding-bottom: calc(4.75rem + env(safe-area-inset-bottom)); }
}`;

const MotionLink = motion.create(Link);

/** Glass tab bar: icons with labels; a soft pill slides to the current section. */
export function BottomNav({ items, active }: { items: Section[]; active: SectionId | null }) {
  return (
    <>
      <style href="medplat-bottom-nav" precedence="medplat">
        {RESERVE_SPACE}
      </style>
      <nav
        aria-label="Navigation principale"
        className="fixed inset-x-0 bottom-0 z-40 hidden border-t border-border bg-background/80 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl backdrop-saturate-150 max-lg:portrait:block"
      >
        <ul className="mx-auto grid h-[4.75rem] max-w-xl grid-cols-3 px-2">
          {items.map((item) => {
            const current = active === item.id;
            return (
              <li key={item.id} className="flex">
                <MotionLink
                  href={item.href}
                  aria-current={current ? "page" : undefined}
                  whileTap={PRESS}
                  className={cn(
                    "relative flex flex-1 flex-col items-center justify-center gap-1 text-xs transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                    current ? "font-medium text-foreground" : "text-muted",
                  )}
                >
                  <span className="relative flex h-8 w-14 items-center justify-center">
                    {current && (
                      <motion.span
                        layoutId="tab-pill"
                        transition={SPRING}
                        aria-hidden
                        className="absolute inset-0 rounded-full bg-primary-soft"
                      />
                    )}
                    <item.icon
                      className={cn("relative size-[1.375rem]", current && "text-primary")}
                      strokeWidth={current ? 1.9 : 1.5}
                      aria-hidden
                    />
                  </span>
                  <span>{item.label}</span>
                  {item.soon && <span className="-mt-1 text-[0.625rem] leading-none text-subtle">bientôt</span>}
                </MotionLink>
              </li>
            );
          })}
        </ul>
      </nav>
    </>
  );
}
