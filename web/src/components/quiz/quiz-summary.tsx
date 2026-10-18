"use client";

import { Check, Lightbulb, RotateCcw, Target, Timer, X } from "lucide-react";
import { motion } from "motion/react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

import { formatDuration, median } from "./grading";
import type { AnswerResult } from "./question-card";

export function QuizSummary({
  results,
  onRetryMissed,
  onFinish,
}: {
  results: AnswerResult[];
  onRetryMissed: () => void;
  onFinish: () => void;
}) {
  const correct = results.filter((result) => result.correct).length;
  const missed = results.filter((result) => !result.correct);
  const accuracy = results.length ? Math.round((correct / results.length) * 100) : 0;
  const times = results.map((result) => result.timeMs);
  const totalTime = times.reduce((sum, value) => sum + value, 0);
  const hints = results.reduce((sum, result) => sum + result.hintsUsed, 0);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.2, 0, 0, 1] }}
      className="flex flex-col gap-6"
    >
      <div className="flex flex-col items-center gap-2 text-center">
        <p className="text-sm font-medium uppercase tracking-wide text-muted">Bilan</p>
        <p className="text-5xl font-semibold tabular-nums">
          {correct}
          <span className="text-2xl text-muted">/{results.length}</span>
        </p>
        <p className="text-sm text-muted">{message(accuracy)}</p>
        <Progress value={accuracy} tone="correct" className="mt-2 max-w-xs" />
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat icon={<Target aria-hidden />} label="Précision" value={`${accuracy} %`} />
        <Stat icon={<Timer aria-hidden />} label="Temps total" value={formatDuration(totalTime)} />
        <Stat icon={<Timer aria-hidden />} label="Temps médian" value={formatDuration(median(times))} />
        <Stat icon={<Lightbulb aria-hidden />} label="Indices utilisés" value={String(hints)} />
      </div>

      {missed.length > 0 ? (
        <section className="flex flex-col gap-3">
          <h3 className="text-base font-semibold">À revoir ({missed.length})</h3>
          <ul className="flex flex-col gap-2.5">
            {missed.map(({ exercise, score, total }) => (
              <li key={exercise.id}>
                <Card className="flex gap-3 p-4">
                  <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-wrong text-surface">
                    <X className="size-3.5" strokeWidth={3} aria-hidden />
                    <span className="sr-only">Incorrect</span>
                  </span>
                  <div className="flex min-w-0 flex-col gap-1.5">
                    <p className="whitespace-pre-line font-medium">{exercise.stem}</p>
                    {total > 1 && (
                      <p className="text-xs text-muted">
                        {score}/{total} unités justes
                      </p>
                    )}
                    {exercise.explanation && (
                      <p className="whitespace-pre-line text-sm leading-relaxed text-muted">{exercise.explanation}</p>
                    )}
                    {exercise.citations && <p className="text-xs text-muted">Sources : {exercise.citations}</p>}
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <p className="flex items-center justify-center gap-2 rounded-card bg-correct-soft px-4 py-3 text-sm">
          <Check className="size-4 text-correct" aria-hidden />
          Aucune erreur sur cette série.
        </p>
      )}

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        {missed.length > 0 && (
          <Button variant="outline" size="lg" onClick={onRetryMissed}>
            <RotateCcw aria-hidden />
            Recommencer les erreurs
          </Button>
        )}
        <Button size="lg" onClick={onFinish}>
          Terminer
        </Button>
      </div>
    </motion.div>
  );
}

export function Stat({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-card border border-border bg-surface-muted/50 p-3">
      <span className="flex items-center gap-1.5 text-xs text-muted [&_svg]:size-3.5">
        {icon}
        {label}
      </span>
      <span className="text-lg font-semibold tabular-nums">{value}</span>
    </div>
  );
}

function message(accuracy: number) {
  if (accuracy === 100) return "Sans faute. Bien joué.";
  if (accuracy >= 80) return "Très bonne série.";
  if (accuracy >= 50) return "C'est en bonne voie : revois les questions manquées.";
  return "Reprends les explications puis retente les erreurs.";
}
