"use client";

import { MotionConfig } from "motion/react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { useProgress } from "@/lib/progress/provider";
import type { Highlight, LessonStatus } from "@/lib/progress/store";

interface LessonContextValue {
  lessonId: string;
  faculty: string;
  year: string;
  status: LessonStatus | null;
  statusLoaded: boolean;
  /** null resets the lesson to "Non lu". */
  setStatus: (status: LessonStatus | null) => Promise<void>;
  highlights: Highlight[];
  addHighlight: (quote: string) => Promise<void>;
  removeHighlight: (id: string) => Promise<void>;
  reportError: (message: string) => Promise<void>;
}

const Context = createContext<LessonContextValue | null>(null);

/** Per-lesson student state (follow-up status, highlights) shared by the lesson's client parts. */
export function LessonProvider({
  lessonId,
  faculty,
  year,
  children,
}: {
  lessonId: string;
  faculty: string;
  year: string;
  children: ReactNode;
}) {
  // The store switches from the browser store to Supabase once the session is known: reload then.
  const { store } = useProgress();
  const [status, setStatusState] = useState<LessonStatus | null>(null);
  const [statusLoaded, setStatusLoaded] = useState(false);
  const [highlights, setHighlights] = useState<Highlight[]>([]);

  useEffect(() => {
    let active = true;
    store.lessonProgress().then((progress) => {
      if (!active) return;
      setStatusState(progress[lessonId]?.status ?? null);
      setStatusLoaded(true);
    });
    store.highlights(lessonId).then((items) => active && setHighlights(items));
    return () => {
      active = false;
    };
  }, [store, lessonId]);

  const setStatus = useCallback(
    async (next: LessonStatus | null) => {
      setStatusState(next);
      if (next === null) await store.clearLessonStatus(lessonId);
      else await store.setLessonStatus(lessonId, faculty, year, next);
    },
    [store, lessonId, faculty, year],
  );

  const addHighlight = useCallback(
    async (quote: string) => {
      await store.addHighlight(lessonId, quote);
      setHighlights(await store.highlights(lessonId));
    },
    [store, lessonId],
  );

  const removeHighlight = useCallback(
    async (id: string) => {
      setHighlights((items) => items.filter((item) => item.id !== id));
      await store.removeHighlight(id);
    },
    [store],
  );

  const reportError = useCallback(
    (message: string) => store.reportError(lessonId, null, message),
    [store, lessonId],
  );

  const value = useMemo(
    () => ({
      lessonId,
      faculty,
      year,
      status,
      statusLoaded,
      setStatus,
      highlights,
      addHighlight,
      removeHighlight,
      reportError,
    }),
    [
      lessonId,
      faculty,
      year,
      status,
      statusLoaded,
      setStatus,
      highlights,
      addHighlight,
      removeHighlight,
      reportError,
    ],
  );

  return (
    <MotionConfig reducedMotion="user">
      <Context.Provider value={value}>{children}</Context.Provider>
    </MotionConfig>
  );
}

export function useLesson() {
  const value = useContext(Context);
  if (!value) throw new Error("useLesson must be used inside <LessonProvider>");
  return value;
}
