"use client";

import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

interface Me {
  member: { firstName: string; gender: "m" | "f" } | null;
  visits?: number;
}

const SHOWN_KEY = "medplat:v1:welcomeBackShown";

/** "Bon retour Ala · 5e visite": once per browser session, on returning visits, then fades out. */
export function ReturningBanner() {
  const pathname = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (pathname === "/" || pathname.startsWith("/acces") || pathname.startsWith("/bienvenue")) return;
    try {
      if (window.sessionStorage.getItem(SHOWN_KEY)) return;
    } catch {
      return;
    }
    let cancelled = false;
    fetch("/api/me", { cache: "no-store" })
      .then((response) => (response.ok ? (response.json() as Promise<Me>) : null))
      .then((data) => {
        if (cancelled || !data?.member || (data.visits ?? 1) < 2) return;
        setMe(data);
        setOpen(true);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  // Remembered once it has been seen (closed or timed out), so a reload mid-display shows it again.
  const close = () => {
    setOpen(false);
    try {
      window.sessionStorage.setItem(SHOWN_KEY, "1");
    } catch {
      // shown again on the next page: harmless
    }
  };

  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(close, 6000);
    return () => window.clearTimeout(timer);
  }, [open]);

  return (
    <AnimatePresence>
      {open && me?.member && (
        <motion.div
          role="status"
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ duration: 0.3 }}
          className="fixed inset-x-0 top-16 z-50 flex justify-center px-4"
        >
          <div className="flex w-full max-w-3xl items-center gap-5 rounded-panel border border-panel-border bg-panel px-6 py-5 shadow-depth-2 shadow-glow">
            <div className="flex flex-col items-center rounded-card bg-primary-soft px-4 py-2 text-primary">
              <span className="numeral text-3xl leading-none font-semibold">{me.visits}</span>
              <span className="text-xs">visites</span>
            </div>
            <div className="flex-1">
              <p className="font-heading text-xl font-semibold sm:text-2xl">Bon retour, {me.member.firstName}.</p>
              <p className="text-sm text-muted sm:text-base">Reprends là où tu t&apos;étais arrêté{me.member.gender === "f" ? "e" : ""}.</p>
            </div>
            <button
              type="button"
              aria-label="Fermer"
              onClick={close}
              className="flex size-12 items-center justify-center rounded-control text-muted hover:text-foreground"
            >
              <X className="size-5" aria-hidden />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
