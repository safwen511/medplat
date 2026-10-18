"use client";

import { AnimatePresence, motion, MotionConfig } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import type { Exercise, TrueFalseExercise } from "@/lib/content/types";
import { useProgress } from "@/lib/progress/provider";
import { shuffle } from "@/lib/utils";

import { TrueFalseButtons } from "./answers/true-false-answer";
import { randomSeed, spokenDuration } from "./grading";
import { QuestionCard, type AnswerResult } from "./question-card";
import { TextAction, ThinBar } from "./quiet";

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
      <div className="flex flex-col gap-8">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="text-2xl">{game.title}</h2>
          <button
            type="button"
            onClick={onExit}
            className="-my-3 min-h-12 shrink-0 -mx-1 rounded-card px-1 text-sm text-muted underline decoration-border underline-offset-4 hover:text-foreground hover:decoration-current focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Quitter
          </button>
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
      <div className="flex flex-col items-start gap-6">
        <p className="text-lg leading-relaxed">
          {items.length} affirmation{items.length > 1 ? "s" : ""} disponible{items.length > 1 ? "s" : ""}. Réponds au
          plus grand nombre en 60 secondes.
        </p>
        <p className="text-sm text-muted">Au clavier : V pour vrai, F pour faux.</p>
        <Button size="lg" onClick={start} disabled={items.length === 0} className="w-full sm:w-auto sm:min-w-40">
          Commencer
        </Button>
      </div>
    );
  }

  if (phase === "over") {
    const accuracy = stats.answered ? Math.round((stats.correct / stats.answered) * 100) : 0;
    return (
      <GameOver
        sentence={`${stats.correct} bonne${stats.correct > 1 ? "s" : ""} réponse${stats.correct > 1 ? "s" : ""} sur ${stats.answered}, en ${spokenDuration(SPRINT_MS - left)}.`}
        detail={`${left <= 0 ? "Temps écoulé." : "Toutes les affirmations ont été jouées."} Précision ${accuracy} %, meilleure série ${stats.best}.`}
        onReplay={onReplay}
        onExit={onExit}
      />
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3 text-sm tabular-nums text-muted">
          <span>{Math.ceil(left / 1000)} s</span>
          <span>
            {stats.correct} juste{stats.correct > 1 ? "s" : ""}
            {stats.streak > 1 && ` · série de ${stats.streak}`}
          </span>
        </div>
        <ThinBar value={left / SPRINT_MS} label="Temps restant" />
      </div>
      <AnimatePresence mode="wait" initial={false}>
        {exercise && (
          <motion.div
            key={exercise.id + index}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
            className="flex min-h-28 items-center"
          >
            <p className="whitespace-pre-line font-serif text-[1.375rem] font-medium leading-snug sm:text-[1.5rem]">
              {exercise.stem}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
      {exercise && (
        <TrueFalseButtons value={flash?.value ?? null} onPick={pick} expected={flash ? exercise.answer : undefined} />
      )}
      <p className="sr-only" role="status">
        {flash ? (flash.correct ? "Bonne réponse" : "Réponse incorrecte") : ""}
      </p>
    </div>
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
    return <p className="text-base text-muted">Aucune question de ce type pour le moment.</p>;
  }

  if (over) {
    const correct = results.filter((result) => result.correct).length;
    const units = results.reduce((sum, result) => sum + result.score, 0);
    const unitsTotal = results.reduce((sum, result) => sum + result.total, 0);
    return (
      <GameOver
        sentence={`${correct} bonne${correct > 1 ? "s" : ""} réponse${correct > 1 ? "s" : ""} sur ${run.length}, en ${spokenDuration(elapsed)}.`}
        detail={`${units} élément${units > 1 ? "s" : ""} bien placé${units > 1 ? "s" : ""} sur ${unitsTotal}.`}
        onReplay={onReplay}
        onExit={onExit}
      />
    );
  }

  const exercise = run[index];
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between text-sm tabular-nums text-muted">
          <span>
            Question {index + 1} / {run.length}
          </span>
          <span>{spokenDuration(elapsed)}</span>
        </div>
        <ThinBar value={results.length / run.length} />
      </div>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={exercise.id + index}
          initial={{ opacity: 0, x: 12 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -12 }}
          transition={{ duration: 0.18 }}
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
  );
}

// End of a game --------------------------------------------------------------------------------

function GameOver({
  sentence,
  detail,
  onReplay,
  onExit,
}: {
  sentence: string;
  detail: string;
  onReplay: () => void;
  onExit: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col gap-8"
      role="status"
    >
      <div className="flex flex-col gap-3">
        <h3 className="text-2xl">Partie terminée</h3>
        <p className="text-lg leading-relaxed">{sentence}</p>
        <p className="text-base text-muted">{detail}</p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row-reverse sm:items-center sm:justify-between">
        <Button size="lg" onClick={onReplay} className="w-full sm:w-auto sm:min-w-40">
          Rejouer
        </Button>
        <TextAction onClick={onExit}>Retour aux mini-jeux</TextAction>
      </div>
    </motion.div>
  );
}
