// ===================================================================================
// Part 3b: sea creatures (Depth Racer). A track can have giant creatures that cross it at one spot (over a glide or
// a jump) on a fixed cycle: each pass sweeps a chain of body segments sideways across the track and away again,
// alternating direction. Anything solid they touch is shoved along with them, skids and loses shield. Everything is a
// function of the race clock, so every client and the sim agree, and the HUD can warn the drivers coming up to it.
// ===================================================================================

const CREATURE_KINDS = {
  //          segments, radius, gap between segments, sway along the track, bob, shove, damage
  serpent: { segs: 9, r: 70, gap: 120, sway: 90, bob: 40, knock: 760, damage: 22 },
  manta:   { segs: 1, r: 240, gap: 0, sway: 0, bob: 70, knock: 620, damage: 16 },
  whale:   { segs: 3, r: 230, gap: 330, sway: 30, bob: 50, knock: 900, damage: 24 },
};

// track data: { kind, i (sample), h (height over the track there), period, phase, speed, span }
function makeCreatures(track) {
  return (track.creatureDefs || []).map((d, k) => {
    const K = CREATURE_KINDS[d.kind] || CREATURE_KINDS.serpent;
    const segs = [];
    for (let j = 0; j < K.segs; j++) segs.push({ x: 0, y: 0, z: 0, yaw: 0 });
    const len = (K.segs - 1) * K.gap;
    return { id: k, kind: d.kind, K, i: d.i, h: d.h || 0, period: d.period, phase: d.phase || 0, speed: d.speed, span: d.span,
             len, travel: 2 * d.span + len, active: false, dir: 1, cycle: -1, segs, warned: -1 };
  });
}

// where every creature is at race time t (seconds since the start of the countdown)
function placeCreatures(arena, t) {
  const T = arena.track;
  for (const cr of arena.creatures) {
    const tt = t + cr.phase;
    const cycle = Math.floor(tt / cr.period);
    const local = tt - cycle * cr.period;
    const dist = local * cr.speed;                          // how far the head has come from its start
    cr.cycle = cycle;
    cr.active = dist < cr.travel;
    cr.dir = cycle % 2 ? -1 : 1;
    if (!cr.active) continue;
    const p = T.point(cr.i * T.step);
    const nx = p.nx, ny = p.ny, tx = p.tx, ty = p.ty;
    const z0 = T.z[cr.i] + cr.h;
    const K = cr.K;
    const headD = cr.dir * (-cr.span + dist);                // lateral offset of the head (left is +)
    for (let j = 0; j < cr.segs.length; j++) {
      const s = cr.segs[j];
      const d = headD - cr.dir * j * K.gap;
      const w = tt * 2.4 - j * 0.7;
      const along = K.sway * Math.sin(w);
      s.x = p.x + nx * d + tx * along; s.y = p.y + ny * d + ty * along;
      s.z = z0 + K.bob * Math.sin(tt * 1.3 + j * 0.5);
      // heading: across the track, turned a little with the sway
      s.yaw = Math.atan2(ny * cr.dir, nx * cr.dir) + 0.35 * Math.cos(w) * (K.sway ? 1 : 0);
    }
  }
}

// creatures against the cars: a shove along the creature's way, a skid and a hit to the shield
function creatureHits(arena, cars) {
  for (const cr of arena.creatures) {
    if (!cr.active) continue;
    const K = cr.K, head = cr.segs[0];
    const reach = K.r + CAR_R;
    const p = arena.track.point(cr.i * arena.track.step);
    for (const c of cars) {
      if (!c.solid || c.noDamage > 0 || c.creatureCd > 0) continue;
      // quick reject: near the crossing at all?
      if (Math.abs(c.x - p.x) > cr.span + 600 || Math.abs(c.y - p.y) > cr.span + 600) continue;
      let hit = null;
      for (const s of cr.segs) {
        const dx = c.x - s.x, dy = c.y - s.y, dz = (c.z + 20) - s.z;
        if (dx * dx + dy * dy + dz * dz < reach * reach) { hit = s; break; }
      }
      if (!hit) continue;
      c.creatureCd = 1.0;
      if (c.aegis > 0) { arena.events.push({ type: 'creatureHit', car: c, cr, blocked: true }); continue; }
      const nx = p.nx * cr.dir, ny = p.ny * cr.dir;
      // on the road: shoved hard across it. In the air: swatted (a smaller shove, knocked down out of the jump),
      // since a full shove there flies the car out over the rails nearly every time (it stops climbing)
      const k = c.air && !c.fly ? RULES.creatureAirKnock : 1;
      c.vx = c.vx * 0.75 + nx * K.knock * k; c.vy = c.vy * 0.75 + ny * K.knock * k;
      if (c.fly) c.vz = Math.max(c.vz, 160);
      else if (c.air) c.vz = Math.min(c.vz, 0);
      c.stagger = RULES.spinStagger * 1.2; c.knockCd = 0.5;
      c.damage(K.damage, null, arena.raceTic); c.fx |= 1;
      arena.events.push({ type: 'creatureHit', car: c, cr, blocked: false });
    }
  }
}

// creatures a car is coming up to: the first one ahead within `within` units of road that will be crossing when the
// car gets there (bots slow down for it; the HUD warns people)
function creatureAhead(arena, car, within) {
  const T = arena.track, L = T.len;
  let best = null;
  for (const cr of arena.creatures) {
    const ahead = ((cr.i * T.step - car.s) % L + L) % L;
    if (ahead > within || ahead < 0) continue;
    const eta = ahead / Math.max(300, car.speed);
    const tt = arena.time + eta + cr.phase;
    const local = tt - Math.floor(tt / cr.period) * cr.period;
    const dist = local * cr.speed;
    // its body covers the road between these head distances
    const onRoad = dist > cr.span - 450 && dist < cr.span + cr.len + 450;
    if (onRoad && (!best || ahead < best.ahead)) best = { cr, ahead, eta };
  }
  return best;
}
