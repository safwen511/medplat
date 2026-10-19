"use client";

import { useSyncExternalStore } from "react";

// Reading preferences for lesson pages, kept in this browser. Storage can be blocked (private
// mode): the defaults then apply for the visit.

export type TextSize = "s" | "m" | "l" | "xl";
export type TextWeight = "light" | "regular" | "bold";
export type Spacing = "tight" | "normal" | "airy";
export type PageWidth = "narrow" | "normal" | "wide";

export interface ReaderSettings {
  showSources: boolean;
  size: TextSize;
  weight: TextWeight;
  spacing: Spacing;
  width: PageWidth;
  /** The five highlighter colours, as CSS colours. */
  colors: string[];
  /** Last pen used on lessons: style and colour index. */
  penStyle: "highlight" | "underline" | "box";
  penColor: number;
}

export const DEFAULT_COLORS = ["#fde047", "#86efac", "#7dd3fc", "#f9a8d4", "#fdba74"];

export const DEFAULTS: ReaderSettings = {
  showSources: false,
  size: "m",
  weight: "regular",
  spacing: "normal",
  width: "normal",
  colors: DEFAULT_COLORS,
  penStyle: "highlight",
  penColor: 0,
};

/** Phone/tablet size, desktop size (px). */
export const SIZES: Record<TextSize, [number, number]> = { s: [16, 17], m: [18, 19], l: [20, 21], xl: [22, 23] };
export const WEIGHTS: Record<TextWeight, number> = { light: 400, regular: 450, bold: 520 };
export const LEADINGS: Record<Spacing, number> = { tight: 1.55, normal: 1.7, airy: 1.9 };
export const MEASURES: Record<PageWidth, string> = { narrow: "60ch", normal: "70ch", wide: "82ch" };

const KEY = "medplat:v1:reader";
const EVENT = "medplat:reader-settings";

let cached: ReaderSettings | null = null;

function read(): ReaderSettings {
  if (cached) return cached;
  try {
    const raw = window.localStorage.getItem(KEY);
    cached = raw ? { ...DEFAULTS, ...(JSON.parse(raw) as Partial<ReaderSettings>) } : DEFAULTS;
  } catch {
    cached = DEFAULTS;
  }
  return cached;
}

function subscribe(callback: () => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.key !== KEY) return;
    cached = null;
    callback();
  };
  window.addEventListener(EVENT, callback);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(EVENT, callback);
    window.removeEventListener("storage", onStorage);
  };
}

export function updateReaderSettings(patch: Partial<ReaderSettings>) {
  cached = { ...read(), ...patch };
  try {
    window.localStorage.setItem(KEY, JSON.stringify(cached));
  } catch {
    // kept for this visit only
  }
  window.dispatchEvent(new Event(EVENT));
}

export function useReaderSettings(): ReaderSettings {
  return useSyncExternalStore(subscribe, read, () => DEFAULTS);
}

/** CSS custom properties applied to the lesson surface. */
export function readerStyle(settings: ReaderSettings): Record<string, string> {
  const [mobile, desktop] = SIZES[settings.size];
  return {
    "--reader-size": `${mobile}px`,
    "--reader-size-xl": `${desktop}px`,
    "--reader-weight": String(WEIGHTS[settings.weight]),
    "--reader-leading": String(LEADINGS[settings.spacing]),
    "--reader-measure": MEASURES[settings.width],
    ...Object.fromEntries(settings.colors.map((color, index) => [`--mark-${index + 1}`, color])),
  };
}
