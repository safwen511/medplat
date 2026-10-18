"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, type ReactNode } from "react";

import { displayNameOf, UserAvatar } from "@/components/layout/user-avatar";
import { useProgress } from "@/lib/progress/provider";
import type { Attempt, Profile } from "@/lib/progress/store";
import { browserClient } from "@/lib/supabase/client";
import { supabaseEnabled } from "@/lib/supabase/config";
import { cn } from "@/lib/utils";

import { Collection } from "./collection";
import { HighlightsSection, lessonDirectory, ReportsSection } from "./notes";
import { EmptyState, EspaceSection, textLink } from "./section";
import { SettingsForm } from "./settings-form";
import { dayKey, daysUntil, formatExamDate, formatMonth, formatSeconds, median, streak } from "./stats";
import type { EspaceYear } from "./types";
import { useEspaceData } from "./use-espace-data";

const DEFAULT_GOAL = 20;

/** A calm personal page: a profile line, then sections set in type. The settings form is the one card. */
export function EspaceView({ years }: { years: EspaceYear[] }) {
  const { user } = useProgress();
  const { data, saveProfile, removeHighlight } = useEspaceData(years);
  const lessons = useMemo(() => lessonDirectory(years), [years]);
  const { profile, now } = data;
  const year = years.find((item) => item.year === profile?.year && item.faculty === (profile?.faculty || "sfax"));
  const name = displayNameOf(user, profile?.displayName);

  if (data.loading)
    return (
      <div className="mx-auto max-w-[640px] py-8" aria-busy="true">
        <p className="text-muted">Chargement de ton espace…</p>
      </div>
    );

  return (
    <div className="mx-auto flex max-w-[640px] flex-col gap-14 py-4 sm:py-8">
      <ProfileLine profile={profile} year={year} name={name} now={now} />

      {year ? (
        <>
          <ProgressSection year={year} attempts={data.attempts} goal={profile?.dailyGoal ?? DEFAULT_GOAL} now={now} />
          <Collection year={year} progress={data.progress} />
        </>
      ) : (
        <EspaceSection id="progression" title="Ma progression">
          <EmptyState
            action={
              <a href="#reglages" className={textLink}>
                Choisir mon année
              </a>
            }
          >
            Choisis ton année pour voir ta progression et ta collection.
          </EmptyState>
        </EspaceSection>
      )}

      <HighlightsSection highlights={data.highlights} lessons={lessons} now={now} onRemove={removeHighlight} />
      {data.reports && <ReportsSection reports={data.reports} lessons={lessons} now={now} />}
      <SettingsForm key={user?.id ?? "local"} initial={profile} fallbackName={displayNameOf(user)} onSave={saveProfile} />
    </div>
  );
}

// Profile line ----------------------------------------------------------------------------------

function ProfileLine({
  profile,
  year,
  name,
  now,
}: {
  profile: Profile | null;
  year: EspaceYear | undefined;
  name: string | null;
  now: Date;
}) {
  const { user, store } = useProgress();
  const router = useRouter();

  const signOut = async () => {
    await browserClient()?.auth.signOut();
    router.push("/");
    router.refresh();
  };

  const details = [
    year?.yearLabel,
    year?.facultyLabel ?? "Faculté de Médecine de Sfax",
    user?.created_at && `membre depuis ${formatMonth(user.created_at)}`,
  ].filter(Boolean);

  return (
    <header className="flex flex-col gap-6">
      <h1 className="text-3xl leading-tight sm:text-4xl">Mon espace</h1>
      <div className="flex items-center gap-4">
        <UserAvatar user={user} name={name} size="md" />
        <div className="flex min-w-0 flex-col">
          <p className="truncate text-lg font-medium">{name ?? "Étudiant·e"}</p>
          <p className="text-[0.9375rem] text-muted">{details.join(" · ")}</p>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <Countdown examDate={profile?.examDate ?? null} now={now} />
        {store.kind === "local" && (
          <p className="text-[0.9375rem] text-muted">
            {supabaseEnabled ? (
              <>
                Tu n&apos;es pas connecté·e : ta progression reste dans ce navigateur.{" "}
                <Link href="/connexion" className="font-medium text-foreground underline underline-offset-4">
                  Se connecter
                </Link>
              </>
            ) : (
              "Mode démo : la connexion n'est pas encore ouverte, ta progression reste dans ce navigateur."
            )}
          </p>
        )}
        {user && (
          <button type="button" onClick={signOut} className={cn(textLink, "self-start font-normal text-muted hover:text-foreground")}>
            Se déconnecter
          </button>
        )}
      </div>
    </header>
  );
}

function Countdown({ examDate, now }: { examDate: string | null; now: Date }) {
  const days = examDate ? daysUntil(examDate, now) : null;
  if (days === null || !examDate)
    return (
      <p className="text-[0.9375rem] text-muted">
        <a href="#reglages" className="font-medium text-foreground underline underline-offset-4">
          Ajoute la date de ton certif
        </a>{" "}
        pour voir le compte à rebours.
      </p>
    );
  const date = formatExamDate(examDate);
  if (days < 0)
    return (
      <p className="text-[0.9375rem] text-muted">
        La date de ton certif ({date}) est passée.{" "}
        <a href="#reglages" className="font-medium text-foreground underline underline-offset-4">
          Mets-la à jour
        </a>
      </p>
    );
  const when =
    days === 0 ? "aujourd'hui" : days === 1 ? "demain" : (
      <>
        dans <span className="font-medium tabular-nums text-foreground">{days} jours</span>
      </>
    );
  return (
    <p className="text-[0.9375rem] text-muted">
      Ton prochain certif est {when}, le {date}.
    </p>
  );
}

// Progression -----------------------------------------------------------------------------------

function Num({ children }: { children: ReactNode }) {
  return <span className="font-medium tabular-nums text-foreground">{children}</span>;
}

function ProgressSection({
  year,
  attempts,
  goal,
  now,
}: {
  year: EspaceYear;
  attempts: Attempt[];
  goal: number;
  now: Date;
}) {
  const mine = attempts.filter((item) => item.year === year.year && item.faculty === year.faculty);
  const base = `/${year.faculty}/${year.year}`;

  if (!mine.length)
    return (
      <EspaceSection id="progression" title="Ma progression">
        <EmptyState
          action={
            <Link href={`${base}/quiz`} className={textLink}>
              Faire un quiz
            </Link>
          }
        >
          Tu n&apos;as pas encore répondu à une question en {year.yearLabel}.
        </EmptyState>
      </EspaceSection>
    );

  const correct = mine.filter((item) => item.correct).length;
  const precision = Math.round((correct / mine.length) * 100);
  const medianTime = median(mine.map((item) => item.timeMs));
  const days = streak(mine, now);
  const today = dayKey(now);
  const answeredToday = mine.filter((item) => dayKey(new Date(item.createdAt)) === today).length;

  return (
    <EspaceSection
      id="progression"
      title="Ma progression"
      action={
        <Link href={`${base}/progression`} className={textLink}>
          Voir le détail
        </Link>
      }
    >
      <div className="flex flex-col gap-2 text-muted">
        <p>
          Tu as répondu à <Num>{mine.length.toLocaleString("fr-FR")}</Num> question{mine.length > 1 ? "s" : ""}, avec{" "}
          <Num>{precision} %</Num> de bonnes réponses. Temps médian : <Num>{formatSeconds(medianTime)}</Num> par
          question.
        </p>
        <p>
          Aujourd&apos;hui :{" "}
          <Num>
            {answeredToday} / {goal}
          </Num>{" "}
          questions de ton objectif du jour.
          {days > 0 && (
            <>
              {" "}
              Tu révises depuis <Num>{days === 1 ? "1 jour" : `${days} jours`}</Num> d&apos;affilée.
            </>
          )}
        </p>
      </div>
    </EspaceSection>
  );
}
