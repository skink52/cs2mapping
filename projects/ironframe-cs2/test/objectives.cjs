// Objective modes (src/core/85_objectives.js + captureStep in 80_game.js): King of the Hill scoring and rotation, Capture the Flag
// take / drop / return / capture, Conquest presence counts, the AI objective pull, and the soak (every bot mode finishes, bots stand on
// the objective). usage: node test/objectives.cjs   (IF_ARENA_FILE=out/addon/_gen/arena.json runs the soak part on Dunes)
const { C, ARENA, makeGame, makeWorld } = require('./lib.cjs');
const DT = 1 / 64;
let fails = 0, passes = 0;
function ok(cond, name, info) { if (cond) passes++; else { fails++; console.log('FAIL ' + name + (info !== undefined ? ': ' + info : '')); } }

// a flat copy of the arena with the three points on the ground (no structures: no traces needed)
const FLAT = JSON.parse(JSON.stringify(ARENA));
FLAT.nav.height = FLAT.nav.height.map(() => 100); FLAT.nav.struct = FLAT.nav.struct.map(() => 0); FLAT.nav.walk = FLAT.nav.walk.map(() => 1);
FLAT.points = [{ id: 'A', pos: [-3500, 0, 100], radius: 700 }, { id: 'B', pos: [0, 0, 100], radius: 700 }, { id: 'C', pos: [3500, 0, 100], radius: 700 }];
delete FLAT.flags;

function setup(mode, specs, opts) {
  opts = opts || {};
  const arena = opts.arena || FLAT;
  const g = makeGame({ arena, seed: 5, cfg: Object.assign({ round: { tb: 9999, cq: 9999, sk: 9999, so: 9999, kh: 9999, ctf: 9999, warmup: 0, podium: 3 },
    ai: { npcFill: false }, feat: { off: true } }, opts.cfg || {}) });
  g.setMode(mode, specs.length); g.startRound(0);
  specs.forEach((s, i) => { g.addPlayer(i, { team: s.team, human: true, name: 'p' + i, pilot: null }); g.requestSpawn(i); });
  g.tick(DT, 0);
  specs.forEach((s, i) => place(g, i, s.x, s.y));
  g.tick(DT, DT); g.events.length = 0;
  return g;
}
function place(g, slot, x, y) {
  const m = g.mechs.get(slot);
  m.pos.x = x; m.pos.y = y; m.pos.z = g.nav.height(x, y); m.vel.x = m.vel.y = m.vel.z = 0; m.dropT = 0; m.onGround = true; m.protect = 0; m.histN = 0;
}
function run(g, secs) { for (let k = 0; k < Math.round(secs * 64); k++) g.tick(DT, g.time + DT); }
const evs = (g, t, f) => g.events.filter((e) => e.t === t && (!f || f(e)));

// ---------------------------------------------------------------- votes survive the core reset at CS2's round restart (the adapter resets, then picks)
{
  const g = makeGame({ arena: FLAT, seed: 2 }); g.setMode('tb', 6); g.startRound(0);
  for (let s = 0; s < 6; s++) { g.addPlayer(s, { team: 2 + (s % 2), human: true, name: 'p' + s, pilot: null }); g.vote(s, s < 4 ? 'ctf' : 'kh'); }
  g.reset();
  ok(g.pickMode(6) === 'ctf', 'a !vote survives the round-restart reset and picks the mode', g.pickMode(6));
  g.setMode('ctf', 6); g.startRound(1);
  ok(g.votes.size === 0, 'votes are spent at the round start');
}
// ---------------------------------------------------------------- King of the Hill
{
  const g = setup('kh', [{ team: 2, x: 0, y: 0 }, { team: 3, x: 5000, y: 3000 }]);
  const M = g.match, hill = M.points[0];
  ok(hill.id === 'B' && M.hill === 1, 'KOTH starts on the centre point B', hill.id);
  ok(M.hillNext === 2 && M.hillLeft > 100, 'next hill C, time left set', M.hillNext + ' ' + M.hillLeft);
  run(g, 9);
  ok(hill.owner === 2, 'T alone takes the hill in about 8 s', hill.owner);
  const cap = evs(g, 'capture')[0];
  ok(cap && cap.point === 1 && cap.id === 'B', 'capture event names the arena point (B = 1), not the one-point list index', cap && cap.point + ' ' + cap.id);
  ok(hill.nT === 1 && hill.nCT === 0, 'presence counts nT / nCT', hill.nT + '/' + hill.nCT);
  const s0 = M.scores[2]; run(g, 5);
  ok(M.scores[2] - s0 >= 4 && M.scores[2] - s0 <= 6 && hill.scoring, 'owner on the hill scores 1 a second', M.scores[2] - s0);
  // the owner leaves: no score (it used to keep scoring an empty hill)
  place(g, 0, -5000, 3000); run(g, 0.3); const s1 = M.scores[2]; run(g, 5);
  ok(M.scores[2] === s1 && hill.owner === 2 && !hill.scoring, 'an empty hill keeps its owner but scores nothing', (M.scores[2] - s1) + ' owner ' + hill.owner);
  // the enemy alone on it: the owner does not score while it is being taken
  place(g, 1, 100, 100); run(g, 0.3); const s2 = M.scores[2]; run(g, 4);
  ok(M.scores[2] === s2, 'the owner does not score while the enemy alone is on the hill', M.scores[2] - s2);
  // contested: nobody scores
  place(g, 0, -100, 0); run(g, 0.3); const c2 = M.scores[2], c3 = M.scores[3]; run(g, 3);
  ok(hill.contested && M.scores[2] === c2 && M.scores[3] === c3, 'contested hill scores nothing', hill.contested);
  // rotation: a warning 15 s before, then the move
  M.hillT = g.cfg.kh.rotate - 16; g.events.length = 0; run(g, 1.5);
  const soon = evs(g, 'hill', (e) => e.soon)[0];
  ok(soon && soon.next === 2, 'hill move warning with the next point', soon && soon.next);
  run(g, 15);
  ok(M.hill === 2 && M.points[0].id === 'C' && M.points[0].owner === 0 && evs(g, 'hill', (e) => e.moved).length === 1, 'the hill moved to C, neutral', M.hill);
  ok(M.hillNext === 0 && M.hillLeft > g.cfg.kh.rotate - 2, 'next hill wraps to A, timer reset', M.hillNext + ' ' + M.hillLeft);
}
// ---------------------------------------------------------------- Conquest presence
{
  const g = setup('cq', [{ team: 2, x: -3500, y: 0 }, { team: 2, x: -3400, y: 200 }, { team: 3, x: 3500, y: 0 }]);
  run(g, 1);
  const [A, B, Cp] = g.match.points;
  ok(A.nT === 2 && A.nCT === 0 && Cp.nCT === 1 && B.nT === 0 && B.nCT === 0, 'Conquest nT / nCT per point', [A.nT, A.nCT, Cp.nCT].join(','));
  run(g, 4.8);
  ok(A.owner === 2 && Cp.owner === 0, 'two mechs capture faster than one (5.3 s against 8 s)', A.owner + ' ' + Cp.owner + ' ' + Cp.progress.toFixed(2));
  ok(evs(g, 'capture', (e) => e.point === 0 && e.id === 'A').length === 1, 'Conquest capture event point 0 = A');
}
// Conquest ticket bleed: majority rule
{
  const g = setup('cq', [{ team: 2, x: 0, y: 5000 }, { team: 3, x: 0, y: -5000 }]);
  const [A, B, Cp] = g.match.points;
  A.owner = 2; A.value = -1; B.owner = 2; B.value = -1; Cp.owner = 3; Cp.value = 1;
  const t2 = g.match.tickets[2], t3 = g.match.tickets[3]; run(g, 10);
  ok(Math.abs(g.match.tickets[2] - t2) < 0.01 && Math.abs(t3 - g.match.tickets[3] - 10) < 0.3, 'Conquest: 2-1 bleeds only the minority, 1 ticket/s', (t2 - g.match.tickets[2]).toFixed(2) + ' / ' + (t3 - g.match.tickets[3]).toFixed(2));
  ok(g.match.bleed && g.match.bleed[3] === 1 && g.match.bleed[2] === 0, 'match.bleed per team', JSON.stringify(g.match.bleed));
  Cp.owner = 2; Cp.value = -1; const u3 = g.match.tickets[3]; run(g, 5);
  ok(Math.abs(u3 - g.match.tickets[3] - 15) < 0.4, 'Conquest: 3-0 bleeds 3 tickets/s', (u3 - g.match.tickets[3]).toFixed(2));
}
// ---------------------------------------------------------------- Capture the Flag
{
  const g = setup('ctf', [{ team: 2, x: -2000, y: 2000 }, { team: 3, x: 2000, y: 2000 }, { team: 3, x: 2500, y: 2000 }]);
  const M = g.match, fT = M.flags[2], fCT = M.flags[3];
  // default bases: the drop centroid a quarter of the way in (the first drop point used to put the flags 11 200 u apart)
  const d = Math.hypot(fT.home.x - fCT.home.x, fT.home.y - fCT.home.y);
  ok(d < 10000 && d > 4000, 'default flag bases are inset toward the centre', Math.round(d));
  ok(fT.returnMax === g.cfg.ctf.returnTime && fT.carrierTeam === 3 && fCT.carrierTeam === 2, 'flag fields returnMax / carrierTeam');
  // the T mech takes the CT flag
  place(g, 0, fCT.home.x, fCT.home.y); run(g, 0.2);
  ok(fCT.state === 'carried' && fCT.carrier === 0 && g.mechs.get(0).carrier, 'enemy touch takes the flag');
  // carried home while the own flag is home: capture
  place(g, 0, fT.home.x + 100, fT.home.y); run(g, 0.2);
  ok(M.scores[2] === 1 && fCT.state === 'home' && !g.mechs.get(0).carrier, 'carrier at the own home flag scores', M.scores[2]);
  // take again, die high in the air: the flag drops on the ground below (it used to go home when the ground was 2000 u below)
  place(g, 0, fCT.home.x, fCT.home.y); run(g, 0.2);
  const c = g.mechs.get(0); c.pos.x = 0; c.pos.y = 2000; c.pos.z = 3200; c.onGround = false;
  C.IF_Game.lib.IF_mechDie(g, c, 1, 'test'); run(g, 0.1);
  ok(fCT.state === 'dropped' && Math.abs(fCT.pos.z - g.nav.height(0, 2000)) < 1, 'a carrier killed high up drops the flag on the ground', fCT.state + ' z ' + Math.round(fCT.pos.z));
  ok(evs(g, 'flag', (e) => e.action === 'drop').length >= 1, 'drop event');
  // a CT mech touching its dropped flag returns it
  place(g, 1, 0, 2000); run(g, 0.2);
  ok(fCT.state === 'home', 'a teammate touch returns the dropped flag', fCT.state);
  // the timed return
  fCT.state = 'dropped'; fCT.pos.x = -3000; fCT.pos.y = -3000; fCT.returnT = g.cfg.ctf.returnTime; run(g, g.cfg.ctf.returnTime + 0.5);
  ok(fCT.state === 'home', 'a dropped flag returns after returnTime', fCT.state);
  // no capture while the own flag is away
  g.requestSpawn(0); run(g, 7); place(g, 0, fCT.home.x, fCT.home.y); run(g, 0.2);
  ok(fCT.state === 'carried', 'retaken', fCT.state);
  place(g, 2, fT.home.x, fT.home.y); run(g, 0.2);
  ok(fT.state === 'carried' && fT.carrier === 2, 'CT takes the T flag');
  const sc = M.scores[2]; place(g, 0, fT.home.x + 50, fT.home.y); run(g, 0.5);
  ok(M.scores[2] === sc, 'no capture while the own flag is away', M.scores[2] - sc);
}
// map flag stands win over the default bases
{
  const A2 = JSON.parse(JSON.stringify(FLAT)); A2.flags = { t: [-4200, 100, 100], ct: [4200, -100, 100] };
  const g = setup('ctf', [{ team: 2, x: 0, y: 3000 }, { team: 3, x: 0, y: -3000 }], { arena: A2 });
  ok(g.match.flags[2].home.x === -4200 && g.match.flags[3].home.x === 4200, 'ARENA.flags (the map stands) set the bases');
}
// flag over the void goes home (Orbital)
{
  const A3 = JSON.parse(JSON.stringify(FLAT)); const ix = (x, y) => Math.floor((y - A3.nav.y0) / A3.nav.cell) * A3.nav.w + Math.floor((x - A3.nav.x0) / A3.nav.cell);
  for (let x = -600; x <= 600; x += 128) for (let y = 1400; y <= 2600; y += 128) A3.nav.height[ix(x, y)] = A3.bounds.min[2];
  const g = setup('ctf', [{ team: 2, x: -2000, y: 0 }, { team: 3, x: 2000, y: 0 }], { arena: A3 });
  const f = g.match.flags[3]; place(g, 0, f.home.x, f.home.y); run(g, 0.2);
  const c = g.mechs.get(0); c.pos.x = 0; c.pos.y = 2000; c.pos.z = 400;
  C.IF_Game.lib.IF_mechDie(g, c, 1, 'test'); run(g, 0.1);
  ok(f.state === 'home', 'a flag dropped over the void goes home', f.state);
}
// ---------------------------------------------------------------- AI pull
{
  const g = setup('kh', [{ team: 2, x: 0, y: 0 }]);
  const m = g.mechs.get(0), ai = { hasGoal: true, goal: { x: 0, y: 0, z: 100 } };
  place(g, 0, 2000, 0);
  const o = g.objPull(m, ai); ok(o && o.x < -2, 'KOTH pull toward the hill from outside', o && o.x);
  place(g, 0, 200, 0); ok(g.objPull(m, ai) === null, 'no pull well inside the hill');
  ai.goal = { x: 5000, y: 5000, z: 100 }; place(g, 0, 2000, 0); ok(g.objPull(m, ai) === null, 'no pull toward a goal that is not a zone');
}
// ---------------------------------------------------------------- soak: AI only, every objective mode ends, bots play the objective
{
  const SECS = 300;
  for (const mode of ['kh', 'cq', 'ctf']) {
    const R = SECS - 20, g = makeGame({ seed: 11, cfg: { round: { tb: R, cq: R, sk: R, so: R, kh: R, ctf: R, warmup: 2, podium: 3 } } });
    // the runtime survey as in CS2 (every non-void cell walkable, cliffs by height step), not the baked walk flags
    g.nav.probeStart(g.arena.bounds); const w = makeWorld(g.arena); while (!g.nav.probeStep(w, 100000));
    g.setMode(mode, 0); g.startRound(0);
    for (let s = 0; s < 16; s++) g.addPlayer(s, { team: s % 2 ? 3 : 2, human: false, name: 'b' + s, pilot: null });
    let t = 0, ended = false, inZone = 0, samples = 0; const team = { 2: 0, 3: 0 }, n = { 2: 0, 3: 0 };
    for (let k = 0; k < 64 * SECS && !ended; k++) {
      g.tick(DT, t); t += DT;
      for (const e of g.events) if (e.t === 'round_end') ended = true;
      g.events.length = 0;
      if (g.match.phase !== 'running' || (k & 63)) continue;
      const M = g.match;
      const zones = mode === 'ctf' ? [M.flags[2], M.flags[3]].map((f) => ({ pos: f.pos, radius: 900 })) : M.points;
      for (const m of g.alive) { samples++; n[m.team]++; if (zones.some((p) => Math.hypot(m.pos.x - p.pos.x, m.pos.y - p.pos.y) < p.radius)) { inZone++; team[m.team]++; } }
    }
    const share = inZone / Math.max(1, samples), sT = team[2] / Math.max(1, n[2]), sCT = team[3] / Math.max(1, n[3]);
    console.log(`  soak ${mode}: ${ended ? 'ended' : 'NOT ENDED'} at ${t.toFixed(0)} s, winner ${g.match.winner}, scores ${JSON.stringify(g.match.scores)} tickets ${JSON.stringify(g.match.tickets)}, on objective ${share.toFixed(2)} (T ${sT.toFixed(2)} CT ${sCT.toFixed(2)})`);
    ok(ended, mode + ' round ends inside ' + SECS + ' s');
    ok(share >= (mode === 'ctf' ? 0.12 : 0.2), mode + ' bots stand on the objective', share.toFixed(2));
    ok(Math.min(sT, sCT) >= (mode === 'ctf' ? 0.05 : 0.08), mode + ' both teams play the objective', sT.toFixed(2) + ' / ' + sCT.toFixed(2));
  }
}
console.log(`objectives: ${passes} passed, ${fails} failed`);
process.exit(fails ? 1 : 0);
