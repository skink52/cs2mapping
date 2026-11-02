// Rough browser approximation of the Panorama HUD (flow-children / align / margins) for
// layout sanity checks. Not pixel exact - Panorama is its own engine.
import fs from "node:fs";
import path from "node:path";
import url from "node:url";
import { chromium } from "playwright";
const root = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), "..");
const xml = fs.readFileSync(path.join(root, "dist/addon/panorama/layout/custom_game/puppet_brawl.xml"), "utf8");
let css = fs.readFileSync(path.join(root, "dist/addon/panorama/styles/custom_game/puppet_brawl.css"), "utf8");

const hex = (h) => { h = h.slice(1); if (h.length === 8) return `rgba(${parseInt(h.slice(0, 2), 16)},${parseInt(h.slice(2, 4), 16)},${parseInt(h.slice(4, 6), 16)},${(parseInt(h.slice(6, 8), 16) / 255).toFixed(3)})`; return "#" + h; };
css = css
  .replace(/#[0-9a-f]{8}\b/gi, (m) => hex(m))
  .replace(/background-color:\s*gradient\(\s*linear,\s*0% 0%,\s*(0% 100%|100% 0%),\s*from\(\s*([^)]+?)\s*\),\s*(?:color-stop\(\s*([\d.]+),\s*([^)]+?)\s*\),\s*)?to\(\s*([^)]+?)\s*\)\s*\)/gi,
    (m, dir, a, at, mid, b) => `background: linear-gradient(${dir === "0% 100%" ? "180deg" : "90deg"}, ${a}${mid ? `, ${mid} ${Math.round(at * 100)}%` : ""}, ${b})`)
  .replace(/pre-transform-rotate2d:\s*([-\d.]+deg)/g, "rotate: $1")
  .replace(/animation-name:\s*([\w-]+)/g, "animation-name: '$1'")
  .replace(/horizontal-align:\s*(\w+)/g, "--ha: $1")
  .replace(/vertical-align:\s*(\w+)/g, "--va: $1")
  .replace(/flow-children:\s*down/g, "display: flex; flex-direction: column")
  .replace(/flow-children:\s*right/g, "display: flex; flex-direction: row")
  .replace(/flow-children:\s*left/g, "display: flex; flex-direction: row-reverse")
  .replace(/pre-transform-scale2d:\s*([\d.]+)/g, "transform: scale($1)")
  .replace(/text-shadow:\s*([-\d.]+px)\s+([-\d.]+px)\s+([-\d.]+px)\s+[\d.]+\s+(#[0-9a-f]+|rgba\([^)]*\))/gi, "text-shadow: $1 $2 $3 $4")
  .replace(/box-shadow:\s*(#[0-9a-f]+|rgba\([^)]*\))\s+([-\d.]+px)\s+([-\d.]+px)\s+([-\d.]+px)\s+([-\d.]+px)/gi, "box-shadow: $2 $3 $4 $5 $1")
  .replace(/visibility:\s*collapse/g, "display: none")
  .replace(/visibility:\s*visible/g, "display: block")
  .replace(/font-weight:\s*black/g, "font-weight: 900")
  .replace(/transition-[a-z-]+:[^;]+;/g, "");

const body = xml
  .replace(/<styles>[\s\S]*?<\/styles>/, "")
  .replace(/<root>|<\/root>/g, "")
  .replace(/<Panel([^>]*)\/>/g, "<div$1></div>")
  .replace(/<Panel/g, "<div").replace(/<\/Panel>/g, "</div>")
  .replace(/<Label([^>]*)text="([^"]*)"([^>]*)\/>/g, (m, a, t, b) => `<span${a}${b} data-t="${t}">${t}</span>`)


const html = `<!doctype html><html><head><style>
html,body{margin:0;width:1920px;height:1080px;overflow:hidden;font-family:"Segoe UI",Arial,sans-serif;background:#3d2f2a}
div,span{box-sizing:border-box;position:relative}\n@property --ha { syntax: '*'; inherits: false; }\n@property --va { syntax: '*'; inherits: false; }
span{display:block;white-space:nowrap}
.bg{position:absolute;inset:0;background:linear-gradient(#1b1530,#3b2a3c 70%,#6b4a2e 70%,#2a1b10)}
${css}
</style></head><body><div class="bg"></div>${body}
<script>
window.layout = () => {
  for (const el of document.querySelectorAll("div, span")) {
    const p = el.parentElement; if (!p || el.classList.contains("bg")) continue;
    const pd = getComputedStyle(p).display;
    if (pd === "flex") { const cs = getComputedStyle(el); const ha = cs.getPropertyValue("--ha").trim(); if (ha === "center") el.style.alignSelf = "center"; if (ha === "right" && getComputedStyle(p).flexDirection === "column") el.style.alignSelf = "flex-end"; continue; }
    const cs = getComputedStyle(el);
    const ha = cs.getPropertyValue("--ha").trim() || "left", va = cs.getPropertyValue("--va").trim() || "top";
    el.style.position = "absolute";
    const ml = cs.marginLeft, mr = cs.marginRight, mt = cs.marginTop, mb = cs.marginBottom;
    el.style.margin = "0";
    if (ha === "left") el.style.left = ml; else if (ha === "right") el.style.right = mr; else { el.style.left = "50%"; el.style.translate = "-50% 0"; }
    if (va === "top") el.style.top = mt; else if (va === "bottom") el.style.bottom = mb; else { el.style.top = "50%"; el.style.translate = (el.style.translate ? "-50% " : "0 ") + "calc(-50% - " + mb + ")"; }
    if (!el.style.width && cs.width === "auto") el.style.width = "max-content";
  }
};
window.setState = (s) => {
  for (const [id, v] of Object.entries(s.vars || {})) { const e = document.getElementById(id); if (e) e.textContent = v; }
  for (const [id, cls] of Object.entries(s.classes || {})) { const e = document.getElementById(id); if (!e) continue; for (const [c, on] of Object.entries(cls)) e.classList.toggle(c, on); }
};
</script></body></html>`;
fs.writeFileSync(path.join(root, "test", "hud_preview.html"), html);

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto("file://" + path.join(root, "test", "hud_preview.html"));
const common = { pb_footer: "A/D move   W jump   S crouch   MOUSE1 punch   MOUSE2 kick   SHIFT block   R special   F throw   hold E leave" };
const lobby = {
  vars: { ...common, pb_lobby_mode: "MODE: WINNER STAYS 1v1", pb_lobby_s1: "P1  skink52   TIMBER   READY", pb_lobby_s2: "P2  Bob   PIROUETTE   picking...", pb_lobby_s3: "P3  CPU 3   BRASS   CPU", pb_lobby_s4: "P4  - open -   stand on pad 4 and press E",
    pb_lobby_count: "Waiting for everyone to press MOUSE1 (ready)", pb_lobby_hint: "skink52 (host): R = change mode   F = add/remove CPU",
    pb_me: "YOU: P1  RED  -  TIMBER:  Sparring dummy. Balanced boxer with big gloves.", pb_moves: "R: Knot Shot     FWD+R: Haymaker     DOWN+R: Rising Splinter", pb_motions: "B,F+P   F,F+P   D,F+P", pb_status: "Locked in - MOUSE2 to change" },
  classes: { pb_game: { Hidden: false, InLobby: true }, pb_lobby_s1: { Taken: true, Ready: true, Me: true }, pb_lobby_s2: { Taken: true }, pb_lobby_s3: { Taken: true, Ready: true } },
};
await page.evaluate((s) => { setState(s); layout(); }, lobby);
await page.screenshot({ path: path.join(root, "test/shots/hud_lobby.png") });
await page.reload();
const fight = {
  vars: { ...common, pb_c1_name: "skink52", pb_c1_fighter: "TIMBER", pb_c2_name: "Bob", pb_c2_fighter: "PIROUETTE", pb_c1_combo: "3 HIT COMBO  22 DMG", pb_c1_best: "BEST 5 HITS", pb_timer: "47", pb_queue: "NEXT UP: CPU 3     STREAK: skink52 x2", pb_announce: "K.O." },
  classes: { pb_game: { Hidden: false, InMatch: true }, pb_c1: { Show: true, Col0: true, Me: true, HasCombo: true, HasBest: true }, pb_c2: { Show: true, Col1: true, Low: true }, pb_c1_fill: { w100: false, w72: true }, pb_c1_chip: { w100: false, w80: true }, pb_c2_fill: { w100: false, w18: true }, pb_c2_chip: { w100: false, w30: true }, pb_c1_pip1: { Won: true }, pb_announce: { Show: true, St_ko: true } },
};
await page.evaluate((s) => { setState(s); layout(); }, fight);
await page.screenshot({ path: path.join(root, "test/shots/hud_fight.png") });
await page.reload();
const four = {
  vars: { ...common, pb_c1_name: "skink52", pb_c1_fighter: "TIMBER", pb_c2_name: "Bob", pb_c2_fighter: "BRASS", pb_c3_name: "Cara", pb_c3_fighter: "MOTLEY", pb_c4_name: "CPU 4", pb_c4_fighter: "PIROUETTE", pb_c4_combo: "2 HITS", pb_timer: "8", pb_announce: "ROUND 2" },
  classes: { pb_game: { Hidden: false, InMatch: true }, pb_c1: { Show: true, Col0: true }, pb_c2: { Show: true, Col1: true, Me: true }, pb_c3: { Show: true, Col4: true, KO: true }, pb_c4: { Show: true, Col5: true, HasCombo: true },
    pb_c3_fill: { w100: false, w0: true }, pb_c3_chip: { w100: false, w0: true }, pb_c1_fill: { w100: false, w55: true }, pb_c4_fill: { w100: false, w40: true }, pb_timer: { Low: true }, pb_announce: { Show: true, St_big: true } },
};
await page.evaluate((s) => { setState(s); layout(); }, four);
await page.screenshot({ path: path.join(root, "test/shots/hud_four.png") });
await browser.close();
console.log("hud shots done");
