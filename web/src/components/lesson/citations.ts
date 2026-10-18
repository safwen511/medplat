// Citation markers such as "[S1 p.12]", "[S2 p.262-263; S3 p.1]" or "[S4 slide 5]".
// Pure and server-safe: used by the markdown renderer and the section galleries.

import type { Figure } from "@/lib/content/types";

export interface CitationRef {
  source: string; // "S1"
  unit: "page" | "slide";
  ranges: [number, number][]; // inclusive page or slide ranges
  text: string; // as written, e.g. "S2 p.262-263"
}

export const CITATION = /\[(S\d+\b[^[\]]*)\]/g;

const ITEM = /^(S\d+)\s*(?:,\s*)?(p{1,2}\.?|pages?|slides?|diapos?)\s*(.+)$/i;

function parseRanges(locator: string): [number, number][] {
  const ranges: [number, number][] = [];
  for (const part of locator.split(/[,/]|\bet\b/)) {
    const match = /^\s*(\d+)(?:\s*[-–]\s*(\d+))?\s*$/.exec(part);
    if (!match) continue;
    const from = Number(match[1]);
    const to = match[2] ? Number(match[2]) : from;
    ranges.push([Math.min(from, to), Math.max(from, to)]);
  }
  return ranges;
}

/** Parses the inside of a citation bracket ("S1 p.10; S2 p.270-271"). Unknown parts are kept as text. */
export function parseCitation(inner: string): CitationRef[] {
  return inner
    .split(";")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((text) => {
      const match = ITEM.exec(text);
      if (!match) {
        const source = /^S\d+/.exec(text)?.[0] ?? text;
        return { source, unit: "page", ranges: [], text };
      }
      const unit = /^s|^d/i.test(match[2]) ? "slide" : "page";
      return { source: match[1], unit, ranges: parseRanges(match[3]), text };
    });
}

export function formatLocator(ref: CitationRef) {
  if (ref.ranges.length === 0) return ref.text.replace(/^S\d+\s*/, "");
  const word = ref.unit === "slide" ? "diapositive" : "page";
  const plural = ref.ranges.length > 1 || ref.ranges[0][0] !== ref.ranges[0][1];
  const values = ref.ranges.map(([from, to]) => (from === to ? `${from}` : `${from}–${to}`)).join(", ");
  return `${word}${plural ? "s" : ""} ${values}`;
}

/** Figures extracted from the cited pages, without duplicates. */
export function figuresFor(refs: CitationRef[], figures: Figure[]): Figure[] {
  const seen = new Set<string>();
  const result: Figure[] = [];
  for (const ref of refs) {
    for (const figure of figures) {
      if (figure.source !== ref.source || seen.has(figure.src)) continue;
      if (ref.ranges.some(([from, to]) => figure.page >= from && figure.page <= to)) {
        seen.add(figure.src);
        result.push(figure);
      }
    }
  }
  return result;
}

/** Every citation in a block of markdown. */
export function citationsIn(markdown: string): CitationRef[] {
  return [...markdown.matchAll(CITATION)].flatMap((match) => parseCitation(match[1]));
}

// remark plugin ------------------------------------------------------------------------------

interface MdNode {
  type: string;
  value?: string;
  children?: MdNode[];
  data?: { hName?: string; hProperties?: Record<string, string> };
}

function split(node: MdNode): MdNode[] {
  const value = node.value ?? "";
  const parts: MdNode[] = [];
  let last = 0;
  for (const match of value.matchAll(CITATION)) {
    const index = match.index ?? 0;
    const before = value.slice(last, index);
    // The chip stays on the line of the word it follows (no orphan chip on its own line).
    const tail = /\S+\s*$/.exec(before)?.[0] ?? "";
    const head = before.slice(0, before.length - tail.length);
    if (head) parts.push({ type: "text", value: head });
    const chip: MdNode = {
      type: "citation",
      children: [{ type: "text", value: match[1] }],
      data: { hName: "cite", hProperties: { dataCitation: match[1] } },
    };
    parts.push(
      tail
        ? {
            type: "citationGroup",
            children: [{ type: "text", value: tail }, chip],
            data: { hName: "span", hProperties: { className: "whitespace-nowrap" } },
          }
        : chip,
    );
    last = index + match[0].length;
  }
  if (parts.length === 0) return [node];
  const rest = value.slice(last);
  if (rest) parts.push({ type: "text", value: rest });
  return parts;
}

function walk(node: MdNode) {
  if (!node.children) return;
  node.children = node.children.flatMap((child) => {
    if (child.type === "text") return split(child);
    walk(child);
    return [child];
  });
}

/** Turns citation text into `<cite data-citation="…">` elements rendered as chips. */
export function remarkCitations() {
  return (tree: MdNode) => walk(tree);
}

export const ROLE_LABELS: Record<string, string> = {
  official_slides: "Diapositives officielles",
  official_polycopie: "Polycopié officiel",
  student_summary: "Résumé étudiant",
  tips: "Astuces",
  tutorial: "Tutoriel",
  reference_book: "Ouvrage de référence",
};

/** Student material is allowed but flagged: it is not an official course document. */
export const STUDENT_ROLES = new Set(["student_summary", "tips", "tutorial"]);
