"use client";

import { ArrowRight, LoaderCircle } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useActionState, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { redeemCode, type RedeemState } from "./actions";

const LENGTH = 14;

export function CodeForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState<RedeemState, FormData>(redeemCode, { error: null });
  const [value, setValue] = useState("");
  const reduce = useReducedMotion();
  const typed = value.replace(/[^a-z0-9]/gi, "").length;
  const complete = typed >= LENGTH;

  return (
    <form action={action} className="flex flex-col gap-4">
      <input type="hidden" name="suite" value={next} />
      <label htmlFor="code" className="flex items-baseline justify-between text-sm font-medium">
        Ton code d&apos;accès
        <span className={cn("numeral text-xs tabular-nums", complete ? "text-primary" : "text-subtle")}>
          {Math.min(typed, LENGTH)} / {LENGTH}
        </span>
      </label>
      <motion.div
        key={state.error ?? "ok"}
        animate={state.error && !reduce ? { x: [0, -8, 8, -5, 5, 0] } : { x: 0 }}
        transition={{ duration: 0.35 }}
        className="flex flex-col gap-2"
      >
        <input
          id="code"
          name="code"
          required
          value={value}
          onChange={(event) => setValue(event.target.value)}
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          inputMode="text"
          maxLength={24}
          placeholder="••••••••••••••"
          aria-invalid={state.error ? true : undefined}
          aria-describedby={state.error ? "code-error" : undefined}
          className={cn(
            "h-16 rounded-card border bg-background/60 px-4 text-center font-mono text-lg tracking-[0.2em] uppercase sm:text-xl sm:tracking-[0.28em] transition-[border-color,box-shadow] duration-200 placeholder:text-subtle/60 focus-visible:outline-none",
            state.error ? "border-wrong/60" : "border-border-strong focus-visible:border-primary/70 focus-visible:shadow-glow",
          )}
        />
        <span aria-hidden className="h-0.5 overflow-hidden rounded-full bg-surface-muted">
          <span
            className="block h-full origin-left rounded-full bg-primary transition-transform duration-300 ease-out"
            style={{ transform: `scaleX(${Math.min(typed, LENGTH) / LENGTH})` }}
          />
        </span>
      </motion.div>
      {state.error && (
        <p id="code-error" role="alert" className="text-sm text-wrong">
          {state.error}
        </p>
      )}
      <Button type="submit" size="lg" disabled={pending} className={cn("mt-2", complete && "shadow-glow")}>
        {pending ? (
          <>
            <LoaderCircle className="animate-spin" aria-hidden /> Vérification…
          </>
        ) : (
          <>
            Entrer <ArrowRight aria-hidden />
          </>
        )}
      </Button>
    </form>
  );
}
