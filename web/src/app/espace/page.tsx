import { EspaceView } from "@/components/espace/espace-view";
import type { EspaceYear } from "@/components/espace/types";
import { availableLessonIds, availableYears, yearIndex } from "@/lib/content/load";

export const metadata = { title: "Mon espace" };

/** Both years are loaded here (the profile, and so the student's year, is only known client-side). */
function espaceYears(): EspaceYear[] {
  return availableYears().flatMap(({ faculty, year }) => {
    const index = yearIndex(faculty, year);
    if (!index) return [];
    return [
      {
        faculty: index.faculty,
        facultyLabel: index.facultyLabel,
        year: index.year,
        yearLabel: index.yearLabel,
        certifs: index.certifs.map((certif) => ({
          slug: certif.slug,
          title: certif.title,
          pole: certif.pole,
          lessons: certif.modules.flatMap((mod) => mod.lessons.map(({ id, title }) => ({ id, title }))),
        })),
        availableLessonIds: availableLessonIds(faculty, year),
      },
    ];
  });
}

export default function EspacePage() {
  return <EspaceView years={espaceYears()} />;
}
