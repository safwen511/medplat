"use client";

import { ArrowLeft, ChevronDown, Flame, LayoutGrid, List, Lock, PlayCircle } from "lucide-react";
import Link from "next/link";
import { useMemo, useState, useSyncExternalStore } from "react";

import { CertifEmblem } from "@/components/cards/certif-art";
import { LessonCard } from "@/components/cards/lesson-card";
import { certifTheme } from "@/components/cards/themes";
import { statusOf, tierOf } from "@/components/cards/tiers";
import { Button } from "@/components/ui/button";
import { PageStack, Panel } from "@/components/ui/panel";
import { StatTile } from "@/components/ui/stat-tile";
import type { CertifSummary, LessonSummary, ModuleSummary, YearIndex } from "@/lib/content/types";

import {
  accuracy,
  certifLessons,
  certifQuizHref,
  formatPercent,
  groupBy,
  HIGH_YIELD_THRESHOLD,
  lessonCardStats,
  lessonHref,
  readingSummary,
  shortCertifTitle,
  useStudentData,
  yearHref,
  type StudentData,
} from "./data";
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
  const theme = certifTheme(certif);
  const lessons = certifLessons(certif);
  const ready = lessons.filter((lesson) => lesson.available);
  const soon = lessons.filter((lesson) => !lesson.available);
  const summary = readingSummary(ready, data.progress);
  const score = accuracy(data.attempts.filter((attempt) => lessons.some((lesson) => lesson.id === attempt.lessonId)));
  const modules = certif.modules
    .map((mod) => ({ ...mod, lessons: mod.lessons.filter((lesson) => lesson.available) }))
    .filter((mod) => mod.lessons.length > 0);

  return (
    <PageStack>
      <section aria-labelledby="certif-title" className="panel relative flex flex-col gap-8 overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-60"
          style={{
            background: `radial-gradient(55% 90% at 100% 0%, oklch(0.45 ${theme.chroma} ${theme.hue} / 0.45), transparent 70%)`,
          }}
        />
        <div className="relative flex flex-col gap-6">
          <Link
            href={yearHref(index)}
            className="-ml-1 inline-flex min-h-12 items-center gap-1.5 self-start rounded-card px-1 text-sm text-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <ArrowLeft className="size-4" strokeWidth={1.5} aria-hidden />
            Tes certifs
          </Link>
          <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-center gap-4">
              <CertifEmblem theme={theme} className="size-14 rounded-2xl shadow-depth-2" />
              <div className="flex min-w-0 flex-col gap-1">
                <p className="text-sm text-muted">
                  {index.yearLabel} · Pôle {certif.pole}
                </p>
                <h1 id="certif-title" className="text-3xl leading-tight sm:text-4xl">
                  {shortCertifTitle(certif.title)}
                </h1>
              </div>
            </div>
            {ready.length > 0 && (
              <Button asChild size="lg" className="self-start shadow-glow sm:self-center">
                <Link href={certifQuizHref(index, certif)}>
                  <PlayCircle aria-hidden /> Quiz sur ce certif
                </Link>
              </Button>
            )}
          </div>
        </div>
        <div className="relative grid grid-cols-3 gap-3">
          <StatTile
            label="disponibles"
            value={
              <>
                {ready.length}
                <span className="text-lg font-normal text-muted">/{lessons.length}</span>
              </>
            }
          />
          <StatTile label="maîtrisés" value={data.loading ? "–" : summary.mastered} />
          <StatTile label="précision" value={data.loading ? "–" : formatPercent(score.percent)} />
        </div>
      </section>

      <Panel
        id="cours"
        title="Cours disponibles"
        subtitle={ready.length ? "Touche une carte pour son dossier : statut, chiffres, Lire et Quiz." : undefined}
        action={
          ready.length > 0 && (
            <div role="group" aria-label="Affichage" className="flex gap-1 rounded-control bg-surface p-1">
              {(["cartes", "liste"] as const).map((option) => (
                <Button
                  key={option}
                  variant={view === option ? "secondary" : "ghost"}
                  aria-pressed={view === option}
                  onClick={() => setView(option)}
                  className="h-10"
                >
                  {option === "cartes" ? <LayoutGrid aria-hidden /> : <List aria-hidden />}
                  {option === "cartes" ? "Cartes" : "Liste"}
                </Button>
              ))}
            </div>
          )
        }
      >
        {ready.length === 0 ? (
          <p className="text-muted">Les premiers cours de ce certif arrivent avec la prochaine vague.</p>
        ) : view === "cartes" ? (
          <CertifCards index={index} certif={certif} modules={modules} data={data} />
        ) : (
          modules.map((mod) => <ModuleSection key={mod.slug} index={index} certif={certif} module={mod} data={data} />)
        )}
      </Panel>

      {soon.length > 0 && <Soon lessons={soon} certif={certif} />}
    </PageStack>
  );
}

/** Lessons not published yet: one compact, collapsed list. */
function Soon({ lessons, certif }: { lessons: LessonSummary[]; certif: CertifSummary }) {
  const moduleOf = new Map(certif.modules.flatMap((mod) => mod.lessons.map((lesson) => [lesson.id, mod.title])));
  const ordered = [...lessons].sort((a, b) => b.pastExamCount - a.pastExamCount || a.order - b.order);
  return (
    <details className="panel group">
      <summary className="-m-2 flex min-h-12 cursor-pointer list-none items-center justify-between gap-4 rounded-control p-2 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none [&::-webkit-details-marker]:hidden">
        <span className="flex items-center gap-3">
          <Lock className="size-5 text-muted" aria-hidden />
          <span className="font-heading text-xl font-semibold sm:text-2xl">Bientôt disponibles</span>
          <span className="numeral rounded-full bg-surface-muted px-2.5 py-0.5 text-sm text-muted">{lessons.length}</span>
        </span>
        <ChevronDown className="size-5 text-muted transition-transform duration-200 group-open:rotate-180" aria-hidden />
      </summary>
      <p className="mt-4 text-sm text-muted">Les plus souvent tombés à l&apos;examen arrivent en premier.</p>
      <ul className="mt-4 grid gap-x-6 sm:grid-cols-2">
        {ordered.map((lesson) => (
          <li key={lesson.id} className="flex min-h-12 items-center gap-3 border-b border-border py-2">
            <span className="min-w-0 flex-1">
              <span className="block truncate text-foreground/85">{lesson.title}</span>
              <span className="block truncate text-xs text-muted">{moduleOf.get(lesson.id)}</span>
            </span>
            {lesson.pastExamCount >= HIGH_YIELD_THRESHOLD && (
              <span
                className="inline-flex shrink-0 items-center gap-0.5 rounded-full bg-highyield-soft px-2 py-0.5 text-xs font-semibold text-highyield"
                title={`Lié à ${lesson.pastExamCount} sujets d'examen`}
              >
                <Flame className="size-3" aria-hidden />
                {lesson.pastExamCount}
              </span>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}

/** The certif's available lessons as 3D cards (hover tilt, flip to the "dossier" back). */
function CertifCards({
  index,
  certif,
  modules,
  data,
}: {
  index: YearIndex;
  certif: CertifSummary;
  modules: ModuleSummary[];
  data: StudentData;
}) {
  const theme = certifTheme(certif);
  const byLesson = useMemo(() => groupBy(data.attempts, (attempt) => attempt.lessonId), [data.attempts]);
  const quizHref = certifQuizHref(index, certif);
  // Course numbers come from the full module (some sources leave order at 0: use the position).
  const numberOf = new Map(
    certif.modules.flatMap((mod) =>
      [...mod.lessons].sort((a, b) => a.order - b.order).map((lesson, position) => [lesson.id, lesson.order || position + 1]),
    ),
  );
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-[repeat(auto-fill,minmax(180px,1fr))] sm:gap-4">
      {modules.flatMap((mod) =>
        [...mod.lessons]
          .sort((a, b) => a.order - b.order)
          .map((lesson) => {
            const record = data.progress[lesson.id];
            return (
              <li key={lesson.id}>
                <LessonCard
                  lesson={{ ...lesson, order: numberOf.get(lesson.id) ?? lesson.order }}
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
          }),
      )}
    </ul>
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
