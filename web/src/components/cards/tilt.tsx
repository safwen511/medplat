"use client";

import { useEffect, useRef, type PointerEvent, type ReactNode } from "react";

import { cn } from "@/lib/utils";

import { styles } from "./styles";

const QUERY = "(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)";

/**
 * 3D tilt that follows a mouse pointer (rotateX/rotateY up to `max` degrees, lift and glare) and
 * springs back on leave. CSS transforms only, driven through custom properties so moving the
 * mouse never re-renders React. Inert on touch screens and with prefers-reduced-motion.
 * Place a <Glare /> inside the shape that should catch the light.
 */
export function Tilt({ children, className, max = 10 }: { children: ReactNode; className?: string; max?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const enabled = useRef(false);

  useEffect(() => {
    const media = window.matchMedia(QUERY);
    const update = () => {
      enabled.current = media.matches;
      if (!media.matches) reset(ref.current);
    };
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    const element = ref.current;
    if (!element || !enabled.current || event.pointerType !== "mouse") return;
    const rect = element.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height));
    element.style.setProperty("--rx", `${((0.5 - y) * 2 * max).toFixed(2)}deg`);
    element.style.setProperty("--ry", `${((x - 0.5) * 2 * max).toFixed(2)}deg`);
    element.style.setProperty("--gx", `${(x * 100).toFixed(1)}%`);
    element.style.setProperty("--gy", `${(y * 100).toFixed(1)}%`);
    element.dataset.active = "true";
  }

  return (
    <div
      ref={ref}
      className={cn(styles.tilt, className)}
      onPointerMove={onPointerMove}
      onPointerLeave={() => reset(ref.current)}
    >
      {children}
    </div>
  );
}

function reset(element: HTMLDivElement | null) {
  if (!element) return;
  for (const name of ["--rx", "--ry", "--gx", "--gy"]) element.style.removeProperty(name);
  delete element.dataset.active;
}

/** Moving highlight that follows the pointer of the nearest <Tilt>. Decorative. */
export function Glare({ className }: { className?: string }) {
  return <span className={cn(styles.glare, className)} aria-hidden />;
}
