"use client";

import { BookOpen } from "lucide-react";
import Link from "next/link";
import { createContext, useContext, type ReactNode } from "react";

import { CITATION, parseCitation } from "@/components/lesson/citations";

export interface CourseLink {
  title: string;
  href: string;
}

const Context = createContext<Record<string, CourseLink>>({});

/** Lesson titles and links for the "Voir le cours" line under explanations. */
export function CourseLinksProvider({ links, children }: { links: Record<string, CourseLink>; children: ReactNode }) {
  return <Context.Provider value={links}>{children}</Context.Provider>;
}

/** The explanation without its raw citation codes ("[S1 p.6]"). */
export function cleanExplanation(text: string): string {
  return text
    .replace(new RegExp(`\\s*${CITATION.source}`, "g"), "")
    .replace(/\s+([.,;:!?)])/g, "$1")
    .replace(/\(\s*\)/g, "")
    .trim();
}

/** Pages of the first cited source, e.g. "p. 34, 36" or "diapo 5". */
function pagesOf(citations: string): string | null {
  const refs = [...citations.matchAll(CITATION)].flatMap((match) => parseCitation(match[1]));
  const first = refs.find((ref) => ref.ranges.length > 0);
  if (!first) return null;
  const values = new Set<string>();
  for (const ref of refs)
    if (ref.source === first.source && ref.unit === first.unit)
      for (const [from, to] of ref.ranges) values.add(from === to ? `${from}` : `${from}–${to}`);
  return `${first.unit === "slide" ? "diapo" : "p."} ${[...values].join(", ")}`;
}

/** "Voir le cours : <titre>, p. 6", linking to the course the question comes from. */
export function CourseRef({ lessonId, citations }: { lessonId: string; citations: string }) {
  const course = useContext(Context)[lessonId];
  const pages = pagesOf(citations);
  if (!course) return pages ? <p className="text-sm text-muted">Voir le cours, {pages}</p> : null;
  return (
    <p className="text-sm text-muted">
      <Link
        href={course.href}
        className="inline-flex min-h-12 items-center gap-2 rounded-control underline-offset-4 hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <BookOpen className="size-4 shrink-0" aria-hidden />
        <span>
          Voir le cours : <span className="text-foreground">{course.title}</span>
          {pages && `, ${pages}`}
        </span>
      </Link>
    </p>
  );
}
