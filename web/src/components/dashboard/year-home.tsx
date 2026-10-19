"use client";

import { ArrowRight, CalendarDays, Flame, Layers, PlayCircle } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useMemo } from "react";

import { CertifArt } from "@/components/cards/certif-art";
import { CertifFolder } from "@/components/cards/certif-folder";
import { certifTheme } from "@/components/cards/themes";
import { countTiers } from "@/components/cards/tiers";
import { Button } from "@/components/ui/button";
import { PageStack, SectionHeader } from "@/components/ui/panel";
import { ProgressRing } from "@/components/ui/progress-ring";
import { Skeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/ui/stat-tile";
import type { CertifSummary, YearIndex } from "@/lib/content/types";
import { validExamDate } from "@/lib/dates";
import { EASE_OUT } from "@/lib/motion";

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
  STATUS_LABELS,
  stepOf,
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
      <ContinueRow index={index} data={data} />
      {[...poles].map(([pole, certifs]) => {
        const ready = certifs.flatMap(certifLessons).filter((lesson) => lesson.available).length;
        return (
          <section key={pole} aria-labelledby={`pole-${pole}`} className="flex flex-col gap-7">
            <SectionHeader
              id={`pole-${pole}`}
              eyebrow={`${certifs.length} certif${certifs.length > 1 ? "s" : ""}`}
              title={`Pôle ${pole}`}
              subtitle="Touche un dossier pour voir tes chiffres, ouvrir ses cours ou lancer un quiz."
              action={
                ready > 0 ? (
                  <span className="inline-flex items-baseline gap-1.5 rounded-full bg-primary-soft px-3 py-1 text-sm text-primary">
                    <span className="numeral font-semibold">{ready}</span> cours prêts
                  </span>
                ) : (
                  <span className="rounded-full border border-border px-3 py-1 text-sm text-muted">bientôt</span>
                )
              }
            />
            <ul className="grid gap-x-6 gap-y-7 sm:grid-cols-2 lg:grid-cols-3">
              {certifs.map((certif, position) => (
                <motion.li
                  key={certif.slug}
                  initial={{ opacity: 0, y: 16 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: "0px 0px -5% 0px" }}
                  transition={{ duration: 0.5, ease: EASE_OUT, delay: Math.min(position, 6) * 0.05 }}
                >
                  <Folder index={index} certif={certif} data={data} />
                </motion.li>
              ))}
            </ul>
          </section>
        );
      })}
    </PageStack>
  );
}

/** Courses touched lately, newest first: a horizontal row to pick up where the student left off. */
function ContinueRow({ index, data }: { index: YearIndex; data: StudentData }) {
  const recent = useMemo(() => {
    const lessons = lessonMap(index);
    return Object.values(data.progress)
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
      .map((record) => ({ record, ref: lessons.get(record.lessonId) }))
      .filter((item) => item.ref?.lesson.available)
      .slice(0, 12);
  }, [index, data.progress]);

  if (data.loading || recent.length === 0) return null;
  return (
    <section aria-labelledby="continuer" className="flex flex-col gap-5">
      <SectionHeader id="continuer" eyebrow="Reprendre" title="Continuer" />
      <ul className="-mx-4 flex snap-x snap-mandatory scroll-px-4 gap-4 overflow-x-auto px-4 pb-2 [scrollbar-width:none] sm:-mx-6 sm:scroll-px-6 sm:px-6">
        {recent.map(({ record, ref }, position) => {
          const { lesson, certif } = ref!;
          const theme = certifTheme(certif);
          return (
            <motion.li
              key={lesson.id}
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.45, ease: EASE_OUT, delay: Math.min(position, 5) * 0.05 }}
              className="w-60 shrink-0 snap-start sm:w-64"
            >
              <Link
                href={lessonHref(index, lesson)}
                className="group flex h-full flex-col overflow-hidden rounded-card border border-border bg-surface shadow-depth-1 transition-[box-shadow,border-color,translate] duration-200 hover:-translate-y-1 hover:border-border-strong hover:shadow-depth-2 focus-visible:shadow-glow focus-visible:outline-none"
              >
                <CertifArt theme={theme} variant={lesson.order} emblemSize={22} className="h-24 w-full" />
                <span className="flex flex-1 flex-col gap-1 p-4">
                  <span className="eyebrow !text-[0.625rem]">{shortCertifTitle(certif.title)}</span>
                  <span className="line-clamp-2 leading-snug font-medium">{lesson.title}</span>
                  <span className="mt-auto flex items-center justify-between pt-3 text-sm">
                    <span className="text-muted">{STATUS_LABELS[stepOf(record.status)]}</span>
                    <span className="inline-flex items-center gap-1 text-primary">
                      Reprendre <ArrowRight className="size-3.5 transition-transform duration-200 group-hover:translate-x-0.5" aria-hidden />
                    </span>
                  </span>
                </span>
              </Link>
            </motion.li>
          );
        })}
      </ul>
    </section>
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
    <section aria-labelledby="home-title" aria-busy={loading} className="panel grain relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{ background: "radial-gradient(60% 80% at 100% 0%, var(--primary-soft), transparent 70%)" }}
      />
      <div className="relative flex flex-col gap-8">
        <div className="flex flex-col items-start gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 flex-col gap-3">
            <p className="eyebrow">{index.yearLabel}</p>
            <h1 id="home-title" className="rise-in text-4xl leading-tight sm:text-5xl">
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
                <span className="text-3xl">{loading ? <Skeleton className="h-7 w-8" /> : today}</span>
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
            value={loading ? <Skeleton className="mt-1 h-9 w-12" /> : days}
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
      exercises={lessons.reduce((sum, lesson) => sum + (lesson.available ? lesson.exerciseCount : 0), 0)}
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
