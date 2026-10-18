import type { LessonStatus } from "@/lib/progress/store";

/** Mastery tier of a lesson card: "non_lu" is the absence of a follow-up record. */
export type Tier = LessonStatus | "non_lu";

export const TIERS: Tier[] = ["non_lu", "lu", "revise_1", "revise_2", "maitrise"];

export const TIER_LABELS: Record<Tier, string> = {
  non_lu: "Non lu",
  lu: "Lu",
  revise_1: "Révisé 1×",
  revise_2: "Révisé 2×",
  maitrise: "Maîtrisé",
};

export function tierOf(status: LessonStatus | null | undefined): Tier {
  return status ?? "non_lu";
}

/** The status to save for a tier; null means "back to Non lu" (clear the record). */
export function statusOf(tier: Tier): LessonStatus | null {
  return tier === "non_lu" ? null : tier;
}

export function countTiers(statuses: (LessonStatus | null | undefined)[]): Record<Tier, number> {
  const counts: Record<Tier, number> = { non_lu: 0, lu: 0, revise_1: 0, revise_2: 0, maitrise: 0 };
  for (const status of statuses) counts[tierOf(status)]++;
  return counts;
}
