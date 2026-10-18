"use client";

import { ArrowRight, BookOpen, CalendarClock, Flame, GraduationCap, Target } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CertifSummary, YearIndex } from "@/lib/content/types";

import {
  accuracy,
  attemptsToday,
  certifHref,
  certifLessons,
  DAILY_GOAL,
  daysUntil,
  formatDate,
  formatPercent,
  groupBy,
  lessonHref,
  lessonMap,
  STATUS_LABELS,
  streak,
  useStudentData,
  type StudentData,
} from "./data";
import { LabelledProgress, LoadingBlocks, PoleBadge } from "./parts";

export function YearHome({ index }: { index: YearIndex }) {
  const data = useStudentData(index);
  const onboarded = Boolean(data.profile?.onboarded);

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <p className="text-sm text-muted">{index.facultyLabel}</p>
        <h1 className="text-2xl font-semibold tracking-tight">
          {onboarded && data.profile?.displayName ? `Bonjour ${data.profile.displayName}` : index.yearLabel}
        </h1>
        {onboarded && data.profile?.displayName && <p className="text-sm text-muted">{index.yearLabel}</p>}
      </header>

      {data.loading ? (
        <LoadingBlocks count={2} />
      ) : onboarded ? (
        <Today index={index} data={data} />
      ) : (
        <Card className="border-primary/40 bg-primary-soft">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GraduationCap className="size-5 text-primary" aria-hidden />
              Configure ton espace
            </CardTitle>
            <CardDescription>
              Choisis ton année et la date de ton certif pour suivre ton objectif du jour, ta série et ton compte à
              rebours.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link href="/onboarding">
                Commencer
                <ArrowRight aria-hidden />
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}

      <CertifGrid index={index} data={data} />
    </div>
  );
}

function Today({ index, data }: { index: YearIndex; data: StudentData }) {
  const { profile, attempts, progress, now } = data;
  const today = attemptsToday(attempts, now);
  const days = streak(attempts, now);
  const countdown = profile?.examDate ? daysUntil(profile.examDate, now) : null;

  const resume = useMemo(() => {
    const lessons = lessonMap(index);
    const latest = Object.values(progress).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))[0];
    const ref = latest && lessons.get(latest.lessonId);
    return ref ? { ...ref, record: latest } : null;
  }, [index, progress]);

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="flex flex-col gap-2 p-4">
          <span className="flex items-center gap-1.5 text-xs font-medium text-muted">
            <CalendarClock className="size-3.5" aria-hidden />
            Compte à rebours
          </span>
          {countdown === null ? (
            <>
              <span className="text-sm">Pas encore de date de certif.</span>
              <Link href="/onboarding" className="text-sm font-medium text-primary hover:underline">
                Ajouter la date
              </Link>
            </>
          ) : countdown > 0 ? (
            <span className="text-lg font-semibold">
              <span className="text-2xl tabular-nums">J-{countdown}</span>{" "}
              <span className="text-base font-normal text-muted">avant ton certif</span>
            </span>
          ) : countdown === 0 ? (
            <span className="text-2xl font-semibold">Jour J. Bon courage !</span>
          ) : (
            <>
              <span className="text-sm">La date de ton certif est passée.</span>
              <Link href="/onboarding" className="text-sm font-medium text-primary hover:underline">
                Mettre à jour la date
              </Link>
            </>
          )}
        </Card>

        <Card className="flex flex-col gap-2 p-4">
          <span className="flex items-center gap-1.5 text-xs font-medium text-muted">
            <Target className="size-3.5" aria-hidden />
            Objectif du jour
          </span>
          <LabelledProgress
            id="daily-goal"
            label={today >= DAILY_GOAL ? "Objectif atteint" : `${DAILY_GOAL} questions par jour`}
            value={(today / DAILY_GOAL) * 100}
            detail={`${today} / ${DAILY_GOAL}`}
            tone={today >= DAILY_GOAL ? "correct" : "primary"}
          />
          <Link
            href={`/${index.faculty}/${index.year}/quiz`}
            className="text-sm font-medium text-primary hover:underline"
          >
            Lancer un quiz
          </Link>
        </Card>

        <Card className="flex flex-col gap-2 p-4">
          <span className="flex items-center gap-1.5 text-xs font-medium text-muted">
            <Flame className="size-3.5" aria-hidden />
            Série
          </span>
          <span className="text-2xl font-semibold tabular-nums">
            {days} <span className="text-base font-normal text-muted">{days > 1 ? "jours" : "jour"}</span>
          </span>
          <span className="text-xs text-muted">
            {today > 0 ? "Tu as révisé aujourd'hui." : days > 0 ? "Réponds à une question pour la prolonger." : "Réponds à une question pour la lancer."}
          </span>
        </Card>
      </div>

      {resume && (
        <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
          <div className="flex min-w-0 flex-1 items-start gap-3">
            <BookOpen className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
            <div className="min-w-0">
              <p className="text-xs font-medium text-muted">Reprendre</p>
              <p className="truncate font-medium">{resume.lesson.title}</p>
              <p className="truncate text-xs text-muted">
                {resume.certif.title} · {STATUS_LABELS[resume.record.status]} le {formatDate(resume.record.updatedAt, now)}
              </p>
            </div>
          </div>
          <Button asChild variant="outline" size="sm" className="self-start sm:self-auto">
            <Link href={resume.lesson.available ? lessonHref(index, resume.lesson) : certifHref(index, resume.certif)}>
              {resume.lesson.available ? "Ouvrir le cours" : "Voir le certif"}
              <ArrowRight aria-hidden />
            </Link>
          </Button>
        </Card>
      )}
    </div>
  );
}

function CertifGrid({ index, data }: { index: YearIndex; data: StudentData }) {
  const poles = useMemo(() => groupBy(index.certifs, (certif) => certif.pole), [index]);
  const byCertif = useMemo(() => {
    const lessons = lessonMap(index);
    return groupBy(data.attempts, (item) => lessons.get(item.lessonId)?.certif.slug ?? "");
  }, [index, data.attempts]);

  return (
    <section aria-labelledby="certifs-title" className="flex flex-col gap-6">
      <h2 id="certifs-title" className="text-lg font-semibold">
        Mes certifs
      </h2>
      {[...poles].map(([pole, certifs]) => (
        <div key={pole} className="flex flex-col gap-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Pôle {pole}</h3>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {certifs.map((certif) => (
              <li key={certif.slug}>
                <CertifCard
                  index={index}
                  certif={certif}
                  data={data}
                  attempts={byCertif.get(certif.slug) ?? []}
                />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

function CertifCard({
  index,
  certif,
  data,
  attempts,
}: {
  index: YearIndex;
  certif: CertifSummary;
  data: StudentData;
  attempts: StudentData["attempts"];
}) {
  const lessons = certifLessons(certif);
  const available = lessons.filter((lesson) => lesson.available).length;
  const read = lessons.filter((lesson) => data.progress[lesson.id]).length;
  const readPercent = lessons.length ? Math.round((read / lessons.length) * 100) : 0;
  const score = accuracy(attempts);

  return (
    <Link
      href={certifHref(index, certif)}
      className="group flex h-full flex-col gap-3 rounded-card border border-border bg-surface p-4 shadow-sm transition-colors hover:border-primary/50 hover:bg-surface-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="flex items-start gap-2">
        <PoleBadge pole={certif.pole} className="shrink-0" />
        <span className="font-medium leading-snug">{certif.title}</span>
      </div>
      <p className="text-xs text-muted">
        {lessons.length} cours · {available === 0 ? "aucun disponible" : `${available} disponible${available > 1 ? "s" : ""}`}
      </p>
      <div className="mt-auto flex flex-col gap-2">
        <LabelledProgress
          id={`read-${certif.slug}`}
          label="Cours lus"
          value={readPercent}
          detail={`${readPercent} %`}
        />
        <p className="flex items-center justify-between text-xs text-muted">
          <span>Précision</span>
          <span className="tabular-nums text-foreground">
            {formatPercent(score.percent)}
            {score.total > 0 && <span className="text-muted"> · {score.total} rép.</span>}
          </span>
        </p>
      </div>
    </Link>
  );
}
