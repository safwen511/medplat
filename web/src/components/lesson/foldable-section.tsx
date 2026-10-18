"use client";

import { ChevronDown, ClipboardCheck } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

import { headingClass, SectionHeading, sectionSpacing } from "./heading";

export const REVEAL_EVENT = "lesson:reveal";

/**
 * A section that starts collapsed ("{plié}" marker or the reviewer note). Its content stays in
 * the DOM (highlights and in-page search keep working) and is only visually collapsed.
 */
export function FoldableSection({
  id,
  level,
  title,
  badge,
  reviewer = false,
  children,
}: {
  id: string;
  level: number;
  title: ReactNode;
  badge?: ReactNode;
  reviewer?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLElement>(null);
  const contentId = `${id}-contenu`;

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const reveal = () => setOpen(true);
    element.addEventListener(REVEAL_EVENT, reveal);
    // Opening a link to this section (or to something inside it) unfolds it.
    const onHash = () => {
      const target = decodeURIComponent(window.location.hash.slice(1));
      if (target && (target === id || element.querySelector(`[id="${CSS.escape(target)}"]`))) setOpen(true);
    };
    onHash();
    window.addEventListener("hashchange", onHash);
    return () => {
      element.removeEventListener(REVEAL_EVENT, reveal);
      window.removeEventListener("hashchange", onHash);
    };
  }, [id]);

  return (
    <section
      ref={ref}
      id={id}
      data-section
      data-foldable
      className={cn(
        "scroll-mt-28",
        sectionSpacing(level),
        reviewer && "rounded-card border border-border bg-surface-muted/60 px-4 py-3 sm:px-5",
      )}
    >
      <SectionHeading
        level={level}
        className={cn(reviewer ? "font-sans text-base font-semibold text-foreground" : headingClass(level))}
      >
        <button
          type="button"
          aria-expanded={open}
          aria-controls={contentId}
          onClick={() => setOpen((value) => !value)}
          className="group -mx-1 flex w-[calc(100%+0.5rem)] items-start gap-2 rounded-md px-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {reviewer && <ClipboardCheck className="mt-0.5 size-5 shrink-0 text-muted" aria-hidden />}
          <span className="min-w-0 flex-1">{title}</span>
          <span className="mt-0.5 flex shrink-0 items-center gap-1 font-sans text-xs font-medium text-muted group-hover:text-primary">
            <span className="hidden sm:inline">{open ? "Replier" : "Déplier"}</span>
            <ChevronDown
              className={cn("size-4 transition-transform duration-200", open && "rotate-180")}
              aria-hidden
            />
          </span>
        </button>
      </SectionHeading>
      {badge && <div className="mt-2">{badge}</div>}
      {reviewer && !open && (
        <p className="mt-1 font-sans text-sm text-muted">
          Divergences entre sources et points incertains, à l&apos;attention du relecteur médical.
        </p>
      )}
      <motion.div
        id={contentId}
        initial={false}
        animate={open ? { height: "auto", opacity: 1 } : { height: 0, opacity: 0 }}
        transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
        style={{ overflow: "hidden" }}
        inert={!open}
        aria-hidden={!open}
        className={cn(reviewer && "text-[0.95rem] text-muted")}
      >
        {children}
      </motion.div>
    </section>
  );
}
