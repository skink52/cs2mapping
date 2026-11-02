// Runs the real scripts/freedm.js against a stand-in for CS2's cs_script API.
// Simulates players (humans with random input + CS2 bots), the round timer, freeze time,
// scripted kills and respawns, and checks the script keeps working.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const HUMANS = +(process.argv[2] || 10), BOTS = +(process.argv[3] || 6), SECONDS = +(process.argv[4] || 240);
const OPTS = process.argv[5] || '';
// 'seed=N': repeatable run (Math.random and the clock are fixed). 'trace': a hash of every call the script makes into
// CS2 (positions, models, HUD classes, inputs fired, log lines) plus engine calls per tick, so an optimisation can be
// checked to change nothing: same seed and options -> same hash
const SEED = (OPTS.match(/seed=(\d+)/) || [])[1];
if (SEED !== undefined) {
  let s = +SEED >>> 0;
  Math.random = () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  Date.now = () => 1790000000000;
}
const TRACE = OPTS.includes('trace');

const CSInputs = { NONE: 0, FORWARD: 1, BACK: 2, LEFT: 4, RIGHT: 8, WALK: 16, DUCK: 32, JUMP: 64, USE: 128, ATTACK: 256, ATTACK2: 512, RELOAD: 1024, SHOW_SCORES: 2048, LOOK_AT_WEAPON: 4096 };
for (const [k, v] of Object.entries({ ...CSInputs })) CSInputs[v] = k;
const CustomCameraMode = { DISABLED: 0, CONTROLLED: 1, CONTROLLED_POSITION: 2, FOLLOW_POSITION: 3 };
const CSRoundEndReason = { UNKNOWN: -1, IN_PROGRESS: 0, GAME_COMMENCING: 1, DRAW: 2, CTS_WIN: 8, TERRORISTS_WIN: 9 };
const CSMoveType = { INVALID: -1, NONE: 0, WALK: 1, FLYGRAVITY: 2, VPHYSICS: 3, NOCLIP: 4, OBSERVER: 5, LADDER: 6, CUSTOM: 7 };
const CSDamageTypes = { GENERIC: 0, BULLET: 2, BLAST: 64 };
const CSDamageFlags = { NONE: 0, PREVENT_DEATH: 8, FORCE_DEATH: 16, IGNORE_ARMOR: 64 };

let time = 0;
const modelOk = new Set();
let H = 2166136261 >>> 0;
const th = TRACE ? (str) => { for (let i = 0; i < str.length; i++) H = Math.imul(H ^ str.charCodeAt(i), 16777619) >>> 0; } : () => {};
const fp = (o) => o ? `${o.x !== undefined ? o.x.toFixed(3) + ',' + o.y.toFixed(3) + ',' + o.z.toFixed(3) : ''}` : '';
const stats = { teamkills: 0, churn: { join: 0, kick: 0, kickDead: 0, swap: 0, leave: 0 }, moves: 0, teleports: 0, setModel: 0, hudCalls: 0, sounds: 0, skins: 0, spawned: 0, kills: 0, scriptKills: 0, errors: [], msgs: [], cvars: {}, says: [] };

class Entity {
  constructor(name, cls, pos) { this.name = name; this.cls = cls; this.pos = pos || { x: 0, y: 0, z: 0 }; this.ang = { pitch: 0, yaw: 0, roll: 0 }; this.valid = true; }
  IsValid() { return this.valid; }
  GetAbsOrigin() { return { ...this.pos }; }
  GetAbsAngles() { return { ...this.ang }; }
  GetEntityName() { return this.name; }
  SetEntityName(n) { this.name = n; }
  GetClassName() { return this.cls; }
  Teleport(o) { stats.teleports++; TRACE && th('T' + this.name + fp(o.position) + (o.angles ? o.angles.yaw.toFixed(2) : '') + (o.velocity ? fp(o.velocity) : '')); if (o.position) this.pos = { ...o.position }; if (o.angles) this.ang = { ...o.angles }; check(o.position); }
  Move(o) { stats.moves++; TRACE && th('M' + this.name + fp(o.position) + (o.angles ? o.angles.pitch.toFixed(2) + ',' + o.angles.yaw.toFixed(2) : '')); if (o.position) this.pos = { ...o.position }; if (o.angles) this.ang = { ...o.angles }; check(o.position); }
  SetModel(m) { stats.setModel++; TRACE && th('S' + this.name + m); if (!modelOk.has(m)) { if (!fs.existsSync(path.join(root, 'out/addon', m))) throw new Error('missing model ' + m); modelOk.add(m); } this.model = m; }
  SetColor(c) { TRACE && th('C' + this.name + JSON.stringify(c)); this.color = c; }
  SetParent(p) { this.parent = p; }
  Kill() { this.valid = false; }
  Remove() { this.valid = false; }
}
let badShown = 0;
function check(p) {
  if (p && [p.x, p.y, p.z].some((v) => !Number.isFinite(v) || Math.abs(v) > 16384)) {
    if (OPTS.includes('dbg') && !badShown++ && ctx.__dbg) {
      const { rm } = ctx.__dbg();
      for (const a of rm.arenas) for (const pl of a.players.values()) if (pl.mo) {
        const w = { x: a.level.off[0] + pl.mo.x };
        if (Math.abs(w.x) > 16000) console.log('DBG', a.mapId, pl.name, 'slot', pl.slot, 'isBot', pl.isBot, 'doom pos', Math.round(pl.mo.x), Math.round(pl.mo.y), 'sector', a.level.sectorAt(pl.mo.x, pl.mo.y).id, 'state', pl.playerstate, 'person', pl.person && pl.person.name, pl.person && pl.person.status, 'off', a.level.off.join(','));
      }
    }
    throw new Error('bad position ' + JSON.stringify(p));
  }
}

const world = new Map();
function addEnt(e) { world.set(e.name, e); return e; }
class PointTemplate extends Entity { ForceSpawn(pos) { stats.spawned++; const e = new Entity('tplspawn' + stats.spawned, 'prop_dynamic', pos); spawnedEnts.push(e); return [e]; } }
// what each player's HUD panels show (panel -> class), so text lines can be read back
const hudState = new Map();
const loadingSlots = new Set();   // 'hudwipe': slots whose client drops HUD messages until they pick a team
class CustomHudLayout extends Entity {
  SetHasClassForPlayer(slot, panel, cls, on) {
    stats.hudCalls++; TRACE && th('H' + slot + panel + cls + on); const k = panel.replace(/\d+$/, "#"); (stats.hudBy ||= {})[k] = ((stats.hudBy[k]) || 0) + 1; if (!hudIds.has(panel)) throw new Error("unknown HUD panel " + panel);
    if (OPTS.includes('hudwipe') && loadingSlots.has(slot)) return;   // client not ready: the change never arrives
    let m = hudState.get(slot); if (!m) hudState.set(slot, m = new Map());
    if (on) m.set(panel, cls); else if (m.get(panel) === cls) m.delete(panel);
  }
  SetDialogVariableStringForPlayer() { stats.hudCalls++; }
  ResetForPlayer(slot) { hudState.delete(slot); }
}
const HUD_STRINGS = JSON.parse(fs.readFileSync(path.join(root, 'build/hud_strings.json'), 'utf8'));
function hudLine(slot, prefix, n) {
  const m = hudState.get(slot) || new Map();
  const img = m.get(prefix + 'img');
  if (img) return HUD_STRINGS[+img.slice(1)];
  let s = '';
  for (let i = 0; i < n; i++) { const c = m.get(prefix + i); s += !c ? '' : c === 'csp' ? ' ' : String.fromCharCode(+c.slice(1)); }
  return s.trimEnd();
}
const spawnedEnts = [];
// music: one track at a time, from the pool that fits the round's mode
const musicInfo = new Map(JSON.parse(fs.readFileSync(path.join(root, 'out/addon/_gen/music.json'), 'utf8')).map((t) => [t.id, t]));
const music = { starts: 0, stops: 0, playing: null, byPool: {}, problems: [] };
function musicEvent(id, on) {
  const t = musicInfo.get(id);
  if (!t) throw new Error('unknown music ' + id);
  if (!on) { music.stops++; if (music.playing && music.playing.id === id) music.playing = null; return; }
  music.starts++;
  music.byPool[t.pool] = (music.byPool[t.pool] || 0) + 1;
  if (music.playing && time < music.playing.until - 0.05) music.problems.push(`t=${time.toFixed(1)} ${id} started over ${music.playing.id}`);
  const rm = ctx.__dbg && ctx.__dbg().rm;
  const respawn = rm && { ffa: true, tdm: true, boss: true, elim: false, lms: false }[rm.modeKey];
  const want = rm && rm.modeKey === 'boss' && [...musicInfo.values()].some((x) => x.pool === 'boss') ? 'boss' : respawn ? 'long' : 'short';
  // the theme (pool opener) opens every round; then the round's own pool
  if (t.pool === 'opener') { if (music.starts > 1 && music.lastRound === rm.roundNumber) music.problems.push(`t=${time.toFixed(1)} theme played twice in round ${rm.roundNumber}`); music.lastRound = rm.roundNumber; }
  else if (rm && want !== t.pool) music.problems.push(`t=${time.toFixed(1)} ${id} (${t.pool}) in a ${rm.modeKey} round`);
  music.playing = { id, until: time + t.seconds };
}
const hudXml = fs.readFileSync(path.join(root, 'out/addon/panorama/layout/custom_game/freedm.xml'), 'utf8');
const hudIds = new Set([...hudXml.matchAll(/id="([^"]+)"/g)].map((m) => m[1]));
const hudCss = fs.readFileSync(path.join(root, 'out/addon/panorama/styles/custom_game/freedm.css'), 'utf8');

// map entities from the VMF
const vmf = fs.readFileSync(path.join(root, 'build/freedm.vmf'), 'utf8');
for (const block of vmf.split('entity\n{').slice(1)) {
  const kv = Object.fromEntries([...block.matchAll(/"([^"]+)" "([^"]*)"/g)].map((m) => [m[1], m[2]]));
  if (!kv.targetname) continue;
  const o = kv.origin.split(' ').map(Number);
  const pos = { x: o[0], y: o[1], z: o[2] };
  if (kv.classname === 'point_template') addEnt(new PointTemplate(kv.targetname, kv.classname, pos));
  else if (kv.classname === 'custom_hud_layout') addEnt(new CustomHudLayout(kv.targetname, kv.classname, pos));
  else addEnt(new Entity(kv.targetname, kv.classname, pos));
}

// ---------------------------------------------------------------- players
const cvar = (k) => stats.cvars[k];
class Camera extends Entity { constructor(p) { super('cam', 'camera'); this.mode = 0; this.pawn = p; } SetMode(m) { this.mode = m; } GetMode() { return this.mode; } GetPlayer() { return this.pawn; } SetFollowConfig() {} }
class Pawn extends Entity {
  constructor(ctrl) { super('pawn' + ctrl.slot, 'player'); this.ctrl = ctrl; this.alive = true; this.buttons = 0; this.prev = 0; this.eye = { pitch: 0, yaw: Math.random() * 360, roll: 0 }; this.cam = null; this.movetype = 1; }
  GetPlayerController() { return this.ctrl; }
  GetOriginalPlayerController() { return this.ctrl; }
  IsAlive() { return this.alive; }
  IsInputPressed(b) { return !!(this.buttons & b); }
  WasInputJustPressed(b) { return !!(this.buttons & b) && !(this.prev & b); }
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
    stats.scriptKills++;
    this.die(d.attacker);
    return d.damage;
  }
  die(attacker) {
    this.alive = false; this.valid = false;
    stats.kills++;
    // scoreboard like CS2: kill +1, teamkill -1 unless teammates are enemies, self/world = death only
    const k = attacker && attacker.ctrl ? attacker.ctrl : attacker instanceof Controller ? attacker : null;
    this.ctrl.deaths++;
    if (k && k !== this.ctrl) {
      if (k.team === this.ctrl.team && cvar('mp_teammates_are_enemies') !== '1') { k.kills--; stats.teamkills++; }
      else k.kills++;
    }
    hooks.OnPlayerKill && hooks.OnPlayerKill({ player: this, attacker });
    const team = this.ctrl.team;
    const respawn = cvar(team === 2 ? 'mp_respawn_on_death_t' : 'mp_respawn_on_death_ct') === '1';
    if (respawn) later(1.5, () => this.ctrl.respawn());
  }
}
class Controller {
  constructor(slot, name, team, bot, noPawn) { this.slot = slot; this.name = name; this.team = team; this.bot = bot; this.connected = true; this.pawn = noPawn ? null : new Pawn(this); this.score = 0; this.kills = 0; this.deaths = 0; this.brain = { turn: 0 }; }
  GetPlayerSlot() { return this.slot; } GetPlayerName() { return this.name; } GetPlayerPawn() { return this.pawn && this.pawn.valid ? this.pawn : undefined; }
  IsBot() { return this.bot; } IsConnected() { return this.connected; } GetTeamNumber() { return this.team; }
  AddScore(n) { this.score += n; stats.addScore = (stats.addScore || 0) + n; } GetScore() { return this.score || 0; } JoinTeam(t) { this.team = t; } IsValid() { return this.connected; }
  respawn() { if (!this.connected) return; this.pawn = new Pawn(this); hooks.OnPlayerReset && hooks.OnPlayerReset({ player: this.pawn }); }
}
const players = [];
for (let i = 0; i < HUMANS + BOTS; i++) players.push(new Controller(i, (i < HUMANS ? 'human' : 'bot') + i, i % 2 ? 3 : 2, i >= HUMANS));

// ---------------------------------------------------------------- Instance
const hooks = {};
let thinkFn = null, nextThink = 0;
const timers = [];
function later(dt, fn) { timers.push({ at: time + dt, fn }); }
let freezeUntil = 2, roundEnd = 600, roundEnded = false, warmup = false, winFired = null; const winReasons = {};
const Instance = {
  Msg: (m) => { const s = String(m); if (!/script time/.test(s)) TRACE && th('L' + s); stats.msgs.push(s); if (/error|WARNING/.test(s)) stats.errors.push(s); if (OPTS.includes('v')) console.log(s); },
  GetGameTime: () => time,
  SetThink: (fn) => { thinkFn = fn; },
  SetNextThink: (t) => { nextThink = t; },
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
  ServerCommand: (c) => { const [k, v] = c.split(' '); if (k === 'say') stats.says.push(c.slice(4)); else stats.cvars[k] = v; },
  ClientCommand: () => {},
  EntFireAtTarget: ({ target, input, value }) => { TRACE && th('E' + target.name + input + (value === undefined ? '' : value));
    if (input === 'Skin') stats.skins++;
    else if (input === 'StartSound' && target.name.startsWith('fdm_mus_')) musicEvent(target.name.slice(8), true);
    else if (input === 'StopSound' && target.name.startsWith('fdm_mus_')) musicEvent(target.name.slice(8), false);
    else if (input === 'StartSound') { stats.sounds++; if (!target.name.startsWith('fdm_snd_')) throw new Error('sound on ' + target.name); }
    else if (input === 'SetSourceEntity') { if (![...spawnedEnts].some((e) => e.name === value)) throw new Error('unknown sound source ' + value); }
    else throw new Error('unexpected input ' + input);
  },
  EntFireAtName: ({ name, input, value }) => { if (input === 'FireWinCondition') { winFired = value; roundEnd = time; } },
  IsFreezePeriod: () => time < freezeUntil,
  IsWarmupPeriod: () => warmup,
  GetRoundRemainingTime: () => roundEnd - time,
  SetRoundRemainingTime: (t) => { roundEnd = time + t; },
};
const NCALLS = new Map();
function countMethods(proto, tag) { for (const k of Object.getOwnPropertyNames(proto)) { if (k === 'constructor' || typeof proto[k] !== 'function') continue; const f = proto[k]; const key = tag + '.' + k; proto[k] = function (...a) { NCALLS.set(key, (NCALLS.get(key) || 0) + 1); return f.apply(this, a); }; } }
if (TRACE) { for (const [c, t] of [[Entity, 'Ent'], [Pawn, 'Pawn'], [Controller, 'Ctrl'], [Camera, 'Cam'], [CustomHudLayout, 'Hud'], [PointTemplate, 'Tpl']]) countMethods(c.prototype, t); countMethods(Instance, 'I'); }
const api = { Instance, CSInputs, CustomCameraMode, CSMoveType, CSRoundEndReason, CSDamageTypes, CSDamageFlags, CSPlayerPawn: Pawn, CSPlayerController: Controller, BaseModelEntity: Entity, PointTemplate, CustomHudLayout, Entity };

let src = fs.readFileSync(process.env.FDM_SCRIPT || path.join(root, 'out/addon/maps/scripts/freedm.js'), 'utf8');
src = src.replace(/^import \{[^}]+\} from "cs_script\/point_script";/m, 'const { Instance, CSInputs, CSPlayerPawn, CSPlayerController, BaseModelEntity, PointTemplate, CustomHudLayout, CSDamageFlags, CSDamageTypes, CustomCameraMode, CSMoveType, CSRoundEndReason, Entity } = __api;');
if (OPTS.includes('elimonly')) src = src.replace(/MODE_WEIGHTS: \{[^}]*\}/, 'MODE_WEIGHTS: { ffa: 0, tdm: 0, elim: 100, lms: 0, boss: 0 }');
if (OPTS.includes('bossonly')) src = src.replace(/MODE_WEIGHTS: \{[^}]*\}/, 'MODE_WEIGHTS: { ffa: 0, tdm: 0, elim: 0, lms: 0, boss: 100 }');
if (OPTS.includes('noboss')) src = src.replace(/MODE_WEIGHTS: \{[^}]*\}/, 'MODE_WEIGHTS: { ffa: 35, tdm: 35, elim: 20, lms: 10, boss: 0 }');
if (OPTS.includes('novote')) src = src.replace('VOTE: true', 'VOTE: false');   // the round flow as before the vote
{ const dm = /diff=([0-9.]+)/.exec(OPTS); if (dm) src = src.replace(/difficulty: [0-9.]+ \}/, 'difficulty: ' + dm[1] + ' }'); }
if (OPTS.includes('monsters')) src = src.replace('MONSTER_CHANCE: 0.15', 'MONSTER_CHANCE: 1');
if (OPTS.includes('hudcheck')) src = src.replace('const HUD_LINE_CHECK = false;', 'const HUD_LINE_CHECK = true;');
if (OPTS.includes('nolinecache')) src = src.replace(/function hudSame\(slot, prefix, value\) \{/, 'function hudSame(slot, prefix, value) { return false;');
src += '\nglobalThis.__dbg = () => ({ rm, views, parked, hudCheckMiss, hudCache, phase, vote: typeof vote === "undefined" ? null : vote });\n';
const ctx = vm.createContext({ __api: api, console, Math, Date, JSON, Map, Set, Array, Object, String, Number, Error, Infinity, NaN });
vm.runInContext(src, ctx, { filename: 'freedm.js' });

// ---------------------------------------------------------------- run
const TICK = 1 / 64;
hooks.OnActivate();
let rounds = 0;
const t0 = Date.now();
let thinkMs = 0, maxThink = 0;
const perf = { ms: [], mv: [], hud: [], snd: 0, sp: 0 };
// 'spec': human0 spectates, asks for help, comes back (and again later); other spectators type !back now and then
const CHATS = OPTS.includes('spec')
  ? { 25: "!spec", 28: "/help", 38: "!back", 45: "!spec", 47: "!doom", 56: "!back" }
  : { 20: "!hud", 30: "/help", 35: "!doom", 40: "/hud small", 50: "!hud", 60: "!hud center", 70: "!hud scores" };
const SPEC_LOOK = [24, 26, 29, 37, 39, 46, 48, 55, 57];
const spec = { lines: [], seen: new Map(), backs: { in: 0, stay: 0 }, problems: [], empty: [] };
function specCheck() {
  const { rm } = ctx.__dbg();
  const sec = Math.round(time);
  const show = (pe) => `status ${pe.status}${pe.arena ? ' (in ' + pe.arena.modeKey + ')' : ''} | msg "${hudLine(pe.slot, 'fdm_msg', 56)}" | above "${hudLine(pe.slot, 'fdm_spec2_', 40)}" | bottom "${hudLine(pe.slot, 'fdm_spec', 32)}"`;
  const p0 = rm.person(0);
  if (p0 && SPEC_LOOK.includes(sec)) spec.lines.push(`t=${sec} ${rm.modeKey} human0: ${show(p0)}`);
  for (const pe of rm.people.values()) {
    if (pe.bot) continue;
    if (rm.state === 'running' && pe.status === 'none' && pe.arena) spec.problems.push(`t=${sec} ${pe.name} stuck: status none but still in an arena`);
    if (pe.status !== 'spectating' || rm.state !== 'running') continue;
    if (!hudLine(pe.slot, 'fdm_spec2_', 40) && !hudLine(pe.slot, 'fdm_spec', 32)) spec.empty.push(`t=${sec} ${pe.name} spec ${JSON.stringify(pe.spec)} arena ${pe.arena ? pe.arena.index : '-'}`);
    const key = `${rm.modeKey} ${pe.arena ? 'knocked out/arena over' : 'left'}: "${hudLine(pe.slot, 'fdm_spec2_', 40).replace(/^SPECTATING .+/, 'SPECTATING <name>')}" / "${hudLine(pe.slot, 'fdm_spec', 32)}"`;
    spec.seen.set(key, (spec.seen.get(key) || 0) + 1);
    // spectators other than human0 try !back now and then: it must work exactly when canJoin says so
    const ctrl = players.find((c) => c.slot === pe.slot && c.connected);
    if (ctrl && pe.slot !== 0 && sec % 9 === pe.slot % 9) {
      const could = rm.canJoin(pe);
      hooks.OnPlayerChat({ player: ctrl, text: '!back' });
      spec.backs[could ? 'in' : 'stay']++;
      if (could && pe.status !== 'playing') spec.problems.push(`t=${sec} ${pe.name}: !back should have joined, status ${pe.status}`);
      if (!could && pe.status !== 'spectating') spec.problems.push(`t=${sec} ${pe.name}: !back should have kept spectating, status ${pe.status}`);
    }
  }
}
// next-mode vote: every human sees the ballot while it's open; no mode three rounds running
let lastRestart = -1;
const voteSeen = { checks: 0, missing: 0, missingSlots: new Set(), ballots: 0 };
function voteCheck() {
  const d = ctx.__dbg();
  if (!d.vote || !d.vote.open || time < d.vote.inputFrom || time < lastRestart + 0.5) return;   // a restart wipes every HUD: redrawn within a few ticks
  voteSeen.ballots++;
  for (const pe of d.rm.people.values()) {
    if (pe.bot || (OPTS.includes('hudwipe') && loadingSlots.has(pe.slot))) continue;
    voteSeen.checks++;
    if (!hudLine(pe.slot, 'fdm_ctr', 24).startsWith('VOTE NEXT MODE')) { voteSeen.missing++; voteSeen.missingSlots.add(pe.slot); if (OPTS.includes('vdbg') && voteSeen.missing < 400) console.log('VOTEMISS t=' + time.toFixed(2), pe.slot, pe.status, d.phase, d.parked.has(pe.slot), JSON.stringify(hudLine(pe.slot, 'fdm_ctr', 24)), (hudState.get(pe.slot) || new Map()).get('fdm_root'), 'ends', d.vote.endsAt.toFixed(2)); }
  }
}
const join = { stranded: new Map(), worst: 0, over2: new Set(), hudBad: 0, hudChecks: 0, hudBadSlots: new Set() };
function joinCheck() {
  const d = ctx.__dbg();
  const rm = d.rm;
  for (const pe of rm.people.values()) {
    const c = players.find((x) => x.slot === pe.slot && x.connected);
    const standing = d.phase === 'running' && rm.state === 'running' && pe.status === 'none' && !pe.afk && (pe.csTeam === 2 || pe.csTeam === 3) && c && c.pawn && c.pawn.valid && c.pawn.alive;
    const n = standing ? (join.stranded.get(pe.slot) || 0) + 1 : 0;
    join.stranded.set(pe.slot, n);
    if (n > join.worst) join.worst = n;
    if (n > 2) join.over2.add(pe.name + '@' + Math.round(time));
    if (c && !c.bot && !loadingSlots.has(pe.slot)) {
      const want = d.hudCache.get(pe.slot), got = hudState.get(pe.slot) || new Map();
      if (want) { join.hudChecks++; let bad = 0; for (const [panel, cls] of want) if ((got.get(panel) || null) !== (cls || null)) bad++; if (bad) { join.hudBad++; join.hudBadSlots.add(pe.slot); } }
    }
  }
}
while (time < SECONDS) {
  time += TICK;
  for (const [at, text] of Object.entries(CHATS)) if (Math.abs(time - +at) < TICK / 2 && players[0] && hooks.OnPlayerChat) hooks.OnPlayerChat({ player: players[0], text, team: 0 });
  if (OPTS.includes('spec') && Math.floor(time) !== Math.floor(time - TICK)) specCheck();
  if (OPTS.includes('churn') && Math.floor(time) !== Math.floor(time - TICK)) joinCheck();
  if (Math.floor(time * 2) !== Math.floor((time - TICK) * 2)) voteCheck();
  // fake human input: move, strafe, turn, shoot, switch weapons
  for (const c of players) {
    const p = c.pawn;
    if (!p || !p.valid || c.bot) continue;
    p.prev = p.buttons;
    const b = c.brain;
    if (Math.random() < 0.02) b.turn = (Math.random() - 0.5) * 6;
    p.eye.yaw = (p.eye.yaw + b.turn + 360) % 360;
    let bt = CSInputs.FORWARD;
    if (Math.random() < 0.6) bt |= CSInputs.ATTACK;
    if (Math.random() < 0.3) bt |= CSInputs.LEFT;
    if (Math.random() < 0.02) bt |= CSInputs.RELOAD;
    if (Math.random() < 0.05) bt |= CSInputs.USE;
    if (OPTS.includes('afk') && c.slot === 0) bt = 0, b.turn = 0;
    p.buttons = bt;
  }
  for (let i = timers.length - 1; i >= 0; i--) if (timers[i].at <= time) { const t = timers.splice(i, 1)[0]; t.fn(); }
  // round timer
  if (!roundEnded && time >= roundEnd && (winFired !== null || cvar('mp_ignore_round_win_conditions') !== '1')) {
    roundEnded = true; rounds++; winReasons[winFired] = (winReasons[winFired] || 0) + 1;
    hooks.OnRoundEnd && hooks.OnRoundEnd({ winningTeam: winFired === 9 ? 2 : winFired === 8 ? 3 : 0, reason: winFired === null ? 0 : winFired }); winFired = null;
    later(3, () => {
      hooks.OnBeginRoundRestart && hooks.OnBeginRoundRestart(); lastRestart = time;
      for (const e of spawnedEnts) e.valid = false;
      spawnedEnts.length = 0;
      for (const c of players) if (c.connected) { c.pawn = new Pawn(c); hooks.OnPlayerReset && hooks.OnPlayerReset({ player: c.pawn }); }
      freezeUntil = time + 2; roundEnd = time + 600; roundEnded = false;
      hooks.OnRoundStart && hooks.OnRoundStart();
    });
  }
  if (thinkFn && nextThink <= time + 1e-9) {
    const s = performance.now();
    try { thinkFn(); } catch (err) { stats.errors.push('THROW ' + err.stack); break; }
    const d = performance.now() - s; thinkMs += d; maxThink = Math.max(maxThink, d);
    if (OPTS.includes('perf') && time > 10) {
      const now = { mv: stats.moves + stats.teleports, hud: stats.hudCalls, snd: stats.sounds, sp: stats.spawned };
      const pv = perf.prev || now; perf.prev = now;
      perf.ms.push(d); perf.mv.push(now.mv - pv.mv); perf.hud.push(now.hud - pv.hud); perf.snd += now.snd - pv.snd; perf.sp += now.sp - pv.sp;
    }
    if (d > 16) (stats.slow ||= []).push(`${time.toFixed(1)}s:${d.toFixed(0)}ms`);
    if (OPTS.includes('prof')) { const now = { hud: stats.hudCalls, tp: stats.teleports + stats.moves, sp: stats.spawned, mdl: stats.setModel }; const pv = stats.prev || now; if (d > 8) console.log(`t=${time.toFixed(2)} ${d.toFixed(1)}ms hud+${now.hud - pv.hud} moves+${now.tp - pv.tp} spawned+${now.sp - pv.sp} setModel+${now.mdl - pv.mdl}`); stats.prev = now; }
  }
  if (OPTS.includes('disc') && Math.abs(time - 60) < TICK / 2) { const c = players[3]; c.connected = false; hooks.OnPlayerDisconnect({ playerSlot: c.slot }); }
  // churn: people joining mid-round (CS2 kicks a bot to make room and the newcomer reuses its slot), team swaps, leavers
  if (OPTS.includes('churn') && time > 15 && Math.floor(time / 5) !== Math.floor((time - TICK) / 5)) churn();
}
function disconnect(c) { c.connected = false; if (c.pawn) c.pawn.valid = false; hooks.OnPlayerDisconnect && hooks.OnPlayerDisconnect({ playerSlot: c.slot }); }
function churn() {
  const live = players.filter((c) => c.connected);
  const r = Math.random();
  if (r < 0.5) {
    // a human joins: kick a bot (often one that is dead and waiting to respawn) and reuse the slot
    const bots = live.filter((c) => c.bot);
    let slot = -1;
    if (bots.length) {
      const dead = bots.filter((c) => !c.pawn || !c.pawn.alive);
      const victim = (dead.length && Math.random() < 0.7 ? dead : bots)[Math.floor(Math.random() * (dead.length && Math.random() < 0.7 ? dead.length : bots.length))] || bots[0];
      if (!victim.pawn || !victim.pawn.alive) stats.churn.kickDead++;
      disconnect(victim); stats.churn.kick++; slot = victim.slot;
    } else { const used = new Set(live.map((c) => c.slot)); for (let i = 0; i < 64; i++) if (!used.has(i)) { slot = i; break; } }
    if (slot < 0) return;
    const c = new Controller(slot, 'late' + slot, 0, false, true);
    players.push(c); stats.churn.join++;
    if (OPTS.includes('hudwipe')) loadingSlots.add(slot);
    hooks.OnPlayerActivate && hooks.OnPlayerActivate({ player: c });
    if (OPTS.includes('resetfirst')) later(2, () => {
      if (!c.connected) return;
      c.team = Math.random() < 0.5 ? 2 : 3; loadingSlots.delete(slot);
      c.pawn = new Pawn(c);
      hooks.OnPlayerReset && hooks.OnPlayerReset({ player: c.pawn });
      hooks.OnPlayerTeamChanged && hooks.OnPlayerTeamChanged({ player: c.pawn, oldTeam: 0 });
    });
    else later(2, () => { if (!c.connected) return; c.team = Math.random() < 0.5 ? 2 : 3; loadingSlots.delete(slot); hooks.OnPlayerTeamChanged && hooks.OnPlayerTeamChanged({ player: c, newTeam: c.team }); later(1, () => c.respawn()); });
  } else if (r < 0.75) {
    const humans = live.filter((c) => !c.bot && c.slot !== 0);
    const c = humans[Math.floor(Math.random() * humans.length)] || live[Math.floor(Math.random() * live.length)];
    if (!c || c.slot === 0) return;
    stats.churn.swap++;
    if (OPTS.includes('resetfirst')) {
      const oldTeam = c.team;
      if (c.pawn) { c.pawn.alive = false; c.pawn.valid = false; }
      c.team = c.team === 2 ? 3 : 2;
      c.pawn = new Pawn(c);
      hooks.OnPlayerReset && hooks.OnPlayerReset({ player: c.pawn });
      hooks.OnPlayerTeamChanged && hooks.OnPlayerTeamChanged({ player: c.pawn, oldTeam });
      return;
    }
    if (c.pawn) { c.pawn.alive = false; c.pawn.valid = false; }
    c.team = c.team === 2 ? 3 : 2;
    hooks.OnPlayerTeamChanged && hooks.OnPlayerTeamChanged({ player: c, newTeam: c.team });
    const respawn = cvar(c.team === 2 ? 'mp_respawn_on_death_t' : 'mp_respawn_on_death_ct') === '1';
    if (respawn) later(1, () => c.respawn());
  } else {
    const humans = live.filter((c) => !c.bot && c.slot !== 0);
    const c = humans[Math.floor(Math.random() * humans.length)];
    if (c) { disconnect(c); stats.churn.leave++; }
  }
}
const cams = players.filter((c) => c.pawn && c.pawn.cam).map((c) => c.pawn.cam.mode);
if (TRACE) {
  let tot = 0; for (const v of NCALLS.values()) tot += v;
  console.log('TRACE HASH', H.toString(16));
  console.log('engine calls per tick', (tot / (SECONDS * 64)).toFixed(1) + ':', [...NCALLS.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12).map(([k, v]) => k + ' ' + (v / (SECONDS * 64)).toFixed(1)).join(', '));
}
console.log('round end reasons', JSON.stringify(winReasons));
console.log(`simulated ${SECONDS}s with ${HUMANS} humans + ${BOTS} bots: ${rounds} CS2 rounds ended`);
console.log(`props spawned ${stats.spawned}, moves ${stats.moves}, teleports ${stats.teleports}, setModel ${stats.setModel}, skins ${stats.skins}, hud calls ${stats.hudCalls}, sounds ${stats.sounds}`);
console.log(`CS2 kills ${stats.kills} (scripted ${stats.scriptKills}), camera modes ${JSON.stringify(cams)}`);
console.log(`think time: avg ${(thinkMs / (SECONDS * 64)).toFixed(3)} ms, max ${maxThink.toFixed(1)} ms`);
console.log('think ticks over 16 ms:', (stats.slow || []).length, (stats.slow || []).slice(0, 12).join(' '));
console.log('cvars', JSON.stringify(stats.cvars));
console.log('says:', stats.says.slice(0, 8).join('\n      '));
console.log('scores', players.map((c) => c.score).join(','));
const live = players.filter((c) => c.connected);
console.log(`scoreboard kills ${players.reduce((n, c) => n + c.kills, 0)} (teamkill penalties ${stats.teamkills}), connected ${live.length} (${live.filter((c) => !c.bot).length} humans), churn ${JSON.stringify(stats.churn)}`);
const off = stats.msgs.find((m) => /Real kills are off/.test(m));
console.log(off ? 'REAL KILLS SWITCHED OFF: ' + off : 'real kills stayed on');
if (stats.errors.length) { console.log('ERRORS/WARNINGS:'); for (const e of [...new Set(stats.errors)].slice(0, 20)) console.log('  ' + e); }
console.log("hud by panel", JSON.stringify(Object.entries(stats.hudBy || {}).sort((a,b)=>b[1]-a[1]).slice(0,14)));
console.log("status bar swaps", (stats.hudBy || {}).fdm_sbarbox || 0);
console.log('log:', stats.msgs.slice(0, 5).join(' | '));
console.log(`music: ${music.starts} tracks started (${JSON.stringify(music.byPool)}), ${music.stops} stops, problems ${music.problems.length}`, music.problems.slice(0, 5).join(' | '));
{
  const modes = stats.msgs.map((m) => (m.match(/round \d+: (\w+),/) || [])[1]).filter(Boolean);
  let run3 = 0; for (let i = 2; i < modes.length; i++) if (modes[i] === modes[i - 1] && modes[i] === modes[i - 2]) run3++;
  const votes = stats.msgs.filter((m) => /\] vote: /.test(m));
  console.log(`modes: ${modes.join(' ')} | three in a row: ${run3} | votes: ${votes.length} | ballot shown: ${voteSeen.checks - voteSeen.missing} of ${voteSeen.checks} checks (missing for slots ${[...voteSeen.missingSlots].join(',') || '-'})`);
  for (const v of votes.slice(0, 4)) console.log('  ' + v);
}
if (OPTS.includes('spec')) {
  console.log('human0 scenario:\n  ' + spec.lines.join('\n  '));
  console.log('spectator lines seen (seconds):\n  ' + [...spec.seen.entries()].sort((a, b) => b[1] - a[1]).map(([k, n]) => `${n}x ${k}`).join('\n  '));
  console.log(`blank spectator lines: ${spec.empty.length}`, spec.empty.slice(0, 6).join(' | '));
  console.log(`!back from other spectators: ${spec.backs.in} joined, ${spec.backs.stay} kept spectating; problems ${spec.problems.length}`, spec.problems.slice(0, 6).join(' | '));
}
if (OPTS.includes('hudcheck')) console.log(`hud line cache check: ${ctx.__dbg().hudCheckMiss} skipped panels that differed`);
if (OPTS.includes('perf') && perf.ms.length) {
  const q = (a, f) => { const b = a.slice().sort((x, y) => x - y); return b[Math.min(b.length - 1, Math.floor(f * b.length))]; };
  const avg = (a) => a.reduce((t, x) => t + x, 0) / a.length;
  const n = perf.ms.length;
  console.log(`perf over ${n} server ticks: script ms avg ${avg(perf.ms).toFixed(2)} p50 ${q(perf.ms, .5).toFixed(2)} p95 ${q(perf.ms, .95).toFixed(2)} p99 ${q(perf.ms, .99).toFixed(2)} max ${Math.max(...perf.ms).toFixed(1)}`);
  console.log(`  entity moves per tick avg ${avg(perf.mv).toFixed(0)} p99 ${q(perf.mv, .99)} max ${Math.max(...perf.mv)}; HUD changes per tick avg ${avg(perf.hud).toFixed(0)} p99 ${q(perf.hud, .99)}; sounds/s ${(perf.snd / (n / 64)).toFixed(0)}; new props/s ${(perf.sp / (n / 64)).toFixed(1)}`);
}
if (OPTS.includes('churn')) {
  console.log(`late joiners left standing in the lobby: longest ${join.worst} s, cases over 2 s: ${join.over2.size}`, [...join.over2].slice(0, 6).join(' '));
  console.log(`screens not matching the script's HUD: ${join.hudBad} of ${join.hudChecks} checks (${join.hudBadSlots.size} players)`);
}
