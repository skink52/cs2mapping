// ===================================================================================
// Part 3b: monsters - thinking, movement, attacks (p_enemy). The state tables are in 00_a_monsters.js.
// Monsters target players (humans and bots alike) and whatever hurts them, so they fight each other too.
// ===================================================================================

const DI_EAST = 0, DI_NORTHEAST = 1, DI_NORTH = 2, DI_NORTHWEST = 3, DI_WEST = 4, DI_SOUTHWEST = 5, DI_SOUTH = 6, DI_SOUTHEAST = 7, DI_NODIR = 8;
const DIR_X = [1, 47000 / 65536, 0, -47000 / 65536, -1, -47000 / 65536, 0, 47000 / 65536];
const DIR_Y = [0, 47000 / 65536, 1, 47000 / 65536, 0, -47000 / 65536, -1, -47000 / 65536];
const DIR_OPPOSITE = [DI_WEST, DI_SOUTHWEST, DI_SOUTH, DI_SOUTHEAST, DI_EAST, DI_NORTHEAST, DI_NORTH, DI_NORTHWEST, DI_NODIR];
const DIR_DIAGS = [DI_NORTHWEST, DI_NORTHEAST, DI_SOUTHWEST, DI_SOUTHEAST];
const SKULLSPEED = 20;
const TRACEANGLE = 0xc000000 / 0x100000000 * 360;   // 16.875 degrees per tracer step
const FATSPREAD = 90 / 8;

function isMonster(mo) { return !!mo && mo.info.kind === 'monster'; }

// ---------------------------------------------------------------- noise: a shot wakes up monsters that can hear it
// Which sectors a shot reaches (and through how many sound-blocking lines) only depends on which two-sided lines are
// shut. That is remembered per sector the shot came from until a door or lift opens or shuts a line (openVersion,
// see movePlane), so a crowd firing from the same rooms doesn't flood the whole level for every shot.
function noiseAlert(target, emitter) {
  if (!G || !G.monsterCount) return;
  G.validcount++;
  const start = emitter.sector || G.level.sectorAt(emitter.x, emitter.y);
  const vc = G.validcount;
  const cache = G.noiseCache || (G.noiseCache = new Map());
  const hit = cache.get(start);
  if (hit && hit.ver === (G.openVersion || 0)) {
    const secs = hit.secs, trav = hit.trav;
    for (let i = 0; i < secs.length; i++) { const sec = secs[i]; sec.validcount = vc; sec.soundtraversed = trav[i]; sec.soundtarget = target; }
    return;
  }
  const secs = [];
  noiseFlood(start, 0, target, vc, secs);
  const trav = new Array(secs.length);
  for (let i = 0; i < secs.length; i++) trav[i] = secs[i].soundtraversed;
  cache.set(start, { ver: G.openVersion || 0, secs, trav });
}

function noiseFlood(sec, soundblocks, soundtarget, vc, secs) {
  if (sec.validcount === vc) { if (sec.soundtraversed <= soundblocks + 1) return; }
  else secs.push(sec);
  sec.validcount = vc;
  sec.soundtraversed = soundblocks + 1;
  sec.soundtarget = soundtarget;
  const lines = sec.lines;
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (!(l.flags & ML_TWOSIDED) || !l.backsector) continue;
    const front = l.frontsector, back = l.backsector;
    // lineOpening(l).range <= 0, written out
    if (Math.min(front.ceilingheight, back.ceilingheight) - Math.max(front.floorheight, back.floorheight) <= 0) continue;
    const other = front === sec ? back : front;
    if (l.flags & ML_SOUNDBLOCK) { if (!soundblocks) noiseFlood(other, 1, soundtarget, vc, secs); }
    else noiseFlood(other, soundblocks, soundtarget, vc, secs);
  }
}

// ---------------------------------------------------------------- targets
function targetable(mo) {
  return !!mo && !mo.removed && mo.health > 0 && (mo.flags & MF_SHOOTABLE) && !(mo.player && mo.player.spectating);
}

// Doom looks at two players per call, round robin, so a crowd doesn't cost a full scan every tic
function lookForPlayers(actor, allaround) {
  const list = G.playerMobjs || [];
  const n = list.length;
  if (!n) return false;
  actor.lastlook = actor.lastlook || 0;
  for (let c = 0; c < Math.min(3, n); c++) {
    const i = (actor.lastlook + c) % n;
    const mo = list[i];
    if (!targetable(mo)) continue;
    if (!checkSight(actor, mo)) continue;
    if (!allaround) {
      const an = Math.abs(angleDiff(actor.angle, pointToAngle(actor.x, actor.y, mo.x, mo.y)));
      if (an > 90 && approxDistance(mo.x - actor.x, mo.y - actor.y) > MELEERANGE) continue;   // behind its back
    }
    actor.lastlook = (i + 1) % n;
    actor.target = mo;
    return true;
  }
  actor.lastlook = (actor.lastlook + 3) % n;
  return false;
}

function checkMeleeRange(actor) {
  const pl = actor.target;
  if (!pl) return false;
  const dist = approxDistance(pl.x - actor.x, pl.y - actor.y);
  if (dist >= MELEERANGE - 20 + pl.info.radius) return false;
  return checkSight(actor, pl);
}

function checkMissileRange(actor) {
  if (!checkSight(actor, actor.target)) return false;
  if (actor.flags & MF_JUSTHIT) { actor.flags &= ~MF_JUSTHIT; return true; }   // just got hit: fight back
  if (actor.reactiontime) return false;
  let dist = approxDistance(actor.x - actor.target.x, actor.y - actor.target.y) - 64;
  if (actor.info.meleestate === S_NULL) dist -= 128;
  if (actor.type === MT.ARCHVILE && dist > 14 * 64) return false;
  if (actor.type === MT.REVENANT) { if (dist < 196) return false; dist /= 2; }
  if (actor.type === MT.CYBERDEMON || actor.type === MT.MASTERMIND || actor.type === MT.LOSTSOUL) dist /= 2;
  if (dist > 200) dist = 200;
  if (actor.type === MT.CYBERDEMON && dist > 160) dist = 160;
  return !(P_Random() < dist);
}

// ---------------------------------------------------------------- movement
// doors a monster can open (Doom: only type 1 and a try at the locked ones).
// Keys don't exist here (deathmatch strips them), and the bots' routes and the spawn spots treat every door as open,
// so monsters open the locked kinds too, else a monster behind one stalls a wave.
const MONSTER_DOORS = new Set([1, 26, 27, 28, 31, 32, 33, 34, 117, 118]);

function monsterMove(actor) {
  if (actor.movedir === DI_NODIR || actor.movedir === undefined) return false;
  const tryx = actor.x + actor.info.speed * DIR_X[actor.movedir], tryy = actor.y + actor.info.speed * DIR_Y[actor.movedir];
  if (!tryMove(actor, tryx, tryy)) {
    if ((actor.flags & MF_FLOAT) && floatok) {
      // must adjust height
      if (actor.z < TM.floorz) actor.z += FLOATSPEED; else actor.z -= FLOATSPEED;
      actor.flags |= MF_INFLOAT;
      return true;
    }
    if (!TM.spechit.length) return false;
    actor.movedir = DI_NODIR;
    let good = false;
    const hits = TM.spechit.slice();
    for (const ld of hits) {
      if (!MONSTER_DOORS.has(ld.special)) continue;
      if (useSpecialLine(actor, ld, 0)) good = true;
    }
    return good;
  }
  actor.flags &= ~MF_INFLOAT;
  if (!(actor.flags & MF_FLOAT)) actor.z = actor.floorz;
  return true;
}

function tryWalk(actor) {
  if (!monsterMove(actor)) return false;
  actor.movecount = P_Random() & 15;
  return true;
}

function newChaseDir(actor) {
  if (!actor.target) { actor.movedir = DI_NODIR; return; }
  const olddir = actor.movedir === undefined ? DI_NODIR : actor.movedir;
  const turnaround = DIR_OPPOSITE[olddir];
  const deltax = actor.target.x - actor.x, deltay = actor.target.y - actor.y;
  const d = [DI_NODIR, DI_NODIR, DI_NODIR];
  if (deltax > 10) d[1] = DI_EAST; else if (deltax < -10) d[1] = DI_WEST;
  if (deltay < -10) d[2] = DI_SOUTH; else if (deltay > 10) d[2] = DI_NORTH;
  if (d[1] !== DI_NODIR && d[2] !== DI_NODIR) {
    actor.movedir = DIR_DIAGS[((deltay < 0 ? 1 : 0) << 1) + (deltax > 0 ? 1 : 0)];
    if (actor.movedir !== turnaround && tryWalk(actor)) return;
  }
  if (P_Random() > 200 || Math.abs(deltay) > Math.abs(deltax)) { const t = d[1]; d[1] = d[2]; d[2] = t; }
  if (d[1] === turnaround) d[1] = DI_NODIR;
  if (d[2] === turnaround) d[2] = DI_NODIR;
  if (d[1] !== DI_NODIR) { actor.movedir = d[1]; if (tryWalk(actor)) return; }
  if (d[2] !== DI_NODIR) { actor.movedir = d[2]; if (tryWalk(actor)) return; }
  if (olddir !== DI_NODIR) { actor.movedir = olddir; if (tryWalk(actor)) return; }
  if (P_Random() & 1) {
    for (let t = DI_EAST; t <= DI_SOUTHEAST; t++) if (t !== turnaround) { actor.movedir = t; if (tryWalk(actor)) return; }
  } else {
    for (let t = DI_SOUTHEAST; t >= DI_EAST; t--) if (t !== turnaround) { actor.movedir = t; if (tryWalk(actor)) return; }
  }
  if (turnaround !== DI_NODIR) { actor.movedir = turnaround; if (tryWalk(actor)) return; }
  actor.movedir = DI_NODIR;
}

// ---------------------------------------------------------------- missiles fired at a thing
function spawnMissile(source, dest, type) {
  const th = spawnMobj(source.x, source.y, source.z + 32, type);
  if (th.info.seesound) startSound(th, th.info.seesound);
  th.target = source;
  let an = pointToAngle(source.x, source.y, dest.x, dest.y);
  if (dest.flags & MF_SHADOW) an = normAngle(an + (P_Random() - P_Random()) * (360 / 4096));
  th.angle = an; th.pangle = an;
  const sp = th.info.speed;
  th.momx = sp * Math.cos(an * DEG); th.momy = sp * Math.sin(an * DEG);
  let dist = approxDistance(dest.x - source.x, dest.y - source.y) / sp;
  if (dist < 1) dist = 1;
  th.momz = (dest.z - source.z) / dist;
  checkMissileSpawn(th);
  return th;
}

// ---------------------------------------------------------------- the shared chase logic
function A_FaceTarget(actor) {
  if (!actor.target) return;
  actor.flags &= ~MF_AMBUSH;
  actor.angle = pointToAngle(actor.x, actor.y, actor.target.x, actor.target.y);
  if (actor.target.flags & MF_SHADOW) actor.angle = normAngle(actor.angle + (P_Random() - P_Random()) * (360 / 2048));
}

function A_Look(actor) {
  actor.threshold = 0;
  const sec = actor.sector;
  const targ = sec && sec.soundtarget;
  let seen = false;
  if (targ && targetable(targ)) {
    actor.target = targ;
    seen = !(actor.flags & MF_AMBUSH) || checkSight(actor, targ);
  }
  if (!seen && !lookForPlayers(actor, false)) return;
  if (actor.info.seesound) {
    let snd = actor.info.seesound;
    if (snd === 'posit1' || snd === 'posit2' || snd === 'posit3') snd = 'posit' + (P_Random() % 3 + 1);
    else if (snd === 'bgsit1' || snd === 'bgsit2') snd = 'bgsit' + (P_Random() % 2 + 1);
    startSound(actor, snd);
  }
  setMobjState(actor, actor.info.seestate);
}

function A_Chase(actor) {
  if (actor.reactiontime) actor.reactiontime--;
  if (actor.threshold) {
    if (!actor.target || actor.target.health <= 0) actor.threshold = 0;
    else actor.threshold--;
  }
  // turn towards the movement direction in 45 degree steps
  if (actor.movedir !== undefined && actor.movedir < 8) {
    actor.angle = Math.floor(normAngle(actor.angle) / 45) * 45;
    const delta = angleDiff(actor.movedir * 45, actor.angle);
    if (delta > 0) actor.angle = normAngle(actor.angle - 45);
    else if (delta < 0) actor.angle = normAngle(actor.angle + 45);
  }
  if (!targetable(actor.target)) {
    if (lookForPlayers(actor, true)) return;   // got a new target
    actor.target = null;
    setMobjState(actor, actor.info.spawnstate);
    return;
  }
  // do not attack twice in a row
  if (actor.flags & MF_JUSTATTACKED) {
    actor.flags &= ~MF_JUSTATTACKED;
    newChaseDir(actor);
    return;
  }
  if (actor.info.meleestate !== S_NULL && checkMeleeRange(actor)) {
    if (actor.info.attacksound) startSound(actor, actor.info.attacksound);
    setMobjState(actor, actor.info.meleestate);
    return;
  }
  if (actor.info.missilestate !== S_NULL && !actor.movecount && checkMissileRange(actor)) {
    setMobjState(actor, actor.info.missilestate);
    actor.flags |= MF_JUSTATTACKED;
    return;
  }
  // possibly choose another target
  if (!actor.threshold && !checkSight(actor, actor.target)) {
    if (lookForPlayers(actor, true)) return;
  }
  if (--actor.movecount < 0 || !monsterMove(actor)) newChaseDir(actor);
  if (actor.info.activesound && P_Random() < 3) startSound(actor, actor.info.activesound);
}

// ---------------------------------------------------------------- attacks
function monsterShot(actor, spread, pellets, sound) {
  if (!actor.target) return;
  A_FaceTarget(actor);
  const bangle = actor.angle;
  const slope = aimLineAttack(actor, bangle, MISSILERANGE);
  if (sound) startSound(actor, sound);
  for (let i = 0; i < pellets; i++) {
    const angle = normAngle(bangle + (P_Random() - P_Random()) * spread);
    const damage = ((P_Random() % 5) + 1) * 3;
    lineAttack(actor, angle, MISSILERANGE, slope, damage);
  }
}

function meleeOrMissile(actor, meleeDamage, missileType, meleeSound) {
  if (!actor.target) return;
  A_FaceTarget(actor);
  if (checkMeleeRange(actor)) {
    if (meleeSound) startSound(actor, meleeSound);
    damageMobj(actor.target, actor, actor, meleeDamage());
    return;
  }
  if (missileType !== undefined) spawnMissile(actor, actor.target, missileType);
}

function refire(actor, chance) {
  A_FaceTarget(actor);
  if (P_Random() < chance) return;
  if (!targetable(actor.target) || !checkSight(actor, actor.target)) setMobjState(actor, actor.info.seestate);
}

function skullAttack(actor) {
  if (!actor.target) return;
  const dest = actor.target;
  actor.flags |= MF_SKULLFLY;
  if (actor.info.attacksound) startSound(actor, actor.info.attacksound);
  A_FaceTarget(actor);
  actor.momx = SKULLSPEED * Math.cos(actor.angle * DEG); actor.momy = SKULLSPEED * Math.sin(actor.angle * DEG);
  let dist = approxDistance(dest.x - actor.x, dest.y - actor.y) / SKULLSPEED;
  if (dist < 1) dist = 1;
  actor.momz = (dest.z + dest.height / 2 - actor.z) / dist;
}

// true when nothing solid lies on the straight line between the two points (one-sided walls, blocking lines, closed
// doors); used where Doom placed things blindly and could put them through a wall
function clearLine(x1, y1, x2, y2, height) {
  return pathTraverse(x1, y1, x2, y2, PT_ADDLINES, (ic) => {
    const li = ic.line;
    if (!li.backsector || !(li.flags & ML_TWOSIDED) || (li.flags & ML_BLOCKING)) return false;
    return lineOpening(li).range >= (height || 16);
  });
}

function painShootSkull(actor, angle) {
  let count = 0;
  for (const m of G.mobjs) if (m.type === MT.LOSTSOUL && m.health > 0) count++;
  if (count > (G.cfg.maxLostSouls || 20)) return;
  const prestep = 4 + 3 * (actor.info.radius + MOBJINFO[MT.LOSTSOUL].radius) / 2;
  const x = actor.x + prestep * Math.cos(angle * DEG), y = actor.y + prestep * Math.sin(angle * DEG);
  // Doom spawns the skull blindly, which can put it beyond a wall into the void (it then flies around outside the level)
  if (!clearLine(actor.x, actor.y, x, y, 32) || (G.inside && !G.inside(x, y))) return;
  const skull = spawnMobj(x, y, actor.z + 8, MT.LOSTSOUL);
  skull.spawnedBy = 'pain';
  if (!tryMove(skull, skull.x, skull.y)) { damageMobj(skull, actor, actor, 10000); return; }
  skull.target = actor.target;
  G.onMonsterSpawned(skull, actor);
  skullAttack(skull);
}

function fatShot(actor, spread1, spread2) {
  // two shots a little apart: the first towards the target plus spread1, the second re-aimed by spread2
  A_FaceTarget(actor);
  actor.angle = normAngle(actor.angle + spread1);
  const mo = spawnMissile(actor, actor.target, MT.FATSHOT);
  const mo2 = spawnMissile(actor, actor.target, MT.FATSHOT);
  mo2.angle = normAngle(mo2.angle + spread2);
  mo2.momx = mo2.info.speed * Math.cos(mo2.angle * DEG); mo2.momy = mo2.info.speed * Math.sin(mo2.angle * DEG);
  return mo;
}

Object.assign(MOBJ_ACTIONS, {
  A_Look, A_Chase, A_FaceTarget,
  A_BossDeath() { /* level-specific in Doom; nothing here */ },
  A_PosAttack(actor) { monsterShot(actor, 360 / 4096, 1, 'pistol'); },
  A_SPosAttack(actor) { monsterShot(actor, 360 / 4096, 3, 'shotgn'); },
  A_CPosAttack(actor) { monsterShot(actor, 360 / 4096, 1, 'shotgn'); },
  A_CPosRefire(actor) { refire(actor, 40); },
  A_SpidRefire(actor) { refire(actor, 10); },
  A_BspiAttack(actor) { if (!actor.target) return; A_FaceTarget(actor); spawnMissile(actor, actor.target, MT.ARACHPLASMA); },
  A_TroopAttack(actor) { meleeOrMissile(actor, () => (P_Random() % 8 + 1) * 3, MT.IMPBALL, 'claw'); },
  A_SargAttack(actor) { meleeOrMissile(actor, () => ((P_Random() % 10) + 1) * 4, undefined, null); },
  A_HeadAttack(actor) { meleeOrMissile(actor, () => (P_Random() % 6 + 1) * 10, MT.CACOBALL, null); },
  A_CyberAttack(actor) { if (!actor.target) return; A_FaceTarget(actor); spawnMissile(actor, actor.target, MT.ROCKET); },
  A_BruisAttack(actor) {
    if (!actor.target) return;
    if (checkMeleeRange(actor)) { startSound(actor, 'claw'); damageMobj(actor.target, actor, actor, (P_Random() % 8 + 1) * 10); return; }
    spawnMissile(actor, actor.target, MT.BARONBALL);
  },
  A_SkelMissile(actor) {
    if (!actor.target) return;
    A_FaceTarget(actor);
    actor.z += 16;
    const mo = spawnMissile(actor, actor.target, MT.TRACER);
    actor.z -= 16;
    mo.x += mo.momx; mo.y += mo.momy;
    mo.tracer = actor.target;
  },
  A_Tracer(actor) {
    if (G.leveltime & 3) return;
    spawnPuff(actor.x, actor.y, actor.z);
    const th = spawnMobj(actor.x - actor.momx, actor.y - actor.momy, actor.z, MT.SMOKE);
    th.momz = 1;
    th.tics -= P_Random() & 3;
    if (th.tics < 1) th.tics = 1;
    const dest = actor.tracer;
    if (!dest || dest.removed || dest.health <= 0) return;
    // adjust direction
    const exact = pointToAngle(actor.x, actor.y, dest.x, dest.y);
    const d = angleDiff(actor.angle, exact);
    if (d !== 0) actor.angle = Math.abs(d) <= TRACEANGLE ? exact : normAngle(actor.angle + (d > 0 ? TRACEANGLE : -TRACEANGLE));
    actor.momx = actor.info.speed * Math.cos(actor.angle * DEG); actor.momy = actor.info.speed * Math.sin(actor.angle * DEG);
    // change slope
    let dist = approxDistance(dest.x - actor.x, dest.y - actor.y) / actor.info.speed;
    if (dist < 1) dist = 1;
    const slope = (dest.z + 40 - actor.z) / dist;
    if (slope < actor.momz) actor.momz -= 1 / 8; else actor.momz += 1 / 8;
  },
  A_SkelWhoosh(actor) { if (!actor.target) return; A_FaceTarget(actor); startSound(actor, 'skeswg'); },
  A_SkelFist(actor) {
    if (!actor.target) return;
    A_FaceTarget(actor);
    if (checkMeleeRange(actor)) { startSound(actor, 'skepch'); damageMobj(actor.target, actor, actor, ((P_Random() % 10) + 1) * 6); }
  },
  A_VileChase(actor) {
    // an arch-vile that walks into a dead monster brings it back
    if (actor.movedir !== undefined && actor.movedir !== DI_NODIR) {
      const tryx = actor.x + actor.info.speed * DIR_X[actor.movedir], tryy = actor.y + actor.info.speed * DIR_Y[actor.movedir];
      const xl = blockX(tryx - MAXRADIUS * 2), xh = blockX(tryx + MAXRADIUS * 2), yl = blockY(tryy - MAXRADIUS * 2), yh = blockY(tryy + MAXRADIUS * 2);
      /** @type {any} */ let corpse = null;
      for (let bx = xl; bx <= xh && !corpse; bx++) for (let by = yl; by <= yh && !corpse; by++) {
        blockThingsIterator(bx, by, (th) => {
          if (!(th.flags & MF_CORPSE) || th.tics !== -1 || !isMonster(th) || th.info.raisestate === S_NULL) return true;
          const maxdist = th.info.radius + actor.info.radius;
          if (Math.abs(th.x - tryx) > maxdist || Math.abs(th.y - tryy) > maxdist) return true;
          th.momx = th.momy = 0;
          th.height *= 4;
          const ok = checkPosition(th, th.x, th.y);
          th.height /= 4;
          if (!ok) return true;
          corpse = th; return false;
        });
      }
      if (corpse) {
        const temp = actor.target;
        actor.target = corpse; A_FaceTarget(actor); actor.target = temp;
        setMobjState(actor, SN('VILE_HEAL1'));
        startSound(corpse, 'slop');
        const info = corpse.info;
        setMobjState(corpse, info.raisestate);
        corpse.height *= 4;
        corpse.flags = info.flags;
        corpse.health = info.spawnhealth;
        corpse.target = null;
        corpse.boss = false;   // a raised boss is just a big monster
        G.onMonsterRaised(corpse);
        return;
      }
    }
    A_Chase(actor);
  },
  A_VileStart(actor) { startSound(actor, 'vilatk'); },
  A_StartFire(actor) { startSound(actor, 'flamst'); MOBJ_ACTIONS.A_Fire(actor); },
  A_FireCrackle(actor) { startSound(actor, 'flame'); MOBJ_ACTIONS.A_Fire(actor); },
  A_Fire(actor) {
    // keep the fire in front of whoever the arch-vile is burning
    const dest = actor.tracer;
    if (!dest || dest.removed) return;
    if (!actor.target || actor.target.removed || !checkSight(actor.target, dest)) return;
    unsetThingPosition(actor);
    actor.x = dest.x + 24 * Math.cos(dest.angle * DEG); actor.y = dest.y + 24 * Math.sin(dest.angle * DEG);
    actor.z = dest.z;
    setThingPosition(actor);
    actor.teleported = true;
  },
  A_VileTarget(actor) {
    if (!actor.target) return;
    A_FaceTarget(actor);
    const fog = spawnMobj(actor.target.x, actor.target.y, actor.target.z, MT.VILEFIRE);
    actor.tracer = fog;
    fog.target = actor; fog.tracer = actor.target;
    MOBJ_ACTIONS.A_Fire(fog);
  },
  A_VileAttack(actor) {
    if (!actor.target) return;
    A_FaceTarget(actor);
    if (!checkSight(actor, actor.target)) return;
    startSound(actor, 'barexp');
    damageMobj(actor.target, actor, actor, 20);
    if (!actor.target.removed) actor.target.momz = 1000 / actor.target.info.mass;
    const fire = actor.tracer;
    if (!fire || fire.removed) return;
    unsetThingPosition(fire);
    fire.x = actor.target.x - 24 * Math.cos(actor.angle * DEG); fire.y = actor.target.y - 24 * Math.sin(actor.angle * DEG);
    setThingPosition(fire);
    radiusAttack(fire, actor, 70);
  },
  A_FatRaise(actor) { A_FaceTarget(actor); startSound(actor, 'manatk'); },
  A_FatAttack1(actor) { if (actor.target) fatShot(actor, FATSPREAD, FATSPREAD); },
  A_FatAttack2(actor) { if (actor.target) fatShot(actor, -FATSPREAD, -FATSPREAD * 2); },
  A_FatAttack3(actor) {
    if (!actor.target) return;
    A_FaceTarget(actor);
    for (const s of [-FATSPREAD / 2, FATSPREAD / 2]) {
      const mo = spawnMissile(actor, actor.target, MT.FATSHOT);
      mo.angle = normAngle(mo.angle + s);
      mo.momx = mo.info.speed * Math.cos(mo.angle * DEG); mo.momy = mo.info.speed * Math.sin(mo.angle * DEG);
    }
  },
  A_SkullAttack: skullAttack,
  A_PainAttack(actor) { if (!actor.target) return; A_FaceTarget(actor); painShootSkull(actor, actor.angle); },
  A_PainDie(actor) {
    actor.flags &= ~MF_SOLID;
    painShootSkull(actor, actor.angle + 90);
    painShootSkull(actor, actor.angle + 180);
    painShootSkull(actor, actor.angle + 270);
  },
  A_Hoof(actor) { startSound(actor, 'hoof'); A_Chase(actor); },
  A_Metal(actor) { startSound(actor, 'metal'); A_Chase(actor); },
  A_BabyMetal(actor) { startSound(actor, 'bspwlk'); A_Chase(actor); },
});

// death cries with Doom's random variants (A_Scream in 30_mobj.js covers the fixed ones)
const baseScream = MOBJ_ACTIONS.A_Scream;
MOBJ_ACTIONS.A_Scream = function (mo) {
  const snd = mo.info.deathsound;
  if (snd === 'podth1' || snd === 'podth2' || snd === 'podth3') { startSound(mo, 'podth' + (P_Random() % 3 + 1)); return; }
  if (snd === 'bgdth1' || snd === 'bgdth2') { startSound(mo, 'bgdth' + (P_Random() % 2 + 1)); return; }
  baseScream(mo);
};
