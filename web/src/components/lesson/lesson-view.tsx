// Lesson reader. The markdown and section structure render on the server; folding, citations,
// table of contents, highlights and follow-up actions are small client islands. Calm reading:
// one ~640px column, serif headings, quiet citations, secondary actions as text links.

import Link from "next/link";

import type { Lesson } from "@/lib/content/types";

import { CITATION, ROLE_LABELS, STUDENT_ROLES } from "./citations";
import { FigureGallery } from "./figures";
import { FoldableSection } from "./foldable-section";
import { HighlightableBody, HighlightsLink } from "./highlights";
import { ReportErrorButton, StatusTracker } from "./lesson-actions";
import { LessonProvider } from "./lesson-context";
import { InlineMarkdown, LessonMarkdown, sectionFigures } from "./lesson-markdown";
import { parseLesson, plainTitle, type LessonSection } from "./parse";
import { headingClass, SectionHeading, sectionSpacing } from "./heading";
import { MarginToc, TocLink, type TocItem } from "./toc";

const ARTICLE_ID = "lecon";

const linkRow = "flex flex-wrap items-center gap-x-5 font-sans";

/** "{examen}": a quiet marker in muted ink under the heading. */
function HighYieldMarker() {
  return <p className="mt-1 font-sans text-sm text-highyield">Souvent à l&apos;examen</p>;
}

function SectionBlock({ section, lesson }: { section: LessonSection; lesson: Lesson }) {
  const title = <InlineMarkdown markdown={section.title.replace(CITATION, "").trim()} lesson={lesson} />;
  const marker = section.highYield ? <HighYieldMarker /> : null;
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
        badge={marker}
        reviewer={section.reviewer}
      >
        {content}
      </FoldableSection>
    );
  }

  return (
    <section id={section.id} data-section className={`scroll-mt-24 ${sectionSpacing(section.level)}`}>
      <SectionHeading level={section.level} className={headingClass(section.level)}>
        {title}
      </SectionHeading>
      {marker}
      {content}
    </section>
  );
}

function SourceList({ lesson }: { lesson: Lesson }) {
  if (lesson.sources.length === 0) return null;
  return (
    <section id="sources" aria-labelledby="sources-titre" className="scroll-mt-24 font-sans">
      <h2 id="sources-titre" className="text-xl">
        Sources du cours
      </h2>
      <ol className="mt-4 flex flex-col gap-4 text-base">
        {lesson.sources.map((source) => (
          <li key={source.key} className="flex gap-3">
            <span className="w-7 shrink-0 text-sm leading-6 text-muted">{source.key}</span>
            <span className="min-w-0">
              <span className="block leading-snug">{source.label}</span>
              <span className="block text-sm text-muted">
                {ROLE_LABELS[source.role] ?? source.role}
                {STUDENT_ROLES.has(source.role) && " · support étudiant, non officiel"}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </section>
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
  const sourceCount = lesson.sources.length;

  return (
    <LessonProvider lessonId={lesson.id} faculty={faculty} year={year}>
      {/* The column stays centred; on wide screens the table of contents hangs in the right margin. */}
      <div className="relative mx-auto w-full max-w-[40rem]">
        <article id={ARTICLE_ID} className="min-w-0">
          <header className="font-sans">
            <p className="text-sm text-muted">
              <Link
                href={`/${faculty}/${year}/${lesson.certif}`}
                className="rounded underline decoration-border underline-offset-4 hover:text-foreground hover:decoration-current focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {lesson.certifTitle}
              </Link>
              {lesson.module && <> · {lesson.module}</>}
            </p>
            <h1 className="mt-3 text-balance text-[2rem] leading-tight sm:text-[2.5rem]">{lesson.title}</h1>

            {lesson.status === "draft_unreviewed" && (
              <p role="note" className="mt-4 text-sm leading-relaxed text-muted">
                Brouillon non relu par un médecin, reconstruit à partir{" "}
                {sourceCount > 0 ? (
                  <a
                    href="#sources"
                    className="underline decoration-border underline-offset-4 hover:text-foreground hover:decoration-current"
                  >
                    {sourceCount > 1 ? `des ${sourceCount} documents du cours` : "du document du cours"}
                  </a>
                ) : (
                  "des documents du cours"
                )}
                .
              </p>
            )}

            <div className="mt-6 flex flex-col">
              <StatusTracker />
              <div className={linkRow}>
                <TocLink items={toc} className="xl:hidden" />
                <HighlightsLink />
                <ReportErrorButton />
              </div>
            </div>
          </header>

          <HighlightableBody className="lesson-prose mt-10 text-[1.0625rem] sm:text-[1.125rem]">
            <LessonMarkdown markdown={parsed.preface} lesson={lesson} />
            {parsed.sections.map((section) => (
              <SectionBlock key={section.id} section={section} lesson={lesson} />
            ))}
          </HighlightableBody>

          <footer className="mt-16 flex flex-col gap-12 border-t border-border pt-8">
            <div className="flex flex-col">
              <StatusTracker />
              <div className={linkRow}>
                <HighlightsLink />
                <ReportErrorButton />
              </div>
            </div>
            <SourceList lesson={lesson} />
          </footer>
        </article>

        <aside className="absolute inset-y-0 left-full ml-12 hidden w-52 xl:block" aria-label="Navigation du cours">
          <div className="sticky top-24 max-h-[calc(100vh-8rem)] overflow-y-auto pb-6 font-sans">
            <MarginToc items={toc} />
          </div>
        </aside>
      </div>
    </LessonProvider>
  );
}
