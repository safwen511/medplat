import type { Attempt } from "@/lib/progress/store";

/** Local calendar day, YYYY-MM-DD. */
export function dayKey(date: Date): string {
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${m}-${d}`;
}

function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

/** Consecutive days with at least one answer, ending today (or yesterday if nothing yet today). */
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

export function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/** Whole days from today to an exam date (YYYY-MM-DD), negative once past. */
export function daysUntil(examDate: string, now: Date): number | null {
  const [y, m, d] = examDate.split("-").map(Number);
  if (!y || !m || !d) return null;
  const exam = new Date(y, m - 1, d);
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((exam.getTime() - today.getTime()) / 86_400_000);
}

export function formatSeconds(ms: number | null): string {
  if (ms === null) return "—";
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds < 10 ? seconds.toFixed(1).replace(".", ",") : Math.round(seconds)} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${String(Math.round(seconds % 60)).padStart(2, "0")}`;
}

const dayMonth = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });
const dayMonthYear = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "numeric" });
const monthYear = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric" });
const longDate = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric" });

export function formatDate(iso: string, now: Date): string {
  const date = new Date(iso);
  return (date.getFullYear() === now.getFullYear() ? dayMonth : dayMonthYear).format(date);
}

export function formatMonth(iso: string): string {
  return monthYear.format(new Date(iso));
}

/** "2026-12-14" -> "14 décembre 2026", read as a local date. */
export function formatExamDate(examDate: string): string {
  const [y, m, d] = examDate.split("-").map(Number);
  return y && m && d ? longDate.format(new Date(y, m - 1, d)) : examDate;
}
