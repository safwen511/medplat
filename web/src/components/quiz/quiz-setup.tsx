"use client";

import { ArrowLeft, BookOpen, Check, ChevronDown, Flame, Gamepad2, ListOrdered, Play, Shuffle, Zap } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState, type ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Exercise, YearIndex } from "@/lib/content/types";
import { useProgress } from "@/lib/progress/provider";
import { cn, shuffle } from "@/lib/utils";

import { Game, GAMES, type GameKind } from "./games";
import { randomSeed, TYPE_LABELS } from "./grading";
import { QuestionPlayer } from "./question-player";

const COUNTS = [5, 10, 20] as const;
const TYPE_ORDER = Object.keys(TYPE_LABELS) as Exercise["type"][];
const GAME_ICONS: Record<GameKind, ReactNode> = {
  sprint: <Zap aria-hidden />,
  association: <Shuffle aria-hidden />,
  ordre: <ListOrdered aria-hidden />,
};

type View = { kind: "setup" } | { kind: "quiz"; items: Exercise[]; key: number } | { kind: "game"; game: GameKind; key: number };

interface LessonInfo {
  id: string;
  title: string;
  certif: string;
  module: string;
}

/** Quiz setup; reads ?certif=<slug> to preselect a certificate (hence its own Suspense boundary). */
export function QuizSetup(props: { index: YearIndex; pool: Exercise[] }) {
  return (
    <Suspense fallback={null}>
      <QuizSetupInner {...props} />
    </Suspense>
  );
}

function QuizSetupInner({ index, pool }: { index: YearIndex; pool: Exercise[] }) {
  const { store } = useProgress();
  const [view, setView] = useState<View>({ kind: "setup" });
  const requested = useSearchParams().get("certif");
  const [certifs, setCertifs] = useState<string[]>(() =>
    requested && index.certifs.some((certif) => certif.slug === requested) ? [requested] : [],
  );
  const [lessons, setLessons] = useState<string[]>([]);
  const [types, setTypes] = useState<Exercise["type"][]>([]);
  const [count, setCount] = useState<(typeof COUNTS)[number]>(10);
  const [highYieldOnly, setHighYieldOnly] = useState(false);
  const [mistakesOnly, setMistakesOnly] = useState(false);
  const [mistakes, setMistakes] = useState<Set<string>>(new Set());
  const [showLessons, setShowLessons] = useState(false);

  // Questions whose most recent attempt was wrong; reloaded whenever the setup is shown again.
  useEffect(() => {
    if (view.kind !== "setup") return;
    let cancelled = false;
    store
      .attempts()
      .then((attempts) => {
        const last = new Map<string, boolean>();
        for (const attempt of attempts) last.set(attempt.questionId, attempt.correct);
        if (!cancelled) setMistakes(new Set([...last].filter(([, correct]) => !correct).map(([id]) => id)));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [store, view.kind]);

  const lessonInfo = useMemo(() => {
    const map = new Map<string, LessonInfo>();
    for (const certif of index.certifs)
      for (const group of certif.modules)
        for (const lesson of group.lessons)
          map.set(lesson.id, { id: lesson.id, title: lesson.title, certif: certif.slug, module: group.title });
    return map;
  }, [index]);

  const certifOf = (exercise: Exercise) => lessonInfo.get(exercise.lessonId)?.certif ?? "";

  // Scope (certifs + lessons) also feeds the mini-games.
  const scoped = pool.filter(
    (exercise) =>
      (certifs.length === 0 || certifs.includes(certifOf(exercise))) &&
      (lessons.length === 0 || lessons.includes(exercise.lessonId)),
  );
  const filtered = scoped.filter(
    (exercise) =>
      (types.length === 0 || types.includes(exercise.type)) &&
      (!highYieldOnly || exercise.highYield) &&
      (!mistakesOnly || mistakes.has(exercise.id)),
  );

  const certifCounts = countBy(pool, certifOf);
  const typeCounts = countBy(
    scoped.filter((exercise) => (!highYieldOnly || exercise.highYield) && (!mistakesOnly || mistakes.has(exercise.id))),
    (exercise) => exercise.type,
  );
  const lessonCounts = countBy(pool, (exercise) => exercise.lessonId);
  const lessonChoices = [...lessonCounts.keys()]
    .map((id) => lessonInfo.get(id) ?? { id, title: id, certif: "", module: "Autres" })
    .filter((lesson) => certifs.length === 0 || certifs.includes(lesson.certif));

  const launch = () => {
    const seed = randomSeed();
    setView({ kind: "quiz", items: shuffle(filtered, seed).slice(0, count), key: seed });
  };

  if (pool.length === 0) return <EmptyState index={index} />;

  if (view.kind === "quiz") {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
        <Button variant="ghost" size="sm" className="self-start" onClick={() => setView({ kind: "setup" })}>
          <ArrowLeft aria-hidden />
          Configuration
        </Button>
        <QuestionPlayer
          key={view.key}
          exercises={view.items}
          mode="quiz"
          faculty={index.faculty}
          year={index.year}
          onFinish={() => setView({ kind: "setup" })}
        />
      </div>
    );
  }

  if (view.kind === "game") {
    return (
      <div className="mx-auto w-full max-w-3xl">
        <Game
          key={view.key}
          kind={view.game}
          pool={scoped}
          faculty={index.faculty}
          year={index.year}
          onExit={() => setView({ kind: "setup" })}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-8">
      <header className="flex flex-col gap-1">
        <p className="text-sm text-muted">{index.yearLabel}</p>
        <h1 className="text-2xl font-semibold">Quiz</h1>
        <p className="text-sm text-muted">Compose ta série : certificats, cours, types de questions.</p>
      </header>

      <Card>
        <CardContent className="flex flex-col gap-6 pt-5">
          <Field label="Certificats" hint={certifs.length === 0 ? "Tous" : undefined}>
            <div className="flex flex-wrap gap-2">
              {index.certifs
                .filter((certif) => certifCounts.has(certif.slug))
                .map((certif) => (
                  <Chip
                    key={certif.slug}
                    pressed={certifs.includes(certif.slug)}
                    onClick={() => {
                      setCertifs(toggle(certifs, certif.slug));
                      setLessons([]);
                    }}
                    count={certifCounts.get(certif.slug)}
                  >
                    {certif.title}
                  </Chip>
                ))}
            </div>
          </Field>

          <Field label="Cours" hint={lessons.length === 0 ? "Tous" : `${lessons.length} sélectionné${lessons.length > 1 ? "s" : ""}`}>
            <button
              type="button"
              onClick={() => setShowLessons(!showLessons)}
              aria-expanded={showLessons}
              className="flex items-center gap-1.5 self-start rounded text-sm font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <ChevronDown className={cn("size-4 transition-transform", showLessons && "rotate-180")} aria-hidden />
              {showLessons ? "Masquer les cours" : "Choisir des cours"}
            </button>
            {showLessons && (
              <ul className="flex max-h-72 flex-col gap-1 overflow-y-auto rounded-card border border-border p-2">
                {lessonChoices.map((lesson) => {
                  const checked = lessons.includes(lesson.id);
                  return (
                    <li key={lesson.id}>
                      <button
                        type="button"
                        role="checkbox"
                        aria-checked={checked}
                        onClick={() => setLessons(toggle(lessons, lesson.id))}
                        className="flex w-full items-center gap-3 rounded-md px-2 py-2 text-left text-sm hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <span
                          aria-hidden
                          className={cn(
                            "flex size-5 shrink-0 items-center justify-center rounded border",
                            checked ? "border-primary bg-primary text-primary-foreground" : "border-border",
                          )}
                        >
                          {checked && <Check className="size-3.5" strokeWidth={3} />}
                        </span>
                        <span className="flex-1">
                          {lesson.title}
                          <span className="block text-xs text-muted">{lesson.module}</span>
                        </span>
                        <span className="text-xs tabular-nums text-muted">{lessonCounts.get(lesson.id)}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </Field>

          <Field label="Types de questions" hint={types.length === 0 ? "Tous" : undefined}>
            <div className="flex flex-wrap gap-2">
              {TYPE_ORDER.filter((type) => pool.some((exercise) => exercise.type === type)).map((type) => (
                <Chip
                  key={type}
                  pressed={types.includes(type)}
                  onClick={() => setTypes(toggle(types, type))}
                  count={typeCounts.get(type) ?? 0}
                >
                  {TYPE_LABELS[type]}
                </Chip>
              ))}
            </div>
          </Field>

          <Field label="Nombre de questions">
            <div role="radiogroup" aria-label="Nombre de questions" className="inline-flex self-start rounded-card bg-surface-muted p-1">
              {COUNTS.map((value) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={count === value}
                  onClick={() => setCount(value)}
                  className={cn(
                    "h-9 min-w-14 rounded-[calc(var(--radius)-0.25rem)] px-4 text-sm font-medium tabular-nums transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    count === value ? "bg-surface text-foreground shadow-sm" : "text-muted hover:text-foreground",
                  )}
                >
                  {value}
                </button>
              ))}
            </div>
          </Field>

          <div className="flex flex-col gap-3">
            <Toggle
              checked={highYieldOnly}
              onChange={setHighYieldOnly}
              label="Tombe souvent uniquement"
              description="Questions sur les notions fréquentes aux examens."
              icon={<Flame className="size-4 text-highyield" aria-hidden />}
            />
            <Toggle
              checked={mistakesOnly}
              onChange={setMistakesOnly}
              label="Mes erreurs"
              description={
                mistakes.size > 0
                  ? `${mistakes.size} question${mistakes.size > 1 ? "s" : ""} ratée${mistakes.size > 1 ? "s" : ""} lors de la dernière tentative.`
                  : "Aucune erreur enregistrée pour l'instant."
              }
              disabled={mistakes.size === 0 && !mistakesOnly}
            />
          </div>
        </CardContent>
        <div className="flex flex-col gap-3 border-t border-border bg-surface-muted/40 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted" aria-live="polite">
            {filtered.length === 0
              ? "Aucune question ne correspond à ces filtres."
              : `${Math.min(count, filtered.length)} question${Math.min(count, filtered.length) > 1 ? "s" : ""} sur ${filtered.length} disponible${filtered.length > 1 ? "s" : ""}`}
          </p>
          <Button size="lg" onClick={launch} disabled={filtered.length === 0}>
            <Play aria-hidden />
            Lancer le quiz
          </Button>
        </div>
      </Card>

      <section className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Gamepad2 className="size-5 text-primary" aria-hidden />
          <h2 className="text-lg font-semibold">Mini-jeux</h2>
        </div>
        <p className="-mt-1 text-sm text-muted">Selon les certificats et cours choisis ci-dessus.</p>
        <div className="grid gap-3 sm:grid-cols-3">
          {GAMES.map((game) => {
            const available = scoped.filter((exercise) => exercise.type === game.type).length;
            return (
              <Card key={game.kind} className="flex flex-col">
                <CardHeader>
                  <span className="mb-2 flex size-9 items-center justify-center rounded-full bg-primary-soft text-primary [&_svg]:size-4.5">
                    {GAME_ICONS[game.kind]}
                  </span>
                  <CardTitle>{game.title}</CardTitle>
                  <CardDescription>{game.description}</CardDescription>
                </CardHeader>
                <CardContent className="mt-auto flex items-center justify-between gap-2">
                  <span className="text-xs text-muted">
                    {available > 0 ? `${available} question${available > 1 ? "s" : ""}` : "Bientôt disponible"}
                  </span>
                  <Button
                    size="sm"
                    variant={available > 0 ? "primary" : "secondary"}
                    disabled={available === 0}
                    onClick={() => setView({ kind: "game", game: game.kind, key: randomSeed() })}
                  >
                    Jouer
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function EmptyState({ index }: { index: YearIndex }) {
  return (
    <div className="mx-auto flex w-full max-w-xl flex-col items-center gap-4 py-10 text-center">
      <span className="flex size-14 items-center justify-center rounded-full bg-primary-soft text-primary">
        <Gamepad2 className="size-7" aria-hidden />
      </span>
      <h1 className="text-2xl font-semibold">Les questions arrivent bientôt</h1>
      <p className="text-sm leading-relaxed text-muted">
        Les quiz et mini-jeux de {index.yearLabel} sont préparés à partir des cours reconstruits, puis vérifiés avant
        d&apos;être publiés. Ils apparaîtront ici dès qu&apos;un cours sera prêt.
      </p>
      <Button asChild variant="outline">
        <Link href={`/${index.faculty}/${index.year}`}>
          <BookOpen aria-hidden />
          Parcourir les cours
        </Link>
      </Button>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-2.5">
      <legend className="mb-2.5 flex w-full items-baseline justify-between text-sm font-semibold">
        {label}
        {hint && <span className="text-xs font-normal text-muted">{hint}</span>}
      </legend>
      {children}
    </fieldset>
  );
}

function Chip({
  pressed,
  onClick,
  count,
  children,
}: {
  pressed: boolean;
  onClick: () => void;
  count?: number;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={cn(
        "inline-flex min-h-9 items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        pressed
          ? "border-primary bg-primary-soft font-medium text-primary"
          : "border-border bg-surface text-foreground hover:bg-surface-muted",
      )}
    >
      {pressed && <Check className="size-3.5" strokeWidth={3} aria-hidden />}
      {children}
      {count !== undefined && (
        <Badge tone={pressed ? "primary" : "neutral"} className="px-1.5 py-0 tabular-nums">
          {count}
        </Badge>
      )}
    </button>
  );
}

function Toggle({
  checked,
  onChange,
  label,
  description,
  icon,
  disabled,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  description: string;
  icon?: ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="flex items-center gap-3 rounded-card border border-border bg-surface px-4 py-3 text-left transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
    >
      <span className="flex flex-1 flex-col">
        <span className="flex items-center gap-1.5 text-sm font-medium">
          {icon}
          {label}
        </span>
        <span className="text-xs text-muted">{description}</span>
      </span>
      <span
        aria-hidden
        className={cn(
          "relative h-6 w-10 shrink-0 rounded-full transition-colors",
          checked ? "bg-primary" : "bg-border",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 size-5 rounded-full bg-surface shadow-sm transition-transform",
            checked ? "translate-x-[1.125rem]" : "translate-x-0.5",
          )}
        />
      </span>
    </button>
  );
}

function toggle<T>(values: T[], value: T) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function countBy<T, K>(items: T[], key: (item: T) => K) {
  const counts = new Map<K, number>();
  for (const item of items) counts.set(key(item), (counts.get(key(item)) ?? 0) + 1);
  return counts;
}
