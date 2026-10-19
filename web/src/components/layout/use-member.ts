"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

export interface Me {
  /** Whether beta access codes are on (otherwise the site is open, demo mode). */
  gate: boolean;
  member: { id: string; firstName: string; gender: "m" | "f"; year: string; role?: "doctor" } | null;
  visits?: number;
}

/** The beta tester signed in with an access code, refreshed on every navigation (sign-out included). */
export function useMember(): Me | null {
  const pathname = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/me", { cache: "no-store" })
      .then((response) => (response.ok ? (response.json() as Promise<Me>) : null))
      .then((data) => {
        if (!cancelled) setMe(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [pathname]);
  return me;
}
