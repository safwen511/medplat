"use client";

import { ChevronDown, PlayCircle } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import { QuestionPlayer } from "@/components/quiz/question-player";
import type { Exercise } from "@/lib/content/types";
import { EASE_OUT } from "@/lib/motion";

/** End of a part: 2–3 questions on what was just read, folded until the student asks. */
export function SectionCheck({ exercises, faculty, year }: { exercises: Exercise[]; faculty: string; year: string }) {
  const [open, setOpen] = useState(false);
  return (
    <aside data-no-highlight className="mt-10 rounded-panel border border-border bg-surface/60 font-sans" aria-label="Questions sur cette partie">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex min-h-14 w-full items-center justify-between gap-3 px-5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="flex items-center gap-2.5 font-heading font-semibold">
          <PlayCircle className="size-4 text-primary" aria-hidden /> Teste-toi sur cette partie
        </span>
        <span className="flex items-center gap-2 text-sm text-muted">
          {exercises.length} question{exercises.length > 1 ? "s" : ""}
          <ChevronDown className={`size-4 transition-transform duration-200 ${open ? "rotate-180" : ""}`} aria-hidden />
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2, ease: EASE_OUT }}
            className="border-t border-border px-5 py-6 text-[1rem]"
          >
            <QuestionPlayer
              exercises={exercises}
              mode="lesson"
              faculty={faculty}
              year={year}
              onFinish={() => setOpen(false)}
              onExit={() => setOpen(false)}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </aside>
  );
}
