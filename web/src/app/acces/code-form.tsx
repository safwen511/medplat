"use client";

import { useActionState } from "react";

import { Button } from "@/components/ui/button";

import { redeemCode, type RedeemState } from "./actions";

export function CodeForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState<RedeemState, FormData>(redeemCode, { error: null });
  return (
    <form action={action} className="flex flex-col gap-4">
      <input type="hidden" name="suite" value={next} />
      <label className="flex flex-col gap-2 text-sm font-medium">
        Ton code d&apos;accès
        <input
          name="code"
          required
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          inputMode="text"
          maxLength={24}
          placeholder="14 caractères"
          aria-invalid={state.error ? true : undefined}
          aria-describedby={state.error ? "code-error" : undefined}
          className="h-14 rounded-card border border-border bg-surface px-4 font-mono text-lg tracking-[0.2em] uppercase focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        />
      </label>
      {state.error && (
        <p id="code-error" role="alert" className="text-sm text-wrong">
          {state.error}
        </p>
      )}
      <Button type="submit" size="lg" disabled={pending}>
        {pending ? "Vérification…" : "Entrer"}
      </Button>
    </form>
  );
}
