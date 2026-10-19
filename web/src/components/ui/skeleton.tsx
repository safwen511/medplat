import { cn } from "@/lib/utils";

/** Loading placeholder with a moving sheen. Decorative: the parent carries aria-busy. */
export function Skeleton({ className }: { className?: string }) {
  return <span aria-hidden className={cn("skeleton block", className)} />;
}
