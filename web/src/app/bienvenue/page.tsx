import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { ACCESS_COOKIE, verifyMember, type Member } from "@/lib/access";
import { yearIndex } from "@/lib/content/load";

import { leave } from "../acces/actions";
import { StartButton } from "./start-button";

export const metadata = { title: "Bienvenue" };

const YEAR_LABEL = { dcem1: "DCEM1 (3e année)", dcem2: "DCEM2 (4e année)" } as const;

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3 rounded-card border border-border bg-surface p-6">
      <h2 className="text-xl">{title}</h2>
      <div className="flex flex-col gap-2 text-[1.0625rem] leading-relaxed">{children}</div>
    </section>
  );
}

function Welcome({ member, next }: { member: Member; next: string }) {
  const g = (masculine: string, feminine: string) => (member.gender === "f" ? feminine : masculine);
  const index = yearIndex("sfax", member.year);
  const lessons =
    index?.certifs.flatMap((certif) => certif.modules.flatMap((module) => module.lessons)) ?? [];
  const ready = lessons.filter((lesson) => lesson.available);
  const exercises = ready.reduce((sum, lesson) => sum + lesson.exerciseCount, 0);
  const certifsReady = (index?.certifs ?? []).filter((certif) =>
    certif.modules.some((module) => module.lessons.some((lesson) => lesson.available)),
  );
  const home = next || `/sfax/${member.year}`;

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-8 py-8">
      <header className="flex flex-col gap-3">
        <p className="text-sm text-muted">Bêta privée · {YEAR_LABEL[member.year]}</p>
        <h1 className="text-3xl leading-tight sm:text-4xl">
          {g("Bienvenu", "Bienvenue")} {member.firstName} !
        </h1>
        <p className="text-lg text-muted">
          Merci d&apos;être {g("l'un de nos deux premiers testeurs", "l'une de nos deux premières testeuses")}
          . MedPlat est encore en construction, et ton avis va décider de la suite.
        </p>
      </header>

      <Panel title="Comment ça marche">
        <p>
          Chaque certif de ton année est un <strong>dossier</strong>. Dedans, chaque cours est une{" "}
          <strong>carte</strong> : touche-la pour la retourner et voir ta progression, puis lance ses
          exercices.
        </p>
        <p>
          Les exercices sont tirés des cours de la faculté : QCM, QRM, vrai/faux, textes à trous,
          associations, mises en ordre, classements et calculs. Si tu bloques, demande un{" "}
          <strong>indice</strong> (il y en a trois, du plus général au plus précis) ; après ta réponse, une
          explication te montre le raisonnement.
        </p>
        <p>
          Ta <strong>fiche de suivi</strong> (Non lu → Lu → Révisé → Maîtrisé) et tes statistiques sont dans{" "}
          <strong>Mon espace</strong>.
        </p>
      </Panel>

      <Panel title="Ce qui est déjà prêt">
        <p>
          {ready.length} cours de ton année avec {exercises} exercices
          {certifsReady.length > 0 && (
            <>
              {" "}
              (
              {certifsReady
                .map((certif) => certif.title.replace(/^Certificat (intégré )?(de |d'|des )?/i, ""))
                .join(", ")}
              )
            </>
          )}
          , choisis parmi les plus souvent tombés à l&apos;examen.
        </p>
        <p>Les mini-jeux (sprint vrai/faux, associations, remise en ordre) et le mode quiz par certif.</p>
      </Panel>

      <Panel title="Ce qui n'est pas encore là">
        <ul className="list-disc space-y-1 pl-5">
          <li>La plupart des cours : ils arrivent par vagues, les plus importants d&apos;abord.</li>
          <li>
            Les comptes : ta progression reste <strong>sur cet appareil</strong> pour l&apos;instant.
          </li>
          <li>Connecter : les amis, leur progression et les défis entre amis.</li>
          <li>
            La relecture par un médecin : tout est encore en brouillon. Si tu vois une erreur, touche «
            Signaler une erreur » sous la question.
          </li>
        </ul>
      </Panel>

      <Panel title="Comment nous aider">
        <p>
          Révise comme d&apos;habitude, et dis-nous ce qui t&apos;aide, ce qui te gêne et ce qui te manque.
          Chaque signalement compte.
        </p>
      </Panel>

      <div className="flex flex-wrap items-center gap-6">
        <StartButton firstName={member.firstName} year={member.year} href={home} />
        <form action={leave}>
          <button
            type="submit"
            className="text-sm text-muted underline underline-offset-4 hover:text-foreground"
          >
            Ce n&apos;est pas moi
          </button>
        </form>
      </div>
      <p className="text-sm text-muted">
        Tu pourras relire ce message depuis{" "}
        <Link href="/espace" className="underline underline-offset-4">
          Mon espace
        </Link>
        .
      </p>
    </div>
  );
}

async function WelcomeForSession({
  searchParams,
}: {
  searchParams: PageProps<"/bienvenue">["searchParams"];
}) {
  const member = await verifyMember((await cookies()).get(ACCESS_COOKIE)?.value);
  if (!member) redirect("/acces");
  const { suite } = await searchParams;
  const next = typeof suite === "string" && suite.startsWith("/") && !suite.startsWith("//") ? suite : "";
  return <Welcome member={member} next={next} />;
}

export default function Bienvenue(props: PageProps<"/bienvenue">) {
  return (
    <Suspense fallback={null}>
      <WelcomeForSession searchParams={props.searchParams} />
    </Suspense>
  );
}
