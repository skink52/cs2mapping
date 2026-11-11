// =====================================================================================================================
// IRONFRAME core, part 8c: destructible street props (11 Nov 2026; skink52: "could we implement some interactive props?
// like cars that if take enough damage have explosions etc and burn").
//
// arena.cars (written by the map generator / patch: _gen/arena.json): [[x, y, z, radius, big, ...], ...]. The entries past
// `big` are the adapter's (yaw, pitch, roll, tint): the core does not read them. A map without the list has no props.
//
// A prop has hit points. It is hurt by
//   - hitscan shots and beams (IF_propsSegment from IF_fireHitscan: the segment muzzle -> end point),
//   - bullets and shells in flight (IF_propsSegment from IF_bulletsStep: each step's segment). They pass through: a car is
//     not cover (it is not solid in the map either), it only takes the damage,
//   - every explosion (IF_propsBlast from IF_explode: missiles, grenades, overdrive, other props),
//   - a mech walking over it: crushed at once (IF_propsStep).
// At 0 it is destroyed: {t:'prop', id, how: 'boom' | 'crush', pos, slot}. A 'boom' prop explodes on the NEXT tick (IF_explode
// with the destroyer as the owner: the damage and the kills are theirs, weapon key 'car'), so a row of cars goes up as a
// chain, one tick apart; then it burns for cfg.burn seconds ({t:'prop_out', id, pos} when the fire is out). Crushed props
// do not explode. Everything is whole again at each round start ({t:'props_reset'}).
// Hooks: IF_Game.startRound (IF_propsReset), update (IF_propsStep after the missiles), IF_explode, IF_fireHitscan,
// IF_bulletsStep. Tests: test/props.cjs.
// =====================================================================================================================
const IF_PROPS_CFG = { hp: 600, hpBig: 1600, blastR: 330, blastDmg: 900, blastImpact: 500, burn: 14, crushSpeed: 60, cell: 256 };

function IF_propKey(i, j) { return (i + 32768) * 65536 + (j + 32768); }
function IF_propsInit(game) {
  const src = (game.arena && game.arena.cars) || [], C = IF_PROPS_CFG.cell;
  const P = { list: [], cells: new Map(), alive: 0, stampN: 0, pending: [] };
  for (let n = 0; n < src.length; n++) {
    const c = src[n], p = { id: n, x: c[0], y: c[1], z: c[2], r: c[3] || 60, big: !!c[4], hp: 0, alive: false, burnT: 0, stamp: 0 };
    P.list.push(p);
    for (let i = Math.floor((p.x - p.r) / C); i <= Math.floor((p.x + p.r) / C); i++) for (let j = Math.floor((p.y - p.r) / C); j <= Math.floor((p.y + p.r) / C); j++) {
      const k = IF_propKey(i, j); let a = P.cells.get(k); if (!a) { a = []; P.cells.set(k, a); } a.push(p);
    }
  }
  game.dprops = P;
  return P;
}
function IF_propsReset(game) {
  const P = game.dprops || IF_propsInit(game);
  for (const p of P.list) { p.alive = true; p.hp = p.big ? IF_PROPS_CFG.hpBig : IF_PROPS_CFG.hp; p.burnT = 0; }
  P.alive = P.list.length; P.pending.length = 0;
  if (P.list.length) game.emit({ t: 'props_reset' });
}
function IF_propKill(game, p, owner, how) {
  if (!p.alive) return;
  const P = game.dprops;
  p.alive = false; p.hp = 0; P.alive--;
  game.emit({ t: 'prop', id: p.id, how, pos: IF_v3(p.x, p.y, p.z), slot: owner, big: p.big });
  if (how === 'boom') { p.burnT = IF_PROPS_CFG.burn; P.pending.push({ p, owner }); }
}
function IF_propHurt(game, p, dmg, owner) {
  if (!p.alive || !(dmg > 0)) return;
  p.hp -= dmg;
  if (p.hp <= 0) IF_propKill(game, p, owner, 'boom');
}
/** a shot or a step of a bullet from a to b: every living prop the segment passes through takes dmg (once) */
function IF_propsSegment(game, ax, ay, az, bx, by, bz, dmg, owner) {
  const P = game.dprops; if (!P || !P.alive) return;
  const C = IF_PROPS_CFG.cell, dx = bx - ax, dy = by - ay, len = Math.sqrt(dx * dx + dy * dy);
  const n = Math.max(1, Math.ceil(len / (C * 0.5))), st = ++P.stampN;
  let li = 1e9, lj = 1e9;
  for (let s = 0; s <= n; s++) {
    const t = s / n, i = Math.floor((ax + dx * t) / C), j = Math.floor((ay + dy * t) / C);
    if (i === li && j === lj) continue;
    li = i; lj = j;
    const a = P.cells.get(IF_propKey(i, j)); if (!a) continue;
    for (let k = 0; k < a.length; k++) {
      const p = a[k]; if (!p.alive || p.stamp === st) continue;
      p.stamp = st;
      const q = IF_segPointDist2(ax, ay, az, bx, by, bz, p.x, p.y, p.z + p.r * 0.4);
      if (q.d2 <= p.r * p.r) IF_propHurt(game, p, dmg, owner);
    }
  }
}
/** an explosion: full damage at the prop's skin, 40 % at the edge of the radius */
function IF_propsBlast(game, pos, radius, dmg, owner) {
  const P = game.dprops; if (!P || !P.alive || !(radius > 0) || !(dmg > 0)) return;
  const C = IF_PROPS_CFG.cell, st = ++P.stampN;
  for (let i = Math.floor((pos.x - radius) / C); i <= Math.floor((pos.x + radius) / C); i++) for (let j = Math.floor((pos.y - radius) / C); j <= Math.floor((pos.y + radius) / C); j++) {
    const a = P.cells.get(IF_propKey(i, j)); if (!a) continue;
    for (let k = 0; k < a.length; k++) {
      const p = a[k]; if (!p.alive || p.stamp === st) continue;
      p.stamp = st;
      const ex = p.x - pos.x, ey = p.y - pos.y, ez = p.z - pos.z, d = Math.max(0, Math.sqrt(ex * ex + ey * ey + ez * ez) - p.r);
      if (d < radius) IF_propHurt(game, p, dmg * (1 - 0.6 * d / radius), owner);
    }
  }
}
function IF_propsStep(game, L, dt) {
  const P = game.dprops; if (!P || !P.list.length) return;
  const F = IF_PROPS_CFG, C = F.cell;
  // last tick's wrecks go up now (a chain runs one tick a link)
  if (P.pending.length) {
    const todo = P.pending; P.pending = [];
    for (const e of todo) IF_explode(game, IF_v3(e.p.x, e.p.y, e.p.z + 30), F.blastR * (e.p.big ? 1.3 : 1), F.blastDmg * (e.p.big ? 1.5 : 1), F.blastImpact, e.owner, 'car', 'car', null);
  }
  // crushed under a walking mech
  if (P.alive) for (let n = 0; n < L.length; n++) {
    const m = L[n]; if (!m.alive || !m.onGround) continue;
    if (m.vel.x * m.vel.x + m.vel.y * m.vel.y < F.crushSpeed * F.crushSpeed) continue;
    const mr = (m.radius || (m.cls && m.cls.radius) || 90) * 0.75;
    for (let i = Math.floor((m.pos.x - mr) / C); i <= Math.floor((m.pos.x + mr) / C); i++) for (let j = Math.floor((m.pos.y - mr) / C); j <= Math.floor((m.pos.y + mr) / C); j++) {
      const a = P.cells.get(IF_propKey(i, j)); if (!a) continue;
      for (let k = 0; k < a.length; k++) {
        const p = a[k]; if (!p.alive) continue;
        const ex = p.x - m.pos.x, ey = p.y - m.pos.y, rr = mr + p.r * 0.5;
        if (ex * ex + ey * ey <= rr * rr && Math.abs(m.pos.z - p.z) < 110) IF_propKill(game, p, m.slot, 'crush');
      }
    }
  }
  // fires burn out
  for (const p of P.list) if (p.burnT > 0) { p.burnT -= dt; if (p.burnT <= 0) { p.burnT = 0; game.emit({ t: 'prop_out', id: p.id, pos: IF_v3(p.x, p.y, p.z) }); } }
}
/** @type {any} */ (IF_Game.lib).IF_PROPS_CFG = IF_PROPS_CFG;      // for the tests (this file loads after 80_game.js)
