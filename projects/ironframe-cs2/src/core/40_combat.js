// ===================================================================================================================
// IRONFRAME core, part 4: combat (DESIGN.md section 5). Weapons per family (proj, lob, hitscan, melee, missile, shield,
// ability), the bullet pool in typed arrays with a uniform-grid broad phase, missiles with proportional navigation and a
// proximity fuse, beams and effect markers for the adapter, damage with shield arcs, bubbles, stagger, splash fall-off,
// spawn protection, rookie shield and boss weak points, kill and assist credit, and the FCS lock (soft / hard / decoys).
//
// Pools the adapter renders (exact shapes, docs/INTERFACES.md section 3):
//   game.projectiles[i] {alive, pos, dir, heavy, kind:'proj'|'lob', slot}   mirrors bullet i of the typed arrays
//   game.missiles[i]    {alive, pos, dir, slot, target}
//   game.beams[i]       {alive, from, to, red, slot}                          alive cfg.weapon.beamTime (0.12 s)
//   game.effects[i]     {alive, kind:'ring'|'landing'|'bubble'|'drone'|'mine', pos, radius, slot, idx}   drone: orbits mech `slot`, idx 0/1;
//                       mine: armed after 1 s, radius = trigger radius, side = owner side
// ===================================================================================================================

const IF_BF_GRAV = 1, IF_BF_AIR = 2, IF_BF_HEAVY = 4, IF_BF_LAG = 8, IF_BF_WORLD = 16, IF_BF_CLUSTER = 32;

class IF_Bullets {
  constructor(n) {
    this.n = n;
    this.px = new Float64Array(n); this.py = new Float64Array(n); this.pz = new Float64Array(n);
    this.vx = new Float64Array(n); this.vy = new Float64Array(n); this.vz = new Float64Array(n);
    this.t = new Float32Array(n); this.tWorld = new Float32Array(n); this.life = new Float32Array(n);
    this.dmg = new Float32Array(n); this.impact = new Float32Array(n); this.splash = new Float32Array(n);
    this.owner = new Int16Array(n); this.side = new Int32Array(n); this.wid = new Int16Array(n); this.hp = new Int8Array(n);
    this.flags = new Uint8Array(n); this.bounce = new Int8Array(n); this.target = new Int16Array(n);
    this.active = new Int32Array(n); this.count = 0;
    this.free = new Int32Array(n); this.nfree = n;
    for (let i = 0; i < n; i++) this.free[i] = n - 1 - i;
    this.peak = 0; this.dropped = 0;
  }
  alloc() {
    if (this.nfree <= 0) { this.dropped++; return -1; }
    const i = this.free[--this.nfree];
    this.active[this.count++] = i;
    if (this.count > this.peak) this.peak = this.count;
    return i;
  }
  // remove the k-th active entry (swap with the last)
  kill(k) { const i = this.active[k]; this.active[k] = this.active[--this.count]; this.free[this.nfree++] = i; return i; }
  clear() { this.count = 0; this.nfree = this.n; for (let i = 0; i < this.n; i++) this.free[i] = this.n - 1 - i; }
}

// ---------------------------------------------------------------------------------------------------------- the grid
// Mechs bucketed into 512-u cells each tick (circle radius + margin), for bullets, splash and airbursts.
class IF_Grid {
  constructor(bounds) {
    this.cell = 512;
    this.x0 = bounds.min[0] - 1024; this.y0 = bounds.min[1] - 1024;
    this.w = Math.ceil((bounds.max[0] - bounds.min[0] + 2048) / this.cell); this.h = Math.ceil((bounds.max[1] - bounds.min[1] + 2048) / this.cell);
    this.head = new Int16Array(this.w * this.h).fill(-1);
    this.next = new Int16Array(IF_MAX_MECHS * 9); this.mech = new Int16Array(IF_MAX_MECHS * 9); this.used = 0;
    this.dirty = [];
    this.stamp = new Int32Array(IF_MAX_MECHS); this.stampN = 1;
  }
  ci(x) { return IF_clamp(Math.floor((x - this.x0) / this.cell), 0, this.w - 1); }
  cj(y) { return IF_clamp(Math.floor((y - this.y0) / this.cell), 0, this.h - 1); }
  build(list, n) {
    for (const c of this.dirty) this.head[c] = -1;
    this.dirty.length = 0; this.used = 0;
    for (let k = 0; k < n; k++) {
      const m = list[k], r = m.radius + 200;
      const i0 = this.ci(m.pos.x - r), i1 = this.ci(m.pos.x + r), j0 = this.cj(m.pos.y - r), j1 = this.cj(m.pos.y + r);
      for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) {
        if (this.used >= this.next.length) return;
        const c = j * this.w + i;
        if (this.head[c] < 0) this.dirty.push(c);
        this.mech[this.used] = m.slot; this.next[this.used] = this.head[c]; this.head[c] = this.used++;
      }
    }
  }
}

// ---------------------------------------------------------------------------------------------------------- helpers
// capsule of a mech: axis from z0 to z1 at (x, y), radius r. A mech is one capsule (AC convention: no hit locations).
function IF_capsule(m, px, py, pz, o) {
  const r = m.radius;
  o.x = px; o.y = py; o.z0 = pz + Math.min(r, m.height * 0.5); o.z1 = pz + Math.max(m.height - r, m.height * 0.5); o.r = r;
  return o;
}
// distance from point p to the mech's capsule surface (negative inside)
function IF_capDist(m, p) {
  const r = m.radius, z0 = m.pos.z + Math.min(r, m.height * 0.5), z1 = m.pos.z + Math.max(m.height - r, m.height * 0.5);
  const dx = p.x - m.pos.x, dy = p.y - m.pos.y, dz = p.z - IF_clamp(p.z, z0, z1);
  return Math.sqrt(dx * dx + dy * dy + dz * dz) - r;
}
function IF_center(m, o) { o.x = m.pos.x; o.y = m.pos.y; o.z = m.pos.z + m.height * 0.55; return o; }

// muzzle of a hard-point in world space (torso yaw; x forward, y left)
function IF_muzzle(m, hp, o) {
  const yr = m.torsoYaw * IF_D2R, fx = Math.cos(yr), fy = Math.sin(yr), lx = -fy, ly = fx, r = m.radius;
  const side = (hp === IF_HP_RA || hp === IF_HP_RS) ? -1 : 1;
  const shoulder = hp >= 2;
  const fwd = r * (shoulder ? 0.2 : 0.7), lat = r * (shoulder ? 0.55 : 0.9) * side, up = m.height * (shoulder ? 0.92 : 0.62);
  o.x = m.pos.x + fx * fwd + lx * lat; o.y = m.pos.y + fy * fwd + ly * lat; o.z = m.pos.z + up;
  return o;
}

// lead point for a projectile of `speed` from `from` at mech t (one refinement): into o
function IF_leadPoint(t, from, speed, frac, o) {
  IF_center(t, o);
  if (!(speed > 0) || frac <= 0) return o;
  const cx = o.x, cy = o.y, cz = o.z, vz = t.onGround ? 0 : t.vel.z;
  let tt = IF_vdist(from, o) / speed;
  for (let k = 0; k < 2; k++) {
    const x = cx + t.vel.x * tt * frac, y = cy + t.vel.y * tt * frac, z = cz + vz * tt * frac;
    tt = Math.sqrt((x - from.x) ** 2 + (y - from.y) ** 2 + (z - from.z) ** 2) / speed;
  }
  o.x = t.pos.x + t.vel.x * tt * frac; o.y = t.pos.y + t.vel.y * tt * frac; o.z = t.pos.z + t.height * 0.55 + (t.onGround ? 0 : t.vel.z * tt * frac);
  return o;
}

// AC6 ideal range (parts.json `falloff`, keyed by weapon key): full damage and impact out to ideal x range, then linear down to
// `min` at the weapon's range. Weapons not listed (explosives, missiles, melee, lobs, rail / sniper) keep full damage.
function IF_falloff(game, part, dist) {
  const F = game.P.raw.falloff, f = F && part ? F[part.key] : null;
  if (!f || !part.w || !(part.w.range > 0)) return 1;
  const R = part.w.range, i0 = R * f.ideal;
  if (dist <= i0) return 1;
  return Math.max(f.min, 1 - (1 - f.min) * (dist - i0) / Math.max(1, R - i0));
}

// ---------------------------------------------------------------------------------------------------------- damage
// Apply damage to victim. src is where it came from (shield arc), pos where it landed (events, weak points).
// Returns the AP actually removed.
function IF_applyDamage(game, v, attacker, amount, impact, pos, wkey, src, opts) {
  if (!v || !v.alive || !(amount > 0)) return 0;
  if (!game.combatOn) return 0;
  const a = attacker >= 0 ? game.mechs.get(attacker) : null;
  const self = attacker === v.slot;
  if (a && !self && !game.enemies(a, v) && !game.cfg.dmg.friendlyFire) return 0;
  if (v.protectedNow) return 0;
  if (a && a.protect > 0 && !self) a.protect = 0;
  let dmg = amount, imp = impact || 0;
  // shield arm raised and the source in front
  if (src) {
    for (let i = 0; i < 4; i++) {
      const w = v.weapons[i];
      if (w.type !== 'shield' || !w.raised) continue;
      const dx = src.x - v.pos.x, dy = src.y - v.pos.y, l = Math.sqrt(dx * dx + dy * dy);
      if (l < 1) continue;
      const yr = v.torsoYaw * IF_D2R, c = (dx * Math.cos(yr) + dy * Math.sin(yr)) / l;
      if (c >= Math.cos((w.w.arc || game.cfg.weapon.shieldHalfArc) * IF_D2R)) {
        const block = Math.min(0.9, w.w.block * w.statMult);
        dmg *= 1 - block; imp *= 1 - block;
        w.hits++;
      }
      break;
    }
  }
  // an allied pulse-shield bubble around the victim absorbs first
  if (game.bubbleCount > 0) {
    for (let i = 0; i < game.effects.length; i++) {
      const e = game.effects[i];
      if (!e.alive || e.kind !== 'bubble' || e.hp <= 0) continue;
      if (e.side !== game.side(v)) continue;
      if (IF_vdist2(e.pos, v.pos) > e.radius * e.radius) continue;
      if (src && IF_vdist2(e.pos, src) < e.radius * e.radius) continue;   // fired from inside: no protection
      const take = Math.min(e.hp, dmg);
      e.hp -= take; dmg -= take; imp *= dmg / Math.max(1e-6, dmg + take);
      if (e.hp <= 0) { e.alive = false; game.bubbleCount--; game.emit({ t: 'sound', key: 'bubble_pop', pos: IF_v3(e.pos.x, e.pos.y, e.pos.z) }); }
      break;
    }
    if (dmg <= 0) return 0;
  }
  // AC6 direct hit: a staggered mech takes the weapon's dha multiplier (kinetic high, energy low; move.stagger_dmg by default)
  let crit = false;
  if (v.staggered > 0) { const wpart = wkey ? game.P.byKey.get(wkey) : null; dmg *= (wpart && wpart.w && wpart.w.dha) || game.move.stagger_dmg; crit = true; }
  // rookie shield (caps.rookie_shield): a low rank pilot takes less from a high rank one
  if (a && v.rank > 0 && a.rank > 0) {
    for (const rs of game.P.caps.rookie_shield || []) if (v.rank < rs.below_rank && a.rank >= rs.vs_rank) { dmg *= 1 - rs.pct / 100; break; }
  }
  // boss weak points (x3)
  if (v.boss && pos) {
    const wp = IF_bossWeakPoints(game, v);
    for (let i = 0; i < wp.n; i++) {
      const s = wp.s[i];
      if ((pos.x - s.x) ** 2 + (pos.y - s.y) ** 2 + (pos.z - s.z) ** 2 <= (s.r + 30) ** 2) { dmg *= game.cfg.so.weakMult; game.stats.weakHits++; break; }
    }
  }
  if (self) dmg *= 1;   // self splash is already halved by the caller
  if (game.feat) dmg = game.featDmg(a, v, dmg, self);
  dmg = IF_traitDmg(game, a, v, dmg, self, src); imp = IF_traitImp(game, v, imp);
  if (dmg <= 0) return 0;
  dmg = Math.min(dmg, v.ap);
  v.ap -= dmg;
  if (game.feat) game.featMeter(a, v, dmg, self);
  IF_traitHit(game, a, v, dmg, self, opts);
  v.lastDamageT = game.time;
  if (a && !self) {
    v.dmgBy[attacker] += dmg; v.dmgT[attacker] = game.time;
    a.sum.damage += dmg; v.sum.dmgTaken += dmg;
    if (opts && opts.wp) { opts.wp.hits++; opts.wp.dmg += dmg; a.sum.hits++; }
    if (wkey) { const ws = a.wsum[wkey] || (a.wsum[wkey] = [0, 0]); ws[1] += dmg; }
  }
  // stagger
  if (imp > 0 && v.staggered <= 0) {
    // after a stagger the meter fills at a quarter for staggerGuard seconds (no stagger lock from sustained fire)
    const guard = game.time - v.staggerEndT < game.cfg.dmg.staggerGuard ? game.cfg.dmg.staggerGuardMult : 1;
    v.stagger += imp * guard * (v.onGround ? 1 : game.cfg.dmg.impactAirborne);
    v.staggerDecayT = game.move.stagger_decay_delay;
    if (v.stagger >= v.staggerMax) {
      v.stagger = v.staggerMax; v.staggered = game.move.stagger_time;
      v.boosting = false;
      if (a && !self) a.sum.staggers++;
      game.emit({ t: 'stagger', slot: v.slot });
    }
  }
  game.emit({ t: 'damage', victim: v.slot, attacker, amount: Math.round(dmg), pos: pos ? IF_v3(pos.x, pos.y, pos.z) : IF_v3(v.pos.x, v.pos.y, v.pos.z + v.height * 0.5), impact: Math.round(imp), weapon: wkey || '', crit });
  if (v.boss) IF_bossPhaseCheck(game, v);
  if (v.ap <= 0.5) { v.ap = 0; IF_mechDie(game, v, attacker, wkey || ''); }
  return dmg;
}

// boss weak-point spheres in world space: the back of the core always, the head from phase 1, the legs' joint at phase 2
function IF_bossWeakPoints(game, v) {
  const o = game._weak, yr = v.torsoYaw * IF_D2R, fx = Math.cos(yr), fy = Math.sin(yr), r = v.radius, h = v.height;
  let n = 0;
  const put = (f, l, z, rad) => { const s = o.s[n++]; s.x = v.pos.x + fx * f - fy * l; s.y = v.pos.y + fy * f + fx * l; s.z = v.pos.z + z; s.r = rad; };
  put(-r * 0.9, 0, h * 0.62, r * 0.45);                       // reactor at the back
  if (v.bossPhase >= 1) put(r * 0.5, 0, h * 0.93, r * 0.35);  // head sensor
  if (v.bossPhase >= 2) { put(0, r * 0.8, h * 0.3, r * 0.4); put(0, -r * 0.8, h * 0.3, r * 0.4); }
  o.n = n;
  return o;
}
function IF_bossPhaseCheck(game, v) {
  const ph = game.cfg.so.bossPhases, f = v.ap / Math.max(1, v.apMax);
  let p = 0;
  for (let i = 0; i < ph.length; i++) if (f <= ph[i]) p = i + 1;
  if (p > v.bossPhase && v.ap > 0) {
    v.bossPhase = p;
    game.emit({ t: 'say', slot: -1, text: 'ARETHA phase ' + (p + 1) + ': new weak points exposed', secs: 4 });
    game.emit({ t: 'sound', key: 'boss_phase', slot: v.slot });
    // a phase change shrugs off stagger and vents a ring
    v.stagger = 0; v.staggered = 0;
    IF_effect(game, 'ring', v.pos, 900, v.slot, 1.0);
  }
}

// a kill: credit, assists, streaks, mode scoring, events
function IF_mechDie(game, v, killer, wkey) {
  if (!v.alive) return;
  const C = game.cfg;
  v.alive = false; v.ap = 0; v.deathT = game.now; v.respawnT = game.time + (game.match.mode === 'so' && v.npc && v.team === 0 ? 1e9 : (game.match.mode === 'so' ? C.so.respawn : C.spawn.respawn));
  IF_vcopy(v.deathPos, v.pos);
  v.boosting = false; v.hover = false; v.braced = false; v.lungeT = 0; v.healLeft = 0; v.burnT = 0; v.burnAcc = 0;
  for (const w of v.weapons) { w.raised = false; w.charging = false; w.pending = false; w.salvo = 0; }
  v.lock.target = -1; v.lock.stage = 0; v.lock.t = 0;
  const k = killer >= 0 && killer !== v.slot ? game.mechs.get(killer) : null;
  const counted = game.match.phase === 'running';
  if (counted) { v.sum.deaths++; }
  if (v.aliveT > v.sum.lifeBest) v.sum.lifeBest = v.aliveT;
  // assists: >= assistPct of apMax within assistWindow seconds, not the killer
  const assist = [];
  const win = C.dmg.assistWindow, need = C.dmg.assistPct * v.apMax;
  for (const [s, o] of game.mechs) {
    if (s === killer || s === v.slot) continue;
    if (v.dmgBy[s] >= need && game.time - v.dmgT[s] <= win) { assist.push(s); if (counted) o.sum.assists++; }
  }
  v.dmgBy.fill(0);
  if (k && counted) {
    k.sum.kills++; k.streak++;
    if (wkey) { const ws = k.wsum[wkey] || (k.wsum[wkey] = [0, 0]); ws[0]++; }
    if (k.streak > k.sum.streakBest) k.sum.streakBest = k.streak;
    // bounty on the victim: killing a 5+ streak doubles the kill XP, 8+ triples it
    for (const b of (game.P.caps.bounty || []).slice().sort((x, y) => y.streak - x.streak)) {
      if (v.streak >= b.streak) { if (b.xp_mult >= 3) k.sum.bountyKills3++; else k.sum.bountyKills2++; break; }
    }
    for (const b of game.P.caps.bounty || []) if (k.streak === b.streak) game.emit({ t: 'bounty', slot: k.slot, streak: k.streak });
    if (v.npc && game.side(v) !== game.side(k)) { k.sum.pveKills++; if (v.boss) k.sum.bossKills++; }
  }
  if (game.feat) game.featOnKill(k, v);
  IF_Ai.onKill(game, k, v);
  v.streak = 0;
  game.emit({ t: 'death', slot: v.slot, killer: k ? k.slot : -1, pos: IF_v3(v.pos.x, v.pos.y, v.pos.z), weapon: wkey });
  game.emit({ t: 'kill', victim: v.slot, killer: k ? k.slot : -1, assist, weapon: wkey });
  if (counted) game.modeOnKill(v, k);
  // missiles locked on the dead mech go dumb
  for (const ms of game.missiles) if (ms.alive && ms.target === v.slot) ms.target = -1;
  for (const o of game.alive) if (o.lock.target === v.slot) { o.lock.target = -1; o.lock.stage = 0; o.lock.t = 0; }
}

// splash: full damage to 40 % of the radius, then linear to 25 % at the edge; self 50 %
function IF_explode(game, pos, radius, dmg, impact, owner, wkey, kind, wp) {
  game.emit({ t: 'explode', pos: IF_v3(pos.x, pos.y, pos.z), radius, kind: kind || wkey || 'blast' });
  if (!(radius > 0)) return;
  const D = game.cfg.dmg;
  const g = game.grid, i0 = g.ci(pos.x - radius), i1 = g.ci(pos.x + radius), j0 = g.cj(pos.y - radius), j1 = g.cj(pos.y + radius);
  const st = ++g.stampN;
  for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) {
    for (let e = g.head[j * g.w + i]; e >= 0; e = g.next[e]) {
      const s = g.mech[e];
      if (g.stamp[s] === st) continue;
      g.stamp[s] = st;
      const v = game.mechs.get(s);
      if (!v || !v.alive) continue;
      const d = Math.max(0, IF_capDist(v, pos));
      if (d > radius) continue;
      const f = d / radius;
      let mult = f <= D.splashInner ? 1 : IF_lerp(1, D.splashEdge, (f - D.splashInner) / (1 - D.splashInner));
      if (s === owner) mult *= D.selfSplash;
      IF_applyDamage(game, v, owner, dmg * mult, impact * mult, pos, wkey, pos, { wp });
    }
  }
}

// ---------------------------------------------------------------------------------------------------------- pools
function IF_effect(game, kind, pos, radius, slot, life) {
  for (let i = 0; i < game.effects.length; i++) {
    const e = game.effects[i];
    if (e.alive) continue;
    e.alive = true; e.kind = kind; IF_vcopy(e.pos, pos); e.radius = radius; e.slot = slot; e.life = life; e.hp = 0; e.side = 0; e.idx = 0; e.t = 0; e.wpi = -1; e.dmg = 0; e.follow = -1;
    return e;
  }
  return null;
}
function IF_beam(game, from, to, red, slot, w) {   // w: drawn width 1..1.5 (a charged shot, a cannon)
  let best = null;
  for (let i = 0; i < game.beams.length; i++) { const b = game.beams[i]; if (!b.alive) { best = b; break; } if (!best || b.life < best.life) best = b; }
  best.alive = true; IF_vcopy(best.from, from); IF_vcopy(best.to, to); best.red = !!red; best.slot = slot; best.w = w || 1; best.life = game.cfg.weapon.beamTime;
  game.emit({ t: 'beam', from: IF_v3(from.x, from.y, from.z), to: IF_v3(to.x, to.y, to.z), kind: red ? 'laser' : 'rail', slot });
}

// ---- the sky. The arena ceiling (bounds.max z) stops mechs; the map's sky shell sits higher (Dunes: 6 143, measured by the adapter into
// game.skyZ). A world trace up there hits the sky, and rockets used to burst on it (10 Nov 2026 playtest). IF_skyZ: the sky height,
// IF_capZ: the highest a projectile or missile cruises, IF_atSky: a point (a hit) at the sky, where shots vanish without a blast. With x, y
// it also counts the sky walls: a point outside the arena box (+100 u) and well above the ground there (Dunes: the shell is 168 u outside).
function IF_skyZ(game) {
  if (Number.isFinite(game.skyZ)) return game.skyZ;
  const A = game.arena; return Number.isFinite(A.sky) ? A.sky : A.bounds.max[2] + ((game.cfg.weapon && game.cfg.weapon.skyDefault) || 1000);
}
function IF_capZ(game) { const C = game.cfg.weapon; return Math.min(IF_skyZ(game) - (C.skyPad || 300), game.arena.bounds.max[2] + (C.ceilPad || 200)); }
function IF_atSky(game, z, x, y) {
  if (z >= IF_skyZ(game) - 64) return true;
  if (x === undefined) return false;
  const B = game.arena.bounds;
  return (x < B.min[0] - 100 || x > B.max[0] + 100 || y < B.min[1] - 100 || y > B.max[1] + 100) && z > IF_groundZ(game, x, y) + 200;
}

// The world along a ray a..b: fraction of the first obstacle (1 = clear). Heightfield always; a world trace (counted)
// only when the segment crosses a near-struct cell.
function IF_hfOpen(game) { return !!(game.world && game.world.traceLine); }
function IF_groundZ(game, x, y) { return IF_hfOpen(game) ? game.nav.heightOpen(x, y) : game.nav.height(x, y); }
function IF_rayWorld(game, a, b) {
  const open = IF_hfOpen(game);
  let f = game.nav.rayFrac(a.x, a.y, a.z, b.x, b.y, b.z, 160, open);
  if (open && game.nav.segNearStruct(a.x, a.y, b.x, b.y)) {
    const r = game.trace(a, b);
    if (r && r.hit && Number.isFinite(r.frac)) f = Math.min(f, IF_clamp(r.frac, 0, 1));
  }
  return f;
}

// first enemy capsule hit along a..b (excluding `owner` and its side); fills game._hitT, returns the mech or null
function IF_rayMechs(game, a, b, owner, side, lag) {
  let best = null, bt = 2;
  const L = game.alive, p = game._lag;
  for (let k = 0; k < L.length; k++) {
    const m = L[k];
    if (m.slot === owner || game.side(m) === side) continue;
    const r = m.radius;
    for (let pass = 0; pass < (lag ? 2 : 1); pass++) {
      const P = pass ? m.poseAgo(IF_LAG_TICKS, p) : m.pos;
      const s = IF_segCapsuleDist2(a.x, a.y, a.z, b.x, b.y, b.z, P.x, P.y, P.z + Math.min(r, m.height * 0.5), P.z + Math.max(m.height - r, m.height * 0.5));
      if (s.d2 <= r * r && s.t < bt) { bt = s.t; best = m; }
    }
  }
  game._hitT = bt;
  return best;
}

// ---------------------------------------------------------------------------------------------------------- aiming
// The point under the screen-centre reticle (humans: the adapter sends the follow camera's position and direction as camPos / camDir):
// the camera ray from where it passes the mech (its own mech and whatever is behind it don't count) out to `reach`, stopped by the
// heightfield, the world (a trace near structures) and an enemy capsule. Cached per tick; null without a camera ray (bots).
// Rounds fly from the muzzle to this point, so they land under the reticle at any range (they used to aim along the mech's eye line at a
// point 6 000 u out, which put every nearer hit below the reticle: 10 Nov 2026 playtest).
const IF_RETICLE_REACH = 12000;   // how far the reticle ray looks (u)
function IF_reticle(game, m, reach) {
  const cp = m.input.camPos, cd = m.input.camDir;
  if (!cp || !cd || !Number.isFinite(cp.x) || !Number.isFinite(cp.z) || !Number.isFinite(cd.x) || !Number.isFinite(cd.z)) return null;
  if (m.retTick === game.tickN && m.retReach === reach) return m.reticle;
  const dl = Math.sqrt(cd.x * cd.x + cd.y * cd.y + cd.z * cd.z); if (dl < 1e-6) return null;
  const ux = cd.x / dl, uy = cd.y / dl, uz = cd.z / dl;
  const t0 = Math.max(0, (m.pos.x - cp.x) * ux + (m.pos.y - cp.y) * uy + (m.pos.z + m.height * 0.5 - cp.z) * uz);
  const a = game._ra || (game._ra = IF_v3()), b = game._rb || (game._rb = IF_v3());
  a.x = cp.x + ux * t0; a.y = cp.y + uy * t0; a.z = cp.z + uz * t0;
  b.x = a.x + ux * reach; b.y = a.y + uy * reach; b.z = a.z + uz * reach;
  let f = IF_rayWorld(game, a, b);
  const e = game._re || (game._re = IF_v3());
  e.x = IF_lerp(a.x, b.x, f); e.y = IF_lerp(a.y, b.y, f); e.z = IF_lerp(a.z, b.z, f);
  // enemies only: rounds pass through allies, so the reticle on an ally aims at whatever stands behind it
  if (IF_rayMechs(game, a, e, m.slot, game.side(m), m.human)) f *= IF_clamp(game._hitT, 0, 1);
  const R = m.reticle;
  R.x = IF_lerp(a.x, b.x, f); R.y = IF_lerp(a.y, b.y, f); R.z = IF_lerp(a.z, b.z, f);
  m.retTick = game.tickN; m.retReach = reach; m.retDist = t0 + reach * f; m.retHit = f < 1;
  return R;
}

// The direction a hard-point fires: from the muzzle toward the reticle point (humans) or the eye-line point (bots), or the (led)
// soft-lock target steered within the FCS gimbal for assisted weapons. speed 0 = hitscan. Result in game._dir; the aim point in game._aimPt.
function IF_fireDir(game, m, hp, w, speed, mz) {
  const d = game._dir, ap = game._aimPt, range = w.range || 4000;
  const lk = m.lock, t = lk.target >= 0 && lk.stage >= 1 ? game.mechs.get(lk.target) : null;
  const reach = Math.min(range, 6000);
  // the reticle point out to IF_RETICLE_REACH whatever the weapon's range: a point cut at the range lies on the camera ray, but the line
  // from the offset muzzle through it leaves the ray past it (34 u off at 5 500 u for a 4 500 u rifle, test/playtest_combat.cjs)
  const R = IF_reticle(game, m, IF_RETICLE_REACH), cd = m.input.camDir, cp = m.input.camPos;
  if (R) {
    ap.x = R.x; ap.y = R.y; ap.z = R.z;
    // a lob solves its arc for the aim point: one past the range is pulled back along the muzzle line to the range
    if (w.type === 'lob') { const qx = ap.x - mz.x, qy = ap.y - mz.y, qz = ap.z - mz.z, ql = Math.sqrt(qx * qx + qy * qy + qz * qz); if (ql > range) { const k = range / ql; ap.x = mz.x + qx * k; ap.y = mz.y + qy * k; ap.z = mz.z + qz * k; } }
  } else {
    // a bot's crosshair point: along its eye line, stopped by the terrain (no trace) and at most the weapon range
    ap.x = m.aimOrigin.x + m.aimDir.x * reach; ap.y = m.aimOrigin.y + m.aimDir.y * reach; ap.z = m.aimOrigin.z + m.aimDir.z * reach;
    const f = game.nav.rayFrac(m.aimOrigin.x, m.aimOrigin.y, m.aimOrigin.z, ap.x, ap.y, ap.z, 200, IF_hfOpen(game));
    if (f < 1) { ap.x = IF_lerp(m.aimOrigin.x, ap.x, f); ap.y = IF_lerp(m.aimOrigin.y, ap.y, f); ap.z = IF_lerp(m.aimOrigin.z, ap.z, f); }
  }
  // a locked target near the crosshair sets the convergence distance (and is the aim point of lobbed rounds)
  let lp = null;
  if (t && t.alive) {
    // a bot's FCS works from what its pilot perceives (50_ai.js aim model): velocity estimate and aim error, not the true lead
    lp = (m.ai && !m.human && w.type !== 'melee' && IF_Ai.fcsPoint(m, t, mz, speed, game._lead)) || IF_leadPoint(t, mz, speed, 1, game._lead);
    const ox = lp.x - m.aimOrigin.x, oy = lp.y - m.aimOrigin.y, oz = lp.z - m.aimOrigin.z;
    if (IF_angleBetween(m.aimDir.x, m.aimDir.y, m.aimDir.z, ox, oy, oz) <= m.fcs.f.cone * game.cfg.lock.keepCone) {
      if (w.type === 'lob') { ap.x = lp.x; ap.y = lp.y; ap.z = lp.z; }
      else if (R) {
        // the target's depth along the camera ray, unless the reticle meets something nearer
        const dl = Math.sqrt(cd.x * cd.x + cd.y * cd.y + cd.z * cd.z) || 1;
        const tl = ((lp.x - cp.x) * cd.x + (lp.y - cp.y) * cd.y + (lp.z - cp.z) * cd.z) / dl;
        if (tl > 0 && tl < m.retDist) { ap.x = cp.x + cd.x / dl * tl; ap.y = cp.y + cd.y / dl * tl; ap.z = cp.z + cd.z / dl * tl; }
      }
      else { const dd = Math.sqrt(ox * ox + oy * oy + oz * oz); ap.x = m.aimOrigin.x + m.aimDir.x * dd; ap.y = m.aimOrigin.y + m.aimDir.y * dd; ap.z = m.aimOrigin.z + m.aimDir.z * dd; }
    }
  }
  // near wall / parallax: the reticle point barely in front of the muzzle (a wall in the camera's face, the muzzle past a corner the
  // camera looks around) would turn the round sideways or back: fire parallel to the camera ray instead
  if (R && w.type !== 'lob') {
    const dl = Math.sqrt(cd.x * cd.x + cd.y * cd.y + cd.z * cd.z) || 1;
    const ahead = ((ap.x - mz.x) * cd.x + (ap.y - mz.y) * cd.y + (ap.z - mz.z) * cd.z) / dl;
    if (ahead < (game.cfg.weapon.minConverge || 200)) { ap.x = mz.x + cd.x / dl * reach; ap.y = mz.y + cd.y / dl * reach; ap.z = mz.z + cd.z / dl * reach; }
  }
  d.x = ap.x - mz.x; d.y = ap.y - mz.y; d.z = ap.z - mz.z; IF_vnorm(d, d);
  if (lp && (w.assist || w.type === 'melee')) {
    let tx = lp.x - mz.x, ty = lp.y - mz.y, tz = lp.z - mz.z;
    const tl = Math.sqrt(tx * tx + ty * ty + tz * tz) || 1;
    tx /= tl; ty /= tl; tz /= tl;
    IF_steerToward(d, tx, ty, tz, m.fcs.f.gimbal);
    if (IF_angleBetween(d.x, d.y, d.z, tx, ty, tz) < 0.5) { ap.x = lp.x; ap.y = lp.y; ap.z = lp.z; }
  }
  return d;
}

// ---------------------------------------------------------------------------------------------------------- firing
function IF_fireEvent(game, m, wp, mz, d) {
  game.emit({ t: 'fire', slot: m.slot, hp: wp.hp, weapon: wp.part.key, pos: IF_v3(mz.x, mz.y, mz.z), dir: IF_v3(d.x, d.y, d.z) });
  m.lastFireT = game.time;
  if (m.protect > 0) m.protect = 0;     // spawn protection ends on firing
  wp.lastShot = game.time; wp.shots++; m.sum.shots++;
}

// spawn one bullet; returns its index or -1
function IF_spawnBullet(game, m, wp, mz, dx, dy, dz, speed, dmg, impact, splash, flags, life) {
  const B = game.bullets, i = B.alloc();
  if (i < 0) return -1;
  B.px[i] = mz.x; B.py[i] = mz.y; B.pz[i] = mz.z;
  B.vx[i] = dx * speed; B.vy[i] = dy * speed; B.vz[i] = dz * speed;
  B.t[i] = 0; B.life[i] = life; B.dmg[i] = dmg; B.impact[i] = impact; B.splash[i] = splash;
  B.owner[i] = m.slot; B.side[i] = game.side(m); B.wid[i] = wp.id; B.hp[i] = wp.hp; B.flags[i] = flags | (m.human ? IF_BF_LAG : 0);
  B.bounce[i] = wp.w.bounce || 0; B.target[i] = m.lock.stage >= 1 ? m.lock.target : -1;
  B.tWorld[i] = life + 1;
  if (!(flags & IF_BF_GRAV)) {
    // the world along the whole flight, once (heightfield; a trace only near struct, cached per hard-point)
    const C = game.cfg.weapon, dist = speed * life;
    const e = game._tb; e.x = mz.x + dx * dist; e.y = mz.y + dy * dist; e.z = mz.z + dz * dist;
    let f;
    const tc = wp.traceDir;
    if (game.time - wp.traceT < C.traceCache && IF_angleBetween(tc.x, tc.y, tc.z, dx, dy, dz) < C.traceCacheDeg && Math.abs(wp.traceZ - mz.z) < 120) f = wp.traceDist;
    else { f = IF_rayWorld(game, mz, e); wp.traceT = game.time; tc.x = dx; tc.y = dy; tc.z = dz; wp.traceDist = f; wp.traceZ = mz.z; }
    if (f < 1) { B.tWorld[i] = life * f; B.flags[i] |= IF_BF_WORLD; }
  }
  const o = game.projectiles[i];
  o.alive = true; o.pos.x = mz.x; o.pos.y = mz.y; o.pos.z = mz.z; o.dir.x = dx; o.dir.y = dy; o.dir.z = dz;
  o.heavy = !!(flags & IF_BF_HEAVY); o.kind = (flags & IF_BF_GRAV) ? 'lob' : 'proj'; o.slot = m.slot;
  return i;
}

function IF_fireProj(game, m, wp, spreadExtra) {
  const w = wp.w, mz = IF_muzzle(m, wp.hp, game._mz);
  const d = IF_fireDir(game, m, wp.hp, w, w.speed, mz);
  const pellets = w.pellets || 1, dmg = w.damage * wp.dmgMult, heavy = (w.splash > 0 || w.damage >= 400) ? IF_BF_HEAVY : 0;
  const flags = heavy | (w.airburst ? IF_BF_AIR : 0);
  const life = (w.range * (w.splash ? 1.0 : 1.15)) / w.speed;
  const s = game._spr;
  for (let p = 0; p < pellets; p++) {
    s.x = d.x; s.y = d.y; s.z = d.z;
    IF_spread(s, ((w.spread || 0) + (spreadExtra || 0)) * (m.spreadMul || 1), game.rng);
    IF_spawnBullet(game, m, wp, mz, s.x, s.y, s.z, w.speed, dmg, w.impact || 0, w.splash || 0, flags, life);
  }
  IF_fireEvent(game, m, wp, mz, d);
}

function IF_fireLob(game, m, wp, spreadExtra) {
  const w = wp.w, mz = IF_muzzle(m, wp.hp, game._mz);
  IF_fireDir(game, m, wp.hp, w, w.speed, mz);
  const ap = game._aimPt, g = game.move.gravity;
  const dx = ap.x - mz.x, dy = ap.y - mz.y, hd = Math.max(1, Math.sqrt(dx * dx + dy * dy));
  const pit = IF_ballisticPitch(w.speed, g, Math.min(hd, w.range), ap.z - mz.z, false);
  const d = game._dir, c = Math.cos(pit);
  d.x = dx / hd * c; d.y = dy / hd * c; d.z = Math.sin(pit);
  IF_spread(d, (0.4 + (spreadExtra || 0)) * (m.spreadMul || 1), game.rng);
  IF_spawnBullet(game, m, wp, mz, d.x, d.y, d.z, w.speed, w.damage * wp.dmgMult, w.impact || 0, w.splash || 0, IF_BF_GRAV | IF_BF_HEAVY | (w.cluster ? IF_BF_CLUSTER : 0), game.cfg.weapon.lobLife);
  IF_fireEvent(game, m, wp, mz, d);
  // the HUD's predicted landing ring for the shooter (grenade cannon)
  if (w.cannon) { const e = IF_effect(game, 'landing', ap, w.splash || 300, m.slot, 1.2); if (e) e.side = game.side(m); }
}

function IF_fireHitscan(game, m, wp, mult, spreadExtra) {
  if (wp.w.cone) return IF_fireFlame(game, m, wp);
  const w = wp.w, mz = IF_muzzle(m, wp.hp, game._mz);
  const d = IF_fireDir(game, m, wp.hp, w, 0, mz);
  if (spreadExtra) IF_spread(d, spreadExtra, game.rng);
  const e = game._tb; e.x = mz.x + d.x * w.range; e.y = mz.y + d.y * w.range; e.z = mz.z + d.z * w.range;
  const fw = IF_rayWorld(game, mz, e);
  e.x = mz.x + d.x * w.range * fw; e.y = mz.y + d.y * w.range * fw; e.z = mz.z + d.z * w.range * fw;
  const v = IF_rayMechs(game, mz, e, m.slot, game.side(m), m.human);
  const to = game._to;
  if (v) { const t = game._hitT; to.x = IF_lerp(mz.x, e.x, t); to.y = IF_lerp(mz.y, e.y, t); to.z = IF_lerp(mz.z, e.z, t); }
  else IF_vcopy(to, e);
  IF_fireEvent(game, m, wp, mz, d);
  IF_beam(game, mz, to, w.en_shot > 0 || !!w.cannon, m.slot, w.cannon ? 1.5 : mult > 1 ? 1.4 : 1);
  if (v) { const fo = IF_falloff(game, wp.part, IF_vdist(mz, to)); IF_applyDamage(game, v, m.slot, w.damage * wp.dmgMult * (mult || 1) * fo, (w.impact || 0) * (mult > 1 ? 1.5 : 1) * fo, to, wp.part.key, mz, { wp }); game.emit({ t: 'hit', pos: IF_v3(to.x, to.y, to.z), normal: null, kind: 'mech' }); }
  else if (fw < 1 && !IF_atSky(game, to.z, to.x, to.y)) game.emit({ t: 'hit', pos: IF_v3(to.x, to.y, to.z), normal: null, kind: 'ground' });
}

function IF_fireMelee(game, m, wp) {
  const w = wp.w, t = m.lock.target >= 0 ? game.mechs.get(m.lock.target) : null;
  const d = m.lungeDir;
  if (t && t.alive && IF_vdistXY(t.pos, m.pos) <= game.cfg.weapon.meleeLockRange) {
    d.x = t.pos.x - m.pos.x; d.y = t.pos.y - m.pos.y; d.z = 0; m.lungeTarget = t.slot;
  } else { d.x = m.aimDir.x; d.y = m.aimDir.y; d.z = 0; m.lungeTarget = -1; }
  IF_vnorm(d, d); if (Math.abs(d.z) > 0.5) { d.x = Math.cos(m.torsoYaw * IF_D2R); d.y = Math.sin(m.torsoYaw * IF_D2R); d.z = 0; }
  const lt = w.lunge_time || game.cfg.weapon.meleeLungeTime;
  m.lungeT = lt; m.lungeHp = wp.hp; m.lungeHit = false;
  m.lungeSpeed = (w.lunge || 600) / lt;
  if (t && m.lungeTarget >= 0) {   // AC lunge: reaches a locked target anywhere in the melee lock range, stops short, never through it
    const gap = Math.max(0, IF_vdistXY(t.pos, m.pos) - t.radius - m.radius);
    m.lungeSpeed = Math.min(Math.max(w.lunge || 600, game.cfg.weapon.meleeLockRange) / lt, gap / lt + 200);
  }
  const mz = IF_muzzle(m, wp.hp, game._mz);
  IF_fireEvent(game, m, wp, mz, d);
}
// during a lunge: the blade sphere in front of the mech; one hit per swing (or a whiff at the end)
function IF_meleeStep(game, m) {
  if (m.lungeHp < 0 || m.lungeHit) return;
  const wp = m.weapons[m.lungeHp], w = wp.w;
  if (!w || w.type !== 'melee') { m.lungeHp = -1; return; }
  const c = game._mz, d = m.lungeDir, hr = w.hit_radius || 180;
  // the lunge homes on its target (AC melee tracking) and slows so it arrives instead of passing
  const lt = m.lungeTarget >= 0 && m.lungeT > 0 ? game.mechs.get(m.lungeTarget) : null;
  if (lt && lt.alive) {
    const hx = lt.pos.x - m.pos.x, hy = lt.pos.y - m.pos.y, hl = Math.sqrt(hx * hx + hy * hy);
    if (hl > 1) { d.x = hx / hl; d.y = hy / hl; d.z = 0; m.lungeSpeed = Math.min(m.lungeSpeed, Math.max(0, hl - lt.radius - m.radius) / Math.max(1 / IF_TICKRATE, m.lungeT) + 200); }
  }
  c.x = m.pos.x + d.x * (m.radius + hr * 0.5); c.y = m.pos.y + d.y * (m.radius + hr * 0.5); c.z = m.pos.z + m.height * 0.55;
  let best = null, bd = Infinity;
  for (const v of game.alive) {
    if (v === m || !game.enemies(m, v)) continue;
    const dd = IF_capDist(v, c);
    if (dd <= hr && dd < bd) { bd = dd; best = v; }
  }
  if (best) {
    m.lungeHit = true; m.lungeT = Math.min(m.lungeT, 0.05);
    IF_applyDamage(game, best, m.slot, w.damage * wp.dmgMult * m.meleeMult, w.impact || 0, c, wp.part.key, m.pos, { wp });
    game.emit({ t: 'hit', pos: IF_v3(c.x, c.y, c.z), normal: null, kind: w.stagger_force ? 'pile' : 'blade' });
    if (w.stagger_force && best.alive && best.staggered <= 0 && !best.protectedNow) IF_forceStagger(game, best);
  }
  if (m.lungeT <= 0) m.lungeHp = -1;
}

// How much higher a missile flying straight up at speed v still climbs while it turns over to level at its turn rate (deg/s) under its
// acceleration: v / w + a (pi/2 - 1) / w^2. The loft ends this far (x cfg loftLead) under its apex and fully this far under a roof.
// 10 Nov 2026 playtest ("rockets still sometimes hit the roof"): the loft used to end AT the apex height and the missile then only nulled
// the sight-line rate, so every vertical pack (the starter VM-6 included) arced to the arena ceiling and landed past any target nearer
// than ~5 000 u (build/msl_probe.cjs: 0 hits of 12 at 1 200 / 2 500 / 3 700 u, apex 4 400 u).
// A lofted missile is `agile` from launch until it first points within cfg agileOff degrees of its target: it holds its launch speed and
// turns cfg loftTurn times as fast (turn radius ~300 u instead of ~2 000 u at full speed: at full speed and its normal turn rate it
// could not come down on anything nearer than ~5 000 u and circled over it instead). Then it accelerates and tracks at its normal rate,
// so a quick boost across its path still shakes it.
const IF_MSL_LOFT_TURN = 3;
function IF_mslRise(v, accel, turn) { const w = Math.max(0.2, turn * IF_D2R); return v / w + accel * 0.571 / (w * w); }
function IF_mslLoftDone(ms, lead, maxAge) {
  const rise = IF_mslRise(ms.speed, 0, ms.turn * IF_MSL_LOFT_TURN);
  return ms.pos.z + rise * lead >= ms.loftZ || ms.pos.z + rise + 40 >= ms.loftCeil || ms.age > maxAge;
}

// missiles: one launch of a salvo
function IF_launchMissile(game, m, wp, target, k) {
  const w = wp.w;
  if (wp.salvoTargets) target = wp.salvoTargets[k % wp.salvoTargets.length];
  let ms = null;
  for (let i = 0; i < game.missiles.length; i++) if (!game.missiles[i].alive) { ms = game.missiles[i]; break; }
  if (!ms) { game.stats.missileDrops++; return; }
  const mz = IF_muzzle(m, wp.hp, game._mz);
  const yr = m.torsoYaw * IF_D2R, fx = Math.cos(yr), fy = Math.sin(yr);
  ms.alive = true; ms.slot = m.slot; ms.target = target; ms.side = game.side(m); ms.wid = wp.id; ms.key = wp.part.key; ms.wp = wp;
  IF_vcopy(ms.pos, mz);
  // a fan: vertical packs go up, the rest leave forward with a small spread
  const fan = ((k % 2) ? 1 : -1) * (0.15 + 0.08 * Math.floor(k / 2));
  // the loft: only for a guided launch (an unguided one leaves along the aim line), and only as high as the space over the launcher: under
  // a deck, in a tunnel or the hangar the packs used to climb straight into the roof (10 Nov 2026 playtest). One trace per salvo.
  const capZ = IF_capZ(game);
  let loft = target >= 0 || wp.salvoTargets ? (w.loft || 0) : 0;
  if (loft > 0) {
    if (k === 0 || wp.loftTick === undefined || game.tickN - wp.loftTick > 128) {
      let top = Math.min(mz.z + loft, game.arena.bounds.max[2] - 700, capZ - 500), ceil = 1e9;
      if (game.world && game.world.traceLine) {
        const a = game._ta, b = game._tb; a.x = mz.x; a.y = mz.y; a.z = mz.z; b.x = mz.x; b.y = mz.y; b.z = mz.z + 3200;
        const r = game.trace(a, b);
        if (r && r.hit && r.pos && Number.isFinite(r.pos.z) && !IF_atSky(game, r.pos.z)) ceil = r.pos.z - 120;
      }
      wp.loftTop = Math.min(top, ceil); wp.loftCeil = ceil; wp.loftTick = game.tickN;
    }
    // no room to turn over under the roof (the turn from straight up carries a missile IF_mslRise further up): straight out
    if (wp.loftCeil - mz.z < IF_mslRise(w.speed * 0.45, 0, (w.turn || 80) * (m.fcs ? m.fcs.f.msl_turn_mult || 1 : 1) * IF_MSL_LOFT_TURN) + 100) loft = 0;
  }
  if (loft > 0) { ms.dir.x = fx * 0.25 - fy * fan; ms.dir.y = fy * 0.25 + fx * fan; ms.dir.z = 1; }
  else { ms.dir.x = m.aimDir.x - fy * fan * 0.6; ms.dir.y = m.aimDir.y + fx * fan * 0.6; ms.dir.z = m.aimDir.z + 0.08; }
  IF_vnorm(ms.dir, ms.dir);
  ms.speed = w.speed * 0.45; ms.maxSpeed = w.speed; ms.accel = w.accel || 3000;
  ms.turn = (w.turn || 80) * (m.fcs ? m.fcs.f.msl_turn_mult || 1 : 1);
  ms.dmg = w.damage * wp.dmgMult; ms.impact = w.impact || 0; ms.life = game.cfg.weapon.missileLife; ms.age = 0;
  // loft apex below the arena ceiling (and any roof over the launcher); the crosshair point for a shot without a lock
  ms.loft = loft; ms.loftZ = loft > 0 ? wp.loftTop : mz.z; ms.loftCeil = loft > 0 ? wp.loftCeil : 1e9; ms.lofting = loft > 0; ms.agile = loft > 0; ms.warned = false; ms.range = w.range || 6000;
  {
    const ar = Math.min(ms.range, 4500), R = IF_reticle(game, m, ar);
    if (R) { ms.aim.x = R.x; ms.aim.y = R.y; ms.aim.z = R.z; }
    else { ms.aim.x = mz.x + m.aimDir.x * ar; ms.aim.y = mz.y + m.aimDir.y * ar; ms.aim.z = mz.z + m.aimDir.z * ar; }
    if (ms.aim.z > capZ - 200) ms.aim.z = capZ - 200;   // a shot at the sky turns level under the ceiling instead of climbing into it
  }
  ms.broke = false;
  game.stats.missiles++; m.sum.mslFired++;
  const t = target >= 0 ? game.mechs.get(target) : null;
  if (t && (k === 0 || (wp.salvoTargets && k < wp.salvoTargets.length))) game.emit({ t: 'threat', slot: t.slot, kind: 'launch' });
  if (k === 0) IF_fireEvent(game, m, wp, mz, ms.dir); else { m.lastFireT = game.time; }
}

function IF_useAbility(game, m, wp) {
  const w = wp.w;
  switch (w.ability) {
    case 'bubble': {
      const e = IF_effect(game, 'bubble', m.pos, w.radius || 350, m.slot, w.duration || 6);
      if (!e) return false;
      e.hp = (w.shield_hp || 4000) * wp.statMult; e.side = game.side(m); e.follow = m.slot;
      game.bubbleCount++;
      break;
    }
    case 'repair': {
      // aimed ally under the crosshair within range (10 degree cone), else self
      let best = m, ba = 10;
      for (const o of game.alive) {
        if (o === m || game.side(o) !== game.side(m)) continue;
        const c = IF_center(o, game._lead), dx = c.x - m.aimOrigin.x, dy = c.y - m.aimOrigin.y, dz = c.z - m.aimOrigin.z;
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (dist > (w.range || 2000)) continue;
        const a = IF_angleBetween(m.aimDir.x, m.aimDir.y, m.aimDir.z, dx, dy, dz);
        if (a < ba) { ba = a; best = o; }
      }
      const heal = (w.heal || 2400) * wp.statMult;
      best.healLeft += heal; best.healRate = heal / (w.duration || 6);
      wp.healTarget = best.slot;
      break;
    }
    case 'decoy': {
      m.decoyT = w.immune || game.cfg.lock.decoyTime;
      for (const o of game.alive) if (o.lock.target === m.slot) { o.lock.target = -1; o.lock.stage = 0; o.lock.t = 0; o.lock.candidate = -1; }
      for (const ms of game.missiles) if (ms.alive && ms.target === m.slot) { ms.target = -1; ms.broke = true; }
      IF_effect(game, 'ring', m.pos, 300, m.slot, 0.6);
      break;
    }
    case 'drones': {
      if (m.droneN > 0) return false;
      for (let i = 0; i < (w.count || 2); i++) {
        const e = IF_effect(game, 'drone', m.pos, w.orbit || 230, m.slot, w.duration || 10);
        if (!e) break;
        e.idx = i; e.wpi = wp.hp; e.follow = m.slot; e.side = game.side(m); e.t = 0.6 + 0.35 * i; e.dmg = (w.damage || 45) * wp.dmgMult;
        m.droneN++;
      }
      if (m.droneN <= 0) return false;
      break;
    }
    case 'mines': {
      if (m.mineN >= (w.max || 4) || !m.onGround) return false;
      const p = game._hp; p.x = m.pos.x; p.y = m.pos.y; p.z = Math.max(m.pos.z, IF_groundZ(game, m.pos.x, m.pos.y)) + 8;
      const e = IF_effect(game, 'mine', p, w.trigger || 250, m.slot, w.life || 40);
      if (!e) return false;
      e.wpi = wp.hp; e.follow = -1; e.side = game.side(m); e.t = w.arm || 1.0; e.dmg = (w.damage || 1400) * wp.dmgMult;
      m.mineN++;
      break;
    }
    default: return false;
  }
  game.emit({ t: 'ability', slot: m.slot, kind: w.ability, weapon: wp.part.key });
  m.lastFireT = game.time;
  return true;
}

// ---------------------------------------------------------------------------------------------------------- per mech
function IF_hasAmmo(wp) { const w = wp.w; if (w.ammo === undefined) return true; return wp.magSize ? (wp.mag > 0) : (wp.ammo > 0); }
function IF_useAmmo(wp) {
  const w = wp.w; if (w.ammo === undefined) return;
  if (wp.magSize) { wp.mag--; if (wp.mag <= 0 && wp.ammo > 0) { wp.reloading = true; wp.reloadT = w.reload || 2; } }
  else wp.ammo--;
}
// the brace a cannon needs (none on quads / cannon_move_acc 1); spread when fired on the move
function IF_cannonPenalty(m) { return m.cannonMoveAcc >= 1 ? 0 : (m.speed > 150 || !m.onGround ? (1 - m.cannonMoveAcc) * 6 : 0); }

function IF_weaponsStep(game, m, dt) {
  const inp = m.input, fireOk = game.combatOn && m.dropT <= 0 && m.alive;
  let braced = false;
  for (let hp = 0; hp < 4; hp++) {
    const wp = m.weapons[hp], w = wp.w;
    if (!w) continue;
    const pressed = fireOk && !!inp.fire[hp], edge = pressed && !wp.wasFire;
    wp.wasFire = pressed; wp.firing = false;
    if (wp.cd > 0) wp.cd -= dt;
    if (wp.reloading) { wp.reloadT -= dt; if (wp.reloadT <= 0) { const take = Math.min(wp.magSize, wp.ammo); wp.mag = take; wp.ammo -= take; wp.reloading = false; } }
    if (wp.charges !== undefined && w.charges && wp.charges < w.charges + (wp.bonusCharges || 0)) {
      wp.chargeCd -= dt;
      if (wp.chargeCd <= 0) { wp.charges++; wp.chargeCd = w.cd || 15; }
    }
    switch (w.type) {
      case 'proj':
      case 'lob': {
        if (w.heat_time) {
          if (wp.overheat) { wp.heat -= dt / (w.cool_time || 3); if (wp.heat <= 0) { wp.heat = 0; wp.overheat = false; } }
          else if (!pressed) wp.heat = Math.max(0, wp.heat - dt / (w.cool_time || 3));
        }
        if (wp.pending) {      // a braced cannon: fire when the brace ends
          wp.windup -= dt; braced = braced || (w.cannon && m.cannonMoveAcc < 1);
          if (wp.windup <= 0) { wp.pending = false; if (w.type === 'lob') IF_fireLob(game, m, wp, wp.penalty); else IF_fireProj(game, m, wp, wp.penalty); }
          break;
        }
        if (wp.burstLeft > 0) {      // the rest of a burst (burst rifle)
          wp.burstT -= dt;
          while (wp.burstLeft > 0 && wp.burstT <= 0) {
            if (wp.reloading || !IF_hasAmmo(wp)) { wp.burstLeft = 0; break; }
            IF_useAmmo(wp); IF_fireProj(game, m, wp, 0); wp.burstLeft--; wp.burstT += w.burst_gap || 0.07;
          }
        }
        if (!pressed || wp.cd > 0 || wp.reloading || wp.overheat || !IF_hasAmmo(wp)) break;
        if (w.en_shot && !m.canSpend(w.en_shot)) break;
        wp.cd = Math.max(0, wp.cd) + wp.period;
        IF_useAmmo(wp);
        if (w.en_shot) m.spendEn(w.en_shot);
        wp.firing = true;
        if (w.cannon || w.brace) {
          wp.penalty = IF_cannonPenalty(m);
          if (w.brace && m.cannonMoveAcc < 1 && m.onGround) { wp.pending = true; wp.windup = w.brace; braced = true; break; }
        } else wp.penalty = 0;
        if (w.type === 'lob') IF_fireLob(game, m, wp, wp.penalty); else IF_fireProj(game, m, wp, wp.penalty);
        if (w.burst > 1) { wp.burstLeft = w.burst - 1; wp.burstT = w.burst_gap || 0.07; }
        if (w.heat_time) { wp.heat += wp.period / w.heat_time; if (wp.heat >= 1) { wp.heat = 1; wp.overheat = true; } }
        break;
      }
      case 'hitscan': {
        if (wp.pending) {      // wind-up (rail) or charge-and-fire (laser cannon)
          wp.windup -= dt; braced = braced || (w.cannon && m.cannonMoveAcc < 1);
          if (w.no_boost && m.boosting) {      // sniper: boosting spoils the shot (round refunded)
            wp.pending = false; wp.cd = Math.min(wp.cd, 0.8);
            if (wp.magSize) wp.mag++; else if (w.ammo !== undefined) wp.ammo++;
            break;
          }
          if (wp.windup <= 0) { wp.pending = false; IF_fireHitscan(game, m, wp, 1, wp.penalty); }
          break;
        }
        if (w.charge && !w.cannon) {
          // laser rifle: hold to charge, release fires (full charge x charge_mult)
          if (pressed && wp.cd <= 0 && !wp.charging && m.canSpend(w.en_shot || 0)) { wp.charging = true; wp.charge = 0; }
          if (wp.charging) {
            if (pressed) { wp.charge = Math.min(w.charge, wp.charge + dt); }
            else {
              wp.charging = false;
              const full = wp.charge >= w.charge - 1e-6;
              if (m.canSpend(w.en_shot || 0)) {
                m.spendEn((w.en_shot || 0) * (full ? 2 : 1));
                wp.cd = wp.period; wp.firing = true;
                IF_fireHitscan(game, m, wp, full ? w.charge_mult : 1, 0);
              }
              wp.charge = 0;
            }
          }
          break;
        }
        if (!pressed || wp.cd > 0 || wp.reloading || !IF_hasAmmo(wp)) break;
        if (w.no_boost && m.boosting) break;
        if (w.en_shot && !m.canSpend(w.en_shot)) break;
        if (w.en_shot) m.spendEn(w.en_shot);
        IF_useAmmo(wp);
        wp.cd = wp.period + (w.windup || w.charge || 0); wp.firing = true;
        wp.penalty = w.cannon ? IF_cannonPenalty(m) : 0;
        const wind = Math.max(w.windup || 0, w.cannon ? (w.charge || 0) : 0, (w.brace && m.cannonMoveAcc < 1 && m.onGround) ? w.brace : 0);
        if (wind > 0) { wp.pending = true; wp.windup = wind; braced = braced || (w.cannon && m.cannonMoveAcc < 1); game.emit({ t: 'sound', key: w.cannon ? 'charge_cannon' : 'charge_rail', slot: m.slot }); }
        else IF_fireHitscan(game, m, wp, 1, wp.penalty);
        break;
      }
      case 'melee': {
        if (!edge || wp.cd > 0 || m.lungeT > 0 || !m.canSpend(w.en_shot || 0)) break;
        m.spendEn(w.en_shot || 0);
        wp.cd = wp.period; wp.firing = true;
        IF_fireMelee(game, m, wp);
        break;
      }
      case 'missile': {
        if (wp.salvo > 0) {
          wp.salvoT -= dt;
          while (wp.salvo > 0 && wp.salvoT <= 0) {
            const k = wp.salvoN - wp.salvo;
            IF_launchMissile(game, m, wp, wp.salvoTarget, k);
            wp.salvo--; wp.salvoT += game.cfg.weapon.missileStagger;
          }
          if (wp.salvo <= 0) wp.salvoTargets = null;
          break;
        }
        if (w.multilock) { IF_multiLock(game, m, wp, pressed, dt); break; }
        // Guided when the FCS holds the lock the launcher needs. Without one the launcher still fires (10 Nov 2026 playtest: "i don't
        // know how to target them": the button did nothing until a lock was complete): a press with nothing in the FCS cone, or a tap
        // released while a lock is still building, sends the salvo unguided at the reticle point; holding the button on a target waits for
        // the lock and launches guided the moment it completes. wp.mslWait: held on a building lock.
        const need = w.lock === 'hard' ? 2 : 1;
        const lt = m.lock.target >= 0 ? game.mechs.get(m.lock.target) : null;
        const locked = !!(lt && lt.alive && m.lock.stage >= need && IF_vdist(lt.pos, m.pos) <= (w.range || 6000) * 1.05);
        const ready = wp.cd <= 0 && IF_hasAmmo(wp) && fireOk;
        let dumb = false;
        if (!pressed) { dumb = wp.mslWait && ready; wp.mslWait = false; if (!dumb) break; }
        else if (!ready) { wp.mslWait = false; break; }
        else if (!locked) {
          if (edge && !lt && !IF_lockCandidate(game, m)) dumb = true;   // nothing to lock: straight at the reticle
          else { if (edge || wp.mslWait) wp.mslWait = true; break; }   // a lock is building: hold for it (release = fire unguided)
        }
        wp.mslWait = false;
        const t = dumb ? null : lt;
        const n = Math.min(w.count || 1, w.ammo !== undefined ? wp.ammo : 99);
        wp.ammo -= w.ammo !== undefined ? n : 0;
        wp.salvo = n; wp.salvoN = n; wp.salvoT = 0; wp.salvoTarget = t ? t.slot : -1; wp.salvoTargets = null; wp.cd = wp.period; wp.firing = true;
        // first missile now
        IF_launchMissile(game, m, wp, wp.salvoTarget, 0); wp.salvo--; wp.salvoT = game.cfg.weapon.missileStagger;
        break;
      }
      case 'shield': {
        const can = pressed && m.enStalled <= 0 && m.en > 0 && m.staggered <= 0;
        wp.raised = can;
        if (can) m.spendEn(w.en_drain * dt);
        break;
      }
      case 'ability': {
        if (!edge || wp.cd > 0) break;
        if (w.charges) { if (wp.charges <= 0) break; }
        if (IF_useAbility(game, m, wp)) {
          if (w.charges) { if (wp.charges >= w.charges) wp.chargeCd = w.cd || 15; wp.charges--; wp.cd = 1.0; }
          else wp.cd = w.cd || 20;
          wp.firing = true;
        }
        break;
      }
      default: break;
    }
  }
  m.braced = braced;
  // repair over time
  if (m.healLeft > 0) {
    const h = Math.min(m.healLeft, m.healRate * dt);
    m.healLeft -= h; m.ap = Math.min(m.apMax, m.ap + h);
  }
  if (m.lungeT > 0 || m.lungeHp >= 0) IF_meleeStep(game, m);
  if (m.burnT > 0) IF_burnStep(game, m, dt);
}

// ---------------------------------------------------------------------------------------------------------- lock-on
function IF_lockStep(game, m, dt, seek) {
  const L = game.cfg.lock, lk = m.lock, f = m.fcs ? m.fcs.f : null;
  if (!f) return;
  const cyc = !!m.input.cycle && !m.prevCycle; m.prevCycle = !!m.input.cycle;
  // keep or lose the current target
  if (lk.target >= 0) {
    const t = game.mechs.get(lk.target);
    let keep = !!(t && t.alive && t.decoyT <= 0 && game.enemies(m, t));
    if (keep) {
      const c = IF_center(t, game._lead), dx = c.x - m.aimOrigin.x, dy = c.y - m.aimOrigin.y, dz = c.z - m.aimOrigin.z;
      const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
      const ang = IF_angleBetween(m.aimDir.x, m.aimDir.y, m.aimDir.z, dx, dy, dz);
      const inCone = ang <= f.cone * L.keepCone && dist <= f.range * 1.1;
      if (seek) lk.los = IF_rayWorld(game, m.aimOrigin, c) >= 0.98;
      if (!inCone || !lk.los) { lk.graceT += dt; if (lk.graceT > L.graceLos) keep = false; }
      else lk.graceT = 0;
    }
    if (keep && cyc) keep = false;   // F: next candidate (the current one is skipped below)
    if (!keep) { lk.skip = cyc ? lk.target : -1; lk.target = -1; lk.stage = 0; lk.t = 0; lk.graceT = 0; }
  }
  if (lk.target >= 0) {
    if (lk.graceT <= 0) lk.t += dt;
    const was = lk.stage;
    if (lk.stage === 0 && lk.t >= m.lockSoft) lk.stage = 1;
    if (lk.stage === 1 && lk.t >= m.lockSoft + m.lockHard) lk.stage = 2;
    if (lk.stage !== was) {
      game.emit({ t: 'lock', slot: m.slot, target: lk.target, stage: lk.stage });
      if (lk.stage === 2) game.emit({ t: 'threat', slot: lk.target, kind: 'lock' });
    }
    if (lk.stage === 2) { const t = game.mechs.get(lk.target); if (t) { t.lockedBy++; IF_addThreat(t, 'lock', m.slot, m.pos, 0); } }
    return;
  }
  if (!seek && !cyc) return;
  // seek: the best enemy in the cone with line of sight (nearest in angle, then distance); F skips the one just dropped
  let best = null, bs = Infinity;
  for (const t of game.alive) {
    if (t === m || !game.enemies(m, t) || t.decoyT > 0 || t.slot === lk.skip) continue;
    const c = IF_center(t, game._lead), dx = c.x - m.aimOrigin.x, dy = c.y - m.aimOrigin.y, dz = c.z - m.aimOrigin.z;
    const d2 = dx * dx + dy * dy + dz * dz;
    if (d2 > f.range * f.range) continue;
    const ang = IF_angleBetween(m.aimDir.x, m.aimDir.y, m.aimDir.z, dx, dy, dz);
    if (ang > f.cone) continue;
    const s = ang / f.cone + Math.sqrt(d2) / f.range * 0.6;
    if (s < bs) { bs = s; best = t; }
  }
  lk.skip = -1;
  if (!best) return;
  const c = IF_center(best, game._lead);
  if (IF_rayWorld(game, m.aimOrigin, c) < 0.98) return;
  lk.target = best.slot; lk.stage = 0; lk.t = 0; lk.los = true; lk.graceT = 0; lk.serial++;
}

// is any enemy inside the FCS cone and range (no sight check)? The FCS seeks only every few ticks: a launcher pressed with one there waits
function IF_lockCandidate(game, m) {
  const f = m.fcs ? m.fcs.f : null; if (!f) return false;
  for (const t of game.alive) {
    if (t === m || !game.enemies(m, t) || t.decoyT > 0) continue;
    const c = IF_center(t, game._lead), dx = c.x - m.aimOrigin.x, dy = c.y - m.aimOrigin.y, dz = c.z - m.aimOrigin.z;
    if (dx * dx + dy * dy + dz * dz > f.range * f.range) continue;
    if (IF_angleBetween(m.aimDir.x, m.aimDir.y, m.aimDir.z, dx, dy, dz) <= f.cone) return true;
  }
  return false;
}

function IF_addThreat(m, kind, from, pos, tti) {
  if (m.threats.length >= 8) return;
  let o = m.threatPool[m.threats.length];
  if (!o) { o = { kind: '', from: -1, x: 0, y: 0, z: 0, tti: 0 }; m.threatPool[m.threats.length] = o; }
  o.kind = kind; o.from = from; o.x = pos.x; o.y = pos.y; o.z = pos.z; o.tti = tti;
  m.threats.push(o);
}

// ---------------------------------------------------------------------------------------------------------- bullets
function IF_bulletsStep(game, dt) {
  const B = game.bullets, G = game.grid, g = game.move.gravity, P = game.P, nav = game.nav, A = game.arena.bounds;
  const lag = game._lag;
  for (let k = B.count - 1; k >= 0; k--) {
    const i = B.active[k];
    const ox = B.px[i], oy = B.py[i], oz = B.pz[i];
    const grav = B.flags[i] & IF_BF_GRAV, vz0 = B.vz[i];
    if (grav) B.vz[i] -= g * dt;
    let t1 = B.t[i] + dt, step = dt, worldHit = false;
    if (!grav && (B.flags[i] & IF_BF_WORLD) && t1 >= B.tWorld[i]) { step = Math.max(0, B.tWorld[i] - B.t[i]); worldHit = true; }
    let nx = ox + B.vx[i] * step, ny = oy + B.vy[i] * step, nz = oz + B.vz[i] * step;
    // mechs in the cells of both ends
    const owner = B.owner[i], side = B.side[i], st = ++G.stampN, useLag = (B.flags[i] & IF_BF_LAG) !== 0;
    let hit = null, ht = 2;
    const c0 = G.cj(oy) * G.w + G.ci(ox), c1 = G.cj(ny) * G.w + G.ci(nx);
    for (let pass = 0; pass < 2; pass++) {
      const c = pass ? c1 : c0;
      if (pass && c === c0) break;
      for (let e = G.head[c]; e >= 0; e = G.next[e]) {
        const s = G.mech[e];
        if (G.stamp[s] === st) continue;
        G.stamp[s] = st;
        if (s === owner) continue;
        const v = game.mechs.get(s);
        if (!v || !v.alive || game.side(v) === side) continue;
        const r = v.radius;
        for (let lp = 0; lp < (useLag ? 2 : 1); lp++) {
          const Pp = lp ? v.poseAgo(IF_LAG_TICKS, lag) : v.pos;
          const q = IF_segCapsuleDist2(ox, oy, oz, nx, ny, nz, Pp.x, Pp.y, Pp.z + Math.min(r, v.height * 0.5), Pp.z + Math.max(v.height - r, v.height * 0.5));
          if (q.d2 <= r * r && q.t < ht) { ht = q.t; hit = v; }
        }
        // air-burst: close to an airborne enemy
        if (!hit && (B.flags[i] & IF_BF_AIR) && !v.onGround) {
          const q = IF_segPointDist2(ox, oy, oz, nx, ny, nz, v.pos.x, v.pos.y, v.pos.z + v.height * 0.5);
          const ar = B.splash[i] * game.cfg.weapon.airburstRadius;
          if (q.d2 <= ar * ar && q.t < ht) { ht = q.t; hit = v; game.stats.airbursts++; }
        }
      }
    }
    const wp = null;
    const part = P.byId.get(B.wid[i]), key = part ? part.key : '';
    const owm = game.mechs.get(owner), owp = owm ? owm.weapons[B.hp[i]] : null;
    const wstat = owp && owp.id === B.wid[i] ? owp : wp;
    if (hit) {
      const hx = IF_lerp(ox, nx, ht), hy = IF_lerp(oy, ny, ht), hz = IF_lerp(oz, nz, ht);
      const hp = game._hp; hp.x = hx; hp.y = hy; hp.z = hz;
      const src = game._src; src.x = ox - B.vx[i] * 0.2; src.y = oy - B.vy[i] * 0.2; src.z = oz;
      if (B.splash[i] > 0) IF_explode(game, hp, B.splash[i], B.dmg[i], B.impact[i], owner, key, key, wstat);
      else { const fo = IF_falloff(game, part, B.t[i] * Math.sqrt(B.vx[i] * B.vx[i] + B.vy[i] * B.vy[i] + B.vz[i] * B.vz[i])); IF_applyDamage(game, hit, owner, B.dmg[i] * fo, B.impact[i] * fo, hp, key, src, { wp: wstat }); if (game.eventsFx) game.emit({ t: 'hit', pos: IF_v3(hx, hy, hz), normal: null, kind: 'mech' }); }
      IF_bulletKill(game, k); continue;
    }
    // the world
    if (grav) {
      const gz = IF_groundZ(game, nx, ny);
      let under = nz <= gz, sky = IF_atSky(game, nz, nx, ny);
      if (!under && !sky && nav.nearStruct(nx, ny) && game.world && game.world.traceLine) {
        const a = game._ta, b = game._tb; a.x = ox; a.y = oy; a.z = oz; b.x = nx; b.y = ny; b.z = nz;
        const r = game.trace(a, b);
        if (r && r.hit && Number.isFinite(r.frac)) {
          if (r.pos && Number.isFinite(r.pos.z) && IF_atSky(game, r.pos.z, r.pos.x, r.pos.y)) sky = true;
          else { under = true; nx = IF_lerp(ox, nx, r.frac); ny = IF_lerp(oy, ny, r.frac); nz = IF_lerp(oz, nz, r.frac) + 2; }
        }
      }
      if (sky) { game.stats.skyVanish = (game.stats.skyVanish || 0) + 1; IF_bulletKill(game, k); continue; }
      if (under) {
        if (B.bounce[i] > 0 && B.vz[i] < -200) {
          B.bounce[i]--; B.vz[i] = -B.vz[i] * 0.45; B.vx[i] *= 0.6; B.vy[i] *= 0.6; nz = Math.max(nz, gz + 2);
          game.emit({ t: 'sound', key: 'grenade_bounce', pos: IF_v3(nx, ny, nz) });
        } else {
          const hp = game._hp; hp.x = nx; hp.y = ny; hp.z = Math.max(nz, gz);
          IF_explode(game, hp, B.splash[i], B.dmg[i], B.impact[i], owner, key, key, wstat);
          IF_bulletKill(game, k); continue;
        }
      }
    } else if (worldHit && IF_atSky(game, nz, nx, ny)) {
      game.stats.skyVanish = (game.stats.skyVanish || 0) + 1;
      IF_bulletKill(game, k); continue;
    } else if (worldHit) {
      const hp = game._hp; hp.x = nx; hp.y = ny; hp.z = nz;
      if (B.splash[i] > 0) IF_explode(game, hp, B.splash[i], B.dmg[i], B.impact[i], owner, key, key, wstat);
      else if (game.eventsFx) game.emit({ t: 'hit', pos: IF_v3(nx, ny, nz), normal: null, kind: 'ground' });
      IF_bulletKill(game, k); continue;
    }
    if ((B.flags[i] & IF_BF_CLUSTER) && vz0 > 0 && B.vz[i] <= 0) { IF_clusterSplit(game, i, nx, ny, nz, wstat); IF_bulletKill(game, k); continue; }
    B.t[i] = t1;
    if (!grav && IF_atSky(game, nz, nx, ny)) { game.stats.skyVanish = (game.stats.skyVanish || 0) + 1; IF_bulletKill(game, k); continue; }
    if (t1 >= B.life[i] || nx < A.min[0] - 2000 || nx > A.max[0] + 2000 || ny < A.min[1] - 2000 || ny > A.max[1] + 2000 || nz < A.min[2] - 2000 || nz > A.max[2] + 3000) {
      if (B.splash[i] > 0 && (B.flags[i] & IF_BF_AIR) && !IF_atSky(game, nz, nx, ny)) { const hp = game._hp; hp.x = nx; hp.y = ny; hp.z = nz; IF_explode(game, hp, B.splash[i], B.dmg[i], B.impact[i], owner, key, key, wstat); }
      IF_bulletKill(game, k); continue;
    }
    B.px[i] = nx; B.py[i] = ny; B.pz[i] = nz;
    const o = game.projectiles[i];
    o.pos.x = nx; o.pos.y = ny; o.pos.z = nz;
    if (grav) { const sp = Math.sqrt(B.vx[i] ** 2 + B.vy[i] ** 2 + B.vz[i] ** 2) || 1; o.dir.x = B.vx[i] / sp; o.dir.y = B.vy[i] / sp; o.dir.z = B.vz[i] / sp; }
  }
}
function IF_bulletKill(game, k) { const i = game.bullets.kill(k); game.projectiles[i].alive = false; }

// ---------------------------------------------------------------------------------------------------------- missiles
function IF_missilesStep(game, dt) {
  const C = game.cfg.weapon, nav = game.nav, navN = 4, cl = game.cfg.lock.closeThreat;
  for (let i = 0; i < game.missiles.length; i++) {
    const ms = game.missiles[i];
    if (!ms.alive) continue;
    ms.age += dt; ms.life -= dt;
    if (ms.agile && (ms.age > 2.5 || !(ms.target >= 0))) ms.agile = false;
    if (!ms.agile) ms.speed = Math.min(ms.maxSpeed, ms.speed + ms.accel * dt);
    const t = ms.target >= 0 ? game.mechs.get(ms.target) : null;
    const tc = game._lead;
    if (!t || !t.alive) {
      ms.agile = false;
      // no lock (or it broke): climb to the loft apex, then fly at the crosshair point it was fired at
      if (ms.lofting && IF_mslLoftDone(ms, C.loftLead === undefined ? 0.6 : C.loftLead, 1.0)) ms.lofting = false;
      if (ms.lofting) IF_steerToward(ms.dir, 0, 0, 1, ms.turn * 2 * dt);
      else if (!ms.broke) { const ax = ms.aim.x - ms.pos.x, ay = ms.aim.y - ms.pos.y, az = ms.aim.z - ms.pos.z, ad = Math.max(1, Math.sqrt(ax * ax + ay * ay + az * az)); IF_steerToward(ms.dir, ax / ad, ay / ad, az / ad, ms.turn * 1.5 * dt); }
    }
    if (t && t.alive) {
      IF_center(t, tc);
      const dx = tc.x - ms.pos.x, dy = tc.y - ms.pos.y, dz = tc.z - ms.pos.z, dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
      // closing speed and time to impact
      const rvx = t.vel.x - ms.dir.x * ms.speed, rvy = t.vel.y - ms.dir.y * ms.speed, rvz = t.vel.z - ms.dir.z * ms.speed;
      const closing = -(dx * rvx + dy * rvy + dz * rvz) / Math.max(1, dist);
      const tti = closing > 1 ? dist / closing : 99;
      if (!ms.warned && dist < cl && ms.age > 0.2) { ms.warned = true; game.emit({ t: 'threat', slot: t.slot, kind: 'close' }); }
      IF_addThreat(t, 'missile', ms.slot, ms.pos, tti);
      // a quick boost across the missile's path inside the last 0.5 s breaks its track (turn limits: it cannot follow)
      if (tti < 0.5 && game.time - t.qbAt <= C.qbDodgeWindow) {
        const qd = t.qbDir, dot = Math.abs(qd.x * ms.dir.x + qd.y * ms.dir.y) / Math.max(1e-6, Math.sqrt(ms.dir.x * ms.dir.x + ms.dir.y * ms.dir.y));
        if (dot < 0.6) { ms.target = -1; ms.broke = true; game.stats.missileDodges++; t.sum.dodges++; }
      }
      if (ms.target >= 0) {
        if (ms.lofting) {
          // climb to the loft height, then turn over toward the target
          if (IF_mslLoftDone(ms, C.loftLead === undefined ? 0.6 : C.loftLead, 1.2)) ms.lofting = false;
          else IF_steerToward(ms.dir, 0, 0, 1, ms.turn * 2 * dt);
        }
        if (!ms.lofting && ms.age > C.missileArm * 0.5) {
          // proportional navigation: a = N * (LOS rate x Vm), capped by the turn rate
          const vm = game._v1; vm.x = ms.dir.x * ms.speed; vm.y = ms.dir.y * ms.speed; vm.z = ms.dir.z * ms.speed;
          const r2 = Math.max(1, dist * dist);
          const wx = (dy * rvz - dz * rvy) / r2, wy = (dz * rvx - dx * rvz) / r2, wz = (dx * rvy - dy * rvx) / r2;
          let ax = navN * (wy * vm.z - wz * vm.y), ay = navN * (wz * vm.x - wx * vm.z), az = navN * (wx * vm.y - wy * vm.x);
          // plus pure pursuit when far off the line (PN alone stalls when pointing away)
          const off = IF_angleBetween(ms.dir.x, ms.dir.y, ms.dir.z, dx, dy, dz);
          if (ms.agile) {
            if (off <= (C.agileOff || 12)) ms.agile = false;
            else IF_steerToward(ms.dir, dx / dist, dy / dist, dz / dist, ms.turn * IF_MSL_LOFT_TURN * dt);
          } else
          // (the pursuit ran only past 60 deg: a missile coming out of its loft 50 deg off a still target flew a wide arc over it)
          if (off > (C.pursuitOff || 25) || dist < 400) { IF_steerToward(ms.dir, dx / dist, dy / dist, dz / dist, ms.turn * dt); }
          else {
            const al = Math.sqrt(ax * ax + ay * ay + az * az);
            if (al > 1e-6) {
              const wrate = Math.min(al / ms.speed, ms.turn * IF_D2R);
              ax /= al; ay /= al; az /= al;
              const st = Math.tan(wrate * dt);
              ms.dir.x += ax * st; ms.dir.y += ay * st; ms.dir.z += az * st; IF_vnorm(ms.dir, ms.dir);
            }
          }
        }
      }
    }
    // the cruise ceiling (IF_capZ, under the sky): inside half a second of it a climbing missile levels off hard; at it, it skims along
    const capZ = IF_capZ(game);
    if (ms.dir.z > 0 && ms.pos.z + ms.dir.z * ms.speed * 0.5 > capZ) {
      const hl = Math.sqrt(ms.dir.x * ms.dir.x + ms.dir.y * ms.dir.y);
      if (hl > 1e-3) IF_steerToward(ms.dir, ms.dir.x / hl, ms.dir.y / hl, 0, Math.max(ms.turn, 90) * 3 * dt);
    }
    const ox = ms.pos.x, oy = ms.pos.y, oz = ms.pos.z;
    let nx = ox + ms.dir.x * ms.speed * dt, ny = oy + ms.dir.y * ms.speed * dt, nz = oz + ms.dir.z * ms.speed * dt;
    if (nz > capZ && nz > oz) {
      nz = Math.max(oz, Math.min(nz, capZ));
      if (ms.dir.z > 0) { ms.dir.z = 0; if (Math.abs(ms.dir.x) + Math.abs(ms.dir.y) < 1e-3) ms.dir.x = 1; IF_vnorm(ms.dir, ms.dir); }
    }
    // proximity fuse against the target (swept), then any enemy it flies through
    let fused = null;
    if (ms.age > C.missileArm) {
      if (t && t.alive && ms.target >= 0) {
        const r = t.radius + C.missileFuse * 0.5;
        const q = IF_segCapsuleDist2(ox, oy, oz, nx, ny, nz, t.pos.x, t.pos.y, t.pos.z + Math.min(t.radius, t.height * 0.5), t.pos.z + Math.max(t.height - t.radius, t.height * 0.5));
        if (q.d2 <= r * r) fused = t;
      }
      if (!fused) {
        const G = game.grid, c = G.cj(ny) * G.w + G.ci(nx);
        for (let e = G.head[c]; e >= 0; e = G.next[e]) {
          const v = game.mechs.get(G.mech[e]);
          if (!v || !v.alive || v.slot === ms.slot || game.side(v) === ms.side) continue;
          const q = IF_segCapsuleDist2(ox, oy, oz, nx, ny, nz, v.pos.x, v.pos.y, v.pos.z + Math.min(v.radius, v.height * 0.5), v.pos.z + Math.max(v.height - v.radius, v.height * 0.5));
          if (q.d2 <= v.radius * v.radius) { fused = v; break; }
        }
      }
    }
    if (fused) {
      const hp = game._hp; hp.x = nx; hp.y = ny; hp.z = nz;
      const src = game._src; src.x = ox - ms.dir.x * 200; src.y = oy - ms.dir.y * 200; src.z = oz;
      IF_applyDamage(game, fused, ms.slot, ms.dmg, ms.impact, hp, ms.key, src, { wp: ms.wp && ms.wp.id === ms.wid ? ms.wp : null });
      game.emit({ t: 'explode', pos: IF_v3(nx, ny, nz), radius: 120, kind: 'missile' });
      ms.alive = false; continue;
    }
    // the world: heightfield, a trace near struct every other tick
    const gz = IF_groundZ(game, nx, ny);
    let ground = nz <= gz, sky = IF_atSky(game, nz, nx, ny), bx = nx, by = ny, bz = Math.max(nz, gz);
    if (!ground && !sky && ((game.tickN + i) & 1) === 0 && nav.nearStruct(nx, ny) && game.world && game.world.traceLine) {
      const a = game._ta, b = game._tb; a.x = ox; a.y = oy; a.z = oz; b.x = nx + ms.dir.x * ms.speed * dt; b.y = ny + ms.dir.y * ms.speed * dt; b.z = nz + ms.dir.z * ms.speed * dt;
      const r = game.trace(a, b);
      if (r && r.hit) {
        if (r.pos && Number.isFinite(r.pos.z) && IF_atSky(game, r.pos.z, r.pos.x, r.pos.y)) sky = true;
        else { ground = true; if (r.pos && Number.isFinite(r.pos.x) && Number.isFinite(r.pos.z)) { bx = r.pos.x; by = r.pos.y; bz = r.pos.z; } }   // the blast where it hit (it used to be drawn on the roof above)
      }
    }
    // the sky (or far above the arena): gone without a blast
    if (sky || nz > game.arena.bounds.max[2] + 2000) { ms.alive = false; game.stats.skyVanish = (game.stats.skyVanish || 0) + 1; continue; }
    if (ground || ms.life <= 0) {
      game.emit({ t: 'explode', pos: IF_v3(bx, by, bz), radius: 120, kind: 'missile' });
      ms.alive = false; continue;
    }
    ms.pos.x = nx; ms.pos.y = ny; ms.pos.z = nz;
  }
}

// beams fade, effects expire / follow, bubbles keep up with their caster
// ---------------------------------------------------------------------------------------------------------- arsenal extras
// stagger on demand (pile bunker): the meter fills at once, whatever the guard window says
function IF_forceStagger(game, v) {
  v.stagger = v.staggerMax; v.staggered = game.move.stagger_time; v.boosting = false;
  game.emit({ t: 'stagger', slot: v.slot });
}

// flamethrower: a short cone in front of the muzzle; each enemy inside takes a direct hit and is set burning (m.burnT)
function IF_fireFlame(game, m, wp) {
  const w = wp.w, mz = IF_muzzle(m, wp.hp, game._mz);
  const d = IF_fireDir(game, m, wp.hp, w, 0, mz);
  IF_fireEvent(game, m, wp, mz, d);
  const R = w.range, c = game._lead, e = game._tb;
  for (const v of game.alive) {
    if (v === m || !game.enemies(m, v)) continue;
    IF_center(v, c);
    const dx = c.x - mz.x, dy = c.y - mz.y, dz = c.z - mz.z, dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
    if (dist - v.radius > R) continue;
    const slack = Math.atan2(v.radius, Math.max(1, dist)) / IF_D2R;
    if (IF_angleBetween(d.x, d.y, d.z, dx, dy, dz) - slack > w.cone) continue;
    if (dist > 300) { e.x = c.x; e.y = c.y; e.z = c.z; if (IF_rayWorld(game, mz, e) < 0.97) continue; }
    const got = IF_applyDamage(game, v, m.slot, w.damage * wp.dmgMult, w.impact || 0, c, wp.part.key, mz, { wp });
    game.emit({ t: 'hit', pos: IF_v3(c.x, c.y, c.z), normal: null, kind: 'flame' });
    if (got > 0 && v.alive) {
      if (v.burnT <= 0) game.emit({ t: 'burn', slot: v.slot, on: true });
      v.burnDps = (v.burnT > 0 && v.burnBy === m.slot ? Math.max(v.burnDps, 0) : 0) || (w.burn_dps || 150) * wp.dmgMult;
      v.burnT = w.burn_time || 3;
      v.burnBy = m.slot; v.burnHp = wp.hp; v.burnId = wp.id; v.burnKey = wp.part.key;
    }
  }
}
// damage over time: applied in 0.25 s lumps (one damage event each)
function IF_burnStep(game, m, dt) {
  m.burnT -= dt; m.burnAcc += dt;
  if (m.burnAcc >= 0.25 || m.burnT <= 0) {
    const amount = m.burnDps * m.burnAcc; m.burnAcc = 0;
    const o = game.mechs.get(m.burnBy), wp = o ? o.weapons[m.burnHp] : null;
    IF_applyDamage(game, m, m.burnBy, amount, 0, null, m.burnKey, null, { wp: wp && wp.id === m.burnId ? wp : null });
  }
  if (m.burnT <= 0 && m.alive) { m.burnT = 0; game.emit({ t: 'burn', slot: m.slot, on: false }); }
}

// multi-lock missiles: hold to lock every enemy inside the FCS cone (each takes the hard-lock time), release to fire.
// wp.mlock [{slot, p 0..1, done}] is what the HUD draws; wp.mlDone counts the finished locks.
function IF_multiLock(game, m, wp, pressed, dt) {
  const w = wp.w, f = m.fcs ? m.fcs.f : null, list = wp.mlock;
  if (pressed && wp.cd <= 0 && IF_hasAmmo(wp) && f) {
    wp.mlHold += dt;
    const maxN = w.multilock, range = Math.min(w.range || 6000, f.range || 6000);
    for (let k = list.length - 1; k >= 0; k--) {
      const L = list[k], v = game.mechs.get(L.slot);
      let inCone = false;
      if (v && v.alive && game.enemies(m, v) && v.decoyT <= 0) {
        const c = IF_center(v, game._lead), dx = c.x - m.aimOrigin.x, dy = c.y - m.aimOrigin.y, dz = c.z - m.aimOrigin.z;
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        inCone = dist <= range * 1.05 && IF_angleBetween(m.aimDir.x, m.aimDir.y, m.aimDir.z, dx, dy, dz) <= f.cone * (L.done ? game.cfg.lock.keepCone : 1);
      } else { list.splice(k, 1); if (L.done) wp.mlDone--; continue; }
      if (inCone) {
        L.out = 0;
        if (!L.done) { L.p = Math.min(1, L.p + dt / m.lockHard); if (L.p >= 1) { L.done = true; wp.mlDone++; game.emit({ t: 'sound', key: 'ui_lock3', slot: m.slot }); } }
      } else if (L.done) { L.out += dt; if (L.out > 0.5) { list.splice(k, 1); wp.mlDone--; } }
      else { L.p -= dt * 2; if (L.p <= 0) list.splice(k, 1); }
    }
    if (list.length < maxN) {
      for (const v of game.alive) {
        if (list.length >= maxN) break;
        if (v === m || !game.enemies(m, v) || v.decoyT > 0 || list.some((L) => L.slot === v.slot)) continue;
        const c = IF_center(v, game._lead), dx = c.x - m.aimOrigin.x, dy = c.y - m.aimOrigin.y, dz = c.z - m.aimOrigin.z;
        if (dx * dx + dy * dy + dz * dz > range * range) continue;
        if (IF_angleBetween(m.aimDir.x, m.aimDir.y, m.aimDir.z, dx, dy, dz) > f.cone) continue;
        if (IF_rayWorld(game, m.aimOrigin, c) < 0.97) continue;      // one line-of-sight check when a candidate enters the cone
        list.push({ slot: v.slot, p: 0, done: false, out: 0 });
      }
    }
    return;
  }
  // released (or cooling down): fire what is locked
  if (wp.mlHold > 0 || list.length) {
    if (wp.mlDone > 0 && wp.cd <= 0 && IF_hasAmmo(wp)) {
      const tg = [];
      for (const L of list) if (L.done) tg.push(L.slot);
      const n = Math.min(w.count || 1, w.ammo !== undefined ? wp.ammo : 99);
      if (tg.length && n > 0) {
        wp.ammo -= w.ammo !== undefined ? n : 0;
        wp.salvo = n; wp.salvoN = n; wp.salvoT = 0; wp.salvoTargets = tg; wp.salvoTarget = tg[0]; wp.cd = wp.period; wp.firing = true;
        IF_launchMissile(game, m, wp, tg[0], 0); wp.salvo--; wp.salvoT = game.cfg.weapon.missileStagger;
      }
    } else if (m.human && wp.mlHold > 0 && wp.cd <= 0 && IF_hasAmmo(wp) && game.combatOn && m.alive && m.dropT <= 0) {
      // released with no finished lock: the salvo goes unguided at the reticle (a pilot's button always does something)
      const n = Math.min(w.count || 1, w.ammo !== undefined ? wp.ammo : 99);
      if (n > 0) {
        wp.ammo -= w.ammo !== undefined ? n : 0;
        wp.salvo = n; wp.salvoN = n; wp.salvoT = 0; wp.salvoTargets = null; wp.salvoTarget = -1; wp.cd = wp.period; wp.firing = true;
        IF_launchMissile(game, m, wp, -1, 0); wp.salvo--; wp.salvoT = game.cfg.weapon.missileStagger;
      }
    }
    list.length = 0; wp.mlDone = 0; wp.mlHold = 0;
  }
}

// cluster artillery: the shell opens at its apex into w.pellets bomblets that fall with a spread
function IF_clusterSplit(game, i, x, y, z, wstat) {
  const B = game.bullets, part = game.P.byId.get(B.wid[i]), w = part ? part.w : null;
  const n = w ? (w.pellets || 6) : 6, key = part ? part.key : '';
  const p = game._hp; p.x = x; p.y = y; p.z = z;
  IF_explode(game, p, 0, 0, 0, B.owner[i], key, 'cluster_split', wstat);
  const sc = w ? (w.scatter || 330) : 330, bs = w ? (w.bomb_splash || 260) : 260;
  for (let b = 0; b < n; b++) {
    const j = B.alloc();
    if (j < 0) break;
    const ang = (b / n) * 6.2831853 + game.rng() * 0.8, sp = sc * (0.55 + 0.9 * game.rng());
    B.px[j] = x; B.py[j] = y; B.pz[j] = z;
    B.vx[j] = B.vx[i] + Math.cos(ang) * sp; B.vy[j] = B.vy[i] + Math.sin(ang) * sp; B.vz[j] = B.vz[i] - 40;
    B.t[j] = 0; B.tWorld[j] = game.cfg.weapon.lobLife + 1; B.life[j] = game.cfg.weapon.lobLife;
    B.dmg[j] = B.dmg[i]; B.impact[j] = B.impact[i] * 0.4; B.splash[j] = bs;
    B.owner[j] = B.owner[i]; B.side[j] = B.side[i]; B.wid[j] = B.wid[i]; B.hp[j] = B.hp[i];
    B.flags[j] = IF_BF_GRAV | IF_BF_HEAVY; B.bounce[j] = 0; B.target[j] = -1;
    const o = game.projectiles[j];
    o.alive = true; o.pos.x = x; o.pos.y = y; o.pos.z = z; o.dir.x = 0; o.dir.y = 0; o.dir.z = -1; o.heavy = true; o.kind = 'lob'; o.slot = B.owner[i];
  }
}

// orbit drones: circle the owner, one line-of-sight check and one cheap hit per shot, at the owner's soft-locked target
function IF_droneStep(game, e, dt) {
  const o = game.mechs.get(e.follow);
  if (!o || !o.alive || e.life <= 0) { e.alive = false; if (o && o.droneN > 0) o.droneN--; return; }
  const wp = o.weapons[e.wpi], w = wp && wp.w;
  if (!w || w.ability !== 'drones') { e.alive = false; if (o.droneN > 0) o.droneN--; return; }
  const a = game.time * (w.spin || 2.4) + e.idx * Math.PI, r = e.radius;
  e.pos.x = o.pos.x + Math.cos(a) * r; e.pos.y = o.pos.y + Math.sin(a) * r; e.pos.z = o.pos.z + o.height * 0.95 + Math.sin(a * 1.7) * 25;
  e.t -= dt;
  if (e.t > 0) return;
  const t = o.lock.target >= 0 && o.lock.stage >= 1 ? game.mechs.get(o.lock.target) : null;
  if (!t || !t.alive || !game.enemies(o, t) || t.decoyT > 0) { e.t = 0.2; return; }
  const c = IF_center(t, game._lead);
  if (IF_vdist(e.pos, c) > (w.range || 3500)) { e.t = 0.2; return; }
  e.t += 1 / (w.rate || 1.5);
  const f = IF_rayWorld(game, e.pos, c);
  if (f < 0.97) return;
  IF_beam(game, e.pos, c, true, o.slot);
  game.emit({ t: 'sound', key: w.shot_sound || 'smg', pos: IF_v3(e.pos.x, e.pos.y, e.pos.z) });
  IF_applyDamage(game, t, o.slot, e.dmg, w.impact || 0, c, wp.part.key, e.pos, { wp });
  wp.shots++;
  game.emit({ t: 'hit', pos: IF_v3(c.x, c.y, c.z), normal: null, kind: 'mech' });
}

// proximity mines: armed after w.arm seconds, checked ten times a second, blast on the first enemy inside the trigger radius
function IF_mineStep(game, e, dt) {
  const o = game.mechs.get(e.slot), wp = o ? o.weapons[e.wpi] : null, w = wp && wp.w && wp.w.ability === 'mines' ? wp.w : null;
  if (e.life <= 0) { e.alive = false; if (o && o.mineN > 0) o.mineN--; return; }
  e.t -= dt;
  if (e.t > 0) return;
  e.t = 0.1;
  for (const v of game.alive) {
    if (game.side(v) === e.side || v.protectedNow) continue;
    if (IF_capDist(v, e.pos) > e.radius) continue;
    e.alive = false; if (o && o.mineN > 0) o.mineN--;
    IF_explode(game, e.pos, w ? (w.splash || 350) : 350, e.dmg, w ? (w.impact || 600) : 600, e.slot, wp && wp.part ? wp.part.key : 'mine', 'mine', wp && w ? wp : null);
    return;
  }
}

function IF_fxStep(game, dt) {
  for (let i = 0; i < game.beams.length; i++) { const b = game.beams[i]; if (b.alive) { b.life -= dt; if (b.life <= 0) b.alive = false; } }
  for (let i = 0; i < game.effects.length; i++) {
    const e = game.effects[i];
    if (!e.alive) continue;
    e.life -= dt;
    if (e.kind === 'drone') IF_droneStep(game, e, dt);
    else if (e.kind === 'mine') IF_mineStep(game, e, dt);
    else if (e.kind === 'bubble') {
      const m = game.mechs.get(e.follow);
      if (m && m.alive) { e.pos.x = m.pos.x; e.pos.y = m.pos.y; e.pos.z = m.pos.z + m.height * 0.4; }
      if (e.life <= 0 || !m || !m.alive) { e.alive = false; game.bubbleCount--; }
    } else if (e.life <= 0) e.alive = false;
  }
}
