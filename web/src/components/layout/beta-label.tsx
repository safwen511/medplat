import { cn } from "@/lib/utils";

export const BETA_TEXT = "Bêta · gratuit · non relu par un médecin";

/** The persistent, discreet beta notice (docs/design.md). Header on tablets and desktop, footer on phones. */
export function BetaLabel({ className }: { className?: string }) {
  return (
    <p
      className={cn(
        "items-center gap-2 rounded-full border border-border px-3 py-1 text-xs whitespace-nowrap text-muted",
        className,
      )}
    >
      <span aria-hidden className="size-1.5 rounded-full bg-highyield" />
      {BETA_TEXT}
    </p>
  );
}
