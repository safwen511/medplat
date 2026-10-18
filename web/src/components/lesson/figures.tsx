"use client";

import Image from "next/image";
import { useState } from "react";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import type { Figure } from "@/lib/content/types";
import { cn } from "@/lib/utils";

export interface LabeledFigure extends Figure {
  sourceLabel: string; // "S1 · Diapositives officielles …"
  unit: "page" | "slide";
}

export function figureCaption(figure: LabeledFigure) {
  return `${figure.source}, ${figure.unit === "slide" ? "diapositive" : "page"} ${figure.page}`;
}

export function FigureThumb({
  figure,
  onOpen,
  className,
}: {
  figure: LabeledFigure;
  onOpen: (figure: LabeledFigure) => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onOpen(figure)}
      className={cn(
        "group flex flex-col gap-1.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-card",
        className,
      )}
      aria-label={`Agrandir la figure (${figureCaption(figure)})`}
    >
      <Image
        src={figure.src}
        alt=""
        width={figure.width}
        height={figure.height}
        sizes="(max-width: 640px) 50vw, 200px"
        className="min-h-0 w-full flex-1 rounded-card border border-border bg-surface object-contain"
      />
      <span className="font-sans text-sm leading-none text-muted group-hover:text-foreground">
        {figureCaption(figure)}
      </span>
    </button>
  );
}

export function FigureDialog({ figure, onClose }: { figure: LabeledFigure | null; onClose: () => void }) {
  return (
    <Dialog open={figure !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl p-4 sm:p-6">
        {figure && (
          <>
            <DialogTitle className="pr-8 text-base">Figure — {figureCaption(figure)}</DialogTitle>
            <DialogDescription className="mb-3">{figure.sourceLabel}</DialogDescription>
            <div className="flex max-h-[75vh] justify-center overflow-auto">
              <Image
                src={figure.src}
                alt={`Figure extraite de ${figure.sourceLabel}, ${figure.unit === "slide" ? "diapositive" : "page"} ${figure.page}`}
                width={figure.width}
                height={figure.height}
                sizes="(max-width: 896px) 100vw, 896px"
                className="h-auto max-h-[75vh] w-auto max-w-full object-contain"
              />
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** The figures cited in a section: a quiet row of images with their page, tap to enlarge. */
export function FigureGallery({ figures }: { figures: LabeledFigure[] }) {
  const [open, setOpen] = useState<LabeledFigure | null>(null);
  if (figures.length === 0) return null;
  return (
    <figure className="my-8" data-no-highlight>
      <ul className="flex gap-4 overflow-x-auto pb-2 [scrollbar-color:var(--border)_transparent] [scrollbar-width:thin]">
        {figures.map((figure) => (
          <li key={figure.src} className="shrink-0">
            <FigureThumb figure={figure} onOpen={setOpen} className="h-40 w-48" />
          </li>
        ))}
      </ul>
      <figcaption className="mt-2 font-sans text-sm text-muted">
        {figures.length > 1 ? "Figures des pages citées" : "Figure de la page citée"} · touche pour agrandir
      </figcaption>
      <FigureDialog figure={open} onClose={() => setOpen(null)} />
    </figure>
  );
}
