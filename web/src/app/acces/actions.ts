"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ACCESS_COOKIE, ACCESS_MAX_AGE, findMember, signMember } from "@/lib/access";

export interface RedeemState {
  error: string | null;
}

/** Checks a beta access code; on success opens a session and shows the personal welcome. */
export async function redeemCode(_previous: RedeemState, form: FormData): Promise<RedeemState> {
  const code = String(form.get("code") ?? "");
  const member = await findMember(code);
  if (!member) return { error: "Ce code ne fonctionne pas. Vérifie-le et réessaie." };
  (await cookies()).set(ACCESS_COOKIE, await signMember(member), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: ACCESS_MAX_AGE,
  });
  const next = String(form.get("suite") ?? "");
  redirect(
    next.startsWith("/") && !next.startsWith("//") && next !== "/"
      ? `/bienvenue?suite=${encodeURIComponent(next)}`
      : "/bienvenue",
  );
}

/** Ends the session on this device (to enter another code). */
export async function leave(): Promise<void> {
  (await cookies()).delete(ACCESS_COOKIE);
  redirect("/acces");
}
