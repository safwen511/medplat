"use client";

import { ArrowLeft, ArrowRight, BookOpen, Flag, Layers, Lightbulb, Sparkles } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { finishWelcome, leave } from "@/app/acces/actions";
import { Button } from "@/components/ui/button";
import { StatTile } from "@/components/ui/stat-tile";
import { useProgress } from "@/lib/progress/provider";

export interface WelcomeMember {
  firstName: string;
  gender: "m" | "f";
  year: "dcem1" | "dcem2";
}

export interface WelcomeStats {
  lessons: number;
  exercises: number;
  certifs: string[];
  yearLabel: string;
}

interface Slide {
  icon: ReactNode;
  title: string;
  body: ReactNode;
}

function slides(member: WelcomeMember, stats: WelcomeStats): Slide[] {
  const g = (masculine: string, feminine: string) => (member.gender === "f" ? feminine : masculine);
  return [
    {
      icon: <Sparkles aria-hidden />,
      title: `${g("Bienvenu", "Bienvenue")} ${member.firstName}.`,
      body: (
        <p>
          Tu es {g("l'un de nos deux premiers testeurs", "l'une de nos deux premières testeuses")}. MedPlat est
          encore en construction, et ton avis va décider de la suite.
        </p>
      ),
    },
    {
      icon: <Layers aria-hidden />,
      title: "Tes certifs sont des dossiers.",
      body: (
        <p>
          Dans chaque dossier, un cours est une carte. Touche-la pour la retourner : ta progression, le cours à
          lire, et ses exercices.
        </p>
      ),
    },
    {
      icon: <Lightbulb aria-hidden />,
      title: "Des exercices qui t'apprennent à raisonner.",
      body: (
        <p>
          QCM, QRM, vrai/faux, textes à trous, associations, mises en ordre, classements, calculs. Bloqué·e ? Trois
          indices, du plus général au plus précis, puis une explication après chaque réponse.
        </p>
      ),
    },
    {
      icon: <BookOpen aria-hidden />,
      title: "Déjà prêt pour toi.",
      body: (
        <div className="flex flex-col gap-6">
          <div className="mx-auto grid w-full max-w-xl grid-cols-3 gap-3 text-left">
            <StatTile value={stats.lessons} label="cours" />
            <StatTile value={stats.exercises} label="exercices" />
            <StatTile value={stats.certifs.length} label="certifs" />
          </div>
          <p>
            {stats.yearLabel} : {stats.certifs.join(", ")}. Les cours choisis sont ceux qui tombent le plus souvent à
            l&apos;examen.
          </p>
        </div>
      ),
    },
    {
      icon: <Flag aria-hidden />,
      title: "Ce qui n'est pas encore là.",
      body: (
        <ul className="mx-auto flex max-w-2xl flex-col gap-2 text-left">
          <li>— La plupart des cours : ils arrivent par vagues, les plus importants d&apos;abord.</li>
          <li>— Les comptes : ta progression reste sur cet appareil pour l&apos;instant.</li>
          <li>— Connecter : les amis, leur progression, les défis.</li>
          <li>— La relecture par un médecin : tout est en brouillon, signale chaque erreur.</li>
        </ul>
      ),
    },
    {
      icon: <Sparkles aria-hidden />,
      title: "On commence ?",
      body: (
        <p>
          Révise comme d&apos;habitude et dis-nous ce qui t&apos;aide, ce qui te gêne et ce qui te manque. Tu
          pourras revoir cet accueil depuis Mon espace.
        </p>
      ),
    },
  ];
}

export function WelcomeSlides({ member, stats, next }: { member: WelcomeMember; stats: WelcomeStats; next: string }) {
  const all = slides(member, stats);
  const [index, setIndex] = useState(0);
  const [direction, setDirection] = useState(1);
  const [pending, setPending] = useState(false);
  const reduce = useReducedMotion();
  const router = useRouter();
  const { store } = useProgress();
  const touchStart = useRef<number | null>(null);
  const last = index === all.length - 1;

  const go = useCallback(
    (step: number) => {
      setDirection(step);
      setIndex((current) => Math.min(all.length - 1, Math.max(0, current + step)));
    },
    [all.length],
  );

  const start = async () => {
    setPending(true);
    const current = await store.profile();
    await store.saveProfile({
      displayName: current?.displayName || member.firstName,
      faculty: "sfax",
      year: member.year,
      examDate: current?.examDate ?? null,
      onboarded: true,
      dailyGoal: current?.dailyGoal ?? 20,
    });
    await finishWelcome();
    router.push(next);
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight") go(1);
      if (event.key === "ArrowLeft") go(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  const slide = all[index];
  const offset = reduce ? 0 : 24 * direction;
  return (
    <div
      className="fixed inset-0 z-[60] flex flex-col overflow-y-auto bg-background"
      style={{ backgroundImage: "radial-gradient(ellipse at 50% 30%, var(--primary-soft), transparent 65%)" }}
      onTouchStart={(event) => (touchStart.current = event.touches[0].clientX)}
      onTouchEnd={(event) => {
        if (touchStart.current === null) return;
        const delta = event.changedTouches[0].clientX - touchStart.current;
        if (Math.abs(delta) > 60) go(delta < 0 ? 1 : -1);
        touchStart.current = null;
      }}
    >
      <div className="flex items-center justify-between px-6 py-5 text-sm text-muted">
        <span className="font-heading text-base font-semibold text-foreground">MedPlat</span>
        {!last && (
          <button type="button" onClick={() => go(all.length)} className="min-h-12 px-2 underline-offset-4 hover:underline">
            Passer
          </button>
        )}
      </div>

      <div className="flex flex-1 items-center justify-center px-6">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.section
            key={index}
            aria-live="polite"
            initial={{ opacity: 0, x: offset }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -offset }}
            transition={{ duration: reduce ? 0 : 0.3, ease: [0.2, 0.8, 0.2, 1] }}
            className="flex w-full max-w-4xl flex-col items-center gap-8 text-center"
          >
            <span className="flex size-16 items-center justify-center rounded-full bg-primary-soft text-primary shadow-glow [&_svg]:size-7">
              {slide.icon}
            </span>
            <h1 className="text-4xl leading-tight sm:text-6xl">{slide.title}</h1>
            <div className="max-w-3xl text-lg leading-relaxed text-muted sm:text-2xl">{slide.body}</div>
            {index === 0 && (
              <form action={leave}>
                <button type="submit" className="min-h-12 text-sm text-muted underline underline-offset-4 hover:text-foreground">
                  Ce n&apos;est pas moi
                </button>
              </form>
            )}
          </motion.section>
        </AnimatePresence>
      </div>

      <footer className="flex flex-col items-center gap-6 px-6 py-8">
        <div className="flex gap-2" role="tablist" aria-label="Étapes de l'accueil">
          {all.map((_, dot) => (
            <button
              key={dot}
              type="button"
              role="tab"
              aria-selected={dot === index}
              aria-label={`Étape ${dot + 1} sur ${all.length}`}
              onClick={() => go(dot - index)}
              className="flex h-12 w-6 items-center justify-center"
            >
              <span
                className={`h-2 rounded-full transition-all duration-200 ${dot === index ? "w-6 bg-primary shadow-glow" : "w-2 bg-border"}`}
              />
            </button>
          ))}
        </div>
        <div className="flex w-full max-w-md items-center justify-between gap-4">
          <Button variant="ghost" size="lg" onClick={() => go(-1)} disabled={index === 0}>
            <ArrowLeft aria-hidden /> Retour
          </Button>
          {last ? (
            <Button size="lg" onClick={start} disabled={pending} className="shadow-glow">
              {pending ? "Ouverture…" : "Commencer"} <ArrowRight aria-hidden />
            </Button>
          ) : (
            <Button size="lg" onClick={() => go(1)} className="shadow-glow">
              Suivant <ArrowRight aria-hidden />
            </Button>
          )}
        </div>
      </footer>
    </div>
  );
}
