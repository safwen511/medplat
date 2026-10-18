"use client";

import { createBrowserClient } from "@supabase/ssr";

import { supabaseAnonKey, supabaseEnabled, supabaseUrl } from "./config";

export function browserClient() {
  if (!supabaseEnabled) return null;
  return createBrowserClient(supabaseUrl, supabaseAnonKey);
}
