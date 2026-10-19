"use client";

import { MoveHorizontal } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Columns whose body cells hold nothing but source chips ("Source" columns) are marked so they
 * hide together with the chips (setting "Afficher les sources").
 */
function markSourceColumns(container: HTMLElement) {
  const rows = [...container.querySelectorAll("tr")];
  const width = Math.max(0, ...rows.map((row) => row.children.length));
  for (let column = 0; column < width; column++) {
    const body = rows.filter((row) => row.parentElement?.tagName === "TBODY").map((row) => row.children[column]);
    const onlySources =
      body.length > 0 &&
      body.every((cell) => {
        if (!cell || !cell.querySelector("[data-citation-chip]")) return false;
        const clone = cell.cloneNode(true) as HTMLElement;
        clone.querySelectorAll("[data-citation-chip]").forEach((chip) => chip.remove());
        return !clone.textContent?.trim();
      });
    if (onlySources) for (const row of rows) row.children[column]?.setAttribute("data-sources-only", "");
  }
}

/**
 * Lesson table: rounded frame, scrolls sideways on small screens with fading edges where more
 * columns hide, and a "faire glisser" hint until the student scrolls.
 */
export function TableFrame({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ left: false, right: false, moved: false });

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const update = () =>
      setEdges((current) => ({
        left: element.scrollLeft > 4,
        right: element.scrollLeft + element.clientWidth < element.scrollWidth - 4,
        moved: current.moved || element.scrollLeft > 4,
      }));
    markSourceColumns(element);
    update();
    element.addEventListener("scroll", update, { passive: true });
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => {
      element.removeEventListener("scroll", update);
      observer.disconnect();
    };
  }, []);

  return (
    <div className="lesson-table relative my-8 font-sans">
      <div ref={ref} className="overflow-x-auto [scrollbar-width:thin]" tabIndex={0} aria-label="Tableau, défilable">
        {children}
      </div>
      <span aria-hidden className={cn("table-fade left-0 rotate-180", edges.left && "opacity-100")} />
      <span aria-hidden className={cn("table-fade right-0", edges.right && "opacity-100")} />
      {edges.right && !edges.moved && (
        <span
          aria-hidden
          className="pointer-events-none absolute right-3 bottom-3 inline-flex items-center gap-1 rounded-full bg-foreground/85 px-2.5 py-1 text-xs font-medium text-background"
        >
          <MoveHorizontal className="size-3.5" /> glisser
        </span>
      )}
    </div>
  );
}
