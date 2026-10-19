"use client";

import type { Mark, Point } from "./store";

// Units are the lesson's text blocks, numbered in document order. A mark is anchored by unit and
// character offset; the quote double-checks the anchor and is searched again if the text moved.

export const UNIT_SELECTOR = "p, li, td, th, h2, h3, h4, blockquote, dt, dd";
const SKIP = "[data-citation-chip], [data-no-highlight], style, [data-recall-hint]";

export function units(body: Element): Element[] {
  return [...body.querySelectorAll(UNIT_SELECTOR)];
}

/** The unit's own text nodes: not those of nested units, not source chips. */
function ownTextNodes(unit: Element): Text[] {
  const nodes: Text[] = [];
  const walker = document.createTreeWalker(unit, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => {
      const parent = node.parentElement;
      if (!parent || parent.closest(SKIP)) return NodeFilter.FILTER_REJECT;
      return parent.closest(UNIT_SELECTOR) === unit ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
    },
  });
  for (let node = walker.nextNode(); node; node = walker.nextNode()) nodes.push(node as Text);
  return nodes;
}

/** DOM position of a unit offset. */
function resolve(list: Element[], point: Point): { node: Text; offset: number } | null {
  const unit = list[Number(point.unit.slice(1))];
  if (!unit) return null;
  let remaining = point.offset;
  const nodes = ownTextNodes(unit);
  for (const node of nodes) {
    const length = node.nodeValue?.length ?? 0;
    if (remaining <= length) return { node, offset: remaining };
    remaining -= length;
  }
  return null;
}

/** Unit offset of a DOM position (null outside the lesson's text). */
function pointOf(list: Element[], node: Node, offset: number): Point | null {
  const element = node.nodeType === Node.TEXT_NODE ? node.parentElement : (node as Element);
  const unit = element?.closest(UNIT_SELECTOR);
  const index = unit ? list.indexOf(unit) : -1;
  if (!unit || index < 0) return null;
  // Measure the unit's own text from its start up to the position.
  const before = document.createRange();
  before.setStart(unit, 0);
  before.setEnd(node, offset);
  let total = 0;
  for (const text of ownTextNodes(unit)) {
    if (text === node) return { unit: `u${index}`, offset: total + offset };
    if (!before.intersectsNode(text)) break;
    total += text.nodeValue?.length ?? 0;
  }
  return { unit: `u${index}`, offset: total };
}

/** The text between two anchors, as the marks store it (chips excluded, spaces collapsed). */
export function textOf(range: Range): string {
  const fragment = range.cloneContents();
  fragment.querySelectorAll(SKIP).forEach((element) => element.remove());
  return (fragment.textContent ?? "").replace(/\s+/g, " ").trim();
}

/** Anchors for a selection inside the lesson body. */
export function anchorsOf(body: Element, range: Range): { start: Point; end: Point; quote: string } | null {
  const list = units(body);
  const start = pointOf(list, range.startContainer, range.startOffset);
  const end = pointOf(list, range.endContainer, range.endOffset);
  const quote = textOf(range);
  if (!start || !end || quote.length < 2) return null;
  return { start, end, quote };
}

// Fallback: whitespace-insensitive search of the quote in the whole body.
function search(body: Element, quote: string): Range | null {
  const key = quote.replace(/\s+/g, "");
  if (!key) return null;
  const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => (node.parentElement?.closest(SKIP) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  const chars: string[] = [];
  const at: [Text, number][] = [];
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const value = node.nodeValue ?? "";
    for (let i = 0; i < value.length; i++) {
      if (/\s/.test(value[i])) continue;
      chars.push(value[i]);
      at.push([node as Text, i]);
    }
  }
  const start = chars.join("").indexOf(key);
  if (start < 0) return null;
  const [startNode, startOffset] = at[start];
  const [endNode, endOffset] = at[start + key.length - 1];
  const range = document.createRange();
  range.setStart(startNode, startOffset);
  range.setEnd(endNode, endOffset + 1);
  return range;
}

/** The DOM range of a mark: its anchors when the text still matches, else a search for the quote. */
export function rangeOf(body: Element, mark: Mark, list = units(body)): Range | null {
  const start = resolve(list, mark.start);
  const end = resolve(list, mark.end);
  if (start && end) {
    const range = document.createRange();
    try {
      range.setStart(start.node, start.offset);
      range.setEnd(end.node, end.offset);
      if (textOf(range).replace(/\s+/g, "") === mark.quote.replace(/\s+/g, "")) return range;
    } catch {
      // anchors out of order or stale: search instead
    }
  }
  return search(body, mark.quote);
}

/** The DOM position under a pointer (for the eraser). */
export function caretAt(x: number, y: number): { node: Node; offset: number } | null {
  const doc = document as Document & {
    caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null;
    caretRangeFromPoint?: (x: number, y: number) => Range | null;
  };
  const position = doc.caretPositionFromPoint?.(x, y);
  if (position) return { node: position.offsetNode, offset: position.offset };
  const range = doc.caretRangeFromPoint?.(x, y);
  return range ? { node: range.startContainer, offset: range.startOffset } : null;
}
