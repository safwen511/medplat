"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useProgress } from "@/lib/progress/provider";

/** Creates the tester's profile on this device (name, year) and opens their year. */
export function StartButton({
  firstName,
  year,
  href,
}: {
  firstName: string;
  year: "dcem1" | "dcem2";
  href: string;
}) {
  const { store } = useProgress();
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const start = async () => {
    setPending(true);
    const current = await store.profile();
    await store.saveProfile({
      displayName: current?.displayName || firstName,
      faculty: "sfax",
      year,
      examDate: current?.examDate ?? null,
      onboarded: true,
      dailyGoal: current?.dailyGoal ?? 20,
    });
    router.push(href);
  };
  return (
    <Button size="lg" onClick={start} disabled={pending} className="self-start">
      {pending ? "Ouverture…" : "Commencer"}
    </Button>
  );
}
