"use client";

import { BookOpen, Flame, Lock, PlayCircle, RotateCcw } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import type { LessonSummary } from "@/lib/content/types";
import { cn } from "@/lib/utils";

import { escapeToFlipBack, tapToFlipBack } from "./flip-back";
import { styles } from "./styles";
import { CertifArt } from "./certif-art";
import { ProgressRing } from "./progress-ring";
import { themeStyle, type CertifTheme } from "./themes";
import { TierFrame } from "./tier-frame";
import { TierStepper } from "./tier-stepper";
import { TIER_LABELS, type Tier } from "./tiers";
import { Glare, Tilt } from "./tilt";

export const HIGH_YIELD_THRESHOLD = 3;

export interface LessonCardStats {
  /** Questions answered on this lesson. */
  answered: number;
  /** 0..100, null without answers. */
  precision: number | null;
  /** Formatted values for the back of the card ("—" when unknown). */
  meanTime: string;
  lastReview: string;
}

const TIER_TEXT: Record<Tier, string> = {
  non_lu: "text-muted",
  lu: "text-primary",
  revise_1: "text-foreground/75",
  revise_2: "text-foreground",
  maitrise: "text-highyield",
};

/**
 * Portrait lesson card. Front: certif art, course number, high-yield flame, "Bientôt" lock,
 * title, module and precision ring, inside a frame showing the mastery tier. Click / Enter flips
 * it to the "dossier" back: stats, the status stepper (back to "Non lu" included) and actions.
 */
export function LessonCard({
  lesson,
  moduleTitle,
  theme,
  tier,
  stats,
  loading = false,
  readHref,
  quizHref,
  onTierChange,
}: {
  lesson: LessonSummary;
  moduleTitle: string;
  theme: CertifTheme;
  tier: Tier;
  stats: LessonCardStats;
  loading?: boolean;
  readHref: string;
  quizHref: string;
  onTierChange: (tier: Tier) => void;
}) {
  const [flipped, setFlipped] = useState(false);
  const frontRef = useRef<HTMLButtonElement>(null);
  const backRef = useRef<HTMLButtonElement>(null);
  const userFlip = useRef(false);
  const reduceMotion = useReducedMotion();
  const highYield = lesson.pastExamCount >= HIGH_YIELD_THRESHOLD;
  const Emblem = theme.emblem;

  function flip(next: boolean) {
    userFlip.current = true;
    setFlipped(next);
  }

  // Keep keyboard focus on the visible face after a flip.
  useEffect(() => {
    if (!userFlip.current) return;
    userFlip.current = false;
    (flipped ? backRef : frontRef).current?.focus({ preventScroll: true });
  }, [flipped]);

  // A flipped card is transient: show the front again when the page is hidden (route cache).
  useLayoutEffect(() => () => setFlipped(false), []);

  const precisionText = stats.precision === null ? "pas encore de réponse" : `${stats.precision} %`;
  const frontLabel = [
    `${lesson.title}, cours ${lesson.order}`,
    moduleTitle,
    `Statut : ${TIER_LABELS[tier]}`,
    `Précision : ${precisionText}`,
    !lesson.available && "Bientôt disponible",
    highYield && `Tombe souvent, ${lesson.pastExamCount} examens`,
    "Afficher le dossier",
  ]
    .filter(Boolean)
    .join(". ");

  return (
    <Tilt className="rounded-[14px]">
      <div className={styles.scene}>
        <motion.div
          className={styles.flipper}
          initial={false}
          animate={{ rotateY: flipped ? 180 : 0 }}
          transition={reduceMotion ? { duration: 0 } : { type: "spring", stiffness: 210, damping: 24, mass: 0.9 }}
        >
          {/* Front ------------------------------------------------------------------------ */}
          <div className={styles.face} inert={flipped} aria-hidden={flipped}>
            <TierFrame tier={tier}>
              <button
                ref={frontRef}
                type="button"
                aria-pressed={false}
                aria-label={frontLabel}
                onClick={() => flip(true)}
                className="flex h-full w-full flex-col text-left focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring focus-visible:ring-inset"
              >
                <CertifArt theme={theme} variant={lesson.order} muted={!lesson.available} className="h-[58%] w-full shrink-0">
                  <span className="absolute top-2 left-2 rounded-md bg-black/30 px-1.5 py-0.5 text-[11px] leading-none font-semibold text-white tabular-nums backdrop-blur-sm">
                    {lesson.order}
                  </span>
                  {highYield && (
                    <span
                      className="absolute top-2 right-2 inline-flex items-center gap-0.5 rounded-full bg-highyield-soft px-1.5 py-0.5 text-[11px] leading-none font-semibold text-highyield shadow-sm"
                      title={`Tombe souvent · ${lesson.pastExamCount} examens`}
                    >
                      <Flame className="size-3" aria-hidden />
                      {lesson.pastExamCount}
                    </span>
                  )}
                  {!lesson.available && (
                    <span className="absolute bottom-2 left-2 inline-flex items-center gap-1 rounded-full bg-black/45 px-2 py-0.5 text-[11px] font-medium text-white backdrop-blur-sm">
                      <Lock className="size-3" aria-hidden />
                      Bientôt
                    </span>
                  )}
                </CertifArt>
                <span className="flex min-h-0 flex-1 flex-col gap-0.5 p-2.5">
                  <span
                    className={cn(
                      "line-clamp-2 text-[13px] leading-snug font-semibold",
                      !lesson.available && "text-foreground/80",
                    )}
                  >
                    {lesson.title}
                  </span>
                  <span className="truncate text-[11px] text-muted">{moduleTitle}</span>
                  <span className="mt-auto flex items-center justify-between gap-2 pt-1">
                    <ProgressRing value={stats.precision} label="Précision" size={28} />
                    {loading ? (
                      <span className="h-3 w-12 animate-pulse rounded-full bg-surface-muted" />
                    ) : (
                      <span className={cn("truncate text-[11px] font-semibold", TIER_TEXT[tier])}>
                        {TIER_LABELS[tier]}
                      </span>
                    )}
                  </span>
                </span>
              </button>
              <Glare />
            </TierFrame>
          </div>

          {/* Back: the lesson's "dossier" ----------------------------------------------------- */}
          <div
            className={cn(styles.face, styles.back)}
            inert={!flipped}
            aria-hidden={!flipped}
            onClick={(event) => tapToFlipBack(event, () => flip(false))}
            onKeyDown={(event) => escapeToFlipBack(event, () => flip(false))}
          >
            <TierFrame tier={tier}>
              <div className="flex h-full flex-col">
                <div
                  className={cn(styles.hueTile, "flex shrink-0 items-center gap-1.5 py-0.5 pr-1 pl-2.5")}
                  style={themeStyle(theme)}
                >
                  <Emblem className="size-3.5 shrink-0" strokeWidth={1.75} aria-hidden />
                  <span className="truncate text-[11px] font-semibold tracking-wide uppercase">
                    Dossier n° {lesson.order}
                  </span>
                  <button
                    ref={backRef}
                    type="button"
                    aria-pressed={true}
                    aria-label={`Retourner la carte « ${lesson.title} »`}
                    title="Retourner"
                    onClick={() => flip(false)}
                    className="ml-auto inline-flex size-6 shrink-0 items-center justify-center rounded-md text-white/90 transition-colors hover:bg-white/15 hover:text-white focus-visible:ring-2 focus-visible:ring-white focus-visible:outline-none"
                  >
                    <RotateCcw className="size-3.5" aria-hidden />
                  </button>
                </div>
                <div className="flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto p-2">
                  <h3 className="line-clamp-1 text-xs leading-snug font-semibold max-sm:sr-only" title={lesson.title}>
                    {lesson.title}
                  </h3>
                  <dl className="flex flex-col text-[11px]">
                    <Row label="Précision" value={stats.precision === null ? "—" : `${stats.precision} %`} />
                    <Row label="Questions répondues" value={String(stats.answered)} />
                    <Row label="Temps moyen" value={stats.meanTime} className="max-sm:hidden" />
                    <Row label="Dernière révision" value={stats.lastReview} className="max-sm:hidden" />
                    <Row
                      label="Examens passés"
                      value={String(lesson.pastExamCount)}
                      emphasis={highYield ? "highyield" : undefined}
                    />
                    <Row label="Exercices disponibles" value={String(lesson.exerciseCount)} className="max-sm:hidden" />
                  </dl>
                  <TierStepper
                    tier={tier}
                    lessonTitle={lesson.title}
                    onChange={onTierChange}
                    disabled={loading}
                  />
                  <div className="mt-auto flex gap-1.5 pt-0.5">
                    {lesson.available ? (
                      <Button asChild size="sm" className="h-7 flex-1 gap-1 px-2 text-xs [&_svg]:size-3.5">
                        <Link href={readHref}>
                          <BookOpen aria-hidden />
                          Lire<span className="sr-only"> le cours</span>
                        </Link>
                      </Button>
                    ) : (
                      <span className="inline-flex h-7 flex-1 items-center justify-center gap-1 rounded-card bg-surface-muted text-xs text-muted">
                        <Lock className="size-3" aria-hidden />
                        Bientôt
                      </span>
                    )}
                    <Button
                      asChild
                      variant="outline"
                      size="sm"
                      className="h-7 flex-1 gap-1 px-2 text-xs [&_svg]:size-3.5"
                    >
                      <Link href={quizHref}>
                        <PlayCircle aria-hidden />
                        Quiz<span className="sr-only"> sur ce certif</span>
                      </Link>
                    </Button>
                  </div>
                </div>
              </div>
            </TierFrame>
          </div>
        </motion.div>
      </div>
    </Tilt>
  );
}

function Row({
  label,
  value,
  emphasis,
  className,
}: {
  label: string;
  value: string;
  emphasis?: "highyield";
  /** Narrow phone cards hide the secondary rows so the actions stay in view. */
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-baseline justify-between gap-2 border-b border-dashed border-border py-[2px] leading-tight last:border-b-0",
        className,
      )}
    >
      <dt className="truncate text-muted">{label}</dt>
      <dd
        className={cn(
          "shrink-0 font-semibold tabular-nums",
          emphasis === "highyield" ? "inline-flex items-center gap-0.5 text-highyield" : "text-foreground",
        )}
      >
        {emphasis === "highyield" && <Flame className="size-3" aria-hidden />}
        {value}
      </dd>
    </div>
  );
}
