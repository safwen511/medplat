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
    <p className="rounded-card border border-border bg-surface p-4 text-[1.0625rem] leading-[2.3]">
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
                "h-9 rounded-md border-b-2 bg-surface-muted px-2 text-base leading-none transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                !submitted && "border-primary/50 focus:border-primary",
                submitted && ok && "border-correct bg-correct-soft",
                submitted && !ok && "border-wrong bg-wrong-soft",
              )}
            />
            {submitted && <Mark state={ok ? "correct" : "wrong"} />}
            {submitted && !ok && (
              <span className="rounded-md bg-correct-soft px-2 py-0.5 text-sm leading-normal text-foreground">
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
