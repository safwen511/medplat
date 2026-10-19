"use client";

// Spaced review in three Leitner boxes: box 1 comes back after 1 day, box 2 after 3 days, box 3
// after 7 days. A miss sends an item back to box 1; a success moves it up; a success in box 3
// retires it. Terms ("Je ne savais pas" in recall mode) are stored here; questions are scheduled
// from the attempt history.

import type { Attempt } from "@/lib/progress/store";

export const INTERVALS = [1, 3, 7] as const;
const DAY = 86_400_000;

export interface TermItem {
  id: string; // lessonId|term
  term: string;
  lessonId: string;
  lessonTitle: string;
  href: string;
  box: 1 | 2 | 3;
  due: string; // ISO
}

const KEY = "medplat:v1:leitner";
const EVENT = "medplat:leitner";

export function readTerms(): TermItem[] {
  try {
    return JSON.parse(window.localStorage.getItem(KEY) ?? "[]") as TermItem[];
  } catch {
    return [];
  }
}

function writeTerms(items: TermItem[]) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(items));
  } catch {
    // kept for this visit only
  }
  window.dispatchEvent(new Event(EVENT));
}

export function onTermsChange(callback: () => void) {
  window.addEventListener(EVENT, callback);
  return () => window.removeEventListener(EVENT, callback);
}

function dueAfter(box: 1 | 2 | 3, from = Date.now()) {
  return new Date(from + INTERVALS[box - 1] * DAY).toISOString();
}

/** Records a recall answer for a key term of a lesson. */
export function recordTerm(
  entry: { term: string; lessonId: string; lessonTitle: string; href: string },
  knew: boolean,
) {
  const id = `${entry.lessonId}|${entry.term.toLocaleLowerCase("fr")}`;
  const items = readTerms();
  const current = items.find((item) => item.id === id);
  const others = items.filter((item) => item.id !== id);
  if (!knew) {
    writeTerms([...others, { ...entry, id, box: 1, due: dueAfter(1) }]);
    return;
  }
  if (!current) return; // known and never missed: nothing to schedule
  if (current.box === 3) writeTerms(others); // retired
  else {
    const box = (current.box + 1) as 2 | 3;
    writeTerms([...others, { ...current, box, due: dueAfter(box) }]);
  }
}

export interface QuestionItem {
  questionId: string;
  lessonId: string;
  box: 1 | 2 | 3;
  due: number;
}

/** Questions in review: replays each question's attempts through the boxes. */
export function questionSchedule(attempts: Attempt[]): QuestionItem[] {
  const byQuestion = new Map<string, Attempt[]>();
  for (const attempt of attempts) byQuestion.set(attempt.questionId, [...(byQuestion.get(attempt.questionId) ?? []), attempt]);
  const items: QuestionItem[] = [];
  for (const [questionId, list] of byQuestion) {
    let box: 0 | 1 | 2 | 3 = 0;
    let due = 0;
    for (const attempt of [...list].sort((a, b) => a.createdAt.localeCompare(b.createdAt))) {
      const time = new Date(attempt.createdAt).getTime();
      if (!attempt.correct) {
        box = 1;
        due = time + INTERVALS[0] * DAY;
      } else if (box > 0) {
        if (box === 3) box = 0;
        else {
          box = (box + 1) as 2 | 3;
          due = time + INTERVALS[box - 1] * DAY;
        }
      }
    }
    if (box > 0) items.push({ questionId, lessonId: list[0].lessonId, box: box as 1 | 2 | 3, due });
  }
  return items;
}

/** Due by the end of today. */
export function isDueToday(due: number | string, now: Date) {
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1).getTime();
  return (typeof due === "string" ? new Date(due).getTime() : due) < end;
}
