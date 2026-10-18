import { Suspense } from "react";

import { CodeForm } from "./code-form";

export const metadata = { title: "Accès" };

async function Form({ searchParams }: { searchParams: PageProps<"/acces">["searchParams"] }) {
  const { suite } = await searchParams;
  return <CodeForm next={typeof suite === "string" ? suite : ""} />;
}

export default function Access(props: PageProps<"/acces">) {
  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-8 py-12">
      <div className="flex flex-col gap-3">
        <p className="text-sm text-muted">Bêta privée</p>
        <h1 className="text-3xl leading-tight">Entre ton code d&apos;accès</h1>
        <p className="text-muted">
          MedPlat est en test avec quelques étudiants. Ton code personnel t&apos;a été envoyé avec
          l&apos;invitation.
        </p>
      </div>
      <Suspense fallback={null}>
        <Form searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}
