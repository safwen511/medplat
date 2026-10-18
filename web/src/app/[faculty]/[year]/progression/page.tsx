import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ProgressView } from "@/components/dashboard/progress-view";
import { availableYears, yearIndex } from "@/lib/content/load";

export function generateStaticParams() {
  return availableYears();
}

export const metadata = { title: "Progression" };

async function ProgressPageContent(props: PageProps<"/[faculty]/[year]/progression">) {
  const { faculty, year } = await props.params;
  const index = yearIndex(faculty, year);
  if (!index) notFound();
  return <ProgressView index={index} />;
}

// URL params are read inside Suspense so navigations stay instant (Cache Components).
export default function ProgressPage(props: PageProps<"/[faculty]/[year]/progression">) {
  return (
    <Suspense fallback={null}>
      <ProgressPageContent {...props} />
    </Suspense>
  );
}
