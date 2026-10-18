"use client";

import type { User } from "@supabase/supabase-js";
import { UserRound } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

/** Best display name: the profile's, then the Google account's, then the e-mail's local part. */
export function displayNameOf(user: User | null, profileName?: string | null): string | null {
  const meta = user?.user_metadata as Record<string, unknown> | undefined;
  const candidates = [profileName, meta?.full_name, meta?.name, user?.email?.split("@")[0]];
  for (const candidate of candidates) if (typeof candidate === "string" && candidate.trim()) return candidate.trim();
  return null;
}

export function initialsOf(name: string | null): string {
  if (!name) return "";
  const words = name.split(/[\s._-]+/).filter(Boolean);
  return words
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase())
    .join("");
}

function avatarUrl(user: User | null): string | null {
  const meta = user?.user_metadata as Record<string, unknown> | undefined;
  const url = meta?.avatar_url ?? meta?.picture;
  return typeof url === "string" && url.startsWith("https://") ? url : null;
}

const SIZES = {
  sm: "size-8 text-xs",
  md: "size-12 text-base",
} as const;

/** Google photo when signed in, otherwise initials, otherwise a neutral person icon. */
export function UserAvatar({
  user,
  name,
  size = "sm",
  className,
}: {
  user: User | null;
  name: string | null;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const url = avatarUrl(user);
  const [failed, setFailed] = useState<string | null>(null);
  const initials = initialsOf(name);
  const base = cn(
    "relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface-muted font-medium text-muted ring-1 ring-border",
    SIZES[size],
    className,
  );

  if (url && failed !== url)
    return (
      <span className={base}>
        {/* Google avatars are external, tiny and already sized: next/image would need a remote pattern. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={url}
          alt=""
          referrerPolicy="no-referrer"
          className="size-full object-cover"
          onError={() => setFailed(url)}
        />
      </span>
    );
  return (
    <span className={base} aria-hidden>
      {initials || <UserRound className="size-1/2" strokeWidth={1.5} />}
    </span>
  );
}
