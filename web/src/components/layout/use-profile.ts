"use client";

import { useEffect, useState } from "react";

import { useProgress } from "@/lib/progress/provider";
import type { Profile } from "@/lib/progress/store";

/** Fired after the profile is saved, so the header follows changes made in "Mon espace". */
const PROFILE_EVENT = "medplat:profile-updated";

export function announceProfile(profile: Profile) {
  window.dispatchEvent(new CustomEvent<Profile>(PROFILE_EVENT, { detail: profile }));
}

/** The student's profile, reloaded when the store changes (sign-in) or the profile is saved. */
export function useProfile(): { profile: Profile | null; loaded: boolean } {
  const { store, ready } = useProgress();
  const [state, setState] = useState<{ profile: Profile | null; loaded: boolean }>({
    profile: null,
    loaded: false,
  });

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    store
      .profile()
      .then((profile) => !cancelled && setState({ profile, loaded: true }))
      .catch(() => !cancelled && setState({ profile: null, loaded: true }));
    const onUpdate = (event: Event) => setState({ profile: (event as CustomEvent<Profile>).detail, loaded: true });
    window.addEventListener(PROFILE_EVENT, onUpdate);
    return () => {
      cancelled = true;
      window.removeEventListener(PROFILE_EVENT, onUpdate);
    };
  }, [store, ready]);

  return state;
}
