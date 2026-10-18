// Public Supabase settings. Only the project URL and the anon (publishable) key may reach the
// browser; row-level security protects the data. Without them the site runs in demo mode and
// keeps progress in the browser.
export const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
export const supabaseEnabled = Boolean(supabaseUrl && supabaseAnonKey);
