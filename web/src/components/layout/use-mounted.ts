"use client";

import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

/** True after hydration: theme-dependent UI must not differ between server and client. */
export function useMounted(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
}
