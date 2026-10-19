"use client";

import { Brain, Eraser, Highlighter, Languages, ListChecks, PenLine, Square, Underline, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type ReactNode } from "react";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { EASE_OUT, PRESS } from "@/lib/motion";
import { useReaderSettings } from "@/lib/reader-settings";
import { cn } from "@/lib/utils";

import { AllMarks } from "./marks-panel";
import type { MarkStyle } from "./store";
import { useCompact, useTools } from "./tools";

const PENS: { style: MarkStyle; label: string; icon: typeof Highlighter }[] = [
  { style: "highlight", label: "Surligneur", icon: Highlighter },
  { style: "underline", label: "Souligné", icon: Underline },
  { style: "box", label: "Encadré", icon: Square },
];

function ToolButton({
  label,
  active = false,
  onClick,
  children,
}: {
  label: string;
  active?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <motion.button
      type="button"
      whileTap={PRESS}
      aria-label={label}
      aria-pressed={active}
      title={label}
      onClick={onClick}
      className={cn(
        "flex size-10 items-center justify-center rounded-full transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active ? "bg-primary-soft text-primary shadow-[inset_0_0_0_1px_var(--primary)]" : "text-muted hover:bg-surface-muted hover:text-foreground",
      )}
    >
      {children}
    </motion.button>
  );
}

const Rule = ({ compact }: { compact: boolean }) =>
  compact ? null : <span aria-hidden className="my-1 h-px w-6 bg-border" />;

/**
 * Lesson tools: three pens, five colours, eraser, "Mes surlignages", and the lens and recall
 * switches. A vertical bar on the left (tablet, desktop); a small pill that opens it on phones.
 */
export function LessonToolbar({ lessonId, hasGlossary }: { lessonId: string; hasGlossary: boolean }) {
  const tools = useTools();
  const { colors } = useReaderSettings();
  const compact = useCompact();
  const [open, setOpen] = useState(false);
  const [marksOpen, setMarksOpen] = useState(false);
  const PenIcon = PENS.find((pen) => pen.style === tools.style)?.icon ?? PenLine;

  const bar = (
    <div
      role="toolbar"
      aria-label="Outils de lecture"
      aria-orientation="vertical"
      data-no-highlight
      className={cn(
        "rounded-[24px] border border-border-strong bg-background/90 p-1.5 shadow-depth-2 backdrop-blur-xl",
        compact ? "grid grid-cols-2 gap-1" : "flex flex-col items-center gap-0.5",
      )}
    >
      {PENS.map((pen) => (
        <ToolButton
          key={pen.style}
          label={pen.label}
          active={tools.tool === "pen" && tools.style === pen.style}
          onClick={() => tools.choosePen(pen.style)}
        >
          <pen.icon className="size-[1.1rem]" strokeWidth={1.8} />
        </ToolButton>
      ))}
      <Rule compact={compact} />
      {colors.map((color, index) => (
        <button
          key={index}
          type="button"
          aria-label={`Couleur ${index + 1}`}
          aria-pressed={tools.color === index}
          onClick={() => tools.chooseColor(index)}
          className="flex size-10 items-center justify-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span
            className={cn(
              "size-5 rounded-full transition-transform duration-150",
              tools.color === index ? "scale-110 ring-2 ring-foreground ring-offset-2 ring-offset-background" : "hover:scale-110",
            )}
            style={{ background: color }}
          />
        </button>
      ))}
      <Rule compact={compact} />
      <ToolButton
        label="Gomme"
        active={tools.tool === "eraser"}
        onClick={() => tools.setTool(tools.tool === "eraser" ? "pen" : "eraser")}
      >
        <Eraser className="size-[1.1rem]" strokeWidth={1.8} />
      </ToolButton>
      <ToolButton label="Mes surlignages" onClick={() => setMarksOpen(true)}>
        <ListChecks className="size-[1.1rem]" strokeWidth={1.8} />
      </ToolButton>
      <Rule compact={compact} />
      {hasGlossary && (
        <ToolButton label="Loupe (traduction en arabe)" active={tools.lens} onClick={() => tools.setLens(!tools.lens)}>
          <Languages className="size-[1.1rem]" strokeWidth={1.8} />
        </ToolButton>
      )}
      <ToolButton label="Mode rappel" active={tools.recall} onClick={() => tools.setRecall(!tools.recall)}>
        <Brain className="size-[1.1rem]" strokeWidth={1.8} />
      </ToolButton>
    </div>
  );

  return (
    <>
      <div
        className={cn(
          "fixed top-1/2 z-30 -translate-y-1/2 print:hidden",
          compact ? "left-2" : "left-3 xl:left-6",
        )}
      >
        {compact ? (
          <AnimatePresence mode="wait" initial={false}>
            {open ? (
              <motion.div
                key="open"
                initial={{ opacity: 0, x: -12, scale: 0.96 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: -12, scale: 0.96 }}
                transition={{ duration: 0.18, ease: EASE_OUT }}
                className="relative"
              >
                {bar}
                <button
                  type="button"
                  aria-label="Fermer les outils"
                  onClick={() => setOpen(false)}
                  className="absolute -top-3 -right-3 flex size-8 items-center justify-center rounded-full border border-border-strong bg-background text-muted shadow-depth-1"
                >
                  <X className="size-4" />
                </button>
              </motion.div>
            ) : (
              <motion.button
                key="pill"
                type="button"
                whileTap={PRESS}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.15 }}
                aria-label="Outils de lecture"
                onClick={() => setOpen(true)}
                className="flex h-14 w-9 flex-col items-center justify-center gap-1 rounded-full border border-border-strong bg-background/90 text-foreground shadow-depth-2 backdrop-blur-xl"
              >
                <PenIcon className="size-4" strokeWidth={1.8} aria-hidden />
                <span className="size-2.5 rounded-full" style={{ background: tools.tool === "pen" ? colors[tools.color] : "transparent", boxShadow: "0 0 0 1px var(--border-strong)" }} />
              </motion.button>
            )}
          </AnimatePresence>
        ) : (
          bar
        )}
      </div>

      <Dialog open={marksOpen} onOpenChange={setMarksOpen}>
        <DialogContent
          className="max-h-[85vh] overflow-y-auto"
          onCloseAutoFocus={(event) => event.preventDefault()}
        >
          <DialogTitle className="mb-1 font-heading">Mes surlignages</DialogTitle>
          <DialogDescription className="mb-4">Tous tes passages, cours par cours.</DialogDescription>
          <AllMarks currentLessonId={lessonId} onNavigate={() => setMarksOpen(false)} />
        </DialogContent>
      </Dialog>
    </>
  );
}
