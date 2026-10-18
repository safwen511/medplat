import { cn } from "@/lib/utils";

export const BETA_TEXT = "Bêta · gratuit · non relu par un médecin";

/** The persistent, discreet beta notice (docs/design.md). Header on tablets and desktop, footer on phones. */
export function BetaLabel({ className }: { className?: string }) {
  return <p className={cn("text-sm text-muted", className)}>{BETA_TEXT}</p>;
}
