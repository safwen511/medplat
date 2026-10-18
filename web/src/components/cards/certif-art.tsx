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

/**
 * Card illustration: the certif's hue as a gradient, a fine grid, an ECG trace and the specialty
 * emblem in a ring, plus a large faint watermark of the same emblem. Children overlay the art
 * (badges). `muted` desaturates it for lessons that are not available yet.
 */
export function CertifArt({
  theme,
  muted = false,
  emblemSize = 34,
  className,
  children,
}: {
  theme: CertifTheme;
  muted?: boolean;
  emblemSize?: number;
  className?: string;
  children?: ReactNode;
}) {
  const Emblem = theme.emblem;
  return (
    <div className={cn("relative", className)} style={themeStyle(theme)}>
      <div className={cn(styles.art, "absolute inset-0")} data-muted={muted} aria-hidden>
        <div className="absolute inset-0" style={GRID} />
        <Emblem
          className="absolute -right-6 -bottom-6 size-32 -rotate-12 text-white/10"
          strokeWidth={1}
          aria-hidden
        />
        <EcgTrace className="top-[52%] h-1/3 text-white/30" />
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
