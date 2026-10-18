"use client";

import { useCallback, useEffect, useState } from "react";

import { useProgress } from "@/lib/progress/provider";
import type { Attempt, Highlight, LessonProgress, Profile } from "@/lib/progress/store";

import type { EspaceYear } from "./types";

export interface ErrorReport {
  lessonId: string;
  questionId: string | null;
  message: string;
  createdAt: string;
}

export interface EspaceData {
  loading: boolean;
  profile: Profile | null;
  attempts: Attempt[];
  progress: Record<string, LessonProgress>;
  highlights: Highlight[];
  /** null when the store cannot list them (Supabase: no read method yet). */
  reports: ErrorReport[] | null;
  /** Captured on load, so render never reads the clock (prerender-safe). */
  now: Date;
}

const EMPTY: EspaceData = {
  loading: true,
  profile: null,
  attempts: [],
  progress: {},
  highlights: [],
  reports: null,
  now: new Date(0),
};

/** Everything "Mon espace" shows, across both years, loaded once from the progress store. */
export function useEspaceData(years: EspaceYear[]) {
  const { store, ready } = useProgress();
  const [data, setData] = useState<EspaceData>(EMPTY);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    const lessonIds = new Set(years.flatMap((year) => year.availableLessonIds));
    Promise.all([
      store.profile(),
      store.attempts(),
      store.lessonProgress(),
      store
        .allHighlights()
        .then((items) => items.filter((item) => lessonIds.has(item.lessonId)))
        .catch(() => []),
      store.errorReports().catch(() => []),
    ])
      .then(([profile, attempts, progress, highlights, reports]) => {
        if (cancelled) return;
        setData({
          loading: false,
          profile,
          attempts,
          progress,
          highlights,
          reports,
          now: new Date(),
        });
      })
      .catch(() => !cancelled && setData({ ...EMPTY, loading: false, now: new Date() }));
    return () => {
      cancelled = true;
    };
  }, [store, ready, years]);

  const saveProfile = useCallback(
    async (profile: Profile) => {
      await store.saveProfile(profile);
      setData((current) => ({ ...current, profile }));
    },
    [store],
  );

  const removeHighlight = useCallback(
    async (id: string) => {
      let removed: Highlight | undefined;
      setData((current) => {
        removed = current.highlights.find((item) => item.id === id);
        return { ...current, highlights: current.highlights.filter((item) => item.id !== id) };
      });
      try {
        await store.removeHighlight(id);
      } catch {
        if (removed) {
          const restored = removed;
          setData((current) => ({ ...current, highlights: [...current.highlights, restored] }));
        }
      }
    },
    [store],
  );

  return { data, saveProfile, removeHighlight };
}
