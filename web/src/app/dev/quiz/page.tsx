import { FeedbackPreview } from "@/components/quiz/dev-preview";
import { fixtureExercises, fixtureIndex } from "@/components/quiz/fixtures";
import { TYPE_LABELS } from "@/components/quiz/grading";
import { QuestionPlayer } from "@/components/quiz/question-player";
import { QuizSetup } from "@/components/quiz/quiz-setup";
import type { Exercise } from "@/lib/content/types";

export const metadata = { title: "Dev · Quiz", robots: { index: false, follow: false } };

const TYPES = Object.keys(TYPE_LABELS) as Exercise["type"][];

/** Development page: every exercise type with placeholder fixtures (no medical content). */
export default function DevQuizPage() {
  const { faculty, year } = fixtureIndex;
  return (
    <div className="mx-auto flex w-full max-w-[40rem] flex-col gap-20">
      <header className="flex flex-col gap-1">
        <p className="text-sm text-muted">Développement</p>
        <h1 className="text-3xl">Quiz : banc d&apos;essai</h1>
        <p className="text-sm text-muted">
          {fixtureExercises.length} questions de démonstration (2 par type), sans contenu médical. Les tentatives sont
          enregistrées dans le stockage de progression actif.
        </p>
        <nav aria-label="Sections" className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
          <a className="text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-current" href="#serie">Série complète</a>
          <a className="text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-current" href="#types">Par type</a>
          <a className="text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-current" href="#corrections">Corrections</a>
          <a className="text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-current" href="#configuration">Configuration et mini-jeux</a>
          <a className="text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-current" href="#vide">État vide</a>
        </nav>
      </header>

      <section id="serie" className="flex scroll-mt-20 flex-col gap-4">
        <h2 className="text-2xl">Série complète</h2>
        <QuestionPlayer exercises={fixtureExercises} mode="quiz" faculty={faculty} year={year} />
      </section>

      <section id="types" className="flex scroll-mt-20 flex-col gap-16">
        <h2 className="text-2xl">Par type</h2>
        {TYPES.map((type) => (
          <div key={type} className="flex flex-col gap-4">
            <h3 className="font-sans text-sm font-normal text-muted">{TYPE_LABELS[type]}</h3>
            <QuestionPlayer
              exercises={fixtureExercises.filter((item) => item.type === type)}
              mode="lesson"
              faculty={faculty}
              year={year}
            />
          </div>
        ))}
      </section>

      <section id="corrections" className="flex scroll-mt-20 flex-col gap-4">
        <h2 className="text-2xl">Corrections (réponse de démonstration partiellement fausse)</h2>
        <FeedbackPreview exercises={TYPES.map((type) => fixtureExercises.find((item) => item.type === type)!)} />
      </section>

      <section id="configuration" className="flex scroll-mt-20 flex-col gap-4">
        <h2 className="text-2xl">Configuration et mini-jeux</h2>
        <QuizSetup index={fixtureIndex} pool={fixtureExercises} />
      </section>

      <section id="vide" className="flex scroll-mt-20 flex-col gap-4">
        <h2 className="text-2xl">État vide</h2>
        <QuizSetup index={fixtureIndex} pool={[]} />
      </section>
    </div>
  );
}
