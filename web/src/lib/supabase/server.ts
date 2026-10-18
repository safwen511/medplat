import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import { supabaseAnonKey, supabaseEnabled, supabaseUrl } from "./config";

export async function serverClient() {
  if (!supabaseEnabled) return null;
  const cookieStore = await cookies();
  return createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll: () => cookieStore.getAll(),
      setAll: (toSet) => {
        try {
          for (const { name, value, options } of toSet) cookieStore.set(name, value, options);
        } catch {
          // Called from a Server Component: the proxy refreshes the session instead.
        }
      },
    },
  });
}

export async function currentUser() {
  const supabase = await serverClient();
  if (!supabase) return null;
  const { data } = await supabase.auth.getUser();
  return data.user;
}
