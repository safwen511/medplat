import Link from "next/link";
import { Suspense } from "react";

import { GoogleButton } from "@/components/auth/google-button";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { supabaseEnabled } from "@/lib/supabase/config";

export const metadata = { title: "Connexion" };

async function AuthError({ searchParams }: { searchParams: PageProps<"/connexion">["searchParams"] }) {
  const { erreur } = await searchParams;
  if (!erreur) return null;
  return (
    <p className="rounded-md bg-wrong-soft px-3 py-2 text-sm text-wrong">
      La connexion n&apos;a pas abouti. Réessaie.
    </p>
  );
}

export default function SignIn(props: PageProps<"/connexion">) {
  return (
    <div className="mx-auto flex max-w-md flex-col gap-6 py-10">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Bienvenue sur MedPlat</CardTitle>
          <CardDescription>
            Un seul clic pour retrouver tes cours, tes QCM et ta progression sur tous tes appareils.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Suspense fallback={null}>
            <AuthError searchParams={props.searchParams} />
          </Suspense>
          {supabaseEnabled ? (
            <GoogleButton />
          ) : (
            <>
              <p className="text-sm text-muted">
                Mode démo : la connexion Google n&apos;est pas encore configurée. Ta progression
                reste enregistrée dans ce navigateur.
              </p>
              <Button asChild size="lg">
                <Link href="/onboarding">Continuer en mode démo</Link>
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
