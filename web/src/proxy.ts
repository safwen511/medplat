import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { ACCESS_COOKIE, accessEnabled, verifyMember } from "@/lib/access";
import { supabaseAnonKey, supabaseEnabled, supabaseUrl } from "@/lib/supabase/config";

// Pages anyone may open without an access code.
const PUBLIC = new Set(["/", "/acces"]);

// Beta gate (access codes), then the Supabase session refresh, once per navigation.
export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (accessEnabled() && !PUBLIC.has(pathname)) {
    const member = await verifyMember(request.cookies.get(ACCESS_COOKIE)?.value);
    if (!member) {
      const target = new URL("/acces", request.url);
      target.searchParams.set("suite", pathname + search);
      return NextResponse.redirect(target);
    }
  }
  let response = NextResponse.next({ request });
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
