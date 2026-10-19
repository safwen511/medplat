"use client";

import { Brain, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useMemo, useSyncExternalStore } from "react";

import { isDueToday, onTermsChange, questionSchedule, readTerms, type TermItem } from "@/lib/leitner";
import type { Attempt } from "@/lib/progress/store";

import { EmptyState, EspaceSection } from "./section";
import { shortCertifTitle, type EspaceYear } from "./types";

let cache: { raw: string; items: TermItem[] } | null = null;
function termsSnapshot(): TermItem[] {
  const items = readTerms();
  const raw = JSON.stringify(items);
  if (cache?.raw !== raw) cache = { raw, items };
  return cache.items;
}
const NONE: TermItem[] = [];

/**
 * "À revoir aujourd'hui": questions answered wrong and terms not known in recall mode, back after
 * 1, 3 then 7 days (Leitner boxes).
 */
export function ReviewToday({ years, attempts, now }: { years: EspaceYear[]; attempts: Attempt[]; now: Date }) {
  const terms = useSyncExternalStore(onTermsChange, termsSnapshot, () => NONE);
  const lessons = useMemo(() => {
    const map = new Map<string, { title: string; certif: string; year: EspaceYear }>();
    for (const year of years)
      for (const certif of year.certifs)
        for (const lesson of certif.lessons) map.set(lesson.id, { title: lesson.title, certif: certif.title, year });
    return map;
  }, [years]);

  const questions = useMemo(() => {
    const due = questionSchedule(attempts).filter((item) => isDueToday(item.due, now));
    const byLesson = new Map<string, number>();
    for (const item of due) byLesson.set(item.lessonId, (byLesson.get(item.lessonId) ?? 0) + 1);
    return [...byLesson.entries()]
      .map(([lessonId, count]) => ({ lessonId, count, info: lessons.get(lessonId) }))
      .filter((row) => row.info)
      .sort((a, b) => b.count - a.count);
  }, [attempts, now, lessons]);

  const dueTerms = useMemo(() => {
    const byLesson = new Map<string, TermItem[]>();
    for (const item of terms.filter((term) => isDueToday(term.due, now)))
      byLesson.set(item.lessonId, [...(byLesson.get(item.lessonId) ?? []), item]);
    return [...byLesson.values()];
  }, [terms, now]);

  const total = questions.reduce((sum, row) => sum + row.count, 0) + dueTerms.reduce((sum, list) => sum + list.length, 0);

  return (
    <EspaceSection
      id="a-revoir-aujourdhui"
      title="À revoir aujourd'hui"
      description="Questions ratées et termes oubliés reviennent après 1, 3 puis 7 jours."
      action={
        total > 0 ? (
          <span className="rounded-full bg-highyield-soft px-3 py-1 text-sm text-highyield">
            <span className="numeral font-semibold">{total}</span> à revoir
          </span>
        ) : undefined
      }
    >
      {total === 0 ? (
        <EmptyState>Rien à revoir aujourd&apos;hui. Les erreurs et les termes non sus apparaîtront ici.</EmptyState>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
          {questions.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="eyebrow">Questions</p>
              <ul className="flex flex-col gap-2">
                {questions.map(({ lessonId, count, info }) => (
                  <li key={lessonId}>
                    <Link
                      href={`/${info!.year.faculty}/${info!.year.year}/quiz?lecon=${encodeURIComponent(lessonId)}&erreurs=1`}
                      className="flex min-h-14 items-center gap-4 rounded-card border border-border bg-surface px-4 py-3 transition-shadow duration-200 hover:shadow-glow focus-visible:shadow-glow focus-visible:outline-none"
                    >
                      <span className="numeral w-10 shrink-0 rounded-control bg-wrong-soft py-1 text-center font-semibold text-wrong">
                        {count}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="line-clamp-2 leading-snug font-medium">{info!.title}</span>
                        <span className="block truncate text-sm text-muted">{shortCertifTitle(info!.certif)}</span>
                      </span>
                      <span className="inline-flex shrink-0 items-center gap-1 text-sm text-primary">
                        <RotateCcw className="size-3.5" aria-hidden /> Refaire
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {dueTerms.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="eyebrow">Termes</p>
              <ul className="flex flex-col gap-2">
                {dueTerms.map((list) => (
                  <li key={list[0].lessonId} className="rounded-card border border-border bg-surface px-4 py-3">
                    <Link
                      href={`${list[0].href}#rappel`}
                      className="flex items-center justify-between gap-3 font-medium hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <span className="line-clamp-1">{list[0].lessonTitle}</span>
                      <span className="inline-flex shrink-0 items-center gap-1 text-sm text-primary">
                        <Brain className="size-3.5" aria-hidden /> Mode rappel
                      </span>
                    </Link>
                    <p className="mt-2 flex flex-wrap gap-1.5">
                      {list.map((item) => (
                        <span key={item.id} className="rounded-full bg-highyield-soft px-2.5 py-0.5 text-sm text-highyield">
                          {item.term}
                        </span>
                      ))}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </EspaceSection>
  );
}
