"use client";

import { Check, X } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import type { Exercise } from "@/lib/content/types";
import { useProgress } from "@/lib/progress/provider";
import type { Mode } from "@/lib/progress/store";
import { cn } from "@/lib/utils";

import { AnswerInput } from "./answers";
import { emptyResponse, grade, isAnswerable, responsePayload, spokenDuration, TYPE_LABELS, type Response } from "./grading";
import { availableHints, HintLink, HintList } from "./hint-ladder";
import { ReportError } from "./report-error";

export interface AnswerResult {
  exercise: Exercise;
  correct: boolean;
  score: number;
  total: number;
  timeMs: number;
  hintsUsed: number;
  response: Response;
}

/**
 * One question: answer UI, hints on request, submit, then inline feedback, explanation and a
 * single "Suivant". The time runs from first display to submit (shown with the feedback when
 * `showTimer`). Mount with `key={exercise.id}` so each question starts fresh.
 */
export function QuestionCard({
  exercise,
  mode,
  faculty,
  year,
  header,
  onAnswered,
  onNext,
  nextLabel = "Suivant",
  hints = true,
  showTimer = true,
}: {
  exercise: Exercise;
  mode: Mode;
  faculty: string;
  year: string;
  header?: ReactNode;
  onAnswered?: (result: AnswerResult) => void;
  onNext: () => void;
  nextLabel?: string;
  hints?: boolean;
  showTimer?: boolean;
}) {
  const { store } = useProgress();
  const [response, setResponse] = useState<Response>(() => emptyResponse(exercise));
  const [hintsUsed, setHintsUsed] = useState(0);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const startRef = useRef(0);
  const nextRef = useRef<HTMLButtonElement>(null);
  const submitted = result !== null;

  useEffect(() => {
    startRef.current = performance.now();
  }, []);

  useEffect(() => {
    if (!submitted) return;
    // Bring the verdict, explanation and "Suivant" into view (the button last, above the phone nav).
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    nextRef.current?.scrollIntoView({ block: "nearest", behavior: reduced ? "auto" : "smooth" });
    nextRef.current?.focus({ preventScroll: true });
  }, [submitted]);

  const answerable = isAnswerable(exercise, response);

  const submit = () => {
    if (submitted || !answerable) return;
    const timeMs = performance.now() - startRef.current;
    const { correct, score, total } = grade(exercise, response);
    const next: AnswerResult = { exercise, correct, score, total, timeMs, hintsUsed, response };
    setResult(next);
    onAnswered?.(next);
    void store
      .recordAttempt({
        questionId: exercise.id,
        questionType: exercise.type,
        lessonId: exercise.lessonId,
        faculty,
        year,
        mode,
        correct,
        response: responsePayload(response),
        timeMs,
        hintsUsed,
      })
      .catch(() => {
        // Progress is best-effort: a failed write never blocks the student.
      });
  };

  const hintCount = hints ? availableHints(exercise.hints) : 0;
  const unit = unitLabel(exercise);

  return (
    <div className="flex flex-col gap-6">
      {header}
      {/* Weight 500 (inline: globals.css sets h3 to 600): long stems stay easy to read. */}
      <h3 className="whitespace-pre-line text-[1.375rem] leading-snug sm:text-[1.5rem]" style={{ fontWeight: 500 }}>
        <span className="sr-only">{TYPE_LABELS[exercise.type]} : </span>
        {exercise.stem}
      </h3>

      <AnswerInput
        exercise={exercise}
        response={response}
        onChange={setResponse}
        submitted={submitted}
        onSubmit={submit}
      />

      {hintCount > 0 && <HintList hints={exercise.hints} used={hintsUsed} />}

      {result ? (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18, ease: [0.2, 0, 0, 1] }}
          className="flex flex-col gap-3"
          role="status"
        >
          <p
            className={cn(
              "flex flex-wrap items-center gap-x-2 gap-y-1 text-lg font-medium",
              result.correct ? "text-correct" : "text-wrong",
            )}
          >
            {result.correct ? (
              <Check className="size-5" strokeWidth={2} aria-hidden />
            ) : (
              <X className="size-5" strokeWidth={2} aria-hidden />
            )}
            {result.correct ? "Bonne réponse" : "Réponse incorrecte"}
            {(result.total > 1 || showTimer) && (
              <span className="text-base font-normal text-muted">
                {result.total > 1 && ` · ${result.score}/${result.total}${unit ? ` ${unit}` : ""}`}
                {showTimer && ` · ${spokenDuration(result.timeMs)}`}
              </span>
            )}
          </p>
          {exercise.explanation && (
            <p className="whitespace-pre-line text-base leading-relaxed text-foreground">{exercise.explanation}</p>
          )}
          {exercise.citations && <p className="text-sm text-muted">Sources : {exercise.citations}</p>}
          <ReportError lessonId={exercise.lessonId} questionId={exercise.id} />
        </motion.div>
      ) : null}

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        {!submitted && hintCount > 0 ? (
          <HintLink
            used={hintsUsed}
            available={hintCount}
            onReveal={() => setHintsUsed((count) => Math.min(3, count + 1))}
          />
        ) : (
          <span aria-hidden className="hidden sm:block" />
        )}
        {submitted ? (
          <Button ref={nextRef} size="lg" onClick={onNext} className="w-full scroll-mb-24 sm:w-auto sm:min-w-40">
            {nextLabel}
          </Button>
        ) : (
          <Button size="lg" onClick={submit} disabled={!answerable} className="w-full sm:w-auto sm:min-w-40">
            Valider
          </Button>
        )}
      </div>
    </div>
  );
}

function unitLabel(exercise: Exercise) {
  switch (exercise.type) {
    case "qrm":
      return "propositions bien jugées";
    case "texte_a_trous":
      return "trous corrects";
    case "association":
      return "paires correctes";
    case "ordre":
      return "éléments bien placés";
    case "categories":
      return "éléments bien classés";
    default:
      return "";
  }
}
