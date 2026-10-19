import { cn } from "@/lib/utils";

/** MedPlat mark: a file folder whose edge is a heartbeat. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className={cn("size-7", className)}>
      <defs>
        <linearGradient id="medplat-mark" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--primary)" />
          <stop offset="1" stopColor="var(--primary)" stopOpacity="0.55" />
        </linearGradient>
      </defs>
      <path
        d="M4 9.5A3.5 3.5 0 0 1 7.5 6h5.2c.9 0 1.7.4 2.3 1l1.2 1.3c.4.4.9.7 1.5.7h6.8A3.5 3.5 0 0 1 28 12.5v10A3.5 3.5 0 0 1 24.5 26h-17A3.5 3.5 0 0 1 4 22.5Z"
        fill="url(#medplat-mark)"
        opacity="0.18"
      />
      <path
        d="M4 9.5A3.5 3.5 0 0 1 7.5 6h5.2c.9 0 1.7.4 2.3 1l1.2 1.3c.4.4.9.7 1.5.7h6.8A3.5 3.5 0 0 1 28 12.5v10A3.5 3.5 0 0 1 24.5 26h-17A3.5 3.5 0 0 1 4 22.5Z"
        fill="none"
        stroke="url(#medplat-mark)"
        strokeWidth="1.6"
      />
      <path
        d="M7 18h4.5l1.6-3.2 2.4 6.4 2.2-8.4 1.8 5.2H25"
        fill="none"
        stroke="var(--primary)"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Mark and wordmark. */
export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LogoMark />
      <span className="font-heading text-[1.15rem] font-semibold tracking-[-0.03em]">MedPlat</span>
    </span>
  );
}
