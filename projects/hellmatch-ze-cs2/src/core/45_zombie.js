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
    attack: 'ZSKL_DASH1', alt: 'ZSKL_DASH1', mt: 0 },
};
for (const c of Object.values(ZCLASS)) {
  c.mt = MT['ZPLAYER_' + c.key];
  for (const k of ['up', 'ready', 'attack', 'alt']) c[k] = SN(c[k]);
  c.hp = Math.round(MOBJINFO[MT[c.key]].spawnhealth * c.hpMul);
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
  p.health = c.hp;
  p.weaponowned.fill(false);
  p.readyweapon = WP_FIST; p.pendingweapon = WP_NOCHANGE;
  p.ammo = [0, 0, 0, 0];
  p.zcd = 0; p.zdash = 0; p.zhit = false;
  p.speedMul = c.speedMul;
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

function zHit(p, t, damage, kind, sound) {
  const mo = p.mo;
  p.zkind = kind;
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
  if (p.zdash > 0) {
    p.zdash--;
    if (!p.zhit) {
      for (const t of G.playerMobjs) {
        if (!targetable(t)) continue;
        if (Math.abs(t.x - mo.x) > t.radius + mo.radius + 10 || Math.abs(t.y - mo.y) > t.radius + mo.radius + 10 || Math.abs(t.z - mo.z) > 48) continue;
        p.zhit = true;
        if (p.zclass === 'DEMON') zHit(p, t, ((P_Random() % 10) + 1) * 4 + 10, 'zDEMON', 'sgtatk');
        else zHit(p, t, ((P_Random() % 8) + 1) * 4 + 6, 'zLOSTSOUL', 'sklatk');
        // the charge stops dead on a hit (as a lost soul's does)
        mo.momx *= 0.2; mo.momy *= 0.2; mo.momz = 0; p.zdash = Math.min(p.zdash, 4);
        break;
      }
    }
    if (p.zclass === 'LOSTSOUL' && p.zdash === 0) mo.momz = 0;
  }
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
  // imp claw: Doom's 3d8 (x3) plus a little, so a pack of imps is a threat to a marine with armour
  A_ZClaw(p) {
    const t = zMeleeTarget(p.mo, MELEERANGE + 8);
    if (t) zHit(p, t, (P_Random() % 8 + 1) * 3 + 6, 'zIMP', 'claw');
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
  // demon bite: Doom's 4d10 (x4), the demon's only attack besides the lunge
  A_ZBite(p) {
    const t = zMeleeTarget(p.mo, MELEERANGE + 12);
    if (t) zHit(p, t, ((P_Random() % 10) + 1) * 4 + 4, 'zDEMON', 'sgtatk');
    else startSound(p.mo, 'dmact');
  },
  // demon lunge: a burst of speed along the view; the first human it runs into is bitten (zombieThink)
  A_ZLunge(p) {
    const mo = p.mo;
    p.zcd = ZCLASS.DEMON.cd;
    zBodyAttack(p);
    const sp = 26;
    mo.momx = sp * Math.cos(mo.angle * DEG); mo.momy = sp * Math.sin(mo.angle * DEG);
    p.zdash = 14; p.zhit = false;
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
  },
};
Object.assign(WEAPON_ACTIONS, ZE_WEAPON_ACTIONS);
