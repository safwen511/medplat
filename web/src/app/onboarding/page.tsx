"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useProgress } from "@/lib/progress/provider";
import type { Profile } from "@/lib/progress/store";
import { cn } from "@/lib/utils";

const YEARS = [
  { id: "dcem1", label: "DCEM1", detail: "3e année" },
  { id: "dcem2", label: "DCEM2", detail: "4e année" },
] as const;

export default function Onboarding() {
  const { store, user } = useProgress();
  const router = useRouter();
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

  const save = async () => {
    if (!profile.year) return;
    await store.saveProfile({ ...profile, displayName: profile.displayName ?? user?.user_metadata?.name ?? null, onboarded: true });
    router.push(`/${profile.faculty}/${profile.year}`);
  };

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-6 py-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Ton année</CardTitle>
          <CardDescription>Pour te proposer les bons cours et les bons QCM.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-medium">Faculté</legend>
            <div className="rounded-card border border-primary bg-primary-soft px-4 py-3 text-sm">
              Faculté de Médecine de Sfax
              <span className="block text-xs text-muted">Tunis, Sousse et Monastir arrivent bientôt.</span>
            </div>
          </fieldset>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-medium">Année</legend>
            <div className="grid grid-cols-2 gap-3">
              {YEARS.map((year) => (
                <button
                  key={year.id}
                  type="button"
                  onClick={() => setProfile({ ...profile, year: year.id })}
                  className={cn(
                    "rounded-card border px-4 py-3 text-left transition-colors",
                    profile.year === year.id
                      ? "border-primary bg-primary-soft"
                      : "border-border hover:bg-surface-muted",
                  )}
                  aria-pressed={profile.year === year.id}
                >
                  <span className="block font-semibold">{year.label}</span>
                  <span className="text-sm text-muted">{year.detail}</span>
                </button>
              ))}
            </div>
          </fieldset>
          <label className="flex flex-col gap-2 text-sm font-medium">
            Date de ton prochain certif (facultatif)
            <input
              type="date"
              value={profile.examDate ?? ""}
              onChange={(event) => setProfile({ ...profile, examDate: event.target.value || null })}
              className="h-10 rounded-card border border-border bg-surface px-3 font-normal"
            />
          </label>
          <Button size="lg" onClick={save} disabled={!profile.year}>
            C&apos;est parti
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
