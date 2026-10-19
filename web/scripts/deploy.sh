#!/usr/bin/env bash
# Build here and upload to Vercel (the content and figures are not in Git, see docs/progress.md).
# Usage: scripts/deploy.sh [--prod]      (without --prod: a private preview deployment)
# While NEXT_PUBLIC_SHOW_FIGURES is not "true", the figures are moved out of public/ for the build,
# so they are neither uploaded nor served, then put back.
set -euo pipefail
cd "$(dirname "$0")/.."
export NODE_OPTIONS=--dns-result-order=ipv4first # this network's IPv6 route to Vercel is broken
VERCEL="npx vercel@64.5.0"

prod=""
target="preview"
if [[ "${1:-}" == "--prod" ]]; then prod="--prod"; target="production"; fi

parked=""
if [[ "${NEXT_PUBLIC_SHOW_FIGURES:-}" != "true" && -d public/figures ]]; then
  parked="../data/web-figures-parked"
  rm -rf "$parked"
  mv public/figures "$parked"
  trap 'mv "$parked" public/figures' EXIT
fi

$VERCEL pull --yes --environment="$target"
if [[ -n "$prod" ]]; then $VERCEL build --prod; else $VERCEL build --target=preview; fi
# One archive instead of thousands of files (the free plan refuses >5000 file uploads a day).
$VERCEL deploy --prebuilt $prod --archive=tgz
