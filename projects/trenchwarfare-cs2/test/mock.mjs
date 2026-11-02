// Runs src/mg_trenchwarfare.js against a stand-in cs_script API: players (humans + bots) spawning, deploying, mortar crews
// plotting / loading / firing, shells landing and hurting players, kills and respawns, chat. Fails on any thrown error,
// unknown HUD panel, or a CSS class the stylesheet lacks.
// usage: node test/mock.mjs [players=24] [seconds=180]
import fs from 'node:fs';
import path from 'node:path';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const MODELS = path.join(root, 'out/addon');
const N = +(process.argv[2] || 24), SECONDS = +(process.argv[3] || 180);
let seed = 7; Math.random = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
const ents = JSON.parse(fs.readFileSync(path.join(root, 'out/entities.json'), 'utf8'));
const xml = fs.readFileSync(path.join(root, 'out/addon/panorama/layout/custom_game/mg_trenchwarfare.xml'), 'utf8');
const css = fs.readFileSync(path.join(root, 'out/addon/panorama/styles/custom_game/mg_trenchwarfare.css'), 'utf8');
const ids = new Set([...xml.matchAll(/id="([^"]+)"/g)].map(m => m[1]));
let time = 0; const stats = { hud: 0, vars: 0, fires: {}, dmg: 0, kills: 0, teleports: 0, impacts: 0, msgs: [] };
const hooks = {};
class Ent {
  constructor(name, cls, pos, ang) { this.name = name; this.cls = cls; this.pos = { ...pos }; this.ang = ang || { pitch: 0, yaw: 0, roll: 0 }; this.valid = true; }
  IsValid() { return this.valid; } GetAbsOrigin() { return { ...this.pos }; } GetAbsAngles() { return { ...this.ang }; }
  GetClassName() { return this.cls; } GetEntityName() { return this.name; }
  Remove() { this.valid = false; this.removed = true; stats.removed = (stats.removed || 0) + 1; } SetModelScale(v) { if (!Number.isFinite(v) || v <= 0) throw new Error('bad scale ' + v); this.scale = v; }
  Teleport(o) { if (o.position) this.pos = { ...o.position }; if (o.angles) this.ang = { ...o.angles }; stats.teleports++; }
  Move(o) { if (o.position) { for (const k of ['x', 'y', 'z']) if (!Number.isFinite(o.position[k])) throw new Error('bad Move ' + JSON.stringify(o)); this.pos = { ...o.position }; } if (o.angles) this.ang = { ...o.angles }; stats.moves = (stats.moves || 0) + 1; }
  SetParent(p) { this.parent = p; } GetParent() { return this.parent; }
}
class Cam extends Ent { constructor(p) { super('', 'camera', { x: 0, y: 0, z: 0 }); this.p = p; this.mode = 0; } SetMode(m) { this.mode = m; stats.cam = (stats.cam || 0) + 1; } GetMode() { return this.mode; } SetFollowConfig(c) { if (!c.followEntity) throw new Error('follow without entity'); } }
const world = new Map();
for (const e of ents) if (e.name) world.set(e.name, new Ent(e.name, e.cls, { x: e.origin[0], y: e.origin[1], z: e.origin[2] }, { pitch: e.angles[0], yaw: e.angles[1], roll: e.angles[2] }));
class Hud extends Ent {
  SetHasClassForPlayer(slot, panel, cls, on) { stats.hud++; if (!ids.has(panel)) throw new Error('unknown panel ' + panel); if (!css.includes('.' + cls)) throw new Error('no css for class ' + cls); }
  SetDialogVariableStringForPlayer(slot, panel, n, v) { stats.vars++; if (!ids.has(panel)) throw new Error('unknown panel ' + panel); if (typeof v !== 'string') throw new Error('bad var'); }
  ResetForPlayer() {}
}
world.set('tw_hud', new Hud('tw_hud', 'custom_hud_layout', { x: 0, y: 0, z: 0 }));
const lobby = ents.filter(e => e.cls.startsWith('info_player'));
const IN = { FORWARD: 1, BACK: 2, LEFT: 4, RIGHT: 8, WALK: 16, DUCK: 32, JUMP: 64, USE: 128, ATTACK: 256, ATTACK2: 512, RELOAD: 1024 };
class Weapon { constructor(n) { this.n = n; this.clip = n === 'weapon_ssg08' ? 10 : 13; this.res = 90; }
  GetClassName() { return this.n; } GetClipAmmo() { return this.clip; } SetClipAmmo(v) { this.clip = v; } GetReserveAmmo() { return this.res; } SetReserveAmmo(v) { this.res = v; } IsValid() { return true; } }
class Pawn extends Ent {
  constructor(ctl) { super('', 'player', { x: 0, y: 0, z: 0 }); this.ctl = ctl; this.hp = 100; this.armor = 0; this.helmet = false; this.weapons = []; this.keys = 0; this.mt = 2; }
  GetPlayerController() { return this.ctl; } GetTeamNumber() { return this.ctl.team; } IsAlive() { return this.hp > 0; }
  GetHealth() { return this.hp; } SetHealth(v) { if (!Number.isInteger(v)) throw new Error('SetHealth non-integer ' + v); this.hp = v; }
  GetArmor() { return this.armor; } SetArmor(v) { if (!Number.isInteger(v)) throw new Error('SetArmor non-integer ' + v); this.armor = v; } HasHelmet() { return this.helmet; } SetHasHelmet(v) { this.helmet = v; }
  IsInputPressed(b) { return (this.keys & b) !== 0; } SetEyeAngles(a) { this.eye = { ...a }; } GetEyeAngles() { return this.eye || { pitch: 0, yaw: 0, roll: 0 }; } SetMoveType(m) { this.mt = m; }
  GetModelName() { return this.model || 'agents/models/stock.vmdl'; } SetModel(m) { if (!fs.existsSync(path.join(MODELS, m)) && !m.startsWith('agents/')) throw new Error('SetModel to a model the addon lacks: ' + m); this.model = m; stats.setmodel = (stats.setmodel || 0) + 1; }
  GetCustomCamera() { return this.cam || (this.cam = new Cam(this)); }
  DestroyWeapons() { this.weapons = []; } DestroyWeapon(w) { this.weapons = this.weapons.filter(x => x !== w); }
  GiveNamedItem(n) { if (this.weapons.find(w => w.n === n)) throw new Error('duplicate weapon ' + n); this.weapons.push(new Weapon(n)); }
  FindWeapon(n) { return this.weapons.find(w => w.n === n); }
  TakeDamage(d) { if (!(d.damage > 0)) throw new Error('bad damage'); if (hooks.mod) { const r = hooks.mod({ player: this, damage: d.damage, damageTypes: d.damageTypes || 0, attacker: d.attacker, inflictor: d.inflictor }); if (r && r.abort) { stats.blocked = (stats.blocked || 0) + 1; return 0; } } stats.dmg++; this.hp -= Math.round(d.damage); if (this.hp <= 0) { this.hp = 0; die(this, d.attacker); } return d.damage; }
}
class Ctl extends Ent {
  constructor(slot, team, bot) { super('', 'cs_player_controller', { x: 0, y: 0, z: 0 }); this.slot = slot; this.team = team; this.bot = bot; this.pawn = new Pawn(this); }
  GetPlayerSlot() { return this.slot; } GetPlayerPawn() { return this.pawn; } IsBot() { return this.bot; } GetPlayerName() { return 'p' + this.slot; }
}
const ctls = [];
function spawn(c) {
  const sp = lobby.filter(e => (e.cls.endsWith('terrorist') && !e.cls.includes('counter')) === (c.team === 2));
  const e = sp[c.slot % sp.length];
  c.pawn = new Pawn(c); c.pawn.pos = { x: e.origin[0], y: e.origin[1], z: e.origin[2] };
  hooks.reset && hooks.reset({ player: c.pawn });
}
function die(pawn, attacker) {
  stats.kills++;
  hooks.kill && hooks.kill({ player: pawn, attacker });
  const c = pawn.ctl; setTimeout0(2, () => spawn(c));
}
const later = [];
function setTimeout0(dt, fn) { later.push({ at: time + dt, fn }); }
const Instance = {
  Msg: (m) => stats.msgs.push(String(m)), GetGameTime: () => time, SetThink: (f) => { Instance._think = f; }, SetNextThink: (t) => { Instance._next = t; },
  OnActivate: (f) => hooks.activate = f, OnRoundStart: (f) => hooks.round = f, OnPlayerReset: (f) => hooks.reset = f, OnPlayerDisconnect: (f) => hooks.disc = f,
  OnPlayerKill: (f) => hooks.kill = f, OnPlayerChat: (f) => hooks.chat = f, OnBulletImpact: (f) => hooks.bullet = f, OnModifyPlayerDamage: (f) => hooks.mod = f,
  FindEntityByName: (n) => world.get(n), FindEntitiesByName: (n) => (world.has(n) && !world.get(n).removed ? [world.get(n)] : []), GetPlayerController: (s) => ctls[s],
  EntFireAtName: (o) => { stats.fires[o.input] = (stats.fires[o.input] || 0) + 1; if (!world.has(o.name) && !o.name.startsWith('mortar_')) throw new Error('EntFire at missing entity ' + o.name); },
  ServerCommand: () => {},
  TraceLine: (o) => {
    for (const v of [o.start, o.end]) for (const k of ['x', 'y', 'z']) if (!Number.isFinite(v[k])) throw new Error('bad trace ' + JSON.stringify(o));
    if (o.end.z >= 0) {
      // aircraft guns: hit an enemy plane if the ray passes close
      if (o.traceHitboxes) for (const e of world.values()) if (e.name.startsWith('tw_plane_') && e.name !== (o.ignoreEntity && o.ignoreEntity[0] && o.ignoreEntity[0].name)) {
        const d = { x: o.end.x - o.start.x, y: o.end.y - o.start.y, z: o.end.z - o.start.z }; const L = Math.hypot(d.x, d.y, d.z);
        const w = { x: e.pos.x - o.start.x, y: e.pos.y - o.start.y, z: e.pos.z - o.start.z }; const tt = (w.x * d.x + w.y * d.y + w.z * d.z) / L;
        if (tt > 0 && tt < L && Math.hypot(w.x - d.x * tt / L, w.y - d.y * tt / L, w.z - d.z * tt / L) < 150) { stats.planeHits = (stats.planeHits || 0) + 1; return { didHit: true, fraction: tt / L, end: e.pos, hitEntity: e, startedInSolid: false }; }
      }
      return { didHit: false, fraction: 1, end: { ...o.end }, startedInSolid: false };
    }
    const f = o.start.z / Math.max(1e-6, o.start.z - o.end.z);
    return { didHit: true, fraction: f, end: { x: o.start.x + (o.end.x - o.start.x) * f, y: o.start.y + (o.end.y - o.start.y) * f, z: 0 }, startedInSolid: false };
  },
};
// ESM loader shim
const src = fs.readFileSync(path.join(root, 'src/mg_trenchwarfare.js'), 'utf8')
  .replace(/import \{([^}]*)\} from "cs_script\/point_script";/, 'const {$1} = globalThis.__cs;');
globalThis.__cs = { Instance, CSInputs: IN, CSMoveType: { NONE: 0, WALK: 2 }, CSDamageTypes: { BLAST: 64 }, CustomCameraMode: { DISABLED: 0, CONTROLLED: 1, CONTROLLED_POSITION: 2, FOLLOW_POSITION: 3 } };
const tmp = path.join(root, 'test/_run.mjs'); fs.writeFileSync(tmp, src);
await import(tmp);
for (let s = 0; s < N; s++) ctls.push(new Ctl(s, s % 2 ? 3 : 2, s % 3 === 2));
hooks.activate(); hooks.round && hooks.round();
for (const c of ctls) spawn(c);
const DT = 1 / 64;
let fired = 0;
for (let step = 0; step < SECONDS * 64; step++) {
  time += DT;
  for (let i = later.length - 1; i >= 0; i--) if (later[i].at <= time) { const f = later[i].fn; later.splice(i, 1); f(); }
  // drive mortar crews: walk to stations and press keys like a player would
  for (const c of ctls) {
    const p = c.pawn; p.keys = 0;
    if (c.bot || p.hp <= 0) continue;
    const pr = globalThis.__twDebug && globalThis.__twDebug.players.get(c.slot);
    if (pr && pr.air && !c.flyStart) c.flyStart = time;
    if (pr && !pr.air && c.flyStart) { (stats.flights = stats.flights || []).push(time - c.flyStart); c.flyStart = 0; }
    if (pr && pr.air) {
      stats.flyTicks = (stats.flyTicks || 0) + 1;
      if (process.env.DEBUGFLY && step % 32 === 0 && c.slot === +process.env.DEBUGFLY) console.log('t', time.toFixed(1), 'z', pr.air.pos.z.toFixed(0), 'fz', pr.air.f.z.toFixed(3), 'v', pr.air.speed.toFixed(0), 'eye', JSON.stringify(p.eye), 'pos', pr.air.pos.x.toFixed(0), pr.air.pos.y.toFixed(0));
      if (pr.air.pos && Number.isFinite(pr.air.pos.z)) { stats.zMin = Math.min(stats.zMin ?? 1e9, pr.air.pos.z); stats.zMax = Math.max(stats.zMax ?? -1e9, pr.air.pos.z); }
      p.eye = { pitch: 10 * Math.sin(time * 0.7 + c.slot), yaw: (c.team === 3 ? 180 : 0) + 70 * Math.sin(time * 0.3 + c.slot), roll: 0 };
      p.keys = IN.ATTACK | (Math.floor(time) % 4 === 0 ? IN.RIGHT : Math.floor(time) % 4 === 2 ? IN.LEFT : 0) | (Math.floor(time * 4) % 37 === 0 ? IN.ATTACK2 : 0) | (time % 10 < 5 ? IN.FORWARD : 0);
      continue;
    }
    if (pr && pr.upgraded && step % 300 === 0) p.keys = IN.WALK | IN.USE;
    const t = c.team === 2 ? 't' : 'ct';
    const near = (n) => world.get(n);
    for (let k = 1; k <= 5; k++) {
      const a = near(`mortarcrew_${t}_${k}_a`).pos, b = near(`mortarcrew_${t}_${k}_b`).pos, pit = near(`mortarpit_${t}_${k}`).pos;
      const d = (q) => Math.hypot(p.pos.x - q.x, p.pos.y - q.y);
      if (d(a) < 60 || d(b) < 60 || d(pit) < 80) {
        const ph = Math.floor(time * 2) % 8;
        if (ph === 0 && p.mt === 0) { p.keys = IN.USE; }
        else if (ph === 0) { p.pos = { ...b }; }
        else if (ph === 1 && d(b) < 60) { p.keys = IN.USE; }
        else if (ph === 2) { p.pos = { ...pit }; }
        else if (ph === 3 && d(pit) < 80) { p.keys = IN.USE; }
        else if (ph === 4) { p.pos = { ...a }; }
        else if (ph === 5 && d(a) < 60) { p.keys = IN.USE; }
        else if (ph === 6 && p.mt === 0) { p.keys = IN.FORWARD | IN.ATTACK; }
        else if (ph === 7 && p.mt === 0) { p.keys = IN.JUMP; fired++; }
        break;
      }
    }
  }
  if (step % 640 === 0) hooks.chat({ player: ctls[1], text: '!mortar', team: 3 });
  if (step % 900 === 0) hooks.chat({ player: ctls[4], text: '!air', team: 3 });
  if (step % 50 === 0 && hooks.bullet) {   // rifle bullets striking a random plane
    const planes = [...world.values()].filter(e => e.name.startsWith('tw_plane_') && /_(t|ct)_\d+$/.test(e.name) && !e.name.includes('_eng_') && !e.name.includes('_gun_'));
    const a = ctls[Math.floor(Math.random() * N)];
    if (planes.length && a.pawn.hp > 0) hooks.bullet({ weapon: { GetOwner: () => a.pawn, GetData: () => ({ GetDamage: () => 88 }) }, position: { x: 0, y: 0, z: 0 }, hitEntity: planes[Math.floor(Math.random() * planes.length)] });
  }
  // bots wandering onto a still-closed area's blocker must be sent back to the trench (CONFIG.BOTS leash)
  if (step % 640 === 320) {
    const locks = ['woodsopen', 'undergroundopen'].map(n => world.get(n)).filter(e => e && !e.removed);
    const bots = ctls.filter(c => c.bot && c.pawn.hp > 0 && Math.abs(c.pawn.pos.z) < 400);
    if (locks.length && bots.length) {
      const c = bots[Math.floor(Math.random() * bots.length)], L = locks[Math.floor(Math.random() * locks.length)];
      c.pawn.pos = { x: L.pos.x + 40, y: L.pos.y - 40, z: L.pos.z };
      later.push({ at: time + 4.5, fn: () => {
        if (L.removed || c.pawn.hp <= 0) return;
        const d = Math.hypot(c.pawn.pos.x - L.pos.x, c.pawn.pos.y - L.pos.y);
        if (d > 300) stats.leashOk = (stats.leashOk || 0) + 1; else throw new Error('bot left at the ' + L.name + ' blocker');
      } });
    }
  }
  // random rifle kills between infantry
  if (step % 97 === 0) {
    const a = ctls[Math.floor(Math.random() * N)], v = ctls[Math.floor(Math.random() * N)];
    if (a.team !== v.team && v.pawn.hp > 0 && a.pawn.hp > 0) v.pawn.TakeDamage({ damage: 150, attacker: a.pawn });
  }
  if (Instance._next !== undefined && Instance._next <= time) { Instance._next = undefined; Instance._think(); }
}
fs.unlinkSync(tmp);
const D = globalThis.__twDebug; const rc = {}; for (const p of D.players.values()) rc[p.team + ':' + p.role] = (rc[p.team + ':' + p.role] || 0) + 1;
console.log('roles', JSON.stringify(rc), 'crews', JSON.stringify(D.crews[3].map(c => [c.a, c.b, c.loaded, !!c.target, c.impacts.length])));
const roles = {}; // count from HUD would need introspection; report activity instead
console.log(JSON.stringify({ hud: stats.hud, vars: stats.vars, fires: stats.fires, dmg: stats.dmg, kills: stats.kills, teleports: stats.teleports, moves: stats.moves, cam: stats.cam, flyTicks: stats.flyTicks, planeHits: stats.planeHits, setModel: stats.setmodel, removed: stats.removed, mortarFireAttempts: fired, leashOk: stats.leashOk, flights: stats.flights ? [stats.flights.length, +(stats.flights.reduce((x, y) => x + y, 0) / stats.flights.length).toFixed(1)] : null, zRange: [Math.round(stats.zMin), Math.round(stats.zMax)], errors: stats.msgs.filter(m => m.includes('error')).slice(0, 3), msgs: stats.msgs.slice(0, 3) }));
