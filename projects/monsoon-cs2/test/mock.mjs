// Runs the built mg_monsoon script (tools/build_script.mjs) against a stand-in cs_script engine: only the CURRENT API names exist
// (Entities.*, Console.*, GameRules.*, ent.FireInput; any other Instance.* name throws). The world is out/entities.json when the map
// generator has written it, otherwise every CONTRACT entity is synthesised from out/layout.json, so this runs before the map exists.
// Humans are driven through every role (pilot flying / landing / boarding riders, gunners, emplaced guns, battery crews, observers,
// kit changes, captures); bots walk at flags, and in low population the script's AI roles must come alive.
// Fails on: a script error, a non-finite or out-of-world position, an input fired at a missing entity or one its class does not
// have, a HUD id / class outside docs/SCRIPT.md "HUD contract", no round end, tickets not moving, no capture, no flight, no
// helicopter shot down, no shell landing, and (low population) no AI pilot / gunner / crew activity.
// usage: node test/mock.mjs [players=32] [seconds=600]      (players < 16: all human, bots join through bot_quota like a real server)
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { build } from '../tools/build_script.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const N = +(process.argv[2] || 32), SECONDS = +(process.argv[3] || 600);
const LOWPOP = N < 16;
let seed = 7; Math.random = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
const L = JSON.parse(fs.readFileSync(path.join(root, 'out/layout.json'), 'utf8'));
const PARK_Z = L.map.park_z, LOBBY_Z = L.map.lobby_z;
const fails = [];
const fail = (m) => { if (fails.length < 40 && !fails.includes(m)) fails.push(m); };
let time = 0;
const stats = { hud: 0, vars: 0, fires: {}, dmg: 0, kills: 0, teleports: 0, moves: 0, cam: 0, traces: 0, blocked: 0, msgs: [], cmds: {}, rounds: 0, terminate: 0, ropes: 0,
                fallBlocked: 0, yields: 0, leashOk: 0, kit: 0, gunfire: 0, panelIds: new Set(), falls: 0 };

// ------------------------------------------------------------------ HUD contract (docs/SCRIPT.md)
const contract = new Map();
{
  const md = fs.readFileSync(path.join(root, 'docs/SCRIPT.md'), 'utf8');
  const m = /HUD-CONTRACT-BEGIN[^\n]*\n([\s\S]*?)<!-- HUD-CONTRACT-END/.exec(md);
  if (!m) throw new Error('docs/SCRIPT.md: HUD contract table not found');
  for (const line of m[1].split('\n')) {
    const c = line.split('|').map((s) => s.trim());
    if (c.length < 5 || !c[1].startsWith('mv_')) continue;
    const e = contract.get(c[1]) || { text: false, classes: new Set(), used: new Set(), textUsed: false };
    if (c[2] === 'text') e.text = true;
    else for (const part of c[3].split(',').map((s) => s.trim()).filter(Boolean)) {
      const r = /^([a-z_]+?)(\d+)\.\.\1(\d+)$/.exec(part);
      if (r) for (let i = +r[2]; i <= +r[3]; i++) e.classes.add(r[1] + i); else e.classes.add(part);
    }
    contract.set(c[1], e);
  }
}
const xmlPath = path.join(root, 'out/addon/panorama/layout/custom_game/mg_monsoon.xml'), cssPath = path.join(root, 'out/addon/panorama/styles/custom_game/mg_monsoon.css');
const xmlIds = fs.existsSync(xmlPath) ? new Set([...fs.readFileSync(xmlPath, 'utf8').matchAll(/id="([^"]+)"/g)].map((m) => m[1])) : null;
const css = fs.existsSync(cssPath) ? fs.readFileSync(cssPath, 'utf8') : null;

// ------------------------------------------------------------------ the world: a height field from the layout
function ground(x, y) {
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
  use() { if (!this.valid) throw new Error('method on an invalid entity ' + this.name); }
  SetModelScale(v) { if (!Number.isFinite(v) || v <= 0) throw new Error('bad scale ' + v); this.scale = v; } GetModelName() { return this.model; }
  Teleport(o) { this.use(); if (o.position) { checkPos(o.position, 'Teleport ' + (this.name || this.cls)); this.pos = { ...o.position }; } if (o.angles) { checkAng(o.angles, this.name); this.ang = { ...o.angles }; } if (o.velocity) { if (!fin(o.velocity)) throw new Error('bad velocity'); this.vel = { ...o.velocity }; } stats.teleports++; }
  Move(o) { this.use(); if (o.position) { checkPos(o.position, 'Move ' + (this.name || this.cls)); this.pos = { ...o.position }; } if (o.angles) { checkAng(o.angles, this.name); this.ang = { ...o.angles }; } if (o.velocity) { if (!fin(o.velocity)) throw new Error('bad velocity'); this.vel = { ...o.velocity }; } stats.moves++; }
  SetParent(p) { this.parent = p; } GetParent() { return this.parent; }
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
class Hud extends Ent {
  chk(panel, cls) {
    stats.panelIds.add(panel);
    const c = contract.get(panel); if (!c) throw new Error('HUD panel not in the contract: ' + panel);
    if (xmlIds && !xmlIds.has(panel)) throw new Error('HUD xml lacks panel ' + panel);
    if (cls === undefined) { if (!c.text) throw new Error('HUD panel ' + panel + ' is not a text panel in the contract'); c.textUsed = true; return; }
    if (!c.classes.has(cls)) throw new Error('HUD class not in the contract: ' + panel + ' .' + cls);
    if (css && !css.includes('.' + cls)) throw new Error('HUD css lacks class ' + cls);
    c.used.add(cls);
  }
  SetHasClassForPlayer(slot, panel, cls, on) { stats.hud++; if (typeof on !== 'boolean') throw new Error('class flag not boolean'); if (ctls[slot] && ctls[slot].bot) throw new Error('HUD call for a bot'); this.chk(panel, cls); }
  SetDialogVariableStringForPlayer(slot, panel, n, v) { stats.vars++; if (n !== 'v' || typeof v !== 'string') throw new Error('bad dialog variable'); if (/undefined|NaN|\[object/.test(v)) throw new Error('bad HUD text for ' + panel + ': ' + v); this.chk(panel); }
  ResetForPlayer() {}
}
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
  IsInputPressed(b) { if (b & (b - 1)) throw new Error('masked IsInputPressed'); return (this.keys & b) !== 0; }
  SetEyeAngles(a) { checkAng(a, 'eye'); this.eye = { ...a }; } GetEyeAngles() { return { ...this.eye }; } GetEyePosition() { return { x: this.pos.x, y: this.pos.y, z: this.pos.z + 64 }; }
  SetMoveType(m) { if (![0, 2].includes(m)) throw new Error('bad move type ' + m); this.mt = m; } GetMoveType() { return this.mt; }
  GetGroundEntity() { return this.pos.z <= ground(this.pos.x, this.pos.y) + 2 || this.pos.z < LOBBY_Z + 100 ? worldEnt : undefined; }
  SetModel(m) { if (![...world.values()].some((e) => e.model === m) && !m.startsWith('agents/')) throw new Error('SetModel to a model no cache prop holds: ' + m); this.model = m; stats.setmodel = (stats.setmodel || 0) + 1; }
  GetCustomCamera() { return this.cam || (this.cam = new Cam(this)); }
  DestroyWeapons() { this.weapons = []; this.active = null; } DestroyWeapon(w) { this.weapons = this.weapons.filter((x) => x !== w); if (this.active === w) this.active = this.weapons[0] || null; }
  GiveNamedItem(n, dep) { if (!WEAPONS.has(n)) throw new Error('unknown weapon ' + n); if (this.weapons.find((w) => w.n === n)) throw new Error('duplicate weapon ' + n); const w = new Weapon(n, this); this.weapons.push(w); if (dep || !this.active) this.active = w; }
  FindWeapon(n) { return this.weapons.find((w) => w.n === n); } GetActiveWeapon() { return this.active || undefined; }
  Reset() { spawn(this.ctl, true); }
  TakeDamage(d) {
    if (!(d.damage > 0) || !Number.isFinite(d.damage)) throw new Error('bad damage ' + d.damage);
    if (this.hp <= 0) return 0;
    let dmg = d.damage;
    if (hooks.mod) { const r = hooks.mod({ player: this, damage: dmg, damageTypes: d.damageTypes || 0, damageFlags: d.damageFlags || 0, hitGroup: 0, attacker: d.attacker, inflictor: d.inflictor });
      if (r && r.abort) { stats.blocked++; if ((d.damageTypes || 0) & DT.FALL) stats.fallBlocked++; return 0; } if (r && r.damage !== undefined) dmg = r.damage; }
    stats.dmg++;
    hooks.damage && hooks.damage({ player: this, damage: dmg, damageTypes: d.damageTypes || 0, damageFlags: d.damageFlags || 0, hitGroup: 0, attacker: d.attacker, inflictor: d.inflictor });
    this.hp -= Math.round(dmg); if ((d.damageFlags || 0) & DF.FORCE_DEATH) this.hp = 0;
    if (this.hp <= 0) { this.hp = 0; die(this, d.attacker); }
    return dmg;
  }
}
class Ctl extends Ent {
  constructor(slot, team, bot) { super('', 'cs_player_controller', { x: 0, y: 0, z: 0 }); this.slot = slot; this.team = team; this.bot = bot; this.pawn = new Pawn(this); this.drv = {}; }
  GetPlayerSlot() { return this.slot; } GetPlayerPawn() { return this.pawn; } IsBot() { return this.bot; } GetPlayerName() { return (this.bot ? 'bot' : 'p') + this.slot; } GetTeamNumber() { return this.team; }
}
const worldEnt = new Ent('world', 'worldent', { x: 0, y: 0, z: 0 });
const ctls = [];
function spawn(c, samePawn) {
  const sp = lobby.filter((e) => (e.cls.endsWith('terrorist') && !e.cls.includes('counter')) === (c.team === 2));
  const e = sp[c.slot % sp.length];
  if (!samePawn) { c.pawn.valid = false; c.pawn = new Pawn(c); } else { c.pawn.hp = 100; c.pawn.mt = 2; }
  c.pawn.pos = { x: e.origin[0], y: e.origin[1], z: e.origin[2] }; c.pawn.vel = { x: 0, y: 0, z: 0 };
  c.drv = { born: time };
  hooks.reset && hooks.reset({ player: c.pawn });
}
const later = [];
function at(dt, fn) { later.push({ at: time + dt, fn }); }
function die(pawn, attacker) { stats.kills++; hooks.kill && hooks.kill({ player: pawn, attacker }); const c = pawn.ctl; at(2, () => { if (ctls[c.slot] === c) spawn(c); }); }
function addPlayer(bot) { const s = ctls.length; const c = new Ctl(s, s % 2 ? 3 : 2, bot); ctls.push(c); spawn(c); return c; }

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
    for (const c of ctls) {
      const p = c.pawn; if (p.hp <= 0 || p.pos.z < -1000 || ign.includes(p) || (p.scale || 1) < 0.5) continue;
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
  OnPlayerDamage: (f) => { hooks.damage = f; }, OnGunFire: (f) => { hooks.gunfire = f; },
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
    if (/[;"\n]/.test(c)) throw new Error('unsafe characters in a server command: ' + c);
    if (w === 'bot_quota') quota = +String(c).split(' ')[1]; if (w === 'bot_quota_mode') quotaMode = String(c).split(' ')[1];
    if (w === 'bot_kick') for (const b of ctls) if (b && b.bot && N < 16) { /* kicked bots keep their slots in this mock */ }
  },
});
let restartAt = -1;
const GameRules = strict('GameRules', {
  TerminateRound: (reason, delay) => { if (![2, 8, 9].includes(reason)) throw new Error('bad round end reason ' + reason); stats.terminate++; if (!process.env.MOCK_NORESTART) restartAt = time + (delay || 0) + 4; },
  AddTeamScore: (team, n) => { if (![2, 3].includes(team) || n !== 1) throw new Error('bad AddTeamScore'); stats.score = (stats.score || 0) + 1; },
  SetRoundRemainingTime: (t) => { if (!Number.isFinite(t)) throw new Error('bad round time'); }, GetRoundRemainingTime: () => 600, IsWarmupPeriod: () => false,
});
const dest = path.join(root, 'test/_run.mjs');
const built = build(dest);
const src = fs.readFileSync(dest, 'utf8').replace(/import \{([^}]*)\} from "cs_script\/point_script";/, 'const {$1} = globalThis.__cs;');
fs.writeFileSync(dest, src);
globalThis.__cs = { Instance, Entities, Console, GameRules, CSInputs: IN, CSMoveType: { NONE: 0, WALK: 2 }, CSDamageTypes: DT, CSDamageFlags: DF,
                    CSRoundEndReason: { DRAW: 2, CTS_WIN: 8, TERRORISTS_WIN: 9 }, CustomCameraMode: { DISABLED: 0, CONTROLLED: 1, CONTROLLED_POSITION: 2, FOLLOW_POSITION: 3 } };
await import(pathToFileURL(dest).href);
const D = globalThis.__mvDebug, CONFIG = D.CONFIG;
CONFIG.CONQUEST.TICKETS = +(process.env.MOCK_TICKETS || 150);        // rounds must end inside the run
CONFIG.CONQUEST.CAPTURE_SECONDS = 8;
if (process.env.MOCK_ROUND) CONFIG.CONQUEST.ROUND_SECONDS = +process.env.MOCK_ROUND;

for (let s = 0; s < N; s++) addPlayer(LOWPOP ? false : s % 3 === 2);
hooks.activate();
hooks.round && hooks.round();
function fillBots() { if (quotaMode !== 'fill') return; while (ctls.length < Math.min(quota, 40)) addPlayer(true); }
fillBots();

// ------------------------------------------------------------------ drivers: press keys like players would
const P = (c) => D.players.get(c.slot);
const tg = (c) => (c.team === 2 ? 't' : 'ct');
const humans = (team) => ctls.filter((c) => !c.bot && c.team === team);
const jobOf = (c) => { const i = humans(c.team).indexOf(c); return LOWPOP ? ['pilot', 'observer'][i] || 'walker' : ['pilot', 'crew', 'crew', 'rider', 'mount', 'observer', 'pilot'][i] || 'walker'; };
const yawTo = (a, b) => Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI;
const d2 = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const wrap = (x) => ((x + 180) % 360 + 360) % 360 - 180;
function tap(c, key) { c.pawn.keys |= key; }
function putAt(c, pos, dz) { c.pawn.pos = { x: pos.x, y: pos.y, z: (pos.z !== undefined ? pos.z : ground(pos.x, pos.y)) + (dz || 0) }; c.pawn.vel = { x: 0, y: 0, z: 0 }; }
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
  if (s.kind === 'gunner') { p.eye = { pitch: 18 + 10 * Math.sin(time), yaw: h.yaw + h.M.GUN.yaw + 40 * Math.sin(time * 0.6), roll: 0 }; p.keys |= IN.ATTACK; }
  if (time - (dv.boardAt || time) > 22 && !h.landed && h.alt < 430 && h.speed < 280) { tap(c, IN.USE); dv.leftAt = time; dv.roped = true; }
  else if (time - (dv.boardAt || time) > 45) { tap(c, IN.USE); dv.leftAt = time; }
  if (step % 640 === 320) hooks.chat({ player: c, text: '!swap', team: c.team });
}
function driveMount(c, pr, step) {
  const p = c.pawn, dv = c.drv;
  if (pr.mount < 0) {
    if (step % 128 !== 0 || time - (dv.leftAt || -99) < 6) return;
    const list = D.mounts.filter((m) => (m.team === c.team || m.team === 0) && (m.user < 0 || ctls[m.user].bot));
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
function driveObserver(c, pr, step) {
  const p = c.pawn, dv = c.drv;
  if (dv.at === undefined) { dv.at = time; hooks.chat({ player: c, text: '!at', team: c.team }); }
  const enemyBase = L[c.team === 2 ? 'ct' : 't'].centre, tgt = D.flags[Math.floor(time / 30) % D.flags.length].pos;
  const ph = time % 12;
  if (ph < 4) { const d = Math.max(450, d2(p.pos, tgt)); p.eye = { pitch: Math.atan2(p.pos.z + 64 - tgt.z, d) * 180 / Math.PI, yaw: yawTo(p.pos, tgt), roll: 0 }; if (ph > 1) p.keys |= IN.USE; }
  else if (ph > 6 && ph < 6.05 && hooks.gunfire) {      // the Zeus trigger: at a flying enemy helicopter if there is one
    const eh = D.helis[c.team === 2 ? 3 : 2].find((h) => h.state === 'flying');
    const aim = eh ? { x: eh.pos.x, y: eh.pos.y, z: eh.pos.z + 80 } : { x: enemyBase[0], y: enemyBase[1], z: 300 };
    const d = d2(p.pos, aim);
    p.eye = { pitch: -Math.atan2(aim.z - p.pos.z - 64, d) * 180 / Math.PI, yaw: yawTo(p.pos, aim), roll: 0 };
    const w = p.FindWeapon('weapon_taser'); if (w) { p.active = w; hooks.gunfire({ weapon: w }); stats.gunfire++; }
  }
  if (step % 1280 === 640) hooks.chat({ player: c, text: '!pos', team: c.team });
}
function walk(c, pr, step) {      // what CS2's own bot brain / a walking human does: go to a flag that is not ours
  const p = c.pawn;
  if (p.mt !== 2 || p.pos.z < LOBBY_Z + 400) return;
  const dv = c.drv;
  if (c.bot && c.slot % 7 === 3) return;                           // an idle bot: the leash must move it
  if (!dv.goal || step % 256 === (c.slot * 5) % 256) {
    const list = D.flags.filter((f) => f.owner !== c.team);
    const f = (list.length ? list : D.flags).slice().sort((a, b) => d2(p.pos, a.pos) - d2(p.pos, b.pos))[c.slot % 2 ? 0 : Math.min(1, (list.length || D.flags.length) - 1)];
    dv.goal = { x: f.pos.x + ((c.slot * 37) % 300) - 150, y: f.pos.y + ((c.slot * 53) % 300) - 150 };
  }
  const d = d2(p.pos, dv.goal);
  if (d > 30) { const k = Math.min(1, 250 / 64 / d); p.pos.x += (dv.goal.x - p.pos.x) * k; p.pos.y += (dv.goal.y - p.pos.y) * k; if (p.pos.z <= ground(p.pos.x, p.pos.y) + 30 || !pr.ropeUntil) p.pos.z = ground(p.pos.x, p.pos.y); }
  if (!c.bot && step % 448 === (c.slot * 11) % 448) {              // a kit change at the nearest station now and then
    const k = [...world.values()].filter((e) => e.name.startsWith('mv_kit_')).sort((a, b) => d2(p.pos, a.pos) - d2(p.pos, b.pos))[0];
    if (k && d2(p.pos, k.pos) < 500) { putAt(c, k.pos); tap(c, IN.USE); stats.kit++; }
  }
}
// checks that run on a schedule
const checks = [];
function expect(dt, what, fn) { checks.push({ at: time + dt, what, fn }); }

// ------------------------------------------------------------------ run
let thinkMs = 0, thinkMax = 0, thinkN = 0;
const DTICK = 1 / 64;
const ticketsStart = CONFIG.CONQUEST.TICKETS;
let ticketsMoved = false, aiSeen = { pilot: false, gunner: false, crew: false }, aiWhenCrowded = false, maxAlt = 0;
for (let step = 0; step < SECONDS * 64; step++) {
  time += DTICK;
  for (let i = later.length - 1; i >= 0; i--) if (later[i].at <= time) { const f = later[i].fn; later.splice(i, 1); f(); }
  if (restartAt > 0 && time >= restartAt) {       // CS2 starts the next round: map entities are re-created, everyone respawns
    restartAt = -1; stats.rounds++;
    makeWorld(); hooks.round();
    for (const c of ctls) spawn(c);
  }
  fillBots();
  for (const c of ctls) {
    const p = c.pawn; p.keys = 0;
    if (p.hp <= 0) continue;
    // crude pawn physics: walking pawns fall
    if (p.mt === 2 && p.pos.z > LOBBY_Z + 400) {
      const g = ground(p.pos.x, p.pos.y);
      if (p.pos.z > g + 1) { p.vel.z -= 800 * DTICK; p.pos.z += p.vel.z * DTICK; if (p.pos.z <= g) { const v = -p.vel.z; p.pos.z = g; p.vel.z = 0; if (v > 580) { stats.falls++; p.TakeDamage({ damage: Math.min(300, (v - 580) * 0.4 + 5), damageTypes: DT.FALL }); } } }
      else { p.pos.z = Math.max(p.pos.z, g); p.vel.z = 0; }
      if (p.hp <= 0) continue;
    }
    const pr = P(c);
    if (!pr || !pr.deployed) { if (!c.bot && step % 200 === (c.slot * 7) % 200) tap(c, IN.RELOAD); continue; }
    if (pr.ropeUntil > 0 && !c.drv.ropeSeen) { c.drv.ropeSeen = true; stats.ropes++; }
    if (c.bot) { if (!pr.heli && pr.mount < 0) walk(c, pr, step); continue; }
    const job = jobOf(c);
    if (job === 'pilot' && pr.role === 'air') drivePilot(c, pr, step);
    else if (job === 'crew' && pr.role === 'artillery' && pr.crew >= 0) driveCrew(c, pr, step);
    else if (job === 'rider' || pr.heli) driveRider(c, pr, step);
    else if (job === 'mount' || pr.mount >= 0) driveMount(c, pr, step);
    else if (job === 'observer' && pr.role === 'infantry') driveObserver(c, pr, step);
    else walk(c, pr, step);
  }
  // chat: roles, kits, spawn choices, help, bots
  if (step === 64 * 2) for (const c of ctls) { if (c.bot) continue; const j = jobOf(c); if (j === 'pilot') hooks.chat({ player: c, text: '!air', team: c.team }); if (j === 'crew') hooks.chat({ player: c, text: '!artillery', team: c.team }); if (j === 'walker') hooks.chat({ player: c, text: ['!infantry', '!mg', '!rifle', '!spawn b'][c.slot % 4], team: c.team }); }
  if (step === 64 * 4) { const c = ctls.find((x) => !x.bot); hooks.chat({ player: c, text: '!roles', team: c.team }); hooks.chat({ player: c, text: '/uniform', team: c.team }); hooks.chat({ player: c, text: '!spawn zz', team: c.team }); hooks.chat({ player: c, text: 'hello there', team: c.team }); }
  if (LOWPOP && step === 64 * 5) { hooks.chat({ player: ctls[0], text: '!bots 14', team: 2 }); fillBots(); }
  if (step > 0 && step % (64 * 150) === 0) for (const c of ctls) { if (!c.bot && ['pilot', 'crew'].includes(jobOf(c)) && P(c) && P(c).role === 'infantry') hooks.chat({ player: c, text: jobOf(c) === 'pilot' ? '!air' : '!artillery', team: c.team }); }
  // low population, second half: the AI holds every helicopter, then a human asks for one and must get it
  if (LOWPOP && step === Math.floor(SECONDS * 32)) { CONFIG.AI.PILOTS = 3; CONFIG.AI.MAX_ROLE_SHARE = 1; }
  if (LOWPOP && step === Math.floor(SECONDS * 32) + 64 * 40) {
    for (const team of [2, 3]) {
      const c = humans(team)[1]; if (!c) continue;
      const before = D.helis[team].filter((h) => h.owner >= 0 && ctls[h.owner].bot).length;
      hooks.chat({ player: c, text: '!air', team });
      expect(110, 'human ' + c.slot + ' asked for a helicopter the AI held (' + before + ' AI pilots) and owns one', () => { const ok = D.helis[team].some((h) => h.owner === c.slot); if (ok) stats.yields++; return ok || before === 0; });
    }
  }
  // a human takes a gun seat an AI gunner holds
  if (LOWPOP && step % (64 * 30) === 64 * 25) {
    const m = D.mounts.find((x) => x.user >= 0 && ctls[x.user].bot);
    const c = m && ctls.find((x) => !x.bot && x.pawn.hp > 0 && (m.team === x.team) && P(x) && P(x).deployed && !P(x).heli && P(x).mount < 0 && !P(x).board && jobOf(x) !== 'pilot');
    if (m && c) { putAt(c, m.seat.pos); c.drv.forceUse = 2; const botSlot = m.user;
      expect(1, 'human ' + c.slot + ' took the emplaced gun from AI gunner ' + botSlot, () => { const ok = m.user === c.slot && P(ctls[botSlot]).aiRole === ''; if (ok) stats.yields++; return ok; }); }
  }
  for (const c of ctls) if (c.drv.forceUse) { c.drv.forceUse--; c.pawn.keys = c.drv.forceUse === 0 ? IN.USE : 0; }
  // rifle fire: random kills between deployed enemies, bullets on flying helicopters
  if (step % 83 === 0) {
    const a = ctls[Math.floor(Math.random() * ctls.length)], v = ctls[Math.floor(Math.random() * ctls.length)];
    const pa = P(a), pv = P(v);
    if (a.team !== v.team && v.pawn.hp > 0 && a.pawn.hp > 0 && pa && pv && pa.deployed && pv.deployed && !pa.heli && d2(a.pawn.pos, v.pawn.pos) < 4500) v.pawn.TakeDamage({ damage: 150, damageTypes: DT.BULLET, attacker: a.pawn });
  }
  if (step % 30 === 0 && hooks.bullet) {
    const flying = [2, 3].flatMap((t) => D.helis[t]).filter((h) => h.state === 'flying' && h.ent);
    if (flying.length) {
      const h = flying[Math.floor(Math.random() * flying.length)], shooters = ctls.filter((c) => c.team !== h.team && c.pawn.hp > 0 && P(c) && P(c).deployed);
      if (shooters.length) { const s = shooters[Math.floor(Math.random() * shooters.length)]; hooks.bullet({ weapon: new Weapon(Math.random() < 0.5 ? 'weapon_m249' : 'weapon_ak47', s.pawn), position: { ...h.pos }, hitEntity: world.get(h.name) }); }
    }
  }
  // a bot thrown out of the playable band must be brought back by the leash
  if (step % (64 * 45) === 64 * 20) {
    const b = ctls.find((c) => c.bot && c.pawn.hp > 0 && P(c) && P(c).deployed && !P(c).aiRole && !P(c).heli && P(c).mount < 0);
    if (b) { b.pawn.pos = { x: L.map.x + 300, y: 0, z: 40 }; b.drv.goal = { x: L.map.x + 300, y: 0 }; b.drv.hold = time + 4; const pawn = b.pawn;
      expect(3, 'bot ' + b.slot + ' outside the band was re-deployed', () => { const ok = b.pawn !== pawn || Math.abs(b.pawn.pos.x) < L.map.x; if (ok) stats.leashOk++; b.drv.goal = null; return ok; }); }
  }
  // disconnect and a slot changing hands
  if (step === 64 * 100 && ctls.length > 8) { const c = ctls[ctls.length - 1]; hooks.disc({ playerSlot: c.slot }); const n = new Ctl(c.slot, c.team, c.bot); ctls[c.slot] = n; c.pawn.valid = false; spawn(n); }
  if (Instance._next !== undefined && Instance._next <= time) {
    Instance._next = undefined;
    const t0 = performance.now(); Instance._think(); const ms = performance.now() - t0;
    thinkMs += ms; thinkN++; if (ms > thinkMax) thinkMax = ms;
  } else if (step > 4) fail('the think loop stopped at ' + time.toFixed(2));
  for (let i = checks.length - 1; i >= 0; i--) if (checks[i].at <= time) { const k = checks[i]; checks.splice(i, 1); let ok = false; try { ok = k.fn(); } catch (e) { ok = false; } if (!ok) fail('expected: ' + k.what + ' (t ' + time.toFixed(0) + ')'); }
  // invariants
  if (step % 16 === 0) {
    if (D.game.tickets[2] !== ticketsStart || D.game.tickets[3] !== ticketsStart) ticketsMoved = true;
    for (const t of [2, 3]) for (const h of D.helis[t]) {
      if (!fin(h.pos) || !fin(h.vel) || ![h.yaw, h.pitch, h.roll, h.hp].every(Number.isFinite)) fail('helicopter ' + h.tag + ' has a non-finite state');
      if (h.state === 'flying') maxAlt = Math.max(maxAlt, h.pos.z - ground(h.pos.x, h.pos.y));
      h.seats.forEach((s, i) => { if (s.slot >= 0) { const q = D.players.get(s.slot); if (!q || q.heli !== h || q.seat !== i) fail('seat ' + i + ' of ' + h.tag + ' points at a player who is not in it'); } });
    }
    for (const c of ctls) {
      const pr = P(c); if (!pr) continue;
      if (c.pawn.hp > 0 && !fin(c.pawn.pos)) fail('pawn ' + c.slot + ' non-finite');
      if (pr.heli && pr.heli.seats[pr.seat].slot !== c.slot) fail('player ' + c.slot + ' thinks it is in a seat it does not hold');
      if (pr.aiRole) { aiSeen[pr.aiRole] = aiSeen[pr.aiRole] || (pr.aiRole === 'crew' ? D.stats.aiShots > 0 : pr.aiRole === 'pilot' ? !!pr.heli && pr.heli.state === 'flying' : D.stats.aiGunTicks > 0); if (!LOWPOP) aiWhenCrowded = true; }
      if (pr.aiRole && !c.bot) fail('a human has an AI role');
    }
  }
}
fs.unlinkSync(dest);

// ------------------------------------------------------------------ verdict
const S = D.stats;
const errs = stats.msgs.filter((m) => m.includes('error in') || m.includes('missing entity') || m.includes('failed'));
for (const e of errs.slice(0, 6)) fail('script log: ' + e.slice(0, 600));
for (const n of lookedUpMissing) if (!OPTIONAL.some((r) => r.test(n))) fail('looked up a missing entity: ' + n);
if (stats.terminate < 1) fail('no round ended (GameRules.TerminateRound never called)');
if (!process.env.MOCK_NORESTART && stats.rounds < 1) fail('no new round started');
if (!ticketsMoved) fail('tickets never moved');
if (S.captures < 1) fail('no flag was captured');
if (S.flights < 1 || !(maxAlt > 150)) fail('no helicopter flew (flights ' + S.flights + ', max height ' + maxAlt.toFixed(0) + ')');
if (S.landings < 1) fail('no helicopter landed');
if (S.heliLost < 1) fail('no helicopter was shot down');
if (S.shells < 1) fail('no shell landed');
if (S.rockets < 1) fail('no rocket was fired');
if (S.missions < 1) fail('no fire mission was called');
if (S.leash < 1) fail('the bot leash never acted');
if (stats.panelIds.size > 1024) fail('more than 1024 HUD panel ids');
if (LOWPOP) { for (const k of ['pilot', 'gunner', 'crew']) if (!aiSeen[k]) fail('low population: the AI ' + k + ' never became active'); if (S.aiLandings < 1) fail('low population: the AI pilot never came back to its pad'); if (stats.yields < 1) fail('low population: no AI seat was given to a human'); }
else if (aiWhenCrowded) fail('AI roles were handed out although both teams had enough humans');
if (!SYNTH) for (const [id, c] of contract) if (xmlIds && !xmlIds.has(id)) fail('HUD xml lacks contract panel ' + id);
const unusedIds = [...contract].filter(([, c]) => !c.textUsed && !c.used.size).map(([id]) => id);
const roles = {}; for (const p of D.players.values()) { const k = p.team + ':' + (p.aiRole ? 'ai-' + p.aiRole : p.role); roles[k] = (roles[k] || 0) + 1; }
console.log('mg_monsoon mock: ' + ctls.length + ' players (' + ctls.filter((c) => !c.bot).length + ' human), ' + SECONDS + ' s, entities ' + (SYNTH ? 'synthesised from layout.json' : 'out/entities.json') + ', script ' + built.lines + ' lines');
console.log('roles', JSON.stringify(roles));
console.log(JSON.stringify({ script: S, engine: { hud: stats.hud, vars: stats.vars, panelIds: stats.panelIds.size, fires: stats.fires, dmg: stats.dmg, kills: stats.kills, blocked: stats.blocked, fallBlocked: stats.fallBlocked, falls: stats.falls,
  teleports: stats.teleports, moves: stats.moves, cam: stats.cam, traces: stats.traces, rounds: stats.rounds, terminate: stats.terminate, ropes: stats.ropes, yields: stats.yields, leashOk: stats.leashOk, kitUses: stats.kit, zeus: stats.gunfire,
  cmds: stats.cmds, setModel: stats.setmodel, maxAlt: Math.round(maxAlt), tickets: D.game.tickets, flags: D.flags.map((f) => f.id + ':' + f.owner).join(' ') } }));
if (unusedIds.length) console.log('HUD contract ids never used in this run: ' + unusedIds.join(' '));
console.log('script time: ' + (thinkMs / Math.max(1, thinkN)).toFixed(3) + ' ms/tick avg, ' + thinkMax.toFixed(2) + ' ms max over ' + thinkN + ' ticks (includes the stand-in engine\'s traces: ' + (stats.traces / Math.max(1, thinkN)).toFixed(1) + ' per tick)');
if (fails.length) { console.log('FAIL (' + fails.length + ')'); for (const f of fails) console.log('  - ' + f); process.exit(1); }
console.log('PASS');
