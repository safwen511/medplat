"use client";

import { Highlighter, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

import { REVEAL_EVENT } from "./foldable-section";
import { textLink } from "./lesson-actions";
import { useLesson } from "./lesson-context";

const BODY_SELECTOR = "[data-lesson-body]";
const HIGHLIGHT_NAME = "lesson-highlight";
const MAX_QUOTE = 600;

// Locating quotes --------------------------------------------------------------------------------
// Whitespace is ignored on both sides: a selection across paragraphs or table cells yields line
// breaks that do not exist in the text nodes. Citation chips and lesson chrome are skipped.

interface TextIndex {
  text: string;
  nodes: Text[];
  offsets: number[];
}

function buildIndex(root: Element): TextIndex {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) =>
      node.parentElement?.closest("[data-no-highlight], [data-citation-chip], style")
        ? NodeFilter.FILTER_REJECT
        : NodeFilter.FILTER_ACCEPT,
  });
  const chars: string[] = [];
  const nodes: Text[] = [];
  const offsets: number[] = [];
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const value = node.nodeValue ?? "";
    for (let i = 0; i < value.length; i++) {
      if (/\s/.test(value[i])) continue;
      chars.push(value[i]);
      nodes.push(node as Text);
      offsets.push(i);
    }
  }
  return { text: chars.join(""), nodes, offsets };
}

function locate(index: TextIndex, quote: string): Range | null {
  const key = quote.replace(/\s+/g, "");
  if (!key) return null;
  const start = index.text.indexOf(key);
  if (start < 0) return null;
  const end = start + key.length - 1;
  const range = document.createRange();
  range.setStart(index.nodes[start], index.offsets[start]);
  range.setEnd(index.nodes[end], index.offsets[end] + 1);
  return range;
}

function lessonBody() {
  return document.querySelector(BODY_SELECTOR);
}

function supportsHighlights() {
  return typeof CSS !== "undefined" && "highlights" in CSS && typeof globalThis.Highlight === "function";
}

function revealAndScroll(range: Range) {
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

// Body ---------------------------------------------------------------------------------------------

interface Floating {
  top: number;
  left: number;
  quote: string;
}

/** Wraps the lesson body: paints saved highlights and offers "Surligner" on text selection. */
export function HighlightableBody({ children, className }: { children: ReactNode; className?: string }) {
  const { highlights, addHighlight } = useLesson();
  const ref = useRef<HTMLDivElement>(null);
  const [floating, setFloating] = useState<Floating | null>(null);

  // Paint saved highlights without touching the DOM (CSS Custom Highlight API).
  useEffect(() => {
    const root = ref.current;
    if (!root || !supportsHighlights()) return;
    const index = buildIndex(root);
    const ranges = highlights
      .map((item) => locate(index, item.quote))
      .filter((range): range is Range => !!range);
    CSS.highlights.set(HIGHLIGHT_NAME, new Highlight(...ranges));
    return () => {
      CSS.highlights.delete(HIGHLIGHT_NAME);
    };
  }, [highlights]);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      const root = ref.current;
      const selection = window.getSelection();
      if (!root || !selection || selection.isCollapsed || selection.rangeCount === 0) {
        setFloating(null);
        return;
      }
      const range = selection.getRangeAt(0);
      if (!root.contains(range.commonAncestorContainer)) {
        setFloating(null);
        return;
      }
      const quote = selection.toString().replace(/\s+/g, " ").trim();
      if (quote.length < 3) {
        setFloating(null);
        return;
      }
      const rect = range.getBoundingClientRect();
      const coarse = window.matchMedia("(pointer: coarse)").matches;
      // On touch screens the system menu sits above the selection: go below it.
      const top = coarse ? rect.bottom + 12 : rect.top - 44;
      const width = document.documentElement.clientWidth;
      const left = Math.min(Math.max(rect.left + rect.width / 2, 64), width - 64);
      setFloating({ top: Math.max(top, 64), left, quote });
    };
    const schedule = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(update);
    };
    document.addEventListener("selectionchange", schedule);
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("selectionchange", schedule);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
    };
  }, []);

  const save = async () => {
    if (!floating) return;
    const quote = floating.quote.slice(0, MAX_QUOTE);
    setFloating(null);
    window.getSelection()?.removeAllRanges();
    if (highlights.some((item) => item.quote.replace(/\s+/g, "") === quote.replace(/\s+/g, ""))) return;
    await addHighlight(quote);
  };

  return (
    <div ref={ref} data-lesson-body className={className}>
      <style>{`::highlight(${HIGHLIGHT_NAME}) { background-color: color-mix(in srgb, var(--highyield) 32%, transparent); color: inherit; }`}</style>
      {children}
      {floating && (
        <button
          type="button"
          data-no-highlight
          onPointerDown={(event) => event.preventDefault()}
          onClick={save}
          style={{ top: floating.top, left: floating.left }}
          className="fixed z-50 inline-flex h-12 -translate-x-1/2 items-center gap-2 rounded-card bg-foreground px-4 font-sans text-sm font-medium text-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Highlighter className="size-4" strokeWidth={1.5} aria-hidden />
          Surligner
        </button>
      )}
    </div>
  );
}

// Panel --------------------------------------------------------------------------------------------

export function HighlightsPanel({ className, onNavigate }: { className?: string; onNavigate?: () => void }) {
  const { highlights, removeHighlight } = useLesson();
  const [missing, setMissing] = useState<Set<string>>(new Set());

  useEffect(() => {
    const root = lessonBody();
    if (!root) return;
    const index = buildIndex(root);
    const next = new Set(highlights.filter((item) => !locate(index, item.quote)).map((item) => item.id));
    const frame = requestAnimationFrame(() => setMissing(next));
    return () => cancelAnimationFrame(frame);
  }, [highlights]);

  const goTo = useCallback(
    (quote: string) => {
      const root = lessonBody();
      const range = root && locate(buildIndex(root), quote);
      if (!range) return;
      onNavigate?.();
      // Let a closing dialog release the page first.
      window.setTimeout(() => revealAndScroll(range), onNavigate ? 50 : 0);
    },
    [onNavigate],
  );

  if (highlights.length === 0) {
    return (
      <p className={cn("font-sans text-base text-muted", className)}>
        Sélectionne un passage du cours, puis touche « Surligner » pour le retrouver ici.
      </p>
    );
  }

  return (
    <ul className={cn("flex flex-col divide-y divide-border font-sans", className)} data-no-highlight>
      {highlights.map((item) => (
        <li key={item.id} className="flex items-start gap-2 py-3">
          <button
            type="button"
            onClick={() => goTo(item.quote)}
            disabled={missing.has(item.id)}
            className="min-h-12 min-w-0 flex-1 rounded-card text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default"
            aria-label={`Aller au passage : ${item.quote}`}
          >
            <span className="line-clamp-3 text-base leading-snug text-foreground">{item.quote}</span>
            {missing.has(item.id) && (
              <span className="mt-1 block text-sm text-muted">Passage introuvable dans la version actuelle du cours.</span>
            )}
          </button>
          <button
            type="button"
            onClick={() => removeHighlight(item.id)}
            className="flex size-12 shrink-0 items-center justify-center rounded-card text-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Supprimer ce surlignage"
          >
            <Trash2 className="size-4" strokeWidth={1.5} aria-hidden />
          </button>
        </li>
      ))}
    </ul>
  );
}

/** "Mes surlignages" text link opening the list of saved passages. */
export function HighlightsLink({ className }: { className?: string }) {
  const { highlights } = useLesson();
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          className={cn(textLink, "text-muted decoration-border hover:text-foreground hover:decoration-current", className)}
        >
          Mes surlignages{highlights.length > 0 && ` (${highlights.length})`}
        </button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto" onCloseAutoFocus={(event) => event.preventDefault()}>
        <DialogTitle className="mb-2">Mes surlignages</DialogTitle>
        <DialogDescription className="sr-only">Passages surlignés de ce cours.</DialogDescription>
        <HighlightsPanel onNavigate={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  );
}
