"use client";

import { Fragment, useMemo } from "react";

import type { FillBlankExercise } from "@/lib/content/types";
import { cn } from "@/lib/utils";

import { blankAccepted, type Response } from "../grading";
import { Mark } from "./marks";

type Segment = { kind: "text"; value: string } | { kind: "blank"; id: string; n: number };

function segments(text: string): Segment[] {
  const result: Segment[] = [];
  let last = 0;
  let n = 0;
  for (const match of text.matchAll(/\{\{\s*([^}\s]+)\s*\}\}/g)) {
    if (match.index > last) result.push({ kind: "text", value: text.slice(last, match.index) });
    result.push({ kind: "blank", id: match[1], n: ++n });
    last = match.index + match[0].length;
  }
  if (last < text.length) result.push({ kind: "text", value: text.slice(last) });
  return result;
}

export function FillBlankAnswer({
  exercise,
  response,
  onChange,
  submitted,
}: {
  exercise: FillBlankExercise;
  response: Extract<Response, { type: "texte_a_trous" }>;
  onChange: (response: Response) => void;
  submitted: boolean;
}) {
  const parts = useMemo(() => segments(exercise.text), [exercise.text]);
  return (
    <p className="text-[1.125rem] leading-[3.25rem]">
      {parts.map((part, i) => {
        if (part.kind === "text") return <Fragment key={i}>{part.value}</Fragment>;
        const value = response.blanks[part.id] ?? "";
        const ok = blankAccepted(exercise.blanks[part.id], value);
        return (
          <span key={i} className="mx-1 inline-flex items-center gap-1.5 align-middle">
            <input
              type="text"
              value={value}
              readOnly={submitted}
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              aria-label={`Trou ${part.n}`}
              onChange={(event) =>
                onChange({ type: "texte_a_trous", blanks: { ...response.blanks, [part.id]: event.target.value } })
              }
              size={Math.max(8, value.length + 1)}
              className={cn(
                "h-12 rounded-card border bg-surface px-3 text-[1.0625rem] leading-none transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                !submitted && "border-border focus:border-primary",
                submitted && ok && "border-correct/60 bg-correct-soft",
                submitted && !ok && "border-wrong/60 bg-wrong-soft",
              )}
            />
            {submitted && <Mark state={ok ? "correct" : "wrong"} />}
            {submitted && !ok && (
              <span className="text-base leading-normal text-correct">
                <span className="sr-only">Réponse attendue : </span>
                {exercise.blanks[part.id]?.[0] ?? ""}
              </span>
            )}
          </span>
        );
      })}
    </p>
  );
}
