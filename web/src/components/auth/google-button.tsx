"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { browserClient } from "@/lib/supabase/client";

export function GoogleButton({ next = "/onboarding" }: { next?: string }) {
  const [pending, setPending] = useState(false);
  const signIn = async () => {
    const client = browserClient();
    if (!client) return;
    setPending(true);
    await client.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}` },
    });
  };
  return (
    <Button size="lg" variant="outline" className="w-full" onClick={signIn} disabled={pending}>
      <svg viewBox="0 0 24 24" aria-hidden className="size-5">
        <path fill="#EA4335" d="M12 10.2v3.9h5.5c-.2 1.3-1.6 3.9-5.5 3.9-3.3 0-6-2.7-6-6s2.7-6 6-6c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.8 3.5 14.6 2.6 12 2.6 6.8 2.6 2.6 6.8 2.6 12s4.2 9.4 9.4 9.4c5.4 0 9-3.8 9-9.2 0-.6-.1-1.1-.2-1.6H12z" />
      </svg>
      {pending ? "Redirection…" : "Continuer avec Google"}
    </Button>
  );
}
