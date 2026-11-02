// Screenshots of the preview: pose galleries and a CPU-vs-CPU fight in progress.
import { chromium } from "playwright";
import path from "node:path";
import url from "node:url";
const root = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), "..");
const file = "file://" + path.join(root, "dist", "puppet_brawl_preview.html");
const out = process.argv[2] || path.join(root, "test", "shots");
const which = (process.argv[3] || "base,normals,specials,fight").split(",");
const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" }).catch(() => chromium.launch());
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
for (const g of ["base", "normals", "specials"]) {
  if (!which.includes(g)) continue;
  await page.goto(file + "?gallery=" + g + (process.argv.includes("--hurt") ? "&hurt=1" : ""));
  await page.waitForTimeout(300);
  await page.locator("#cv").screenshot({ path: path.join(out, "gallery_" + g + ".png") });
}
if (which.includes("fight")) {
  await page.goto(file);
  await page.waitForTimeout(300);
  // the page opens in attract mode (CPU vs CPU) by itself
  for (const t of [2600, 4500, 7000, 9000]) {
    await page.waitForTimeout(t === 2600 ? 2600 : 1900);
    await page.locator("#cv").screenshot({ path: path.join(out, `fight_${t}.png`) });
  }
}
console.log(errors.length ? "ERRORS:\n" + errors.join("\n") : "no page errors");
await browser.close();
