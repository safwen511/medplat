"use client";

import { LogOut, Moon, Sun } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import { signOut } from "@/app/acces/actions";
import { useProgress } from "@/lib/progress/provider";
import { cn } from "@/lib/utils";

import { BetaLabel } from "./beta-label";
import { BottomNav } from "./bottom-nav";
import { Logo } from "./logo";
import { NavPills } from "./nav-pills";
import { activeSection, sections, studyBase, studyLinks } from "./nav";
import { useMember } from "./use-member";
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

const iconButton = cn(
  "flex size-11 items-center justify-center rounded-full text-muted transition-colors duration-150 hover:bg-surface-muted hover:text-foreground",
  focusRing,
);

/**
 * Glass header: logo, the three sections with a sliding indicator (tablet landscape and up; phones
 * and portrait tablets use the bottom tab bar), the beta notice, theme and account.
 */
export function SiteHeader() {
  const { user } = useProgress();
  const { profile } = useProfile();
  const me = useMember();
  // Signed in: a Google account, a beta access code, or (open demo, no codes) a local profile.
  const member = Boolean(me?.member);
  const signedIn = Boolean(user) || member || (me?.gate === false && Boolean(profile?.onboarded));
  // Visitors without access see no study navigation (it only leads to the code page). While the
  // check loads, a device that has studied before keeps its navigation (no flicker).
  const showNav = signedIn || (me === null && Boolean(profile?.onboarded));
  const { resolvedTheme, setTheme } = useTheme();
  const mounted = useMounted();
  const reduce = useReducedMotion();
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
      <header className="sticky top-0 z-40 border-b border-border bg-background/75 backdrop-blur-xl backdrop-saturate-150">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 sm:px-6 lg:gap-6">
          <Link href={base ?? "/"} aria-label="MedPlat, accueil" className={cn("-mx-1 rounded-full px-1", focusRing)}>
            <Logo />
          </Link>

          {showNav && (
            <NavPills
              group="sections"
              label="Navigation principale"
              className="hidden landscape:block lg:block"
              items={items.map((item) => ({
                key: item.id,
                href: item.href,
                active: active === item.id,
                label: (
                  <>
                    {item.label}
                    {item.soon && (
                      <span className="rounded-full border border-border px-1.5 py-px text-[0.6875rem] text-subtle">
                        bientôt
                      </span>
                    )}
                  </>
                ),
              }))}
            />
          )}

          <div className="ml-auto flex items-center gap-1">
            <BetaLabel className="mr-2 hidden md:portrait:inline-flex lg:inline-flex" />
            <button
              type="button"
              aria-label={dark ? "Passer en thème clair" : "Passer en thème sombre"}
              title={dark ? "Thème clair" : "Thème sombre"}
              onClick={() => setTheme(dark ? "light" : "dark")}
              className={iconButton}
            >
              <AnimatePresence mode="wait" initial={false}>
                <motion.span
                  key={dark ? "sun" : "moon"}
                  initial={reduce ? { opacity: 0 } : { opacity: 0, rotate: -60, scale: 0.6 }}
                  animate={{ opacity: 1, rotate: 0, scale: 1 }}
                  exit={reduce ? { opacity: 0 } : { opacity: 0, rotate: 60, scale: 0.6 }}
                  transition={{ duration: 0.18 }}
                  className="flex"
                >
                  {dark ? (
                    <Sun className="size-5" strokeWidth={1.5} aria-hidden />
                  ) : (
                    <Moon className="size-5" strokeWidth={1.5} aria-hidden />
                  )}
                </motion.span>
              </AnimatePresence>
            </button>
            {signedIn ? (
              <Link
                href="/espace"
                aria-label={name ? `Mon espace (${name})` : "Mon espace"}
                title={name ?? undefined}
                className={cn(
                  "flex size-11 items-center justify-center rounded-full transition-shadow duration-200 hover:shadow-glow",
                  focusRing,
                )}
              >
                <UserAvatar user={user} name={name} />
              </Link>
            ) : pathname.startsWith("/acces") ? null : (
              <Link
                href="/acces"
                className={cn(
                  "flex h-10 items-center whitespace-nowrap rounded-full bg-foreground px-4 text-sm font-medium text-background transition-opacity duration-150 hover:opacity-85",
                  focusRing,
                )}
              >
                Se connecter
              </Link>
            )}
            {!user && member && (
              <form action={signOut}>
                <button type="submit" aria-label="Se déconnecter" title="Se déconnecter" className={iconButton}>
                  <LogOut className="size-5" strokeWidth={1.5} aria-hidden />
                </button>
              </form>
            )}
          </div>
        </div>

        {subLinks && (
          <div className="border-t border-border/60">
            <NavPills
              group="study"
              label="Étudier"
              variant="underline"
              className="mx-auto max-w-6xl overflow-x-auto px-2 sm:px-3"
              items={subLinks.map((link) => ({
                key: link.label,
                href: link.href,
                label: link.label,
                active: link.active,
                onClick: announceHash,
              }))}
            />
          </div>
        )}
      </header>

      {showNav && <BottomNav items={items} active={active} />}
    </>
  );
}
