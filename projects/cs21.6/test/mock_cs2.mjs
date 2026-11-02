// Runs the real out/addon/maps/scripts/cs16.js against a stand-in for CS2's cs_script API: players joining and leaving,
// warmup, rounds with freeze time, buying through the menu and chat, gunfights (with CS2-like damage events), knives,
// grenades, falls, bomb plants / defuses / explosions on every map, round ends through FireWinCondition.
// It checks the script keeps working (no errors, rounds end, nobody outside their map, HUD panels exist) and measures
// the script's time and engine calls per tick.
// usage: node test/mock_cs2.mjs [players=64] [seconds=600] [opts: v,churn,seed=<n>]
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const N = +(process.argv[2] || 64), SECONDS = +(process.argv[3] || 600), OPTS = process.argv[4] || '';
const SEED = +((OPTS.match(/seed=(\d+)/) || [])[1] || 1);
{ let st = SEED >>> 0; Math.random = () => { st = (st + 0x6D2B79F5) >>> 0; let t = st; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const R = (a, b) => a + Math.random() * (b - a);

const MAPS = JSON.parse(fs.readFileSync(path.join(root, 'out/addon/_gen/maps.json'), 'utf8')).maps;
const hudIds = new Set(JSON.parse(fs.readFileSync(path.join(root, 'out/addon/_gen/hud_ids.json'), 'utf8')));
const css = fs.readFileSync(path.join(root, 'out/addon/panorama/styles/custom_game/cs16.css'), 'utf8');
const sounds = JSON.parse(fs.readFileSync(path.join(root, 'out/addon/_gen/sounds.json'), 'utf8'));

let time = 0, calls = 0;
const stats = { errors: [], msgs: [], rounds: 0, wins: {}, kills: 0, buys: 0, plants: 0, defuses: 0, explodes: 0, hud: 0, hudVars: 0, sounds: 0,
  teleports: 0, outside: 0, clicks: 0, cvars: [], tickMs: [], callsPerTick: [], dmg: { n: 0, cs2: 0, s16: 0 }, money: [], falls: 0, models: 0 };
const hooks = {};
const later = [];
function after(dt, fn) { later.push({ at: time + dt, fn }); }

// ---------------------------------------------------------------- entities
class Entity {
  constructor(name, cls, pos) { this.name = name; this.cls = cls; this.pos = pos || { x: 0, y: 0, z: 0 }; this.valid = true; this.ang = { pitch: 0, yaw: 0, roll: 0 }; }
  IsValid() { calls++; return this.valid; }
  GetAbsOrigin() { calls++; return { ...this.pos }; }
  GetAbsAngles() { calls++; return { ...this.ang }; }
  GetClassName() { calls++; return this.cls; }
  GetEntityName() { return this.name; }
  SetEntityName(n) { calls++; this.name = n; }
  GetTeamNumber() { return this.team || 0; }
}
const world = new Map();
function addEnt(e) { world.set(e.name, e); return e; }
class Hud extends Entity {
  SetHasClassForPlayer(slot, panel, cls, on) { calls++; stats.hud++; if (!hudIds.has(panel)) throw new Error('unknown HUD panel ' + panel); if (!css.includes('.' + cls)) throw new Error('class without css ' + cls); }
  SetDialogVariableStringForPlayer(slot, panel, name, v) { calls++; stats.hudVars++; if (!hudIds.has(panel)) throw new Error('unknown HUD panel ' + panel); if (typeof v !== 'string') throw new Error('non-string'); }
  ResetForPlayer() { calls++; }
  SetInputCaptureEnabled(slot, on) { calls++; const c = players[slot]; if (c) c.capture = on; }
  IsInputCaptureEnabled(slot) { return !!(players[slot] && players[slot].capture); }
}
addEnt(new Hud('cs16_hud', 'custom_hud_layout'));
addEnt(new Entity('cs16_map_params', 'info_map_parameters'));
for (const s of sounds) addEnt(new Entity('cs16_snd_' + s.split('.')[1], 'point_soundevent'));

// ---------------------------------------------------------------- weapons
const WDATA = {   // CS2 weapon data: name, type, gear slot, damage, range modifier, clip, reserve
  weapon_glock: ['weapon_glock', 1, 1, 30, 0.85, 20, 120], weapon_usp_silencer: ['weapon_usp_silencer', 1, 1, 35, 0.91, 12, 24], weapon_hkp2000: ['weapon_hkp2000', 1, 1, 35, 0.91, 13, 52],
  weapon_p250: ['weapon_p250', 1, 1, 38, 0.9, 13, 26], weapon_deagle: ['weapon_deagle', 1, 1, 53, 0.85, 7, 35], weapon_elite: ['weapon_elite', 1, 1, 38, 0.79, 30, 120],
  weapon_fiveseven: ['weapon_fiveseven', 1, 1, 32, 0.81, 20, 100], weapon_nova: ['weapon_nova', 4, 0, 26, 0.7, 8, 32], weapon_xm1014: ['weapon_xm1014', 4, 0, 20, 0.7, 7, 32],
  weapon_mac10: ['weapon_mac10', 2, 0, 29, 0.8, 30, 100], weapon_mp9: ['weapon_mp9', 2, 0, 26, 0.87, 30, 120], weapon_mp5sd: ['weapon_mp5sd', 2, 0, 27, 0.85, 30, 120],
  weapon_ump45: ['weapon_ump45', 2, 0, 35, 0.85, 25, 100], weapon_p90: ['weapon_p90', 2, 0, 26, 0.86, 50, 100], weapon_galilar: ['weapon_galilar', 3, 0, 30, 0.98, 35, 90],
  weapon_famas: ['weapon_famas', 3, 0, 30, 0.96, 25, 90], weapon_ak47: ['weapon_ak47', 3, 0, 36, 0.98, 30, 90], weapon_m4a1_silencer: ['weapon_m4a1_silencer', 3, 0, 38, 0.99, 20, 80],
  weapon_sg556: ['weapon_sg556', 3, 0, 30, 0.98, 30, 90], weapon_aug: ['weapon_aug', 3, 0, 28, 0.98, 30, 90], weapon_ssg08: ['weapon_ssg08', 5, 0, 88, 0.98, 10, 90],
  weapon_awp: ['weapon_awp', 5, 0, 115, 0.99, 10, 30], weapon_g3sg1: ['weapon_g3sg1', 5, 0, 80, 0.98, 20, 90], weapon_scar20: ['weapon_scar20', 5, 0, 80, 0.98, 20, 90],
  weapon_m249: ['weapon_m249', 6, 0, 32, 0.97, 100, 200], weapon_knife: ['weapon_knife', 0, 2, 40, 1, -1, -1], weapon_knife_t: ['weapon_knife_t', 0, 2, 40, 1, -1, -1],
  weapon_c4: ['weapon_c4', 7, 4, 0, 1, -1, -1], weapon_hegrenade: ['weapon_hegrenade', 9, 3, 0, 1, -1, 1], weapon_flashbang: ['weapon_flashbang', 9, 3, 0, 1, -1, 2],
  weapon_smokegrenade: ['weapon_smokegrenade', 9, 3, 0, 1, -1, 1],
};
class WeaponData {
  constructor(d) { this.d = d; }
  GetName() { calls++; return this.d[0]; } GetType() { calls++; return this.d[1]; } GetGearSlot() { return this.d[2]; } GetDamage() { calls++; return this.d[3]; }
  GetRangeModifier() { calls++; return this.d[4]; } GetMaxClipAmmo() { return this.d[5]; } GetMaxReserveAmmo() { return this.d[6]; } GetPenetration() { return 1; }
}
class Weapon extends Entity {
  constructor(cls, owner) { super('', cls); const d = WDATA[cls]; if (!d) throw new Error('GiveNamedItem unknown ' + cls); this.data = new WeaponData(d); this.owner = owner; this.clip = d[5]; this.reserve = d[6]; this.sil = cls.includes('silencer'); }
  GetData() { calls++; return this.data; } GetOwner() { calls++; return this.owner; }
  GetClipAmmo() { calls++; return this.clip; } GetReserveAmmo() { calls++; return this.reserve; }
  SetClipAmmo(n) { calls++; this.clip = n; } SetReserveAmmo(n) { calls++; if (!(n >= 0)) throw new Error('bad reserve ' + n); this.reserve = n; }
  IsSilencerOn() { calls++; return this.sil; }
}

// ---------------------------------------------------------------- players
class Pawn extends Entity {
  constructor(ctrl) {
    super('', 'player'); this.ctrl = ctrl; this.team = ctrl.team; this.alive = true; this.health = 100; this.armor = 0; this.helmet = false; this.defuser = false;
    this.vel = { x: 0, y: 0, z: 0 }; this.weapons = []; this.active = null; this.buttons = 0; this.prev = 0;
    this.give('weapon_knife'); this.give(ctrl.team === 2 ? 'weapon_glock' : 'weapon_hkp2000');
    const m = MAPS[Math.floor(Math.random() * MAPS.length)];
    const sp = m.spawns[ctrl.team === 2 ? 'T' : 'CT'][0];
    this.pos = { x: sp[0] + R(-500, 500), y: sp[1] + R(-500, 500), z: sp[2] };      // CS2 puts them on any map's spawn
  }
  give(cls) { const w = new Weapon(cls, this); const slot = w.data.d[2]; if (slot !== 3 && slot !== 4) this.weapons = this.weapons.filter((x) => x.data.d[2] !== slot || x.cls === cls && false); this.weapons.push(w); this.active = w; return w; }
  GetPlayerController() { calls++; return this.ctrl; } GetOriginalPlayerController() { return this.ctrl; }
  IsAlive() { calls++; return this.alive; } GetHealth() { calls++; return this.health; } SetHealth(h) { this.health = h; }
  GetArmor() { calls++; return this.armor; } SetArmor(a) { calls++; if (!(a >= 0 && a <= 100)) throw new Error('bad armour ' + a); this.armor = a; }
  HasHelmet() { calls++; return this.helmet; } SetHasHelmet(h) { calls++; this.helmet = h; } HasDefuser() { calls++; return this.defuser; } SetHasDefuser(d) { calls++; this.defuser = d; }
  GetAbsVelocity() { calls++; return { ...this.vel }; }
  GetEyePosition() { calls++; return { x: this.pos.x, y: this.pos.y, z: this.pos.z + 64 }; }
  GetEyeAngles() { calls++; return { ...this.ang }; } SetEyeAngles(a) { calls++; this.ang = { ...a }; }
  Teleport(o) { calls++; stats.teleports++; if (o.position) { const p = o.position; if (![p.x, p.y, p.z].every(Number.isFinite)) throw new Error('bad teleport'); this.pos = { ...p }; } if (o.angles) this.ang = { ...o.angles }; }
  IsInputPressed(b) { calls++; return !!(this.buttons & b); } WasInputJustPressed(b) { calls++; return !!(this.buttons & ~this.prev & b); } WasInputJustReleased() { return false; }
  IsBuyMenuOpen() { calls++; return false; }
  FindWeapon(cls) { calls++; return this.weapons.find((w) => w.cls === cls); }
  FindWeaponBySlot(s) { calls++; return this.weapons.find((w) => w.data.d[2] === s); }
  GetActiveWeapon() { calls++; return this.active; }
  GetC4() { calls++; return this.weapons.find((w) => w.cls === 'weapon_c4'); }
  GiveNamedItem(cls) { calls++; if (OPTS.includes('defer')) after(0.02, () => { if (this.alive) this.give(cls); }); else this.give(cls); }
  DropWeapon(w) { calls++; this.weapons = this.weapons.filter((x) => x !== w); if (this.active === w) this.active = this.weapons[0]; }
  DestroyWeapon(w) { calls++; this.DropWeapon(w); }
  SetModel(m) { calls++; stats.models++; if (!/^(characters\/models|models\/player\/cs16)\/.+\.vmdl$/.test(m)) throw new Error('bad model ' + m); }
  TakeDamage(d) {
    calls++;
    const r = hooks.OnModifyPlayerDamage ? hooks.OnModifyPlayerDamage({ player: this, damage: d.damage, damageTypes: d.damageTypes || 0, damageFlags: d.damageFlags || 0, hitGroup: 0 }) : undefined;
    if (r && r.abort) return 0;
    hit(this, r && r.damage !== undefined ? r.damage : d.damage, null, null);
    return d.damage;
  }
}
class Controller {
  constructor(slot, team, bot) { this.slot = slot; this.team = team; this.bot = bot; this.connected = true; this.pawn = null; this.money = 800; }
  GetPlayerSlot() { calls++; return this.slot; } GetPlayerName() { return 'p' + this.slot; } GetPlayerPawn() { calls++; return this.pawn && this.pawn.valid ? this.pawn : undefined; }
  IsBot() { calls++; return this.bot; } IsConnected() { calls++; return this.connected; } GetTeamNumber() { calls++; return this.team; } IsValid() { return this.connected; }
  GetMoneySpendableNow() { calls++; return this.money; }
  AddMoneySpendableNow(n) { calls++; if (!Number.isFinite(n)) throw new Error('bad money'); this.money = Math.max(0, Math.min(16000, this.money + n)); }
  spawn() { if (!this.connected || this.team < 2) return; const old = this.pawn; const keep = old && old.alive; if (!keep) { if (old) old.valid = false; this.pawn = new Pawn(this); } hooks.OnPlayerReset({ player: this.pawn }); }
}
const players = [];
for (let i = 0; i < N; i++) players.push(new Controller(i, i % 2 ? 3 : 2, i >= 8));

function die(p, attacker, weapon) {
  p.alive = false; stats.kills++;
  for (const w of p.weapons) if (w.cls === 'weapon_c4') { const c4 = new Entity('', 'weapon_c4', { ...p.pos }); c4.dropped = true; droppedC4.push({ ent: c4, pos: { ...p.pos } }); }
  hooks.OnPlayerKill && hooks.OnPlayerKill({ player: p, attacker, weapon });
}
const droppedC4 = [];
function hit(p, dmg, attacker, weapon) {
  if (!p.alive) return;
  p.health -= Math.max(0, Math.round(dmg));
  if (p.health <= 0) { p.health = 0; die(p, attacker, weapon); }
}

// ---------------------------------------------------------------- the game: warmup, rounds, freeze time, round ends
let warmup = true, frozen = false, roundTime = 0, roundLive = false, plantedC4s = [];
let thinkFn = null;
const Instance = {
  Msg: (m) => { const s = String(m); stats.msgs.push(s); if (/error in|WARNING/.test(s)) stats.errors.push(s); if (OPTS.includes('v')) console.log(s); },
  GetGameTime: () => time, SetThink: (f) => { thinkFn = f; }, SetNextThink: () => {}, Delay: (s) => new Promise((r) => after(s, r)),
  IsWarmupPeriod: () => { calls++; return warmup; }, IsFreezePeriod: () => { calls++; return frozen; },
  GetRoundRemainingTime: () => { calls++; return roundTime; }, GetRoundsPlayed: () => { calls++; return Math.max(0, stats.rounds); }, SetRoundRemainingTime: (t) => { calls++; roundTime = t; },
  ServerCommand: (c) => { calls++; stats.cvars.push(c); },
  FindEntityByName: (n) => { calls++; return world.get(n); },
  GetPlayerController: (s) => { calls++; const c = players[s]; return c && c.connected ? c : undefined; },
  GetAllPlayerControllers: () => players.filter((c) => c.connected),
  EntFireAtName: (o) => { calls++; if (o.input === 'FireWinCondition') { if (OPTS.includes('dbg')) dumpState('win ' + o.value); endRound(o.value); } },
  EntFireAtTarget: (o) => { calls++; if (o.input === 'StartSound') stats.sounds++; if (o.input === 'SetSourceEntity' && !players.some((c) => c.pawn && c.pawn.name === o.value)) throw new Error('sound source missing ' + o.value); },
};
for (const k of ['OnActivate', 'OnPlayerActivate', 'OnPlayerConnect', 'OnPlayerDisconnect', 'OnPlayerReset', 'OnPlayerTeamChanged', 'OnRoundStart', 'OnRoundEnd',
  'OnBeginRoundRestart', 'OnBombPlant', 'OnBombDefuse', 'OnBombExplode', 'OnPlayerKill', 'OnModifyPlayerDamage', 'OnPlayerLand', 'OnKnifeAttack', 'OnPlayerChat',
  'OnCustomHudClicked', 'OnGrenadeThrow', 'OnScriptInput', 'OnPlayerDamage', 'OnBombPlantStart', 'OnGunFire', 'OnPlayerJump', 'OnScriptReload']) Instance[k] = (f) => { hooks[k] = f; };

function dumpState(why) {
  const g = globalThis.__cs16;
  console.log(`t=${time.toFixed(1)} ${why}: plan`, [...g.round.maps.values()].map((m) => `${m.key} active=${m.active} res=${JSON.stringify(m.result)}`).join('; '));
  for (const c of players) { const r = g.recs.get(c.slot); console.log(`  slot ${c.slot} conn=${c.connected} team=${c.team} pawn=${!!c.pawn} alive=${c.pawn && c.pawn.alive} | rec team=${r && r.team} map=${r && r.map} alive=${r && r.alive}`); }
}
function endRound(reason) {
  if (!roundLive) return;
  roundLive = false; stats.rounds++;
  const winner = reason === 9 ? 2 : reason === 8 ? 3 : 0;     // (the script sends 9 / 8 for wins, 10 or 2 for a draw)
  if (![8, 9, 10, 2].includes(reason)) throw new Error('unexpected FireWinCondition ' + reason);
  stats.wins[reason] = (stats.wins[reason] || 0) + 1;
  hooks.OnRoundEnd({ winningTeam: winner, reason });
  after(5, startRound);
}
function startRound() {
  hooks.OnBeginRoundRestart && hooks.OnBeginRoundRestart();
  plantedC4s = []; droppedC4.length = 0;
  for (const c of players) c.spawn();
  frozen = true; roundLive = true; roundTime = 115;
  hooks.OnRoundStart();
  after(6, () => { frozen = false; });
}

// ---------------------------------------------------------------- load the script
const src = fs.readFileSync(path.join(root, 'out/addon/maps/scripts/cs16.js'), 'utf8').replace(/^import .*$/m, '');
const fn = new Function('Instance', 'CSInputs', 'CSDamageFlags', 'CSDamageTypes', src + '\nglobalThis.__cs16 = { recs, round };');
fn(Instance, { NONE: 0, FORWARD: 1, BACK: 2, LEFT: 4, RIGHT: 8, WALK: 16, DUCK: 32, JUMP: 64, USE: 128, ATTACK: 256, ATTACK2: 512, RELOAD: 1024, SHOW_SCORES: 2048, LOOK_AT_WEAPON: 4096 },
  { NONE: 0, IGNORE_ARMOR: 64 }, { GENERIC: 0, BULLET: 2, SLASH: 4, FALL: 32, BLAST: 64, HEADSHOT: 8192 });
hooks.OnActivate();
for (const c of players) { hooks.OnPlayerConnect && hooks.OnPlayerConnect({ player: c }); hooks.OnPlayerActivate({ player: c }); c.spawn(); }

// ---------------------------------------------------------------- what players do each tick
function mapOf(p) { for (const m of MAPS) { const [lo, hi] = m.bounds; if (p.x >= lo[0] - 64 && p.x <= hi[0] + 64 && p.y >= lo[1] - 64 && p.y <= hi[1] + 64) return m; } return null; }
const BUY_CHAT = ['!buy ak47', '!m4a1', '!vesthelm', '!deagle', '!awp', '!buy primammo', '!hegren', '!flash', '!defuser', '!rebuy', '!dust2', '!nuke', '!maps', '!hud', '!class', '!help'];
function act(c) {
  const p = c.pawn;
  if (!p || !p.alive) return;
  p.prev = p.buttons; p.buttons = 0;
  // the script keeps players on their map: check where they are
  const m = mapOf(p.pos);
  if (!m) { stats.outside++; if (OPTS.includes('dbg') && !c.reported) { c.reported = true; const r = globalThis.__cs16.recs.get(c.slot); console.log(`t=${time.toFixed(2)} off-map slot ${c.slot} team ${c.team} pos ${JSON.stringify(p.pos)} rec map=${r && r.map} alive=${r && r.alive} warmup=${warmup}`); } }
  if (Math.random() < 0.01) p.buttons |= 4096;                     // inspect = buy menu
  if (c.capture && Math.random() < 0.05) { stats.clicks++; hooks.OnCustomHudClicked({ player: c, buttonId: 'cs_mb' + Math.floor(Math.random() * 10) }); }
  if (Math.random() < 0.002) hooks.OnPlayerChat({ player: c, text: BUY_CHAT[Math.floor(Math.random() * BUY_CHAT.length)], team: 0 });
  if (frozen || !roundLive) return;
  // move around a little, sometimes fall
  p.pos.x += R(-3, 3); p.pos.y += R(-3, 3);
  if (Math.random() < 0.0005) { p.vel.z = -R(400, 900); after(0.05, () => { if (p.alive) { stats.falls++; hooks.OnPlayerLand({ player: p }); p.vel.z = 0; } }); }
  // shoot someone of the other team on the same map
  if (Math.random() < 0.004) {
    const foes = players.filter((o) => o.pawn && o.pawn.alive && o.team !== c.team && mapOf(o.pawn.pos) === m);
    if (!foes.length) return;
    const v = foes[Math.floor(Math.random() * foes.length)].pawn;
    const w = p.active || p.weapons[0];
    if (!w) return;
    const d = w.data.d;
    const hg = [1, 2, 2, 3, 4, 5, 6, 7][Math.floor(Math.random() * 8)];
    if (d[1] === 0) { hooks.OnKnifeAttack({ weapon: w, attackType: Math.random() < 0.5 ? 0 : 1 }); }
    if (d[1] === 9) { hooks.OnGrenadeThrow({ weapon: w, projectile: new Entity('', 'hegrenade_projectile') });
      const proj = new Entity('', 'hegrenade_projectile', { x: v.pos.x + R(-200, 200), y: v.pos.y, z: v.pos.z + 20 });
      const r = hooks.OnModifyPlayerDamage({ player: v, damage: 60, damageTypes: 64, damageFlags: 0, hitGroup: 0, inflictor: proj, attacker: p });
      if (!(r && r.abort)) hit(v, r ? r.damage : 60, p, null); return; }
    if (d[1] === 7) return;
    const dist = Math.hypot(v.pos.x - p.pos.x, v.pos.y - p.pos.y);
    const mult = [1, 4, 1, 1.25, 1, 1, 0.75, 0.75, 1][hg];
    let cs2 = d[3] * Math.pow(d[4], dist / 500) * mult * (Math.random() < 0.15 ? 0.5 : 1);
    const r = hooks.OnModifyPlayerDamage({ player: v, damage: cs2, damageTypes: 2, damageFlags: 0, hitGroup: hg, inflictor: p, attacker: p, weapon: w });
    stats.dmg.n++; stats.dmg.cs2 += cs2; stats.dmg.s16 += r && !r.abort ? r.damage : r && r.abort ? 0 : cs2;
    if (r && r.abort) return;
    hit(v, r ? r.damage : cs2, p, w);
  }
  // terrorists with the bomb plant it now and then; CTs defuse
  const c4 = p.weapons.find((w) => w.cls === 'weapon_c4');
  if (c4 && m && Math.random() < 0.003) {
    const site = m.sites[Math.floor(Math.random() * m.sites.length)];
    const pos = { x: (site.mins[0] + site.maxs[0]) / 2, y: (site.mins[1] + site.maxs[1]) / 2, z: site.mins[2] };
    p.weapons = p.weapons.filter((w) => w !== c4);
    const pc = new Entity('', 'planted_c4', pos);
    pc.site = site.letter; pc.explodeAt = time + 45; pc.map = m;
    pc.IsBombsiteA = () => site.letter === 'A'; pc.IsBombsiteB = () => site.letter === 'B'; pc.GetExplodeTime = () => pc.explodeAt;
    plantedC4s.push(pc); stats.plants++;
    hooks.OnBombPlant({ plantedC4: pc });
  }
  if (c.team === 3 && Math.random() < 0.0004) {
    const pc = plantedC4s.find((x) => x.valid && x.map === m);
    if (pc) { pc.valid = false; stats.defuses++; hooks.OnBombDefuse({ plantedC4: pc }); }
  }
}

// ---------------------------------------------------------------- run
const TICK = 1 / 64;
const WARMUP = 20;
let lastPrint = 0;
while (time < SECONDS) {
  time += TICK;
  for (let i = later.length - 1; i >= 0; i--) if (later[i].at <= time) { const f = later[i].fn; later.splice(i, 1); f(); }
  if (warmup && time > WARMUP) { warmup = false; startRound(); }
  if (roundLive && !frozen) roundTime = Math.max(0, roundTime - TICK);
  for (const pc of plantedC4s) if (pc.valid && time >= pc.explodeAt) {
    pc.valid = false; stats.explodes++;
    for (const c of players) if (c.pawn && c.pawn.alive) {
      const d = Math.hypot(c.pawn.pos.x - pc.pos.x, c.pawn.pos.y - pc.pos.y, c.pawn.pos.z - pc.pos.z);
      if (d < 1750) { const r = hooks.OnModifyPlayerDamage({ player: c.pawn, damage: 500, damageTypes: 64, damageFlags: 0, hitGroup: 0, inflictor: pc }); if (!(r && r.abort)) hit(c.pawn, r ? r.damage : 500, null, null); }
    }
    hooks.OnBombExplode({ plantedC4: pc });
  }
  if (warmup) for (const c of players) if (c.pawn && !c.pawn.alive && Math.random() < 0.02) c.spawn();
  for (const c of players) act(c);
  // churn: people leave and join, change team
  if (OPTS.includes('churn') && Math.random() < 0.01) {
    const c = players[Math.floor(Math.random() * N)];
    if (c.connected && Math.random() < 0.5) { c.connected = false; if (c.pawn) c.pawn.valid = false; hooks.OnPlayerDisconnect({ playerSlot: c.slot }); after(R(2, 20), () => { c.connected = true; c.team = Math.random() < 0.5 ? 2 : 3; c.money = 800; c.pawn = null; hooks.OnPlayerActivate({ player: c }); if (warmup) c.spawn(); }); }
    else if (c.connected) { c.team = c.team === 2 ? 3 : 2; if (c.pawn) { c.pawn.alive = false; hooks.OnPlayerTeamChanged({ player: c.pawn, oldTeam: 0 }); } if (warmup) c.spawn(); }
  }
  calls = 0;
  const t0 = process.hrtime.bigint();
  thinkFn && thinkFn();
  stats.tickMs.push(Number(process.hrtime.bigint() - t0) / 1e6);
  stats.callsPerTick.push(calls);
  if (time - lastPrint > 60) { lastPrint = time; stats.money.push(players.slice(0, 4).map((c) => c.money)); }
}
// guns players hold, and their spare ammo (a bought gun should have had its ammo bought too, for bots at least)
{ const prim = []; for (const c of players) if (c.pawn && c.pawn.alive) for (const w of c.pawn.weapons) if (w.data.d[2] === 0) prim.push((c.bot ? 'bot ' : '') + w.cls.replace('weapon_', '') + ':' + w.clip + '/' + w.reserve);
  console.log('primaries at the end:', prim.slice(0, 12).join(', ')); }
const avg = (a) => a.reduce((x, y) => x + y, 0) / Math.max(1, a.length);
const pct = (a, q) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length * q)]; };
console.log(`players ${N}, ${SECONDS} s: rounds ${stats.rounds} (end reasons ${JSON.stringify(stats.wins)}), kills ${stats.kills}, plants ${stats.plants}, defuses ${stats.defuses}, explosions ${stats.explodes}, falls ${stats.falls}`);
console.log(`script per tick: avg ${avg(stats.tickMs).toFixed(3)} ms, 99% ${pct(stats.tickMs, 0.99).toFixed(3)} ms, max ${Math.max(...stats.tickMs).toFixed(2)} ms; engine calls avg ${avg(stats.callsPerTick).toFixed(0)}, 99% ${pct(stats.callsPerTick, 0.99)}`);
console.log(`hud classes ${stats.hud}, hud texts ${stats.hudVars}, sounds ${stats.sounds}, teleports ${stats.teleports}, menu clicks ${stats.clicks}, models ${stats.models}; ticks with a player off every map ${stats.outside}`);
console.log(`damage: ${stats.dmg.n} hits, CS2 avg ${(stats.dmg.cs2 / Math.max(1, stats.dmg.n)).toFixed(1)} -> 1.6 avg ${(stats.dmg.s16 / Math.max(1, stats.dmg.n)).toFixed(1)}; money samples ${JSON.stringify(stats.money.slice(-3))}`);
const msgs = stats.msgs.filter((m) => !/script time/.test(m));
console.log('script log (last 12):\n  ' + msgs.slice(-12).join('\n  '));
if (stats.errors.length) { console.log('ERRORS:\n  ' + [...new Set(stats.errors)].join('\n  ')); process.exit(1); }
if (stats.rounds < 2) { console.log('ERROR: rounds did not end'); process.exit(1); }
console.log('ok');
