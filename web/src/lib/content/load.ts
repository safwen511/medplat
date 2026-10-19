import "server-only";

import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { SHOW_FIGURES } from "@/lib/flags";

import type { ExerciseSet, GlossaryEntry, Lesson, SourceRef, YearIndex } from "./types";

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

const ROLE_TITLES: Record<string, string> = {
  official_slides: "Diapositives officielles",
  official_polycopie: "Polycopié officiel",
  student_summary: "Résumé étudiant",
  tips: "Astuces",
  tutorial: "Tutoriel",
  reference_book: "Ouvrage de référence",
};

/**
 * Source labels name their authors (teachers, students, sometimes in the file title): they never
 * leave the server. The page only gets the source's kind.
 */
function anonymous(source: SourceRef): SourceRef {
  return { ...source, label: ROLE_TITLES[source.role] ?? "Document du cours" };
}

export function lesson(faculty: string, year: string, lessonId: string): Lesson | null {
  const data = readJson<Lesson>(faculty, year, "lessons", `${lessonId}.json`);
  if (!data) return null;
  return { ...data, sources: data.sources.map(anonymous), figures: SHOW_FIGURES ? data.figures : [] };
}

export function exercises(faculty: string, year: string, lessonId: string): ExerciseSet | null {
  const data = readJson<ExerciseSet>(faculty, year, "exercises", `${lessonId}.json`);
  if (!data || SHOW_FIGURES) return data;
  return { ...data, items: data.items.filter((item) => item.type !== "image") };
}

/** The lesson's glossary (Arabic lens): exported by the pipeline, else a committed fixture. */
export function glossary(faculty: string, year: string, lessonId: string): GlossaryEntry[] {
  const exported = readJson<GlossaryEntry[]>(faculty, year, "glossary", `${lessonId}.json`);
  if (exported) return exported;
  const fixture = path.join(process.cwd(), "fixtures", "glossary", `${lessonId}.json`);
  return existsSync(fixture) ? (JSON.parse(readFileSync(fixture, "utf-8")) as GlossaryEntry[]) : [];
}

export function availableLessonIds(faculty: string, year: string): string[] {
  const directory = path.join(ROOT, faculty, year, "lessons");
  return existsSync(directory)
    ? readdirSync(directory)
        .filter((file) => file.endsWith(".json"))
        .map((file) => file.replace(/\.json$/, ""))
    : [];
}
