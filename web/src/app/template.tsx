import type { ReactNode } from "react";

/** Re-mounted on every navigation: each page fades in (opacity only, see `.page-enter`). */
export default function Template({ children }: { children: ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
