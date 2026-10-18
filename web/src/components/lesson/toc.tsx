"use client";

import { ChevronDown, ClipboardCheck, Flame, ListTree } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

export interface TocItem {
  id: string;
  title: string;
  highYield: boolean;
  reviewer: boolean;
}

const ACTIVE_OFFSET = 140; // px below the top of the viewport (site header + sommaire bar)

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

/** Thin bar under the site header showing how much of the lesson has been read. */
export function ReadingProgress({ targetId }: { targetId: string }) {
  const [progress, setProgress] = useState(0);
  useScrollFrame(() => {
    const element = document.getElementById(targetId);
    if (!element) return;
    const rect = element.getBoundingClientRect();
    const total = rect.height - window.innerHeight * 0.6;
    const read = ACTIVE_OFFSET - rect.top;
    setProgress(total > 0 ? Math.max(0, Math.min(1, read / total)) : 1);
  });
  return (
    <div
      role="progressbar"
      aria-label="Progression de lecture"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(progress * 100)}
      className="pointer-events-none fixed inset-x-0 top-14 z-40 h-0.5 bg-transparent"
    >
      <div
        className="h-full origin-left bg-primary transition-transform duration-150 ease-out"
        style={{ transform: `scaleX(${progress})` }}
      />
    </div>
  );
}

function ItemIcon({ item }: { item: TocItem }) {
  if (item.reviewer)
    return <ClipboardCheck className="mt-0.5 size-3.5 shrink-0 text-muted" aria-label="Note relecteur" />;
  if (item.highYield)
    return (
      <Flame className="mt-0.5 size-3.5 shrink-0 text-highyield" aria-label="Tombe souvent à l'examen" />
    );
  return null;
}

function TocList({
  items,
  active,
  onNavigate,
}: {
  items: TocItem[];
  active: string | null;
  onNavigate?: () => void;
}) {
  return (
    <ol className="flex flex-col">
      {items.map((item) => (
        <li key={item.id}>
          <a
            href={`#${item.id}`}
            onClick={onNavigate}
            aria-current={active === item.id ? "location" : undefined}
            className={cn(
              "flex gap-2 border-l-2 py-1.5 pl-3 pr-2 text-sm leading-snug transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active === item.id
                ? "border-primary font-medium text-primary"
                : "border-border text-muted hover:border-primary/40 hover:text-foreground",
            )}
          >
            <span className="min-w-0 flex-1">{item.title}</span>
            <ItemIcon item={item} />
          </a>
        </li>
      ))}
    </ol>
  );
}

export function DesktopToc({ items }: { items: TocItem[] }) {
  const active = useActiveSection(items);
  if (items.length === 0) return null;
  return (
    <nav aria-label="Sommaire du cours">
      <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
        <ListTree className="size-3.5" aria-hidden />
        Sommaire
      </p>
      <TocList items={items} active={active} />
    </nav>
  );
}

/** Compact sticky "Sommaire" dropdown for phones. */
export function MobileToc({ items, className }: { items: TocItem[]; className?: string }) {
  const active = useActiveSection(items);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = items.find((item) => item.id === active);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  if (items.length === 0) return null;
  return (
    <div
      ref={ref}
      data-no-highlight
      className={cn(
        "sticky top-14 z-30 -mx-4 border-b border-border bg-surface/95 px-4 backdrop-blur sm:-mx-6 sm:px-6 lg:hidden",
        className,
      )}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls="sommaire-mobile"
        onClick={() => setOpen((value) => !value)}
        className="flex h-11 w-full items-center gap-2 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ListTree className="size-4 shrink-0 text-primary" aria-hidden />
        <span className="font-medium">Sommaire</span>
        {current && <span className="min-w-0 flex-1 truncate text-muted">· {current.title}</span>}
        <ChevronDown
          className={cn("ml-auto size-4 shrink-0 text-muted transition-transform", open && "rotate-180")}
          aria-hidden
        />
      </button>
      <AnimatePresence>
        {open && (
          <motion.nav
            id="sommaire-mobile"
            aria-label="Sommaire du cours"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="absolute inset-x-0 top-full max-h-[65vh] overflow-y-auto border-b border-border bg-surface px-4 py-2 shadow-lg sm:px-6"
          >
            <TocList items={items} active={active} onNavigate={() => setOpen(false)} />
          </motion.nav>
        )}
      </AnimatePresence>
    </div>
  );
}
