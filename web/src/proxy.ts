import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import {
  ACCESS_COOKIE,
  ACCESS_MAX_AGE,
  accessEnabled,
  SESSION_COOKIE,
  verifyMember,
  VISITS_COOKIE,
  WELCOMED_COOKIE,
} from "@/lib/access";
import { supabaseAnonKey, supabaseEnabled, supabaseUrl } from "@/lib/supabase/config";

// Pages anyone may open without an access code.
const PUBLIC = new Set(["/", "/acces"]);

// Beta gate (access codes), then the Supabase session refresh, once per navigation.
export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  let visitCookies: [string, string, number | undefined][] = [];
  if (accessEnabled()) {
    const member = await verifyMember(request.cookies.get(ACCESS_COOKIE)?.value);
    if (!member && !PUBLIC.has(pathname)) {
      const target = new URL("/acces", request.url);
      target.searchParams.set("suite", pathname + search);
      return NextResponse.redirect(target);
    }
    if (member) {
      // A known tester never sees the code page again: straight to the welcome or their year.
      if (PUBLIC.has(pathname)) {
        const welcomed = request.cookies.get(WELCOMED_COOKIE)?.value === "1";
        return NextResponse.redirect(new URL(welcomed ? `/sfax/${member.year}` : "/bienvenue", request.url));
      }
      // One visit per browser session.
      if (!request.cookies.get(SESSION_COOKIE)) {
        const visits = (Number(request.cookies.get(VISITS_COOKIE)?.value) || 0) + 1;
        request.cookies.set(VISITS_COOKIE, String(visits));
        request.cookies.set(SESSION_COOKIE, "1");
        visitCookies = [
          [VISITS_COOKIE, String(visits), ACCESS_MAX_AGE],
          [SESSION_COOKIE, "1", undefined],
        ];
      }
    }
  }
  let response = NextResponse.next({ request });
  for (const [name, value, maxAge] of visitCookies)
    response.cookies.set(name, value, { path: "/", sameSite: "lax", httpOnly: true, maxAge });
  if (!supabaseEnabled) return response;
  const supabase = createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (toSet, headers) => {
        for (const { name, value } of toSet) request.cookies.set(name, value);
        response = NextResponse.next({ request });
        for (const { name, value, options } of toSet) response.cookies.set(name, value, options);
        for (const [key, value] of Object.entries(headers ?? {})) response.headers.set(key, value);
      },
    },
  });
  await supabase.auth.getUser();
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|figures/|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|webp)$).*)"],
};
