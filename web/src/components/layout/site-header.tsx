"use client";

import { LogOut, Moon, Stethoscope, Sun } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useProgress } from "@/lib/progress/provider";
import type { Profile } from "@/lib/progress/store";
import { browserClient } from "@/lib/supabase/client";

export function SiteHeader() {
  const { store, user } = useProgress();
  const { resolvedTheme, setTheme } = useTheme();
  const [profile, setProfile] = useState<Profile | null>(null);
  const router = useRouter();

  useEffect(() => {
    store.profile().then(setProfile);
  }, [store]);

  const home = profile?.year ? `/${profile.faculty}/${profile.year}` : "/";
  const signOut = async () => {
    await browserClient()?.auth.signOut();
    router.push("/");
    router.refresh();
  };

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-surface/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 sm:px-6">
        <Link href={home} className="flex items-center gap-2 font-semibold text-primary">
          <Stethoscope className="size-5" aria-hidden />
          MedPlat
        </Link>
        {profile?.year && (
          <nav className="hidden items-center gap-1 text-sm sm:flex">
            <Button asChild variant="ghost" size="sm">
              <Link href={home}>Mes certifs</Link>
            </Button>
            <Button asChild variant="ghost" size="sm">
              <Link href={`${home}/quiz`}>Quiz</Link>
            </Button>
            <Button asChild variant="ghost" size="sm">
              <Link href={`${home}/progression`}>Progression</Link>
            </Button>
          </nav>
        )}
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Changer de thème"
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
          >
            {resolvedTheme === "dark" ? <Sun /> : <Moon />}
          </Button>
          {user ? (
            <Button variant="ghost" size="icon" aria-label="Se déconnecter" onClick={signOut}>
              <LogOut />
            </Button>
          ) : (
            <Button asChild size="sm" variant="outline">
              <Link href="/connexion">Se connecter</Link>
            </Button>
          )}
        </div>
      </div>
    </header>
  );
}
