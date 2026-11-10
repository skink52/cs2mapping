// Frame auras (src/cs2/47_auras.js + data/parts.json#auras + out/addon/_gen/auras.json). usage: node test/auras.cjs
// Runs the adapter file in a sandbox with a stand-in prop pool and rig table: data integrity, LOD tiers and caps, the prop
// budget and pool reserve, claim rate, flare sequences, holds, the overdrive level, pilot dimming, polled conditions,
// one-off afterimages, release on death / rig change / reset.
const fs = require('fs'), path = require('path'), vm = require('vm');
const ROOT = path.join(__dirname, '..');
const PARTS = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'parts.json'), 'utf8'));
const GEN = path.join(ROOT, 'out', 'addon', '_gen', 'auras.json');
let fails = 0, passes = 0;
function ok(cond, name, info) { if (cond) passes++; else { fails++; console.log('FAIL ' + name + (info !== undefined ? ': ' + info : '')); } }
if (!fs.existsSync(GEN)) { console.log('auras: ' + GEN + ' missing (python -I tools/auras.py)'); process.exit(1); }
const AURAS = JSON.parse(fs.readFileSync(GEN, 'utf8'));
const FRAMES = new Map(PARTS.parts.filter((p) => p.kind === 'frame').map((p) => [p.key, p]));
const SPECS = Object.entries(PARTS.auras || {}).filter(([k]) => k[0] !== '_');

// ---------------------------------------------------------------- data
function hueOf(c) {
  const [r, g, b] = c.map((x) => x / 255), mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
  if (d < 1e-6) return { h: 0, s: 0 };
  let h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  h *= 60; if (h < 0) h += 360;
  return { h, s: d / mx };
}
const IFF = { T: [255, 140, 40], CT: [40, 200, 255], red: [255, 50, 50] };
for (const [key, sp] of SPECS) {
  const fr = FRAMES.get(key);
  ok(!!fr, key + ' is a frame part key');
  ok(!!(AURAS.frames && AURAS.frames[key]), key + ' has generated models');
  const gen = (AURAS.frames || {})[key] || { parts: {} };
  ok(!!sp.parts[sp.reduced], key + ' reduced part exists', sp.reduced);
  for (const [pid, pd] of Object.entries(sp.parts)) {
    for (const s of pd.states) ok(!!(gen.parts[pid] && gen.parts[pid].states[s]), key + '.' + pid + '.' + s + ' has a model');
    ok(pd.idle === null || pd.states.includes(pd.idle), key + '.' + pid + ' idle state listed', pd.idle);
  }
  for (const f of sp.flares || []) {
    if (f.part) { ok(!!sp.parts[f.part], key + ' flare part ' + f.part); for (const [s] of f.seq) ok(s === '' || sp.parts[f.part].states.includes(s), key + ' flare state ' + s); }
    if (f.fx) ok(!!(f.fx_part && sp.parts[f.fx_part] && sp.parts[f.fx_part].attach === 'none'), key + ' fx part ' + f.fx_part);
    if (f.pfx) ok(!!(AURAS.pools && AURAS.pools[f.pfx]), key + ' particle pool ' + f.pfx);
  }
  for (const h of sp.holds || []) ok(sp.parts[h.part] && sp.parts[h.part].states.includes(h.state), key + ' hold ' + h.part + '.' + h.state);
  // colour: not the IFF's team hues (saturated colours at least 14 degrees away from T orange, CT cyan and red)
  const c = hueOf(sp.color);
  if (c.s > 0.35) for (const [t, ic] of Object.entries(IFF)) { const ih = hueOf(ic).h; const dh = Math.min(Math.abs(c.h - ih), 360 - Math.abs(c.h - ih)); ok(dh >= 14, key + ' colour clear of IFF ' + t, Math.round(c.h) + ' vs ' + Math.round(ih)); }
}
for (const fr of FRAMES.values()) if (fr.trait) ok(SPECS.some(([k]) => k === fr.key), 'trait frame ' + fr.key + ' has an aura');

// ---------------------------------------------------------------- sandbox
const src = fs.readFileSync(path.join(ROOT, 'src', 'cs2', '47_auras.js'), 'utf8') +
  '\nthis.__a = { auraSt, auraStats, AURA_CFG, AURA_SPEC, auraFx, used: () => auraUsed, fxLive: () => auraFxLive };\n';
function sandbox(cfgOver) {
  const S = {};
  let serial = 0;
  const free = [];
  const log = [];
  function ent(name) {
    return { name, parent: null, model: '', color: null, scale: 1, pos: null, IsValid: () => true,
      Teleport(o) { this.pos = o.position; log.push(['tp', name]); }, SetParent(p) { this.parent = p || null; log.push(['parent', name, p ? 'set' : 'clear']); },
      SetModel(m) { this.model = m; }, SetColor(c) { this.color = c; }, SetModelScale(s) { this.scale = s; } };
  }
  S.ctx = {
    console, Math, Object, Number, Array, Map, Set, Infinity, JSON, String, Boolean,
    CONFIG: { MAX_POOL: 900, AURA: Object.assign({}, { on: true, fullDist: 4000, reducedDist: 9000, fullCap: 40, reducedCap: 32, maxProps: 160, reserve: 60, claimsPerTick: 6, every: 16, poll: 4, ghosts: 12, hyst: 400 }, cfgOver || {}) },
    PARTS, AURAS, PFX_POOLS: { boost: 128 }, rigs: new Map(), game: { mechs: new Map() }, people: new Map(),
    propCount: 0, ifrTickNo: 0, now: 0, ZERO_ANG: { pitch: 0, yaw: 0, roll: 0 }, NULL_MODEL: 'models/ifr/null.vmdl', R2D: 180 / Math.PI,
    bursts: [],
  };
  const C = S.ctx;
  C.gameTime = () => C.now;
  C.guard = (w, fn) => { try { return fn(); } catch (e) { console.log('guard ' + w + ': ' + e.stack); fails++; return undefined; } };
  C.live = (e) => e;
  C.v3 = (x, y, z) => ({ x, y, z }); C.vsub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z }); C.vlen = (a) => Math.hypot(a.x, a.y, a.z);
  C.vdist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z); C.clampWorld = (p) => p;
  C.takeProp = () => { if (free.length) return free.pop(); C.propCount++; const n = 'p' + (++serial); return { ent: ent(n), name: n, model: '', hidden: true, lastPos: null, lastAng: null, tpRun: 0, scale: 1, color: '', parent: undefined }; };
  C.releaseProp = (p) => { if (p.parent) { p.ent.SetParent(undefined); p.parent = undefined; } p.scale = 1; p.color = ''; p.model = C.NULL_MODEL; p.ent.model = C.NULL_MODEL; free.push(p); };
  // 30_render.js propParentLocal: the child goes onto the parent's transform (+ a local offset), then SetParent
  C.propParentLocal = (p, parent, local) => { if (p.parent === parent) return true; if (!parent.lastPos) return false; p.ent.Teleport({ position: parent.lastPos, angles: parent.lastAng }); p.lastPos = parent.lastPos; p.ent.SetParent(parent.ent); p.parent = parent; return true; };
  C.HIDE_POS = { x: 0, y: 0, z: -15000 };
  C.propModel = (p, m) => { if (p.model === m || !m) return; p.ent.SetModel(m); p.model = m; p.hidden = false; };
  C.propColor = (p, rgb) => { const k = rgb ? rgb.join(',') : ''; if (p.color === k) return; p.ent.SetColor(rgb); p.color = k; };
  C.propScale = (p, s) => { p.ent.SetModelScale(s); p.scale = s; };
  C.pfxBurst = (kind, pos) => C.bursts.push(kind);
  vm.createContext(C);
  vm.runInContext(src, C, { filename: '47_auras.js' });
  S.A = C.__a; S.log = log; S.free = free;
  S.mech = (slot, key, x, y, human) => {
    const fr = FRAMES.get(key);
    const m = { slot, alive: true, frame: fr, pos: { x, y, z: 0 }, cls: { height: 288 }, weapons: [null, null, null, null], overdrive: 0, assault: false, trT: { wind: 0 }, lock: { target: -1 } };
    C.game.mechs.set(slot, m);
    const mk = (n) => ({ ent: ent(n), name: n, model: 'm', lastPos: { x, y, z: 0 }, lastAng: { pitch: 0, yaw: 0, roll: 0 }, hidden: false });
    C.rigs.set(slot, { slot, upper: mk('up' + slot), legs: mk('lg' + slot) });
    if (human) C.people.set(slot, { slot, human: true, deathPos: null });
    return m;
  };
  S.tick = (n) => { for (let i = 0; i < (n || 1); i++) { C.ifrTickNo++; C.now += 1 / 64; C.auraTick(); } };
  S.part = (slot, pid) => { const st = S.A.auraSt.get(slot); return st && st.parts[pid]; };
  S.model = (slot, pid) => { const p = S.part(slot, pid); return p && p.prop ? p.prop.model : ''; };
  return S;
}
const KEYS = SPECS.map(([k]) => k);

// ---------------------------------------------------------------- LOD tiers, caps, budget, claim rate
{
  const S = sandbox(); const C = S.ctx;
  S.mech(0, 'lisa', 0, 0, true); S.mech(1, 'ogre', 30000, 0, true);
  let slot = 64;
  for (let i = 0; i < 110; i++) S.mech(slot++, KEYS[i % KEYS.length], (i % 11) * 900 - 4500, Math.floor(i / 11) * 900 - 4500, false);
  let maxStep = 0, prev = 0;
  for (let t = 0; t < 200; t++) { S.tick(); const u = S.A.used(); maxStep = Math.max(maxStep, u - prev); prev = u; }
  const sts = [...S.A.auraSt.values()];
  const t2 = sts.filter((s) => s.tier === 2 && !s.human), t1 = sts.filter((s) => s.tier === 1);
  ok(S.A.auraSt.get(0).tier === 2 && S.A.auraSt.get(1).tier === 2, 'humans own mechs are full');
  ok(t2.length <= C.CONFIG.AURA.fullCap, 'full cap', t2.length);
  ok(t1.length <= C.CONFIG.AURA.reducedCap, 'reduced cap', t1.length);
  ok(t2.every((s) => s.dist < 4000 + 400), 'full tier within fullDist');
  ok(sts.filter((s) => s.tier === 0).every((s) => s.dist > 4000 || t2.length >= 40), 'tier 0 only beyond range or caps');
  ok(S.A.used() <= C.CONFIG.AURA.maxProps, 'prop budget', S.A.used());
  ok(maxStep <= C.CONFIG.AURA.claimsPerTick, 'claims per tick', maxStep);
  ok(sts.filter((s) => s.tier >= 1).every((s) => !s.dirty), 'every wanted part got a prop', sts.filter((s) => s.dirty).length);
  ok(t1.every((s) => Object.values(s.parts).filter((p) => p.prop).length <= 1), 'reduced tier keeps one part');
  const props = sts.flatMap((s) => Object.values(s.parts).filter((p) => p.prop));
  ok(props.every((p) => p.prop.parent && p.prop.ent.parent), 'every aura prop is parented');
  ok(props.every((p) => p.prop.model.indexOf('models/ifr/aura/') === 0), 'aura models only');
  const far = sts.find((s) => s.slot === 1); ok(far && far.dist === 0, 'own position counts as a human');
  // budget: a tiny maxProps downgrades the farthest first
  const S2 = sandbox({ maxProps: 10 });
  for (let i = 0; i < 30; i++) S2.mech(64 + i, 'krasnaya', i * 100, 0, false);
  S2.mech(0, 'krasnaya', 0, 0, true);
  S2.tick(80);
  ok(S2.A.used() <= 10, 'small budget respected', S2.A.used());
  ok(S2.A.auraSt.get(0).tier === 2, 'human first under a small budget');
  const tiers = [...S2.A.auraSt.values()].sort((a, b) => a.dist - b.dist).map((s) => s.tier);
  ok(tiers.every((t, i) => i === 0 || t <= tiers[i - 1] || tiers[i - 1] === 2), 'tiers fall with distance', tiers.join(''));
  // pool reserve: nothing new when the shared pool is nearly full
  const S3 = sandbox(); S3.ctx.propCount = 870; S3.mech(0, 'lisa', 0, 0, true); S3.tick(40);
  ok(S3.A.used() === 0, 'pool reserve blocks claims', S3.A.used());
}

// ---------------------------------------------------------------- flares, holds, level, dimming, polls, fx, release
{
  const S = sandbox(); const C = S.ctx;
  S.mech(0, 'lisa', 0, 0, true); S.mech(64, 'lisa', 500, 0, false); S.mech(65, 'legion', 600, 0, false); S.mech(66, 'unicorn', 700, 0, false);
  S.mech(67, 'rx78', 800, 0, false); S.mech(68, 'ronin', 900, 0, false); S.mech(69, 'whiteglint', 1000, 0, false); S.mech(70, 'barbatos', 1100, 0, false);
  S.tick(40);
  ok(/wings_fold/.test(S.model(64, 'wings')), 'lisa idle folded', S.model(64, 'wings'));
  const seen = [];
  C.auraEvent({ t: 'trait', slot: 64, key: 'lisa', phase: 'fire' });
  for (let i = 0; i < 110; i++) { const m = S.model(64, 'wings').replace(/.*wings_|\.vmdl/g, ''); if (seen[seen.length - 1] !== m) seen.push(m); S.tick(); }
  ok(seen.join(',') === 'half,spread,flare,spread,half,fold', 'lisa double-jump sequence', seen.join(','));
  // pilot dimming: the human's own wings are dimmer than the AI's
  const kh = S.part(0, 'wings').k, ka = S.part(64, 'wings').k;
  ok(kh < ka && Math.abs(kh - Math.round(ka * PARTS.auras.lisa.cam * 16) / 16) < 0.07, 'pilot cam dimming', kh + ' vs ' + ka);
  // hold: legion's wall exists only while the trait is on
  ok(!S.part(65, 'wall').prop, 'legion wall hidden at idle');
  C.auraEvent({ t: 'trait', slot: 65, key: 'legion', phase: 'on' }); S.tick(20);
  ok(/wall_up/.test(S.model(65, 'wall')) && /projector_on/.test(S.model(65, 'projector')), 'legion wall + projector on hold', S.model(65, 'wall'));
  C.auraEvent({ t: 'damage', victim: 65, attacker: 64, amount: 10 }); S.tick();
  ok(/wall_flare/.test(S.model(65, 'wall')), 'legion wall flares when hit while up');
  C.auraEvent({ t: 'trait', slot: 65, key: 'legion', phase: 'off' }); S.tick(20);
  ok(!S.part(65, 'wall').prop && /projector_idle/.test(S.model(65, 'projector')), 'legion wall released on off');
  // a 'damage' flare guarded by "if": no wall flare while the shield is down
  C.auraEvent({ t: 'damage', victim: 65, attacker: 64, amount: 10 }); S.tick();
  ok(!S.part(65, 'wall').prop, 'legion wall stays hidden when hit while down');
  // overdrive level: unicorn's seams brighten with the meter
  const k0 = S.part(66, 'seams').k; C.game.mechs.get(66).overdrive = 1; S.tick(20);
  const k1 = S.part(66, 'seams').k;
  ok(k0 <= 0.35 && k1 === 1, 'unicorn seams follow overdrive', k0 + ' -> ' + k1);
  ok(/seams_full/.test(S.model(66, 'seams')), 'unicorn full state at a full meter');
  // polled shield: raised -> hold, a block (hits up) -> flare
  const rx = C.game.mechs.get(67); rx.weapons[1] = { type: 'shield', raised: true, hits: 0 }; S.tick(8);
  ok(/aegis_raised/.test(S.model(67, 'aegis')), 'rx78 aegis raised with the shield');
  rx.weapons[1].hits = 1; S.tick(5);
  ok(/aegis_flare/.test(S.model(67, 'aegis')), 'rx78 aegis flares on a block');
  // white glint: the halo shows while the second wind runs
  C.game.mechs.get(69).trT.wind = 2; S.tick(8);
  ok(/halo_on/.test(S.model(69, 'halo')), 'white glint halo while the wind runs');
  C.game.mechs.get(69).trT.wind = 0; S.tick(8);
  ok(!S.part(69, 'halo').prop, 'white glint halo gone after');
  // ronin afterimages: count ghosts spawn and all go away
  const u0 = S.A.used();
  C.auraEvent({ t: 'trait', slot: 68, key: 'ronin', phase: 'on' }); S.tick(16);
  ok(S.A.fxLive() === 4, 'ronin afterimages spawned', S.A.fxLive());
  S.tick(64);
  ok(S.A.fxLive() === 0 && S.A.used() === u0, 'afterimages released', S.A.fxLive() + ' ' + S.A.used() + '/' + u0);
  // barbatos: a lifesteal hit draws a drain beam towards the victim
  C.auraEvent({ t: 'damage', victim: 64, attacker: 70, amount: 500 }); C.auraEvent({ t: 'trait', slot: 70, key: 'barbatos', phase: 'fire' }); S.tick(2);
  ok(S.A.fxLive() === 1 && S.A.auraFx[0].kind === 'drain' && Math.abs(S.A.auraFx[0].p.scale - 600 / 400) < 0.01, 'barbatos drain beam', S.A.fxLive());
  ok(/tendrils_lash/.test(S.model(70, 'tendrils')), 'barbatos tendrils lash');
  S.tick(40); ok(S.A.fxLive() === 0, 'drain beam released');
  ok(C.bursts.includes('aura_lisa') && C.bursts.includes('aura_legion'), 'flares burst their particle pools');
  // death releases, a rig change re-parents, reset clears
  const before = S.A.used(); const n64 = Object.values(S.A.auraSt.get(64).parts).filter((p) => p.prop).length;
  C.auraEvent({ t: 'death', slot: 64 });
  ok(!S.A.auraSt.has(64) && S.A.used() === before - n64, 'death releases the aura', S.A.used() + ' ' + before);
  const oldProp = S.part(66, 'seams').prop;
  const r = C.rigs.get(66); C.rigs.set(66, Object.assign({}, r, { upper: Object.assign({}, r.upper, { ent: Object.assign({}, r.upper.ent), name: 'up66b' }) }));
  S.tick(3);
  ok(S.part(66, 'seams').prop && S.part(66, 'seams').prop.parent === C.rigs.get(66).upper && oldProp.parent !== r.upper, 're-parented after a rig change');
  C.auraGone(66); ok(!S.A.auraSt.has(66), 'auraGone drops the mech');
  C.auraReset(); ok(S.A.auraSt.size === 0 && S.A.used() === 0, 'reset clears');
}
// particle pools join PFX_POOLS (fxInit finds them on the map when patched)
{ const S = sandbox(); ok(Object.keys(AURAS.pools || {}).every((k) => S.ctx.PFX_POOLS[k] === AURAS.pools[k].count), 'aura pools registered'); }

console.log((fails ? 'auras: FAIL ' + fails : 'auras: OK') + ' (' + passes + ' checks, ' + SPECS.length + ' auras)');
process.exit(fails ? 1 : 0);
