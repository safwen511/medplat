"use client";

import { ArrowLeft, Flame, RotateCcw, Target, Timer, Trophy, Zap } from "lucide-react";
import { AnimatePresence, motion, MotionConfig } from "motion/react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { Exercise, TrueFalseExercise } from "@/lib/content/types";
import { useProgress } from "@/lib/progress/provider";
import { cn, shuffle } from "@/lib/utils";

import { TrueFalseButtons } from "./answers/true-false-answer";
import { formatDuration, randomSeed } from "./grading";
import { QuestionCard, type AnswerResult } from "./question-card";
import { Stat } from "./quiz-summary";

export type GameKind = "sprint" | "association" | "ordre";

export const GAMES: { kind: GameKind; title: string; description: string; type: Exercise["type"] }[] = [
  {
    kind: "sprint",
    title: "Sprint Vrai/Faux",
    description: "60 secondes pour répondre à un maximum d'affirmations. Enchaîne les bonnes réponses.",
    type: "vrai_faux",
  },
  {
    kind: "association",
    title: "Course d'associations",
    description: "Associe les éléments le plus vite possible, série chronométrée.",
    type: "association",
  },
  {
    kind: "ordre",
    title: "Remets dans l'ordre",
    description: "Reconstitue les séquences du cours, série chronométrée.",
    type: "ordre",
  },
];

const SPRINT_MS = 60_000;
const RUN_LENGTH = 5;

export function Game({
  kind,
  pool,
  faculty,
  year,
  onExit,
}: {
  kind: GameKind;
  pool: Exercise[];
  faculty: string;
  year: string;
  onExit: () => void;
}) {
  const [round, setRound] = useState(0);
  const game = GAMES.find((item) => item.kind === kind)!;
  const items = pool.filter((item) => item.type === game.type);
  return (
    <MotionConfig reducedMotion="user">
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onExit}>
            <ArrowLeft aria-hidden />
            Jeux
          </Button>
          <h2 className="text-lg font-semibold">{game.title}</h2>
        </div>
        {kind === "sprint" ? (
          <Sprint
            key={round}
            items={items.filter((item): item is TrueFalseExercise => item.type === "vrai_faux")}
            faculty={faculty}
            year={year}
            onReplay={() => setRound((value) => value + 1)}
            onExit={onExit}
          />
        ) : (
          <TimedRun
            key={round}
            items={items}
            faculty={faculty}
            year={year}
            onReplay={() => setRound((value) => value + 1)}
            onExit={onExit}
          />
        )}
      </div>
    </MotionConfig>
  );
}

// Sprint Vrai/Faux ----------------------------------------------------------------------------

function Sprint({
  items,
  faculty,
  year,
  onReplay,
  onExit,
}: {
  items: TrueFalseExercise[];
  faculty: string;
  year: string;
  onReplay: () => void;
  onExit: () => void;
}) {
  const { store } = useProgress();
  const [deck, setDeck] = useState<TrueFalseExercise[]>([]);
  const [phase, setPhase] = useState<"ready" | "playing" | "over">("ready");
  const [index, setIndex] = useState(0);
  const [left, setLeft] = useState(SPRINT_MS);
  const [flash, setFlash] = useState<{ value: boolean; correct: boolean } | null>(null);
  const [stats, setStats] = useState({ answered: 0, correct: 0, streak: 0, best: 0 });
  const startRef = useRef(0);
  const shownRef = useRef(0);

  const start = () => {
    setDeck(shuffle(items, randomSeed()));
    setIndex(0);
    setStats({ answered: 0, correct: 0, streak: 0, best: 0 });
    setLeft(SPRINT_MS);
    startRef.current = performance.now();
    shownRef.current = startRef.current;
    setPhase("playing");
  };

  useEffect(() => {
    if (phase !== "playing") return;
    const timer = window.setInterval(() => {
      const remaining = SPRINT_MS - (performance.now() - startRef.current);
      setLeft(Math.max(0, remaining));
      if (remaining <= 0) setPhase("over");
    }, 200);
    return () => window.clearInterval(timer);
  }, [phase]);

  const exercise = deck[index];

  const pick = useCallback(
    (value: boolean) => {
      if (phase !== "playing" || flash || !exercise) return;
      const correct = value === exercise.answer;
      const now = performance.now();
      setFlash({ value, correct });
      setStats((previous) => {
        const streak = correct ? previous.streak + 1 : 0;
        return {
          answered: previous.answered + 1,
          correct: previous.correct + (correct ? 1 : 0),
          streak,
          best: Math.max(previous.best, streak),
        };
      });
      void store
        .recordAttempt({
          questionId: exercise.id,
          questionType: exercise.type,
          lessonId: exercise.lessonId,
          faculty,
          year,
          mode: "game",
          correct,
          response: { value },
          timeMs: now - shownRef.current,
          hintsUsed: 0,
        })
        .catch(() => {});
      window.setTimeout(
        () => {
          setFlash(null);
          shownRef.current = performance.now();
          if (index + 1 >= deck.length) setPhase("over");
          else setIndex(index + 1);
        },
        correct ? 450 : 900,
      );
    },
    [phase, flash, exercise, store, faculty, year, index, deck.length],
  );

  useEffect(() => {
    if (phase !== "playing") return;
    const onKey = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      const key = event.key.toLowerCase();
      if (key === "v" || key === "arrowleft") pick(true);
      if (key === "f" || key === "arrowright") pick(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, pick]);

  if (phase === "ready") {
    return (
      <Card className="flex flex-col items-center gap-4 p-6 text-center sm:p-8">
        <span className="flex size-12 items-center justify-center rounded-full bg-primary-soft text-primary">
          <Zap className="size-6" aria-hidden />
        </span>
        <p className="max-w-sm text-sm text-muted">
          {items.length} affirmation{items.length > 1 ? "s" : ""} disponible{items.length > 1 ? "s" : ""}. Réponds
          vite : 60 secondes au total. Raccourcis clavier : V = vrai, F = faux.
        </p>
        <Button size="lg" onClick={start} disabled={items.length === 0}>
          Commencer
        </Button>
      </Card>
    );
  }

  if (phase === "over") {
    const accuracy = stats.answered ? Math.round((stats.correct / stats.answered) * 100) : 0;
    return (
      <ScoreCard
        score={stats.correct}
        caption={left <= 0 ? "Temps écoulé" : "Toutes les affirmations ont été jouées"}
        stats={[
          { icon: <Target aria-hidden />, label: "Réponses", value: String(stats.answered) },
          { icon: <Target aria-hidden />, label: "Précision", value: `${accuracy} %` },
          { icon: <Flame aria-hidden />, label: "Meilleure série", value: String(stats.best) },
          { icon: <Timer aria-hidden />, label: "Temps", value: formatDuration(SPRINT_MS - left) },
        ]}
        onReplay={onReplay}
        onExit={onExit}
      />
    );
  }

  return (
    <Card className="flex flex-col gap-5 p-5 sm:p-6">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="inline-flex items-center gap-1.5 font-semibold tabular-nums">
          <Timer className="size-4 text-muted" aria-hidden />
          {Math.ceil(left / 1000)} s
        </span>
        <span className="tabular-nums text-muted">Score {stats.correct}</span>
        <motion.span
          key={stats.streak}
          initial={{ scale: stats.streak > 0 ? 1.25 : 1 }}
          animate={{ scale: 1 }}
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold tabular-nums",
            stats.streak > 0 ? "bg-highyield-soft text-highyield" : "bg-surface-muted text-muted",
          )}
        >
          <Flame className="size-3.5" aria-hidden />
          Série {stats.streak}
        </motion.span>
      </div>
      <Progress value={(left / SPRINT_MS) * 100} tone={left < 10_000 ? "highyield" : "primary"} className="h-1.5" />
      <AnimatePresence mode="wait" initial={false}>
        {exercise && (
          <motion.div
            key={exercise.id + index}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.16 }}
            className="flex min-h-24 items-center"
          >
            <p className="whitespace-pre-line text-lg font-semibold leading-snug sm:text-xl">{exercise.stem}</p>
          </motion.div>
        )}
      </AnimatePresence>
      {exercise && (
        <TrueFalseButtons
          value={flash?.value ?? null}
          onPick={pick}
          expected={flash ? exercise.answer : undefined}
        />
      )}
      <p className="sr-only" role="status">
        {flash ? (flash.correct ? "Bonne réponse" : "Réponse incorrecte") : ""}
      </p>
    </Card>
  );
}

// Timed series (association, ordering) ----------------------------------------------------------

function TimedRun({
  items,
  faculty,
  year,
  onReplay,
  onExit,
}: {
  items: Exercise[];
  faculty: string;
  year: string;
  onReplay: () => void;
  onExit: () => void;
}) {
  const [run] = useState(() => shuffle(items, randomSeed()).slice(0, RUN_LENGTH));
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<AnswerResult[]>([]);
  const [over, setOver] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(0);
  const endRef = useRef<number | null>(null);

  useEffect(() => {
    startRef.current = performance.now();
  }, []);

  useEffect(() => {
    if (over) return;
    const timer = window.setInterval(() => {
      if (endRef.current === null) setElapsed(performance.now() - startRef.current);
    }, 250);
    return () => window.clearInterval(timer);
  }, [over]);

  if (run.length === 0) {
    return <Card className="p-6 text-center text-sm text-muted">Aucune question de ce type pour le moment.</Card>;
  }

  if (over) {
    const correct = results.filter((result) => result.correct).length;
    const units = results.reduce((sum, result) => sum + result.score, 0);
    const unitsTotal = results.reduce((sum, result) => sum + result.total, 0);
    return (
      <ScoreCard
        score={correct}
        outOf={run.length}
        caption="Série terminée"
        stats={[
          { icon: <Timer aria-hidden />, label: "Temps total", value: formatDuration(elapsed) },
          {
            icon: <Timer aria-hidden />,
            label: "Par question",
            value: formatDuration(elapsed / Math.max(1, results.length)),
          },
          { icon: <Target aria-hidden />, label: "Éléments justes", value: `${units}/${unitsTotal}` },
          {
            icon: <Target aria-hidden />,
            label: "Précision",
            value: `${unitsTotal ? Math.round((units / unitsTotal) * 100) : 0} %`,
          },
        ]}
        onReplay={onReplay}
        onExit={onExit}
      />
    );
  }

  const exercise = run[index];
  return (
    <Card className="overflow-hidden">
      <div className="flex flex-col gap-2 border-b border-border bg-surface-muted/40 px-5 py-3">
        <div className="flex items-center justify-between text-xs font-medium text-muted">
          <span>
            {index + 1} / {run.length}
          </span>
          <span className="inline-flex items-center gap-1 font-semibold tabular-nums text-foreground">
            <Timer className="size-3.5 text-muted" aria-hidden />
            {formatDuration(elapsed)}
          </span>
        </div>
        <Progress value={(results.length / run.length) * 100} className="h-1.5" />
      </div>
      <div className="p-5 sm:p-6">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={exercise.id + index}
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -16 }}
            transition={{ duration: 0.2 }}
          >
            <QuestionCard
              exercise={exercise}
              mode="game"
              faculty={faculty}
              year={year}
              hints={false}
              showTimer={false}
              nextLabel={index + 1 < run.length ? "Suivant" : "Voir le score"}
              onAnswered={(result) => {
                setResults((previous) => [...previous, result]);
                if (index + 1 >= run.length) {
                  endRef.current = performance.now();
                  setElapsed(endRef.current - startRef.current);
                }
              }}
              onNext={() => (index + 1 < run.length ? setIndex(index + 1) : setOver(true))}
            />
          </motion.div>
        </AnimatePresence>
      </div>
    </Card>
  );
}

// Score card ----------------------------------------------------------------------------------

function ScoreCard({
  score,
  outOf,
  caption,
  stats,
  onReplay,
  onExit,
}: {
  score: number;
  outOf?: number;
  caption: string;
  stats: { icon: ReactNode; label: string; value: string }[];
  onReplay: () => void;
  onExit: () => void;
}) {
  return (
    <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.25 }}>
      <Card className="flex flex-col items-center gap-5 p-6 text-center sm:p-8">
        <motion.span
          initial={{ rotate: -12, scale: 0.7 }}
          animate={{ rotate: 0, scale: 1 }}
          transition={{ type: "spring", stiffness: 300, damping: 16 }}
          className="flex size-14 items-center justify-center rounded-full bg-highyield-soft text-highyield"
        >
          <Trophy className="size-7" aria-hidden />
        </motion.span>
        <div>
          <p className="text-sm text-muted">{caption}</p>
          <p className="text-5xl font-semibold tabular-nums">
            {score}
            {outOf !== undefined && <span className="text-2xl text-muted">/{outOf}</span>}
          </p>
          <p className="text-sm text-muted">bonne{score > 1 ? "s" : ""} réponse{score > 1 ? "s" : ""}</p>
        </div>
        <div className="grid w-full grid-cols-2 gap-3 text-left sm:grid-cols-4">
          {stats.map((stat) => (
            <Stat key={stat.label} {...stat} />
          ))}
        </div>
        <div className="flex flex-col-reverse gap-2 sm:flex-row">
          <Button variant="outline" size="lg" onClick={onExit}>
            Retour aux jeux
          </Button>
          <Button size="lg" onClick={onReplay}>
            <RotateCcw aria-hidden />
            Rejouer
          </Button>
        </div>
      </Card>
    </motion.div>
  );
}
