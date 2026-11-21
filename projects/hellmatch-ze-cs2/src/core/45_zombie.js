// ===================================================================================
// Part 4b (Hellmatch ZE): zombie classes - a player driving a monster's body. The body takes the monster's look, size,
// weight and (scaled) health; the first-person view is a psprite machine like a weapon's, with a cooldown ability on
// the second button (BT_ALT). Monsters and zombie players are one side (zeFaction): they never hurt each other.
// ===================================================================================

// hpMul: monster health x this (a player takes far more fire than a lone monster); speedMul: run speed against a marine;
// cd: ability cooldown in tics; kb: how far shots push this class (on top of the mass rule in damageMobj)
const ZCLASS = {
  IMP: { key: 'IMP', name: 'IMP', ability: 'FIREBALL', hpMul: 3, speedMul: 1.0, cd: Math.round(1.4 * TICRATE), up: 'ZIMP_UP', ready: 'ZIMP_READY',
    attack: 'ZIMP_CLAW1', alt: 'ZIMF_1', mt: 0 },
  DEMON: { key: 'DEMON', name: 'DEMON', ability: 'LUNGE', hpMul: 2.2, speedMul: 1.08, cd: Math.round(3.5 * TICRATE), up: 'ZDMN_UP', ready: 'ZDMN_READY',
    attack: 'ZDMN_BITE1', alt: 'ZDMN_LUNGE1', mt: 0 },
  LOSTSOUL: { key: 'LOSTSOUL', name: 'LOST SOUL', ability: 'DASH', hpMul: 1.2, speedMul: 1.12, cd: Math.round(1.2 * TICRATE), up: 'ZSKL_UP', ready: 'ZSKL_READY',
    attack: 'ZSKL_DASH1', alt: 'ZSKL_DASH1', mt: 0,
    // 4.1: the body floats like the monster (MF_NOGRAVITY): hover units above the floor (Doom's floaters drift to their
    // target's height + half their own, 28 for a skull level with a marine), a gentle bob of bob units over bobTics,
    // the eye view units above the body's bottom (the skull's eyes, not a marine's 41)
    hover: 28, bob: 3, bobTics: 70, view: 32 },
};
for (const c of Object.values(ZCLASS)) {
  c.mt = MT['ZPLAYER_' + c.key];
  for (const k of ['up', 'ready', 'attack', 'alt']) c[k] = SN(c[k]);
  c.hp = Math.round(MOBJINFO[MT[c.key]].spawnhealth * c.hpMul);
}

// stage bosses a zombie player can drive (3.1): ZCLASS 'B_<type>'. melee: [dice sides, x, +] on ATTACK (none: ATTACK
// fires too); missile on the ability key (MOUSE2 / R) with its cooldown; spread: that many shots fanned out (degrees).
// Health is the boss's own (set at the takeover), speed a little under a marine's.
const ZBOSS = {
  BARON: { atkName: 'CLAW', ability: 'FIREBALL', melee: [8, 5, 10], missile: 'BARONBALL', cd: 1.0, speedMul: 0.85 },
  KNIGHT: { atkName: 'CLAW', ability: 'FIREBALL', melee: [8, 4, 8], missile: 'BARONBALL', cd: 0.9, speedMul: 0.9 },
  REVENANT: { atkName: 'PUNCH', ability: 'MISSILE', melee: [10, 4, 6], missile: 'TRACER', cd: 1.1, speedMul: 1.0 },
  MANCUBUS: { atkName: 'FIREBALLS', ability: 'FIREBALLS', melee: null, missile: 'FATSHOT', spread: [-8, 8], cd: 1.4, speedMul: 0.75 },
  ARACHNOTRON: { atkName: 'PLASMA', ability: 'PLASMA', melee: null, missile: 'ARACHPLASMA', cd: 0.25, speedMul: 0.85 },
  CYBERDEMON: { atkName: 'ROCKET', ability: 'ROCKET', melee: null, missile: 'ROCKET', cd: 0.8, speedMul: 0.8 },
};
for (const [T, b] of Object.entries(ZBOSS)) {
  if (MT['ZPLAYER_B_' + T] === undefined) continue;
  const k = 'B_' + T;
  ZCLASS[k] = Object.assign({ key: k, type: T, boss: true, name: String(MOBJINFO[MT[T]].name).toUpperCase(), hpMul: 1, mt: MT['ZPLAYER_B_' + T],
    up: SN('ZBV_UP'), ready: SN('ZBV_READY'), attack: SN(b.melee ? 'ZBV_MELEE1' : 'ZBV_FIRE1'), alt: SN('ZBV_FIRE1'),
    hp: MOBJINFO[MT[T]].spawnhealth }, b, { cd: Math.round(b.cd * TICRATE) });
}

// 0 = neither (barrels, items), 1 = human, 2 = horde (monsters and zombie players)
function zeFaction(mo) {
  if (mo.player) return mo.player.zclass ? 2 : 1;
  return mo.info.kind === 'monster' ? 2 : 0;
}

// key doors (Doom specials) -> key colour, for sidecars that keep keys
const ZE_KEY_DOORS = { 26: 'b', 32: 'b', 27: 'y', 34: 'y', 28: 'r', 33: 'r' };
const ZE_KEY_NAMES = { b: 'BLUE', y: 'YELLOW', r: 'RED' };

function makeZombie(p, cls) {
  p.zclass = cls;
  p.speedMul = ZCLASS[cls].speedMul;
}

function zombieReborn(p) {
  const c = ZCLASS[p.zclass];
  p.health = c.boss ? c.hp : Math.round(c.hp * zeCfg().zHp * zeHumanScale());   // a boss body gets the boss's health after
  p.weaponowned.fill(false);
  p.readyweapon = WP_FIST; p.pendingweapon = WP_NOCHANGE;
  p.ammo = [0, 0, 0, 0];
  p.zcd = 0; p.zdash = 0; p.zhit = false; p.zdv = null; p.zDoorAt = 0;
  p.speedMul = c.speedMul;
  if (c.view) { p.viewheight = c.view; p.deltaviewheight = 0; }
}

// 4.1: a floating body (the lost soul): alive, its class hovers
function zHovers(p) {
  const c = p.zclass && ZCLASS[p.zclass];
  return !!c && !!c.hover && p.playerstate === 'live' && !!p.mo && !p.mo.removed;
}

// per tic: steer the floating body to its hover height over the floor under it (stepping onto a ledge lifts it, off one
// it sinks), under the ceiling, with a slow bob; a dash flies free (zDashCarry) and the body drifts back afterwards
function zHover(p) {
  const mo = p.mo, c = ZCLASS[p.zclass];
  if (p.zdash > 0 && p.zdv) return;
  const bob = c.bob * Math.sin(((G.leveltime + p.slot * 13) % c.bobTics) / c.bobTics * 2 * Math.PI);
  let want = mo.floorz + c.hover + bob;
  if (want + mo.height > mo.ceilingz) want = mo.ceilingz - mo.height;
  if (want < mo.floorz) want = mo.floorz;
  mo.momz = Math.max(-FLOATSPEED, Math.min(FLOATSPEED, (want - mo.z) * 0.3));
}

// 4.2: a zombie player running into a closed manual door (a press-E door) opens it, as Doom's monsters do: the door
// lines met by the failed move (TM.spechit); a door already moving is left alone unless it is closing (it opens again)
function zeBumpDoor(mo) {
  const p = mo.player;
  if (!p || (p.zDoorAt || 0) > G.leveltime) return false;
  for (let i = TM.spechit.length - 1; i >= 0; i--) {
    const ld = TM.spechit[i];
    if (!NAV_DOORS.has(ld.special) || !ld.backsector) continue;
    if (pointOnLineSide(mo.x, mo.y, ld) === 1) continue;
    const d = ld.backsector.specialdata;
    if (d && !(d.kind === 'door' && d.direction === -1)) continue;
    p.zDoorAt = G.leveltime + 8;
    useSpecialLine(mo, ld, 0);
    return true;
  }
  return false;
}

// the nearest human in front of a zombie within reach (melee): Doom's melee range check, in a cone
function zMeleeTarget(mo, range) {
  let best = null, bd = 1e9;
  for (const t of G.playerMobjs) {
    if (!targetable(t)) continue;
    const d = approxDistance(t.x - mo.x, t.y - mo.y);
    if (d >= range + t.radius + mo.radius - 16) continue;
    if (Math.abs(t.z - mo.z) > 48) continue;
    const an = Math.abs(angleDiff(mo.angle, pointToAngle(mo.x, mo.y, t.x, t.y)));
    if (an > 55 && d > mo.radius + t.radius + 8) continue;
    if (d < bd && checkSight(mo, t)) { bd = d; best = t; }
  }
  return best;
}

// the round's ZE settings (DEFAULT_CFG.ze merged with the CS2 config) from inside an arena's tic
function zeCfg() { return G && G.ze ? G.ze.round.zcfg : DEFAULT_CFG.ze; }

// a zombie player's body is as tough as the humans it hunts are many (live humans in its arena when it rises): from
// 8 humans up the class's own health, fewer -> less (a lone survivor faces bodies at about half health)
function zeHumanScale() {
  const c = zeCfg(), h = G && G.ze ? G.ze.humans().length : 8;
  return Math.max(c.zHpMin, Math.min(c.zHpMax, c.zHpBase + c.zHpPerHuman * h));
}

function zHit(p, t, damage, kind, sound) {
  const mo = p.mo;
  p.zkind = kind;
  damage = Math.max(1, Math.round(damage * zeCfg().zDamage));
  damageMobj(t, mo, mo, damage);
  p.zkind = undefined;
  spawnBlood(t.x, t.y, t.z + t.height / 2, damage);
  if (sound) startSound(mo, sound);
}

// the body shows the attack, then goes back to standing (or running, by movePlayer)
function zBodyAttack(p) { if (p.mo && p.playerstate === 'live') setMobjState(p.mo, p.mo.info.atk1); }

// per tic, before the psprites: cooldown, and the demon's lunge / lost soul's dash hitting whoever it runs into
function zombieThink(p) {
  const mo = p.mo;
  if (p.zcd > 0) p.zcd--;
  if (ZCLASS[p.zclass].hover) zHover(p);
  if (p.zdash > 0 && p.zdv && !p.zhit) zDashCarry(p);
  if (p.zdash > 0) {
    p.zdash--;
    if (!p.zhit) {
      for (const t of G.playerMobjs) {
        if (!targetable(t)) continue;
        if (Math.abs(t.x - mo.x) > t.radius + mo.radius + 10 || Math.abs(t.y - mo.y) > t.radius + mo.radius + 10 || Math.abs(t.z - mo.z) > 48) continue;
        p.zhit = true;
        // lunge 2d10-ish (12-30), dash a little over Doom's skull (7-28): a charge that lands hurts, but a single one never kills
        if (p.zclass === 'DEMON') zHit(p, t, ((P_Random() % 10) + 1) * 2 + 10, 'zDEMON', 'sgtatk');
        else zHit(p, t, ((P_Random() % 8) + 1) * 3 + 4, 'zLOSTSOUL', 'sklatk');
        // the charge stops dead on a hit (as a lost soul's does)
        mo.momx *= 0.2; mo.momy *= 0.2; mo.momz = 0; p.zdash = Math.min(p.zdash, 4);
        break;
      }
    }
    if (p.zdash === 0) zDashEnd(p);
  }
}

// a charge (demon lunge, lost soul dash) holds its speed for its whole length, like Doom's charging skull: floor friction
// and gravity don't eat it. Running into a wall (or a ledge) stops it dead, as a skull's does, instead of skating along
// the wall; a glancing touch only slides.
function zDashCarry(p) {
  const mo = p.mo, v = p.zdv;
  if (v.started) {
    const want = Math.hypot(v.x, v.y), got = Math.hypot(mo.x - v.lx, mo.y - v.ly);
    if (want > 4 && got < want * 0.4 && Math.abs(mo.z - v.lz) < Math.abs(v.z) * 0.4 + 1) {
      mo.momx = mo.momy = 0; mo.momz = Math.min(0, mo.momz);
      p.zdash = 0; p.zdv = null;
      startSound(mo, 'dmpain');   // the bump
      return;
    }
  }
  v.started = true; v.lx = mo.x; v.ly = mo.y; v.lz = mo.z;
  mo.momx = v.x; mo.momy = v.y;
  if (v.fly) {
    // a lost soul flies along its aim; at the floor or the ceiling it carries on level
    let z = v.z;
    if ((z < 0 && mo.z <= mo.floorz) || (z > 0 && mo.z + mo.height >= mo.ceilingz)) z = 0;
    mo.momz = z;
  }
}

// the end of a charge: a little of it carries on (so it doesn't stop like a wall), and a lost soul hangs for a moment
function zDashEnd(p) {
  const mo = p.mo;
  if (p.zdv) { mo.momx *= 0.35; mo.momy *= 0.35; }
  if (p.zclass === 'LOSTSOUL') mo.momz = 0;
  p.zdv = null;
}

function zAbilityReady(p) { return p.zcd <= 0; }

const ZE_WEAPON_ACTIONS = {
  A_ZRaise(p, psp) {
    psp.sy -= RAISESPEED * 2;
    if (psp.sy > WEAPONTOP) return;
    psp.sy = WEAPONTOP;
    setPsprite(p, 0, ZCLASS[p.zclass].ready);
  },
  A_ZReady(p, psp) {
    const c = ZCLASS[p.zclass];
    if (!p.health) return;
    psp.sy = WEAPONTOP;
    const angle = ((128 * G.leveltime) % 8192) / 8192 * 2 * Math.PI;
    psp.sx = 1 + p.bob * Math.cos(angle);
    if ((p.cmd.buttons & BT_ALT) && zAbilityReady(p)) { setPsprite(p, 0, c.alt); return; }
    if (p.cmd.buttons & BT_ATTACK) {
      if (c.attack === c.alt && !zAbilityReady(p)) return;   // the lost soul's only move is its dash
      setPsprite(p, 0, c.attack);
    }
  },
  A_ZReFire(p) {
    const c = ZCLASS[p.zclass];
    if ((p.cmd.buttons & BT_ATTACK) && p.health) setPsprite(p, 0, c.attack);
  },
  A_ZWindup(p) {
    zBodyAttack(p);
    const c = p.zclass;
    if (c === 'LOSTSOUL') startSound(p.mo, 'sklatk');
    else if (c === 'DEMON' && p.psprites[0].state === SN('ZDMN_LUNGE1')) startSound(p.mo, 'sgtsit');
  },
  // imp claw: Doom's own (1d8 x3, 3-24); balance runs (test/sim_ze.cjs, Nov 2026) had the old +6 wiping humans by stage 2
  A_ZClaw(p) {
    const t = zMeleeTarget(p.mo, MELEERANGE + 8);
    if (t) zHit(p, t, (P_Random() % 8 + 1) * 3, 'zIMP', 'claw');
    else startSound(p.mo, 'bgact');
    noiseAlert(p.mo, p.mo);
  },
  A_ZFireStart(p) { zBodyAttack(p); },
  A_ZFireball(p) {
    p.zcd = ZCLASS.IMP.cd;
    p.zkind = 'zIMPfire';
    const th = spawnPlayerMissile(p.mo, MT.IMPBALL);
    p.zkind = undefined;
    if (th) th.zfire = true;
  },
  // a boss's melee (a baron's claw: 15-50) and its missile (the monster's own, fanned out for a mancubus)
  A_ZBossMelee(p) {
    const c = ZCLASS[p.zclass], m = c.melee || [8, 3, 6];
    const t = zMeleeTarget(p.mo, MELEERANGE + 20);
    if (t) zHit(p, t, (P_Random() % m[0] + 1) * m[1] + m[2], 'zBOSS', 'claw');
    else startSound(p.mo, 'dmact');
    noiseAlert(p.mo, p.mo);
  },
  A_ZBossMissile(p) {
    const c = ZCLASS[p.zclass], mo = p.mo;
    if (!c || !c.boss || MT[c.missile] === undefined) return;
    p.zcd = c.cd;
    const base = mo.angle;
    for (const off of c.spread || [0]) {
      mo.angle = normAngle(base + off);
      const th = spawnPlayerMissile(mo, MT[c.missile]);
      if (th) { th.zkind = 'zBOSSfire'; if (AIM.linetarget) th.tracer = AIM.linetarget; }
    }
    mo.angle = base;
  },
  // demon bite: 8-26 a bite, about 1.7 bites a second (Doom's monster bites 4-40 but far less often)
  A_ZBite(p) {
    const t = zMeleeTarget(p.mo, MELEERANGE + 12);
    if (t) zHit(p, t, ((P_Random() % 10) + 1) * 2 + 6, 'zDEMON', 'sgtatk');
    else startSound(p.mo, 'dmact');
  },
  // demon lunge: a burst of speed along the view; the first human it runs into is bitten (zombieThink)
  A_ZLunge(p) {
    const mo = p.mo;
    p.zcd = ZCLASS.DEMON.cd;
    zBodyAttack(p);
    const sp = 22;   // held for the whole lunge (zDashCarry): about 240 units
    mo.momx = sp * Math.cos(mo.angle * DEG); mo.momy = sp * Math.sin(mo.angle * DEG);
    p.zdash = 11; p.zhit = false;
    p.zdv = { x: mo.momx, y: mo.momy, z: 0, fly: false, started: false, lx: 0, ly: 0, lz: 0 };
  },
  // lost soul dash: Doom's skull charge (speed 20), aimed by the view, up and down too
  A_ZDash(p) {
    const mo = p.mo;
    p.zcd = ZCLASS.LOSTSOUL.cd;
    zBodyAttack(p);
    const sp = SKULLSPEED + 4;
    const pitch = Math.max(-45, Math.min(45, p.pitch || 0));
    const c = Math.cos(pitch * DEG);
    mo.momx = sp * c * Math.cos(mo.angle * DEG); mo.momy = sp * c * Math.sin(mo.angle * DEG);
    mo.momz = -sp * Math.sin(pitch * DEG) / ZSCALE_AIM;
    p.zdash = 12; p.zhit = false;
    p.zdv = { x: mo.momx, y: mo.momy, z: mo.momz, fly: true, started: false, lx: 0, ly: 0, lz: 0 };
  },
};
Object.assign(WEAPON_ACTIONS, ZE_WEAPON_ACTIONS);
