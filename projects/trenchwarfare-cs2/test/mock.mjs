// Runs the shipped src/mg_trenchwarfare.js (built from src/modules by create/build_script.mjs) on a stand-in cs_script engine where
// only the CURRENT API exists (Instance / Entities / Console; any deprecated Instance.* name throws). World: out/entities.json and
// the HUD xml / css restaged by tools/restage_out.py. Humans are driven through every role (infantry, mortar crews at the table, ammo
// box and tube, pilots flying, strafing and bombing); the infantry fight is a rate model (CS2's bots and players can't run here).
//
// usage: node test/mock.mjs [players=32] [seconds=120] [key=value ...]
//   seed=<n>         random seed (the script's Math.random too); default 7
//   humans=<n>       how many players are human (default 2 x round(players / 3), split evenly between the sides; the rest bots)
//   scenario=<name>  one bug class: round | churn | crew | air | reload | edge   (all = every one, each in its own process)
//   mode=balance     one round window with the real CONFIG, a JSON result line (test/sim_balance via create/sim_balance.mjs); json=1 only that
//   perf=<avg>,<max> fail when the script's think time (ms per tick) is over these
//   script=<file>    run this build of the script instead of src/mg_trenchwarfare.js (no stale check)
//   MOCK_LOG=1       print the script's console lines as they come
// Fails (exit 1) on: a script error, a stale build, a call outside the current API, an input fired at a missing entity or one its
// class lacks, a HUD id / class the xml / css lacks, a HUD call for a bot, SetModel on a shrunk pawn or after the kit was issued,
// a team kill credited, and every invariant below. Default runs with 16+ players and 300+ s print a coverage table: a feature at 0 fails.
// Invariants every 16 ticks: crew seats and aircraft point only at connected players of that side who hold them; no live pawn out of
// an aircraft left shrunk or on a camera, none frozen outside the sight; no non-finite position.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { build } from '../../../create/build_script.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const argv = process.argv.slice(2), posArgs = argv.filter((a) => !a.includes('=')), opt = Object.fromEntries(argv.filter((a) => a.includes('=')).map((a) => { const i = a.indexOf('='); return [a.slice(0, i), a.slice(i + 1)]; }));
const N = Math.min(64, +(posArgs[0] || 32)), SECONDS = +(posArgs[1] || 120);
const SCEN = opt.scenario || '', BAL = opt.mode === 'balance', JSONONLY = opt.json === '1';
const SCENARIOS = ['round', 'churn', 'crew', 'air', 'reload', 'edge'];

if (SCEN === 'all') {                      // every scenario in its own process (fresh module state), pass / total
  let ok = 0; const lines = [];
  for (const s of SCENARIOS) {
    const r = spawnSync(process.execPath, [fileURLToPath(import.meta.url), String(N), String(SECONDS), 'scenario=' + s, ...(opt.seed ? ['seed=' + opt.seed] : []), ...(opt.script ? ['script=' + opt.script] : [])], { encoding: 'utf8' });
    const last = (r.stdout || '').trim().split('\n').filter((l) => /^RESULT|^FAIL/.test(l));
    if (r.status === 0) ok++;
    lines.push((r.status === 0 ? 'pass ' : 'FAIL ') + s.padEnd(7) + ' ' + (last.slice(0, 4).join(' | ') || (r.stderr || '').slice(-300)));
  }
  for (const l of lines) console.log(l);
  console.log('scenarios: ' + ok + ' / ' + SCENARIOS.length + ' pass');
  process.exit(ok === SCENARIOS.length ? 0 : 1);
}

let seed = +(opt.seed || 7); Math.random = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
const rnd = () => Math.random();
const fails = [];
const fail = (m) => { if (!fails.includes(m) && fails.length < 40) fails.push(m); };
let time = 0, tick = 0;
const stats = { hud: 0, vars: 0, hudBots: 0, fires: {}, dmg: 0, kills: 0, teleports: 0, moves: 0, traces: 0, msgs: [], cmds: {}, setModel: 0,
                killsBy: {}, killsTeam: { 2: 0, 3: 0 }, killsTeamBy: {}, deaths: { 2: 0, 3: 0 }, assists: 0, mortarAssists: 0, teamKills: 0, blockedSeen: 0, rounds: 0, restarts: 0,
                planeHitsRifle: 0, chats: {}, churn: {}, pieces: {} };
const piece = (k, n) => { stats.pieces[k] = (stats.pieces[k] || 0) + (n === undefined ? 1 : n); };

// ------------------------------------------------------------------ the shipped script must be the build of the modules
// script=<file> runs another build instead (no stale check): how docs/REVIEW_SCRIPT_1.md proved each scenario fails without its fix
const built = build(path.join(root, 'src/build.json'), { check: true });
if (built.stale && !opt.script) { console.log('FAIL src/mg_trenchwarfare.js is stale: run  node ../../create/build_script.mjs src/build.json'); process.exit(1); }
const SRC = fs.readFileSync(opt.script ? path.resolve(opt.script) : path.join(root, 'src/mg_trenchwarfare.js'), 'utf8');
const m = /^import \{([^}]*)\} from "cs_script\/point_script";$/m.exec(SRC);
if (!m) { console.log('FAIL no import line in the shipped script'); process.exit(1); }
const RUNSRC = SRC.replace(m[0], 'const {' + m[1] + '} = globalThis.__cs;');

// ------------------------------------------------------------------ enums from Valve's d.ts (the same file api.py reads)
const dts = fs.readFileSync(path.join(root, 'test/point_script.d.ts'), 'utf8');
const ENUMS = {};
for (const mm of dts.matchAll(/export enum (\w+)\s*\{([^}]*)\}/g)) {
  const e = {}; let v = -1;
  for (let item of mm[2].replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '').split(',')) {
    item = item.trim(); if (!item) continue;
    const [k, ex] = item.split('=').map((s) => s.trim());
    if (ex !== undefined) { const sh = ex.match(/^(-?\d+)\s*<<\s*(\d+)$/); v = sh ? (+sh[1]) << +sh[2] : +ex; } else v++;
    e[k] = v;
  }
  ENUMS[mm[1]] = e;
}
const IN = ENUMS.CSInputs, MT = ENUMS.CSMoveType, DT = ENUMS.CSDamageTypes, DF = ENUMS.CSDamageFlags, GS = ENUMS.CSGearSlot, CAM = ENUMS.CustomCameraMode;

// ------------------------------------------------------------------ world
const ENTS = JSON.parse(fs.readFileSync(path.join(root, 'out/entities.json'), 'utf8'));
const xml = fs.readFileSync(path.join(root, 'out/addon/panorama/layout/custom_game/mg_trenchwarfare.xml'), 'utf8');
const css = fs.readFileSync(path.join(root, 'out/addon/panorama/styles/custom_game/mg_trenchwarfare.css'), 'utf8');
const RADAR = JSON.parse(fs.readFileSync(path.join(root, 'out/radar_region.json'), 'utf8'));
const ids = new Set([...xml.matchAll(/\bid="([^"]+)"/g)].map((x) => x[1]));
const cssHas = new Map();
const hasClass = (c) => { if (!cssHas.has(c)) cssHas.set(c, new RegExp('\\.' + c + '(?![\\w-])').test(css)); return cssHas.get(c); };
const INPUTS = { point_soundevent: ['StartSound', 'StopSound', 'SetSourceEntity'], info_particle_system: ['Start', 'Stop'], env_shake: ['StartShake'],
                 prop_dynamic: ['SetAnimation'] };
const fin = (v) => v && Number.isFinite(v.x) && Number.isFinite(v.y) && Number.isFinite(v.z);
class Ent {
  constructor(name, cls, pos, ang) { this.name = name || ''; this.cls = cls; this.pos = { ...pos }; this.ang = ang ? { ...ang } : { pitch: 0, yaw: 0, roll: 0 }; this.valid = true; this.scale = 1; }
  IsValid() { return this.valid; } GetAbsOrigin() { return { ...this.pos }; } GetAbsAngles() { return { ...this.ang }; }
  GetClassName() { return this.cls; } GetEntityName() { return this.name; } GetTeamNumber() { return 0; }
  Remove() { this.valid = false; this.removed = true; stats.removed = (stats.removed || 0) + 1; }
  SetModelScale(v) { if (!Number.isFinite(v) || v <= 0) throw new Error('bad scale ' + v); this.scale = v; } GetModelScale() { return this.scale; }
  Teleport(o) { place(this, o); stats.teleports++; }
  Move(o) { place(this, o); stats.moves++; }
  SetParent(p) { this.parent = p; } GetParent() { return this.parent; }
  FireInput(o) { if (!o || !o.input) throw new Error('FireInput needs { input }'); entInput(this, o.input); }
}
function place(e, o) {
  if (!o || typeof o !== 'object') throw new Error('Teleport/Move needs an object');
  if (o.position) { if (!fin(o.position)) throw new Error('non-finite position ' + JSON.stringify(o.position)); e.pos = { ...o.position }; }
  if (o.angles) { for (const k of ['pitch', 'yaw', 'roll']) if (!Number.isFinite(o.angles[k])) throw new Error('non-finite angles'); e.ang = { ...o.angles }; }
  if (o.velocity && !fin(o.velocity)) throw new Error('non-finite velocity');
}
function entInput(e, input) {
  stats.fires[input] = (stats.fires[input] || 0) + 1;
  const ok = INPUTS[e.cls];
  if (ok && !ok.includes(input)) fail('input ' + input + ' fired at ' + e.cls + ' ' + e.name);
  if (input === 'StopSound') e.playing = false; if (input === 'StartSound') e.playing = true;
}
let byName = new Map();
function buildWorld() {           // map entities are re-created every round
  byName = new Map(); planeList = null;
  for (const d of ENTS) if (d.name) {
    const e = new Ent(d.name, d.cls, { x: d.origin[0], y: d.origin[1], z: d.origin[2] }, { pitch: d.angles[0], yaw: d.angles[1], roll: d.angles[2] });
    if (!byName.has(d.name)) byName.set(d.name, []);
    byName.get(d.name).push(e);
  }
  const h = new Hud('tw_hud', 'custom_hud_layout', { x: 0, y: 0, z: 0 });
  byName.set('tw_hud', [h]);
}
const one = (n) => (byName.get(n) || []).find((e) => e.valid);
let planeList = null;
const allPlanes = () => (planeList || (planeList = [...byName.entries()].filter(([n]) => /^tw_plane_(t|ct)_\d+$/.test(n)).map(([, a]) => a[0]))).filter((e) => e && e.valid);

// ground: z 0, except the trench floors, pits and stations (from their named points), on a 64-u grid
const G = new Map(), GC = 64;
for (const d of ENTS) if (/^(trench_|heal_|mortarpit_|mortarcrew_)/.test(d.name || '')) {
  const [x, y, z] = d.origin;
  for (let i = -2; i <= 2; i++) for (let j = -2; j <= 2; j++) { const k = (Math.floor(x / GC) + i) + ',' + (Math.floor(y / GC) + j); G.set(k, Math.min(G.get(k) ?? 0, z - 4)); }
}
const groundAt = (x, y) => G.get(Math.floor(x / GC) + ',' + Math.floor(y / GC)) ?? 0;

// ------------------------------------------------------------------ HUD
const hudState = new Map();     // slot -> Map(key -> value)
class Hud extends Ent {
  SetHasClassForPlayer(slot, panel, cls, on) {
    stats.hud++; hudTick++;
    if (!ids.has(panel)) fail('unknown HUD panel ' + panel); if (!hasClass(cls)) fail('no css for class ' + cls);
    if (ctls[slot] && ctls[slot].bot) stats.hudBots++;
    let s = hudState.get(slot); if (!s) hudState.set(slot, s = new Map()); s.set(panel + '.' + cls, !!on);
  }
  SetDialogVariableStringForPlayer(slot, panel, n, v) {
    stats.vars++; hudTick++;
    if (!ids.has(panel)) fail('unknown HUD panel ' + panel); if (typeof v !== 'string') fail('non-string dialog var ' + panel);
    if (ctls[slot] && ctls[slot].bot) stats.hudBots++;
  }
  ResetForPlayer(slot) { hudState.delete(slot); }
}
let hudTick = 0;

// ------------------------------------------------------------------ players
const lobbyT = ENTS.filter((e) => e.cls === 'info_player_terrorist'), lobbyCT = ENTS.filter((e) => e.cls === 'info_player_counterterrorist');
const STOCK = 'characters/models/stock_agent.vmdl';
const PISTOL_CLS = new Set(['weapon_glock', 'weapon_hkp2000', 'weapon_p250', 'weapon_usp_silencer']);
class Weapon {
  constructor(n, owner) { this.n = n; this.owner = owner; this.clip = 10; this.res = 90; this.valid = true; }
  GetClassName() { return this.n; } GetClipAmmo() { return this.clip; } SetClipAmmo(v) { if (!Number.isInteger(v)) fail('SetClipAmmo non-integer'); this.clip = v; }
  GetReserveAmmo() { return this.res; } SetReserveAmmo(v) { this.res = v; } IsValid() { return this.valid; } GetOwner() { return this.owner; }
  GetData() { return { GetDamage: () => 88 }; }
  get slot() { return this.n.startsWith('weapon_knife') ? GS.KNIFE : PISTOL_CLS.has(this.n) ? GS.PISTOL : GS.RIFLE; }
}
class Cam extends Ent {
  constructor(p) { super('', 'camera', { x: 0, y: 0, z: 0 }); this.p = p; this.mode = CAM.DISABLED; }
  GetPlayer() { return this.p; } SetMode(m) { this.mode = m; stats.cam = (stats.cam || 0) + 1; } GetMode() { return this.mode; }
  SetFollowConfig(c) { if (!c || !c.followEntity) throw new Error('SetFollowConfig without followEntity'); if (!c.followEntity.valid) fail('camera follows a removed entity'); }
}
class Pawn extends Ent {
  constructor(ctl) { super('', 'player', { x: 0, y: -3000, z: -2892 }); this.ctl = ctl; this.hp = 0; this.armor = 0; this.helmet = false; this.weapons = []; this.keys = 0; this.prev = 0; this.mt = MT.WALK; this.model = STOCK; this.eye = { pitch: 0, yaw: 0, roll: 0 }; }
  IsValid() { return this.valid && this.ctl.connected; }
  GetPlayerController() { return this.ctl.connected ? this.ctl : undefined; } GetTeamNumber() { return this.ctl.team; } IsAlive() { return this.hp > 0; }
  GetHealth() { return this.hp; } SetHealth(v) { if (!Number.isInteger(v)) fail('SetHealth non-integer ' + v); this.hp = v; }
  GetArmor() { return this.armor; } SetArmor(v) { if (!Number.isInteger(v)) fail('SetArmor non-integer ' + v); this.armor = v; } HasHelmet() { return this.helmet; } SetHasHelmet(v) { this.helmet = !!v; }
  IsInputPressed(b) { return (this.keys & b) !== 0; } WasInputJustPressed(b) { return (this.keys & ~this.prev & b) !== 0; }
  SetEyeAngles(a) { for (const k of ['pitch', 'yaw', 'roll']) if (!Number.isFinite(a[k])) throw new Error('bad eye angles'); this.eye = { ...a }; } GetEyeAngles() { return { ...this.eye }; }
  SetMoveType(m) { this.mt = m; } GetMoveType() { return this.mt; }
  GetModelName() { return this.model; }
  SetModel(mdl) {
    if (!fs.existsSync(path.join(root, 'out/addon', mdl)) && mdl !== STOCK) fail('SetModel to a model the addon lacks: ' + mdl);
    if (this.scale !== 1) fail('SetModel on a shrunk pawn (slot ' + this.ctl.slot + ')');
    if (this.issued) fail('SetModel after the kit was issued (weapons out: the giant first-person weapon path), slot ' + this.ctl.slot);
    this.model = mdl; stats.setModel++;
  }
  GetCustomCamera() { return this.cam || (this.cam = new Cam(this)); }
  DestroyWeapons() { for (const w of this.weapons) w.valid = false; this.weapons = []; this.active = undefined; }
  DestroyWeapon(w) { if (!w || !w.valid) throw new Error('Invalid entity (DestroyWeapon)'); w.valid = false; this.weapons = this.weapons.filter((x) => x !== w); if (this.active === w) this.active = this.weapons[0]; }
  GiveNamedItem(n, deploy) { if (this.weapons.find((w) => w.n === n)) fail('duplicate weapon ' + n); const w = new Weapon(n, this); this.weapons.push(w); if (deploy || !this.active) this.active = w; this.issued = true; }
  FindWeapon(n) { return this.weapons.find((w) => w.n === n); } FindWeaponBySlot(s) { return this.weapons.find((w) => w.slot === s); }
  GetActiveWeapon() { return this.active; } SwitchToWeapon(w) { if (this.weapons.includes(w)) this.active = w; }
  TakeDamage(d) { return hurt(this, d); }
}
class Ctl {
  constructor(slot, team, bot) { this.slot = slot; this.team = team; this.bot = bot; this.connected = true; this.pawn = new Pawn(this); this.respawnAt = time + 0.1; this.since = time; }
  IsValid() { return this.connected; } GetPlayerSlot() { return this.slot; } GetPlayerPawn() { return this.connected && this.pawn.hp > 0 || this.connected ? this.pawn : undefined; }
  IsBot() { return this.bot; } GetPlayerName() { return (this.bot ? 'bot' : 'p') + this.slot; } GetTeamNumber() { return this.team; } IsConnected() { return this.connected; }
  GetClassName() { return 'cs_player_controller'; } GetEntityName() { return ''; }
}
const ctls = new Array(64).fill(undefined);
const everyone = () => ctls.filter((c) => c && c.connected);
function spawn(c) {
  if (!c.connected || (c.team !== 2 && c.team !== 3)) return;
  const sp = c.team === 2 ? lobbyT : lobbyCT, e = sp[c.slot % sp.length];
  const p = c.pawn;
  p.pos = { x: e.origin[0], y: e.origin[1], z: e.origin[2] }; p.hp = 100; p.armor = 0; p.helmet = false; p.mt = MT.WALK; p.model = STOCK;
  p.weapons = []; p.active = undefined; p.GiveNamedItem(c.team === 3 ? 'weapon_knife' : 'weapon_knife_t'); p.GiveNamedItem(c.team === 3 ? 'weapon_hkp2000' : 'weapon_glock');
  p.issued = false;               // the spawn loadout is the engine's; the script's kit sets issued
  p.keys = p.prev = 0; p.dmgBy = new Map(); p.spawnedAt = time;
  // the engine does NOT reset model scale or the custom camera here (worst case): the script has to
  c.respawnAt = Infinity;
  hooks.reset && hooks.reset({ player: p });
}
let curSrc = '';
function hurt(v, d) {
  if (!d || !(d.damage > 0) || !Number.isFinite(d.damage)) { fail('TakeDamage needs a finite damage > 0: ' + JSON.stringify(d && d.damage)); return 0; }
  if (v.hp <= 0) return 0;
  let dmg = d.damage, flags = d.damageFlags || 0, types = d.damageTypes || 0;
  if (hooks.mod) {
    const r = hooks.mod({ player: v, damage: dmg, damageTypes: types, damageFlags: flags, hitGroup: 0, attacker: d.attacker, inflictor: d.inflictor, weapon: d.weapon });
    if (r && r.abort) { stats.blocked = (stats.blocked || 0) + 1; return 0; }
    if (r && Number.isFinite(r.damage)) dmg = r.damage; if (r && r.damageFlags !== undefined) flags = r.damageFlags;
  }
  let hpLoss = dmg;
  if (!(flags & DF.IGNORE_ARMOR) && v.armor > 0 && (types & (DT.BLAST | DT.BULLET))) { hpLoss = dmg * 0.5; v.armor = Math.max(0, Math.round(v.armor - dmg * 0.25)); }
  hpLoss = Math.max(1, Math.round(hpLoss));
  stats.dmg++;
  const a = d.attacker && d.attacker.ctl ? d.attacker : undefined;
  if (a && a !== v) v.dmgBy.set(a.ctl, (v.dmgBy.get(a.ctl) || 0) + Math.min(hpLoss, v.hp));
  v.hp -= hpLoss;
  if (v.hp <= 0) { v.hp = 0; die(v, d.attacker, d.inflictor, d.weapon); }
  return hpLoss;
}
function die(pawn, attacker, inflictor, weapon) {
  stats.kills++;
  const c = pawn.ctl, a = attacker && attacker.ctl ? attacker : undefined;
  pawn.killedBy = a ? a.ctl : undefined;
  stats.deaths[c.team] = (stats.deaths[c.team] || 0) + 1;
  if (a && a !== pawn) {
    if (a.ctl.team === c.team) { stats.teamKills++; fail('team kill credited: slot ' + a.ctl.slot + ' killed team-mate ' + c.slot + ' (' + (curSrc || 'script') + ')'); }
    else stats.killsTeam[a.ctl.team]++;
    if (!a.ctl.connected) fail('kill credited to a disconnected player');
    for (const [ac, dmg] of pawn.dmgBy) if (ac !== a.ctl && ac.team !== c.team && dmg >= 41) { stats.assists++; const pr = dbg().players.get(ac.slot); if (pr && pr.role === 'mortar') stats.mortarAssists++; }
  }
  if (curSrc) stats.killsBy[curSrc] = (stats.killsBy[curSrc] || 0) + 1;
  if (a && a !== pawn && a.ctl.team !== c.team) { const tb = (stats.killsTeamBy[a.ctl.team] = stats.killsTeamBy[a.ctl.team] || {}); if (curSrc) tb[curSrc] = (tb[curSrc] || 0) + 1; }
  hooks.kill && hooks.kill({ player: pawn, attacker, inflictor, weapon });
  c.respawnAt = time + 2;          // mp_respawn_on_death
}

// ------------------------------------------------------------------ the API (current names only)
const hooks = {};
const strict = (name, obj) => new Proxy(obj, { get(t, k) { if (k in t || typeof k === 'symbol') return t[k]; throw new Error(name + '.' + String(k) + ' is not in the current API (deprecated or misspelt)'); } });
function traceLine(o) {
  stats.traces++;
  for (const v of [o.start, o.end]) if (!fin(v)) throw new Error('bad trace ' + JSON.stringify(o));
  const d = { x: o.end.x - o.start.x, y: o.end.y - o.start.y, z: o.end.z - o.start.z }, L = Math.hypot(d.x, d.y, d.z) || 1e-6;
  const ign = Array.isArray(o.ignoreEntity) ? o.ignoreEntity : o.ignoreEntity ? [o.ignoreEntity] : [];
  let f = 1, hitEntity;
  if (o.start.z > groundAt(o.start.x, o.start.y) - 40) {          // underground rooms (the lobby) see no ground
    if (Math.abs(d.x) + Math.abs(d.y) < 1e-3) { const gz = groundAt(o.start.x, o.start.y); if (d.z < 0 && o.end.z < gz && o.start.z >= gz) f = (o.start.z - gz) / (o.start.z - o.end.z); }
    else {
      const steps = Math.min(240, Math.ceil(L / 48)); let pf = 0;
      for (let i = 1; i <= steps; i++) {
        const cf = i / steps, x = o.start.x + d.x * cf, y = o.start.y + d.y * cf, z = o.start.z + d.z * cf;
        if (z < groundAt(x, y)) { let lo = pf, hi = cf; for (let k = 0; k < 6; k++) { const mid = (lo + hi) / 2; if (o.start.z + d.z * mid < groundAt(o.start.x + d.x * mid, o.start.y + d.y * mid)) hi = mid; else lo = mid; } f = lo; break; }
        pf = cf;
      }
    }
  }
  if (f < 1) hitEntity = worldEnt;
  const along = (q, r) => { const w = { x: q.x - o.start.x, y: q.y - o.start.y, z: q.z - o.start.z }, t = (w.x * d.x + w.y * d.y + w.z * d.z) / L;
    if (t <= 0 || t >= f * L) return -1; return Math.hypot(w.x - d.x * t / L, w.y - d.y * t / L, w.z - d.z * t / L) < r ? t / L : -1; };
  for (const e of allPlanes()) { if (ign.includes(e)) continue; const t = along(e.pos, 150); if (t >= 0) { f = t; hitEntity = e; } }
  if (!o.ignorePlayers) for (const c of everyone()) {
    const p = c.pawn; if (p.hp <= 0 || p.scale < 0.5 || ign.includes(p)) continue;
    for (const hz of [12, 36, 60]) { const t = along({ x: p.pos.x, y: p.pos.y, z: p.pos.z + hz }, 18); if (t >= 0) { f = t; hitEntity = p; break; } }   // a standing body: three spheres
  }
  const end = { x: o.start.x + d.x * f, y: o.start.y + d.y * f, z: o.start.z + d.z * f };
  return { didHit: f < 1, fraction: f, end, hitEntity: f < 1 ? hitEntity : undefined, startedInSolid: false, normal: { x: 0, y: 0, z: 1 } };
}
const worldEnt = new Ent('', 'worldent', { x: 0, y: 0, z: 0 });
const Instance = strict('Instance', {
  _think: null, _next: undefined,
  GetGameTime: () => time, SetThink: (f) => { Instance._think = f; }, SetNextThink: (t) => { if (!Number.isFinite(t)) throw new Error('bad think time'); Instance._next = t; },
  OnActivate: (f) => { hooks.activate = f; }, OnRoundStart: (f) => { hooks.round = f; }, OnPlayerReset: (f) => { hooks.reset = f; }, OnPlayerDisconnect: (f) => { hooks.disc = f; },
  OnPlayerKill: (f) => { hooks.kill = f; }, OnPlayerChat: (f) => { hooks.chat = f; }, OnBulletImpact: (f) => { hooks.bullet = f; }, OnModifyPlayerDamage: (f) => { hooks.mod = f; },
  OnScriptReload: (c) => { hooks.reloadCfg = c; },
  GetPlayerController: (s) => (ctls[s] && ctls[s].connected ? ctls[s] : undefined), TraceLine: traceLine,
});
const Entities = strict('Entities', {
  FindByName: (n) => (byName.get(n) || []).filter((e) => e.valid),
  FireInput: (o) => {
    const list = (byName.get(o.name) || []).filter((e) => e.valid);
    if (!list.length) { fail('Entities.FireInput at a missing entity ' + o.name); return; }
    for (const e of list) e.FireInput(o);
  },
});
const Console = strict('Console', {
  Log: (msg) => { const s = String(msg); stats.msgs.push(s); if (stats.msgs.length > 4000) stats.msgs.splice(0, 1000); if (process.env.MOCK_LOG) console.log(time.toFixed(2), s); },
  ServerCommand: (c) => {
    const w = String(c).split(' ')[0]; stats.cmds[w] = (stats.cmds[w] || 0) + 1;
    if (!/^(mp_|bot_|say$)/.test(w)) fail('server command outside mp_ / bot_ / say: ' + c);
    if (/[;\n]/.test(c)) fail('unsafe characters in a server command: ' + c);
    if (w === 'say') stats.says = (stats.says || []).concat([String(c).slice(4)]).slice(-50);
  },
});
globalThis.__cs = { Instance, Entities, Console, ...ENUMS };
const dbg = () => globalThis.__twDebug;
let loads = 0;
async function loadScript() {
  const tmp = path.join(root, 'test', '_run_' + process.pid + '_' + (loads++) + '.mjs');
  fs.writeFileSync(tmp, RUNSRC);
  try { await import(pathToFileURL(tmp).href); } finally { fs.unlinkSync(tmp); }
}

// ------------------------------------------------------------------ start
buildWorld();
await loadScript();
const HUMANS = opt.humans !== undefined ? +opt.humans : 2 * Math.round(N / 3);
// slots: team by slot parity; within each team the humans first take the places not 2 mod 3, so both sides get the same mix
{
  const want = { 2: Math.ceil(HUMANS / 2), 3: Math.floor(HUMANS / 2) }, idx = { 2: [], 3: [] };
  for (let s = 0; s < N; s++) idx[s % 2 ? 3 : 2].push(s);
  for (const team of [2, 3]) {
    const order = idx[team].map((s, i) => [s, i]).sort((a, b) => ((a[1] % 3 === 2) - (b[1] % 3 === 2)) || a[1] - b[1]);
    order.forEach(([s], k) => { ctls[s] = new Ctl(s, team, k >= want[team]); });
  }
}
hooks.activate();
hooks.round && hooks.round(); stats.rounds++;
const CFG = dbg().CONFIG;

// ------------------------------------------------------------------ helpers for drivers / set pieces
const PR = (slot) => dbg().players.get(slot);
const alive = (c) => c && c.connected && c.pawn.hp > 0;
const onGround = (c) => alive(c) && c.pawn.pos.z > -1000 && !(PR(c.slot) && PR(c.slot).air);
const tagOf = (team) => (team === 2 ? 't' : 'ct');
function say(c, text) { stats.chats[text] = (stats.chats[text] || 0) + 1; hooks.chat({ player: c, text, team: c.team }); }
function disconnect(c, why) {
  c.connected = false; c.pawn.valid = false; ctls[c.slot] = undefined; stats.churn[why || 'leave'] = (stats.churn[why || 'leave'] || 0) + 1;
  hooks.disc && hooks.disc({ playerSlot: c.slot });
}
function connect(slot, team, bot) { const c = new Ctl(slot, team, bot); ctls[slot] = c; c.respawnAt = time + 0.5; return c; }
function switchTeam(c, team) {                    // CS2: the pawn dies and the controller joins the other side (or spectates: team 1)
  if (c.pawn.hp > 0) { c.pawn.hp = 0; hooks.kill && hooks.kill({ player: c.pawn, attacker: undefined }); }
  c.team = team; c.respawnAt = team >= 2 ? time + 1 : Infinity; stats.churn['team ' + team] = (stats.churn['team ' + team] || 0) + 1;
}
function roundRestart(order) {                     // map entities re-created, every pawn back at spawn, OnRoundStart (order alternates)
  stats.restarts++;
  buildWorld();
  const respawnAll = () => { for (const c of everyone()) if (c.team >= 2) spawn(c); };
  if (order) { hooks.round(); respawnAll(); } else { respawnAll(); hooks.round(); }
  stats.rounds++;
}
// which of the enemies a test-driven human shoots / shells / bombs: a random live one on the ground
function enemyOnGround(team) { const l = everyone().filter((c) => c.team !== team && c.team >= 2 && onGround(c) && Math.abs(c.pawn.pos.x) < 4000); return l.length ? l[Math.floor(rnd() * l.length)] : undefined; }

// mortar crew driver: ammo box -> tube (load) -> table (sight: steer, lock on an enemy, fire) -> leave; per 0.125 s step
function driveCrew(c, pr) {
  const p = c.pawn, t = tagOf(c.team), k = pr.crew + 1;
  const A = one(`mortarcrew_${t}_${k}_a`), B = one(`mortarcrew_${t}_${k}_b`), pit = one(`mortarpit_${t}_${k}`);
  if (!A || !B || !pit) return;
  const crew = dbg().crews[c.team][pr.crew];
  const st = c.crewSt || (c.crewSt = { phase: 0, wait: 0 });
  if (time < st.wait) return;
  st.wait = time + 0.125;
  if (pr.inSight) {
    if (!st.aim) { const e = enemyOnGround(c.team); st.aim = e ? { x: e.pawn.pos.x, y: e.pawn.pos.y } : { x: c.team === 2 ? 1649 : -1649, y: (rnd() - 0.5) * 5000 }; }
    const want = dbg().worldToSight(c.team, st.aim.x, st.aim.y), step = 1 / CFG.TARGET_STEPS;
    let keys = 0;
    if (pr.u < want.u - step) keys |= IN.RIGHT; else if (pr.u > want.u + step) keys |= IN.LEFT;
    if (pr.v < want.v - step) keys |= IN.BACK; else if (pr.v > want.v + step) keys |= IN.FORWARD;
    if (keys) { p.keys = keys; return; }
    if (!st.locked) { p.keys = IN.ATTACK; st.locked = true; return; }
    if (crew.loaded && time >= crew.cooldown) { p.keys = IN.JUMP; st.fired = (st.fired || 0) + 1; st.locked = false; st.aim = undefined; return; }
    if (!crew.loaded) { p.keys = IN.USE; st.locked = false; st.aim = undefined; return; }     // leave the sight to fetch a bomb
    return;
  }
  const d2 = (q) => Math.hypot(p.pos.x - q.pos.x, p.pos.y - q.pos.y);
  if (pr.carrying) { if (d2(pit) > 40) { p.pos = { ...pit.pos }; return; } p.keys = IN.USE; return; }
  if (!crew.loaded && !pr.carrying && pr.seat === 'b') { if (d2(B) > 30) { p.pos = { ...B.pos }; return; } p.keys = IN.USE; return; }
  if (pr.seat === 'a' || crew.loaded) { if (d2(A) > 30) { p.pos = { ...A.pos }; return; } p.keys = IN.USE; return; }
  if (!crew.loaded && pr.seat === 'a') { if (d2(B) > 30) { p.pos = { ...B.pos }; return; } p.keys = IN.USE; }
}
// pilot driver: dive on an enemy on the ground, guns when lined up, a bomb when the sight's landing point is on him, climb when low
function drivePilot(c, pr) {
  const a = pr.air, p = c.pawn;
  if (c.afk) { p.keys = 0; return; }
  const gz = groundAt(a.pos.x, a.pos.y), alt = a.pos.z - gz;
  if (!c.target || !alive(c.target) || time > c.targetUntil) { c.target = enemyOnGround(c.team); c.targetUntil = time + 12; }
  let dir, keys = (Math.floor(time * 2) % 3 === 0 ? IN.FORWARD : 0);
  if (c.target) {
    const q = c.target.pawn.pos, dx = q.x - a.pos.x, dy = q.y - a.pos.y, dz = q.z + 40 - a.pos.z, h = Math.hypot(dx, dy);
    // attack profile: cruise at ~1000 u, a shallow dive (at most ~35 degrees) from 2200 u out, pull out at 550 u or once past him
    const diving = h < 2200 && alt > 550 && -dz < h * 0.7 && (a.f.x * dx + a.f.y * dy) > 0;
    dir = diving ? { x: dx, y: dy, z: dz } : { x: dx, y: dy, z: Math.max(-0.25, Math.min(0.35, (1000 - alt) / 1500)) * Math.max(h, 1) };
    if (alt < 550 && !diving) dir = { x: dx, y: dy, z: Math.max(h, 1) * 0.5 };
    if (alt < 400) dir = { x: a.f.x, y: a.f.y, z: 0.8 };
    const L = Math.hypot(dir.x, dir.y, dir.z) || 1, cosA = (a.f.x * dir.x + a.f.y * dir.y + a.f.z * dir.z) / L;
    if (cosA > 0.97 && Math.hypot(dx, dy, dz) < 3200 && alt > 200) keys |= IN.ATTACK;          // a human holds the trigger on the run in
    if (a.land && Math.hypot(a.land.x - q.x, a.land.y - q.y) < 260 && Math.floor(time * 8) % 2 === 0) keys |= IN.ATTACK2;
  } else dir = { x: c.team === 2 ? 1 : -1, y: 0, z: alt < 900 ? 0.3 : 0 };
  const toEye = (v) => { const L = Math.hypot(v.x, v.y, v.z) || 1; return { pitch: -Math.asin(Math.max(-1, Math.min(1, v.z / L))) * 180 / Math.PI, yaw: Math.atan2(v.y, v.x) * 180 / Math.PI, roll: 0 }; };
  p.eye = toEye(dir);
  if (c.target && (keys & IN.ATTACK)) {
    // a human puts the CROSSHAIR on the man: the chase camera sits behind and above the aircraft (the script's gunAim), so aim from there
    const q = c.target.pawn.pos, A = CFG.AIR, back = a.camBack || -A.CAM_OFFSET.x;
    for (let k = 0; k < 3; k++) {
      const P_ = p.eye.pitch * Math.PI / 180, Y = p.eye.yaw * Math.PI / 180;
      const f = { x: Math.cos(P_) * Math.cos(Y), y: Math.cos(P_) * Math.sin(Y), z: -Math.sin(P_) };
      const u = { x: Math.sin(P_) * Math.cos(Y), y: Math.sin(P_) * Math.sin(Y), z: Math.cos(P_) };
      const cam = { x: a.pos.x + A.CAM_FOLLOW.x - f.x * back + u.x * A.CAM_OFFSET.z, y: a.pos.y + A.CAM_FOLLOW.y - f.y * back + u.y * A.CAM_OFFSET.z, z: a.pos.z + A.CAM_FOLLOW.z - f.z * back + u.z * A.CAM_OFFSET.z };
      p.eye = toEye({ x: q.x - cam.x, y: q.y - cam.y, z: q.z + 36 - cam.z });
    }
  }
  p.keys = keys;
}

// infantry rate model: every 0.25 s each infantryman on the ground may kill the nearest enemy on the ground within 4200 u
// (mean time to kill 18 s at 3300 u, the width of no man's land), and puts rounds into an enemy aircraft within 2600 u
const FIGHT = { ENGAGE: +(opt.engage || 4200), TTK: +(opt.ttk || 30), REF: 3300, PLANE_R: 2600, PLANE_P: +(opt.planep || 0.006) };
function fightModel() {
  const D = dbg(), list = everyone().filter(onGround);
  const flyers = everyone().filter((c) => alive(c) && PR(c.slot) && PR(c.slot).air);
  for (const c of list) {
    const pr = D.players.get(c.slot); if (!pr || pr.role !== 'infantry' || !pr.deployed) continue;
    let best, bd = FIGHT.ENGAGE;
    for (const e of list) if (e.team !== c.team) { const d = Math.hypot(e.pawn.pos.x - c.pawn.pos.x, e.pawn.pos.y - c.pawn.pos.y); if (d < bd) { bd = d; best = e; } }
    if (best && rnd() < 0.25 / Math.min(60, Math.max(5, FIGHT.TTK * bd / FIGHT.REF))) {
      curSrc = 'rifle'; best.pawn.TakeDamage({ damage: 200, damageTypes: DT.BULLET, attacker: c.pawn, inflictor: c.pawn, weapon: c.pawn.active }); curSrc = '';
    }
    for (const f of flyers) if (f.team !== c.team && !(SCEN === 'air' && f.afk)) {   // the air scenario's AFK pilot must live long enough to be AFK
      const a = PR(f.slot).air; if (!a) continue;
      if (Math.hypot(a.pos.x - c.pawn.pos.x, a.pos.y - c.pawn.pos.y, a.pos.z - c.pawn.pos.z) < FIGHT.PLANE_R && rnd() < FIGHT.PLANE_P) {
        stats.planeHitsRifle++;
        hooks.bullet({ weapon: new Weapon('weapon_awp', c.pawn), position: { ...a.pos }, hitEntity: a.ac.ent });
      }
    }
  }
}

// ------------------------------------------------------------------ invariants
function invariants() {
  const D = dbg(), pts = D.points;
  for (const team of [2, 3]) D.crews[team].forEach((cr, k) => {
    for (const seat of ['a', 'b']) {
      const s = cr[seat]; if (s < 0) continue;
      const c = ctls[s], pr = D.players.get(s);
      if (!c || !c.connected) fail('crew ' + tagOf(team) + '_' + (k + 1) + seat + ' points at a slot with nobody connected (' + s + ')');
      else if (c.team !== team) fail('crew ' + tagOf(team) + '_' + (k + 1) + ' seat held by a player now on ' + (c.team >= 2 ? 'the other side' : 'no side (spectating)'));
      else if (!pr || pr.crew !== k || pr.seat !== seat || pr.role !== 'mortar') fail('crew seat ' + tagOf(team) + '_' + (k + 1) + seat + ' and the player record disagree');
    }
  });
  if (pts) for (const team of [2, 3]) for (const ac of pts.aircraft[team] || []) {
    if (!fin(ac.ent.pos)) fail('aircraft at a non-finite position');
    if (ac.pilot < 0) continue;
    const pr = D.players.get(ac.pilot), c = ctls[ac.pilot];
    if (!c || !c.connected) fail('aircraft ' + ac.ent.name + ' held by a slot with nobody connected');
    else if (c.team !== team) fail('aircraft ' + ac.ent.name + ' held by a player who left its side');
    else if (!pr || !pr.air || pr.air.ac !== ac) fail('aircraft ' + ac.ent.name + ' held by a player who is not flying it');
  }
  for (const [s, pr] of D.players) {
    const c = ctls[s];
    if (!c || !c.connected) { fail('player record kept for disconnected slot ' + s); continue; }
    if (pr.air && (!pts || pr.air.ac.pilot !== s)) fail('player ' + s + ' flies an aircraft that is not his');
    const p = c.pawn;
    if (p.hp > 0 && !pr.air && time - p.spawnedAt > 0.05) {
      if (p.scale !== 1) fail('live pawn left shrunk out of an aircraft (slot ' + s + ')');
      if (p.cam && p.cam.mode !== CAM.DISABLED) fail('live pawn left on a camera out of an aircraft (slot ' + s + ')');
      if (!pr.inSight && p.mt === MT.NONE) fail('live pawn left frozen outside the sight (slot ' + s + ')');
    }
    if (p.hp > 0 && !fin(p.pos)) fail('non-finite pawn position');
  }
}

// ------------------------------------------------------------------ scenario set pieces (time -> function); checks fail() themselves
const at = [];
const when = (t, fn, name) => at.push({ t, fn, name });
const humansOf = (team) => everyone().filter((c) => !c.bot && (!team || c.team === team));
const flying = () => everyone().filter((c) => alive(c) && PR(c.slot) && PR(c.slot).air);
const crewInSight = () => everyone().filter((c) => alive(c) && PR(c.slot) && PR(c.slot).inSight);
const parkOf = (ac) => ac.park;
const D_pick = (team) => dbg().pickTrench(team, undefined, true);
function forceAir(n) { for (const c of humansOf().slice(0, n)) say(c, '!air'); }   // in the briefing room: posted at once if a plane is free

if (SCEN === 'round') {
  when(1, () => forceAir(6));
  for (const [k, t] of [[0, 40], [1, 75], [0, 100]].entries()) when(t[1], () => {
    const fl = flying().length, sg = crewInSight().length;
    piece('restart with ' + fl + ' flying, ' + sg + ' in the sight');
    if (k === 0 && !fl) fail('round scenario: nobody was flying at the first restart');
    roundRestart(t[0]);
    const D = dbg();
    for (const pr of D.players.values()) if (pr.air) fail('round restart left a player flying');
    for (const team of [2, 3]) for (const cr of D.crews[team]) if (cr.loaded || cr.target || cr.impacts.length) fail('round restart left a crew loaded / targeted');
    if (D.shells.length) fail('round restart left shells in flight');
    if (D.unlocked.size) fail('round restart left areas unlocked');
    for (const c of everyone()) if (c.pawn.hp > 0 && (c.pawn.scale !== 1 || c.pawn.mt !== MT.WALK || (c.pawn.cam && c.pawn.cam.mode !== CAM.DISABLED))) fail('round restart left a pawn shrunk / frozen / on a camera');
  }, 'restart');
  when(120, () => { if (stats.restarts < 3) fail('round scenario: fewer than 3 restarts'); });
}
if (SCEN === 'churn') {
  when(1, () => forceAir(4));
  let next = 20;
  const ev = () => {
    const D = dbg(), list = everyone(), pick = (l) => l[Math.floor(rnd() * l.length)];
    const pilots = flying(), sight = crewInSight(), carriers = list.filter((c) => PR(c.slot) && PR(c.slot).carrying);
    const loaders = list.filter((c) => D.shells.some((s) => s.loaderSlot === c.slot || s.firerSlot === c.slot));
    const kinds = [['pilot-air', pilots], ['sight', sight], ['carrying', carriers], ['shell-in-flight', loaders], ['any', list]];
    const [why, pool] = kinds[Math.floor(rnd() * kinds.length)];
    const c = pool.length ? pick(pool) : pick(list); if (!c) return;
    const r = rnd();
    if (r < 0.4) {
      const slot = c.slot, team = c.team, ac = PR(slot) && PR(slot).air ? PR(slot).air.ac : undefined;
      disconnect(c, why);
      if (ac) {
        tickOnce();
        if (ac.pilot === slot) fail('a pilot who disconnected mid-air still holds his aircraft');
        if (Math.hypot(ac.ent.pos.x - ac.park.x, ac.ent.pos.y - ac.park.y, ac.ent.pos.z - ac.park.z) > 1) fail('the aircraft of a pilot who disconnected was not taken home');
        const eng = one('tw_plane_eng_' + ac.ent.name.slice(9)); if (eng && eng.playing) fail('engine sound left playing after the pilot disconnected');
        piece('pilot disconnects mid-air');
      }
      when(time + 1 + rnd() * 3, () => {
        if (ctls[slot]) return;
        // the engine may still hold the last player's HUD overrides for the slot: a marker stands for them; the newcomer's first
        // think must have reset the slot (ResetForPlayer clears it)
        let st = hudState.get(slot); if (!st) hudState.set(slot, st = new Map()); st.set('tw_fly.stale', true);
        const n = connect(slot, rnd() < 0.5 ? team : 5 - team, rnd() < 0.3); n.fresh = true; piece('slot reused');
        tickOnce(); tickOnce();
        const st2 = hudState.get(slot); if (st2 && st2.get('tw_fly.stale')) fail('slot reuse: the newcomer in slot ' + slot + ' kept the last player HUD');
      });
    } else if (r < 0.7) { switchTeam(c, 5 - c.team); piece('team switch (' + why + ')'); }
    else if (r < 0.85) { const dead = c.pawn.hp <= 0; switchTeam(c, 1); piece(dead ? 'spectate while dead' : 'spectate'); const slot = c.slot; when(time + 3, () => { if (ctls[slot] === c) switchTeam(c, 2 + Math.floor(rnd() * 2)); }); }
    else { c.pawn.TakeDamage({ damage: 500, damageTypes: DT.GENERIC, attacker: c.pawn }); switchTeam(c, 5 - c.team); piece('team switch while dead'); }
  };
  for (let t = next; t < SECONDS - 5; t += 2.5) when(t, ev);
  // slot reuse: the newcomer must not inherit the HUD classes of the last player
  when(SECONDS - 4, () => { for (const c of everyone()) if (c.fresh && !c.bot) { const s = hudState.get(c.slot); if (s && s.get('tw_fly.show') && !(PR(c.slot) && PR(c.slot).air)) fail('slot reuse: newcomer ' + c.slot + ' sees the last player\'s cockpit'); } });
}
if (SCEN === 'crew') {
  when(30, () => {
    const D = dbg();
    // (a) world damage (a fall, a trigger) to a crewman at his tube: blocked and logged
    const crew = everyone().filter((c) => alive(c) && PR(c.slot) && PR(c.slot).role === 'mortar' && PR(c.slot).deployed && PR(c.slot).crew >= 0);
    if (!crew.length) { fail('crew scenario: no deployed crew'); return; }
    const c = crew[0], hp0 = c.pawn.hp, b0 = stats.blocked || 0;
    const pit = D.pitPos(c.team, PR(c.slot).crew); c.pawn.pos = { x: pit.x + 60, y: pit.y, z: pit.z };
    c.pawn.TakeDamage({ damage: 60, damageTypes: DT.FALL });
    if (c.pawn.hp !== hp0 || (stats.blocked || 0) !== b0 + 1) fail('world damage to a crewman at his tube was not blocked');
    if (!stats.msgs.some((x) => x.startsWith('[tw] blocked') && x.includes('mortar pit'))) fail('no "[tw] blocked" console line for the crewman');
    piece('world damage at the pit blocked');
    // (b) his own crew's shell on his own pit: nobody on his side is hurt
    const before = everyone().filter((q) => q.team === c.team && alive(q)).map((q) => q.pawn.hp);
    const k = PR(c.slot).crew, cr = D.crews[c.team][k];
    cr.loaded = true; cr.target = { x: pit.x, y: pit.y }; cr.cooldown = 0; cr.loader = c.slot; cr.loaderGen = PR(c.slot).gen;
    if (!D.fireMortar(c.team, k, c.slot)) fail('fireMortar refused a loaded, targeted tube');
    const sh = D.shells[D.shells.length - 1]; sh.x = pit.x; sh.y = pit.y; sh.t = time;
    tickOnce();
    const after = everyone().filter((q) => q.team === c.team && alive(q)).map((q) => q.pawn.hp);
    if (before.length !== after.length || before.some((h, i) => after[i] < h)) fail('a crew\'s own shell hurt its own side');
    piece('own shell on own pit: no harm');
  });
  when(45, () => {
    // (c) an enemy shell on a crew: the kill goes to the enemy firer, and "[tw] crew death" says what killed him
    const D = dbg();
    const victims = everyone().filter((c) => onGround(c) && PR(c.slot) && PR(c.slot).role === 'mortar' && PR(c.slot).crew >= 0);
    const v = victims[0]; if (!v) { fail('crew scenario: no crew to shell'); return; }
    const enemyCrew = everyone().filter((c) => c.team !== v.team && alive(c) && PR(c.slot) && PR(c.slot).role === 'mortar' && PR(c.slot).crew >= 0);
    const f = enemyCrew[0]; if (!f) { fail('crew scenario: no enemy crew'); return; }
    const k0 = stats.killsTeam[f.team];
    v.pawn.hp = 40; v.pawn.armor = 0;
    D.impact({ team: f.team, k: PR(f.slot).crew, firerSlot: f.slot, firerGen: PR(f.slot).gen, loaderSlot: -1, src: 'mortar', x: v.pawn.pos.x, y: v.pawn.pos.y, z: v.pawn.pos.z });
    if (v.pawn.hp > 0) fail('a direct mortar hit did not kill a 40-hp crewman');
    else if (v.pawn.killedBy !== f) fail('mortar kill not credited to the enemy firer (' + (v.pawn.killedBy ? 'slot ' + v.pawn.killedBy.slot : 'nobody') + ')');
    if (!stats.msgs.some((x) => x.startsWith('[tw] crew death'))) fail('no "[tw] crew death" console line');
    piece('enemy shell kills a crewman (credited, logged)');
    // (d) loader assist: loader and firer differ, the victim has armour: the loader lands at least 41 health damage
    const tgt = everyone().find((c) => c.team !== f.team && onGround(c) && c !== v);
    const mates = D.crews[f.team][PR(f.slot).crew], ls = mates.a === f.slot ? mates.b : mates.a;
    if (tgt && ls >= 0 && PR(ls)) {
      tgt.pawn.hp = 100; tgt.pawn.armor = 100; tgt.pawn.dmgBy = new Map();
      const a0 = stats.mortarAssists;
      D.impact({ team: f.team, k: PR(f.slot).crew, firerSlot: f.slot, firerGen: PR(f.slot).gen, loaderSlot: ls, loaderGen: PR(ls).gen, src: 'mortar', x: tgt.pawn.pos.x, y: tgt.pawn.pos.y, z: tgt.pawn.pos.z });
      const fromLoader = tgt.pawn.dmgBy.get(ctls[ls]) || 0;
      if (fromLoader < 41) fail('the loader\'s share was ' + fromLoader + ' health damage through armour (assist needs 41)');
      if (tgt.pawn.hp <= 0 && stats.mortarAssists === a0) fail('a mortar kill with a loader gave no assist');
      piece('loader assist share (' + fromLoader + ' hp through armour)');
    } else fail('crew scenario: no loader for the assist piece');
    // (e) the firer changes sides before the shell lands: no kill credited to him (or to his new side)
    const g = enemyCrew[1] || f, gslot = g.slot, ggen = PR(gslot).gen, gteam = g.team;
    const w = everyone().find((c) => c.team !== gteam && onGround(c));
    if (w) {
      switchTeam(g, 5 - gteam);
      w.pawn.hp = 30; w.pawn.armor = 0;
      D.impact({ team: gteam, k: 0, firerSlot: gslot, firerGen: ggen, loaderSlot: -1, src: 'mortar', x: w.pawn.pos.x, y: w.pawn.pos.y, z: w.pawn.pos.z });
      piece('firer switched sides before impact');           // die() fails on a team kill credit
    }
  });
  when(60, () => {
    // (f) damage in the first tick of a round, before the points are read: no script error
    roundRestart(1);
    const c = everyone().find((q) => alive(q) && PR(q.slot) && PR(q.slot).role === 'mortar');
    if (c) { c.pawn.TakeDamage({ damage: 5, damageTypes: DT.FALL }); piece('damage before the first think of a round'); }
  });
  when(90, () => { if (!stats.msgs.some((x) => x.startsWith('[tw] crew death'))) fail('crew scenario: no crew death logged'); });
}
if (SCEN === 'air') {
  when(1, () => forceAir(10));
  when(25, () => {
    const pl = flying(); if (pl.length < 3) { fail('air scenario: fewer than 3 flying'); return; }
    // (a) AFK pilot: no keys, no look for AFK.PILOT seconds: home, infantry, in the trench
    const c = pl[0]; c.afk = true; c.afkSlot = c.slot; const afkFrom = time; c.pawn.eye = { pitch: 0, yaw: 0, roll: 0 };
    // he may be shot down while AFK and fly again (a new sortie restarts the clock): wait for the script to take him home
    const poll = () => {
      const pr = PR(c.slot);
      if (dbg().stats.afk > 0) {
        if (pr && pr.air) fail('the AFK pilot was counted as taken home but is still flying');
        else if (pr && pr.role !== 'infantry') fail('an AFK pilot was not made infantry');
        for (const team of [2, 3]) for (const ac of dbg().points.aircraft[team]) if (ac.pilot === c.slot) fail('the AFK pilot\'s aircraft was not freed');
        c.afk = false; piece('AFK pilot taken home'); return;
      }
      if (pr && pr.air && time - Math.max(afkFrom, pr.air.since ?? afkFrom) > CFG.AFK.PILOT + 3) fail('an AFK pilot was still flying ' + (CFG.AFK.PILOT + 3) + ' s into an AFK sortie');
      when(time + 2, poll);
    };
    when(time + 2, poll);
    // (b) !uniform while flying: no SetModel on the shrunk pawn (the mock's SetModel fails on it)
    pl[1].pawn.model = STOCK; say(pl[1], '!uniform'); say(pl[1], '!uniform'); tickOnce(); tickOnce(); piece('!uniform while flying');
    // (c) !infantry while flying: waits for the next deploy, he keeps flying
    say(pl[2], '!infantry');
    if (!PR(pl[2].slot).air) fail('!infantry in the air took the pilot out at once (should wait for the next deploy)');
    else piece('role change in the air deferred');
    const p2 = pl[2];
    when(time + 1, () => { const e = everyone().find((q) => q.team !== p2.team && alive(q)); if (alive(p2) && e) p2.pawn.TakeDamage({ damage: 999, damageTypes: DT.BULLET, attacker: e.pawn }); });
    when(time + 5, () => { const pr = PR(p2.slot); if (pr && pr.role !== 'infantry') fail('after !infantry and a death the pilot came back as ' + pr.role); else piece('next deploy applies the role'); });
  });
  when(40, () => {
    // (d) crash credit: an enemy hits a plane, the plane crashes: the hitter gets the kill; if the hitter left, nobody does
    const pl = flying().filter((c) => !c.afk); if (pl.length < 2) { fail('air scenario: not enough pilots for the crash pieces'); return; }
    for (const [i, leave] of [[0, false], [1, true]]) {
      const v = pl[i], a = PR(v.slot).air, hitter = everyone().find((c) => c.team !== v.team && alive(c) && !c.bot && !(PR(c.slot) && PR(c.slot).air));
      if (!hitter) continue;
      hooks.bullet({ weapon: new Weapon('weapon_awp', hitter.pawn), position: { ...a.pos }, hitEntity: a.ac.ent });
      const k0 = stats.killsTeam[hitter.team];
      if (leave) { disconnect(hitter, 'hitter left'); connect(hitter.slot, hitter.team, false); }
      a.pos = { x: a.pos.x, y: a.pos.y, z: groundAt(a.pos.x, a.pos.y) + 5 }; a.f = { x: 0, y: 0, z: -1 };   // into the ground
      const under = everyone().find((q) => q.team === hitter.team && onGround(q) && q !== hitter);
      if (under) { under.pawn.pos = { x: a.pos.x + 40, y: a.pos.y, z: a.pos.z - 5 }; under.pawn.hp = 20; under.pawn.armor = 0; }   // the wreck lands on him
      tickOnce();
      if (PR(v.slot) && PR(v.slot).air) fail('a plane flown into the ground did not crash');
      if (!leave && v.pawn.killedBy !== hitter) fail('crash kill not credited to the last enemy who hit the plane (' + (v.pawn.killedBy ? 'slot ' + v.pawn.killedBy.slot : 'nobody') + ')');
      if (leave && v.pawn.killedBy && v.pawn.killedBy.slot === hitter.slot) fail('crash kill credited to a slot whose player had left');
      piece(leave ? 'crash credit refused (hitter left)' : 'crash credit to the hitter');
    }
  });
  when(50, () => {
    // (e) two players ask for the last free aircraft in the briefing room: one gets it
    const D = dbg(), team = 2, acs = D.points.aircraft[team];
    const free = acs.filter((a) => a.pilot < 0);
    const lobby = humansOf(team).filter((c) => alive(c) && PR(c.slot) && !PR(c.slot).deployed && PR(c.slot).role !== 'air');
    if (free.length && lobby.length >= 2) { for (const c of lobby.slice(0, 2)) say(c, '!air'); piece('two ask for the last aircraft'); }
  });
  when(SECONDS - 2, () => { if (!stats.pieces['AFK pilot taken home']) fail('air scenario: the AFK piece did not run'); });
}
if (SCEN === 'reload') {
  when(1, () => forceAir(5));
  for (const t of [40, 80]) when(t, async () => {
    const D0 = dbg(), fly0 = flying().length, kills0 = D0.roundKills, unl0 = [...D0.unlocked];
    const parks = {}; for (const team of [2, 3]) for (const a of D0.points.aircraft[team]) parks[a.ent.name] = { ...a.park };
    if (!hooks.reloadCfg || !hooks.reloadCfg.before) { fail('the script registers no OnScriptReload before()'); return; }
    const mem = hooks.reloadCfg.before();
    hooks.reloadCfg = null; Instance._next = undefined;
    await loadScript();
    if (!hooks.reloadCfg || !hooks.reloadCfg.after) { fail('the reloaded script has no OnScriptReload after()'); return; }
    hooks.reloadCfg.after(mem);
    const D = dbg();
    if (D === D0) fail('reload did not create a new module state');
    if (D.roundKills !== kills0) fail('round kill count not carried over a reload');
    if ([...D.unlocked].join() !== unl0.join()) fail('unlocks not carried over a reload');
    tickOnce(); tickOnce();
    for (const team of [2, 3]) for (const a of D.points.aircraft[team]) {
      const pk = parks[a.ent.name]; if (!pk) continue;
      if (Math.hypot(a.park.x - pk.x, a.park.y - pk.y, a.park.z - pk.z) > 1) fail('aircraft ' + a.ent.name + ' park moved over a reload (read mid-air)');
      if (a.pilot < 0 && Math.hypot(a.ent.pos.x - pk.x, a.ent.pos.y - pk.y, a.ent.pos.z - pk.z) > 1) fail('aircraft ' + a.ent.name + ' left where the old script flew it');
    }
    for (const c of everyone()) if (c.pawn.hp > 0 && !(PR(c.slot) && PR(c.slot).air) && (c.pawn.scale !== 1 || (c.pawn.cam && c.pawn.cam.mode !== CAM.DISABLED))) fail('a pawn left shrunk / on a camera after a reload');
    piece('script reload with ' + fly0 + ' flying');
  });
  when(SECONDS - 2, () => { if ((dbg().stats.reloads || 0) < 2) fail('reload scenario: the reload counter did not carry (' + dbg().stats.reloads + ')'); });
}
if (SCEN === 'edge') {
  when(20, () => {
    // (a) a role asked for in the field waits for the next deploy: no teleport, no fresh kit
    const c = everyone().find((q) => !q.bot && onGround(q) && PR(q.slot).role === 'infantry' && PR(q.slot).deployed);
    if (!c) { fail('edge: no deployed infantry'); return; }
    const pos = { ...c.pawn.pos }; c.pawn.armor = 3;
    say(c, '!mortar');
    if (PR(c.slot).role !== 'infantry' || Math.hypot(c.pawn.pos.x - pos.x, c.pawn.pos.y - pos.y) > 1 || c.pawn.armor !== 3) fail('!mortar in the field switched at once (teleport / fresh kit)');
    else piece('field role change deferred');
    c.pawn.TakeDamage({ damage: 999, damageTypes: DT.BULLET });
    when(time + 6, () => { const pr = PR(c.slot); if (pr && pr.role !== 'mortar' && dbg().crews[c.team].some((k) => k.a < 0 || k.b < 0)) fail('the deferred !mortar was not applied at the next deploy'); else piece('deferred role applied'); });
    // (b) !uniform in the field: nothing until the next spawn (the mock fails SetModel after the kit was issued)
    const u = everyone().find((q) => !q.bot && onGround(q) && q !== c); if (u) { u.pawn.model = STOCK; say(u, '!uniform'); say(u, '!uniform'); tickOnce(); tickOnce(); piece('!uniform in the field'); }
    // (c) !pos: the radar square agrees with out/radar_region.json (the overview the radar picture was made for)
    for (const [x, y] of [[0, 0], [-4299, 4699], [4301, -3901], [1649, -2752], [-9000, 0], [0, 4800]]) {
      c.pawn.pos = { x, y, z: 0 }; stats.says = [];
      say(c, '!pos');
      const col = Math.floor((x - RADAR.x0) / RADAR.span * 16), row = Math.floor((RADAR.y0 - y) / RADAR.span * 16);
      const want = col >= 0 && col < 16 && row >= 0 && row < 16 ? String.fromCharCode(65 + col) + (row + 1) : 'off the map';
      const got = (stats.says || []).join(' ');
      if (!got.includes('radar square ' + want)) fail('!pos at ' + x + ',' + y + ' said "' + got + '", the radar says ' + want);
    }
    c.pawn.pos = pos; piece('!pos radar squares');
    // (d) chat from a spectator / no team
    const s = everyone().find((q) => !q.bot && q !== c && q !== u); if (s) { switchTeam(s, 1); for (const txt of ['!mortar', '!air', '!roles', '!pos', '!swap', '!uniform']) say(s, txt); piece('chat from a spectator'); }
  });
  when(8, () => {
    // (e) the bot leash never sends a bot to a post beside a still-closed blocker: the picker 300 times per side, then bots for real
    for (const team of [2, 3]) for (let i = 0; i < 300; i++) {
      const s = D_pick(team); if (!s) continue;
      for (const L of ['undergroundopen', 'woodsopen'].flatMap((n) => byName.get(n) || []).filter((e) => e.valid))
        if (Math.hypot(s.pos.x - L.pos.x, s.pos.y - L.pos.y) < CFG.BOTS.LEASH_AVOID) { fail('the leash picked a post ' + Math.round(Math.hypot(s.pos.x - L.pos.x, s.pos.y - L.pos.y)) + ' u from the ' + L.name + ' blocker'); break; }
    }
    const D = dbg(), locks = ['undergroundopen', 'woodsopen'].flatMap((n) => byName.get(n) || []).filter((e) => e.valid);
    const bots = everyone().filter((c) => c.bot && onGround(c));
    for (const L of locks) for (const b of bots.slice(0, 3)) {
      if (b.team !== (L.pos.x < 0 ? 2 : 3)) continue;
      b.pawn.pos = { x: L.pos.x + 30, y: L.pos.y + 30, z: L.pos.z }; const life = b.pawn.spawnedAt;
      for (let i = 0; i < 64 * 4; i++) tickOnce();
      if (b.pawn.spawnedAt !== life || b.pawn.hp <= 0) continue;  // died and deployed again meanwhile: not the leash's doing
      const d = Math.hypot(b.pawn.pos.x - L.pos.x, b.pawn.pos.y - L.pos.y);
      if (dbg().unlocked.has(L.name)) continue;                 // opened meanwhile (kills): no leash there any more, by design
      if (d < CFG.BOTS.LEASH_AVOID) fail('the leash left a bot ' + Math.round(d) + ' u from the ' + L.name + ' blocker');
      else piece('leash away from the blocker');
    }
  });
  when(40, () => {
    // (f) a long hitch (1 s in one tick) and a think scheduled late: nothing non-finite
    time += 1.0; piece('1 s hitch');
  });
}

// default runs (no scenario): small set pieces so every guard shows in the coverage table
if (!SCEN && !BAL) {
  when(5, () => forceAir(3));
  when(100, () => {
    const c = everyone().find((q) => alive(q) && PR(q.slot) && PR(q.slot).role === 'mortar' && PR(q.slot).deployed && PR(q.slot).crew >= 0);
    if (c) { const pit = dbg().pitPos(c.team, PR(c.slot).crew); c.pawn.pos = { x: pit.x + 50, y: pit.y, z: pit.z }; c.pawn.TakeDamage({ damage: 30, damageTypes: DT.FALL }); }
  });
  // an AFK pilot: one at a time from 120 s until the script has taken one home (a pilot shot down while AFK is replaced)
  const afkTry = () => { if (dbg().stats.afk) { for (const c of everyone()) c.afk = false; return; }
    if (!everyone().some((c) => c.afk && alive(c) && PR(c.slot) && PR(c.slot).air)) { for (const c of everyone()) c.afk = false; const pl = flying()[0]; if (pl) pl.afk = true; }
    if (time < SECONDS - 5) when(time + 5, afkTry); };
  when(120, afkTry);
}

// ------------------------------------------------------------------ the loop
const DTK = 1 / 64;
const perf = { ms: [], hud: 0, traces: 0 };
function tickOnce() {
  time += DTK; tick++;
  for (const c of everyone()) if (time >= c.respawnAt && c.team >= 2) spawn(c);
  // drivers
  const D = dbg();
  for (const c of everyone()) {
    const p = c.pawn; p.prev = p.keys; p.keys = 0;
    if (c.bot || p.hp <= 0) continue;
    const pr = D.players.get(c.slot); if (!pr) continue;
    if (pr.air) { if (pr.air.since === undefined) pr.air.since = time; drivePilot(c, pr); continue; }
    if (c.afk) continue;
    if (pr.role === 'mortar' && pr.crew >= 0 && pr.deployed) { driveCrew(c, pr); continue; }
    if (pr.upgraded && tick % 300 === c.slot) p.keys = IN.WALK | IN.USE;
    if (pr.deployed && p.hp < 70 && tick % 64 === c.slot % 64) {            // walk to a dressing station when hurt
      const hs = ENTS.filter((e) => e.name && e.name.startsWith('heal_' + tagOf(c.team) + '_')); const h = hs[c.slot % hs.length];
      if (h) p.pos = { x: h.origin[0] + 20, y: h.origin[1], z: h.origin[2] };
    }
    if (tick % 64 === 0 && pr.deployed) { p.eye = { pitch: p.eye.pitch, yaw: p.eye.yaw + 3, roll: 0 }; }   // a human looks around
  }
  if (tick % 16 === 0) fightModel();
  if (tick % 16 === 0) {                                   // balance bookkeeping: when areas open, how long each flight lasts
    const un = D.unlocked; if (un && un.size > (stats.unlockAt || []).length) (stats.unlockAt = stats.unlockAt || []).push(Math.round(time));
    for (const c of everyone()) { const pr = D.players.get(c.slot), fl = !!(pr && pr.air);
      if (fl && c.flySince === undefined) c.flySince = time; else if (!fl && c.flySince !== undefined) { (stats.flightLife = stats.flightLife || []).push(time - c.flySince); c.flySince = undefined; } }
  }
  if (!SCEN && !BAL && tick % 640 === 3) { const h = humansOf(); if (h.length) say(h[(tick / 640 | 0) % h.length], ['!mortar', '!air', '!roles', '!pos', '!infantry', '!random', '!swap', '!uniform'][(tick / 640 | 0) % 8]); }
  if (Instance._next !== undefined && Instance._next <= time + 1e-9) {
    Instance._next = undefined;
    const h0 = hudTick, t0 = stats.traces, c0 = performance.now();
    Instance._think();
    perf.ms.push(performance.now() - c0); perf.hud += hudTick - h0; perf.traces += stats.traces - t0;
  }
  for (const c of everyone()) { const pr = D.players.get(c.slot); if (pr) pr.lastPrompt = undefined; }
  if (tick % 16 === 0) invariants();
}
for (let step = 0; step < SECONDS * 64; step++) {
  for (let i = at.length - 1; i >= 0; i--) if (at[i].t <= time) { const a = at[i]; at.splice(i, 1); try { await a.fn(); } catch (e) { fail('set piece ' + (a.name || '') + ' threw: ' + (e && e.stack ? e.stack.split('\n').slice(0, 3).join(' ') : e)); } }
  tickOnce();
}

// ------------------------------------------------------------------ report
const D = dbg(), S = D.stats;
const errs = stats.msgs.filter((x) => x.includes('[tw] error'));
for (const e of errs.slice(0, 3)) fail('script error: ' + e.slice(0, 300));
if (stats.hudBots) fail(stats.hudBots + ' HUD calls for bots');
const ms = perf.ms.slice().sort((a, b) => a - b), pct = (f) => ms.length ? ms[Math.min(ms.length - 1, Math.floor(ms.length * f))] : 0;
const P_ = { avg: +(ms.reduce((a, b) => a + b, 0) / Math.max(1, ms.length)).toFixed(4), p50: +pct(0.5).toFixed(4), p99: +pct(0.99).toFixed(3), max: +(ms[ms.length - 1] || 0).toFixed(2),
             over1: ms.filter((x) => x > 1).length, over8: ms.filter((x) => x > 8).length, ticks: ms.length, hud: +(perf.hud / Math.max(1, ms.length)).toFixed(1), traces: +(perf.traces / Math.max(1, ms.length)).toFixed(1) };
if (opt.perf) { const [a, mx] = opt.perf.split(',').map(Number); if (P_.avg > a) fail('script time avg ' + P_.avg + ' ms over ' + a); if (P_.max > mx) fail('script time max ' + P_.max + ' ms over ' + mx); }
const killsBy = { ...S.killsBy }; for (const [k, v] of Object.entries(stats.killsBy)) killsBy[k] = (killsBy[k] || 0) + v;
if (BAL) {
  const k2 = stats.killsTeam[2], k3 = stats.killsTeam[3];
  const out = { seed: +(opt.seed || 7), secs: SECONDS, players: N, humans: HUMANS, kills: { t: k2, ct: k3 }, winner: k2 > k3 ? 2 : k3 > k2 ? 3 : 0, killsBy, deaths: stats.kills,
                killsTeamBy: (() => { const o = {}; for (const t of [2, 3]) { o[t] = { ...(stats.killsTeamBy[t] || {}) }; for (const [k, v] of Object.entries(S.killsByTeam[t] || {})) o[t][k] = (o[t][k] || 0) + v; } return o; })(), flights: S.flights, crashes: S.crashes, flightLife: (stats.flightLife || []).map((x) => Math.round(x)), shots: S.shots, bombs: S.bombs, assists: stats.mortarAssists, unlocks: S.unlocks, unlockAt: stats.unlockAt || [],
                perf: P_, errors: errs.length + fails.length, fails: fails.slice(0, 5) };
  console.log(JSON.stringify(out));
  process.exit(out.errors ? 1 : 0);
}
const scenOK = SCEN ? Object.keys(stats.pieces).length > 0 : true;
if (SCEN && !scenOK) fail('scenario ' + SCEN + ': no set piece ran');
console.log('mg_trenchwarfare mock: ' + everyone().length + ' players (' + everyone().filter((c) => !c.bot).length + ' human), ' + SECONDS + ' s' + (SCEN ? ', scenario ' + SCEN : '') + ', script ' + built.lines + ' lines, ' + built.files.length + ' modules');
console.log(JSON.stringify({ kills: stats.kills, killsTeam: stats.killsTeam, killsBy, hud: stats.hud, vars: stats.vars, fires: stats.fires, dmg: stats.dmg, blocked: stats.blocked || 0,
  teleports: stats.teleports, moves: stats.moves, setModel: stats.setModel, removed: stats.removed || 0, restarts: stats.restarts, churn: stats.churn }));
if (Object.keys(stats.pieces).length) console.log('set pieces: ' + Object.entries(stats.pieces).map(([k, v]) => k + (v > 1 ? ' x' + v : '')).join('; '));
if (!SCEN) {
  const table = {
    'deploys: infantry': S.deploys.infantry, 'deploys: mortar crew': S.deploys.mortar, 'deploys: aircraft': S.deploys.air,
    'mortar: target locked at the table': S.sightLocks, 'mortar: pistol stowed at the table': S.stows, 'mortar: bombs loaded': S.loads, 'mortar: shots': S.shots,
    'mortar: impacts': S.impacts, 'mortar: kills': killsBy.mortar || 0, 'mortar: loader assist shares (41+ hp)': S.assistShares, 'mortar: assists credited (mock rule)': stats.mortarAssists,
    'air: flights': S.flights, 'air: gun rounds': S.gunRounds, 'air: gun hits on men': S.gunHits, 'air: bombs dropped': S.bombs, 'air: bomb kills': killsBy.bomb || 0,
    'air: rifle hits on aircraft': S.planeHits, 'air: pilots shot down': killsBy.shot_down || 0, 'air: crashes': S.crashes, 'air: AFK pilot taken home': S.afk,
    'rifle kills (rate model)': killsBy.rifle || 0, 'areas opened (unlocks)': S.unlocks, 'dressing station heals': S.heals, 'streak upgrades': S.upgrades, 'rifle swaps': S.swaps,
    'uniforms set': S.uniforms, 'ambient bursts': S.ambient, 'damage blocked at the pit / pilot': S.blocked, 'field role requests deferred': S.deferred,
    '!pos / !roles / !uniform': (stats.chats['!pos'] || 0) + (stats.chats['!roles'] || 0) + (stats.chats['!uniform'] || 0), 'per-minute perf line': S.perfLines,
  };
  if (BAL || N < 16) delete table['air: AFK pilot taken home'];
  const need = N >= 16 && SECONDS >= 300;
  console.log('coverage (feature -> times exercised)' + (need ? '' : ' (not enforced: runs of 16+ players and 300+ s only)') + ':');
  for (const [k, v] of Object.entries(table)) { console.log('  ' + String(v).padStart(6) + '  ' + k); if (need && !(v > 0)) fail('coverage: "' + k + '" was never exercised'); }
}
console.log('script time: ' + P_.avg.toFixed(3) + ' ms/tick avg, p50 ' + P_.p50.toFixed(3) + ', p99 ' + P_.p99 + ', max ' + P_.max + ' ms over ' + P_.ticks + ' ticks, ' + P_.over1 + ' over 1 ms, ' + P_.over8 +
  ' over 8 ms; per tick ' + P_.hud + ' HUD calls, ' + P_.traces + ' traces (the stand-in engine\'s own time is included)');
for (const f of fails) console.log('FAIL ' + f);
console.log(fails.length ? 'RESULT: ' + fails.length + ' failure(s)' : 'RESULT: ok' + (SCEN ? ' (scenario ' + SCEN + ')' : ''));
process.exit(fails.length ? 1 : 0);
