import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  // The dev badge sits where the lesson settings button is (bottom left).
  devIndicators: false,
  // Course content is read from disk (src/lib/content/load.ts) and is not in Git: bundle it with
  // every server function of a prebuilt deploy.
  outputFileTracingIncludes: { "/**": ["./content/**/*", "./fixtures/**/*"] },
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
