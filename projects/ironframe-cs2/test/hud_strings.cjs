// test/hud_strings.cjs: every string the script can put on the HUD must fit where it is shown. Nothing may be cut silently.
// usage: node test/hud_strings.cjs [-v]     (needs out/addon/_gen/hud.json from tools/hud.py; -v lists every measured message)
//
// What it measures (10 Nov 2026 evening playtest: "many in game messages get cut off"):
//  1. the garage, driven for real: every tab / row / focus column / money state / drafted part with the real parts.json, every buy and upgrade
//     question, every answer the garage gives (garageSay), in server mode and stand-alone;
//  2. the fight HUD with worst-case values: every weapon in every state (ammo, reload, heat, charge, lock states, multi-lock), vitals, overdrive,
//     buff badges, the pilot plate, the streak meter, the lock bracket, every mode's panel / chips / capture strip, the loadout card for every
//     frame and weapon; slates and pops with 24-letter names made of the widest letters;
//  3. EVERY message source in the script, found by scanning the source: each reply( / garageSay( / spectate( / garageOpen( call and each core
//     `say` event, plus the message tables (HINTS, STREAK_TEXT, CRATE_TEXT, TRAIT_LINES, HELP_LINES, DENY_TEXT, GARAGE_DENY). A call's text
//     expression becomes an upper bound: its string literals in order, each gap between them filled with the worst value for what stands there
//     (a 24-letter name, the longest part name, a big number...). A new call anywhere in src/ is picked up by the scan, so it cannot go unmeasured.
//     Line messages must fit ONE page of the message line (three rows); garage answers their two rows.
//  4. the message line by construction: random long messages are shown page by page and every character must appear.
// The driver records every cut it makes (ifrHudCuts): the test fails on any.
const fs = require('fs'), path = require('path'), vm = require('vm');
const root = path.join(__dirname, '..');
const VERBOSE = process.argv.includes('-v');
const HUD = JSON.parse(fs.readFileSync(path.join(root, 'out/addon/_gen/hud.json'), 'utf8'));
const PARTS = JSON.parse(fs.readFileSync(path.join(root, 'data/parts.json'), 'utf8'));
const stub = new Proxy(function () {}, { get: (t, k) => (k === Symbol.toPrimitive ? () => 0 : stub), apply: () => stub, construct: () => stub });
const fmt = (n) => { let t = String(Math.abs(Math.round(n))); for (let i = t.length - 3; i > 0; i -= 3) t = t.slice(0, i) + ' ' + t.slice(i); return (n < 0 ? '-' : '') + t; };
let now = 100;
const byId = new Map(PARTS.parts.map((p) => [p.id, p]));
const read = (f) => fs.readFileSync(path.join(root, f), 'utf8');
// the core's part card rows (src/core/70_progress.js describe), level 0
function describe(id) {
  const P = PARTS, p = byId.get(+id), rows = [], add = (k, v) => rows.push([k, String(v)]);
  if (!p) return null;
  if (p.kind === 'frame') { const c = P.classes[p.class] || {}, m = p.mods || {}; add('Class', p.class); add('Legs', p.legs); add('AP', Math.round(c.ap * (m.ap || 1))); add('Walk', Math.round(c.walk * (m.walk || 1))); add('Boost', Math.round(c.boost * (m.boost || 1))); add('Quick boost', Math.round(c.qb * (m.qb || 1))); add('Load', c.load); add('Stagger cap', Math.round(c.stagger * (m.stagger || 1))); }
  else if (p.w) {
    const w = p.w; add('Type', w.type + (w.ability ? ' (' + w.ability + ')' : ''));
    if (w.damage) add('Damage', Math.round(w.damage) + (w.pellets ? ' x' + w.pellets : '') + (w.count ? ' x' + w.count : ''));
    if (w.rate) add('Rate', w.rate + '/s'); if (w.cd) add('Cooldown', w.cd + ' s');
    const fo = PARTS.falloff && PARTS.falloff[p.key]; if (w.range) add('Range', fo ? Math.round(w.range * fo.ideal) + ' / ' + w.range : w.range); if (w.impact) add('Impact', w.impact); if (w.splash) add('Splash', w.splash);
    if (w.mag) add('Magazine', w.mag); if (w.ammo) add('Ammo', w.ammo); if (w.en_shot) add('EN per shot', w.en_shot);
    if (w.lock) add('Lock', w.lock); if (w.block) add('Blocks', Math.round(w.block * 100) + ' % in front');
    if (w.shield_hp) add('Bubble HP', w.shield_hp); if (w.heal) add('Heal', w.heal); if (w.charges) add('Charges', w.charges);
    add('DPS', 999);
  } else if (p.g) { add('Capacity', p.g.capacity); add('Regen', p.g.regen + '/s'); add('Output', p.g.output); add('Stall', p.g.stall + ' s'); }
  else if (p.b) { add('Thrust', 'x' + p.b.thrust); add('Quick boost', 'x' + p.b.qb_mult); add('QB cost', 'x' + p.b.qb_cost_mult); add('Hover', 'x' + p.b.hover); add('Drain', 'x' + p.b.drain_mult); }
  else if (p.f) { add('Cone', p.f.cone + ' deg'); add('Range', p.f.range); add('Soft lock', p.f.soft + ' s'); add('Hard lock', p.f.hard + ' s'); add('Gimbal', p.f.gimbal + ' deg'); }
  add('Weight', p.weight); if (p.kind !== 'paint') add('EN load', p.en);
  return { rows };
}
// a table literal from the source: `const NAME = {...};` / `[...]` evaluated on its own (strings only)
function table(file, name) {
  const s = read(file), i = s.indexOf('const ' + name + ' = ');
  if (i < 0) throw new Error('no ' + name + ' in ' + file);
  let j = s.indexOf('=', i) + 1; while (s[j] === ' ') j++;
  const open = s[j], close = open === '{' ? '}' : ']'; let depth = 0, k = j, q = '';
  for (; k < s.length; k++) {
    const c = s[k];
    if (q) { if (c === '\\') k++; else if (c === q) q = ''; continue; }
    if (c === "'" || c === '"' || c === '`') { q = c; continue; }
    if (c === open) depth++; else if (c === close && --depth === 0) break;
  }
  return vm.runInNewContext('(' + s.slice(j, k + 1) + ')');
}
const DENY_TEXT = table('src/cs2/70_server.js', 'DENY_TEXT');
const ent = { IsValid() { return true; }, ResetForPlayer() {}, SetInputCaptureEnabled() {}, SetHasClassForPlayer() {}, SetDialogVariableStringForPlayer() {} };
const base = { HUD, PARTS, console, Entities: { FindByName: () => (ent ? [ent] : []), FireInput() {} }, Console: { Log() {}, ServerCommand() {} }, GameRules: { IsWarmupPeriod: () => false }, Instance: { FindEntityByName: () => ent, GetGameTime: () => now, Msg() {} }, ARENA: { name: 'Dunes', id: 'dunes', points: [], drops: { t: [], ct: [] } },
  CONFIG: { HUD: 'ifr_hud', HUD_BUDGET: 900 }, serverMode: true, gfmt: fmt, guard: (w, f) => { try { return f(); } catch (e) { return null; } }, game: { garage: { describe: (id) => describe(id) } },
  gameTime: () => now, DENY_TEXT };
vm.createContext(base);
// the core helpers the garage calls (upgrade cost, tier name), taken from the real 70_progress.js
const prog = read('src/core/70_progress.js');
const coreFns = ['IF_upgradeCost', 'IF_tierName'].map((n) => { const i = prog.indexOf('function ' + n + '('); if (i < 0) throw new Error('no ' + n + ' in 70_progress.js'); const one = prog.indexOf('\n', i), body = prog.indexOf('\n}\n', i); return prog.slice(i, prog.slice(i, one).trim().endsWith('}') ? one : body + 2); }).join('\n');
const src = coreFns + '\n' + read('src/cs2/50_hud.js') + '\n' + read('src/cs2/60_garage.js') + '\n' + read('src/cs2/70_server.js');
// the pilot customisation (S2): the real codec from the core, the people the adapter looks up, a name for nameOf
const people = new Map(); let nameNow = 'W'.repeat(24);
Object.assign(base, require('./lib.cjs').careerGlobals(), { people, person: (s) => people.get(s), nameOf: () => nameNow, ifrCmd() {}, sndTone() {}, reply() {}, log() {}, warnOnce() {}, TEAM_T: 2, TEAM_CT: 3 }); vm.createContext(base);
for (let i = 0; i < 40; i++) {
  try { vm.runInContext(src + '\n;this.__api = { ifrHudSlot, garageOpen, garageRows, garageDraw, garageSay, garagePick, garageUpgradeAsk, garageConfirm, garageClick, ifrHudInit, ifrHudCutList, ifrHudVar, ifrHudMode, ifrHudSlate, ifrHudWeapons, ifrHudLock, ifrHudLine, ifrHudVitals, ifrHudFeed, ifrHudLoadout, ifrHudTick, ifrHudWrap, ifrHudWrapAll, ifrHudFits, ifrHudWidth, ifrHudObjective, ifrHudOff, GARAGE_TABS, PART_BY_ID, garageStr, GARAGE_DENY, GARAGE_SLOTS, IFR_HUD_TXT, IFR_HUD_ROLE, IFR_HUD_TRAIT, IFR_HUD_MODE_NAMES, IFR_HUD_STREAKS, ifrHudPilot, ifrHudBoard, setBoard: (b) => { srvBoard = b; }, setServerMode: (v) => { serverMode = v; } };', base); break; }
  catch (e) { const m = /(\w+) is not defined/.exec(e.message); if (!m) throw e; base[m[1]] = stub; vm.createContext(base); }
}
const A = base.__api;
A.ifrHudInit();
const fails = new Map();
let measured = 0;
const note = (ctx) => { measured++; for (const c of A.ifrHudCutList()) { const k = c.split(':')[0]; if (!fails.has(k)) fails.set(k, ctx + ' | ' + c); } };
const fail = (key, msg) => { if (!fails.has(key)) fails.set(key, msg); };
const parts = PARTS.parts, ids = parts.map((p) => p.id);
const weapons = parts.filter((p) => p.kind === 'arm' || p.kind === 'shoulder');
// worst-case values
const NAME_W = 'W'.repeat(24), NAME_M = 'M'.repeat(24), NAME_MIX = 'xX_Dr4g0n-Sl4y3r_420_Xx!!', longName = 'WORLDMASTERS';
const longPart = weapons.map((p) => p.name).sort((a, b) => b.length - a.length)[0];
const longAny = parts.map((p) => p.name).sort((a, b) => b.length - a.length)[0];
const LINE = HUD.line.slots;

// ================================================================ 1. the garage
function pe(rank, credits, lvl, owned) {
  const up = {}; for (const p of parts) up[p.id] = lvl;
  return { slot: 1, human: true, status: 'dead', pilot: { rank, credits, active: 1, upgrades: up, loadouts: [null, null, null], owned: owned || new Set(ids) }, garage: null };
}
const GMSGS = ['', 'Need 9 999 999 CR', 'Buying ' + longAny + '...', 'Upgrading ' + longAny + '...', 'No upgrade track', 'Loadout 3 selected', 'Rank 99 needed', 'Already at MK V'];
for (const [rank, credits, lvl] of [[12, 1250000, 0], [1, 100, 0], [12, 60000, 5], [6, 3000, 3]]) {
  const p = pe(rank, credits, lvl);
  try { A.garageOpen(p, 'test'); } catch (e) { /* the hangar preview needs the engine */ }
  const g = p.garage; if (g) g.slot = 1;
  if (!g) throw new Error('garage did not open');
  for (let tab = 0; tab < A.GARAGE_TABS.length; tab++) {
    g.tab = tab; g.row = 0; g.scroll = 0; g.col = 1; g.confirm = null;
    try { A.garageRows(p); } catch (e) { continue; }
    for (let r = 0; r < Math.max(1, g.rows.length); r++) {
      g.row = r; if (g.row >= g.scroll + 10) g.scroll = g.row - 9;
      for (const col of [0, 1, 2]) {
        g.col = col; g.urow = r % 8; g.dirty = true;
        for (const msg of GMSGS) { g.msg = msg; g.msgAt = now; try { A.garageDraw(p); } catch (e) { /* preview props */ } note('r' + rank + ' tab ' + tab + ' row ' + r + ' col ' + col + ' ' + (g.rows[r] ? g.rows[r].name : '')); }
      }
    }
    g.confirm = null;
  }
}
// every frame, weapon and utility part as the equipped / drafted one (frame plate, top bar, equipped weapons, upgrade tracks)
{
  const p = pe(12, 1250000, 5); try { A.garageOpen(p, 'test'); } catch (e) { }
  const g = p.garage; g.slot = 1; g.col = 0; g.confirm = null;
  const kinds = { 0: 'frame', 1: 'arm', 2: 'arm', 3: 'shoulder', 4: 'shoulder', 5: 'generator', 6: 'booster', 7: 'fcs' };
  for (const [idx, kind] of Object.entries(kinds)) {
    for (const part of parts.filter((q) => q.kind === kind && !q.pve)) {
      g.draft[idx] = part.id; g.tab = 0; try { A.garageRows(p); } catch (e) { }
      for (const msg of ['', 'Upgrading ' + part.name + '...']) { g.msg = msg; g.msgAt = now; try { A.garageDraw(p); } catch (e) { } note('draft ' + kind + ' ' + part.name); }
    }
  }
}
// the real questions and answers: buying every part (a poor, low-rank pilot who owns nothing), upgrading every part at every level, server and stand-alone
let questions = 0;
for (const server of [true, false]) {
  A.setServerMode(server);
  for (const lvl of [0, 1, 2, 3, 4, 5]) {
    const p = pe(99, 99999999, lvl, lvl === 0 ? new Set() : undefined); try { A.garageOpen(p, ''); } catch (e) { }
    const g = p.garage; g.slot = 1;
    for (let tab = 0; tab < A.GARAGE_TABS.length; tab++) {
      g.tab = tab; g.row = 0; g.scroll = 0; g.col = 1; g.confirm = null; g.pending = false;
      try { A.garageRows(p); } catch (e) { continue; }
      for (let r = 0; r < g.rows.length; r++) {
        g.row = r; g.confirm = null; g.pending = false; g.msg = '';
        try { A.garagePick(p); } catch (e) { }
        if (g.confirm) questions++;
        g.msgAt = now; try { A.garageDraw(p); } catch (e) { } note((server ? 'server' : 'offline') + ' pick ' + (g.rows[r] ? g.rows[r].name : r) + ' lvl ' + lvl + ' -> ' + (g.confirm ? g.confirm.q : g.msg));
        g.confirm = null; g.pending = false; g.msg = '';
        const part = g.rows[r] && g.rows[r].part;
        if (part) {
          try { A.garageUpgradeAsk(p, part); } catch (e) { }
          if (g.confirm) questions++;
          g.msgAt = now; try { A.garageDraw(p); } catch (e) { } note((server ? 'server' : 'offline') + ' upgrade ' + part.name + ' lvl ' + lvl + ' -> ' + (g.confirm ? g.confirm.q : g.msg));
          if (g.confirm && !server) { try { A.garageConfirm(p, true); } catch (e) { } g.msgAt = now; try { A.garageDraw(p); } catch (e) { } note('offline upgraded ' + part.name + ' -> ' + g.msg); }
        }
        g.confirm = null; g.pending = false;
        try { A.garageRows(p); } catch (e) { }
      }
    }
  }
}
A.setServerMode(true);
if (questions < 100) fail('questions', 'the garage asked only ' + questions + ' buy / upgrade questions: the drive is broken');
// a pilot with nothing: the locked / poor answers
{
  const p = pe(1, 0, 0, new Set()); try { A.garageOpen(p, ''); } catch (e) { }
  const g = p.garage; g.slot = 1;
  for (let tab = 0; tab < A.GARAGE_TABS.length; tab++) {
    g.tab = tab; g.row = 0; g.scroll = 0; g.col = 1; try { A.garageRows(p); } catch (e) { continue; }
    for (let r = 0; r < g.rows.length; r++) { g.row = r; g.confirm = null; g.msg = ''; try { A.garagePick(p); } catch (e) { } g.msgAt = now; try { A.garageDraw(p); } catch (e) { } note('poor pick ' + (g.rows[r] ? g.rows[r].name : r) + ' -> ' + g.msg); }
  }
}

// the SLOTS and PILOT tabs, the identity strip, the podium titles and the top pilots with a full profile (S2 / S3): every honour worn, every
// accent, the widest callsign and loadout names, contracts with the largest numbers, a leaderboard of the widest names; server and stand-alone;
// and the same pilot with nothing set and with the honours earned so far (the "Next: ..." texts)
{
  const K = base.IF_Career, D = K.data, wide = (n) => 'W'.repeat(n);
  const tabs = ['load', 'plt'].map((k) => A.GARAGE_TABS.findIndex((t) => t.key === k));
  let rowsSeen = 0, picks = 0;
  for (const server of [true, false]) {
    A.setServerMode(server);
    const board = { total: 9999999, rows: [1, 2, 3, 4, 5].map((k) => ({ name: k % 2 ? wide(12) : 'ZZ-TOP 99 ZZ', rank: 50, xp: k === 1 ? 9999999 : 999999 })) };
    A.setBoard(server ? board : null);
    for (const h of [null].concat(D.honours)) for (const none of [false, true]) {
      const p = pe(50, 99999999, 0); p.pilot.xp = 9999999; p.pilot.loadouts = ['4,101,103,201,209,301,401,501,601', null, null, null, null, '8,105,105,204,203,303,403,502,601'];
      const pr = K.blank();
      for (const x of D.honours) if (none ? (h && x.id < h.id) : true) pr.earned.add(x.id);
      if (!none) Object.assign(pr, { callsign: wide(12), names: [wide(10), 'MMMMMMMMMM', '', 'A', '', wide(10)], fav: 24, place: 9999999, prefs: 12,
        accents: [1, 2, 3, 4, 5, 6].map((k) => D.accents[(k + (h ? h.id : 0)) % D.accents.length].id),
        daily: [0, 1, 2].map((i) => ({ code: ((h ? h.id : 0) + i) % D.contract_stats.length + 1, progress: i === 1 ? 8191 : 8190, goal: 8191, reward: 8191 })) });
      if (h && !none) pr[h.kind] = h.id;
      p.profile = pr; p.localProfile = pr; people.set(p.slot, p);
      try { A.garageOpen(p, ''); } catch (e) { /* the hangar preview needs the engine */ }
      const g = p.garage;
      for (const slot of [1, 6]) for (const tab of tabs) {
        g.slot = slot; g.tab = tab; g.row = 0; g.scroll = 0; g.col = 1; g.confirm = null; g.pending = false;
        A.garageRows(p);
        for (let r = 0; r < g.rows.length; r++) {
          rowsSeen++; g.row = r; g.msg = ''; g.msgAt = now; g.pending = false;
          A.garageDraw(p); note((server ? 'server' : 'offline') + ' ' + A.GARAGE_TABS[tab].key + ' row ' + g.rows[r].name + ' (' + (h ? h.name : 'no honour') + (none ? ', bare' : '') + ')');
          const was = JSON.stringify([pr.title, pr.badge, pr.prefs, pr.fav, pr.accents]);
          A.garagePick(p); g.msgAt = now; g.pending = false; A.garageDraw(p); note('pick ' + g.rows[Math.min(r, g.rows.length - 1)].name + ' -> ' + g.msg);
          if (JSON.stringify([pr.title, pr.badge, pr.prefs, pr.fav, pr.accents]) !== was) picks++;
        }
      }
      // the strip in the fight, the podium (three pilots with the widest names, this one's title beside the kills), the top pilots
      nameNow = NAME_W; A.ifrHudPilot(p.slot); note('identity strip ' + (h ? h.name : 'no honour'));
      nameNow = 'A'; A.ifrHudPilot(p.slot); note('identity strip, short name ' + (h ? h.name : 'no honour'));
      nameNow = NAME_W;
      A.ifrHudSlate(p.slot, 'podium', { winner: 2, team: 2, podium: [0, 1, 2].map((i) => ({ slot: p.slot, name: i ? NAME_M : pr.callsign || NAME_W, kills: 999, team: 2 })),
        me: { kills: 999, assists: 999, captures: 99, pveKills: 999, bossKills: 99, damage: 9999999, streakBest: 99, xp: 999999, credits: 999999 } });
      note('podium with titles ' + (h ? h.name : 'no honour'));
      A.ifrHudBoard(p.slot, board, { place: none ? 0 : 9999999, rank: 50, xp: 9999999 }); note('top pilots');
      people.delete(p.slot);
    }
  }
  A.setServerMode(true); A.setBoard(null);
  if (rowsSeen < 2000) fail('pilot rows', 'the SLOTS / PILOT tabs drew only ' + rowsSeen + ' rows: the drive is broken');
  if (picks < 200) fail('pilot picks', 'only ' + picks + ' setting picks changed the profile: the drive is broken');
}

// ================================================================ 2. the fight HUD with worst-case values
const S = 2;
// every mode's panel, objective chips and capture strip with the longest realistic states (errors fail the test: these must not throw)
{
  const P3 = (o) => ['A', 'B', 'C'].map((id, i) => Object.assign({ id, pos: { x: i * 3000, y: 0, z: 0 }, radius: 700, owner: 0, value: 0, progress: 0, capTeam: 0, contested: false, nT: 0, nCT: 0 }, o[i] || {}));
  const pointSets = [
    P3([{ owner: 2, progress: 1, capTeam: 2, value: -1 }, { owner: 0, progress: 0.64, capTeam: 3, value: 0.64, nCT: 2 }, { owner: 3, progress: 1, capTeam: 3, value: 1, contested: true, nT: 1, nCT: 1 }]),
    P3([{ owner: 2, progress: 0.36, capTeam: 2, value: -0.36, nCT: 3 }, { owner: 0, progress: 0, capTeam: 0 }, { owner: 3, progress: 1, capTeam: 3, value: 1 }]),
  ];
  const mb = { phase: 'running', timeLeft: 3599, scores: { 2: 9999, 3: 9999 }, tickets: { 2: 9999, 3: 9999 }, killTarget: 150, wave: 12, waves: 12, khTarget: 150, ctfCaptures: 3 };
  const runs = [];
  for (const m of ['tb', 'sk']) runs.push(Object.assign({}, mb, { mode: m, points: [] }));
  for (const pts of pointSets) runs.push(Object.assign({}, mb, { mode: 'cq', points: pts }));
  for (const pts of pointSets) for (const p of pts) {
    runs.push(Object.assign({}, mb, { mode: 'kh', points: [Object.assign({}, p, { scoring: p.owner && !p.contested })], allPoints: pts, hillLeft: 119 }));
    runs.push(Object.assign({}, mb, { mode: 'so', points: [p], boss: { ap: 5, apMax: 10 } }));
  }
  const flag = (team, state, extra) => Object.assign({ team, state, home: { x: team === 2 ? 0 : 9000, y: 0, z: 0 }, pos: { x: 4000, y: 0, z: 0 }, carrier: -1, returnT: 0, returnMax: 20, carrierTeam: team === 2 ? 3 : 2 }, extra || {});
  for (const [a, b] of [['home', 'home'], ['carried', 'dropped'], ['dropped', 'carried'], ['carried', 'carried']]) for (const carrier of [S, 7]) {
    runs.push(Object.assign({}, mb, { mode: 'ctf', points: [], flags: { 2: flag(2, a, { carrier, returnT: 19.6 }), 3: flag(3, b, { carrier: carrier === S ? 9 : S, returnT: 12.2 }) } }));
  }
  for (const team of [2, 3]) for (const r of runs) {
    for (const pos of [null, { x: 0, y: 0, z: 0 }, { x: 3000, y: 100, z: 0 }]) {
      A.ifrHudSlot(S).pos = pos;
      A.ifrHudMode(S, r, team); note('mode ' + r.mode + ' team ' + team);
    }
  }
  // the intro of every mode (objective in two lines), with the longest arena name the maps have
  for (const m of ['tb', 'cq', 'sk', 'so', 'kh', 'ctf']) for (const arena of ['Dunes of Karakum', 'Sprawl 4', 'Orbital Station 4']) { A.ifrHudSlate(S, 'intro', { title: 'IRONFRAME', arena, mode: m, hint: 'ANY MENU KEY: GARAGE' }); note('intro ' + m); }
}
// slates and pops with the widest names CS2 can hand us (nameOf cuts at 24 characters): shortened with '..', never clipped
for (const nm of [NAME_W, NAME_M, NAME_MIX, longName, 'the arena']) {
  for (const wk of weapons.map((w) => w.key).concat(['overdrive', 'artillery', ''])) { A.ifrHudSlate(S, 'death', { killer: nm, weapon: wk, frame: 'Noblesse Oblige', respawn: 10 }); note('death ' + nm + ' ' + wk); }
  for (const fr of parts.filter((p) => p.kind === 'frame')) { A.ifrHudSlate(S, 'death', { killer: nm, weapon: 'vm6', frame: fr.name, respawn: 10 }); note('death frame ' + fr.name); }
  A.ifrHudSlate(S, 'podium', { winner: 2, podium: [1, 2, 3].map((i) => ({ slot: i, name: nm, kills: 999 })), me: { xp: 999999, credits: 999999, kills: 999, assists: 999, captures: 99, pveKills: 999, bossKills: 99, damage: 99999999, streakBest: 99, name: nm }, team: 2, sub: 'KING OF THE HILL  DUNES OF KARAKUM', foot: 'NEXT ROUND SOON' }); note('podium ' + nm);
  A.ifrHudSlate(S, 'spectator', { name: nm, slot: 3 }); note('spectator ' + nm);
  A.ifrHudFeed(S, { kill: nm, xp: 99999, streak: 12, bounty: true, rookie: true }); note('kill pop ' + nm);
}
A.ifrHudVar(S, 'respawn', 'SPACE SORTIE   CTRL GARAGE'); note('respawn');
A.ifrHudVar(S, 'respawn', 'RESPAWN IN 99'); note('respawn');
// every weapon in every state the driver can show (the big figure and the state row)
function wst(part, over) {
  const w = part.w || {};
  return Object.assign({ part, w: part.w, ammo: w.ammo !== undefined ? w.ammo - (w.mag || 0) : 0, mag: w.mag || 0, magSize: w.mag || 0, cd: 0, heat: 0, overheat: false, charge: 0, charging: false, reloading: false, reloadT: 0,
    charges: w.charges || 0, firing: false, raised: false, lastShot: -99, salvo: 0, mlock: [], mlDone: 0, mlHold: 0 }, over || {});
}
const me = { slot: S, team: 2, name: 'ME', pos: { x: 0, y: 0, z: 0 }, torsoYaw: 0, ap: 99990, apMax: 99990, en: 99980, enMax: 99990, enStalled: 0, stagger: 0, staggerMax: 1400, staggered: 0, protect: 0, dropT: 0, landLag: 0,
  boosting: false, assault: false, qbCd: 0, lockSoft: 0.3, lockHard: 0.9, fcs: parts.find((p) => p.kind === 'fcs'), lock: { target: -1, stage: 0, t: 0 }, threats: [], weapons: [null, null, null, null],
  overdrive: 0, odPhase: 0, odT: 0, sum: { kills: 999, deaths: 999, assists: 999 }, fkills: 0, streak: 0, input: { camPos: { x: -500, y: 0, z: 200 }, camDir: { x: 1, y: 0, z: 0 }, fire: [false, false, false, false] } };
const foe = { slot: 9, team: 3, name: NAME_W, pos: { x: 3000, y: 0, z: 0 }, ap: 5000, apMax: 9000, height: 288, alive: true };
base.game.mechs = new Map([[9, foe], [10, Object.assign({}, foe, { slot: 10, pos: { x: 2500, y: 900, z: 0 } })], [11, Object.assign({}, foe, { slot: 11, pos: { x: 2500, y: -900, z: 300 } })], [12, Object.assign({}, foe, { slot: 12, pos: { x: 4000, y: 0, z: 600 } })]]);
const locks = [{ target: -1, stage: 0, t: 0 }, { target: 9, stage: 0, t: 0.29 }, { target: 9, stage: 1, t: 0.31 }, { target: 9, stage: 1, t: 1.19 }, { target: 9, stage: 2, t: 9 }];
for (const part of weapons) {
  const w = part.w || {}, states = [{}, { cd: 12.4 }, { cd: 0.4 }, { firing: true }];
  if (w.mag) states.push({ reloading: true, reloadT: 12.4, mag: 0 }, { mag: 0, ammo: 0 }, { ammo: 99999 });
  if (w.ammo !== undefined) states.push({ ammo: 0, mag: 0 });
  if (w.heat_time) states.push({ heat: 0.5 }, { heat: 0.85 }, { heat: 1, overheat: true });
  if (w.charge) states.push({ charging: true, charge: 0.3 }, { charging: true, charge: 1 });
  if (w.charges) states.push({ charges: 0 });
  if (w.type === 'shield') states.push({ raised: true });
  if (w.type === 'missile') states.push({ salvo: 3 }, { mslWait: true });
  if (w.multilock) states.push({ mlHold: 0.2 }, { mlHold: 1, mlock: [9, 10, 11, 12].map((sl) => ({ slot: sl, p: 0.5, done: false })) }, { mlHold: 2, mlDone: 4, mlock: [9, 10, 11, 12].map((sl) => ({ slot: sl, p: 1, done: true })) });
  for (const st of states) for (const lk of (w.type === 'missile' ? locks : [locks[0]])) for (const far of (w.type === 'missile' ? [false, true] : [false])) {
    me.lock = lk; foe.pos.x = far ? 99990 : 3000;
    for (let i = 0; i < 4; i++) me.weapons[i] = wst(part, st);
    try { A.ifrHudVitals(S, me); A.ifrHudLock(S, me.lock, me.threats, lk.target >= 0 ? foe : null, me); A.ifrHudWeapons(S, me.weapons); } catch (e) { fail('weapon ' + part.key, 'weapon ' + part.name + ' threw: ' + e.message); }
    note('weapon ' + part.name + ' ' + JSON.stringify(st) + ' lock ' + lk.stage + (far ? ' far' : ''));
  }
}
foe.pos.x = 3000;
// vitals, overdrive, buff badges, the pilot plate, the streak meter
for (const od of [0, 0.5, 0.999, 1]) for (const ph of [0, 1]) for (const fk of [0, 1, 2, 3, 4, 5, 7, 8, 12, 99]) for (const ace of [0, 99]) {
  Object.assign(me, { overdrive: od, odPhase: ph, odT: 1.2, fkills: fk, aceT: ace, boostDmgT: 99, shieldT: 99, radarT: 99, artyReady: true });     // timers are 10-20 s in the core
  try { A.ifrHudVitals(S, me); } catch (e) { fail('vitals', 'vitals threw: ' + e.message); } note('vitals od ' + od + ' phase ' + ph + ' streak ' + fk);
}
// the loadout card: every player frame (its trait rows), every weapon in every slot
for (const fr of parts.filter((p) => p.kind === 'frame')) { me.frame = fr; for (let i = 0; i < 4; i++) me.weapons[i] = wst(weapons[(fr.id + i) % weapons.length]); try { A.ifrHudLoadout(S, me, 5); } catch (e) { fail('loadout', 'loadout card threw: ' + e.message); } note('loadout frame ' + fr.name); }
for (const part of weapons) { for (let i = 0; i < 4; i++) me.weapons[i] = wst(part); A.ifrHudLoadout(S, me, 5); note('loadout weapon ' + part.name); }
me.weapons = [null, null, null, null]; me.frame = {}; A.ifrHudLoadout(S, me, 5); note('loadout empty');
for (const k of Object.keys(A.IFR_HUD_TRAIT)) if (!parts.some((p) => p.kind === 'frame' && (p.trait || p.key) === k)) fail('trait ' + k, 'IFR_HUD_TRAIT has ' + k + ' but no frame has that trait');
for (const p of parts.filter((q) => q.kind === 'frame' && !q.pve && q.trait_name)) if (!A.IFR_HUD_TRAIT[p.trait || p.key]) fail('trait ' + p.key, 'frame ' + p.name + ' (trait ' + (p.trait || p.key) + ') has no row in IFR_HUD_TRAIT (50_hud.js): the loadout card cannot say how to use it');
for (const p of weapons) if (!A.IFR_HUD_ROLE[p.key]) fail('role ' + p.key, 'weapon ' + p.name + ' has no role in IFR_HUD_ROLE (50_hud.js)');

// ================================================================ 3. every message source in the script
// the line: one page = the line's rows. A message that needs more is shown as two pages in game, but every source must fit one.
const lineRows = (text) => A.ifrHudWrapAll(LINE[0], text);
const lineMsgs = [], sayMsgs = [];
function lineCheck(where, text) {
  if (!String(text).trim()) return;
  const rows = lineRows(text); measured++;
  lineMsgs.push({ where, text, rows: rows.length });
  if (rows.length > LINE.length) fail('line ' + where, 'message line: ' + where + ' needs ' + rows.length + ' rows (a page has ' + LINE.length + '): ' + text);
  A.ifrHudLine(S, text, 4, false, 2); note('line ' + where); A.ifrHudLine(S, '');
}
function sayCheck(where, text) {
  if (!String(text).trim()) return;
  measured++; sayMsgs.push({ where, text });
  const rows = A.ifrHudWrap(['ghint', 'ghint2'], text);
  if (A.ifrHudCutList().some((c) => c.startsWith('ghint:'))) fail('ghint ' + where, 'garage answer: ' + where + ' does not fit its two rows: ' + text + ' -> ' + rows.join(' / '));
  A.ifrHudWrap(['ghint', 'ghint2'], 'OK');
}
// ---- the source scan
const SRC_FILES = fs.readdirSync(path.join(root, 'src/cs2')).filter((f) => f.endsWith('.js')).map((f) => 'src/cs2/' + f).concat(fs.readdirSync(path.join(root, 'src/core')).filter((f) => f.endsWith('.js')).map((f) => 'src/core/' + f));
/** call sites of fn( in a source text: [{line, args: [expr text]}] (the definition `function fn(` is skipped) */
function calls(text, fn) {
  const out = [], re = new RegExp('(^|[^\\w.$])' + fn + '\\(', 'g'); let m;
  while ((m = re.exec(text))) {
    const start = m.index + m[0].length;
    if (/function\s+$/.test(text.slice(Math.max(0, m.index - 12), m.index + m[1].length))) continue;
    const args = []; let depth = 0, q = '', cur = '', k = start;
    for (; k < text.length; k++) {
      const c = text[k];
      if (q) { cur += c; if (c === '\\') { cur += text[++k]; } else if (c === q) q = ''; continue; }
      if (c === "'" || c === '"' || c === '`') { q = c; cur += c; continue; }
      if (c === '(' || c === '[' || c === '{') depth++;
      else if (c === ')' || c === ']' || c === '}') { if (depth === 0) break; depth--; }
      if (c === ',' && depth === 0) { args.push(cur.trim()); cur = ''; continue; }
      cur += c;
    }
    args.push(cur.trim());
    out.push({ line: text.slice(0, m.index).split('\n').length, args });
  }
  return out;
}
// the worst value for what stands between two string literals of a message expression
const TOP4 = weapons.map((p) => p.name).sort((a, b) => b.length - a.length).slice(0, 4).join(', ');
const LONG_OBJ = ['tb', 'cq', 'sk', 'so', 'kh', 'ctf'].map((m) => A.ifrHudObjective(m, {})).sort((a, b) => b.length - a.length)[0];
const FILL = [
  [/unlocked\.slice|\.join\(/, TOP4], [/nameOf\(/, NAME_W], [/ifrHudObjective/, LONG_OBJ], [/IFR_HUD_MODE_NAMES|IF_MODE_NAMES|\bnm\b/, 'CAPTURE THE FLAG'], [/IF_tierName/, 'MK V'], [/GARAGE_SLOTS/, 'R SHLD'],
  [/\.name\b/, longAny], [/gfmt\(|\.xp\b|\.credits\b|cost/, '9 999 999'], [/\.id\b|pt \?/, 'C'],
  // strings that come from somewhere else and are measured there (tables, pass-through arguments, the perf figures of the server operator)
  [/^[\s+()|?:]*(HELP_LINES|HINTS|STREAK_TEXT|CRATE_TEXT|DENY_TEXT|GARAGE_DENY|TRAIT_LINES|ev\.text|text|line|why|l|r|perfText)\b/, ''],
  [/CRATE_TEXT|STREAK_TEXT|HINTS|DENY_TEXT/, ''],
];
function fill(gap) {
  if (!/[A-Za-z0-9_$]/.test(gap)) return '';
  for (const [re, v] of FILL) if (re.test(gap)) return v;
  return '999';
}
/** an upper bound of a message expression: its string literals in order, the gaps filled with worst-case values; null when it has no literal */
function worst(expr) {
  let out = '', gap = '', any = false, k = 0;
  while (k < expr.length) {
    const c = expr[k];
    if (c === "'" || c === '"') {
      let j = k + 1, lit = ''; for (; j < expr.length && expr[j] !== c; j++) { if (expr[j] === '\\') j++; lit += expr[j]; }
      out += fill(gap) + lit; gap = ''; any = true; k = j + 1; continue;
    }
    gap += c; k++;
  }
  out += fill(gap);
  return any ? out : null;
}
const SCAN = { reply: { arg: 1, to: 'line' }, garageSay: { arg: 1, to: 'say' }, spectate: { arg: 1, to: 'line' }, garageOpen: { arg: 1, to: 'say' }, ifrHudLine: { arg: 1, to: 'line' }, ifrHudHint: { arg: 2, to: 'line' } };
let sites = 0;
for (const f of SRC_FILES) {
  const text = read(f);
  for (const fn of Object.keys(SCAN)) {
    if (f.endsWith('50_hud.js') && (fn === 'ifrHudLine' || fn === 'ifrHudHint')) continue;      // the driver's own plumbing passes texts through
    for (const c of calls(text, fn)) {
      const expr = c.args[SCAN[fn].arg]; if (expr === undefined) continue;
      sites++;
      const w = worst(expr); if (w === null) continue;        // a pass-through (measured at its source)
      (SCAN[fn].to === 'line' ? lineCheck : sayCheck)(f + ':' + c.line + ' ' + fn, w);
    }
  }
  // core `say` events and the vote replies
  for (const m of text.matchAll(/t: 'say'[^}]*?text: ([^}]*?)(?:, secs:| \})/g)) { sites++; const w = worst(m[1]); if (w !== null) lineCheck(f + ' say', w); }
  if (f.endsWith('80_game.js')) for (const m of text.matchAll(/return ('Vote[^;]*);/g)) { sites++; lineCheck(f + ' vote', worst(m[1])); }
}
if (sites < 60) fail('scan', 'the source scan found only ' + sites + ' message call sites: the scan is broken');
// ---- the tables
const tables = { HINTS: table('src/cs2/45_features.js', 'HINTS'), CRATE_TEXT: table('src/cs2/45_features.js', 'CRATE_TEXT'), STREAK_TEXT: table('src/cs2/45_features.js', 'STREAK_TEXT'),
  TRAIT_LINES: table('src/cs2/46_traits.js', 'TRAIT_LINES'), HELP_LINES: table('src/cs2/80_chat.js', 'HELP_LINES') };
for (const [k, v] of Object.entries(tables.HINTS)) lineCheck('HINTS.' + k, v);
for (const [k, v] of Object.entries(tables.CRATE_TEXT)) lineCheck('CRATE_TEXT.' + k, 'SUPPLY CRATE: ' + v);
for (const [k, v] of Object.entries(tables.STREAK_TEXT)) lineCheck('STREAK_TEXT.' + k, '12' + v);
for (const [k, v] of Object.entries(tables.TRAIT_LINES)) for (const [ph, t] of Object.entries(v)) lineCheck('TRAIT_LINES.' + k + '.' + ph, t);
tables.HELP_LINES.forEach((l, i) => lineCheck('HELP_LINES[' + i + ']', l));
for (const m of ['tb', 'cq', 'sk', 'so', 'kh', 'ctf']) lineCheck('mode hint ' + m, A.IFR_HUD_MODE_NAMES[m].replace(/\s+CO-OP$/, '') + ': ' + A.ifrHudObjective(m, { killTarget: 150, khTarget: 150, ctfCaptures: 3 }));
for (const [k, v] of Object.entries(DENY_TEXT)) sayCheck('DENY_TEXT.' + k, v);
for (const [k, v] of Object.entries(A.GARAGE_DENY)) sayCheck('GARAGE_DENY.' + k, v);
for (const p of parts) for (const lvl of [1, 5]) sayCheck('upgraded ' + p.name, p.name + ' MK ' + ['I', 'II', 'III', 'IV', 'V'][lvl - 1] + ': next sortie');
// the hints the script can show must all exist (a typo in a key would show nothing)
{ const ft = read('src/cs2/45_features.js'); for (const m of ft.matchAll(/onbHint\([^,]+, '(\w+)'/g)) if (!tables.HINTS[m[1]]) fail('hint ' + m[1], '45_features.js shows hint "' + m[1] + '" but HINTS has no such key'); }

// ================================================================ 4. the message line by construction: nothing is ever dropped
{
  let seed = 12345; const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  const words = ['OVERDRIVE', 'READY', 'HOLD', 'SPACE', '+', 'R', 'E', 'KILL', 'STREAK:', 'ARTILLERY', '6 000', 'U', 'A', 'I', '!!', NAME_W, NAME_M, 'W'.repeat(60), 'WWWWWW', "IT'S", 'LOCK-ON', '100 %'];
  for (let n = 0; n < 400; n++) {
    const len = 1 + Math.floor(rnd() * 60), msg = []; for (let i = 0; i < len; i++) msg.push(words[Math.floor(rnd() * words.length)]);
    const text = msg.join(' '), rows = lineRows(text);
    if (rows.join('').replace(/ /g, '') !== text.replace(/ /g, '')) { fail('fuzz', 'the line wrap lost text: ' + text + ' -> ' + rows.join(' / ')); break; }
    const bad = rows.find((r) => !A.ifrHudFits(LINE[0], r)); if (bad) { fail('fuzz', 'a wrapped row does not fit: ' + bad); break; }
    // shown page by page through the real line
    A.ifrHudOff(60); A.ifrHudLine(60, text, 3); let shown = '', guard = 0;
    const cur = () => A.ifrHudSlot(60).lineCur;
    while (cur() && guard++ < 200) { const c = cur(); shown += c.pages[c.page].join(''); now += 3.01; A.ifrHudTick(); }
    if (shown.replace(/ /g, '') !== text.replace(/ /g, '')) { fail('fuzz', 'the line pages lost text: ' + text); break; }
    note('fuzz');
  }
}

if (VERBOSE) {
  console.log('message line (' + lineMsgs.length + ' sources):'); for (const m of lineMsgs.sort((a, b) => b.rows - a.rows || b.text.length - a.text.length)) console.log('  ' + m.rows + ' row(s)  ' + m.where + '  |  ' + m.text);
  console.log('garage answers (' + sayMsgs.length + ' sources):'); for (const m of sayMsgs) console.log('  ' + m.where + '  |  ' + m.text);
}
if (fails.size) { console.log('FAIL: ' + fails.size + ' problem(s):'); for (const [k, v] of fails) console.log('  ' + v); process.exit(1); }
console.log('ok: every string fits where it is shown (' + Object.keys(HUD.text_slots).length + ' slots, ' + measured + ' drawn states and messages, ' + sites + ' message call sites scanned in ' + SRC_FILES.length + ' files, '
  + lineMsgs.length + ' line messages on one page of ' + LINE.length + ' rows, ' + sayMsgs.length + ' garage answers, ' + questions + ' buy / upgrade questions)');
