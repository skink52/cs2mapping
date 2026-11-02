// ===================================================================================
// CS2 adapter, part 3: enemies. Pooled props with a tiny state machine each: chase, attack (melee / telegraphed shot / flown bolt),
// hurt by real bullets (the eye -> impact segment crossing the body, so solidity doesn't matter), knives and the dash.
// ===================================================================================
const ROOMS = new Map();   // room id -> { enemies: [], bolts: [], cleared, exitOpen, squad, spawnedAt, waveLeft }

function roomState(id) {
  let r = ROOMS.get(id);
  if (!r) { r = { id, enemies: [], bolts: [], cleared: false, exitOpen: false, squad: -1, waveLeft: 0, spawnQueue: [], beacon: null, beaconSnd: null }; ROOMS.set(id, r); }
  return r;
}

function spawnWave(G, roomId, count, floor, boss) {
  const rm = LAYOUT.rooms[roomId]; const R = roomState(roomId);
  R.cleared = false; R.exitOpen = false; R.waveLeft = 0; R.spawnQueue = [];
  const mix = WAVE_MIX[Math.min(WAVE_MIX.length - 1, floor - 1)];
  const bag = []; for (const k in mix) for (let i = 0; i < mix[k]; i++) bag.push(k);
  // never right on top of the squad: spots at least SPAWN_MIN_DIST from the entry plate (all spots if the room is too small for that)
  const ex = rm.entry; let spots = rm.spots.filter((s) => Math.hypot(s[0] - ex[0], s[1] - ex[1]) >= CONFIG.SPAWN_MIN_DIST);
  if (spots.length < 6) spots = rm.spots.slice();
  spots = G.rng.shuffle(spots);
  const kinds = [];
  for (let i = 0; i < count; i++) kinds.push(G.rng.pick(bag));
  if (boss) { kinds.push('golem', 'golem'); }
  // sentinels stand on the dais or against the far wall; the rest take any spot
  // the wave wakes one guardian at a time: the first after WAVE_GRACE, then one every WAVE_TRICKLE (sentinels first so the room reads at a glance)
  kinds.sort((a, b) => (a === 'sentinel' ? 0 : 1) - (b === 'sentinel' ? 0 : 1));
  kinds.forEach((k, i) => { const s = spots[i % spots.length]; R.spawnQueue.push({ kind: k, x: s[0], y: s[1], floor, wakeAt: E.now + CONFIG.WAVE_GRACE + i * CONFIG.WAVE_TRICKLE }); });
  R.waveLeft = R.spawnQueue.length;
}

function spawnOne(G, R, q) {
  const kind = ENEMIES[q.kind];
  const hp = Math.round(kind.hp * (1 + 0.25 * (q.floor - 1)));
  const pos = { x: q.x, y: q.y, z: kind.z };
  const rm = LAYOUT.rooms[R.id]; const yaw0 = kind.turn === false ? V.yawTo(pos, { x: rm.entry[0], y: rm.entry[1] }) : G.rng.int(360);
  // it rises out of the floor over the last second before it wakes (parked under the floor until then: the vault box hides it)
  const p = poolTake(kind.model, { x: pos.x, y: pos.y, z: pos.z - kind.height - 8 }, yaw0, kind.scale, kind.tint === false ? undefined : kind.color);
  if (!p) return false;
  const en = { id: p.id, prop: p, kind, key: q.kind, hp, maxHp: hp, pos, yaw: yaw0, room: R.id, nextAttack: (q.wakeAt || E.now) + 1.0 + G.rng.next() * 1.5,
               telegraphAt: 0, target: null, bob: G.rng.next() * 6.28, alive: true, hitFlash: 0, hitSndAt: 0, wakeAt: q.wakeAt || E.now, awake: false, moving: false };
  R.enemies.push(en);
  return true;
}

function enemyTick(G, R, members) {
  // spawn a few per tick so a wave never hitches the server
  let budget = 3;
  while (R.spawnQueue.length && budget-- > 0) { if (!spawnOne(G, R, R.spawnQueue.shift())) break; }
  const alive = members.filter((m) => m.alive);
  for (const en of R.enemies) {
    if (!en.alive) continue;
    if (!en.awake) {
      // dormant: rise through the floor over the last second, no moving, no attacking (bullets still count)
      const t = clamp(1 - (en.wakeAt - E.now), 0, 1); const kk = en.kind;
      if (t > 0) poolMove(en.prop, { x: en.pos.x, y: en.pos.y, z: kk.z - (kk.height + 8) * (1 - t) }, en.yaw);
      if (E.now >= en.wakeAt) { en.awake = true; if (kk.speed > 200) sfx('drone_lunge', en.pos); }
      continue;
    }
    // nearest living squad member
    let best = null, bd = 1e9;
    for (const m of alive) { const d = V.dist2d(m.lastPos, en.pos); if (d < bd) { bd = d; best = m; } }
    en.target = best;
    const k = en.kind;
    if (best && k.speed > 0 && bd > k.reach * 0.8) {
      const dir = V.norm({ x: best.lastPos.x - en.pos.x, y: best.lastPos.y - en.pos.y, z: 0 });
      let step = k.speed * E.dt;
      // keep off pillars and each other (cheap: push away from anything within 2 radii)
      let px = 0, py = 0;
      for (const o of R.enemies) { if (o === en || !o.alive) continue; const d = V.dist2d(o.pos, en.pos); if (d < (k.radius + o.kind.radius) * 1.2 && d > 0.1) { px += (en.pos.x - o.pos.x) / d; py += (en.pos.y - o.pos.y) / d; } }
      const rm = LAYOUT.rooms[en.room];
      for (const [qx, qy] of rm.pillars) { const d = V.dist2d({ x: qx, y: qy }, en.pos); if (d < k.radius + 48 && d > 0.1) { px += 2 * (en.pos.x - qx) / d; py += 2 * (en.pos.y - qy) / d; } }
      let nx = en.pos.x + (dir.x + px * 0.5) * step, ny = en.pos.y + (dir.y + py * 0.5) * step;
      const b = rm.box; nx = clamp(nx, b[0] + k.radius + 8, b[3] - k.radius - 8); ny = clamp(ny, b[1] + k.radius + 8, b[4] - k.radius - 8);
      en.pos.x = nx; en.pos.y = ny; en.moving = true;
      if (k.turn !== false) en.yaw = V.yawTo(en.pos, best.lastPos);
    } else { en.moving = false; if (best && k.turn !== false) en.yaw = V.yawTo(en.pos, best.lastPos); }
    // procedural motion: drones hover and sway, walkers stomp (a bob with a pitch/roll rock per step), turrets sit still
    let z = k.z, pitch = 0, roll = 0;
    if (k.speed > 200) { en.bob += E.dt * 3; z += Math.sin(en.bob) * 6; roll = Math.sin(en.bob * 0.7) * 6; pitch = en.moving ? 8 : 0; }
    else if (k.speed > 0 && en.moving) { en.bob += E.dt * (k.height > 100 ? 5 : 7); const s = Math.sin(en.bob); z += Math.abs(s) * (k.height > 100 ? 5 : 3); roll = s * (k.height > 100 ? 4 : 2.5); pitch = Math.cos(en.bob * 2) * 1.5; }
    poolMove(en.prop, { x: en.pos.x, y: en.pos.y, z }, en.yaw, pitch, roll);
    // attacks
    if (best && E.now >= en.nextAttack) {
      if (k.attack === 'melee') {
        if (bd <= k.reach) { hurtPlayer(G, best, k.dmg, en, k.armorIgnore); en.nextAttack = E.now + k.rate; sfx(en.key === 'golem' ? 'golem_slam' : 'drone_lunge', en.pos); }
      } else if (k.attack === 'shot') {
        if (!en.telegraphAt) { en.telegraphAt = E.now; sfx('sentinel_charge', en.pos); try { en.prop.ent.SetColor({ r: 255, g: 60, b: 200, a: 255 }); } catch (e) { /* */ } }
        else if (E.now - en.telegraphAt >= (k.telegraph || 0.5)) {
          en.telegraphAt = 0; en.nextAttack = E.now + k.rate;
          try { const c = k.tint === false ? { r: 255, g: 255, b: 255 } : k.color; en.prop.ent.SetColor({ r: c.r, g: c.g, b: c.b, a: 255 }); } catch (e) { /* */ }
          if (bd <= k.reach && best.alive) {
            const from = { x: en.pos.x, y: en.pos.y, z: en.pos.z + k.height * 0.7 }; const to = best.pawn.GetEyePosition();
            const tr = Instance.TraceLine({ start: from, end: to, ignoreEntity: en.prop.ent });
            if (tr.hitEntity === best.pawn || !tr.didHit || tr.fraction > 0.98) { if (!insideDome(to) || insideDome(from)) hurtPlayer(G, best, k.dmg, en, false); }
            G.fx.tracer(from, to, { r: 255, g: 60, b: 200 }); sfx('sentinel_shot', from);
          }
        }
      } else if (k.attack === 'bolt') {
        if (bd <= k.reach) {
          const from = { x: en.pos.x, y: en.pos.y, z: en.pos.z + k.height * 0.6 };
          const to = best.pawn.GetEyePosition(); to.z -= 16;
          const dir = V.norm(V.sub(to, from));
          const prop = poolTake(FXM.bolt, from, V.yawTo(from, to), 1, { r: 255, g: 200, b: 90, a: 255 });
          if (prop) { R.bolts.push({ prop, pos: from, dir, speed: k.boltSpeed, dmg: k.dmg, born: E.now, from: en }); sfx('bolt_launch', from); }
          en.nextAttack = E.now + k.rate;
        }
      }
    }
  }
  // bolts: script-flown, stopped by walls, players and domes
  for (let i = R.bolts.length - 1; i >= 0; i--) {
    const b = R.bolts[i]; const next = V.add(b.pos, V.mul(b.dir, b.speed * E.dt));
    let dead = E.now - b.born > 3;
    const tr = Instance.TraceLine({ start: b.pos, end: next, ignoreEntity: b.prop.ent, ignorePlayers: true });
    if (tr.didHit) dead = true;
    const dIn = insideDome(next); if (dIn && !insideDome(b.pos)) dead = true;
    for (const m of alive) { const o = m.lastPos; if (Math.abs(o.x - next.x) < 24 && Math.abs(o.y - next.y) < 24 && next.z > o.z - 8 && next.z < o.z + 72) { hurtPlayer(G, m, b.dmg, b.from, false); dead = true; break; } }
    if (dead) { if (E.now - b.born <= 3) sfx('bolt_hit', b.pos); poolGive(b.prop); R.bolts.splice(i, 1); continue; }
    b.pos = next; poolMove(b.prop, next);
  }
}

function hurtPlayer(G, m, dmg, en, armorIgnore) {
  if (!m.alive || E.now < (m.immuneUntil || 0)) return;
  let flags = CSDamageFlags.NONE; if (armorIgnore) flags |= CSDamageFlags.IGNORE_ARMOR;
  try { m.pawn.TakeDamage({ damage: dmg, inflictor: en.prop.ent, damageTypes: en.kind.attack === 'melee' ? CSDamageTypes.CLUB : CSDamageTypes.BULLET, damageFlags: flags }); } catch (e) { /* */ }
}

function hurtEnemy(G, en, dmg, p, melee) {
  if (!en.alive) return;
  en.hp -= dmg;
  try { en.prop.ent.SetColor({ r: 255, g: 255, b: 255, a: 255 }); en.hitFlash = E.now + 0.08; } catch (e) { /* */ }
  if (en.hp > 0 && E.now - (en.hitSndAt || 0) > 0.09) { en.hitSndAt = E.now; sfx('enemy_hit', { x: en.pos.x, y: en.pos.y, z: en.pos.z + en.kind.height * 0.5 }); }
  if (en.hp <= 0) {
    en.alive = false;
    const R = roomState(en.room);
    R.waveLeft = Math.max(0, R.waveLeft - 1);
    G.fx.burst(en.pos, en.kind.color); sfx('enemy_die', en.pos);
    poolGive(en.prop);
    if (p) { G.match && G.match.enemyKilled(p.slot, en.key); if (melee) { p.meleeKills++; if (p.cls === 'ninja') p.cdUntil = 0; } }
    if (R.waveLeft === 0 && !R.spawnQueue.length && !R.cleared) { R.cleared = true; G.match && G.match.roomCleared(en.room, E.now); }
  }
}

function enemiesNear(pos, r) {
  const out = [];
  for (const R of ROOMS.values()) for (const en of R.enemies) if (en.alive && V.dist2d(en.pos, pos) <= r) out.push(en);
  return out;
}
function clearRoomEnemies(roomId) {
  const R = ROOMS.get(roomId); if (!R) return;
  for (const en of R.enemies) if (en.alive) { en.alive = false; poolGive(en.prop); }
  for (const b of R.bolts) poolGive(b.prop);
  if (R.beacon) { poolGive(R.beacon); R.beacon = null; }
  if (R.beaconSnd) { sfxStop(R.beaconSnd); R.beaconSnd = null; }
  R.enemies = []; R.bolts = []; R.spawnQueue = []; R.waveLeft = 0; R.cleared = false; R.exitOpen = false; R.squad = -1;
}

// a bullet from `shooter` that ended at `impact`: the first enemy whose body the eye -> impact segment crosses is hit
function bulletHit(G, shooter, weapon, impact) {
  const p = PL.get(slotOf(shooter)); if (!p || !p.alive) return;
  const eye = shooter.GetEyePosition();
  let best = null, bt = 1e9;
  for (const en of enemiesNear(eye, 2000)) {
    const c = { x: en.pos.x, y: en.pos.y, z: en.pos.z + en.kind.height * 0.5 };
    if (V.segDist(c, eye, impact) < en.kind.radius + 6) { const t = V.dist(eye, c); if (t < bt) { bt = t; best = en; } }
  }
  if (!best) return;
  let base = 30, rm = 0.85;
  try { const d = weapon.GetData(); base = d.GetDamage(); rm = d.GetRangeModifier(); } catch (e) { /* */ }
  let dmg = weaponDamage(base, rm, bt);
  // weak point: the top quarter of the body
  const top = best.pos.z + best.kind.height * 0.75;
  if (V.segDist({ x: best.pos.x, y: best.pos.y, z: top + best.kind.height * 0.125 }, eye, impact) < best.kind.radius * 0.6) dmg *= 2.5;
  hurtEnemy(G, best, dmg, p, false);
}

function knifeHit(G, weapon, attackType) {
  const shooter = weapon.GetOwner ? weapon.GetOwner() : undefined; if (!shooter) return;
  const p = PL.get(slotOf(shooter)); if (!p || !p.alive) return;
  const eye = shooter.GetEyePosition(); const dir = V.fromAngles(shooter.GetEyeAngles());
  const tip = V.add(eye, V.mul(dir, 72));
  for (const en of enemiesNear(eye, 160)) {
    const c = { x: en.pos.x, y: en.pos.y, z: en.pos.z + en.kind.height * 0.5 };
    if (V.segDist(c, eye, tip) < en.kind.radius + 20) { hurtEnemy(G, en, attackType === 1 ? 90 : 45, p, true); break; }
  }
}
