// test/hud_driver.cjs: loads src/cs2/50_hud.js with a stub Instance / HUD / PARTS / ARENA and checks the driver's rules.
// usage: node test/hud_driver.cjs     (needs out/addon/_gen/hud.json from tools/hud.py)
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const root = path.join(__dirname, '..');
const HUD = JSON.parse(fs.readFileSync(path.join(root, 'out/addon/_gen/hud.json'), 'utf8'));
const PARTS = JSON.parse(fs.readFileSync(path.join(root, 'data/parts.json'), 'utf8'));
const ARENA = { points: [{ id: 'A', pos: [-3000, 0, 0] }, { id: 'B', pos: [0, 0, 0] }, { id: 'C', pos: [3000, 0, 0] }], drops: { t: [[-6000, 0, 0, 0]], ct: [[6000, 0, 0, 0]] } };

const calls = [];
const shownVar = new Map();     // slot|panel -> the Label's text (what the client shows)
const idsSeen = new Set();      // every panel id named to the engine (CS2 caps these at 1024 per layout)
let now = 100;
const ent = {
  IsValid() { return true; },
  Reset() { calls.push(['reset']); },
  ResetForPlayer(slot) { calls.push(['resetp', slot]); },
  SetInputCaptureEnabled(slot, on) { calls.push(['capture', slot, on]); },
  SetHasClassForPlayer(slot, id, cls, on) { idsSeen.add(id); if (!HUD.panels[id]) throw new Error('class on an id the layout does not have: ' + id); calls.push(['cls', slot, id, cls, on]); },
  SetDialogVariableStringForPlayer(slot, id, v, text) { idsSeen.add(id); if (!HUD.panels[id] || v !== 'v') throw new Error('text on an id the layout does not have: ' + id + '.' + v); calls.push(['var', slot, id, text]); shownVar.set(slot + '|' + id, text); },
};
const ctx = { HUD, PARTS, ARENA, CONFIG: { HUD: 'ifr_hud', HUD_BUDGET: 900 }, Instance: { FindEntityByName: () => ent, GetGameTime: () => now, Msg: (m) => console.log('  (log) ' + m) }, console };
vm.createContext(ctx);
const src = fs.readFileSync(path.join(root, 'src/cs2/50_hud.js'), 'utf8');
const api = vm.runInContext(src + '\n;({ ifrHudInit, ifrHudSet, ifrHudVar, ifrHudNum, ifrHudLadder, ifrHudLine, ifrHudReset, ifrHudOff, ifrHudTick, ifrHudStats, ifrHudPending, ifrHudScreen, ifrHudVitals, ifrHudWeapons, ifrHudLock, ifrHudRadar, ifrHudMode, ifrHudSlate, ifrHudGarage, ifrHudCapture, ifrHudFeed, ifrHudCard, ifrHudCardOn, ifrHudHint, ifrHudHinted, ifrHudCount, ifrHudLoadout, ifrHudProject, ifrHudWrapAll, ifrHudFitText, ifrHudFits, ifrHudCutList })', ctx);
const H = api;
/** the text a slot's pixel row shows (cells' g<code> classes), trimmed */
const text = (slot, name) => (shownVar.get(slot + '|' + HUD.text_slots[name].panel) || '').replace(/ /g, ' ').trim();
const panelOf = (id) => id.replace(/_t_(\d+|sp)$/, '');
const uniq = (a) => a.filter((x, i) => i === 0 || x !== a[i - 1]);
const writes = () => calls.filter((c) => c[0] === 'cls' || c[0] === 'var');
const clear = () => { calls.length = 0; };
let passed = 0;
function test(name, fn) { try { fn(); passed++; console.log('ok   ' + name); } catch (e) { console.log('FAIL ' + name + ': ' + (e.stack || e)); process.exitCode = 1; } }

H.ifrHudInit();
test('unknown panel / class / text slot / ladder throw', () => {
  assert.throws(() => H.ifrHudSet(0, 'ifr_nope', 'stOn', true), /unknown panel/);
  assert.throws(() => H.ifrHudSet(0, 'ifr_lag', 'stWrong', true), /no class/);
  assert.throws(() => H.ifrHudVar(0, 'nope', 'x'), /unknown text slot/);
  assert.throws(() => H.ifrHudLadder(0, 'nope', 0.5), /unknown ladder/);
  H.ifrHudSet(0, 'ifr_rd3', 'stG575', true); assert.throws(() => H.ifrHudSet(0, 'ifr_rd3', 'stG576', true), /no class/);
});
test('change-only: the second identical call sends nothing', () => {
  H.ifrHudOff(0); clear(); H.ifrHudSet(0, 'ifr_lag', 'stOn', true); H.ifrHudVar(0, 'ap', '6 420'); H.ifrHudTick();
  assert.strictEqual(writes().length, 2);      // the class + ONE call for the text (a Label's dialog variable; it was one class per character)
  clear(); H.ifrHudVar(0, 'ap', '6 450'); H.ifrHudTick(); assert.strictEqual(writes().length, 1); assert.strictEqual(text(0, 'ap'), '6 450');
  H.ifrHudVar(0, 'ap', '6 420'); H.ifrHudTick();
  clear(); H.ifrHudSet(0, 'ifr_lag', 'stOn', true); H.ifrHudVar(0, 'ap', '6 420'); H.ifrHudTick();
  assert.strictEqual(writes().length, 0);
  clear(); H.ifrHudSet(0, 'ifr_lag', 'stOn', false); H.ifrHudSet(0, 'ifr_lag', 'stOn', true); H.ifrHudTick();   // back and forth before the flush: free
  assert.strictEqual(writes().length, 0);
});
test('ladder clears the previous step', () => {
  clear(); H.ifrHudLadder(0, 'ap', 0.5); H.ifrHudTick();
  assert.deepStrictEqual(writes().map((c) => c.slice(2)), [['ifr_l_ap', 'stL10', true]]);
  clear(); H.ifrHudLadder(0, 'ap', 0.7); H.ifrHudTick();
  assert.deepStrictEqual(writes().map((c) => c.slice(2)).sort(), [['ifr_l_ap', 'stL10', false], ['ifr_l_ap', 'stL14', true]]);
  clear(); H.ifrHudLadder(0, 'ap', 0.71); H.ifrHudTick(); assert.strictEqual(writes().length, 0);
});
test('quantised numbers with hysteresis', () => {
  clear(); H.ifrHudNum(0, 'en', 100, 10); H.ifrHudTick(); assert.strictEqual(text(0, 'en'), '100');
  clear(); H.ifrHudNum(0, 'en', 105, 10); H.ifrHudTick(); assert.strictEqual(writes().length, 0);
  clear(); H.ifrHudNum(0, 'en', 106.5, 10); H.ifrHudTick(); assert.strictEqual(text(0, 'en'), '110');
  clear(); H.ifrHudNum(0, 'en', 104.5, 10); H.ifrHudTick(); assert.strictEqual(writes().length, 0);
});
test('governor caps at 900 writes per tick and finishes next tick', () => {
  clear();
  for (let i = 0; i < 64; i++) H.ifrHudSet(5, 'ifr_rd' + i, 'stG' + i, true);           // 64
  for (let i = 0; i < 64; i++) { H.ifrHudSet(5, 'ifr_rd' + i, 'stE', true); H.ifrHudSet(5, 'ifr_rd' + i, 'stBig', true); }   // 128
  for (let i = 0; i < 12; i++) H.ifrHudSet(6, 'ifr_rd' + i, 'stA', true);
  for (let sl = 10; sl < 24; sl++) for (let i = 0; i < 64; i++) H.ifrHudSet(sl, 'ifr_rd' + i, 'stG' + (i + sl), true);   // 896 more
  const total = H.ifrHudPending(5) + H.ifrHudPending(6);
  let sum = 0; for (let sl = 10; sl < 24; sl++) sum += H.ifrHudPending(sl);
  assert.strictEqual(total + sum, 192 + 12 + 896);
  const n1 = H.ifrHudTick(); assert.strictEqual(n1, 900); assert.strictEqual(writes().length, 900);
  clear(); const n2 = H.ifrHudTick(); assert.strictEqual(n2, 200);
  clear(); assert.strictEqual(H.ifrHudTick(), 0);
});
test('priority bands: warnings before gauges before text, whatever the order of the calls', () => {
  clear(); H.ifrHudVar(7, 'line', 'hello'); H.ifrHudLadder(7, 'en', 0.3); H.ifrHudSet(7, 'ifr_mwarn', 'stOn', true); H.ifrHudTick();
  assert.deepStrictEqual(uniq(writes().map((c) => panelOf(c[2]))), ['ifr_mwarn', 'ifr_l_en', 'ifr_linea']); assert.strictEqual(text(7, 'line'), 'HELLO');   // the message line's first row (Nov 2026: two rows in ifr_line)
});
test('odd / even halves alternate: the first-served half changes every tick', () => {
  for (const sl of [30, 31]) { H.ifrHudOff(sl); }
  clear(); for (const sl of [30, 31]) for (let i = 0; i < 576; i++) H.ifrHudSet(sl, 'ifr_rd' + (i % 64), 'stG' + i, true);
  // each slot has 576 writes; the budget serves one half fully (576) and the other 324
  H.ifrHudTick();
  const firstSlot = writes()[0][1], t = H.ifrHudStats().tick;
  assert.strictEqual(firstSlot & 1, t & 1);
  assert.strictEqual(writes().filter((c) => c[1] === firstSlot).length, 576);
  assert.strictEqual(writes().filter((c) => c[1] !== firstSlot).length, 324);
  clear(); for (const sl of [30, 31]) for (let i = 0; i < 576; i++) H.ifrHudSet(sl, 'ifr_rd' + (i % 64), 'stG' + i, false);
  H.ifrHudTick();
  assert.strictEqual(writes()[0][1], firstSlot ^ 1);        // the other half first this time
  H.ifrHudTick(); H.ifrHudOff(30); H.ifrHudOff(31);
});
test('reset redraws everything that is wanted', () => {
  H.ifrHudOff(8); clear();
  H.ifrHudScreen(8, 'fight'); H.ifrHudLadder(8, 'ap', 1); H.ifrHudVar(8, 'ap', '9 000'); H.ifrHudSet(8, 'ifr_lag', 'stOn', true); H.ifrHudSet(8, 'ifr_lag', 'stOn', false);
  H.ifrHudTick();
  const mine = () => writes().filter((c) => c[1] === 8).map((c) => c.slice(1).join(' ')).sort();
  const first = mine();
  clear(); H.ifrHudTick(); assert.strictEqual(mine().length, 0);
  clear(); H.ifrHudReset(8); assert.deepStrictEqual(calls[0], ['resetp', 8]); H.ifrHudTick();
  const again = mine();
  assert.deepStrictEqual(again, first.filter((w) => !/ false$/.test(w)));     // only the "on" classes and texts come back
});
// ---- the helpers with the adapter's shapes (90_main.js / 60_garage.js), and the budget figures for docs/HUD.md
const byId = new Map(PARTS.parts.map((p) => [p.id, p]));
function weapon(id, over) {
  const part = byId.get(id) || null, w = part ? part.w : null;
  return Object.assign({ part, w, ammo: w && w.ammo !== undefined ? w.ammo - (w.mag || 0) : 0, mag: w ? w.mag || 0 : 0, magSize: w ? w.mag || 0 : 0, cd: 0, heat: 0, overheat: false, charge: 0, charging: false, reloading: false, charges: w ? w.charges || 0 : 0, firing: false, raised: false, lastShot: -99 }, over || {});
}
const mech = (slot, team, x) => ({ slot, team, name: 'PILOT_' + slot, pos: { x, y: 0, z: 100 }, torsoYaw: 90, ap: 6420, apMax: 9000, en: 2850, enMax: 3400, enStalled: 0, stagger: 400, staggerMax: 1400, staggered: 0, protect: 0, dropT: 0, landLag: 0, boosting: true, assault: false, qbCd: 0.2, lockHard: 0.9, fcs: byId.get(501), lock: { target: -1, stage: 0, t: 0 }, threats: [], weapons: [weapon(101), weapon(103), weapon(201), weapon(209)] });
const match = { mode: 'cq', phase: 'running', timeLeft: 402, scores: { 2: 12, 3: 9 }, tickets: { 2: 212, 3: 178 }, points: [{ id: 'A', owner: 2, progress: 1 }, { id: 'B', owner: 0, progress: 0.4 }, { id: 'C', owner: 3, progress: 1 }], killTarget: 60 };
test('full refresh of a fight state and the steady-state cost', () => {
  H.ifrHudOff(1); clear();
  const me = mech(1, 2, 0), tgt = mech(2, 3, 2450);
  me.lock = { target: 2, stage: 1, t: 0.5 }; me.threats = [{ kind: 'lock', pos: tgt.pos }, { kind: 'launch', dir: 5 }];
  const dots = []; for (let i = 0; i < 20; i++) dots.push({ x: (i - 10) * 500, y: (i % 5) * 700 - 1400, team: i % 3 ? 3 : 2, kind: i === 2 ? 'target' : i === 7 ? 'bounty' : 'mech' });
  const draw = () => { H.ifrHudSlate(1, 'none', null); H.ifrHudMode(1, match, 2); H.ifrHudVitals(1, me); H.ifrHudWeapons(1, me.weapons); H.ifrHudLock(1, me.lock, me.threats, tgt, me); H.ifrHudRadar(1, dots, me.torsoYaw, me.pos); H.ifrHudFeed(1, { streak: 3, rookie: true }); };
  draw(); const full = H.ifrHudTick(); console.log('  full refresh (fight, 20 radar dots, lock, 2 threats): ' + full + ' writes');
  assert.ok(full < 250, 'full refresh ' + full + ' >= 250');
  clear(); draw(); assert.strictEqual(H.ifrHudTick(), 0);
  // a typical tick: EN drains a step, AP takes a hit, one weapon fires, the radar moves two dots one cell
  me.en = 2650; me.ap = 6100; me.weapons[0].mag = 29; me.weapons[0].lastShot = now; me.weapons[0].firing = true; me.weapons[0].cd = 0.1;
  dots[3].x += 600; dots[4].y += 600; me.lock.t = 0.7;
  clear(); draw(); const steady = H.ifrHudTick(); console.log('  busy tick (EN + AP step, a shot, 2 dots moved, lock beep): ' + steady + ' writes');
  assert.ok(steady < 25, 'steady ' + steady + ' >= 25');
  H.ifrHudReset(1); clear(); const redraw = H.ifrHudTick(); console.log('  redraw after reset: ' + redraw + ' writes'); assert.ok(redraw < 250);
  assert.strictEqual(text(1, 'ap'), '6 100', 'a reset sends the texts again');
});
test('slates, line, death countdown, garage', () => {
  H.ifrHudSlate(3, 'intro', { title: 'IRONFRAME: Dunes', arena: 'Dunes', mode: 'cq' }); H.ifrHudTick();
  H.ifrHudSlate(3, 'death', { killer: 'PILOT_SEVEN', weapon: 'vm6', respawn: 6 }); H.ifrHudTick();
  clear(); now += 2.2; H.ifrHudTick(); assert.ok(text(3, 'respawn') === 'RESPAWN IN 4');
  H.ifrHudSlate(3, 'podium', { winner: 2, podium: [{ slot: 9, name: 'ACE', kills: 18 }, { slot: 3, name: 'ME', kills: 11 }], me: { xp: 1240, credits: 620, kills: 11, assists: 3, captures: 2, damage: 48000, streakBest: 4 }, team: 2 }); H.ifrHudTick();
  H.ifrHudSlate(3, 'spectator', { name: 'Ace', slot: 9 }); H.ifrHudTick();
  clear(); H.ifrHudLine(3, 'hello there', 2); H.ifrHudTick(); assert.ok(text(3, 'line') === 'HELLO THERE');
  clear(); now += 2.5; H.ifrHudTick(); assert.ok(writes().some((c) => c[2] === 'ifr_line' && c[3] === 'stOn' && c[4] === false));   // the box fades
  const arms = PARTS.parts.filter((p) => p.kind === 'arm').slice(0, 10);
  const states = ['equipped', 'owned', 'owned', 'buy', 'buy', 'poor', 'locked', 'locked', 'owned', 'buy'];
  const rows = arms.map((p, i) => ({ name: p.name, type: 'ARM / PROJECTILE', c: states[i] === 'buy' ? '3 000 CR' : states[i].toUpperCase(), r: i === 0 ? 'R ARM' : '', state: states[i], pic: p.key }));
  const tracks = [0, 1, 2, 3].map((i) => ({ n: 'R ARM DAMAGE', s: 'AR-22 RIFLE  +2 % PER LEVEL', c: i === 3 ? 'MAX' : '4 500 CR', l: i + '/5', a: '170', b: i === 3 ? '' : '173', frac: i / 5, state: i === 3 ? 'max' : i === 1 ? 'poor' : 'up' }));
  const st = { tabs: ['All', 'Primary', 'Secondary', 'Special', 'Utility', 'Frames', 'Paint', 'Loadouts', 'SORTIE'], tab: 1, col: 1, rows, sel: 4, scroll: 0, total: 14, tracks, urow: 1, utitle: 'COST BASE X (LV+1)',
    budgets: { weight: 3920, load: 4600, en: 1460, output: 1400, valid: true, deny: 0, ap: 9000, walk: 440, boost: 1300, qb: 2500 }, lock: 6000, frame: { name: 'White Glint', type: 'medium tetrapod' },
    top: { map: 'Dunes', credits: '8 450 CR', kda: '11 / 3 / 4', mech: 'White Glint', rank: 'R12 / LOADOUT 1' }, bay: 'White Glint   BAY 3', spin: 'A / D ROTATE', confirm: null,
    info: { name: 'BZ-Hammer', type: 'ARM / PROJECTILE   RANK 4   3 000 CR', lines: ['Magazine 4  Ammo 24', 'Reload 3.5 s'], key: 'DMG 1800  RATE 0.5/S', cmp: 'VS R ARM: WEIGHT +560  EN +120' },
    weapons: [{ pic: 'rifle', name: 'AR-22 Rifle', stats: 'DMG 170  AMMO 300' }, { pic: 'shotgun', name: 'SG-Scatter', stats: 'DMG 90' }, null, null], legend: 'W/S ITEM   SPACE EQUIP / BUY', tips: ['a', 'b'], hint: 'Pick a loadout', pending: false };
  clear(); H.ifrHudGarage(3, st); let n = H.ifrHudTick(), ticks = 1; for (let t = 0; t < 6 && H.ifrHudPending(3); t++) { n += H.ifrHudTick(); ticks++; }
  console.log('  garage first draw: ' + n + ' writes over ' + ticks + ' tick(s) (governor 900 per tick)'); assert.ok(n < 2000 && !H.ifrHudPending(3));
  clear(); H.ifrHudGarage(3, st); assert.strictEqual(H.ifrHudTick(), 0);
  st.sel = 5; clear(); H.ifrHudGarage(3, st); const m = H.ifrHudTick(); console.log('  garage row move: ' + m + ' writes'); assert.ok(m < 40);
  st.confirm = { q: 'Buy BZ-Hammer for 3 000 CR?', hint: 'Space confirm / Ctrl cancel' }; clear(); H.ifrHudGarage(3, st); H.ifrHudTick(); assert.ok(writes().some((c) => c[2] === 'ifr_gcbar' && c[4] === true));
  assert.strictEqual(typeof H.ifrHudCapture, 'function'); clear(); H.ifrHudCapture(3, true);
});
// ---- 10 Nov 2026 evening playtest: messages, lock, overdrive / streak, cards, hints
const has = (slot, id, cls) => { let on = false; for (const c of calls) if (c[0] === 'cls' && c[1] === slot && c[2] === id && c[3] === cls) on = c[4]; return on; };
const lineText = (slot) => HUD.line.slots.map((n) => text(slot, n)).filter(Boolean).join(' | ');
test('message line: nothing replaces a message before it was readable; ambient news never interrupts; important cuts in', () => {
  const S = 40; H.ifrHudOff(S); clear();
  H.ifrHudLine(S, 'first message', 4); H.ifrHudTick(); assert.strictEqual(lineText(S), 'FIRST MESSAGE');
  now += 0.3; H.ifrHudLine(S, 'second message', 4); H.ifrHudTick(); assert.strictEqual(lineText(S), 'FIRST MESSAGE', 'a newer message waits while the first is under 1.6 s old');
  H.ifrHudLine(S, 'a bot took the crate', 3, false, 0); H.ifrHudTick(); assert.strictEqual(lineText(S), 'FIRST MESSAGE', 'ambient news does not interrupt');
  now += 2.4; H.ifrHudTick(); assert.strictEqual(lineText(S), 'SECOND MESSAGE', 'the waiting message follows (the first gave way after ~2.2 s)');
  now += 0.2; H.ifrHudLine(S, 'overdrive ready', 5, false, 2); H.ifrHudTick(); assert.strictEqual(lineText(S), 'OVERDRIVE READY'); assert.ok(has(S, 'ifr_line', 'stHi'), 'important = gold');
  now += 5.1; H.ifrHudTick(); assert.strictEqual(lineText(S), 'SECOND MESSAGE', 'the interrupted message comes back');
  now += 4.1; H.ifrHudTick(); assert.ok(!has(S, 'ifr_line', 'stOn'));
  H.ifrHudLine(S, 'news', 3, false, 0); H.ifrHudTick(); assert.strictEqual(lineText(S), 'NEWS', 'ambient shows on a free line'); now += 3.1; H.ifrHudTick();
});
test('message line: a long message wraps into the rows and continues on a second page; a name wider than a row is broken, nothing is lost', () => {
  const S = 41; H.ifrHudOff(S); clear();
  const long = 'STREAK 5: ARTILLERY READY. LOCK AN ENEMY 700 U OR MORE AWAY AND SIX SHELLS FALL ON IT ' + 'W'.repeat(40) + ' THEN SOME MORE WORDS TO FILL A SECOND PAGE OF THE LINE FOR SURE AND A FEW ON TOP OF THAT TO BE CERTAIN ABOUT IT';
  H.ifrHudLine(S, long, 6); H.ifrHudTick();
  let seen = lineText(S); assert.ok(has(S, 'ifr_line', 'stR4') || has(S, 'ifr_line', 'stR3'), 'every row in use (four since the line moved beside the mech)');
  for (let i = 0; i < 6; i++) { now += 3.05; H.ifrHudTick(); if (!has(S, 'ifr_line', 'stOn')) break; const t = lineText(S); if (!seen.endsWith(t)) seen += ' | ' + t; }
  assert.strictEqual(seen.replace(/[ |]/g, ''), long.replace(/ /g, ''), 'every character was shown');
  for (const row of H.ifrHudWrapAll('line', long)) assert.ok(H.ifrHudFits('line', row), 'row fits: ' + row);
  assert.strictEqual(H.ifrHudFitText('tname', 'W'.repeat(24)).slice(-2), '..'); assert.ok(H.ifrHudFits('tname', H.ifrHudFitText('tname', 'W'.repeat(24))));
  assert.strictEqual(H.ifrHudFitText('tname', 'PILOT_7'), 'PILOT_7');
});
test('hints: once per pilot and session; cards time out', () => {
  const S = 42; H.ifrHudOff(S); clear();
  assert.strictEqual(H.ifrHudHint(S, 'stall', 'EN EMPTY', 5), true); assert.strictEqual(H.ifrHudHint(S, 'stall', 'EN EMPTY', 5), false); assert.ok(H.ifrHudHinted(S, 'stall'));
  H.ifrHudReset(S); assert.strictEqual(H.ifrHudHint(S, 'stall', 'EN EMPTY', 5), false, 'a HUD reset keeps the session');
  H.ifrHudOff(S); assert.strictEqual(H.ifrHudHint(S, 'stall', 'EN EMPTY', 5), true, 'a new pilot in the slot gets it again');
  assert.strictEqual(H.ifrHudCount(S, 'spawns'), 1); assert.strictEqual(H.ifrHudCount(S, 'spawns'), 2);
  H.ifrHudCard(S, 'controls', 5); H.ifrHudTick(); assert.ok(has(S, 'ifr_ctrl', 'stOn')); assert.ok(H.ifrHudCardOn(S, 'controls'));
  now += 5.1; H.ifrHudTick(); assert.ok(!has(S, 'ifr_ctrl', 'stOn'));
  const me = mech(S, 2, 0); me.frame = byId.get(10);
  H.ifrHudLoadout(S, me, 8); H.ifrHudTick();
  assert.ok(has(S, 'ifr_load', 'stOn')); assert.strictEqual(text(S, 'lc2r'), 'LOCK-ON MISSILES'); assert.strictEqual(text(S, 'lc3r'), 'BREAKS LOCKS'); assert.strictEqual(text(S, 'lct'), 'GUN SHIELD: HOLD F');
  now += 8.1; H.ifrHudTick(); assert.ok(!has(S, 'ifr_load', 'stOn'));
});
test('lock: acquiring -> soft -> locked on the bracket; the launcher row says what a press will do; the bracket follows the target', () => {
  const S = 43; H.ifrHudOff(S); clear();
  const me = mech(S, 2, 0), tgt = mech(2, 3, 2450); me.lockSoft = 0.3; me.pos.z = 0; tgt.pos = { x: 2450, y: 0, z: 0 }; tgt.height = 288;
  me.input = { camPos: { x: -500, y: 0, z: 158.4 }, camDir: { x: 1, y: 0, z: 0 } };
  const draw = () => { H.ifrHudVitals(S, me); H.ifrHudWeapons(S, me.weapons); H.ifrHudLock(S, me.lock, me.threats, me.lock.target >= 0 ? tgt : null, me); H.ifrHudWeapons(S, me.weapons); H.ifrHudTick(); };
  draw(); assert.strictEqual(text(S, 'w2s'), 'NO LOCK: UNGUIDED'); assert.ok(has(S, 'ifr_w2', 'stLkNo')); assert.ok(!has(S, 'ifr_lock', 'stAcq'));
  me.lock = { target: 2, stage: 0, t: 0.1 }; draw(); assert.ok(has(S, 'ifr_lock', 'stAcq')); assert.strictEqual(text(S, 'lstate'), 'ACQUIRING'); assert.strictEqual(text(S, 'w2s'), 'HOLD: LOCK 5 %');
  me.lock = { target: 2, stage: 1, t: 0.6 }; draw(); assert.ok(has(S, 'ifr_lock', 'stHard1') || has(S, 'ifr_lock', 'stSoft')); assert.strictEqual(text(S, 'lstate'), 'SOFT LOCK'); assert.strictEqual(text(S, 'w2s'), 'HOLD: LOCK 50 %'); assert.ok(has(S, 'ifr_w2', 'stLkAcq'));
  me.weapons[2].mslWait = true; draw(); assert.strictEqual(text(S, 'w2s'), 'KEEP HOLDING 50 %'); me.weapons[2].mslWait = false;
  me.lock = { target: 2, stage: 2, t: 1.3 }; draw(); assert.ok(has(S, 'ifr_lock', 'stHard3')); assert.strictEqual(text(S, 'lstate'), 'LOCKED'); assert.strictEqual(text(S, 'w2s'), 'LOCKED: FIRE'); assert.ok(has(S, 'ifr_w2', 'stLkOn'));
  // straight ahead: the bracket at the centre; 10 degrees to the left and above: left and up by 720 x tan
  const g = HUD.lockgrid; assert.ok(has(S, 'ifr_lkx', 'stX' + g.x) && has(S, 'ifr_lky', 'stY' + g.y), 'centred on a target straight ahead');
  tgt.pos = { x: 2450, y: 2950 * Math.tan(10 * Math.PI / 180), z: 0 }; draw();
  const p = H.ifrHudProject(me, tgt); assert.ok(Math.abs(p.x + 720 * Math.tan(10 * Math.PI / 180)) < 2 && Math.abs(p.y) < 2, 'projected ' + JSON.stringify(p));
  assert.ok(has(S, 'ifr_lkx', 'stX' + (g.x + Math.round(p.x / g.step))));
  tgt.pos = { x: 9900, y: 0, z: 0 }; draw(); assert.strictEqual(text(S, 'w2s'), 'OUT OF RANGE');
  tgt.pos = { x: 2450, y: 0, z: 0 }; me.weapons[2].cd = 4.2; draw(); assert.strictEqual(text(S, 'w2s'), 'READY IN 5 S');
  me.weapons[2].cd = 0; me.weapons[2].ammo = 0; draw(); assert.strictEqual(text(S, 'w2s'), 'NO AMMO');
  // multi-lock: hold to lock, release to fire, a diamond on each mech
  const ml = weapon(213, { mlock: [], mlDone: 0, mlHold: 0 }); me.weapons[3] = ml; ctx.game = { mechs: new Map([[2, Object.assign(tgt, { alive: true })]]) };
  draw(); assert.strictEqual(text(S, 'w3s'), 'HOLD TO LOCK');
  ml.mlHold = 0.2; draw(); assert.strictEqual(text(S, 'w3s'), 'NO TARGET IN RING');
  ml.mlock = [{ slot: 2, p: 0.4, done: false }]; draw(); assert.strictEqual(text(S, 'w3s'), 'KEEP HOLDING: 1'); assert.ok(has(S, 'ifr_ml0', 'stOn'));
  ml.mlock[0].done = true; ml.mlDone = 1; draw(); assert.strictEqual(text(S, 'w3s'), '1 LOCKED: RELEASE'); assert.ok(has(S, 'ifr_ml0', 'stDone') && !has(S, 'ifr_ml0', 'stOn'));
  ml.mlock = []; ml.mlDone = 0; ml.mlHold = 0; draw(); assert.ok(!has(S, 'ifr_ml0', 'stDone')); delete ctx.game;
});
test('overdrive block, buff badges, pilot plate and streak meter', () => {
  const S = 44; H.ifrHudOff(S); clear();
  const me = mech(S, 2, 0); me.overdrive = 0.62; me.odPhase = 0; me.sum = { kills: 4, deaths: 2, assists: 3 }; me.fkills = 2;
  const draw = () => { H.ifrHudVitals(S, me); H.ifrHudMode(S, match, 2); H.ifrHudTick(); };
  draw(); assert.strictEqual(text(S, 'odp'), '60 %'); assert.strictEqual(text(S, 'odl'), 'DEAL OR TAKE DAMAGE TO FILL'); assert.ok(!has(S, 'ifr_odready', 'stOn'));
  assert.strictEqual(text(S, 'pk'), '4'); assert.strictEqual(text(S, 'pd'), '2'); assert.strictEqual(text(S, 'pa'), '3'); assert.strictEqual(text(S, 'pmy'), '212'); assert.strictEqual(text(S, 'pen'), '178');
  assert.strictEqual(text(S, 'stk'), '2'); assert.strictEqual(text(S, 'str'), 'NEXT: 3 KILLS = RADAR PING'); assert.strictEqual(text(S, 'str2'), 'ENEMIES ON RADAR FOR 10 S'); assert.ok(has(S, 'ifr_l_skp', 'stL2'));
  me.overdrive = 1; draw(); assert.strictEqual(text(S, 'odl'), 'READY: HOLD SPACE + R + E'); assert.ok(has(S, 'ifr_odready', 'stOn'));
  me.odPhase = 1; me.odT = 0.8; draw(); assert.strictEqual(text(S, 'odl'), 'CHARGING: BLAST IN 0.8 S'); assert.ok(has(S, 'ifr_odready', 'stCharge') && has(S, 'ifr_odbar', 'stCharge') && !has(S, 'ifr_odready', 'stOn'));
  me.odPhase = 0; me.overdrive = 0; me.fkills = 5; me.artyReady = true; me.aceT = 0; me.radarT = 7.2; draw();
  assert.strictEqual(text(S, 'str'), 'NEXT: 8 KILLS = ACE'); assert.strictEqual(text(S, 'bfarty'), 'READY: LOCK A TARGET'); assert.strictEqual(text(S, 'bfradar'), '8 S: ENEMIES ON RADAR');
  me.fkills = 8; draw(); assert.strictEqual(text(S, 'str'), 'ACE EARNED: TOP REWARD');
  assert.strictEqual(H.ifrHudCutList().filter((c) => !/^g/.test(c)).join('; '), '', 'nothing cut (the garage strings of the test above are made up)');
});
test('panel ids: everything this harness drew names fewer ids than the budget (CS2 stops at 1024 per layout)', () => {
  console.log('  panel ids referenced by this harness: ' + idsSeen.size + ' of ' + Object.keys(HUD.panels).length + ' in the layout (budget ' + HUD.ids.budget + ', CS2 cap ' + HUD.ids.cap + ')');
  assert.ok(Object.keys(HUD.panels).length <= HUD.ids.budget, 'the layout has more ids than the budget');
  assert.ok(idsSeen.size <= 950);
  assert.strictEqual(H.ifrHudStats().ids, idsSeen.size, 'the driver counts the ids it names');
  for (const ts of Object.values(HUD.text_slots)) assert.ok(HUD.panels[ts.panel] && !ts.row, 'a text slot is one Label id: ' + ts.panel);
});
test('no HUD baked: every call is a no-op', () => {
  const c2 = { HUD: {}, PARTS, CONFIG: {}, Instance: ctx.Instance, console };
  vm.createContext(c2);
  const a = vm.runInContext(src + '\n;({ ifrHudInit, ifrHudSet, ifrHudVitals, ifrHudTick })', c2);
  a.ifrHudInit(); a.ifrHudSet(0, 'ifr_nope', 'stOn', true); a.ifrHudVitals(0, mech(0, 2, 0)); assert.strictEqual(a.ifrHudTick(), 0);
});
console.log(passed + ' test group(s) passed' + (process.exitCode ? ', with FAILURES' : ''));
