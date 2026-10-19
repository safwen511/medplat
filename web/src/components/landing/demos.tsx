"use client";

import { BookOpen, Check, FileText, X } from "lucide-react";
import { AnimatePresence, motion, useInView, useReducedMotion } from "motion/react";
import { useRef, useState } from "react";

import { ProgressRing } from "@/components/ui/progress-ring";
import { EASE_OUT, PRESS, SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

/** A course sentence with its source chip: hover (mouse, stylus) or tap shows where it comes from. */
export function CitationDemo() {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative rounded-panel border border-border bg-surface p-6 shadow-depth-2 sm:p-8">
      <p className="eyebrow">Cardiologie · Insuffisance cardiaque</p>
      <p className="mt-4 text-lg leading-relaxed">
        L&apos;<strong>insuffisance cardiaque</strong> est un <strong>syndrome</strong> dû à l&apos;incapacité du cœur
        à fournir un débit sanguin suffisant pour satisfaire les besoins métaboliques de l&apos;organisme.{" "}
        <span className="relative inline-block">
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
            onPointerEnter={(event) => event.pointerType !== "touch" && setOpen(true)}
            onPointerLeave={(event) => event.pointerType !== "touch" && setOpen(false)}
            className={cn(
              "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 align-middle text-xs font-medium transition-colors duration-150",
              open ? "border-primary/50 bg-primary-soft text-primary" : "border-border text-muted",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
          >
            <FileText className="size-3" aria-hidden /> S1 p.45
          </button>
          <AnimatePresence>
            {open && (
              <motion.span
                role="tooltip"
                initial={{ opacity: 0, y: 6, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 4, scale: 0.98 }}
                transition={{ duration: 0.18, ease: EASE_OUT }}
                className="absolute bottom-full left-1/2 z-10 mb-2 w-64 -translate-x-1/2 rounded-card border border-border-strong bg-panel p-3 text-left text-sm shadow-depth-3"
              >
                <span className="block font-medium text-foreground">Polycopié de cardiologie</span>
                <span className="mt-0.5 block text-muted">Document officiel de la faculté, page 45</span>
              </motion.span>
            )}
          </AnimatePresence>
        </span>
      </p>
      <p className="mt-6 text-sm text-muted">Touche ou survole la source.</p>
    </div>
  );
}

const OPTIONS = [
  { id: "a", text: "Avant-bras" },
  { id: "b", text: "Cuir chevelu" },
  { id: "c", text: "Scrotum" },
  { id: "d", text: "Front" },
];

/** A real question from the dermatology course, playable. */
export function QuizDemo() {
  const [picked, setPicked] = useState<string | null>(null);
  const correct = picked === "c";
  return (
    <div className="rounded-panel border border-border bg-surface p-6 shadow-depth-2 sm:p-8">
      <div className="flex items-center justify-between">
        <p className="eyebrow">QCM · Dermatologie</p>
        {picked && (
          <button
            type="button"
            onClick={() => setPicked(null)}
            className="rounded-full px-3 py-1 text-sm text-muted transition-colors hover:bg-surface-muted hover:text-foreground"
          >
            Rejouer
          </button>
        )}
      </div>
      <p className="mt-4 text-lg leading-snug font-medium">
        Pour un même dermocorticoïde, quel site d&apos;application a le taux d&apos;absorption le plus élevé ?
      </p>
      <div role="radiogroup" aria-label="Propositions" className="mt-5 grid gap-2 sm:grid-cols-2">
        {OPTIONS.map((option) => {
          const chosen = picked === option.id;
          const answer = option.id === "c";
          const state = !picked ? "idle" : answer ? "right" : chosen ? "wrong" : "dim";
          return (
            <motion.button
              key={option.id}
              type="button"
              role="radio"
              aria-checked={chosen}
              disabled={picked !== null}
              whileTap={picked ? undefined : PRESS}
              onClick={() => setPicked(option.id)}
              className={cn(
                "flex min-h-12 items-center justify-between gap-3 rounded-control border px-4 py-3 text-left transition-colors duration-200",
                state === "idle" && "border-border hover:border-border-strong hover:bg-surface-muted",
                state === "right" && "border-correct/60 bg-correct-soft text-foreground",
                state === "wrong" && "border-wrong/60 bg-wrong-soft",
                state === "dim" && "border-border text-muted",
              )}
            >
              {option.text}
              {state === "right" && <Check className="size-4 text-correct" aria-hidden />}
              {state === "wrong" && <X className="size-4 text-wrong" aria-hidden />}
            </motion.button>
          );
        })}
      </div>
      <AnimatePresence initial={false}>
        {picked && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25, ease: EASE_OUT }}
          >
            <div className="pt-5" role="status">
              <p className={cn("font-medium", correct ? "text-correct" : "text-wrong")}>
                {correct ? "Bonne réponse" : "Réponse incorrecte"}
              </p>
              <p className="mt-2 leading-relaxed text-muted">
                Le scrotum absorbe 36 %, contre 1 % pour l&apos;avant-bras, 4 % pour le cuir chevelu et 7 % pour le
                front. Peau fine ou pli : absorption majorée, dermocorticoïde modéré ou faible.
              </p>
              <p className="mt-3 inline-flex items-center gap-2 text-sm text-muted">
                <BookOpen className="size-4" aria-hidden /> Voir le cours :{" "}
                <span className="text-foreground">Corticothérapie locale</span>, p. 24
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

const BARS = [
  { label: "Cardiologie", value: 72, tone: "bg-highyield" },
  { label: "Pneumologie", value: 54, tone: "bg-primary" },
  { label: "Néphrologie", value: 31, tone: "bg-primary/50" },
];

/** Progress figures that fill in when they scroll into view. */
export function ProgressDemo() {
  const ref = useRef<HTMLDivElement>(null);
  const seen = useInView(ref, { once: true, margin: "0px 0px -15% 0px" });
  const reduce = useReducedMotion();
  return (
    <div ref={ref} className="rounded-panel border border-border bg-surface p-6 shadow-depth-2 sm:p-8">
      <div className="flex items-center gap-6">
        <ProgressRing value={seen ? 65 : 0} size={112} stroke={10} label="Objectif du jour">
          <span className="flex flex-col items-center leading-none">
            <span className="text-2xl">13</span>
            <span className="mt-1 text-xs font-normal text-muted">/ 20</span>
          </span>
        </ProgressRing>
        <div className="grid flex-1 grid-cols-2 gap-3">
          <div className="rounded-card bg-surface-muted p-3">
            <p className="text-xs text-muted">bonnes réponses</p>
            <p className="numeral text-2xl font-semibold">82 %</p>
          </div>
          <div className="rounded-card bg-surface-muted p-3">
            <p className="text-xs text-muted">série</p>
            <p className="numeral text-2xl font-semibold">6 j</p>
          </div>
        </div>
      </div>
      <ul className="mt-6 flex flex-col gap-4">
        {BARS.map((bar, index) => (
          <li key={bar.label} className="flex flex-col gap-1.5">
            <span className="flex justify-between text-sm">
              <span>{bar.label}</span>
              <span className="text-muted tabular-nums">{bar.value} %</span>
            </span>
            <span className="h-2 overflow-hidden rounded-full bg-surface-muted">
              <motion.span
                className={cn("block h-full origin-left rounded-full", bar.tone)}
                style={{ width: `${bar.value}%` }}
                initial={false}
                animate={{ scaleX: seen || reduce ? 1 : 0 }}
                transition={{ ...SPRING, delay: reduce ? 0 : 0.2 + index * 0.1 }}
              />
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
