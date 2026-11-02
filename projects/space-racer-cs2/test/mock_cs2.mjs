// Runs the real out/addon/maps/scripts/space_racer.js against a stand-in for CS2's cs_script API.
// Simulates players (humans with random input + CS2 bots), the round timer, freeze time, scripted kills and
// respawns, people joining and leaving, and checks the script keeps working.
// usage: node test/mock_cs2.mjs [humans=10] [bots=22] [seconds=400] [opts: v,churn,afk,prof,silent,norespawn,warmup,hudstats,4x16,alt,track=<id>,
//        held,seed=<n>,trace=<file>,calls]
//   held: humans hold keys like people do (throttle on, boost in bursts, spectators click now and then) - use for timing
//   seed=<n>: repeatable run (mock randomness and the script's seed); trace=<file>: write what each tick changed on
//   screen (HUD classes / texts, props, cameras, sounds, kills) so two builds can be compared line by line;
//   calls: count the script's engine calls per tick (each crosses into CS2 and many are networked)
//   SPR_SCRIPT=<file> runs another build of the script; vm: run it in a vm context (slower, the old harness)
//   silent: churn without disconnect events (slots change hands unannounced); norespawn: CS2 never respawns killed
//   players; warmup: the whole run is warmup (FireWinCondition ends nothing)
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const HUMANS = +(process.argv[2] || 10), BOTS = +(process.argv[3] || 22), SECONDS = +(process.argv[4] || 400);
const OPTS = process.argv[5] || '';
const NAME = process.env.SPR_NAME || ({ neon: 'neon_racer', depth: 'depth_racer' }[process.env.SPR_THEME] || 'space_racer');

const CSInputs = { NONE: 0, FORWARD: 1, BACK: 2, LEFT: 4, RIGHT: 8, WALK: 16, DUCK: 32, JUMP: 64, USE: 128, ATTACK: 256, ATTACK2: 512, RELOAD: 1024, SHOW_SCORES: 2048, LOOK_AT_WEAPON: 4096 };
const CustomCameraMode = { DISABLED: 0, CONTROLLED: 1, CONTROLLED_POSITION: 2, FOLLOW_POSITION: 3 };
const CSRoundEndReason = { UNKNOWN: -1, IN_PROGRESS: 0, GAME_COMMENCING: 1, DRAW: 2, CTS_WIN: 8, TERRORISTS_WIN: 9 };
const CSMoveType = { INVALID: -1, NONE: 0, WALK: 1, FLYGRAVITY: 2, VPHYSICS: 3, NOCLIP: 4, OBSERVER: 5, LADDER: 6, CUSTOM: 7 };
const CSDamageTypes = { GENERIC: 0, BULLET: 2, VEHICLE: 16, BLAST: 64 };
const CSDamageFlags = { NONE: 0, PREVENT_DEATH: 8, FORCE_DEATH: 16, IGNORE_ARMOR: 64 };

let time = 0;
const SEED = +((OPTS.match(/seed=(\d+)/) || [])[1] || 0);
if (SEED) { let st = SEED >>> 0; Math.random = () => { st = (st + 0x6D2B79F5) >>> 0; let t = st; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const FakeDate = SEED ? { now: () => 1700000000000 + SEED } : Date;
const TRACE = (OPTS.match(/trace=([^,]+)/) || [])[1];
const traceOut = [];
// observable state, so builds can be compared by what ends up on screen rather than by the calls that got it there
const obs = { hud: new Map(), vars: new Map(), ents: new Map(), events: [] };
const dirty = new Map();      // 'h'|'v'|'e' + key -> value at the start of this tick
const ser = (kind, key) => { if (kind === 'h') { const v = obs.hud.get(key); return v ? [...v].sort().join(' ') : ''; } if (kind === 'v') return obs.vars.get(key) ?? ''; return obs.ents.get(key) ?? ''; };
function touch(kind, key) { const k = kind + key; if (!dirty.has(k)) dirty.set(k, ser(kind, key)); }
const r1 = (v) => (Math.round(v * 100) / 100).toFixed(2);
function entState(e) { const p = e.pos, a = e.ang; return `${r1(p.x)},${r1(p.y)},${r1(p.z)} ${r1(a.pitch)},${r1(a.yaw)},${r1(a.roll)} ${e.model || ''} ${e.skin ?? ''} ${e.color ? e.color.a : ''}${e.glow ? ' glow ' + e.glow : ''}`; }
function entKey(e) { return e.cls === 'camera' ? 'cam' + e.pawn.ctrl.slot : e.cls === 'player' ? 'pawn' + e.ctrl.slot : e.name; }
function obsEnt(e) { if (!TRACE) return; const k = entKey(e); touch('e', k); obs.ents.set(k, entState(e)); }
function traceTick() {
  const lines = [];
  for (const [k, before] of dirty) { const now = ser(k[0], k.slice(1)); if (now !== before) lines.push(k + ' = ' + now); }
  dirty.clear();
  lines.sort();
  for (const e of obs.events.sort()) lines.push('! ' + e);
  obs.events.length = 0;
  if (lines.length) traceOut.push('t' + Math.round(time * 64) + '\n' + lines.join('\n'));
}
const stats = { teamkills: 0, churn: { join: 0, kick: 0, swap: 0, leave: 0 }, moves: 0, teleports: 0, setModel: 0, hudCalls: 0, hudVars: 0, sounds: 0, skins: 0, spawned: 0, kills: 0, scriptKills: 0, errors: [], msgs: [], cvars: {}, says: [], camMoves: 0, badPos: 0 };
const models = new Set();
for (const f of walk(path.join(root, 'out/addon/models'))) if (f.endsWith('.vmdl')) models.add(path.relative(path.join(root, 'out/addon'), f).replace(/\\/g, '/'));
function* walk(dir) { for (const e of fs.readdirSync(dir, { withFileTypes: true })) { const p = path.join(dir, e.name); if (e.isDirectory()) yield* walk(p); else yield p; } }

class Entity {
  constructor(name, cls, pos) { this.name = name; this.cls = cls; this.pos = pos || { x: 0, y: 0, z: 0 }; this.ang = { pitch: 0, yaw: 0, roll: 0 }; this.valid = true; }
  IsValid() { return this.valid; }
  GetAbsOrigin() { return { ...this.pos }; }
  GetAbsAngles() { return { ...this.ang }; }
  GetEntityName() { return this.name; }
  SetEntityName(n) { this.name = n; }
  GetClassName() { return this.cls; }
  Teleport(o) {
    stats.teleports++;
    // CS2 stops drawing a prop that is teleported every tick: count runs of 3+ ticks in a row
    const tk = Math.round(time * 64);
    if (this.tpTick === tk - 1) { this.tpRun = (this.tpRun || 0) + 1; if (this.tpRun === 2) stats.tpRuns = (stats.tpRuns || 0) + 1; } else this.tpRun = 0;
    this.tpTick = tk;
    if (o.position) this.pos = { ...o.position }; if (o.angles) this.ang = { ...o.angles }; check(o.position, o.angles); obsEnt(this);
  }
  Move(o) { stats.moves++; if (o.position) this.pos = { ...o.position }; if (o.angles) this.ang = { ...o.angles }; check(o.position, o.angles); obsEnt(this); }
  SetModel(m) { stats.setModel++; if (!models.has(m)) throw new Error('missing model ' + m); this.model = m; obsEnt(this); }
  SetColor(c) { this.color = c; obsEnt(this); }
  Glow(c) { this.glow = c ? c.r + ',' + c.g + ',' + c.b : 'on'; stats.glows = (stats.glows || 0) + 1; obsEnt(this); }
  Unglow() { this.glow = ''; obsEnt(this); }
  IsGlowing() { return !!this.glow; }
  SetParent(p) { this.parent = p; }
  Kill() { this.valid = false; }
  Remove() { this.valid = false; }
}
function check(p, a) {
  if (p && [p.x, p.y, p.z].some((v) => !Number.isFinite(v) || Math.abs(v) > 16384)) { stats.badPos++; throw new Error('bad position ' + JSON.stringify(p)); }
  if (a && [a.pitch, a.yaw, a.roll].some((v) => !Number.isFinite(v))) throw new Error('bad angles ' + JSON.stringify(a));
}

const world = new Map();
function addEnt(e) { world.set(e.name, e); return e; }
const spawnedEnts = [];
class PointTemplate extends Entity { ForceSpawn(pos) { stats.spawned++; const e = new Entity('tplspawn' + stats.spawned, 'prop_dynamic', pos); spawnedEnts.push(e); return [e]; } }
const hudIds = new Set(JSON.parse(fs.readFileSync(path.join(root, 'out/addon/_gen/hud_ids.json'), 'utf8')));
const hudCss = fs.readFileSync(path.join(root, `out/addon/panorama/styles/custom_game/${NAME}.css`), 'utf8');
const classesUsed = new Map();
const rootCls = new Map();      // slot -> the state classes on spr_root right now (stRes = results board, stPick = car picker)
const resStart = new Map();     // slot -> when their results board last came up
class CustomHudLayout extends Entity {
  SetHasClassForPlayer(slot, panel, cls, on) {
    if (panel === 'spr_root') {
      let s = rootCls.get(slot); if (!s) rootCls.set(slot, s = new Set());
      if (on) s.add(cls); else s.delete(cls);
      if (on && cls === 'stRes') resStart.set(slot, time);
    }
    if (TRACE) { const k = slot + '|' + panel; touch('h', k); let set = obs.hud.get(k); if (!set) obs.hud.set(k, set = new Set()); if (on) set.add(cls); else set.delete(cls); }
    stats.hudCalls++; if (OPTS.includes('hudstats')) { const pk = panel.replace(/_\d+$/, '').replace(/\d+$/, ''); (stats.hudBy ||= {})[pk] = (stats.hudBy[pk] || 0) + 1; } if (OPTS.includes('hudtrace') && slot === 0 && (pk === 'spr_lap' || pk === 'spr_sub') && on && time > 60 && time < 64) console.log('t', time.toFixed(2), panel, cls); if (!hudIds.has(panel)) throw new Error('unknown HUD panel ' + panel); classesUsed.set(cls, (classesUsed.get(cls) || 0) + 1); }
  SetDialogVariableStringForPlayer(slot, panel, name, value) { stats.hudVars++; if (TRACE) { touch('v', slot + '|' + panel); obs.vars.set(slot + '|' + panel, value); } if (!hudIds.has(panel)) throw new Error('unknown HUD panel ' + panel); if (typeof value !== 'string') throw new Error('non-string dialog var'); }
  ResetForPlayer(slot) { rootCls.delete(slot); if (TRACE) { for (const k of [...obs.hud.keys()]) if (k.startsWith(slot + '|')) { touch('h', k); obs.hud.delete(k); } for (const k of [...obs.vars.keys()]) if (k.startsWith(slot + '|')) { touch('v', k); obs.vars.delete(k); } } }
}
const ents = JSON.parse(fs.readFileSync(path.join(root, 'build/entities.json'), 'utf8'));
for (const e of ents) {
  if (!e.targetname) continue;
  const pos = { x: e.origin[0], y: e.origin[1], z: e.origin[2] };
  if (e.classname === 'point_template') addEnt(new PointTemplate(e.targetname, e.classname, pos));
  else if (e.classname === 'custom_hud_layout') addEnt(new CustomHudLayout(e.targetname, e.classname, pos));
  else addEnt(new Entity(e.targetname, e.classname, pos));
}

// ---------------------------------------------------------------- players
const cvar = (k) => stats.cvars[k];
class Camera extends Entity { constructor(p) { super('cam', 'camera'); this.mode = 0; this.pawn = p; } SetMode(m) { this.mode = m; if (TRACE) obs.events.push('cammode ' + this.pawn.ctrl.slot + ' ' + m); } GetMode() { return this.mode; } GetPlayer() { return this.pawn; } SetFollowConfig() {} Move(o) { stats.camMoves++; check(o.position, o.angles); if (o.position) this.pos = { ...o.position }; if (o.angles) this.ang = { ...o.angles }; obsEnt(this); } }
class Pawn extends Entity {
  constructor(ctrl) { super('pawn' + ctrl.slot, 'player'); this.ctrl = ctrl; this.alive = true; this.buttons = 0; this.prev = 0; this.eye = { pitch: 0, yaw: Math.random() * 360, roll: 0 }; this.cam = null; this.movetype = 1; }
  GetPlayerController() { return this.ctrl; }
  GetOriginalPlayerController() { return this.ctrl; }
  IsAlive() { return this.alive; }
  // a mask of several keys means "any of them" (CS2's likely behaviour); maskall = "all of them" to test the fallback
  IsInputPressed(b) { return OPTS.includes('maskall') ? (this.buttons & b) === b : !!(this.buttons & b); }
  WasInputJustPressed(b) { const j = this.buttons & ~this.prev & b; return OPTS.includes('maskall') ? j === b : j !== 0; }
  WasInputJustReleased(b) { return !(this.buttons & b) && !!(this.prev & b); }
  GetEyeAngles() { return { ...this.eye }; }
  SetEyeAngles(a) { this.eye = { ...a }; }
  SetMoveType(t) { this.movetype = t; }
  DestroyWeapons() {}
  GetCustomCamera() { if (!this.cam) this.cam = new Camera(this); return this.cam; }
  TakeDamage(d) {
    if (!this.alive) return 0;
    const r = hooks.OnModifyPlayerDamage && hooks.OnModifyPlayerDamage({ player: this, damage: d.damage, attacker: d.attacker });
    if (r && r.abort) return 0;
    stats.scriptKills++; if (TRACE) obs.events.push('kill ' + this.ctrl.slot + ' by ' + (d.attacker && d.attacker.ctrl ? d.attacker.ctrl.slot : d.attacker instanceof Controller ? d.attacker.slot : '-'));
    this.die(d.attacker);
    return d.damage;
  }
  die(attacker) {
    this.alive = false; this.valid = false;
    stats.kills++;
    const k = attacker && attacker.ctrl ? attacker.ctrl : attacker instanceof Controller ? attacker : null;
    this.ctrl.deaths++;
    if (k && k !== this.ctrl) {
      if (k.team === this.ctrl.team && cvar('mp_teammates_are_enemies') !== '1') { k.kills--; stats.teamkills++; }
      else k.kills++;
    }
    hooks.OnPlayerKill && hooks.OnPlayerKill({ player: this, attacker });
    const respawn = !OPTS.includes('norespawn') && cvar(this.ctrl.team === 2 ? 'mp_respawn_on_death_t' : 'mp_respawn_on_death_ct') === '1';
    if (respawn) later(1.5, () => this.ctrl.respawn());
  }
}
class Controller {
  constructor(slot, name, team, bot, noPawn) { this.slot = slot; this.name = name; this.team = team; this.bot = bot; this.connected = true; this.pawn = noPawn ? null : new Pawn(this); this.score = 0; this.kills = 0; this.deaths = 0; this.brain = { steer: 0, t: 0 }; }
  GetPlayerSlot() { return this.slot; } GetPlayerName() { return this.name; } GetPlayerPawn() { return this.pawn && this.pawn.valid ? this.pawn : undefined; }
  IsBot() { return this.bot; } IsConnected() { return this.connected; } GetTeamNumber() { return this.team; }
  AddScore(n) { this.score += n; } GetScore() { return this.score || 0; } JoinTeam(t) {
    // like CS2: the team changes, the team-change event fires, and the player spawns a moment later
    if (this.team === t) return;
    this.team = t; stats.autoTeams = (stats.autoTeams || 0) + 1;
    if (this.pawn) { this.pawn.alive = false; this.pawn.valid = false; }
    hooks.OnPlayerTeamChanged && hooks.OnPlayerTeamChanged({ player: this, newTeam: t });
    later(1, () => this.respawn());
  } IsValid() { return this.connected; }
  respawn() { if (!this.connected) return; this.pawn = new Pawn(this); hooks.OnPlayerReset && hooks.OnPlayerReset({ player: this.pawn }); }
}
const players = [];
// unassigned: every other human starts on no team, with no pawn (CS2's team menu at map load)
for (let i = 0; i < HUMANS + BOTS; i++) {
  const un = OPTS.includes('unassigned') && i < HUMANS && i % 2 === 1;
  players.push(new Controller(i, (i < HUMANS ? 'human' : 'bot') + i, un ? 0 : i % 2 ? 3 : 2, i >= HUMANS, un));
}

// ---------------------------------------------------------------- Instance
const hooks = {};
let thinkFn = null, nextThink = 0;
const timers = [];
function later(dt, fn) { timers.push({ at: time + dt, fn }); }
let freezeUntil = 2, roundEnd = 600, roundEnded = false, warmup = OPTS.includes('warmup'), winFired = null; const winReasons = {};
const Instance = {
  Msg: (m) => { const s = String(m); stats.msgs.push(s); if (/error|WARNING/.test(s)) stats.errors.push(s); if (OPTS.includes('v')) console.log(s); },
  GetGameTime: () => time,
  SetThink: (fn) => { thinkFn = fn; },
  SetNextThink: (t) => { nextThink = t; },
  Delay: (s) => new Promise((res) => later(s, res)),
  OnActivate: (f) => { hooks.OnActivate = f; },
  OnScriptReload: () => {},
  OnRoundStart: (f) => { hooks.OnRoundStart = f; }, OnRoundEnd: (f) => { hooks.OnRoundEnd = f; }, OnBeginRoundRestart: (f) => { hooks.OnBeginRoundRestart = f; },
  OnPlayerDisconnect: (f) => { hooks.OnPlayerDisconnect = f; }, OnPlayerActivate: (f) => { hooks.OnPlayerActivate = f; },
  OnPlayerTeamChanged: (f) => { hooks.OnPlayerTeamChanged = f; }, OnPlayerReset: (f) => { hooks.OnPlayerReset = f; }, OnPlayerKill: (f) => { hooks.OnPlayerKill = f; },
  OnModifyPlayerDamage: (f) => { hooks.OnModifyPlayerDamage = f; }, OnPlayerChat: (f) => { hooks.OnPlayerChat = f; },
  FindEntityByName: (n) => world.get(n),
  FindEntitiesByName: (n) => (world.get(n) ? [world.get(n)] : []),
  GetAllPlayerControllers: () => players.filter((p) => p.connected),
  GetPlayerController: (s) => players.find((p) => p.slot === s && p.connected),
  ServerCommand: (c) => { if (TRACE) obs.events.push('cmd ' + c); const [k, v] = c.split(' '); if (k === 'say') stats.says.push(c.slice(4)); else stats.cvars[k] = v; },
  ClientCommand: () => {},
  EntFireAtTarget: ({ target, input, value }) => {
    if (input === 'Skin') { stats.skins++; target.skin = value; obsEnt(target); }
    else if (input === 'StartSound') { stats.sounds++; if (TRACE) obs.events.push('snd ' + target.name + ' ' + (target.src || '')); if (!target.name.startsWith('spr_snd_')) throw new Error('sound on ' + target.name); }
    else if (input === 'StopSound') { stats.stops = (stats.stops || 0) + 1; if (!target.name.startsWith('spr_snd_mus_')) throw new Error('stop on ' + target.name); }
    else if (input === 'SetSourceEntity') { target.src = value; if (!spawnedEnts.some((e) => e.name === value)) throw new Error('unknown sound source ' + value); }
    else throw new Error('unexpected input ' + input);
  },
  EntFireAtName: ({ name, input, value }) => { if (input === 'FireWinCondition') { winFired = value; roundEnd = time; } },
  IsFreezePeriod: () => time < freezeUntil,
  IsWarmupPeriod: () => warmup,
  GetRoundRemainingTime: () => roundEnd - time,
  SetRoundRemainingTime: (t) => { roundEnd = time + t; },
};
const api = { Instance, CSInputs, CustomCameraMode, CSMoveType, CSRoundEndReason, CSDamageTypes, CSDamageFlags, CSPlayerPawn: Pawn, CSPlayerController: Controller, BaseModelEntity: Entity, PointTemplate, CustomHudLayout, Entity };

let src = fs.readFileSync(process.env.SPR_SCRIPT || path.join(root, `out/addon/maps/scripts/${NAME}.js`), 'utf8');
src = src.replace(/^import \{[^}]+\} from "cs_script\/point_script";/m, 'const { Instance, CSInputs, CSPlayerPawn, CSPlayerController, BaseModelEntity, PointTemplate, CustomHudLayout, CSDamageFlags, CSDamageTypes, CustomCameraMode, CSMoveType, CSRoundEndReason, Entity } = __api;');
if (OPTS.includes('4x16')) src = src.replace("ARENA_LAYOUT: '2x32'", "ARENA_LAYOUT: '4x16'");
if (OPTS.includes('alt')) src = src.replace("ARENA_LAYOUT: '2x32'", "ARENA_LAYOUT: 'alternate'");
// track=<id>: race only that track (every other one blacklisted)
const onlyTrack = (OPTS.match(/track=(\w+)/) || [])[1];
if (onlyTrack) {
  const ids = JSON.parse(fs.readFileSync(path.join(root, 'out/addon/_gen/tracks.json'), 'utf8')).map((t) => t.id).filter((id) => id !== onlyTrack);
  src = src.replace('TRACK_BLACKLIST: [],', 'TRACK_BLACKLIST: ' + JSON.stringify(ids) + ',');
}
src += '\nglobalThis.__dbg = () => ({ rm, views, parked, phase });\n';
// CS2 runs the script as a module: its top-level functions and classes are module locals and the built-ins are plain
// globals. A vm context would route every global lookup (Math, every top-level function) through the context's
// interceptor and make the timings several times too slow, so the script runs here as one function in this context
// (OPTS vm = the old way).
let ctx;
if (OPTS.includes('vm')) {
  ctx = vm.createContext({ __api: api, console, Math, Date: FakeDate, JSON, Map, Set, Array, Object, String, Number, Error, Infinity, NaN, Promise, performance });
  vm.runInContext(src, ctx, { filename: NAME + '.js' });
} else {
  new Function('__api', 'Date', src + '\n//# sourceURL=' + NAME + '.js')(api, FakeDate);
  ctx = globalThis;
}

// ---------------------------------------------------------------- calls on an entity that has gone away throw, as in CS2
for (const C of [Entity, Pawn, Camera]) for (const k of Object.getOwnPropertyNames(C.prototype)) {
  if (k === 'constructor' || k === 'IsValid' || !/^[A-Z]/.test(k)) continue;
  const f = C.prototype[k];
  if (typeof f !== 'function') continue;
  C.prototype[k] = function (...a) { if (!this.valid) { stats.invalidCalls = (stats.invalidCalls || 0) + 1; throw new Error('Invalid entity (' + k + ')'); } return f.apply(this, a); };
}

// ---------------------------------------------------------------- engine call counting (calls)
const calls = new Map();
let callsTotal = 0;
if (OPTS.includes('calls')) {
  const wrap = (obj, label) => { for (const k of Object.getOwnPropertyNames(obj)) {
    if (k === 'constructor' || !/^[A-Z]/.test(k)) continue;
    const d = Object.getOwnPropertyDescriptor(obj, k); if (!d || typeof d.value !== 'function') continue;
    const f = d.value, name = label + '.' + k;
    obj[k] = function (...a) { if (inThink) { callsTotal++; calls.set(name, (calls.get(name) || 0) + 1); } return f.apply(this, a); };
  } };
  for (const [C, l] of [[Entity, 'Entity'], [Pawn, 'Pawn'], [Camera, 'Camera'], [CustomHudLayout, 'Hud'], [PointTemplate, 'Template'], [Controller, 'Controller']]) wrap(C.prototype, l);
  wrap(Instance, 'Instance');
}
let inThink = false;

// ---------------------------------------------------------------- run
const TICK = 1 / 64;
hooks.OnActivate();
let rounds = 0;
const t0 = Date.now();
let thinkMs = 0, maxThink = 0;
const CHATS = { 5: '!shade', 6: '!shade 4', 7: '!shade rose', 8: '!vote', 135: '!vote 2', 136: '!vote helix', 12: '!car 3', 16: '!car', 18: '!cam', 20: '!cam near', 22: '!tilt', 23: '!tilt', 25: '!race', 28: '!crt', 29: '!crt', 32: '!music',
  40: '!car meteor', 70: '!spec', 90: '!back', 100: '/car', 130: '!afk', 150: '!back', 170: '!pick', 175: '!car 2', 230: '/pick', 290: '!car' };
const phases = {};
// the car picker must never sit over the results board unless that player asked for it (!car / /car / !pick) since
// the board came up
const asked = new Map(), picker = { overResults: 0, askedOverResults: 0, ticks: new Map() };
while (time < SECONDS) {
  time += TICK;
  for (const [at, text] of Object.entries(CHATS)) if (Math.abs(time - +at) < TICK / 2 && players[0] && hooks.OnPlayerChat) {
    if (/^[!/](car|pick)$/.test(text)) asked.set(0, time);
    hooks.OnPlayerChat({ player: players[0], text, team: 0 });
  }
  for (const c of players) {
    const s = !c.bot && c.connected && rootCls.get(c.slot);
    if (!s || !s.has('stPick')) continue;
    picker.ticks.set(c.slot, (picker.ticks.get(c.slot) || 0) + 1);
    if (s.has('stRes')) { if ((asked.get(c.slot) ?? -99) >= (resStart.get(c.slot) ?? 0)) picker.askedOverResults++; else picker.overResults++; }
  }
  // fake human input: drive forward, wobble the steering, boost and spin now and then, pick cars in the lobby
  for (const c of players) {
    const p = c.pawn;
    if (!p || !p.valid || c.bot) continue;
    p.prev = p.buttons;
    const b = c.brain;
    if (Math.random() < 0.05) b.steer = Math.floor(Math.random() * 3) - 1;
    let bt = CSInputs.FORWARD;
    if (b.steer < 0) bt |= CSInputs.LEFT; if (b.steer > 0) bt |= CSInputs.RIGHT;
    if (OPTS.includes('held')) {
      // people hold keys: boost and drift in bursts of a second or two, a spin / E / click every few seconds
      if (Math.random() < 0.012) b.boost = !b.boost;
      if (Math.random() < 0.01) b.drift = !b.drift;
      if (b.boost) bt |= CSInputs.ATTACK; if (b.drift) bt |= CSInputs.JUMP;
      if (Math.random() < 0.004) bt |= CSInputs.ATTACK2;
      if (Math.random() < 0.003) bt |= CSInputs.USE;
      if (Math.random() < 0.004) bt |= CSInputs.BACK;     // (S: brakes in a race, moves a vote after one)
    } else {
    if (Math.random() < 0.3) bt |= CSInputs.ATTACK;
    if (Math.random() < 0.01) bt |= CSInputs.ATTACK2;
    if (Math.random() < 0.05) bt |= CSInputs.JUMP;
    if (Math.random() < 0.02) bt |= CSInputs.USE;
    }
    if (OPTS.includes('afk') && c.slot === 0) bt = 0;
    p.buttons = bt;
  }
  for (let i = timers.length - 1; i >= 0; i--) if (timers[i].at <= time) { const t = timers.splice(i, 1)[0]; t.fn(); }
  if (warmup) winFired = null;     // in warmup FireWinCondition ends nothing
  if (!roundEnded && !warmup && time >= roundEnd && (winFired !== null || cvar('mp_ignore_round_win_conditions') !== '1')) {
    roundEnded = true; rounds++; winReasons[winFired] = (winReasons[winFired] || 0) + 1;
    hooks.OnRoundEnd && hooks.OnRoundEnd({ winningTeam: winFired === 9 ? 2 : winFired === 8 ? 3 : 0, reason: winFired === null ? 0 : winFired }); winFired = null;
    later(3, () => {
      hooks.OnBeginRoundRestart && hooks.OnBeginRoundRestart();
      for (const e of spawnedEnts) e.valid = false;
      spawnedEnts.length = 0;
      for (const c of players) if (c.connected) { c.pawn = new Pawn(c); hooks.OnPlayerReset && hooks.OnPlayerReset({ player: c.pawn }); }
      freezeUntil = time + 2; roundEnd = time + 600; roundEnded = false;
      hooks.OnRoundStart && hooks.OnRoundStart();
    });
  }
  if (thinkFn && nextThink <= time + 1e-9) {
    const s = performance.now();
    inThink = true;
    try { thinkFn(); } catch (err) { inThink = false; stats.errors.push('THROW ' + err.stack); break; }
    inThink = false;
    const d = performance.now() - s; (stats.thinkTimes ||= []).push(d); if (process.env.SPR_TICKLOG) (stats.tickLog ||= []).push(time.toFixed(3) + ' ' + d.toFixed(3) + ' ' + ctx.__dbg().phase); thinkMs += d; maxThink = Math.max(maxThink, d);
    if (d > 16) (stats.slow ||= []).push(`${time.toFixed(1)}s:${d.toFixed(0)}ms`);
  }
  if (Math.floor(time) !== Math.floor(time - TICK)) { const ph = ctx.__dbg().phase; phases[ph] = (phases[ph] || 0) + 1; }
  if (OPTS.includes('churn') && time > 15 && Math.floor(time / 5) !== Math.floor((time - TICK) / 5)) churn();
  if (TRACE) traceTick();
}
if (TRACE) fs.writeFileSync(TRACE, traceOut.join('\n') + '\n');
if (process.env.SPR_TICKLOG) fs.writeFileSync(process.env.SPR_TICKLOG, stats.tickLog.join('\n') + '\n');
function disconnect(c) { c.connected = false; if (c.pawn) c.pawn.valid = false; if (!OPTS.includes('silent')) hooks.OnPlayerDisconnect && hooks.OnPlayerDisconnect({ playerSlot: c.slot }); }
function churn() {
  const live = players.filter((c) => c.connected);
  const r = Math.random();
  if (r < 0.5) {
    const bots = live.filter((c) => c.bot);
    let slot = -1;
    if (bots.length) { const victim = bots[Math.floor(Math.random() * bots.length)]; disconnect(victim); stats.churn.kick++; slot = victim.slot; }
    else { const used = new Set(live.map((c) => c.slot)); for (let i = 0; i < 64; i++) if (!used.has(i)) { slot = i; break; } }
    if (slot < 0) return;
    const c = new Controller(slot, 'late' + slot + '_' + stats.churn.join, 0, false, true);
    players.push(c); stats.churn.join++;
    if (OPTS.includes('silent')) {
      // unannounced: the newcomer is already on a team with a pawn when the script next looks
      c.team = Math.random() < 0.5 ? 2 : 3; c.pawn = new Pawn(c); c.joinedAt = time;
    } else {
      hooks.OnPlayerActivate && hooks.OnPlayerActivate({ player: c });
      later(2, () => { if (!c.connected || c.team !== 0) return; c.team = Math.random() < 0.5 ? 2 : 3; hooks.OnPlayerTeamChanged && hooks.OnPlayerTeamChanged({ player: c, newTeam: c.team }); later(1, () => c.respawn()); });
    }
  } else if (r < 0.75) {
    const humans = live.filter((c) => !c.bot && c.slot !== 0);
    const c = humans[Math.floor(Math.random() * humans.length)];
    if (!c) return;
    stats.churn.swap++;
    if (c.pawn) { c.pawn.alive = false; c.pawn.valid = false; }
    c.team = c.team === 2 ? 3 : 2;
    hooks.OnPlayerTeamChanged && hooks.OnPlayerTeamChanged({ player: c, newTeam: c.team });
    later(1, () => c.respawn());
  } else {
    const humans = live.filter((c) => !c.bot && c.slot !== 0);
    const c = humans[Math.floor(Math.random() * humans.length)];
    if (c) { disconnect(c); stats.churn.leave++; }
  }
}
const cams = players.filter((c) => c.pawn && c.pawn.cam).map((c) => c.pawn.cam.mode);
console.log('round end reasons', JSON.stringify(winReasons), 'phases (s)', JSON.stringify(phases));
console.log(`simulated ${SECONDS}s with ${HUMANS} humans + ${BOTS} bots: ${rounds} CS2 rounds ended`);
console.log(`props spawned ${stats.spawned}, moves ${stats.moves}, teleports ${stats.teleports}, setModel ${stats.setModel}, skins ${stats.skins}, hud class calls ${stats.hudCalls}, hud vars ${stats.hudVars}, sounds ${stats.sounds}, camera moves ${stats.camMoves}`);
console.log(`CS2 kills ${stats.kills} (scripted ${stats.scriptKills}), camera modes ${JSON.stringify(cams.slice(0, 12))}`);
console.log(`think time: avg ${(thinkMs / (SECONDS * 64)).toFixed(3)} ms, max ${maxThink.toFixed(1)} ms; ticks over 16 ms: ${(stats.slow || []).length} ${(stats.slow || []).slice(0, 8).join(' ')}`);
{ const tt = (stats.thinkTimes || []).slice().sort((a, b) => a - b); const q = (f) => (tt[Math.min(tt.length - 1, Math.floor(tt.length * f))] || 0).toFixed(2); console.log(`think time percentiles: p50 ${q(0.5)} ms, p90 ${q(0.9)} ms, p99 ${q(0.99)} ms, p99.9 ${q(0.999)} ms`);
  // after warm-up (the first rounds include V8 compiling the script): what a server sees for the rest of the map
  const W = +((OPTS.match(/warm=(\d+)/) || [])[1] || 240) * 64, wt = (stats.thinkTimes || []).slice(W);
  if (wt.length > 64 * 60) { const avg = wt.reduce((a, b) => a + b, 0) / wt.length; wt.sort((a, b) => a - b); const qq = (f) => (wt[Math.min(wt.length - 1, Math.floor(wt.length * f))] || 0).toFixed(2);
    console.log(`think time after ${W / 64} s: avg ${avg.toFixed(3)} ms, p50 ${qq(0.5)}, p90 ${qq(0.9)}, p99 ${qq(0.99)}, p99.9 ${qq(0.999)}, max ${wt[wt.length - 1].toFixed(2)} ms`); } }
if (OPTS.includes('calls')) console.log(`engine calls: ${(callsTotal / (SECONDS * 64)).toFixed(1)} per tick; top: ` + [...calls].sort((a, b) => b[1] - a[1]).slice(0, 16).map(([k, v]) => `${k} ${(v / (SECONDS * 64)).toFixed(1)}`).join(', '));
console.log('cvars', JSON.stringify(stats.cvars));
console.log('says:', stats.says.slice(0, 10).join('\n      '));
const live = players.filter((c) => c.connected);
console.log(`scoreboard kills ${players.reduce((n, c) => n + c.kills, 0)} deaths ${players.reduce((n, c) => n + c.deaths, 0)} (teamkill penalties ${stats.teamkills}), connected ${live.length} (${live.filter((c) => !c.bot).length} humans), churn ${JSON.stringify(stats.churn)}`);
const unknownCls = [...classesUsed.keys()].filter((c) => c && !hudCss.includes('.' + c));
if (OPTS.includes('hudstats')) console.log('HUD calls by panel:', JSON.stringify(Object.entries(stats.hudBy || {}).sort((a, b) => b[1] - a[1]).slice(0, 14)));
console.log('HUD classes not in the css:', unknownCls.join(' ') || 'none');
// a class the script switches must not have a lone rule of its own (".Pick { }"): the panel would take that rule's layout
const loneCls = [...classesUsed.keys()].filter((c) => c && new RegExp('(^|\\n)\\.' + c + ' \\{').test(hudCss));
console.log('switched HUD classes with a rule of their own:', loneCls.join(' ') || 'none');
if (loneCls.length) stats.errors.push('HUD state classes collide with panel classes: ' + loneCls.join(' '));
console.log(`car picker: up ${((picker.ticks.get(0) || 0) / 64).toFixed(1)} s for the player typing !car, ${([...picker.ticks].filter(([k]) => k !== 0).reduce((n, [, v]) => n + v, 0) / 64 / Math.max(1, HUMANS - 1)).toFixed(1)} s on average for the others; over the results ${(picker.askedOverResults / 64).toFixed(1)} s when asked, ${(picker.overResults / 64).toFixed(1)} s unasked`);
if (picker.overResults) stats.errors.push('the car picker covered the results board without !car: ' + (picker.overResults / 64).toFixed(1) + ' s');
console.log(`auto team joins: ${stats.autoTeams || 0}`);
console.log(`votes: ${(stats.says.join(' | ').match(/VOTED/g) || []).length} voted arenas announced; glow calls ${stats.glows || 0}`);
console.log('props teleported 3+ ticks in a row:', stats.tpRuns || 0, '; calls on entities that had gone away:', stats.invalidCalls || 0);
if (stats.tpRuns) stats.errors.push('props teleported every tick (CS2 hides them): ' + stats.tpRuns);
if (stats.errors.length) { console.log('ERRORS/WARNINGS:'); for (const e of [...new Set(stats.errors)].slice(0, 20)) console.log('  ' + e); }
console.log('log:', stats.msgs.filter((m) => !/chat command/.test(m)).slice(0, 12).join(' | '));
