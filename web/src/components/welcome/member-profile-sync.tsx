"use client";

import { useEffect } from "react";

import { useMember } from "@/components/layout/use-member";
import { announceProfile } from "@/components/layout/use-profile";
import { useProgress } from "@/lib/progress/provider";

export const PROFILE_OWNER_KEY = "medplat:v1:profileOwner";

/**
 * Several testers can share one tablet, but the study profile lives in the browser. When the
 * signed-in tester is not the profile's owner, the profile switches to them (name, year; exam
 * date and goal back to defaults). Renders nothing.
 */
export function MemberProfileSync() {
  const me = useMember();
  const { store } = useProgress();
  const member = me?.member;

  useEffect(() => {
    if (!member?.id) return;
    let owner: string | null = null;
    try {
      owner = window.localStorage.getItem(PROFILE_OWNER_KEY);
    } catch {
      return;
    }
    if (owner === member.id) return;
    let cancelled = false;
    store.profile().then(async (current) => {
      // A profile never claimed (before this sync existed) is kept for its first tester.
      if (cancelled || (owner === null && current?.displayName === member.firstName)) {
        window.localStorage.setItem(PROFILE_OWNER_KEY, member.id);
        return;
      }
      if (!current?.onboarded) return; // the welcome creates it
      const profile = {
        ...current,
        displayName: member.firstName,
        year: member.year as "dcem1" | "dcem2",
        examDate: null,
        dailyGoal: 20,
      };
      await store.saveProfile(profile);
      window.localStorage.setItem(PROFILE_OWNER_KEY, member.id);
      announceProfile(profile);
    });
    return () => {
      cancelled = true;
    };
  }, [member?.id, member?.firstName, member?.year, store]);

  return null;
}
