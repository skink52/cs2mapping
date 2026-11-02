// ===================================================================================
// Part 3: map objects - spawning, states, movement, damage, death, pickups (p_mobj / p_inter)
// ===================================================================================

let mobjSerial = 1;

function spawnMobj(x, y, z, type) {
  const info = MOBJINFO[type];
  const mo = {
    id: mobjSerial++, type, info, x, y, z, angle: 0,
    momx: 0, momy: 0, momz: 0, radius: info.radius, height: info.height,
    flags: info.flags, health: info.spawnhealth,
    state: S_NULL, tics: 0, sprite: '', frame: 0, bright: false,
    floorz: 0, ceilingz: 0, sector: null, bcell: null, bindex: 0,
    target: null, tracer: null, player: null, reactiontime: 0,
    validcount: 0, removed: false, spawnpoint: null,
    // render interpolation
    px: x, py: y, pz: z, pangle: 0, rev: 0, teleported: true,
    // filled in later for some things only; declared here so every map object has the same shape (V8 then keeps
    // property reads fast everywhere instead of falling back to slow lookups)
    movedir: undefined, movecount: undefined, threshold: undefined, lastlook: undefined,
    wave: undefined, maxHealth: undefined, idleSince: undefined, bestNear: undefined, progressAt: undefined,
    spawnedBy: undefined, corpseColor: undefined, boss: undefined,
  };
  if (info.kind === 'monster') {
    mo.movedir = DI_NODIR; mo.movecount = 0; mo.threshold = 0; mo.lastlook = P_Random() & 3;
    mo.reactiontime = info.reactiontime;
    G.monsterCount = (G.monsterCount || 0) + 1;
  }
  setThingPosition(mo);
  mo.floorz = mo.sector.floorheight; mo.ceilingz = mo.sector.ceilingheight;
  if (z === ONFLOORZ) mo.z = mo.floorz;
  else if (z === ONCEILINGZ) mo.z = mo.ceilingz - mo.height;
  mo.pz = mo.z;
  G.mobjs.add(mo);
  const st = STATES[info.spawnstate];
  mo.state = info.spawnstate; mo.tics = st.tics; mo.sprite = st.sprite; mo.frame = st.frame; mo.bright = st.bright;
  return mo;
}

function removeMobj(mo) {
  if (mo.removed) return;
  if (mo.info.kind === 'monster') G.monsterCount = Math.max(0, (G.monsterCount || 0) - 1);
  if ((mo.flags & MF_SPECIAL) && !(mo.flags & MF_DROPPED) && mo.spawnpoint &&
      mo.type !== MT.INVULN && mo.type !== MT.INVIS) {
    G.itemRespawnQueue.push({ point: mo.spawnpoint, time: G.leveltime });
  }
  unsetThingPosition(mo);
  mo.removed = true;
  G.mobjs.delete(mo);
  G.removedMobjs.push(mo);
}

function setMobjState(mo, state) {
  let guard = 0;
  do {
    if (state === S_NULL) { mo.state = S_NULL; removeMobj(mo); return false; }
    const st = STATES[state];
    mo.state = state; mo.tics = st.tics; mo.sprite = st.sprite; mo.frame = st.frame; mo.bright = st.bright;
    mo.rev++;
    if (st.action) MOBJ_ACTIONS[st.action](mo);
    if (mo.removed) return false;
    state = st.next;
  } while (!mo.tics && ++guard < 100);
  return true;
}

// ---------------------------------------------------------------- movement
function xyMovement(mo) {
  if (!mo.momx && !mo.momy) {
    if (mo.flags & MF_SKULLFLY) {
      // the skull slammed into something
      mo.flags &= ~MF_SKULLFLY;
      mo.momx = mo.momy = mo.momz = 0;
      setMobjState(mo, mo.info.spawnstate);
    }
    return;
  }
  const player = mo.player;
  if (mo.momx > MAXMOVE) mo.momx = MAXMOVE; else if (mo.momx < -MAXMOVE) mo.momx = -MAXMOVE;
  if (mo.momy > MAXMOVE) mo.momy = MAXMOVE; else if (mo.momy < -MAXMOVE) mo.momy = -MAXMOVE;
  let xmove = mo.momx, ymove = mo.momy;
  do {
    let ptryx, ptryy;
    if (xmove > MAXMOVE / 2 || ymove > MAXMOVE / 2 || xmove < -MAXMOVE / 2 || ymove < -MAXMOVE / 2) {
      ptryx = mo.x + xmove / 2; ptryy = mo.y + ymove / 2;
      xmove /= 2; ymove /= 2;
    } else {
      ptryx = mo.x + xmove; ptryy = mo.y + ymove;
      xmove = ymove = 0;
    }
    if (!tryMove(mo, ptryx, ptryy)) {
      if (mo.player) slideMove(mo);
      else if (mo.flags & MF_MISSILE) {
        if (TM.ceilingline && TM.ceilingline.backsector && TM.ceilingline.backsector.sky &&
            mo.z > TM.ceilingline.backsector.ceilingheight - 1) {
          removeMobj(mo); return;
        }
        explodeMissile(mo); return;
      } else { mo.momx = mo.momy = 0; }
    }
    if (mo.removed) return;
  } while (xmove || ymove);
  if (mo.flags & (MF_MISSILE | MF_SKULLFLY)) {
    // no friction for missiles or charging skulls. A shot that got out of the level (through a gap in the outline)
    // would fly on forever into the void, past the edge of the CS2 world on levels near it: it goes away
    if ((mo.flags & MF_MISSILE) && G.inside && !G.inside(mo.x, mo.y)) removeMobj(mo);
    return;
  }
  if (mo.z > mo.floorz) return;
  if (mo.flags & MF_CORPSE) {
    if ((mo.momx > 0.25 || mo.momx < -0.25 || mo.momy > 0.25 || mo.momy < -0.25) && mo.floorz !== mo.sector.floorheight) return;
  }
  const cmd = player && player.cmd;
  if (mo.momx > -STOPSPEED && mo.momx < STOPSPEED && mo.momy > -STOPSPEED && mo.momy < STOPSPEED &&
      (!player || (!cmd.forwardmove && !cmd.sidemove))) {
    if (player && (mo.state >= SN('PLAY_RUN1') && mo.state <= SN('PLAY_RUN4'))) setMobjState(mo, SN('PLAY'));
    mo.momx = 0; mo.momy = 0;
  } else {
    mo.momx *= FRICTION; mo.momy *= FRICTION;
  }
}

function zMovement(mo) {
  if (mo.player && mo.z < mo.floorz) {
    mo.player.viewheight -= mo.floorz - mo.z;
    mo.player.deltaviewheight = (VIEWHEIGHT - mo.player.viewheight) / 8;
  }
  mo.z += mo.momz;
  // floaters drift towards their target's height
  if ((mo.flags & MF_FLOAT) && mo.target && !(mo.flags & (MF_SKULLFLY | MF_INFLOAT))) {
    const dist = approxDistance(mo.x - mo.target.x, mo.y - mo.target.y);
    const delta = (mo.target.z + mo.height / 2) - mo.z;
    if (delta < 0 && dist < -(delta * 3)) mo.z -= FLOATSPEED;
    else if (delta > 0 && dist < delta * 3) mo.z += FLOATSPEED;
  }
  if (mo.z <= mo.floorz) {
    if (mo.flags & MF_SKULLFLY) mo.momz = -mo.momz;   // the skull slammed into the floor
    if (mo.momz < 0) {
      if (mo.player && mo.momz < -GRAVITY * 8) {
        mo.player.deltaviewheight = mo.momz / 8;
        startSound(mo, 'oof');
      }
      mo.momz = 0;
    }
    mo.z = mo.floorz;
    if ((mo.flags & MF_MISSILE) && !(mo.flags & MF_NOCLIP)) { explodeMissile(mo); return; }
  } else if (!(mo.flags & MF_NOGRAVITY)) {
    if (mo.momz === 0) mo.momz = -GRAVITY * 2;
    else mo.momz -= GRAVITY;
  }
  if (mo.z + mo.height > mo.ceilingz) {
    if (mo.momz > 0) mo.momz = 0;
    mo.z = mo.ceilingz - mo.height;
    if (mo.flags & MF_SKULLFLY) mo.momz = -mo.momz;   // the skull slammed into the ceiling
    if ((mo.flags & MF_MISSILE) && !(mo.flags & MF_NOCLIP)) {
      if (mo.sector && mo.sector.sky && mo.ceilingz >= mo.sector.ceilingheight) { removeMobj(mo); return; }
      explodeMissile(mo); return;
    }
  }
}

function mobjThinker(mo) {
  mo.px = mo.x; mo.py = mo.y; mo.pz = mo.z; mo.pangle = mo.angle;
  if (mo.momx || mo.momy || (mo.flags & MF_SKULLFLY)) { xyMovement(mo); if (mo.removed) return; }
  if (mo.z !== mo.floorz || mo.momz) { zMovement(mo); if (mo.removed) return; }
  if (mo.tics !== -1) {
    mo.tics--;
    if (!mo.tics) setMobjState(mo, STATES[mo.state].next);
  }
}

// ---------------------------------------------------------------- effects
function spawnPuff(x, y, z) {
  z += (P_Random() - P_Random()) / 64;
  const th = spawnMobj(x, y, z, MT.PUFF);
  th.momz = 1;
  th.tics -= P_Random() & 3;
  if (th.tics < 1) th.tics = 1;
  if (AIM.attackrange === MELEERANGE) setMobjState(th, SN('PUFF3'));
  return th;
}

function spawnBlood(x, y, z, damage) {
  z += (P_Random() - P_Random()) / 64;
  const th = spawnMobj(x, y, z, MT.BLOOD);
  th.momz = 2;
  th.tics -= P_Random() & 3;
  if (th.tics < 1) th.tics = 1;
  if (damage <= 12 && damage >= 9) setMobjState(th, SN('BLOOD2'));
  else if (damage < 9) setMobjState(th, SN('BLOOD3'));
  return th;
}

function explodeMissile(mo) {
  mo.momx = mo.momy = mo.momz = 0;
  setMobjState(mo, mo.info.deathstate);
  if (mo.removed) return;
  mo.tics -= P_Random() & 3;
  if (mo.tics < 1) mo.tics = 1;
  mo.flags &= ~MF_MISSILE;
  if (mo.info.deathsound) startSound(mo, mo.info.deathsound);
}

function checkMissileSpawn(th) {
  th.tics -= P_Random() & 3;
  if (th.tics < 1) th.tics = 1;
  th.x += th.momx / 2; th.y += th.momy / 2; th.z += th.momz / 2;
  if (!tryMove(th, th.x, th.y)) explodeMissile(th);
}

function spawnPlayerMissile(source, type) {
  let an = source.angle;
  let slope = aimLineAttack(source, an, 16 * 64);
  if (!AIM.linetarget) {
    an = normAngle(an + AIMSPREAD); slope = aimLineAttack(source, an, 16 * 64);
    if (!AIM.linetarget) {
      an = normAngle(an - 2 * AIMSPREAD); slope = aimLineAttack(source, an, 16 * 64);
    }
    if (!AIM.linetarget) { an = source.angle; slope = freeAimSlope(source); }
  }
  const z = source.z + 32;
  const th = spawnMobj(source.x, source.y, z, type);
  if (th.info.seesound) startSound(th, th.info.seesound);
  th.target = source;
  th.angle = an;
  const sp = th.info.speed;
  th.momx = sp * Math.cos(an * DEG); th.momy = sp * Math.sin(an * DEG);
  th.momz = sp * slope;
  th.pangle = an;
  checkMissileSpawn(th);
  return th;
}

function freeAimSlope(mo) {
  if (!mo.player || !G.cfg.freelookAim) return 0;
  const p = Math.max(-60, Math.min(60, mo.player.pitch));
  return -Math.tan(p * DEG) / ZSCALE_AIM;
}
// CS2 pitch is measured in the stretched (1.2x tall) world; convert to Doom slope
const ZSCALE_AIM = 1.2;

// ---------------------------------------------------------------- damage and death
function damageMobj(target, inflictor, source, damage) {
  if (!(target.flags & MF_SHOOTABLE)) return;
  if (target.health <= 0) return;
  const player = target.player;
  if (player && player.spectating) return;
  if (player && G.isProtected(player) && damage < 10000) return;
  // teammates never hurt each other, except a telefrag: two things sharing one spot can never move again, so the one
  // arriving always wins (Doom's co-op rule)
  if (damage < 10000 && sameTeamNoFF(source, target)) return;
  if (target.flags & MF_SKULLFLY) target.momx = target.momy = target.momz = 0;
  if (inflictor && !(target.flags & MF_NOCLIP) &&
      (!source || !source.player || source.player.readyweapon !== WP_CHAINSAW)) {
    let ang = pointToAngle(inflictor.x, inflictor.y, target.x, target.y);
    let thrust = damage * 0.125 * 100 / target.info.mass;
    if (damage < 40 && damage > target.health && target.z - inflictor.z > 64 && (P_Random() & 1)) {
      ang += 180; thrust *= 4;
    }
    target.momx += thrust * Math.cos(ang * DEG);
    target.momy += thrust * Math.sin(ang * DEG);
  }
  if (player) {
    if (damage < 10000 && player.powers[PW_INVULN]) return;
    if (player.armortype) {
      let saved = player.armortype === 1 ? Math.floor(damage / 3) : Math.floor(damage / 2);
      if (player.armorpoints <= saved) { saved = player.armorpoints; player.armortype = 0; }
      player.armorpoints -= saved;
      damage -= saved;
    }
    player.health -= damage;
    if (player.health < 0) player.health = 0;
    player.attacker = source;
    player.damagecount += damage;
    if (player.damagecount > 100) player.damagecount = 100;
    if (source && source.player && source !== target) source.player.stats.damage += damage;
  }
  target.health -= damage;
  if (target.health <= 0) { killMobj(source, target, inflictor); return; }
  if ((P_Random() < target.info.painchance) && target.info.painstate !== S_NULL && !(target.flags & MF_SKULLFLY)) {
    target.flags |= MF_JUSTHIT;   // fight back
    setMobjState(target, target.info.painstate);
  }
  target.reactiontime = 0;
  // monsters remember who hurt them (and other monsters' stray shots start fights between them)
  if (!target.player && (!target.threshold || target.type === MT.ARCHVILE) && source && source !== target && source.type !== MT.ARCHVILE) {
    target.target = source;
    target.threshold = BASETHRESHOLD;
    if (target.state === target.info.spawnstate && target.info.seestate !== S_NULL) setMobjState(target, target.info.seestate);
  }
}

function killMobj(source, target, inflictor) {
  target.flags &= ~(MF_SHOOTABLE | MF_FLOAT | MF_SKULLFLY);
  if (target.type !== MT.LOSTSOUL) target.flags &= ~MF_NOGRAVITY;
  target.flags |= MF_CORPSE | MF_DROPOFF;
  target.height /= 4;
  const monster = target.info.kind === 'monster';
  if (monster) G.onMonsterKilled(target, source, inflictor);
  if (target.player) {
    target.flags &= ~MF_SOLID;
    const p = target.player;
    p.playerstate = 'dead';
    p.deathTime = G.leveltime;
    dropWeapon(p);
    G.onPlayerKilled(p, source && source.player ? source.player : null, inflictor, source);
  }
  if (target.health < -target.info.spawnhealth && target.info.xdeathstate !== S_NULL) setMobjState(target, target.info.xdeathstate);
  else setMobjState(target, target.info.deathstate);
  if (target.removed) return;
  target.tics -= P_Random() & 3;
  if (target.tics < 1) target.tics = 1;
  if (!monster) return;
  // zombies drop their weapon
  const drop = target.type === MT.ZOMBIE ? MT.CLIP : target.type === MT.SHOTGUY ? MT.SHOTGUN : target.type === MT.CHAINGUY ? MT.CHAINGUN : null;
  if (drop !== null) {
    const mo = spawnMobj(target.x, target.y, ONFLOORZ, drop);
    mo.flags |= MF_DROPPED;
  }
  // only the last few monster corpses stay (every corpse is a prop in CS2)
  const q = G.corpseQueue || (G.corpseQueue = []);
  q.push(target);
  while (q.length > (G.cfg.maxMonsterCorpses || 24)) { const old = q.shift(); if (!old.removed && (old.flags & MF_CORPSE)) removeMobj(old); }
}

// ---------------------------------------------------------------- pickups
function giveAmmo(player, ammo, num) {
  if (ammo === AM_NOAMMO) return false;
  if (player.ammo[ammo] === player.maxammo[ammo]) return false;
  if (num) num *= CLIPAMMO[ammo]; else num = CLIPAMMO[ammo] / 2;
  const oldammo = player.ammo[ammo];
  player.ammo[ammo] = Math.min(player.maxammo[ammo], player.ammo[ammo] + num);
  if (oldammo) return true;
  switch (ammo) {
    case AM_CLIP:
      if (player.readyweapon === WP_FIST) player.pendingweapon = player.weaponowned[WP_CHAINGUN] ? WP_CHAINGUN : WP_PISTOL;
      break;
    case AM_SHELL:
      if (player.readyweapon === WP_FIST || player.readyweapon === WP_PISTOL) if (player.weaponowned[WP_SHOTGUN]) player.pendingweapon = WP_SHOTGUN;
      break;
    case AM_CELL:
      if (player.readyweapon === WP_FIST || player.readyweapon === WP_PISTOL) if (player.weaponowned[WP_PLASMA]) player.pendingweapon = WP_PLASMA;
      break;
    case AM_MISL:
      if (player.readyweapon === WP_FIST) if (player.weaponowned[WP_MISSILE]) player.pendingweapon = WP_MISSILE;
      break;
  }
  return true;
}

function giveWeapon(player, weapon, dropped) {
  const ammo = WEAPONINFO[weapon].ammo;
  if (!G.cfg.altdeath && !dropped) {
    // weapons stay: only collect a weapon you don't have yet
    if (player.weaponowned[weapon]) return false;
    player.bonuscount += BONUSADD;
    player.weaponowned[weapon] = true;
    giveAmmo(player, ammo, 5);
    player.pendingweapon = weapon;
    startLocalSound(player, 'wpnup');
    G.message(player, [null, null, MSG.GOTSHOTGUN, MSG.GOTCHAINGUN, MSG.GOTLAUNCHER, MSG.GOTPLASMA, MSG.GOTBFG9000, MSG.GOTCHAINSAW, MSG.GOTSHOTGUN2][weapon]);
    return false;
  }
  let gaveammo = false, gaveweapon = false;
  if (ammo !== AM_NOAMMO) gaveammo = giveAmmo(player, ammo, dropped ? 1 : 2);
  if (!player.weaponowned[weapon]) {
    gaveweapon = true; player.weaponowned[weapon] = true; player.pendingweapon = weapon;
  }
  return gaveweapon || gaveammo;
}

function giveBody(player, num) {
  if (player.health >= 100) return false;
  player.health = Math.min(100, player.health + num);
  player.mo.health = player.health;
  return true;
}

function giveArmor(player, type) {
  const hits = type * 100;
  if (player.armorpoints >= hits) return false;
  player.armortype = type; player.armorpoints = hits;
  return true;
}

function givePower(player, power) {
  if (power === PW_INVULN) { player.powers[power] = POWER_TICS[power]; return true; }
  if (power === PW_INVIS) { player.powers[power] = POWER_TICS[power]; player.mo.flags |= MF_SHADOW; return true; }
  if (power === PW_STRENGTH) { giveBody(player, 100); player.powers[power] = 1; return true; }
  if (player.powers[power]) return false;
  player.powers[power] = POWER_TICS[power];
  return true;
}

function touchSpecialThing(special, toucher) {
  const delta = special.z - toucher.z;
  if (delta > toucher.height || delta < -8) return;
  if (toucher.health <= 0) return;
  const player = toucher.player;
  if (!player || player.spectating) return;
  let sound = 'itemup', msg = null;
  const pk = special.info.pickup;
  const [kind, a, b] = pk.split(':');
  switch (kind) {
    case 'armor':
      if (!giveArmor(player, +a)) return;
      msg = a === '1' ? MSG.GOTARMOR : MSG.GOTMEGA; break;
    case 'hbonus':
      player.health = Math.min(200, player.health + 1); player.mo.health = player.health; msg = MSG.GOTHTHBONUS; break;
    case 'abonus':
      player.armorpoints = Math.min(200, player.armorpoints + 1);
      if (!player.armortype) player.armortype = 1;
      msg = MSG.GOTARMBONUS; break;
    case 'soul':
      player.health = Math.min(200, player.health + 100); player.mo.health = player.health;
      msg = MSG.GOTSUPER; sound = 'getpow'; break;
    case 'mega':
      player.health = 200; player.mo.health = 200; giveArmor(player, 2);
      msg = MSG.GOTMSPHERE; sound = 'getpow'; break;
    case 'stim':
      if (!giveBody(player, 10)) return; msg = MSG.GOTSTIM; break;
    case 'medi':
      if (!giveBody(player, 25)) return;
      msg = player.health < 25 + 25 ? MSG.GOTMEDINEED : MSG.GOTMEDIKIT; break;
    case 'invuln':
      if (!givePower(player, PW_INVULN)) return; msg = MSG.GOTINVUL; sound = 'getpow'; break;
    case 'berserk':
      if (!givePower(player, PW_STRENGTH)) return;
      msg = MSG.GOTBERSERK;
      if (player.readyweapon !== WP_FIST) player.pendingweapon = WP_FIST;
      sound = 'getpow'; break;
    case 'invis':
      if (!givePower(player, PW_INVIS)) return; msg = MSG.GOTINVIS; sound = 'getpow'; break;
    case 'ammo': {
      const am = +a, n = +b;
      if (!giveAmmo(player, am, (special.flags & MF_DROPPED) ? 0 : n)) return;
      msg = [[MSG.GOTCLIP, MSG.GOTCLIPBOX], [MSG.GOTSHELLS, MSG.GOTSHELLBOX], [MSG.GOTCELL, MSG.GOTCELLBOX], [MSG.GOTROCKET, MSG.GOTROCKBOX]][am][n === 5 ? 1 : 0];
      break;
    }
    case 'backpack':
      if (!player.backpack) { for (let i = 0; i < 4; i++) player.maxammo[i] *= 2; player.backpack = true; }
      for (let i = 0; i < 4; i++) giveAmmo(player, i, 1);
      msg = MSG.GOTBACKPACK; break;
    case 'weapon': {
      const w = +a;
      if (!giveWeapon(player, w, !!(special.flags & MF_DROPPED))) return;
      msg = [null, null, MSG.GOTSHOTGUN, MSG.GOTCHAINGUN, MSG.GOTLAUNCHER, MSG.GOTPLASMA, MSG.GOTBFG9000, MSG.GOTCHAINSAW, MSG.GOTSHOTGUN2][w];
      sound = 'wpnup'; break;
    }
    default:
      return;
  }
  removeMobj(special);
  player.bonuscount += BONUSADD;
  if (msg) G.message(player, msg);
  startLocalSound(player, sound);
  player.stats.pickups++;
}

function dropWeapon(player) {
  setPsprite(player, 0, WEAPONINFO[player.readyweapon].down);
}

// item respawn (deathmatch 2.0 rules)
function respawnSpecials() {
  if (!G.cfg.altdeath) return;
  const q = G.itemRespawnQueue;
  if (!q.length) return;
  if (G.leveltime - q[0].time < G.cfg.itemRespawnTics) return;
  const { point } = q.shift();
  const x = point[0], y = point[1];
  const sec = G.level.sectorAt(x, y);
  const fog = spawnMobj(x, y, sec.floorheight, MT.IFOG);
  startSound(fog, 'itmbk');
  const type = DOOMEDNUM[point[3]];
  const info = MOBJINFO[type];
  const mo = spawnMobj(x, y, (info.flags & MF_SPAWNCEILING) ? ONCEILINGZ : ONFLOORZ, type);
  mo.spawnpoint = point;
  mo.angle = point[2];
}

// ---------------------------------------------------------------- mobj action functions
const MOBJ_ACTIONS = {
  A_Explode(mo) { radiusAttack(mo, mo.target, 128); },
  A_Scream(mo) { if (mo.info.deathsound) startSound(mo, mo.info.deathsound); },
  A_XScream(mo) { startSound(mo, 'slop'); },
  A_Pain(mo) { if (mo.info.painsound) startSound(mo, mo.info.painsound); },
  A_Fall(mo) { mo.flags &= ~MF_SOLID; },
  A_PlayerScream(mo) {
    let sound = 'pldeth';
    if (mo.health < -50) sound = 'pdiehi';
    startSound(mo, sound);
  },
  A_BFGSpray(mo) {
    const src = mo.target;
    if (!src || src.removed) return;
    for (let i = 0; i < 40; i++) {
      const an = normAngle(mo.angle - ANG90 / 2 + (ANG90 / 40) * i);
      aimLineAttack(src, an, 16 * 64);
      const t = AIM.linetarget;
      if (!t) continue;
      spawnMobj(t.x, t.y, t.z + t.height / 4, MT.EXTRABFG);
      let damage = 0;
      for (let j = 0; j < 15; j++) damage += (P_Random() & 7) + 1;
      G.damageCtx = 'bfgspray';
      damageMobj(t, src, src, damage);
      G.damageCtx = null;
    }
  },
};
