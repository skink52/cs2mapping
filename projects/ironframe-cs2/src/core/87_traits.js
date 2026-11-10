// ===================================================================================================================
// IRONFRAME core: frame traits (docs/FEATURES.md "Frame traits"). Every player frame has a stat profile (frame.mods in
// data/parts.json) and ONE signature trait (frame.trait key, frame.trait_desc text). Mods keys: ap walk boost qb load stagger
// melee regen cannon_move_acc (20_mech.js) plus qb_cost (quick boost EN x), hover (hover thrust x), armor (flat damage cut 0..1).
//   krasnaya  Opener       first hit within 1.2 s of a quick boost deals +20 %
//   stryder   Reflex       quick boost costs 30 % less (mods.qb_cost) and its cooldown runs 50 % faster
//   lisa      Double jump  a second JUMP press in the air (250 EN)
//   whiteglint Second wind EN regen +40 % for 2.5 s after a quick boost
//   atlas     Field repair +0.8 % AP per second after 5 s without damage
//   supplice  Overshoot    assault boost costs 25 % less EN
//   rx78      Shield mastery shield block +30 % (capped at 90 %)
//   ogre      Plating      -15 % damage from the front arc
//   noblesse  Quick-load   shoulder weapons reload 20 % faster
//   legion    Gun shield   hold F 0.5 s (bots under fire): 3 s, -25 % front damage, half speed, 20 s cooldown, 400 EN
//   barbatos  Lifesteal    melee damage heals 15 % of itself
//   mule      Brace        still for 1 s: -30 % damage taken and 15 % tighter spread
//   ronin     Phase dash   double-tap quick boost: 0.35 s untouchable dash (600 EN, 7 s cooldown)
//   unicorn   Overdrive meter fills 30 % faster
//   me3atlas  Hardened     3 s stagger immunity after a stagger ends
//   sandviper Spotter      a lock held 1.5 s marks the target for 6 s: allies see it on the radar, it takes +10 % damage
//   kestrel   Slipstream   -35 % damage taken for 0.5 s from the start of a quick boost
//   warden    Aegis pulse  hold F 0.5 s (bots: it or an ally in range under fire): a 900 u pulse gives itself and every ally in
//                          range a barrier of 10 % of their max AP for 6 s (18 s cooldown, 300 EN)
//   bastion   Siege mode   hold F 0.5 s on the ground (bots: a locked target 700-3200 u away): rooted for 4 s, +20 % damage dealt;
//                          a quick boost or leaving the ground ends it (16 s cooldown, 300 EN)
// Event {t:'trait', slot, key, phase:'on'|'off'|'fire'} for the adapter (src/cs2/46_traits.js).
// Hooks: IF_mechApplyLoadout -> IF_traitApply; IF_applyDamage -> IF_traitDmg / IF_traitImp / IF_traitHit; setInput copies
// input.cycleHeld; weapon spread x m.spreadMul. featReset / featPre are wrapped here. Bots need no AI hook: featPre drives them.
// ===================================================================================================================
const IF_TRAIT = {
  opener: { window: 1.2, mult: 1.2 }, reflexCd: 0.5, dj: { en: 250, vz: 560 }, wind: { t: 2.5, mult: 0.4 }, repair: { delay: 5, pct: 0.008 },
  overshoot: 0.25, shield: 1.3, plating: { mult: 0.85 }, quickload: 0.25,
  gunshield: { hold: 0.5, t: 3, cd: 20, en: 400, mult: 0.75, speed: 0.5 }, lifesteal: 0.15, brace: { t: 1, mult: 0.7, spread: 0.85 },
  phase: { tap: 0.3, t: 0.35, cd: 7, en: 600, speed: 1.1 }, od: 0.3, hardened: 3,
  mark: { lock: 1.5, t: 6, mult: 1.1 }, slip: { t: 0.5, mult: 0.65 },
  aegis: { hold: 0.5, r: 900, pct: 0.1, t: 6, cd: 18, en: 300 }, siege: { hold: 0.5, t: 4, cd: 16, en: 300, mult: 1.2, near: 700, far: 3200 },
};
const IF_TRAIT_G = /** @type {any} */ (IF_Game.prototype);

function IF_traitFresh() {
  return { first: 0, wind: 0, still: 0, brace: false, ph: 0, cd: 0, act: 0, dj: false, imm: 0, hold: 0, pj: false, pq: false, lastQ: -99, qbSeen: -99, stEnd: -99, rep: false, sh: false,
    mk: -1, slip: 0, fireT: -99 };
}

// after the loadout numbers are set: new mods keys and trait set-up (weapons are already built)
function IF_traitApply(game, m) {
  const mods = m.mods || {};
  if (mods.qb_cost) m.qbCost *= mods.qb_cost;
  if (mods.hover) m.hoverMult *= mods.hover;
  m.armor = mods.armor || 0; m.spreadMul = 1;
}

const IF_traitReset0 = IF_TRAIT_G.featReset;
IF_TRAIT_G.featReset = function (m) {
  IF_traitReset0.call(this, m); m.trT = IF_traitFresh(); m.trT.stEnd = m.staggerEndT; m.spreadMul = 1;
  m.markT = 0; m.markTeam = -1; m.barrier = 0; m.barrierT = 0;   // Spotter mark and Aegis barrier sit on whichever mech receives them
};

function IF_traitFront(m, src) {
  if (!src) return false;
  const dx = src.x - m.pos.x, dy = src.y - m.pos.y, l = Math.sqrt(dx * dx + dy * dy);
  if (l < 1) return true;
  const yr = m.torsoYaw * IF_D2R;
  return (dx * Math.cos(yr) + dy * Math.sin(yr)) / l > 0;
}

// damage in: victim reductions, attacker bonuses
function IF_traitDmg(game, a, v, dmg, self, src) {
  const s = v.trT, f = v.frame;
  if (v.armor) dmg *= 1 - v.armor;
  if (s && f) {
    const k = f.trait;
    if (s.ph > 0) return 0;
    if (k === 'ogre' && IF_traitFront(v, src)) dmg *= IF_TRAIT.plating.mult;
    else if (k === 'legion' && s.act > 0 && IF_traitFront(v, src)) dmg *= IF_TRAIT.gunshield.mult;
    else if (k === 'mule' && s.brace) dmg *= IF_TRAIT.brace.mult;
    else if (k === 'kestrel' && s.slip > 0) {
      dmg *= IF_TRAIT.slip.mult;
      if (game.time - s.fireT > 0.25) { s.fireT = game.time; game.emit({ t: 'trait', slot: v.slot, key: 'kestrel', phase: 'fire' }); }
    }
  }
  if (a && !self && a.trT && a.trT.first > 0) { a.trT.first = 0; dmg *= IF_TRAIT.opener.mult; game.emit({ t: 'trait', slot: a.slot, key: 'krasnaya', phase: 'fire' }); }
  if (a && !self && a.trT && a.trT.act > 0 && a.frame && a.frame.trait === 'bastion') dmg *= IF_TRAIT.siege.mult;
  if (!self && v.markT > 0) dmg *= IF_TRAIT.mark.mult;
  if (v.barrier > 0 && dmg > 0) {   // Aegis barrier: absorbs last, after every other cut
    const take = Math.min(v.barrier, dmg); v.barrier -= take; dmg -= take;
    if (v.barrier <= 0) IF_traitBarrierEnd(game, v);
  }
  return dmg;
}
function IF_traitImp(game, v, imp) {
  const s = v.trT;
  return s && (s.ph > 0 || s.imm > 0) ? 0 : imp;
}
// after the AP was removed: lifesteal, extra overdrive fill
function IF_traitHit(game, a, v, dmg, self, opts) {
  if (a && !self && a.frame && a.frame.trait === 'barbatos' && opts && opts.wp && opts.wp.w && opts.wp.w.type === 'melee' && a.alive) {
    a.ap = Math.min(a.apMax, a.ap + dmg * IF_TRAIT.lifesteal);
    game.emit({ t: 'trait', slot: a.slot, key: 'barbatos', phase: 'fire' });
  }
  const F = game.feat;
  if (!F || F.off || game._odBlast) return;
  const O = F.od;
  if (a && !self && a.frame && a.frame.trait === 'unicorn' && a.odPhase === 0) a.overdrive = Math.min(1, a.overdrive + IF_TRAIT.od * dmg / (O.dealPerApMax * Math.max(1, v.apMax)));
  if (v.frame && v.frame.trait === 'unicorn' && v.odPhase === 0 && v.alive) v.overdrive = Math.min(1, v.overdrive + IF_TRAIT.od * dmg / (O.takePerApMax * Math.max(1, v.apMax)));
}

function IF_traitEmit(game, m, key, phase) { game.emit({ t: 'trait', slot: m.slot, key, phase }); }
function IF_traitBarrierEnd(game, m) {
  m.barrier = 0; m.barrierT = 0;
  if (m.frame && m.frame.trait === 'warden') IF_traitEmit(game, m, 'warden', 'off');   // the Warden's own barrier drives its aura hold
}

const IF_traitPre0 = IF_TRAIT_G.featPre;
IF_TRAIT_G.featPre = function (L, dt) {
  IF_traitPre0.call(this, L, dt);
  const MV = this.move, T = IF_TRAIT;
  const featOn = !!(this.feat && !this.feat.off);
  for (let k = 0; k < L.length; k++) {
    const m = L[k], s = m.trT, f = m.frame;
    if (m.markT > 0) { m.markT -= dt; if (m.markT <= 0) m.markT = 0; }
    if (m.barrierT > 0) { m.barrierT -= dt; if (m.barrierT <= 0) IF_traitBarrierEnd(this, m); }
    if (!s || !f) continue;
    if (!featOn) m.featSpeed = 1;
    m.spreadMul = 1;
    if (m.dropT > 0) continue;
    const key = f.trait; if (!key) continue;
    const inp = m.input, ground = m.onGround;
    const qbNew = m.qbAt !== s.qbSeen; if (qbNew) s.qbSeen = m.qbAt;
    const qbEdge = !!inp.qb && !s.pq; s.pq = !!inp.qb;
    const jumpEdge = !!inp.jump && !s.pj; s.pj = !!inp.jump;
    if (s.cd > 0) s.cd -= dt;
    if (s.first > 0) s.first -= dt;
    if (s.wind > 0) s.wind -= dt;
    const free = m.staggered <= 0 && m.landLag <= 0 && m.enStalled <= 0;
    switch (key) {
      case 'rx78':   // weapons are rebuilt at spawn after featReset, so the first live tick applies it
        if (!s.sh) { s.sh = true; for (let i = 0; i < 4; i++) { const w = m.weapons[i]; if (w && w.type === 'shield') w.statMult *= T.shield; } }
        break;
      case 'krasnaya': if (qbNew) s.first = T.opener.window; break;
      case 'stryder': if (m.qbCd > 0) m.qbCd -= dt * T.reflexCd; break;
      case 'whiteglint':
        if (qbNew) s.wind = T.wind.t;
        if (s.wind > 0 && m.enPause <= 0 && m.enStalled <= 0 && m.en < m.enMax) m.en = Math.min(m.enMax, m.en + m.enRegen * T.wind.mult * (ground ? MV.ground_regen_mult : 1) * dt);
        break;
      case 'atlas': {
        const on = this.time - m.lastDamageT >= T.repair.delay && m.ap < m.apMax;
        if (on) { m.ap = Math.min(m.apMax, m.ap + m.apMax * T.repair.pct * dt); if (!s.rep) { s.rep = true; IF_traitEmit(this, m, key, 'on'); } } else if (s.rep) { s.rep = false; IF_traitEmit(this, m, key, 'off'); }
        break;
      }
      case 'supplice': if (m.assault) m.en = Math.min(m.enMax, m.en + MV.boost_drain * m.drainMult * MV.assault_drain_mult * T.overshoot * dt); break;
      case 'noblesse':
        for (let hp = 2; hp < 4; hp++) { const wp = m.weapons[hp]; if (wp && wp.reloading) wp.reloadT -= dt * T.quickload; }
        break;
      case 'lisa': {
        if (ground) s.dj = false;
        let go = false;
        if (jumpEdge && !ground && m.airTime > 0.12 && !s.dj) go = true;
        else if (!m.human && !ground && !s.dj && m.vel.z < 0 && m.lock && m.lock.target >= 0 && m.en > m.enMax * 0.5 && this.rng() < 1.2 * dt) go = true;
        if (go && free && m.en >= T.dj.en) {
          s.dj = true; m.vel.z = Math.max(m.vel.z, 0) * 0.5 + T.dj.vz * m.legs.jump_mult; m.spendEn(T.dj.en); IF_traitEmit(this, m, key, 'fire');
        }
        break;
      }
      case 'mule': {
        if (ground && m.speed < 40 && m.staggered <= 0) s.still += dt; else s.still = 0;
        const b = s.still >= T.brace.t;
        if (b !== s.brace) { s.brace = b; IF_traitEmit(this, m, key, b ? 'on' : 'off'); }
        if (b) m.spreadMul = T.brace.spread;
        break;
      }
      case 'legion': {
        const G = T.gunshield;
        if (s.act > 0) {
          s.act -= dt; m.featSpeed *= G.speed;
          if (s.act <= 0) { s.act = 0; IF_traitEmit(this, m, key, 'off'); }
        }
        if (m.human) { if (inp.cycleHeld && ground && s.act <= 0) s.hold += dt; else s.hold = 0; }
        let go = m.human && s.hold >= G.hold;
        if (!m.human && s.act <= 0 && this.time - m.lastDamageT < 0.4 && m.lock && m.lock.target >= 0 && this.rng() < 3 * dt) go = true;
        if (go && s.act <= 0 && s.cd <= 0 && ground && free && m.canSpend(G.en)) {
          s.hold = 0; s.act = G.t; s.cd = G.cd; m.spendEn(G.en); IF_traitEmit(this, m, key, 'on');
        }
        break;
      }
      case 'ronin': {
        const P = T.phase;
        if (s.ph > 0) { s.ph -= dt; if (s.ph <= 0) { s.ph = 0; IF_traitEmit(this, m, key, 'off'); } }
        let go = false, dx = m.wish.x, dy = m.wish.y;
        if (qbEdge) { if (this.time - s.lastQ < P.tap) go = true; s.lastQ = this.time; }
        if (!m.human && s.ph <= 0 && this.time - m.lastDamageT < 0.35 && this.rng() < 3 * dt) {
          const t = m.lock && m.lock.target >= 0 ? this.mechs.get(m.lock.target) : null;
          if (t && t.alive && IF_vdistXY(t.pos, m.pos) < 1100) { dx = t.pos.x - m.pos.x; dy = t.pos.y - m.pos.y; go = true; }
        }
        if (go && s.ph <= 0 && s.cd <= 0 && free && m.canSpend(P.en)) {
          let l = Math.sqrt(dx * dx + dy * dy);
          if (l < 0.1) { dx = m.qbDir.x; dy = m.qbDir.y; l = Math.sqrt(dx * dx + dy * dy) || 1; }
          m.vel.x = dx / l * m.qbSpeed * P.speed; m.vel.y = dy / l * m.qbSpeed * P.speed;
          s.ph = P.t; s.cd = P.cd; m.spendEn(P.en); m.qbAt = this.time; s.qbSeen = m.qbAt; m.qbTime = 0.25;
          IF_traitEmit(this, m, key, 'on');
        }
        break;
      }
      case 'sandviper': {
        const M = T.mark, lk = m.lock;
        if (lk && lk.target >= 0 && lk.t >= M.lock) {
          const t = this.mechs.get(lk.target);
          if (t && t.alive) {
            const fresh = t.markT <= 0 || s.mk !== t.slot;
            t.markT = M.t; t.markTeam = m.team;
            if (fresh) { s.mk = t.slot; this.emit({ t: 'trait', slot: m.slot, key, phase: 'on', target: t.slot }); }
          }
        }
        if (s.mk >= 0) { const t = this.mechs.get(s.mk); if (!t || !t.alive || t.markT <= 0) { s.mk = -1; IF_traitEmit(this, m, key, 'off'); } }
        break;
      }
      case 'kestrel':
        if (qbNew) s.slip = T.slip.t;
        else if (s.slip > 0) s.slip -= dt;
        break;
      case 'warden': {
        const A = T.aegis;
        if (m.human) { if (inp.cycleHeld && s.cd <= 0) s.hold += dt; else s.hold = 0; }
        let go = m.human && s.hold >= A.hold;
        if (!m.human && s.cd <= 0 && m.lock && m.lock.target >= 0 && this.rng() < 3 * dt) {
          for (let j = 0; j < L.length && !go; j++) {
            const o = L[j];
            if (o.alive && (o === m || !this.enemies(m, o)) && this.time - o.lastDamageT < 0.5 && o.ap < o.apMax * 0.9 && IF_vdistXY(o.pos, m.pos) < A.r) go = true;
          }
        }
        if (go && s.cd <= 0 && free && m.canSpend(A.en)) {
          s.hold = 0; s.cd = A.cd; m.spendEn(A.en);
          const allies = [];
          for (let j = 0; j < L.length; j++) {
            const o = L[j];
            if (!o.alive || o.dropT > 0 || (o !== m && this.enemies(m, o)) || IF_vdistXY(o.pos, m.pos) > A.r) continue;
            o.barrier = Math.max(o.barrier || 0, o.apMax * A.pct); o.barrierT = A.t;
            if (o !== m) allies.push(o.slot);
          }
          this.emit({ t: 'trait', slot: m.slot, key, phase: 'on', allies });
        }
        break;
      }
      case 'bastion': {
        const G = T.siege;
        if (s.act > 0) {
          s.act -= dt;
          if (s.act <= 0 || qbNew || !ground) { s.act = 0; s.cd = G.cd; IF_traitEmit(this, m, key, 'off'); } else m.featSpeed = 0;
        }
        if (m.human) { if (inp.cycleHeld && ground && s.act <= 0 && s.cd <= 0) s.hold += dt; else s.hold = 0; }
        let go = m.human && s.hold >= G.hold;
        if (!m.human && s.act <= 0 && s.cd <= 0 && m.lock && m.lock.target >= 0 && m.lock.los && this.rng() < 1.5 * dt) {
          const t = this.mechs.get(m.lock.target), d = t ? IF_vdistXY(t.pos, m.pos) : 0;
          if (t && t.alive && d > G.near && d < G.far && m.ap > m.apMax * 0.3) go = true;
        }
        if (go && s.act <= 0 && s.cd <= 0 && ground && free && m.canSpend(G.en)) {
          s.hold = 0; s.act = G.t; m.spendEn(G.en); m.featSpeed = 0; m.boosting = false; IF_traitEmit(this, m, key, 'on');
        }
        break;
      }
      case 'me3atlas':
        if (m.staggerEndT !== s.stEnd) { s.stEnd = m.staggerEndT; s.imm = T.hardened; IF_traitEmit(this, m, key, 'on'); }
        if (s.imm > 0) { s.imm -= dt; if (m.staggered <= 0) m.stagger = 0; if (s.imm <= 0) { s.imm = 0; IF_traitEmit(this, m, key, 'off'); } }
        break;
      default: break;
    }
  }
};
