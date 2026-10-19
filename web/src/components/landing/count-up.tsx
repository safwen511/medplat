"use client";

import { animate, useInView, useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";

/** A number that counts up once it scrolls into view (instantly with reduced motion). */
export function CountUp({ value, className }: { value: number; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const seen = useInView(ref, { once: true, margin: "0px 0px -10% 0px" });
  const reduce = useReducedMotion();

  useEffect(() => {
    const element = ref.current;
    if (!element || !seen) return;
    const format = (n: number) => Math.round(n).toLocaleString("fr-FR");
    if (reduce) {
      element.textContent = format(value);
      return;
    }
    const controls = animate(0, value, {
      duration: 1.4,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (n) => (element.textContent = format(n)),
    });
    return () => controls.stop();
  }, [seen, value, reduce]);

  // Server and first paint show the real value (no layout shift, readable without JavaScript).
  return (
    <span ref={ref} className={className}>
      {value.toLocaleString("fr-FR")}
    </span>
  );
}
