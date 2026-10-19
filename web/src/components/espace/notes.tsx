"use client";

import Link from "next/link";

import { EmptyState, EspaceSection } from "./section";
import { formatDate } from "./stats";
import { lessonHref, type EspaceYear } from "./types";
import type { ErrorReport } from "./use-espace-data";

export interface LessonInfo {
  title: string;
  certifTitle: string;
  href: string;
}

/** lessonId -> title and link, across every year. */
export function lessonDirectory(years: EspaceYear[]): Map<string, LessonInfo> {
  const map = new Map<string, LessonInfo>();
  for (const year of years)
    for (const certif of year.certifs)
      for (const lesson of certif.lessons)
        map.set(lesson.id, { title: lesson.title, certifTitle: certif.title, href: lessonHref(year, lesson.id) });
  return map;
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count > 1 ? "s" : ""}`;
}

function LessonTitle({ info, fallback }: { info: LessonInfo | undefined; fallback: string }) {
  if (!info) return <span className="font-medium">{fallback}</span>;
  return (
    <Link
      href={info.href}
      className="rounded-card font-medium underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {info.title}
    </Link>
  );
}

export function ReportsSection({
  reports,
  lessons,
  now,
}: {
  reports: ErrorReport[];
  lessons: Map<string, LessonInfo>;
  now: Date;
}) {
  const sorted = [...reports].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  return (
    <EspaceSection
      id="signalements"
      title="Mes signalements"
      description={
        reports.length
          ? `${plural(reports.length, "erreur")} signalée${reports.length > 1 ? "s" : ""} au relecteur médical. Merci.`
          : undefined
      }
    >
      {sorted.length === 0 ? (
        <EmptyState>
          Une erreur dans un cours ou une question ? Signale-la depuis la page : un relecteur la vérifiera.
        </EmptyState>
      ) : (
        <ul className="flex flex-col">
          {sorted.map((report, position) => (
            <li
              key={`${report.createdAt}-${position}`}
              className="flex flex-col gap-1 border-b border-border py-4 first:pt-0 last:border-b-0"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                <LessonTitle info={lessons.get(report.lessonId)} fallback={report.lessonId} />
                <span className="text-sm text-muted">
                  {report.questionId ? "Question" : "Cours"} · {formatDate(report.createdAt, now)}
                </span>
              </div>
              <p className="whitespace-pre-line text-[0.9375rem] text-muted">{report.message}</p>
            </li>
          ))}
        </ul>
      )}
    </EspaceSection>
  );
}
