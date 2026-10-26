// Generic smoke test for a cs_script point_script: runs the real script file against a stand-in for CS2's
// "cs_script/point_script" API with simulated players, rounds, inputs, chat, damage, kills, respawns and disconnects.
// Fails (exit 1) on any exception thrown inside the script's callbacks or an Instance method that is not in Valve's
// point_script.d.ts (a typo, or an API newer than the .d.ts). Entity methods the stand-in doesn't model return a default
// for their declared return type and are counted, not failed.
//
// usage: node mock_point_script.mjs <script.js> [entities.json] [players=8] [seconds=120] [inputs=a,b,c] [chat=!x,!y] [seed=N]
//   entities.json: from create/dump_entities.py <vmap> (named entities + spawns), so FindEntityByName finds the map's names.
//   inputs: RunScriptInput names to fire (default: every name the script registers with OnScriptInput).
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const args = process.argv.slice(2);
if (!args[0]) { console.log('usage: node mock_point_script.mjs <script.js> [entities.json] [players=8] [seconds=120] [inputs=a,b] [chat=!x] [seed=N]'); process.exit(2); }
const opt = (k, d) => { const a = args.find((x) => x.startsWith(k + '=')); return a ? a.slice(k.length + 1) : d; };
const SCRIPT = path.resolve(args[0]);
const ENTS = args[1] && args[1].endsWith('.json') ? JSON.parse(fs.readFileSync(args[1], 'utf8')) : [];
const PLAYERS = +opt('players', 8), SECONDS = +opt('seconds', 120);
let seed = +opt('seed', 1) >>> 0;
Math.random = () => { seed = (seed + 0x6D2B79F5) >>> 0; let t = seed; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const here = path.dirname(new URL(import.meta.url).pathname);
const dts = fs.readFileSync(path.join(here, 'point_script.d.ts'), 'utf8');
const API = new Set([...dts.matchAll(/^\s{8}([A-Z][A-Za-z]+)(?:<[^>]*>)?\(/gm)].map((m) => m[1]));
const RET = {};   // method name -> declared return type, for defaults on methods the stand-in doesn't model
for (const m of dts.matchAll(/^\s{8}([A-Z][A-Za-z]+)(?:<[^>]*>)?\(.*\):\s*([^;]+);/gm)) RET[m[1]] = RET[m[1]] || m[2].trim();
const dflt = (k) => { const t = RET[k] || ''; if (/^number/.test(t)) return 0; if (/^boolean/.test(t)) return false; if (/^string/.test(t)) return '';
  if (/^Vector/.test(t)) return V(); if (/^QAngle/.test(t)) return Q(); if (/^Color/.test(t)) return { r: 255, g: 255, b: 255, a: 255 }; if (/\[\]/.test(t)) return []; return undefined; };

let time = 0;
const stats = { calls: {}, unknownEntityCalls: {}, fired: {}, errors: [], notInApi: {} };
const count = (o, k) => { o[k] = (o[k] || 0) + 1; };
const V = (x = 0, y = 0, z = 0) => ({ x, y, z });
const Q = (pitch = 0, yaw = 0, roll = 0) => ({ pitch, yaw, roll });

class Ent {
  constructor(name, cls, pos, ang) { this._n = name || ''; this._c = cls; this._p = pos || V(); this._a = ang || Q(); this._v = V(); this._ok = true; this._hp = 100; this._team = 0; this._parent = undefined; this._owner = undefined; }
  IsValid() { return this._ok; } GetClassName() { return this._c; } GetEntityName() { return this._n; } SetEntityName(n) { this._n = n; }
  GetAbsOrigin() { return { ...this._p }; } GetLocalOrigin() { return { ...this._p }; } GetAbsAngles() { return { ...this._a }; } GetLocalAngles() { return { ...this._a }; }
  GetAbsVelocity() { return { ...this._v }; } GetLocalVelocity() { return { ...this._v }; } GetEyeAngles() { return { ...this._a }; } GetEyePosition() { return V(this._p.x, this._p.y, this._p.z + 64); }
  Teleport(o) { chk(o); if (o.position) this._p = { ...o.position }; if (o.angles) this._a = { ...o.angles }; if (o.velocity) this._v = { ...o.velocity }; }
  Move(o) { this.Teleport(o); }
  GetParent() { return this._parent; } SetParent(p) { this._parent = p; } GetOwner() { return this._owner; } SetOwner(o) { this._owner = o; }
  GetTeamNumber() { return this._team; } GetHealth() { return this._hp; } SetHealth(h) { if (!Number.isFinite(h)) throw new Error('SetHealth(' + h + ')'); this._hp = h; }
  GetMaxHealth() { return 100; } SetMaxHealth() {} IsAlive() { return this._hp > 0; } IsWorld() { return false; } GetGroundEntity() { return undefined; }
  TakeDamage(d) { this._hp -= d.damage || 0; return d.damage || 0; } Kill() { this._ok = false; } Remove() { this._ok = false; }
  GetMoveType() { return 2; } SetMoveType() {}
}
function chk(o) { for (const k of ['position', 'velocity']) if (o && o[k]) for (const c of ['x', 'y', 'z']) if (!Number.isFinite(o[k][c])) throw new Error('non-finite ' + k + ' ' + JSON.stringify(o[k])); }
const permissive = (e) => new Proxy(e, { get(t, k) { if (k in t || typeof k === 'symbol') return t[k]; count(stats.unknownEntityCalls, t._c + '.' + String(k)); return () => dflt(String(k)); } });

const world = [];
const add = (e) => { const p = permissive(e); world.push(p); return p; };
for (const e of ENTS) add(new Ent(e.name, e.cls, V(...e.origin), Q(...(e.angles || [0, 0, 0]))));
const spawns = world.filter((e) => e._c.startsWith('info_player'));

class Weapon extends Ent { constructor(n) { super('', n); this.clip = 30; } GetData() { return new Proxy({ GetName: () => this._c, GetMaxClipAmmo: () => 30 }, { get: (t, k) => (k in t ? t[k] : () => dflt(String(k))) }); } GetClipAmmo() { return this.clip; } SetClipAmmo(v) { this.clip = v; } GetReserveAmmo() { return 90; } SetReserveAmmo() {} }
class Pawn extends Ent {
  constructor(ctl) { super('', 'player'); this.ctl = ctl; this.w = [add(new Weapon('weapon_knife'))]; this.keys = 0; }
  GetPlayerController() { return this.ctl; } GetOriginalPlayerController() { return this.ctl; }
  IsInputPressed(b) { return !!(this.keys & b); } WasInputJustPressed(b) { return !!(this.keys & b) && Math.random() < 0.2; } WasInputJustReleased() { return false; }
  GiveNamedItem(n) { const w = add(new Weapon(n)); this.w.push(w); return w; } DestroyWeapons() { this.w = []; } DestroyWeapon() {} SwitchToWeapon() {} FindWeapon(n) { return this.w.find((w) => w._c === n); } FindWeaponBySlot() { return this.w[0]; }
  GetActiveWeapon() { return this.w[0]; } GetArmor() { return 0; } SetArmor() {} IsNoclipping() { return false; } SetModel() {} GetModelName() { return 'characters/models/x.vmdl'; } SetColor() {} SetGlow() {} Unglow() {}
}
class Controller extends Ent {
  constructor(slot) { super('', 'cs_player_controller'); this.slot = slot; this.pawn = null; this._team = 2 + (slot % 2); this.bot = slot % 4 === 3; }
  GetPlayerSlot() { return this.slot; } GetPlayerPawn() { return this.pawn; } GetObserverPawn() { return undefined; } GetPlayerName() { return 'player' + this.slot; }
  IsBot() { return this.bot; } IsConnected() { return this._ok; } IsObserving() { return false; } JoinTeam(t) { this._team = t; if (this.pawn) this.pawn._team = t; } ChangeTeam(t) { this.JoinTeam(t); }
  GetScore() { return 0; } AddScore() {} SetScore() {} GetWeaponDataForLoadoutSlot() { return undefined; }
}
const players = [];

const hooks = {}; let think = null, nextThink = Infinity; const inputs = {};
const timers = [];
const Instance = new Proxy({
  Msg(t) { if (process.env.MOCK_VERBOSE) console.log('[Msg]', String(t)); }, DebugScreenText() {}, DebugLine() {}, DebugSphere() {}, DebugBox() {},
  SetSaveData(d) { this._save = d; }, GetSaveData() { return this._save || ''; },
  SetThink(cb) { think = cb; }, SetNextThink(t) { nextThink = t; }, QueueAfterThinks(cb) { timers.push([time, cb]); },
  Delay(d) { return new Promise((r) => timers.push([time + d, r])); },
  OnScriptInput(name, cb) { inputs[name] = cb; },
  EntFireAtName(c, input) { const cfg = typeof c === 'object' ? c : { name: c, input }; count(stats.fired, cfg.name + '.' + cfg.input); },
  EntFireAtTarget(c, input) { const cfg = c && c.target ? c : { target: c, input }; count(stats.fired, '<target>.' + cfg.input); },
  ConnectOutput() { return 1; }, DisconnectOutput() {},
  FindEntityByName(n) { return world.find((e) => e._ok && e._n === n); }, FindEntitiesByName(n) { return world.filter((e) => e._ok && (n.endsWith('*') ? e._n.startsWith(n.slice(0, -1)) : e._n === n)); },
  FindEntityByClass(c) { return world.find((e) => e._ok && e._c === c); }, FindEntitiesByClass(c) { return world.filter((e) => e._ok && e._c === c); },
  GetPlayerController(s) { return players[s] && players[s]._ok ? players[s] : undefined; }, GetAllPlayerControllers() { return players.filter((p) => p && p._ok); },
  TraceLine(t) { return { didHit: Math.random() < 0.5, fraction: Math.random(), end: t.end || t.start, normal: V(0, 0, 1), startedInSolid: false, hitEntity: undefined }; },
  TraceSphere(t) { return this.TraceLine(t); }, TraceBox(t) { return this.TraceLine(t); }, TracePlayer(t) { return this.TraceLine(t); }, TraceBullet() { return []; },
  IsDedicatedServer() { return true; }, GetGameTime() { return time; }, IsWarmupPeriod() { return false; }, IsFreezePeriod() { return false; }, IsTeamIntroPeriod() { return false; },
  GetGameType() { return 0; }, GetGameMode() { return 0; }, GetMapName() { return 'mock_map'; }, GetRoundsPlayed() { return 0; }, GetRoundRemainingTime() { return 600 - time; }, SetRoundRemainingTime() {},
  ServerCommand(c) { count(stats.calls, 'ServerCommand ' + c.split(' ')[0]); }, ClientCommand() {}, RegisterCheatCommand() {}, AddTeamMoney() {},
  SpawnGrenadeProjectile() { return add(new Ent('', 'hegrenade_projectile')); },
}, {
  get(t, k) {
    if (typeof k === 'symbol') return t[k];
    if (k.startsWith('On') && !(k in t)) { if (!API.has(k)) count(stats.notInApi, k); return (cb) => { (hooks[k] = hooks[k] || []).push(cb); }; }
    if (!(k in t)) { if (!API.has(k)) { count(stats.notInApi, k); return () => undefined; } return (...a) => { count(stats.calls, 'unmodelled Instance.' + k); return dflt(k); }; }
    count(stats.calls, k); return t[k];
  },
});
const enumProxy = (o) => new Proxy(o, { get: (t, k) => (k in t ? t[k] : 0) });
const stub = {
  Instance, Entity: Ent, BaseModelEntity: Ent, CSPlayerPawn: Pawn, CSPlayerController: Controller, CSWeaponBase: Weapon, PointTemplate: Ent, CustomHudLayout: Ent, CustomPlayerCamera: Ent,
  CSInputs: enumProxy({ NONE: 0, FORWARD: 1, BACK: 2, LEFT: 4, RIGHT: 8, WALK: 16, DUCK: 32, JUMP: 64, USE: 128, ATTACK: 256, ATTACK2: 512, RELOAD: 1024, SHOW_SCORES: 2048, LOOK_AT_WEAPON: 4096 }),
  CustomCameraMode: enumProxy({ DISABLED: 0, CONTROLLED: 1, CONTROLLED_POSITION: 2, FOLLOW_POSITION: 3 }),
  CSRoundEndReason: enumProxy({ UNKNOWN: -1, IN_PROGRESS: 0, DRAW: 2, CTS_WIN: 8, TERRORISTS_WIN: 9 }),
  CSMoveType: enumProxy({ NONE: 0, WALK: 1, FLYGRAVITY: 2, NOCLIP: 4, OBSERVER: 5, LADDER: 6 }),
  CSDamageTypes: enumProxy({ GENERIC: 0, BULLET: 2, BLAST: 64 }), CSDamageFlags: enumProxy({ NONE: 0 }), CSGearSlot: enumProxy({}), CSLoadoutSlot: enumProxy({}),
  CSWeaponType: enumProxy({}), CSWeaponAttackType: enumProxy({}), CSHitGroup: enumProxy({}), CSTeamMoneyReason: enumProxy({}),
};
globalThis.__mock_cs2 = stub;
const stubFile = path.join(os.tmpdir(), 'mock_point_script_stub.mjs');
fs.writeFileSync(stubFile, 'const s = globalThis.__mock_cs2;\nexport const ' + Object.keys(stub).map((k) => `${k} = s.${k}`).join(', ') + ';\n');
const src = fs.readFileSync(SCRIPT, 'utf8').replace(/from\s+["']cs_script\/point_script["']/g, 'from ' + JSON.stringify(pathToFileURL(stubFile).href));
const tmp = path.join(os.tmpdir(), 'mock_' + path.basename(SCRIPT).replace(/\.js$/, '') + '_' + process.pid + '.mjs');
fs.writeFileSync(tmp, src);

const safe = (what, fn) => { try { const r = fn(); if (r && r.catch) r.catch((e) => fail(what, e)); return r; } catch (e) { fail(what, e); } };
const fail = (what, e) => { stats.errors.push(what + ': ' + (e && e.stack ? e.stack.split('\n').slice(0, 3).join(' | ') : e)); };
const fire = (k, ev) => (hooks[k] || []).map((cb) => safe(k, () => cb(ev)));

try { await import(pathToFileURL(tmp).href); } catch (e) { console.log('script failed to load:', e.message); process.exit(1); } finally { fs.rmSync(tmp, { force: true }); }
fire('OnActivate');
const spawnAt = (p) => { const s = spawns.length ? spawns[Math.floor(Math.random() * spawns.length)] : null; p._p = s ? { ...s._p } : V(); p._hp = 100; p._ok = true; };
function join(slot) {
  const c = add(new Controller(slot)); players[slot] = c;
  fire('OnPlayerConnect', { player: c }); const pw = add(new Pawn(c)); pw._team = c._team; c.pawn = pw; spawnAt(pw);
  fire('OnPlayerActivate', { player: c }); fire('OnPlayerReset', { player: pw });
}
for (let i = 0; i < PLAYERS; i++) join(i);
fire('OnRoundStart');
const inputNames = (opt('inputs', '') ? opt('inputs').split(',') : null);
const chat = opt('chat', '').split(',').filter(Boolean);
const DT = 1 / 64;
for (let tick = 0; time < SECONDS; tick++) {
  time = tick * DT;
  for (const p of players) if (p && p.pawn) p.pawn.keys = Math.random() < 0.3 ? (1 << Math.floor(Math.random() * 11)) : p.pawn.keys;
  if (think && time >= nextThink) { nextThink = Infinity; safe('think', think); }
  for (let i = timers.length - 1; i >= 0; i--) if (timers[i][0] <= time) { const [, cb] = timers.splice(i, 1)[0]; safe('timer', cb); }
  if (tick % 64 === 0) {
    const live = players.filter((p) => p && p._ok && p.pawn);
    const a = live[Math.floor(Math.random() * live.length)], b = live[Math.floor(Math.random() * live.length)];
    const names = inputNames || Object.keys(inputs);
    if (names.length && a) { const n = names[Math.floor(Math.random() * names.length)]; if (inputs[n]) safe('input ' + n, () => inputs[n]({ caller: world[0], activator: a.pawn })); }
    if (a && b && Math.random() < 0.5) {
      const ev = { player: b.pawn, attacker: a.pawn, inflictor: a.pawn, weapon: a.pawn.w[0], damage: 25, damageType: 2, damageFlags: 0, hitgroup: 1 };
      fire('OnBeforePlayerDamage', ev); fire('OnModifyPlayerDamage', ev); fire('OnPlayerDamage', ev);
      b.pawn._hp -= 25; if (b.pawn._hp <= 0) { fire('OnPlayerKill', { player: b.pawn, attacker: a.pawn, inflictor: a.pawn, weapon: a.pawn.w[0] }); spawnAt(b.pawn); fire('OnPlayerReset', { player: b.pawn }); }
    }
    if (a && chat.length && Math.random() < 0.3) fire('OnPlayerChat', { player: a, text: chat[Math.floor(Math.random() * chat.length)], team: a._team });
    if (a && Math.random() < 0.2) { fire('OnPlayerJump', { player: a.pawn }); fire('OnPlayerLand', { player: a.pawn }); }
  }
  if (tick === Math.floor(SECONDS * 32)) { const p = players[1]; if (p) { p._ok = false; p.pawn._ok = false; fire('OnPlayerDisconnect', { playerSlot: 1 }); join(1); } }
  if (stats.errors.length > 20) break;
}
fire('OnRoundEnd', { winningTeam: 3, reason: 8 }); fire('OnBeginRoundRestart'); fire('OnRoundStart');
await new Promise((r) => setTimeout(r, 0));
const top = (o) => Object.entries(o).sort((x, y) => y[1] - x[1]).slice(0, 15).map(([k, v]) => k + ' x' + v).join(', ');
const ins = Object.keys(inputs);
console.log(`ran ${SECONDS}s with ${PLAYERS} players; hooks: ${Object.keys(hooks).join(', ') || 'none'}; ${ins.length} script inputs${ins.length ? ' (' + ins.slice(0, 12).join(', ') + (ins.length > 12 ? ', ...' : '') + ')' : ''}`);
console.log('Instance calls:', top(stats.calls) || 'none');
console.log('EntFire:', top(stats.fired) || 'none');
if (Object.keys(stats.unknownEntityCalls).length) console.log('entity methods not modelled (returned undefined):', top(stats.unknownEntityCalls));
if (Object.keys(stats.notInApi).length) stats.errors.push('Instance methods not in point_script.d.ts: ' + Object.keys(stats.notInApi).join(', '));
if (stats.errors.length) { console.log('ERRORS (' + stats.errors.length + '):\n  ' + [...new Set(stats.errors)].slice(0, 10).join('\n  ')); process.exit(1); }
console.log('OK: no errors');
