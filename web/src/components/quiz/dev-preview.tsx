"use client";

import type { Exercise } from "@/lib/content/types";

import { AnswerInput } from "./answers";
import { Mark } from "./answers/marks";
import { emptyResponse, grade, TYPE_LABELS, type Response } from "./grading";

/** Development only: each exercise shown already corrected, with a partly wrong demo response. */
export function FeedbackPreview({ exercises }: { exercises: Exercise[] }) {
  return (
    <div className="flex flex-col divide-y divide-border border-y border-border">
      {exercises.map((exercise) => {
        const response = demoResponse(exercise);
        const result = grade(exercise, response);
        return (
          <div key={exercise.id} className="flex flex-col gap-5 py-8">
            <p className="flex items-center gap-2 text-sm text-muted">
              {TYPE_LABELS[exercise.type]}
              <Mark state={result.correct ? "correct" : "wrong"} className="ml-auto" />
              <span className="tabular-nums">
                {result.score}/{result.total}
              </span>
            </p>
            <p className="font-serif text-[1.375rem] font-medium leading-snug">{exercise.stem}</p>
            <AnswerInput exercise={exercise} response={response} onChange={() => {}} submitted />
          </div>
        );
      })}
    </div>
  );
}

function demoResponse(exercise: Exercise): Response {
  switch (exercise.type) {
    case "qcm":
    case "image":
      return { type: exercise.type, choice: exercise.options.find((option) => option.id !== exercise.answer)!.id };
    case "qrm": {
      const wrong = exercise.options.find((option) => !exercise.answer.includes(option.id))!.id;
      return { type: "qrm", choices: [...exercise.answer.slice(1), wrong] };
    }
    case "vrai_faux":
      return { type: "vrai_faux", value: !exercise.answer };
    case "texte_a_trous": {
      const [first, ...rest] = Object.keys(exercise.blanks);
      return {
        type: "texte_a_trous",
        blanks: { [first]: exercise.blanks[first][0], ...Object.fromEntries(rest.map((id) => [id, "erreur"])) },
      };
    }
    case "association": {
      const lefts = exercise.left.map((left) => left.id);
      const pairs = { ...exercise.pairs };
      [pairs[lefts[0]], pairs[lefts[1]]] = [pairs[lefts[1]], pairs[lefts[0]]];
      return { type: "association", pairs };
    }
    case "ordre":
      return emptyResponse(exercise);
    case "categories":
      return {
        type: "categories",
        mapping: Object.fromEntries(exercise.items.map((item) => [item.id, exercise.categories[0].id])),
      };
    case "numerique":
      return { type: "numerique", value: String(exercise.value + exercise.tolerance + 1).replace(".", ",") };
  }
}
