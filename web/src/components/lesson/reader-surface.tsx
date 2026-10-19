"use client";

import type { CSSProperties, ReactNode } from "react";

import { readerStyle, useReaderSettings } from "@/lib/reader-settings";
import { cn } from "@/lib/utils";

/** The lesson column: applies the reading settings (size, weight, spacing, width, sources). */
export function ReaderSurface({ children, className }: { children: ReactNode; className?: string }) {
  const settings = useReaderSettings();
  return (
    <div
      className={cn("reader", className)}
      data-sources={settings.showSources ? "on" : "off"}
      style={readerStyle(settings) as CSSProperties}
    >
      {children}
    </div>
  );
}
