import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { supabaseAnonKey, supabaseEnabled, supabaseUrl } from "@/lib/supabase/config";

// Refresh the Supabase session cookie once per navigation, before pages render.
export async function proxy(request: NextRequest) {
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
