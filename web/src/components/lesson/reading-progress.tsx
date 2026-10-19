"use client";

import { motion, useScroll, useSpring } from "motion/react";

/** Thin accent line under the header that fills as the student reads down the page. */
export function ReadingProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 260, damping: 40, restDelta: 0.001 });
  return (
    <motion.div
      aria-hidden
      style={{ scaleX }}
      className="fixed inset-x-0 top-16 z-30 h-0.5 origin-left bg-gradient-to-r from-primary/60 to-primary"
    />
  );
}
