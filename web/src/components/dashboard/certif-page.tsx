"use client";

import { ArrowLeft, LayoutGrid, List } from "lucide-react";
import Link from "next/link";
import { useMemo, useState, useSyncExternalStore } from "react";

import { LessonCard } from "@/components/cards/lesson-card";
import { certifTheme } from "@/components/cards/themes";
import { statusOf, tierOf } from "@/components/cards/tiers";
import { Button } from "@/components/ui/button";
import type { CertifSummary, LessonSummary, ModuleSummary, YearIndex } from "@/lib/content/types";

import {
  certifLessons,
  certifQuizHref,
  groupBy,
  HIGH_YIELD_THRESHOLD,
  lessonCardStats,
  lessonHref,
  readingSummary,
  useStudentData,
  yearHref,
  type StudentData,
} from "./data";
import { Column } from "./parts";
import { StatusControl } from "./status-control";

type View = "cartes" | "liste";
const VIEW_KEY = "medplat:v1:certifView";

/** Cards (default) or list, remembered per browser; storage may be blocked (private mode). */
function readView(): View {
  try {
    return window.localStorage.getItem(VIEW_KEY) === "liste" ? "liste" : "cartes";
  } catch {
    return "cartes";
  }
}

function subscribeView(onChange: () => void) {
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
}

function useView(): [View, (view: View) => void] {
  const stored = useSyncExternalStore(subscribeView, readView, () => "cartes" as View);
  const [chosen, setChosen] = useState<View | null>(null);
  const choose = (next: View) => {
    setChosen(next);
    try {
      window.localStorage.setItem(VIEW_KEY, next);
    } catch {
      // remembered for this visit only
    }
  };
  return [chosen ?? stored, choose];
}

export function CertifPage({ index, certif }: { index: YearIndex; certif: CertifSummary }) {
  const data = useStudentData(index);
  const [view, setView] = useView();
  const lessons = certifLessons(certif);
  const available = lessons.filter((lesson) => lesson.available).length;
  const summary = readingSummary(lessons, data.progress);

  return (
    <div className="flex flex-col gap-12">
      <Column className="gap-12">
        <header className="flex flex-col gap-6">
          <Link
            href={yearHref(index)}
            className="-ml-1 inline-flex min-h-12 items-center gap-1.5 self-start rounded-card px-1 text-sm text-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <ArrowLeft className="size-4" strokeWidth={1.5} aria-hidden />
            Tes certifs
          </Link>
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted">
              {index.yearLabel} · Pôle {certif.pole}
            </p>
            <h1 className="text-3xl leading-tight sm:text-4xl">{certif.title}</h1>
            <p className="text-lg text-muted">
              {lessons.length} cours, dont {available} disponible{available > 1 ? "s" : ""}
              {data.loading
                ? "."
                : ` ; ${summary.read} lu${summary.read > 1 ? "s" : ""} et ${summary.mastered} maîtrisé${summary.mastered > 1 ? "s" : ""}.`}
            </p>
          </div>
          <Button asChild size="lg" className="self-start">
            <Link href={certifQuizHref(index, certif)}>Quiz sur ce certif</Link>
          </Button>
        </header>

        <div role="group" aria-label="Affichage" className="flex gap-1 self-start">
          {(["cartes", "liste"] as const).map((option) => (
            <Button
              key={option}
              variant={view === option ? "secondary" : "ghost"}
              aria-pressed={view === option}
              onClick={() => setView(option)}
            >
              {option === "cartes" ? <LayoutGrid aria-hidden /> : <List aria-hidden />}
              {option === "cartes" ? "Cartes" : "Liste"}
            </Button>
          ))}
        </div>

        {view === "liste" &&
          certif.modules.map((mod) => (
            <ModuleSection key={mod.slug} index={index} certif={certif} module={mod} data={data} />
          ))}
      </Column>
      {view === "cartes" && <CertifCards index={index} certif={certif} data={data} />}
    </div>
  );
}

/** The certif's lessons as 3D cards (hover tilt, flip to the "dossier" back). */
function CertifCards({
  index,
  certif,
  data,
}: {
  index: YearIndex;
  certif: CertifSummary;
  data: StudentData;
}) {
  const theme = certifTheme(certif);
  const byLesson = useMemo(() => groupBy(data.attempts, (attempt) => attempt.lessonId), [data.attempts]);
  const quizHref = certifQuizHref(index, certif);
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-12">
      {certif.modules.map((mod) => (
        <section key={mod.slug} aria-labelledby={`cards-${mod.slug}`} className="flex flex-col gap-4">
          <h2 id={`cards-${mod.slug}`} className="text-xl">
            {mod.title}
          </h2>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-[repeat(auto-fill,minmax(180px,1fr))] sm:gap-4">
            {[...mod.lessons]
              .sort((a, b) => a.order - b.order)
              .map((lesson, position) => {
                const record = data.progress[lesson.id];
                return (
                  <li key={lesson.id}>
                    <LessonCard
                      // Some modules have no course numbering (order 0): show the position instead.
                      lesson={lesson.order > 0 ? lesson : { ...lesson, order: position + 1 }}
                      moduleTitle={mod.title}
                      theme={theme}
                      tier={tierOf(record?.status)}
                      stats={lessonCardStats(byLesson.get(lesson.id) ?? [], record, data.now)}
                      loading={data.loading}
                      readHref={lessonHref(index, lesson)}
                      quizHref={quizHref}
                      onTierChange={(tier) => data.setStatus(lesson.id, statusOf(tier))}
                    />
                  </li>
                );
              })}
          </ul>
        </section>
      ))}
    </div>
  );
}

function ModuleSection({
  index,
  certif,
  module: mod,
  data,
}: {
  index: YearIndex;
  certif: CertifSummary;
  module: ModuleSummary;
  data: StudentData;
}) {
  const headingId = `module-${certif.slug}-${mod.slug}`;
  const summary = readingSummary(mod.lessons, data.progress);
  const lessons = [...mod.lessons].sort((a, b) => a.order - b.order);
  // A certif with a single module repeats its own title: the heading would only add noise.
  const showHeading = certif.modules.length > 1 || mod.title !== certif.title;

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id={headingId} className={showHeading ? "text-xl" : "sr-only"}>
          {mod.title}
        </h2>
        <p className="text-sm text-muted tabular-nums">{data.loading ? " " : summary.text}</p>
      </div>
      <ol className="flex flex-col">
        {lessons.map((lesson, position) => (
          <LessonRow key={lesson.id} index={index} lesson={lesson} position={position + 1} data={data} />
        ))}
      </ol>
    </section>
  );
}

function LessonRow({
  index,
  lesson,
  position,
  data,
}: {
  index: YearIndex;
  lesson: LessonSummary;
  /** 1-based place in the module, after sorting by `order` (some sources leave order at 0). */
  position: number;
  data: StudentData;
}) {
  const record = data.progress[lesson.id];
  const highYield = lesson.pastExamCount >= HIGH_YIELD_THRESHOLD;

  return (
    <li className="flex min-h-14 items-center gap-3 border-b border-border py-2 last:border-b-0 sm:gap-4">
      <span className="w-7 shrink-0 text-right text-sm text-muted tabular-nums">{position}</span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5 py-1">
        {lesson.available ? (
          <Link
            href={lessonHref(index, lesson)}
            className="self-start rounded-sm text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {lesson.title}
          </Link>
        ) : (
          <span className="text-muted">
            {lesson.title}
            <span className="ml-2 text-sm italic">bientôt</span>
          </span>
        )}
        {highYield && (
          <span className="text-sm text-highyield" title={`Lié à ${lesson.pastExamCount} sujets d'examen`}>
            souvent à l&apos;examen
          </span>
        )}
      </div>
      {data.loading ? (
        <span className="h-12 w-24 shrink-0" aria-hidden />
      ) : (
        <StatusControl
          status={record?.status ?? null}
          lessonTitle={lesson.title}
          onChange={(status) => data.setStatus(lesson.id, status)}
        />
      )}
    </li>
  );
}
