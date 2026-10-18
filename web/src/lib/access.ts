// Beta access by personal code (no e-mail login yet). Codes live in the server-only environment
// variable MEDPLAT_VIP (generated with the repo-root "vip" file, both Git-ignored) and never reach
// the browser. A valid code sets an HTTP-only cookie holding the member, signed with
// MEDPLAT_ACCESS_SECRET (HMAC-SHA-256). Web Crypto only, so the proxy and pages share this code.

export interface Member {
  id: string;
  name: string;
  firstName: string;
  gender: "m" | "f";
  year: "dcem1" | "dcem2";
}

interface Entry extends Member {
  code: string;
}

export const ACCESS_COOKIE = "medplat_access";
export const ACCESS_MAX_AGE = 60 * 60 * 24 * 120; // 120 days

const encoder = new TextEncoder();

function entries(): Entry[] {
  try {
    const parsed: unknown = JSON.parse(process.env.MEDPLAT_VIP ?? "[]");
    return Array.isArray(parsed) ? (parsed as Entry[]) : [];
  } catch {
    return [];
  }
}

/** The gate is on when codes and a signing secret are configured. */
export function accessEnabled(): boolean {
  return Boolean(process.env.MEDPLAT_ACCESS_SECRET) && entries().length > 0;
}

function normalize(code: string): string {
  return code.toUpperCase().replace(/[^A-Z0-9]/g, "");
}

async function digest(value: string): Promise<Uint8Array> {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", encoder.encode(value)));
}

function sameBytes(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let difference = 0;
  for (let index = 0; index < a.length; index++) difference |= a[index] ^ b[index];
  return difference === 0;
}

/** The member owning this code, compared in constant time over SHA-256 digests. */
export async function findMember(code: string): Promise<Member | null> {
  const typed = await digest(normalize(code));
  let found: Member | null = null;
  for (const { code: expected, ...member } of entries()) {
    if (sameBytes(typed, await digest(normalize(expected)))) found = member;
  }
  return found;
}

function base64url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64url(value: string): Uint8Array {
  const binary = atob(value.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

async function hmac(payload: string): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(process.env.MEDPLAT_ACCESS_SECRET ?? ""),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, encoder.encode(payload)));
}

export async function signMember(member: Member): Promise<string> {
  const payload = base64url(encoder.encode(JSON.stringify(member)));
  return `${payload}.${base64url(await hmac(payload))}`;
}

/** The member in a session cookie, or null when absent, forged or for a revoked code. */
export async function verifyMember(token: string | undefined): Promise<Member | null> {
  if (!token || !accessEnabled()) return null;
  const [payload, signature] = token.split(".");
  if (!payload || !signature) return null;
  try {
    if (!sameBytes(fromBase64url(signature), await hmac(payload))) return null;
    const member = JSON.parse(new TextDecoder().decode(fromBase64url(payload))) as Member;
    // A code removed from the list revokes its sessions.
    return entries().some((entry) => entry.id === member.id) ? member : null;
  } catch {
    return null;
  }
}
