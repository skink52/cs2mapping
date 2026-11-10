// test/garage_upgrades.cjs: an upgrade bought in the garage reaches the mech in the fight (10 Nov 2026 playtest: "verify upgrades are applied").
// Loads the real 50_hud.js + 60_garage.js + 70_server.js with the real core (build/core_test.cjs) and drives them like a player:
//   1. stand-alone (offline listen server): click an upgrade track, CONFIRM, SORTIE -> the spawned mech's AP / damage / EN / boost drain / lock
//      time carry the level; the garage's "now" figures equal the mech's; a round restart (core reset, the adapter passes pilot null) keeps them;
//   2. server mode: the click sends `ifr_srv <slot> upg <id>`, the plugin's answer comes through the mailbox (origin encoding -> payload ->
//      parsePilot), the save + sortie round trip spawns the mech with the server's levels;
//   3. the catalogue maths: every upgradable part at every level, the garage's track value against the core's mech numbers.
// usage: node test/garage_upgrades.cjs   (needs build/core_test.cjs and out/addon/_gen/hud.json: tools/build_all.sh or build.mjs + hud.py)
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const { C, makeGame, careerGlobals } = require('./lib.cjs');
const root = path.join(__dirname, '..');
const HUD = JSON.parse(fs.readFileSync(path.join(root, 'out/addon/_gen/hud.json'), 'utf8'));
const PARTS = C.PARTS;
const byId = new Map(PARTS.parts.map((p) => [p.id, p]));
const caps = PARTS.caps;
let fails = 0, checks = 0;
function ok(cond, what) { checks++; if (!cond) { fails++; console.log('FAIL ' + what); } }
function near(a, b, what, tol) { ok(Math.abs(a - b) <= (tol === undefined ? 1e-6 : tol), what + ': ' + a + ' vs ' + b); }

// ---------------------------------------------------------------- the adapter in a sandbox
const stub = new Proxy(function () {}, { get: (t, k) => (k === Symbol.toPrimitive ? () => 0 : stub), apply: () => stub, construct: () => stub });
let now = 10;
const sent = [], logs = [], people = new Map();
const ent = { IsValid() { return true; }, ResetForPlayer() {}, SetInputCaptureEnabled() {}, IsInputCaptureEnabled() { return true; }, SetHasClassForPlayer() {}, SetDialogVariableStringForPlayer() {}, Reset() {} };
const mail = new Map();   // slot -> mailbox name
const base = {
  HUD, PARTS, console, Math, JSON, Map, Set, Number, String, Array, Object, Error,
  Instance: { FindEntityByName: () => ent, GetGameTime: () => now, Msg() {}, IsWarmupPeriod: () => false },
  ARENA: { name: 'Dunes', id: 'dunes', points: [], drops: { t: [], ct: [] } },
  CONFIG: { HUD: 'ifr_hud', HUD_BUDGET: 900, MAIL_PREFIX: 'ifr_mail_', PROTOCOL: 1, HELLO_EVERY: 60 },
  IFR_VERSION: 'test', guard: (w, f) => { try { return f(); } catch (e) { logs.push(w + ': ' + e.message); return null; } },
  gameTime: () => now, log: (m) => logs.push(m), dlog() {}, warnOnce() {}, sndTone() {}, revivePawn() {}, releaseProp() {}, takeProp: () => null,
  ifrCmd: (line) => sent.push(line), ifrFind: () => null, live: (e) => e || undefined, pad2: (n) => (n < 10 ? '0' : '') + n,
  person: (s) => people.get(s), people, slotOfEntity: (e) => (e && e.slot !== undefined ? e.slot : undefined), reply() {},
  v3: (x, y, z) => ({ x, y, z }), boothPos: () => ({ x: 0, y: 0, z: 0 }), fwdOf: () => ({ x: 1, y: 0, z: 0 }), normAngle: (a) => a,
  menuKeys: () => 0, MK: { up: 1, down: 2, left: 4, right: 8, ok: 16, back: 32, cycle: 64, fire: 128, fire2: 256, use: 512 },
  FRAMES: {}, WEAPON_MODELS: {}, PAINTS: {}, FX_MODELS: {}, NULL_MODEL: '', game: null, ...careerGlobals(),
};
vm.createContext(base);
const prog = fs.readFileSync(path.join(root, 'src/core/70_progress.js'), 'utf8');
const coreFns = ['IF_upgradeCost', 'IF_tierName'].map((n) => { const i = prog.indexOf('function ' + n + '('); if (i < 0) throw new Error('no ' + n + ' in 70_progress.js'); const one = prog.indexOf('\n', i), body = prog.indexOf('\n}\n', i); return prog.slice(i, prog.slice(i, one).trim().endsWith('}') ? one : body + 2); }).join('\n');
const src = coreFns + '\n' + ['50_hud.js', '60_garage.js', '70_server.js'].map((f) => fs.readFileSync(path.join(root, 'src/cs2', f), 'utf8')).join('\n');
const API = '\n;this.__api = { garageOpen, garageClick, garageSave, garageDraw, garageTrackValue, garageLevel, onPilotInput, srvDecodeInts, parsePilot, mailEnts, setServer: (v) => { serverMode = v; }, isServer: () => serverMode };';
for (let i = 0; i < 40; i++) {
  try { vm.runInContext(src + API, base); break; }
  catch (e) { const m = /(\w+) is not defined/.exec(e.message); if (!m) throw e; base[m[1]] = stub; vm.createContext(base); }
}
const A = base.__api;

// a core game running a round; spawn: tick until the slot's mech is alive
function newGame(seed) { const g = makeGame({ seed }); g.setMode('tb', 1); g.startRound(0); return g; }
function spawned(g, slot) {
  for (let t = 0; t < 20 * 64; t++) { g.tick(1 / 64, t / 64); g.events.length = 0; const m = g.mechs.get(slot); if (m && m.alive) return m; }
  return null;
}
function trackOf(pe, idx) { return pe.garage.tracks.find((t) => t.idx === idx); }
function clickTrack(pe, idx) {
  const k = pe.garage.tracks.findIndex((t) => t.idx === idx);
  assert(k >= 0, 'no track for slot index ' + idx);
  A.garageClick(pe, 'ifr_ur' + k);
  ok(pe.garage.confirm && pe.garage.confirm.op === 'upg', 'track ' + idx + ': a click asks to upgrade (confirm bar)');
  A.garageClick(pe, 'ifr_gcy');
}
const num = (t) => Number(String(t).replace(/[^0-9.]/g, ''));
const L = (id, lvl) => ({ ap: 0, id, lvl });

// ---------------------------------------------------------------- 1. stand-alone: click, confirm, sortie
{
  A.setServer(false);
  const g = newGame(11); base.game = g;
  const pe = { slot: 0, human: true, team: 2, pilot: null, status: 'dead' };
  people.set(0, pe);
  g.addPlayer(0, { team: 2, human: true, name: 'P0', pilot: null });
  A.garageOpen(pe, '');
  const draft = pe.garage.draft.slice();         // starter: White Glint, AR-22 (R), SG-Scatter (L), VM-6, DC-Chaff, GN / BT / FCS Standard
  const frame = byId.get(draft[0]), ra = byId.get(draft[1]), gen = byId.get(draft[5]), bst = byId.get(draft[6]), fcs = byId.get(draft[7]);
  const base0 = spawned(newGameWith(draft, null), 0);
  ok(trackOf(pe, 0).state === 'up', 'stand-alone tracks are upgradable (state up, was dis)');
  clickTrack(pe, 0); clickTrack(pe, 0);                 // frame AP x2
  clickTrack(pe, 1); clickTrack(pe, 1); clickTrack(pe, 1);   // R arm damage x3
  clickTrack(pe, 5);                                    // generator capacity
  clickTrack(pe, 6); clickTrack(pe, 6);                 // booster efficiency x2
  clickTrack(pe, 7);                                    // FCS lock time
  ok(A.garageLevel(pe, frame.id) === 2 && A.garageLevel(pe, ra.id) === 3 && A.garageLevel(pe, gen.id) === 1 && A.garageLevel(pe, bst.id) === 2 && A.garageLevel(pe, fcs.id) === 1,
    'levels after the clicks: frame 2, R arm 3, gen 1, booster 2, FCS 1');
  const shown = { ap: num(trackOf(pe, 0).a), dmg: num(trackOf(pe, 1).a), cap: num(trackOf(pe, 5).a), lock: num(trackOf(pe, 7).a) };
  A.garageSave(pe, true);                               // SORTIE: the loadout to the core, a spawn request
  ok(!pe.garage.open, 'SORTIE closed the garage');
  const m = spawned(g, 0);
  ok(!!m, 'the mech spawned after SORTIE');
  if (m) {
    const cls = PARTS.classes[frame.class], mods = frame.mods || {};
    const apWant = Math.round(cls.ap * (mods.ap || 1) * (1 + Math.min(caps.ap_pct, frame.upgrade.pct * 2) / 100));
    near(m.apMax, apWant, 'frame AP in the fight (MK II)');
    ok(m.apMax > base0.apMax, 'frame AP above stock (' + m.apMax + ' > ' + base0.apMax + ')');
    near(m.apMax, shown.ap, 'the garage track showed the same AP', 1);
    const dm = 1 + Math.min(caps.dps_pct, ra.upgrade.pct * 3) / 100;
    near(m.weapons[0].dmgMult, dm, 'R arm damage multiplier in the fight (MK III)');
    near(Math.round(ra.w.damage * m.weapons[0].dmgMult), shown.dmg, 'the garage track showed the same damage', 1);
    // upgrades belong to the part: the same part in the other arm carries them too (the first starter loadout is two rifles since 10 Nov 2026)
    near(m.weapons[1].dmgMult, m.weapons[1].id === m.weapons[0].id ? dm : 1, 'L arm: stock unless it is the same part as the upgraded R arm');
    near(m.enMax, Math.round(gen.g.capacity * (1 + gen.upgrade.pct / 100)), 'generator capacity in the fight');
    near(m.enMax, shown.cap, 'the garage track showed the same capacity', 1);
    near(m.drainMult, bst.b.drain_mult * (1 - Math.min(caps.mobility_pct, bst.upgrade.pct * 2) / 100), 'booster drain in the fight');
    near(m.lockHard, fcs.f.hard * (1 + Math.max(-30, fcs.upgrade.pct) / 100), 'FCS hard lock time in the fight');
    near(m.lockHard, shown.lock, 'the garage track showed the same lock time', 0.006);
  }
  // a round restart: CS2 re-creates the round, the core is reset, the adapter adds the player again with pe.pilot (null stand-alone)
  g.reset(); g.setMode('tb', 1); g.startRound(100);
  g.addPlayer(0, { team: 2, human: true, name: 'P0', pilot: null });
  g.requestSpawn(0);
  const m2 = spawned(g, 0);
  ok(!!m2 && m2.apMax === (m && m.apMax), 'a round restart keeps the stand-alone upgrades (AP ' + (m2 && m2.apMax) + ')');
  ok(!!m2 && m2.rank === 0, 'a stand-alone garage pilot has no rank (no rookie shield, no rating)');
  // the upgraded draft must still validate against the local pilot (every part owned)
  ok(g.setLoadout(0, '8,103,103,201,209,301,401,501,601') === 0, 'stand-alone: any loadout validates with the local pilot');
}
function newGameWith(draft, pilot) { const g = newGame(12); g.addPlayer(0, { team: 2, human: true, name: 'B', pilot }); g.setLoadout(0, draft.join(',')); g.requestSpawn(0); return g; }

// ---------------------------------------------------------------- 2. server mode: the mailbox round trip
{
  A.setServer(true); sent.length = 0;
  const g = newGame(21); base.game = g;
  const slot = 1, frameId = 4, L1 = [4, 101, 103, 201, 209, 301, 401, 501, 601];
  // the plugin's pilot record, origin encoding (MailboxMode "origin": [rank, active, flags, xp lo, xp hi, credits lo, credits hi, n, (id, lvl) x n, L1, L2, L3])
  const payload = (ups, credits) => A.srvDecodeInts(1, [12, 1, 0, 5000 % 8192, Math.floor(5000 / 8192), credits % 8192, Math.floor(credits / 8192), ups.length].concat(...ups).concat(L1, new Array(18).fill(0)));
  const deliver = (pl) => { A.mailEnts[slot] = { IsValid: () => true, GetEntityName: () => 'ifr_mail_01:' + pl, GetAbsOrigin: () => ({ x: 0, y: 0, z: 0 }) }; A.onPilotInput({ activator: { slot } }); };
  const pe = { slot, human: true, team: 3, pilot: null, status: 'dead' };
  people.set(slot, pe);
  g.addPlayer(slot, { team: 3, human: true, name: 'P1', pilot: null });
  deliver(payload([], 90000));
  ok(pe.pilot && pe.pilot.credits === 90000 && pe.pilot.rank === 12, 'server: the mailbox pilot arrived (rank 12, 90 000 CR)');
  A.garageOpen(pe, '');
  const k = pe.garage.tracks.findIndex((t) => t.idx === 0);
  A.garageClick(pe, 'ifr_ur' + k); A.garageClick(pe, 'ifr_gcy');
  ok(sent.some((l) => l === 'echo ifr_srv 1 upg ' + frameId), 'server: CONFIRM sends "ifr_srv 1 upg 4" (sent: ' + sent.join(' | ') + ')');
  ok(pe.garage.pending, 'server: the garage waits for the answer');
  deliver(payload([[frameId, 1]], 90000 - 1350));      // the plugin bought it: level 1, credits down
  ok(!pe.garage.pending && A.garageLevel(pe, frameId) === 1, 'server: the answer shows MK I in the garage');
  A.garageSave(pe, true);
  ok(sent.some((l) => l.startsWith('echo ifr_srv 1 save 1 4,101')), 'server: SORTIE saves the loadout first');
  deliver(payload([[frameId, 1]], 90000 - 1350));      // the save answer
  ok(!pe.garage.open, 'server: the save answer launches the sortie');
  const m = spawned(g, slot);
  const frame = byId.get(frameId), cls = PARTS.classes[frame.class];
  ok(!!m && m.apMax === Math.round(cls.ap * ((frame.mods || {}).ap || 1) * (1 + Math.min(caps.ap_pct, frame.upgrade.pct) / 100)), 'server: the mech fights with the MK I frame AP (' + (m && m.apMax) + ')');
  A.setServer(false);
}

// ---------------------------------------------------------------- 3. every upgradable part, every level: the garage's figure = the core's
{
  const g = newGame(31);
  const ids = (k) => PARTS.parts.filter((p) => p.kind === k && !p.pve && p.upgrade);
  const starter = [4, 101, 103, 201, 209, 301, 401, 501, 601];
  let n = 0;
  for (const [kind, pos] of [['frame', 0], ['arm', 1], ['shoulder', 3], ['generator', 5], ['booster', 6], ['fcs', 7]]) {
    for (const p of ids(kind)) {
      for (let lvl = 0; lvl <= caps.levels; lvl++) {
        const lo = starter.slice(); lo[pos] = p.id;
        if (kind === 'arm' && p.left_only) { lo[1] = 101; lo[2] = p.id; }
        const hp = kind === 'arm' && p.left_only ? 1 : kind === 'shoulder' ? 2 : 0;
        const pilot = { local: true, rank: 0, owned: new Set(byId.keys()), upgrades: { [p.id]: lvl }, loadouts: [null, null, null] };
        const slot = 2 + (n++ % 60);
        g.mechs.delete(slot); g.addPlayer(slot, { team: 2, human: true, name: 'X', pilot });
        const code = g.setLoadout(slot, lo.join(','));
        if (code) continue;                                         // over weight / EN with the starter kit: not this test's business
        const m = g.mechs.get(slot);
        g.spawnMech(m);                                             // the core's own spawn: IF_mechApplyLoadout with the pilot's levels
        g.events.length = 0;
        const shown = A.garageTrackValue(p, lvl), st = p.upgrade.stat, wp = m.weapons[hp];
        if (st === 'ap') near(m.apMax, num(shown), p.name + ' AP at ' + lvl, 1);
        else if (st === 'damage' && p.w && p.w.damage) near(Math.round(p.w.damage * wp.dmgMult), num(String(shown).split(' x')[0]), p.name + ' damage at ' + lvl, 1);
        else if (st === 'capacity') near(m.enMax, num(shown), p.name + ' capacity at ' + lvl, 1);
        else if (st === 'lock_time') near(m.lockHard, num(shown), p.name + ' lock time at ' + lvl, 0.006);
        else if (st === 'efficiency') near(m.drainMult, p.b.drain_mult * (1 - num(shown) / 100), p.name + ' efficiency at ' + lvl, 1e-3);
        else if (st === 'charges') near(wp.charges, num(shown), p.name + ' charges at ' + lvl);
        else if (st === 'block') near(Math.round(p.w.block * wp.statMult * 100), num(shown), p.name + ' block at ' + lvl, 1);
        else if (st === 'shield_hp' || st === 'heal') near(Math.round(p.w[st] * wp.statMult), num(shown), p.name + ' ' + st + ' at ' + lvl, 1);
      }
    }
  }
  ok(n > 100, 'catalogue sweep ran (' + n + ' part levels)');
}

if (logs.some((l) => /garage HUD section|: .*Error/.test(l))) console.log('log: ' + logs.filter((l) => /garage HUD section|Error/.test(l)).join(' | '));
console.log((fails ? 'FAIL: ' + fails + ' of ' : 'ok: ') + checks + ' checks (garage upgrades reach the mech, stand-alone and server mode)');
process.exit(fails ? 1 : 0);
