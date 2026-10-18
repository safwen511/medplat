"use client";

import Link from "next/link";

import { cn } from "@/lib/utils";

import type { Section, SectionId } from "./nav";

// Shown on phones and tablets held in portrait (below the lg breakpoint). The bar is fixed, so the
// page reserves its height (plus the iPhone home-indicator area) to keep the end of every page
// reachable. React hoists this <style> into <head>.
const RESERVE_SPACE = `@media (width < 64rem) and (orientation: portrait) {
  body { padding-bottom: calc(4.5rem + env(safe-area-inset-bottom)); }
}`;

/** Calm bottom tab bar: thin icons with labels, the current section in the accent colour. */
export function BottomNav({ items, active }: { items: Section[]; active: SectionId | null }) {
  return (
    <>
      <style href="medplat-bottom-nav" precedence="medplat">
        {RESERVE_SPACE}
      </style>
      <nav
        aria-label="Navigation principale"
        className="fixed inset-x-0 bottom-0 z-40 hidden border-t border-border bg-background pb-[env(safe-area-inset-bottom)] max-lg:portrait:block"
      >
        <ul className="mx-auto grid h-[4.5rem] max-w-xl grid-cols-3">
          {items.map((item) => {
            const current = active === item.id;
            return (
              <li key={item.id} className="flex">
                <Link
                  href={item.href}
                  aria-current={current ? "page" : undefined}
                  className={cn(
                    "flex flex-1 flex-col items-center gap-1 pt-3 text-xs transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                    current ? "font-medium text-primary" : "text-muted active:text-foreground",
                  )}
                >
                  <item.icon className="size-6" strokeWidth={1.5} aria-hidden />
                  <span>{item.label}</span>
                  {item.soon && <span className="-mt-1 text-[0.6875rem] leading-none text-muted">bientôt</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </>
  );
}
