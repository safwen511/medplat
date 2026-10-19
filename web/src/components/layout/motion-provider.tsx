"use client";

import { MotionConfig } from "motion/react";
import type { ReactNode } from "react";

/** With "reduce motion" on, motion skips transforms and keeps only quick fades. */
export function MotionProvider({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
