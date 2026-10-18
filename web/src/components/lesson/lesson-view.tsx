// Lesson reader. The markdown and section structure render on the server; folding, citations,
// table of contents, highlights and follow-up actions are small client islands.

import { BookOpen, ChevronRight, Flame, ShieldAlert } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import type { Lesson } from "@/lib/content/types";

import { CITATION, ROLE_LABELS, STUDENT_ROLES } from "./citations";
import { FigureGallery } from "./figures";
import { FoldableSection } from "./foldable-section";
import { HighlightableBody, HighlightsPanel } from "./highlights";
import { ReportErrorButton, StatusTracker } from "./lesson-actions";
import { LessonProvider } from "./lesson-context";
import { InlineMarkdown, LessonMarkdown, sectionFigures } from "./lesson-markdown";
import { parseLesson, plainTitle, type LessonSection } from "./parse";
import { headingClass, SectionHeading, sectionSpacing } from "./heading";
import { DesktopToc, MobileToc, ReadingProgress, type TocItem } from "./toc";

const ARTICLE_ID = "lecon";

function HighYieldBadge() {
  return (
    <Badge tone="highyield" className="font-sans">
      <Flame aria-hidden />
      Tombe souvent à l&apos;examen
    </Badge>
  );
}

function SectionBlock({ section, lesson }: { section: LessonSection; lesson: Lesson }) {
  const title = <InlineMarkdown markdown={section.title.replace(CITATION, "").trim()} lesson={lesson} />;
  const badge = section.highYield ? <HighYieldBadge /> : null;
  const figures = sectionFigures(section.body, lesson);
  const content = (
    <>
      <LessonMarkdown markdown={section.body} lesson={lesson} />
      {figures.length > 0 && <FigureGallery figures={figures} />}
      {section.children.map((child) => (
        <SectionBlock key={child.id} section={child} lesson={lesson} />
      ))}
    </>
  );

  if (section.folded) {
    return (
      <FoldableSection
        id={section.id}
        level={section.level}
        title={title}
        badge={badge}
        reviewer={section.reviewer}
      >
        {content}
      </FoldableSection>
    );
  }

  return (
    <section id={section.id} data-section className={`scroll-mt-28 ${sectionSpacing(section.level)}`}>
      <SectionHeading level={section.level} className={headingClass(section.level)}>
        {title}
      </SectionHeading>
      {badge && <div className="mt-2">{badge}</div>}
      {content}
    </section>
  );
}

function SourceList({ lesson }: { lesson: Lesson }) {
  if (lesson.sources.length === 0) return null;
  return (
    <details className="group mt-4 rounded-card border border-border bg-surface">
      <summary className="flex cursor-pointer list-none items-center gap-2 rounded-card px-4 py-2.5 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
        <BookOpen className="size-4 text-primary" aria-hidden />
        Sources du cours ({lesson.sources.length})
        <ChevronRight
          className="ml-auto size-4 text-muted transition-transform group-open:rotate-90"
          aria-hidden
        />
      </summary>
      <ul className="flex flex-col gap-2.5 border-t border-border px-4 py-3 text-sm">
        {lesson.sources.map((source) => (
          <li key={source.key} className="flex gap-2.5">
            <span className="mt-0.5 h-fit shrink-0 rounded bg-primary-soft px-1.5 text-xs font-semibold text-primary">
              {source.key}
            </span>
            <span className="min-w-0">
              <span className="block leading-snug">{source.label}</span>
              <span className="block text-xs text-muted">
                {ROLE_LABELS[source.role] ?? source.role}
                {STUDENT_ROLES.has(source.role) && " · support étudiant, non officiel"}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}

export function LessonView({ lesson, faculty, year }: { lesson: Lesson; faculty: string; year: string }) {
  const parsed = parseLesson(lesson.markdown);
  const toc: TocItem[] = parsed.sections
    .filter((section) => section.level <= 2)
    .map((section) => ({
      id: section.id,
      title: plainTitle(section.title),
      highYield: section.highYield,
      reviewer: section.reviewer,
    }));

  return (
    <LessonProvider lessonId={lesson.id} faculty={faculty} year={year}>
      <ReadingProgress targetId={ARTICLE_ID} />
      <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_15rem] lg:gap-12 xl:grid-cols-[minmax(0,1fr)_17rem]">
        <article id={ARTICLE_ID} className="mx-auto w-full min-w-0 max-w-3xl lg:mx-0">
          <header className="font-sans">
            <nav aria-label="Fil d'Ariane">
              <ol className="flex flex-wrap items-center gap-1 text-sm text-muted">
                <li>
                  <Link
                    href={`/${faculty}/${year}/${lesson.certif}`}
                    className="rounded hover:text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {lesson.certifTitle}
                  </Link>
                </li>
                {lesson.module && (
                  <>
                    <li aria-hidden>
                      <ChevronRight className="size-3.5" />
                    </li>
                    <li>{lesson.module}</li>
                  </>
                )}
              </ol>
            </nav>
            <h1 className="mt-2 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
              {lesson.title}
            </h1>

            {lesson.status === "draft_unreviewed" && (
              <div
                role="note"
                className="mt-4 flex gap-3 rounded-card border border-border bg-surface-muted px-4 py-3 text-sm"
              >
                <ShieldAlert className="mt-0.5 size-4 shrink-0 text-highyield" aria-hidden />
                <p className="leading-snug">
                  <span className="font-semibold">Brouillon — non relu par un médecin.</span>{" "}
                  <span className="text-muted">
                    Reconstruit uniquement à partir des documents du cours ; chaque passage renvoie à sa
                    source. En cas de doute, vérifie sur le document original.
                  </span>
                </p>
              </div>
            )}

            <SourceList lesson={lesson} />

            <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
              <StatusTracker variant="compact" />
              <ReportErrorButton />
            </div>
          </header>

          <MobileToc items={toc} className="mt-4" />

          <HighlightableBody className="lesson-prose mt-6">
            <LessonMarkdown markdown={parsed.preface} lesson={lesson} />
            {parsed.sections.map((section) => (
              <SectionBlock key={section.id} section={section} lesson={lesson} />
            ))}
          </HighlightableBody>

          <footer className="mt-12 flex flex-col gap-6">
            <StatusTracker />
            <HighlightsPanel className="lg:hidden" />
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4 font-sans text-sm text-muted">
              <span>Une erreur dans ce cours ?</span>
              <ReportErrorButton />
            </div>
          </footer>
        </article>

        <aside className="hidden lg:block" aria-label="Navigation du cours">
          <div className="sticky top-20 flex max-h-[calc(100vh-6rem)] flex-col gap-8 overflow-y-auto pb-6 pr-1 font-sans">
            <DesktopToc items={toc} />
            <HighlightsPanel />
          </div>
        </aside>
      </div>
    </LessonProvider>
  );
}
