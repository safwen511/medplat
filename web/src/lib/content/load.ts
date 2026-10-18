import "server-only";

import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import type { ExerciseSet, Lesson, YearIndex } from "./types";

const ROOT = path.join(process.cwd(), "content");

function readJson<T>(...parts: string[]): T | null {
  const file = path.join(ROOT, ...parts);
  return existsSync(file) ? (JSON.parse(readFileSync(file, "utf-8")) as T) : null;
}

/** Faculty/year pairs that have exported content, e.g. [{faculty: "sfax", year: "dcem2"}]. */
export function availableYears(): { faculty: string; year: string }[] {
  if (!existsSync(ROOT)) return [];
  return readdirSync(ROOT).flatMap((faculty) =>
    readdirSync(path.join(ROOT, faculty))
      .filter((year) => existsSync(path.join(ROOT, faculty, year, "index.json")))
      .map((year) => ({ faculty, year })),
  );
}

export function yearIndex(faculty: string, year: string): YearIndex | null {
  return readJson<YearIndex>(faculty, year, "index.json");
}

export function lesson(faculty: string, year: string, lessonId: string): Lesson | null {
  return readJson<Lesson>(faculty, year, "lessons", `${lessonId}.json`);
}

export function exercises(faculty: string, year: string, lessonId: string): ExerciseSet | null {
  return readJson<ExerciseSet>(faculty, year, "exercises", `${lessonId}.json`);
}

export function availableLessonIds(faculty: string, year: string): string[] {
  const directory = path.join(ROOT, faculty, year, "lessons");
  return existsSync(directory)
    ? readdirSync(directory)
        .filter((file) => file.endsWith(".json"))
        .map((file) => file.replace(/\.json$/, ""))
    : [];
}
