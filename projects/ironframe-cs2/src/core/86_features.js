// ===================================================================================================================
// IRONFRAME core: fun features added to IF_Game (docs/FEATURES.md).
//   1 Overdrive (Assault Armor): m.overdrive 0..1, filled by damage dealt (victim AP x 2 per full) and taken (own AP x 4 per
//     full). Full + the input flag input.od held 0.6 s (bots: at once) -> 1.2 s charge (self slow) -> AoE pulse.
//     Events {t:'overdrive', slot, phase:'charge'|'blast', pos}.
//   2 Supply drops (tb/cq/kh/ctf/sk): one crate at a time, game.effects entry {kind:'crate', state:'fall'|'ground', fall,
//     ckind, pos, slot:-1}. First live mech to touch it gets repair / ammo / damage boost / shield / overdrive.
//     Events {t:'crate', phase:'drop'|'land'|'take', pos, slot, kind}.
//   3 Killstreak rewards (per life, counted kills that are not rookie stomps): 3 radar ping, 5 artillery (fires at the next
//     lock target), 8 ACE (speed + overdrive regen). Event {t:'streak', slot, kind:'radar'|'arty'|'ace'|'arty_fire', streak}.
// Hooks into other core files: tick (featPre, featStep), spawnMech (featReset), IF_applyDamage (featDmg, featMeter),
// IF_mechDie (featOnKill), mech speed (m.featSpeed), setInput (input.od), Ai goal (featGoal), startRound (featInit).
// ===================================================================================================================
const IF_FEAT = {
  od: { dealPerApMax: 2, takePerApMax: 4, hold: 0.6, charge: 1.2, radius: 600, damage: 2500, edge: 0.4, impact: 99999, knock: 900, lift: 350, slow: 0.4 },
  crate: { first: [25, 40], every: [60, 90], refN: 12, fallTime: 2.4, fallHeight: 3200, life: 50, touch: 260, minMechDist: 500, boostT: 15, shieldT: 15, boostMul: 1.25, shieldMul: 0.6,
    repair: 0.4, modes: ['tb', 'cq', 'kh', 'ctf', 'sk'], weights: { repair: 25, ammo: 20, damage: 20, shield: 20, overdrive: 15 } },
  streak: { radar: 3, arty: 5, ace: 8, radarT: 10, radarRange: 6000, shells: 6, shellTime: 4, shellLead: 0.9, shellSpread: 450, shellRadius: 380, shellDmg: 900, shellImpact: 500,
    artyMinDist: 700, aceT: 20, aceSpeed: 1.2, aceRegen: 0.08, aceStart: 0.5 },
};
const IF_FEAT_G = /** @type {any} */ (IF_Game.prototype);

IF_FEAT_G.featInit = function (mode) {
  const cf = this.cfg.feat || {};
  /** @type {any} */ const F = this.feat = { od: Object.assign({}, IF_FEAT.od, cf.od), crate: Object.assign({}, IF_FEAT.crate, cf.crate), streak: Object.assign({}, IF_FEAT.streak, cf.streak), off: !!cf.off };
  F.crateOn = !F.off && F.crate.modes.indexOf(mode) >= 0;
  this.crate = null; this.crateT = F.crate.first[0] + this.rng() * (F.crate.first[1] - F.crate.first[0]); this.crateN = 0; this.shells = [];
};

IF_FEAT_G.featReset = function (m) {
  m.overdrive = 0; m.odPhase = 0; m.odT = 0; m.odHold = 0; m.boostDmgT = 0; m.shieldT = 0; m.aceT = 0; m.radarT = 0; m.artyReady = false; m.fkills = 0;
  m.featSpeed = 1; m.odThinkT = 0;
};

// ---------------------------------------------------------------------------------------------------- damage hooks
IF_FEAT_G.featDmg = function (a, v, dmg, self) {
  if (a && !self && a.boostDmgT > 0) dmg *= this.feat.crate.boostMul;
  if (v.shieldT > 0) dmg *= this.feat.crate.shieldMul;
  return dmg;
};
IF_FEAT_G.featMeter = function (a, v, dmg, self) {
  if (this._odBlast || this.feat.off) return;
  const O = this.feat.od;
  if (a && !self && a.odPhase === 0) a.overdrive = Math.min(1, a.overdrive + dmg / (O.dealPerApMax * Math.max(1, v.apMax)));
  if (v.odPhase === 0 && v.alive) v.overdrive = Math.min(1, v.overdrive + dmg / (O.takePerApMax * Math.max(1, v.apMax)));
};

// ---------------------------------------------------------------------------------------------------- per tick, before movement
IF_FEAT_G.featPre = function (L, dt) {
  const F = this.feat; if (!F || F.off) return;
  const O = F.od;
  for (let k = 0; k < L.length; k++) {
    const m = L[k];
    if (m.dropT > 0) continue;
    if (m.boostDmgT > 0) m.boostDmgT -= dt;
    if (m.shieldT > 0) m.shieldT -= dt;
    if (m.radarT > 0) m.radarT -= dt;
    if (m.aceT > 0) { m.aceT -= dt; if (m.odPhase === 0) m.overdrive = Math.min(1, m.overdrive + F.streak.aceRegen * dt); }
    const inp = m.input;
    if (m.odPhase === 0) {
      let go = false;
      if (m.overdrive >= 1) {
        if (m.human) {
          if (inp.od) { m.odHold += dt; inp.fire[2] = false; inp.fire[3] = false; if (m.odHold >= O.hold) go = true; } else m.odHold = 0;
        } else {
          m.odThinkT -= dt;
          if (m.odThinkT <= 0) {
            m.odThinkT = 0.2;
            let n = 0;
            for (let i = 0; i < L.length; i++) { const o = L[i]; if (o !== m && this.enemies(m, o) && !o.protectedNow && IF_vdist(o.pos, m.pos) < O.radius + 100) n++; }
            go = n >= 3 || (m.staggered > 0 && m.ap < m.apMax * 0.35 && n >= 1);
          }
        }
      } else m.odHold = 0;
      if (go) { m.odPhase = 1; m.odT = O.charge; m.odHold = 0; this.emit({ t: 'overdrive', slot: m.slot, phase: 'charge', pos: IF_v3(m.pos.x, m.pos.y, m.pos.z) }); }
    } else {
      m.odT -= dt;
      if (m.odT <= 0) this.featBlast(m);
    }
    m.featSpeed = (m.odPhase === 1 ? O.slow : 1) * (m.aceT > 0 ? F.streak.aceSpeed : 1);
  }
};

IF_FEAT_G.featBlast = function (m) {
  const O = this.feat.od;
  m.odPhase = 0; m.odT = 0; m.overdrive = 0;
  const c = IF_v3(m.pos.x, m.pos.y, m.pos.z + m.height * 0.5);
  m.sum.od++;
  this.emit({ t: 'overdrive', slot: m.slot, phase: 'blast', pos: IF_v3(m.pos.x, m.pos.y, m.pos.z) });
  this.emit({ t: 'explode', pos: IF_v3(c.x, c.y, c.z), radius: O.radius, kind: 'overdrive' });
  this._odBlast = true;
  for (const v of this.alive.slice()) {
    if (v === m || !v.alive || !this.enemies(m, v)) continue;
    const d = Math.max(0, IF_capDist(v, c));
    if (d > O.radius) continue;
    const f = 1 - (1 - O.edge) * (d / O.radius);
    IF_applyDamage(this, v, m.slot, O.damage * f, O.impact, IF_v3(v.pos.x, v.pos.y, v.pos.z + v.height * 0.5), 'overdrive', c, null);
    if (!v.alive) continue;
    if (!v.protectedNow && v.staggered <= 0) IF_forceStagger(this, v);
    let dx = v.pos.x - m.pos.x, dy = v.pos.y - m.pos.y; const l = Math.hypot(dx, dy) || 1; dx /= l; dy /= l;
    const kn = O.knock * (0.5 + 0.5 * f);
    v.vel.x += dx * kn; v.vel.y += dy * kn; v.vel.z = Math.max(v.vel.z, O.lift); v.onGround = false;
  }
  this._odBlast = false;
};

// ---------------------------------------------------------------------------------------------------- per tick, running phase
IF_FEAT_G.featStep = function (dt) {
  const F = this.feat; if (!F || F.off) return;
  const S = F.streak;
  // artillery shells in flight
  for (let i = this.shells.length - 1; i >= 0; i--) {
    const s = this.shells[i]; s.t -= dt;
    if (s.t > 0) continue;
    this.shells.splice(i, 1);
    IF_explode(this, s.pos, S.shellRadius, S.shellDmg, S.shellImpact, s.owner, 'artillery', 'artillery', null);
  }
  // artillery call-in: fires at the next lock target
  for (const m of this.alive) {
    if (!m.artyReady || m.lock.target < 0) continue;
    const t = this.mechs.get(m.lock.target);
    if (!t || !t.alive || !this.enemies(m, t) || IF_vdistXY(t.pos, m.pos) < S.artyMinDist) continue;
    m.artyReady = false;
    this.emit({ t: 'streak', slot: m.slot, kind: 'arty_fire', streak: m.fkills, pos: IF_v3(t.pos.x, t.pos.y, t.pos.z) });
    const ring = IF_effect(this, 'ring', IF_v3(t.pos.x, t.pos.y, this.nav.height(t.pos.x, t.pos.y) + 10), S.shellSpread, m.slot, S.shellTime + S.shellLead);
    if (ring) ring.artillery = true;
    for (let i = 0; i < S.shells; i++) {
      const a = this.rng() * Math.PI * 2, r = Math.sqrt(this.rng()) * S.shellSpread;
      const x = t.pos.x + Math.cos(a) * r, y = t.pos.y + Math.sin(a) * r, z = this.nav.height(x, y);
      const delay = S.shellLead + (i / Math.max(1, S.shells - 1)) * (S.shellTime - S.shellLead);
      this.shells.push({ t: delay, pos: IF_v3(x, y, z + 5), owner: m.slot });
      this.emit({ t: 'shell', pos: IF_v3(x, y, z + 5), delay, slot: m.slot });
    }
  }
  if (F.crateOn) this.crateStep(dt);
};

// ---------------------------------------------------------------------------------------------------- kill streaks
IF_FEAT_G.featOnKill = function (k, v) {
  const F = this.feat; if (!F || F.off || !k || k.slot === v.slot || !this.enemies(k, v)) return;
  // rookie shield spirit: a high rank pilot stomping a rookie earns no reward progress
  for (const rs of this.P.caps.rookie_shield || []) if (v.rank > 0 && k.rank > 0 && v.rank < rs.below_rank && k.rank >= rs.vs_rank) return;
  const S = F.streak;
  k.fkills++;
  const n = k.fkills;   // exactly 3, 5 and 8: nothing beyond 8 (bounty territory)
  if (n === S.radar) { k.radarT = S.radarT; this.emit({ t: 'streak', slot: k.slot, kind: 'radar', streak: n }); }
  else if (n === S.arty) { k.artyReady = true; this.emit({ t: 'streak', slot: k.slot, kind: 'arty', streak: n }); }
  else if (n === S.ace) { k.aceT = S.aceT; k.overdrive = Math.max(k.overdrive, S.aceStart); this.emit({ t: 'streak', slot: k.slot, kind: 'ace', streak: n }); }
};

// ---------------------------------------------------------------------------------------------------- supply crates
IF_FEAT_G.crateStep = function (dt) {
  const C = this.feat.crate, e = this.crate;
  if (!e) {
    if ((this.crateT -= dt) > 0) return;
    const n = this.alive.length, scale = IF_clamp(C.refN / Math.max(6, n), 0.6, 1.4);
    this.crateT = (C.every[0] + this.rng() * (C.every[1] - C.every[0])) * scale;
    const p = this.cratePoint(); if (!p) { this.crateT = 5; return; }
    const fx = IF_effect(this, 'crate', p, 120, -1, C.fallTime + C.life);
    if (!fx) return;
    fx.state = 'fall'; fx.fall = C.fallHeight; fx.fallT = 0; fx.ckind = ''; this.crate = fx; this.crateN++;
    this.emit({ t: 'crate', phase: 'drop', pos: IF_v3(p.x, p.y, p.z), slot: -1, kind: '' });
    return;
  }
  if (!e.alive) { this.crate = null; return; }
  if (e.state === 'fall') {
    e.fallT += dt;
    const u = Math.min(1, e.fallT / C.fallTime);
    e.fall = C.fallHeight * (1 - u * u);
    if (u >= 1) {
      e.state = 'ground'; e.fall = 0;
      this.emit({ t: 'crate', phase: 'land', pos: IF_v3(e.pos.x, e.pos.y, e.pos.z), slot: -1, kind: '' });
      this.emit({ t: 'sound', key: 'boom_small', pos: IF_v3(e.pos.x, e.pos.y, e.pos.z) });
    }
    return;
  }
  for (const m of this.alive) {
    if (m.dropT > 0) continue;
    if (IF_vdistXY(m.pos, e.pos) > C.touch || Math.abs(m.pos.z - e.pos.z) > 500) continue;
    this.crateTake(m, e); return;
  }
};
IF_FEAT_G.cratePoint = function () {
  const b = this.arena.bounds, C = this.feat.crate;
  const wx = b.max[0] - b.min[0], wy = b.max[1] - b.min[1];
  for (let tr = 0; tr < 60; tr++) {
    const x = b.min[0] + wx * (0.12 + 0.76 * this.rng()), y = b.min[1] + wy * (0.12 + 0.76 * this.rng());
    if (!this.nav.walk(x, y) || this.nav.nearStruct(x, y)) continue;
    let bad = false;
    for (const m of this.alive) if (IF_vdistXY(m.pos, IF_v3(x, y, 0)) < C.minMechDist) { bad = true; break; }
    if (bad) continue;
    return IF_v3(x, y, this.nav.height(x, y));
  }
  return null;
};
IF_FEAT_G.crateTake = function (m, e) {
  const C = this.feat.crate, W = C.weights;
  const useless = (k) => (k === 'repair' && m.ap > m.apMax * 0.9) || (k === 'overdrive' && m.overdrive > 0.8) ||
    (k === 'ammo' && !m.weapons.some((w) => w.w && w.w.ammo !== undefined && (w.ammo + w.mag) < w.w.ammo * 0.8));
  let kind = 'repair';
  for (let tr = 0; tr < 4; tr++) {
    let r = this.rng() * (W.repair + W.ammo + W.damage + W.shield + W.overdrive);
    kind = 'overdrive';
    for (const k of ['repair', 'ammo', 'damage', 'shield']) { if (r < W[k]) { kind = k; break; } r -= W[k]; }
    if (!useless(kind)) break;
  }
  if (kind === 'repair') m.ap = Math.min(m.apMax, m.ap + C.repair * m.apMax);
  else if (kind === 'ammo') { for (const w of m.weapons) if (w.w && w.w.ammo !== undefined) { w.mag = w.magSize; w.ammo = w.w.ammo - w.magSize; w.reloading = false; } }
  else if (kind === 'damage') m.boostDmgT = C.boostT;
  else if (kind === 'shield') m.shieldT = C.shieldT;
  else m.overdrive = 1;
  e.alive = false; this.crate = null;
  m.sum.crates++;
  this.emit({ t: 'crate', phase: 'take', pos: IF_v3(e.pos.x, e.pos.y, e.pos.z), slot: m.slot, kind });
  this.emit({ t: 'sound', key: 'ui_capture', slot: m.slot, only: m.slot });
};

// AI: a bot with no enemy close by heads for a landed crate within 3500 (called after the objective goal is chosen)
IF_FEAT_G.featGoal = function (m, ai, best) {
  const e = this.crate;
  if (!e || !e.alive || e.state !== 'ground' || (best && ai.dist < 1500)) return;
  if (IF_vdistXY(m.pos, e.pos) > 3500) return;
  IF_vcopy(ai.goal, e.pos); ai.hasGoal = true;
};
