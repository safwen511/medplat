"use client";

import { Brain, Check, Eye, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";

import { recordTerm } from "@/lib/leitner";
import { EASE_OUT } from "@/lib/motion";

import { BODY_SELECTOR } from "./marks/marked-body";
import { useTools } from "./marks/tools";

// Bold key terms of the lesson text (not headings, not table headers).
const TERMS = "strong:not(h2 strong, h3 strong, h4 strong, th strong, [data-no-highlight] strong)";

interface Prompt {
  top: number;
  left: number;
}

interface Counts {
  total: number;
  revealed: number;
  known: number;
}

/**
 * "Mode rappel": key terms turn into blanks. A tap reveals one, then the student says whether
 * they knew it; terms they did not know go to "À revoir aujourd'hui" (Leitner boxes).
 */
export function RecallMode({ lessonId, title, href }: { lessonId: string; title: string; href: string }) {
  const { recall, setRecall } = useTools();
  const [prompt, setPrompt] = useState<Prompt | null>(null);
  // The term being answered (a DOM node of the server-rendered text, not React state).
  const current = useRef<HTMLElement | null>(null);
  const [counts, setCounts] = useState<Counts>({ total: 0, revealed: 0, known: 0 });

  // Arriving from "À revoir aujourd'hui" (#rappel): start in recall mode.
  useEffect(() => {
    if (window.location.hash !== "#rappel") return;
    const frame = requestAnimationFrame(() => setRecall(true));
    history.replaceState(null, "", window.location.pathname);
    return () => cancelAnimationFrame(frame);
  }, [setRecall]);

  const recount = useCallback(() => {
    const terms = [...document.querySelectorAll<HTMLElement>(`${BODY_SELECTOR} ${TERMS}`)];
    setCounts({
      total: terms.length,
      revealed: terms.filter((term) => term.dataset.recall).length,
      known: terms.filter((term) => term.dataset.recall === "known").length,
    });
  }, []);

  useEffect(() => {
    const body = document.querySelector<HTMLElement>(BODY_SELECTOR);
    if (!body) return;
    if (!recall) {
      body.dataset.recall = "off";
      body.querySelectorAll<HTMLElement>("[data-recall]").forEach((term) => delete term.dataset.recall);
      return;
    }
    body.dataset.recall = "on";
    const frame = requestAnimationFrame(recount);
    const onClick = (event: MouseEvent) => {
      const term = (event.target as Element | null)?.closest<HTMLElement>(TERMS);
      if (!term || !body.contains(term) || term.dataset.recall) return;
      event.preventDefault();
      term.dataset.recall = "open";
      current.current = term;
      const rect = term.getBoundingClientRect();
      const width = document.documentElement.clientWidth;
      setPrompt({ top: rect.bottom + 8, left: Math.min(Math.max(rect.left + rect.width / 2, 130), width - 130) });
      recount();
    };
    const close = () => setPrompt(null);
    body.addEventListener("click", onClick);
    window.addEventListener("scroll", close, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      body.removeEventListener("click", onClick);
      window.removeEventListener("scroll", close);
    };
  }, [recall, recount]);

  const answer = (knew: boolean) => {
    const term = current.current;
    if (!term) return;
    term.dataset.recall = knew ? "known" : "unknown";
    recordTerm({ term: term.textContent?.trim() ?? "", lessonId, lessonTitle: title, href }, knew);
    current.current = null;
    setPrompt(null);
    recount();
  };

  const revealAll = () => {
    document.querySelectorAll<HTMLElement>(`${BODY_SELECTOR} ${TERMS}`).forEach((term) => {
      if (!term.dataset.recall) term.dataset.recall = "open";
    });
    setPrompt(null);
    recount();
  };

  return (
    <>
      <AnimatePresence>
        {recall && (
          <motion.div
            data-recall-hint
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: EASE_OUT }}
            className="recall-bar fixed inset-x-0 z-30 flex justify-center px-4 print:hidden"
          >
            <div className="flex items-center gap-3 rounded-full border border-border-strong bg-background/90 py-1.5 pr-1.5 pl-4 font-sans text-sm shadow-depth-2 backdrop-blur-xl">
              <Brain className="size-4 text-primary" aria-hidden />
              <span>
                <span className="numeral font-semibold">{counts.revealed}</span>
                <span className="text-muted">/{counts.total} révélés</span>
                <span className="text-muted"> · </span>
                <span className="numeral font-semibold text-correct">{counts.known}</span>
                <span className="text-muted"> sus</span>
              </span>
              <button
                type="button"
                onClick={revealAll}
                className="inline-flex h-9 items-center gap-1.5 rounded-full px-3 text-muted transition-colors hover:bg-surface-muted hover:text-foreground"
              >
                <Eye className="size-4" aria-hidden /> Tout révéler
              </button>
              <button
                type="button"
                aria-label="Quitter le mode rappel"
                onClick={() => setRecall(false)}
                className="flex size-9 items-center justify-center rounded-full text-muted transition-colors hover:bg-surface-muted hover:text-foreground"
              >
                <X className="size-4" aria-hidden />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <AnimatePresence>
        {recall && prompt && (
          <motion.div
            data-recall-hint
            initial={{ opacity: 0, y: -4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: 0.16, ease: EASE_OUT }}
            style={{ top: prompt.top, left: prompt.left }}
            className="fixed z-50 flex -translate-x-1/2 gap-2 rounded-full border border-border-strong bg-panel p-1.5 font-sans text-sm shadow-depth-3"
          >
            <button
              type="button"
              onClick={() => answer(true)}
              className="inline-flex h-10 items-center gap-1.5 rounded-full bg-correct-soft px-4 font-medium text-correct transition-colors hover:brightness-110"
            >
              <Check className="size-4" aria-hidden /> Je savais
            </button>
            <button
              type="button"
              onClick={() => answer(false)}
              className="inline-flex h-10 items-center gap-1.5 rounded-full bg-highyield-soft px-4 font-medium text-highyield transition-colors hover:brightness-110"
            >
              Je ne savais pas
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
