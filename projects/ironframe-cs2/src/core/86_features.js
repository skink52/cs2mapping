// ===================================================================================================================
// IRONFRAME core: fun features added to IF_Game (docs/FEATURES.md).
//   1 Overdrive: m.overdrive 0..1, filled by damage dealt (victim AP x 2 per full) and taken (own AP x 4 per full). Full + the
//     input flag input.od held 0.6 s (bots: when it pays) -> 1.2 s charge (self slow) -> what the frame class does (11 Nov 2026):
//       light / medium  FIELD REFIT: +45 % AP, EN full, every weapon's ammo and charges full (featRefit)
//       heavy           ASSAULT ARMOR: the AoE pulse, 3 200 damage within 1 200 u (twice the old reach: skink52, "700 units is small
//                       considering frames are up to 600"), and +40 % EN (featBlast; a boss keeps 2 500 / 600)
//     Events {t:'overdrive', slot, phase:'charge'|'blast'|'refit', kind:'refit'|'blast', pos}.
//   1b Supply (11 Nov 2026, skink52: "the most annoying part of gameplay is running out of ammo - there's nothing you can do
//     about it, and there's also no way to heal"): a kill salvages 25 % ammo for every weapon and 8 % AP (event {t:'salvage'});
//     a weapon not fired for 6 s rebuilds its reserve, empty to full in 120 s (IF_weaponsStep, 40_combat.js): a floor, so no
//     pilot is ever left with nothing to fire; the refit above is the real resupply.
//   2 Supply drops (tb/cq/kh/ctf/sk): one crate at a time, game.effects entry {kind:'crate', state:'fall'|'ground', fall,
//     ckind, pos, slot:-1}. First live mech to touch it gets repair / ammo / damage boost / shield / overdrive.
//     Events {t:'crate', phase:'drop'|'land'|'take', pos, slot, kind}.
//   3 Killstreak rewards (per life, counted kills that are not rookie stomps): 3 radar ping, 5 artillery (fires at the next
//     lock target), 8 ACE (speed + overdrive regen). Event {t:'streak', slot, kind:'radar'|'arty'|'ace'|'arty_fire'|'arty_close', streak}.
//     Artillery (11 Nov 2026, skink52: "no artillery fire seemed to reach my lock"): it used to fire the instant it was earned at
//     whatever was locked, every shell at the spot the target stood on 1-4 s earlier. Now it arms 1.5 s after the reward, and
//     each shell picks its spot 0.9 s before it lands, where the target will be (its velocity x 0.6 of the fall), 280 u spread.
// Hooks into other core files: tick (featPre, featStep), spawnMech (featReset), IF_applyDamage (featDmg, featMeter),
// IF_mechDie (featOnKill), mech speed (m.featSpeed), setInput (input.od), Ai goal (featGoal), startRound (featInit).
// ===================================================================================================================
const IF_FEAT = {
  od: { dealPerApMax: 2, takePerApMax: 4, hold: 0.6, charge: 1.2, radius: 600, damage: 2500, edge: 0.4, impact: 99999, knock: 900, lift: 350, slow: 0.4,
    refit: { classes: ['light', 'medium'], ap: 0.45, botAp: 0.5, botAmmo: 0.15 }, heavy: { radius: 1200, damage: 3200, en: 0.4 } },
  supply: { killAmmo: 0.25, killAp: 0.08, restT: 6, fabTime: 120 },
  crate: { first: [25, 40], every: [60, 90], refN: 12, fallTime: 2.4, fallHeight: 3200, life: 50, touch: 260, minMechDist: 500, boostT: 15, shieldT: 15, boostMul: 1.25, shieldMul: 0.6,
    repair: 0.4, modes: ['tb', 'cq', 'kh', 'ctf', 'sk'], weights: { repair: 25, ammo: 20, damage: 20, shield: 20, overdrive: 15 } },
  streak: { radar: 3, arty: 5, ace: 8, radarT: 10, radarRange: 6000, shells: 6, shellTime: 4, shellLead: 0.9, shellSpread: 280, shellAim: 0.6, artyArm: 1.5, artyWarn: 5, shellRadius: 380, shellDmg: 900, shellImpact: 500,
    artyMinDist: 700, aceT: 20, aceSpeed: 1.2, aceRegen: 0.08, aceStart: 0.5 },
};
const IF_FEAT_G = /** @type {any} */ (IF_Game.prototype);

IF_FEAT_G.featInit = function (mode) {
  const cf = this.cfg.feat || {};
  /** @type {any} */ const F = this.feat = { od: Object.assign({}, IF_FEAT.od, cf.od), crate: Object.assign({}, IF_FEAT.crate, cf.crate), streak: Object.assign({}, IF_FEAT.streak, cf.streak), supply: Object.assign({}, IF_FEAT.supply, cf.supply), off: !!cf.off };
  F.crateOn = !F.off && F.crate.modes.indexOf(mode) >= 0;
  this.crate = null; this.crateT = F.crate.first[0] + this.rng() * (F.crate.first[1] - F.crate.first[0]); this.crateN = 0; this.shells = [];
};

IF_FEAT_G.featReset = function (m) {
  m.overdrive = 0; m.odPhase = 0; m.odT = 0; m.odHold = 0; m.boostDmgT = 0; m.shieldT = 0; m.aceT = 0; m.radarT = 0; m.artyReady = false; m.artyArmT = 0; m.artyWarnT = 0; m.fkills = 0;
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
    if (m.artyArmT > 0) m.artyArmT -= dt;
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
            if (this.odKind(m) === 'refit') go = m.ap < m.apMax * O.refit.botAp || this.featAmmoLeft(m) < O.refit.botAmmo;      // a bot refits when hurt or dry
            else {
              let n = 0; const rad = Math.min(800, this.odBlast(m).radius);      // a bot wants them well inside, not at the 40 % edge of a 1 200 u blast
              for (let i = 0; i < L.length; i++) { const o = L[i]; if (o !== m && this.enemies(m, o) && !o.protectedNow && IF_vdist(o.pos, m.pos) < rad + 100) n++; }
              go = n >= 3 || (m.staggered > 0 && m.ap < m.apMax * 0.35 && n >= 1);
            }
          }
        }
      } else m.odHold = 0;
      if (go) { m.odPhase = 1; m.odT = O.charge; m.odHold = 0; this.emit({ t: 'overdrive', slot: m.slot, phase: 'charge', kind: this.odKind(m), pos: IF_v3(m.pos.x, m.pos.y, m.pos.z) }); }
    } else {
      m.odT -= dt;
      if (m.odT <= 0) { if (this.odKind(m) === 'refit') this.featRefit(m); else this.featBlast(m); }
    }
    m.featSpeed = (m.odPhase === 1 ? O.slow : 1) * (m.aceT > 0 ? F.streak.aceSpeed : 1);
  }
};

// what a full overdrive does for this frame: 'refit' (light / medium) or 'blast' (heavy, boss, anything else)
IF_FEAT_G.odKind = function (m) { const k = m.cls && m.cls.key; return this.feat.od.refit.classes.indexOf(k) >= 0 ? 'refit' : 'blast'; };
IF_FEAT_G.odBlast = function (m) { const O = this.feat.od, H = m.cls && m.cls.key === 'heavy' ? O.heavy : null; return { radius: H ? H.radius : O.radius, damage: H ? H.damage : O.damage, en: H ? H.en : 0 }; };
// ammo: the share of all ammo left (1 when no weapon carries any), and a refill of `frac` of every weapon's full ammo (1 = full, with the charges)
IF_FEAT_G.featAmmoLeft = function (m) {
  let have = 0, full = 0;
  for (const wp of m.weapons) if (wp.w && wp.w.ammo !== undefined) { have += (wp.ammo + wp.mag) / wp.w.ammo; full++; }
  return full > 0 ? have / full : 1;
};
IF_FEAT_G.featAmmo = function (m, frac) {
  let got = false;
  for (const wp of m.weapons) {
    const w = wp.w; if (!w) continue;
    if (frac >= 1 && w.charges && wp.charges < w.charges + (wp.bonusCharges || 0)) { wp.charges = w.charges + (wp.bonusCharges || 0); got = true; }
    if (w.ammo === undefined) continue;
    const cap = w.ammo - wp.magSize;
    if (frac >= 1) { if (wp.mag < wp.magSize || wp.ammo < cap) got = true; wp.mag = wp.magSize; wp.ammo = cap; wp.reloading = false; continue; }
    if (wp.ammo >= cap) continue;
    wp.ammo = Math.min(cap, wp.ammo + Math.max(1, Math.round(w.ammo * frac))); got = true;
    if (wp.magSize && wp.mag <= 0 && !wp.reloading) { wp.reloading = true; wp.reloadT = w.reload || 2; }
  }
  return got;
};
IF_FEAT_G.featRefit = function (m) {
  const R = this.feat.od.refit;
  m.odPhase = 0; m.odT = 0; m.overdrive = 0;
  const heal = Math.max(0, Math.min(m.apMax - m.ap, Math.round(R.ap * m.apMax)));
  m.ap += heal; m.en = m.enMax; m.enStalled = 0;
  this.featAmmo(m, 1);
  m.sum.od++;
  this.emit({ t: 'overdrive', slot: m.slot, phase: 'refit', kind: 'refit', heal, pos: IF_v3(m.pos.x, m.pos.y, m.pos.z) });
};

IF_FEAT_G.featBlast = function (m) {
  const O = Object.assign({}, this.feat.od, this.odBlast(m));
  m.odPhase = 0; m.odT = 0; m.overdrive = 0;
  if (O.en > 0) { m.en = Math.min(m.enMax, m.en + O.en * m.enMax); m.enStalled = 0; }
  const c = IF_v3(m.pos.x, m.pos.y, m.pos.z + m.height * 0.5);
  m.sum.od++;
  this.emit({ t: 'overdrive', slot: m.slot, phase: 'blast', kind: 'blast', radius: O.radius, pos: IF_v3(m.pos.x, m.pos.y, m.pos.z) });
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
    if (!s.fixed && s.t <= S.shellLead) {         // the shell commits to a spot now: where its target will be when it lands
      const tg = this.mechs.get(s.target);
      if (tg && tg.alive) {
        const x = tg.pos.x + tg.vel.x * S.shellLead * S.shellAim + s.ox, y = tg.pos.y + tg.vel.y * S.shellLead * S.shellAim + s.oy;
        s.pos.x = x; s.pos.y = y; s.pos.z = this.nav.height(x, y) + 5;
      }
      s.fixed = true;
      this.emit({ t: 'shell', pos: IF_v3(s.pos.x, s.pos.y, s.pos.z), delay: Math.max(0, s.t), slot: s.owner });
    }
    if (s.t > 0) continue;
    this.shells.splice(i, 1);
    IF_explode(this, s.pos, S.shellRadius, S.shellDmg, S.shellImpact, s.owner, 'artillery', 'artillery', null);
  }
  // artillery call-in: fires at the next lock target
  for (const m of this.alive) {
    if (!m.artyReady || m.artyArmT > 0 || m.lock.target < 0) continue;
    const t = this.mechs.get(m.lock.target);
    if (!t || !t.alive || !this.enemies(m, t)) continue;
    if (IF_vdistXY(t.pos, m.pos) < S.artyMinDist) {        // too close to shell: say so (it used to wait without a word)
      if (this.time >= (m.artyWarnT || 0)) { m.artyWarnT = this.time + S.artyWarn; this.emit({ t: 'streak', slot: m.slot, kind: 'arty_close', streak: m.fkills }); }
      continue;
    }
    m.artyReady = false;
    this.emit({ t: 'streak', slot: m.slot, kind: 'arty_fire', streak: m.fkills, target: t.slot, pos: IF_v3(t.pos.x, t.pos.y, t.pos.z) });
    const ring = IF_effect(this, 'ring', IF_v3(t.pos.x, t.pos.y, this.nav.height(t.pos.x, t.pos.y) + 10), S.shellSpread, m.slot, S.shellTime + S.shellLead);
    if (ring) ring.artillery = true;
    for (let i = 0; i < S.shells; i++) {
      const a = this.rng() * Math.PI * 2, r = Math.sqrt(this.rng()) * S.shellSpread;
      const x = t.pos.x + Math.cos(a) * r, y = t.pos.y + Math.sin(a) * r, z = this.nav.height(x, y);
      const delay = S.shellLead + (i / Math.max(1, S.shells - 1)) * (S.shellTime - S.shellLead);
      this.shells.push({ t: delay, pos: IF_v3(x, y, z + 5), owner: m.slot, target: t.slot, ox: x - t.pos.x, oy: y - t.pos.y, fixed: false });
    }
  }
  if (F.crateOn) this.crateStep(dt);
};

// ---------------------------------------------------------------------------------------------------- kill streaks
IF_FEAT_G.featOnKill = function (k, v) {
  const F = this.feat; if (!F || F.off || !k || k.slot === v.slot || !this.enemies(k, v)) return;
  // salvage: every kill gives back ammo and a little armour
  if (k.alive && (F.supply.killAmmo > 0 || F.supply.killAp > 0)) {
    const heal = Math.max(0, Math.min(k.apMax - k.ap, Math.round(F.supply.killAp * k.apMax))); k.ap += heal;
    if (this.featAmmo(k, F.supply.killAmmo) || heal > 0) this.emit({ t: 'salvage', slot: k.slot, heal });
  }
  // rookie shield spirit: a high rank pilot stomping a rookie earns no reward progress
  for (const rs of this.P.caps.rookie_shield || []) if (v.rank > 0 && k.rank > 0 && v.rank < rs.below_rank && k.rank >= rs.vs_rank) return;
  const S = F.streak;
  k.fkills++;
  const n = k.fkills;   // exactly 3, 5 and 8: nothing beyond 8 (bounty territory)
  if (n === S.radar) { k.radarT = S.radarT; this.emit({ t: 'streak', slot: k.slot, kind: 'radar', streak: n }); }
  else if (n === S.arty) { k.artyReady = true; k.artyArmT = S.artyArm; this.emit({ t: 'streak', slot: k.slot, kind: 'arty', streak: n }); }
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
