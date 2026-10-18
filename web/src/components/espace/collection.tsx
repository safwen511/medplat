import Link from "next/link";

import type { LessonProgress } from "@/lib/progress/store";

import { EspaceSection } from "./section";
import { certifHref, shortCertifTitle, tierOf, type EspaceYear } from "./types";

function count(lessonIds: string[], progress: Record<string, LessonProgress>) {
  let mastered = 0;
  let opened = 0;
  for (const id of lessonIds) {
    const tier = tierOf(progress[id]);
    if (tier === "maitrise") mastered++;
    if (tier !== "non_lu") opened++;
  }
  return { mastered, opened, total: lessonIds.length };
}

/** A thin line for the mastered share; the numbers next to it carry the meaning. */
function ThinLine({ value, total }: { value: number; total: number }) {
  const share = total ? (value / total) * 100 : 0;
  return (
    <div aria-hidden className="h-0.5 w-full overflow-hidden rounded-full bg-border">
      <div className="h-full rounded-full bg-muted" style={{ width: `${share}%` }} />
    </div>
  );
}

export function Collection({ year, progress }: { year: EspaceYear; progress: Record<string, LessonProgress> }) {
  const totals = count(
    year.certifs.flatMap((certif) => certif.lessons.map((lesson) => lesson.id)),
    progress,
  );

  return (
    <EspaceSection
      id="collection"
      title="Ma collection"
      description={
        <>
          <span className="font-medium tabular-nums text-foreground">
            {totals.mastered} / {totals.total}
          </span>{" "}
          cours maîtrisés en {year.yearLabel}, {totals.opened} ouverts au moins une fois.
        </>
      }
    >
      <ul className="flex flex-col">
        {year.certifs.map((certif) => {
          const { mastered, total } = count(
            certif.lessons.map((lesson) => lesson.id),
            progress,
          );
          return (
            <li key={certif.slug}>
              <Link
                href={certifHref(year, certif.slug)}
                className="flex flex-col gap-2 rounded-card py-4 transition-colors duration-150 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="flex items-baseline justify-between gap-4">
                  <span className="min-w-0 truncate" title={certif.title}>
                    {shortCertifTitle(certif.title)}
                  </span>
                  <span className="shrink-0 text-sm text-muted tabular-nums">
                    {mastered} / {total} maîtrisés
                  </span>
                </span>
                <ThinLine value={mastered} total={total} />
              </Link>
            </li>
          );
        })}
      </ul>
    </EspaceSection>
  );
}
