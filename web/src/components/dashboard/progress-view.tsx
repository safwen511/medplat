"use client";

import { ArrowRight, CircleCheck, Flame, Lightbulb, ListChecks, Timer } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { Button } from "@/components/ui/button";
import { PageStack, SectionHeader } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/ui/stat-tile";
import type { YearIndex } from "@/lib/content/types";
import type { Attempt } from "@/lib/progress/store";
import { cn } from "@/lib/utils";

import { ActivityChart, type ActivityRow } from "./charts";
import {
  accuracy,
  addDays,
  certifHref,
  dayKey,
  formatSeconds,
  groupBy,
  lessonHref,
  lessonMap,
  median,
  quizHref,
  shortCertifTitle,
  streak,
  useStudentData,
} from "./data";

const WEAK_MIN_ATTEMPTS = 3;
const dayLabel = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });

export function ProgressView({ index }: { index: YearIndex }) {
  const data = useStudentData(index);
  const { attempts, now } = data;
  const stats = useMemo(() => computeStats(index, attempts, now), [index, attempts, now]);

  return (
    <PageStack className="max-w-5xl">
      <header className="flex flex-col gap-3">
        <p className="eyebrow">{index.yearLabel}</p>
        <h1 className="rise-in text-4xl leading-tight sm:text-5xl">Progression</h1>
      </header>

      {data.loading ? (
        <div aria-busy="true" aria-label="Chargement" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-28 rounded-card" />
          ))}
        </div>
      ) : attempts.length === 0 ? (
        <section className="panel flex flex-col items-start gap-6">
          <p className="text-lg text-muted">Réponds à tes premières questions pour voir ta progression ici.</p>
          <Button asChild size="lg" className="shadow-glow">
            <Link href={quizHref(index)}>Commencer un quiz</Link>
          </Button>
        </section>
      ) : (
        <>
          <section aria-label="En bref" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile
              icon={<ListChecks className="size-4" aria-hidden />}
              label="questions répondues"
              value={stats.overall.total.toLocaleString("fr-FR")}
            />
            <StatTile
              icon={<CircleCheck className="size-4" aria-hidden />}
              label="bonnes réponses"
              value={`${stats.overall.percent} %`}
            />
            <StatTile icon={<Flame className="size-4" aria-hidden />} label="série de jours" value={stats.streak} />
            <StatTile
              icon={<Timer className="size-4" aria-hidden />}
              label="temps médian"
              value={formatSeconds(stats.medianTime)}
              hint={
                stats.medianCorrect !== null && stats.medianWrong !== null
                  ? `juste ${formatSeconds(stats.medianCorrect)} · faux ${formatSeconds(stats.medianWrong)}`
                  : undefined
              }
            />
            {stats.hinted > 0 && (
              <>
                <StatTile
                  icon={<Lightbulb className="size-4" aria-hidden />}
                  label="questions avec indice"
                  value={`${stats.hintShare} %`}
                />
                <StatTile label="justes sans indice" value={`${stats.withoutHints.percent ?? 0} %`} />
                <StatTile label="justes avec indice" value={`${stats.withHints.percent ?? 0} %`} />
              </>
            )}
          </section>

          <section aria-labelledby="activity-title" className="flex flex-col gap-6">
            <SectionHeader
              id="activity-title"
              title="30 derniers jours"
              action={
                <span className="flex gap-2 text-sm">
                  <span className="rounded-full bg-primary-soft px-3 py-1 text-primary">
                    <span className="numeral font-semibold">{stats.last30Total}</span> questions
                  </span>
                  <span className="rounded-full border border-border px-3 py-1 text-muted">
                    <span className="numeral font-semibold text-foreground">{stats.activeDays}</span> jours actifs
                  </span>
                </span>
              }
            />
            <div className="panel">
              <ActivityChart rows={stats.activity} />
            </div>
            <div className="sr-only">
              <table>
                <caption>Questions par jour, 30 derniers jours</caption>
                <thead>
                  <tr>
                    <th scope="col">Jour</th>
                    <th scope="col">Questions</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.activity
                    .filter((row) => row.count > 0)
                    .map((row) => (
                      <tr key={row.key}>
                        <th scope="row">{row.label}</th>
                        <td>{row.count}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </section>

          <div className="grid gap-12 lg:grid-cols-2 lg:gap-8 [&>*]:min-w-0">
            {stats.byCertif.length > 0 && (
              <section aria-labelledby="certifs-title" className="flex flex-col gap-5">
                <SectionHeader id="certifs-title" title="Par certif" subtitle="Bonnes réponses et nombre de réponses." />
                <ul className="flex flex-col gap-1">
                  {stats.byCertif.map((row) => (
                    <li key={row.certif.slug}>
                      <Link
                        href={certifHref(index, row.certif)}
                        className="-mx-2 flex flex-col gap-2 rounded-card px-2 py-3 transition-colors duration-150 hover:bg-surface focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                      >
                        <span className="flex items-baseline justify-between gap-4">
                          <span className="min-w-0 truncate font-medium">{shortCertifTitle(row.certif.title)}</span>
                          <span className="shrink-0 text-sm text-muted tabular-nums">
                            <span className="numeral font-semibold text-foreground">{row.score.percent} %</span> ·{" "}
                            {row.score.total}
                          </span>
                        </span>
                        <span aria-hidden className="h-1.5 overflow-hidden rounded-full bg-surface-muted">
                          <span
                            className={cn("block h-full rounded-full", tone(row.score.percent ?? 0, "bar"))}
                            style={{ width: `${row.score.percent}%` }}
                          />
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section aria-labelledby="weak-title" className="flex flex-col gap-5">
              <SectionHeader
                id="weak-title"
                title="À retravailler"
                subtitle={`Les cours avec le moins de bonnes réponses (au moins ${WEAK_MIN_ATTEMPTS} réponses).`}
              />
              {stats.weakest.length === 0 ? (
                <p className="text-muted">Pas encore assez de réponses par cours.</p>
              ) : (
                <ol className="flex flex-col gap-2">
                  {stats.weakest.map((row) => (
                    <li key={row.lesson.id}>
                      <Link
                        href={row.lesson.available ? lessonHref(index, row.lesson) : certifHref(index, row.certif)}
                        className="flex min-h-14 items-center gap-4 rounded-card border border-border bg-surface px-4 py-3 transition-shadow duration-200 hover:shadow-glow focus-visible:shadow-glow focus-visible:outline-none"
                      >
                        <span
                          className={cn(
                            "numeral w-16 shrink-0 rounded-control py-1 text-center text-lg font-semibold",
                            tone(row.score.percent ?? 0, "badge"),
                          )}
                        >
                          {row.score.percent} %
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="line-clamp-2 leading-snug font-medium">{row.lesson.title}</span>
                          <span className="block truncate text-sm text-muted tabular-nums">
                            {shortCertifTitle(row.certif.title)} · {row.score.correct}/{row.score.total}
                          </span>
                        </span>
                        <ArrowRight className="size-4 shrink-0 text-muted" aria-hidden />
                      </Link>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>
        </>
      )}
    </PageStack>
  );
}

/** Colour for an accuracy: red under 50 %, amber under 75 %, green above. */
function tone(percent: number, kind: "bar" | "badge") {
  if (percent < 50) return kind === "bar" ? "bg-wrong" : "bg-wrong-soft text-wrong";
  if (percent < 75) return kind === "bar" ? "bg-highyield" : "bg-highyield-soft text-highyield";
  return kind === "bar" ? "bg-correct" : "bg-correct-soft text-correct";
}

function computeStats(index: YearIndex, attempts: Attempt[], now: Date) {
  const lessons = lessonMap(index);
  const overall = accuracy(attempts);

  const byCertifGroups = groupBy(attempts, (item) => lessons.get(item.lessonId)?.certif.slug ?? "");
  const byCertif = index.certifs.flatMap((certif) => {
    const group = byCertifGroups.get(certif.slug);
    return group ? [{ certif, score: accuracy(group) }] : [];
  });

  const perDay = groupBy(attempts, (item) => dayKey(new Date(item.createdAt)));
  const activity: ActivityRow[] = Array.from({ length: 30 }, (_, i) => {
    const day = addDays(now, i - 29);
    const key = dayKey(day);
    return { key, label: dayLabel.format(day), count: perDay.get(key)?.length ?? 0 };
  });

  const hinted = attempts.filter((item) => item.hintsUsed > 0);
  const byLesson = groupBy(attempts, (item) => item.lessonId);
  const weakest = [...byLesson]
    .flatMap(([lessonId, group]) => {
      const ref = lessons.get(lessonId);
      const score = accuracy(group);
      return ref && group.length >= WEAK_MIN_ATTEMPTS && score.correct < score.total ? [{ ...ref, score }] : [];
    })
    .sort((a, b) => (a.score.percent ?? 0) - (b.score.percent ?? 0) || b.score.total - a.score.total)
    .slice(0, 5);

  return {
    overall,
    medianTime: median(attempts.map((item) => item.timeMs)),
    medianCorrect: median(attempts.filter((item) => item.correct).map((item) => item.timeMs)),
    medianWrong: median(attempts.filter((item) => !item.correct).map((item) => item.timeMs)),
    streak: streak(attempts, now),
    byCertif,
    activity,
    last30Total: activity.reduce((sum, row) => sum + row.count, 0),
    activeDays: activity.filter((row) => row.count > 0).length,
    hinted: hinted.length,
    hintShare: attempts.length ? Math.round((hinted.length / attempts.length) * 100) : 0,
    withHints: accuracy(hinted),
    withoutHints: accuracy(attempts.filter((item) => item.hintsUsed === 0)),
    weakest,
  };
}
