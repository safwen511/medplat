import { notFound } from "next/navigation";

import { ProgressView } from "@/components/dashboard/progress-view";
import { availableYears, yearIndex } from "@/lib/content/load";

export function generateStaticParams() {
  return availableYears();
}

export const metadata = { title: "Progression" };

export default async function ProgressPage(props: PageProps<"/[faculty]/[year]/progression">) {
  const { faculty, year } = await props.params;
  const index = yearIndex(faculty, year);
  if (!index) notFound();
  return <ProgressView index={index} />;
}
