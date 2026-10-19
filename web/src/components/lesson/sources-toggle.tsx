"use client";

import { updateReaderSettings, useReaderSettings } from "@/lib/reader-settings";
import { cn } from "@/lib/utils";

/** Shows or hides the inline source chips ("S1 p.12"); hidden by default. */
export function SourcesToggle({ className }: { className?: string }) {
  const { showSources } = useReaderSettings();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={showSources}
      onClick={() => updateReaderSettings({ showSources: !showSources })}
      className={cn(
        "inline-flex min-h-12 items-center gap-2.5 rounded-control text-[0.9375rem] text-muted transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
    >
      <span
        aria-hidden
        className={cn(
          "relative h-5 w-9 rounded-full transition-colors duration-200",
          showSources ? "bg-primary" : "bg-surface-muted ring-1 ring-border-strong",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 left-0.5 size-4 rounded-full bg-background shadow transition-transform duration-200",
            showSources && "translate-x-4",
          )}
        />
      </span>
      Afficher les sources
    </button>
  );
}
