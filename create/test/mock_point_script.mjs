// Generic smoke and regression test for a cs_script point_script: runs the real script file against a stand-in for CS2's
// "cs_script/point_script" API (Valve's point_script.d.ts) with simulated players, rounds, inputs, chat, damage, kills,
// respawns, team changes and disconnects. Fails (exit 1) on any exception inside the script's callbacks, a call outside
// the .d.ts, or a flagged problem (see README.md next to this file for every option, scenario and check).
//
// usage: node mock_point_script.mjs <script.js> [entities.json] [players=8] [seconds=120] [seed=N] [key=value | flag ...]
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';

const args = process.argv.slice(2);
if (!args[0] || /^(-h|--help)$/.test(args[0])) {
  console.log('usage: node mock_point_script.mjs <script.js> [entities.json] [players=8] [seconds=120] [seed=N] [option ...]  (options: README.md)');
  process.exit(2);
}
const kv = new Map();
let ENTFILE = null;
for (const a of args.slice(1)) { const i = a.indexOf('='); if (i < 0 && a.endsWith('.json')) ENTFILE = a; else kv.set(i < 0 ? a : a.slice(0, i), i < 0 ? '1' : a.slice(i + 1)); }
const opt = (k, d) => (kv.has(k) ? kv.get(k) : d);
const on = (k) => kv.has(k) && kv.get(k) !== '0';
const KNOWN = 'players seconds seed round warm trace calls held churn silent norespawn warmup unassigned resetfirst hudwipe maskall autoents models hud css inputs chat';
for (const k of kv.keys()) if (!KNOWN.split(' ').includes(k)) console.log('warning: unknown option ' + k);

const SCRIPT = path.resolve(args[0]);
const ENTS = (ENTFILE ? JSON.parse(fs.readFileSync(ENTFILE, 'utf8')) : []).map((e) => ({
  name: e.name ?? e.targetname ?? '', cls: e.cls ?? e.classname ?? 'info_target', origin: e.origin || [0, 0, 0], angles: e.angles || [0, 0, 0] }));
const PLAYERS = Math.min(64, +opt('players', 8)), SECONDS = +opt('seconds', 120);
const ROUND = +opt('round', Math.max(20, Math.round(SECONDS / 3)));
const WARM = +opt('warm', Math.min(240, Math.floor(SECONDS / 4)));
const TRACE = kv.has('trace') ? opt('trace') : null;
const CALLS = on('calls'), HELD = on('held'), SILENT = on('silent'), HUDWIPE = on('hudwipe'), CHURN = on('churn') || SILENT || HUDWIPE;
const NORESPAWN = on('norespawn'), WARMUP = on('warmup'), UNASSIGNED = on('unassigned'), RESETFIRST = on('resetfirst'), MASKALL = on('maskall'), AUTOENTS = on('autoents');
const MODEL_ROOTS = kv.has('models') ? opt('models').split(',').map((d) => path.resolve(d)) : null;

let time = 0, tick = 0;
let rs = +opt('seed', 1) >>> 0;
Math.random = () => { rs = (rs + 0x6D2B79F5) >>> 0; let t = rs; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
// the script sees game-time clocks (repeatable runs); the mock keeps the real one for its own timing
const clock = performance.now.bind(performance);
Date.now = () => 1790000000000 + Math.round(time * 1000);
Object.defineProperty(globalThis, 'performance', { value: { now: () => time * 1000, timeOrigin: 1790000000000 }, configurable: true, writable: true });
const pick = (a) => a[Math.floor(Math.random() * a.length)];

// ---------------------------------------------------------------- Valve's declarations: API names, return types, classes, enums
const here = path.dirname(fileURLToPath(import.meta.url));
const dts = fs.readFileSync(path.join(here, 'point_script.d.ts'), 'utf8');
const API = new Set([...dts.matchAll(/^\s{8}([A-Z][A-Za-z]+)(?:<[^>]*>)?\(/gm)].map((m) => m[1]));
const RET = {};
for (const m of dts.matchAll(/^\s{8}([A-Z][A-Za-z]+)(?:<[^>]*>)?\(.*\):\s*([^;]+);/gm)) RET[m[1]] = RET[m[1]] || m[2].trim();
const DCLS = {};
{ let cur = null;
  for (const line of dts.split('\n')) {
    let m = line.match(/^\s{4}export class (\w+)(?: extends (\w+))?/);
    if (m) { cur = DCLS[m[1]] = { parent: m[2], methods: new Set() }; continue; }
    if (/^\s{4}\S/.test(line)) { cur = null; continue; }
    if (cur && (m = line.match(/^\s{8}([A-Z]\w*)(?:<[^>]*>)?\(/))) cur.methods.add(m[1]);
  } }
const ENUMS = {};
for (const m of dts.matchAll(/export enum (\w+)\s*\{([^}]*)\}/g)) {
  const e = {}; let v = -1;
  for (let item of m[2].replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '').split(',')) {
    item = item.trim(); if (!item) continue;
    const [k, ex] = item.split('=').map((s) => s.trim());
    if (ex !== undefined) { const sh = ex.match(/^(-?\d+)\s*<<\s*(\d+)$/); v = sh ? (+sh[1]) << +sh[2] : +ex; } else v++;
    e[k] = v;
  }
  ENUMS[m[1]] = e;
}
const IN = ENUMS.CSInputs, DF = ENUMS.CSDamageFlags, RR = ENUMS.CSRoundEndReason, WT = ENUMS.CSWeaponType, GS = ENUMS.CSGearSlot, MT = ENUMS.CSMoveType;
const V = (x = 0, y = 0, z = 0) => ({ x, y, z });
const Q = (pitch = 0, yaw = 0, roll = 0) => ({ pitch, yaw, roll });
const dflt = (k) => { const t = RET[k] || ''; if (/^number/.test(t)) return 0; if (/^boolean/.test(t)) return false; if (/^string/.test(t)) return '';
  if (/^(Vector|RotationVector)/.test(t)) return V(); if (/^QAngle/.test(t)) return Q(); if (/^Color/.test(t)) return { r: 255, g: 255, b: 255, a: 255 }; if (/\[\]/.test(t)) return []; return undefined; };

// ---------------------------------------------------------------- bookkeeping
const stats = { calls: {}, unknownEntityCalls: {}, fired: {}, errors: [], notInApi: {}, problems: [], kills: 0, scriptDamage: 0, teamkills: 0, respawns: 0,
  teamChanges: 0, roundEnds: {}, restarts: 0, spawned: 0, hudCalls: 0, hudDropped: 0, tpRuns: 0, tpNames: new Set(), tpAuto: 0, tpAutoNames: new Set(), invalidCalls: 0, models: new Set(),
  churn: { join: 0, kick: 0, swap: 0, leave: 0 } };
const count = (o, k) => { o[k] = (o[k] || 0) + 1; };
const flagIt = (msg) => stats.problems.push(msg);
const cvars = { mp_freezetime: '2', mp_round_restart_delay: '3' };
const cvar = (k) => cvars[k];

// trace: observable state per tick, so two builds can be compared by what ends up on screen
const OBS = TRACE !== null;
const state = new Map(), dirty = new Map(), evs = [], traceOut = [];
const see = (key, val) => { if (!dirty.has(key)) dirty.set(key, state.get(key)); if (val === undefined) state.delete(key); else state.set(key, val); };
const r2 = (n) => (Math.round(n * 100) / 100).toFixed(2);
function entState(e) {
  const p = e._p, a = e._a; let s = `${r2(p.x)},${r2(p.y)},${r2(p.z)} ${r2(a.pitch)},${r2(a.yaw)},${r2(a.roll)}`;
  if (e._model !== undefined) { const c = e._color; s += ` ${e._model} s${e._skin} c${c.r},${c.g},${c.b},${c.a}${e._glow ? ' glow ' + e._glow : ''}${e._scale !== 1 ? ' x' + e._scale : ''}`; }
  if (e instanceof Pawn) s += e._alive ? ' hp' + e._hp : ' dead';
  if (e instanceof Camera) s += ' m' + e.mode;
  return s;
}
const nameSeq = new Map();
function traceKey(e) {
  if (e._tk) return e._tk;
  if (e instanceof Pawn) return 'pawn' + e.ctl.slot; if (e instanceof Camera) return 'cam' + e.pawn.ctl.slot;
  const base = e._n || e._c, n = (nameSeq.get(base) || 0) + 1; nameSeq.set(base, n);
  return (e._tk = base + (n > 1 ? '#' + n : ''));
}
const seeEnt = (e) => { if (OBS && !(e instanceof Controller) && !(e instanceof Weapon)) see('e ' + traceKey(e), e._ok ? entState(e) : undefined); };
const event = (s) => { if (OBS) evs.push(s); };
function traceTick() {
  if (!dirty.size && !evs.length) return;
  const lines = [];
  for (const [k, before] of dirty) { const now = state.get(k); if (now !== before) lines.push(k + ' = ' + (now ?? '-')); }
  dirty.clear(); lines.sort();
  for (const e of evs.sort()) lines.push('! ' + e);
  evs.length = 0;
  if (lines.length) traceOut.push('t' + tick + '\n' + lines.join('\n'));
}

// calls: engine calls per tick, top methods and (sampled) the script lines making them
const callCount = new Map(), sites = new Map();
let callTotal = 0, sampleN = 0, tmpBase = '';
function cnt(name) {
  callTotal++; callCount.set(name, (callCount.get(name) || 0) + 1);
  if (++sampleN % 61) return;
  const line = (new Error().stack || '').split('\n').find((l) => l.includes(tmpBase));
  const m = line && line.match(/at (?:(\S+) \()?.*:(\d+):\d+\)?$/);
  if (m) { const k = (m[1] || '<anon>') + ':' + m[2]; sites.set(k, (sites.get(k) || 0) + 1); }
}

// ---------------------------------------------------------------- entities
let world = [], dead = 0, nextId = 1, mapProps = [];
function chkV(v, what, lim) {
  if (!v || typeof v !== 'object') throw new Error(what + ' is not a vector: ' + JSON.stringify(v));
  for (const c of 'xyz') { const n = v[c]; if (!Number.isFinite(n)) throw new Error('non-finite ' + what + ' ' + JSON.stringify(v)); if (lim && Math.abs(n) > 16384) throw new Error(what + ' outside +-16384 ' + JSON.stringify(v)); }
}
function chkA(a, what) { if (!a || ['pitch', 'yaw', 'roll'].some((c) => !Number.isFinite(a[c]))) throw new Error('non-finite ' + what + ' ' + JSON.stringify(a)); }
function chkCol(c) { if (!c || ['r', 'g', 'b'].some((k) => !Number.isFinite(c[k])) || (c.a !== undefined && !Number.isFinite(c.a))) throw new Error('bad color ' + JSON.stringify(c)); }
function setInt(e, f, v, what) { if (!Number.isFinite(v)) throw new Error(what + '(' + v + ')'); if (!Number.isInteger(v)) flagIt(what + '(' + v + '): not an integer (unverified CS2 rule)'); e[f] = v; }
function chkDmg(d) { if (!d || !Number.isFinite(d.damage)) throw new Error('TakeDamage needs a finite damage: ' + JSON.stringify(d && d.damage)); }
function place(e, o, tp) {
  if (!o || typeof o !== 'object') throw new Error((tp ? 'Teleport' : 'Move') + ' needs an object');
  if (o.position) chkV(o.position, 'position', true); if (o.velocity) chkV(o.velocity, 'velocity'); if (o.angularVelocity) chkV(o.angularVelocity, 'angularVelocity');
  if (o.angles) chkA(o.angles, 'angles');
  if (tp && e._tp && (o.position || o.angles)) {   // CS2 doesn't draw a prop whose position is Teleported every tick
    if (e._tpTick === tick - 1) { if (++e._tpRun === 2) { if (e._auto) { stats.tpAuto++; stats.tpAutoNames.add(e._n); } else { stats.tpRuns++; stats.tpNames.add(e._n || e._c); } } } else if (e._tpTick !== tick) e._tpRun = 0;
    e._tpTick = tick;
  }
  if (o.position) e._p = { x: o.position.x, y: o.position.y, z: o.position.z };
  if (o.angles) e._a = { pitch: o.angles.pitch, yaw: o.angles.yaw, roll: o.angles.roll };
  if (o.velocity) e._v = { x: o.velocity.x, y: o.velocity.y, z: o.velocity.z };
  seeEnt(e);
}
const modelSeen = new Map();
function setModel(e, m) {
  if (typeof m !== 'string') throw new Error('SetModel(' + m + ')');
  stats.models.add(m);
  if (MODEL_ROOTS && m) {
    if (!modelSeen.has(m)) modelSeen.set(m, MODEL_ROOTS.some((r) => fs.existsSync(path.join(r, m)) || fs.existsSync(path.join(r, m + '_c'))));
    if (!modelSeen.get(m)) throw new Error('missing model ' + m + ' (not under models=)');
  }
  e._model = m; seeEnt(e);
}

class Ent {
  constructor(name, cls, pos, ang) { this._id = nextId++; this._n = name || ''; this._c = cls; this._p = pos ? { ...pos } : V(); this._a = ang ? { ...ang } : Q(); this._v = V();
    this._ok = true; this._hp = 100; this._maxhp = 100; this._team = 0; this._parent = undefined; this._owner = undefined; this._mt = MT.NONE; }
  IsValid() { return this._ok; }
  GetClassName() { return this._c; } GetEntityName() { return this._n; } SetEntityName(n) { unindex(this); this._n = String(n); index(this); seeEnt(this); }
  GetAbsOrigin() { return { ...this._p }; } GetLocalOrigin() { return { ...this._p }; } GetAbsAngles() { return { ...this._a }; } GetLocalAngles() { return { ...this._a }; }
  GetAbsVelocity() { return { ...this._v }; } GetLocalVelocity() { return { ...this._v }; } GetAbsAngularVelocity() { return V(); } GetLocalAngularVelocity() { return V(); }
  GetEyeAngles() { return { ...this._a }; } GetEyePosition() { return V(this._p.x, this._p.y, this._p.z + 64); }
  Teleport(o, a, v) { if (o === null || arguments.length > 1 || (o && 'x' in o)) o = { position: o || undefined, angles: a || undefined, velocity: v || undefined }; place(this, o, true); }
  Move(o) { place(this, o, false); }
  GetMoveType() { return this._mt; } SetMoveType(t) { this._mt = t; }
  GetOwner() { return this._owner; } SetOwner(o) { this._owner = o; } GetParent() { return this._parent; } SetParent(p) { this._parent = p; }
  GetTeamNumber() { return this._team; } GetHealth() { return this._hp; } SetHealth(h) { setInt(this, '_hp', h, 'SetHealth'); }
  GetMaxHealth() { return this._maxhp; } SetMaxHealth(h) { setInt(this, '_maxhp', h, 'SetMaxHealth'); }
  IsAlive() { return this._hp > 0; } IsWorld() { return this === worldEnt; } GetGroundEntity() { return worldEnt; }
  TakeDamage(d) { chkDmg(d); stats.scriptDamage++; this._hp -= d.damage; return d.damage; }
  Kill() { removeEnt(this); } Remove() { removeEnt(this); }
}
class ModelEnt extends Ent {
  constructor(...a) { super(...a); this._tp = true; this._tpTick = -9; this._tpRun = 0; this._model = ''; this._scale = 1; this._color = { r: 255, g: 255, b: 255, a: 255 }; this._glow = null; this._skin = 0; }
  SetModel(m) { setModel(this, m); } GetModelName() { return this._model; }
  SetModelScale(s) { if (!Number.isFinite(s)) throw new Error('SetModelScale(' + s + ')'); this._scale = s; seeEnt(this); } GetModelScale() { return this._scale; }
  SetColor(c) { chkCol(c); this._color = { r: c.r, g: c.g, b: c.b, a: c.a ?? 255 }; seeEnt(this); } GetColor() { return { ...this._color }; }
  Glow(c) { if (c) chkCol(c); this._glow = c ? `${c.r},${c.g},${c.b}` : 'on'; seeEnt(this); } Unglow() { this._glow = null; seeEnt(this); } IsGlowing() { return !!this._glow; }
}
function winfo(c) {
  if (/knife|bayonet/.test(c)) return [WT.KNIFE, GS.KNIFE];
  if (/glock|usp|hkp2000|p250|deagle|fiveseven|tec9|cz75|elite|revolver/.test(c)) return [WT.PISTOL, GS.PISTOL];
  if (/grenade|flashbang|molotov|decoy|smoke/.test(c)) return [WT.GRENADE, GS.GRENADES];
  if (/c4/.test(c)) return [WT.C4, GS.C4];
  if (/taser/.test(c)) return [WT.TASER, GS.KNIFE];
  if (/healthshot/.test(c)) return [WT.STACKABLEITEM, GS.BOOSTS];
  if (/awp|ssg08|scar20|g3sg1/.test(c)) return [WT.SNIPER_RIFLE, GS.RIFLE];
  if (/mp\d|mac10|ump|p90|bizon/.test(c)) return [WT.SUBMACHINEGUN, GS.RIFLE];
  if (/nova|xm1014|mag7|sawedoff/.test(c)) return [WT.SHOTGUN, GS.RIFLE];
  if (/negev|m249/.test(c)) return [WT.MACHINEGUN, GS.RIFLE];
  return [WT.RIFLE, GS.RIFLE];
}
class WeaponData {
  constructor(c) { this._c = c; [this._type, this._slot] = winfo(c); }
  GetName() { return this._c; } GetType() { return this._type; } GetGearSlot() { return this._slot; } GetPrice() { return 500; } GetDamage() { return 30; }
  GetMaxClipAmmo() { return 30; } GetMaxReserveAmmo() { return 90; } GetRange() { return 8192; } GetRangeModifier() { return 0.85; } GetPenetration() { return 1; }
}
class Weapon extends ModelEnt {
  constructor(c, owner) { super('', c); this._owner = owner; this._orig = owner; this.clip = 30; this.reserve = 90; [this._type, this._slot] = winfo(c); this._model = 'weapons/models/' + c + '.vmdl'; }
  GetData() { return new WeaponData(this._c); } GetOwner() { return this._owner && this._owner._ok ? this._owner : undefined; } GetOriginalOwner() { return this._orig; }
  GetClipAmmo() { return this.clip; } SetClipAmmo(v) { setInt(this, 'clip', v, 'SetClipAmmo'); } GetReserveAmmo() { return this.reserve; } SetReserveAmmo(v) { setInt(this, 'reserve', v, 'SetReserveAmmo'); }
  IsSilencerOn() { return false; }
}
class Grenade extends ModelEnt {
  constructor(type, thrower, pos) { super('', 'hegrenade_projectile', pos); this._gt = type; this._thrower = thrower; }
  GetThrower() { return this._thrower; } GetGrenadeType() { return this._gt; } Detonate() { removeEnt(this); }
}
const STACK = new Set(['weapon_flashbang', 'weapon_healthshot']);
class Pawn extends ModelEnt {
  constructor(ctl) { super('', 'player'); this._tp = false; this.ctl = ctl; this.w = []; this.active = null; this.keys = 0; this.prev = 0; this._alive = false; this._hp = 0;
    this._armor = 0; this._helmet = false; this._defuser = false; this._eye = Q(0, Math.floor(Math.random() * 360), 0); this._turn = 0; this.cam = null; this._mt = MT.WALK; this._model = 'characters/models/player.vmdl'; }
  GetPlayerController() { return this.ctl._ok ? this.ctl : undefined; } GetOriginalPlayerController() { return this.ctl; }
  GetTeamNumber() { return this.ctl._team; } IsAlive() { return this._alive; }
  IsInputPressed(b) { return MASKALL ? (this.keys & b) === b : (this.keys & b) !== 0; }
  WasInputJustPressed(b) { const j = this.keys & ~this.prev & b; return MASKALL ? j === b : j !== 0; }
  WasInputJustReleased(b) { const j = ~this.keys & this.prev & b; return MASKALL ? j === b : j !== 0; }
  GetEyeAngles() { return { ...this._eye }; } SetEyeAngles(a) { chkA(a, 'eye angles'); this._eye = { pitch: a.pitch, yaw: a.yaw, roll: a.roll }; }
  GetGroundEntity() { return this.keys & IN.JUMP ? undefined : worldEnt; }
  FindWeapon(n) { return this.w.find((w) => w._c === n); } FindWeaponBySlot(s) { return this.w.find((w) => w._slot === s); }
  GetActiveWeapon() { return this.active && this.active._ok ? this.active : undefined; } GetC4() { return this.FindWeapon('weapon_c4'); }
  DestroyWeapon(w) { if (!w || !w._ok) throw new Error('Invalid entity (DestroyWeapon)'); this.w = this.w.filter((x) => x !== w); if (this.active === w) this.active = this.w[0] || null; removeEnt(w); }
  DestroyWeapons() { for (const w of this.w) removeEnt(w); this.w = []; this.active = null; }
  DropWeapon(w) { if (!w || !w._ok) throw new Error('Invalid entity (DropWeapon)'); this.w = this.w.filter((x) => x !== w); if (this.active === w) this.active = this.w[0] || null; w._owner = undefined; }
  SwitchToWeapon(w) { if (this.w.includes(w)) this.active = w; }
  GiveNamedItem(n, deploy) {
    if (typeof n !== 'string') throw new Error('GiveNamedItem(' + n + ')');
    if (n === 'item_kevlar' || n === 'item_assaultsuit') { this._armor = 100; if (n === 'item_assaultsuit') this._helmet = true; return; }
    if (!n.startsWith('weapon_')) return;
    if (!STACK.has(n) && this.w.some((w) => w._c === n)) flagIt(`GiveNamedItem("${n}") to a player who already has one (CS2 gives a duplicate)`);
    give(this, n, deploy !== false);
  }
  GetArmor() { return this._armor; } SetArmor(v) { setInt(this, '_armor', v, 'SetArmor'); } HasHelmet() { return this._helmet; } SetHasHelmet(v) { this._helmet = !!v; }
  HasDefuser() { return this._defuser; } SetHasDefuser(v) { this._defuser = !!v; }
  IsDucking() { return !!(this.keys & IN.DUCK); } IsDucked() { return !!(this.keys & IN.DUCK); } IsScoped() { return false; } IsNoclipping() { return this._mt === MT.NOCLIP; } IsBuyMenuOpen() { return false; }
  GetCustomCamera() { return this.cam || (this.cam = add(new Camera(this))); }
  TakeDamage(d) { chkDmg(d); stats.scriptDamage++; return hurt(this, d); }
  Kill() { if (this._alive) die(this); } Remove() { if (this._alive) die(this); }
}
class Controller extends Ent {
  constructor(slot, bot) { super('', 'cs_player_controller'); this.slot = slot; this.bot = bot; this.pawn = null; this.connected = true; this.kills = 0; this.deaths = 0; this.score = 0; this._money = 800; }
  GetPlayerSlot() { return this.slot; } GetPlayerName() { return (this.bot ? 'bot' : 'player') + this.slot; }
  GetPlayerPawn() { return this.pawn && this.pawn._ok ? this.pawn : undefined; } GetObserverPawn() { return undefined; }
  GetScore() { return this.score; } AddScore(n) { if (!Number.isFinite(n)) throw new Error('AddScore(' + n + ')'); this.score = Math.max(0, this.score + n); }
  IsObserving() { return !this.IsAlive(); } IsBot() { return this.bot; } IsConnected() { return this.connected; }
  IsAlive() { return !!(this.pawn && this.pawn._ok && this.pawn._alive); }
  JoinTeam(t) { if (!Number.isInteger(t)) throw new Error('JoinTeam(' + t + ')'); if (t !== this._team) teamChange(this, t); }
  GetMoneySpendableNow() { return this._money; } AddMoneySpendableNow(n) { this._money += n; }
}
// HUD: per-slot classes and dialog variables; with hud=<layout.xml> unknown panel ids throw
let HUD = null;
if (kv.has('hud')) {
  const [x, c] = opt('hud').split(',');
  const cssPath = opt('css') || c || x.replace(/layout([\\/])/, 'styles$1').replace(/\.xml$/, '.css');
  const xml = fs.readFileSync(x, 'utf8'), css = fs.existsSync(cssPath) ? fs.readFileSync(cssPath, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '') : null;
  if (css === null) console.log('warning: no css at ' + cssPath + ' (css=<file>); class checks skipped');
  const lone = new Set();
  if (css) for (const m of css.matchAll(/(^|\})\s*([^{}@]+)\{/g)) for (const sel of m[2].split(',')) { const t = sel.trim(); if (/^\.[\w-]+$/.test(t)) lone.add(t.slice(1)); }
  HUD = { ids: new Set([...xml.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1])), css, classes: css ? new Set([...css.matchAll(/\.([A-Za-z_][\w-]*)/g)].map((m) => m[1])) : null, lone, used: new Map() };
}
const hudState = new Map();   // 'slot|panel' -> Set of classes
const loading = new Set();    // hudwipe: slots whose client drops HUD changes until they pick a team
function hudPanel(panel, cls) {
  stats.hudCalls++;
  if (typeof panel !== 'string') throw new Error('HUD panel id must be a string: ' + panel);
  if (HUD && !HUD.ids.has(panel)) throw new Error('unknown HUD panel ' + panel);
  if (cls !== undefined) { if (typeof cls !== 'string') throw new Error('HUD class must be a string: ' + cls); if (HUD) HUD.used.set(cls, (HUD.used.get(cls) || 0) + 1); }
}
const chkSlot = (s) => { if (!Number.isInteger(s) || s < 0 || s > 63) throw new Error('bad player slot ' + s); };
function hudCls(scope, panel, cls, has) {
  const k = scope + '|' + panel; let set = hudState.get(k);
  if (!set) hudState.set(k, set = new Set());
  if (has === true || has === undefined && scope === 'all') set.add(cls); else set.delete(cls);
  if (OBS) see('h ' + k, [...set].sort().join(' '));
}
function hudReset(prefix) { for (const k of [...hudState.keys()]) if (!prefix || k.startsWith(prefix)) { hudState.delete(k); if (OBS) see('h ' + k, undefined); }
  if (OBS) for (const k of [...state.keys()]) if (k.startsWith('v ') && (!prefix || k.startsWith('v ' + prefix))) see(k, undefined); }
class Hud extends Ent {
  SetHasClass(panel, cls, has) { hudPanel(panel, cls); hudCls('all', panel, cls, has === undefined ? false : !!has); }
  SetHasClassForPlayer(slot, panel, cls, has) { chkSlot(slot); hudPanel(panel, cls); if (HUDWIPE && loading.has(slot)) { stats.hudDropped++; return; } hudCls(slot, panel, cls, has === undefined ? undefined : !!has); }
  SetDialogVariableString(panel, name, value) { hudPanel(panel); if (typeof value !== 'string') throw new Error('non-string dialog var ' + panel + '.' + name + ' = ' + value); if (OBS) see('v all|' + panel + '.' + name, value); }
  SetDialogVariableStringForPlayer(slot, panel, name, value) { chkSlot(slot); hudPanel(panel);
    if (value !== undefined && typeof value !== 'string') throw new Error('non-string dialog var ' + panel + '.' + name + ' = ' + value);
    if (HUDWIPE && loading.has(slot)) { stats.hudDropped++; return; } if (OBS) see('v ' + slot + '|' + panel + '.' + name, value); }
  SetInputCaptureEnabled(slot) { chkSlot(slot); } IsInputCaptureEnabled() { return false; }
  Reset() { hudReset(''); } ResetForPlayer(slot) { chkSlot(slot); hudReset(slot + '|'); }
}
class Template extends Ent {
  ForceSpawn(origin, angle) { if (origin) chkV(origin, 'ForceSpawn origin', true); if (angle) chkA(angle, 'ForceSpawn angles'); stats.spawned++;
    const e = add(new ModelEnt('', 'prop_dynamic', origin || this._p, angle || this._a)); e._spawned = true; return [e]; }
}
class Camera extends Ent {
  constructor(p) { super('', 'camera'); this.pawn = p; this.mode = 0; }
  GetPlayer() { return this.pawn; } GetMode() { return this.mode; } SetMode(m) { this.mode = m; seeEnt(this); }
  SetFollowConfig(c) { if (!c || !c.followEntity) throw new Error('SetFollowConfig without followEntity'); }
}
const worldEnt = new Ent('', 'worldspawn');

// every class the .d.ts declares, the unmodelled ones as plain subclasses; unmodelled methods return a default and are counted
const CLS = { Entity: Ent, BaseModelEntity: ModelEnt, CSWeaponBase: Weapon, CSWeaponData: WeaponData, CSGrenadeProjectileBase: Grenade, CSPlayerPawn: Pawn,
  CSPlayerController: Controller, CustomHudLayout: Hud, PointTemplate: Template, CustomPlayerCamera: Camera };
for (let left = Object.keys(DCLS).filter((n) => !CLS[n]); left.length;) {
  const n = left.find((k) => !DCLS[k].parent || CLS[DCLS[k].parent]);
  if (!n) { for (const k of left) CLS[k] = { [k]: class extends Ent {} }[k]; break; }
  const P = DCLS[n].parent ? CLS[DCLS[n].parent] : Object;
  CLS[n] = { [n]: class extends P {} }[n]; left = left.filter((k) => k !== n);
}
for (const [n, d] of Object.entries(DCLS)) for (const m of d.methods) if (!(m in CLS[n].prototype)) {
  const label = n + '.' + m;
  CLS[n].prototype[m] = function () { count(stats.unknownEntityCalls, label); return dflt(m); };
}
// calls on an entity that has gone away throw, as in CS2
for (const [n, C] of Object.entries(CLS)) for (const k of Object.getOwnPropertyNames(C.prototype)) {
  const f = C.prototype[k]; if (!/^[A-Z]/.test(k) || typeof f !== 'function') continue;
  const label = n + '.' + k;
  C.prototype[k] = k === 'IsValid' ? (CALLS ? function () { cnt(label); return f.call(this); } : f)
    : function (...a) { if (this._ok === false) { stats.invalidCalls++; throw new Error('Invalid entity (' + label + ' on ' + this._c + ')'); } if (CALLS) cnt(label); return f.apply(this, a); };
}

const permissive = (e) => new Proxy(e, { get(t, k) { if (k in t || typeof k === 'symbol' || !/^[A-Z]/.test(k)) return t[k]; count(stats.unknownEntityCalls, t._c + '.' + String(k)); return () => dflt(String(k)); } });
const add = (e) => { const x = e._auto ? permissive(e) : e; world.push(x); index(x); seeEnt(x); return x; };
const byName = new Map();
function index(e) { if (!e._n) return; let a = byName.get(e._n); if (!a) byName.set(e._n, a = []); a.push(e); }
function unindex(e) { const a = e._n && byName.get(e._n); if (!a) return; const i = a.indexOf(e); if (i >= 0) a.splice(i, 1); if (!a.length) byName.delete(e._n); }
function removeEnt(e) {
  if (!e._ok) return;
  e._ok = false; unindex(e); dead++; seeEnt(e);
  if (e instanceof Pawn) { for (const w of e.w) removeEnt(w); e.w = []; e.active = null; e._alive = false; if (e.cam) removeEnt(e.cam); }
}
function byNameMatch(n) {
  if (typeof n !== 'string') throw new Error('entity name must be a string: ' + n);
  if (n.includes('*')) { const re = new RegExp('^' + n.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$'); return world.filter((e) => e._ok && re.test(e._n)); }
  let a = byName.get(n);
  if (!a && AUTOENTS && n) {   // autoents: any name the script looks up exists, as a permissive prop/template/hud
    const C = /templ|tpl/i.test(n) ? Template : /hud/i.test(n) ? Hud : ModelEnt;
    const e = new C(n, C === Template ? 'point_template' : C === Hud ? 'custom_hud_layout' : 'prop_dynamic'); e._auto = true; e._map = true;
    a = [add(e)];
  }
  return a || [];
}
const PRESERVE = new Set(['worldspawn', 'point_script', 'custom_hud_layout', 'info_player_terrorist', 'info_player_counterterrorist', 'info_player_start', 'info_map_parameters',
  'info_target', 'func_brush', 'func_wall', 'func_buyzone', 'func_illusionary', 'env_soundscape', 'env_soundscape_proxy', 'env_soundscape_triggerable', 'env_sun', 'env_wind',
  'env_fog_controller', 'env_cascade_light', 'env_sky', 'light_environment', 'sky_camera', 'trigger_soundscape', 'keyframe_rope', 'move_rope', 'info_ladder', 'shadow_control',
  'point_viewcontrol', 'point_viewcontrol_multiplayer', 'cs_gamerules', 'cs_team_manager', 'cs_player_manager', 'infodecal', 'info_projecteddecal']);
function addMapEnt(d) {
  const C = d.cls === 'custom_hud_layout' ? Hud : d.cls === 'point_template' ? Template : /^(info_|logic_|point_|math_|game_|env_|filter_|ambient_)/.test(d.cls) ? Ent : ModelEnt;
  const e = add(new C(d.name, d.cls, V(...d.origin), Q(...d.angles))); e._map = true; return e;
}
for (const d of ENTS) addMapEnt(d);
if (HUD && !world.some((e) => e instanceof Hud)) addMapEnt({ name: 'hud', cls: 'custom_hud_layout', origin: [0, 0, 0], angles: [0, 0, 0] });
const SPAWNS = ENTS.filter((e) => e.cls.startsWith('info_player'));

// ---------------------------------------------------------------- players, damage, rounds
const players = [];
const give = (p, n, deploy) => { const w = add(new Weapon(n, p)); p.w.push(w); if (deploy || !p.active) p.active = w; return w; };
function loadout(p) { if (p.w.length) return; const ct = p.ctl._team === 3; give(p, ct ? 'weapon_knife' : 'weapon_knife_t'); give(p, ct ? 'weapon_usp_silencer' : 'weapon_glock', true); }
function spawnAt(p) {
  const t = p.ctl._team, own = SPAWNS.filter((s) => (t === 2 ? s.cls === 'info_player_terrorist' : t === 3 ? s.cls === 'info_player_counterterrorist' : false));
  const s = own.length ? pick(own) : SPAWNS.length ? pick(SPAWNS) : null;
  p._p = s ? V(...s.origin) : V(); p._a = s ? Q(...s.angles) : Q(); p._v = V();
}
function revive(p) { p._alive = true; p._hp = 100; p._maxhp = 100; p._armor = 0; p._mt = MT.WALK; p.keys = p.prev = 0; spawnAt(p); loadout(p); seeEnt(p); }
function respawn(c) {
  if (!c._ok || !c.connected || c._team < 2) return;
  let p = c.pawn; if (!p || !p._ok) p = c.pawn = add(new Pawn(c));
  if (p._alive) return;
  revive(p); stats.respawns++;
  fire('OnPlayerReset', { player: p });
}
function connect(slot, bot, team, silent) {
  const old = players[slot];
  if (old && old._ok) { old.connected = false; if (old.pawn) removeEnt(old.pawn); removeEnt(old); }   // the slot changes hands: the old controller is gone
  const c = add(new Controller(slot, bot)); c._team = team; players[slot] = c;
  if (team >= 2) { c.pawn = add(new Pawn(c)); revive(c.pawn); }
  if (!silent) { fire('OnPlayerConnect', { player: c }); fire('OnPlayerActivate', { player: c }); if (c.pawn) fire('OnPlayerReset', { player: c.pawn }); }
  return c;
}
function disconnect(c) {
  c.connected = false; loading.delete(c.slot);
  if (c.pawn) removeEnt(c.pawn);
  event('disconnect ' + c.slot);
  if (!SILENT) fire('OnPlayerDisconnect', { playerSlot: c.slot });
}
function teamChange(c, t) {
  const old = c._team; c._team = t; stats.teamChanges++; event('team ' + c.slot + ' ' + old + '>' + t);
  let p = c.pawn;
  if (p && p._ok && p._alive) { p._alive = false; p._hp = 0; for (const w of p.w) removeEnt(w); p.w = []; p.active = null; seeEnt(p); }
  if (!p || !p._ok) p = c.pawn = add(new Pawn(c));
  if (RESETFIRST && t >= 2) { revive(p); fire('OnPlayerReset', { player: p }); fire('OnPlayerTeamChanged', { player: p, oldTeam: old }); return; }
  fire('OnPlayerTeamChanged', { player: p, oldTeam: old });
  if (t >= 2) later(1, () => respawn(c));
}
function hurt(victim, d) {
  if (!victim._alive) return 0;
  const ev = { player: victim, damage: d.damage, damageTypes: d.damageTypes || 0, damageFlags: d.damageFlags || 0, hitGroup: d.hitGroup ?? 0, inflictor: d.inflictor, attacker: d.attacker, weapon: d.weapon };
  if (!(ev.damageFlags & DF.SUPPRESS_DAMAGE_MODIFICATION)) for (const k of ['OnBeforePlayerDamage', 'OnModifyPlayerDamage']) for (const cb of hooks[k] || []) {
    const r = safe(k, () => cb(ev));
    if (r && typeof r === 'object' && typeof r.then !== 'function') {
      if (r.abort) return 0;
      if (r.damage !== undefined) ev.damage = r.damage; if (r.damageTypes !== undefined) ev.damageTypes = r.damageTypes; if (r.damageFlags !== undefined) ev.damageFlags = r.damageFlags;
    }
  }
  if (!Number.isFinite(ev.damage)) throw new Error('OnModifyPlayerDamage returned a non-finite damage ' + ev.damage);
  let hp = victim._hp - ev.damage;
  if (ev.damageFlags & DF.FORCE_DEATH) hp = Math.min(hp, 0); else if (ev.damageFlags & DF.PREVENT_DEATH) hp = Math.max(hp, 1);
  const before = victim._hp;
  victim._hp = hp > 0 ? Math.max(1, Math.floor(hp)) : 0;
  fire('OnPlayerDamage', { ...ev, damage: before - victim._hp });
  if (victim._hp <= 0 && victim._alive) die(victim, ev.attacker, ev.inflictor, ev.weapon);
  else seeEnt(victim);
  return before - victim._hp;
}
function die(p, attacker, inflictor, weapon) {
  p._alive = false; p._hp = 0; stats.kills++; p.ctl.deaths++;
  const k = attacker instanceof Pawn ? attacker.ctl : attacker instanceof Controller ? attacker : null;
  if (k && k !== p.ctl) { if (k._team === p.ctl._team && cvar('mp_teammates_are_enemies') !== '1') { k.kills--; stats.teamkills++; } else k.kills++; }
  event('kill ' + p.ctl.slot + ' by ' + (k ? k.slot : '-'));
  seeEnt(p);
  fire('OnPlayerKill', { player: p, attacker, inflictor, weapon });
  for (const w of p.w) removeEnt(w); p.w = []; p.active = null;
  const c = p.ctl;
  if (!NORESPAWN && (WARMUP || cvar(c._team === 2 ? 'mp_respawn_on_death_t' : 'mp_respawn_on_death_ct') === '1')) later(2, () => respawn(c));
}
let roundOver = false, roundEndAt = ROUND, freezeUntil = +cvar('mp_freezetime'), rounds = 0, winReq = null;
const roundLen = () => (cvar('mp_roundtime') ? +cvar('mp_roundtime') * 60 : ROUND);
const winnerOf = (r) => ([RR.TARGET_BOMBED, RR.HOSTAGES_NOT_RESCUED, RR.TERRORISTS_WIN, RR.CTS_SURRENDER].includes(r) ? 2
  : [RR.TARGET_SAVED, RR.BOMB_DEFUSED, RR.HOSTAGES_RESCUED, RR.CTS_WIN, RR.TERRORISTS_SURRENDER].includes(r) ? 3 : 0);
function endRound(team, reason) {
  roundOver = true; rounds++; count(stats.roundEnds, reason); event('round end ' + team + ' ' + reason);
  fire('OnRoundEnd', { winningTeam: team, reason });
  later(+cvar('mp_round_restart_delay') || 3, restartRound);
}
function restartRound() {
  stats.restarts++; event('round restart');
  fire('OnBeginRoundRestart');
  // map entities respawn (new objects; the old ones go invalid), spawned things and dropped weapons go away
  for (const e of world) if (e._ok && (e._map || e._spawned || e instanceof Grenade || (e instanceof Weapon && !(e._owner && e._owner._ok))) && !PRESERVE.has(e._c)) removeEnt(e);
  for (const d of ENTS) if (!PRESERVE.has(d.cls)) addMapEnt(d);
  roundOver = false; winReq = null; roundEndAt = time + roundLen(); freezeUntil = time + (+cvar('mp_freezetime') || 0);
  for (const c of players) if (c && c._ok && c.connected && c._team >= 2) {
    let p = c.pawn; if (!p || !p._ok) p = c.pawn = add(new Pawn(c));
    revive(p); fire('OnPlayerReset', { player: p });
  }
  fire('OnRoundStart');
}
function roundTick() {
  if (roundOver || WARMUP) return;
  if (winReq) { const w = winReq; winReq = null; return endRound(w.team, w.reason); }
  if (cvar('mp_ignore_round_win_conditions') === '1') return;
  if (time >= roundEndAt) { const d = +cvar('mp_default_team_winner_no_objective'); return endRound(d === 2 || d === 3 ? d : 0, d === 2 ? RR.TERRORISTS_WIN : d === 3 ? RR.CTS_WIN : RR.DRAW); }
  const present = [0, 0, 0, 0], alive = [0, 0, 0, 0];
  for (const c of players) if (c && c._ok && c.connected && c._team >= 2) { present[c._team]++; if (c.pawn && c.pawn._ok && c.pawn._alive) alive[c._team]++; }
  if (present[2] && present[3] && (!alive[2] || !alive[3])) endRound(!alive[2] && !alive[3] ? 0 : alive[2] ? 2 : 3, !alive[2] && !alive[3] ? RR.DRAW : alive[2] ? RR.TERRORISTS_WIN : RR.CTS_WIN);
}

// ---------------------------------------------------------------- Instance
const hooks = {}, inputs = {}, conns = new Map(), afterQ = [], timers = [];
let think = null, nextThink = Infinity, connId = 0, timerSeq = 0, asyncPending = false;
const later = (dt, fn) => { timers.push({ at: time + Math.max(0, +dt || 0), seq: timerSeq++, fn }); };
const fmt = (v) => (v === undefined ? '' : ' ' + (typeof v === 'object' ? JSON.stringify(v) : String(v)));
function applyInput(e, input, value, cfg) {
  const i = input.toLowerCase();
  if (i === 'kill' || i === 'killhierarchy') removeEnt(e);
  else if (i === 'skin') { e._skin = +value || 0; seeEnt(e); }
  else if (i === 'alpha' && e._color) { e._color = { ...e._color, a: +value }; seeEnt(e); }
  else if (i === 'color' && e._color) { const c = typeof value === 'string' ? value.split(/\s+/).map(Number) : value ? [value.r, value.g, value.b] : []; if (c.length >= 3) { e._color = { ...e._color, r: c[0], g: c[1], b: c[2] }; seeEnt(e); } }
  else if (i === 'firewincondition' && (e._c === 'info_map_parameters')) { if (!WARMUP && !roundOver) winReq = { team: winnerOf(+value), reason: +value }; }
  else if (i === 'runscriptinput' && e._c === 'point_script' && inputs[value]) safe('input ' + value, () => inputs[value]({ caller: cfg.caller, activator: cfg.activator }));
}
function entFire(targets, label, cfg) {
  const input = String(cfg.input); count(stats.fired, label + '.' + input); event('fire ' + label + '.' + input + fmt(cfg.value));
  const go = () => {
    for (const e of targets()) if (e._ok) applyInput(e, input, cfg.value, cfg);
    if (/^firewincondition$/i.test(input) && !ENTS.length && !WARMUP && !roundOver) winReq = { team: winnerOf(+cfg.value), reason: +cfg.value };   // no entities.json: take any target
  };
  if (cfg.delay > 0) later(cfg.delay, go); else go();
}
function chkTrace(t) { if (!t || typeof t !== 'object') throw new Error('trace needs a config object'); chkV(t.start, 'trace start'); if (t.end) chkV(t.end, 'trace end'); }
function traceRes(t) { const f = Math.random(), s = t.start, e = t.end || s;
  return { didHit: Math.random() < 0.5, fraction: f, end: V(s.x + (e.x - s.x) * f, s.y + (e.y - s.y) * f, s.z + (e.z - s.z) * f), normal: V(0, 0, 1), startedInSolid: false, hitEntity: undefined }; }
let saveData = '';
const Instance = new Proxy({
  Msg(t) { const s = String(t); event('log ' + s.slice(0, 200)); if (process.env.MOCK_VERBOSE) console.log('[Msg]', s); }, DebugScreenText() {}, DebugLine() {}, DebugSphere() {}, DebugBox() {},
  SetSaveData(d) { saveData = String(d); }, GetSaveData() { return saveData; },
  SetThink(cb) { think = cb; }, SetNextThink(t) { if (!Number.isFinite(t)) throw new Error('SetNextThink(' + t + ')'); nextThink = t; },
  QueueAfterThinks(cb) { afterQ.push(cb); },
  Delay(d) { if (!Number.isFinite(d)) throw new Error('Delay(' + d + ')'); return new Promise((r) => later(d, () => { asyncPending = true; r(); })); },
  OnScriptInput(name, cb) { inputs[name] = cb; },
  EntFireAtName(c, input, data, delay) {
    const cfg = c && typeof c === 'object' ? c : { name: c, input, value: data && typeof data === 'object' && 'value' in data ? data.value : data, delay };
    entFire(() => byNameMatch(cfg.name), cfg.name, cfg);
  },
  EntFireAtTarget(c, input, data, delay) {
    const cfg = c && typeof c === 'object' && 'target' in c ? c : { target: c, input, value: data && typeof data === 'object' && 'value' in data ? data.value : data, delay };
    if (!cfg.target || !cfg.target._ok) throw new Error('Invalid entity (EntFireAtTarget ' + (cfg.target && cfg.target._c) + ')');
    entFire(() => [cfg.target], cfg.target._n || cfg.target._c, cfg);
  },
  ConnectOutput(target, output, cb) { if (!target || !target._ok) throw new Error('Invalid entity (ConnectOutput)'); conns.set(++connId, { target, output, cb }); return connId; },
  DisconnectOutput(id) { conns.delete(id); },
  FindEntityByName(n) { return byNameMatch(n)[0]; }, FindEntitiesByName(n) { return byNameMatch(n).slice(); },
  FindEntityByClass(c) { return world.find((e) => e._ok && e._c === c); }, FindEntitiesByClass(c) { return world.filter((e) => e._ok && e._c === c); },
  GetPlayerController(s) { const c = players[s]; return c && c._ok && c.connected ? c : undefined; },
  GetAllPlayerControllers() { return players.filter((c) => c && c._ok); },   // includes disconnected players, as the .d.ts says
  TraceLine(t) { chkTrace(t); return traceRes(t); }, TraceSphere(t) { chkTrace(t); return traceRes(t); }, TraceBox(t) { chkTrace(t); return traceRes(t); },
  TracePlayer(t) { chkTrace(t); const r = traceRes(t); delete r.hitGroup; return r; }, TraceBullet(t) { chkTrace(t); return []; },
  GetTraceHit(s, e) { chkTrace({ start: s, end: e }); return traceRes({ start: s, end: e }); },
  IsDedicatedServer() { return true; }, GetGameTime() { return time; }, IsWarmupPeriod() { return WARMUP; }, IsFreezePeriod() { return time < freezeUntil; }, IsTeamIntroPeriod() { return false; },
  GetGameType() { return 0; }, GetGameMode() { return 0; }, GetMapName() { return 'mock_map'; }, GetRoundsPlayed() { return rounds; },
  GetRoundRemainingTime() { return Math.max(0, roundEndAt - time); }, SetRoundRemainingTime(t) { if (!Number.isFinite(t)) throw new Error('SetRoundRemainingTime(' + t + ')'); roundEndAt = time + t; },
  ServerCommand(cmd) {
    for (const one of String(cmd).split(';')) {
      const [k, ...rest] = one.trim().split(/\s+/); if (!k) continue;
      count(stats.calls, 'ServerCommand ' + k); event('cmd ' + one.trim());
      const v = rest.join(' ').replace(/^"|"$/g, '');
      if (k === 'mp_restartgame') later(+v || 1, () => { roundOver = true; rounds = 0; restartRound(); });
      else if (k !== 'say' && rest.length) cvars[k] = v;
    }
  },
  ClientCommand(slot, cmd) { chkSlot(slot); event('ccmd ' + slot + ' ' + cmd); }, RegisterCheatCommand() {}, AddTeamMoney() {},
  SpawnGrenadeProjectile(cfg) { if (cfg && cfg.position) chkV(cfg.position, 'grenade position', true); if (cfg && cfg.velocity) chkV(cfg.velocity, 'grenade velocity');
    const g = add(new Grenade(cfg ? cfg.type : 0, cfg && cfg.thrower, cfg && cfg.position)); later(2, () => removeEnt(g)); return g; },
}, {
  get(t, k) {
    if (typeof k === 'symbol') return t[k];
    if (k.startsWith('On') && !(k in t)) { if (!API.has(k)) count(stats.notInApi, k); return (cb) => { (hooks[k] = hooks[k] || []).push(cb); }; }
    if (!(k in t)) { if (!API.has(k)) { count(stats.notInApi, k); return () => undefined; } return () => { count(stats.calls, 'unmodelled Instance.' + k); return dflt(k); }; }
    count(stats.calls, k); if (CALLS) cnt('Instance.' + k); return t[k];
  },
});

// ---------------------------------------------------------------- load the script
const stub = { Instance, ...ENUMS, ...CLS };
globalThis.__mock_cs2 = stub;
const stubFile = path.join(os.tmpdir(), 'mock_point_script_stub_' + process.pid + '.mjs');
fs.writeFileSync(stubFile, 'const s = globalThis.__mock_cs2;\nexport const ' + Object.keys(stub).map((k) => `${k} = s.${k}`).join(', ') + ';\n');
const src = fs.readFileSync(SCRIPT, 'utf8').replace(/from\s+["']cs_script\/point_script["']/g, 'from ' + JSON.stringify(pathToFileURL(stubFile).href));
tmpBase = 'mock_' + path.basename(SCRIPT).replace(/\.m?js$/, '') + '_' + process.pid + '.mjs';
const tmp = path.join(os.tmpdir(), tmpBase);
fs.writeFileSync(tmp, src);

let depth = 0, tickMs = 0;
const fail = (what, e) => { stats.errors.push(what + ': ' + (e && e.stack ? e.stack.split('\n').slice(0, 3).join(' | ') : e)); };
function safe(what, fn) {
  const top = depth++ === 0, t0 = top ? clock() : 0;
  try { const r = fn(); if (r && typeof r.then === 'function') { asyncPending = true; r.then(null, (e) => fail(what, e)); } return r; }
  catch (e) { fail(what, e); }
  finally { depth--; if (top) tickMs += clock() - t0; }
}
const fire = (k, ev) => { const a = hooks[k]; if (a) for (const cb of a) safe(k, () => cb(ev)); };
process.on('unhandledRejection', (e) => fail('async', e));

try { await import(pathToFileURL(tmp).href); } catch (e) { console.log('script failed to load:', e.stack ? e.stack.split('\n').slice(0, 3).join(' | ') : e); process.exit(1); }
finally { fs.rmSync(tmp, { force: true }); fs.rmSync(stubFile, { force: true }); }

// ---------------------------------------------------------------- run
fire('OnActivate');
for (let i = 0; i < PLAYERS; i++) { const bot = i % 4 === 3; connect(i, bot, UNASSIGNED && !bot && i % 2 === 1 ? 0 : 2 + (i % 2), false); }
fire('OnRoundStart');
const inputNames = opt('inputs', '') ? opt('inputs').split(',') : null;
const chat = opt('chat', '').split(',').filter(Boolean);
const HOLD = [[IN.FORWARD, 0.02, 0.01], [IN.BACK, 0.003, 0.1], [IN.LEFT, 0.01, 0.05], [IN.RIGHT, 0.01, 0.05], [IN.WALK, 0.002, 0.05], [IN.DUCK, 0.003, 0.05],
  [IN.JUMP, 0.006, 0.3], [IN.USE, 0.004, 0.3], [IN.ATTACK, 0.01, 0.04], [IN.ATTACK2, 0.003, 0.2], [IN.RELOAD, 0.002, 0.4]];
function attack(p) {
  const w = p.active; if (!w || !w._ok) return;
  if (w._type === WT.KNIFE) fire('OnKnifeAttack', { weapon: w, attackType: 0 });
  else if (w._type === WT.GRENADE) {
    const g = add(new Grenade(0, p, V(p._p.x, p._p.y, p._p.z + 64))); p.w = p.w.filter((x) => x !== w); p.active = p.w[0] || null;
    fire('OnGrenadeThrow', { weapon: w, projectile: g }); removeEnt(w); later(2, () => removeEnt(g));
  } else {
    fire('OnGunFire', { weapon: w });
    const y = p._eye.yaw * Math.PI / 180, d = 200 + Math.random() * 1500, hit = mapProps.length && Math.random() < 0.3 ? pick(mapProps) : undefined;
    fire('OnBulletImpact', { weapon: w, position: V(p._p.x + Math.cos(y) * d, p._p.y + Math.sin(y) * d, p._p.z + 40), hitEntity: hit && hit._ok ? hit : undefined });
  }
}
function inputsTick() {
  for (const c of players) {
    if (!c || !c.connected || !c._ok) continue;
    const p = c.pawn; if (!p || !p._ok || !p._alive) continue;
    p.prev = p.keys;
    if (HELD) { let k = p.keys; for (const [b, onP, offP] of HOLD) if (k & b ? Math.random() < offP : Math.random() < onP) k ^= b; p.keys = k; }
    else if (Math.random() < 0.3) p.keys = 1 << Math.floor(Math.random() * 11);
    if (Math.random() < 0.02) p._turn = (Math.random() - 0.5) * 6;
    p._eye.yaw = (p._eye.yaw + p._turn + 360) % 360;
    const j = p.keys & ~p.prev;
    if (j & IN.ATTACK) attack(p);
    if (j & IN.RELOAD && p.active && p.active._type !== WT.KNIFE) fire('OnGunReload', { weapon: p.active });
  }
}
function perSecond() {
  mapProps = world.filter((e) => e._ok && e._map && e instanceof ModelEnt);
  const live = players.filter((c) => c && c._ok && c.connected && c.pawn && c.pawn._ok && c.pawn._alive);
  const a = pick(live), b = pick(live);
  const names = inputNames || Object.keys(inputs);
  if (names.length && a) { const n = pick(names); if (inputs[n]) safe('input ' + n, () => inputs[n]({ caller: mapProps.length ? pick(mapProps) : undefined, activator: a.pawn })); }
  if (a && b && Math.random() < 0.5) hurt(b.pawn, { damage: 25, damageTypes: ENUMS.CSDamageTypes.BULLET, attacker: a.pawn, inflictor: a.pawn, weapon: a.pawn.active || undefined, hitGroup: ENUMS.CSHitGroup.CHEST });
  if (a && chat.length && Math.random() < 0.3) fire('OnPlayerChat', { player: a, text: pick(chat), team: a._team });
  if (a && a.pawn._alive && Math.random() < 0.2) { fire('OnPlayerJump', { player: a.pawn }); fire('OnPlayerLand', { player: a.pawn }); }
  for (const c of live) if (c.pawn.w.length && Math.random() < 0.1) c.pawn.active = pick(c.pawn.w);
  if (tick % 128 === 0 && conns.size) {   // a hooked entity output fires now and then (only while its entity exists)
    const live2 = [...conns.values()].filter((x) => x.target._ok);
    const x = pick(live2); if (x) safe('output ' + x.output, () => x.cb({ caller: x.target, activator: a ? a.pawn : undefined, value: undefined }));
  }
  if (dead > 512) { world = world.filter((e) => e._ok); dead = 0; }
  if (UNASSIGNED && tick === 64 * 10) for (const c of players) if (c && c._ok && c.connected && !c._team) teamChange(c, 2 + (c.slot % 2));   // whoever the script left on no team picks one
}
function churn() {
  const live = players.filter((c) => c && c._ok && c.connected), r = Math.random();
  if (r < 0.5) {   // someone joins: CS2 kicks a bot to make room and the newcomer reuses its slot
    const bots = live.filter((c) => c.bot); let slot = -1;
    if (bots.length) { const v = pick(bots); disconnect(v); stats.churn.kick++; slot = v.slot; }
    else for (let i = 0; i < 64; i++) if (!players[i] || !players[i].connected) { slot = i; break; }
    if (slot < 0) return;
    stats.churn.join++;
    if (SILENT) { connect(slot, false, Math.random() < 0.5 ? 2 : 3, true); return; }
    const c = connect(slot, false, 0, false);
    if (HUDWIPE) loading.add(slot);
    later(2, () => { if (!c._ok || !c.connected || c._team) return; loading.delete(slot); teamChange(c, Math.random() < 0.5 ? 2 : 3); });
  } else if (r < 0.75) {
    const c = pick(live.filter((x) => x.slot !== 0 && x._team >= 2)); if (!c) return;
    stats.churn.swap++; teamChange(c, c._team === 2 ? 3 : 2);
  } else {
    const c = pick(live.filter((x) => !x.bot && x.slot !== 0)); if (c) { disconnect(c); stats.churn.leave++; }
  }
}

const DT = 1 / 64, TICKS = Math.round(SECONDS * 64), churnFrom = Math.min(15, SECONDS / 4);
const times = new Float64Array(TICKS), slow = [];
let ran = 0;
for (tick = 0; tick < TICKS; tick++) {
  time = tick * DT; tickMs = 0;
  inputsTick();
  if (timers.length) {
    const due = timers.filter((t) => t.at <= time + 1e-9).sort((x, y) => x.at - y.at || x.seq - y.seq);
    if (due.length) { const set = new Set(due); for (let i = timers.length - 1; i >= 0; i--) if (set.has(timers[i])) timers.splice(i, 1); for (const t of due) t.fn(); }
  }
  if (think && time >= nextThink - 1e-9) { nextThink = Infinity; safe('think', think); }
  for (let n = 0; afterQ.length && n < 64; n++) for (const cb of afterQ.splice(0)) safe('QueueAfterThinks', cb);
  if (tick % 64 === 0) perSecond();
  roundTick();
  if (CHURN) { if (time > churnFrom && tick % 320 === 0) churn(); }
  else if (tick === Math.floor(TICKS / 2) && players[1]) { const old = players[1]; disconnect(old); connect(1, old.bot, old._team || 3, false); }
  if (asyncPending) { asyncPending = false; const t0 = clock(); await new Promise(setImmediate); tickMs += clock() - t0; }
  times[tick] = tickMs; ran = tick + 1;
  if (tickMs > 16) slow.push(time.toFixed(1) + 's:' + tickMs.toFixed(0) + 'ms');
  if (OBS) traceTick();
  if (stats.errors.length > 20) break;
}
await new Promise(setImmediate); await new Promise(setImmediate);

// ---------------------------------------------------------------- report
const top = (o, n = 15) => Object.entries(o).sort((x, y) => y[1] - x[1]).slice(0, n).map(([k, v]) => k + ' x' + v).join(', ');
const ins = Object.keys(inputs);
const scen = ['held', 'churn', 'silent', 'norespawn', 'warmup', 'unassigned', 'resetfirst', 'hudwipe', 'maskall', 'autoents'].filter(on);
console.log(`ran ${(ran / 64).toFixed(0)}s with ${PLAYERS} players${scen.length ? ' [' + scen.join(' ') + ']' : ''}; hooks: ${Object.keys(hooks).join(', ') || 'none'}; ${ins.length} script inputs${ins.length ? ' (' + ins.slice(0, 12).join(', ') + (ins.length > 12 ? ', ...' : '') + ')' : ''}`);
console.log('Instance calls:', top(stats.calls) || 'none');
console.log('EntFire:', top(stats.fired) || 'none');
const sb = players.filter(Boolean);
console.log(`rounds ended ${rounds} (reasons ${JSON.stringify(stats.roundEnds)}), restarts ${stats.restarts}; kills ${stats.kills} (scoreboard ${sb.reduce((n, c) => n + c.kills, 0)}, teamkill penalties ${stats.teamkills}), script TakeDamage ${stats.scriptDamage}, respawns ${stats.respawns}, team changes ${stats.teamChanges}${CHURN ? ', churn ' + JSON.stringify(stats.churn) : ''}`);
if (Object.keys(stats.unknownEntityCalls).length) console.log('entity methods not modelled (returned a default):', top(stats.unknownEntityCalls));
if (stats.models.size) console.log(`models set (${stats.models.size}):`, [...stats.models].slice(0, 8).join(', ') + (stats.models.size > 8 ? ', ...' : ''));
if (HUD) {
  const used = [...HUD.used.keys()], missing = HUD.classes ? used.filter((c) => !HUD.classes.has(c)) : [], lone = used.filter((c) => HUD.lone.has(c));
  console.log(`HUD: ${stats.hudCalls} calls, ${used.length} classes switched; not in the css: ${missing.join(' ') || 'none'}; with a lone css rule: ${lone.join(' ') || 'none'}${HUDWIPE ? '; changes dropped by loading clients ' + stats.hudDropped : ''}`);
  if (lone.length) flagIt('switched HUD classes with a css rule of their own (the panel takes that rule): ' + lone.join(' '));
}
{
  const w = Math.min(Math.round(WARM * 64), Math.max(0, ran - 64)), t = Array.from(times.subarray(w, ran)).sort((a, b) => a - b);
  const q = (f) => (t.length ? t[Math.min(t.length - 1, Math.floor(t.length * f))] : 0).toFixed(3), avg = t.reduce((a, b) => a + b, 0) / Math.max(1, t.length);
  console.log(`script time after ${(w / 64).toFixed(0)}s: avg ${avg.toFixed(3)} ms/tick, p50 ${q(0.5)}, p90 ${q(0.9)}, p99 ${q(0.99)}, p99.9 ${q(0.999)}, max ${(t[t.length - 1] || 0).toFixed(2)} ms; ticks over 16 ms: ${slow.length}${slow.length ? ' (' + slow.slice(0, 8).join(' ') + ')' : ''}`);
}
if (CALLS) {
  console.log(`engine calls: ${(callTotal / Math.max(1, ran)).toFixed(1)} per tick; top: ` + [...callCount].sort((a, b) => b[1] - a[1]).slice(0, 16).map(([k, v]) => `${k} ${(v / ran).toFixed(2)}`).join(', '));
  if (sites.size) console.log('hot script lines (sampled): ' + [...sites].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([k, v]) => `${k} ${v}`).join(', '));
}
if (OBS) {
  const text = traceOut.join('\n') + '\n';
  let h = 2166136261 >>> 0; for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619) >>> 0;
  if (TRACE !== '1') fs.writeFileSync(TRACE, text);
  console.log(`trace: ${traceOut.length} ticks with changes, hash ${h.toString(16).padStart(8, '0')}${TRACE !== '1' ? ' -> ' + TRACE : ''}`);
}
if (stats.tpRuns) flagIt(`props Teleported 3+ ticks in a row (CS2 doesn't draw them; use Move): ${stats.tpRuns} (${[...stats.tpNames].slice(0, 6).join(', ')})`);
if (stats.tpAuto) console.log(`autoents names Teleported 3+ ticks in a row (a problem only if they are props; give entities.json to check): ${stats.tpAuto} (${[...stats.tpAutoNames].slice(0, 6).join(', ')})`);
if (stats.invalidCalls) console.log('calls on entities that had gone away:', stats.invalidCalls);
if (Object.keys(stats.notInApi).length) stats.errors.push('Instance methods not in point_script.d.ts: ' + Object.keys(stats.notInApi).join(', '));
const probs = [...new Set(stats.problems)];
if (probs.length) console.log('PROBLEMS (' + probs.length + '):\n  ' + probs.slice(0, 10).join('\n  '));
if (stats.errors.length) { const u = [...new Set(stats.errors)]; console.log('ERRORS (' + stats.errors.length + ', ' + u.length + ' distinct):\n  ' + u.slice(0, 10).join('\n  ')); }
if (stats.errors.length || probs.length) process.exit(1);
console.log('OK: no errors');
