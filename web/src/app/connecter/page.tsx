import { ArrowRight, Heart, LineChart, Lock, Trophy, UserPlus } from "lucide-react";

import { StudyLink } from "@/components/layout/study-link";
import { Reveal } from "@/components/ui/reveal";

export const metadata = { title: "Connecter" };

const COMING = [
  { icon: UserPlus, title: "Tes amis de promo", text: "Sur invitation, rien d'autre." },
  { icon: LineChart, title: "Leur progression", text: "S'ils choisissent de la partager." },
  { icon: Heart, title: "Publications et « j'aime »", text: "Entre amis, autour des cours." },
  { icon: Trophy, title: "Défis", text: "Sur un certificat ou un cours, à deux ou en groupe." },
];

/** Placeholder for the upcoming social space: what is coming, no fake data. */
export default function ConnecterPage() {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-14 py-6 sm:py-12">
      <div className="flex flex-col items-start gap-5">
        <span className="rise-in inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 text-xs text-muted">
          <span aria-hidden className="size-1.5 rounded-full bg-highyield" /> Bientôt
        </span>
        <h1 className="rise-in max-w-2xl text-4xl leading-[1.08] sm:text-6xl" style={{ animationDelay: "60ms" }}>
          Réviser ensemble, à ton rythme.
        </h1>
        <p className="rise-in max-w-xl text-lg text-muted text-pretty" style={{ animationDelay: "120ms" }}>
          Connecter n&apos;est pas encore ouvert. Il réunira ta promo au même endroit que tes cours.
        </p>
      </div>

      <section aria-labelledby="a-venir" className="flex flex-col gap-6">
        <h2 id="a-venir" className="eyebrow">
          Ce qui arrive
        </h2>
        <ul className="grid gap-3 sm:grid-cols-2">
          {COMING.map((item, index) => (
            <li key={item.title}>
              <Reveal delay={index * 0.06}>
                <div className="flex h-full items-start gap-4 rounded-panel border border-border bg-surface/60 p-5 transition-colors duration-200 hover:border-border-strong hover:bg-surface">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary">
                    <item.icon className="size-5" strokeWidth={1.6} aria-hidden />
                  </span>
                  <span className="flex flex-col gap-0.5">
                    <span className="font-heading font-semibold">{item.title}</span>
                    <span className="text-muted">{item.text}</span>
                  </span>
                </div>
              </Reveal>
            </li>
          ))}
        </ul>
        <p className="flex items-center gap-2 text-muted">
          <Lock className="size-4 shrink-0" strokeWidth={1.6} aria-hidden />
          Rien ne sera partagé par défaut : tu choisiras qui voit quoi.
        </p>
      </section>

      <StudyLink className="group inline-flex h-12 items-center gap-2 self-start rounded-full border border-border px-5 font-medium transition-colors hover:border-border-strong hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        Retour à Étudier
        <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-0.5" strokeWidth={1.5} aria-hidden />
      </StudyLink>
    </div>
  );
}
