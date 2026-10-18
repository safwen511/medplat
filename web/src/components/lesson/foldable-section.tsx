"use client";

import { motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

import { headingClass, SectionHeading, sectionSpacing } from "./heading";
import { textLink } from "./lesson-actions";

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
    <section ref={ref} id={id} data-section data-foldable className={cn("scroll-mt-24", sectionSpacing(level))}>
      <SectionHeading level={level} className={headingClass(level)}>
        {title}
      </SectionHeading>
      {badge}
      {reviewer && (
        <p className="mt-2 font-sans text-base text-muted">
          Divergences entre sources et points incertains, à l&apos;attention du relecteur médical.
        </p>
      )}
      <button
        type="button"
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen((value) => !value)}
        className={cn(textLink, "font-sans text-muted decoration-border hover:text-foreground hover:decoration-current")}
      >
        {open ? "Replier" : "Afficher la section"}
      </button>
      <motion.div
        id={contentId}
        initial={false}
        animate={open ? { height: "auto", opacity: 1 } : { height: 0, opacity: 0 }}
        transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
        style={{ overflow: "hidden" }}
        inert={!open}
        aria-hidden={!open}
        className={cn(reviewer && "text-muted")}
      >
        {children}
      </motion.div>
    </section>
  );
}
