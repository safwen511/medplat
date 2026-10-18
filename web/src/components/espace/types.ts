import type { LessonProgress } from "@/lib/progress/store";

/** A slim year index for "Mon espace": only what the collection and the lesson links need. */
export interface EspaceYear {
  faculty: string;
  facultyLabel: string;
  year: string;
  yearLabel: string;
  certifs: EspaceCertif[];
  /** Lessons with a published page: the only ones that can carry highlights. */
  availableLessonIds: string[];
}

export interface EspaceCertif {
  slug: string;
  title: string;
  pole: string;
  lessons: { id: string; title: string }[];
}

/** Mastery steps collapsed to four ranks for the collection summary. */
export type Tier = "maitrise" | "revise" | "lu" | "non_lu";

export const TIERS: Tier[] = ["maitrise", "revise", "lu", "non_lu"];

export const TIER_LABELS: Record<Tier, string> = {
  non_lu: "Non lu",
  lu: "Lu",
  revise: "Révisé",
  maitrise: "Maîtrisé",
};

export function tierOf(progress: LessonProgress | undefined): Tier {
  switch (progress?.status) {
    case "maitrise":
      return "maitrise";
    case "revise_1":
    case "revise_2":
      return "revise";
    case "lu":
      return "lu";
    default:
      return "non_lu";
  }
}

export function lessonHref(year: Pick<EspaceYear, "faculty" | "year">, lessonId: string) {
  return `/${year.faculty}/${year.year}/lecon/${encodeURIComponent(lessonId)}`;
}

export function certifHref(year: Pick<EspaceYear, "faculty" | "year">, slug: string) {
  return `/${year.faculty}/${year.year}/${slug}`;
}

/** "Certificat intégré de pédiatrie" -> "Pédiatrie". */
export function shortCertifTitle(title: string): string {
  const short = title.replace(/^Certificat\s+(intégré\s+)?(de\s+l['’]|de\s+la\s+|des\s+|du\s+|de\s+|d['’])?/i, "");
  return short.charAt(0).toUpperCase() + short.slice(1);
}
