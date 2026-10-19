// Feature flags, read at build time.

/**
 * Figures cut from the faculty documents. Off for now: lesson pages and exercises show no
 * images (the pipeline still extracts and exports them). Turn on with NEXT_PUBLIC_SHOW_FIGURES=true.
 */
export const SHOW_FIGURES = process.env.NEXT_PUBLIC_SHOW_FIGURES === "true";
