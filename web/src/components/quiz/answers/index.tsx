"use client";

import type { Exercise, NumericExercise } from "@/lib/content/types";
import { cn } from "@/lib/utils";

import { parseNumber, type Response } from "../grading";
import { CategoriesAnswer, MatchingAnswer } from "./board-answers";
import { ChoiceAnswer } from "./choice-answer";
import { FillBlankAnswer } from "./fill-blank-answer";
import { Mark } from "./marks";
import { OrderingAnswer } from "./ordering-answer";
import { TrueFalseButtons } from "./true-false-answer";

export interface AnswerProps {
  exercise: Exercise;
  response: Response;
  onChange: (response: Response) => void;
  submitted: boolean;
  onSubmit?: () => void;
}

/** Answer UI for any exercise type; shows per-unit feedback once `submitted`. */
export function AnswerInput({ exercise, response, onChange, submitted, onSubmit }: AnswerProps) {
  const common = { onChange, submitted };
  switch (exercise.type) {
    case "qcm":
    case "qrm":
    case "image":
      if (response.type !== "qcm" && response.type !== "qrm" && response.type !== "image") return null;
      return <ChoiceAnswer exercise={exercise} response={response} {...common} />;
    case "vrai_faux":
      if (response.type !== "vrai_faux") return null;
      return (
        <TrueFalseButtons
          value={response.value}
          onPick={(value) => onChange({ type: "vrai_faux", value })}
          expected={submitted ? exercise.answer : undefined}
        />
      );
    case "texte_a_trous":
      if (response.type !== "texte_a_trous") return null;
      return <FillBlankAnswer exercise={exercise} response={response} {...common} />;
    case "association":
      if (response.type !== "association") return null;
      return <MatchingAnswer exercise={exercise} response={response} {...common} />;
    case "ordre":
      if (response.type !== "ordre") return null;
      return <OrderingAnswer exercise={exercise} response={response} {...common} />;
    case "categories":
      if (response.type !== "categories") return null;
      return <CategoriesAnswer exercise={exercise} response={response} {...common} />;
    case "numerique":
      if (response.type !== "numerique") return null;
      return <NumericAnswer exercise={exercise} response={response} {...common} onSubmit={onSubmit} />;
  }
}

const numberFormat = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 6 });

function NumericAnswer({
  exercise,
  response,
  onChange,
  submitted,
  onSubmit,
}: {
  exercise: NumericExercise;
  response: Extract<Response, { type: "numerique" }>;
  onChange: (response: Response) => void;
  submitted: boolean;
  onSubmit?: () => void;
}) {
  const value = parseNumber(response.value);
  const ok = value !== null && Math.abs(value - exercise.value) <= exercise.tolerance + 1e-9;
  const invalid = response.value.trim() !== "" && value === null;
  return (
    <div className="flex flex-col gap-3">
      <form
        className="flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit?.();
        }}
      >
        <div
          className={cn(
            "flex h-14 w-full max-w-xs items-center overflow-hidden rounded-card border bg-surface transition-colors duration-150 focus-within:border-primary",
            !submitted && "border-border",
            submitted && (ok ? "border-correct/60 bg-correct-soft" : "border-wrong/60 bg-wrong-soft"),
          )}
        >
          <input
            type="text"
            inputMode="decimal"
            autoComplete="off"
            value={response.value}
            readOnly={submitted}
            onChange={(event) => onChange({ type: "numerique", value: event.target.value })}
            aria-label="Valeur numérique"
            aria-invalid={invalid}
            placeholder="Valeur"
            className="h-full min-w-0 flex-1 bg-transparent px-4 text-xl tabular-nums focus:outline-none"
          />
          {exercise.unit && (
            <span className="flex h-full items-center px-4 text-base text-muted">
              {exercise.unit}
            </span>
          )}
        </div>
        {submitted && <Mark state={ok ? "correct" : "wrong"} />}
      </form>
      {invalid && !submitted && <p className="text-sm text-muted">Saisis un nombre (virgule ou point acceptés).</p>}
      {submitted && (
        <p className="text-base text-muted">
          Valeur attendue :{" "}
          <span className="font-medium text-foreground">
            {numberFormat.format(exercise.value)}
            {exercise.tolerance > 0 && ` ± ${numberFormat.format(exercise.tolerance)}`} {exercise.unit}
          </span>
        </p>
      )}
    </div>
  );
}
