// Frame traits (src/core/87_traits.js). usage: node test/traits.cjs
// A flat test arena (no structures, so no traces), two or three mechs placed by hand, inputs set each tick.
const fs = require('fs'), path = require('path');
const { C, ARENA, makeGame, ROOT } = require('./lib.cjs');
const L = C.IF_Game.lib;
const DT = 1 / 64;
let fails = 0, passes = 0;
function ok(cond, name, info) { if (cond) passes++; else { fails++; console.log('FAIL ' + name + (info !== undefined ? ': ' + info : '')); } }
const near = (a, b, tol) => Math.abs(a - b) <= tol;

const FLAT = JSON.parse(JSON.stringify(ARENA));
FLAT.nav.height = FLAT.nav.height.map(() => 100); FLAT.nav.struct = FLAT.nav.struct.map(() => 0); FLAT.nav.walk = FLAT.nav.walk.map(() => 1);

// a game with mechs at given positions, already landed and unprotected
function setup(specs, opts) {
  opts = opts || {};
  const g = makeGame({ arena: FLAT, seed: opts.seed || 3, cfg: Object.assign({ round: { tb: 9999, cq: 9999, sk: 9999, so: 9999, warmup: 0, podium: 3 }, ai: { npcFill: false } }, opts.cfg || {}) });
  g.setMode(opts.mode || 'tb', 2); g.startRound(0);
  specs.forEach((s, i) => {
    g.addPlayer(i, { team: s.team || (i % 2 ? 3 : 2), human: true, name: 'p' + i, pilot: s.pilot || null });
    if (s.lo) { const c = g.setLoadout(i, s.lo); if (c) throw new Error('loadout ' + s.lo + ' denied ' + c); }
    g.requestSpawn(i);
  });
  g.tick(DT, 0);
  specs.forEach((s, i) => {
    const m = g.mechs.get(i);
    m.pos.x = s.x || 0; m.pos.y = s.y || 0; m.pos.z = 100; m.vel.x = m.vel.y = m.vel.z = 0;
    m.dropT = 0; m.onGround = true; m.protect = 0; m.torsoYaw = m.legYaw = m.input.yaw = s.yaw || 0; m.histN = 0;
  });
  g.tick(DT, DT);   // rebuild the live list and the grid at the new places
  g.events.length = 0;
  return g;
}
function aim(g, m, t) {
  const ox = m.pos.x, oy = m.pos.y, oz = m.pos.z + m.height * 0.8;
  const tx = t.pos.x + t.vel.x * 0, ty = t.pos.y, tz = t.pos.z + t.height * 0.55;
  m.input.yaw = Math.atan2(ty - oy, tx - ox) * 180 / Math.PI;
  m.input.pitch = -Math.atan2(tz - oz, Math.hypot(tx - ox, ty - oy)) * 180 / Math.PI;
}
function run(g, secs, each) { for (let k = 0; k < Math.round(secs * 64); k++) { if (each) each(k); g.tick(DT, g.time + DT); } }

const LO = (f, sh) => f + ',101,0,' + (sh || '0') + ',0,301,401,501,601';
const hit = (g, v, a, amt, src, opts, imp) => { const ap = v.ap; L.IF_applyDamage(g, v, a ? a.slot : 1, amt, imp || 0, null, 'test', src || (a ? a.pos : null), opts || null); return ap - v.ap; };
const one = (f) => { const g = setup([{ lo: LO(f) }, { x: 1000, yaw: 180, lo: LO(4) }]); return { g, m: g.mechs.get(0), o: g.mechs.get(1) }; };
const BACK = { x: -1000, y: 0, z: 100 };

// every player frame has a trait and its text
for (const p of C.PARTS.parts) if (p.kind === 'frame' && !p.pve) ok(!!p.trait && !!p.trait_desc && /[a-z]/.test(p.desc), 'trait text on frame ' + p.id);
ok(C.PARTS.parts.filter((p) => p.kind === 'frame' && !p.pve).length === 19, '19 player frames');
{ // every trait key is used by one frame only
  const keys = C.PARTS.parts.filter((p) => p.kind === 'frame' && p.trait).map((p) => p.trait);
  ok(new Set(keys).size === keys.length, 'trait keys unique', keys.join(','));
}

{ // krasnaya: first hit after a quick boost +20 %, once
  const { g, m, o } = one(1);
  m.input.qb = true; m.input.mx = 1; run(g, 0.05); m.input.qb = false;
  const d1 = hit(g, o, m, 1000), d2 = hit(g, o, m, 1000);
  ok(near(d1, 1200, 1) && near(d2, 1000, 1), 'krasnaya opener +20 % once', d1 + ' ' + d2);
}
{ // stryder: quick boost cost 30 % less than white glint's
  const a = one(2).m, b = one(4).m;
  ok(near(a.qbCost / b.qbCost, 0.7, 0.01), 'stryder qb cost -30 %', a.qbCost + ' ' + b.qbCost);
}
{ // lisa: second jump press in the air, once
  const { g, m } = one(3);
  m.input.jump = true; run(g, 0.3); m.input.jump = false; run(g, 0.05);
  ok(!m.onGround, 'lisa airborne');
  const vz = m.vel.z, en = m.en; m.input.jump = true; g.tick(DT, g.time + DT); m.input.jump = false;
  ok(m.vel.z > vz + 200 && m.en < en, 'lisa double jump', vz + ' -> ' + m.vel.z);
  run(g, 0.05); const vz2 = m.vel.z; m.input.jump = true; g.tick(DT, g.time + DT);
  ok(m.vel.z < vz2 + 100, 'lisa only one double jump per air time', vz2 + ' -> ' + m.vel.z);
}
{ // white glint: EN regen faster after a quick boost
  const w = one(4), c = one(4);
  w.m.input.qb = true; w.m.input.mx = 1; run(w.g, 0.05); w.m.input.qb = false; w.m.input.mx = 0; run(w.g, 0.1);
  for (const t of [w, c]) { t.m.en = t.m.enMax * 0.2; t.m.enPause = 0; t.m.onGround = true; }
  const e0 = w.m.en; run(w.g, 1); const dw = w.m.en - e0;
  const e1 = c.m.en; run(c.g, 1); const dc = c.m.en - e1;
  ok(dw > dc * 1.3 && w.m.trT.wind > 0, 'white glint second wind', dw + ' vs ' + dc);
}
{ // atlas: 0.8 % AP/s after 5 s without damage, not before (was 2 %: too strong once bots miss, Nov 2026 aim model)
  const { g, m } = one(5);
  m.ap = m.apMax * 0.5; m.lastDamageT = g.time; run(g, 4); ok(near(m.ap, m.apMax * 0.5, 1), 'atlas no repair before 5 s', m.ap);
  run(g, 2); ok(m.ap > m.apMax * 0.5 + m.apMax * 0.006, 'atlas field repair', m.ap);
}
{ // ogre: -15 % from the front only
  const { g, m, o } = one(8);
  const f = hit(g, m, o, 1000, o.pos), b = hit(g, m, o, 1000, BACK);
  ok(near(f, 850, 1) && near(b, 1000, 1), 'ogre plating front/back', f + ' ' + b);
}
{ // noblesse: shoulder reload 20 % faster
  const g = setup([{ lo: '9,101,0,201,0,301,401,501,601' }]), m = g.mechs.get(0); const wp = m.weapons[2], w2 = m.weapons[0];
  wp.reloading = true; wp.reloadT = 5; w2.reloading = true; w2.reloadT = 5;
  run(g, 1); ok(near(5 - wp.reloadT, 1.25, 0.1) && near(5 - w2.reloadT, 1, 0.1), 'noblesse shoulder reload faster', wp.reloadT + ' ' + w2.reloadT);
}
{ // legion: hold F 0.5 s -> gun shield, front -50 %, slow, cooldown
  const { g, m, o } = one(10);
  m.input.cycleHeld = true; run(g, 0.4); ok(m.trT.act <= 0, 'legion needs the full hold');
  run(g, 0.3); ok(m.trT.act > 0, 'legion gun shield up');
  ok(near(hit(g, m, o, 1000, o.pos), 750, 1), "legion front -25 %"); ok(near(hit(g, m, o, 1000, BACK), 1000, 1), 'legion rear unshielded');
  m.input.cycleHeld = false; m.input.my = 1; run(g, 1); ok(m.speed < m.walkSpeed * 0.6, 'legion slowed under the shield', m.speed);
  run(g, 3.5); ok(m.trT.act <= 0 && m.trT.cd > 0, 'legion shield ends, cooldown');
  m.input.my = 0; m.input.cycleHeld = true; run(g, 0.7); ok(m.trT.act <= 0, 'legion cooldown holds');
}
{ // barbatos: melee lifesteal 15 %
  const { g, m, o } = one(11); m.ap = m.apMax * 0.5; const ap = m.ap;
  L.IF_applyDamage(g, o, 0, 1000, 0, null, 'blade', m.pos, { wp: { w: { type: 'melee' }, hits: 0, dmg: 0 } });
  ok(near(m.ap - ap, 150, 1), 'barbatos melee lifesteal', m.ap - ap);
  const ap2 = m.ap; L.IF_applyDamage(g, o, 0, 1000, 0, null, 'rifle', m.pos, { wp: { w: { type: 'proj' }, hits: 0, dmg: 0 } });
  ok(m.ap === ap2, 'barbatos no lifesteal on bullets');
}
{ // mule: still 1 s -> brace -30 %, moving breaks it
  const { g, m, o } = one(12);
  run(g, 0.5); ok(near(hit(g, m, o, 1000), 1000, 1), 'mule not braced yet');
  run(g, 0.7); ok(m.trT.brace && m.spreadMul < 1, 'mule braced'); ok(near(hit(g, m, o, 1000), 700, 1), 'mule brace -30 %');
  m.vel.x = 300; run(g, 0.05); ok(!m.trT.brace, 'mule brace breaks on moving');
}
{ // ronin: double-tap quick boost -> untouchable dash, cooldown; slow taps do nothing
  const { g, m, o } = one(13); m.input.mx = 1;
  m.input.qb = true; run(g, 1 / 64); m.input.qb = false; run(g, 0.1); m.input.qb = true; run(g, 1 / 64); m.input.qb = false;
  ok(m.trT.ph > 0, 'ronin phase dash on double tap');
  ok(hit(g, m, o, 1000, o.pos, null, 99999) === 0 && m.staggered <= 0, 'ronin untouchable while phasing');
  run(g, 0.5); ok(m.trT.ph <= 0 && near(hit(g, m, o, 1000), 1000, 1), 'ronin phase ends');
  m.input.qb = true; run(g, 1 / 64); m.input.qb = false; run(g, 0.1); m.input.qb = true; run(g, 1 / 64); ok(m.trT.ph <= 0, 'ronin phase on cooldown');
  const t = one(13); t.m.input.mx = 1; t.m.input.qb = true; run(t.g, 1 / 64); t.m.input.qb = false; run(t.g, 0.6); t.m.input.qb = true; run(t.g, 1 / 64); ok(t.m.trT.ph <= 0, 'ronin slow taps are no phase dash');
}
{ // unicorn: overdrive fills 30 % faster than the same medium without the trait
  const u = one(14), w = one(4);
  const fill = (t) => { t.m.overdrive = 0; L.IF_applyDamage(t.g, t.o, 0, 500, 0, null, 'test', t.m.pos); return t.m.overdrive; };
  const a = fill(u), b = fill(w);
  ok(a > 0 && near(a / b, 1.3, 0.02), 'unicorn overdrive +30 %', a + ' ' + b);
}
{ // cerberus atlas: after a stagger ends, 3 s without stagger
  const { g, m, o } = one(20); m.staggerMax = 1000;
  L.IF_applyDamage(g, m, 1, 100, 5000, null, 'test', o.pos); ok(m.staggered > 0, 'cerberus staggers first');
  run(g, 2.2); ok(m.staggered <= 0 && m.trT.imm > 0, 'cerberus stagger immunity starts', m.trT.imm);
  L.IF_applyDamage(g, m, 1, 100, 5000, null, 'test', o.pos); ok(m.staggered <= 0, 'cerberus immune to stagger');
  run(g, 3.2); L.IF_applyDamage(g, m, 1, 100, 5000, null, 'test', o.pos); ok(m.staggered > 0, 'cerberus immunity ends');
}
{ // rx78: shield block +30 %
  const sh = (f) => setup([{ lo: f + ',101,111,0,0,301,401,501,601' }]).mechs.get(0).weapons.find((w) => w.w && w.w.type === 'shield');
  const a = sh(7), b = sh(4);
  ok(a && b && near(a.statMult / b.statMult, 1.3, 0.001), 'rx78 shield mastery', a && a.statMult);
}
{ // sandviper: a lock held 1.5 s marks the target (6 s, +10 % damage from anyone, the marker's team on it), then it wears off
  const { g, m, o } = one(21);
  m.lock.target = o.slot; m.lock.t = 1.0; m.lock.stage = 1; run(g, 1 / 64); ok(!(o.markT > 0), 'sandviper no mark before 1.5 s');
  m.lock.t = 1.6; g.tick(DT, g.time + DT);
  ok(o.markT > 0 && o.markTeam === m.team, 'sandviper marks the locked target', o.markT);
  ok(g.events.some((e) => e.t === 'trait' && e.key === 'sandviper' && e.phase === 'on' && e.target === o.slot), 'sandviper mark event');
  ok(near(hit(g, o, m, 1000), 1100, 1), 'sandviper marked target takes +10 %');
  m.lock.target = -1; m.lock.t = 0; m.input.yaw = 180; g.events.length = 0; run(g, 6.2, () => { m.lock.target = -1; });
  ok(o.markT <= 0 && near(hit(g, o, m, 1000), 1000, 1), 'sandviper mark wears off after 6 s');
  ok(g.events.some((e) => e.t === 'trait' && e.key === 'sandviper' && e.phase === 'off'), 'sandviper mark off event');
}
{ // kestrel: -35 % for 0.5 s from the start of a quick boost
  const { g, m, o } = one(22);
  ok(near(hit(g, m, o, 1000), 1000, 1), 'kestrel full damage at rest');
  m.input.qb = true; m.input.mx = 1; run(g, 2 / 64); m.input.qb = false;
  ok(near(hit(g, m, o, 1000), 650, 1), 'kestrel slipstream -35 % during the quick boost');
  ok(g.events.some((e) => e.t === 'trait' && e.key === 'kestrel' && e.phase === 'fire'), 'kestrel slipstream event');
  run(g, 0.6); ok(near(hit(g, m, o, 1000), 1000, 1), 'kestrel slipstream over after 0.5 s');
}
{ // warden: hold F 0.5 s -> barrier (10 % max AP, 6 s) on itself and the ally in range, not the enemy; cooldown
  const g = setup([{ lo: LO(23), team: 2 }, { x: 500, lo: LO(4), team: 2 }, { x: -2000, lo: LO(4), team: 2 }, { x: 1000, yaw: 180, lo: LO(4), team: 3 }]);
  const m = g.mechs.get(0), al = g.mechs.get(1), far = g.mechs.get(2), en = g.mechs.get(3);
  m.input.cycleHeld = true; run(g, 0.4); ok(!(m.barrier > 0), 'warden needs the full hold');
  run(g, 0.2); m.input.cycleHeld = false;
  ok(near(m.barrier, m.apMax * 0.1, 1) && near(al.barrier, al.apMax * 0.1, 1), 'warden aegis barrier on itself and the ally', m.barrier + ' ' + al.barrier);
  ok(!(far.barrier > 0) && !(en.barrier > 0), 'warden aegis skips the far ally and the enemy');
  ok(g.events.some((e) => e.t === 'trait' && e.key === 'warden' && e.phase === 'on' && e.allies && e.allies.includes(1)), 'warden pulse event lists the ally');
  const b = al.barrier; ok(near(hit(g, al, en, 500), 0, 0.5) && near(al.barrier, b - 500, 1), 'warden barrier absorbs first');
  ok(near(hit(g, al, en, 1000), 1000 - (b - 500), 1) && !(al.barrier > 0), 'warden barrier breaks, the rest goes through');
  m.input.cycleHeld = true; run(g, 0.7); m.input.cycleHeld = false; ok(!(al.barrier > 0), 'warden aegis on cooldown');
  run(g, 6); ok(!(m.barrier > 0), 'warden barrier expires after 6 s');
}
{ // bastion: hold F 0.5 s on the ground -> rooted 4 s, +20 % damage dealt; a quick boost ends it
  const { g, m, o } = one(24);
  m.input.cycleHeld = true; run(g, 0.4); ok(!(m.trT.act > 0), 'bastion needs the full hold');
  run(g, 0.2); m.input.cycleHeld = false; ok(m.trT.act > 0, 'bastion siege mode on');
  ok(near(hit(g, o, m, 1000), 1200, 1), 'bastion siege +20 % damage');
  m.input.my = 1; run(g, 0.5); ok(m.speed < 5, 'bastion rooted in siege mode', m.speed);
  m.input.qb = true; run(g, 2 / 64); m.input.qb = false; m.input.my = 0;
  ok(!(m.trT.act > 0) && m.trT.cd > 0, 'bastion quick boost ends siege mode, cooldown');
  ok(near(hit(g, o, m, 1000), 1000, 1), 'bastion no bonus after siege');
  m.input.cycleHeld = true; run(g, 0.7); m.input.cycleHeld = false; ok(!(m.trT.act > 0), 'bastion siege on cooldown');
  const t = one(24); t.m.input.cycleHeld = true; run(t.g, 0.6); t.m.input.cycleHeld = false; run(t.g, 4.1); ok(!(t.m.trT.act > 0), 'bastion siege ends after 4 s');
}
{ // bots use the active traits (Warden aegis, Bastion siege) in a 1v1 AI duel, with no AI hook
  const used = (f) => {
    const g = makeGame({ seed: 5, cfg: { round: { tb: 9999, warmup: 0, podium: 2 }, ai: { npcFill: false }, tb: { killMin: 999, killMax: 999 } } });
    g.setMode('tb', 0); g.startRound(0);
    [[f, 2], [4, 3]].forEach(([fr, team], i) => { g.addPlayer(i, { team, human: false, name: 'b' + i }); g.setLoadout(i, LO(fr)); C.IF_Ai.attach(g, g.mechs.get(i), 'normal'); });
    g.tick(DT, DT);
    [0, 1].forEach((i) => { const m = g.mechs.get(i); m.pos.x = (i ? 1 : -1) * 1300; m.pos.y = 0; m.pos.z = g.nav.height(m.pos.x, 0) + 5; m.dropT = 0; m.onGround = true; m.protect = 0; });
    let n = 0, t = DT;
    for (let k = 0; k < 40 * 64; k++) { g.tick(DT, t += DT); for (const e of g.events) if (e.t === 'trait' && e.slot === 0 && e.phase === 'on') n++; g.events.length = 0; }
    return n;
  };
  const w = used(23), b = used(24);
  ok(w > 0, 'bot warden pulses its aegis', w); ok(b > 0, 'bot bastion uses siege mode', b);
}
console.log('traits: ' + passes + ' passed, ' + fails + ' failed');
process.exit(fails ? 1 : 0);
