"use client";

import { ImageIcon } from "lucide-react";
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type MouseEvent } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/utils";

import { FigureDialog, FigureThumb, type LabeledFigure } from "./figures";

export interface ChipRef {
  source: string; // "S1"
  label: string; // source title, or "Source inconnue"
  role: string | null; // French role label
  student: boolean;
  locator: string; // "page 12", "pages 262–263", "diapositive 5"
  short: string; // "p.12"
}

interface Position {
  top: number;
  left: number;
}

const GAP = 6;
const MARGIN = 8;
const HEADER = 64;

/** A discreet citation chip; hover, focus or tap shows the sources, pages and page figures. */
export function CitationChip({ refs, figures }: { refs: ChipRef[]; figures: LabeledFigure[] }) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<Position | null>(null);
  const [figure, setFigure] = useState<LabeledFigure | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const pinned = useRef(false);
  const timer = useRef<number | undefined>(undefined);
  const focusPanel = useRef(false);
  const panelId = useId();

  const schedule = useCallback((next: boolean, delay: number) => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setOpen(next), delay);
  }, []);

  const close = useCallback(() => {
    window.clearTimeout(timer.current);
    pinned.current = false;
    setOpen(false);
  }, []);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const trigger = triggerRef.current;
      const panel = panelRef.current;
      if (!trigger || !panel) return;
      const rect = trigger.getBoundingClientRect();
      const width = panel.offsetWidth;
      const height = panel.offsetHeight;
      const viewport = document.documentElement.clientWidth;
      const left = Math.min(
        Math.max(rect.left + rect.width / 2 - width / 2, MARGIN),
        Math.max(MARGIN, viewport - width - MARGIN),
      );
      let top = rect.bottom + GAP;
      if (top + height > window.innerHeight - MARGIN && rect.top - GAP - height > HEADER) {
        top = rect.top - GAP - height;
      }
      setPosition({ top, left });
    };
    place();
    window.addEventListener("scroll", place, { capture: true, passive: true });
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("scroll", place, { capture: true });
      window.removeEventListener("resize", place);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (focusPanel.current) {
      focusPanel.current = false;
      panelRef.current?.querySelector<HTMLElement>("button")?.focus();
    }
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (triggerRef.current?.contains(target) || panelRef.current?.contains(target)) return;
      close();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      close();
      triggerRef.current?.focus();
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, close]);

  const onClick = (event: MouseEvent<HTMLButtonElement>) => {
    window.clearTimeout(timer.current);
    if (open && pinned.current) {
      close();
      return;
    }
    pinned.current = true;
    // Keyboard activation (detail 0) moves focus to the figures so they can be opened.
    focusPanel.current = event.detail === 0 && figures.length > 0;
    setOpen(true);
    if (open && focusPanel.current) {
      focusPanel.current = false;
      panelRef.current?.querySelector<HTMLElement>("button")?.focus();
    }
  };

  const onLeave = (event: { pointerType: string }) => {
    if (event.pointerType === "mouse" && !pinned.current) schedule(false, 150);
  };

  const onBlur = (event: { relatedTarget: EventTarget | null }) => {
    const next = event.relatedTarget as Node | null;
    if (next && (triggerRef.current?.contains(next) || panelRef.current?.contains(next))) return;
    if (figure) return;
    close();
  };

  const label = refs.map((ref) => `${ref.source}, ${ref.label}, ${ref.locator}`).join(" ; ");

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        data-citation-chip
        aria-label={`Source : ${label}${figures.length ? ` (${figures.length} figure${figures.length > 1 ? "s" : ""})` : ""}`}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-haspopup="dialog"
        onClick={onClick}
        onPointerEnter={(event) => event.pointerType === "mouse" && schedule(true, 120)}
        onPointerLeave={onLeave}
        onFocus={(event) => {
          if (event.currentTarget.matches(":focus-visible")) setOpen(true);
        }}
        onBlur={onBlur}
        className={cn(
          "mx-0.5 inline-flex select-none items-center gap-1 whitespace-nowrap rounded-md border px-1.5 align-[0.1em] font-sans text-[0.6875rem] font-medium leading-[1.4] tabular-nums transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          open
            ? "border-primary/40 bg-primary-soft text-primary"
            : "border-border bg-surface-muted text-muted hover:border-primary/40 hover:text-primary",
        )}
      >
        {figures.length > 0 && <ImageIcon className="size-3" aria-hidden />}
        {refs.map((ref) => `${ref.source} ${ref.short}`.trim()).join(" · ")}
      </button>
      {open &&
        createPortal(
          <div
            ref={panelRef}
            id={panelId}
            role="dialog"
            aria-label="Source citée"
            onPointerEnter={() => window.clearTimeout(timer.current)}
            onPointerLeave={onLeave}
            onBlur={onBlur}
            style={{
              top: position?.top ?? 0,
              left: position?.left ?? 0,
              visibility: position ? "visible" : "hidden",
            }}
            className="fixed z-50 w-[min(20rem,calc(100vw-1rem))] rounded-card border border-border bg-surface p-3 font-sans text-sm shadow-lg"
          >
            <ul className="flex flex-col gap-2">
              {refs.map((ref, index) => (
                <li key={`${ref.source}-${index}`} className="flex gap-2">
                  <span className="mt-0.5 h-fit shrink-0 rounded bg-primary-soft px-1.5 text-xs font-semibold text-primary">
                    {ref.source}
                  </span>
                  <span className="min-w-0">
                    <span className="block leading-snug text-foreground">{ref.label}</span>
                    <span className="block text-xs text-muted">
                      {[ref.role, ref.locator].filter(Boolean).join(" · ")}
                      {ref.student && " · support étudiant"}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
            {figures.length > 0 && (
              <div className="mt-3 border-t border-border pt-3">
                <p className="mb-2 text-xs text-muted">Figures de ces pages</p>
                <div className="grid grid-cols-3 gap-2">
                  {figures.map((item) => (
                    <FigureThumb
                      key={item.src}
                      figure={item}
                      className="aspect-[4/3]"
                      onOpen={(selected) => {
                        setFigure(selected);
                        close();
                      }}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>,
          document.body,
        )}
      {figure && <FigureDialog figure={figure} onClose={() => setFigure(null)} />}
    </>
  );
}
