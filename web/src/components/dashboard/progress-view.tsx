"use client";

import { Activity, ArrowRight, Check, Flame, Lightbulb, Percent, Timer, X } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { YearIndex } from "@/lib/content/types";
import type { Attempt, Mode } from "@/lib/progress/store";

import { ActivityChart, CertifAccuracyChart, type ActivityRow, type CertifAccuracyRow } from "./charts";
import {
  accuracy,
  addDays,
  certifHref,
  dayKey,
  formatPercent,
  formatSeconds,
  groupBy,
  lessonHref,
  lessonMap,
  median,
  shortCertifTitle,
  streak,
  useStudentData,
} from "./data";
import { LabelledProgress, LoadingBlocks, StatTile } from "./parts";

const MODE_LABELS: Record<Mode, string> = {
  lesson: "Fin de cours",
  quiz: "Quiz",
  game: "Jeu",
  exam: "Examen blanc",
};

const WEAK_MIN_ATTEMPTS = 3;
const dayLabel = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });

export function ProgressView({ index }: { index: YearIndex }) {
  const data = useStudentData(index);
  const { attempts, now } = data;
  const stats = useMemo(() => computeStats(index, attempts, now), [index, attempts, now]);
  const yearHref = `/${index.faculty}/${index.year}`;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Progression</h1>
        <p className="text-sm text-muted">{index.yearLabel}</p>
      </header>

      {data.loading ? (
        <LoadingBlocks count={3} />
      ) : attempts.length === 0 ? (
        <Card className="flex flex-col items-center gap-4 px-6 py-12 text-center">
          <Activity className="size-8 text-primary" aria-hidden />
          <p className="max-w-sm text-base font-medium">Réponds à tes premiers QCM pour voir ta progression</p>
          <Button asChild>
            <Link href={`${yearHref}/quiz`}>
              Lancer un quiz
              <ArrowRight aria-hidden />
            </Link>
          </Button>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile label="Questions répondues" value={stats.overall.total} icon={<Activity aria-hidden />} />
            <StatTile
              label="Précision"
              value={formatPercent(stats.overall.percent)}
              detail={`${stats.overall.correct} justes sur ${stats.overall.total}`}
              icon={<Percent aria-hidden />}
            />
            <StatTile
              label="Temps médian / question"
              value={formatSeconds(stats.medianTime)}
              icon={<Timer aria-hidden />}
            />
            <StatTile
              label="Série"
              value={`${stats.streak} ${stats.streak > 1 ? "jours" : "jour"}`}
              icon={<Flame aria-hidden />}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Précision par certif</CardTitle>
                <CardDescription>Part de réponses justes, certifs travaillés uniquement.</CardDescription>
              </CardHeader>
              <CardContent>
                <CertifAccuracyChart rows={stats.byCertif} />
                <table className="sr-only">
                  <caption>Précision par certif</caption>
                  <thead>
                    <tr>
                      <th scope="col">Certif</th>
                      <th scope="col">Précision</th>
                      <th scope="col">Réponses</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.byCertif.map((row) => (
                      <tr key={row.title}>
                        <th scope="row">{row.title}</th>
                        <td>{row.percent} %</td>
                        <td>{row.total}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Activité sur 30 jours</CardTitle>
                <CardDescription>
                  {stats.last30Total} question{stats.last30Total > 1 ? "s" : ""} sur {stats.activeDays} jour
                  {stats.activeDays > 1 ? "s" : ""} actif{stats.activeDays > 1 ? "s" : ""}.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ActivityChart rows={stats.activity} />
                <table className="sr-only">
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
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle>Temps de réponse</CardTitle>
                <CardDescription>Temps médian selon le résultat.</CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1 rounded-card bg-correct-soft p-3">
                  <span className="flex items-center gap-1 text-xs font-medium text-correct">
                    <Check className="size-3.5" aria-hidden />
                    Réponse juste
                  </span>
                  <span className="text-xl font-semibold tabular-nums">{formatSeconds(stats.medianCorrect)}</span>
                </div>
                <div className="flex flex-col gap-1 rounded-card bg-wrong-soft p-3">
                  <span className="flex items-center gap-1 text-xs font-medium text-wrong">
                    <X className="size-3.5" aria-hidden />
                    Réponse fausse
                  </span>
                  <span className="text-xl font-semibold tabular-nums">{formatSeconds(stats.medianWrong)}</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Précision par mode</CardTitle>
                <CardDescription>Fin de cours, quiz, jeu ou examen blanc.</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {stats.byMode.map((row) => (
                  <LabelledProgress
                    key={row.mode}
                    id={`mode-${row.mode}`}
                    label={MODE_LABELS[row.mode]}
                    value={row.percent ?? 0}
                    detail={`${formatPercent(row.percent)} · ${row.total} rép.`}
                  />
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Lightbulb className="size-4 text-primary" aria-hidden />
                  Indices
                </CardTitle>
                <CardDescription>
                  {stats.hintShare} % des questions avec au moins un indice ({stats.hintTotal} indice
                  {stats.hintTotal > 1 ? "s" : ""} au total).
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <LabelledProgress
                  id="hints-without"
                  label="Précision sans indice"
                  value={stats.withoutHints.percent ?? 0}
                  detail={`${formatPercent(stats.withoutHints.percent)} · ${stats.withoutHints.total} rép.`}
                />
                <LabelledProgress
                  id="hints-with"
                  label="Précision avec indice"
                  value={stats.withHints.percent ?? 0}
                  detail={`${formatPercent(stats.withHints.percent)} · ${stats.withHints.total} rép.`}
                />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Cours à retravailler</CardTitle>
              <CardDescription>
                Précision la plus basse, parmi les cours avec au moins {WEAK_MIN_ATTEMPTS} réponses.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {stats.weakest.length === 0 ? (
                <p className="text-sm text-muted">
                  Pas encore assez de réponses par cours. Continue à t&apos;entraîner.
                </p>
              ) : (
                <ol className="divide-y divide-border">
                  {stats.weakest.map((row) => (
                    <li key={row.lesson.id} className="flex items-center gap-3 py-3">
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium">{row.lesson.title}</p>
                        <p className="truncate text-xs text-muted">
                          {shortCertifTitle(row.certif.title)} ·{" "}
                          <span className="tabular-nums">
                            {row.score.percent} % ({row.score.correct}/{row.score.total})
                          </span>
                        </p>
                      </div>
                      <Button asChild variant="outline" size="sm">
                        <Link
                          href={row.lesson.available ? lessonHref(index, row.lesson) : certifHref(index, row.certif)}
                          aria-label={`Réviser « ${row.lesson.title} »`}
                        >
                          Réviser
                        </Link>
                      </Button>
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function computeStats(index: YearIndex, attempts: Attempt[], now: Date) {
  const lessons = lessonMap(index);
  const overall = accuracy(attempts);

  const byCertifGroups = groupBy(attempts, (item) => lessons.get(item.lessonId)?.certif.slug ?? "");
  const byCertif: CertifAccuracyRow[] = index.certifs.flatMap((certif) => {
    const group = byCertifGroups.get(certif.slug);
    if (!group) return [];
    const score = accuracy(group);
    return [
      { label: shortCertifTitle(certif.title), title: certif.title, percent: score.percent ?? 0, total: score.total },
    ];
  });

  const perDay = groupBy(attempts, (item) => dayKey(new Date(item.createdAt)));
  const activity: ActivityRow[] = Array.from({ length: 30 }, (_, i) => {
    const day = addDays(now, i - 29);
    const key = dayKey(day);
    return { key, label: dayLabel.format(day), count: perDay.get(key)?.length ?? 0 };
  });

  const byModeGroups = groupBy(attempts, (item) => item.mode);
  const byMode = (Object.keys(MODE_LABELS) as Mode[]).flatMap((mode) => {
    const group = byModeGroups.get(mode);
    return group ? [{ mode, ...accuracy(group) }] : [];
  });

  const hinted = attempts.filter((item) => item.hintsUsed > 0);
  const byLesson = groupBy(attempts, (item) => item.lessonId);
  const weakest = [...byLesson]
    .flatMap(([lessonId, group]) => {
      const ref = lessons.get(lessonId);
      return ref && group.length >= WEAK_MIN_ATTEMPTS ? [{ ...ref, score: accuracy(group) }] : [];
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
    byMode,
    hintShare: attempts.length ? Math.round((hinted.length / attempts.length) * 100) : 0,
    hintTotal: attempts.reduce((sum, item) => sum + item.hintsUsed, 0),
    withHints: accuracy(hinted),
    withoutHints: accuracy(attempts.filter((item) => item.hintsUsed === 0)),
    weakest,
  };
}
