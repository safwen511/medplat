import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { styles } from "./styles";
import { themeStyle, type CertifTheme } from "./themes";

const GRID = {
  backgroundImage:
    "linear-gradient(rgb(255 255 255 / 0.08) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255 / 0.08) 1px, transparent 1px)",
  backgroundSize: "14px 14px",
};

/** ECG trace drawn across the art. Decorative. */
export function EcgTrace({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 200 60"
      preserveAspectRatio="none"
      className={cn("pointer-events-none absolute inset-x-0", className)}
      aria-hidden
    >
      <path
        d="M0 40 H58 L64 40 L70 30 L76 44 L84 8 L92 54 L98 40 H128 L134 33 L142 40 H200"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

const DOTS = {
  backgroundImage: "radial-gradient(rgb(255 255 255 / 0.14) 1px, transparent 1.5px)",
  backgroundSize: "12px 12px",
};

/** Smooth wave trace (respiratory / EEG feel). Decorative. */
function WaveTrace({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 60" preserveAspectRatio="none" className={cn("pointer-events-none absolute inset-x-0", className)} aria-hidden>
      <path
        d="M0 30 C 20 6, 30 6, 50 30 S 80 54, 100 30 S 130 6, 150 30 S 180 54, 200 30"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

/** Concentric arcs from a corner. Decorative. */
function Arcs({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" className={cn("pointer-events-none absolute", className)} aria-hidden>
      {[30, 48, 66, 84].map((r) => (
        <circle key={r} cx="0" cy="100" r={r} fill="none" stroke="currentColor" strokeWidth="0.8" />
      ))}
    </svg>
  );
}

/**
 * Composition variants so neighbouring course cards of one certif don't look identical: the
 * pattern, the trace, the watermark corner and a small hue shift change; identity stays.
 */
const VARIANTS = [
  { hueShift: 0, pattern: GRID, watermark: "-right-6 -bottom-6 -rotate-12", trace: "ecg" },
  { hueShift: 10, pattern: DOTS, watermark: "-left-6 -top-6 rotate-12", trace: "wave" },
  { hueShift: -10, pattern: GRID, watermark: "-left-8 -bottom-8 rotate-6", trace: "arcs" },
  { hueShift: 18, pattern: DOTS, watermark: "-right-8 -top-8 -rotate-6", trace: "ecg-low" },
] as const;

/**
 * Card illustration: the certif's hue as a gradient, a fine grid, an ECG trace and the specialty
 * emblem in a ring, plus a large faint watermark of the same emblem. Children overlay the art
 * (badges). `muted` desaturates it for lessons that are not available yet.
 */
export function CertifArt({
  theme,
  muted = false,
  emblemSize = 34,
  variant = 0,
  className,
  children,
}: {
  theme: CertifTheme;
  muted?: boolean;
  /** Any integer (e.g. the course number); picks one of the composition variants. */
  variant?: number;
  emblemSize?: number;
  className?: string;
  children?: ReactNode;
}) {
  const Emblem = theme.emblem;
  const look = VARIANTS[Math.abs(Math.trunc(variant)) % VARIANTS.length];
  return (
    <div className={cn("relative", className)} style={themeStyle({ ...theme, hue: theme.hue + look.hueShift })}>
      <div className={cn(styles.art, "absolute inset-0")} data-muted={muted} aria-hidden>
        <div className="absolute inset-0" style={look.pattern} />
        <Emblem className={cn("absolute size-32 text-white/10", look.watermark)} strokeWidth={1} aria-hidden />
        {look.trace === "ecg" && <EcgTrace className="top-[52%] h-1/3 text-white/30" />}
        {look.trace === "ecg-low" && <EcgTrace className="top-[68%] h-1/4 text-white/25" />}
        {look.trace === "wave" && <WaveTrace className="top-[58%] h-1/4 text-white/25" />}
        {look.trace === "arcs" && <Arcs className="bottom-0 left-0 size-full text-white/15" />}
        <div className="absolute inset-0 flex items-center justify-center">
          <span
            className={cn(
              "flex items-center justify-center rounded-full bg-white/12 ring-1 ring-white/35 backdrop-blur-[2px]",
              "shadow-[0_0_0_6px_rgb(255_255_255/0.06),0_8px_24px_-8px_rgb(0_0_0/0.35)]",
              muted && "opacity-75",
            )}
            style={{ width: emblemSize * 1.9, height: emblemSize * 1.9 }}
          >
            <Emblem className="text-white" style={{ width: emblemSize, height: emblemSize }} strokeWidth={1.5} />
          </span>
        </div>
      </div>
      {children}
    </div>
  );
}

/** Small rounded tile with the certif emblem on its hue, for headers and lists. */
export function CertifEmblem({ theme, className }: { theme: CertifTheme; className?: string }) {
  const Emblem = theme.emblem;
  return (
    <span
      className={cn(styles.hueTile, "relative inline-flex size-10 shrink-0 items-center justify-center rounded-xl", className)}
      style={themeStyle(theme)}
      aria-hidden
    >
      <Emblem className="size-1/2" strokeWidth={1.75} />
    </span>
  );
}
