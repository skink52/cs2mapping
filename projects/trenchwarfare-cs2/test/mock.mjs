// Runs the shipped src/mg_trenchwarfare.js (built from src/modules by create/build_script.mjs) on a stand-in cs_script engine where
// only the CURRENT API exists (Instance / Entities / Console; any deprecated Instance.* name throws). World: out/entities.json and
// the HUD xml / css restaged by tools/restage_out.py. Humans are driven through every role (infantry, mortar crews at the table, ammo
// box and tube, pilots flying, strafing and bombing); the infantry fight is a rate model (CS2's bots and players can't run here).
//
// usage: node test/mock.mjs [players=32] [seconds=120] [key=value ...]
//   seed=<n>         random seed (the script's Math.random too); default 7
//   humans=<n>       how many players are human (default 2 x round(players / 3), split evenly between the sides; the rest bots)
//   scenario=<name>  one bug class: round | churn | crew | air | reload | edge, or a bot case: bots | lopsided | full | yield |
//                    threshold | botround | handover   (all = every one, each in its own process)
//   fill=1           bots come and go through the script's bot_quota / bot_quota_mode (CS2's "fill"): only humans are created, split
//                    by split=<T>,<CT> (default humans / 2 each); the bot scenarios always run this way
//   mode=balance     one round window with the real CONFIG, a JSON result line (test/sim_balance via create/sim_balance.mjs); json=1 only that
//   perf=<avg>,<max> fail when the script's think time (ms per tick) is over these
//   script=<file>    run this build of the script instead of src/mg_trenchwarfare.js (no stale check)
//   sounds=0         leave out the sound emitters of tools/patch_sounds.py (out/step8/patch_sounds.entities.json, added to the
//                    deployed map's out/entities.json by default): the script must then fire nothing at them
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
const SCENARIOS = ['round', 'churn', 'crew', 'air', 'reload', 'edge', 'bots', 'lopsided', 'full', 'yield', 'threshold', 'botround', 'handover'];
// the bot scenarios: humans per side (T, CT); bots join through the script's bot_quota (fill)
const FILLSCEN = { bots: [2, 2], lopsided: [4, 0], full: [32, 32], yield: [2, 2], threshold: [2, 2], botround: [2, 2], handover: [2, 2] };
const FILL = opt.fill === '1' || !!FILLSCEN[SCEN];

if (SCEN === 'all') {                      // every scenario in its own process (fresh module state), pass / total
  let ok = 0; const lines = [];
  for (const s of SCENARIOS) {
    const r = spawnSync(process.execPath, [fileURLToPath(import.meta.url), String(N), String(SECONDS), 'scenario=' + s, ...(opt.seed ? ['seed=' + opt.seed] : []), ...(opt.script ? ['script=' + opt.script] : [])], { encoding: 'utf8' });
    const last = (r.stdout || '').trim().split('\n').filter((l) => /^RESULT|^FAIL/.test(l));
    if (r.status === 0) ok++;
    lines.push((r.status === 0 ? 'pass ' : 'FAIL ') + s.padEnd(9) + ' ' + (last.slice(0, 4).join(' | ') || (r.stderr || '').slice(-300)));
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
                planeHitsRifle: 0, chats: {}, churn: {}, pieces: {}, sounds: {} };
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
// the sound emitters of tools/patch_sounds.py (tw_whistle_attack, tw_plane_dive_N, tw_rain_tin_<tg>_N): not in the deployed map that
// out/entities.json restages, so they are added from the patch's own list (names already present are not added twice); sounds=0: none
const SNDF = path.join(root, 'out/step8/patch_sounds.entities.json');
if (opt.sounds !== '0' && fs.existsSync(SNDF)) {
  const have = new Set(ENTS.map((e) => e.name));
  for (const e of JSON.parse(fs.readFileSync(SNDF, 'utf8')).entities) if (!have.has(e.name)) ENTS.push({ name: e.name, cls: e.cls, origin: e.origin, angles: e.angles });
}
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
const linger = new Array(64).fill(undefined);   // disconnected controllers CS2 may keep in their slots (IsConnected false)
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
  if (v.hp <= 0 || v.ctl.god) return 0;          // god: a set piece's test subject the rate model must not kill mid-test
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
  // a disconnected player's controller may stay in its slot (IsConnected false) until the slot is reused: linger[s] (set by a scenario)
  GetPlayerController: (s) => (ctls[s] && ctls[s].connected ? ctls[s] : ctls[s] ? undefined : linger[s]), TraceLine: traceLine,
});
const Entities = strict('Entities', {
  FindByName: (n) => (byName.get(n) || []).filter((e) => e.valid),
  FireInput: (o) => {
    const list = (byName.get(o.name) || []).filter((e) => e.valid);
    if (!list.length) { fail('Entities.FireInput at a missing entity ' + o.name); return; }
    if (o.input === 'StartSound') stats.sounds[o.name] = (stats.sounds[o.name] || 0) + 1;
    for (const e of list) e.FireInput(o);
  },
});
const Console = strict('Console', {
  Log: (msg) => { const s = String(msg); stats.msgs.push(s); if (stats.msgs.length > 4000) stats.msgs.splice(0, 1000); if (process.env.MOCK_LOG) console.log(time.toFixed(2), s); },
  ServerCommand: (c) => {
    const w = String(c).split(' ')[0]; stats.cmds[w] = (stats.cmds[w] || 0) + 1;
    if (w === 'bot_quota') quota = +String(c).split(' ')[1]; if (w === 'bot_quota_mode') quotaMode = String(c).split(' ')[1];
    if (w === 'bot_kick') kickAll = true;
    if (!/^(mp_|bot_|say$)/.test(w)) fail('server command outside mp_ / bot_ / say: ' + c);
    if (/[;\n\r]/.test(c) || (w === 'say' && /"/.test(c))) fail('unsafe characters in a server command: ' + c);
    if (w === 'say') stats.says = (stats.says || []).concat([String(c).slice(4)]).slice(-50);
  },
});
globalThis.__cs = { Instance, Entities, Console, ...ENUMS };
// CS2's bot quota as the mock plays it (fill=1 / the bot scenarios): bots = quota - humans in "fill" mode, quota in "normal"; a new bot
// joins the smaller side, a kicked one leaves the larger side; bot_kick removes them all
let quota = 0, quotaMode = 'normal', kickAll = false, fillTie = 2;
function fillBots() {
  if (!FILL) return;
  const size = (t) => everyone().filter((c) => c.team === t).length;
  if (kickAll) { kickAll = false; for (const b of everyone().filter((c) => c.bot)) disconnect(b, 'bot_kick'); }
  const humans = everyone().filter((c) => !c.bot).length;
  const want = quotaMode === 'fill' ? Math.max(0, quota - humans) : quota;
  const bots = everyone().filter((c) => c.bot);
  while (bots.length > want) {
    const big = size(2) > size(3) ? 2 : 3, i = bots.map((c) => c.team).lastIndexOf(big);
    disconnect(bots.splice(i >= 0 ? i : bots.length - 1, 1)[0], 'quota kick');
  }
  while (bots.length < want) {
    const slot = ctls.findIndex((c) => !c); if (slot < 0) break;
    const other = 5 - fillTie, team = size(other) < size(fillTie) ? other : fillTie;
    if (size(2) === size(3)) fillTie = 5 - fillTie;
    bots.push(connect(slot, team, true)); stats.botsAdded = (stats.botsAdded || 0) + 1;
  }
}
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
const SPLIT = FILL ? (opt.split ? opt.split.split(',').map(Number) : FILLSCEN[SCEN] || [Math.ceil(+(opt.humans || 4) / 2), Math.floor(+(opt.humans || 4) / 2)]) : null;
const HUMANS = FILL ? SPLIT[0] + SPLIT[1] : opt.humans !== undefined ? +opt.humans : 2 * Math.round(N / 3);
// fill: the humans only (T first), bots come with the quota. Otherwise slots: team by slot parity; within each team the humans first
// take the places not 2 mod 3, so both sides get the same mix
// (interleaved like the default slots: whichever side holds the low slots wins more of the mock's fights - 61 % / 41 % over 150 bot runs
// with T / CT first - so neither side may: humans T, CT, T, CT ... while both have some left, bots join with the tie going to each side in turn)
if (FILL) { let s = 0; const left = { 2: SPLIT[0], 3: SPLIT[1] }; let tm = 2; while (left[2] + left[3] > 0) { if (!left[tm]) tm = 5 - tm; ctls[s] = new Ctl(s, tm, false); s++; left[tm]--; tm = 5 - tm; } }
else {
  const want = { 2: Math.ceil(HUMANS / 2), 3: Math.floor(HUMANS / 2) }, idx = { 2: [], 3: [] };
  for (let s = 0; s < N; s++) idx[s % 2 ? 3 : 2].push(s);
  for (const team of [2, 3]) {
    const order = idx[team].map((s, i) => [s, i]).sort((a, b) => ((a[1] % 3 === 2) - (b[1] % 3 === 2)) || a[1] - b[1]);
    order.forEach(([s], k) => { ctls[s] = new Ctl(s, team, k >= want[team]); });
  }
}
hooks.activate();
hooks.round && hooks.round(); stats.rounds++;
fillBots();
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
  // in a random order: in slot order the lower slots shoot first and win more duels (fill=1 gives T the lower slots: T won 61 % of 150
  // bot runs, 2 kills a window ahead, before this shuffle)
  for (let i = list.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); const x = list[i]; list[i] = list[j]; list[j] = x; }
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
      if (!pr.inSight && p.mt === MT.NONE && !(pr.aiRole === 'crew' && pr.deployed)) fail('live pawn left frozen outside the sight (slot ' + s + ')');
    }
    if (p.hp > 0 && !fin(p.pos)) fail('non-finite pawn position');
    // the script roles (85_ai): bots only, each in its own seat; a script crew runs its tube alone; only a script pilot flies a bot
    if (pr.aiRole && !c.bot) fail('a human has a script role (' + pr.aiRole + ', slot ' + s + ')');
    if (pr.aiRole === 'pilot' && pr.role !== 'air') fail('AI pilot without the air role (slot ' + s + ')');
    if (pr.aiRole === 'crew') {
      const cr = D.crews[pr.team] && D.crews[pr.team][pr.crew];
      if (pr.role !== 'mortar' || !cr || cr.a !== s) fail('AI crewman not in seat a of his crew (slot ' + s + ')');
      else if (cr.b >= 0) fail('a player shares a tube with a script bot (crew ' + tagOf(pr.team) + '_' + (pr.crew + 1) + ')');
    }
    if (pr.air && c.bot && pr.aiRole !== 'pilot') fail('a bot flies without the AI pilot role (slot ' + s + ')');
  }
  if (pts) for (const team of [2, 3]) for (const ac of pts.aircraft[team] || []) {
    let n = 0; for (const pr of D.players.values()) if (pr.air && pr.air.ac === ac) n++;
    if (n > 1) fail('two players fly aircraft ' + ac.ent.name);
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
    // a firer whose crew has a mate (for the loader piece), when one exists
    const paired = (c) => { const cr = D.crews[c.team][PR(c.slot).crew]; return cr.a >= 0 && cr.b >= 0 && PR(cr.a) && PR(cr.b); };
    enemyCrew.sort((x, y) => paired(y) - paired(x));
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
    const mates = D.crews[f.team][PR(f.slot).crew];
    let ls = mates.a === f.slot ? mates.b : mates.a;
    if (!(ls >= 0)) { const ok = (c) => c.team === f.team && c !== f && alive(c) && PR(c.slot); const o = everyone().find((c) => ok(c) && PR(c.slot).role === 'mortar') || everyone().find(ok); ls = o ? o.slot : -1; }   // no crewmate this seed: a team-mate stands in as the loader
    if (tgt && ls >= 0 && PR(ls)) {
      tgt.pawn.hp = 100; tgt.pawn.armor = 100; tgt.pawn.dmgBy = new Map();
      const a0 = stats.assists;
      D.impact({ team: f.team, k: PR(f.slot).crew, firerSlot: f.slot, firerGen: PR(f.slot).gen, loaderSlot: ls, loaderGen: PR(ls).gen, src: 'mortar', x: tgt.pawn.pos.x, y: tgt.pawn.pos.y, z: tgt.pawn.pos.z });
      const fromLoader = tgt.pawn.dmgBy.get(ctls[ls]) || 0;
      if (fromLoader < 41) fail('the loader\'s share was ' + fromLoader + ' health damage through armour (assist needs 41)');
      if (tgt.pawn.hp <= 0 && stats.assists === a0) fail('a mortar kill with a loader gave no assist');
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
  when(80, () => {
    // (g) a prop grinding a crewman at his tube (or a pilot) every tick: every hit is blocked, and the console gets a line now and then,
    //     not one per tick (64 players x 64 ticks of "[tw] blocked" would be the server's whole console)
    const D = dbg();
    const c = everyone().find((q) => alive(q) && PR(q.slot) && PR(q.slot).role === 'mortar' && PR(q.slot).deployed && PR(q.slot).crew >= 0);
    if (!c) { fail('crew scenario: no deployed crew for the flood piece'); return; }
    const pit = D.pitPos(c.team, PR(c.slot).crew), tag = '(slot ' + c.slot + ',';
    const count = () => stats.msgs.filter((x) => x.startsWith('[tw] blocked') && x.includes(tag)).length;
    const n0 = count(), b0 = D.stats.blocked;
    for (let i = 0; i < 64; i++) { c.pawn.pos = { x: pit.x + 60, y: pit.y, z: pit.z }; c.pawn.TakeDamage({ damage: 3, damageTypes: DT.CRUSH }); tickOnce(); }
    const lines = count() - n0;
    if (D.stats.blocked - b0 < 60) fail('flood piece: only ' + (D.stats.blocked - b0) + ' of 64 grinding hits were blocked');
    if (lines > 2) fail('the damage guard printed ' + lines + ' "[tw] blocked" lines for one crewman in one second');
    piece('grinding damage at the pit: ' + lines + ' console line(s) for 64 blocked hits');
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
      a.pos = { x: a.pos.x, y: a.pos.y, z: groundAt(a.pos.x, a.pos.y) + 5 }; a.f = { x: 0.5, y: 0, z: -0.866 };   // into the ground (a 60-degree dive: the flight never points straight down)
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
    if (s) when(time + 1, () => {
      const st = hudState.get(s.slot);
      if (ctls[s.slot] === s && s.team === 1 && st && (st.get('tw_status.show') || st.get('tw_brief.show'))) fail('a spectator kept the role card / orders sheet on screen (slot ' + s.slot + ')');
      else piece('spectator: no role card');
    });
    // (g) a player name with ; and " in it: !pos puts the name in a "say" server command (a ; there runs whatever follows it)
    const e = everyone().find((q) => !q.bot && alive(q) && q !== s);
    if (e) { const nm = e.GetPlayerName; e.GetPlayerName = () => 'Tommy";quit;"'; say(e, '!pos'); e.GetPlayerName = nm; piece('!pos with ; and " in the name'); }
    when(time + 2, briefingSpectate);              // after (d): the t=8 piece runs late and could otherwise hand (d) this piece's man
  });
  const briefingSpectate = () => {
    // (h) spectating from the briefing room: the orders sheet must not stay up over the spectator view
    const h = everyone().find((q) => !q.bot && !q.god && onGround(q) && PR(q.slot) && PR(q.slot).deployed && PR(q.slot).role === 'infantry' && q.team >= 2);   // (a crewman at his pit would be guarded)
    if (!h) { fail('edge: no human to send to the briefing room'); return; }
    h.pawn.TakeDamage({ damage: 999, damageTypes: DT.BULLET });
    when(time + 2.4, () => {
      const pr = PR(h.slot);
      if (!alive(h) || !pr || pr.deployed) { fail('edge: the briefing-room spectator piece found him out of the briefing room (alive ' + alive(h) + ', deployed ' + (pr && pr.deployed) + ', hp ' + h.pawn.hp + ', team ' + h.team + ', spawned ' + h.pawn.spawnedAt + ', now ' + time + ')'); return; }
      const st0 = hudState.get(h.slot); if (!st0 || !st0.get('tw_brief.show')) { fail('edge: the orders sheet was not up in the briefing room'); return; }
      switchTeam(h, 1);
      for (let i = 0; i < 64; i++) tickOnce();
      const st = hudState.get(h.slot);
      if (st && st.get('tw_brief.show')) fail('spectating from the briefing room left the orders sheet up (slot ' + h.slot + ')');
      else piece('spectate from the briefing room: orders sheet down');
    });
  };
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

// ------------------------------------------------------------------ bot scenarios (85_ai)
const aiBots = (team, role) => [...dbg().players.values()].filter((q) => q.team === team && q.aiRole === role && ctls[q.slot] && ctls[q.slot].bot);
const aiFlying = (team) => aiBots(team, 'pilot').filter((q) => q.air);
const aiSeated = (team) => aiBots(team, 'crew').filter((q) => q.deployed && alive(ctls[q.slot]));
const botsOf = (team) => everyone().filter((c) => c.bot && (!team || c.team === team));
const postsOf = (team) => ENTS.filter((e) => e.name && e.name.startsWith('trench_' + tagOf(team) + '_')).map((e) => ({ x: e.origin[0], y: e.origin[1], z: e.origin[2] }));
const nearPost = (c, r) => postsOf(c.team).some((q) => Math.hypot(c.pawn.pos.x - q.x, c.pawn.pos.y - q.y) < (r || 60));
const areaPts = (team, name) => (CFG.BOTS.AREAS[name] || []).map((a) => ({ x: (team === 3 ? 1 : -1) * a.x, y: a.y, z: a.z }));
// poll a condition every `every` s until it holds (then ok()) or `secs` pass (then fail(msg))
function poll(cond, secs, ok, msg, every) {
  const t0 = time;
  const step = () => { let r; try { r = cond(); } catch (e) { fail(msg + ' (threw ' + e + ')'); return; } if (r) { if (ok) ok(r); return; } if (time - t0 > secs) { fail(msg); return; } when(time + (every || 0.25), step); };
  when(time + (every || 0.25), step);
}
// a deployed infantry bot put out of play (kind: nml | lobby | far): the leash must bring it back to one of its posts
function leashPiece(kind, place) {
  const D = dbg(), B = CFG.BOTS;
  const b = everyone().find((c) => c.bot && onGround(c) && PR(c.slot) && PR(c.slot).role === 'infantry' && PR(c.slot).deployed && !c.god && !c.leashUsed);
  if (!b) { fail('no deployed infantry bot for the ' + kind + ' leash'); return; }
  b.leashUsed = true; b.god = true; const life = b.pawn.spawnedAt, n0 = D.stats.botLeash[kind];
  b.pawn.pos = place(b);
  poll(() => b.pawn.spawnedAt !== life || !b.connected || (D.stats.botLeash[kind] > n0 && nearPost(b)), B.OUT_TIME + B.CHECK + B.COMBAT_GRACE + 3,
       () => { b.god = false; piece('leash: ' + kind + (b.pawn.spawnedAt === life ? '' : ' (respawned first)')); },
       'the ' + kind + ' leash left a bot out of play at ' + JSON.stringify(b.pawn.pos));
}
function leashPieces(t0) {
  when(t0, () => leashPiece('nml', () => ({ x: 0, y: 500, z: 0 })));
  when(t0 + 2, () => leashPiece('lobby', () => ({ ...lobbyT[0] ? { x: lobbyT[0].origin[0], y: lobbyT[0].origin[1], z: lobbyT[0].origin[2] } : { x: 0, y: -3000, z: -2892 } })));
  when(t0 + 4, () => leashPiece('far', (b) => ({ x: (b.team === 3 ? 1 : -1) * 6000, y: 0, z: 0 })));
}
// both sides have their script pilot up and their script crews at the table
const aiUp = (team) => aiFlying(team).length >= Math.min(1, CFG.AI.PILOTS) && aiSeated(team).length >= CFG.AI.CREWS;
function aiAtSeats(team) {
  for (const q of aiSeated(team)) { const c = ctls[q.slot], sa = one('mortarcrew_' + tagOf(team) + '_' + (q.crew + 1) + '_a'); if (!sa || Math.hypot(c.pawn.pos.x - sa.pos.x, c.pawn.pos.y - sa.pos.y) > 40 || c.pawn.mt !== MT.NONE) return false; }
  return true;
}
if (SCEN === 'bots') {
  when(2, () => {
    const b = botsOf(), want = Math.max(0, 2 * CFG.BOTS.FILL_PER_SIDE - HUMANS);
    if (b.length !== want) fail('quota fill: ' + b.length + ' bots for ' + HUMANS + ' humans (want ' + want + ')');
    else if (botsOf(2).length !== botsOf(3).length) fail('quota fill: uneven bots ' + botsOf(2).length + ' / ' + botsOf(3).length);
    else piece('quota fill: ' + b.length + ' bots for ' + HUMANS + ' humans');
  });
  poll(() => aiUp(2) && aiUp(3) && aiAtSeats(2) && aiAtSeats(3), 30, () => piece('AI pilot flying and AI crews at the table, both sides'), 'bots: the AI roles did not come up on both sides in 30 s');
  when(60, () => {
    let n = 0;
    for (const c of botsOf()) {
      const pr = PR(c.slot); if (!pr || pr.role !== 'infantry' || !pr.deployed || !onGround(c) || c.leashUsed) continue;
      n++;
      const o = c.pawn.pos, B = CFG.BOTS;
      if (Math.abs(o.x) < B.NML_X && Math.abs(o.y) < B.NML_Y && o.z > B.NML_ZMIN) fail('an infantry bot stands in no man\'s land');
      if (o.z < B.LOBBY_Z) fail('a deployed infantry bot stands in the briefing room');
      if (!nearPost(c, 80)) fail('an infantry bot deployed away from every post: ' + JSON.stringify(o));
    }
    if (!n) fail('bots: no deployed infantry bot to check'); else piece('infantry bots at their posts (' + n + ')');
  });
  leashPieces(40);
  when(70, () => { CFG.UNLOCKS[0].kills = 0; piece('woods opened'); });
  for (let t = 72; t < 104; t += 2) when(t, () => { for (const c of botsOf()) { const pr = PR(c.slot); if (pr && pr.role === 'infantry' && pr.deployed && alive(c) && !c.god && rnd() < 0.5) c.pawn.TakeDamage({ damage: 999, damageTypes: DT.BULLET }); } });
  for (let t = 74; t < 120; t += 3) when(t, () => {
    for (const team of [2, 3]) {
      const inArea = [...dbg().players.values()].filter((q) => q.team === team && q.bot && q.deployed && q.anchor && q.anchor.area === 'woodsopen');
      if (inArea.length > CFG.BOTS.AREA_MAX) fail('more than AREA_MAX bots of one side sent into the woods');
      for (const q of inArea) {
        const c = ctls[q.slot]; if (!alive(c) || c.leashUsed) continue;
        const ok = areaPts(team, 'woodsopen').some((a) => Math.hypot(c.pawn.pos.x - a.x, c.pawn.pos.y - a.y) < 60) || nearPost(c, 60);
        if (!ok) fail('a bot sent to the woods is neither at a woods point nor at the ladder post: ' + JSON.stringify(c.pawn.pos));
      }
    }
  });
  when(125, () => {
    const S = dbg().stats;
    if (!(S.botDeploys.area > 0)) fail('bots: no deploy into the opened woods'); else piece('bots deployed into the opened woods x' + S.botDeploys.area);
    if (!(S.aiShots > 0)) fail('bots: the AI crews fired nothing'); else piece('AI crew shots x' + S.aiShots);
    if (!(S.aiGunRounds + S.aiBombs > 0)) fail('bots: the AI pilots fired nothing'); else piece('AI pilot gun rounds / bombs ' + S.aiGunRounds + ' / ' + S.aiBombs);
  });
}
if (SCEN === 'lopsided') {
  when(3, () => {
    const t2 = everyone().filter((c) => c.team === 2), t3 = everyone().filter((c) => c.team === 3);
    if (botsOf().length !== 12 || t2.length !== 8 || t3.length !== 8) fail('lopsided: want 4 humans + 4 bots vs 8 bots, got T ' + t2.length + ' (' + botsOf(2).length + ' bots), CT ' + t3.length);
    else piece('4 humans (all T) + 12 bots: T 4 + 4, CT 8 bots');
  });
  poll(() => aiUp(3) && aiAtSeats(3), 30, () => {
    if (aiBots(2, 'pilot').length || aiBots(2, 'crew').length) fail('lopsided: the side with 4 humans got script roles');
    if (dbg().aiWanted(2, time) || !dbg().aiWanted(3, time)) fail('lopsided: aiWanted wrong (T ' + dbg().aiWanted(2, time) + ', CT ' + dbg().aiWanted(3, time) + ')');
    piece('the all-bot side runs its pilot and crews; the side at the threshold does not');
  }, 'lopsided: the all-bot side got no AI pilot / crews in 30 s');
  when(130, () => { if (!(dbg().stats.aiShots > 0)) fail('lopsided: the all-bot side\'s crews fired nothing'); else piece('CT AI crew shots x' + dbg().stats.aiShots); });
}
if (SCEN === 'full') {
  for (const t of [5, 60, 140]) when(t, () => {
    const b = botsOf().length, D = dbg();
    if (b) fail('full server: ' + b + ' bots joined with ' + HUMANS + ' humans');
    if ([...D.players.values()].some((q) => q.aiRole)) fail('full server: a script role was handed out');
    if (D.stats.aiPilots || D.stats.aiCrews) fail('full server: AI roles counted');
    piece('32v32 humans: no bots, no script roles');
  });
  when(1, () => { if (!(stats.cmds.bot_quota > 0) || quotaMode !== 'fill') fail('the script set no bot_quota / fill'); else piece('bot_quota ' + quota + ' (' + quotaMode + ')'); });
}
if (SCEN === 'yield') {
  const T_ = 2;
  when(1, () => { CFG.AI.PILOTS = 5; CFG.AI.CREWS = 0; CFG.AI.MAX_SHARE = 1; });
  poll(() => dbg().points && dbg().points.aircraft[T_].every((a) => a.pilot >= 0 && PR(a.pilot) && PR(a.pilot).aiRole === 'pilot'), 40, () => {
    piece('all 5 T aircraft flown by script pilots');
    // (a) mid-flight: a human asks for the air in the field (waits for his next deploy), dies, and at the deploy takes a bot's aircraft
    const h = humansOf(T_).find((c) => alive(c) && PR(c.slot).deployed && !PR(c.slot).air);
    if (!h) { fail('yield: no T human on the ground'); return; }
    const held = new Map(dbg().points.aircraft[T_].map((a) => [a, a.pilot]));
    say(h, '!air'); h.pawn.TakeDamage({ damage: 999, damageTypes: DT.BULLET });
    poll(() => PR(h.slot) && PR(h.slot).air, 10, () => {
      const ac = PR(h.slot).air.ac, was = held.get(ac), q = PR(was), c = ctls[was];
      if (ac.pilot !== h.slot) fail('yield: the aircraft does not point at the human');
      if (!q || !c || !c.bot) { fail('yield: the human got an aircraft no bot held'); return; }
      if (q.air || q.aiRole || q.role !== 'infantry') fail('yield: the bot still flies / keeps its role');
      if (alive(c) && (c.pawn.scale !== 1 || c.pawn.mt !== MT.WALK || !q.deployed || !nearPost(c))) fail('yield: the bot was not put back on its feet at a post');
      if (dbg().stats.yields.air !== 1) fail('yield: ' + dbg().stats.yields.air + ' aircraft hand-overs counted');
      if (aiFlying(T_).length !== 4) fail('yield: ' + aiFlying(T_).length + ' script pilots still flying (want 4)');
      piece('human takes a bot-held aircraft mid-flight (same tick)');
      when(time + 3, groundPiece);
    }, 'yield: the human who asked for the air got no aircraft', 1 / 64);
  }, 'yield: the script pilots never held all 5 T aircraft');
  // (b) on the ground: a script pilot is shot down; while he waits in the briefing room his aircraft stands at its park and a human
  //     who asked takes it; the bot, finding none free, deploys as infantry
  function groundPiece() {
    // wait for a script pilot in the air and the second T human alive on the ground (the rate model may have just shot him)
    const ready = () => aiFlying(T_)[0] && humansOf(T_).find((c) => alive(c) && PR(c.slot) && PR(c.slot).deployed && !PR(c.slot).air);
    if (!ready()) { poll(ready, 20, groundPiece, 'yield (ground): no script pilot / no second T human on the ground for 20 s'); return; }
    const b = aiFlying(T_)[0], h2 = humansOf(T_).find((c) => alive(c) && PR(c.slot) && PR(c.slot).deployed && !PR(c.slot).air);
    const bc = ctls[b.slot], ac = b.air.ac, killer = everyone().find((c) => c.team !== T_ && alive(c)), life2 = h2.pawn.spawnedAt;
    say(h2, '!air'); h2.pawn.TakeDamage({ damage: 999, damageTypes: DT.BULLET, attacker: killer && killer.pawn });
    when(time + 0.5, () => {
      const lifeB = bc.pawn.spawnedAt;
      bc.pawn.TakeDamage({ damage: 999, damageTypes: DT.BULLET, attacker: killer && killer.pawn });
      if (bc.pawn.hp > 0) { fail('yield (ground): the script pilot could not be shot down'); return; }
      // both back from the briefing room: the human deploys first (he died 0.5 s earlier) and takes the parked aircraft
      poll(() => h2.pawn.spawnedAt !== life2 && bc.pawn.spawnedAt !== lifeB && PR(h2.slot).deployed && PR(b.slot) && PR(b.slot).deployed, 10, () => {
        const q = PR(b.slot);
        if (!PR(h2.slot).air) fail('yield (ground): the human who asked did not fly');
        if (q.air && q.air.ac === PR(h2.slot).air.ac) fail('yield (ground): two players on one aircraft');
        if (q.aiRole === 'pilot' && q.air) fail('yield (ground): the bot flies again while a human waited');
        if (PR(h2.slot).air && PR(h2.slot).air.ac !== ac) fail('yield (ground): the human did not get the parked aircraft of the bot');
        if (!q.air && (q.aiRole || q.role !== 'infantry')) fail('yield (ground): the bot without an aircraft kept its pilot role');
        piece('human takes a bot\'s parked aircraft (bot ' + (q.air ? 'flies another' : 'deploys as infantry') + ')');
        when(time + 2, seatPiece);
      }, 'yield (ground): no hand-over within 10 s', 1 / 64);
    });
  }
  // (c) a mortar seat: script crews in all five T pits; a human asks for the mortar and takes a seat a bot ran, the same tick
  function seatPiece() {
    CFG.AI.PILOTS = 0; CFG.AI.CREWS = 5;
    poll(() => dbg().crews[T_].every((c) => { const q = c.a >= 0 ? PR(c.a) : undefined; return q && q.aiRole === 'crew'; }), 20, () => {
      piece('all 5 T crews run by script bots');
      const h = humansOf(T_).find((c) => alive(c)); if (!h) { fail('yield (seat): no T human'); return; }
      const before = new Map(dbg().crews[T_].map((c, k) => [k, c.a]));
      const foe = everyone().find((c) => c.team !== T_ && alive(c));          // a pilot in the air only takes enemy damage (the guard)
      say(h, '!mortar'); h.pawn.TakeDamage({ damage: 999, damageTypes: DT.BULLET, attacker: foe && foe.pawn });
      poll(() => PR(h.slot) && PR(h.slot).role === 'mortar', 12, () => {
        const pr = PR(h.slot), k = pr.crew, cr = dbg().crews[T_][k], was = before.get(k), q = PR(was), c = ctls[was];
        if (cr.a !== h.slot && cr.b !== h.slot) fail('yield (seat): the crew does not point at the human');
        if (cr.a >= 0 && cr.b >= 0) fail('yield (seat): the human shares the tube with the bot');
        if (q && (q.aiRole || q.role === 'mortar' || q.crew >= 0)) fail('yield (seat): the bot kept the seat or its role');
        if (c && alive(c) && q && q.deployed && c.pawn.mt === MT.NONE) fail('yield (seat): the bot was left frozen at the table');
        if (cr.ai) fail('yield (seat): the crew kept the bot\'s AI state');
        if (dbg().stats.yields.seat !== 1) fail('yield (seat): ' + dbg().stats.yields.seat + ' seat hand-overs counted');
        piece('human takes a bot-held mortar seat (same tick)');
      }, 'yield (seat): the human who asked never got a seat', 1 / 64);
    }, 'yield (seat): the script crews never held all 5 T pits');
  }
}
if (SCEN === 'threshold') {
  const T_ = 2, added = [];
  poll(() => aiUp(T_) && aiUp(3), 30, () => {
    piece('T and CT run script roles with 2 humans each');
    const flyer = aiFlying(T_)[0], seated = aiSeated(T_).map((q) => q.slot);
    for (let i = 0; i < 2; i++) { const s = ctls.findIndex((c) => !c); added.push(connect(s, T_, false)); }
    fillBots();
    poll(() => !aiBots(T_, 'pilot').length && !aiBots(T_, 'crew').length, 6, () => {
      const D = dbg();
      if (flyer && PR(flyer.slot) && PR(flyer.slot).air) fail('threshold: the script pilot still flies');
      for (const ac of D.points.aircraft[T_]) if (ac.pilot >= 0 && ctls[ac.pilot] && ctls[ac.pilot].bot) fail('threshold: a T aircraft still held by a bot');
      for (const c of D.crews[T_]) for (const s of [c.a, c.b]) if (s >= 0 && ctls[s] && ctls[s].bot) fail('threshold: a T pit still held by a bot');
      for (const s of seated) { const c = ctls[s]; if (c && alive(c) && c.pawn.mt === MT.NONE) fail('threshold: a released crew bot left frozen'); }
      if (!aiUp(3)) fail('threshold: CT (2 humans) lost its script roles');
      piece('T reached 4 humans: its script roles released (' + D.stats.aiReleased.humans + ')');
      when(time + 5, () => {
        // they leave; CS2 may keep a disconnected player's controller in the slot (IsConnected false): it is nobody, and no human
        for (const c of added) { disconnect(c, 'left'); linger[c.slot] = c; }
        fillBots();
        poll(() => aiUp(T_), 25, () => piece('T back to 2 humans: script roles again'), 'threshold: the script roles did not come back after the humans left');
      });
    }, 'threshold: T kept its script roles with 4 humans');
  }, 'threshold: the script roles did not come up');
}
if (SCEN === 'botround') {
  const restart = (order, next) => poll(() => aiUp(2) && aiUp(3) && aiAtSeats(2) && aiAtSeats(3), 40, () => {
    const D = dbg(), shots0 = D.stats.aiShots, sorties0 = D.stats.aiSorties;
    roundRestart(order);
    for (const pr of D.players.values()) if (pr.air) fail('restart left a script pilot flying');
    for (const team of [2, 3]) for (const c of D.crews[team]) if (c.ai) fail('restart left a crew\'s AI state');
    piece('restart (order ' + order + ') with script pilots up and crews at the table');
    poll(() => aiUp(2) && aiUp(3) && aiAtSeats(2) && aiAtSeats(3) && D.stats.aiSorties > sorties0, 20, () => {
      piece('script roles back after the restart (order ' + order + ')');
      poll(() => D.stats.aiShots > shots0, 40, () => { piece('script crews fire again (order ' + order + ')'); if (next) next(); }, 'botround: no AI crew shot after the restart');
    }, 'botround: the script roles did not come back after the restart');
  }, 'botround: the script roles were not up before the restart');
  when(1, () => restart(0, () => restart(1)));
}

if (SCEN === 'handover') {
  // a slot changes hands with no disconnect event (CS2 kicks a bot for a joining human: docs/reference/cs2-gotchas.md, cs_script-notes):
  // the newcomer must start on a record of his own: no script role, crew seat, aircraft, kills or HUD of the last holder
  const takeSlot = (old, bot) => {
    const slot = old.slot;
    old.connected = false; old.pawn.valid = false;                     // the old controller is gone, and no OnPlayerDisconnect comes
    let st = hudState.get(slot); if (!st) hudState.set(slot, st = new Map()); st.set('tw_fly.stale', true);   // the last holder's HUD
    const n = connect(slot, old.team, bot); n.fresh = true; stats.churn['hand-over'] = (stats.churn['hand-over'] || 0) + 1;
    return n;
  };
  poll(() => aiUp(2) && aiUp(3) && aiAtSeats(2) && aiAtSeats(3), 30, () => {
    const cases = [];
    for (const [q, what] of [[aiSeated(2)[0], 'AI crewman -> human'], [aiFlying(3)[0], 'AI pilot -> human']]) {
      if (!q) { fail('handover: no ' + what); continue; }
      const gen = q.gen, team = q.team, crew = q.crew, ac = q.air ? q.air.ac : undefined;
      cases.push({ n: takeSlot(ctls[q.slot], false), gen, team, crew, ac, what });
    }
    const h = humansOf(2).find((c) => alive(c) && PR(c.slot) && PR(c.slot).deployed);
    if (h) { const pr = PR(h.slot); pr.kills = 7; cases.push({ gen: pr.gen, team: 2, crew: pr.role === 'mortar' ? pr.crew : -1, ac: pr.air ? pr.air.ac : undefined, what: 'human -> human', n: takeSlot(h, false) }); }
    poll(() => cases.every((k) => alive(k.n) && PR(k.n.slot) && PR(k.n.slot).deployed && time - k.n.pawn.spawnedAt > 0.5), 12, () => {
      const D = dbg();
      for (const k of cases) {
        const c = k.n, pr = PR(c.slot);
        if (pr.gen === k.gen) fail('handover (' + k.what + '): the newcomer in slot ' + c.slot + ' plays on the last holder\'s record');
        if (pr.aiRole) fail('handover (' + k.what + '): the human newcomer has the script role ' + pr.aiRole);
        if (pr.kills) fail('handover (' + k.what + '): the newcomer inherited ' + pr.kills + ' kills');
        if (c.pawn.mt === MT.NONE && !pr.inSight && !pr.air) fail('handover (' + k.what + '): the newcomer is frozen (move type NONE)');
        if (k.ac && k.ac.pilot === c.slot && !(pr.air && pr.air.ac === k.ac)) fail('handover (' + k.what + '): the last holder\'s aircraft still points at the slot');
        if (k.crew >= 0) { const cr = D.crews[k.team][k.crew]; if ((cr.a === c.slot || cr.b === c.slot) && pr.crew !== k.crew) fail('handover (' + k.what + '): the last holder\'s seat still points at the slot'); }
        const st = hudState.get(c.slot); if (st && st.get('tw_fly.stale')) fail('handover (' + k.what + '): the newcomer kept the last holder\'s HUD');
        piece('slot hand-over with no disconnect event: ' + k.what);
      }
    }, 'handover: the newcomers never deployed');
  }, 'handover: the script roles did not come up');
}

// default runs (no scenario): small set pieces so every guard shows in the coverage table
if (!SCEN && !BAL && botsOf().length + (FILL ? 1 : 0)) leashPieces(150);
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
  if (tick % 64 === 5) {
    fillBots();
    if (botsOf().length) { stats.botsSeen = true; if ([2, 3].some((t) => D.aiWanted(t, time))) stats.aiSeen = true; }
  }
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
                bots: botsOf().length, aiShots: S.aiShots, aiSorties: S.aiSorties, aiAttacks: S.aiAttacks || 0, aiGunRounds: S.aiGunRounds, aiBombs: S.aiBombs,
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
// the sounds the script starts (patch_sounds.py emitters): counted at the emitters; the script's own counters must agree (no reload:
// a reloaded script counts from 0)
const sndW = stats.sounds.tw_whistle_attack || 0, sndD = Object.entries(stats.sounds).filter(([k]) => /^tw_plane_dive_\d+$/.test(k)).reduce((a, [, v]) => a + v, 0);
if (!S.reloads && (sndW !== (S.whistles || 0) || sndD !== (S.dives || 0))) fail('sound counters disagree: whistle ' + sndW + ' vs ' + S.whistles + ', dives ' + sndD + ' vs ' + S.dives);
if (opt.sounds === '0' && (sndW || sndD)) fail('sounds=0: the script started a sound at an emitter the map lacks');
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
    ['sounds: attack whistle / plane dives (' + sndW + ' / ' + sndD + ' started, ' + S.divesSilent + ' dives silent: pool busy or no emitters)']: sndW && sndD ? sndW + sndD : 0,
  };
  if (BAL || N < 16 || HUMANS < 16) delete table['air: AFK pilot taken home'];   // few humans: the AFK pilot may be shot down first
  const need = N >= 16 && SECONDS >= 300;
  // fill=1 runs check the bot rows below; with 4 humans the human-pair rows (a loader beside a firer) may stay at 0
  console.log('coverage (feature -> times exercised)' + (need && !FILL ? '' : FILL ? ' (not enforced in fill=1 runs: the bot rows are)' : ' (not enforced: runs of 16+ players and 300+ s only)') + ':');
  for (const [k, v] of Object.entries(table)) { console.log('  ' + String(v).padStart(6) + '  ' + k); if (need && !FILL && !(v > 0)) fail('coverage: "' + k + '" was never exercised'); }
  // bots (85_ai): enforced when bots played (the deploy and leash rows) and when a side was under the human threshold (the AI rows)
  const L = S.botLeash, bd = S.botDeploys;
  const botRows = [['bots: deploys to the fire trench', bd.fire, 'bots'], ['bots: deploys to the support trench', bd.support, 'bots'], ['bots: deploys into opened areas', bd.area, 'bots'],
    ['bots: leash, no man\'s land / briefing room / far / blocker (' + L.nml + ' / ' + L.lobby + ' / ' + L.far + ' / ' + L.lock + ')', L.nml && L.lobby && L.far ? L.nml + L.lobby + L.far + L.lock : 0, 'bots'],
    ['AI: pilots assigned / sorties (' + S.aiPilots + ' / ' + S.aiSorties + ')', S.aiPilots && S.aiSorties, 'ai'], ['AI: pilot gun rounds', S.aiGunRounds, 'ai'], ['AI: pilot bombs', S.aiBombs, 'ai'],
    ['AI: crews assigned', S.aiCrews, 'ai'], ['AI: crew shots', S.aiShots, 'ai']];
  const botNeed = { bots: need && stats.botsSeen, ai: need && stats.aiSeen };
  console.log('bots (enforced: ' + (botNeed.bots ? 'bot rows' : 'no bot rows') + ', ' + (botNeed.ai ? 'AI rows' : 'no AI rows: no side under ' + CFG.AI.MIN_HUMANS + ' humans with bots') + '):');
  for (const [k, v, kind] of botRows) { console.log('  ' + String(+v || 0).padStart(6) + '  ' + k); if (botNeed[kind] && !(v > 0)) fail('coverage: "' + k + '" was never exercised'); }
}
console.log('script time: ' + P_.avg.toFixed(3) + ' ms/tick avg, p50 ' + P_.p50.toFixed(3) + ', p99 ' + P_.p99 + ', max ' + P_.max + ' ms over ' + P_.ticks + ' ticks, ' + P_.over1 + ' over 1 ms, ' + P_.over8 +
  ' over 8 ms; per tick ' + P_.hud + ' HUD calls, ' + P_.traces + ' traces (the stand-in engine\'s own time is included)');
for (const f of fails) console.log('FAIL ' + f);
console.log(fails.length ? 'RESULT: ' + fails.length + ' failure(s)' : 'RESULT: ok' + (SCEN ? ' (scenario ' + SCEN + ')' : ''));
process.exit(fails.length ? 1 : 0);
