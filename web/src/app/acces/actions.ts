"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import {
  ACCESS_COOKIE,
  ACCESS_MAX_AGE,
  findMember,
  hasReadWelcome,
  SESSION_COOKIE,
  signMember,
  verifyMember,
  VISITS_COOKIE,
  WELCOMED_COOKIE,
  withVisit,
  withWelcomeRead,
} from "@/lib/access";

export interface RedeemState {
  error: string | null;
}

const cookieOptions = (maxAge: number) => ({
  httpOnly: true,
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
  path: "/",
  maxAge,
});

function safeNext(value: string): string {
  return value.startsWith("/") && !value.startsWith("//") && value !== "/" ? value : "";
}

/** Checks a beta access code; first visit → personal welcome, returning → straight back in. */
export async function redeemCode(_previous: RedeemState, form: FormData): Promise<RedeemState> {
  const member = await findMember(String(form.get("code") ?? ""));
  if (!member) return { error: "Ce code ne fonctionne pas. Vérifie-le et réessaie." };
  const store = await cookies();
  store.set(ACCESS_COOKIE, await signMember(member), cookieOptions(ACCESS_MAX_AGE));
  // The proxy ran before the cookie existed: count this visit here.
  if (!store.get(SESSION_COOKIE)) {
    store.set(VISITS_COOKIE, withVisit(store.get(VISITS_COOKIE)?.value, member.id), cookieOptions(ACCESS_MAX_AGE));
    store.set(SESSION_COOKIE, "1", { ...cookieOptions(0), maxAge: undefined });
  }
  const next = safeNext(String(form.get("suite") ?? ""));
  if (hasReadWelcome(store.get(WELCOMED_COOKIE)?.value, member.id)) redirect(next || `/sfax/${member.year}`);
  redirect(next ? `/bienvenue?suite=${encodeURIComponent(next)}` : "/bienvenue");
}

/** The welcome was read: remember it for this member on this device. */
export async function finishWelcome(): Promise<void> {
  const store = await cookies();
  const member = await verifyMember(store.get(ACCESS_COOKIE)?.value);
  if (member)
    store.set(WELCOMED_COOKIE, withWelcomeRead(store.get(WELCOMED_COOKIE)?.value, member.id), cookieOptions(ACCESS_MAX_AGE));
}

/** Signs out on this device; it still remembers the welcome was read and the visit count. */
export async function signOut(): Promise<void> {
  const store = await cookies();
  for (const name of [ACCESS_COOKIE, SESSION_COOKIE]) store.delete(name);
  redirect("/acces");
}

/** Forgets this device's tester entirely (another person, or another code). */
export async function leave(): Promise<void> {
  const store = await cookies();
  for (const name of [ACCESS_COOKIE, WELCOMED_COOKIE, VISITS_COOKIE, SESSION_COOKIE]) store.delete(name);
  redirect("/acces");
}
