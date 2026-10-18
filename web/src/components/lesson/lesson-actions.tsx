"use client";

import { AlertCircle, Check, CheckCircle2, Flag, Loader2 } from "lucide-react";
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

const STEPS: { status: LessonStatus; label: string }[] = [
  { status: "lu", label: "Lu" },
  { status: "revise_1", label: "Révisé 1 fois" },
  { status: "revise_2", label: "Révisé 2 fois" },
  { status: "maitrise", label: "Maîtrisé" },
];

const NEXT_ACTION: Record<LessonStatus | "none", { status: LessonStatus; label: string } | null> = {
  none: { status: "lu", label: "Marquer comme lu" },
  lu: { status: "revise_1", label: "Révisé 1 fois" },
  revise_1: { status: "revise_2", label: "Révisé 2 fois" },
  revise_2: { status: "maitrise", label: "Maîtrisé" },
  maitrise: null,
};

function statusLabel(status: LessonStatus | null) {
  return STEPS.find((step) => step.status === status)?.label ?? "Pas encore lu";
}

/** Follow-up sheet: lu → révisé 1 fois → révisé 2 fois → maîtrisé. */
export function StatusTracker({
  variant = "card",
  className,
}: {
  variant?: "card" | "compact";
  className?: string;
}) {
  const { status, statusLoaded, setStatus } = useLesson();
  const next = NEXT_ACTION[status ?? "none"];
  const currentIndex = STEPS.findIndex((step) => step.status === status);

  if (variant === "compact") {
    return (
      <div className={cn("flex flex-wrap items-center gap-2", className)} aria-live="polite">
        {statusLoaded && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-muted px-2.5 py-1 text-xs font-medium text-muted">
            {status && <Check className="size-3 text-primary" aria-hidden />}
            {statusLabel(status)}
          </span>
        )}
        {statusLoaded && next && (
          <Button size="sm" variant={status ? "outline" : "primary"} onClick={() => setStatus(next.status)}>
            {next.label}
          </Button>
        )}
      </div>
    );
  }

  return (
    <section
      aria-labelledby="fiche-de-suivi"
      className={cn("rounded-card border border-border bg-surface p-4 font-sans sm:p-5", className)}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="fiche-de-suivi" className="text-base font-semibold">
          Fiche de suivi
        </h2>
        <p className="text-sm text-muted" aria-live="polite">
          Statut :{" "}
          <span className="font-medium text-foreground">{statusLoaded ? statusLabel(status) : "…"}</span>
        </p>
      </div>
      <ol className="mt-4 grid grid-cols-4 gap-1.5" aria-label="Étapes de révision">
        {STEPS.map((step, index) => {
          const done = index <= currentIndex;
          return (
            <li key={step.status}>
              <button
                type="button"
                aria-pressed={step.status === status}
                onClick={() => setStatus(step.status)}
                disabled={!statusLoaded}
                className={cn(
                  "flex w-full flex-col items-center gap-1.5 rounded-lg px-1 py-2 text-center text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  done ? "text-primary" : "text-muted hover:bg-surface-muted",
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-full rounded-full transition-colors",
                    done ? "bg-primary" : "bg-surface-muted",
                  )}
                  aria-hidden
                />
                <span className="flex items-center gap-1 leading-tight">
                  {done && <Check className="size-3 shrink-0" aria-hidden />}
                  {step.label}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
      <div className="mt-4">
        {next ? (
          <Button
            onClick={() => setStatus(next.status)}
            disabled={!statusLoaded}
            className="w-full sm:w-auto"
          >
            {next.label}
          </Button>
        ) : (
          <p className="flex items-center gap-2 text-sm font-medium text-primary">
            <CheckCircle2 className="size-4" aria-hidden />
            Cours maîtrisé. Pense à le revoir avant l&apos;examen.
          </p>
        )}
      </div>
    </section>
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
        <Button variant="ghost" size="sm" className={cn("text-muted", className)}>
          <Flag aria-hidden />
          Signaler une erreur
        </Button>
      </DialogTrigger>
      <DialogContent>
        {state === "sent" ? (
          <div className="flex flex-col items-start gap-3">
            <CheckCircle2 className="size-8 text-primary" aria-hidden />
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
              className="w-full resize-y rounded-card border border-border bg-surface px-3 py-2 text-sm placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="Section concernée, ce qui te semble faux, et la page du document original si tu l'as."
            />
            <p id={hintId} className="text-xs text-muted">
              Au moins 5 caractères. N&apos;indique pas d&apos;informations personnelles.
            </p>
            {state === "failed" && (
              <p className="flex items-center gap-1.5 text-sm text-wrong" role="alert">
                <AlertCircle className="size-4 shrink-0" aria-hidden />
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
