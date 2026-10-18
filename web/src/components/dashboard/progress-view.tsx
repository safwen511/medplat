"use client";

import Link from "next/link";
import { useMemo, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import type { YearIndex } from "@/lib/content/types";
import type { Attempt } from "@/lib/progress/store";

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
import { Column, LoadingLines } from "./parts";

const WEAK_MIN_ATTEMPTS = 3;
const dayLabel = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });

const plural = (count: number, word: string) => `${count} ${word}${count > 1 ? "s" : ""}`;

export function ProgressView({ index }: { index: YearIndex }) {
  const data = useStudentData(index);
  const { attempts, now } = data;
  const stats = useMemo(() => computeStats(index, attempts, now), [index, attempts, now]);

  return (
    <Column className="gap-12">
      <header className="flex flex-col gap-3">
        <p className="text-sm text-muted">{index.yearLabel}</p>
        <h1 className="text-3xl leading-tight sm:text-4xl">Progression</h1>
      </header>

      {data.loading ? (
        <LoadingLines count={3} />
      ) : attempts.length === 0 ? (
        <section className="flex flex-col items-start gap-6">
          <p className="text-lg text-muted">Réponds à tes premières questions pour voir ta progression ici.</p>
          <Button asChild size="lg">
            <Link href={quizHref(index)}>Commencer un quiz</Link>
          </Button>
        </section>
      ) : (
        <>
          <section aria-label="En bref" className="flex flex-col gap-4 text-lg">
            <p>
              Tu as répondu à <Strong>{plural(stats.overall.total, "question")}</Strong>, dont{" "}
              <Strong>{stats.overall.percent} %</Strong> de réponses justes.
            </p>
            <p className="text-muted">
              Temps médian par question : {formatSeconds(stats.medianTime)}
              {stats.medianCorrect !== null && stats.medianWrong !== null
                ? ` (${formatSeconds(stats.medianCorrect)} quand c'est juste, ${formatSeconds(stats.medianWrong)} quand c'est faux).`
                : "."}
              {stats.streak > 0 && ` Série en cours : ${plural(stats.streak, "jour")}.`}
            </p>
            {stats.hinted > 0 && (
              <p className="text-muted">
                Indices utilisés sur {stats.hintShare} % des questions ; {stats.withoutHints.percent ?? 0} % de justes
                sans indice, {stats.withHints.percent ?? 0} % avec.
              </p>
            )}
          </section>

          <section aria-labelledby="activity-title" className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <h2 id="activity-title" className="text-xl">
                30 derniers jours
              </h2>
              <p className="text-muted">
                {plural(stats.last30Total, "question")} sur {plural(stats.activeDays, "jour")} actif
                {stats.activeDays > 1 ? "s" : ""}.
              </p>
            </div>
            <ActivityChart rows={stats.activity} />
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

          {stats.byCertif.length > 0 && (
            <section aria-labelledby="certifs-title" className="flex flex-col gap-2">
              <h2 id="certifs-title" className="text-xl">
                Par certif
              </h2>
              <ul className="flex flex-col">
                {stats.byCertif.map((row) => (
                  <li
                    key={row.certif.slug}
                    className="flex min-h-12 items-baseline justify-between gap-4 border-b border-border py-3 last:border-b-0"
                  >
                    <Link
                      href={certifHref(index, row.certif)}
                      className="min-w-0 truncate underline decoration-border underline-offset-4 hover:decoration-foreground"
                    >
                      {shortCertifTitle(row.certif.title)}
                    </Link>
                    <span className="shrink-0 text-sm text-muted tabular-nums">
                      {row.score.percent} % · {plural(row.score.total, "réponse")}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section aria-labelledby="weak-title" className="flex flex-col gap-2">
            <div className="flex flex-col gap-1">
              <h2 id="weak-title" className="text-xl">
                À retravailler
              </h2>
              <p className="text-muted">
                {stats.weakest.length === 0
                  ? `Pas encore assez de réponses par cours (il en faut au moins ${WEAK_MIN_ATTEMPTS}).`
                  : `Les cours où tu as le moins de réponses justes, parmi ceux avec au moins ${WEAK_MIN_ATTEMPTS} réponses.`}
              </p>
            </div>
            {stats.weakest.length > 0 && (
              <ol className="flex flex-col">
                {stats.weakest.map((row) => (
                  <li
                    key={row.lesson.id}
                    className="flex min-h-14 items-center justify-between gap-4 border-b border-border py-3 last:border-b-0"
                  >
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <span className="truncate">{row.lesson.title}</span>
                      <span className="truncate text-sm text-muted tabular-nums">
                        {shortCertifTitle(row.certif.title)} · {row.score.percent} % ({row.score.correct}/
                        {row.score.total})
                      </span>
                    </div>
                    <Link
                      href={row.lesson.available ? lessonHref(index, row.lesson) : certifHref(index, row.certif)}
                      aria-label={`${row.lesson.available ? "Revoir le cours" : "Voir le certif"} « ${row.lesson.title} »`}
                      className="inline-flex min-h-12 shrink-0 items-center rounded-card px-1 text-sm text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                    >
                      {row.lesson.available ? "Revoir le cours" : "Voir le certif"}
                    </Link>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </>
      )}
    </Column>
  );
}

function Strong({ children }: { children: ReactNode }) {
  return <span className="font-medium tabular-nums">{children}</span>;
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
