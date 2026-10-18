"use client";

import Link from "next/link";

import { cn } from "@/lib/utils";

import { styles } from "./styles";
import { themeStyle, type CertifTheme } from "./themes";
import { TierFill } from "./tier-frame";
import { TIER_LABELS, TIERS, type Tier } from "./tiers";
import { Glare, Tilt } from "./tilt";

/**
 * Certif "dossier": a medical file folder in the certif's hue with its pole on the tab and the
 * edges of its best cards peeking out behind (their frames show the tiers reached). Opens the
 * certif's card collection.
 */
export function CertifDeck({
  href,
  title,
  fullTitle,
  pole,
  theme,
  counts,
  available,
  precision,
  answered,
}: {
  href: string;
  /** Short display title ("Cardiologie"). */
  title: string;
  /** Full certif title, for assistive tech and the tooltip. */
  fullTitle: string;
  pole: string;
  theme: CertifTheme;
  counts: Record<Tier, number>;
  available: number;
  /** 0..100, null without answers. */
  precision: number | null;
  answered: number;
}) {
  const Emblem = theme.emblem;
  const total = TIERS.reduce((sum, tier) => sum + counts[tier], 0);
  const read = total - counts.non_lu;
  const readPercent = total ? Math.round((read / total) * 100) : 0;
  const peeks = peekTiers(counts);
  const distribution = TIERS.filter((tier) => counts[tier] > 0)
    .map((tier) => `${counts[tier]} ${TIER_LABELS[tier].toLowerCase()}`)
    .join(", ");

  return (
    <Tilt className="rounded-2xl" max={8}>
      <Link
        href={href}
        title={fullTitle}
        className={cn(
          styles.deck,
          "h-[212px] sm:h-[228px]",
          "focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
        )}
        style={themeStyle(theme)}
      >
        <span className={styles.deckBack} aria-hidden />
        <span className={styles.deckTab}>
          Pôle {pole}
        </span>
        {peeks.map((tier, index) => (
          <span key={index} className={styles.peek} data-i={index} data-tier={tier} aria-hidden />
        ))}
        <span className={cn(styles.deckFront, "flex flex-col gap-3 p-4")}>
          <Emblem
            className="pointer-events-none absolute -right-5 -bottom-7 size-36 -rotate-12 text-white/10"
            strokeWidth={1}
            aria-hidden
          />
          <span className="relative flex items-start gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-white/15 ring-1 ring-white/30">
              <Emblem className="size-5" strokeWidth={1.75} aria-hidden />
            </span>
            <span className="flex min-w-0 flex-col gap-0.5">
              <span className="line-clamp-2 text-[15px] leading-tight font-semibold">
                <span className="sr-only">{fullTitle}</span>
                <span aria-hidden>{title}</span>
              </span>
              <span className="text-[11px] text-white/85">
                {total} cours · {available === 0 ? "bientôt disponibles" : `${available} disponible${available > 1 ? "s" : ""}`}
              </span>
            </span>
          </span>

          <span className="relative mt-auto flex items-end justify-between gap-3">
            <span className="leading-none">
              <span className="text-2xl font-semibold tabular-nums">{counts.maitrise}</span>
              <span className="text-sm text-white/85">
                {" "}
                / {total} maîtrisée{counts.maitrise > 1 ? "s" : ""}
              </span>
            </span>
            <span className="flex flex-col items-end gap-0.5 text-[11px] text-white/85">
              <span>
                Lus <span className="font-semibold text-white tabular-nums">{readPercent} %</span>
              </span>
              <span>
                Précision{" "}
                <span className="font-semibold text-white tabular-nums">
                  {precision === null ? "—" : `${precision} %`}
                </span>
                {answered > 0 && <span className="sr-only"> sur {answered} réponses</span>}
              </span>
            </span>
          </span>

          <span className="relative flex h-1.5 w-full gap-px overflow-hidden rounded-full" aria-hidden>
            {TIERS.map((tier) =>
              counts[tier] > 0 ? (
                <TierFill key={tier} tier={tier} onHue className="block h-full" style={{ flexGrow: counts[tier] }} />
              ) : null,
            )}
          </span>
          <span className="sr-only">Répartition : {distribution || "aucun cours"}.</span>
          <Glare />
        </span>
      </Link>
    </Tilt>
  );
}

/** Three card edges behind the folder: the highest tiers reached, the best one in front. */
function peekTiers(counts: Record<Tier, number>): Tier[] {
  const reached = [...TIERS].reverse().filter((tier) => tier !== "non_lu" && counts[tier] > 0);
  const picked = reached.slice(0, 3);
  while (picked.length < 3) picked.push("non_lu");
  return picked.reverse();
}
