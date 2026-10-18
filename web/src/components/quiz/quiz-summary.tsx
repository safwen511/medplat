"use client";

import { X } from "lucide-react";
import { motion } from "motion/react";

import { Button } from "@/components/ui/button";

import { spokenDuration } from "./grading";
import type { AnswerResult } from "./question-card";
import { TextAction } from "./quiet";

/** End of a series: one sentence with score and time, the missed questions, one primary action. */
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
  const totalTime = results.reduce((sum, result) => sum + result.timeMs, 0);
  const hints = results.reduce((sum, result) => sum + result.hintsUsed, 0);
  const accuracy = results.length ? correct / results.length : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.2, 0, 0, 1] }}
      className="flex flex-col gap-10"
    >
      <div className="flex flex-col gap-3" role="status">
        <h3 className="text-2xl">Série terminée</h3>
        <p className="text-lg leading-relaxed">
          {correct} bonne{correct > 1 ? "s" : ""} réponse{correct > 1 ? "s" : ""} sur {results.length}, en{" "}
          {spokenDuration(totalTime)}.
        </p>
        <p className="text-base text-muted">
          {message(accuracy)}
          {hints > 0 && ` ${hints} indice${hints > 1 ? "s" : ""} utilisé${hints > 1 ? "s" : ""}.`}
        </p>
      </div>

      {missed.length > 0 && (
        <section className="flex flex-col gap-2">
          <h4 className="text-sm text-muted">À revoir</h4>
          <ul className="flex flex-col divide-y divide-border border-y border-border">
            {missed.map(({ exercise, score, total }) => (
              <li key={exercise.id} className="flex gap-3 py-5">
                <X className="mt-1 size-5 shrink-0 text-wrong" strokeWidth={2} aria-hidden />
                <span className="sr-only">Incorrect : </span>
                <div className="flex min-w-0 flex-col gap-2">
                  <p className="whitespace-pre-line text-base font-medium leading-snug">{exercise.stem}</p>
                  {total > 1 && (
                    <p className="text-sm text-muted">
                      {score}/{total} justes
                    </p>
                  )}
                  {exercise.explanation && (
                    <p className="whitespace-pre-line text-base leading-relaxed text-muted">{exercise.explanation}</p>
                  )}
                  {exercise.citations && <p className="text-sm text-muted">Sources : {exercise.citations}</p>}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="flex flex-col gap-2 sm:flex-row-reverse sm:items-center sm:justify-between">
        <Button size="lg" onClick={onFinish} className="w-full sm:w-auto sm:min-w-40">
          Terminer
        </Button>
        {missed.length > 0 && (
          <TextAction onClick={onRetryMissed}>
            Refaire {missed.length > 1 ? `les ${missed.length} questions manquées` : "la question manquée"}
          </TextAction>
        )}
      </div>
    </motion.div>
  );
}

function message(accuracy: number) {
  if (accuracy === 1) return "Sans faute.";
  if (accuracy >= 0.8) return "Très bonne série.";
  if (accuracy >= 0.5) return "C'est en bonne voie : relis les explications ci-dessous.";
  return "Relis les explications ci-dessous, puis refais les questions manquées.";
}
