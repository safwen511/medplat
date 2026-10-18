import { notFound } from "next/navigation";
import { Suspense } from "react";

import { CertifPage } from "@/components/dashboard/certif-page";
import { availableYears, yearIndex } from "@/lib/content/load";

export function generateStaticParams() {
  return availableYears().flatMap(({ faculty, year }) =>
    (yearIndex(faculty, year)?.certifs ?? []).map((certif) => ({ faculty, year, certif: certif.slug })),
  );
}

async function CertifContent(props: PageProps<"/[faculty]/[year]/[certif]">) {
  const { faculty, year, certif } = await props.params;
  const index = yearIndex(faculty, year);
  const summary = index?.certifs.find((item) => item.slug === certif);
  if (!index || !summary) notFound();
  return <CertifPage index={index} certif={summary} />;
}

// URL params are read inside Suspense so navigations stay instant (Cache Components).
export default function Certif(props: PageProps<"/[faculty]/[year]/[certif]">) {
  return (
    <Suspense fallback={null}>
      <CertifContent {...props} />
    </Suspense>
  );
}
