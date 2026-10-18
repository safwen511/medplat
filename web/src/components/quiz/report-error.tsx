"use client";

import { Check, Flag } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useProgress } from "@/lib/progress/provider";

/** "Signaler une erreur" link + dialog; the report goes to the medical reviewers' queue. */
export function ReportError({ lessonId, questionId }: { lessonId: string; questionId: string }) {
  const { store } = useProgress();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "failed">("idle");

  const send = async () => {
    setState("sending");
    try {
      await store.reportError(lessonId, questionId, message.trim());
      setState("sent");
      setMessage("");
    } catch {
      setState("failed");
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setState("idle");
      }}
    >
      <DialogTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded text-xs text-muted underline-offset-4 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Flag className="size-3" aria-hidden />
          Signaler une erreur
        </button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Signaler une erreur</DialogTitle>
        <DialogDescription className="mt-1">
          Énoncé, réponse ou explication qui te semble faux ? Décris le problème : il sera transmis au relecteur
          médical.
        </DialogDescription>
        {state === "sent" ? (
          <div className="mt-5 flex flex-col gap-4">
            <p className="flex items-center gap-2 rounded-card bg-correct-soft px-4 py-3 text-sm">
              <Check className="size-4 text-correct" aria-hidden />
              Merci, ton signalement a été enregistré.
            </p>
            <Button variant="secondary" className="self-end" onClick={() => setOpen(false)}>
              Fermer
            </Button>
          </div>
        ) : (
          <form
            className="mt-4 flex flex-col gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              if (message.trim()) void send();
            }}
          >
            <label htmlFor={`report-${questionId}`} className="sr-only">
              Description du problème
            </label>
            <textarea
              id={`report-${questionId}`}
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              rows={4}
              maxLength={2000}
              placeholder="Ex. : la proposition C me semble contredire le cours, page…"
              className="w-full resize-y rounded-card border border-border bg-surface p-3 text-sm focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            {state === "failed" && (
              <p className="text-xs text-muted">L&apos;envoi a échoué. Réessaie dans un instant.</p>
            )}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                Annuler
              </Button>
              <Button type="submit" disabled={!message.trim() || state === "sending"}>
                {state === "sending" ? "Envoi…" : "Envoyer"}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
