"use client";

import Image from "next/image";
import { Check, ZoomIn } from "lucide-react";
import { useMemo } from "react";

import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import type { Figure, ImageExercise, QcmExercise, QrmExercise } from "@/lib/content/types";
import { cn } from "@/lib/utils";

import { shuffledOptions, type Response } from "../grading";
import { Mark, markClasses, markOf } from "./marks";

type ChoiceExercise = QcmExercise | QrmExercise | ImageExercise;
type ChoiceResponse = Extract<Response, { type: "qcm" | "qrm" | "image" }>;

export function ChoiceAnswer({
  exercise,
  response,
  onChange,
  submitted,
}: {
  exercise: ChoiceExercise;
  response: ChoiceResponse;
  onChange: (response: Response) => void;
  submitted: boolean;
}) {
  const options = useMemo(() => shuffledOptions(exercise.id, exercise.options), [exercise.id, exercise.options]);
  const multiple = exercise.type === "qrm";
  const chosen = new Set(response.type === "qrm" ? response.choices : response.choice ? [response.choice] : []);
  const expected = new Set(exercise.type === "qrm" ? exercise.answer : [exercise.answer]);

  const toggle = (id: string) => {
    if (submitted) return;
    if (response.type === "qrm") {
      const next = chosen.has(id) ? response.choices.filter((value) => value !== id) : [...response.choices, id];
      onChange({ type: "qrm", choices: next });
    } else {
      onChange({ type: response.type, choice: id });
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {exercise.type === "image" && <ZoomableFigure figure={exercise.figure} />}
      {multiple && !submitted && <p className="text-sm text-muted">Plusieurs réponses possibles.</p>}
      <div role={multiple ? "group" : "radiogroup"} aria-label="Propositions" className="flex flex-col gap-2">
        {options.map((option) => {
          const isChosen = chosen.has(option.id);
          const state = submitted ? markOf(expected.has(option.id), isChosen) : "neutral";
          return (
            <button
              key={option.id}
              type="button"
              role={multiple ? "checkbox" : "radio"}
              aria-checked={isChosen}
              aria-disabled={submitted}
              onClick={() => toggle(option.id)}
              className={cn(
                "flex min-h-14 w-full items-center gap-4 rounded-card border px-4 py-3 text-left text-[1.0625rem] leading-snug transition-[color,background-color,border-color,box-shadow,scale] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                !submitted && "active:scale-[0.99]",
                !submitted && isChosen && "border-primary/70 bg-primary-soft shadow-glow",
                !submitted && !isChosen && "border-border bg-surface hover:border-border-strong hover:bg-surface-muted/60",
                submitted && markClasses[state],
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "flex size-5 shrink-0 items-center justify-center border transition-colors duration-150",
                  multiple ? "rounded-[5px]" : "rounded-full",
                  isChosen ? "border-primary bg-primary text-primary-foreground" : "border-muted/60",
                  submitted && !isChosen && "opacity-50",
                )}
              >
                {isChosen &&
                  (multiple ? (
                    <Check className="size-3.5" strokeWidth={2.5} />
                  ) : (
                    <span className="size-2 rounded-full bg-primary-foreground" />
                  ))}
              </span>
              <span className={cn("flex-1", state === "neutral" && submitted ? "text-muted" : "text-foreground")}>
                {option.text}
                {state === "missed" && (
                  <span className="mt-0.5 block text-sm text-correct">Réponse attendue</span>
                )}
              </span>
              {submitted && <Mark state={state} />}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function ZoomableFigure({ figure }: { figure: Figure }) {
  const unoptimized = figure.src.startsWith("data:");
  return (
    <Dialog>
      <DialogTrigger asChild>
        <button
          type="button"
          className="group flex flex-col gap-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-card"
        >
          <Image
            src={figure.src}
            alt={`Figure (${figure.source} p.${figure.page})`}
            width={figure.width}
            height={figure.height}
            unoptimized={unoptimized}
            className="h-auto max-h-[60vh] w-full rounded-card border border-border object-contain"
          />
          <span className="inline-flex items-center gap-1.5 text-sm text-muted group-hover:text-foreground">
            <ZoomIn className="size-4" strokeWidth={1.5} aria-hidden /> Agrandir la figure
          </span>
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-5xl p-3 sm:p-4">
        <DialogTitle className="sr-only">Figure agrandie</DialogTitle>
        <Image
          src={figure.src}
          alt={`Figure (${figure.source} p.${figure.page})`}
          width={figure.width}
          height={figure.height}
          unoptimized={unoptimized}
          className="h-auto max-h-[85vh] w-full object-contain"
        />
        <p className="mt-2 text-xs text-muted">
          Source : {figure.source} p.{figure.page}
        </p>
      </DialogContent>
    </Dialog>
  );
}
