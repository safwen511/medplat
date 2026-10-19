import { notFound } from "next/navigation";
import type { ReactNode } from "react";

/** Developer tools (draft comparison, quiz fixtures): local only, never on the live site. */
export default function DevLayout({ children }: { children: ReactNode }) {
  if (process.env.NODE_ENV === "production") notFound();
  return children;
}
