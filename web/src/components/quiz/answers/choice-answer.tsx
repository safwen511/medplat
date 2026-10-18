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
      {multiple && (
        <p className="text-sm font-medium text-primary">Plusieurs réponses possibles</p>
      )}
      <div
        role={multiple ? "group" : "radiogroup"}
        aria-label="Propositions"
        className="flex flex-col gap-2.5"
      >
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
                "flex min-h-12 w-full items-center gap-3 rounded-card border px-4 py-3 text-left text-[0.95rem] transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                !submitted && "hover:border-primary/60 hover:bg-surface-muted active:scale-[0.99]",
                !submitted && isChosen && "border-primary bg-primary-soft shadow-sm",
                !submitted && !isChosen && "border-border bg-surface",
                submitted && markClasses[state],
                submitted && state === "neutral" && "opacity-70",
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "flex size-5 shrink-0 items-center justify-center border-2 transition-colors",
                  multiple ? "rounded-md" : "rounded-full",
                  isChosen ? "border-primary bg-primary text-primary-foreground" : "border-border bg-surface",
                )}
              >
                {isChosen &&
                  (multiple ? (
                    <Check className="size-3.5" strokeWidth={3} />
                  ) : (
                    <span className="size-2 rounded-full bg-primary-foreground" />
                  ))}
              </span>
              <span className="flex-1 text-foreground">{option.text}</span>
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
          className="group relative overflow-hidden rounded-card border border-border bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label="Agrandir la figure"
        >
          <Image
            src={figure.src}
            alt={`Figure (${figure.source} p.${figure.page})`}
            width={figure.width}
            height={figure.height}
            unoptimized={unoptimized}
            className="h-auto max-h-[60vh] w-full object-contain"
          />
          <span className="absolute bottom-2 right-2 inline-flex items-center gap-1 rounded-full bg-surface/90 px-2.5 py-1 text-xs text-muted shadow-sm transition-colors group-hover:text-foreground">
            <ZoomIn className="size-3.5" aria-hidden /> Agrandir
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
