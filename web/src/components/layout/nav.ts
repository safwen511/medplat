import { BookOpen, UserRound, Users, type LucideIcon } from "lucide-react";

import type { Profile } from "@/lib/progress/store";

export type SectionId = "etudier" | "espace" | "connecter";

export interface Section {
  id: SectionId;
  label: string;
  href: string;
  icon: LucideIcon;
  soon?: boolean;
}

export interface SubLink {
  label: string;
  href: string;
  active: boolean;
}

/** Study links point to the student's year; without a year yet, to the onboarding. */
export function studyBase(profile: Profile | null): string | null {
  return profile?.year ? `/${profile.faculty || "sfax"}/${profile.year}` : null;
}

export function sections(profile: Profile | null): Section[] {
  return [
    { id: "etudier", label: "Étudier", href: studyBase(profile) ?? "/onboarding", icon: BookOpen },
    { id: "espace", label: "Mon espace", href: "/espace", icon: UserRound },
    { id: "connecter", label: "Connecter", href: "/connecter", icon: Users, soon: true },
  ];
}

const YEAR_ROUTE = /^\/[^/]+\/dcem\d(\/|$)/;

/** Which primary section a path belongs to. The statistics page lives with "Mon espace". */
export function activeSection(pathname: string): SectionId | null {
  if (pathname.startsWith("/espace")) return "espace";
  if (pathname.startsWith("/connecter")) return "connecter";
  if (YEAR_ROUTE.test(pathname)) return pathname.split("/")[3] === "progression" ? "espace" : "etudier";
  return null;
}

/** Sub-links of "Étudier", shown under the header on study pages (not while reading a lesson). */
export function studyLinks(base: string, pathname: string, hash: string): SubLink[] | null {
  if (!pathname.startsWith(base) || activeSection(pathname) !== "etudier") return null;
  const rest = pathname.slice(base.length);
  if (rest.startsWith("/lecon/")) return null;
  const quiz = rest === "/quiz";
  return [
    { label: "Mes certifs", href: base, active: !quiz },
    { label: "Quiz", href: `${base}/quiz`, active: quiz && hash !== "#mini-jeux" },
    { label: "Mini-jeux", href: `${base}/quiz#mini-jeux`, active: quiz && hash === "#mini-jeux" },
  ];
}
