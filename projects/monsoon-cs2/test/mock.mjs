// Runs the built mg_monsoon script (tools/build_script.mjs) against a stand-in cs_script engine: only the CURRENT API names exist
// (Entities.*, Console.*, GameRules.*, ent.FireInput; any other Instance.* name throws). The world is out/entities.json when the map
// generator has written it, otherwise every CONTRACT entity is synthesised from out/layout.json, so this runs before the map exists.
// Humans are driven through every role (pilot flying / landing / boarding riders, gunners, emplaced guns, battery crews, observers,
// kit changes, captures); bots walk at flags, and in low population the script's AI roles must come alive.
//
// usage: node test/mock.mjs [players=32] [seconds=600] [key=value ...]
//   humans=<n>        how many of the players are human (default: 2 of 3; players < 16: all, bots join through bot_quota)
//   seed=<n>          random seed (the script's Math.random too)
//   scenario=<name>   churn   disconnects, slots changing hands, team switches, spectating, suicides, in every seat
//                     restart rounds ending while helicopters fly: CS2 restarts, and the script's own restart, alternately
//                     edge    set pieces: helicopter shot down full of riders, pilot quits mid-air, deaths at the board / gun / rack,
//                             two E presses on one seat, contested flags, ticket underflow (runs with the HUD additions on)
//                     reload  the script reloaded in the tools twice, mid-round
//                     review2 review pass 2's bug classes (run with humans=4 so the AI holds seats; the river bed is cut into the
//                             ground): a departed controller left in its slot, one AI helicopter per waiting human and a withdrawn
//                             request, a pilot gone over the river, a pilot back on his pad, an AI gunner in an abandoned helicopter,
//                             control characters in a name sent with say
//   piece=<text>      only the set pieces whose name contains <text> (one bug class at a time, e.g. scenario=edge piece="shot down")
//   script=<file>     run that built script instead of building src/ (e.g. out/review2/before_review2.js: the build before pass 2)
//   river=1           the river bed lies below the water (layout river line, 180 u each side); on in scenario=review2
//   hudnew=1          out/hud.json is given the "HUD additions (pass 1)" ids, so the script uses them
//   mode=balance      real CONFIG (400 tickets, 15 s captures), a stand-in infantry fight, one round, a JSON result line
//                     (test/sim_balance.mjs runs many of these); json=1 prints only that line
// Default runs with 16+ players also play the FEATURE set pieces (Beehive, marksman, gun repair, AT vs helicopter, smoke, counter-
// battery, flight envelope, wreck, spawn modes, AFK, late join ...) and print a coverage table: feature -> times exercised. A listed
// feature at 0 fails the run (600 s runs only: shorter ones print the table).
// Fails on: a script error, a non-finite or out-of-world position, an input fired at a missing entity or one its class does not
// have, a HUD id / class outside docs/SCRIPT.md, a state leak (a pawn left shrunk, frozen or on a seat camera; a seat, crew, gun or
// helicopter pointing at a player who is not there), no round end, tickets not moving, no capture, no flight, and so on.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { build } from '../tools/build_script.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const argv = process.argv.slice(2), posArgs = argv.filter((a) => !a.includes('=')), opt = Object.fromEntries(argv.filter((a) => a.includes('=')).map((a) => a.split('=')));
const N = +(posArgs[0] || 32), SECONDS = +(posArgs[1] || 600);
const SCEN = opt.scenario || '', BAL = opt.mode === 'balance', JSONONLY = opt.json === '1';
const LOWPOP = N < 16 && opt.humans === undefined;
let HUDNEW = opt.hudnew === '1' || SCEN === 'edge';     // also turned on below when out/hud.json already lists every addition
const FEATURES = !BAL && !SCEN && N >= 16;
let seed = +(opt.seed || 7); Math.random = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
const L = JSON.parse(fs.readFileSync(path.join(root, 'out/layout.json'), 'utf8'));
const PARK_Z = L.map.park_z, LOBBY_Z = L.map.lobby_z;
const fails = [];
const fail = (m) => { if (fails.length < 40 && !fails.includes(m)) fails.push(m); };
let time = 0;
const stats = { hud: 0, vars: 0, fires: {}, dmg: 0, kills: 0, teleports: 0, moves: 0, cam: 0, traces: 0, blocked: 0, msgs: [], cmds: {}, rounds: 0, terminate: 0, ropes: 0,
                fallBlocked: 0, yields: 0, leashOk: 0, kit: 0, gunfire: 0, panelIds: new Set(), falls: 0, churn: {}, softRestarts: 0, inputs: 0 };
const cov = {};                                   // feature -> times exercised (set pieces add to it; the rest is read from the script's stats)
const hit = (k, n) => { cov[k] = (cov[k] || 0) + (n === undefined ? 1 : n); };

// ------------------------------------------------------------------ HUD contract (docs/SCRIPT.md): the table, and the pass 1 additions
const contract = new Map();
{
  const md = fs.readFileSync(path.join(root, 'docs/SCRIPT.md'), 'utf8');
  const read = (re, added) => {
    const m = re.exec(md); if (!m) return false;
    for (const line of m[1].split('\n')) {
      const c = line.split('|').map((s) => s.trim());
      if (c.length < 5 || !c[1].startsWith('mv_')) continue;
      const e = contract.get(c[1]) || { text: false, classes: new Set(), used: new Set(), textUsed: false, added };
      if (c[2] === 'text') e.text = true;
      else for (const part of c[3].split(',').map((s) => s.trim()).filter(Boolean)) {
        const r = /^([a-z_]+?)(\d+)\.\.\1(\d+)$/.exec(part);
        if (r) for (let i = +r[2]; i <= +r[3]; i++) e.classes.add(r[1] + i); else e.classes.add(part);
      }
      contract.set(c[1], e);
    }
    return true;
  };
  if (!read(/HUD-CONTRACT-BEGIN[^\n]*\n([\s\S]*?)<!-- HUD-CONTRACT-END/, false)) throw new Error('docs/SCRIPT.md: HUD contract table not found');
  read(/HUD-ADDITIONS-BEGIN[^\n]*\n([\s\S]*?)<!-- HUD-ADDITIONS-END/, true);
}
const ADDED_IDS = [...contract].filter(([, c]) => c.added).map(([id]) => id);
try {                                            // the generated HUD already carries the additions: the script uses them, so the mock must accept them
  const hj = JSON.parse(fs.readFileSync(new URL('../out/hud.json', import.meta.url), 'utf8'));
  if (ADDED_IDS.length && Array.isArray(hj.ids) && ADDED_IDS.every((id) => hj.ids.includes(id))) HUDNEW = true;
} catch (e) { /* no out/hud.json yet */ }
const xmlPath = path.join(root, 'out/addon/panorama/layout/custom_game/mg_monsoon.xml'), cssPath = path.join(root, 'out/addon/panorama/styles/custom_game/mg_monsoon.css');
const xmlIds = fs.existsSync(xmlPath) ? new Set([...fs.readFileSync(xmlPath, 'utf8').matchAll(/id="([^"]+)"/g)].map((m) => m[1])) : null;
const css = fs.existsSync(cssPath) ? fs.readFileSync(cssPath, 'utf8') : null;

// ------------------------------------------------------------------ the world: a height field from the layout
const RIVER = (opt.river === '1' || SCEN === 'review2') && Array.isArray(L.river) && L.river.length > 1 ? L.river : null;
function riverY(x) {
  const R = RIVER; if (!R) return NaN;
  if (x <= R[0][0]) return R[0][1];
  for (let i = 1; i < R.length; i++) if (x <= R[i][0]) { const a = R[i - 1], b = R[i], t = (x - a[0]) / Math.max(1e-6, b[0] - a[0]); return a[1] + (b[1] - a[1]) * t; }
  return R[R.length - 1][1];
}
const inRiver = (x, y) => !!RIVER && Math.abs(y - riverY(x)) < 180 && Math.abs(x) > 700;      // the bridge (flag B) stays dry
function ground(x, y) {
  if (inRiver(x, y)) return L.map.water_z - 120;
  let z = 40;
  for (const tg of ['t', 'ct']) { const b = L[tg], d = Math.hypot(x - b.centre[0], y - b.centre[1]); if (d < 800) z = Math.max(z, b.z); else if (d < 1400) z = Math.max(z, b.z * (1400 - d) / 600); }
  for (const k of L.karst) if (Math.hypot(x - k.x, y - k.y) < k.r) z = Math.max(z, k.top);
  return z;
}
const fin = (v) => v && Number.isFinite(v.x) && Number.isFinite(v.y) && Number.isFinite(v.z);
function checkPos(v, what) {
  if (!fin(v)) throw new Error('non-finite position for ' + what + ': ' + JSON.stringify(v));
  if (Math.abs(v.x) > L.map.air[0] + 1400 || Math.abs(v.y) > L.map.air[1] + 1400 || v.z < PARK_Z - 60 || v.z > L.map.air[2] + 1500) throw new Error('position outside the world for ' + what + ': ' + JSON.stringify(v));
}
function checkAng(a, what) { if (!a || ![a.pitch, a.yaw, a.roll].every(Number.isFinite)) throw new Error('bad angles for ' + what + ': ' + JSON.stringify(a)); }
const INPUTS = {
  info_particle_system: ['Start', 'Stop'], point_soundevent: ['StartSound', 'StopSound', 'SetSourceEntity'], env_shake: ['StartShake'],
  prop_dynamic: ['Skin', 'SetAnimation'], info_map_parameters: ['FireWinCondition'],
};
const world = new Map();
class Ent {
  constructor(name, cls, pos, ang) { this.name = name; this.cls = cls; this.pos = { ...pos }; this.ang = ang ? { ...ang } : { pitch: 0, yaw: 0, roll: 0 }; this.vel = { x: 0, y: 0, z: 0 }; this.valid = true; this.model = ''; this.inputs = {}; }
  IsValid() { return this.valid; } GetAbsOrigin() { this.use(); return { ...this.pos }; } GetAbsAngles() { this.use(); return { ...this.ang }; } GetAbsVelocity() { return { ...this.vel }; }
  GetClassName() { return this.cls; } GetEntityName() { return this.name; }
  use() { if (!this.valid) throw new Error('method on an invalid entity ' + (this.name || this.cls)); }
  SetModelScale(v) { this.use(); if (!Number.isFinite(v) || v <= 0) throw new Error('bad scale ' + v); this.scale = v; } GetModelName() { return this.model; }
  Teleport(o) { this.use(); if (o.position) { checkPos(o.position, 'Teleport ' + (this.name || this.cls)); this.pos = { ...o.position }; } if (o.angles) { checkAng(o.angles, this.name); this.ang = { ...o.angles }; } if (o.velocity) { if (!fin(o.velocity)) throw new Error('bad velocity'); this.vel = { ...o.velocity }; } stats.teleports++; }
  Move(o) { this.use(); if (o.position) { checkPos(o.position, 'Move ' + (this.name || this.cls)); this.pos = { ...o.position }; } if (o.angles) { checkAng(o.angles, this.name); this.ang = { ...o.angles }; } if (o.velocity) { if (!fin(o.velocity)) throw new Error('bad velocity'); this.vel = { ...o.velocity }; } stats.moves++; }
  SetParent(p) { this.parent = p; } GetParent() { return this.parent; }
  GetTeamNumber() { return 0; }
  FireInput(o) {
    this.use();
    const ok = INPUTS[this.cls] || [];
    if (!ok.includes(o.input)) throw new Error('input ' + o.input + ' fired at ' + this.name + ' (' + this.cls + ')');
    if (o.input === 'SetSourceEntity' && !world.has(String(o.value))) throw new Error('SetSourceEntity to a missing entity ' + o.value);
    if (o.input === 'Skin' && ![0, 1, 2].includes(o.value)) throw new Error('bad skin ' + o.value);
    if (o.input === 'SetAnimation' && !['idle', 'spin_slow', 'spin'].includes(o.value)) throw new Error('bad animation ' + o.value);
    stats.fires[o.input] = (stats.fires[o.input] || 0) + 1; this.inputs[o.input] = (this.inputs[o.input] || 0) + 1; this.last = o.input + ':' + o.value;
  }
}
const hudState = new Map();                       // slot -> Map(panel#class -> bool, panel$ -> text): what each human's screen shows
const loading = new Set();                        // slots whose client has not finished loading (their HUD calls are lost)
class Hud extends Ent {
  chk(slot, panel, cls) {
    stats.panelIds.add(panel);
    if (ctls[slot] && ctls[slot].bot) throw new Error('HUD call for a bot (slot ' + slot + ', ' + panel + ')');
    const c = contract.get(panel); if (!c) throw new Error('HUD panel not in the contract: ' + panel);
    if (c.added && !HUDNEW) throw new Error('HUD addition ' + panel + ' used although out/hud.json does not list it');
    if (xmlIds && !c.added && !xmlIds.has(panel)) throw new Error('HUD xml lacks panel ' + panel);
    if (cls === undefined) { if (!c.text) throw new Error('HUD panel ' + panel + ' is not a text panel in the contract'); c.textUsed = true; return; }
    if (!c.classes.has(cls)) throw new Error('HUD class not in the contract: ' + panel + ' .' + cls);
    if (css && !c.added && !css.includes('.' + cls)) throw new Error('HUD css lacks class ' + cls);
    c.used.add(cls);
  }
  st(slot) { let m = hudState.get(slot); if (!m) hudState.set(slot, m = new Map()); return m; }
  // a client still loading (cs2-gotchas: HUD changes sent before a joining client is ready are lost): the call is made and lost
  SetHasClassForPlayer(slot, panel, cls, on) { stats.hud++; if (typeof on !== 'boolean') throw new Error('class flag not boolean'); this.chk(slot, panel, cls); if (loading.has(slot)) return; this.st(slot).set(panel + '#' + cls, on); }
  SetDialogVariableStringForPlayer(slot, panel, n, v) {
    stats.vars++; if (n !== 'v' || typeof v !== 'string') throw new Error('bad dialog variable'); if (/undefined|NaN|\[object|null/.test(v)) throw new Error('bad HUD text for ' + panel + ': ' + v);
    if (v.length > 96) throw new Error('HUD text too long for ' + panel + ' (' + v.length + '): ' + v);
    this.chk(slot, panel); if (loading.has(slot)) return; this.st(slot).set(panel + '$', v);
  }
  ResetForPlayer(slot) { hudState.delete(slot); stats.hudResets = (stats.hudResets || 0) + 1; }
}
const shows = (slot, panel, cls) => !!(hudState.get(slot) && hudState.get(slot).get(panel + '#' + (cls || 'show')));
function synthesise() {
  const out = [];
  const add = (name, cls, x, y, z, yaw) => out.push({ name, cls, origin: [x, y, z], angles: [0, yaw || 0, 0] });
  add('mv_script', 'point_script', 0, 0, LOBBY_Z); add('mv_hud', 'custom_hud_layout', 0, 0, LOBBY_Z); add('mv_params', 'info_map_parameters', 0, 0, LOBBY_Z);
  add('mv_ambience', 'point_soundevent', 0, 0, 500);
  for (let i = 0; i < 32; i++) { add('', 'info_player_terrorist', -800 + (i % 8) * 60, 300 + Math.floor(i / 8) * 60, LOBBY_Z + 8); add('', 'info_player_counterterrorist', 800 - (i % 8) * 60, -300 - Math.floor(i / 8) * 60, LOBBY_Z + 8); }
  let mount = 0;
  const addMount = (x, y, yaw) => { mount++; const z = ground(x, y); add('mv_mount_' + mount, 'prop_dynamic', x, y, z + 44, yaw); const r = yaw * Math.PI / 180;
    add('mv_mountseat_' + mount, 'info_teleport_destination', x - Math.cos(r) * 48, y - Math.sin(r) * 48, z, yaw); add('mv_mount_snd_' + mount, 'point_soundevent', x, y, z + 44); add('mv_mountinfo_' + mount, 'info_target', x, y, z + 80); };
  for (const tg of ['t', 'ct']) {
    const b = L[tg], cx = b.centre[0], cy = b.centre[1], toMid = Math.atan2(-cy, -cx) * 180 / Math.PI;
    for (let i = 1; i <= 16; i++) { const a = i * Math.PI / 8; add(`mv_spawn_${tg}_${i}`, 'info_teleport_destination', cx + Math.cos(a) * 330, cy + Math.sin(a) * 330, ground(cx, cy), toMid); }
    add(`mv_kit_${tg}`, 'info_target', cx + 140, cy + 60, ground(cx, cy));
    b.pads.forEach((p, i) => {
      const n = i + 1, z = ground(p[0], p[1]), yaw = b.pad_yaw, r = yaw * Math.PI / 180;
      add(`mv_pad_${tg}_${n}`, 'info_target', p[0], p[1], z, yaw);
      add(`mv_heli_${tg}_${n}`, 'prop_dynamic', p[0], p[1], z, tg === 'ct' ? yaw - 90 : yaw);
      if (tg === 't') { add(`mv_rotor_t_${n}`, 'prop_dynamic', p[0] - 30 * Math.cos(r), p[1] - 30 * Math.sin(r), z + 174, yaw); add(`mv_tail_t_${n}`, 'prop_dynamic', p[0] - 541 * Math.cos(r) - 16 * Math.sin(r), p[1] - 541 * Math.sin(r) + 16 * Math.cos(r), z + 161, yaw); }
      for (const k of ['eng', 'gun', 'gun2', 'rkt']) add(`mv_heli_${k}_${tg}_${n}`, 'point_soundevent', p[0], p[1], z + 60);
      add(`mv_heli_smoke_${tg}_${n}`, 'info_particle_system', p[0], p[1], PARK_Z); add(`mv_heli_dust_${tg}_${n}`, 'info_particle_system', p[0], p[1], PARK_Z);
      add(`mv_wreck_${tg}_${n}`, 'prop_dynamic', p[0], p[1], PARK_Z);
    });
    b.guns.forEach((g, i) => {
      const k = i + 1, z = ground(g[0], g[1]), yaw = Math.atan2(-g[1], -g[0]) * 180 / Math.PI, r = yaw * Math.PI / 180;
      add(`mv_gun_${tg}_${k}`, 'prop_dynamic', g[0], g[1], z, yaw); add(`mv_tube_${tg}_${k}`, 'prop_dynamic', g[0] + 10 * Math.cos(r), g[1] + 10 * Math.sin(r), z + 42, yaw);
      if (tg === 't') add(`mv_round_t_${k}`, 'prop_dynamic', g[0], g[1], PARK_Z);
      add(`mv_rack_${tg}_${k}`, 'info_target', g[0] - 150 * Math.cos(r) + 60, g[1] - 150 * Math.sin(r), z);
      add(`mv_boardseat_${tg}_${k}`, 'info_teleport_destination', b.fdc[0] + 60 * k - 120, b.fdc[1] - 90, ground(b.fdc[0], b.fdc[1]), 90);
      add(`mv_gun_snd_${tg}_${k}`, 'point_soundevent', g[0], g[1], z + 40); add(`mv_gun_fx_${tg}_${k}`, 'info_particle_system', g[0], g[1], z + 40);
    });
    add(`mv_board_${tg}`, 'info_target', b.fdc[0], b.fdc[1], ground(b.fdc[0], b.fdc[1]));
    addMount(cx - 500 * Math.sign(cx), cy + 420 * Math.sign(cy) * -1, toMid); addMount(cx - 420 * Math.sign(cx), cy - 520 * Math.sign(cy) * -1, toMid);
  }
  for (const f of L.flags) {
    const z = ground(f.x, f.y);
    add('mv_flag_' + f.id, 'info_target', f.x, f.y, z); add('mv_flagpole_' + f.id, 'prop_dynamic', f.x, f.y, z); add('mv_kit_' + f.id, 'info_target', f.x + 110, f.y + 40, z);
    for (let i = 1; i <= 8; i++) { const a = i * Math.PI / 4; add(`mv_flagspawn_${f.id}_${i}`, 'info_teleport_destination', f.x + Math.cos(a) * 240, f.y + Math.sin(a) * 240, z, a * 180 / Math.PI + 180); }
  }
  addMount(120, -300, 0); addMount(2500, 780, 200);
  for (let i = 1; i <= 16; i++) { add('mv_boom_fx_' + i, 'info_particle_system', 0, 0, PARK_Z); add('mv_dirt_fx_' + i, 'info_particle_system', 0, 0, PARK_Z); add('mv_boom_snd_' + i, 'point_soundevent', 0, 0, PARK_Z);
    add('mv_whistle_snd_' + i, 'point_soundevent', 0, 0, PARK_Z); add('mv_shake_' + i, 'env_shake', 0, 0, PARK_Z); add('mv_rocket_' + i, 'prop_dynamic', 0, 0, PARK_Z); }
  for (let i = 1; i <= 24; i++) add('mv_tracer_' + i, 'prop_dynamic', 0, 0, PARK_Z);
  for (let i = 1; i <= 10; i++) add('mv_marker_' + i, 'prop_dynamic', 0, 0, PARK_Z);
  for (let i = 1; i <= 6; i++) add('mv_smoke_fx_' + i, 'info_particle_system', 0, 0, PARK_Z);
  for (let i = 1; i <= 12; i++) add('mv_shell_' + i, 'prop_dynamic', 0, 0, PARK_Z);
  for (let i = 1; i <= 3; i++) add('mv_tunnel_' + i, 'info_teleport_destination', -3000 + i * 700, 2000 - i * 500, ground(-3000 + i * 700, 2000 - i * 500));
  const U = ['models/player/gmod/nva_soldier/nva_soldier.vmdl', 'models/player/gmod/soldier2_woodland/soldier2_woodland.vmdl'];
  U.forEach((m, i) => out.push({ name: 'mv_cache_' + (i + 1), cls: 'prop_dynamic', origin: [0, 64 * i, PARK_Z], angles: [0, 0, 0], model: m }));
  return out;
}
const entsPath = path.join(root, 'out/entities.json');
const SYNTH = !fs.existsSync(entsPath);
const entDefs = SYNTH ? synthesise() : JSON.parse(fs.readFileSync(entsPath, 'utf8'));
// what-if for the layout: move.<flag>=dx,dy shifts a flag with its pole, crate and deploy points (balance experiments only)
for (const k of Object.keys(opt)) if (k.startsWith('move.')) { const id = k.slice(5), [dx, dy] = opt[k].split(',').map(Number); for (const e of entDefs) if (new RegExp('^mv_(flag|flagpole|kit|flag_snd)_' + id + '$|^mv_flagspawn_' + id + '_').test(e.name || '')) { e.origin[0] += dx; e.origin[1] += dy; } }
// what-if: spawnflip.<flag>=1 mirrors that flag's deploy points through the flag (the other bank / side)
for (const k of Object.keys(opt)) if (k.startsWith('spawnflip.')) { const id = k.slice(10), f = entDefs.find((e) => e.name === 'mv_flag_' + id); if (f) for (const e of entDefs) if (new RegExp('^mv_flagspawn_' + id + '_').test(e.name || '')) { e.origin[0] = 2 * f.origin[0] - e.origin[0]; e.origin[1] = 2 * f.origin[1] - e.origin[1]; } }
let lobby = [];
function makeWorld() {
  for (const e of world.values()) e.valid = false;
  world.clear();
  for (const e of entDefs) {
    if (!e.name) continue;
    const o = { x: e.origin[0], y: e.origin[1], z: e.origin[2] }, a = { pitch: e.angles[0], yaw: e.angles[1], roll: e.angles[2] };
    const ent = e.cls === 'custom_hud_layout' ? new Hud(e.name, e.cls, o, a) : new Ent(e.name, e.cls, o, a);
    ent.model = e.model || ''; world.set(e.name, ent);
  }
  lobby = entDefs.filter((e) => e.cls.startsWith('info_player'));
  hudState.clear();
}
makeWorld();

// ------------------------------------------------------------------ players
const IN = { NONE: 0, FORWARD: 1, BACK: 2, LEFT: 4, RIGHT: 8, WALK: 16, DUCK: 32, JUMP: 64, USE: 128, ATTACK: 256, ATTACK2: 512, RELOAD: 1024, SHOW_SCORES: 2048, LOOK_AT_WEAPON: 4096 };
const DT = { GENERIC: 0, CRUSH: 1, BULLET: 2, SLASH: 4, BURN: 8, VEHICLE: 16, FALL: 32, BLAST: 64, CLUB: 128, SHOCK: 256 };
const DF = { NONE: 0, SUPPRESS_HEALTH_CHANGES: 1, SUPPRESS_PHYSICS_FORCE: 2, SUPPRESS_EFFECTS: 4, PREVENT_DEATH: 8, FORCE_DEATH: 16, SUPPRESS_DAMAGE_MODIFICATION: 32, IGNORE_ARMOR: 64 };
const hooks = {};
const WEAPONS = new Set(['weapon_knife', 'weapon_glock', 'weapon_hkp2000', 'weapon_ak47', 'weapon_m4a1', 'weapon_negev', 'weapon_m249', 'weapon_taser', 'weapon_scar20', 'weapon_g3sg1', 'weapon_p250']);
class Weapon { constructor(n, owner) { this.n = n; this.owner = owner; } GetClassName() { return this.n; } GetOwner() { return this.owner; } GetData() { return { GetDamage: () => 30 }; } IsValid() { return true; } }
class Cam extends Ent {
  constructor(p) { super('', 'camera', { x: 0, y: 0, z: 0 }); this.p = p; this.mode = 0; this.parent = p; }
  SetMode(m) { if (![0, 1, 2, 3].includes(m)) throw new Error('bad camera mode'); this.mode = m; stats.cam++; } GetMode() { return this.mode; }
  SetFollowConfig(c) { if (!c.followEntity || !c.followEntity.IsValid()) throw new Error('follow without a valid entity'); for (const k of ['followOffset', 'cameraOffset']) if (c[k] && !fin(c[k])) throw new Error('bad ' + k); stats.cam++; }
}
class Pawn extends Ent {
  constructor(ctl) { super('', 'player', { x: 0, y: 0, z: 0 }); this.ctl = ctl; this.hp = 100; this.armor = 0; this.helmet = false; this.weapons = []; this.keys = 0; this.mt = 2; this.eye = { pitch: 0, yaw: 0, roll: 0 }; this.active = null; this.model = 'agents/models/stock.vmdl'; }
  GetPlayerController() { return this.ctl; } GetTeamNumber() { return this.ctl.team; } IsAlive() { return this.hp > 0; }
  GetHealth() { return this.hp; } SetHealth(v) { if (!Number.isInteger(v)) throw new Error('SetHealth non-integer ' + v); this.hp = v; }
  GetArmor() { return this.armor; } SetArmor(v) { if (!Number.isInteger(v)) throw new Error('SetArmor non-integer ' + v); this.armor = v; } HasHelmet() { return this.helmet; } SetHasHelmet(v) { this.helmet = !!v; }
  IsInputPressed(b) { stats.inputs++; if (b & (b - 1)) throw new Error('masked IsInputPressed'); return (this.keys & b) !== 0; }
  SetEyeAngles(a) { checkAng(a, 'eye'); this.eye = { ...a }; } GetEyeAngles() { return { ...this.eye }; } GetEyePosition() { return { x: this.pos.x, y: this.pos.y, z: this.pos.z + 64 }; }
  SetMoveType(m) { this.use(); if (![0, 2].includes(m)) throw new Error('bad move type ' + m); this.mt = m; } GetMoveType() { return this.mt; }
  GetGroundEntity() { return this.pos.z <= ground(this.pos.x, this.pos.y) + 2 || this.pos.z < LOBBY_Z + 100 ? worldEnt : undefined; }
  SetModel(m) { if (![...world.values()].some((e) => e.model === m) && !m.startsWith('agents/')) throw new Error('SetModel to a model no cache prop holds: ' + m); this.model = m; stats.setmodel = (stats.setmodel || 0) + 1; }
  GetCustomCamera() { return this.cam || (this.cam = new Cam(this)); }
  DestroyWeapons() { this.weapons = []; this.active = null; } DestroyWeapon(w) { this.weapons = this.weapons.filter((x) => x !== w); if (this.active === w) this.active = this.weapons[0] || null; }
  GiveNamedItem(n, dep) { if (!WEAPONS.has(n)) throw new Error('unknown weapon ' + n); if (this.weapons.find((w) => w.n === n)) throw new Error('duplicate weapon ' + n); const w = new Weapon(n, this); this.weapons.push(w); if (dep || !this.active) this.active = w; }
  FindWeapon(n) { return this.weapons.find((w) => w.n === n); } GetActiveWeapon() { return this.active || undefined; }
  Reset() { spawn(this.ctl, true); }
  // weapon: this stand-in's own extension (CS2 names the weapon of a bullet kill itself)
  TakeDamage(d) {
    if (!(d.damage > 0) || !Number.isFinite(d.damage)) throw new Error('bad damage ' + d.damage);
    if (this.hp <= 0) return 0;
    if (d.attacker !== undefined && !(d.attacker instanceof Ent)) throw new Error('bad attacker');
    if (this.ctl.god && !((d.damageFlags || 0) & DF.FORCE_DEATH)) return 0;
    let dmg = d.damage;
    if (hooks.mod) { const r = hooks.mod({ player: this, damage: dmg, damageTypes: d.damageTypes || 0, damageFlags: d.damageFlags || 0, hitGroup: 0, attacker: d.attacker, inflictor: d.inflictor });
      if (r && r.abort) { stats.blocked++; if ((d.damageTypes || 0) & DT.FALL) stats.fallBlocked++; return 0; } if (r && r.damage !== undefined) dmg = r.damage; }
    stats.dmg++;
    hooks.damage && hooks.damage({ player: this, damage: dmg, damageTypes: d.damageTypes || 0, damageFlags: d.damageFlags || 0, hitGroup: 0, attacker: d.attacker, inflictor: d.inflictor });
    this.hp -= Math.round(dmg); if ((d.damageFlags || 0) & DF.FORCE_DEATH) this.hp = 0;
    if (this.hp <= 0) { this.hp = 0; die(this, d.attacker, d.weapon); }
    return dmg;
  }
}
class Ctl extends Ent {
  constructor(slot, team, bot) { super('', 'cs_player_controller', { x: 0, y: 0, z: 0 }); this.slot = slot; this.team = team; this.bot = bot; this.pawn = new Pawn(this); this.drv = {}; this.q = []; this.hold = 0; this.stunt = ''; this.god = false; this.spec = false; this.gone = false; this.name = ''; }
  GetPlayerSlot() { return this.slot; } GetPlayerPawn() { return this.spec || this.gone ? undefined : this.pawn; } IsBot() { return this.bot; } GetPlayerName() { return this.name || (this.bot ? 'bot' : 'p') + this.slot; } GetTeamNumber() { return this.team; }
  IsConnected() { return !this.gone; }
}
const worldEnt = new Ent('world', 'worldent', { x: 0, y: 0, z: 0 });
const ctls = [];                                  // by slot; a slot can be empty (undefined) for a while in the churn scenario
// a departed player's controller CS2 leaves in the slot (gone: IsConnected false, no pawn) is nobody: the drivers skip it
const everyone = () => ctls.filter((c) => c && !c.gone);
// a player leaves and CS2 keeps the controller in the slot, with no disconnect event (a bot kicked by bot_quota fill); the slot is
// emptied after `linger` seconds
function depart(c, linger) { c.gone = true; c.pawn.valid = false; const slot = c.slot; at(linger, () => { if (ctls[slot] === c) ctls[slot] = undefined; }); }
function spawn(c, samePawn) {
  if (c.spec || ctls[c.slot] !== c) return;
  const sp = lobby.filter((e) => (e.cls.endsWith('terrorist') && !e.cls.includes('counter')) === (c.team === 2));
  const e = sp[c.slot % sp.length];
  if (!samePawn) { c.pawn.valid = false; c.pawn = new Pawn(c); } else { c.pawn.hp = 100; c.pawn.mt = 2; }
  c.pawn.pos = { x: e.origin[0], y: e.origin[1], z: e.origin[2] }; c.pawn.vel = { x: 0, y: 0, z: 0 };
  c.drv = { born: time };
  hooks.reset && hooks.reset({ player: c.pawn });
}
const later = [];
function at(dt, fn) { later.push({ at: time + dt, fn }); }
function die(pawn, attacker, weapon) { stats.kills++; hooks.kill && hooks.kill({ player: pawn, attacker, weapon }); const c = pawn.ctl; at(2, () => { if (ctls[c.slot] === c && c.pawn === pawn) spawn(c); }); }
// load = seconds the client is still loading after its first spawn (HUD calls lost); OnPlayerActivate fires when it is done
function addPlayer(bot, slot, load) {
  const s = slot === undefined ? ctls.length : slot; const c = new Ctl(s, s % 2 ? 3 : 2, bot); ctls[s] = c;
  if (load > 0) { loading.add(s); at(load, () => { loading.delete(s); if (ctls[s] === c) hooks.pactivate && hooks.pactivate({ player: c }); }); }
  else hooks.pactivate && hooks.pactivate({ player: c });
  spawn(c); return c;
}

// ------------------------------------------------------------------ engine API (current names only)
function traceLine(o) {
  stats.traces++;
  for (const v of [o.start, o.end]) if (!fin(v)) throw new Error('bad trace ' + JSON.stringify(o));
  if (o.ignoreEntity !== undefined && !Array.isArray(o.ignoreEntity) && !(o.ignoreEntity instanceof Ent)) throw new Error('bad ignoreEntity');
  const d = { x: o.end.x - o.start.x, y: o.end.y - o.start.y, z: o.end.z - o.start.z }, len = Math.hypot(d.x, d.y, d.z);
  const res = (f, normal, ent, solid) => ({ didHit: f < 1, fraction: f, end: { x: o.start.x + d.x * f, y: o.start.y + d.y * f, z: o.start.z + d.z * f }, normal, hitEntity: ent, startedInSolid: !!solid });
  let f = 1, normal = { x: 0, y: 0, z: 1 };
  if (o.start.z < ground(o.start.x, o.start.y) - 1) return res(0, normal, worldEnt, true);
  if (Math.abs(d.x) < 1e-6 && Math.abs(d.y) < 1e-6) { const g = ground(o.start.x, o.start.y); if (o.end.z < g) f = (o.start.z - g) / Math.max(1e-6, o.start.z - o.end.z); }
  else {
    const steps = Math.max(2, Math.min(40, Math.ceil(len / 90)));
    let pf = 0;
    for (let i = 1; i <= steps; i++) {
      const cf = i / steps, x = o.start.x + d.x * cf, y = o.start.y + d.y * cf, z = o.start.z + d.z * cf;
      if (z < ground(x, y)) {
        let lo = pf, hi = cf;
        for (let k = 0; k < 7; k++) { const m = (lo + hi) / 2; if (o.start.z + d.z * m < ground(o.start.x + d.x * m, o.start.y + d.y * m)) hi = m; else lo = m; }
        f = lo;
        const gl = ground(o.start.x + d.x * lo, o.start.y + d.y * lo), gh = ground(o.start.x + d.x * hi, o.start.y + d.y * hi);
        if (gh - gl > 40) { const h = Math.hypot(d.x, d.y) || 1; normal = { x: -d.x / h, y: -d.y / h, z: 0 }; }   // a wall (karst side, plateau edge)
        break;
      }
      pf = cf;
    }
  }
  let hitEnt = f < 1 ? worldEnt : undefined;
  if (!o.ignorePlayers && len > 1) {
    const ign = Array.isArray(o.ignoreEntity) ? o.ignoreEntity : o.ignoreEntity ? [o.ignoreEntity] : [];
    for (const c of everyone()) {
      const p = c.pawn; if (c.spec || p.hp <= 0 || p.pos.z < -1000 || ign.includes(p) || (p.scale || 1) < 0.5) continue;
      const w = { x: p.pos.x - o.start.x, y: p.pos.y - o.start.y, z: p.pos.z + 40 - o.start.z }, t = (w.x * d.x + w.y * d.y + w.z * d.z) / len;
      if (t <= 0 || t >= f * len) continue;
      if (Math.hypot(w.x - d.x * t / len, w.y - d.y * t / len, w.z - d.z * t / len) < 26) { f = t / len; hitEnt = p; normal = { x: 0, y: 0, z: 1 }; }
    }
  }
  const r = res(f, normal, hitEnt, false);
  if (f >= 1) { r.didHit = false; r.hitEntity = undefined; }
  return r;
}
const strict = (name, obj) => new Proxy(obj, { get(t, k) { if (k in t || typeof k === 'symbol') return t[k]; throw new Error(name + '.' + String(k) + ' is not in the current API (deprecated or misspelt)'); } });
const lookedUpMissing = new Set();
const OPTIONAL = [/^mv_flag_snd_/, /^mv_cache_\d+$/, /^mv_mount_\d+$/, /^mv_tunnel_\d+$/];
const Instance = strict('Instance', {
  _think: null, _next: undefined,
  GetGameTime: () => time, SetThink: (f) => { Instance._think = f; }, SetNextThink: (t) => { if (!Number.isFinite(t)) throw new Error('bad think time'); Instance._next = t; },
  OnActivate: (f) => { hooks.activate = f; }, OnRoundStart: (f) => { hooks.round = f; }, OnPlayerReset: (f) => { hooks.reset = f; }, OnPlayerDisconnect: (f) => { hooks.disc = f; },
  OnPlayerKill: (f) => { hooks.kill = f; }, OnPlayerChat: (f) => { hooks.chat = f; }, OnBulletImpact: (f) => { hooks.bullet = f; }, OnModifyPlayerDamage: (f) => { hooks.mod = f; },
  OnPlayerDamage: (f) => { hooks.damage = f; }, OnGunFire: (f) => { hooks.gunfire = f; }, OnScriptReload: (c) => { hooks.reloadCfg = c; },
  OnPlayerActivate: (f) => { hooks.pactivate = f; },
  GetPlayerController: (s) => ctls[s], TraceLine: traceLine,
});
const Entities = strict('Entities', {
  FindByName: (n) => { const e = world.get(n); if (!e) { lookedUpMissing.add(n); return []; } return [e]; },
  FindByClass: (c) => [...world.values()].filter((e) => e.cls === c),
  FireInput: (o) => { const e = world.get(o.name); if (!e) throw new Error('Entities.FireInput at a missing entity ' + o.name); e.FireInput(o); },
});
let quota = 0, quotaMode = 'normal';
const Console = strict('Console', {
  Log: (m) => { stats.msgs.push(String(m)); if (process.env.MOCK_LOG) console.log(time.toFixed(2), String(m)); },
  ServerCommand: (c) => {
    const w = String(c).split(' ')[0]; stats.cmds[w] = (stats.cmds[w] || 0) + 1;
    if (!/^(mp_|bot_|say$)/.test(w)) throw new Error('server command outside the allowed set: ' + c);
    if (/[;"\x00-\x1f\x7f]/.test(c)) throw new Error('unsafe characters in a server command: ' + JSON.stringify(c));
    if (w === 'bot_quota') quota = +String(c).split(' ')[1]; if (w === 'bot_quota_mode') quotaMode = String(c).split(' ')[1];
  },
});
let restartAt = -1;
const NORESTART = () => !!process.env.MOCK_NORESTART || (SCEN === 'restart' && stats.terminate % 2 === 0);
const GameRules = strict('GameRules', {
  TerminateRound: (reason, delay) => { if (![2, 8, 9].includes(reason)) throw new Error('bad round end reason ' + reason); stats.terminate++; if (!NORESTART()) restartAt = time + (delay || 0) + 4; },
  AddTeamScore: (team, n) => { if (![2, 3].includes(team) || n !== 1) throw new Error('bad AddTeamScore'); stats.score = (stats.score || 0) + 1; },
  SetRoundRemainingTime: (t) => { if (!Number.isFinite(t)) throw new Error('bad round time'); }, GetRoundRemainingTime: () => 600, IsWarmupPeriod: () => false,
});
const dest = path.join(root, 'test/_run' + (opt.tag || (BAL ? '_' + process.pid : '')) + '.mjs');
const built = opt.script ? (() => { const t = fs.readFileSync(path.resolve(root, opt.script), 'utf8'); fs.writeFileSync(dest, t); return { dest, lines: t.split('\n').length }; })() : build(dest);
{
  let src = fs.readFileSync(dest, 'utf8').replace(/import \{([^}]*)\} from "cs_script\/point_script";/, 'const {$1} = globalThis.__cs;');
  if (HUDNEW) src = src.replace(/^const HUDDATA = (.*);$/m, (m, j) => { const h = JSON.parse(j); h.ids = [...new Set([...(h.ids || [...contract.keys()]), ...ADDED_IDS])]; return 'const HUDDATA = ' + JSON.stringify(h) + ';'; });
  fs.writeFileSync(dest, src);
}
globalThis.__cs = { Instance, Entities, Console, GameRules, CSInputs: IN, CSMoveType: { NONE: 0, WALK: 2 }, CSDamageTypes: DT, CSDamageFlags: DF,
                    CSRoundEndReason: { DRAW: 2, CTS_WIN: 8, TERRORISTS_WIN: 9 }, CustomCameraMode: { DISABLED: 0, CONTROLLED: 1, CONTROLLED_POSITION: 2, FOLLOW_POSITION: 3 } };
let D, CONFIG, loads = 0;
async function loadScript() {
  await import(pathToFileURL(dest).href + '?v=' + (loads++));
  D = globalThis.__mvDebug; CONFIG = D.CONFIG;
  for (const k of Object.keys(opt)) if (k.startsWith('cfg.')) {      // cfg.HELI.ACCEL=0.45 style overrides (test/sim_balance.mjs)
    const pth = k.slice(4).split('.'); let o = CONFIG; for (let i = 0; i < pth.length - 1; i++) o = o[pth[i]];
    o[pth[pth.length - 1]] = JSON.parse(opt[k]);
  }
  if (BAL) return;
  CONFIG.CONQUEST.TICKETS = +(process.env.MOCK_TICKETS || (SCEN === 'restart' ? 5 : 40));        // rounds must end inside the run
  CONFIG.CONQUEST.CAPTURE_SECONDS = 8;
  CONFIG.AFK.TIME = 40;
  if (process.env.MOCK_ROUND) CONFIG.CONQUEST.ROUND_SECONDS = +process.env.MOCK_ROUND;
}
await loadScript();
if (BAL && opt.round) CONFIG.CONQUEST.ROUND_SECONDS = +opt.round;

const HUMANS = opt.humans !== undefined ? +opt.humans : -1;
for (let s = 0; s < N; s++) addPlayer(HUMANS >= 0 ? s >= HUMANS : LOWPOP ? false : s % 3 === 2);
hooks.activate();
hooks.round && hooks.round();
function fillBots() { if (quotaMode !== 'fill' || BAL || HUMANS >= 0) return; while (ctls.length < Math.min(quota, 40)) addPlayer(true); }
fillBots();

// ------------------------------------------------------------------ drivers: press keys like players would
const P = (c) => (c ? D.players.get(c.slot) : undefined);
const humans = (team) => everyone().filter((c) => !c.bot && c.team === team);
const jobCache = new Map();
const jobOf = (c) => { const i = humans(c.team).indexOf(c); return LOWPOP ? ['pilot', 'observer'][i] || 'walker' : ['pilot', 'crew', 'crew', 'rider', 'mount', 'observer', 'pilot'][i] || 'walker'; };
const yawTo = (a, b) => Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI;
const d2 = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const wrap = (x) => ((x + 180) % 360 + 360) % 360 - 180;
const say = (c, text) => hooks.chat({ player: c, text, team: c.team });
function tap(c, key) { c.pawn.keys |= key; }
function press(c, key, ticks) { c.q.push({ k: 0, n: 1 }, { k: key, n: ticks || 2 }, { k: 0, n: 1 }); }      // a clean key edge, whatever the driver does
function putAt(c, pos, dz) { c.pawn.pos = { x: pos.x, y: pos.y, z: (pos.z !== undefined ? pos.z : ground(pos.x, pos.y)) + (dz || 0) }; c.pawn.vel = { x: 0, y: 0, z: 0 }; }
function lookAt(c, pt) { const p = c.pawn, d = Math.max(1, d2(p.pos, pt)); p.eye = { pitch: Math.atan2(p.pos.z + 64 - pt.z, d) * 180 / Math.PI, yaw: yawTo(p.pos, pt), roll: 0 }; }
function drivePilot(c, pr, step) {
  const p = c.pawn, dv = c.drv, h = pr.heli;
  if (!h) {      // walk to the own helicopter and climb in
    const own = D.helis[c.team].find((x) => x.owner === c.slot);
    if (own && own.state === 'parked' && own.seats[0].slot < 0 && step % 64 === 0) { putAt(c, { x: own.pos.x + 150, y: own.pos.y + 40, z: own.pos.z }); tap(c, IN.USE); }
    return;
  }
  if (pr.seat !== 0) return;
  stats.flyTicks = (stats.flyTicks || 0) + 1;
  if (h.landed) {
    if (dv.landedAt === undefined) { dv.landedAt = time; dv.sortie = (dv.sortie || 0) + 1; }
    if (time - dv.landedAt > (d2(h.pos, h.pad.pos) < 200 ? 14 : 6)) { p.keys |= IN.JUMP; dv.tookOff = time; }
    p.eye = { pitch: 0, yaw: h.yaw, roll: 0 };
    if (dv.sortie % 4 === 3 && time - dv.landedAt > 3 && time - dv.landedAt < 3.05) tap(c, IN.USE);      // gets out for a moment, climbs back in
    return;
  }
  dv.landedAt = undefined;
  const flight = time - (dv.tookOff || time), enemyFlag = D.flags[(c.slot + (dv.sortie || 0)) % D.flags.length];
  const drop = dv.sortie % 3 === 2;      // every third sortie puts down at a flag instead of the pad
  const home = flight > 28 ? (drop && flight < 60 ? { x: enemyFlag.pos.x + 300, y: enemyFlag.pos.y - 300, z: enemyFlag.pos.z } : h.pad.pos) : null;
  const goal = home || enemyFlag.pos, d = d2(h.pos, goal), agl = h.pos.z - ground(h.pos.x, h.pos.y);
  const wantYaw = d > 200 ? yawTo(h.pos, goal) : h.yaw;
  p.eye = { pitch: home ? 0 : 14, yaw: wantYaw, roll: 0 };
  const cy = Math.cos(h.yaw * Math.PI / 180), sy = Math.sin(h.yaw * Math.PI / 180);
  const vf = h.vel.x * cy + h.vel.y * sy, vr = h.vel.x * sy - h.vel.y * cy;
  const dxl = (goal.x - h.pos.x) * cy + (goal.y - h.pos.y) * sy, dyl = (goal.x - h.pos.x) * sy - (goal.y - h.pos.y) * cy;
  const wf = Math.max(-300, Math.min(700, dxl * 0.5)), wr = Math.max(-300, Math.min(300, dyl * 0.5));
  if (wf > vf + 30) p.keys |= IN.FORWARD; else if (wf < vf - 30) p.keys |= IN.BACK;
  if (wr > vr + 30) p.keys |= IN.RIGHT; else if (wr < vr - 30) p.keys |= IN.LEFT;
  if (home && d < 120 && Math.hypot(vf, vr) < 110) p.keys |= IN.DUCK;
  else { const want = home && d < 600 ? 220 : 520; if (agl < want - 40) p.keys |= IN.JUMP; else if (agl > want + 120) p.keys |= IN.DUCK; }
  if (!home && d < 2600 && d > 500 && Math.abs(wrap(wantYaw - h.yaw)) < 6) p.keys |= IN.ATTACK;
  if (process.env.DEBUGFLY && +process.env.DEBUGFLY === c.slot && step % 64 === 0) console.log('t', time.toFixed(1), 'pos', h.pos.x.toFixed(0), h.pos.y.toFixed(0), h.pos.z.toFixed(0), 'agl', agl.toFixed(0), 'v', vf.toFixed(0), vr.toFixed(0), h.vel.z.toFixed(0), 'd', d.toFixed(0), 'hp', h.hp.toFixed(0), 'rk', h.rockets, home ? 'home' : 'out', h.warn);
}
function driveRider(c, pr, step) {
  const p = c.pawn, dv = c.drv, h = pr.heli;
  if (!h) {
    if (step % 96 !== 0 || time - (dv.leftAt || -99) < 8) return;
    const ride = D.helis[c.team].find((x) => x.state === 'parked' && x.ent && x.seats[0].slot >= 0 && x.seats.some((s, i) => i > 0 && s.slot < 0));
    if (ride) { putAt(c, { x: ride.pos.x - 60, y: ride.pos.y + 170, z: ride.pos.z }); tap(c, IN.USE); dv.boardAt = time; }
    return;
  }
  const s = h.seats[pr.seat];
  if (s.kind === 'gunner') { p.eye = { pitch: 18 + 10 * Math.sin(time), yaw: h.yaw + h.M.GUN.yaw + 40 * Math.sin(time * 0.6), roll: 0 }; p.keys |= IN.ATTACK; if (step % 1500 === 700) tap(c, IN.RELOAD); }
  else p.eye = { pitch: 5, yaw: h.yaw + 30 * Math.sin(time * 0.3), roll: 0 };      // a rider looks about (and so is not AFK)
  if (time - (dv.boardAt || time) > 22 && !h.landed && h.alt < 430 && h.speed < 280) { tap(c, IN.USE); dv.leftAt = time; dv.roped = true; }
  else if (time - (dv.boardAt || time) > 45) { tap(c, IN.USE); dv.leftAt = time; }
  if (step % 640 === 320) say(c, '!swap');
}
function driveMount(c, pr, step) {
  const p = c.pawn, dv = c.drv;
  if (pr.mount < 0) {
    if (step % 128 !== 0 || time - (dv.leftAt || -99) < 6) return;
    const list = D.mounts.filter((m) => (m.team === c.team || m.team === 0) && (m.user < 0 || (ctls[m.user] && ctls[m.user].bot)));
    if (!list.length) return;
    const m = list[Math.floor(time / 30) % list.length];
    putAt(c, m.seat.pos); tap(c, IN.USE); dv.onAt = time;
    return;
  }
  const m = D.mounts[pr.mount];
  if (dv.onAt === undefined) dv.onAt = time;
  p.eye = { pitch: -8 + 14 * Math.sin(time * 0.8), yaw: m.yaw0 + 45 * Math.sin(time * 0.5), roll: 0 };
  p.keys |= IN.ATTACK;
  if (time - dv.onAt > 16) { tap(c, IN.USE); dv.leftAt = time; }
}
function driveCrew(c, pr, step) {
  const p = c.pawn, g = D.guns[c.team][pr.crew]; if (!g) return;
  const ph = Math.floor(time * 2) % 20, edge = step % 32 === 0, T = c.team === 2;
  if (time < g.disabledUntil) { putAt(c, g.pos); p.keys |= IN.USE; return; }
  if (pr.board) {
    if (ph < 9) { p.keys |= (Math.floor(time) % 2 ? IN.FORWARD : IN.LEFT) | (ph % 3 === 0 ? IN.WALK : 0); if (ph === 8 && edge) tap(c, IN.RELOAD); }
    else if (ph === 9 || ph === 10) { if (edge) tap(c, IN.ATTACK); }
    else if (ph >= 17 && ph < 19) { if (edge) tap(c, IN.JUMP); }
    else if (ph === 19 && edge && Math.floor(time / 10) % 3 === 0) tap(c, IN.USE);
    return;
  }
  const second = g.crew.indexOf(c.slot) === 1;
  if (ph === 0 || (T && ph === 4)) { if (g.rack) putAt(c, g.rack); }
  else if (ph === 1 || (T && ph === 5)) { if (edge) { if (!T && Math.floor(time / 10) % 3 === 1) tap(c, IN.ATTACK2); else tap(c, IN.USE); } }
  else if (ph === 2 || (T && ph === 6)) { if (edge && !T && !pr.carrying) tap(c, IN.USE); if (pr.carrying) putAt(c, { x: g.pos.x + 30, y: g.pos.y + 30, z: g.pos.z }); }
  else if (ph === 3 || (T && ph === 7)) { if (edge) tap(c, IN.USE); }
  else if (ph === 8 && !second) { if (g.seat) putAt(c, g.seat.pos); }
  else if (ph === 9 && !second) { if (edge) tap(c, IN.USE); }
  else if (ph === 16 && second) { putAt(c, { x: g.pos.x + 30, y: g.pos.y + 30, z: g.pos.z }); if (edge) tap(c, IN.JUMP); }
}
function fireZeus(c, aim, lead) {      // the AT kit's trigger, aimed at a point (led by the target's velocity when given)
  const p = c.pawn, w = p.FindWeapon('weapon_taser'); if (!w) return false;
  let pt = aim;
  if (lead) { const t = Math.hypot(aim.x - p.pos.x, aim.y - p.pos.y, aim.z - p.pos.z - 64) / CONFIG.AT.SPEED; pt = { x: aim.x + lead.x * t, y: aim.y + lead.y * t, z: aim.z + lead.z * t + 0.5 * CONFIG.AT.GRAVITY * t * t }; }
  lookAt(c, pt); p.eye.pitch = -Math.atan2(pt.z - p.pos.z - 64, Math.max(1, d2(p.pos, pt))) * 180 / Math.PI;
  p.active = w; hooks.gunfire({ weapon: w }); stats.gunfire++;
  return true;
}
function driveObserver(c, pr, step) {
  const p = c.pawn, dv = c.drv;
  if (dv.at === undefined) { dv.at = time; say(c, '!at'); }
  const enemyBase = L[c.team === 2 ? 'ct' : 't'].centre, tgt = D.flags[Math.floor(time / 30) % D.flags.length].pos;
  const ph = time % 12;
  if (ph < 4) { const d = Math.max(450, d2(p.pos, tgt)); p.eye = { pitch: Math.atan2(p.pos.z + 64 - tgt.z, d) * 180 / Math.PI, yaw: yawTo(p.pos, tgt), roll: 0 }; if (ph > 1) p.keys |= IN.USE; }
  else if (ph > 6 && ph < 6.05 && hooks.gunfire) {      // the Zeus trigger: at a flying enemy helicopter in reach if there is one
    const eh = D.helis[c.team === 2 ? 3 : 2].find((h) => h.state === 'flying' && (!BAL || Math.hypot(h.pos.x - p.pos.x, h.pos.y - p.pos.y, h.pos.z - p.pos.z) < 2600));
    if (eh) fireZeus(c, { x: eh.pos.x, y: eh.pos.y, z: eh.pos.z + 80 }, BAL ? eh.vel : null);
    else if (!BAL) fireZeus(c, { x: enemyBase[0], y: enemyBase[1], z: 300 });
  }
  if (step % 1280 === 640) say(c, '!pos');
}
function walk(c, pr, step) {      // what CS2's own bot brain / a walking human does: go to a flag that is not ours
  const p = c.pawn;
  if (p.mt !== 2 || p.pos.z < LOBBY_Z + 400) return;
  const dv = c.drv;
  if (c.bot && c.slot % 7 === 3 && !BAL) return;                   // an idle bot: the leash must move it
  if (dv.hold && time < dv.hold) return;
  if (!dv.goal || step % 256 === (c.slot * 5) % 256) {
    const list = D.flags.filter((f) => f.owner !== c.team);
    let f;
    if (BAL) {      // nearest flag that is not ours most of the time; sometimes one of ours that is being taken, or any
      const hot = D.flags.filter((x) => x.owner === c.team && x.capTeam && x.capTeam !== c.team && x.prog > 0);
      const pool = hot.length && Math.random() < 0.5 ? hot : list.length ? list : D.flags;
      const sorted = pool.slice().sort((a, b) => d2(p.pos, a.pos) - d2(p.pos, b.pos));
      f = sorted[Math.min(sorted.length - 1, Math.random() < 0.65 ? 0 : Math.random() < 0.7 ? 1 : 2)];
    } else f = (list.length ? list : D.flags).slice().sort((a, b) => d2(p.pos, a.pos) - d2(p.pos, b.pos))[(c.slot >> 1) % 2 ? 0 : Math.min(1, (list.length || D.flags.length) - 1)];
    dv.goal = { x: f.pos.x + ((c.slot * 37) % 300) - 150, y: f.pos.y + ((c.slot * 53) % 300) - 150 };
  }
  if (BAL && time - (dv.fight || -9) < 1.5) return;                // stands and fights
  const d = d2(p.pos, dv.goal);
  if (d > 30) { const k = Math.min(1, 250 / 64 / d); p.pos.x += (dv.goal.x - p.pos.x) * k; p.pos.y += (dv.goal.y - p.pos.y) * k; if (p.pos.z <= ground(p.pos.x, p.pos.y) + 30 || !pr.ropeUntil) p.pos.z = ground(p.pos.x, p.pos.y); }
  if (!c.bot && !BAL && step % 448 === (c.slot * 11) % 448) {      // a kit change at the nearest station now and then
    const k = [...world.values()].filter((e) => e.name.startsWith('mv_kit_')).sort((a, b) => d2(p.pos, a.pos) - d2(p.pos, b.pos))[0];
    if (k && d2(p.pos, k.pos) < 500) { putAt(c, k.pos); tap(c, IN.USE); stats.kit++; }
  }
}
// ---- balance mode drivers (mixed matches): the test's own stand-in players. They use the same keys a player has.
const foes = (team) => everyone().filter((c) => c.team !== team && !c.spec && c.pawn.hp > 0 && P(c) && P(c).deployed && !P(c).heli && c.pawn.pos.z > LOBBY_Z + 400);
function hotSpot(team, from, maxD) {      // where the enemy infantry is thickest (a flag's surroundings), nearest first on ties
  let best = null, bn = 0;
  const fs = foes(team);
  for (const f of D.flags) { const n = fs.filter((c) => d2(c.pawn.pos, f.pos) < 700).length - (from ? d2(from, f.pos) / 8000 : 0); if (n > bn && (!maxD || !from || d2(from, f.pos) < maxD)) { bn = n; best = f; } }
  if (!best) return null;
  const near = fs.filter((c) => d2(c.pawn.pos, best.pos) < 700);
  return { x: near.reduce((a, c) => a + c.pawn.pos.x, 0) / near.length, y: near.reduce((a, c) => a + c.pawn.pos.y, 0) / near.length, z: best.pos.z, n: near.length, flag: best };
}
const gaussM = () => { let u = 0; while (u === 0) u = Math.random(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * Math.random()); };
function gunAim(c, origin, centreYaw, cone, range) {      // a human gunner: nearest enemy in the arc, a degree or so of error, bursts
  const p = c.pawn; let best = null, bd = range;
  for (const v of foes(c.team)) { const d = Math.hypot(v.pawn.pos.x - origin.x, v.pawn.pos.y - origin.y, v.pawn.pos.z + 40 - origin.z); if (d < bd && Math.abs(wrap(yawTo(origin, v.pawn.pos) - centreYaw)) < cone) { bd = d; best = v; } }
  if (!best) { for (const h of D.helis[other(c.team)]) { if (h.state !== 'flying') continue; const d = Math.hypot(h.pos.x - origin.x, h.pos.y - origin.y, h.pos.z - origin.z); if (d < bd && Math.abs(wrap(yawTo(origin, h.pos) - centreYaw)) < cone) { bd = d; best = { pawn: { pos: { x: h.pos.x, y: h.pos.y, z: h.pos.z + 40 } } }; } } }
  if (!best) return false;
  const t = best.pawn.pos, dv = c.drv;
  if (!dv.err || time > dv.errAt) { dv.err = [gaussM() * 1.1, gaussM() * 0.8]; dv.errAt = time + 0.4; }
  p.eye = { pitch: Math.atan2(origin.z - (t.z + 40), Math.max(1, d2(origin, t))) * 180 / Math.PI + dv.err[1], yaw: yawTo(origin, t) + dv.err[0], roll: 0 };
  if (time % 2.2 < 1.5) p.keys |= IN.ATTACK;
  return true;
}
function flyTo(c, h, goal, alt, vmax) {
  const p = c.pawn, d = d2(h.pos, goal), agl = h.pos.z - Math.max(ground(h.pos.x, h.pos.y), ground(h.pos.x + h.vel.x, h.pos.y + h.vel.y), ground(h.pos.x + h.vel.x * 2.5, h.pos.y + h.vel.y * 2.5));
  const cy = Math.cos(h.yaw * Math.PI / 180), sy = Math.sin(h.yaw * Math.PI / 180);
  const vf = h.vel.x * cy + h.vel.y * sy, vr = h.vel.x * sy - h.vel.y * cy;
  const dxl = (goal.x - h.pos.x) * cy + (goal.y - h.pos.y) * sy, dyl = (goal.x - h.pos.x) * sy - (goal.y - h.pos.y) * cy;
  const wf = Math.max(-300, Math.min(vmax, dxl * 0.5)), wr = Math.max(-300, Math.min(300, dyl * 0.5));
  if (wf > vf + 30) p.keys |= IN.FORWARD; else if (wf < vf - 30) p.keys |= IN.BACK;
  if (wr > vr + 30) p.keys |= IN.RIGHT; else if (wr < vr - 30) p.keys |= IN.LEFT;
  if (agl < alt - 40) p.keys |= IN.JUMP; else if (agl > alt + 120) p.keys |= IN.DUCK;
  return d;
}
function drivePilotBal(c, pr, step) {
  const p = c.pawn, dv = c.drv, h = pr.heli;
  if (!h) { const own = D.helis[c.team].find((x) => x.owner === c.slot); if (own && own.state === 'parked' && own.seats[0].slot < 0 && step % 64 === 0) { putAt(c, { x: own.pos.x + 150, y: own.pos.y + 40, z: own.pos.z }); tap(c, IN.USE); } return; }
  if (pr.seat !== 0) return;
  const armed = h.M.ROCKETS > 0, onPad = d2(h.pos, h.pad.pos) < 200;
  if (h.landed) {
    p.eye = { pitch: 0, yaw: h.yaw, roll: 0 };
    if (dv.landedAt === undefined) dv.landedAt = time;
    const ready = onPad ? h.hp >= h.maxHp && h.rockets >= h.M.ROCKETS && time - dv.landedAt > 6 : time - dv.landedAt > 4;
    if (ready) { p.keys |= IN.JUMP; dv.tookOff = time; dv.rtb = false; dv.phase = 'in'; }
    return;
  }
  dv.landedAt = undefined;
  if (!dv.rtb && (h.hp < 45 || (armed && h.rockets < 2) || time - (dv.tookOff || time) > 110)) dv.rtb = true;
  if (dv.rtb) {
    const d = flyTo(c, h, h.pad.pos, d2(h.pos, h.pad.pos) < 600 ? 200 : 480, 700);
    p.eye = { pitch: 0, yaw: d > 200 ? yawTo(h.pos, h.pad.pos) : h.pad.yaw, roll: 0 };
    if (d < 120 && h.speed < 110) { p.keys &= ~IN.JUMP; p.keys |= IN.DUCK; }
    return;
  }
  if (!dv.tgt || step % 128 === 0) dv.tgt = hotSpot(c.team, h.pos) || { ...D.flags[(c.slot + Math.floor(time / 40)) % 5].pos, n: 0 };
  const t = dv.tgt, d = d2(h.pos, t);
  if (armed) {      // run in nose-on, fire from 2200 to 700, break off past the target, come round again
    if (dv.phase === 'out') { if (d2(h.pos, dv.out) < 500 || time > dv.outUntil) dv.phase = 'in'; flyTo(c, h, dv.out, 480, 800); p.eye = { pitch: 0, yaw: yawTo(h.pos, dv.out), roll: 0 }; return; }
    flyTo(c, h, t, 430, d < 1500 ? 380 : 800);
    const yaw = yawTo(h.pos, t);
    p.eye = { pitch: Math.atan2(h.pos.z + CONFIG.HELI.CAM.UP - t.z, Math.max(1, d)) * 180 / Math.PI + gaussM() * 0.6, yaw: yaw + gaussM() * 0.6, roll: 0 };
    if (t.n > 0 && d < 2200 && d > 700 && Math.abs(wrap(yaw - h.yaw)) < 5) p.keys |= IN.ATTACK;
    if (d < 650) { const a = (h.yaw + (c.slot % 2 ? 150 : -150)) * Math.PI / 180; dv.out = { x: t.x + Math.cos(a) * 2600, y: t.y + Math.sin(a) * 2600 }; dv.phase = 'out'; dv.outUntil = time + 12; }
  } else {          // a transport: circles the fight with the door (left side) toward it
    const a = Math.atan2(h.pos.y - t.y, h.pos.x - t.x) - 0.5, goal = { x: t.x + Math.cos(a) * 800, y: t.y + Math.sin(a) * 800 };
    flyTo(c, h, goal, 330, d > 1800 ? 800 : 320);
    p.eye = { pitch: 0, yaw: d > 1800 ? yawTo(h.pos, goal) : yawTo(h.pos, t) - 90, roll: 0 };
  }
}
function driveRiderBal(c, pr, step) {
  const h = pr.heli, dv = c.drv;
  if (!h) {
    if (step % 96 !== 0) return;
    const ride = D.helis[c.team].find((x) => x.state === 'parked' && x.ent && x.seats[0].slot >= 0 && x.seats.some((s, i) => i > 0 && s.kind === 'gunner' && s.slot < 0) && d2(x.pos, x.pad.pos) < 300);
    if (ride && d2(c.pawn.pos, ride.pos) < 2500) { putAt(c, { x: ride.pos.x - 60, y: ride.pos.y + 170, z: ride.pos.z }); tap(c, IN.USE); } else walk(c, pr, step);
    return;
  }
  const s = h.seats[pr.seat], G = h.M.GUN;
  if (s.kind === 'gunner') { if (!gunAim(c, { x: h.pos.x, y: h.pos.y, z: h.pos.z + 60 }, h.yaw + G.yaw, G.cone - 5, 3600)) c.pawn.eye = { pitch: 10, yaw: h.yaw + G.yaw + 20 * Math.sin(time), roll: 0 }; }
  else if (h.landed && d2(h.pos, h.pad.pos) > 400) tap(c, IN.USE);
}
function driveMountBal(c, pr, step) {
  const dv = c.drv;
  if (pr.mount < 0) {
    if (step % 128 !== 0) return;
    const fs = foes(c.team), score = (m) => fs.filter((v) => d2(v.pawn.pos, m.pos) < 2600 && Math.abs(wrap(yawTo(m.pos, v.pawn.pos) - m.yaw0)) < m.cone).length;
    const list = D.mounts.filter((m) => (m.team === c.team || m.team === 0) && m.user < 0).map((m) => [score(m), m]).sort((a, b) => b[0] - a[0]);
    if (list.length && list[0][0] > 0 && d2(c.pawn.pos, list[0][1].pos) < 3000) { putAt(c, list[0][1].seat.pos); tap(c, IN.USE); dv.onAt = time; dv.idle = time; } else walk(c, pr, step);
    return;
  }
  const m = D.mounts[pr.mount];
  if (gunAim(c, m.pos, m.yaw0, m.cone - 2, 3600)) dv.idle = time; else c.pawn.eye = { pitch: 0, yaw: m.yaw0 + 10 * Math.sin(time), roll: 0 };
  if (time - (dv.idle || time) > 15) tap(c, IN.USE);
}
function driveCrewBal(c, pr, step) {
  const p = c.pawn, g = D.guns[c.team][pr.crew], dv = c.drv; if (!g) return;
  const T = c.team === 2, edge = step % 16 === 0, maxLoad = CONFIG.ARTY.MAX_LOAD[c.team];
  if (time < g.disabledUntil) { if (pr.board) return; putAt(c, g.pos); p.keys |= IN.USE; return; }
  const mates = g.crew.filter((s) => ctls[s] && !ctls[s].bot), aimer = mates[0] === c.slot, solo = mates.length < 2;
  const wantLoad = g.loaded.length < (T ? 3 : 1) && g.salvo === 0;
  if (aimer && !(solo && wantLoad && !pr.board && !g.target)) {
    if (solo && wantLoad && g.target) { if (pr.board) { if (edge) tap(c, IN.USE); return; } }
    else {
      if (!pr.board) { if (g.seat && d2(p.pos, g.seat.pos) > 40) { putAt(c, g.seat.pos); return; } if (edge) tap(c, IN.USE); return; }
      p.eye = { pitch: 10, yaw: time * 7 % 360, roll: 0 };
      if (g.lay === 'laid' && g.loaded.length && time >= g.cooldown && g.salvo === 0 && time - (dv.locked || 0) > 0.5) { if (edge) tap(c, IN.JUMP); return; }
      if (time - (dv.locked || -99) > 9 && g.lay !== 'laying' && edge) {      // a new target: the oldest mission not shot at, else where the enemy is thickest
        const m = D.missions[c.team].filter((x) => !x.shot).sort((a, b) => a.at - b.at)[0], hs = m ? null : hotSpot(c.team, null);
        const t = m || hs;
        if (t) { Object.assign(pr, uvOf(t.x, t.y)); tap(c, IN.ATTACK); dv.locked = time; }
      }
      return;
    }
  }
  // loading: rack, then the gun (a walk of a few seconds each way)
  if (!wantLoad && !pr.carrying) return;
  if (!dv.leg || time >= dv.legAt) {
    if (!pr.carrying) { if (g.rack) { putAt(c, g.rack); dv.leg = 'take'; dv.legAt = time + 2.5; tap(c, IN.USE); } }
    else { putAt(c, { x: g.pos.x + 30, y: g.pos.y + 30, z: g.pos.z }); dv.leg = 'load'; dv.legAt = time + 2.5; tap(c, IN.USE); }
  } else if (edge && ((dv.leg === 'take' && !pr.carrying) || (dv.leg === 'load' && pr.carrying))) tap(c, IN.USE);
}
function driveObserverBal(c, pr, step) {
  const p = c.pawn, dv = c.drv;
  if (dv.at === undefined) { dv.at = time; say(c, '!at'); }
  const eh = D.helis[other(c.team)].find((h) => h.state === 'flying' && Math.hypot(h.pos.x - p.pos.x, h.pos.y - p.pos.y, h.pos.z - p.pos.z) < 2400);
  if (eh && pr.kit === 'at' && time >= pr.atReadyAt && p.FindWeapon('weapon_taser') && step % 32 === 0) { const e = 60 * gaussM(); fireZeus(c, { x: eh.pos.x + e, y: eh.pos.y + e, z: eh.pos.z + 80 + 40 * gaussM() }, eh.vel); return; }
  if (pr.kit === 'at' && time >= pr.atReadyAt && p.FindWeapon('weapon_taser') && step % 32 === 0) {
    const v = foes(c.team).filter((x) => { const d = d2(x.pawn.pos, p.pos); return d > 300 && d < 1500; }).sort((a, b) => d2(a.pawn.pos, p.pos) - d2(b.pawn.pos, p.pos))[0];
    if (v) { fireZeus(c, { x: v.pawn.pos.x + 40 * gaussM(), y: v.pawn.pos.y + 40 * gaussM(), z: v.pawn.pos.z + 10 }); return; }
  }
  const hs = hotSpot(c.team, p.pos, 6000), mine = D.missions[c.team].find((m) => m.owner === c.slot);
  if (hs && (!mine || (mine.shot && time - mine.at > 20) || d2(mine, hs) > 500) && d2(p.pos, hs) > 500) { dv.goal = null; dv.hold = time + 2; lookAt(c, { x: hs.x, y: hs.y, z: hs.z }); p.keys |= IN.USE; return; }
  walk(c, pr, step);
}
// balance mode: the infantry fight CS2's own bots and players would have, as a rate model (ASSUMPTIONS, see docs/REVIEW_SCRIPT_1.md):
// an infantryman with an enemy inside ENGAGE kills him after about TTK seconds (faster close up, 35 % faster with the MG kit);
// one with no man to shoot at puts HELI_HITS rounds a second into a flying enemy helicopter inside HELI_RANGE.
const FIGHT = { ENGAGE: +(opt.engage || 1300), TTK: +(opt.ttk || 9), HELI_RANGE: 2000, HELI_HITS: +(opt.helihits || 0.8), EVERY: 32 };
const MGW = { 2: 'weapon_negev', 3: 'weapon_m249' }, RIFLEW = { 2: 'weapon_ak47', 3: 'weapon_m4a1' };
function fight() {
  const inf = everyone().filter((c) => { const pr = P(c); return !c.spec && c.pawn.hp > 0 && pr && pr.deployed && !pr.heli && pr.mount < 0 && !pr.board && c.pawn.pos.z > LOBBY_Z + 400; });
  const dts = FIGHT.EVERY / 64;
  for (const a of inf) {
    const pa = P(a); if (pa.carrying) continue;
    let best = null, bd = FIGHT.ENGAGE;
    for (const v of inf) if (v.team !== a.team && v.pawn.hp > 0) { const d = d2(a.pawn.pos, v.pawn.pos); if (d < bd && Math.abs(a.pawn.pos.z - v.pawn.pos.z) < 500) { bd = d; best = v; } }
    const mg = pa.role === 'infantry' && pa.kit === 'mg', wcls = (mg ? MGW : RIFLEW)[a.team];
    // a human AT man fires the launcher (the script's own rocket) at a helicopter low enough, else at a man 400+ u away
    if (!a.bot && pa.role === 'infantry' && pa.kit === 'at' && time >= pa.atReadyAt && a.pawn.FindWeapon('weapon_taser')) {
      const h = D.helis[other(a.team)].find((x) => x.state === 'flying' && x.ent && Math.hypot(x.pos.x - a.pawn.pos.x, x.pos.y - a.pawn.pos.y, x.pos.z - a.pawn.pos.z) < 1600);
      if (h && Math.random() < 0.5) { fireZeus(a, { x: h.pos.x, y: h.pos.y, z: h.pos.z + 80 }, h.vel); continue; }
      if (best && bd > 400 && Math.random() < dts / 3) { fireZeus(a, { x: best.pawn.pos.x, y: best.pawn.pos.y, z: best.pawn.pos.z + 20 }); continue; }
    }
    if (best) {
      a.drv.fight = time;
      const ttk = FIGHT.TTK * (0.45 + 0.75 * bd / FIGHT.ENGAGE) / (mg ? 1.35 : 1);
      if (Math.random() < dts / ttk) best.pawn.TakeDamage({ damage: 150, damageTypes: DT.BULLET, attacker: a.pawn, weapon: new Weapon(wcls, a.pawn) });
      continue;
    }
    if (pa.aiRole) continue;
    for (const h of D.helis[a.team === 2 ? 3 : 2]) {
      if (h.state !== 'flying' || !h.ent || Math.hypot(h.pos.x - a.pawn.pos.x, h.pos.y - a.pawn.pos.y, h.pos.z - a.pawn.pos.z) > FIGHT.HELI_RANGE) continue;
      let n = FIGHT.HELI_HITS * dts * (mg ? 1.5 : 1); n = Math.floor(n) + (Math.random() < n % 1 ? 1 : 0);
      for (let k = 0; k < n; k++) hooks.bullet({ weapon: new Weapon(wcls, a.pawn), position: { ...h.pos }, hitEntity: world.get(h.name) });
      break;
    }
  }
}

// ------------------------------------------------------------------ set pieces: each is a generator that yields seconds to wait, or
// { until: () => bool, what, timeout } to wait for something (a timeout fails the run)
const pieces = [];
function piece(name, t0, make) { if (opt.piece && !name.includes(opt.piece)) return; pieces.push({ name, t0, make, gen: null, wake: 0, cond: null, what: '', deadline: 0, done: false, actors: [] }); }
let curPiece = null;
function free(c) { const pr = P(c); return c && !c.bot && !c.stunt && !c.spec && c.pawn.hp > 0 && pr && pr.deployed; }
function actor(team, pred) {      // a walking human of that team who is doing nothing special
  const c = humans(team).find((x) => free(x) && jobOf(x) === 'walker' && P(x).role === 'infantry' && !P(x).heli && P(x).mount < 0 && (!pred || pred(x)));
  if (!c) return null;
  c.stunt = curPiece.name; c.q = []; c.hold = 0; curPiece.actors.push(c);
  return c;
}
const need = (c, what) => { if (!c) throw new Error('no ' + what); return c; };
function release(pc) { for (const c of pc.actors) { c.stunt = ''; c.god = false; c.hold = 0; c.q = []; } pc.actors = []; }
function runPieces() {
  for (const pc of pieces) {
    if (pc.done || time < pc.t0) continue;
    curPiece = pc;
    try {
      if (!pc.gen) pc.gen = pc.make();
      if (pc.cond) { if (pc.cond()) pc.cond = null; else if (time > pc.deadline) throw new Error('timed out waiting for: ' + pc.what); else continue; }
      if (time < pc.wake) continue;
      const r = pc.gen.next();
      if (r.done) { pc.done = true; release(pc); continue; }
      if (typeof r.value === 'number') pc.wake = time + r.value;
      else { pc.cond = r.value.until; pc.what = r.value.what || '?'; pc.deadline = time + (r.value.timeout || 30); }
    } catch (e) { fail('set piece "' + pc.name + '": ' + (e && e.message ? e.message : e) + ' (t ' + time.toFixed(0) + ')'); pc.done = true; release(pc); }
  }
  curPiece = null;
}
const until = (fn, what, timeout) => ({ until: fn, what, timeout });
const other = (team) => (team === 2 ? 3 : 2);
const alive = (c) => ctls[c.slot] === c && c.pawn.hp > 0;
const enemyOf = (team) => everyone().find((c) => c.team === other(team) && c.pawn.hp > 0 && P(c) && P(c).deployed);
const uvOf = (x, y) => ({ u: (x + 6400) / 12800, v: (6400 - y) / 12800 });
function baseSpot(team, k) { const b = L[team === 2 ? 't' : 'ct'].centre; return { x: b[0] + 60 * (k || 0), y: b[1] + 40, z: ground(b[0], b[1]) }; }
// a gun of that team nobody human crews, loaded and laid on a point by the test (the firing, flight and impact are the script's)
function* gunFire(team, type, pt, missionId, firerSlot, which) {
  const g = which || D.guns[team].find((x) => !x.crew.some((s) => ctls[s] && !ctls[s].bot) && time >= x.disabledUntil) || D.guns[team][D.guns[team].length - 1];
  g.loaded.length = 0; g.loaded.push(type); g.cooldown = 0; g.salvo = 0; g.disabledUntil = 0;
  D.fn.setTarget(g, pt, missionId);
  yield until(() => g.lay === 'laid', 'gun laid', 8);
  const S = CONFIG.ARTY.SIGMA, keep = { 2: S[2], 3: S[3] }, xs = g.extraSigma; S[2] = [0, 0]; S[3] = [0, 0]; g.extraSigma = 0;
  const ok = D.fn.fireGun(g, firerSlot === undefined ? -1 : firerSlot);
  if (ok && team === 2) { yield 0.1; }       // the T salvo's first round goes on the next gun tick
  S[2] = keep[2]; S[3] = keep[3]; g.extraSigma = xs;
  if (!ok) throw new Error('the gun would not fire');
  return g;
}
// the test seats a player in a flying helicopter directly (boarding is only possible on the ground or in a low hover)
function seatHack(c, h, i) { const pr = P(c); h.seats[i].slot = c.slot; pr.heli = h; pr.seat = i; c.pawn.DestroyWeapons(); c.pawn.GiveNamedItem('weapon_knife'); c.pawn.SetModelScale(0.02); c.pawn.SetMoveType(0); pr.hidden = true; pr.moveNone = true; }
const flatAhead = (x, y, yaw, len) => { for (let s = 0; s <= len; s += 150) { const px = x + Math.cos(yaw * Math.PI / 180) * s, py = y + Math.sin(yaw * Math.PI / 180) * s; if (ground(px, py) > 41 || Math.abs(px) > L.map.air[0] - 900 || Math.abs(py) > L.map.air[1] - 900) return false; } return true; };
const flatYaw = (h, len) => { const home = yawTo(h.pos, { x: 0, y: 0 }); return [0, 30, -30, 60, -60, 90, -90, 135, -135, 180].map((d) => home + d).find((y) => flatAhead(h.pos.x, h.pos.y, y, len)) ?? home; };

if (FEATURES) {
  // ---- kit limits (1 in 4) and the marksman kit at a held flag's crate
  piece('kits', 3, function* () {
    const team = 2, list = humans(team).filter((c) => P(c) && P(c).role === 'infantry');
    const lim = Math.max(1, Math.floor(D.players.size && [...D.players.values()].filter((q) => q.team === team).length * 0.25));
    for (const c of list) say(c, '!mg');           // in the briefing room: issued at once, while they last
    yield 0.5;
    const mgs = [...D.players.values()].filter((q) => q.team === team && q.kit === 'mg' && q.role === 'infantry').length;
    if (mgs > lim) throw new Error(mgs + ' machine gunners, limit ' + lim);
    if (list.length > lim && D.stats.kitDenied < 1) throw new Error('nobody was refused the MG kit (' + list.length + ' asked, limit ' + lim + ')');
    hit('kit limit refusals', D.stats.kitDenied);
    yield until(() => D.flags.some((f) => f.owner === team) && humans(team).some((x) => free(x) && jobOf(x) === 'walker'), 'a flag held by T', 400);
    const a = need(actor(team), 'free walker'); a.god = true;
    const f = D.flags.find((x) => x.owner === team);
    putAt(a, world.get('mv_kit_' + f.id).pos);
    for (let k = 0; k < 8 && P(a).kit !== 'marksman'; k++) { if (f.owner !== team) throw new Error('lost the flag while at its crate'); press(a, IN.USE); yield 0.2; }
    if (P(a).kit !== 'marksman' || !a.pawn.FindWeapon('weapon_scar20')) throw new Error('no marksman rifle from the flag crate (kit ' + P(a).kit + ')');
    hit('marksman kit');
    putAt(a, world.get('mv_kit_t').pos); yield 0.2;
    const before = P(a).kit; press(a, IN.USE); yield 0.2;
    if (P(a).kit === 'marksman' && before !== 'marksman') throw new Error('the base rack issued a marksman rifle');
  });
  // ---- Beehive: a CT crewman loads it, locks a point inside 900 u on the board, fires; the men there are hit
  piece('beehive', 34, function* () {
    const b = need(actor(3), 'CT walker'); b.god = true;
    putAt(b, baseSpot(3)); yield 0.1; say(b, '!artillery');
    yield until(() => P(b).role === 'artillery' && P(b).crew >= 0 && P(b).deployed, 'a battery seat', 10);
    const g = D.guns[3][P(b).crew]; g.loaded.length = 0; g.disabledUntil = 0;
    putAt(b, g.rack); yield 0.15;
    press(b, IN.ATTACK2); yield 0.15; press(b, IN.ATTACK2); yield 0.15; press(b, IN.USE); yield 0.15;
    if (P(b).carrying !== 'beehive') throw new Error('expected Beehive in hand, got "' + P(b).carrying + '"');
    putAt(b, { x: g.pos.x + 30, y: g.pos.y + 30, z: g.pos.z }); yield 0.1; press(b, IN.USE); yield 0.15;
    if (g.loaded[g.loaded.length - 1] !== 'beehive') throw new Error('the Beehive round was not loaded');
    const bc = L.ct.centre, dd = Math.max(1, Math.hypot(bc[0] - g.pos.x, bc[1] - g.pos.y)), k = Math.min(450, dd * 0.8) / dd;
    const pt = { x: g.pos.x + (bc[0] - g.pos.x) * k, y: g.pos.y + (bc[1] - g.pos.y) * k };
    const v1 = need(actor(2), 'T victim'), v2 = actor(2);
    for (const v of [v1, v2]) if (v) { putAt(v, { x: pt.x + (v === v1 ? 0 : 50), y: pt.y, z: ground(pt.x, pt.y) }); v.pawn.hp = 100; P(v).protectUntil = 0; }
    putAt(b, g.seat.pos);
    yield until(() => g.aimer < 0, 'the crewmate to leave the board', 60);
    press(b, IN.USE); yield 0.15;
    if (!P(b).board) throw new Error('did not get the board');
    if (b.pawn.weapons.length !== 1) throw new Error('weapons not put away at the board');
    Object.assign(P(b), uvOf(pt.x, pt.y)); press(b, IN.ATTACK);
    yield until(() => g.lay === 'laid' && g.target && d2(g.target, pt) < 5, 'laid for direct fire', 6);
    if (g.pitch > 2) throw new Error('the Beehive lay is not flat (pitch ' + g.pitch + ')');
    const n0 = D.stats.beehive; press(b, IN.JUMP); yield 0.2;
    if (D.stats.beehive <= n0) throw new Error('Beehive hit nobody (shots ' + D.stats.beehiveShots + ')');
    hit('Beehive hits', D.stats.beehive - n0);
    press(b, IN.USE); yield 0.2;
    if (b.pawn.weapons.length < 2) throw new Error('weapons not returned after the board');
    putAt(b, baseSpot(3)); yield 0.1; say(b, '!infantry'); yield 0.2;
    if (P(b).role !== 'infantry') throw new Error('could not go back to the infantry at the base');
  });
  // ---- smoke screen: a WP shell between an emplaced gun and its target; then the same burst after the smoke is gone
  piece('smoke', 60, function* () {
    const m = need(D.mounts.find((x) => x.team === 2 && x.user < 0), 'free T emplaced gun');
    const gnr = need(actor(2), 'T walker'); gnr.god = true;
    const vic = need(actor(3), 'CT walker'); vic.god = true;
    const r = m.yaw0 * Math.PI / 180, at700 = { x: m.pos.x + Math.cos(r) * 700, y: m.pos.y + Math.sin(r) * 700 }, at350 = { x: m.pos.x + Math.cos(r) * 350, y: m.pos.y + Math.sin(r) * 350 };
    putAt(vic, { ...at700, z: ground(at700.x, at700.y) });
    putAt(gnr, m.seat.pos); yield 0.1; press(gnr, IN.USE); yield 0.2;
    if (P(gnr).mount < 0) throw new Error('did not get the gun');
    if (gnr.pawn.weapons.length !== 1) throw new Error('weapons not put away on the emplaced gun');
    const n0 = D.stats.smokes;
    yield* gunFire(3, 'smoke', { ...at350, z: ground(at350.x, at350.y) });
    yield until(() => D.stats.smokes > n0, 'the smoke shell to land', 15);
    const aim = () => { gnr.pawn.eye = { pitch: Math.atan2(m.pos.z - (vic.pawn.pos.z + 40), 700) * 180 / Math.PI, yaw: m.yaw0, roll: 0 }; };
    aim(); const b0 = D.stats.smokeBlocked, dmg0 = stats.dmg; vic.god = false; vic.pawn.hp = 100; P(vic).protectUntil = 0; const hp0 = vic.pawn;
    gnr.hold = IN.ATTACK; yield 1.5; gnr.hold = 0;
    if (D.stats.smokeBlocked <= b0) throw new Error('rounds were not stopped by the smoke');
    if (vic.pawn === hp0 && vic.pawn.hp < 100) throw new Error('the man behind the smoke was hit');
    hit('smoke blocks gunners', D.stats.smokeBlocked - b0);
    yield until(() => D.smokes.length === 0, 'the smoke to clear', 40);
    putAt(vic, { ...at700, z: ground(at700.x, at700.y) }); vic.pawn.hp = 100; P(vic).protectUntil = 0; aim(); const pawn0 = vic.pawn;
    const mk0 = D.stats.killsBy.mount || 0;
    gnr.hold = IN.ATTACK; yield until(() => (D.stats.killsBy.mount || 0) > mk0, 'the emplaced gun to kill its target', 8); gnr.hold = 0;
    hit('emplaced gun kills', (D.stats.killsBy.mount || 0) - mk0);
    press(gnr, IN.RELOAD); yield 0.2;
    if (!m.st.reloadAt) throw new Error('R did not start a belt change');
    hit('belt reload (manual)');
    press(gnr, IN.USE); yield 0.2;
    if (gnr.pawn.weapons.length < 2) throw new Error('weapons not returned after the emplaced gun');
  });
  // ---- the AT rocket: against a flying helicopter, against a gun (counter-battery), then a man repairs the gun; artillery counter-battery
  piece('at + counter-battery', 100, function* () {
    const a = need(actor(2), 'T walker'); a.god = true;
    putAt(a, world.get('mv_kit_t').pos); yield 0.1; say(a, '!at'); yield 0.2;
    if (P(a).kit !== 'at' || !a.pawn.FindWeapon('weapon_taser')) throw new Error('no AT kit at the rack (kit ' + P(a).kit + ')');
    let got = false;
    for (let tries = 0; tries < 6 && !got; tries++) {
      const ok = (x) => x.state === 'flying' && x.alt > 100 && time >= x.guardUntil;
      yield until(() => D.helis[3].some(ok), 'a CT helicopter in the air', 250);
      const h = D.helis[3].find(ok);
      putAt(a, { x: h.pos.x + 420, y: h.pos.y + 60 }); P(a).atReadyAt = 0;
      const n0 = D.stats.rocketHeliHits;
      if (!a.pawn.FindWeapon('weapon_taser')) a.pawn.GiveNamedItem('weapon_taser', true);
      fireZeus(a, { x: h.pos.x, y: h.pos.y, z: h.pos.z + 80 }, h.vel);
      yield 1.2;
      got = D.stats.rocketHeliHits > n0;
    }
    if (!got || !(D.stats.heliDmgBy.at > 0)) throw new Error('six AT rockets, no hit on a helicopter');
    hit('AT rocket hits a helicopter', D.stats.heliDmgBy.at / CONFIG.AT.HELI);
    // the launcher is not reloaded by sitting on a gun for a moment
    const ready = P(a).atReadyAt;
    if (!(ready > time + 5)) throw new Error('AT reload not running');
    const g = D.guns[3].find((x) => !x.crew.some((s) => ctls[s] && !ctls[s].bot)) || D.guns[3][2];
    g.disabledUntil = 0; g.graceUntil = 0;
    putAt(a, { x: g.pos.x + 380, y: g.pos.y, z: ground(g.pos.x + 380, g.pos.y) }); P(a).atReadyAt = 0;
    if (!a.pawn.FindWeapon('weapon_taser')) a.pawn.GiveNamedItem('weapon_taser', true);
    fireZeus(a, { x: g.pos.x, y: g.pos.y, z: g.pos.z + 1 });
    yield until(() => time < g.disabledUntil, 'the gun to be knocked out by the AT rocket', 3);
    hit('counter-battery: AT knocks a gun out', D.stats.gunsDisabledBy.at || 0);
    const r = need(actor(3), 'CT walker'); r.god = true;
    putAt(r, { x: g.pos.x + 40, y: g.pos.y + 20, z: g.pos.z }); const rep0 = D.stats.repairs;
    r.hold = IN.USE; yield until(() => D.stats.repairs > rep0, 'the repair (hold E ' + CONFIG.ARTY.REPAIR_HOLD + ' s)', CONFIG.ARTY.REPAIR_HOLD + 3); r.hold = 0;
    yield 0.1;
    if (time < g.disabledUntil) throw new Error('gun still out after the repair');
    hit('human gun repair', D.stats.repairs - rep0);
    P(a).atReadyAt = 0; if (!a.pawn.FindWeapon('weapon_taser')) a.pawn.GiveNamedItem('weapon_taser', true);
    fireZeus(a, { x: g.pos.x, y: g.pos.y, z: g.pos.z + 1 }); yield 1.5;
    if (time < g.disabledUntil) throw new Error('a gun just repaired was knocked out again inside its grace time');
    hit('repair grace');
    // artillery on artillery
    const tg = D.guns[2].find((x) => time >= x.disabledUntil && !x.crew.some((s) => ctls[s] && !ctls[s].bot)) || D.guns[2][3];
    tg.graceUntil = 0; const n1 = D.stats.gunsDisabledBy.arty || 0;
    yield* gunFire(3, 'he', { x: tg.pos.x, y: tg.pos.y, z: tg.pos.z });
    yield until(() => (D.stats.gunsDisabledBy.arty || 0) > n1, 'the shell to knock the enemy gun out', 15);
    hit('counter-battery: shell knocks a gun out', (D.stats.gunsDisabledBy.arty || 0) - n1);
  });
  // ---- fire missions: three at once on the board, the observer's assist, flash marks from three guns
  piece('fire missions', 150, function* () {
    const obs = [actor(2), actor(2), actor(2)].filter(Boolean);
    if (!obs.length) throw new Error('no T walker');
    const spots = [{ x: -1500, y: 600 }, { x: -1200, y: -400 }, { x: -900, y: 1300 }];
    obs.forEach((o, i) => { o.god = true; putAt(o, spots[i]); lookAt(o, { x: spots[i].x + 1500, y: spots[i].y - 200, z: 40 }); o.hold = IN.USE; });
    yield until(() => obs.every((o) => D.missions[2].some((m) => m.owner === o.slot)), 'the fire missions', 6);
    obs.forEach((o) => { o.hold = 0; });
    hit('fire missions at once', D.missions[2].length);
    const m = D.missions[2].find((x) => x.owner === obs[0].slot);
    // a T crewman looks at the board: every mission has its marker
    const cm = humans(2).find((c) => alive(c) && !c.stunt && P(c).role === 'artillery' && P(c).crew >= 0 && P(c).deployed);
    if (cm) {
      cm.stunt = curPiece.name; cm.q = []; cm.hold = 0; cm.god = true; curPiece.actors.push(cm);
      const g = D.guns[2][P(cm).crew];
      if (!P(cm).board) { yield until(() => g.aimer < 0, 'the T board to be free', 30); putAt(cm, g.seat.pos); yield 0.1; press(cm, IN.USE); yield 0.2; }
      if (!P(cm).board) throw new Error('the crewman did not get the board');
      yield 0.3;
      const n = ['mv_msn0', 'mv_msn1', 'mv_msn2'].filter((id) => shows(cm.slot, id, 'on')).length;
      if (n < Math.min(3, D.missions[2].length)) throw new Error('the board shows ' + n + ' of ' + D.missions[2].length + ' fire missions');
      press(cm, IN.RELOAD); yield 0.2;
      if (!['mv_msn0', 'mv_msn1', 'mv_msn2'].some((id) => shows(cm.slot, id, 'sel'))) throw new Error('R did not select a fire mission');
      hit('board: missions shown and cycled', n);
      press(cm, IN.USE); yield 0.2; cm.stunt = ''; cm.god = false;
    }
    const vic = need(actor(3), 'CT walker'); putAt(vic, { x: m.x, y: m.y, z: m.z }); vic.pawn.hp = 100; P(vic).protectUntil = 0; const pawn0 = vic.pawn;
    const crewman = humans(2).find((c) => P(c) && P(c).role === 'artillery');
    const n0 = D.stats.foAssists, merit0 = P(obs[0]).merit;
    yield* gunFire(2, 'rocket', { x: m.x, y: m.y, z: m.z }, m.id, crewman ? crewman.slot : -1);
    yield until(() => { if (vic.pawn === pawn0 && vic.pawn.hp > 0) { putAt(vic, { x: m.x, y: m.y, z: m.z }); P(vic).protectUntil = 0; } return D.stats.foAssists > n0; }, 'the observer\'s assist', 20);
    if (P(obs[0]).merit <= merit0) throw new Error('no merit for the observer');
    hit('FO assist credit', D.stats.foAssists - n0);
    // three CT guns fire: three flash marks for the T board
    const f0 = D.stats.flashes;
    for (const g of D.guns[3]) { if (time < g.disabledUntil) continue; try { yield* gunFire(3, 'he', { x: 5200, y: 4200, z: 40 }, undefined, -1, g); } catch (e) { /* a crew driver was using it */ } }
    yield until(() => D.stats.flashes >= f0 + 2, 'two or more flash marks', 10);
    hit('flash marks', D.stats.flashes - f0);
  });
  // ---- flight envelope: ceiling, the soft wall, a hard landing, a crash, the wreck, the new helicopter's guard
  piece('flight envelope', 24, function* () {
    const H = CONFIG.HELI, AIR = L.map.air;
    let h = D.helis[3].find((x) => x.owner < 0), f;
    if (h) { f = need(actor(3), 'CT walker'); putAt(f, baseSpot(3, 2)); yield 0.1; say(f, '!air'); yield 0.3; }
    else {
      h = need(D.helis[3].find((x) => ctls[x.owner] && !ctls[x.owner].bot && jobOf(ctls[x.owner]) !== 'pilot'), 'a CT helicopter no pilot driver flies');
      f = ctls[h.owner]; f.stunt = curPiece.name; f.q = []; f.hold = 0; curPiece.actors.push(f);
    }
    f.god = true;
    yield until(() => alive(f) && P(f).role === 'air' && P(f).heli && P(f).seat === 0 && P(f).heli.state === 'parked', 'the pilot seat', 70);
    h = P(f).heli; h.hp = H.HEALTH;
    const dead = () => { if (h.state === 'dead' || h.state === 'crashing') throw new Error('the helicopter was lost (' + h.warn + ', last hit by ' + h.lastSrc + ')'); };
    f.pawn.eye = { pitch: 0, yaw: h.yaw, roll: 0 }; f.hold = IN.JUMP;
    yield until(() => !h.landed && h.alt > 300, 'take-off', 12);
    h.guardUntil = time + 400;                       // nothing else shoots it during the test
    // rockets: a pair at a man on the ground ahead
    f.hold = 0;
    const tgt = need(actor(2), 'T walker'); P(tgt).protectUntil = 0;
    const ry = h.pad.yaw * Math.PI / 180, spot = { x: h.pos.x + Math.cos(ry) * 900, y: h.pos.y + Math.sin(ry) * 900 }; spot.z = ground(spot.x, spot.y);
    const kr0 = D.stats.killsBy.helirocket || 0, tp = tgt.pawn;
    yield until(() => { if (tgt.pawn === tp && tp.hp > 0) { putAt(tgt, spot); P(tgt).protectUntil = 0; } f.pawn.eye = { pitch: Math.atan2(h.pos.z + CONFIG.HELI.CAM.UP - spot.z, d2(h.pos, spot)) * 180 / Math.PI, yaw: yawTo(h.pos, spot), roll: 0 };
      f.hold = Math.abs(wrap(h.yaw - yawTo(h.pos, spot))) < 4 ? IN.ATTACK : 0; return (D.stats.killsBy.helirocket || 0) > kr0; }, 'a rocket kill', 20);
    hit('helicopter rockets kill', (D.stats.killsBy.helirocket || 0) - kr0);
    f.hold = IN.JUMP;
    const ceil0 = D.stats.softWall;
    yield until(() => { dead(); return h.warn === 'CEILING'; }, 'the ceiling warning', 25);
    yield 6; dead();
    if (h.pos.z > AIR[2] + H.BOUNDS.HARD) throw new Error('above the hard ceiling');
    hit('bounds: ceiling', D.stats.softWall - ceil0);
    f.hold = IN.FORWARD; f.pawn.eye = { pitch: 0, yaw: 0, roll: 0 };
    const w0 = D.stats.softWall;
    yield until(() => { dead(); return h.warn.startsWith('LEAVING'); }, 'the soft wall warning', 30);
    yield 12; dead();
    if (Math.abs(h.pos.x) > AIR[0] + H.BOUNDS.HARD || Math.abs(h.pos.y) > AIR[1] + H.BOUNDS.HARD) throw new Error('through the hard wall');
    hit('bounds: soft wall', D.stats.softWall - w0);
    // over flat ground, down, and onto it at about 300 u/s: a hard landing (damage, a bounce), not a wreck
    f.pawn.eye = { pitch: 0, yaw: 180, roll: 0 }; f.hold = IN.FORWARD;
    yield until(() => { dead(); return h.pos.x < AIR[0] - 1500; }, 'back inside', 20);
    f.hold = IN.DUCK; f.pawn.eye = { pitch: 0, yaw: h.yaw, roll: 0 };
    yield until(() => { dead(); return h.alt < 700 && h.speed < 120; }, 'down to 700', 30);
    let yaw = flatYaw(h, 2600);
    f.pawn.eye = { pitch: 0, yaw, roll: 0 }; f.hold = 0;
    yield until(() => Math.abs(wrap(h.yaw - yaw)) < 5, 'the turn', 8);
    const hl0 = D.stats.hardLandings, cl0 = D.stats.crashLandings;
    yield until(() => { dead(); f.hold = IN.DUCK | (h.speed < 300 ? IN.FORWARD : 0); return D.stats.hardLandings > hl0 || h.landed; }, 'a hard landing', 40);
    if (D.stats.hardLandings <= hl0) throw new Error('touched down at ' + Math.round(h.speed) + ' u/s without a hard landing');
    if (!(h.hp < H.HEALTH) || h.hp <= 0) throw new Error('a hard landing should cost airframe health (hp ' + h.hp + ')');
    hit('landing: hard (damage, bounce)', D.stats.hardLandings - hl0);
    // again, at full speed: destroyed
    f.hold = IN.JUMP; yield until(() => { dead(); return h.alt > 260; }, 'climb', 10);
    yaw = flatYaw(h, 3400); f.pawn.eye = { pitch: 0, yaw, roll: 0 }; f.hold = 0;
    yield until(() => Math.abs(wrap(h.yaw - yaw)) < 5, 'the turn', 8);
    yield until(() => { if (h.state === 'dead') return true; f.hold = IN.FORWARD | (h.speed > 780 ? IN.DUCK : h.alt < 200 ? IN.JUMP : 0); return false; }, 'the crash', 40);
    if (D.stats.crashLandings <= cl0) throw new Error('lost, but not by the crash landing rule');
    hit('landing: crash (destroyed)', D.stats.crashLandings - cl0);
    f.hold = 0; f.god = false;
    const wreck = world.get('mv_wreck_' + h.tag), tDead = time;
    if (!(wreck.pos.z > PARK_Z + 500)) throw new Error('no wreck at the crash');
    yield until(() => wreck.pos.z < PARK_Z + 100, 'the wreck to be cleared', H.WRECK_TIME + 3);
    if (time - tDead < H.WRECK_TIME - 1) throw new Error('the wreck went after ' + (time - tDead).toFixed(0) + ' s, WRECK_TIME is ' + H.WRECK_TIME);
    hit('wreck lifetime', 1);
    yield until(() => h.state === 'parked', 'the new helicopter', H.RESPAWN - H.WRECK_TIME + 4);
    const foe = need(enemyOf(3), 'an enemy'), g0 = D.stats.heliGuard;
    D.fn.damageHeli(h, 30, foe.slot, 'helirocket');
    if (h.hp < H.HEALTH || D.stats.heliGuard <= g0) throw new Error('a helicopter just rolled out was damaged');
    hit('pad guard (new helicopter)', D.stats.heliGuard - g0);
    yield H.SPAWN_GUARD + 0.3;
    D.fn.damageHeli(h, 30, foe.slot, 'helirocket');
    if (!(h.hp < H.HEALTH)) throw new Error('the pad guard never ends'); h.hp = H.HEALTH;
  });
  // ---- deploy choices: a held flag, the deploy cover, aboard a waiting helicopter
  piece('spawn modes', 210, function* () {
    const team = 2;
    yield until(() => D.flags.some((f) => f.owner === team), 'a flag held by T', 200);
    const a = need(actor(team), 'T walker');
    let f = D.flags.find((x) => x.owner === team);
    say(a, '!spawn ' + f.id);
    const kill = (c) => { const e = need(enemyOf(c.team), 'an enemy'); P(c).protectUntil = 0; c.pawn.TakeDamage({ damage: 500, damageTypes: DT.BULLET, attacker: e.pawn }); };
    let ok = false;
    for (let tries = 0; tries < 6 && !ok; tries++) {
      f = D.flags.find((x) => x.owner === team && x.id === P(a).spawnSel) || D.flags.find((x) => x.owner === team);
      if (!f) { yield until(() => D.flags.some((x) => x.owner === team), 'a flag held by T (after a round end)', 150); continue; }      // a round can end meanwhile
      if (P(a).spawnSel !== f.id) say(a, '!spawn ' + f.id);
      // a flag with an enemy inside is closed to deploys (right): keep its circle clear while the actor redeploys (busy at 64 players)
      const ff = f, clear = () => { for (const c of everyone()) if (c.team !== team && !c.stunt && c.pawn.hp > 0 && d2(c.pawn.pos, ff.pos) < ff.r + 300) { c.pawn.pos.x += 1500; c.drv.goal = null; c.drv.hold = time + 20; } };
      clear();
      yield until(() => !!enemyOf(team) && alive(a) && P(a).deployed, 'an enemy in the field (a round restart puts everyone in the briefing room)', 30);
      const n0 = D.stats.flagSpawns; kill(a);
      yield until(() => { clear(); return alive(a) && P(a).deployed; }, 'the redeploy', 12);
      yield until(() => alive(a) && P(a).deployed, 'the redeploy', 12);
      ok = D.stats.flagSpawns > n0 && d2(a.pawn.pos, f.pos) < 500;
    }
    if (!ok) throw new Error('never deployed at the chosen flag');
    hit('!spawn at a held flag');
    // deploy cover
    if (!enemyOf(team)) throw new Error('no enemy in the field right after the redeploy');
    const e = need(enemyOf(team), 'an enemy'), g0 = D.stats.spawnGuard;
    a.pawn.TakeDamage({ damage: 60, damageTypes: DT.BULLET, attacker: e.pawn });
    if (a.pawn.hp !== 100 || D.stats.spawnGuard <= g0) throw new Error('hit inside the deploy cover');
    hit('deploy cover', D.stats.spawnGuard - g0);
    a.pawn.TakeDamage({ damage: 30, damageTypes: DT.FALL });
    if (a.pawn.hp === 100) throw new Error('the deploy cover should not stop a fall');
    a.pawn.hp = 100; a.god = true;
    yield CONFIG.SPAWN_PROTECT + 0.3;
    yield until(() => !!enemyOf(team) && alive(a) && P(a).deployed && time >= P(a).deployedAt + CONFIG.SPAWN_PROTECT + 0.2, 'an enemy in the field, the cover over', 30);
    a.god = false; a.pawn.hp = 100;
    a.pawn.TakeDamage({ damage: 30, damageTypes: DT.BULLET, attacker: need(enemyOf(team), 'an enemy').pawn });
    if (a.pawn.hp === 100) throw new Error('the deploy cover never ends');
    // aboard a waiting helicopter
    say(a, '!spawn heli'); ok = false;
    for (let tries = 0; tries < 8 && !ok; tries++) {
      yield until(() => alive(a) && P(a).deployed && D.helis[team].some((h) => h.state === 'parked' && h.seats[0].slot >= 0 && h.seats.some((s, i) => i > 0 && s.slot < 0) && d2(h.pos, h.pad.pos) < 200), 'a friendly helicopter waiting with its pilot', 150);
      const n0 = D.stats.spawnAboard; a.god = false; if (P(a).heli) { press(a, IN.USE); yield 0.2; }
      yield until(() => !!enemyOf(team) && alive(a) && P(a).deployed, 'an enemy in the field', 30);
      kill(a);
      yield until(() => alive(a) && P(a).deployed, 'the redeploy', 12);
      ok = D.stats.spawnAboard > n0 && !!P(a).heli;
    }
    if (!ok) throw new Error('never deployed aboard a helicopter');
    hit('spawn aboard a helicopter');
    say(a, '!spawn base');
  });
  // ---- fast-rope: out of a helicopter in a low, slow hover: a capped fall, no fall damage
  piece('fast-rope', 140, function* () {
    const H = CONFIG.HELI, ok = (h) => h.state === 'flying' && h.alt > 150 && h.alt < H.ROPE_ALT - 40 && h.speed < H.ROPE_SPEED - 60 && h.seats.some((s, i) => i > 0 && s.slot < 0);
    yield until(() => D.helis[2].some(ok) && humans(2).some((x) => free(x) && jobOf(x) === 'walker' && P(x).role === 'infantry' && !P(x).heli && P(x).mount < 0), 'a T helicopter in a low hover', 300);      // the walker test actor() makes
    const h = D.helis[2].find(ok), a = need(actor(2), 'T walker'), n0 = D.stats.ropes, f0 = stats.falls;
    seatHack(a, h, h.seats.findIndex((s, i) => i > 0 && s.slot < 0)); a.pawn.hp = 100;
    press(a, IN.USE); yield 0.15;
    if (D.stats.ropes <= n0 || P(a).heli) throw new Error('E in a low hover did not rope down');
    const pw = a.pawn;
    yield until(() => a.pawn !== pw || a.pawn.pos.z <= ground(a.pawn.pos.x, a.pawn.pos.y) + 2, 'the ground', 6);
    if (a.pawn !== pw || a.pawn.hp < 100 || stats.falls > f0 + 5) { if (a.pawn !== pw || a.pawn.hp < 100) throw new Error('hurt by the rope descent'); }
    if (a.pawn.mt !== 2 || (a.pawn.scale || 1) < 1 || a.pawn.weapons.length < 2) throw new Error('roped down frozen, shrunk or unarmed');
    hit('fast-rope (set piece)', D.stats.ropes - n0);
  });
  // ---- AFK: a crewman who does nothing loses the seat and stops counting; a key brings him back
  // ---- a helicopter's own gun: a gunner in a parked Apache shoots a man in front of the nose
  piece('helicopter gun', 300, function* () {
    yield until(() => D.helis[3].some((h) => h.state === 'parked' && d2(h.pos, h.pad.pos) < 100 && h.seats[1].slot < 0 && h.seats[0].slot < 0) && humans(3).some((x) => free(x) && jobOf(x) === 'walker'), 'a parked CT helicopter with a free gun seat', 200);
    const h = D.helis[3].find((x) => x.state === 'parked' && d2(x.pos, x.pad.pos) < 100 && x.seats[1].slot < 0 && x.seats[0].slot < 0);
    const a = need(actor(3), 'CT walker'), v = need(actor(2), 'T walker'); a.god = true;
    putAt(a, { x: h.pos.x + 60, y: h.pos.y + 150, z: h.pos.z }); yield 0.1; press(a, IN.USE); yield 0.3;
    if (P(a).heli !== h || h.seats[P(a).seat].kind !== 'gunner') throw new Error('did not get the gun seat');
    const r = h.yaw * Math.PI / 180, spot = { x: h.pos.x + Math.cos(r) * 520, y: h.pos.y + Math.sin(r) * 520 }; spot.z = ground(spot.x, spot.y);
    const k0 = D.stats.killsBy.heligun || 0, vp = v.pawn;
    yield until(() => { if (v.pawn === vp && vp.hp > 0) { putAt(v, spot); P(v).protectUntil = 0; } a.pawn.eye = { pitch: Math.atan2(h.pos.z + h.M.GUN.muzzle[2] - spot.z - 40, 520 - h.M.GUN.muzzle[0]) * 180 / Math.PI, yaw: h.yaw, roll: 0 }; a.hold = IN.ATTACK; return (D.stats.killsBy.heligun || 0) > k0; }, 'a kill with the helicopter gun', 12);
    hit('helicopter gun kills', (D.stats.killsBy.heligun || 0) - k0);
    a.hold = 0; press(a, IN.USE); yield 0.3;
    if (P(a).heli) throw new Error('could not leave the parked helicopter');
  });
  piece('afk', 262, function* () {
    const a = need(actor(3), 'CT walker'); a.god = true;
    let m, n0;
    for (let tries = 0; ; tries++) {      // a round that ends meanwhile respawns everyone (review 2: the 32 x 600 run's round 2 began at 268 s)
      if (tries > 3) throw new Error('four rounds ended before an AFK gunner could be tested');
      yield until(() => !D.game.over && alive(a) && P(a).deployed, 'the actor deployed in a running round', 30);
      m = need(D.mounts.find((x) => x.team === 3 && x.user < 0), 'free CT emplaced gun'); n0 = D.stats.afk;
      putAt(a, m.seat.pos); yield 0.1; press(a, IN.USE); yield 0.3;
      if (m.user !== a.slot) throw new Error('did not get the gun');
      const r0 = stats.rounds;
      yield until(() => P(a).afk || D.game.over || stats.rounds !== r0, 'the AFK flag (' + CONFIG.AFK.TIME + ' s)', CONFIG.AFK.TIME + 5);
      if (P(a).afk) break;
      yield until(() => !D.game.over, 'the next round', 60);
    }
    yield 0.1;
    if (m.user >= 0 || P(a).mount >= 0 || a.pawn.mt !== 2) throw new Error('the AFK gunner kept the gun');
    hit('AFK seat release', D.stats.afk - n0);
    press(a, IN.FORWARD, 4); yield 1.5;
    if (P(a).afk) throw new Error('still AFK after a key press');
  });
  // ---- an AFK pilot in the air: the stick is let go (no flying on with the last keys held), it lets down, and he is taken out
  piece('afk pilot', 330, function* () {
    const fly = (c) => free(c) && jobOf(c) === 'pilot' && P(c).heli && P(c).seat === 0 && P(c).heli.state === 'flying' && P(c).heli.alt > 200;
    for (let tries = 0; tries < 4; tries++) {          // a round that ends meanwhile (everyone respawns) starts it over
      yield until(() => everyone().some(fly), 'a human pilot in the air', 200);
      const a = everyone().find(fly), h = P(a).heli, n0 = D.stats.afk;
      a.stunt = curPiece.name; a.q = []; a.hold = IN.FORWARD | IN.JUMP; curPiece.actors.push(a); a.god = true;
      yield 1;
      a.hold = 0;                                                  // hands off: the helicopter hovers (holds altitude) until the AFK flag
      yield until(() => { h.hp = h.maxHp; return P(a).afk || P(a).heli !== h; }, 'the pilot to go AFK', CONFIG.AFK.TIME + 5);
      if (P(a).heli !== h) { release(curPiece); continue; }
      let zMax = h.pos.z;
      yield until(() => { h.hp = h.maxHp; zMax = Math.max(zMax, h.pos.z); return h.landed || h.state !== 'flying' || D.game.over; }, "the AFK pilot's helicopter to come down", 90);
      if (D.game.over) { release(curPiece); continue; }
      if (h.state === 'dead' || h.state === 'crashing') throw new Error("the AFK pilot's helicopter crashed");
      if (zMax > h.pos.z + 2000) throw new Error("the AFK pilot's helicopter climbed first");
      yield 0.5;
      if (P(a).heli || a.pawn.mt !== 2 || (a.pawn.scale || 1) < 1) throw new Error('the AFK pilot is still in the seat (or frozen / shrunk)');
      if (h.owner === a.slot) throw new Error('the AFK pilot still owns the helicopter');
      hit('AFK pilot let down and taken out', D.stats.afk - n0);
      press(a, IN.FORWARD, 4); yield 1.5;
      return;
    }
    throw new Error('four rounds ended before an AFK pilot could be tested');
  });
  // ---- a player joins in the middle of the round
  piece('late join', 120, function* () {
    // a full server (64 slots): a bot leaves first and the newcomer takes its slot
    let slot; if (ctls.length >= 64) { const b = need(everyone().find((x) => x.bot && !x.stunt && P(x) && !P(x).aiRole), 'a bot to make room'); slot = b.slot; hooks.disc({ playerSlot: slot }); b.pawn.valid = false; ctls[slot] = undefined; }
    const n0 = D.stats.lateJoins, c = addPlayer(false, slot, 1.5);      // the client is still loading for 1.5 s after it spawns
    yield 2.5;
    if (P(c) && !P(c).deployed && !shows(c.slot, 'mv_brief')) throw new Error('the late joiner sees no briefing card (HUD sent while his client loaded was lost)');
    hit('late join: HUD sent again once the client has loaded', D.stats.hudActivates || 0);
    yield until(() => P(c) && P(c).deployed, 'the late joiner to deploy', CONFIG.LOBBY_FIRST + 6);
    yield 0.5;
    if (!shows(c.slot, 'mv_obj')) throw new Error('no objective bar for the late joiner');
    if (D.stats.lateJoins <= n0) throw new Error('late join not counted');
    hit('late join', D.stats.lateJoins - n0);
  });
  // ---- two E presses on the same seat in the same tick
  piece('two on one seat', 335, function* () {
    yield until(() => humans(3).filter((x) => free(x) && jobOf(x) === 'walker' && P(x).role === 'infantry' && !P(x).heli && P(x).mount < 0).length >= 2, 'two free CT walkers', 120);
    const m = need(D.mounts.find((x) => x.team === 3 && x.user < 0), 'free CT emplaced gun');
    const a = need(actor(3), 'CT walker'), b = need(actor(3), 'second CT walker'); a.god = b.god = true;
    putAt(a, m.seat.pos); putAt(b, { x: m.seat.pos.x + 12, y: m.seat.pos.y, z: m.seat.pos.z }); yield 0.1;
    press(a, IN.USE); press(b, IN.USE); yield 0.3;
    const got = [a, b].filter((c) => P(c).mount >= 0);
    if (got.length !== 1 || m.user !== got[0].slot) throw new Error(got.length + ' players on one emplaced gun');
    hit('two E on one seat: one gets it');
    press(got[0], IN.USE); yield 0.2;
    // a role asked for out in the field waits for the next deploy
    const far = got[0], d0 = D.stats.roleDeferred; putAt(far, { x: 0, y: -900 }); yield 0.1; say(far, '!air'); yield 0.1;
    if (D.stats.roleDeferred <= d0 || P(far).role !== 'infantry' || d2(far.pawn.pos, { x: 0, y: -900 }) > 50) throw new Error('a role request in the field was not deferred');
    hit('role change deferred to the next deploy', D.stats.roleDeferred - d0); say(far, '!infantry');
  });
}

if (SCEN === 'edge') {
  const full = (team) => D.helis[team].find((h) => h.state === 'flying' && h.alt > 200 && h.seats[0].slot >= 0 && ctls[h.seats[0].slot] && !ctls[h.seats[0].slot].bot);
  // a helicopter shot down with every seat taken: everyone aboard dies, the killer is credited, nobody comes back shrunk or frozen
  piece('shot down full', 30, function* () {
    yield until(() => full(2), 'a T helicopter flying', 120);
    const h = full(2), riders = [];
    for (let i = 1; i < h.seats.length; i++) { if (h.seats[i].slot >= 0) continue; const c = humans(2).find((x) => free(x) && !P(x).heli && P(x).mount < 0 && !P(x).board && jobOf(x) !== 'pilot'); if (!c) break; c.stunt = curPiece.name; curPiece.actors.push(c); riders.push(c); seatHack(c, h, i); }
    const aboard = h.seats.filter((s) => s.slot >= 0).map((s) => ctls[s.slot]), pawns = aboard.map((c) => c.pawn);
    const foe = need(enemyOf(2), 'an enemy'), k0 = P(foe).kills, t0 = D.game.tickets[2];
    D.fn.damageHeli(h, 500, foe.slot, 'helirocket');
    yield until(() => h.state === 'dead', 'the crash', 25);
    const stayed = aboard.filter((c, i) => c.stunt || i === 0);          // a rider driver may have jumped on the way down
    if (stayed.some((c) => c.pawn === pawns[aboard.indexOf(c)] && c.pawn.hp > 0)) throw new Error('someone aboard survived the crash');
    if (P(foe) && P(foe).kills - k0 < stayed.length) throw new Error('the killer got ' + (P(foe).kills - k0) + ' kills for ' + stayed.length + ' aboard');
    if (t0 - D.game.tickets[2] < stayed.length) throw new Error('tickets not paid for the crew');
    hit('shot down with ' + aboard.length + ' aboard');
    yield until(() => aboard.every((c) => alive(c) && P(c).deployed), 'everyone to deploy again', 15);
    for (const c of aboard) if ((c.pawn.scale || 1) < 1 || (c.pawn.mt !== 2 && !P(c).heli)) throw new Error('slot ' + c.slot + ' came back shrunk or frozen');
  });
  // the pilot quits in the air: the helicopter settles by itself, the riders can get out, the ground crew fetch it home
  piece('pilot quits mid-air', 70, function* () {
    yield until(() => full(3), 'a CT helicopter flying', 120);
    const h = full(3), pilot = ctls[h.seats[0].slot];
    const rider = humans(3).find((x) => free(x) && !P(x).heli && P(x).mount < 0 && !P(x).board && jobOf(x) === 'walker');
    if (rider) { rider.stunt = curPiece.name; curPiece.actors.push(rider); rider.god = true; const i = h.seats.findIndex((s, k) => k > 0 && s.slot < 0);
      seatHack(rider, h, i); }
    h.guardUntil = time + 200;
    hooks.disc({ playerSlot: pilot.slot }); pilot.pawn.valid = false; ctls[pilot.slot] = undefined;
    at(6, () => addPlayer(false, pilot.slot));
    yield 0.2;
    if (h.owner >= 0 || h.seats[0].slot >= 0) throw new Error('the gone pilot still holds the helicopter');
    yield until(() => h.landed || h.state === 'dead', 'the pilotless helicopter to settle', 60);
    if (h.state === 'dead') { hit('pilot quit mid-air: wrecked on the way down'); return; }
    hit('pilot quit mid-air: settled');
    if (rider && alive(rider) && P(rider).heli === h) { press(rider, IN.USE); yield 0.3; if (P(rider).heli) throw new Error('the rider could not get out'); if (rider.pawn.mt !== 2 || (rider.pawn.scale || 1) < 1) throw new Error('the rider got out frozen or shrunk'); }
    if (d2(h.pos, h.pad.pos) > CONFIG.HELI.PAD_RADIUS && h.owner < 0) { const r0 = D.stats.recalls; yield until(() => D.stats.recalls > r0 || h.owner >= 0 || h.state !== 'parked', 'the empty helicopter to be fetched home', CONFIG.HELI.ABANDON + 6); if (D.stats.recalls > r0) hit('abandoned helicopter fetched home'); }
  });
  // deaths at the board, on an emplaced gun, with a round in hand
  piece('deaths in seats', 110, function* () {
    const crew = humans(3).find((c) => jobOf(c) === 'crew' && alive(c) && P(c).role === 'artillery');
    if (crew) {
      crew.stunt = curPiece.name; crew.q = []; crew.hold = 0; curPiece.actors.push(crew);
      for (const was of ['carry', 'board']) {
        yield until(() => alive(crew) && P(crew).deployed && P(crew).role === 'artillery' && P(crew).crew >= 0, 'the crewman at his gun', 15);
        const g = D.guns[3][P(crew).crew];
        if (was === 'carry') { g.loaded.length = 0; putAt(crew, g.rack); yield 0.1; press(crew, IN.USE); yield 0.2; if (!P(crew).carrying) throw new Error('no round taken'); }
        else { yield until(() => g.aimer < 0, 'the board to be free', 40); putAt(crew, g.seat.pos); yield 0.1; press(crew, IN.USE); yield 0.2; if (!P(crew).board) throw new Error('no board'); }
        P(crew).protectUntil = 0; crew.pawn.TakeDamage({ damage: 500, damageTypes: DT.BULLET, attacker: need(enemyOf(3), 'an enemy').pawn });
        if (P(crew).board || P(crew).carrying || g.aimer === crew.slot) throw new Error('death at the ' + was + ' left state behind');
        if ([...world.values()].some((e) => /^mv_shell_[1-6]$/.test(e.name) && e.pos.z > PARK_Z + 500)) throw new Error('a carried round was left in the world');
        hit('death at the ' + was);
      }
    }
    const m = need(D.mounts.find((x) => x.team === 2 && x.user < 0), 'free T emplaced gun'), a = need(actor(2), 'T walker');
    putAt(a, m.seat.pos); yield 0.1; press(a, IN.USE); yield 0.2;
    if (P(a).mount < 0) throw new Error('no gun');
    a.pawn.TakeDamage({ damage: 500, damageTypes: DT.BULLET, attacker: need(enemyOf(2), 'an enemy').pawn });
    if (m.user >= 0 || P(a).mount >= 0) throw new Error('death on the emplaced gun left it taken');
    hit('death on an emplaced gun');
    yield until(() => alive(a) && P(a).deployed, 'the redeploy', 12);
    if (a.pawn.mt !== 2 || (a.pawn.cam && a.pawn.cam.mode !== 0)) throw new Error('came back frozen or on the gun camera');
  });
  // flags: contested = frozen; three count, a fourth adds nothing; tickets never go below zero and the round ends once
  piece('flags and tickets', 150, function* () {
    const f = D.flags[1], T2 = [actor(2), actor(2), actor(2), actor(2)].filter(Boolean), C3 = [actor(3)].filter(Boolean);
    if (T2.length < 2 || !C3.length) throw new Error('not enough walkers');
    for (const c of [...T2, ...C3]) c.god = true;
    const others = () => everyone().filter((c) => !c.stunt && c.pawn.hp > 0 && d2(c.pawn.pos, f.pos) < f.r + 200);
    const clear = () => { for (const c of others()) { c.pawn.pos.x += 1200; c.drv.goal = null; c.drv.hold = time + 30; } };
    f.owner = 3; f.prog = 0; f.capTeam = 0;
    T2.forEach((c, i) => putAt(c, { x: f.pos.x + 40 * i, y: f.pos.y + 60, z: f.pos.z })); putAt(C3[0], { x: f.pos.x, y: f.pos.y - 60, z: f.pos.z });
    clear(); yield 0.6; clear();
    const p0 = f.prog; yield 1.5; clear();
    if (!f.contested || Math.abs(f.prog - p0) > 1e-6) throw new Error('a contested flag moved (contested ' + f.contested + ', ' + p0 + ' -> ' + f.prog + ')');
    hit('contested flag frozen');
    putAt(C3[0], { x: f.pos.x + 3000, y: f.pos.y, z: 40 }); clear(); yield 0.6;
    const p1 = f.prog, t1 = time; yield 1.0; clear();
    const rate = (f.prog - p1) / (time - t1), want = Math.min(CONFIG.CONQUEST.CAPTURE_MAX, T2.length) / CONFIG.CONQUEST.CAPTURE_SECONDS;
    if (f.owner === 3 && Math.abs(rate - want) > want * 0.25) throw new Error('capture rate ' + rate.toFixed(3) + '/s with ' + T2.length + ' men, expected ' + want.toFixed(3));
    hit('capture rate capped at ' + CONFIG.CONQUEST.CAPTURE_MAX);
    // ticket underflow
    const term0 = stats.terminate; D.game.tickets[3] = 2;
    const vics = humans(3).filter((c) => alive(c) && P(c).deployed && !P(c).heli).slice(0, 6), e = need(enemyOf(3), 'an enemy');
    for (const v of vics) { v.god = false; P(v).protectUntil = 0; v.pawn.TakeDamage({ damage: 500, damageTypes: DT.BULLET, attacker: e.pawn }); }
    yield 0.2;
    if (D.game.tickets[3] !== 0) throw new Error('tickets at ' + D.game.tickets[3] + ' after ' + vics.length + ' deaths from 2');
    if (stats.terminate !== term0 + 1 || !D.game.over || D.game.winner !== 2) throw new Error('the round did not end exactly once for T (' + (stats.terminate - term0) + ' ends, winner ' + D.game.winner + ')');
    hit('ticket underflow: clamped, one round end');
  });
}

// ------------------------------------------------------------------ review pass 2: one set piece per bug class (docs/REVIEW_SCRIPT_2.md)
// node test/mock.mjs 32 400 scenario=review2 humans=4   (each fails on out/review2/before_review2.js: add script=out/review2/before_review2.js)
if (SCEN === 'review2') {
  const grab = (c) => { c.stunt = curPiece.name; c.q = []; c.hold = 0; curPiece.actors.push(c); return c; };
  const H = () => CONFIG.HELI;
  // flat dry ground in the open, well away from the helicopter's pad and the map edge
  const fieldSpot = (h) => {
    for (const [x, y] of [[1800, -1900], [-1500, -2600], [2200, 2400], [-900, 3300], [3600, -1200], [-3200, -1000], [1200, 1500]]) {
      if (ground(x, y) === 40 && !inRiver(x, y) && d2({ x, y }, h.pad.pos) > 2500 && L.flags.every((f) => Math.hypot(f.x - x, f.y - y) > 600)) return { x, y };
    }
    throw new Error('no flat field spot');
  };
  const quit = (c, back) => { hooks.disc({ playerSlot: c.slot }); c.pawn.valid = false; ctls[c.slot] = undefined; if (back) { const s = c.slot, bot = c.bot; at(back, () => { if (!ctls[s]) addPlayer(bot, s); }); } };
  // (1) say(): a player's name goes to the server console with !pos; control characters must not reach it (`;` and `"` already could not)
  piece('say: control characters in a name', 3, function* () {
    const c = need(everyone().find((x) => !x.bot && x.pawn.hp > 0), 'a human');
    const n0 = stats.cmds.say || 0, keep = c.name;
    c.name = 'Tom";quit;"\x1b[2J\x00\tx'; say(c, '!pos'); c.name = keep;
    if ((stats.cmds.say || 0) <= n0) throw new Error('!pos said nothing');
    hit('say strips control characters');
  });
  // (2) a departed player's controller left in its slot (no disconnect event, IsConnected false): its AI role, seat, gun crew and
  // helicopter go back at once, and the director gives the role to another bot
  const after = (name) => until(() => pieces.every((x) => x.name !== name || x.done), 'set piece "' + name + '" to finish', 400);
  piece('departed controller', 150, function* () {
    yield after('one yield per human, withdrawn'); yield after('waiting human, AI pilot gone');
    for (const role of ['pilot', 'crew']) {
      yield until(() => everyone().some((c) => c.bot && c.pawn.hp > 0 && P(c) && P(c).aiRole === role && P(c).deployed), 'a bot with the AI ' + role + ' role', 120);
      const c = everyone().find((x) => x.bot && x.pawn.hp > 0 && P(x) && P(x).aiRole === role && P(x).deployed), team = c.team, slot = c.slot, d0 = D.stats.departed || 0;
      depart(c, 8); at(10, () => { if (!ctls[slot]) addPlayer(true, slot); });
      yield 1;
      const q = D.players.get(slot);
      if (q && (q.aiRole || q.team)) throw new Error('slot ' + slot + ' (departed, controller left behind) still has ' + (q.aiRole ? 'the AI ' + q.aiRole + ' role' : 'a side'));
      if (D.helis[team].some((h) => h.owner === slot || h.seats.some((s) => s.slot === slot))) throw new Error('a helicopter still belongs to departed slot ' + slot);
      if (D.guns[team].some((g) => g.crew.includes(slot))) throw new Error('a gun crew still lists departed slot ' + slot);
      yield until(() => [...D.players.values()].some((x) => x.team === team && x.aiRole === role && x.slot !== slot), 'another bot to take the AI ' + role + ' role', 15);
      hit('departed controller: AI ' + role + ' handed on', (D.stats.departed || 0) - d0);
    }
  });
  // (3) one AI helicopter comes home per waiting human; !infantry withdraws the request and nobody is put in a helicopter later
  piece('one yield per human, withdrawn', 30, function* () {
    const team = 2, keep = { p: CONFIG.AI.PILOTS, s: CONFIG.AI.MAX_ROLE_SHARE };
    CONFIG.AI.PILOTS = 3; CONFIG.AI.MAX_ROLE_SHARE = 1;
    const aiFlying = () => D.helis[team].filter((h) => h.ai && h.state === 'flying' && ctls[h.owner] && ctls[h.owner].bot && h.yieldTo < 0);
    const who = () => everyone().find((c) => !c.bot && c.team === team && !c.stunt && c.pawn.hp > 0 && P(c) && P(c).deployed && P(c).role !== 'air' && !P(c).heli);
    yield until(() => aiFlying().length >= 2 && who(), 'two AI helicopters in the air and a T human on foot', 240);
    const a = grab(who()); a.god = true;
    putAt(a, baseSpot(team)); yield 0.1;
    say(a, '!air'); yield 0.3; say(a, '!air'); yield 0.3;
    const yielding = D.helis[team].filter((h) => h.yieldTo === a.slot);
    if (yielding.length > 1) throw new Error(yielding.length + ' AI helicopters were called home for one human');
    if (!yielding.length) throw new Error('no AI helicopter was called home (role ' + P(a).role + ')');
    hit('one AI helicopter per waiting human');
    const h1 = yielding[0];
    say(a, '!infantry'); yield 0.3;
    if (D.helis[team].some((h) => h.yieldTo === a.slot) || P(a).waitRole) throw new Error('!infantry did not withdraw the helicopter request');
    const t1 = time;      // the AI may land (it had turned for home) or fly on (it had not yet): either way he must stay on foot
    yield until(() => (h1.state === 'parked' && d2(h1.pos, h1.pad.pos) < H().PAD_RADIUS) || h1.state === 'dead' || P(a).role === 'air' || time - t1 > 90, 'the AI helicopter back on its pad, or 90 s', 100);
    yield 2;
    if (P(a).role === 'air' || D.helis[team].some((h) => h.owner === a.slot)) throw new Error('a withdrawn request still put the player in a helicopter');
    hit('withdrawn helicopter request');
    CONFIG.AI.PILOTS = keep.p; CONFIG.AI.MAX_ROLE_SHARE = keep.s;
  });
  // (3b) the AI pilot of the helicopter coming home for a human leaves on the way: the human gets that helicopter (it was locked:
  // no owner, and both the director and takeHeli skipped a helicopter with a yieldTo)
  piece('waiting human, AI pilot gone', 30, function* () {
    yield after('one yield per human, withdrawn');
    const team = 3, keep = { p: CONFIG.AI.PILOTS, s: CONFIG.AI.MAX_ROLE_SHARE };
    CONFIG.AI.PILOTS = 3; CONFIG.AI.MAX_ROLE_SHARE = 1;
    const aiOwned = (h) => h.ai && ctls[h.owner] && ctls[h.owner].bot;
    const who = () => everyone().find((c) => !c.bot && c.team === team && !c.stunt && c.pawn.hp > 0 && P(c) && P(c).deployed && P(c).role !== 'air' && !P(c).heli);
    yield until(() => D.helis[team].every((h) => h.owner >= 0 && h.yieldTo < 0 && (!ctls[h.owner] || !ctls[h.owner].bot || (aiOwned(h) && h.state === 'flying'))) && D.helis[team].some(aiOwned) && who(),
      'every CT helicopter held, the AI ones in the air, a CT human on foot', 300);
    const a = grab(who()); a.god = true;
    putAt(a, baseSpot(team)); yield 0.1;
    say(a, '!air'); yield 0.3;
    const x = D.helis[team].find((h) => h.yieldTo === a.slot);
    if (!x) { if (P(a).role === 'air') { hit('waiting human: helicopter at once'); CONFIG.AI.PILOTS = keep.p; CONFIG.AI.MAX_ROLE_SHARE = keep.s; return; } throw new Error('no AI helicopter was called home'); }
    quit(ctls[x.owner], 8);
    yield until(() => P(a).role === 'air' && D.helis[team].some((h) => h.owner === a.slot), 'the waiting human to get a helicopter after its AI pilot left', 8);
    if (D.helis[team].some((h) => h.yieldTo === a.slot)) throw new Error('a helicopter still waits for a human who has one');
    hit('waiting human: helicopter whose AI pilot left handed over');
    CONFIG.AI.PILOTS = keep.p; CONFIG.AI.MAX_ROLE_SHARE = keep.s;
    say(a, '!artillery');
  });
  // (4) a pilot gone in the air over the river: the helicopter holds its height and creeps to the bank before it lets down
  piece('pilot gone over the river', 100, function* () {
    const team = 2, fly = (c) => c.team === team && !c.bot && !c.stunt && P(c) && P(c).heli && P(c).seat === 0 && P(c).heli.state === 'flying' && P(c).heli.alt > 100;
    yield until(() => everyone().some(fly), 'a T human pilot in the air', 200);
    const c = grab(everyone().find(fly)), h = P(c).heli;
    const x = -1500, y = riverY(x); h.pos = { x, y, z: L.map.water_z + 260 }; h.vel = { x: 0, y: 0, z: 0 }; h.guardUntil = time + 120;
    yield 0.1;
    quit(c, 6);
    yield until(() => h.landed || h.state === 'dead' || h.state === 'crashing', 'the pilotless helicopter to come down', 60);
    if (h.state !== 'parked') throw new Error('the pilotless helicopter ditched in the river (' + h.state + ')');
    if (inRiver(h.pos.x, h.pos.y)) throw new Error('landed in the river bed');
    hit('pilotless helicopter crept off the river');
  });
  // (5) a pilot killed in the air redeploys on his pad while his empty helicopter lets itself down in the field: it is fetched
  piece('pilot back on his pad', 100, function* () {
    const team = 3, fly = (c) => c.team === team && !c.bot && !c.stunt && P(c) && P(c).heli && P(c).seat === 0 && P(c).heli.state === 'flying' && P(c).heli.alt > 100;
    yield until(() => everyone().some(fly), 'a CT human pilot in the air', 200);
    const c = grab(everyone().find(fly)), h = P(c).heli, sp = fieldSpot(h);
    h.pos = { x: sp.x, y: sp.y, z: ground(sp.x, sp.y) + 2600 }; h.vel = { x: 0, y: 0, z: 0 }; h.guardUntil = time + 120;
    yield 0.1;
    c.pawn.hp = 0; die(c.pawn, undefined);
    yield until(() => h.landed || h.state === 'dead', 'the empty helicopter to come down', 40);
    if (h.state === 'dead') throw new Error('the empty helicopter was lost on the way down');
    yield until(() => (P(c) && P(c).heli === h) || (h.state === 'parked' && d2(h.pos, h.pad.pos) < H().PAD_RADIUS), 'the helicopter back with its pilot (pilot ' + (P(c) && P(c).deployed ? 'deployed' : 'in the lobby') + ')', 20);
    hit('helicopter fetched for its pilot', D.stats.fetched || 0);
  });
  // (6) an AI gunner left in a helicopter whose pilot quit in the field: the helicopter still goes home (and the gunner with it)
  piece('AI gunner in an abandoned helicopter', 170, function* () {
    yield after('departed controller');
    CONFIG.AI.PILOTS = 0;                  // no AI pilot may fly the abandoned helicopter home: the ground crew must fetch it
    const ok = (h) => h.state === 'parked' && ctls[h.owner] && !ctls[h.owner].bot && !ctls[h.owner].stunt && h.seats.some((s) => s.kind === 'gunner' && s.slot >= 0 && ctls[s.slot] && ctls[s.slot].bot && P(ctls[s.slot]).aiRole === 'gunner');
    yield until(() => D.helis[2].concat(D.helis[3]).some(ok), 'a human\'s parked helicopter with an AI gunner aboard', 200);
    const h = D.helis[2].concat(D.helis[3]).find(ok), sp = fieldSpot(h), r0 = D.stats.recalls;
    quit(ctls[h.owner]);                   // not back: a newcomer in the slot could be drawn into the air role and fly it home himself
    for (const c of everyone()) if (!c.bot && c.team === h.team) { grab(c); say(c, '!infantry'); }      // nor may the side's other humans
    h.pos = { x: sp.x, y: sp.y, z: ground(sp.x, sp.y) }; h.guardUntil = time + 200;
    for (const t of [2, 3]) D.game.tickets[t] = Math.max(D.game.tickets[t], 400);      // no round end (new helicopter objects) during the wait
    const t0 = time;
    yield until(() => d2(h.pos, h.pad.pos) < H().PAD_RADIUS || h.state !== 'parked' || time - t0 > H().ABANDON + 8, 'the abandoned helicopter to be fetched home', H().ABANDON + 10);
    if (h.state !== 'parked' || d2(h.pos, h.pad.pos) > H().PAD_RADIUS) throw new Error('the abandoned helicopter is not on its pad (' + h.state + ', owner ' + h.owner + (ctls[h.owner] ? (ctls[h.owner].bot ? ' bot ' : ' human ') + P(ctls[h.owner]).aiRole : '') + ', ' + Math.round(d2(h.pos, h.pad.pos)) + ' u from it, recalls ' + (D.stats.recalls - r0) + ', aboard ' + h.seats.map((s) => s.slot < 0 ? '-' : (ctls[s.slot] && ctls[s.slot].bot ? 'bot' : 'human') + s.slot).join(' ') + ', idle ' + h.idleT.toFixed(1) + ')');
    const g = h.seats.find((s) => s.kind === 'gunner' && s.slot >= 0);
    if (g && ctls[g.slot] && ctls[g.slot].pawn.hp > 0 && d2(ctls[g.slot].pawn.pos, h.pos) > 400) throw new Error('the AI gunner was left behind in the field');
    hit('abandoned helicopter with an AI gunner fetched home');
    CONFIG.AI.PILOTS = 1;
  });
}

// ------------------------------------------------------------------ churn: players come and go in whatever seat they are in
function churn(step) {
  if (step % 150 !== 75) return;
  const list = everyone().filter((c) => !c.spec);
  // every third time someone in a seat, a crew or at a gun is picked on purpose
  const seated = list.filter((c) => { const pr = P(c); return pr && (pr.heli || pr.mount >= 0 || pr.board || pr.carrying || pr.crew >= 0 || D.helis[c.team].some((h) => h.owner === c.slot)); });
  const c = (step % 450 === 75 && seated.length ? seated : list)[Math.floor(Math.random() * (step % 450 === 75 && seated.length ? seated : list).length)];
  if (!c) return;
  const kind = ['quit', 'swap-slot', 'team', 'spectate', 'suicide', 'quit'][Math.floor(Math.random() * 6)];
  const pr = P(c), where = pr ? (pr.heli ? (pr.seat === 0 ? (pr.heli.landed ? 'pilot' : 'pilot-air') : 'aboard') : pr.mount >= 0 ? 'mount' : pr.board ? 'board' : pr.carrying ? 'carry' : pr.crew >= 0 ? 'crew' : pr.deployed ? 'foot' : 'lobby') : 'new';
  stats.churn[kind + ':' + where] = (stats.churn[kind + ':' + where] || 0) + 1;
  if (kind === 'quit') { hooks.disc({ playerSlot: c.slot }); c.pawn.valid = false; ctls[c.slot] = undefined; const bot = c.bot, slot = c.slot; at(1 + Math.random() * 6, () => { if (!ctls[slot]) addPlayer(bot, slot); }); }
  else if (kind === 'swap-slot') { c.pawn.valid = false; const n = new Ctl(c.slot, c.team, c.bot); ctls[c.slot] = n; spawn(n); }      // no disconnect event at all
  else if (kind === 'team') { c.pawn.hp = 0; die(c.pawn, undefined); c.team = other(c.team); }
  else if (kind === 'spectate') { const team = c.team; c.pawn.hp = 0; die(c.pawn, undefined); c.team = 1; c.spec = true; at(4 + Math.random() * 8, () => { if (ctls[c.slot] === c) { c.spec = false; c.team = team; spawn(c); } }); }
  else if (c.pawn.hp > 0) { c.pawn.hp = 0; die(c.pawn, undefined); }
}

// checks that run on a schedule
const checks = [];
function expect(dt, what, fn) { checks.push({ at: time + dt, what, fn }); }

// ------------------------------------------------------------------ invariants: nothing a player left may still point at them
function invariants() {
  const seen = (slot) => { const c = ctls[slot]; return c && !c.spec && !c.gone ? c : null; };
  for (const t of [2, 3]) {
    for (const h of D.helis[t]) {
      if (!fin(h.pos) || !fin(h.vel) || ![h.yaw, h.pitch, h.roll, h.hp].every(Number.isFinite)) fail('helicopter ' + h.tag + ' has a non-finite state');
      if (h.state === 'flying') maxAlt = Math.max(maxAlt, h.pos.z - ground(h.pos.x, h.pos.y));
      h.seats.forEach((s, i) => { if (s.slot >= 0) { const q = D.players.get(s.slot); if (!q || q.heli !== h || q.seat !== i) fail('seat ' + i + ' of ' + h.tag + ' points at a player who is not in it'); else if (q.team !== t) fail('seat ' + i + ' of ' + h.tag + ' holds an enemy'); } });
      if (h.owner >= 0) { const q = D.players.get(h.owner); if (!q || !seen(h.owner)) fail('helicopter ' + h.tag + ' is owned by slot ' + h.owner + ' who is gone'); else if (q.team !== t || q.role !== 'air') fail('helicopter ' + h.tag + ' is owned by a player who is ' + q.role + ' on team ' + q.team); }
      if (h.yieldTo >= 0 && !D.players.get(h.yieldTo)) fail('helicopter ' + h.tag + ' waits for a player who is gone');
      if (h.hp < 0 || h.hp > h.maxHp + 1e-6) fail('helicopter ' + h.tag + ' health ' + h.hp);
      if (h.rockets < 0 || h.rockets > h.M.ROCKETS) fail('helicopter ' + h.tag + ' rockets ' + h.rockets);
    }
    for (const g of D.guns[t]) {
      if (g.crew.length > CONFIG.ROLES.ARTY_CREW) fail('gun ' + g.tag + ' has ' + g.crew.length + ' crew');
      for (const s of g.crew) { const q = D.players.get(s); if (!q || !seen(s)) fail('gun ' + g.tag + ' crew slot ' + s + ' is gone'); else if (q.team !== t || q.role !== 'artillery' || q.crew !== g.k) fail('gun ' + g.tag + ' lists slot ' + s + ' who is ' + q.role + ' / crew ' + q.crew + ' / team ' + q.team); }
      if (g.aimer >= 0) { const q = D.players.get(g.aimer); if (!q || !q.board || q.crew !== g.k || q.team !== t) fail('gun ' + g.tag + ' board is held by slot ' + g.aimer + ' who is not at it'); }
      if (g.loaded.length > CONFIG.ARTY.MAX_LOAD[t]) fail('gun ' + g.tag + ' holds ' + g.loaded.length + ' rounds');
      if (![g.yaw, g.pitch].every(Number.isFinite)) fail('gun ' + g.tag + ' has a non-finite lay');
    }
    for (const m of D.missions[t]) { const q = D.players.get(m.owner); if (!q || q.team !== t) fail('a fire mission of team ' + t + ' belongs to slot ' + m.owner + ' who is gone or changed sides'); }
    if (!(D.game.tickets[t] >= 0) || !Number.isInteger(D.game.tickets[t])) fail('tickets ' + D.game.tickets[t]);
  }
  D.mounts.forEach((m, i) => { if (m.user >= 0) { const q = D.players.get(m.user); if (!q || q.mount !== i || !seen(m.user)) fail('emplaced gun ' + m.n + ' is held by slot ' + m.user + ' who is not on it'); } });
  for (const f of D.flags) if (!(f.prog >= 0 && f.prog <= 1.0001) || ![0, 2, 3].includes(f.owner)) fail('flag ' + f.id + ' state ' + f.prog + ' / ' + f.owner);
  for (const [slot, pr] of D.players) {
    const c = ctls[slot];
    if (!c) { if (pr.ctl) fail('the script still knows slot ' + slot + ' after it emptied'); continue; }
    if (c.gone) { if (pr.ctl || pr.team || pr.aiRole) fail('the script still plays slot ' + slot + ' after its player left (controller left behind, ' + (pr.aiRole ? 'AI ' + pr.aiRole : pr.role) + ')'); continue; }
    // a panel shown with no text: its text went with a HUD reset (round restart, slot change) while the timer that shows it ran on
    if (!c.bot && !loading.has(slot)) {
      const st = hudState.get(slot);
      for (const [panel, text] of [['mv_banner', 'mv_banner_title'], ['mv_toast', 'mv_toast_text'], ['mv_info', 'mv_info_title']])
        if (shows(slot, panel) && !(st && st.has(text + '$'))) fail('player ' + slot + ' sees an empty ' + panel + ' (round ' + stats.rounds + ', t ' + time.toFixed(0) + ')');
    }
    if (pr.heli && pr.heli.seats[pr.seat].slot !== slot) fail('player ' + slot + ' thinks it is in a seat it does not hold');
    if (pr.mount >= 0 && D.mounts[pr.mount].user !== slot) fail('player ' + slot + ' thinks it mans a gun it does not hold');
    if (pr.aiRole) { aiSeen[pr.aiRole] = aiSeen[pr.aiRole] || (pr.aiRole === 'crew' ? D.stats.aiShots > 0 : pr.aiRole === 'pilot' ? !!pr.heli && pr.heli.state === 'flying' : D.stats.aiGunTicks > 0); if (!LOWPOP && !BAL && HUMANS < 0 && SCEN !== 'churn') aiWhenCrowded = true; }
    if (pr.aiRole && !c.bot) fail('a human has an AI role');
    if (pr.carrying && pr.role !== 'artillery') fail('player ' + slot + ' carries a round but is ' + pr.role);
    if (pr.crew >= 0 && pr.role !== 'artillery') fail('player ' + slot + ' has a gun crew seat but is ' + pr.role);
    if (c.spec || c.pawn.hp <= 0) continue;
    const p = c.pawn, seated = !!pr.heli;
    if (!fin(p.pos)) fail('pawn ' + slot + ' non-finite');
    if (seated !== ((p.scale || 1) < 0.5)) fail('pawn ' + slot + (seated ? ' is aboard but not hidden' : ' is shrunk but not aboard (' + (pr.deployed ? 'deployed' : 'lobby') + ')'));
    const parked = seated || pr.mount >= 0 || pr.board || pr.aiRole === 'crew';
    if (!parked && p.mt !== 2) fail('pawn ' + slot + ' is frozen with no seat (' + (pr.deployed ? pr.role : 'lobby') + ')');
    if (p.cam && p.cam.mode !== 0 && !seated && pr.mount < 0) fail('pawn ' + slot + ' is on a seat camera with no seat');
    if (!c.bot && pr.deployed && (seated || pr.mount >= 0 || pr.board) && p.weapons.length !== 1) fail('player ' + slot + ' holds ' + p.weapons.length + ' weapons in a seat');
    if (!c.bot && pr.deployed && !parked && p.weapons.length < 2) fail('player ' + slot + ' on foot holds ' + p.weapons.length + ' weapon(s)');
    if (!c.bot && pr.deployed && !pr.heli && !pr.board && !shows(slot, 'mv_obj')) { if ((pr.deployedAt || 0) + 1 < time) fail('player ' + slot + ' is deployed without the objective bar'); }
    if (!c.bot && !pr.heli && shows(slot, 'mv_fly')) fail('player ' + slot + ' sees the flight instruments on foot');
    if (!c.bot && !pr.board && shows(slot, 'mv_board')) fail('player ' + slot + ' sees the plotting board away from it');
  }
}

// ------------------------------------------------------------------ run
let thinkMs = 0, thinkMax = 0, thinkN = 0, slow = 0;
const DTICK = 1 / 64;
const ticketsStart = CONFIG.CONQUEST.TICKETS;
let ticketsMoved = false, aiSeen = { pilot: false, gunner: false, crew: false }, aiWhenCrowded = false, maxAlt = 0, balDone = null;
const ownTime = {};      // flag id -> seconds held by nobody / T / CT (balance report)
const aiUp = { n: 0, pilot: { 2: 0, 3: 0 }, gunner: { 2: 0, 3: 0 }, crew: { 2: 0, 3: 0 } };
const thinkTimes = [];
for (let step = 0; step < SECONDS * 64 && !balDone; step++) {
  time += DTICK;
  for (let i = later.length - 1; i >= 0; i--) if (later[i].at <= time) { const f = later[i].fn; later.splice(i, 1); f(); }
  if (restartAt > 0 && time >= restartAt) {       // CS2 starts the next round: map entities are re-created, everyone respawns
    restartAt = -1; stats.rounds++;
    makeWorld(); hooks.round();
    for (const c of everyone()) spawn(c);
  }
  fillBots();
  if (SCEN === 'churn' && step > 64 * 20) churn(step);
  if (SCEN === 'reload' && (step === 64 * 100 || step === 64 * 200)) {      // the tools reload the script: new module state, same world and pawns
    const mem = hooks.reloadCfg && hooks.reloadCfg.before ? hooks.reloadCfg.before() : undefined;
    const tk = { ...D.game.tickets }, owners = D.flags.map((f) => f.owner);
    Instance._next = undefined; hooks.reloadCfg = null;
    await loadScript();
    if (!hooks.reloadCfg || !hooks.reloadCfg.after) fail('the reloaded script has no OnScriptReload after()'); else hooks.reloadCfg.after(mem);
    if (D.game.tickets[2] !== tk[2] || D.game.tickets[3] !== tk[3]) fail('tickets not carried over a script reload');
    if (D.flags.map((f) => f.owner).join() !== owners.join()) fail('flag owners not carried over a script reload');
    hit('script reload');
  }
  if (FEATURES || SCEN === 'edge' || SCEN === 'review2') runPieces();
  for (const c of everyone()) {
    const p = c.pawn; p.keys = 0;
    if (c.spec || p.hp <= 0) continue;
    // crude pawn physics: walking pawns fall
    if (p.mt === 2 && p.pos.z > LOBBY_Z + 400) {
      const g = ground(p.pos.x, p.pos.y);
      if (p.pos.z > g + 1) { p.vel.z -= 800 * DTICK; p.pos.z += p.vel.z * DTICK; if (p.pos.z <= g) { const v = -p.vel.z; p.pos.z = g; p.vel.z = 0; if (v > 580) { stats.falls++; p.TakeDamage({ damage: Math.min(300, (v - 580) * 0.4 + 5), damageTypes: DT.FALL }); } } }
      else { p.pos.z = Math.max(p.pos.z, g); p.vel.z = 0; }
      if (p.hp <= 0) continue;
    }
    const pr = P(c);
    if (c.stunt) { let k = c.hold; if (c.q.length) { k |= c.q[0].k; if (--c.q[0].n <= 0) c.q.shift(); } p.keys = k; continue; }
    if (!pr || !pr.deployed) { if (!c.bot && step % 200 === (c.slot * 7) % 200) tap(c, IN.RELOAD); continue; }
    if (c.bot) { if (!pr.heli && pr.mount < 0) walk(c, pr, step); continue; }
    const job = jobOf(c);
    if (BAL) {
      if (job === 'pilot' && pr.role === 'air') drivePilotBal(c, pr, step);
      else if (job === 'crew' && pr.role === 'artillery' && pr.crew >= 0) driveCrewBal(c, pr, step);
      else if (job === 'rider' || pr.heli) driveRiderBal(c, pr, step);
      else if (job === 'mount' || pr.mount >= 0) driveMountBal(c, pr, step);
      else if (job === 'observer' && pr.role === 'infantry') driveObserverBal(c, pr, step);
      else walk(c, pr, step);
    }
    else if (job === 'pilot' && pr.role === 'air') drivePilot(c, pr, step);
    else if (job === 'crew' && pr.role === 'artillery' && pr.crew >= 0) driveCrew(c, pr, step);
    else if (job === 'rider' || pr.heli) driveRider(c, pr, step);
    else if (job === 'mount' || pr.mount >= 0) driveMount(c, pr, step);
    else if (job === 'observer' && pr.role === 'infantry') driveObserver(c, pr, step);
    else walk(c, pr, step);
    if (c.q.length) { p.keys |= c.q[0].k; if (--c.q[0].n <= 0) c.q.shift(); }
  }
  // chat: roles, kits, spawn choices, help, bots
  if (step === 64 * 2) for (const c of everyone()) { if (c.bot) continue; const j = jobOf(c); if (j === 'pilot') say(c, '!air'); if (j === 'crew') say(c, '!artillery'); if (j === 'walker' && !BAL) { if (c.slot % 8 !== 7) say(c, '!infantry'); say(c, ['!rifle', '!mg', '!rifle', '!spawn b'][c.slot % 4]); } if (j === 'walker' && BAL && c.slot % 4 < 3) say(c, c.slot % 4 === 2 ? '!at' : '!mg'); }
  if (step === 64 * 4 && !BAL) { const c = everyone().find((x) => !x.bot); if (c) { say(c, '!roles'); say(c, '/uniform'); say(c, '!spawn zz'); say(c, 'hello there'); } }
  if (LOWPOP && step === 64 * 5) { say(ctls[0], '!bots 14'); fillBots(); }
  if (step > 0 && step % (64 * 150) === 0) for (const c of everyone()) { if (!c.bot && !c.stunt && ['pilot', 'crew'].includes(jobOf(c)) && P(c) && P(c).role === 'infantry') say(c, jobOf(c) === 'pilot' ? '!air' : '!artillery'); }
  // low population, second half: the AI holds every helicopter, then a human asks for one and must get it
  if (LOWPOP && step === Math.floor(SECONDS * 32)) { CONFIG.AI.PILOTS = 3; CONFIG.AI.MAX_ROLE_SHARE = 1; }
  if (LOWPOP && step === Math.floor(SECONDS * 32) + 64 * 40) {
    for (const team of [2, 3]) {
      const c = humans(team)[1]; if (!c) continue;
      const before = D.helis[team].filter((h) => h.owner >= 0 && ctls[h.owner].bot).length;
      if (c.pawn.hp > 0 && P(c) && P(c).deployed) putAt(c, baseSpot(team));      // roles change at the base
      say(c, '!air');
      expect(110, 'human ' + c.slot + ' asked for a helicopter the AI held (' + before + ' AI pilots) and owns one', () => { const ok = D.helis[team].some((h) => h.owner === c.slot); if (ok) stats.yields++; return ok || before === 0; });
    }
  }
  // a human takes a gun seat an AI gunner holds
  if (LOWPOP && step % (64 * 30) === 64 * 25) {
    const m = D.mounts.find((x) => x.user >= 0 && ctls[x.user].bot);
    const c = m && everyone().find((x) => !x.bot && x.pawn.hp > 0 && (m.team === x.team) && P(x) && P(x).deployed && !P(x).heli && P(x).mount < 0 && !P(x).board && jobOf(x) !== 'pilot');
    if (m && c) { putAt(c, m.seat.pos); press(c, IN.USE); const botSlot = m.user;
      expect(1, 'human ' + c.slot + ' took the emplaced gun from AI gunner ' + botSlot, () => { const ok = m.user === c.slot && P(ctls[botSlot]).aiRole === ''; if (ok) stats.yields++; return ok; }); }
  }
  if (BAL) { if (step % FIGHT.EVERY === 0) fight(); }
  else {
    // rifle fire: random kills between deployed enemies, bullets on flying helicopters
    if (step % 83 === 0) {
      const all = everyone(), a = all[Math.floor(Math.random() * all.length)], v = all[Math.floor(Math.random() * all.length)];
      const pa = P(a), pv = P(v);
      if (a.team !== v.team && !a.spec && !v.spec && !a.stunt && !v.stunt && v.pawn.hp > 0 && a.pawn.hp > 0 && pa && pv && pa.deployed && pv.deployed && !pa.heli && d2(a.pawn.pos, v.pawn.pos) < 4500)
        v.pawn.TakeDamage({ damage: 150, damageTypes: DT.BULLET, attacker: a.pawn, weapon: new Weapon(pa.kit === 'mg' ? MGW[a.team] : RIFLEW[a.team], a.pawn) });
    }
    if (step % 30 === 0 && hooks.bullet) {
      const flying = [2, 3].flatMap((t) => D.helis[t]).filter((h) => h.state === 'flying' && h.ent);
      if (flying.length) {
        const h = flying[Math.floor(Math.random() * flying.length)], shooters = everyone().filter((c) => c.team !== h.team && !c.spec && c.pawn.hp > 0 && P(c) && P(c).deployed);
        if (shooters.length) { const s = shooters[Math.floor(Math.random() * shooters.length)]; hooks.bullet({ weapon: new Weapon(Math.random() < 0.5 ? 'weapon_m249' : 'weapon_ak47', s.pawn), position: { ...h.pos }, hitEntity: world.get(h.name) }); }
      }
    }
    // a bot thrown out of the playable band must be brought back by the leash
    if (step % (64 * 45) === 64 * 20) {
      const b = everyone().find((c) => c.bot && c.pawn.hp > 0 && P(c) && P(c).deployed && !P(c).aiRole && !P(c).heli && P(c).mount < 0);
      if (b) { b.pawn.pos = { x: L.map.x + 300, y: 0, z: 40 }; b.drv.goal = { x: L.map.x + 300, y: 0 }; const pawn = b.pawn;
        expect(3, 'bot ' + b.slot + ' outside the band was re-deployed', () => { const ok = ctls[b.slot] !== b || b.pawn !== pawn || Math.abs(b.pawn.pos.x) < L.map.x; if (ok) stats.leashOk++; b.drv.goal = null; return ok; }); }
    }
    // disconnect and a slot changing hands
    if (step === 64 * 100 && ctls.length > 8 && !SCEN) { const c = ctls[N - 1]; hooks.disc({ playerSlot: c.slot }); const n = new Ctl(c.slot, c.team, c.bot); ctls[c.slot] = n; c.pawn.valid = false; spawn(n); }
  }
  if (Instance._next !== undefined && Instance._next <= time) {
    Instance._next = undefined;
    const t0 = performance.now(); Instance._think(); const ms = performance.now() - t0;
    thinkMs += ms; thinkN++; if (ms > thinkMax) thinkMax = ms; if (ms > 8) slow++;
    if (step > 640) thinkTimes.push(ms);
  } else if (step > 4) fail('the think loop stopped at ' + time.toFixed(2));
  for (let i = checks.length - 1; i >= 0; i--) if (checks[i].at <= time) { const k = checks[i]; checks.splice(i, 1); let ok = false; try { ok = k.fn(); } catch (e) { ok = false; } if (!ok) fail('expected: ' + k.what + ' (t ' + time.toFixed(0) + ')'); }
  if (step % 16 === 0) {
    if (D.game.tickets[2] !== ticketsStart || D.game.tickets[3] !== ticketsStart) ticketsMoved = true;
    invariants();
  }
  if (step % 64 === 0) {
    aiUp.n++;
    for (const f of D.flags) { const o = ownTime[f.id] || (ownTime[f.id] = { 0: 0, 2: 0, 3: 0 }); o[f.owner]++; }
    for (const t of [2, 3]) {
      const bots = [...D.players.values()].filter((q) => q.team === t && q.bot);
      if (bots.some((q) => q.aiRole === 'pilot' && q.heli && q.heli.state === 'flying')) aiUp.pilot[t]++;
      if (bots.some((q) => q.aiRole === 'gunner' && (q.heli || q.mount >= 0))) aiUp.gunner[t]++;
      if (bots.some((q) => q.aiRole === 'crew' && q.deployed)) aiUp.crew[t]++;
    }
  }
  if (BAL && D.game.over) balDone = D.stats.results[D.stats.results.length - 1];
}
try { fs.unlinkSync(dest); } catch (e) {}

// ------------------------------------------------------------------ verdict
const S = D.stats;
const errs = stats.msgs.filter((m) => m.includes('error in') || m.includes('missing entity') || m.includes('failed'));
for (const e of errs.slice(0, 6)) fail('script log: ' + e.slice(0, 600));
for (const n of lookedUpMissing) if (!OPTIONAL.some((r) => r.test(n))) fail('looked up a missing entity: ' + n);
thinkTimes.sort((a, b) => a - b);
const pct = (q) => (thinkTimes.length ? thinkTimes[Math.min(thinkTimes.length - 1, Math.floor(thinkTimes.length * q))] : 0);
const perf = { avg: +(thinkMs / Math.max(1, thinkN)).toFixed(4), p50: +pct(0.5).toFixed(4), p99: +pct(0.99).toFixed(3), p999: +pct(0.999).toFixed(3), max: +thinkMax.toFixed(2), over8ms: slow, ticks: thinkN,
               traces: +(stats.traces / Math.max(1, thinkN)).toFixed(1), hud: +((stats.hud + stats.vars) / Math.max(1, thinkN)).toFixed(1), inputs: +(stats.inputs / Math.max(1, thinkN)).toFixed(1), moves: +((stats.moves + stats.teleports) / Math.max(1, thinkN)).toFixed(1) };
if (BAL) {
  const frac = (o) => ({ t: +(o[2] / Math.max(1, aiUp.n)).toFixed(2), ct: +(o[3] / Math.max(1, aiUp.n)).toFixed(2) });
  const lives = S.heliLives.slice();
  const out = { seed: +(opt.seed || 7), players: ctls.length, humans: everyone().filter((c) => !c.bot).length, ended: !!balDone, secs: balDone ? balDone.secs : Math.round(time), winner: balDone ? balDone.winner : 0,
                tickets: { t: D.game.tickets[2], ct: D.game.tickets[3] }, flagChanges: Object.fromEntries(D.flags.map((f) => [f.id, f.changes])), captures: S.captures,
                killsBy: S.killsBy, killsOn: S.killsOn, deaths: S.deaths, bleedOn: { t: S.bleedOn[2], ct: S.bleedOn[3] }, deathsOn: { t: Object.values(S.killsOn[2] || {}).reduce((a, b) => a + b, 0), ct: Object.values(S.killsOn[3] || {}).reduce((a, b) => a + b, 0) }, heliLives: lives, heliLost: S.heliLost, heliLostBy: S.heliLostBy, heliDmgBy: S.heliDmgBy, flights: S.flights,
                heliLostTeam: { t: S.heliLostTeam[2], ct: S.heliLostTeam[3] }, shells: S.shells, shellHits: S.shellHits, missions: S.missions, missionShells: S.missionShells, missionHits: S.missionHits,
                gunsDisabled: S.gunsDisabled, fired: S.fired, rockets: S.rockets, gunShots: S.gunShots, landings: S.landings, own: Object.fromEntries(Object.entries(ownTime).map(([k, o]) => [k, { t: +(o[2] / Math.max(1, aiUp.n)).toFixed(2), ct: +(o[3] / Math.max(1, aiUp.n)).toFixed(2) }])), ai: { pilot: frac(aiUp.pilot), gunner: frac(aiUp.gunner), crew: frac(aiUp.crew) }, perf, errors: errs.length + fails.length, fails: fails.slice(0, 5) };
  console.log((JSONONLY ? '' : 'BALANCE ') + JSON.stringify(out));
  process.exit(fails.length ? 1 : 0);
}
const FULL = !SCEN && SECONDS >= 600;
if ((FULL || SCEN === 'restart') && stats.terminate < 1) fail('no round ended (GameRules.TerminateRound never called)');
if (FULL && !process.env.MOCK_NORESTART && stats.rounds < 1) fail('no new round started');
if (!ticketsMoved) fail('tickets never moved');
if (S.flights < 1 || !(maxAlt > 150)) fail('no helicopter flew (flights ' + S.flights + ', max height ' + maxAlt.toFixed(0) + ')');
if (FULL) {
  if (S.captures < 1) fail('no flag was captured');
  if (S.landings < 1) fail('no helicopter landed');
  if (S.heliLost < 1) fail('no helicopter was shot down');
  if (S.shells < 1) fail('no shell landed');
  if (S.rockets < 1) fail('no rocket was fired');
  if (S.missions < 1) fail('no fire mission was called');
  if (S.leash < 1) fail('the bot leash never acted');
}
if (stats.panelIds.size > 1024) fail('more than 1024 HUD panel ids');
if (LOWPOP) { for (const k of ['pilot', 'gunner', 'crew']) if (!aiSeen[k]) fail('low population: the AI ' + k + ' never became active'); if (S.aiLandings < 1) fail('low population: the AI pilot never came back to its pad'); if (stats.yields < 1) fail('low population: no AI seat was given to a human'); }
else if (aiWhenCrowded) fail('AI roles were handed out although both teams had enough humans');
if (SCEN === 'restart') { if (stats.rounds < 2) fail('restart scenario: fewer than two CS2 restarts (' + stats.rounds + ')'); if (!stats.msgs.some((m) => m.includes('restarts its own'))) fail('restart scenario: the script never restarted its own round'); if (S.rounds < 4) fail('restart scenario: only ' + S.rounds + ' rounds'); }
if (SCEN === 'churn') { const n = Object.values(stats.churn).reduce((a, b) => a + b, 0); if (n < 20) fail('churn scenario: only ' + n + ' events'); for (const k of ['pilot-air', 'aboard', 'crew']) if (!Object.keys(stats.churn).some((x) => x.endsWith(':' + k))) fail('churn scenario: nobody left from "' + k + '"'); }
if (SCEN === 'reload' && (cov['script reload'] || 0) < 2) fail('reload scenario: the script was not reloaded twice');
if (!SYNTH) for (const [id, c] of contract) if (xmlIds && !c.added && !xmlIds.has(id)) fail('HUD xml lacks contract panel ' + id);
if (HUDNEW) for (const id of ADDED_IDS) if (SCEN === 'edge' && !opt.piece && !stats.panelIds.has(id)) fail('HUD addition ' + id + ' was never used although the HUD lists it');
const unusedIds = [...contract].filter(([, c]) => !c.added && !c.textUsed && !c.used.size).map(([id]) => id);
const roles = {}; for (const p of D.players.values()) { const k = p.team + ':' + (p.aiRole ? 'ai-' + p.aiRole : p.role); roles[k] = (roles[k] || 0) + 1; }
console.log('mg_monsoon mock: ' + everyone().length + ' players (' + everyone().filter((c) => !c.bot).length + ' human), ' + SECONDS + ' s' + (SCEN ? ', scenario ' + SCEN : '') + (HUDNEW ? ', HUD additions on' : '') + ', entities ' + (SYNTH ? 'synthesised from layout.json' : 'out/entities.json') + ', script ' + built.lines + ' lines');
console.log('roles', JSON.stringify(roles));
console.log(JSON.stringify({ script: { ...S, heliLives: S.heliLives.length, results: S.results.length }, engine: { hud: stats.hud, vars: stats.vars, panelIds: stats.panelIds.size, fires: stats.fires, dmg: stats.dmg, kills: stats.kills, blocked: stats.blocked, fallBlocked: stats.fallBlocked, falls: stats.falls,
  teleports: stats.teleports, moves: stats.moves, cam: stats.cam, traces: stats.traces, rounds: stats.rounds, terminate: stats.terminate, yields: stats.yields, leashOk: stats.leashOk, kitUses: stats.kit, zeus: stats.gunfire,
  cmds: stats.cmds, setModel: stats.setmodel, maxAlt: Math.round(maxAlt), tickets: D.game.tickets, flags: D.flags.map((f) => f.id + ':' + f.owner).join(' '), churn: stats.churn } }));
if (unusedIds.length) console.log('HUD contract ids never used in this run: ' + unusedIds.join(' '));
// ---- coverage: feature -> times exercised. Set pieces fill cov; the rest comes from the script's own counters.
if (FEATURES || SCEN === 'edge' || SCEN === 'review2') {
  const used = (id) => { const c = contract.get(id); return c && (c.textUsed || c.used.size) ? 1 : 0; };
  const table = FEATURES ? {
    ...cov,

    'pad repair': S.padRepairs, 'pad re-arm (rocket pairs)': S.padRearms, 'landing: soft': S.landings,
    'smoke shells': S.smokes, 'belt changes': S.beltReloads, 'board: second flash marker': used('mv_fl1'),
    'event feed lines': S.feed, 'per-minute perf line': S.perfLines,
    'kills by artillery': S.killsBy.arty || 0,
    'helicopter lost with riders (crash kills)': Object.entries(S.killsBy).filter(([k]) => !['rifle', 'mg', 'other'].includes(k)).reduce((a, [, v]) => a + v, 0),
  } : cov;
  const need0 = !opt.piece && (SECONDS >= 600 || SCEN === 'edge' || SCEN === 'review2');
  console.log('coverage (feature -> times exercised):');
  for (const [k, v] of Object.entries(table)) { console.log('  ' + String(Math.round(v * 10) / 10).padStart(6) + '  ' + k); if (need0 && !(v > 0)) fail('coverage: "' + k + '" was never exercised'); }
  for (const pc of pieces) if (!pc.done && need0) fail('set piece "' + pc.name + '" did not finish (waiting for: ' + (pc.what || 'its start') + ')');
}
console.log('script time: ' + perf.avg.toFixed(3) + ' ms/tick avg, p50 ' + perf.p50.toFixed(3) + ', p99 ' + perf.p99 + ', p99.9 ' + perf.p999 + ', max ' + perf.max + ' ms over ' + thinkN + ' ticks, ' + slow + ' over 8 ms; per tick: ' +
  perf.traces + ' traces, ' + perf.hud + ' HUD calls, ' + perf.inputs + ' key reads, ' + perf.moves + ' moves (the stand-in engine\'s own time is included)');
if (opt.perf) { const lim = opt.perf.split(',').map(Number); if (perf.avg > lim[0]) fail('script time avg ' + perf.avg + ' ms over the ' + lim[0] + ' ms limit'); if (perf.max > lim[1]) fail('script time max ' + perf.max + ' ms over the ' + lim[1] + ' ms limit'); }
if (fails.length) { console.log('FAIL (' + fails.length + ')'); for (const f of fails) console.log('  - ' + f); process.exit(1); }
console.log('PASS');
