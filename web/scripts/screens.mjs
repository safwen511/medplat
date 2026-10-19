// Screenshots of the running site at tablet (1024x768) and phone (390x844), signed in with a beta
// access code read from the repo-root "vip" file (never stored in this script).
// Usage: node scripts/screens.mjs <out-dir> <member: ala|salsabil|owner> <route> [<route> ...]
// Special routes: "welcome" shoots every welcome slide and finishes it; "revisit" starts a new
// browser session (visit counter +1) and shoots the year home with its "Bon retour" banner.
// "seed" fills this browser's local progress with sample answers and statuses (screenshots only).
// "quiz" opens the year quiz (QCM only), shoots a question, answers it and shoots the feedback.
// "<route>#flip" taps the first card (folder or course) of the page and shoots it flipped.
import { readFileSync } from "node:fs";
import path from "node:path";

import { chromium } from "playwright";

const [outDir, who, ...routes] = process.argv.slice(2);
const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const vip = readFileSync(path.join(import.meta.dirname, "..", "..", "vip"), "utf-8")
  .split("\n")
  .filter((line) => line && !line.startsWith("#"));
const NAMES = { ala: "Ala Arfa", salsabil: "Salsabil Yahyaoui", owner: "Safwen", marwen: "Marwen Yahyaoui" };
const line = vip.find((entry) => entry.startsWith(NAMES[who]));
if (!line) throw new Error(`no code for ${who}`);
const code = line.split(" · ").at(-1).trim();

const SIZES = { tablet: { width: 1024, height: 768 }, phone: { width: 390, height: 844 } };
// CHROMIUM_ARGS: extra flags, e.g. --host-resolver-rules to force IPv4 on a network whose IPv6 is broken.
const browser = await chromium.launch({ args: process.env.CHROMIUM_ARGS?.split(/\s+(?=--)/).filter(Boolean) ?? [] });
try {
  for (const [size, viewport] of Object.entries(SIZES)) {
    const context = await browser.newContext({ viewport, colorScheme: "dark", locale: "fr-FR" });
    const page = await context.newPage();
    await page.goto(`${BASE}/acces`);
    await page.fill('input[name="code"]', code);
    await Promise.all([page.waitForURL(/\/bienvenue/), page.click('button[type="submit"]')]);
    const shoot = async (label) => {
      const name = `${who}-${size}-${label}.png`;
      await page.screenshot({ path: path.join(outDir, name), fullPage: true });
      console.log(name);
    };
    for (const route of routes) {
      if (route === "welcome") {
        await page.goto(`${BASE}/bienvenue`, { waitUntil: "networkidle" });
        for (let slide = 1; ; slide++) {
          await page.waitForTimeout(500);
          await shoot(`welcome-${slide}`);
          const next = page.getByRole("button", { name: "Suivant" });
          if (!(await next.count())) break;
          await next.click();
        }
        const finish = page.getByRole("button", { name: /^(Commencer|DCEM2)/ }).first();
        await Promise.all([page.waitForURL(/\/sfax\//), finish.click()]);
        await page.waitForLoadState("networkidle");
        continue;
      }
      if (route === "seed") {
        const year = { ala: "dcem2", salsabil: "dcem1", owner: "dcem1" }[who];
        const index = JSON.parse(readFileSync(path.join(import.meta.dirname, "..", "content", "sfax", year, "index.json"), "utf-8"));
        const ready = index.certifs.flatMap((c) => c.modules.flatMap((m) => m.lessons)).filter((l) => l.available);
        const now = Date.now();
        const attempts = [];
        ready.forEach((lesson, i) => {
          const n = 4 + ((i * 3) % 7);
          for (let k = 0; k < n; k++)
            attempts.push({
              questionId: `${lesson.id}-q${k}`, questionType: "qcm", lessonId: lesson.id, faculty: "sfax", year,
              mode: "quiz", correct: (k * 7 + i * 5) % 10 < 4 + i, response: null, timeMs: 9000 + ((k * 4111) % 30000),
              hintsUsed: 0, createdAt: new Date(now - ((k + i) % 4) * 86400000).toISOString(),
            });
        });
        const statuses = ["lu", "revise_1", "maitrise", "revise_2"];
        const progress = Object.fromEntries(
          ready.slice(0, 4).map((lesson, i) => [lesson.id, { lessonId: lesson.id, status: statuses[i], revisions: i, updatedAt: new Date(now).toISOString() }]),
        );
        await page.evaluate(([a, p]) => {
          localStorage.setItem("medplat:v1:attempts", JSON.stringify(a));
          localStorage.setItem("medplat:v1:lessonProgress", JSON.stringify(p));
        }, [attempts, progress]);
        continue;
      }
      if (route === "quiz") {
        const year = { ala: "dcem2", salsabil: "dcem1", owner: "dcem1" }[who];
        await page.goto(`${BASE}/sfax/${year}/quiz`, { waitUntil: "networkidle" });
        await shoot("quiz-setup");
        await page.getByRole("button", { name: /^QCM\b/ }).click();
        await page.getByRole("button", { name: "Lancer" }).click();
        await page.waitForTimeout(500);
        await shoot("quiz-question");
        await page.locator('[aria-label="Propositions"] button').first().click();
        await page.getByRole("button", { name: "Valider" }).click();
        await page.waitForTimeout(600);
        await shoot("quiz-feedback");
        continue;
      }
      if (route === "revisit") {
        await context.clearCookies({ name: "medplat_live" });
        await page.evaluate(() => sessionStorage.clear());
        await page.goto(`${BASE}/`);
        await page.getByText("Bon retour").waitFor({ timeout: 15000 }).catch(() => console.log("no banner"));
        await page.waitForTimeout(400);
        await shoot("revisit");
        continue;
      }
      if (route.endsWith("#flip")) {
        await page.goto(`${BASE}${route.slice(0, -5)}`, { waitUntil: "networkidle" });
        await page.locator("button.mpc-deck, .mpc-face button").first().click();
        await page.waitForTimeout(900);
        await page.screenshot({ path: path.join(outDir, `${who}-${size}-flip.png`) });
        console.log(`${who}-${size}-flip.png`);
        continue;
      }
      await page.goto(`${BASE}${route}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(800);
      await shoot(route.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "") || "home");
    }
    await context.close();
  }
} finally {
  await browser.close();
}
