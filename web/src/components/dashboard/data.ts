"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { CertifSummary, LessonSummary, YearIndex } from "@/lib/content/types";
import { useProgress } from "@/lib/progress/provider";
import type { Attempt, LessonProgress, LessonStatus, Profile } from "@/lib/progress/store";

export const DAILY_GOAL = 20;

export const STATUS_STEPS: LessonStatus[] = ["lu", "revise_1", "revise_2", "maitrise"];

export const STATUS_LABELS: Record<LessonStatus | "non_lu", string> = {
  non_lu: "Non lu",
  lu: "Lu",
  revise_1: "Révisé 1×",
  revise_2: "Révisé 2×",
  maitrise: "Maîtrisé",
};

export interface LessonRef {
  lesson: LessonSummary;
  certif: CertifSummary;
}

/** lessonId -> lesson and its certif, for every lesson of the year. */
export function lessonMap(index: YearIndex): Map<string, LessonRef> {
  const map = new Map<string, LessonRef>();
  for (const certif of index.certifs)
    for (const mod of certif.modules) for (const lesson of mod.lessons) map.set(lesson.id, { lesson, certif });
  return map;
}

export function certifLessons(certif: CertifSummary): LessonSummary[] {
  return certif.modules.flatMap((mod) => mod.lessons);
}

export interface StudentData {
  loading: boolean;
  profile: Profile | null;
  /** This year's attempts, oldest first. */
  attempts: Attempt[];
  /** This year's lesson progress. */
  progress: Record<string, LessonProgress>;
  /** Captured on load, so render never reads the clock (prerender-safe). */
  now: Date;
  setStatus(lessonId: string, status: LessonStatus): Promise<void>;
}

/** Loads the student's profile, attempts and lesson progress for one year, client-side. */
export function useStudentData(index: YearIndex): StudentData {
  const { store, ready } = useProgress();
  const lessons = useMemo(() => lessonMap(index), [index]);
  const [state, setState] = useState<{
    loading: boolean;
    profile: Profile | null;
    attempts: Attempt[];
    progress: Record<string, LessonProgress>;
    now: Date;
  }>({ loading: true, profile: null, attempts: [], progress: {}, now: new Date(0) });

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    Promise.all([store.profile(), store.attempts(), store.lessonProgress()])
      .then(([profile, attempts, progress]) => {
        if (cancelled) return;
        setState({
          loading: false,
          profile,
          attempts: attempts.filter(
            (item) => item.faculty === index.faculty && item.year === index.year && lessons.has(item.lessonId),
          ),
          progress: Object.fromEntries(Object.entries(progress).filter(([id]) => lessons.has(id))),
          now: new Date(),
        });
      })
      .catch(() => {
        if (!cancelled) setState((previous) => ({ ...previous, loading: false, now: new Date() }));
      });
    return () => {
      cancelled = true;
    };
  }, [store, ready, index, lessons]);

  const setStatus = useCallback(
    async (lessonId: string, status: LessonStatus) => {
      const updatedAt = new Date().toISOString();
      let previous: LessonProgress | undefined;
      setState((current) => {
        previous = current.progress[lessonId];
        const revisions = Math.max(previous?.revisions ?? 0, STATUS_STEPS.indexOf(status));
        return {
          ...current,
          progress: { ...current.progress, [lessonId]: { lessonId, status, revisions, updatedAt } },
        };
      });
      try {
        await store.setLessonStatus(lessonId, index.faculty, index.year, status);
      } catch {
        setState((current) => {
          const progress = { ...current.progress };
          if (previous) progress[lessonId] = previous;
          else delete progress[lessonId];
          return { ...current, progress };
        });
      }
    },
    [store, index.faculty, index.year],
  );

  return { ...state, setStatus };
}

// Stats ---------------------------------------------------------------------------------------

/** Local calendar day, YYYY-MM-DD. */
export function dayKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

/** Consecutive days with at least one attempt, ending today (or yesterday if nothing yet today). */
export function streak(attempts: Attempt[], now: Date): number {
  const days = new Set(attempts.map((item) => dayKey(new Date(item.createdAt))));
  let cursor = days.has(dayKey(now)) ? now : addDays(now, -1);
  let count = 0;
  while (days.has(dayKey(cursor))) {
    count++;
    cursor = addDays(cursor, -1);
  }
  return count;
}

export function attemptsToday(attempts: Attempt[], now: Date): number {
  const today = dayKey(now);
  return attempts.filter((item) => dayKey(new Date(item.createdAt)) === today).length;
}

/** Whole days from today to an exam date (YYYY-MM-DD), negative once past. */
export function daysUntil(examDate: string, now: Date): number | null {
  const [y, m, d] = examDate.split("-").map(Number);
  if (!y || !m || !d) return null;
  const exam = new Date(y, m - 1, d);
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((exam.getTime() - today.getTime()) / 86_400_000);
}

export interface Accuracy {
  total: number;
  correct: number;
  /** 0..100, null without attempts. */
  percent: number | null;
}

export function accuracy(attempts: Attempt[]): Accuracy {
  const correct = attempts.filter((item) => item.correct).length;
  return {
    total: attempts.length,
    correct,
    percent: attempts.length ? Math.round((correct / attempts.length) * 100) : null,
  };
}

export function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export function groupBy<T>(items: T[], key: (item: T) => string): Map<string, T[]> {
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const k = key(item);
    const group = groups.get(k);
    if (group) group.push(item);
    else groups.set(k, [item]);
  }
  return groups;
}

// Formatting ----------------------------------------------------------------------------------

export function formatPercent(value: number | null): string {
  return value === null ? "—" : `${value} %`;
}

export function formatSeconds(ms: number | null): string {
  if (ms === null) return "—";
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds < 10 ? seconds.toFixed(1).replace(".", ",") : Math.round(seconds)} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${String(Math.round(seconds % 60)).padStart(2, "0")}`;
}

const shortDate = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });
const shortDateYear = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "numeric" });

export function formatDate(iso: string, now: Date): string {
  const date = new Date(iso);
  return (date.getFullYear() === now.getFullYear() ? shortDate : shortDateYear).format(date);
}

/** "Certificat intégré de pédiatrie" -> "Pédiatrie", for compact chart labels. */
export function shortCertifTitle(title: string): string {
  const short = title.replace(/^Certificat\s+(intégré\s+)?(de\s+l['’]|de\s+la\s+|des\s+|du\s+|de\s+|d['’])?/i, "");
  return short.charAt(0).toUpperCase() + short.slice(1);
}

export function lessonHref(index: YearIndex, lesson: LessonSummary): string {
  return `/${index.faculty}/${index.year}/lecon/${encodeURIComponent(lesson.id)}`;
}

export function certifHref(index: YearIndex, certif: CertifSummary): string {
  return `/${index.faculty}/${index.year}/${certif.slug}`;
}
