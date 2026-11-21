// Round 4 row 4.4: zombie players don't collide with each other or with the AI horde (packs don't jam); they stay solid
// to humans and walls, and shootable. 4 humans + 4 bots, 20 s, zemap=map01.
//   CT humans 1 and 3 die -> zombies in the T arena. T human 0 next to zombie 3: neither can move into the other;
//   human 0 shoots zombie 3 (Doom hitscan): it is hurt. Zombie 1 moves into zombie 3's spot, both stand on one spot and
//   walk away from it (no telefrag either). An AI imp next to zombie 3: each can move into the other. Zombie 1 against
//   a one-sided wall: blocked.
import { rm, pe, killDoom, liveZombie, timeline, invariants, checker, god, arenaOf, tpInto } from './_lib.mjs';
const { probs, want } = checker();
const MF_SOLID = 2, MF_SHOOTABLE = 4;
const at = (api, a, fn) => { let r; a.run(() => { r = fn(api.ctx); }); return r; };
const steps = timeline([
  [3, (api) => { killDoom(api, 1, null); killDoom(api, 3, null); api.log('CT humans 1 and 3 killed: zombies in the T arena'); }],
  [10, (api) => {
    const a = arenaOf(api, 2);
    if (!liveZombie(api, 1) || !liveZombie(api, 3) || pe(api, 3).arena !== a) { probs.add('zombies 1 and 3 not up in the T arena at 10 s'); return; }
    const z3 = pe(api, 3).player, h = pe(api, 0).player;
    want(!!(z3.mo.flags & MF_SOLID) && !!(z3.mo.flags & MF_SHOOTABLE), 'a zombie body is solid and shootable');
    // human 0 at 96 units from zombie 3 (any free side), facing it
    let placed = false;
    for (const [dx, dy] of [[96, 0], [-96, 0], [0, 96], [0, -96], [70, 70], [-70, -70]]) if (tpInto(api, a, h, z3.mo.x + dx, z3.mo.y + dy) && Math.hypot(h.mo.x - z3.mo.x, h.mo.y - z3.mo.y) < 140) { placed = true; break; }
    if (!placed) { probs.add('could not put human 0 next to zombie 3'); return; }
    want(!at(api, a, (c) => c.checkPosition(z3.mo, h.mo.x, h.mo.y)), 'a zombie can move into a human');
    want(!at(api, a, (c) => c.checkPosition(h.mo, z3.mo.x, z3.mo.y)), 'a human can move into a zombie');
    // shoot: Doom's autoaim and hitscan, as the pistol does
    z3.powers[0] = 0; z3.protectUntil = 0;
    const hp = z3.mo.health;
    at(api, a, (c) => { const ang = c.pointToAngle(h.mo.x, h.mo.y, z3.mo.x, z3.mo.y); const sl = c.aimLineAttack(h.mo, ang, 2048); c.lineAttack(h.mo, ang, 2048, sl, 15); });
    want(z3.mo.health < hp, `human 0's shot hurt zombie 3: ${hp} -> ${z3.mo.health}`);
    api.log(`human 0 shot zombie 3: ${hp} -> ${z3.mo.health}`);
    tpInto(api, a, h, h.mo.x + 400, h.mo.y);   // out of the way
  }],
  [11, (api) => {
    const a = arenaOf(api, 2), z1 = pe(api, 1).player, z3 = pe(api, 3).player;
    if (!z1 || !z3 || !z1.mo || !z3.mo || z1.playerstate !== 'live' || z3.playerstate !== 'live') { probs.add('zombies not up at 11 s'); return; }
    z3.powers[0] = 1 << 20;
    want(tpInto(api, a, z1, z3.mo.x + 48, z3.mo.y) || tpInto(api, a, z1, z3.mo.x, z3.mo.y + 48), 'zombie 1 next to zombie 3');
    want(at(api, a, (c) => c.tryMove(z1.mo, z3.mo.x, z3.mo.y)), 'zombie 1 can move into zombie 3');
    want(Math.abs(z1.mo.x - z3.mo.x) < 1 && Math.abs(z1.mo.y - z3.mo.y) < 1, 'both zombies on one spot');
    const ok1 = at(api, a, (c) => c.tryMove(z1.mo, z1.mo.x + 20, z1.mo.y) || c.tryMove(z1.mo, z1.mo.x, z1.mo.y + 20));
    const ok3 = at(api, a, (c) => c.tryMove(z3.mo, z3.mo.x - 20, z3.mo.y) || c.tryMove(z3.mo, z3.mo.x, z3.mo.y - 20));
    want(ok1 && ok3, `both walk off the shared spot: ${ok1} ${ok3}`);
    // a teleport onto another zombie is no telefrag
    const h1 = z1.mo.health;
    at(api, a, (c) => c.teleportMove(z3.mo, z1.mo.x, z1.mo.y));
    want(z1.playerstate === 'live' && z1.mo.health === h1, 'a zombie teleported onto another one telefragged it');
  }],
  [12, (api) => {
    const a = arenaOf(api, 2), z1 = pe(api, 1).player, z3 = pe(api, 3).player;
    if (!z1 || !z3 || !z1.mo || !z3.mo) return;
    const m = at(api, a, () => a.director.placeAt('IMP', z3.mo.x + 80, z3.mo.y, 0, {}));
    if (!m) { probs.add('could not place an imp next to zombie 3'); return; }
    want(at(api, a, (c) => c.checkPosition(z3.mo, m.x, m.y)), 'a zombie player can move into an AI imp');
    want(at(api, a, (c) => c.checkPosition(m, z3.mo.x, z3.mo.y)), 'an AI imp can move into a zombie player');
    // a wall: a point just behind a one-sided line
    const L = a.level;
    const l = L.lines.find((x) => !x.backsector && Math.hypot(x.dx, x.dy) > 96);
    const len = Math.hypot(l.dx, l.dy), mx = (l.x1 + l.x2) / 2, my = (l.y1 + l.y2) / 2;
    // Doom's front side is on the right of the line's direction; the back (outside) is on the left
    const bx = mx - l.dy / len * 8, by = my + l.dx / len * 8;
    want(!at(api, a, (c) => c.checkPosition(z1.mo, bx, by)), 'a zombie can move into a wall');
    at(api, a, (c) => c.removeMobj(m));
  }],
]);
export default {
  setup(api) { for (const s of [0, 1, 2, 3]) api.manual.add(s); },
  tick(api) { god(api); steps(api); invariants(api, probs); },
  check: () => [...probs],
};
