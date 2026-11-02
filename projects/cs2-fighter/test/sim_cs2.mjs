// Runs the real built puppet_brawl.js against the mock point_script module.
import fs from "node:fs";
import path from "node:path";
import url from "node:url";
const here = path.dirname(url.fileURLToPath(import.meta.url));
const built = fs.readFileSync(path.join(here, "..", "dist", "addon", "scripts", "puppet_brawl.js"), "utf8");
fs.writeFileSync(path.join(here, "tmp_script.mjs"), built.replace('from "cs_script/point_script"', 'from "./mock_point_script.mjs"'));

const M = await import("./mock_point_script.mjs");
const { sim, stats, Entity, BaseModelEntity, PointTemplate, CustomHudLayout, CSInputs, CSMoveType, CustomCameraMode } = M;

// ---- the test map: stage along +X, audience at -Y
new Entity("pb_stage_left", "info_target", { x: -450, y: 0, z: 0 });
new Entity("pb_stage_right", "info_target", { x: 450, y: 0, z: 0 });
const padPos = [{ x: -300, y: -900, z: 0 }, { x: -100, y: -900, z: 0 }, { x: 100, y: -900, z: 0 }, { x: 300, y: -900, z: 0 }];
padPos.forEach((p, i) => new Entity("pb_pad_" + (i + 1), "info_target", p));
new Entity("pb_watch_1", "info_target", { x: 0, y: -1200, z: 0 });
new Entity("pb_exit", "info_target", { x: 0, y: -1000, z: 0 });
new PointTemplate("pb_tpl_ball", "models/puppet_brawl/pb_ball.vmdl", { x: 0, y: 0, z: -500 });
const AGENTS = { timber: "agents/models/tm_professional/tm_professional_varf.vmdl", brass: "agents/models/ctm_swat/ctm_swat_varianth.vmdl", pirouette: "agents/models/ctm_fbi/ctm_fbi_variantb.vmdl", motley: "agents/models/tm_leet/tm_leet_variantf.vmdl" };
for (const [id, m] of Object.entries(AGENTS)) new PointTemplate("pb_tpl_" + id, ["models/puppet_brawl/rig/pb_rig.vmdl", m], { x: 0, y: 0, z: -500 });
for (const k of ["proj_knot", "proj_cog", "proj_jball", "fx_ring", "fx_burst", "fx_orb"]) new PointTemplate("pb_tpl_" + k, "models/puppet_brawl/pb_" + k + ".vmdl", { x: 0, y: 0, z: -500 });
for (const k of ["sparks", "zap", "arc", "streak", "firework", "confetti", "dust", "embers"]) new PointTemplate("pb_tpl_fx_" + k, "particle:" + k, { x: 0, y: 0, z: -500 });
new Entity("pb_stage_text", "point_worldtext"); new Entity("pb_stage_sub", "point_worldtext");
const CLIPS = JSON.parse(fs.readFileSync(path.join(here, "..", "dist", "rig_clips.json"), "utf8"));
const hud = new CustomHudLayout("pb_hud");
for (const s of ["hit", "heavy", "block", "ko", "bell", "tick", "select", "win"]) new Entity("pb_snd_" + s, "point_soundevent");

const alice = sim.addPlayer(0, "Alice", { ...padPos[0] });
let bob = sim.addPlayer(1, "Bob", { ...padPos[1] });
const cara = sim.addPlayer(2, "Cara", { x: 0, y: -1200, z: 0 });

await import("./tmp_script.mjs");
sim.fire("activate");
sim.tick(4);

const fails = [];
const check = (cond, msg) => { if (!cond) { fails.push(msg); console.log("FAIL: " + msg); } else console.log("ok   " + msg); };
const tap = (pawn, bits) => { pawn.press(bits); sim.tick(1); pawn._held &= ~bits; sim.tick(1); };
const hold = (pawn, bits, ticks) => { pawn._held |= bits; pawn._just |= bits; sim.tick(ticks); pawn._held &= ~bits; };

check(stats.cmds.includes("bot_kick") && stats.cmds.includes("mp_ignore_round_win_conditions 1"), "arena commands sent (bots kicked, rounds never end)");
check(stats.msgs.some((m) => m.includes("ready:")), "script initialised: " + (stats.msgs.find((m) => m.includes("ready")) || stats.msgs.join(" | ")));

// ---- joining
tap(alice, CSInputs.USE);
tap(bob, CSInputs.USE);
check(alice._moveType === CSMoveType.NONE && bob._moveType === CSMoveType.NONE, "both players frozen at their pads");
check(alice._cam && alice._cam._mode === CustomCameraMode.CONTROLLED, "fight camera taken (CONTROLLED)");
check(alice._cam && alice._cam._parent === undefined, "camera unparented for control");
check(hud.pclasses.get("0:pb_game.Hidden") === false, "HUD shown to Alice");
check(alice._weapons.length === 0, "Alice's weapons put away while she plays (WEAPONS strip)");

// ---- lobby: pick a different fighter, ready up
tap(alice, CSInputs.RIGHT);
tap(alice, CSInputs.ATTACK);
tap(bob, CSInputs.ATTACK);
sim.tick(64 * 4);
check(hud.classes.get("pb_game.InMatch") === true, "match started after countdown");
check(hud.vars.get("pb_c1_name.t") === "Alice" && hud.vars.get("pb_c2_name.t") === "Bob", "cards show both players: " + hud.vars.get("pb_c1_name.t") + " / " + hud.vars.get("pb_c2_name.t"));
const rigs = () => M.sim.ents.filter((e) => e._valid && String(e._model || "").includes("pb_rig") && e._name.startsWith("pb_rig_"));
check(rigs().length >= 2, "fighter bodies spawned (rig + agent): " + rigs().length);
const animIn = () => stats.inputs.filter((i) => i.input.startsWith("SetAnimation"));
check(animIn().length >= 2 && animIn().every((i) => CLIPS[i.value]), "rigs told to play known clips: " + [...new Set(animIn().map((i) => i.value))].join(","));

// ---- fight with random mashing for 45 seconds
const keys = [CSInputs.LEFT, CSInputs.RIGHT, CSInputs.ATTACK, CSInputs.ATTACK2, CSInputs.FORWARD, CSInputs.BACK, CSInputs.WALK, CSInputs.RELOAD, CSInputs.LOOK_AT_WEAPON];
let seed = 99;
const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
const moves0 = stats.moves;
for (let t = 0; t < 64 * 45; t++) {
  for (const p of [alice, bob]) {
    if (t % 6 === 0) {
      p._held = 0;
      const k = keys[Math.floor(rnd() * keys.length)];
      p.press(k);
      if (rnd() < 0.5) p._held |= (p === alice ? CSInputs.RIGHT : CSInputs.LEFT);
    }
  }
  sim.tick(1);
}
alice._held = 0; bob._held = 0;
check(stats.moves - moves0 > 64 * 30, "rigs moved with Move(): " + (stats.moves - moves0));
const played = new Set(animIn().map((i) => i.value));
check(["jab", "kickMid", "walkf"].some((c) => played.has(c)) && played.size >= 6, "fight drove varied clips: " + [...played].join(","));
{
  const table = JSON.parse(fs.readFileSync(new URL("../dist/rig_clips.json", import.meta.url), "utf8"));
  const missing = [...played].filter((c) => !table[c]);
  check(!missing.length, "every clip played exists in the rig: " + (missing.join(",") || "ok"));
}
check(stats.inputs.some((i) => i.input === "SetPlaybackRate" && i.value === 0), "hitstop pauses the animation (rate 0)");
const agentsMerged = M.sim.ents.filter((e) => e._valid && e._name === "pb_agent" && e._parent && String(e._parent._model || "").includes("pb_rig"));
check(agentsMerged.length >= 2, "agents stay parented to their rigs: " + agentsMerged.length);
const hp1 = hud.classes, widths = [...hud.classes.entries()].filter(([k, v]) => v && /pb_c[12]_fill\.w\d+/.test(k)).map(([k]) => k);
check(widths.length >= 1, "health bars set: " + widths.join(", "));
check(stats.fired.some((f) => f.startsWith("pb_snd_hit") || f.startsWith("pb_snd_heavy")), "hit sounds fired: " + stats.fired.filter((f) => /hit|heavy/.test(f)).length);

// ---- Bob holds E to leave
hold(bob, CSInputs.USE, 64);
check(bob._moveType === CSMoveType.WALK, "Bob unfrozen after holding E");
check(bob._weapons.length >= 2, "Bob got his weapons back: " + bob._weapons.map((w) => w._cls).join(","));
check(bob._cam._mode === CustomCameraMode.DISABLED, "Bob's camera handed back");
check(Math.abs(bob._pos.y - -1000) < 1, "Bob dropped at pb_exit");
check(hud.pclasses.get("1:pb_game.Hidden") === undefined, "Bob's HUD override reset");
sim.tick(64 * 5);
check(stats.say.length >= 1, "match result in chat: " + stats.say.join(" | "));

// ---- add CPUs with map buttons and start
const say0 = stats.say.length;
sim.scriptInputs.ModeFFA({});
sim.scriptInputs.AddCPU({});
sim.scriptInputs.AddCPU({});
sim.tick(4);
{
  const said = stats.say.slice(say0).join(" | ");
  check(/mode: FREE-FOR-ALL/.test(said) && (said.match(/CPU added on pad/g) || []).length === 2, "buttons report in chat: " + said);
}
tap(alice, CSInputs.ATTACK);
sim.tick(64 * 5);
check(hud.classes.get("pb_game.Mode_ffa") === true && hud.classes.get("pb_game.InMatch") === true, "FFA match with CPUs started");
for (let t = 0; t < 64 * 30; t++) { if (t % 8 === 0) { alice._held = 0; alice.press(keys[Math.floor(rnd() * keys.length)]); } sim.tick(1); }

// ---- spectator spot
tap(cara, CSInputs.USE);
check(cara._cam && cara._cam._mode === CustomCameraMode.CONTROLLED, "Cara is watching with the fight camera");
sim.tick(40);
tap(cara, CSInputs.USE);
check(cara._cam._mode === CustomCameraMode.DISABLED && cara._moveType === CSMoveType.WALK, "Cara stopped watching");

// ---- damage protection
const dmg = sim.hooks.modifyDamage[0]({ player: alice, damage: 50 });
check(dmg && dmg.abort === true, "players at the controls are protected");

// ---- death releases the player
const removedBefore = stats.removed;
sim.fire("kill", { player: alice });
check(alice._moveType === CSMoveType.WALK && alice._cam._mode === CustomCameraMode.DISABLED, "killed player released");

// ---- round restart
sim.tick(70);   // re-entry cooldown
tap(alice, CSInputs.USE);
check(alice._moveType === CSMoveType.NONE, "Alice rejoined");
sim.fire("beginRoundRestart");
sim.fire("roundStart");
check(alice._moveType === CSMoveType.WALK && alice._cam._mode === CustomCameraMode.DISABLED, "round restart releases players");
sim.tick(64);
check(stats.msgs.filter((m) => m.includes("ready:")).length >= 2, "re-initialised after round start");
check(stats.removed > removedBefore, "old parts removed: " + (stats.removed - removedBefore));

// ---- tools-mode reload
sim.hooks.reload.before();
sim.hooks.reload.after();
sim.tick(10);
check(stats.msgs.filter((m) => m.includes("ready:")).length >= 3, "re-initialised after script reload");

// ---- cheat commands
sim.cheats.pb_status("");
sim.cheats.pb_cpu_match("");
sim.tick(64 * 8);
check(hud.classes.get("pb_game.InMatch") === true, "pb_cpu_match starts a CPU-only match");

const scriptErrors = stats.msgs.filter((m) => m.includes("script error") || m.includes("failed"));
check(scriptErrors.length === 0, "no script errors" + (scriptErrors.length ? ": " + scriptErrors.slice(0, 3).join(" || ") : ""));
check(stats.errors.length === 0, "no invalid values" + (stats.errors.length ? ": " + stats.errors.slice(0, 5).join(", ") : ""));
// ---- tag team with CPUs: only two on stage, benched partners at the back
{
  sim.scriptInputs.Reset({}); sim.tick(4);
  sim.scriptInputs.ModeTeams({});
  for (let i = 0; i < 4; i++) sim.scriptInputs.AddCPU({});
  sim.cheats.pb_cpu_match();
  sim.tick(64 * 6);
  check(hud.classes.get("pb_game.Mode_teams") === true && hud.classes.get("pb_game.InMatch") === true, "tag team CPU match running");
  for (let t = 0; t < 64 * 40; t++) { sim.tick(1); }
  sim.cheats.pb_stop(); sim.tick(8);
  check(stats.say.slice(-3).some((x) => /CPUs? removed/.test(x)), "STOP CPUs reports in chat: " + stats.say.slice(-2).join(" | "));
}

// ---- effects: projectile models, rings, particles, stage text
{
  const models = new Set(sim.ents.filter((e) => e._model).map((e) => e._model));
  for (const k of ["pb_proj_knot", "pb_fx_ring", "pb_fx_burst", "pb_fx_orb"]) check([...models].some((m) => m.includes(k)), "effect model used: " + k);
  const fx = sim.ents.filter((e) => e._cls === "info_particle_system");
  check(fx.length > 0, "particles spawned: " + [...new Set(fx.map((e) => e._effect))].join(", "));
  check(fx.filter((e) => e._valid).length <= 14, "particles cleaned up (" + fx.filter((e) => e._valid).length + " alive of " + fx.length + ")");
  check((stats.text || []).some((t) => t.startsWith("pb_stage_text=") && t.length > 16), "stage text shows the announcer: " + (stats.text || []).filter((t) => t.startsWith("pb_stage_text=") && t.length > 16).slice(0, 3).join(" | "));
  check((stats.text || []).some((t) => t.startsWith("pb_stage_sub=") && t.includes(" - ")), "stage sub-line calls specials: " + (stats.text || []).filter((t) => t.startsWith("pb_stage_sub=") && t.includes(" - ")).slice(0, 3).join(" | "));
  const knot = sim.ents.find((e) => e._model && e._model.includes("pb_proj_knot"));
  check(!knot || Number.isFinite(knot._ang.pitch), "projectile spin angle set");
}

console.log(`\nspawned ${stats.spawned}, removed ${stats.removed}, teleports ${stats.teleports}, moves ${stats.moves}, scale ${stats.scale}, color ${stats.color}, hud vars ${stats.hudVar}/${stats.hudVarP}, classes ${stats.hudClass}/${stats.hudClassP}`);
console.log("warnings:", stats.msgs.filter((m) => m.includes("WARNING")).join(" | ") || "none");
console.log(fails.length ? `\n${fails.length} FAILED` : "\nALL PASSED");
process.exit(fails.length ? 1 : 0);
