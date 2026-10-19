import { Suspense } from "react";

import { LogoMark } from "@/components/layout/logo";

import { CodeForm } from "./code-form";

export const metadata = { title: "Accès" };

async function Form({ searchParams }: { searchParams: PageProps<"/acces">["searchParams"] }) {
  const { suite } = await searchParams;
  return <CodeForm next={typeof suite === "string" ? suite : ""} />;
}

export default function Access(props: PageProps<"/acces">) {
  return (
    <div className="flex min-h-[calc(100svh-12rem)] items-center justify-center py-10">
      <div className="panel grain relative w-full max-w-md overflow-hidden sm:p-10">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{ background: "radial-gradient(80% 60% at 50% 0%, var(--primary-soft), transparent 70%)" }}
        />
        <div className="relative flex flex-col gap-8">
          <div className="flex flex-col items-center gap-4 text-center">
            <span className="rise-in flex size-16 items-center justify-center rounded-2xl border border-border-strong bg-background/60 shadow-glow">
              <LogoMark className="size-9" />
            </span>
            <p className="eyebrow">Bêta privée</p>
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
      </div>
    </div>
  );
}
