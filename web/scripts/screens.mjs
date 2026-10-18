// Screenshots of the running site at tablet (1024x768) and phone (390x844), signed in with a beta
// access code read from the repo-root "vip" file (never stored in this script).
// Usage: node scripts/screens.mjs <out-dir> <member: ala|salsabil|owner> <route> [<route> ...]
import { readFileSync } from "node:fs";
import path from "node:path";

import { chromium } from "playwright";

const [outDir, who, ...routes] = process.argv.slice(2);
const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const vip = readFileSync(path.join(import.meta.dirname, "..", "..", "vip"), "utf-8")
  .split("\n")
  .filter((line) => line && !line.startsWith("#"));
const NAMES = { ala: "Ala Arfa", salsabil: "Salsabil Yahyaoui", owner: "Safwen" };
const line = vip.find((entry) => entry.startsWith(NAMES[who]));
if (!line) throw new Error(`no code for ${who}`);
const code = line.split(" · ").at(-1).trim();

const SIZES = { tablet: { width: 1024, height: 768 }, phone: { width: 390, height: 844 } };
const browser = await chromium.launch();
try {
  for (const [size, viewport] of Object.entries(SIZES)) {
    const context = await browser.newContext({ viewport, colorScheme: "dark", locale: "fr-FR" });
    const page = await context.newPage();
    await page.goto(`${BASE}/acces`);
    await page.fill('input[name="code"]', code);
    await Promise.all([page.waitForURL(/\/bienvenue/), page.click('button[type="submit"]')]);
    for (const route of routes) {
      await page.goto(`${BASE}${route}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(800);
      const name = `${who}-${size}-${route.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "") || "home"}.png`;
      await page.screenshot({ path: path.join(outDir, name), fullPage: true });
      console.log(name);
    }
    await context.close();
  }
} finally {
  await browser.close();
}
