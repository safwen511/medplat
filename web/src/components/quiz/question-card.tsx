"use client";

import { ArrowRight, Check, Clock, Flame, X } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Exercise } from "@/lib/content/types";
import { useProgress } from "@/lib/progress/provider";
import type { Mode } from "@/lib/progress/store";
import { cn } from "@/lib/utils";

import { AnswerInput } from "./answers";
import { emptyResponse, formatDuration, grade, isAnswerable, responsePayload, TYPE_LABELS, type Response } from "./grading";
import { HintLadder } from "./hint-ladder";
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
 * One question: answer UI, hint ladder, submit, feedback. The timer runs from first display to
 * submit. Mount with `key={exercise.id}` so each question starts fresh.
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
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(0);
  const feedbackRef = useRef<HTMLDivElement>(null);
  const nextRef = useRef<HTMLButtonElement>(null);
  const submitted = result !== null;

  useEffect(() => {
    startRef.current = performance.now();
  }, []);

  useEffect(() => {
    if (submitted) return;
    const timer = window.setInterval(() => setElapsed(performance.now() - startRef.current), 1000);
    return () => window.clearInterval(timer);
  }, [submitted]);

  useEffect(() => {
    if (!submitted) return;
    feedbackRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    nextRef.current?.focus({ preventScroll: true });
  }, [submitted]);

  const answerable = isAnswerable(exercise, response);

  const submit = () => {
    if (submitted || !answerable) return;
    const timeMs = performance.now() - startRef.current;
    const { correct, score, total } = grade(exercise, response);
    const next: AnswerResult = { exercise, correct, score, total, timeMs, hintsUsed, response };
    setElapsed(timeMs);
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

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        {header}
        <Badge tone="primary">{TYPE_LABELS[exercise.type]}</Badge>
        {exercise.highYield && (
          <Badge tone="highyield">
            <Flame aria-hidden /> Tombe souvent
          </Badge>
        )}
        {showTimer && (
          <span
            className="ml-auto inline-flex items-center gap-1 text-xs tabular-nums text-muted/80"
            aria-label={`Temps écoulé : ${formatDuration(elapsed)}`}
          >
            <Clock className="size-3" aria-hidden />
            {formatDuration(elapsed)}
          </span>
        )}
      </div>

      <h3 className="whitespace-pre-line text-lg font-semibold leading-snug sm:text-xl">{exercise.stem}</h3>

      <AnswerInput
        exercise={exercise}
        response={response}
        onChange={setResponse}
        submitted={submitted}
        onSubmit={submit}
      />

      {hints && (
        <HintLadder
          hints={exercise.hints}
          used={hintsUsed}
          onReveal={() => setHintsUsed((count) => Math.min(3, count + 1))}
          disabled={submitted}
        />
      )}

      {result ? (
        <motion.div
          ref={feedbackRef}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: [0.2, 0, 0, 1] }}
          className={cn(
            "flex flex-col gap-3 rounded-card border p-4 sm:p-5",
            result.correct ? "border-correct/40 bg-correct-soft" : "border-wrong/40 bg-wrong-soft",
          )}
          role="status"
        >
          <div className="flex flex-wrap items-center gap-3">
            <motion.span
              initial={{ scale: 0.6 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 420, damping: 18 }}
              className={cn(
                "flex size-9 items-center justify-center rounded-full text-surface",
                result.correct ? "bg-correct" : "bg-wrong",
              )}
            >
              {result.correct ? (
                <Check className="size-5" strokeWidth={3} aria-hidden />
              ) : (
                <X className="size-5" strokeWidth={3} aria-hidden />
              )}
            </motion.span>
            <p className="text-base font-semibold">{result.correct ? "Bonne réponse" : "Réponse incorrecte"}</p>
            {result.total > 1 && (
              <span className="rounded-full bg-surface/70 px-2.5 py-0.5 text-xs font-medium text-muted">
                {result.score}/{result.total} {unitLabel(exercise)}
              </span>
            )}
          </div>
          {exercise.explanation && (
            <p className="whitespace-pre-line text-[0.95rem] leading-relaxed text-foreground">{exercise.explanation}</p>
          )}
          {exercise.citations && <p className="text-xs text-muted">Sources : {exercise.citations}</p>}
        </motion.div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <ReportError lessonId={exercise.lessonId} questionId={exercise.id} />
        {submitted ? (
          <Button ref={nextRef} size="lg" onClick={onNext}>
            {nextLabel}
            <ArrowRight aria-hidden />
          </Button>
        ) : (
          <Button size="lg" onClick={submit} disabled={!answerable}>
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
