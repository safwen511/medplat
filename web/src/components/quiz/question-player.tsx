"use client";

import { AnimatePresence, motion, MotionConfig } from "motion/react";
import { useRef, useState } from "react";

import type { Exercise } from "@/lib/content/types";
import type { Mode } from "@/lib/progress/store";

import { QuestionCard, type AnswerResult } from "./question-card";
import { TextAction, ThinBar } from "./quiet";
import { QuizSummary } from "./quiz-summary";

/**
 * Plays a series of exercises one per screen, then a calm summary. Used for the end-of-lesson
 * check (mode "lesson") and the quiz (mode "quiz"). `onFinish` is called by "Terminer";
 * `onExit` adds a quiet "Quitter" link next to the counter.
 */
export function QuestionPlayer({
  exercises,
  mode,
  faculty,
  year,
  onFinish,
  onExit,
}: {
  exercises: Exercise[];
  mode: Mode;
  faculty: string;
  year: string;
  onFinish?: () => void;
  onExit?: () => void;
}) {
  const [queue, setQueue] = useState(exercises);
  const [round, setRound] = useState(0);
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<AnswerResult[]>([]);
  const [phase, setPhase] = useState<"playing" | "summary" | "done">("playing");
  const topRef = useRef<HTMLDivElement>(null);

  const restart = (items: Exercise[]) => {
    setQueue(items);
    setRound((value) => value + 1);
    setIndex(0);
    setResults([]);
    setPhase("playing");
  };

  const scrollTop = () => {
    const top = topRef.current;
    if (!top || top.getBoundingClientRect().top >= 64) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    top.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  };

  const next = () => {
    if (index + 1 < queue.length) setIndex(index + 1);
    else setPhase("summary");
    scrollTop();
  };

  if (queue.length === 0) {
    return <p className="text-base text-muted">Aucune question pour le moment.</p>;
  }

  const exercise = queue[index];
  const answered = results.length;

  return (
    <MotionConfig reducedMotion="user">
      <div ref={topRef} className="flex scroll-mt-20 flex-col gap-8">
        {phase === "playing" && (
          <div className="flex flex-col gap-3">
            <div className="flex min-h-6 items-center justify-between gap-4 text-sm text-muted">
              <span className="tabular-nums" aria-live="polite">
                Question {index + 1} / {queue.length}
              </span>
              {onExit && (
                <button
                  type="button"
                  onClick={onExit}
                  className="-my-3 min-h-12 -mx-1 rounded-card px-1 underline decoration-border underline-offset-4 hover:text-foreground hover:decoration-current focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  Quitter
                </button>
              )}
            </div>
            <ThinBar value={answered / queue.length} />
          </div>
        )}
        <AnimatePresence mode="wait" initial={false}>
          {phase === "playing" && (
            <motion.div
              key={`${round}:${index}`}
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.18, ease: [0.2, 0, 0, 1] }}
            >
              <QuestionCard
                exercise={exercise}
                mode={mode}
                faculty={faculty}
                year={year}
                hints={mode !== "exam"}
                nextLabel={index + 1 < queue.length ? "Suivant" : "Voir le bilan"}
                onAnswered={(result) => setResults((previous) => [...previous, result])}
                onNext={next}
              />
            </motion.div>
          )}
          {phase === "summary" && (
            <motion.div key={`summary:${round}`} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
              <QuizSummary
                results={results}
                onRetryMissed={() => restart(results.filter((result) => !result.correct).map((r) => r.exercise))}
                onFinish={() => (onFinish ? onFinish() : setPhase("done"))}
              />
            </motion.div>
          )}
          {phase === "done" && (
            <motion.div
              key="done"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.18 }}
              className="flex flex-col items-start gap-1"
            >
              <p className="text-base text-muted">Série terminée.</p>
              <TextAction onClick={() => restart(exercises)}>Refaire la série</TextAction>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </MotionConfig>
  );
}
