"use client";

import { RotateCcw, Settings2 } from "lucide-react";
import { motion } from "motion/react";
import { useTheme } from "next-themes";
import { useState, type ReactNode } from "react";

import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { PRESS } from "@/lib/motion";
import {
  DEFAULTS,
  updateReaderSettings,
  useReaderSettings,
  type PageWidth,
  type Spacing,
  type TextSize,
  type TextWeight,
} from "@/lib/reader-settings";
import { cn } from "@/lib/utils";

import { SourcesToggle } from "./sources-toggle";

const PALETTES: { name: string; colors: string[] }[] = [
  { name: "Classique", colors: DEFAULTS.colors },
  { name: "Pastel", colors: ["#fef08a", "#bbf7d0", "#bae6fd", "#fbcfe8", "#fed7aa"] },
  { name: "Vif", colors: ["#facc15", "#22c55e", "#38bdf8", "#f472b6", "#fb923c"] },
  { name: "Sobre", colors: ["#e7d38a", "#a7c7a1", "#9fb8d1", "#d3a5b5", "#d9b08c"] },
];

function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (value: T) => void;
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 text-sm font-medium">{label}</legend>
      <div className="grid gap-1 rounded-control bg-surface-muted p-1" style={{ gridTemplateColumns: `repeat(${options.length}, 1fr)` }}>
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={value === option.value}
            onClick={() => onChange(option.value)}
            className={cn(
              "flex min-h-10 items-center justify-center rounded-[10px] px-2 text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              value === option.value ? "bg-background font-medium text-foreground shadow-depth-1" : "text-muted hover:text-foreground",
            )}
          >
            {option.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

/** Round button at the bottom left of lesson pages: reading settings, kept in this browser. */
export function ReaderSettingsButton() {
  const settings = useReaderSettings();
  const { resolvedTheme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <motion.button
          type="button"
          whileTap={PRESS}
          aria-label="Réglages de lecture"
          title="Réglages de lecture"
          className="fixed bottom-[calc(1.25rem+env(safe-area-inset-bottom))] left-4 z-30 flex size-12 items-center justify-center rounded-full border border-border-strong bg-background/85 text-foreground shadow-depth-2 backdrop-blur-xl transition-shadow hover:shadow-glow focus-visible:shadow-glow focus-visible:outline-none print:hidden"
        >
          <Settings2 className="size-5" strokeWidth={1.7} aria-hidden />
        </motion.button>
      </DialogTrigger>
      <DialogContent
        className="top-auto bottom-0 left-0 max-h-[88vh] w-full max-w-none translate-x-0 translate-y-0 overflow-y-auto rounded-b-none pb-[calc(1.5rem+env(safe-area-inset-bottom))] sm:top-1/2 sm:bottom-auto sm:left-1/2 sm:w-[calc(100%-2rem)] sm:max-w-md sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-b-card"
        onCloseAutoFocus={(event) => event.preventDefault()}
      >
        <DialogTitle className="font-heading">Réglages de lecture</DialogTitle>
        <DialogDescription className="mb-5">Gardés sur cet appareil.</DialogDescription>
        <div className="flex flex-col gap-6 font-sans">
          <Segmented<TextSize>
            label="Taille du texte"
            value={settings.size}
            onChange={(size) => updateReaderSettings({ size })}
            options={[
              { value: "s", label: <span className="text-[0.8rem]">Aa</span> },
              { value: "m", label: <span className="text-[0.95rem]">Aa</span> },
              { value: "l", label: <span className="text-[1.1rem]">Aa</span> },
              { value: "xl", label: <span className="text-[1.25rem]">Aa</span> },
            ]}
          />
          <Segmented<TextWeight>
            label="Graisse"
            value={settings.weight}
            onChange={(weight) => updateReaderSettings({ weight })}
            options={[
              { value: "light", label: <span style={{ fontWeight: 400 }}>Fine</span> },
              { value: "regular", label: <span style={{ fontWeight: 450 }}>Normale</span> },
              { value: "bold", label: <span style={{ fontWeight: 540 }}>Appuyée</span> },
            ]}
          />
          <Segmented<Spacing>
            label="Interligne"
            value={settings.spacing}
            onChange={(spacing) => updateReaderSettings({ spacing })}
            options={[
              { value: "tight", label: "Serré" },
              { value: "normal", label: "Normal" },
              { value: "airy", label: "Aéré" },
            ]}
          />
          <Segmented<PageWidth>
            label="Largeur de page"
            value={settings.width}
            onChange={(width) => updateReaderSettings({ width })}
            options={[
              { value: "narrow", label: "Étroite" },
              { value: "normal", label: "Normale" },
              { value: "wide", label: "Large" },
            ]}
          />
          <Segmented<"dark" | "light">
            label="Thème"
            value={resolvedTheme === "light" ? "light" : "dark"}
            onChange={(theme) => setTheme(theme)}
            options={[
              { value: "dark", label: "Sombre" },
              { value: "light", label: "Clair" },
            ]}
          />
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-medium">Couleurs du surligneur</legend>
            <div className="grid grid-cols-2 gap-2">
              {PALETTES.map((palette) => {
                const current = palette.colors.join() === settings.colors.join();
                return (
                  <button
                    key={palette.name}
                    type="button"
                    aria-pressed={current}
                    onClick={() => updateReaderSettings({ colors: palette.colors })}
                    className={cn(
                      "flex min-h-12 items-center justify-between gap-2 rounded-control border px-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      current ? "border-primary/60 bg-primary-soft" : "border-border hover:border-border-strong",
                    )}
                  >
                    {palette.name}
                    <span className="flex -space-x-1">
                      {palette.colors.map((color) => (
                        <span key={color} className="size-3.5 rounded-full ring-2 ring-background" style={{ background: color }} />
                      ))}
                    </span>
                  </button>
                );
              })}
            </div>
          </fieldset>
          <SourcesToggle />
          <button
            type="button"
            onClick={() => updateReaderSettings({ ...DEFAULTS, penStyle: settings.penStyle, penColor: settings.penColor })}
            className="inline-flex min-h-11 items-center gap-2 self-start rounded-control text-sm text-muted transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <RotateCcw className="size-4" aria-hidden /> Réinitialiser
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
