import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  // Course content is read from disk (src/lib/content/load.ts) and is not in Git: bundle it with
  // every server function of a prebuilt deploy.
  outputFileTracingIncludes: { "/**": ["./content/**/*"] },
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
