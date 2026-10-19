"use client";

import { setExamDateBounds, validExamDate } from "@/lib/dates";
import { Check, X } from "lucide-react";
import { useTheme } from "next-themes";
import { useId, useState, type FormEvent, type ReactNode } from "react";

import { useMounted } from "@/components/layout/use-mounted";
import { announceProfile } from "@/components/layout/use-profile";
import { Button } from "@/components/ui/button";
import type { Profile } from "@/lib/progress/store";
import { cn } from "@/lib/utils";

import { EspaceSection } from "./section";

const YEARS = [
  { id: "dcem1", label: "DCEM1", detail: "3e année" },
  { id: "dcem2", label: "DCEM2", detail: "4e année" },
] as const;

const THEMES = [
  { id: "system", label: "Système" },
  { id: "light", label: "Clair" },
  { id: "dark", label: "Sombre" },
] as const;

export const GOAL_MIN = 5;
export const GOAL_MAX = 200;
const DEFAULT_GOAL = 20;

function clampGoal(value: number): number {
  return Number.isFinite(value) ? Math.min(GOAL_MAX, Math.max(GOAL_MIN, Math.round(value))) : DEFAULT_GOAL;
}

const fieldClass =
  "h-12 w-full rounded-card border border-border bg-background px-4 text-base font-normal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

function Choice({
  pressed,
  onClick,
  children,
}: {
  pressed: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={pressed}
      className={cn(
        "flex min-h-12 flex-1 items-center justify-center gap-2 rounded-card border px-3 py-2 text-[0.9375rem] transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        pressed ? "border-primary font-medium text-foreground" : "border-border text-muted hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

type SaveState = "idle" | "saving" | "saved" | "error";

export function SettingsForm({
  initial,
  fallbackName,
  onSave,
}: {
  initial: Profile | null;
  fallbackName: string | null;
  onSave: (profile: Profile) => Promise<void>;
}) {
  const id = useId();
  const { theme, setTheme } = useTheme();
  const mounted = useMounted();
  const [name, setName] = useState(initial?.displayName ?? fallbackName ?? "");
  const [year, setYear] = useState<Profile["year"]>(initial?.year ?? null);
  const [examDate, setExamDate] = useState(initial?.examDate ?? "");
  const [goal, setGoal] = useState(String(initial?.dailyGoal ?? DEFAULT_GOAL));
  const [state, setState] = useState<SaveState>("idle");

  const goalNumber = Number(goal);
  const goalValid = goal.trim() !== "" && goalNumber >= GOAL_MIN && goalNumber <= GOAL_MAX;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!year || !goalValid) return;
    const profile: Profile = {
      displayName: name.trim() || null,
      faculty: initial?.faculty || "sfax",
      year,
      examDate: validExamDate(examDate),
      onboarded: true,
      dailyGoal: clampGoal(goalNumber),
    };
    setState("saving");
    try {
      await onSave(profile);
      announceProfile(profile);
      setState("saved");
    } catch {
      setState("error");
    }
  };

  const touch = () => state !== "saving" && setState("idle");

  return (
    <EspaceSection id="reglages" title="Réglages">
      <div>
        <form onSubmit={submit} onChange={touch} className="flex flex-col gap-6">
          <label className="flex flex-col gap-2 text-[0.9375rem] font-medium">
            Nom affiché
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={60}
              autoComplete="nickname"
              placeholder="Ton prénom"
              className={fieldClass}
            />
          </label>

          <fieldset className="flex flex-col gap-1.5">
            <legend className="mb-2 text-[0.9375rem] font-medium">Année</legend>
            <div className="flex gap-2">
              {YEARS.map((item) => (
                <Choice
                  key={item.id}
                  pressed={year === item.id}
                  onClick={() => {
                    setYear(item.id);
                    touch();
                  }}
                >
                  <span>{item.label}</span>
                  <span className="text-sm text-muted">{item.detail}</span>
                </Choice>
              ))}
            </div>
            {!year && <p className="text-sm text-muted">Choisis ton année pour retrouver tes cours.</p>}
          </fieldset>

          <div className="grid gap-6 sm:grid-cols-2">
            <label className="flex flex-col gap-2 text-[0.9375rem] font-medium">
              Date du prochain certif
              <input
                type="date"
                ref={setExamDateBounds}
                value={examDate}
                onChange={(event) => setExamDate(event.target.value)}
                className={fieldClass}
              />
              <span className="text-sm font-normal text-muted">Facultatif : active le compte à rebours.</span>
            </label>
            <label className="flex flex-col gap-2 text-[0.9375rem] font-medium">
              Objectif du jour
              <span className="relative">
                <input
                  type="number"
                  inputMode="numeric"
                  min={GOAL_MIN}
                  max={GOAL_MAX}
                  step={5}
                  value={goal}
                  onChange={(event) => setGoal(event.target.value)}
                  aria-invalid={!goalValid}
                  aria-describedby={`${id}-goal`}
                  className={cn(
                    fieldClass,
                    "pr-36 tabular-nums [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none",
                    !goalValid && "border-wrong",
                  )}
                />
                <span className="pointer-events-none absolute inset-y-0 right-4 flex items-center text-sm font-normal text-muted">
                  questions / jour
                </span>
              </span>
              <span
                id={`${id}-goal`}
                className={cn("flex items-center gap-1 text-sm font-normal", goalValid ? "text-muted" : "text-wrong")}
              >
                {!goalValid && <X className="size-3" aria-hidden />}
                Entre {GOAL_MIN} et {GOAL_MAX}.
              </span>
            </label>
          </div>

          <fieldset className="flex flex-col gap-1.5">
            <legend className="mb-2 text-[0.9375rem] font-medium">Thème</legend>
            <div className="flex gap-2">
              {THEMES.map(({ id: themeId, label }) => (
                <Choice key={themeId} pressed={mounted && theme === themeId} onClick={() => setTheme(themeId)}>
                  {label}
                </Choice>
              ))}
            </div>
            <p className="text-sm text-muted">Appliqué tout de suite, sur cet appareil.</p>
          </fieldset>

          <div className="flex flex-wrap items-center gap-4">
            <Button type="submit" size="lg" disabled={!year || !goalValid || state === "saving"}>
              {state === "saving" ? "Enregistrement…" : "Enregistrer"}
            </Button>
            <p role="status" className="text-[0.9375rem]">
              {state === "saved" && (
                <span className="flex items-center gap-1.5 text-muted">
                  <Check className="size-4" aria-hidden />
                  Réglages enregistrés.
                </span>
              )}
              {state === "error" && (
                <span className="flex items-center gap-1.5">
                  <X className="size-4" aria-hidden />
                  L&apos;enregistrement a échoué. Réessaie.
                </span>
              )}
            </p>
          </div>
        </form>
      </div>
    </EspaceSection>
  );
}
