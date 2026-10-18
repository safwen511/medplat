"use client";

import Link from "next/link";
import type { ComponentProps } from "react";

import { studyBase } from "./nav";
import { useProfile } from "./use-profile";

/** Link to the student's year (or to the onboarding when no year is chosen yet). */
export function StudyLink(props: Omit<ComponentProps<typeof Link>, "href">) {
  const { profile } = useProfile();
  return <Link href={studyBase(profile) ?? "/onboarding"} {...props} />;
}
