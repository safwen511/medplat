"use client";

import Link from "next/link";
import { useMemo } from "react";

import { CertifDeck } from "@/components/cards/certif-deck";
import { certifTheme } from "@/components/cards/themes";
import { countTiers } from "@/components/cards/tiers";
import { Button } from "@/components/ui/button";
import type { CertifSummary, YearIndex } from "@/lib/content/types";

import {
  accuracy,
  attemptsToday,
  certifHref,
  certifLessons,
  DAILY_GOAL,
  daysUntil,
  groupBy,
  lessonHref,
  lessonMap,
  quizHref,
  shortCertifTitle,
  useStudentData,
  type StudentData,
} from "./data";
import { Column } from "./parts";

export function YearHome({ index }: { index: YearIndex }) {
  const data = useStudentData(index);
  const name = data.profile?.onboarded ? data.profile.displayName : null;

  return (
    <div className="flex flex-col gap-16">
      <Column>
        <section aria-labelledby="home-title" className="flex flex-col gap-6">
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted">{index.yearLabel}</p>
            <h1 id="home-title" className="text-3xl leading-tight sm:text-4xl">
              {name ? `Bonjour ${name}.` : "Bonjour."}
            </h1>
            <Today data={data} />
          </div>
          <PrimaryAction index={index} data={data} />
        </section>
      </Column>
      <Certifs index={index} data={data} />
    </div>
  );
}

/** Countdown and today's goal, as one sentence. */
function Today({ data }: { data: StudentData }) {
  if (data.loading) return <p className="min-h-[1.6em] text-muted" aria-hidden />;

  const { profile, attempts, now } = data;
  const today = attemptsToday(attempts, now);
  const goal = profile?.dailyGoal ?? DAILY_GOAL;
  const countdown = profile?.examDate ? daysUntil(profile.examDate, now) : null;

  const goalPart =
    today >= goal
      ? `objectif du jour atteint, ${today} question${today > 1 ? "s" : ""}`
      : `${today} question${today > 1 ? "s" : ""} sur ${goal} aujourd'hui`;

  let sentence: string;
  if (countdown !== null && countdown > 1) sentence = `J-${countdown} avant ton certif, ${goalPart}.`;
  else if (countdown === 1) sentence = `Ton certif est demain, ${goalPart}.`;
  else if (countdown === 0) sentence = "C'est le jour de ton certif. Bon courage.";
  else sentence = `${goalPart.charAt(0).toUpperCase()}${goalPart.slice(1)}.`;

  const needsDate = countdown === null || countdown < 0;
  return (
    <p className="text-lg text-muted">
      {sentence}
      {needsDate && (
        <>
          {" "}
          <Link
            href="/onboarding"
            className="text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
          >
            {countdown === null ? "Ajouter la date de ton certif" : "Mettre à jour la date de ton certif"}
          </Link>
        </>
      )}
    </p>
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
    <Button asChild size="lg" className="max-w-full self-start">
      {resume ? (
        <Link href={lessonHref(index, resume.lesson)}>
          <span className="truncate">Reprendre : {resume.lesson.title}</span>
        </Link>
      ) : (
        <Link href={quizHref(index)}>Commencer un quiz</Link>
      )}
    </Button>
  );
}

function Certifs({ index, data }: { index: YearIndex; data: StudentData }) {
  const poles = useMemo(() => groupBy(index.certifs, (certif) => certif.pole), [index]);
  return (
    <section aria-labelledby="certifs-title" className="mx-auto flex w-full max-w-5xl flex-col gap-10">
      <h2 id="certifs-title" className="text-2xl">
        Tes certifs
      </h2>
      {[...poles].map(([pole, certifs]) => (
        <section key={pole} aria-labelledby={`pole-${pole}`} className="flex flex-col gap-4">
          <p id={`pole-${pole}`} className="text-sm text-muted">
            Pôle {pole}
          </p>
          <ul className="grid gap-x-6 gap-y-7 sm:grid-cols-2 lg:grid-cols-3">
            {certifs.map((certif) => (
              <li key={certif.slug}>
                <CertifRow index={index} certif={certif} data={data} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </section>
  );
}

function CertifRow({ index, certif, data }: { index: YearIndex; certif: CertifSummary; data: StudentData }) {
  const lessons = certifLessons(certif);
  const score = accuracy(
    data.attempts.filter((attempt) => lessons.some((lesson) => lesson.id === attempt.lessonId)),
  );
  return (
    <CertifDeck
      href={certifHref(index, certif)}
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
