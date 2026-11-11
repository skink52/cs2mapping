// test/hud_garage_turn.cjs: the garage preview faces the camera, turns with the buttons under its feet and with E / R, eases, and goes back to
// the front when the frame changes; the camera keeps the feet just above the buttons (10 Nov 2026 evening playtest).
// usage: node test/hud_garage_turn.cjs     (needs out/addon/_gen/hud.json from tools/hud.py)
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const root = path.join(__dirname, '..');
const read = (f) => fs.readFileSync(path.join(root, f), 'utf8');
const HUD = JSON.parse(read('out/addon/_gen/hud.json')), PARTS = JSON.parse(read('data/parts.json'));
const stub = new Proxy(function () {}, { get: (t, k) => (k === Symbol.toPrimitive ? () => 0 : stub), apply: () => stub, construct: () => stub });
let now = 100;
const D2R = Math.PI / 180;
const KEYS = { left: 4, right: 8, ra: 256, rs: 1024, ls: 128 };
const held = new Set();
const pawn = { IsValid: () => true, IsAlive: () => true, IsInputPressed: (k) => held.has(k), WasInputJustPressed: () => false };
const placed = [], cams = [];
const BAY_YAW = 135, BAY = { x: 1000, y: -2000, z: 64 };
const ent = { IsValid() { return true; }, ResetForPlayer() {}, SetInputCaptureEnabled() {}, IsInputCaptureEnabled: () => true, SetHasClassForPlayer() {}, GetAbsOrigin: () => BAY, GetAbsAngles: () => ({ pitch: 0, yaw: BAY_YAW, roll: 0 }) };
const fwdOf = (yaw, pitch) => { const cp = Math.cos(pitch * D2R); return { x: Math.cos(yaw * D2R) * cp, y: Math.sin(yaw * D2R) * cp, z: -Math.sin(pitch * D2R) }; };
const normAngle = (a) => { a = a % 360; if (a > 180) a -= 360; if (a < -180) a += 360; return a; };
const FRAMES = new Proxy({}, { get: (t, k) => ({ upper: 'models/' + String(k) + '_upper.vmdl', legs: 'models/' + String(k) + '_legs.vmdl', hardpoints: { ra: [40, -70, 60], la: [40, 70, 60], rs: [-20, -50, 120], ls: [-20, 50, 120] } }) });
const base = { HUD, PARTS, console, KEYS, FRAMES, WEAPON_MODELS: {}, PAINTS: {}, FX_MODELS: {}, NULL_MODEL: '', serverMode: false, MK: { up: 1, down: 2, left: 4, right: 8, ok: 16, back: 32, cycle: 64, fire: 128, fire2: 256, use: 512 },
  Entities: { FindByName: () => (ent ? [ent] : []), FireInput() {} }, Console: { Log() {}, ServerCommand() {} }, GameRules: { IsWarmupPeriod: () => false }, Instance: { FindEntityByName: () => ent, GetGameTime: () => now, Msg() {}, TraceLine: () => ({ didHit: false, fraction: 1 }) }, ARENA: { name: 'Sprawl' }, CONFIG: { HUD: 'ifr_hud', BAY_CAMERA_YAW: { 1: BAY_YAW } },
  gameTime: () => now, guard: (w, f) => f(), live: (e) => e, v3: (x, y, z) => ({ x, y, z }), fwdOf, normAngle, log() {}, warnOnce() {}, sndTone() {}, revivePawn() {}, menuKeys: () => 0,
  ifrFind: (n) => (n === 'ifr_bay_1' ? ent : undefined), localToWorld: (o) => o, weaponMountPos: (k, w, i, hp) => hp,
  takeProp: () => ({ id: placed.length }), releaseProp() {}, propModel() {}, propParent() {}, propColor() {},
  propPlace: (p, pos, ang) => { placed.push({ p, pos, yaw: ang.yaw }); }, controlledCamera: (pe, pos, look) => { cams.push({ pos, look }); },
  game: { events: [], garage: { describe: () => ({ rows: [] }), budgets: () => ({ weight: 1, load: 2, en: 1, output: 2, valid: true, deny: 0 }) }, setPilot() {}, pilotSummary: () => ({}) }, DENY_TEXT: {} };
vm.createContext(base);
const prog = read('src/core/70_progress.js');
const coreFns = ['IF_upgradeCost', 'IF_tierName'].map((n) => { const i = prog.indexOf('function ' + n + '('); const one = prog.indexOf('\n', i), body = prog.indexOf('\n}\n', i); return prog.slice(i, prog.slice(i, one).trim().endsWith('}') ? one : body + 2); }).join('\n');
const src = coreFns + '\n' + read('src/cs2/50_hud.js') + '\n' + read('src/cs2/60_garage.js') + '\n' + read('src/cs2/70_server.js');
Object.assign(base, require('./lib.cjs').careerGlobals(), { people: new Map(), person: () => undefined }); vm.createContext(base);
for (let i = 0; i < 40; i++) {
  try { vm.runInContext(src + '\n;this.__api = { garageOpen, garageTick, garageClick, garageRows, garageFront, GARAGE_TURN, IFR_HUD_FOCAL, ifrHudInit, GARAGE_TABS };', base); break; }
  catch (e) { const m = /(\w+) is not defined/.exec(e.message); if (!m) throw e; base[m[1]] = stub; vm.createContext(base); }
}
const A = base.__api; A.ifrHudInit();
let passed = 0;
function test(name, fn) { try { fn(); passed++; console.log('ok   ' + name); } catch (e) { console.log('FAIL ' + name + ': ' + (e.stack || e)); process.exitCode = 1; } }
const pe = { slot: 3, human: true, status: 'dead', pawn, pilot: null, garage: null };
const yawNow = () => placed[placed.length - 1].yaw;
const run = (secs) => { for (let t = 0; t < secs; t += 1 / 64) { now += 1 / 64; A.garageTick(pe); } };
const near = (a, b, tol, msg) => assert.ok(Math.abs(normAngle(a - b)) <= tol, (msg || '') + ' ' + a + ' vs ' + b);

test('the mech faces the camera when the garage opens, and stays (no idle spin)', () => {
  A.garageOpen(pe, ''); run(0.2);
  near(yawNow(), BAY_YAW, 0.01, 'opening yaw');
  const c = cams[cams.length - 1], f = fwdOf(BAY_YAW, 0);
  // the camera stands on the side the mech looks at
  assert.ok((c.pos.x - BAY.x) * f.x + (c.pos.y - BAY.y) * f.y > 300, 'camera in front of the mech');
  run(6); near(yawNow(), BAY_YAW, 0.01, 'after 6 s idle');
});
test('the camera keeps the feet GARAGE_TURN.feetPx under the screen centre (the turn buttons sit below them)', () => {
  const c = cams[cams.length - 1];
  const d = Math.hypot(c.pos.x - BAY.x, c.pos.y - BAY.y), pitch = Math.atan2(c.pos.z - c.look.z, d);          // camera looks down by `pitch`
  const feet = Math.atan2(c.pos.z - BAY.z, d);                                                                  // the feet are this far under the horizon
  const px = A.IFR_HUD_FOCAL * Math.tan(feet - pitch);
  assert.ok(Math.abs(px - A.GARAGE_TURN.feetPx) < 1.5, 'feet at ' + px.toFixed(1) + ' px under the centre');
  assert.ok(540 + px < 686, 'above the turn buttons (y 686 in tools/hud.py)');
});
test('a click on a turn button turns 45 degrees, eased; FRONT comes back', () => {
  A.garageClick(pe, 'ifr_grr'); run(1 / 64); const first = normAngle(yawNow() - BAY_YAW);
  assert.ok(first > 0 && first < 15, 'eased, not a jump: ' + first);
  run(1.5); near(yawNow(), BAY_YAW + 45, 0.1, 'after the right button');
  A.garageClick(pe, 'ifr_grl'); A.garageClick(pe, 'ifr_grl'); run(1.5); near(yawNow(), BAY_YAW - 45, 0.1, 'two clicks left');
  A.garageClick(pe, 'ifr_grf'); run(1.5); near(yawNow(), BAY_YAW, 0.1, 'FRONT');
});
test('the mouse button held on a turn button keeps turning; letting go stops', () => {
  A.garageClick(pe, 'ifr_grr'); held.add(KEYS.ra); run(0.75); held.delete(KEYS.ra); run(0.8);
  const turned = normAngle(yawNow() - BAY_YAW); assert.ok(turned > 90 && turned < 170, 'kept turning past the 45 degree step: ' + turned);
  run(0.6); const a = yawNow(); run(1); near(yawNow(), a, 0.1, 'stopped');
  A.garageClick(pe, 'ifr_grf'); run(2);
});
test('E / R held turn it in any column; A / D only in the tabs column', () => {
  for (const col of [0, 1, 2]) {
    pe.garage.col = col; A.garageClick(pe, 'ifr_grf'); run(1.5);
    held.add(KEYS.rs); run(0.5); held.delete(KEYS.rs); run(1); assert.ok(normAngle(yawNow() - BAY_YAW) > 40, 'R turns right in column ' + col);
    held.add(KEYS.ls); run(1); held.delete(KEYS.ls); run(1); assert.ok(normAngle(yawNow() - BAY_YAW) < -40, 'E turns left in column ' + col);
  }
  pe.garage.col = 1; A.garageClick(pe, 'ifr_grf'); run(1.5); held.add(KEYS.right); run(0.5); held.delete(KEYS.right); run(1); near(yawNow(), BAY_YAW, 0.1, 'D is list navigation in the list');
  pe.garage.col = 0; held.add(KEYS.right); run(0.5); held.delete(KEYS.right); run(1); assert.ok(normAngle(yawNow() - BAY_YAW) > 40, 'D turns in the tabs');
});
test('another frame: the mech faces the camera again', () => {
  const frames = PARTS.parts.filter((p) => p.kind === 'frame' && !p.pve);
  pe.garage.draft[0] = frames.find((f) => f.id !== pe.garage.draft[0]).id; run(1.5);
  near(yawNow(), BAY_YAW, 0.1, 'after the frame changed');
});
test('the frame list is by class with the Tripo frames first in each', () => {
  const g = pe.garage; g.tab = A.GARAGE_TABS.findIndex((t) => t.key === 'frm'); A.garageRows(pe);
  const rows = g.rows.map((r) => r.part), cls = rows.map((p) => p.class);
  assert.deepStrictEqual(Array.from(cls), Array.from(cls).sort((a, b) => ['light', 'medium', 'heavy'].indexOf(a) - ['light', 'medium', 'heavy'].indexOf(b)), 'by class');
  for (const c of ['light', 'medium', 'heavy']) { const of = rows.filter((p) => p.class === c), tr = of.filter((p) => /^tripo_/.test(p.model)); if (tr.length) assert.ok(of.indexOf(tr[tr.length - 1]) === tr.length - 1, 'Tripo first in ' + c); }
  const firstTripo = rows.findIndex((p) => /^tripo_/.test(p.model)); assert.ok(firstTripo >= 0 && firstTripo < 8, 'a Tripo frame on the first page');
});
console.log(passed + ' test group(s) passed' + (process.exitCode ? ', with FAILURES' : ''));
