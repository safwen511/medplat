"use client";

import { ListTree } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState, type MouseEvent } from "react";

import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { PRESS } from "@/lib/motion";
import { cn } from "@/lib/utils";

export interface TocItem {
  id: string;
  title: string;
  highYield: boolean;
  reviewer: boolean;
  /** Sub-sections (H3). */
  children: TocItem[];
}

const ACTIVE_OFFSET = 140; // px below the top of the viewport (under the site header)

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

/** Scroll spy: the last section (H2 or H3) whose heading has passed under the header. */
function useActiveSection(items: TocItem[]) {
  const ids = useMemo(() => items.flatMap((item) => [item.id, ...item.children.map((child) => child.id)]), [items]);
  const [active, setActive] = useState<string | null>(null);
  useScrollFrame(() => {
    let current: string | null = null;
    for (const id of ids) {
      const element = document.getElementById(id);
      if (element && element.getBoundingClientRect().top <= ACTIVE_OFFSET) current = id;
    }
    setActive(current);
  });
  return active;
}

function jumpTo(id: string) {
  const target = document.getElementById(id);
  if (!target) return;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  target.scrollIntoView({ block: "start", behavior: reduced ? "auto" : "smooth" });
  history.replaceState(null, "", `#${id}`);
}

/** Nested outline: sections and their sub-sections, the current one lit. */
function Outline({
  items,
  active,
  onNavigate,
  dense = false,
}: {
  items: TocItem[];
  active: string | null;
  onNavigate?: (event: MouseEvent<HTMLAnchorElement>, id: string) => void;
  dense?: boolean;
}) {
  const link = (item: TocItem, sub: boolean) => {
    const current = active === item.id;
    const inside = !sub && item.children.some((child) => child.id === active);
    return (
      <a
        href={`#${item.id}`}
        onClick={onNavigate ? (event) => onNavigate(event, item.id) : undefined}
        aria-current={current ? "location" : undefined}
        className={cn(
          "relative flex items-baseline gap-2 rounded-control py-1.5 pr-2 leading-snug transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          sub ? "pl-4 text-[0.875rem]" : "pl-3 text-[0.9375rem] font-medium",
          dense ? "min-h-9" : "min-h-11",
          current || inside ? "text-foreground" : "text-muted hover:text-foreground",
          current && "bg-primary-soft text-primary",
        )}
      >
        {!sub && (
          <span
            aria-hidden
            className={cn(
              "absolute top-2 bottom-2 left-0 w-0.5 rounded-full transition-colors duration-150",
              current || inside ? "bg-primary" : "bg-transparent",
            )}
          />
        )}
        <span className="min-w-0 flex-1">
          {item.title}
          {item.highYield && <span className="sr-only"> (souvent à l&apos;examen)</span>}
        </span>
        {item.highYield && <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-highyield" />}
      </a>
    );
  };
  return (
    <ol className="flex flex-col gap-0.5">
      {items.map((item) => (
        <li key={item.id}>
          {link(item, false)}
          {item.children.length > 0 && (
            <ol className="ml-3 flex flex-col border-l border-border">
              {item.children.map((child) => (
                <li key={child.id}>{link(child, true)}</li>
              ))}
            </ol>
          )}
        </li>
      ))}
    </ol>
  );
}

/** "Plan du cours" at the top of the lesson: the whole outline, foldable. */
export function PlanBlock({ items }: { items: TocItem[] }) {
  const active = useActiveSection(items);
  const count = items.length + items.reduce((sum, item) => sum + item.children.length, 0);
  // Long lessons start folded: the floating "Plan" and the margin outline stay at hand. Kept in
  // state so the scroll spy's re-renders never undo the student's choice.
  const [open, setOpen] = useState(count <= 16);
  if (items.length === 0) return null;
  return (
    <details
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
      className="group mt-8 rounded-panel border border-border bg-surface/60 font-sans"
    >
      <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 px-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
        <span className="flex items-center gap-2.5 font-heading font-semibold">
          <ListTree className="size-4 text-primary" aria-hidden /> Plan du cours
        </span>
        <span className="text-sm text-muted">
          {count} parties · <span className="group-open:hidden">afficher</span>
          <span className="hidden group-open:inline">replier</span>
        </span>
      </summary>
      <nav aria-label="Plan du cours" className="border-t border-border px-3 py-3 sm:columns-2 sm:gap-6">
        <Outline items={items} active={active} dense />
      </nav>
    </details>
  );
}

/** Floating "Plan" button (screens without the margin outline): a sheet with the outline. */
export function PlanButton({ items }: { items: TocItem[] }) {
  const active = useActiveSection(items);
  const [open, setOpen] = useState(false);
  if (items.length === 0) return null;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <motion.button
          type="button"
          whileTap={PRESS}
          className="fixed right-4 bottom-[calc(1.25rem+env(safe-area-inset-bottom))] z-30 flex h-12 items-center gap-2 rounded-full border border-border-strong bg-background/85 px-4 font-medium shadow-depth-2 backdrop-blur-xl transition-shadow hover:shadow-glow focus-visible:shadow-glow focus-visible:outline-none xl:hidden print:hidden"
        >
          <ListTree className="size-4 text-primary" aria-hidden /> Plan
        </motion.button>
      </DialogTrigger>
      <DialogContent
        className="top-auto bottom-0 left-0 max-h-[80vh] w-full max-w-none translate-x-0 translate-y-0 overflow-y-auto rounded-b-none pb-[calc(1.5rem+env(safe-area-inset-bottom))] sm:top-1/2 sm:bottom-auto sm:left-1/2 sm:w-[calc(100%-2rem)] sm:max-w-lg sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-b-card"
        // Focus stays put: returning it to the button would scroll back to it.
        onCloseAutoFocus={(event) => event.preventDefault()}
      >
        <DialogTitle className="mb-3 flex items-center gap-2 font-heading">
          <ListTree className="size-4 text-primary" aria-hidden /> Plan du cours
        </DialogTitle>
        <nav aria-label="Plan du cours">
          <Outline
            items={items}
            active={active}
            onNavigate={(event, id) => {
              event.preventDefault();
              setOpen(false);
              // Scroll once the sheet has released the page.
              window.setTimeout(() => jumpTo(id), 50);
            }}
          />
        </nav>
      </DialogContent>
    </Dialog>
  );
}

/** Outline in the right margin on wide screens, sticky, with the current section lit. */
export function MarginToc({ items }: { items: TocItem[] }) {
  const active = useActiveSection(items);
  if (items.length === 0) return null;
  return (
    <nav aria-label="Sommaire du cours">
      <p className="eyebrow mb-3">Sommaire</p>
      <Outline items={items} active={active} dense />
    </nav>
  );
}
