"use client";

import { ArrowRight, ChevronRight } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { setExamDateBounds, validExamDate } from "@/lib/dates";
import { EASE_OUT } from "@/lib/motion";
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
        examDate: validExamDate(profile.examDate),
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
      <div className="flex flex-col gap-3">
        <p className="eyebrow" aria-live="polite">
          Étape {step === "annee" ? 1 : 2} sur 2
        </p>
        <div aria-hidden className="grid grid-cols-2 gap-1.5">
          <span className="h-1 rounded-full bg-primary" />
          <span
            className={cn(
              "h-1 rounded-full transition-colors duration-300",
              step === "annee" ? "bg-surface-muted" : "bg-primary",
            )}
          />
        </div>
      </div>

      <AnimatePresence mode="wait" initial={false}>
        {step === "annee" ? (
          <motion.section
            key="annee"
            initial={{ opacity: 0, x: -24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -24 }}
            transition={{ duration: 0.25, ease: EASE_OUT }}
            aria-labelledby="titre-annee"
            className="flex flex-col gap-8"
          >
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
                        "group flex min-h-20 w-full items-center gap-5 rounded-panel border px-5 py-4 text-left transition-[border-color,background-color,box-shadow,scale] duration-200 hover:border-border-strong hover:bg-surface active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        selected ? "border-primary/70 bg-primary-soft shadow-glow" : "border-border bg-surface/50",
                      )}
                    >
                      <span className="numeral flex size-12 shrink-0 items-center justify-center rounded-2xl bg-surface-muted text-xl font-semibold">
                        {year.detail.charAt(0)}
                        <span className="text-xs">e</span>
                      </span>
                      <span className="flex flex-1 flex-col">
                        <span className="font-heading text-lg font-semibold">{year.label}</span>
                        <span className="text-sm text-muted">{year.detail}</span>
                      </span>
                      <ChevronRight
                        className="size-5 text-muted transition-transform duration-200 group-hover:translate-x-0.5"
                        strokeWidth={1.5}
                        aria-hidden
                      />
                    </button>
                  </li>
                );
              })}
            </ul>
          </motion.section>
        ) : (
          <motion.section
            key="date"
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 24 }}
            transition={{ duration: 0.25, ease: EASE_OUT }}
            aria-labelledby="titre-date"
            className="flex flex-col gap-8"
          >
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
                ref={setExamDateBounds}
                value={profile.examDate ?? ""}
                onChange={(event) => setProfile({ ...profile, examDate: event.target.value || null })}
                className="h-14 w-full rounded-card border border-border-strong bg-surface px-4 text-lg transition-[border-color,box-shadow] duration-200 focus-visible:border-primary/70 focus-visible:shadow-glow focus-visible:outline-none"
              />
            </label>
            <div className="flex flex-col items-center gap-2">
              <Button size="lg" className="w-full shadow-glow" onClick={save} disabled={!profile.year || saving}>
                {saving ? "Un instant…" : "Commencer"} {!saving && <ArrowRight aria-hidden />}
              </Button>
              <button
                type="button"
                onClick={() => setStep("annee")}
                className="flex h-12 items-center rounded-card px-2 text-[0.9375rem] text-muted underline-offset-4 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                Changer d&apos;année
              </button>
            </div>
          </motion.section>
        )}
      </AnimatePresence>
    </div>
  );
}
