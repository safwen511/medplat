"use client";

import { ChevronDown, Loader2 } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { LessonStatus } from "@/lib/progress/store";
import { cn } from "@/lib/utils";

import { useLesson } from "./lesson-context";

type Step = LessonStatus | "non_lu";

const STEPS: Step[] = ["non_lu", "lu", "revise_1", "revise_2", "maitrise"];

export const STATUS_LABELS: Record<Step, string> = {
  non_lu: "Non lu",
  lu: "Lu",
  revise_1: "Révisé 1×",
  revise_2: "Révisé 2×",
  maitrise: "Maîtrisé",
};

const NEXT_ACTION: Record<Step, { status: LessonStatus; label: string } | null> = {
  non_lu: { status: "lu", label: "Marquer comme lu" },
  lu: { status: "revise_1", label: "Marquer « Révisé 1× »" },
  revise_1: { status: "revise_2", label: "Marquer « Révisé 2× »" },
  revise_2: { status: "maitrise", label: "Marquer « Maîtrisé »" },
  maitrise: null,
};

/** Quiet text-link look shared by the lesson's secondary actions (48px tap height). */
export const textLink =
  "inline-flex min-h-12 items-center rounded-card text-sm underline underline-offset-4 transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/**
 * Fiche de suivi as one quiet line: the current step as a word that opens the native list
 * (Non lu → Lu → Révisé 1× → Révisé 2× → Maîtrisé, or back to « Non lu »), plus the next step
 * as a text link.
 */
export function StatusTracker({ className }: { className?: string }) {
  const { status, statusLoaded, setStatus } = useLesson();
  const selectId = useId();
  const step: Step = status ?? "non_lu";
  const next = NEXT_ACTION[step];

  return (
    <div className={cn("flex flex-wrap items-center gap-x-4 font-sans text-sm", className)} aria-live="polite">
      <span className="inline-flex items-center">
        <label htmlFor={selectId} className="text-muted">
          Fiche de suivi :
        </label>
        {/* The visible word sizes the control; the native list (transparent) sits on top of it. */}
        <span className="relative inline-flex h-12 items-center rounded-card pl-1.5 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring">
          <span
            aria-hidden
            className={cn(
              "inline-flex items-center gap-1 font-medium underline decoration-border underline-offset-4",
              step === "non_lu" ? "text-muted" : "text-foreground",
            )}
          >
            {STATUS_LABELS[step]}
            <ChevronDown className="size-3.5 text-muted" strokeWidth={1.5} />
          </span>
          <select
            id={selectId}
            value={step}
            disabled={!statusLoaded}
            onChange={(event) => {
              const value = event.target.value as Step;
              void setStatus(value === "non_lu" ? null : value);
            }}
            className="absolute inset-0 cursor-pointer appearance-none opacity-0 focus:outline-none disabled:cursor-default"
          >
            {STEPS.map((item) => (
              <option key={item} value={item}>
                {item === "non_lu" && status ? "Remettre à « Non lu »" : STATUS_LABELS[item]}
              </option>
            ))}
          </select>
        </span>
      </span>
      {statusLoaded && next && (
        <button
          type="button"
          onClick={() => setStatus(next.status)}
          className={cn(textLink, "text-primary decoration-primary/30 hover:decoration-current")}
        >
          {next.label}
        </button>
      )}
      {statusLoaded && status && (
        <button
          type="button"
          onClick={() => setStatus(null)}
          className={cn(textLink, "text-muted decoration-border hover:text-foreground hover:decoration-current")}
        >
          Remettre à « Non lu »
        </button>
      )}
    </div>
  );
}

/** "Signaler une erreur": a short free-text report sent to the content team. */
export function ReportErrorButton({ className }: { className?: string }) {
  const { reportError } = useLesson();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "failed">("idle");
  const fieldId = useId();
  const hintId = useId();

  const onOpenChange = (value: boolean) => {
    setOpen(value);
    if (!value) {
      setMessage("");
      setState("idle");
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (message.trim().length < 5) return;
    setState("sending");
    try {
      await reportError(message.trim());
      setState("sent");
    } catch {
      setState("failed");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <button
          type="button"
          className={cn(textLink, "text-muted decoration-border hover:text-foreground hover:decoration-current", className)}
        >
          Signaler une erreur
        </button>
      </DialogTrigger>
      <DialogContent>
        {state === "sent" ? (
          <div className="flex flex-col items-start gap-3">
            <DialogTitle>Merci pour ton signalement</DialogTitle>
            <DialogDescription>
              Il sera transmis à l&apos;équipe qui relit les cours. Chaque signalement aide à fiabiliser le
              contenu.
            </DialogDescription>
            <DialogClose asChild>
              <Button className="mt-2">Fermer</Button>
            </DialogClose>
          </div>
        ) : (
          <form onSubmit={submit} className="flex flex-col gap-3">
            <DialogTitle>Signaler une erreur</DialogTitle>
            <DialogDescription>
              Une valeur, une source ou une formulation te semble fausse ? Décris-la ici.
            </DialogDescription>
            <label htmlFor={fieldId} className="text-sm font-medium">
              Ton message
            </label>
            <textarea
              id={fieldId}
              aria-describedby={hintId}
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              rows={5}
              maxLength={2000}
              required
              className="w-full resize-y rounded-card border border-border bg-surface px-3 py-2 text-base placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="Section concernée, ce qui te semble faux, et la page du document original si tu l'as."
            />
            <p id={hintId} className="text-xs text-muted">
              Au moins 5 caractères. N&apos;indique pas d&apos;informations personnelles.
            </p>
            {state === "failed" && (
              <p className="text-sm text-muted" role="alert">
                L&apos;envoi a échoué. Réessaie dans un instant.
              </p>
            )}
            <div className="mt-1 flex justify-end gap-2">
              <DialogClose asChild>
                <Button type="button" variant="ghost">
                  Annuler
                </Button>
              </DialogClose>
              <Button type="submit" disabled={state === "sending" || message.trim().length < 5}>
                {state === "sending" && <Loader2 className="animate-spin" aria-hidden />}
                Envoyer
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
