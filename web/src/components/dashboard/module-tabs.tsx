"use client";

import { motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

import { SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

export interface ModuleTab {
  slug: string;
  title: string;
  count: number;
}

/**
 * Sticky module tabs over a certif's cards: the tab of the module on screen lights up (scroll spy),
 * a tap scrolls to its module. The indicator slides between tabs.
 */
export function ModuleTabs({ modules }: { modules: ModuleTab[] }) {
  const [active, setActive] = useState(modules[0]?.slug ?? "");
  const reduce = useReducedMotion();

  useEffect(() => {
    const sections = modules
      .map((mod) => document.getElementById(`module-${mod.slug}`))
      .filter((element): element is HTMLElement => element !== null);
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting);
        if (visible.length) setActive(visible[0].target.getAttribute("data-module") ?? "");
      },
      { rootMargin: "-35% 0px -60% 0px" },
    );
    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, [modules]);

  return (
    <nav
      aria-label="Modules"
      className="sticky top-[7.25rem] z-30 -mx-2 rounded-full border border-border bg-background/80 p-1 backdrop-blur-xl"
    >
      <ul className="flex gap-1 overflow-x-auto [scrollbar-width:none]">
        {modules.map((mod) => (
          <li key={mod.slug} className="relative shrink-0">
            {active === mod.slug && (
              <motion.span
                layoutId="module-pill"
                transition={SPRING}
                aria-hidden
                className="absolute inset-0 rounded-full bg-surface-muted shadow-[var(--highlight)]"
              />
            )}
            <button
              type="button"
              aria-current={active === mod.slug ? "true" : undefined}
              onClick={() => {
                setActive(mod.slug);
                document
                  .getElementById(`module-${mod.slug}`)
                  ?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
              }}
              className={cn(
                "relative flex h-10 items-center gap-2 rounded-full px-4 text-sm whitespace-nowrap transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active === mod.slug ? "text-foreground" : "text-muted hover:text-foreground",
              )}
            >
              {mod.title}
              <span className="numeral text-xs text-subtle">{mod.count}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
