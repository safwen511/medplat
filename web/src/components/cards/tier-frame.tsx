import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

import { styles } from "./styles";
import type { Tier } from "./tiers";

/**
 * The card's frame shows its mastery tier: thin neutral (Non lu), teal (Lu), silver gradient
 * (Révisé 1×, brighter for 2×), gold gradient with glow and a slow shimmer (Maîtrisé).
 */
export function TierFrame({ tier, className, children, ...props }: ComponentProps<"div"> & { tier: Tier }) {
  return (
    <div className={cn(styles.frame, className)} data-tier={tier} {...props}>
      <div className={styles.frameInner}>{children}</div>
    </div>
  );
}

/** Solid tier color (stepper segments, distribution bars). */
export function TierFill({
  tier,
  onHue = false,
  className,
  ...props
}: ComponentProps<"span"> & { tier: Tier; onHue?: boolean }) {
  return <span className={cn(onHue ? styles.onHue : styles.fill, className)} data-tier={tier} {...props} />;
}

/** Tiny framed card used as a legend for tier counts. */
export function TierSwatch({ tier, className }: { tier: Tier; className?: string }) {
  return <span className={cn(styles.swatch, "h-[18px] w-3.5 shrink-0", className)} data-tier={tier} aria-hidden />;
}
