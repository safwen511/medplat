import Link from "next/link";

import type { Attempt, LessonProgress } from "@/lib/progress/store";
import { cn } from "@/lib/utils";

import { EspaceSection } from "./section";
import { certifHref, shortCertifTitle, tierOf, TIER_LABELS, type EspaceYear, type Tier } from "./types";

const BAR: Record<Exclude<Tier, "non_lu">, string> = {
  maitrise: "bg-highyield",
  revise: "bg-primary",
  lu: "bg-primary/45",
};

function count(lessonIds: string[], progress: Record<string, LessonProgress>) {
  const tiers: Record<Tier, number> = { maitrise: 0, revise: 0, lu: 0, non_lu: 0 };
  for (const id of lessonIds) tiers[tierOf(progress[id])]++;
  return { tiers, total: lessonIds.length };
}

/** Stacked bar: mastered, revised, read; the rest of the track is still to read. */
function TierBar({ tiers, total, label }: { tiers: Record<Tier, number>; total: number; label: string }) {
  const done = total - tiers.non_lu;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={done}
      className="flex h-2 w-full gap-px overflow-hidden rounded-full bg-surface-muted"
    >
      {(["maitrise", "revise", "lu"] as const).map((tier) =>
        tiers[tier] ? (
          <span key={tier} className={cn("h-full", BAR[tier])} style={{ flexGrow: tiers[tier], flexBasis: 0 }} />
        ) : null,
      )}
      {tiers.non_lu > 0 && <span className="h-full" style={{ flexGrow: tiers.non_lu, flexBasis: 0 }} />}
    </div>
  );
}

/** Per-certif progress: a stacked bar each, mastered count and accuracy. */
export function Collection({
  year,
  progress,
  attempts,
}: {
  year: EspaceYear;
  progress: Record<string, LessonProgress>;
  attempts: Attempt[];
}) {
  const totals = count(
    year.certifs.flatMap((certif) => certif.lessons.map((lesson) => lesson.id)),
    progress,
  );

  return (
    <EspaceSection
      id="collection"
      title="Progression par certif"
      action={
        <span className="inline-flex items-baseline gap-1 rounded-full bg-highyield-soft px-3 py-1 text-sm text-highyield">
          <span className="numeral font-semibold">{totals.tiers.maitrise}</span>/{totals.total} maîtrisés
        </span>
      }
    >
      <div className="flex items-center justify-between gap-4">
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Légende">
        {(["maitrise", "revise", "lu"] as const).map((tier) => (
          <li key={tier} className="inline-flex items-center gap-1.5">
            <span className={cn("size-2.5 rounded-full", BAR[tier])} aria-hidden />
            {TIER_LABELS[tier]}
          </li>
        ))}
      </ul>
        <span className="flex shrink-0 gap-3 text-xs text-muted" aria-hidden>
          <span>maîtrisés</span>
          <span className="w-12 text-right">précision</span>
        </span>
      </div>
      <ul className="-mx-2 flex flex-col">
        {year.certifs.map((certif) => {
          const ids = new Set(certif.lessons.map((lesson) => lesson.id));
          const { tiers, total } = count([...ids], progress);
          const mine = attempts.filter((item) => ids.has(item.lessonId));
          const percent = mine.length
            ? Math.round((mine.filter((item) => item.correct).length / mine.length) * 100)
            : null;
          const title = shortCertifTitle(certif.title);
          return (
            <li key={certif.slug}>
              <Link
                href={certifHref(year, certif.slug)}
                className="flex flex-col gap-2 rounded-card px-2 py-3 transition-colors duration-150 hover:bg-surface focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                <span className="flex items-baseline justify-between gap-4">
                  <span className="min-w-0 truncate font-medium" title={certif.title}>
                    {title}
                  </span>
                  <span className="flex shrink-0 items-baseline gap-3 text-sm text-muted tabular-nums">
                    <span>
                      <span className="numeral font-semibold text-foreground">{tiers.maitrise}</span>/{total}
                    </span>
                    <span className="w-12 text-right">{percent === null ? "—" : `${percent} %`}</span>
                  </span>
                </span>
                <TierBar tiers={tiers} total={total} label={`${title} : ${total - tiers.non_lu} cours ouverts sur ${total}`} />
              </Link>
            </li>
          );
        })}
      </ul>
    </EspaceSection>
  );
}
