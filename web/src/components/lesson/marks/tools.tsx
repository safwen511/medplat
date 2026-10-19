"use client";

import { createContext, useCallback, useContext, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";

import { updateReaderSettings, useReaderSettings } from "@/lib/reader-settings";

import type { MarkStyle } from "./store";

export type Tool = "pen" | "eraser" | null;

interface ToolsValue {
  /** "pen": a selection is marked; "eraser": a tap removes a mark; null: plain reading. */
  tool: Tool;
  style: MarkStyle;
  color: number;
  /** Arabic lens (glossary terms underlined, tap for the translation). */
  lens: boolean;
  /** Active recall: key terms become blanks. */
  recall: boolean;
  setTool: (tool: Tool) => void;
  choosePen: (style: MarkStyle) => void;
  chooseColor: (color: number) => void;
  setLens: (on: boolean) => void;
  setRecall: (on: boolean) => void;
}

const Context = createContext<ToolsValue | null>(null);

/** Reading tools of a lesson page, shared by the toolbar and the lesson text. */
export function ToolsProvider({ children }: { children: ReactNode }) {
  const [tool, setTool] = useState<Tool>("pen");
  const settings = useReaderSettings();
  const pen = useMemo(() => ({ style: settings.penStyle, color: settings.penColor }), [settings.penStyle, settings.penColor]);
  const [lens, setLens] = useState(false);
  const [recall, setRecall] = useState(false);

  const remember = useCallback(
    (next: { style: MarkStyle; color: number }) => updateReaderSettings({ penStyle: next.style, penColor: next.color }),
    [],
  );

  const value = useMemo<ToolsValue>(
    () => ({
      tool,
      style: pen.style,
      color: pen.color,
      lens,
      recall,
      setTool,
      choosePen: (style) => {
        // Tapping the active pen again puts it down (plain reading).
        if (tool === "pen" && pen.style === style) setTool(null);
        else {
          setTool("pen");
          remember({ ...pen, style });
        }
      },
      chooseColor: (color) => {
        setTool("pen");
        remember({ ...pen, color });
      },
      setLens,
      setRecall,
    }),
    [tool, pen, lens, recall, remember],
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useTools(): ToolsValue {
  const value = useContext(Context);
  if (!value) throw new Error("useTools must be used inside <ToolsProvider>");
  return value;
}

const COMPACT = "(max-width: 767px), (max-height: 30rem) and (orientation: landscape)";

/** Phones and phones in landscape: the toolbar folds into a small pill. */
export function useCompact(): boolean {
  return useSyncExternalStore(
    (callback) => {
      const media = window.matchMedia(COMPACT);
      media.addEventListener("change", callback);
      return () => media.removeEventListener("change", callback);
    },
    () => window.matchMedia(COMPACT).matches,
    () => false,
  );
}
