import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { LessonView } from "@/components/lesson/lesson-view";
import { QuestionPlayer } from "@/components/quiz/question-player";
import type { ExerciseSet, Lesson } from "@/lib/content/types";

import { CompareTabs } from "./compare-tabs";

export const metadata = { title: "Comparer les modèles", robots: { index: false } };

const ROOT = path.join(process.cwd(), "content", "_compare");
const RUN_LABELS: Record<string, string> = { v2: "Opus 5.5", "test-sonnet-2": "Sonnet 5.5" };

interface Variant {
  label: string;
  lesson: Lesson;
  exercises: ExerciseSet | null;
}

function readJson<T>(file: string): T | null {
  return existsSync(file) ? (JSON.parse(readFileSync(file, "utf-8")) as T) : null;
}

/** Every lesson exported by a comparison run, with one variant per run (model). */
function comparisons() {
  const byLesson = new Map<string, { faculty: string; year: string; lessonId: string; variants: Variant[] }>();
  if (!existsSync(ROOT)) return [];
  for (const faculty of readdirSync(ROOT))
    for (const year of readdirSync(path.join(ROOT, faculty)))
      for (const run of readdirSync(path.join(ROOT, faculty, year)).sort()) {
        const lessons = path.join(ROOT, faculty, year, run, "lessons");
        if (!existsSync(lessons)) continue;
        for (const file of readdirSync(lessons)) {
          const lessonId = file.replace(/\.json$/, "");
          const lesson = readJson<Lesson>(path.join(lessons, file));
          if (!lesson) continue;
          const key = `${faculty}/${year}/${lessonId}`;
          const entry = byLesson.get(key) ?? { faculty, year, lessonId, variants: [] };
          entry.variants.push({
            label: RUN_LABELS[run] ?? run,
            lesson,
            exercises: readJson<ExerciseSet>(path.join(ROOT, faculty, year, run, "exercises", file)),
          });
          byLesson.set(key, entry);
        }
      }
  return [...byLesson.values()];
}

export default function Compare() {
  const items = comparisons();
  return (
    <div className="flex flex-col gap-10">
      <header className="flex flex-col gap-2">
        <span className="text-sm text-muted">Développement</span>
        <h1 className="text-3xl">Comparer les modèles</h1>
        <p className="max-w-2xl text-sm text-muted">
          Le même cours reconstruit par deux modèles, à partir des mêmes sources. Compare la clarté, la
          structure, la fidélité aux sources et ce que chaque version garde ou oublie.
        </p>
      </header>
      {items.length === 0 && <p className="text-muted">Aucune comparaison exportée pour l&apos;instant.</p>}
      {items.map(({ faculty, year, lessonId, variants }) => (
        <section key={`${year}-${lessonId}`} className="flex flex-col gap-4 border-t border-border pt-6">
          <h2 className="text-lg font-semibold">
            {variants[0]?.lesson.title ?? lessonId}{" "}
            <span className="text-sm font-normal text-muted">({year.toUpperCase()})</span>
          </h2>
          <CompareTabs
            labels={variants.map((variant) => {
              const errors = variant.lesson.validationErrors?.length ?? 0;
              return `${variant.label} · ${errors === 0 ? "validé" : `${errors} erreur${errors > 1 ? "s" : ""}`}`;
            })}
          >
            {variants.map((variant) => (
              <div key={variant.label} className="flex flex-col gap-8">
                {(variant.lesson.validationErrors?.length ?? 0) > 0 && (
                  <details className="mx-auto w-full max-w-[40rem] text-sm">
                    <summary className="cursor-pointer text-muted">
                      Brouillon non publié : {variant.lesson.validationErrors?.length} erreur(s) du validateur
                    </summary>
                    <ul className="mt-2 list-disc pl-5 text-foreground">
                      {variant.lesson.validationErrors?.map((error) => (
                        <li key={error}>{error}</li>
                      ))}
                    </ul>
                  </details>
                )}
                <LessonView lesson={variant.lesson} faculty={faculty} year={year} />
                {variant.exercises && variant.exercises.items.length > 0 && (
                  <div className="mx-auto w-full max-w-[40rem]">
                    <QuestionPlayer exercises={variant.exercises.items} mode="quiz" faculty={faculty} year={year} />
                  </div>
                )}
              </div>
            ))}
          </CompareTabs>
        </section>
      ))}
    </div>
  );
}
