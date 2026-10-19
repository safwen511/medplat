// Server-rendered lesson markdown: GFM tables, quiet blocks and inline citations.

import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import type { Lesson } from "@/lib/content/types";

import { CitationChip, type ChipRef } from "./citation-chip";
import {
  CITATION,
  figuresFor,
  formatLocator,
  parseCitation,
  remarkCitations,
  STUDENT_ROLES,
} from "./citations";
import type { LabeledFigure } from "./figures";
import { TableFrame } from "./table-frame";

const remarkPlugins = [remarkGfm, remarkCitations];

/** Chip data for a citation's inner text, resolved against the lesson's sources and figures. */
export function resolveCitation(
  inner: string,
  lesson: Lesson,
): { refs: ChipRef[]; figures: LabeledFigure[] } {
  const parsed = parseCitation(inner);
  const refs = parsed.map((ref) => {
    const source = lesson.sources.find((item) => item.key === ref.source);
    return {
      source: ref.source,
      // The loader already reduced the label to the source's kind (no author names).
      label: source?.label ?? "Source non répertoriée",
      role: null,
      student: source ? STUDENT_ROLES.has(source.role) : false,
      locator: formatLocator(ref),
      short: ref.text.replace(/^S\d+\s*,?\s*/, ""),
    };
  });
  const figures = parsed.flatMap((ref) =>
    figuresFor([ref], lesson.figures).map((figure) => ({
      ...figure,
      unit: ref.unit,
      sourceLabel: `${figure.source} · ${lesson.sources.find((item) => item.key === figure.source)?.label ?? ""}`,
    })),
  );
  const unique = figures.filter(
    (figure, index) => figures.findIndex((item) => item.src === figure.src) === index,
  );
  return { refs, figures: unique };
}

function omitNode<P extends { node?: unknown }>(props: P): Omit<P, "node"> {
  const rest = { ...props };
  delete rest.node;
  return rest;
}

function components(lesson: Lesson): Components {
  return {
    cite: (props) => {
      const inner = String((props as Record<string, unknown>)["data-citation"] ?? "");
      const { refs, figures } = resolveCitation(inner, lesson);
      return <CitationChip refs={refs} figures={figures} />;
    },
    p: (props) => <p className="my-5" {...omitNode(props)} />,
    ul: (props) => (
      <ul className="my-5 list-disc space-y-2.5 pl-6 marker:text-primary/70" {...omitNode(props)} />
    ),
    ol: (props) => <ol className="my-5 list-decimal space-y-2.5 pl-6 marker:font-heading marker:text-primary/80" {...omitNode(props)} />,
    li: (props) => <li className="pl-1 [&>p]:my-1" {...omitNode(props)} />,
    blockquote: (props) => (
      <blockquote
        className="my-6 rounded-r-card border-l-2 border-primary/40 bg-surface/60 py-3 pr-4 pl-5 text-muted"
        {...omitNode(props)}
      />
    ),
    strong: (props) => <strong className="font-semibold text-foreground" {...omitNode(props)} />,
    a: ({ href, ...props }) => {
      const external = Boolean(href && /^https?:/.test(href));
      return (
        <a
          href={href}
          className="text-primary underline underline-offset-2 hover:text-primary-hover"
          {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
          {...omitNode(props)}
        />
      );
    },
    code: (props) => (
      <code className="rounded bg-surface-muted px-1 py-0.5 font-mono text-[0.85em]" {...omitNode(props)} />
    ),
    pre: (props) => (
      <pre className="my-4 overflow-x-auto rounded-lg bg-surface-muted p-3 text-sm" {...omitNode(props)} />
    ),
    hr: () => <hr className="my-12 border-border" />,
    table: (props) => (
      <TableFrame>
        <table {...omitNode(props)} />
      </TableFrame>
    ),
  };
}

export function LessonMarkdown({ markdown, lesson }: { markdown: string; lesson: Lesson }) {
  if (!markdown.trim()) return null;
  return (
    <Markdown remarkPlugins={remarkPlugins} components={components(lesson)}>
      {markdown}
    </Markdown>
  );
}

/** Inline markdown for headings (no wrapping paragraph). */
export function InlineMarkdown({ markdown, lesson }: { markdown: string; lesson: Lesson }) {
  return (
    <Markdown
      remarkPlugins={remarkPlugins}
      components={{ ...components(lesson), p: ({ children }) => <>{children}</> }}
    >
      {markdown}
    </Markdown>
  );
}

/** Figures from the pages cited in a block of markdown, without duplicates. */
export function sectionFigures(markdown: string, lesson: Lesson): LabeledFigure[] {
  if (lesson.figures.length === 0) return [];
  const result: LabeledFigure[] = [];
  for (const match of markdown.matchAll(CITATION)) {
    for (const figure of resolveCitation(match[1], lesson).figures) {
      if (!result.some((item) => item.src === figure.src)) result.push(figure);
    }
  }
  return result;
}
