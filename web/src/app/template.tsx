"use client";

import { useLayoutEffect, useRef, type ReactNode } from "react";

// The first page of a visit appears as served; later navigations fade in.
let firstPage = true;

/**
 * Re-mounted on every navigation. The fade runs through the Web Animations API with no fill, so
 * once played nothing stays applied: no lasting stacking context that would trap fixed overlays
 * (the welcome slides) under the tab bar.
 */
export default function Template({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    if (firstPage) {
      firstPage = false;
      return;
    }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    ref.current?.animate([{ opacity: 0 }, { opacity: 1 }], {
      duration: 220,
      easing: "cubic-bezier(0.22, 1, 0.36, 1)",
    });
  }, []);
  return <div ref={ref}>{children}</div>;
}
