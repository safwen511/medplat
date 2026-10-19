"use client";

import { LogOut, Moon, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import { signOut } from "@/app/acces/actions";
import { useProgress } from "@/lib/progress/provider";
import { cn } from "@/lib/utils";

import { BetaLabel } from "./beta-label";
import { BottomNav } from "./bottom-nav";
import { activeSection, sections, studyBase, studyLinks } from "./nav";
import { useMounted } from "./use-mounted";
import { useProfile } from "./use-profile";
import { displayNameOf, UserAvatar } from "./user-avatar";

// Next's router changes the hash with pushState (no "hashchange"): links announce it themselves.
const HASH_EVENT = "medplat:hash";
function subscribeHash(callback: () => void) {
  window.addEventListener("hashchange", callback);
  window.addEventListener("popstate", callback);
  window.addEventListener(HASH_EVENT, callback);
  return () => {
    window.removeEventListener("hashchange", callback);
    window.removeEventListener("popstate", callback);
    window.removeEventListener(HASH_EVENT, callback);
  };
}
const announceHash = () => setTimeout(() => window.dispatchEvent(new Event(HASH_EVENT)), 0);

const focusRing = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/** Current item: near-black text with a thin accent underline; the others stay muted. */
const navLink = cn(
  "flex h-12 items-center gap-1.5 rounded-card px-3 text-[0.9375rem] text-muted transition-colors duration-150 hover:text-foreground",
  "aria-[current=page]:text-foreground aria-[current=page]:underline aria-[current=page]:decoration-primary aria-[current=page]:decoration-2 aria-[current=page]:underline-offset-8",
  focusRing,
);

/**
 * Quiet, thin header. The section links live here from tablet landscape up (and on phones held
 * in landscape); phones and tablets in portrait get the bottom tab bar instead.
 */
export function SiteHeader() {
  const { user } = useProgress();
  const { profile } = useProfile();
  const { resolvedTheme, setTheme } = useTheme();
  const mounted = useMounted();
  const pathname = usePathname();
  const hash = useSyncExternalStore(
    subscribeHash,
    () => window.location.hash,
    () => "",
  );

  const items = sections(profile);
  const active = activeSection(pathname);
  const base = studyBase(profile);
  const subLinks = base ? studyLinks(base, pathname, hash) : null;
  const name = displayNameOf(user, profile?.displayName);
  const dark = mounted && resolvedTheme === "dark";

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-border bg-background">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 sm:px-6 lg:gap-8">
          <Link
            href={base ?? "/"}
            className={cn("-mx-1 rounded-card px-1 font-serif text-xl font-semibold tracking-tight", focusRing)}
          >
            MedPlat
          </Link>

          <nav aria-label="Navigation principale" className="hidden landscape:block lg:block">
            <ul className="flex items-center">
              {items.map((item) => (
                <li key={item.id}>
                  <Link href={item.href} aria-current={active === item.id ? "page" : undefined} className={navLink}>
                    <span>
                      {item.label}
                      {item.soon && <span className="ml-1.5 inline-block text-sm text-muted">bientôt</span>}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div className="ml-auto flex items-center gap-1">
            <BetaLabel className="mr-3 hidden whitespace-nowrap md:portrait:block lg:block" />
            <button
              type="button"
              aria-label={dark ? "Passer en thème clair" : "Passer en thème sombre"}
              title={dark ? "Thème clair" : "Thème sombre"}
              onClick={() => setTheme(dark ? "light" : "dark")}
              className={cn(
                "flex size-12 items-center justify-center rounded-card text-muted transition-colors duration-150 hover:text-foreground",
                focusRing,
              )}
            >
              {dark ? (
                <Sun className="size-5" strokeWidth={1.5} aria-hidden />
              ) : (
                <Moon className="size-5" strokeWidth={1.5} aria-hidden />
              )}
            </button>
            {user || profile?.onboarded ? (
              <Link
                href="/espace"
                aria-label={name ? `Mon espace (${name})` : "Mon espace"}
                title={name ?? undefined}
                className={cn("flex size-12 items-center justify-center rounded-card", focusRing)}
              >
                <UserAvatar user={user} name={name} />
              </Link>
            ) : (
              <Link
                href="/acces"
                className={cn(
                  "flex h-12 items-center whitespace-nowrap rounded-card px-2 text-[0.9375rem] font-medium underline-offset-4 hover:underline",
                  focusRing,
                )}
              >
                Se connecter
              </Link>
            )}
            {!user && profile?.onboarded && (
              <form action={signOut}>
                <button
                  type="submit"
                  aria-label="Se déconnecter"
                  title="Se déconnecter"
                  className={cn(
                    "flex size-12 items-center justify-center rounded-card text-muted transition-colors duration-150 hover:text-foreground",
                    focusRing,
                  )}
                >
                  <LogOut className="size-5" strokeWidth={1.5} aria-hidden />
                </button>
              </form>
            )}
          </div>
        </div>
      </header>

      {subLinks && (
        <div className="border-b border-border bg-background">
          <nav aria-label="Étudier" className="mx-auto max-w-6xl px-2 sm:px-3">
            <ul className="flex overflow-x-auto">
              {subLinks.map((link) => (
                <li key={link.label} className="shrink-0">
                  <Link
                    href={link.href}
                    onClick={announceHash}
                    aria-current={link.active ? "page" : undefined}
                    className={cn(navLink, "text-sm")}
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      )}

      <BottomNav items={items} active={active} />
    </>
  );
}
