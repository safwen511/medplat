import { ArrowRight, Moon, PenLine, WifiOff } from "lucide-react";
import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

import { CountUp } from "@/components/landing/count-up";
import { CitationDemo, ProgressDemo, QuizDemo } from "@/components/landing/demos";
import { HeroDeck } from "@/components/landing/hero-deck";
import { ParallaxPhoto } from "@/components/landing/photo";
import { LogoMark } from "@/components/layout/logo";
import { Button } from "@/components/ui/button";
import { Reveal } from "@/components/ui/reveal";
import { availableYears, yearIndex } from "@/lib/content/load";
import { cn } from "@/lib/utils";

/** Published figures, read from the content at build time. */
function figures() {
  let lessons = 0;
  let exercises = 0;
  let certifs = 0;
  for (const { faculty, year } of availableYears()) {
    for (const certif of yearIndex(faculty, year)?.certifs ?? []) {
      const ready = certif.modules.flatMap((mod) => mod.lessons).filter((lesson) => lesson.available);
      lessons += ready.length;
      exercises += ready.reduce((sum, lesson) => sum + lesson.exerciseCount, 0);
      if (ready.length) certifs++;
    }
  }
  return { lessons, exercises, certifs, years: availableYears().length };
}

const delay = (ms: number) => ({ animationDelay: `${ms}ms` }) as CSSProperties;

function Feature({
  index,
  title,
  children,
  demo,
  reverse = false,
}: {
  index: string;
  title: string;
  children: ReactNode;
  demo: ReactNode;
  reverse?: boolean;
}) {
  return (
    <div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-16">
      <Reveal className={cn("flex flex-col gap-4", reverse && "lg:order-2")}>
        <p className="eyebrow">{index}</p>
        <h2 className="text-3xl leading-tight sm:text-[2.75rem]">{title}</h2>
        <div className="max-w-lg text-lg leading-relaxed text-muted">{children}</div>
      </Reveal>
      <Reveal delay={0.1}>{demo}</Reveal>
    </div>
  );
}

/** Public landing: expressive, everything else in the site stays calm. */
export default function Home() {
  const stats = figures();
  return (
    <div className="flex flex-col">
      <section className="grid items-center gap-6 pt-4 pb-12 lg:min-h-[calc(100svh-9rem)] lg:grid-cols-[1.05fr_1fr] lg:gap-10 lg:pt-0">
        <div className="flex flex-col items-start gap-7">
          <p className="eyebrow rise-in">Faculté de Médecine de Sfax · DCEM1 · DCEM2</p>
          <h1 className="rise-in text-[2.75rem] leading-[1.02] sm:text-6xl lg:text-[4.25rem]" style={delay(70)}>
            Tes certifs,
            <br />
            <span className="bg-gradient-to-r from-primary to-foreground/70 bg-clip-text text-transparent">
              enfin en ordre.
            </span>
          </h1>
          <p className="rise-in max-w-xl text-lg leading-relaxed text-muted sm:text-xl" style={delay(140)}>
            Chaque cours reconstruit à partir des documents de la faculté, chaque phrase reliée à sa page. Des
            exercices pour t&apos;entraîner, un suivi pour savoir où tu en es.
          </p>
          <div className="rise-in flex flex-wrap items-center gap-3" style={delay(210)}>
            <Button asChild size="lg" className="shadow-glow">
              <Link href="/acces">
                Entrer avec mon code <ArrowRight aria-hidden />
              </Link>
            </Button>
            <Button asChild size="lg" variant="ghost">
              <a href="#comment">Comment ça marche</a>
            </Button>
          </div>
          <p className="rise-in text-sm text-subtle" style={delay(280)}>
            Bêta privée, sur invitation · gratuite
          </p>
        </div>
        <div className="relative" style={delay(180)}>
          <ParallaxPhoto
            src="/landing/stethoscope.webp"
            sizes="(min-width: 1024px) 40vw, 90vw"
            priority
            drift={40}
            className="landing-photo absolute inset-x-[6%] -top-4 -bottom-2 rounded-[28px] border border-border [mask-image:linear-gradient(to_bottom,black_55%,transparent)] sm:inset-x-[12%] lg:inset-x-[4%]"
          />
          <div className="rise-in relative">
            <HeroDeck />
          </div>
        </div>
      </section>

      <section
        aria-label="En chiffres"
        className="grid grid-cols-2 gap-x-6 gap-y-8 border-y border-border py-10 sm:grid-cols-4 sm:py-12"
      >
        {[
          { value: stats.lessons, label: "cours reconstruits" },
          { value: stats.exercises, label: "exercices avec correction" },
          { value: stats.certifs, label: "certifs couverts" },
          { value: stats.years, label: "années d'études" },
        ].map((item) => (
          <div key={item.label} className="flex flex-col gap-1">
            <CountUp value={item.value} className="numeral text-4xl font-semibold sm:text-5xl" />
            <span className="text-sm text-muted">{item.label}</span>
          </div>
        ))}
      </section>

      <section id="comment" aria-label="Comment ça marche" className="flex scroll-mt-24 flex-col gap-24 py-20 sm:gap-32 sm:py-28">
        <Feature index="01 · Des cours sourcés" title="Chaque phrase sait d'où elle vient." demo={<CitationDemo />}>
          Les cours sont reconstruits à partir des diapositives et des polycopiés officiels. Chaque élément renvoie à
          sa page source, et chaque chiffre y est vérifié.
        </Feature>
        <Feature index="02 · Des exercices" title="Des questions qui font raisonner." demo={<QuizDemo />} reverse>
          QCM, QRM, vrai ou faux, textes à trous, associations, mises en ordre, calculs. Trois indices si tu bloques,
          une explication après chaque réponse, et le chemin vers la page du cours.
        </Feature>
        <Feature index="03 · Ton suivi" title="Tu sais toujours où tu en es." demo={<ProgressDemo />}>
          Un objectif par jour, ta série, ta précision par certif et les cours qui te résistent, pour réviser ce
          qui compte vraiment avant l&apos;examen.
        </Feature>
      </section>

      <section
        aria-labelledby="tablette"
        className="relative mx-[calc(50%-50vw)] mb-20 overflow-hidden py-24 sm:py-32 lg:py-40"
      >
        <ParallaxPhoto
          src="/landing/desk.webp"
          sizes="100vw"
          drift={90}
          className="absolute inset-0 hidden [mask-image:linear-gradient(to_bottom,transparent,black_22%,black_78%,transparent)] sm:block"
          imageClassName="object-[75%_50%]"
        />
        <ParallaxPhoto
          src="/landing/desk-tall.webp"
          sizes="100vw"
          drift={60}
          className="absolute inset-0 [mask-image:linear-gradient(to_bottom,transparent,black_18%,black_82%,transparent)] sm:hidden"
          imageClassName="object-[70%_50%]"
        />
        <div
          aria-hidden
          className="absolute inset-0 bg-gradient-to-r from-background via-background/85 to-background/5 max-sm:hidden"
        />
        <div aria-hidden className="absolute inset-0 bg-background/75 sm:hidden" />
        <div className="relative mx-auto flex max-w-6xl flex-col gap-10 px-4 sm:px-6">
          <Reveal className="flex max-w-xl flex-col gap-4">
            <p className="eyebrow">04 · Pensé pour réviser</p>
            <h2 id="tablette" className="text-3xl leading-tight sm:text-[2.75rem]">
              Ta tablette, ton stylet, tes surligneurs.
            </h2>
            <p className="text-lg leading-relaxed text-muted">
              MedPlat a été dessiné pour la façon dont tu révises vraiment : sur une tablette, un stylet à la
              main, des heures d&apos;affilée.
            </p>
          </Reveal>
          <ul className="grid max-w-xl gap-3">
            {[
              {
                icon: PenLine,
                title: "Tablette et stylet",
                text: "Survole une carte au stylet pour la voir bouger, touche-la pour la retourner.",
              },
              { icon: Moon, title: "Des heures sans fatigue", text: "Thème sombre ou clair, lecture large et calme." },
              {
                icon: WifiOff,
                title: "Ta progression chez toi",
                text: "Pendant la bêta, tout reste sur ton appareil. Rien à installer.",
              },
            ].map((item, index) => (
              <li key={item.title}>
                <Reveal delay={0.1 + index * 0.08}>
                  <div className="flex items-start gap-4 rounded-panel border border-border bg-background/60 p-5 backdrop-blur-md transition-colors duration-200 hover:border-border-strong">
                    <item.icon className="mt-0.5 size-5 shrink-0 text-primary" strokeWidth={1.6} aria-hidden />
                    <span className="flex flex-col gap-0.5">
                      <span className="font-heading font-semibold">{item.title}</span>
                      <span className="text-muted">{item.text}</span>
                    </span>
                  </div>
                </Reveal>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <Reveal>
        <section className="panel grain relative mb-10 overflow-hidden px-6 py-16 text-center sm:py-20">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0"
            style={{ background: "radial-gradient(60% 90% at 50% 0%, var(--primary-soft), transparent 70%)" }}
          />
          <div className="relative flex flex-col items-center gap-6">
            <h2 className="text-3xl sm:text-5xl">Prêt·e pour ton prochain certif ?</h2>
            <p className="max-w-md text-lg text-muted">Entre ton code d&apos;accès personnel et commence.</p>
            <Button asChild size="lg" className="shadow-glow">
              <Link href="/acces">
                Entrer avec mon code <ArrowRight aria-hidden />
              </Link>
            </Button>
          </div>
        </section>
      </Reveal>

      <footer className="flex flex-col items-start justify-between gap-3 border-t border-border py-8 text-sm text-muted sm:flex-row sm:items-center">
        <span className="inline-flex items-center gap-2">
          <LogoMark className="size-5" /> MedPlat
        </span>
        <p>MedPlat est un projet bêta, indépendant de la Faculté de Médecine de Sfax.</p>
      </footer>
    </div>
  );
}
