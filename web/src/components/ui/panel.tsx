import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Level-2 surface: a section panel with a clear title row (title left, optional action right). */
export function Panel({
  title,
  subtitle,
  action,
  children,
  className,
  id,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  const headingId = id ? `${id}-title` : undefined;
  return (
    <section
      id={id}
      aria-labelledby={title ? headingId : undefined}
      className={cn("panel flex flex-col gap-6", className)}
    >
      {(title || action) && (
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
          <div className="flex min-w-0 flex-col gap-1">
            {title && (
              <h2 id={headingId} className="text-xl sm:text-2xl">
                {title}
              </h2>
            )}
            {subtitle && <p className="text-sm text-muted">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

/** Consistent vertical rhythm between the panels of a page (48–64px). */
export function PageStack({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("mx-auto flex w-full max-w-6xl flex-col gap-12 sm:gap-16", className)}>{children}</div>
  );
}
