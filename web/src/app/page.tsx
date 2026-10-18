import { BookOpenCheck, Brain, ChartLine, Lightbulb } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const FEATURES = [
  {
    icon: BookOpenCheck,
    title: "Des cours clairs",
    text: "La structure de la faculté, l'essentiel mis en avant, chaque phrase reliée à sa source.",
  },
  {
    icon: Brain,
    title: "Des QCM qui apprennent",
    text: "QCM, QRM, vrai/faux, associations… corrigés en vert et en rouge, avec explication.",
  },
  {
    icon: Lightbulb,
    title: "Apprendre à raisonner",
    text: "Des indices en trois étapes pour savoir aborder une question, pas seulement la réponse.",
  },
  {
    icon: ChartLine,
    title: "Ta progression",
    text: "Précision, temps de réflexion, fiche de suivi et compte à rebours avant le certif.",
  },
];

export default function Home() {
  return (
    <div className="flex flex-col gap-12 py-6">
      <section className="flex flex-col items-start gap-5">
        <span className="rounded-full bg-primary-soft px-3 py-1 text-xs font-medium text-primary">
          Faculté de Médecine de Sfax · DCEM1 et DCEM2
        </span>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl">
          Révise tes certifs avec des cours clairs et des QCM qui t&apos;apprennent à raisonner.
        </h1>
        <p className="max-w-2xl text-lg text-muted">
          Tous les cours de ton année, réorganisés à partir des diapos et du polycopié, avec les
          questions des examens en ligne de mire.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button asChild size="lg">
            <Link href="/connexion">Commencer</Link>
          </Button>
        </div>
      </section>
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <Card key={title}>
            <CardHeader>
              <Icon className="size-6 text-primary" aria-hidden />
              <CardTitle>{title}</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>{text}</CardDescription>
            </CardContent>
          </Card>
        ))}
      </section>
    </div>
  );
}
