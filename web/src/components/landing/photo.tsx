"use client";

import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import Image from "next/image";
import { useRef } from "react";

import { cn } from "@/lib/utils";

/**
 * A decorative photo that drifts slower than the page (parallax) and settles in with a slow zoom
 * on first view. Transform only; still with reduced motion.
 */
export function ParallaxPhoto({
  src,
  className,
  imageClassName,
  sizes,
  priority = false,
  drift = 60,
}: {
  src: string;
  className?: string;
  imageClassName?: string;
  sizes: string;
  priority?: boolean;
  /** Pixels of vertical drift across the photo's pass through the viewport. */
  drift?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], reduce ? [0, 0] : [-drift / 2, drift / 2]);

  return (
    <div ref={ref} aria-hidden className={cn("overflow-hidden", className)}>
      <motion.div style={{ y }} className="absolute -inset-y-12 inset-x-0">
        <Image
          src={src}
          alt=""
          fill
          sizes={sizes}
          priority={priority}
          className={cn("settle-in object-cover", imageClassName)}
        />
      </motion.div>
    </div>
  );
}
