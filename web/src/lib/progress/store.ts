"use client";

import type { SupabaseClient } from "@supabase/supabase-js";

export type Mode = "lesson" | "quiz" | "game" | "exam";
export type LessonStatus = "lu" | "revise_1" | "revise_2" | "maitrise";

export interface Profile {
  displayName: string | null;
  faculty: string;
  year: "dcem1" | "dcem2" | null;
  examDate: string | null; // YYYY-MM-DD
  onboarded: boolean;
  dailyGoal?: number; // questions per day, default 20
}

export interface AttemptInput {
  questionId: string;
  questionType: string;
  lessonId: string;
  faculty: string;
  year: string;
  mode: Mode;
  correct: boolean;
  response: unknown;
  timeMs: number;
  hintsUsed: number;
}

export interface Attempt extends AttemptInput {
  createdAt: string;
}

export interface LessonProgress {
  lessonId: string;
  status: LessonStatus;
  revisions: number;
  updatedAt: string;
}

export interface ErrorReport {
  lessonId: string;
  questionId: string | null;
  message: string;
  createdAt: string;
}

export interface Highlight {
  id: string;
  lessonId: string;
  quote: string;
  note: string | null;
  createdAt: string;
}

/** Per-student data, stored in Supabase (signed in) or in this browser (demo mode). */
export interface ProgressStore {
  kind: "supabase" | "local";
  profile(): Promise<Profile | null>;
  saveProfile(profile: Profile): Promise<void>;
  recordAttempt(attempt: AttemptInput): Promise<void>;
  attempts(): Promise<Attempt[]>;
  lessonProgress(): Promise<Record<string, LessonProgress>>;
  setLessonStatus(lessonId: string, faculty: string, year: string, status: LessonStatus): Promise<void>;
  /** Back to "Non lu": removes the lesson's follow-up record. */
  clearLessonStatus(lessonId: string): Promise<void>;
  highlights(lessonId: string): Promise<Highlight[]>;
  allHighlights(): Promise<Highlight[]>;
  errorReports(): Promise<ErrorReport[]>;
  addHighlight(lessonId: string, quote: string, note?: string): Promise<void>;
  removeHighlight(id: string): Promise<void>;
  reportError(lessonId: string, questionId: string | null, message: string): Promise<void>;
}

const now = () => new Date().toISOString();
const STATUS_ORDER: LessonStatus[] = ["lu", "revise_1", "revise_2", "maitrise"];

// Demo mode -----------------------------------------------------------------------------------

function read<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(`medplat:v1:${key}`);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown) {
  try {
    window.localStorage.setItem(`medplat:v1:${key}`, JSON.stringify(value));
  } catch {
    // Storage full or blocked (private mode): progress is simply not kept.
  }
}

export const localStore: ProgressStore = {
  kind: "local",
  async profile() {
    return read<Profile | null>("profile", null);
  },
  async saveProfile(profile) {
    write("profile", profile);
  },
  async recordAttempt(attempt) {
    const attempts = read<Attempt[]>("attempts", []);
    attempts.push({ ...attempt, createdAt: now() });
    write("attempts", attempts.slice(-5000));
  },
  async attempts() {
    return read<Attempt[]>("attempts", []);
  },
  async lessonProgress() {
    return read<Record<string, LessonProgress>>("lessonProgress", {});
  },
  async setLessonStatus(lessonId, _faculty, _year, status) {
    const progress = read<Record<string, LessonProgress>>("lessonProgress", {});
    const previous = progress[lessonId];
    const revisions = Math.max(previous?.revisions ?? 0, STATUS_ORDER.indexOf(status));
    progress[lessonId] = { lessonId, status, revisions, updatedAt: now() };
    write("lessonProgress", progress);
  },
  async clearLessonStatus(lessonId) {
    const progress = read<Record<string, LessonProgress>>("lessonProgress", {});
    delete progress[lessonId];
    write("lessonProgress", progress);
  },
  async highlights(lessonId) {
    return read<Highlight[]>("highlights", []).filter((item) => item.lessonId === lessonId);
  },
  async allHighlights() {
    return read<Highlight[]>("highlights", []);
  },
  async errorReports() {
    return read<ErrorReport[]>("errorReports", []);
  },
  async addHighlight(lessonId, quote, note) {
    const items = read<Highlight[]>("highlights", []);
    items.push({ id: crypto.randomUUID(), lessonId, quote, note: note ?? null, createdAt: now() });
    write("highlights", items);
  },
  async removeHighlight(id) {
    write(
      "highlights",
      read<Highlight[]>("highlights", []).filter((item) => item.id !== id),
    );
  },
  async reportError(lessonId, questionId, message) {
    const reports = read<unknown[]>("errorReports", []);
    reports.push({ lessonId, questionId, message, createdAt: now() });
    write("errorReports", reports);
  },
};

// Supabase --------------------------------------------------------------------------------------

export function supabaseStore(client: SupabaseClient, userId: string): ProgressStore {
  return {
    kind: "supabase",
    async profile() {
      const { data } = await client.from("profiles").select("*").eq("id", userId).maybeSingle();
      if (!data) return null;
      return {
        displayName: data.display_name,
        faculty: data.faculty,
        year: data.year,
        examDate: data.exam_date,
        onboarded: Boolean(data.onboarded_at),
        dailyGoal: data.daily_goal ?? 20,
      };
    },
    async saveProfile(profile) {
      await client
        .from("profiles")
        .update({
          display_name: profile.displayName,
          faculty: profile.faculty,
          year: profile.year,
          exam_date: profile.examDate,
          daily_goal: profile.dailyGoal ?? 20,
        })
        .eq("id", userId);
      // Keep the first onboarding date; set it only once.
      if (profile.onboarded)
        await client.from("profiles").update({ onboarded_at: now() }).eq("id", userId).is("onboarded_at", null);
    },
    async recordAttempt(attempt) {
      await client.from("attempts").insert({
        question_id: attempt.questionId,
        question_type: attempt.questionType,
        lesson_id: attempt.lessonId,
        faculty: attempt.faculty,
        year: attempt.year,
        mode: attempt.mode,
        correct: attempt.correct,
        response: attempt.response,
        time_ms: Math.max(0, Math.round(attempt.timeMs)),
        hints_used: attempt.hintsUsed,
      });
    },
    async attempts() {
      const { data } = await client
        .from("attempts")
        .select("*")
        .order("created_at", { ascending: true })
        .limit(5000);
      return (data ?? []).map((row) => ({
        questionId: row.question_id,
        questionType: row.question_type,
        lessonId: row.lesson_id,
        faculty: row.faculty,
        year: row.year,
        mode: row.mode,
        correct: row.correct,
        response: row.response,
        timeMs: row.time_ms,
        hintsUsed: row.hints_used,
        createdAt: row.created_at,
      }));
    },
    async lessonProgress() {
      const { data } = await client.from("lesson_progress").select("*");
      return Object.fromEntries(
        (data ?? []).map((row) => [
          row.lesson_id,
          { lessonId: row.lesson_id, status: row.status, revisions: row.revisions, updatedAt: row.updated_at },
        ]),
      );
    },
    async setLessonStatus(lessonId, faculty, year, status) {
      await client.from("lesson_progress").upsert(
        { lesson_id: lessonId, faculty, year, status, revisions: STATUS_ORDER.indexOf(status) },
        { onConflict: "user_id,lesson_id" },
      );
    },
    async clearLessonStatus(lessonId) {
      await client.from("lesson_progress").delete().eq("lesson_id", lessonId);
    },
    async allHighlights() {
      const { data } = await client.from("highlights").select("*").order("created_at");
      return (data ?? []).map((row) => ({
        id: String(row.id),
        lessonId: row.lesson_id,
        quote: row.quote,
        note: row.note,
        createdAt: row.created_at,
      }));
    },
    async errorReports() {
      const { data } = await client.from("error_reports").select("*").order("created_at", { ascending: false });
      return (data ?? []).map((row) => ({
        lessonId: row.lesson_id,
        questionId: row.question_id,
        message: row.message,
        createdAt: row.created_at,
      }));
    },
    async highlights(lessonId) {
      const { data } = await client
        .from("highlights")
        .select("*")
        .eq("lesson_id", lessonId)
        .order("created_at");
      return (data ?? []).map((row) => ({
        id: String(row.id),
        lessonId: row.lesson_id,
        quote: row.quote,
        note: row.note,
        createdAt: row.created_at,
      }));
    },
    async addHighlight(lessonId, quote, note) {
      await client.from("highlights").insert({ lesson_id: lessonId, quote, note: note ?? null });
    },
    async removeHighlight(id) {
      await client.from("highlights").delete().eq("id", Number(id));
    },
    async reportError(lessonId, questionId, message) {
      await client.from("error_reports").insert({ lesson_id: lessonId, question_id: questionId, message });
    },
  };
}
