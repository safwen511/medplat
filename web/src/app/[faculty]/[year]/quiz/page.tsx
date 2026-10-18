import { notFound } from "next/navigation";
import { Suspense } from "react";

import { QuizSetup } from "@/components/quiz/quiz-setup";
import { availableLessonIds, availableYears, exercises, yearIndex } from "@/lib/content/load";

export function generateStaticParams() {
  return availableYears();
}

export const metadata = { title: "Quiz" };

async function QuizPageContent(props: PageProps<"/[faculty]/[year]/quiz">) {
  const { faculty, year } = await props.params;
  const index = yearIndex(faculty, year);
  if (!index) notFound();
  const pool = availableLessonIds(faculty, year).flatMap(
    (lessonId) => exercises(faculty, year, lessonId)?.items ?? [],
  );
  return <QuizSetup index={index} pool={pool} />;
}

// URL params are read inside Suspense so navigations stay instant (Cache Components).
export default function QuizPage(props: PageProps<"/[faculty]/[year]/quiz">) {
  return (
    <Suspense fallback={null}>
      <QuizPageContent {...props} />
    </Suspense>
  );
}
