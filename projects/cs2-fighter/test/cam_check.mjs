// Projects the script's real entity output through a Source-style camera to check framing.
import fs from "node:fs";
import path from "node:path";
import url from "node:url";
const here = path.dirname(url.fileURLToPath(import.meta.url));
const built = fs.readFileSync(path.join(here, "..", "dist", "addon", "scripts", "puppet_brawl.js"), "utf8");
fs.writeFileSync(path.join(here, "tmp_script2.mjs"), built.replace('from "cs_script/point_script"', 'from "./mock_point_script.mjs"'));
const M = await import("./mock_point_script.mjs");
const { sim, Entity, PointTemplate, CustomHudLayout, CSInputs } = M;

// a stage rotated 30 degrees so yaw maths is exercised
const yaw = 30 * Math.PI / 180, R = { x: Math.cos(yaw), y: Math.sin(yaw) };
const C = { x: 1000, y: 500, z: 64 };
new Entity("pb_stage_left", "info_target", { x: C.x - R.x * 450, y: C.y - R.y * 450, z: C.z });
new Entity("pb_stage_right", "info_target", { x: C.x + R.x * 450, y: C.y + R.y * 450, z: C.z });
const D = { x: R.y, y: -R.x };   // audience side
const pads = [0, 1, 2, 3].map((i) => ({ x: C.x + D.x * 900 + R.x * (i - 1.5) * 150, y: C.y + D.y * 900 + R.y * (i - 1.5) * 150, z: C.z }));
pads.forEach((p, i) => new Entity("pb_pad_" + (i + 1), "info_target", p));
for (const m of ["limb", "block", "ball"]) { const t = new PointTemplate("pb_tpl_" + m, m, { x: 0, y: 0, z: -900 }); }
new CustomHudLayout("pb_hud");
const a = sim.addPlayer(0, "A", pads[0]), b = sim.addPlayer(1, "B", pads[1]);
await import("./tmp_script2.mjs");
sim.fire("activate"); sim.tick(3);
const tap = (p, bits) => { p.press(bits); sim.tick(1); p._held &= ~bits; sim.tick(1); };
tap(a, CSInputs.USE); tap(b, CSInputs.USE); tap(a, CSInputs.ATTACK); tap(b, CSInputs.ATTACK);
sim.tick(64 * 5.5);
const out = [];
for (const [label, ticks] of [["start", 0], ["mid", 64 * 3]]) {
  // walk A forward a bit for the second shot
  if (ticks) { a._held = CSInputs.RIGHT; sim.tick(ticks); a._held = 0; sim.tick(8); }
  const cam = a._cam;
  const parts = M.sim.ents.filter((e) => e._valid && e._cls === "prop_dynamic" && e._scale > 0.05).map((e) => ({ p: e._pos, ang: e._ang, s: e._scale, m: e._model, c: e._color }));
  out.push({ label, cam: { pos: cam._pos, ang: cam._ang }, parts });
}
fs.writeFileSync(path.join(here, "cam_frames.json"), JSON.stringify({ stage: { C, R, D }, frames: out }));
console.log("frames", out.map((f) => f.label + ":" + f.parts.length).join(" "), "cam", JSON.stringify(out[0].cam));
