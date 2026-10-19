"use client";

import { CalendarDays, Flame, Layers, PlayCircle } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { CertifFolder } from "@/components/cards/certif-folder";
import { certifTheme } from "@/components/cards/themes";
import { countTiers } from "@/components/cards/tiers";
import { Button } from "@/components/ui/button";
import { PageStack, Panel } from "@/components/ui/panel";
import { ProgressRing } from "@/components/ui/progress-ring";
import { StatTile } from "@/components/ui/stat-tile";
import type { CertifSummary, YearIndex } from "@/lib/content/types";
import { validExamDate } from "@/lib/dates";

import {
  accuracy,
  attemptsToday,
  certifHref,
  certifLessons,
  certifQuizHref,
  DAILY_GOAL,
  daysUntil,
  groupBy,
  lessonHref,
  lessonMap,
  quizHref,
  shortCertifTitle,
  streak,
  useStudentData,
  type StudentData,
} from "./data";

export function YearHome({ index }: { index: YearIndex }) {
  const data = useStudentData(index);
  const poles = useMemo(() => groupBy(index.certifs, (certif) => certif.pole), [index]);

  return (
    <PageStack>
      <Hero index={index} data={data} />
      {[...poles].map(([pole, certifs]) => {
        const ready = certifs.flatMap(certifLessons).filter((lesson) => lesson.available).length;
        return (
          <Panel
            key={pole}
            id={`pole-${pole}`}
            title={`Pôle ${pole}`}
            subtitle="Touche un dossier pour voir tes chiffres, ouvrir ses cours ou lancer un quiz."
            action={
              <span className="inline-flex items-center gap-1.5 rounded-full bg-primary-soft px-3 py-1 text-sm text-primary">
                <span className="numeral font-semibold">{ready}</span> cours prêts
              </span>
            }
          >
            <ul className="grid gap-x-6 gap-y-7 sm:grid-cols-2 lg:grid-cols-3">
              {certifs.map((certif) => (
                <li key={certif.slug}>
                  <Folder index={index} certif={certif} data={data} />
                </li>
              ))}
            </ul>
          </Panel>
        );
      })}
    </PageStack>
  );
}

/** Greeting, today's goal as a ring, the main action and three key figures. */
function Hero({ index, data }: { index: YearIndex; data: StudentData }) {
  const name = data.profile?.onboarded ? data.profile.displayName : null;
  const { profile, attempts, now, loading } = data;
  const today = attemptsToday(attempts, now);
  const goal = profile?.dailyGoal ?? DAILY_GOAL;
  const examDate = validExamDate(profile?.examDate, now);
  const countdown = examDate ? daysUntil(examDate, now) : null;
  const days = streak(attempts, now);
  const ready = index.certifs.flatMap(certifLessons).filter((lesson) => lesson.available).length;

  return (
    <section aria-labelledby="home-title" className="panel relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{ background: "radial-gradient(60% 80% at 100% 0%, var(--primary-soft), transparent 70%)" }}
      />
      <div className="relative flex flex-col gap-8">
        <div className="flex flex-col items-start gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 flex-col gap-3">
            <p className="text-sm text-muted">{index.yearLabel}</p>
            <h1 id="home-title" className="text-4xl leading-tight sm:text-5xl">
              {name ? `Bonjour ${name}.` : "Bonjour."}
            </h1>
            <p className="text-lg text-muted">
              {loading ? " " : today >= goal ? "Objectif du jour atteint. Bravo." : "Une série de questions, et c'est parti."}
            </p>
            <PrimaryAction index={index} data={data} />
          </div>
          <div className="flex flex-col items-center gap-2 self-center">
            <ProgressRing value={loading ? 0 : (today / goal) * 100} size={136} stroke={12} label="Objectif du jour">
              <span className="flex flex-col items-center leading-none">
                <span className="text-3xl">{loading ? "–" : today}</span>
                <span className="mt-1 text-sm font-normal text-muted">/ {goal}</span>
              </span>
            </ProgressRing>
            <span className="text-sm text-muted">objectif du jour</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {countdown !== null && countdown >= 0 ? (
            <StatTile
              className="col-span-2 sm:col-span-1"
              icon={<CalendarDays className="size-4" aria-hidden />}
              label="avant ton certif"
              value={countdown === 0 ? "Jour J" : `J-${countdown}`}
              hint={
                <Link href="/espace#reglages" className="underline underline-offset-4 hover:text-foreground">
                  Modifier la date
                </Link>
              }
            />
          ) : (
            <Link
              href="/onboarding"
              className="col-span-2 flex flex-col justify-center gap-1 rounded-card border border-dashed sm:col-span-1 border-border bg-surface p-5 transition-shadow duration-200 hover:shadow-glow focus-visible:shadow-glow focus-visible:outline-none"
            >
              <span className="flex items-center gap-2 text-sm text-muted">
                <CalendarDays className="size-4" aria-hidden /> date du certif
              </span>
              <span className="text-lg font-semibold">Ajoute la date de ton certif</span>
            </Link>
          )}
          <StatTile
            icon={<Flame className="size-4" aria-hidden />}
            label="série de jours"
            value={loading ? "–" : days}
            hint={days === 0 && !loading ? "Réponds à une question" : undefined}
          />
          <StatTile icon={<Layers className="size-4" aria-hidden />} label="cours prêts" value={ready} />
        </div>
      </div>
    </section>
  );
}

/** One primary action: resume the last lesson touched, otherwise start a quiz. */
function PrimaryAction({ index, data }: { index: YearIndex; data: StudentData }) {
  const resume = useMemo(() => {
    const lessons = lessonMap(index);
    return (
      Object.values(data.progress)
        .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
        .map((record) => lessons.get(record.lessonId))
        .find((ref) => ref?.lesson.available) ?? null
    );
  }, [index, data.progress]);

  if (data.loading) return <div className="h-12" aria-hidden />;

  return (
    <div className="flex max-w-full flex-wrap gap-3">
      <Button asChild size="lg" className="max-w-full shadow-glow">
        <Link href={quizHref(index)}>
          <PlayCircle aria-hidden /> Commencer un quiz
        </Link>
      </Button>
      {resume && (
        <Button asChild size="lg" variant="outline" className="max-w-full">
          <Link href={lessonHref(index, resume.lesson)}>
            <span className="truncate">Reprendre : {resume.lesson.title}</span>
          </Link>
        </Button>
      )}
    </div>
  );
}

function Folder({ index, certif, data }: { index: YearIndex; certif: CertifSummary; data: StudentData }) {
  const lessons = certifLessons(certif);
  const score = accuracy(
    data.attempts.filter((attempt) => lessons.some((lesson) => lesson.id === attempt.lessonId)),
  );
  return (
    <CertifFolder
      href={certifHref(index, certif)}
      quizHref={certifQuizHref(index, certif)}
      title={shortCertifTitle(certif.title)}
      fullTitle={certif.title}
      pole={certif.pole}
      theme={certifTheme(certif)}
      counts={countTiers(lessons.map((lesson) => data.progress[lesson.id]?.status))}
      available={lessons.filter((lesson) => lesson.available).length}
      precision={score.percent}
      answered={score.total}
    />
  );
}
