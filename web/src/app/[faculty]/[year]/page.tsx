import { notFound } from "next/navigation";

import { YearHome } from "@/components/dashboard/year-home";
import { availableYears, yearIndex } from "@/lib/content/load";

export function generateStaticParams() {
  return availableYears();
}

export default async function YearPage(props: PageProps<"/[faculty]/[year]">) {
  const { faculty, year } = await props.params;
  const index = yearIndex(faculty, year);
  if (!index) notFound();
  return <YearHome index={index} />;
}
