import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { WelcomeSlides } from "@/components/welcome/welcome-slides";
import { ACCESS_COOKIE, verifyMember } from "@/lib/access";
import { yearIndex } from "@/lib/content/load";

export const metadata = { title: "Bienvenue" };

const YEAR_LABEL = { dcem1: "DCEM1", dcem2: "DCEM2" } as const;

async function WelcomeForSession({ searchParams }: { searchParams: PageProps<"/bienvenue">["searchParams"] }) {
  const member = await verifyMember((await cookies()).get(ACCESS_COOKIE)?.value);
  if (!member) redirect("/acces");
  const { suite } = await searchParams;
  const next =
    typeof suite === "string" && suite.startsWith("/") && !suite.startsWith("//") ? suite : `/sfax/${member.year}`;

  const index = yearIndex("sfax", member.year);
  const ready = (index?.certifs ?? []).flatMap((certif) =>
    certif.modules.flatMap((module) => module.lessons).filter((lesson) => lesson.available),
  );
  const certifs = (index?.certifs ?? [])
    .filter((certif) => certif.modules.some((module) => module.lessons.some((lesson) => lesson.available)))
    .map((certif) => certif.title.replace(/^Certificat (intégré )?(de |d'|des )?/i, ""));
  const stats = {
    lessons: ready.length,
    exercises: ready.reduce((sum, lesson) => sum + lesson.exerciseCount, 0),
    certifs,
    yearLabel: YEAR_LABEL[member.year],
  };
  return (
    <WelcomeSlides
      member={{ firstName: member.firstName, gender: member.gender, year: member.year }}
      stats={stats}
      next={next}
    />
  );
}

export default function Bienvenue(props: PageProps<"/bienvenue">) {
  return (
    <Suspense fallback={null}>
      <WelcomeForSession searchParams={props.searchParams} />
    </Suspense>
  );
}
