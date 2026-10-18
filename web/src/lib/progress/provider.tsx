"use client";

import type { User } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { browserClient } from "@/lib/supabase/client";

import { localStore, supabaseStore, type ProgressStore } from "./store";

interface ProgressContext {
  store: ProgressStore;
  user: User | null;
  ready: boolean;
}

const Context = createContext<ProgressContext>({ store: localStore, user: null, ready: false });

/** Picks the Supabase store for a signed-in student, the browser store otherwise. */
export function ProgressProvider({ children }: { children: ReactNode }) {
  const client = useMemo(() => browserClient(), []);
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(!client);

  useEffect(() => {
    if (!client) return;
    client.auth.getUser().then(({ data }) => {
      setUser(data.user);
      setReady(true);
    });
    const { data } = client.auth.onAuthStateChange((_event, session) => setUser(session?.user ?? null));
    return () => data.subscription.unsubscribe();
  }, [client]);

  const store = useMemo(
    () => (client && user ? supabaseStore(client, user.id) : localStore),
    [client, user],
  );
  return <Context.Provider value={{ store, user, ready }}>{children}</Context.Provider>;
}

export function useProgress() {
  return useContext(Context);
}
