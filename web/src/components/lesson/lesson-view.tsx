// Lesson reader. The markdown and section structure render on the server; folding, citations,
// table of contents, highlights and follow-up actions are small client islands. Calm reading:
// one ~640px column, serif headings, quiet citations, secondary actions as text links.

import { Clock, FileText, ListTree } from "lucide-react";
import Link from "next/link";

import { CertifEmblem } from "@/components/cards/certif-art";
import { certifTheme } from "@/components/cards/themes";

import type { Lesson } from "@/lib/content/types";

import { CITATION, STUDENT_ROLES } from "./citations";
import { FigureGallery } from "./figures";
import { FoldableSection } from "./foldable-section";
import { ReportErrorButton, StatusTracker } from "./lesson-actions";
import { LessonProvider } from "./lesson-context";
import { InlineMarkdown, LessonMarkdown, sectionFigures } from "./lesson-markdown";
import { parseLesson, plainTitle, type LessonSection } from "./parse";
import { GlossaryLens } from "./glossary-lens";
import { LessonGuard } from "./lesson-guard";
import { MarkedBody } from "./marks/marked-body";
import { LessonToolbar } from "./marks/toolbar";
import { ToolsProvider } from "./marks/tools";
import { ReaderSettingsButton } from "./reader-settings-panel";
import { ReadingProgress } from "./reading-progress";
import { headingClass, SectionHeading, sectionSpacing } from "./heading";
import { ReaderSurface } from "./reader-surface";
import { SourcesToggle } from "./sources-toggle";
import { MarginToc, PlanBlock, PlanButton, type TocItem } from "./toc";

const ARTICLE_ID = "lecon";

const linkRow = "flex flex-wrap items-center gap-x-5 font-sans";

/** About 200 words a minute for dense medical French, citations left out. */
function readingMinutes(markdown: string): number {
  const words = markdown.replace(CITATION, "").split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / 200));
}

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
              {STUDENT_ROLES.has(source.role) && (
                <span className="block text-sm text-muted">Support étudiant, non officiel</span>
              )}
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
      children: section.children
        .filter((child) => child.level === 3)
        .map((child) => ({
          id: child.id,
          title: plainTitle(child.title),
          highYield: child.highYield,
          reviewer: child.reviewer,
          children: [],
        })),
    }));
  const sourceCount = lesson.sources.length;

  return (
    <LessonProvider lessonId={lesson.id} faculty={faculty} year={year}>
      <ToolsProvider>
        <ReadingProgress />
        <LessonGuard articleId={ARTICLE_ID} />
        {/* The column stays centred; on wide screens the table of contents hangs in the right margin. */}
        <ReaderSurface className="relative mx-auto w-full">
          <article id={ARTICLE_ID} className="min-w-0">
            <header className="font-sans">
              <Link
                href={`/${faculty}/${year}/${lesson.certif}`}
                className="group inline-flex items-center gap-2.5 rounded-full py-1 pr-3 pl-1 text-sm text-muted transition-colors hover:bg-surface hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <CertifEmblem theme={certifTheme({ slug: lesson.certif, pole: "" })} className="size-7 rounded-full" />
                <span>
                  {lesson.certifTitle}
                  {lesson.module && <span className="text-subtle"> · {lesson.module}</span>}
                </span>
              </Link>
              <h1 className="rise-in mt-5 text-[2.125rem] leading-[1.1] sm:text-[2.75rem]">{lesson.title}</h1>
              <p className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
                <span className="inline-flex items-center gap-1.5">
                  <Clock className="size-4" strokeWidth={1.6} aria-hidden />≈ {readingMinutes(lesson.markdown)} min de lecture
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <FileText className="size-4" strokeWidth={1.6} aria-hidden />
                  {sourceCount} source{sourceCount > 1 ? "s" : ""}
                </span>
                {toc.length > 0 && (
                  <span className="inline-flex items-center gap-1.5">
                    <ListTree className="size-4" strokeWidth={1.6} aria-hidden />
                    {toc.length} parties
                  </span>
                )}
              </p>

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
                  <SourcesToggle />
                  <ReportErrorButton />
                </div>
              </div>
            </header>

            <PlanBlock items={toc} />

            <MarkedBody
              lessonId={lesson.id}
              title={lesson.title}
              href={`/${faculty}/${year}/lecon/${encodeURIComponent(lesson.id)}`}
              className="lesson-prose mt-10"
            >
              <LessonMarkdown markdown={parsed.preface} lesson={lesson} />
              {parsed.sections.map((section) => (
                <SectionBlock key={section.id} section={section} lesson={lesson} />
              ))}
            </MarkedBody>

            <footer className="mt-16 flex flex-col gap-12 border-t border-border pt-8">
              <div className="flex flex-col">
                <StatusTracker />
                <div className={linkRow}>
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
          <PlanButton items={toc} />
        </ReaderSurface>
        <LessonToolbar lessonId={lesson.id} hasGlossary={(lesson.glossary?.length ?? 0) > 0} />
      {lesson.glossary?.length ? <GlossaryLens entries={lesson.glossary} /> : null}
        <ReaderSettingsButton />
      </ToolsProvider>
    </LessonProvider>
  );
}
