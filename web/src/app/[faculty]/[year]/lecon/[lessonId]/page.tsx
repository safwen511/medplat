import { notFound } from "next/navigation";
import { Suspense } from "react";

import { LessonView } from "@/components/lesson/lesson-view";
import { QuestionPlayer } from "@/components/quiz/question-player";
import { availableLessonIds, availableYears, exercises, lesson } from "@/lib/content/load";

export function generateStaticParams() {
  return availableYears().flatMap(({ faculty, year }) =>
    availableLessonIds(faculty, year).map((lessonId) => ({ faculty, year, lessonId })),
  );
}

export async function generateMetadata(props: PageProps<"/[faculty]/[year]/lecon/[lessonId]">) {
  const { faculty, year, lessonId } = await props.params;
  return { title: lesson(faculty, year, decodeURIComponent(lessonId))?.title ?? "Cours" };
}

async function LessonPageContent(props: PageProps<"/[faculty]/[year]/lecon/[lessonId]">) {
  const { faculty, year, lessonId: raw } = await props.params;
  const lessonId = decodeURIComponent(raw);
  const content = lesson(faculty, year, lessonId);
  if (!content) notFound();
  // End-of-lesson check: the first five exercises, high-yield ones first.
  const items = [...(exercises(faculty, year, lessonId)?.items ?? [])]
    .sort((a, b) => Number(b.highYield) - Number(a.highYield))
    .slice(0, 5);
  return (
    <div className="flex flex-col gap-20">
      <LessonView lesson={content} faculty={faculty} year={year} />
      {items.length > 0 && (
        <section aria-labelledby="teste-toi" className="mx-auto w-full max-w-[40rem] border-t border-border pt-10">
          <h2 id="teste-toi" className="mb-8 text-[1.625rem] sm:text-[1.75rem]">
            Teste-toi sur ce cours
          </h2>
          <QuestionPlayer exercises={items} mode="lesson" faculty={faculty} year={year} />
        </section>
      )}
    </div>
  );
}

// URL params are read inside Suspense so navigations stay instant (Cache Components).
export default function LessonPage(props: PageProps<"/[faculty]/[year]/lecon/[lessonId]">) {
  return (
    <Suspense fallback={null}>
      <LessonPageContent {...props} />
    </Suspense>
  );
}
