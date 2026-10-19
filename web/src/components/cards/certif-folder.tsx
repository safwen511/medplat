"use client";

import { FolderOpen, PlayCircle, RotateCcw } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { useEffect, useLayoutEffect, useRef, useState, type ComponentProps } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { CertifDeck } from "./certif-deck";
import { escapeToFlipBack, tapToFlipBack } from "./flip-back";
import { styles } from "./styles";
import { themeStyle } from "./themes";
import { TIERS } from "./tiers";

/**
 * Certif "dossier" that flips: tap (or Enter) turns the folder over to its back, with the certif's
 * figures and two actions, open the folder or start a quiz on it. Instant swap with reduced motion.
 */
export function CertifFolder({
  quizHref,
  exercises,
  ...deck
}: Omit<ComponentProps<typeof CertifDeck>, "onOpen"> & { quizHref: string; exercises: number }) {
  const [flipped, setFlipped] = useState(false);
  const backRef = useRef<HTMLButtonElement>(null);
  const frontRef = useRef<HTMLDivElement>(null);
  const userFlip = useRef(false);
  const reduceMotion = useReducedMotion();
  const Emblem = deck.theme.emblem;
  const total = TIERS.reduce((sum, tier) => sum + deck.counts[tier], 0);
  const read = total ? Math.round(((total - deck.counts.non_lu) / total) * 100) : 0;

  function flip(next: boolean) {
    userFlip.current = true;
    setFlipped(next);
  }

  // Keep keyboard focus on the visible face after a flip.
  useEffect(() => {
    if (!userFlip.current) return;
    userFlip.current = false;
    if (flipped) backRef.current?.focus({ preventScroll: true });
    else frontRef.current?.querySelector("button")?.focus({ preventScroll: true });
  }, [flipped]);

  // A flipped folder is transient: show the front again when the page is hidden (route cache).
  useLayoutEffect(() => () => setFlipped(false), []);

  return (
    <div className="h-[212px] [perspective:1400px] sm:h-[228px]">
      <motion.div
        className={styles.flipper}
        initial={false}
        animate={{ rotateY: flipped ? 180 : 0 }}
        transition={{ duration: reduceMotion ? 0 : 0.3, ease: [0.2, 0.8, 0.2, 1] }}
      >
        <div ref={frontRef} className={styles.face} inert={flipped} aria-hidden={flipped}>
          <CertifDeck {...deck} onOpen={() => flip(true)} />
        </div>

        <div
          className={cn(
            styles.face,
            styles.back,
            "flex flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-depth-2",
          )}
          inert={!flipped}
          aria-hidden={!flipped}
          onClick={(event) => tapToFlipBack(event, () => flip(false))}
          onKeyDown={(event) => escapeToFlipBack(event, () => flip(false))}
        >
          <div className={cn(styles.hueTile, "flex items-center gap-2 px-4 py-2.5")} style={themeStyle(deck.theme)}>
            <Emblem className="size-4 shrink-0" strokeWidth={1.75} aria-hidden />
            <span className="truncate text-sm font-semibold">{deck.title}</span>
            <button
              ref={backRef}
              type="button"
              aria-label={`Retourner le dossier « ${deck.title} »`}
              title="Retourner"
              onClick={() => flip(false)}
              className="ml-auto inline-flex size-9 shrink-0 items-center justify-center rounded-control text-white/90 transition-colors hover:bg-white/15 hover:text-white focus-visible:ring-2 focus-visible:ring-white focus-visible:outline-none"
            >
              <RotateCcw className="size-4" aria-hidden />
            </button>
          </div>

          <dl className="grid flex-1 grid-cols-3 gap-2 px-3 py-3">
            <Figure label="maîtrisés" value={deck.counts.maitrise} of={total} />
            <Figure label="lus" value={`${read} %`} />
            <Figure label="précision" value={deck.precision === null ? "—" : `${deck.precision} %`} />
          </dl>

          <div className="flex gap-2 px-3 pb-3">
            <Button asChild variant="outline" className="h-12 flex-1">
              <Link href={deck.href}>
                <FolderOpen aria-hidden /> Ouvrir
              </Link>
            </Button>
            {exercises > 0 ? (
              <Button asChild className="h-12 flex-1 shadow-glow">
                <Link href={quizHref}>
                  <PlayCircle aria-hidden /> Quiz
                </Link>
              </Button>
            ) : (
              <Button disabled className="h-12 flex-1">
                Bientôt
              </Button>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
}

function Figure({ label, value, of }: { label: string; value: number | string; of?: number }) {
  return (
    <div className="flex flex-col-reverse justify-center rounded-control bg-surface-muted px-2 py-2 text-center">
      <dt className="mt-1 text-xs text-muted">{label}</dt>
      <dd className="numeral text-2xl leading-none font-semibold">
        {value}
        {of !== undefined && <span className="text-sm font-normal text-muted">/{of}</span>}
      </dd>
    </div>
  );
}
