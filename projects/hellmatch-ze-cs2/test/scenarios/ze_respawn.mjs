// Round 4 row 4.2 (seen on MAP06 Janus Terminal): zombies (players and AI) only come in where they can walk to a live human
// of that arena as the level is open now, and zombie players open doors. 4 humans + 12 bots, 45 s, zemap=map06.
//   every zombie player body and every AI zombie that appears is checked against the bots' sector graph (no lifts that
//   need a switch; blocked lines are out of it): its sector must lead to a sector with a live human of its arena
//   CT human 1 dies -> a zombie in the T arena: walked into a closed press-E door it opens it; at another closed door
//   it presses E (no walking) and that one opens too
//   at 21 s every live T human is put in the escape zone (behind the blue door, which is blocked until stage 4, so no
//   zombie spot of the level is connected to them): from then on no AI comes in cut off (none at all), and zombie
//   players rise near the humans in a connected sector (the fallback) instead of at the old spots behind
import { rm, pe, killDoom, liveZombie, timeline, invariants, checker, god, arenaOf, tpInto } from './_lib.mjs';
const { probs, want } = checker();
const IN = { FORWARD: 1, USE: 128 };
const DOORS = new Set([1, 26, 27, 28, 31, 32, 33, 34, 117, 118]);
const seen = { players: 0, ai: 0, bad: [], after: 0 };
let push = null;   // { slot, buttons, yaw, until }
let doors = [];
let forcedAt = Infinity;

// sectors of arena a from which a live human's sector can be walked to (independent of the script's own code)
function reachSet(api, a) {
  let nav;
  a.run(() => { nav = api.ctx.buildNav(a.level); });
  const n = a.level.sectors.length, rev = Array.from({ length: n }, () => []);
  for (let u = 0; u < n; u++) for (const e of nav[u]) if (!e.lift) rev[e.to].push(u);
  const r = new Uint8Array(n), q = [];
  for (const p of a.players.values()) if (!p.zclass && !p.spectating && p.playerstate === 'live' && p.mo) { const id = a.level.sectorAt(p.mo.x, p.mo.y).id; if (!r[id]) { r[id] = 1; q.push(id); } }
  if (!q.length) return null;
  while (q.length) { const v = q.pop(); for (const u of rev[v]) if (!r[u]) { r[u] = 1; q.push(u); } }
  return r;
}
function checkSpawn(api, a, mo, what) {
  if (!mo || a.zeFinale) return;
  const r = reachSet(api, a);
  if (!r) return;
  if (api.time >= forcedAt && a.zeSide === 2) seen.after++;
  if (!r[a.level.sectorAt(mo.x, mo.y).id]) seen.bad.push(`t=${api.time.toFixed(1)} ${a.mapId} ${what} at ${Math.round(mo.x)},${Math.round(mo.y)} sector ${a.level.sectorAt(mo.x, mo.y).id}`);
}
function hook(api) {
  const R = api.ctx.__ZeRound.prototype, sz = R.spawnZombie;
  R.spawnZombie = function (a, p) { const ok = sz.call(this, a, p); if (ok) { seen.players++; checkSpawn(api, a, p.mo, 'zombie player ' + p.name); } return ok; };
}
let aiHooked = false;
function hookAi(api) {
  const a = arenaOf(api, 2);
  if (aiHooked || !a || !a.director) return;
  aiHooked = true;
  const D = Object.getPrototypeOf(a.director), sa = D.spawnAt;
  D.spawnAt = function (type, x, y, opts) { const mo = sa.call(this, type, x, y, opts); if (mo) { seen.ai++; checkSpawn(api, this.a, mo, 'AI ' + type); } return mo; };
}

// closed manual doors of arena a with room to stand in front of them (front side, 40 + radius off the middle)
function closedDoors(a, radius) {
  const out = [];
  for (const l of a.level.lines) {
    if (!DOORS.has(l.special) || !l.backsector || !l.frontsector) continue;
    const b = l.backsector, f = l.frontsector, len = Math.hypot(l.dx, l.dy);
    if (len < 64 || b.ceilingheight - b.floorheight >= 56 || f.ceilingheight - f.floorheight < 72) continue;
    const mx = (l.x1 + l.x2) / 2, my = (l.y1 + l.y2) / 2, d = radius + 12;
    out.push({ l, sp: l.special, sec: b, x: mx + l.dy / len * d, y: my - l.dx / len * d, mx, my });   // the front (right) side
  }
  // repeatable doors (DR: 1, 26-28, 117) first: a one-time door (31-34, 118) loses its special once opened
  const rep = (x) => [1, 26, 27, 28, 117].includes(x.l.special) ? 0 : 1;
  return out.sort((p, q) => rep(p) - rep(q));
}
function aimAt(api, slot, p, d) {
  let yaw;
  p.arena.run(() => { yaw = api.ctx.pointToAngle(p.mo.x, p.mo.y, d.mx, d.my); });
  const c = api.ctrl(slot);
  c.pawn.eye = { pitch: 0, yaw, roll: 0 };
  return yaw;
}
function startDoor(api, buttons) {
  const z = pe(api, 1).player, a = arenaOf(api, 2);
  if (!z || z.playerstate !== 'live' || z.arena !== a) { probs.add('zombie 1 not up in the T arena'); return null; }
  while (doors.length) {
    const d = doors.shift();
    if (d.sec.ceilingheight - d.sec.floorheight >= 56 || d.sec.specialdata) continue;
    if (!tpInto(api, a, z, d.x, d.y) || Math.hypot(z.mo.x - d.x, z.mo.y - d.y) > 24) continue;
    const yaw = aimAt(api, 1, z, d);
    push = { slot: 1, buttons, yaw, until: api.time + 2 };
    return d;
  }
  probs.add('no closed press-E door left to try');
  return null;
}
let door1 = null, door2 = null;
const steps = timeline([
  [3, (api) => {
    killDoom(api, 1, null);
    // CT bots too: more zombie players in the T arena
    let n = 0;
    for (const p of arenaOf(api, 3).players.values()) if (p.isBot && !p.zclass && p.playerstate === 'live' && n < 5) { killDoom(api, p.slot, null); n++; }
    api.log(`CT human 1 and ${n} CT bots killed: zombies in the T arena`);
  }],
  [10, (api) => {
    const z = pe(api, 1).player;
    if (!liveZombie(api, 1)) { probs.add('zombie 1 not up at 10 s'); return; }
    doors = closedDoors(arenaOf(api, 2), z.mo.radius);
    api.log(`${doors.length} closed press-E doors in ${arenaOf(api, 2).mapId}`);
    door1 = startDoor(api, IN.FORWARD);
    if (door1) api.log(`zombie 1 walks into the door at line ${door1.l.id} (sector ${door1.sec.id})`);
  }],
  [12.5, (api) => {
    if (door1) want(!!door1.sec.specialdata || door1.sec.ceilingheight - door1.sec.floorheight >= 56, `the door at line ${door1.l.id} opened for the zombie walking into it`);
    push = null;
  }],
  [18, (api) => {
    // E at a closed door: the first one again, shut at once here, or another one
    // (MAP06 has few press-E doors: the first one is shut again and, if it was a one-time door, given its special back)
    if (door1) {
      const sec = door1.sec, d = sec.specialdata;
      if (d) { d.removed = true; sec.specialdata = null; }
      sec.ceilingheight = sec.floorheight;
      door1.l.special = door1.sp;
    }
    doors = closedDoors(arenaOf(api, 2), pe(api, 1).player && pe(api, 1).player.mo ? pe(api, 1).player.mo.radius : 20);
    door2 = startDoor(api, IN.USE);
    if (door2) api.log(`zombie 1 presses E at the door at line ${door2.l.id} (sector ${door2.sec.id})`);
  }],
  [20.5, (api) => {
    if (door2) want(!!door2.sec.specialdata || door2.sec.ceilingheight - door2.sec.floorheight >= 56, `the door at line ${door2.l.id} opened on E`);
    push = null;
  }],
  [21, (api) => {
    const a = arenaOf(api, 2), ze = a.ze, e = ze.stages.find((s) => s.d.escape);
    const c = e && ze.zoneCentreNow(e.d.zone);
    let n = 0;
    if (c) for (const p of a.players.values()) if (!p.zclass && p.playerstate === 'live' && p.mo && tpInto(api, a, p, c.x + (n % 3) * 40 - 40, c.y + Math.floor(n / 3) * 40)) n++;
    forcedAt = api.time;
    api.log(`${n} live T humans put in the escape zone (${e ? e.name : '?'})`);
  }],
]);
export default {
  setup(api) { for (const s of [0, 1, 2, 3]) api.manual.add(s); hook(api); },
  tick(api) {
    god(api); hookAi(api);
    // T human bots are part of the setting here: keep them alive so the arena has humans to reach
    const a = arenaOf(api, 2);
    if (a) for (const p of a.players.values()) if (p.isBot && !p.zclass && p.playerstate === 'live') p.powers[0] = 1 << 20;
    if (push && api.time < push.until) { const c = api.ctrl(push.slot); if (c && c.pawn) { c.pawn.buttons = push.buttons; c.pawn.eye = { pitch: 0, yaw: push.yaw, roll: 0 }; } }
    steps(api); invariants(api, probs);
  },
  check(api) {
    api.log(`zombie players spawned ${seen.players}, AI ${seen.ai}, after the move into the escape zone ${seen.after}; cut off: ${seen.bad.length}`);
    for (const b of seen.bad.slice(0, 6)) probs.add('spawned cut off from every live human: ' + b);
    want(seen.players >= 5 && seen.ai >= 20 && seen.after >= 3, `enough spawns to judge: ${seen.players} players, ${seen.ai} AI, ${seen.after} after the move`);
    return [...probs];
  },
};
