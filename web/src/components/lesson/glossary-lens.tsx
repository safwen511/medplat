"use client";

import { Languages, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";

import type { GlossaryEntry } from "@/lib/content/types";
import { EASE_OUT } from "@/lib/motion";

import { BODY_SELECTOR } from "./marks/marked-body";
import { useTools } from "./marks/tools";

interface Open {
  entry: GlossaryEntry;
  top: number;
  left: number;
  above: boolean;
}

const CARD_WIDTH = 300;

/**
 * Arabic lens: with "Loupe" on, the glossary terms are underlined (CSS on [data-lens=on]) and a
 * tap opens a small card with the indicative Arabic translation and a plain French definition.
 */
export function GlossaryLens({ entries }: { entries: GlossaryEntry[] }) {
  const { lens } = useTools();
  const [open, setOpen] = useState<Open | null>(null);
  const shown = lens ? open : null;

  useEffect(() => {
    if (!lens) return;
    const onClick = (event: MouseEvent) => {
      const target = (event.target as Element | null)?.closest<HTMLElement>(".gloss");
      if (!target || !target.closest(BODY_SELECTOR)) {
        if (!(event.target as Element | null)?.closest("[data-gloss-card]")) setOpen(null);
        return;
      }
      const entry = entries[Number(target.dataset.term)];
      if (!entry) return;
      event.preventDefault();
      const rect = target.getBoundingClientRect();
      const width = document.documentElement.clientWidth;
      const above = rect.bottom + 230 > window.innerHeight;
      setOpen({
        entry,
        top: above ? rect.top - 10 : rect.bottom + 10,
        left: Math.min(Math.max(rect.left + rect.width / 2 - CARD_WIDTH / 2, 12), width - CARD_WIDTH - 12),
        above,
      });
    };
    const close = () => setOpen(null);
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && close();
    document.addEventListener("click", onClick);
    window.addEventListener("scroll", close, { passive: true });
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", onClick);
      window.removeEventListener("scroll", close);
      window.removeEventListener("keydown", onKey);
    };
  }, [lens, entries]);

  return (
    <AnimatePresence>
      {shown && (
        <motion.div
          key={shown.entry.term}
          data-gloss-card
          data-no-highlight
          role="dialog"
          aria-label={`Traduction : ${shown.entry.term}`}
          initial={{ opacity: 0, y: shown.above ? 6 : -6, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, scale: 0.98 }}
          transition={{ duration: 0.18, ease: EASE_OUT }}
          style={{ top: shown.top, left: shown.left, width: CARD_WIDTH, translate: shown.above ? "0 -100%" : undefined }}
          className="fixed z-50 rounded-panel border border-border-strong bg-panel p-4 font-sans shadow-depth-3"
        >
          <div className="flex items-start justify-between gap-3">
            <p className="font-heading text-base font-semibold first-letter:uppercase">{shown.entry.term}</p>
            <button
              type="button"
              aria-label="Fermer"
              onClick={() => setOpen(null)}
              className="-mt-1 -mr-1 flex size-8 shrink-0 items-center justify-center rounded-full text-muted hover:bg-surface-muted hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          </div>
          <p dir="rtl" lang="ar" className="mt-2 text-right font-ar text-[1.6rem] leading-snug font-semibold text-primary">
            {shown.entry.ar}
          </p>
          <p className="mt-2 text-sm leading-relaxed text-muted">{shown.entry.fr_definition}</p>
          <p className="mt-3 flex items-center gap-1.5 border-t border-border pt-2.5 text-xs text-subtle">
            <Languages className="size-3.5" aria-hidden /> Traduction indicative
          </p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
