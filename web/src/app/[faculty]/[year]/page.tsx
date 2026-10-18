import { notFound } from "next/navigation";
import { Suspense } from "react";

import { YearHome } from "@/components/dashboard/year-home";
import { availableYears, yearIndex } from "@/lib/content/load";

export function generateStaticParams() {
  return availableYears();
}

async function YearPageContent(props: PageProps<"/[faculty]/[year]">) {
  const { faculty, year } = await props.params;
  const index = yearIndex(faculty, year);
  if (!index) notFound();
  return <YearHome index={index} />;
}

// URL params are read inside Suspense so navigations stay instant (Cache Components).
export default function YearPage(props: PageProps<"/[faculty]/[year]">) {
  return (
    <Suspense fallback={null}>
      <YearPageContent {...props} />
    </Suspense>
  );
}
