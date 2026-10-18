"use client";

import { useMemo } from "react";

import type { CategorizingExercise, MatchingExercise } from "@/lib/content/types";

import { shuffledOptions, type Response } from "../grading";
import { PlacementBoard } from "./placement-board";

const invert = (record: Record<string, string>) =>
  Object.fromEntries(Object.entries(record).map(([key, value]) => [value, key]));

export function MatchingAnswer({
  exercise,
  response,
  onChange,
  submitted,
}: {
  exercise: MatchingExercise;
  response: Extract<Response, { type: "association" }>;
  onChange: (response: Response) => void;
  submitted: boolean;
}) {
  const chips = useMemo(() => shuffledOptions(exercise.id, exercise.right), [exercise.id, exercise.right]);
  return (
    <PlacementBoard
      chips={chips}
      targets={exercise.left}
      placement={invert(response.pairs)}
      onChange={(placement) => onChange({ type: "association", pairs: invert(placement) })}
      submitted={submitted}
      expected={invert(exercise.pairs)}
      capacity={1}
      layout="columns"
      poolLabel="À associer"
    />
  );
}

export function CategoriesAnswer({
  exercise,
  response,
  onChange,
  submitted,
}: {
  exercise: CategorizingExercise;
  response: Extract<Response, { type: "categories" }>;
  onChange: (response: Response) => void;
  submitted: boolean;
}) {
  const chips = useMemo(() => shuffledOptions(exercise.id, exercise.items), [exercise.id, exercise.items]);
  return (
    <PlacementBoard
      chips={chips}
      targets={exercise.categories}
      placement={response.mapping}
      onChange={(mapping) => onChange({ type: "categories", mapping })}
      submitted={submitted}
      expected={exercise.mapping}
      layout="buckets"
      poolLabel="À classer"
    />
  );
}
