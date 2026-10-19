import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** An open section of "Mon espace" (no box), reachable by anchor (#id): title row over a hairline. */
export function EspaceSection({
  id,
  title,
  description,
  action,
  children,
  className,
}: {
  id: string;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-titre`} className={cn("flex scroll-mt-28 flex-col gap-6", className)}>
      <div className="flex flex-col gap-1 border-b border-border pb-4">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4">
          <h2 id={`${id}-titre`} className="text-xl leading-tight sm:text-2xl">
            {title}
          </h2>
          {action}
        </div>
        {description && <p className="text-sm text-muted">{description}</p>}
      </div>
      {children}
    </section>
  );
}

/** Quiet text link with a 48px tap height. */
export const textLink =
  "inline-flex min-h-12 items-center gap-1.5 rounded-card text-[0.9375rem] font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/** Empty state: one short sentence, plus at most one action. */
export function EmptyState({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-1">
      <p className="text-muted">{children}</p>
      {action}
    </div>
  );
}
