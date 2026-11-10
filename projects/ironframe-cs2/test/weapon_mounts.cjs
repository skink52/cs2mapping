// Weapon parenting (src/cs2/30_render.js): a weapon prop must end up at parent transform x mount, using the transform the ENGINE
// reports for the parent, whatever the script last asked for (10 Nov 2026 playtest: "shoulder weapons occasionally float").
// Runs the real functions against a small fake engine that models SetParent the way Source does (the child keeps its world offset
// at the moment of parenting and then follows the parent).   node test/weapon_mounts.cjs
const fs = require('fs'), path = require('path'), vm = require('vm');
const root = path.join(__dirname, '..');
const util = fs.readFileSync(path.join(root, 'src/cs2/10_util.js'), 'utf8');
const rend = fs.readFileSync(path.join(root, 'src/cs2/30_render.js'), 'utf8');
function fn(src, name) {           // the source text of `function name(...) {...}`
  const i = src.indexOf('function ' + name + '('); if (i < 0) throw new Error('no function ' + name);
  let d = 0, j = src.indexOf('{', i);
  for (; j < src.length; j++) { if (src[j] === '{') d++; else if (src[j] === '}') { d--; if (!d) break; } }
  return src.slice(i, j + 1);
}
let now = 0;
const ctx = { Math, Number, console, gameTime: () => now, warned: [], live: (e) => (e && e.valid !== false ? e : undefined) };
vm.createContext(ctx);
vm.runInContext('const D2R = Math.PI / 180, R2D = 180 / Math.PI; const ZERO_ANG = { pitch: 0, yaw: 0, roll: 0 }; function warnOnce(k, m) { warned.push(m); } let mountCheckOff = false;', ctx);
for (const n of ['v3', 'vsub', 'vdist', 'vfinite', 'fwdOf', 'rightOf', 'localToWorld', 'clampWorld']) vm.runInContext(fn(util, n), ctx);
for (const n of ['angAxes', 'propXform', 'xformPoint', 'propParentLocal', 'propParent', 'rigMountCheck']) vm.runInContext(fn(rend, n), ctx);

// ---- a fake engine entity: world transform, children keep their local offset
function axes(a) { return vm.runInContext('angAxes', ctx)(a); }
class Ent {
  constructor(p, a) { this.p = { ...p }; this.a = { ...a }; this.parent = null; this.local = null; }
  world() {
    if (!this.parent) return { p: this.p, a: this.a };
    const pw = this.parent.world(), ax = axes(pw.a), l = this.local;
    return { p: { x: pw.p.x + ax.f.x * l[0] + ax.l.x * l[1] + ax.u.x * l[2], y: pw.p.y + ax.f.y * l[0] + ax.l.y * l[1] + ax.u.y * l[2], z: pw.p.z + ax.f.z * l[0] + ax.l.z * l[1] + ax.u.z * l[2] }, a: pw.a };
  }
  GetAbsOrigin() { return { ...this.world().p }; }
  GetAbsAngles() { return { ...this.world().a }; }
  Teleport(v) { if (v.position) this.p = { ...v.position }; if (v.angles) this.a = { ...v.angles }; }
  Move(v) { this.Teleport(v); }
  SetParent(par) {
    if (!par) { const w = this.world(); this.p = { ...w.p }; this.a = { ...w.a }; this.parent = null; this.local = null; return; }
    const pw = par.world(), ax = axes(pw.a), d = { x: this.p.x - pw.p.x, y: this.p.y - pw.p.y, z: this.p.z - pw.p.z };
    this.local = [d.x * ax.f.x + d.y * ax.f.y + d.z * ax.f.z, d.x * ax.l.x + d.y * ax.l.y + d.z * ax.l.z, d.x * ax.u.x + d.y * ax.u.y + d.z * ax.u.z];
    this.parent = par;
  }
}
const prop = (p, a) => ({ ent: new Ent(p, a), lastPos: null, lastAng: null, tpRun: 0, parent: undefined, model: 'm' });
let fails = 0, checks = 0;
function near(a, b, tol, what) { checks++; const d = Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z); if (!(d <= tol)) { fails++; console.log('FAIL ' + what + ': off by ' + d.toFixed(2) + ' u', a, b); } }
const C = (name) => vm.runInContext(name, ctx);
const L = [-35.5, 62.0, 251.3];          // a shoulder mount

// 1. xformPoint agrees with localToWorld (pitch only) and its axes are orthonormal
for (const [pitch, yaw] of [[0, 0], [0, 73], [12, -140], [-25, 30]]) {
  near(C('xformPoint')({ o: { x: 100, y: -50, z: 20 }, a: { pitch, yaw, roll: 0 } }, L), C('localToWorld')({ x: 100, y: -50, z: 20 }, yaw, pitch, L), 1e-6, 'xformPoint vs localToWorld ' + pitch + '/' + yaw);
}
{ const ax = axes({ pitch: 17, yaw: 40, roll: -23 }); const dot = (a, b) => a.x * b.x + a.y * b.y + a.z * b.z;
  checks++; if (Math.abs(dot(ax.f, ax.l)) > 1e-9 || Math.abs(dot(ax.f, ax.u)) > 1e-9 || Math.abs(dot(ax.l, ax.u)) > 1e-9 || Math.abs(dot(ax.f, ax.f) - 1) > 1e-9) { fails++; console.log('FAIL axes not orthonormal'); } }

// 2. the mount holds wherever the parent ends up, also when the engine does NOT have the parent where the script put it
function expectAt(par, child, what) {
  for (const [p, a] of [[{ x: 500, y: 900, z: 64 }, { pitch: 0, yaw: 10, roll: 0 }], [{ x: -3000, y: 1200, z: 1500 }, { pitch: -18, yaw: 200, roll: 9 }]]) {
    par.ent.Teleport({ position: p, angles: a });
    near(child.ent.GetAbsOrigin(), C('xformPoint')({ o: p, a }, L), 0.01, what + ' after the parent moved to ' + JSON.stringify(p));
  }
}
{ // parent placed and reported in place
  const par = prop({ x: 10, y: 20, z: 30 }, { pitch: 0, yaw: 45, roll: 0 }); par.lastPos = { x: 10, y: 20, z: 30 }; par.lastAng = { pitch: 0, yaw: 45, roll: 0 };
  const ch = prop({ x: 0, y: 0, z: -15000 }, { pitch: 0, yaw: 0, roll: 0 });
  C('propParentLocal')(ch, par, L); expectAt(par, ch, 'placed parent');
}
{ // the script believes the parent is at the mech (lastPos), the engine still has it parked 15 000 u below (a placement that did not land)
  const par = prop({ x: 0, y: 0, z: -15000 }, { pitch: 0, yaw: 0, roll: 0 }); par.lastPos = { x: 800, y: 800, z: 200 }; par.lastAng = { pitch: 0, yaw: 90, roll: 0 };
  const ch = prop({ x: 0, y: 0, z: -15000 }, { pitch: 0, yaw: 0, roll: 0 });
  C('propParentLocal')(ch, par, L); expectAt(par, ch, 'parked parent');
}
{ // parented while the mech is pitched and rolled (a weapon the pool could only give a few ticks later)
  const a = { pitch: 14, yaw: -120, roll: -8 }; const par = prop({ x: 40, y: 2, z: 900 }, a); par.lastPos = { x: 40, y: 2, z: 900 }; par.lastAng = a;
  const ch = prop({ x: 0, y: 0, z: -15000 }, { pitch: 0, yaw: 0, roll: 0 });
  C('propParentLocal')(ch, par, L); expectAt(par, ch, 'pitched parent');
}
{ // the older call (garage preview): a world position for where the script placed the parent
  const a = { pitch: 0, yaw: 33, roll: 0 }, at = { x: -700, y: 350, z: 128 }; const par = prop(at, a); par.lastPos = at; par.lastAng = a;
  const ch = prop({ x: 0, y: 0, z: -15000 }, { pitch: 0, yaw: 0, roll: 0 });
  C('propParent')(ch, par, C('localToWorld')(at, 33, 0, L), a); expectAt(par, ch, 'propParent (world position)');
}

// 3. the one-off mount check: a weapon knocked off its mount is said in the log and put back; a good one is left alone
{ const a = { pitch: 0, yaw: 0, roll: 0 }; const par = prop({ x: 0, y: 0, z: 0 }, a); par.lastPos = { x: 0, y: 0, z: 0 }; par.lastAng = a;
  const good = prop({ x: 0, y: 0, z: 0 }, a), bad = prop({ x: 0, y: 0, z: 0 }, a);
  C('propParentLocal')(good, par, L); C('propParentLocal')(bad, par, [10, -60, 240]);
  bad.ent.local = [10, -60, 640];                                        // 400 u above its mount
  const r = { key: 'test_frame', upper: par, weapons: [good, bad, undefined, undefined], want: false, mountOk: false, upHid: false };
  now = 5; par.ent.Teleport({ position: { x: 300, y: 0, z: 0 }, angles: { pitch: 5, yaw: 60, roll: 0 } });
  C('rigMountCheck')(r);
  checks++; if (ctx.warned.length !== 1 || !/400 u off/.test(ctx.warned[0])) { fails++; console.log('FAIL drift not reported once:', ctx.warned); }
  near(bad.ent.GetAbsOrigin(), C('xformPoint')({ o: par.ent.GetAbsOrigin(), a: par.ent.GetAbsAngles() }, [10, -60, 240]), 0.01, 'drifted weapon put back');
  near(good.ent.GetAbsOrigin(), C('xformPoint')({ o: par.ent.GetAbsOrigin(), a: par.ent.GetAbsAngles() }, L), 0.01, 'good weapon untouched');
  checks++; if (!r.mountOk) { fails++; console.log('FAIL mount check did not finish'); }
}

// 4. rigFill: a rig the pool could not complete at claim time is completed on later ticks (it used to stay without the missing
//    upper body / weapon for the mech's whole life), and nothing is mounted again after the upper body was hidden (gibs)
{ let budget = 0; const taken = [];
  ctx.takeProp = () => { if (budget <= 0) return undefined; budget--; const p = prop({ x: 0, y: 0, z: -15000 }, { pitch: 0, yaw: 0, roll: 0 }); taken.push(p); return p; };
  ctx.propModel = (p, m) => { p.model = m; }; ctx.propColor = () => {}; ctx.releaseProp = (p) => { p.released = true; };
  ctx.propPlace = (p, pos, ang) => { p.ent.Teleport({ position: pos, angles: ang }); p.lastPos = pos; p.lastAng = ang; };
  vm.runInContext('const FX_MODELS = {}, NULL_MODEL = "null", WEAPON_MODELS = { rifle: "w/rifle", vm6: "w/vm6" }; function weaponMountPos(k, w, i) { return [10 * i, i % 2 ? 50 : -50, 200]; }', ctx);
  vm.runInContext(fn(rend, 'pivotOrigin'), ctx); vm.runInContext(fn(rend, 'rigFill'), ctx);
  const m = { pos: { x: 100, y: 200, z: 0 }, torsoYaw: 30, legYaw: 0, alive: true, weapons: [{ part: { key: 'rifle' } }, null, { part: { key: 'vm6' } }, { part: { key: 'vm6' } }] };
  const r = { key: 'f', fr: { upper: 'f_upper', legs: 'f_legs', pivot: [5, 0] }, upper: undefined, legs: undefined, weapons: [undefined, undefined, undefined, undefined], paint: null, want: true };
  const count = () => r.weapons.filter(Boolean).length;
  const tick = (b, what, exp) => { budget = b; C('rigFill')(r, m); checks++; const got = [!!r.upper, !!r.legs, count(), r.want].join(' '); if (got !== exp) { fails++; console.log('FAIL rigFill ' + what + ': ' + got + ' (wanted ' + exp + ')'); } };
  tick(0, 'empty pool', 'false false 0 true');
  tick(1, 'one prop: the upper body', 'true false 0 true');
  tick(2, 'legs + one weapon', 'true true 1 true');
  tick(5, 'the rest', 'true true 3 false');
  near(r.weapons[2].ent.GetAbsOrigin(), C('xformPoint')({ o: r.upper.ent.GetAbsOrigin(), a: r.upper.ent.GetAbsAngles() }, [20, -50, 200]), 0.01, 'late weapon on its mount');
  r.weapons[0] = undefined; r.upHid = true; r.want = true;
  tick(5, 'hidden upper body: nothing mounted', 'true true 2 false');
}
console.log((fails ? 'FAILED ' : 'ok ') + (checks - fails) + '/' + checks + ' weapon mount checks');
process.exit(fails ? 1 : 0);
