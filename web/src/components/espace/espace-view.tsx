"use client";

import { CalendarDays, CircleCheck, DoorOpen, Flame, ListChecks, LogOut, PlayCircle, Settings, Sparkles, Target, Timer } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { leave, signOut as signOutCode } from "@/app/acces/actions";
import { Button } from "@/components/ui/button";
import { ProgressRing } from "@/components/ui/progress-ring";
import { StatTile } from "@/components/ui/stat-tile";
import { validExamDate } from "@/lib/dates";
import { useMember, type Me } from "@/components/layout/use-member";
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
import { lessonHref, shortCertifTitle, type EspaceYear } from "./types";
import { useEspaceData } from "./use-espace-data";

const DEFAULT_GOAL = 20;

/** The student's dashboard: profile, figures, per-certif progress, courses to review, notes, settings. */
export function EspaceView({ years }: { years: EspaceYear[] }) {
  const { user } = useProgress();
  const { data, saveProfile, removeHighlight } = useEspaceData(years);
  const lessons = useMemo(() => lessonDirectory(years), [years]);
  const me = useMember();
  const { profile, now } = data;
  const year = years.find((item) => item.year === profile?.year && item.faculty === (profile?.faculty || "sfax"));
  const name = displayNameOf(user, profile?.displayName) ?? me?.member?.firstName ?? null;

  if (data.loading)
    return (
      <div className="mx-auto max-w-5xl py-8" aria-busy="true">
        <p className="text-muted">Chargement de ton espace…</p>
      </div>
    );

  const attempts = year ? data.attempts.filter((item) => item.year === year.year && item.faculty === year.faculty) : [];

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-12 sm:gap-16">
      <ProfilePanel profile={profile} year={year} name={name} now={now} me={me} />

      {year ? (
        <>
          <ProgressPanel year={year} attempts={attempts} goal={profile?.dailyGoal ?? DEFAULT_GOAL} now={now} />
          <div className="grid grid-cols-1 gap-12 sm:gap-16 lg:grid-cols-2 lg:gap-6 [&>*]:min-w-0">
            <Collection year={year} progress={data.progress} attempts={attempts} />
            <ToReview year={year} attempts={attempts} />
          </div>
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

// Profile ---------------------------------------------------------------------------------------

function ProfilePanel({
  profile,
  year,
  name,
  now,
  me,
}: {
  profile: Profile | null;
  year: EspaceYear | undefined;
  name: string | null;
  now: Date;
  me: Me | null;
}) {
  const { user, store } = useProgress();
  const router = useRouter();
  const member = me?.member;

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
    <section aria-labelledby="espace-titre" className="panel relative flex flex-col gap-8 overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{ background: "radial-gradient(55% 90% at 0% 0%, var(--primary-soft), transparent 70%)" }}
      />
      <div className="relative flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-5">
          <span className="rounded-full shadow-glow">
            <UserAvatar user={user} name={name} size="md" />
          </span>
          <div className="flex min-w-0 flex-col gap-1">
            <h1 id="espace-titre" className="truncate text-3xl leading-tight sm:text-4xl">
              {name ?? "Mon espace"}
            </h1>
            <p className="text-[0.9375rem] text-muted">{details.join(" · ")}</p>
            {member && (
              <span className="mt-1 inline-flex items-center gap-1.5 self-start rounded-full bg-primary-soft px-3 py-1 text-sm text-primary">
                <Sparkles className="size-3.5" aria-hidden />
                {member.gender === "f" ? "Testeuse" : "Testeur"} bêta
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {member && (
            <Button asChild variant="outline">
              <Link href="/bienvenue">Revoir l&apos;accueil</Link>
            </Button>
          )}
          <Button asChild variant="ghost">
            <a href="#reglages">
              <Settings aria-hidden /> Réglages
            </a>
          </Button>
          {member && (
            <form action={signOutCode}>
              <Button type="submit" variant="outline">
                <LogOut aria-hidden /> Se déconnecter
              </Button>
            </form>
          )}
        </div>
      </div>

      <div className="relative grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Countdown examDate={validExamDate(profile?.examDate, now)} now={now} />
        {member && me?.visits !== undefined && (
          <StatTile icon={<DoorOpen className="size-4" aria-hidden />} label="visites" value={me.visits} />
        )}
        <StatTile
          icon={<Target className="size-4" aria-hidden />}
          label="objectif du jour"
          value={profile?.dailyGoal ?? DEFAULT_GOAL}
          hint="questions"
        />
      </div>

      {(store.kind === "local" || user || member) && (
        <div className="relative flex flex-col gap-1 text-[0.9375rem] text-muted">
          {store.kind === "local" && (
            <p>
              {supabaseEnabled && !member ? (
                <>
                  Tu n&apos;es pas connecté·e : ta progression reste dans ce navigateur.{" "}
                  <Link href="/connexion" className="font-medium text-foreground underline underline-offset-4">
                    Se connecter
                  </Link>
                </>
              ) : (
                "Pendant la bêta, ta progression reste sur cet appareil."
              )}
            </p>
          )}
          {user && (
            <button type="button" onClick={signOut} className={cn(textLink, "self-start font-normal text-muted hover:text-foreground")}>
              Se déconnecter
            </button>
          )}
          {member && (
            <form action={leave}>
              <button type="submit" className={cn(textLink, "font-normal text-muted hover:text-foreground")}>
                Changer de code d&apos;accès
              </button>
            </form>
          )}
        </div>
      )}
    </section>
  );
}

function Countdown({ examDate, now }: { examDate: string | null; now: Date }) {
  const days = examDate ? daysUntil(examDate, now) : null;
  if (days === null || !examDate || days < 0)
    return (
      <a
        href="#reglages"
        className="col-span-2 flex flex-col justify-center gap-1 rounded-card border border-dashed border-border bg-surface p-5 transition-shadow duration-200 hover:shadow-glow focus-visible:shadow-glow focus-visible:outline-none sm:col-span-1"
      >
        <span className="flex items-center gap-2 text-sm text-muted">
          <CalendarDays className="size-4" aria-hidden /> date du certif
        </span>
        <span className="text-lg font-semibold">
          {days !== null && days < 0 ? "Mets à jour la date de ton certif" : "Ajoute la date de ton certif"}
        </span>
      </a>
    );
  return (
    <StatTile
      className="col-span-2 sm:col-span-1"
      icon={<CalendarDays className="size-4" aria-hidden />}
      label="avant ton certif"
      value={days === 0 ? "Jour J" : `J-${days}`}
      hint={formatExamDate(examDate)}
    />
  );
}

// Progression -----------------------------------------------------------------------------------

function ProgressPanel({
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
  const base = `/${year.faculty}/${year.year}`;
  const correct = attempts.filter((item) => item.correct).length;
  const precision = attempts.length ? Math.round((correct / attempts.length) * 100) : null;
  const medianTime = median(attempts.map((item) => item.timeMs));
  const days = streak(attempts, now);
  const today = dayKey(now);
  const answeredToday = attempts.filter((item) => dayKey(new Date(item.createdAt)) === today).length;

  return (
    <EspaceSection
      id="progression"
      title="Ma progression"
      description={year.yearLabel}
      action={
        attempts.length ? (
          <Link href={`${base}/progression`} className={textLink}>
            Voir le détail
          </Link>
        ) : (
          <Button asChild className="shadow-glow">
            <Link href={`${base}/quiz`}>
              <PlayCircle aria-hidden /> Faire un quiz
            </Link>
          </Button>
        )
      }
    >
      <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-stretch">
        <div className="flex flex-col items-center justify-center gap-2 rounded-card border border-border bg-surface px-8 py-5">
          <ProgressRing value={(answeredToday / goal) * 100} size={128} stroke={11} label="Objectif du jour">
            <span className="flex flex-col items-center leading-none">
              <span className="text-3xl">{answeredToday}</span>
              <span className="mt-1 text-sm font-normal text-muted">/ {goal}</span>
            </span>
          </ProgressRing>
          <span className="text-sm text-muted">objectif du jour</span>
        </div>
        <div className="grid w-full flex-1 grid-cols-2 gap-3">
          <StatTile
            icon={<ListChecks className="size-4" aria-hidden />}
            label="questions répondues"
            value={attempts.length.toLocaleString("fr-FR")}
          />
          <StatTile
            icon={<CircleCheck className="size-4" aria-hidden />}
            label="bonnes réponses"
            value={precision === null ? "—" : `${precision} %`}
          />
          <StatTile icon={<Flame className="size-4" aria-hidden />} label="série de jours" value={days} />
          <StatTile icon={<Timer className="size-4" aria-hidden />} label="temps médian" value={formatSeconds(medianTime)} />
        </div>
      </div>
      {!attempts.length && (
        <p className="text-sm text-muted">Réponds à ta première question : tes chiffres apparaîtront ici.</p>
      )}
    </EspaceSection>
  );
}

// Courses to review -------------------------------------------------------------------------------

/** Lessons answered at least twice, lowest accuracy first. */
function ToReview({ year, attempts }: { year: EspaceYear; attempts: Attempt[] }) {
  const rows = useMemo(() => {
    const info = new Map(
      year.certifs.flatMap((certif) => certif.lessons.map((lesson) => [lesson.id, { lesson, certif }] as const)),
    );
    const byLesson = new Map<string, Attempt[]>();
    for (const item of attempts) byLesson.set(item.lessonId, [...(byLesson.get(item.lessonId) ?? []), item]);
    return [...byLesson.entries()]
      .filter(([id, items]) => info.has(id) && items.length >= 2)
      .map(([id, items]) => ({
        ...info.get(id)!,
        answered: items.length,
        percent: Math.round((items.filter((item) => item.correct).length / items.length) * 100),
      }))
      .sort((a, b) => a.percent - b.percent || b.answered - a.answered)
      .slice(0, 6);
  }, [year, attempts]);

  return (
    <EspaceSection id="a-revoir" title="Cours à revoir" description="Là où tu te trompes le plus, en premier.">
      {rows.length === 0 ? (
        <EmptyState>Réponds à quelques questions : les cours qui te résistent apparaîtront ici.</EmptyState>
      ) : (
        <ul className="flex flex-col gap-2">
          {rows.map(({ lesson, certif, answered, percent }) => (
            <li key={lesson.id}>
              <Link
                href={lessonHref(year, lesson.id)}
                className="flex min-h-14 items-center gap-4 rounded-card border border-border bg-surface px-4 py-3 transition-shadow duration-200 hover:shadow-glow focus-visible:shadow-glow focus-visible:outline-none"
              >
                <span
                  className={cn(
                    "numeral w-16 shrink-0 rounded-control py-1 text-center text-lg font-semibold",
                    percent < 50 ? "bg-wrong-soft text-wrong" : percent < 75 ? "bg-highyield-soft text-highyield" : "bg-correct-soft text-correct",
                  )}
                >
                  {percent} %
                </span>
                <span className="min-w-0 flex-1">
                  <span className="line-clamp-2 font-medium leading-snug">{lesson.title}</span>
                  <span className="block truncate text-sm text-muted">
                    {shortCertifTitle(certif.title)} · {answered} réponses
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </EspaceSection>
  );
}
