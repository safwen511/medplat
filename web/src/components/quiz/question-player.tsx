"use client";

import { RotateCcw } from "lucide-react";
import { AnimatePresence, motion, MotionConfig } from "motion/react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { Exercise } from "@/lib/content/types";
import type { Mode } from "@/lib/progress/store";

import { QuestionCard, type AnswerResult } from "./question-card";
import { QuizSummary } from "./quiz-summary";

/**
 * Plays a series of exercises one at a time, then shows a summary. Used for the end-of-lesson
 * check (mode "lesson") and the quiz (mode "quiz"). `onFinish` is called by "Terminer".
 */
export function QuestionPlayer({
  exercises,
  mode,
  faculty,
  year,
  onFinish,
}: {
  exercises: Exercise[];
  mode: Mode;
  faculty: string;
  year: string;
  onFinish?: () => void;
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
    if (top && top.getBoundingClientRect().top < 0) top.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const next = () => {
    if (index + 1 < queue.length) setIndex(index + 1);
    else setPhase("summary");
    scrollTop();
  };

  if (queue.length === 0) {
    return (
      <Card className="p-6 text-center text-sm text-muted">Aucune question pour le moment.</Card>
    );
  }

  const exercise = queue[index];
  const answered = results.length;

  return (
    <MotionConfig reducedMotion="user">
      <div ref={topRef} className="scroll-mt-20">
        <Card className="overflow-hidden">
          {phase === "playing" && (
            <div className="flex flex-col gap-2 border-b border-border bg-surface-muted/40 px-5 py-3">
              <div className="flex items-center justify-between text-xs font-medium text-muted">
                <span>
                  Question {index + 1} / {queue.length}
                </span>
                <span className="tabular-nums">
                  {results.filter((result) => result.correct).length} juste
                  {results.filter((result) => result.correct).length > 1 ? "s" : ""}
                </span>
              </div>
              <Progress value={(answered / queue.length) * 100} className="h-1.5" />
            </div>
          )}
          <div className="p-5 sm:p-6">
            <AnimatePresence mode="wait" initial={false}>
              {phase === "playing" && (
                <motion.div
                  key={`${round}:${index}`}
                  initial={{ opacity: 0, x: 16 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -16 }}
                  transition={{ duration: 0.2, ease: [0.2, 0, 0, 1] }}
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
                <motion.div key={`summary:${round}`} exit={{ opacity: 0 }}>
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
                  className="flex flex-col items-center gap-3 py-4 text-center"
                >
                  <p className="text-sm text-muted">Série terminée.</p>
                  <Button variant="outline" onClick={() => restart(exercises)}>
                    <RotateCcw aria-hidden />
                    Refaire la série
                  </Button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </Card>
      </div>
    </MotionConfig>
  );
}
