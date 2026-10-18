import { ArrowRight } from "lucide-react";

import { StudyLink } from "@/components/layout/study-link";

export const metadata = { title: "Connecter" };

const COMING = [
  "Tes amis de promo, sur invitation.",
  "Leur progression, s'ils choisissent de la partager.",
  "Des publications et des « j'aime » entre amis.",
  "Des défis sur un certificat ou un cours.",
];

/** Placeholder for the upcoming social space: a short note on what is coming, no fake data. */
export default function ConnecterPage() {
  return (
    <div className="mx-auto flex max-w-[640px] flex-col gap-10 py-8 sm:py-16">
      <div className="flex flex-col gap-3">
        <p className="text-sm text-muted">Bientôt</p>
        <h1 className="text-3xl leading-tight sm:text-4xl">Réviser ensemble, à ton rythme.</h1>
        <p className="text-lg text-muted text-pretty">
          Connecter n&apos;est pas encore ouvert. Il réunira ta promo au même endroit que tes cours.
        </p>
      </div>

      <section aria-labelledby="a-venir" className="flex flex-col gap-4">
        <h2 id="a-venir" className="text-xl">
          Ce qui arrive
        </h2>
        <ul className="flex flex-col gap-2 pl-5 marker:text-muted [list-style:disc]">
          {COMING.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p className="text-muted">Rien ne sera partagé par défaut : tu choisiras qui voit quoi.</p>
      </section>

      <StudyLink className="inline-flex h-12 items-center gap-2 self-start rounded-card font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        Retour à Étudier
        <ArrowRight className="size-4" strokeWidth={1.5} aria-hidden />
      </StudyLink>
    </div>
  );
}
