"use client";

import { ImageIcon } from "lucide-react";
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
        "group relative overflow-hidden rounded-lg border border-border bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      aria-label={`Agrandir la figure (${figureCaption(figure)})`}
    >
      <Image
        src={figure.src}
        alt=""
        width={figure.width}
        height={figure.height}
        sizes="160px"
        className="h-full w-full object-contain transition-transform duration-200 group-hover:scale-[1.03]"
      />
      <span className="absolute bottom-1 left-1 rounded bg-surface/90 px-1.5 py-0.5 font-sans text-[0.6875rem] leading-none text-muted">
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
            <div className="flex max-h-[75vh] justify-center overflow-auto rounded-lg bg-surface-muted">
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

/** Compact gallery of the figures cited in a section. */
export function FigureGallery({ figures }: { figures: LabeledFigure[] }) {
  const [open, setOpen] = useState<LabeledFigure | null>(null);
  if (figures.length === 0) return null;
  return (
    <div className="mt-4 rounded-card border border-border bg-surface p-3" data-no-highlight>
      <p className="mb-2 flex items-center gap-1.5 font-sans text-xs font-medium text-muted">
        <ImageIcon className="size-3.5" aria-hidden />
        Figures des pages citées ({figures.length})
      </p>
      <ul className="flex gap-2 overflow-x-auto pb-1">
        {figures.map((figure) => (
          <li key={figure.src} className="shrink-0">
            <FigureThumb figure={figure} onOpen={setOpen} className="h-24 w-32" />
          </li>
        ))}
      </ul>
      <FigureDialog figure={open} onClose={() => setOpen(null)} />
    </div>
  );
}
