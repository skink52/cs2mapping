// test/hud_ids.cjs: the HUD's panel-id budget. CS2 keeps at most 1024 panel ids per custom_hud_layout: every id the script names in
// SetHasClass* / SetDialogVariable* takes a place in a table that never frees, and past 1024 the console says "The maximum number of panel ids
// has been reached, no more can be referenced" and those panels are never updated again (10 Nov 2026, 19:50: bars empty, weapons blank, lock
// marker gone; the glyph-cell HUD named 2 644 ids in a mock session, the garage alone over 1 000).
// This walks EVERY screen through the real driver (50_hud.js) and garage (60_garage.js): every garage tab, row, focus column, question and turn
// button; the fight HUD in every mode with all 64 radar dots, every threat direction, every lock stage, all multi-lock marks, every weapon,
// buff, card and message row; intro, death, podium and spectator slates. It counts the distinct ids the engine was handed and fails when
//   * an id is not in the layout xml, or the layout has an id the generator did not register (the budget would not count it);
//   * the walk leaves an id of the layout unreferenced other than the click-only Buttons (then the walk is not exhaustive: extend it);
//   * the total is over the budget (hud.json ids.budget, 800), and hard over 950.
// usage: node test/hud_ids.cjs     (needs out/addon/_gen/hud.json and the layout xml from tools/hud.py)
const fs = require('fs'), path = require('path'), vm = require('vm');
const root = path.join(__dirname, '..');
const read = (f) => fs.readFileSync(path.join(root, f), 'utf8');
const HUD = JSON.parse(read('out/addon/_gen/hud.json')), PARTS = JSON.parse(read('data/parts.json'));
const xmlIds = new Set([...read('out/addon/panorama/layout/custom_game/ironframe.xml').matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]));
const HARD = 950;
const stub = new Proxy(function () {}, { get: (t, k) => (k === Symbol.toPrimitive ? () => 0 : stub), apply: () => stub, construct: () => stub });
let now = 100;
const ids = new Map();      // id -> first screen that named it
let screenNow = 'start', calls = 0;
const bad = [];
const ref = (id) => { calls++; if (!xmlIds.has(id)) { if (bad.length < 20) bad.push('the script named an id the layout does not have: ' + id); return; } if (!ids.has(id)) ids.set(id, screenNow); };
const ent = { IsValid: () => true, Reset() {}, ResetForPlayer() {}, SetInputCaptureEnabled() {}, IsInputCaptureEnabled: () => true,
  SetHasClass(id) { ref(id); }, SetHasClassForPlayer(slot, id) { ref(id); }, SetDialogVariableString(id) { ref(id); }, SetDialogVariableStringForPlayer(slot, id) { ref(id); } };
const byId = new Map(PARTS.parts.map((p) => [p.id, p]));
const base = { HUD, PARTS, console, Instance: { FindEntityByName: () => ent, GetGameTime: () => now, Msg() {} },
  ARENA: { name: 'Dunes', id: 'dunes', points: [{ id: 'A', pos: [-3000, 0, 0] }, { id: 'B', pos: [0, 0, 0] }, { id: 'C', pos: [3000, 0, 0] }], drops: { t: [[-6000, 0, 0, 0]], ct: [[6000, 0, 0, 0]] } },
  CONFIG: { HUD: 'ifr_hud', HUD_BUDGET: 900 }, serverMode: true, gfmt: (n) => String(Math.round(n)), guard: (w, f) => { try { return f(); } catch (e) { return null; } },
  game: { garage: { budgets: () => ({ weight: 4900, load: 4600, en: 1500, output: 1400, valid: false, deny: 5, ap: 9000, walk: 440, boost: 1300, qb: 2500 }), describe: () => ({ rows: [['Type', 'proj'], ['Damage', '100'], ['Magazine', '30'], ['Ammo', '300'], ['DPS', '999'], ['Weight', '100'], ['EN load', '10']] }) }, mechs: new Map() },
  gameTime: () => now, DENY_TEXT: { 3: 'not enough credits' } };
vm.createContext(base);
const prog = read('src/core/70_progress.js');
const coreFns = ['IF_upgradeCost', 'IF_tierName'].map((n) => { const i = prog.indexOf('function ' + n + '('); const one = prog.indexOf('\n', i), body = prog.indexOf('\n}\n', i); return prog.slice(i, prog.slice(i, one).trim().endsWith('}') ? one : body + 2); }).join('\n');
const src = coreFns + '\n' + read('src/cs2/50_hud.js') + '\n' + read('src/cs2/60_garage.js') + '\n' + read('src/cs2/70_server.js');
const people = new Map();
Object.assign(base, require('./lib.cjs').careerGlobals(), { people, person: (s) => people.get(s), nameOf: () => 'WORLDMASTERS', ifrCmd() {}, sndTone() {}, reply() {}, log() {}, warnOnce() {}, TEAM_T: 2, TEAM_CT: 3 }); vm.createContext(base);
for (let i = 0; i < 40; i++) {
  try { vm.runInContext(src + '\n;this.__api = { ifrHudInit, ifrHudTick, ifrHudPending, ifrHudStats, ifrHudReset, ifrHudScreen, ifrHudTeam, ifrHudVitals, ifrHudWeapons, ifrHudLock, ifrHudAllies, ifrHudRadar, ifrHudMode, ifrHudFeed, ifrHudHit, ifrHudSlate, ifrHudLine, ifrHudHint, ifrHudCard, ifrHudLoadout, ifrHudCapture, garageOpen, garageRows, garageDraw, garagePick, garageUpgradeAsk, garageClick, GARAGE_TABS, ifrHudPilot, ifrHudBoard, setBoard: (b) => { srvBoard = b; } };', base); break; }
  catch (e) { const m = /(\w+) is not defined/.exec(e.message); if (!m) throw e; base[m[1]] = stub; vm.createContext(base); }
}
const A = base.__api; A.ifrHudInit();
const flush = () => { let g = 0; do { now += 1 / 64; A.ifrHudTick(); } while ((A.ifrHudPending(1) || A.ifrHudPending(2)) && g++ < 400); };
const at = (name) => { screenNow = name; };
const weapons = PARTS.parts.filter((p) => p.kind === 'arm' || p.kind === 'shoulder');
const wst = (part, over) => { const w = part.w || {}; return Object.assign({ part, w: part.w, ammo: w.ammo !== undefined ? w.ammo - (w.mag || 0) : 0, mag: w.mag || 0, magSize: w.mag || 0, cd: 0, heat: 0, overheat: false, charge: 0, charging: false, reloading: false, reloadT: 0, charges: w.charges || 0, firing: false, raised: false, lastShot: -99, salvo: 0, mlock: [], mlDone: 0, mlHold: 0 }, over || {}); };

for (const S of [1, 2]) {
  // ------------------------------------------------ fight
  at('fight');
  A.ifrHudSlate(S, 'none', null); A.ifrHudTeam(S, S === 1 ? 2 : 3);
  const me = { slot: S, team: 2, name: 'ME', pos: { x: 0, y: 0, z: 0 }, torsoYaw: 0, ap: 5000, apMax: 9000, en: 2000, enMax: 3400, enStalled: 1, enOver: true, stagger: 900, staggerMax: 1400, staggered: 1, protect: 1, dropT: 0, landLag: 1,
    boosting: true, assault: false, qbCd: 0.2, lockSoft: 0.3, lockHard: 0.9, fcs: PARTS.parts.find((p) => p.kind === 'fcs'), lock: { target: -1, stage: 0, t: 0 }, threats: [], weapons: [], frame: byId.get(10),
    overdrive: 0.5, odPhase: 0, odT: 0, sum: { kills: 3, deaths: 2, assists: 1 }, fkills: 2, streak: 2, boostDmgT: 9, shieldT: 9, aceT: 9, radarT: 9, artyReady: true,
    input: { camPos: { x: -500, y: 0, z: 200 }, camDir: { x: 1, y: 0, z: 0 }, fire: [false, false, false, false] } };
  for (let k = 0; k < 4; k++) base.game.mechs.set(20 + k, { slot: 20 + k, team: 3, name: 'FOE ' + k, pos: { x: 3000, y: (k - 1.5) * 900, z: k * 200 }, ap: 5000, apMax: 9000, height: 288, alive: true });
  const foe = base.game.mechs.get(20);
  for (let i = 0; i < weapons.length; i += 4) {
    me.weapons = [0, 1, 2, 3].map((k) => wst(weapons[(i + k) % weapons.length], { lastShot: now + i, firing: k === 0, reloading: k === 1, heat: 0.9, overheat: k === 2, charging: k === 3, charge: 0.5, cd: 1 }));
    for (const od of [[0.4, 0], [1, 0], [1, 1]]) { me.overdrive = od[0]; me.odPhase = od[1]; A.ifrHudVitals(S, me); A.ifrHudWeapons(S, me.weapons); flush(); now += 0.5; }
  }
  me.boosting = true; me.assault = true; A.ifrHudVitals(S, me); me.enStalled = 0; A.ifrHudVitals(S, me); flush();
  const ml = wst(byId.get(213), { mlHold: 1, mlDone: 2, mlock: [20, 21, 22, 23].map((sl, k) => ({ slot: sl, p: 1, done: k < 2 })) });
  me.weapons = [wst(byId.get(101)), wst(byId.get(103)), wst(byId.get(201)), ml];
  for (const lk of [{ target: 20, stage: 0, t: 0.1 }, { target: 20, stage: 1, t: 0.35 }, { target: 20, stage: 1, t: 0.7 }, { target: 20, stage: 1, t: 1.1 }, { target: 20, stage: 2, t: 2 }, { target: -1, stage: 0, t: 0 }]) {
    me.lock = lk;
    for (const y of [-2000, 0, 2500]) {
      foe.pos.y = y;
      const threats = []; for (let d = 0; d < 8; d++) threats.push({ kind: ['lock', 'launch', 'close'][(d + (lk.stage | 0)) % 3], dir: d });
      A.ifrHudVitals(S, me); A.ifrHudLock(S, lk, threats, lk.target >= 0 ? foe : null, me); A.ifrHudWeapons(S, me.weapons); flush();
    }
  }
  // teammate marks: eight allies across the view, near and far, then none
  { const al = new Map(); for (let k = 0; k < 8; k++) al.set(30 + k, { slot: 30 + k, alive: true, height: 288, pos: { x: foe.pos.x, y: (k - 3.5) * 150, z: foe.pos.z } });
    const was = me.alive; me.alive = true; A.ifrHudAllies(S, me, al, () => true); flush(); A.ifrHudAllies(S, me, al, () => false); flush(); me.alive = was; }
  for (const k of ['hit', 'heavy', 'kill']) { A.ifrHudHit(S, k); flush(); A.ifrHudHit(S, k); flush(); }
  A.ifrHudFeed(S, { kill: 'PILOT_SEVEN', xp: 40, streak: 3, bounty: true, rookie: true }); flush(); A.ifrHudFeed(S, { kill: 'PILOT_EIGHT', xp: 80 }); flush();
  A.ifrHudLoadout(S, me, 5); A.ifrHudCard(S, 'controls', 5); A.ifrHudCard(S, 'help', 5); flush();
  A.ifrHudLine(S, 'ONE ROW', 2, false, 1); flush(); A.ifrHudLine(S, 'TWO ROWS: ' + 'WORD '.repeat(14), 2, false, 2); flush(); A.ifrHudLine(S, ''); A.ifrHudLine(S, 'THREE ROWS: ' + 'WORD '.repeat(24), 2, false, 2); flush();
  A.ifrHudHint(S, 'walk' + S, 'A HINT', 3); flush();
  // ------------------------------------------------ common: radar (all 64 dots, every kind), every mode
  at('common');
  const dots = []; for (let i = 0; i < 64; i++) dots.push({ x: (i % 8 - 3.5) * 1400, y: (Math.floor(i / 8) - 3.5) * 1400, team: i % 2 ? 3 : 2, kind: ['mech', 'bounty', 'target', 'boss'][i % 4] });
  const P3 = (o) => ['A', 'B', 'C'].map((id, i) => Object.assign({ id, pos: { x: (i - 1) * 3000, y: 0, z: 0 }, radius: 700, owner: 0, progress: 0, capTeam: 0, contested: false, nT: 0, nCT: 0 }, o[i] || {}));
  const pts = [P3([{ owner: 2, progress: 1, capTeam: 2 }, { owner: 0, progress: 0.6, capTeam: 3, nCT: 2 }, { owner: 3, progress: 1, capTeam: 3, contested: true, nT: 1, nCT: 1 }]), P3([{ owner: 3, progress: 1, capTeam: 3 }, { owner: 2, progress: 1, capTeam: 2 }, { owner: 0 }])];
  const mb = { phase: 'running', timeLeft: 300, scores: { 2: 12, 3: 9 }, tickets: { 2: 200, 3: 150 }, killTarget: 60, wave: 2, waves: 9, khTarget: 150, ctfCaptures: 3 };
  const flag = (team, state, carrier) => ({ team, state, home: { x: team === 2 ? -4000 : 4000, y: 0, z: 0 }, pos: { x: 0, y: 0, z: 0 }, carrier, returnT: 12, returnMax: 20, carrierTeam: team === 2 ? 3 : 2 });
  const runs = [Object.assign({}, mb, { mode: 'tb', points: [] }), Object.assign({}, mb, { mode: 'sk', points: [] })];
  for (const p of pts) { runs.push(Object.assign({}, mb, { mode: 'cq', points: p }), Object.assign({}, mb, { mode: 'kh', points: [Object.assign({ scoring: true }, p[0])], allPoints: p, hillLeft: 60 }), Object.assign({}, mb, { mode: 'so', points: [p[1]], boss: { ap: 5, apMax: 10 } })); }
  for (const [a, b, c] of [['home', 'home', -1], ['carried', 'dropped', S], ['dropped', 'carried', 7], ['carried', 'carried', 7]]) runs.push(Object.assign({}, mb, { mode: 'ctf', points: [], flags: { 2: flag(2, a, c), 3: flag(3, b, c === S ? 9 : S) } }));
  for (const team of [2, 3]) for (const r of runs) for (const pos of [{ x: 0, y: 0, z: 0 }, { x: 3000, y: 0, z: 0 }]) {
    A.ifrHudRadar(S, dots.map((d, i) => Object.assign({}, d, { x: d.x + (pos.x ? 700 : 0), team: (i + team) % 2 ? 3 : 2 })), pos.x ? 90 : 0, pos); A.ifrHudMode(S, r, team); flush();
  }
  A.ifrHudRadar(S, [], 0, null); flush();
  // ------------------------------------------------ slates
  at('slates');
  for (const m of ['tb', 'cq', 'sk', 'so', 'kh', 'ctf']) { A.ifrHudSlate(S, 'intro', { title: 'IRONFRAME', arena: 'Dunes', mode: m }); flush(); }
  A.ifrHudSlate(S, 'death', { killer: 'PILOT_SEVEN', weapon: 'vm6', frame: 'White Glint', respawn: 6 }); flush(); now += 7; flush();
  for (const w of [2, 3, 0]) { A.ifrHudSlate(S, 'podium', { winner: w, podium: [{ slot: S, name: 'ME', kills: 9, team: 2 }, { slot: 9, name: 'B', kills: 8, team: 3 }, { slot: 8, name: 'C', kills: 7, team: 2 }], me: { xp: 1200, credits: 600, kills: 9, assists: 3, captures: 2, pveKills: 4, bossKills: 1, damage: 48000, streakBest: 4 }, team: 2, sub: 'CONQUEST  DUNES' }); flush(); }
  A.ifrHudSlate(S, 'spectator', { name: 'PILOT_SEVEN', slot: 9 }); flush();
  // ------------------------------------------------ garage: every tab, row, column, question, turn buttons, both modes
  at('garage');
  for (const server of [true, false]) {
    base.serverMode = server; vm.runInContext('serverMode = ' + server, base);
    const up = {}; for (const p of PARTS.parts) up[p.id] = server ? 3 : 0;
    const pe = { slot: S, human: true, status: 'dead', pilot: server ? { rank: 12, credits: 60000, active: 1, upgrades: up, loadouts: ['4,101,103,201,209,301,401,501,601', null, null], owned: new Set(PARTS.parts.filter((p, i) => i % 3).map((p) => p.id)) } : null, garage: null };
    try { A.garageOpen(pe, 'Pick a loadout and SORTIE'); } catch (e) { /* the hangar props need the engine */ }
    const g = pe.garage; g.slot = 1;
    // the profile that follows the pilot (the SLOTS and PILOT tabs, the identity strip) and the server's top pilots
    const K = base.IF_Career, pr = K.blank(); for (const hh of K.data.honours) pr.earned.add(hh.id);
    Object.assign(pr, { callsign: 'ZZ-TOP 99 ZZ', title: 5, badge: 13, place: 3, fav: 4, names: ['ALPHA', '', '', '', '', ''], daily: [{ code: 1, progress: 1, goal: 2, reward: 600 }, { code: 2, progress: 15, goal: 15, reward: 800 }] });
    pe.profile = pr; pe.localProfile = pr; people.set(S, pe);
    A.setBoard(server ? { total: 1234, rows: [{ name: 'RAVEN 7', rank: 50, xp: 1270507 }, { name: 'SKINK52', rank: 41, xp: 800123 }] } : null);
    for (let tab = 0; tab < A.GARAGE_TABS.length; tab++) {
      g.tab = tab; g.row = 0; g.scroll = 0; g.confirm = null; g.pending = false;
      try { A.garageRows(pe); } catch (e) { continue; }
      for (let r = 0; r < Math.max(1, g.rows.length); r++) {
        g.row = r; if (g.row >= g.scroll + 8) g.scroll = g.row - 7;
        for (const col of [0, 1, 2]) { g.col = col; g.urow = r % 8; g.msg = col ? 'Need 3 000 CR and a second row of words for the answer line' : ''; g.msgAt = now; try { A.garageDraw(pe); } catch (e) { } flush(); }
        g.col = 1; try { A.garagePick(pe); } catch (e) { } try { A.garageDraw(pe); } catch (e) { } flush();
        const part = g.rows[r] && g.rows[r].part; g.confirm = null; g.pending = false;
        if (part) { try { A.garageUpgradeAsk(pe, part); } catch (e) { } try { A.garageDraw(pe); } catch (e) { } flush(); g.confirm = null; }
        try { A.garageRows(pe); } catch (e) { }
      }
      for (const id of ['ifr_gup', 'ifr_gdn', 'ifr_grl', 'ifr_grr', 'ifr_grf']) { try { A.garageClick(pe, id); } catch (e) { } flush(); }
      g.pending = true; try { A.garageDraw(pe); } catch (e) { } flush(); g.pending = false;
    }
    A.ifrHudCapture(S, false);
    at('fight'); A.ifrHudPilot(S); flush();
    at('podium'); A.ifrHudBoard(S, { total: 1234, rows: [1, 2, 3, 4, 5].map((k) => ({ name: 'PILOT ' + k, rank: 10 * k, xp: 1000 * k })) }, { place: 3, rank: 20, xp: 132236 }); flush();
    A.ifrHudBoard(S, null, null); flush();
    people.delete(S);
  }
  at('reset'); A.ifrHudReset(S); flush();
}

// ------------------------------------------------ the count
const layout = Object.keys(HUD.panels);
const perScreen = {}; for (const id of ids.keys()) { const sc = (HUD.panels[id] || {}).screen || '?'; perScreen[sc] = (perScreen[sc] || 0) + 1; }
const CLICK_ONLY = new Set(['ifr_gup', 'ifr_gdn', 'ifr_gcy', 'ifr_gcx', 'ifr_grl', 'ifr_grf', 'ifr_grr']);     // Buttons the script only hears clicks from
const unref = layout.filter((id) => !ids.has(id) && !CLICK_ONLY.has(id));
const problems = bad.slice();
for (const id of xmlIds) if (!HUD.panels[id]) problems.push('the layout xml has an id the generator did not register (the budget does not count it): ' + id);
for (const id of layout) if (!xmlIds.has(id)) problems.push('registered but not in the layout xml: ' + id);
if (unref.length) problems.push('the walk never referenced ' + unref.length + ' id(s) of the layout (dead ids, or the walk is not exhaustive): ' + unref.slice(0, 30).join(' '));
for (const ts of Object.values(HUD.text_slots)) if (ts.row) problems.push('text slot ' + ts.panel + ' is a row of glyph cells again (one id per character)');
if (layout.length > HUD.ids.budget) problems.push('the layout has ' + layout.length + ' ids, over the budget of ' + HUD.ids.budget);
if (ids.size > HUD.ids.budget) problems.push(ids.size + ' ids referenced, over the budget of ' + HUD.ids.budget);
if (ids.size > HARD || xmlIds.size > HARD) problems.push('over ' + HARD + ' panel ids: CS2 stops updating panels at 1024');
if (A.ifrHudStats().ids !== ids.size) problems.push('the driver counts ' + A.ifrHudStats().ids + ' ids, the engine saw ' + ids.size);
console.log('panel ids referenced in a full walk of every screen: ' + ids.size + ' of ' + layout.length + ' in the layout (' + xmlIds.size + ' ids in the xml; budget ' + HUD.ids.budget + ', hard fail ' + HARD + ', CS2 cap ' + HUD.ids.cap + '); ' + calls + ' engine calls');
console.log('  by screen (layout): ' + Object.entries(HUD.ids.screens).sort((a, b) => b[1] - a[1]).map(([k, v]) => k + ' ' + (perScreen[k] || 0) + '/' + v).join(', ') + '; click-only buttons ' + CLICK_ONLY.size);
if (problems.length) { console.log('FAIL: ' + problems.length + ' problem(s):'); for (const p of problems) console.log('  ' + p); process.exit(1); }
console.log('ok: the HUD stays under CS2\'s panel-id cap whatever screens a session uses');
