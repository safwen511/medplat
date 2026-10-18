"use client";

import { Check as CheckIcon } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import type { Exercise, YearIndex } from "@/lib/content/types";
import { useProgress } from "@/lib/progress/provider";
import { cn, shuffle } from "@/lib/utils";

import { Game, GAMES, type GameKind } from "./games";
import { randomSeed, TYPE_LABELS } from "./grading";
import { QuestionPlayer } from "./question-player";

const COUNTS = [5, 10, 20] as const;
const TYPE_ORDER = Object.keys(TYPE_LABELS) as Exercise["type"][];

type View =
  | { kind: "setup" }
  | { kind: "quiz"; items: Exercise[]; key: number }
  | { kind: "game"; game: GameKind; key: number };

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
  const rootRef = useRef<HTMLDivElement>(null);
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

  // Each screen starts at the top of the page.
  const open = (next: View) => {
    setView(next);
    requestAnimationFrame(() => {
      const top = rootRef.current?.getBoundingClientRect().top ?? 0;
      if (top < 0) rootRef.current?.scrollIntoView({ block: "start" });
    });
  };

  const launch = () => {
    const seed = randomSeed();
    open({ kind: "quiz", items: shuffle(filtered, seed).slice(0, count), key: seed });
  };

  if (pool.length === 0) return <EmptyState index={index} />;

  if (view.kind === "quiz") {
    return (
      <div ref={rootRef} className="mx-auto w-full max-w-[40rem] scroll-mt-20">
        <QuestionPlayer
          key={view.key}
          exercises={view.items}
          mode="quiz"
          faculty={index.faculty}
          year={index.year}
          onFinish={() => open({ kind: "setup" })}
          onExit={() => open({ kind: "setup" })}
        />
      </div>
    );
  }

  if (view.kind === "game") {
    return (
      <div ref={rootRef} className="mx-auto w-full max-w-[40rem] scroll-mt-20">
        <Game
          key={view.key}
          kind={view.game}
          pool={scoped}
          faculty={index.faculty}
          year={index.year}
          onExit={() => open({ kind: "setup" })}
        />
      </div>
    );
  }

  const planned = Math.min(count, filtered.length);
  const visibleCertifs = index.certifs.filter((certif) => certifCounts.has(certif.slug));
  const visibleTypes = TYPE_ORDER.filter((type) => pool.some((exercise) => exercise.type === type));

  return (
    <div ref={rootRef} className="mx-auto flex w-full max-w-[40rem] scroll-mt-20 flex-col gap-12">
      <header className="flex flex-col gap-2">
        <p className="text-sm text-muted">{index.yearLabel}</p>
        <h1 className="text-3xl">Quiz</h1>
      </header>

      <div className="flex flex-col gap-10">
        {visibleCertifs.length > 1 && (
          <Field label="Certificats" hint={certifs.length === 0 ? "tous" : undefined}>
            <Choices>
              {visibleCertifs.map((certif) => (
                <Choice
                  key={certif.slug}
                  pressed={certifs.includes(certif.slug)}
                  onClick={() => {
                    setCertifs(toggle(certifs, certif.slug));
                    setLessons([]);
                  }}
                  count={certifCounts.get(certif.slug)}
                >
                  {certif.title}
                </Choice>
              ))}
            </Choices>
          </Field>
        )}

        <Field
          label="Cours"
          hint={lessons.length === 0 ? "tous" : `${lessons.length} choisi${lessons.length > 1 ? "s" : ""}`}
        >
          <button
            type="button"
            onClick={() => setShowLessons(!showLessons)}
            aria-expanded={showLessons}
            aria-controls="quiz-cours"
            className="-my-2 min-h-12 self-start -mx-1 rounded-card px-1 text-base text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-current focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {showLessons ? "Masquer la liste" : "Choisir des cours"}
          </button>
          {showLessons && (
            <ul
              id="quiz-cours"
              className="flex max-h-[60vh] flex-col divide-y divide-border overflow-y-auto border-y border-border"
            >
              {lessonChoices.map((lesson) => {
                const checked = lessons.includes(lesson.id);
                return (
                  <li key={lesson.id}>
                    <button
                      type="button"
                      role="checkbox"
                      aria-checked={checked}
                      onClick={() => setLessons(toggle(lessons, lesson.id))}
                      className="flex min-h-14 w-full items-center gap-4 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <Box checked={checked} />
                      <span className="flex-1 leading-snug">
                        {lesson.title}
                        <span className="block text-sm text-muted">{lesson.module}</span>
                      </span>
                      <span className="text-sm tabular-nums text-muted">{lessonCounts.get(lesson.id)}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Field>

        {visibleTypes.length > 1 && (
          <Field label="Types de questions" hint={types.length === 0 ? "tous" : undefined}>
            <Choices>
              {visibleTypes.map((type) => (
                <Choice
                  key={type}
                  pressed={types.includes(type)}
                  onClick={() => setTypes(toggle(types, type))}
                  count={typeCounts.get(type) ?? 0}
                >
                  {TYPE_LABELS[type]}
                </Choice>
              ))}
            </Choices>
          </Field>
        )}

        <Field label="Nombre de questions">
          <Choices role="radiogroup" label="Nombre de questions">
            {COUNTS.map((value) => (
              <Choice key={value} radio pressed={count === value} onClick={() => setCount(value)}>
                {value}
              </Choice>
            ))}
          </Choices>
        </Field>

        <Field label="Affiner">
          <div className="flex flex-col">
            <Check
              checked={highYieldOnly}
              onChange={setHighYieldOnly}
              label="Seulement ce qui tombe souvent à l'examen"
            />
            <Check
              checked={mistakesOnly}
              onChange={setMistakesOnly}
              label="Seulement mes erreurs"
              description={
                mistakes.size > 0
                  ? `${mistakes.size} question${mistakes.size > 1 ? "s" : ""} ratée${mistakes.size > 1 ? "s" : ""} à la dernière tentative`
                  : "Aucune erreur enregistrée pour l'instant"
              }
              disabled={mistakes.size === 0 && !mistakesOnly}
            />
          </div>
        </Field>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row-reverse sm:items-center sm:justify-between">
        <Button size="lg" onClick={launch} disabled={filtered.length === 0} className="w-full sm:w-auto sm:min-w-40">
          Lancer
        </Button>
        <p className="text-base text-muted" aria-live="polite">
          {filtered.length === 0
            ? "Aucune question ne correspond à ces choix."
            : `${planned} question${planned > 1 ? "s" : ""} sur ${filtered.length} disponible${filtered.length > 1 ? "s" : ""}.`}
        </p>
      </div>

      <section id="mini-jeux" aria-labelledby="mini-jeux-titre" className="flex scroll-mt-24 flex-col gap-3 pt-4">
        <h2 id="mini-jeux-titre" className="text-xl">
          Mini-jeux
        </h2>
        <ul className="flex flex-col">
          {GAMES.map((game) => {
            const available = scoped.filter((exercise) => exercise.type === game.type).length;
            return (
              <li key={game.kind}>
                {available > 0 ? (
                  <button
                    type="button"
                    onClick={() => open({ kind: "game", game: game.kind, key: randomSeed() })}
                    className="group flex min-h-12 w-full flex-col items-start rounded-card py-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <span className="text-base text-primary underline decoration-primary/30 underline-offset-4 group-hover:decoration-current">
                      {game.title}
                    </span>
                    <span className="text-sm text-muted">{game.description}</span>
                  </button>
                ) : (
                  <p className="flex min-h-12 flex-col justify-center py-2">
                    <span className="text-base text-muted">{game.title}</span>
                    <span className="text-sm text-muted">Pas encore de questions de ce type.</span>
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}

function EmptyState({ index }: { index: YearIndex }) {
  return (
    <div className="mx-auto flex w-full max-w-[40rem] flex-col items-start gap-4 py-10">
      <h1 className="text-3xl">Les questions arrivent bientôt</h1>
      <p className="text-base leading-relaxed text-muted">
        Les quiz de {index.yearLabel} apparaîtront ici dès qu&apos;un cours sera prêt.
      </p>
      <Button asChild size="lg" className="mt-2">
        <Link href={`/${index.faculty}/${index.year}`}>Parcourir les cours</Link>
      </Button>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="mb-3 text-base font-medium">
        {label}
        {hint && <span className="font-normal text-muted"> · {hint}</span>}
      </legend>
      {children}
    </fieldset>
  );
}

function Choices({ role, label, children }: { role?: "radiogroup"; label?: string; children: ReactNode }) {
  return (
    <div role={role} aria-label={label} className="flex flex-wrap gap-2">
      {children}
    </div>
  );
}

/** A simple choice: a hairline row that takes the accent when selected. */
function Choice({
  pressed,
  onClick,
  count,
  radio,
  children,
}: {
  pressed: boolean;
  onClick: () => void;
  count?: number;
  radio?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      {...(radio ? { role: "radio", "aria-checked": pressed } : { "aria-pressed": pressed })}
      onClick={onClick}
      className={cn(
        "inline-flex min-h-12 items-center gap-2 rounded-card border px-4 text-base transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        pressed ? "border-primary bg-primary-soft text-primary" : "border-border bg-surface hover:border-muted/50",
      )}
    >
      {children}
      {count !== undefined && <span className={cn("text-sm tabular-nums", pressed ? "text-primary/80" : "text-muted")}>{count}</span>}
    </button>
  );
}

function Box({ checked }: { checked: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex size-5 shrink-0 items-center justify-center rounded-[5px] border transition-colors duration-150",
        checked ? "border-primary bg-primary text-primary-foreground" : "border-muted/60",
      )}
    >
      {checked && <CheckIcon className="size-3.5" strokeWidth={2.5} />}
    </span>
  );
}

function Check({
  checked,
  onChange,
  label,
  description,
  disabled,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="flex min-h-12 items-center gap-4 rounded-card py-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
    >
      <Box checked={checked} />
      <span className="flex flex-col leading-snug">
        <span className="text-base">{label}</span>
        {description && <span className="text-sm text-muted">{description}</span>}
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
