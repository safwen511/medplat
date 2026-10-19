"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";

import { EASE_OUT } from "@/lib/motion";

/**
 * Rises into view once, when it scrolls into the viewport. For content below the fold only:
 * above the fold, use the CSS `.rise-in` class so it shows before JavaScript loads.
 */
export function Reveal({
  children,
  delay = 0,
  y = 18,
  className,
}: {
  children: ReactNode;
  delay?: number;
  y?: number;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "0px 0px -8% 0px" }}
      transition={{ duration: 0.6, ease: EASE_OUT, delay }}
    >
      {children}
    </motion.div>
  );
}
