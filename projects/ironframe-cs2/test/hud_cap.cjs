// test/hud_cap.cjs: the HUD byte budget (24 Nov 2026; src/cs2/50_hud.js "Packed-size budget"). The live JB box crashed when CS2's
// serializer ran out of room packing the layout entity (every player's classes and texts plus the panel-id and class-name tables),
// so the driver keeps its own estimate under CONFIG.HUD_PACK_BUDGET bytes, all players together.
// usage: node test/hud_cap.cjs     (needs out/addon/_gen/hud.json from tools/hud.py)
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const root = path.join(__dirname, '..');
const HUD = JSON.parse(fs.readFileSync(path.join(root, 'out/addon/_gen/hud.json'), 'utf8'));
const PARTS = JSON.parse(fs.readFileSync(path.join(root, 'data/parts.json'), 'utf8'));
const BUDGET = 2000;   // bytes (CONFIG.HUD_PACK_BUDGET)

const on = new Map();           // slot|panel|class -> true: what the engine has switched on
const count = () => on.size;
let TWO = false;                // the last test adds a second layout copy (ifr_hud2)
const on2 = new Map();
const ent2 = {
  IsValid() { return true; }, Reset() { on2.clear(); },
  ResetForPlayer(slot) { for (const k of [...on2.keys()]) if (k.startsWith(slot + '|')) on2.delete(k); },
  SetInputCaptureEnabled() {},
  SetHasClassForPlayer(slot, id, cls, v) { const k = slot + '|' + id + '|' + cls; if (v) on2.set(k, true); else on2.delete(k); },
  SetDialogVariableStringForPlayer() {},
};
const ent = {
  IsValid() { return true; }, Reset() { on.clear(); },
  ResetForPlayer(slot) { for (const k of [...on.keys()]) if (k.startsWith(slot + '|')) on.delete(k); },
  SetInputCaptureEnabled() {},
  SetHasClassForPlayer(slot, id, cls, v) { if (!HUD.panels[id]) throw new Error('no panel ' + id); const k = slot + '|' + id + '|' + cls; if (v) on.set(k, true); else on.delete(k); },
  SetDialogVariableStringForPlayer() {},
};
const ctx = { HUD, PARTS, ARENA: { points: [], drops: null }, CONFIG: { HUD: 'ifr_hud', HUD_BUDGET: 100000, HUD_PACK_BUDGET: BUDGET },
  Entities: { FindByName: (n) => (n === 'ifr_hud' ? [ent] : n === 'ifr_hud2' && TWO ? [ent2] : []), FireInput() {} }, Console: { Log() {}, ServerCommand() {} }, GameRules: { IsWarmupPeriod: () => false },
  Instance: { FindEntityByName: () => ent, GetGameTime: () => 100, Msg() {} }, console };
vm.createContext(ctx);
const src = fs.readFileSync(path.join(root, 'src/cs2/50_hud.js'), 'utf8');
const H = vm.runInContext(src + '\n;({ ifrHudInit, ifrHudSet, ifrHudTick, ifrHudOff, ifrHudPending, ifrHudRadar, ifrHudBudgetStats })', ctx);
let passed = 0;
function test(name, fn) { try { fn(); passed++; console.log('ok   ' + name); } catch (e) { console.log('FAIL ' + name + ': ' + (e.stack || e)); process.exitCode = 1; } }

H.ifrHudInit();
// distinct (panel, class) pairs from the radar's 12 columns (stGx0..23) and 12 items (stGy0..23): 576 in all (24 Nov 2026: the radar
// went from one cell class stG0..575 to a column + row class each)
const RP = (i) => (i % 576) < 288 ? ['ifr_rd' + (i % 12), 'stGx' + (Math.floor(i / 12) % 24)] : ['ifr_rd' + (i % 12) + 'y', 'stGy' + (Math.floor((i % 576 - 288) / 12) % 24)];
test('four players asking for 300 classes each stay under the byte budget together', () => {
  for (let sl = 0; sl < 4; sl++) for (let i = 0; i < 300; i++) H.ifrHudSet(sl, ...RP(i), true);
  H.ifrHudTick(); H.ifrHudTick();
  const st = H.ifrHudBudgetStats();
  assert.ok(st.bytes <= BUDGET, st.bytes + ' bytes, budget ' + BUDGET);
  assert.ok(st.bytes > BUDGET * 0.9, 'the room is used: ' + st.bytes);
  assert.strictEqual(st.classes, count());                  // the driver's count matches what the engine has on
  // (under 80 % of the budget nobody is held to a share, so the first served may get all of theirs; the others wait)
  assert.ok([0, 1, 2, 3].filter((sl) => H.ifrHudPending(sl) > 0).length >= 2, 'players have classes waiting');
});
test('screen states (priority 0) always go out', () => {
  H.ifrHudSet(0, 'ifr_root', HUD.panels.ifr_root.classes[0], true); H.ifrHudTick();
  assert.ok(on.has('0|ifr_root|' + HUD.panels.ifr_root.classes[0]));
});
test('a player leaving frees room: the waiting classes of the others go out', () => {
  // the player holding the most classes leaves (under 80 % of the budget nobody is held to a share, so the first served fill it)
  const per = [0, 1, 2, 3].map((sl) => [...on.keys()].filter((k) => k.startsWith(sl + '|')).length);
  const big = per.indexOf(Math.max(...per)), rest = [0, 1, 2, 3].filter((sl) => sl !== big);
  const pend = () => rest.reduce((n, sl) => n + H.ifrHudPending(sl), 0);
  const before = pend();
  H.ifrHudOff(big); H.ifrHudTick(); H.ifrHudTick();
  const after = pend();
  assert.ok(after < before, 'waiting ' + before + ' -> ' + after);
  assert.ok(H.ifrHudBudgetStats().bytes <= BUDGET, H.ifrHudBudgetStats().bytes + ' bytes');
});
test('the radar draws the nearest 12 mechs only', () => {
  for (const sl of [1, 2, 3]) H.ifrHudOff(sl);
  on.clear();
  const dots = []; for (let i = 0; i < 60; i++) dots.push({ x: (60 - i) * 300, y: 0, team: 2, kind: 'mech' });
  H.ifrHudRadar(9, dots, 0, { x: 0, y: 0, z: 0 }); H.ifrHudTick();
  const shown = new Set([...on.keys()].filter((k) => k.startsWith('9|ifr_rd') && /\|stGx\d+$/.test(k)).map((k) => k.split('|')[1]));
  assert.ok(shown.size <= 12, shown.size + ' radar dots');
});
test('two layout copies: players split between them, each copy under the budget, twice the room', () => {
  for (const sl of [0, 9]) H.ifrHudOff(sl);
  on.clear(); TWO = true; H.ifrHudInit();
  const slots = [10, 11, 12, 13];
  for (const sl of slots) for (let i = 0; i < 300; i++) H.ifrHudSet(sl, ...RP(i), true);
  H.ifrHudTick(); H.ifrHudTick(); H.ifrHudTick();
  const st = H.ifrHudBudgetStats();
  assert.strictEqual(st.copies.length, 2, 'two copies found');
  for (const c of st.copies) { assert.strictEqual(c.players, 2, c.name + ' serves two players'); assert.ok(c.bytes <= BUDGET, c.name + ': ' + c.bytes + ' bytes'); }
  assert.ok(st.bytes > BUDGET, 'more room than one copy: ' + st.bytes);
  const s1 = new Set([...on.keys()].map((k) => k.split('|')[0])), s2 = new Set([...on2.keys()].map((k) => k.split('|')[0]));
  for (const sl of s1) assert.ok(!s2.has(sl), 'slot ' + sl + ' is on one copy only');
  assert.strictEqual(s1.size + s2.size, 4, 'every player is on a copy');
});
console.log(passed + ' test group(s) passed' + (process.exitCode ? ', with FAILURES' : ''));
