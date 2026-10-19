"use client";

import { Highlighter, Square, Underline } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";

import { useReaderSettings } from "@/lib/reader-settings";

import { REVEAL_EVENT } from "../foldable-section";
import { useLesson } from "../lesson-context";
import { anchorsOf, caretAt, rangeOf, units } from "./anchor";
import { newMarkId, onMarksChange, readLessonMarks, writeLessonMarks, type Mark, type MarkStyle } from "./store";
import { useTools } from "./tools";

export const BODY_SELECTOR = "[data-lesson-body]";
const STYLE_ICONS: Record<MarkStyle, typeof Highlighter> = { highlight: Highlighter, underline: Underline, box: Square };

function supportsHighlights() {
  return typeof CSS !== "undefined" && "highlights" in CSS && typeof globalThis.Highlight === "function";
}

/** Highlight and underline paint through the CSS Custom Highlight API (no DOM changes). */
function highlightCss(colors: string[]) {
  return colors
    .map(
      (color, index) =>
        `::highlight(mk-highlight-${index}){background-color:color-mix(in srgb,${color} 55%,transparent);color:inherit}` +
        `:root.dark ::highlight(mk-highlight-${index}){background-color:color-mix(in srgb,${color} 34%,transparent)}` +
        `::highlight(mk-underline-${index}){text-decoration-line:underline;text-decoration-color:${color};text-decoration-thickness:3px}`,
    )
    .join("");
}

/** Scrolls to a range, unfolding the sections around it first. */
export function revealAndScroll(range: Range) {
  let element = range.startContainer.parentElement;
  let folded = false;
  while (element) {
    const section = element.closest<HTMLElement>("[data-foldable]");
    if (!section) break;
    folded = true;
    section.dispatchEvent(new CustomEvent(REVEAL_EVENT));
    element = section.parentElement;
  }
  const target = range.startContainer.parentElement;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.setTimeout(
    () => target?.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" }),
    folded ? 300 : 0,
  );
}

interface Box {
  id: string;
  color: string;
  rects: { x: number; y: number; w: number; h: number }[];
}

interface Bubble {
  top: number;
  left: number;
}

/**
 * The lesson body with the student's marks. With the pen, a selection is marked at once with a
 * mouse or stylus; on touch screens (selection handles) a bubble confirms. The eraser removes the
 * mark under a tap. "Encadré" draws boxes over the text.
 */
export function MarkedBody({
  lessonId,
  title,
  href,
  children,
  className,
}: {
  lessonId: string;
  title: string;
  href: string;
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { tool, style, color, lens } = useTools();
  const { colors } = useReaderSettings();
  const { highlights: legacy, removeHighlight } = useLesson();
  const marks = useSyncExternalStore(onMarksChange, () => readMarksSnapshot(lessonId), () => EMPTY);
  const [boxes, setBoxes] = useState<Box[]>([]);
  const [bubble, setBubble] = useState<Bubble | null>(null);

  const save = useCallback(
    (next: Mark[]) => writeLessonMarks({ lessonId, title, href, marks: next }),
    [lessonId, title, href],
  );

  // One-time move of the old single-style highlights (stored as quotes) to marks.
  useEffect(() => {
    const body = ref.current;
    if (!body || legacy.length === 0) return;
    const added: Mark[] = [];
    for (const item of legacy) {
      const range = rangeOf(body, { quote: item.quote, start: { unit: "u-1", offset: 0 }, end: { unit: "u-1", offset: 0 } } as Mark);
      const anchors = range && anchorsOf(body, range);
      if (anchors) added.push({ id: newMarkId(), ...anchors, style: "highlight", color: 0, createdAt: item.createdAt });
      void removeHighlight(item.id);
    }
    if (added.length) save([...(readLessonMarks(lessonId)?.marks ?? []), ...added]);
  }, [legacy, removeHighlight, save, lessonId]);

  // Paint highlights/underlines; measure boxes.
  useLayoutEffect(() => {
    const body = ref.current;
    if (!body) return;
    const paint = () => {
      const list = units(body);
      const groups = new Map<string, Range[]>();
      const nextBoxes: Box[] = [];
      const origin = body.getBoundingClientRect();
      for (const mark of marks) {
        const range = rangeOf(body, mark, list);
        if (!range) continue;
        if (mark.style === "box") {
          const rects = [...range.getClientRects()]
            .filter((rect) => rect.width > 1 && rect.height > 1)
            .map((rect) => ({ x: rect.left - origin.left, y: rect.top - origin.top, w: rect.width, h: rect.height }));
          nextBoxes.push({ id: mark.id, color: colors[mark.color] ?? colors[0], rects });
        } else {
          const name = `mk-${mark.style}-${mark.color}`;
          groups.set(name, [...(groups.get(name) ?? []), range]);
        }
      }
      if (supportsHighlights()) {
        for (const name of [...CSS.highlights.keys()]) if (name.startsWith("mk-")) CSS.highlights.delete(name);
        for (const [name, ranges] of groups) CSS.highlights.set(name, new Highlight(...ranges));
      }
      setBoxes(nextBoxes);
    };
    paint();
    const observer = new ResizeObserver(() => paint());
    observer.observe(body);
    return () => {
      observer.disconnect();
      if (supportsHighlights()) for (const name of [...CSS.highlights.keys()]) if (name.startsWith("mk-")) CSS.highlights.delete(name);
    };
  }, [marks, colors]);

  const addFromSelection = useCallback(() => {
    const body = ref.current;
    const selection = window.getSelection();
    if (!body || !selection || selection.isCollapsed || selection.rangeCount === 0) return false;
    const range = selection.getRangeAt(0);
    if (!body.contains(range.commonAncestorContainer)) return false;
    const anchors = anchorsOf(body, range);
    if (!anchors) return false;
    save([...marks, { id: newMarkId(), ...anchors, style, color, createdAt: new Date().toISOString() }]);
    selection.removeAllRanges();
    return true;
  }, [marks, save, style, color]);

  // Mouse and stylus: mark on release. Touch: show the confirm bubble once the selection settles.
  useEffect(() => {
    if (tool !== "pen") return;
    let frame = 0;
    const onPointerUp = (event: PointerEvent) => {
      if (event.pointerType === "touch") return;
      window.setTimeout(addFromSelection, 0);
    };
    const onSelection = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const body = ref.current;
        const selection = window.getSelection();
        if (!body || !selection || selection.isCollapsed || selection.rangeCount === 0) return setBubble(null);
        const range = selection.getRangeAt(0);
        if (!body.contains(range.commonAncestorContainer) || !window.matchMedia("(pointer: coarse)").matches)
          return setBubble(null);
        const rect = range.getBoundingClientRect();
        const width = document.documentElement.clientWidth;
        setBubble({ top: rect.bottom + 14, left: Math.min(Math.max(rect.left + rect.width / 2, 72), width - 72) });
      });
    };
    document.addEventListener("pointerup", onPointerUp);
    document.addEventListener("selectionchange", onSelection);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("pointerup", onPointerUp);
      document.removeEventListener("selectionchange", onSelection);
    };
  }, [tool, addFromSelection]);

  // Eraser: remove the mark under the tap.
  const onClick = (event: React.MouseEvent) => {
    if (tool !== "eraser") return;
    const body = ref.current;
    if (!body) return;
    const caret = caretAt(event.clientX, event.clientY);
    const origin = body.getBoundingClientRect();
    const x = event.clientX - origin.left;
    const y = event.clientY - origin.top;
    const list = units(body);
    const hit = [...marks].reverse().find((mark) => {
      if (mark.style === "box") {
        const box = boxes.find((item) => item.id === mark.id);
        return box?.rects.some((rect) => x >= rect.x - 4 && x <= rect.x + rect.w + 4 && y >= rect.y - 4 && y <= rect.y + rect.h + 4);
      }
      const range = rangeOf(body, mark, list);
      return !!(caret && range && range.isPointInRange(caret.node, caret.offset));
    });
    if (hit) save(marks.filter((mark) => mark.id !== hit.id));
  };

  // Arriving with #mark=<id> (from "Mes surlignages" on another lesson): go to it.
  useEffect(() => {
    const id = new URLSearchParams(window.location.hash.slice(1)).get("mark");
    const body = ref.current;
    const mark = id ? marks.find((item) => item.id === id) : null;
    if (!body || !mark) return;
    const range = rangeOf(body, mark);
    if (range) revealAndScroll(range);
    history.replaceState(null, "", window.location.pathname);
  }, [marks]);

  const Icon = STYLE_ICONS[style];
  return (
    <div
      ref={ref}
      data-lesson-body
      data-tool={tool ?? "none"}
      data-lens={lens ? "on" : "off"}
      onClick={onClick}
      className={className}
      style={{ position: "relative" }}
    >
      <style>{highlightCss(colors)}</style>
      {children}
      <div aria-hidden className="pointer-events-none absolute inset-0" data-no-highlight>
        {boxes.flatMap((box) =>
          box.rects.map((rect, index) => (
            <span
              key={`${box.id}-${index}`}
              className="absolute rounded-[5px] border-2"
              style={{ left: rect.x - 3, top: rect.y - 2, width: rect.w + 6, height: rect.h + 4, borderColor: box.color }}
            />
          )),
        )}
      </div>
      {bubble && tool === "pen" && (
        <button
          type="button"
          data-no-highlight
          onPointerDown={(event) => event.preventDefault()}
          onClick={() => {
            addFromSelection();
            setBubble(null);
          }}
          style={{ top: bubble.top, left: bubble.left }}
          className="fixed z-50 inline-flex h-12 -translate-x-1/2 items-center gap-2 rounded-full bg-foreground px-4 font-sans text-sm font-medium text-background shadow-depth-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className="size-3 rounded-full" style={{ background: colors[color] }} />
          <Icon className="size-4" strokeWidth={1.75} aria-hidden />
          {style === "highlight" ? "Surligner" : style === "underline" ? "Souligner" : "Encadrer"}
        </button>
      )}
    </div>
  );
}

const EMPTY: Mark[] = [];
const snapshots = new Map<string, { raw: string | null; marks: Mark[] }>();

/** Stable snapshot for useSyncExternalStore (same array while the stored value is unchanged). */
function readMarksSnapshot(lessonId: string): Mark[] {
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(`medplat:v1:marks:${lessonId}`);
  } catch {
    raw = null;
  }
  const cached = snapshots.get(lessonId);
  if (cached && cached.raw === raw) return cached.marks;
  const marks = raw ? ((JSON.parse(raw) as { marks: Mark[] }).marks ?? EMPTY) : EMPTY;
  snapshots.set(lessonId, { raw, marks });
  return marks;
}
