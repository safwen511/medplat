"use client";

import { ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useProgress } from "@/lib/progress/provider";
import type { Profile } from "@/lib/progress/store";
import { cn } from "@/lib/utils";

const YEARS = [
  { id: "dcem1", label: "DCEM1", detail: "3e année" },
  { id: "dcem2", label: "DCEM2", detail: "4e année" },
] as const;

type Step = "annee" | "date";

/** Two short steps, one choice per screen: the year, then (optionally) the next certif's date. */
export default function Onboarding() {
  const { store, user } = useProgress();
  const router = useRouter();
  const [step, setStep] = useState<Step>("annee");
  const [saving, setSaving] = useState(false);
  const [profile, setProfile] = useState<Profile>({
    displayName: null,
    faculty: "sfax",
    year: null,
    examDate: null,
    onboarded: false,
  });

  useEffect(() => {
    store.profile().then((saved) => saved && setProfile(saved));
  }, [store]);

  const chooseYear = (year: Profile["year"]) => {
    setProfile({ ...profile, year });
    setStep("date");
  };

  const save = async () => {
    if (!profile.year) return;
    setSaving(true);
    try {
      await store.saveProfile({
        ...profile,
        displayName: profile.displayName ?? user?.user_metadata?.name ?? null,
        onboarded: true,
      });
      router.push(`/${profile.faculty}/${profile.year}`);
    } catch {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-md flex-col gap-8 py-8 sm:py-16">
      <p className="text-sm text-muted" aria-live="polite">
        Étape {step === "annee" ? 1 : 2} sur 2
      </p>

      {step === "annee" ? (
        <section aria-labelledby="titre-annee" className="flex flex-col gap-8">
          <div className="flex flex-col gap-2">
            <h1 id="titre-annee" className="text-3xl leading-tight">
              Quelle est ton année ?
            </h1>
            <p className="text-muted">Faculté de Médecine de Sfax.</p>
          </div>
          <ul className="flex flex-col gap-3">
            {YEARS.map((year) => {
              const selected = profile.year === year.id;
              return (
                <li key={year.id}>
                  <button
                    type="button"
                    onClick={() => chooseYear(year.id)}
                    aria-pressed={selected}
                    className={cn(
                      "flex min-h-16 w-full items-center gap-4 rounded-card border px-5 py-3 text-left transition-colors duration-150 hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      selected ? "border-primary" : "border-border",
                    )}
                  >
                    <span className="flex flex-1 flex-col">
                      <span className="text-lg font-medium">{year.label}</span>
                      <span className="text-sm text-muted">{year.detail}</span>
                    </span>
                    <ChevronRight className="size-5 text-muted" strokeWidth={1.5} aria-hidden />
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ) : (
        <section aria-labelledby="titre-date" className="flex flex-col gap-8">
          <div className="flex flex-col gap-2">
            <h1 id="titre-date" className="text-3xl leading-tight">
              Quand a lieu ton prochain certif ?
            </h1>
            <p className="text-muted">Facultatif : pour le compte à rebours. Tu pourras la changer dans Mon espace.</p>
          </div>
          <label className="flex flex-col gap-2">
            <span className="sr-only">Date du prochain certif</span>
            <input
              type="date"
              value={profile.examDate ?? ""}
              onChange={(event) => setProfile({ ...profile, examDate: event.target.value || null })}
              className="h-14 w-full rounded-card border border-border bg-surface px-4 text-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </label>
          <div className="flex flex-col items-center gap-2">
            <Button size="lg" className="w-full" onClick={save} disabled={!profile.year || saving}>
              {saving ? "Un instant…" : "Commencer"}
            </Button>
            <button
              type="button"
              onClick={() => setStep("annee")}
              className="flex h-12 items-center rounded-card px-2 text-[0.9375rem] text-muted underline-offset-4 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Changer d&apos;année
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
