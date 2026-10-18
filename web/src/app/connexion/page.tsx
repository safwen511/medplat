import Link from "next/link";
import { Suspense } from "react";

import { GoogleButton } from "@/components/auth/google-button";
import { Button } from "@/components/ui/button";
import { supabaseEnabled } from "@/lib/supabase/config";

export const metadata = { title: "Connexion" };

async function AuthError({ searchParams }: { searchParams: PageProps<"/connexion">["searchParams"] }) {
  const { erreur } = await searchParams;
  if (!erreur) return null;
  return (
    <p role="alert" className="text-[0.9375rem]">
      La connexion n&apos;a pas abouti. Réessaie.
    </p>
  );
}

/** One screen, one action: continue with Google (or, without sign-in configured, just continue). */
export default function SignIn(props: PageProps<"/connexion">) {
  return (
    <div className="mx-auto flex min-h-[calc(100svh-14rem)] max-w-sm flex-col justify-center gap-8 py-12 text-center">
      <div className="flex flex-col gap-3">
        <h1 className="text-3xl leading-tight sm:text-4xl">Bienvenue sur MedPlat</h1>
        <p className="text-muted text-pretty">
          {supabaseEnabled
            ? "Connecte-toi pour retrouver tes cours, tes questions et ta progression sur tous tes appareils."
            : "Ta progression sera gardée dans ce navigateur."}
        </p>
      </div>
      <div className="flex flex-col items-center gap-4">
        <Suspense fallback={null}>
          <AuthError searchParams={props.searchParams} />
        </Suspense>
        {supabaseEnabled ? (
          <>
            <GoogleButton />
            <Link
              href="/onboarding"
              className="flex h-12 items-center rounded-card px-2 text-[0.9375rem] text-muted underline-offset-4 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Continuer sans compte
            </Link>
          </>
        ) : (
          <Button asChild size="lg" className="w-full">
            <Link href="/onboarding">Continuer</Link>
          </Button>
        )}
      </div>
    </div>
  );
}
