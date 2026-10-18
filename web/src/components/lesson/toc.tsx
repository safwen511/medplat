"use client";

import { useEffect, useRef, useState, type MouseEvent } from "react";

import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

import { textLink } from "./lesson-actions";

export interface TocItem {
  id: string;
  title: string;
  highYield: boolean;
  reviewer: boolean;
}

const ACTIVE_OFFSET = 120; // px below the top of the viewport (under the site header)

function useScrollFrame(callback: () => void) {
  const saved = useRef(callback);
  useEffect(() => {
    saved.current = callback;
  });
  useEffect(() => {
    let frame = 0;
    const onScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => saved.current());
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);
}

function useActiveSection(items: TocItem[]) {
  const [active, setActive] = useState<string | null>(null);
  useScrollFrame(() => {
    let current: string | null = null;
    for (const item of items) {
      const element = document.getElementById(item.id);
      if (element && element.getBoundingClientRect().top <= ACTIVE_OFFSET) current = item.id;
    }
    setActive(current);
  });
  return active;
}

function TocList({
  items,
  active,
  onNavigate,
}: {
  items: TocItem[];
  active: string | null;
  onNavigate?: (event: MouseEvent<HTMLAnchorElement>, id: string) => void;
}) {
  return (
    <ol className="flex flex-col">
      {items.map((item) => (
        <li key={item.id}>
          <a
            href={`#${item.id}`}
            onClick={onNavigate ? (event) => onNavigate(event, item.id) : undefined}
            aria-current={active === item.id ? "location" : undefined}
            className={cn(
              "flex min-h-10 items-center rounded-card py-1.5 text-sm leading-snug transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active === item.id ? "text-foreground" : "text-muted hover:text-foreground",
            )}
          >
            <span className="min-w-0 flex-1">
              {item.title}
              {item.highYield && <span className="sr-only"> (souvent à l&apos;examen)</span>}
            </span>
          </a>
        </li>
      ))}
    </ol>
  );
}

/** Table of contents sitting quietly in the right margin on wide screens. */
export function MarginToc({ items }: { items: TocItem[] }) {
  const active = useActiveSection(items);
  if (items.length === 0) return null;
  return (
    <nav aria-label="Sommaire du cours">
      <p className="mb-2 text-sm text-muted">Sommaire</p>
      <TocList items={items} active={active} />
    </nav>
  );
}

/** "Sommaire" text link opening the table of contents (screens without a margin). */
export function TocLink({ items, className }: { items: TocItem[]; className?: string }) {
  const active = useActiveSection(items);
  const [open, setOpen] = useState(false);
  if (items.length === 0) return null;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button type="button" className={cn(textLink, "text-muted decoration-border hover:text-foreground hover:decoration-current", className)}>
          Sommaire
        </button>
      </DialogTrigger>
      <DialogContent
        className="max-h-[85vh] overflow-y-auto"
        // Focus stays put: returning it to the link would scroll back to the top of the lesson.
        onCloseAutoFocus={(event) => event.preventDefault()}
      >
        <DialogTitle className="mb-3">Sommaire</DialogTitle>
        <nav aria-label="Sommaire du cours">
          <TocList
            items={items}
            active={active}
            onNavigate={(event, id) => {
              event.preventDefault();
              setOpen(false);
              // Scroll once the dialog has released the page.
              window.setTimeout(() => {
                const target = document.getElementById(id);
                if (!target) return;
                const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
                target.scrollIntoView({ block: "start", behavior: reduced ? "auto" : "smooth" });
                history.replaceState(null, "", `#${id}`);
              }, 50);
            }}
          />
        </nav>
      </DialogContent>
    </Dialog>
  );
}
