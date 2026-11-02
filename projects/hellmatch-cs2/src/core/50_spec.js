// ===================================================================================
// Part 5: specials - doors, lifts, floors, ceilings, teleporters, switches, sector damage
// ===================================================================================

const PLANE_OK = 0, PLANE_CRUSHED = 1, PLANE_PASTDEST = 2;

// shut two-sided lines around a sector (a door or lift moving can only open or only shut lines in one move)
function shutLines(sector) {
  let n = 0;
  const lines = sector.lines;
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (!(l.flags & ML_TWOSIDED) || !l.backsector) continue;
    const front = l.frontsector, back = l.backsector;
    if (Math.min(front.ceilingheight, back.ceilingheight) - Math.max(front.floorheight, back.floorheight) <= 0) n++;
  }
  return n;
}

function movePlane(sector, speed, dest, crush, floorOrCeiling, direction) {
  const shut = shutLines(sector);
  const r = movePlaneHeights(sector, speed, dest, crush, floorOrCeiling, direction);
  if (shutLines(sector) !== shut) G.openVersion = (G.openVersion || 0) + 1;   // noise paths changed (noiseAlert)
  return r;
}

function movePlaneHeights(sector, speed, dest, crush, floorOrCeiling, direction) {
  if (floorOrCeiling === 0) {
    if (direction === -1) {
      if (sector.floorheight - speed < dest) {
        const last = sector.floorheight; sector.floorheight = dest;
        if (changeSector(sector, crush)) { sector.floorheight = last; changeSector(sector, crush); }
        return PLANE_PASTDEST;
      }
      const last = sector.floorheight; sector.floorheight -= speed;
      if (changeSector(sector, crush)) { sector.floorheight = last; changeSector(sector, crush); return PLANE_CRUSHED; }
    } else {
      if (sector.floorheight + speed > dest) {
        const last = sector.floorheight; sector.floorheight = dest;
        if (changeSector(sector, crush)) { sector.floorheight = last; changeSector(sector, crush); }
        return PLANE_PASTDEST;
      }
      const last = sector.floorheight; sector.floorheight += speed;
      if (changeSector(sector, crush)) {
        if (crush) return PLANE_CRUSHED;
        sector.floorheight = last; changeSector(sector, crush); return PLANE_CRUSHED;
      }
    }
  } else {
    if (direction === -1) {
      if (sector.ceilingheight - speed < dest) {
        const last = sector.ceilingheight; sector.ceilingheight = dest;
        if (changeSector(sector, crush)) { sector.ceilingheight = last; changeSector(sector, crush); }
        return PLANE_PASTDEST;
      }
      const last = sector.ceilingheight; sector.ceilingheight -= speed;
      if (changeSector(sector, crush)) {
        if (crush) return PLANE_CRUSHED;
        sector.ceilingheight = last; changeSector(sector, crush); return PLANE_CRUSHED;
      }
    } else {
      if (sector.ceilingheight + speed > dest) {
        const last = sector.ceilingheight; sector.ceilingheight = dest;
        if (changeSector(sector, crush)) { sector.ceilingheight = last; changeSector(sector, crush); }
        return PLANE_PASTDEST;
      }
      sector.ceilingheight += speed;
      changeSector(sector, crush);
    }
  }
  return PLANE_OK;
}

// ---------------------------------------------------------------- neighbour searches
function getNextSector(line, sec) {
  if (!(line.flags & ML_TWOSIDED)) return null;
  return line.frontsector === sec ? line.backsector : line.frontsector;
}
function findLowestFloorSurrounding(sec) {
  let h = sec.floorheight;
  for (const l of sec.lines) { const o = getNextSector(l, sec); if (o && o.floorheight < h) h = o.floorheight; }
  return h;
}
function findHighestFloorSurrounding(sec) {
  let h = -500, found = false;
  for (const l of sec.lines) { const o = getNextSector(l, sec); if (o && (!found || o.floorheight > h)) { h = o.floorheight; found = true; } }
  return found ? h : -500;
}
function findNextHighestFloor(sec, cur) {
  let best = null;
  for (const l of sec.lines) {
    const o = getNextSector(l, sec);
    if (o && o.floorheight > cur && (best === null || o.floorheight < best)) best = o.floorheight;
  }
  return best === null ? cur : best;
}
function findLowestCeilingSurrounding(sec) {
  let h = 32767;
  for (const l of sec.lines) { const o = getNextSector(l, sec); if (o && o.ceilingheight < h) h = o.ceilingheight; }
  return h;
}
function findHighestCeilingSurrounding(sec) {
  let h = 0;
  for (const l of sec.lines) { const o = getNextSector(l, sec); if (o && o.ceilingheight > h) h = o.ceilingheight; }
  return h;
}
function sectorsWithTag(tag) { return G.level.sectors.filter((s) => s.tag === tag); }

function sectorSound(sec, sfx) { startSound({ x: sec.soundorg.x, y: sec.soundorg.y, z: (sec.floorheight + sec.ceilingheight) / 2, sectorOrigin: sec }, sfx); }

function addThinker(t) { G.thinkers.push(t); }
function removeThinker(t) { t.removed = true; }

// ---------------------------------------------------------------- doors
const VDOORSPEED = 2, VDOORWAIT = 150;

function doorThink(d) {
  const sec = d.sector;
  switch (d.direction) {
    case 0:
      if (!--d.topcountdown) {
        if (d.type === 'blazeRaise' || d.type === 'normal') { d.direction = -1; sectorSound(sec, d.type === 'blazeRaise' ? 'bdcls' : 'dorcls'); }
        else if (d.type === 'close30ThenOpen') { d.direction = 1; sectorSound(sec, 'doropn'); }
      }
      break;
    case 2:
      if (!--d.topcountdown) {
        if (d.type === 'raiseIn5Mins') { d.direction = 1; d.type = 'normal'; sectorSound(sec, 'doropn'); }
      }
      break;
    case -1: {
      const res = movePlane(sec, d.speed, sec.floorheight, false, 1, -1);
      if (res === PLANE_PASTDEST) {
        if (d.type === 'blazeRaise' || d.type === 'blazeClose') { sec.specialdata = null; removeThinker(d); sectorSound(sec, 'bdcls'); }
        else if (d.type === 'normal' || d.type === 'close') { sec.specialdata = null; removeThinker(d); }
        else if (d.type === 'close30ThenOpen') { d.direction = 0; d.topcountdown = TICRATE * 30; }
      } else if (res === PLANE_CRUSHED) {
        if (d.type !== 'blazeClose' && d.type !== 'close') { d.direction = 1; sectorSound(sec, 'doropn'); }
      }
      break;
    }
    case 1: {
      const res = movePlane(sec, d.speed, d.topheight, false, 1, 1);
      if (res === PLANE_PASTDEST) {
        if (d.type === 'blazeRaise' || d.type === 'normal') { d.direction = 0; d.topcountdown = d.topwait; }
        else { sec.specialdata = null; removeThinker(d); }
      }
      break;
    }
  }
}

function newDoor(sec, type, speed) {
  const d = { kind: 'door', think: doorThink, sector: sec, type, speed, topwait: VDOORWAIT, direction: 1, topheight: 0, topcountdown: 0, removed: false };
  sec.specialdata = d;
  addThinker(d);
  return d;
}

function doDoor(line, type) {
  let rtn = false;
  for (const sec of sectorsWithTag(line.tag)) {
    if (sec.specialdata) continue;
    rtn = true;
    const blaze = type.startsWith('blaze');
    const d = newDoor(sec, type, blaze ? VDOORSPEED * 4 : VDOORSPEED);
    switch (type) {
      case 'blazeClose': case 'close':
        d.topheight = findLowestCeilingSurrounding(sec) - 4; d.direction = -1;
        sectorSound(sec, blaze ? 'bdcls' : 'dorcls'); break;
      case 'close30ThenOpen':
        d.topheight = sec.ceilingheight; d.direction = -1; sectorSound(sec, 'dorcls'); break;
      case 'blazeRaise': case 'blazeOpen': case 'normal': case 'open':
        d.direction = 1; d.topheight = findLowestCeilingSurrounding(sec) - 4;
        if (d.topheight !== sec.ceilingheight) sectorSound(sec, blaze ? 'bdopn' : 'doropn');
        break;
    }
  }
  return rtn;
}

function verticalDoor(line, thing) {
  const sec = line.backsector;
  if (!sec) return;
  const sp = line.special;
  if (sec.specialdata) {
    const d = sec.specialdata;
    if (d.kind === 'door' && (sp === 1 || sp === 26 || sp === 27 || sp === 28 || sp === 117)) {
      if (d.direction === -1) d.direction = 1;
      else { if (!thing.player) return; d.direction = -1; }
      return;
    }
    return;
  }
  switch (sp) {
    case 117: case 118: sectorSound(sec, 'bdopn'); break;
    default: sectorSound(sec, 'doropn'); break;
  }
  const d = newDoor(sec, 'normal', VDOORSPEED);
  switch (sp) {
    case 1: case 26: case 27: case 28: d.type = 'normal'; break;
    case 31: case 32: case 33: case 34: d.type = 'open'; line.special = 0; break;
    case 117: d.type = 'blazeRaise'; d.speed = VDOORSPEED * 4; break;
    case 118: d.type = 'blazeOpen'; line.special = 0; d.speed = VDOORSPEED * 4; break;
  }
  d.topheight = findLowestCeilingSurrounding(sec) - 4;
}

// ---------------------------------------------------------------- plats (lifts)
const PLATWAIT = 3, PLATSPEED = 1;

function platThink(p) {
  const sec = p.sector;
  switch (p.status) {
    case 'up': {
      const res = movePlane(sec, p.speed, p.high, p.crush, 0, 1);
      if (res === PLANE_CRUSHED && !p.crush) { p.count = p.wait; p.status = 'down'; sectorSound(sec, 'pstart'); }
      else if (res === PLANE_PASTDEST) {
        p.count = p.wait; p.status = 'waiting'; sectorSound(sec, 'pstop');
        if (p.type === 'downWaitUpStay' || p.type === 'blazeDWUS' || p.type === 'raiseAndChange' || p.type === 'raiseToNearestAndChange') {
          removeActivePlat(p);
        }
      }
      break;
    }
    case 'down': {
      const res = movePlane(sec, p.speed, p.low, false, 0, -1);
      if (res === PLANE_PASTDEST) { p.count = p.wait; p.status = 'waiting'; sectorSound(sec, 'pstop'); }
      break;
    }
    case 'waiting':
      if (!--p.count) {
        p.status = sec.floorheight === p.low ? 'up' : 'down';
        sectorSound(sec, 'pstart');
      }
      break;
    case 'in_stasis': break;
  }
}

function removeActivePlat(p) { p.sector.specialdata = null; removeThinker(p); G.activeplats.delete(p); }

function doPlat(line, type, amount) {
  let rtn = false;
  if (type === 'perpetualRaise') activateInStasis(line.tag);
  for (const sec of sectorsWithTag(line.tag)) {
    if (sec.specialdata) continue;
    rtn = true;
    const p = { kind: 'plat', think: platThink, sector: sec, type, crush: false, tag: line.tag, speed: PLATSPEED, wait: 0,
      low: 0, high: 0, status: 'down', oldstatus: null, count: 0, removed: false };
    sec.specialdata = p;
    addThinker(p); G.activeplats.add(p);
    switch (type) {
      case 'raiseToNearestAndChange':
        p.speed = PLATSPEED / 2; p.high = findNextHighestFloor(sec, sec.floorheight); p.wait = 0; p.status = 'up';
        sectorSound(sec, 'stnmov'); break;
      case 'raiseAndChange':
        p.speed = PLATSPEED / 2; p.high = sec.floorheight + amount; p.wait = 0; p.status = 'up';
        sectorSound(sec, 'stnmov'); break;
      case 'downWaitUpStay': case 'blazeDWUS':
        p.speed = PLATSPEED * (type === 'blazeDWUS' ? 8 : 4);
        p.low = Math.min(findLowestFloorSurrounding(sec), sec.floorheight);
        p.high = sec.floorheight; p.wait = TICRATE * PLATWAIT; p.status = 'down';
        sectorSound(sec, 'pstart'); break;
      case 'perpetualRaise':
        p.speed = PLATSPEED; // Doom: PLATSPEED (slow) for perpetual lifts
        p.low = Math.min(findLowestFloorSurrounding(sec), sec.floorheight);
        p.high = Math.max(findHighestFloorSurrounding(sec), sec.floorheight);
        p.wait = TICRATE * PLATWAIT; p.status = (P_Random() & 1) ? 'down' : 'up';
        sectorSound(sec, 'pstart'); break;
    }
  }
  return rtn;
}

function activateInStasis(tag) {
  for (const p of G.activeplats) if (p.tag === tag && p.status === 'in_stasis') { p.status = p.oldstatus; }
}

function stopPlat(line) {
  for (const p of G.activeplats) if (p.status !== 'in_stasis' && p.tag === line.tag) { p.oldstatus = p.status; p.status = 'in_stasis'; }
}

// ---------------------------------------------------------------- floors
const FLOORSPEED = 1;
function floorThink(f) {
  const res = movePlane(f.sector, f.speed, f.dest, f.crush, 0, f.direction);
  if (!(G.leveltime & 7)) sectorSound(f.sector, 'stnmov');
  if (res === PLANE_PASTDEST) {
    f.sector.specialdata = null;
    sectorSound(f.sector, 'pstop');
    removeThinker(f);
  }
}

function doFloor(line, type) {
  let rtn = false;
  for (const sec of sectorsWithTag(line.tag)) {
    if (sec.specialdata) continue;
    rtn = true;
    const f = { kind: 'floor', think: floorThink, sector: sec, type, crush: false, direction: -1, speed: FLOORSPEED, dest: sec.floorheight, removed: false };
    sec.specialdata = f; addThinker(f);
    switch (type) {
      case 'lowerFloor': f.dest = findHighestFloorSurrounding(sec); break;
      case 'lowerFloorToLowest': f.dest = findLowestFloorSurrounding(sec); break;
      case 'turboLower':
        f.speed = FLOORSPEED * 4; f.dest = findHighestFloorSurrounding(sec);
        if (f.dest !== sec.floorheight) f.dest += 8; break;
      case 'raiseFloorCrush': case 'raiseFloor':
        f.direction = 1; f.crush = type === 'raiseFloorCrush';
        f.dest = findLowestCeilingSurrounding(sec);
        if (f.dest > sec.ceilingheight) f.dest = sec.ceilingheight;
        if (type === 'raiseFloorCrush') f.dest -= 8;
        break;
      case 'raiseFloorTurbo': f.direction = 1; f.speed = FLOORSPEED * 4; f.dest = findNextHighestFloor(sec, sec.floorheight); break;
      case 'raiseFloorToNearest': f.direction = 1; f.dest = findNextHighestFloor(sec, sec.floorheight); break;
      case 'raiseFloor24': case 'raiseFloor24AndChange': f.direction = 1; f.dest = sec.floorheight + 24; break;
      case 'raiseFloor512': f.direction = 1; f.dest = sec.floorheight + 512; break;
      case 'raiseToTexture': f.direction = 1; f.dest = sec.floorheight + 64; break;
      case 'lowerAndChange': f.dest = findLowestFloorSurrounding(sec); break;
    }
  }
  return rtn;
}

// ---------------------------------------------------------------- ceilings / crushers
const CEILSPEED = 1;
function ceilingThink(c) {
  const sec = c.sector;
  if (c.direction === 1) {
    const res = movePlane(sec, c.speed, c.topheight, false, 1, 1);
    if (!(G.leveltime & 7) && c.type !== 'silentCrushAndRaise') sectorSound(sec, 'stnmov');
    if (res === PLANE_PASTDEST) {
      if (c.type === 'raiseToHighest') { sec.specialdata = null; removeThinker(c); G.activeceilings.delete(c); }
      else if (c.type === 'silentCrushAndRaise' || c.type === 'fastCrushAndRaise' || c.type === 'crushAndRaise') {
        if (c.type === 'silentCrushAndRaise') sectorSound(sec, 'pstop');
        c.direction = -1;
      }
    }
  } else if (c.direction === -1) {
    const res = movePlane(sec, c.speed, c.bottomheight, c.crush, 1, -1);
    if (!(G.leveltime & 7) && c.type !== 'silentCrushAndRaise') sectorSound(sec, 'stnmov');
    if (res === PLANE_PASTDEST) {
      if (c.type === 'silentCrushAndRaise' || c.type === 'crushAndRaise') {
        if (c.type === 'silentCrushAndRaise') sectorSound(sec, 'pstop');
        c.speed = CEILSPEED; c.direction = 1;
      } else if (c.type === 'fastCrushAndRaise') c.direction = 1;
      else { sec.specialdata = null; removeThinker(c); G.activeceilings.delete(c); }
    } else if (res === PLANE_CRUSHED) {
      if (c.type === 'silentCrushAndRaise' || c.type === 'crushAndRaise' || c.type === 'lowerAndCrush') c.speed = CEILSPEED / 8;
    }
  }
}

function doCeiling(line, type) {
  let rtn = false;
  if (type === 'fastCrushAndRaise' || type === 'silentCrushAndRaise' || type === 'crushAndRaise') {
    for (const c of G.activeceilings) if (c.tag === line.tag && c.direction === 0) { c.direction = c.olddirection; rtn = true; }
  }
  for (const sec of sectorsWithTag(line.tag)) {
    if (sec.specialdata) continue;
    rtn = true;
    const c = { kind: 'ceiling', think: ceilingThink, sector: sec, type, crush: false, tag: line.tag, speed: CEILSPEED,
      direction: -1, olddirection: 0, topheight: sec.ceilingheight, bottomheight: sec.floorheight, removed: false };
    sec.specialdata = c; addThinker(c); G.activeceilings.add(c);
    switch (type) {
      case 'fastCrushAndRaise': c.crush = true; c.topheight = sec.ceilingheight; c.bottomheight = sec.floorheight + 8; c.speed = CEILSPEED * 2; break;
      case 'silentCrushAndRaise': case 'crushAndRaise': c.crush = true; c.topheight = sec.ceilingheight; c.bottomheight = sec.floorheight + 8; break;
      case 'lowerAndCrush': c.bottomheight = sec.floorheight + 8; break;
      case 'lowerToFloor': c.bottomheight = sec.floorheight; break;
      case 'raiseToHighest': c.topheight = findHighestCeilingSurrounding(sec); c.direction = 1; break;
    }
  }
  return rtn;
}

function ceilingCrushStop(line) {
  let rtn = false;
  for (const c of G.activeceilings) if (c.tag === line.tag && c.direction !== 0) { c.olddirection = c.direction; c.direction = 0; rtn = true; }
  return rtn;
}

// ---------------------------------------------------------------- teleport
function teleport(line, side, thing) {
  if (thing.flags & MF_MISSILE) return false;
  if (side === 1) return false;
  for (const sec of G.level.sectors) {
    if (sec.tag !== line.tag) continue;
    for (const m of G.mobjs) {
      if (m.type !== MT.TELEPORTMAN || m.sector !== sec) continue;
      const oldx = thing.x, oldy = thing.y, oldz = thing.z;
      let dx = m.x, dy = m.y;
      // a wide monster (demon, mancubus...) can land overlapping a wall when the destination sits close to one, and is
      // then stuck for good: step it to the nearest clear spot (players keep Doom's exact landing)
      if (!thing.player && thing.info.kind === 'monster' && G.fitSpot) {
        const f = G.fitSpot(m.x, m.y, 96, null, thing.radius, thing.height, thing.info);
        if (f) { dx = f.x; dy = f.y; }
      }
      if (!teleportMove(thing, dx, dy)) return false;
      thing.z = thing.floorz;
      if (thing.player) thing.player.viewz = thing.z + thing.player.viewheight;
      const fog = spawnMobj(oldx, oldy, oldz, MT.TFOG);
      startSound(fog, 'telept');
      const an = m.angle;
      const fog2 = spawnMobj(m.x + 20 * Math.cos(an * DEG), m.y + 20 * Math.sin(an * DEG), thing.z, MT.TFOG);
      startSound(fog2, 'telept');
      if (thing.player) { thing.reactiontime = 18; G.onTeleport(thing.player, an); }
      thing.angle = an;
      thing.momx = thing.momy = thing.momz = 0;
      thing.teleported = true;
      return true;
    }
  }
  return false;
}

// ---------------------------------------------------------------- line activation
function crossSpecialLine(line, side, thing) {
  const sp = line.special;
  // monsters only use teleporters and the few walkover lines Doom lets them (missiles never trigger any)
  if (!thing.player && (!(thing.info && thing.info.kind === 'monster') || ![39, 97, 4, 10, 88].includes(sp))) return;
  const once = () => { line.special = 0; };
  switch (sp) {
    // doors
    case 2: doDoor(line, 'open'); once(); break;
    case 3: doDoor(line, 'close'); once(); break;
    case 4: doDoor(line, 'normal'); once(); break;
    case 16: doDoor(line, 'close30ThenOpen'); once(); break;
    case 75: doDoor(line, 'close'); break;
    case 76: doDoor(line, 'close30ThenOpen'); break;
    case 86: doDoor(line, 'open'); break;
    case 90: doDoor(line, 'normal'); break;
    case 105: doDoor(line, 'blazeRaise'); break;
    case 106: doDoor(line, 'blazeOpen'); break;
    case 107: doDoor(line, 'blazeClose'); break;
    case 108: doDoor(line, 'blazeRaise'); once(); break;
    case 109: doDoor(line, 'blazeOpen'); once(); break;
    case 110: doDoor(line, 'blazeClose'); once(); break;
    // lifts
    case 10: doPlat(line, 'downWaitUpStay', 0); once(); break;
    case 88: doPlat(line, 'downWaitUpStay', 0); break;
    case 120: doPlat(line, 'blazeDWUS', 0); break;
    case 121: doPlat(line, 'blazeDWUS', 0); once(); break;
    case 53: doPlat(line, 'perpetualRaise', 0); once(); break;
    case 87: doPlat(line, 'perpetualRaise', 0); break;
    case 54: stopPlat(line); once(); break;
    case 89: stopPlat(line); break;
    case 22: doPlat(line, 'raiseToNearestAndChange', 0); once(); break;
    case 95: doPlat(line, 'raiseToNearestAndChange', 0); break;
    // floors
    case 5: doFloor(line, 'raiseFloor'); once(); break;
    case 19: doFloor(line, 'lowerFloor'); once(); break;
    case 30: doFloor(line, 'raiseToTexture'); once(); break;
    case 36: doFloor(line, 'turboLower'); once(); break;
    case 37: doFloor(line, 'lowerAndChange'); once(); break;
    case 38: doFloor(line, 'lowerFloorToLowest'); once(); break;
    case 56: doFloor(line, 'raiseFloorCrush'); once(); break;
    case 58: doFloor(line, 'raiseFloor24'); once(); break;
    case 59: doFloor(line, 'raiseFloor24AndChange'); once(); break;
    case 119: doFloor(line, 'raiseFloorToNearest'); once(); break;
    case 130: doFloor(line, 'raiseFloorTurbo'); once(); break;
    case 82: doFloor(line, 'lowerFloorToLowest'); break;
    case 83: doFloor(line, 'lowerFloor'); break;
    case 84: doFloor(line, 'lowerAndChange'); break;
    case 91: doFloor(line, 'raiseFloor'); break;
    case 92: doFloor(line, 'raiseFloor24'); break;
    case 93: doFloor(line, 'raiseFloor24AndChange'); break;
    case 94: doFloor(line, 'raiseFloorCrush'); break;
    case 96: doFloor(line, 'raiseToTexture'); break;
    case 98: doFloor(line, 'turboLower'); break;
    case 128: doFloor(line, 'raiseFloorToNearest'); break;
    case 129: doFloor(line, 'raiseFloorTurbo'); break;
    // ceilings
    case 6: doCeiling(line, 'fastCrushAndRaise'); once(); break;
    case 25: doCeiling(line, 'crushAndRaise'); once(); break;
    case 40: doCeiling(line, 'raiseToHighest'); doFloor(line, 'lowerFloorToLowest'); once(); break;
    case 44: doCeiling(line, 'lowerAndCrush'); once(); break;
    case 57: ceilingCrushStop(line); once(); break;
    case 141: doCeiling(line, 'silentCrushAndRaise'); once(); break;
    case 72: doCeiling(line, 'lowerAndCrush'); break;
    case 73: doCeiling(line, 'crushAndRaise'); break;
    case 74: ceilingCrushStop(line); break;
    case 77: doCeiling(line, 'fastCrushAndRaise'); break;
    // teleports
    case 39: if (teleport(line, side, thing)) once(); break;
    case 97: teleport(line, side, thing); break;
    // exits
    case 52: case 124: G.onExitLine(thing.player, line); break;
  }
}

function shootSpecialLine(thing, line) {
  if (!thing || !thing.player) return;
  switch (line.special) {
    case 24: doFloor(line, 'raiseFloor'); changeSwitch(line, false); break;
    case 46: doDoor(line, 'open'); changeSwitch(line, true); break;
    case 47: doPlat(line, 'raiseToNearestAndChange', 0); changeSwitch(line, false); break;
  }
}

function changeSwitch(line, useAgain) {
  const exit = line.special === 11 || line.special === 51;
  if (!useAgain) line.special = 0;
  const mx = (line.x1 + line.x2) / 2, my = (line.y1 + line.y2) / 2;
  const sec = line.frontsector;
  startSound({ x: mx, y: my, z: (sec.floorheight + sec.ceilingheight) / 2 }, exit ? 'swtchx' : 'swtchn');
  if (useAgain) line.switchUntil = G.leveltime + TICRATE;
}

function useSpecialLine(thing, line, side) {
  if (side) return false;
  const sp = line.special;
  switch (sp) {
    // manual doors
    case 1: case 26: case 27: case 28: case 31: case 32: case 33: case 34: case 117: case 118:
      verticalDoor(line, thing); return true;
    // switches, once
    case 7: case 9: changeSwitch(line, false); break;
    case 11: case 51: if (G.onExitLine(thing.player, line)) changeSwitch(line, false); break;
    case 14: if (doPlat(line, 'raiseAndChange', 32)) changeSwitch(line, false); break;
    case 15: if (doPlat(line, 'raiseAndChange', 24)) changeSwitch(line, false); break;
    case 18: if (doFloor(line, 'raiseFloorToNearest')) changeSwitch(line, false); break;
    case 20: if (doPlat(line, 'raiseToNearestAndChange', 0)) changeSwitch(line, false); break;
    case 21: if (doPlat(line, 'downWaitUpStay', 0)) changeSwitch(line, false); break;
    case 23: if (doFloor(line, 'lowerFloorToLowest')) changeSwitch(line, false); break;
    case 29: if (doDoor(line, 'normal')) changeSwitch(line, false); break;
    case 41: if (doCeiling(line, 'lowerToFloor')) changeSwitch(line, false); break;
    case 71: if (doFloor(line, 'turboLower')) changeSwitch(line, false); break;
    case 49: if (doCeiling(line, 'crushAndRaise')) changeSwitch(line, false); break;
    case 50: if (doDoor(line, 'close')) changeSwitch(line, false); break;
    case 55: if (doFloor(line, 'raiseFloorCrush')) changeSwitch(line, false); break;
    case 101: if (doFloor(line, 'raiseFloor')) changeSwitch(line, false); break;
    case 102: if (doFloor(line, 'lowerFloor')) changeSwitch(line, false); break;
    case 103: if (doDoor(line, 'open')) changeSwitch(line, false); break;
    case 111: if (doDoor(line, 'blazeRaise')) changeSwitch(line, false); break;
    case 112: if (doDoor(line, 'blazeOpen')) changeSwitch(line, false); break;
    case 113: if (doDoor(line, 'blazeClose')) changeSwitch(line, false); break;
    case 122: if (doPlat(line, 'blazeDWUS', 0)) changeSwitch(line, false); break;
    case 131: if (doFloor(line, 'raiseFloorTurbo')) changeSwitch(line, false); break;
    case 140: if (doFloor(line, 'raiseFloor512')) changeSwitch(line, false); break;
    // switches, repeatable
    case 42: if (doDoor(line, 'close')) changeSwitch(line, true); break;
    case 43: if (doCeiling(line, 'lowerToFloor')) changeSwitch(line, true); break;
    case 45: if (doFloor(line, 'lowerFloor')) changeSwitch(line, true); break;
    case 60: if (doFloor(line, 'lowerFloorToLowest')) changeSwitch(line, true); break;
    case 61: if (doDoor(line, 'open')) changeSwitch(line, true); break;
    case 62: if (doPlat(line, 'downWaitUpStay', 1)) changeSwitch(line, true); break;
    case 63: if (doDoor(line, 'normal')) changeSwitch(line, true); break;
    case 64: if (doFloor(line, 'raiseFloor')) changeSwitch(line, true); break;
    case 65: if (doFloor(line, 'raiseFloorCrush')) changeSwitch(line, true); break;
    case 66: if (doPlat(line, 'raiseAndChange', 24)) changeSwitch(line, true); break;
    case 67: if (doPlat(line, 'raiseAndChange', 32)) changeSwitch(line, true); break;
    case 68: if (doPlat(line, 'raiseToNearestAndChange', 0)) changeSwitch(line, true); break;
    case 69: if (doFloor(line, 'raiseFloorToNearest')) changeSwitch(line, true); break;
    case 70: if (doFloor(line, 'turboLower')) changeSwitch(line, true); break;
    case 114: if (doDoor(line, 'blazeRaise')) changeSwitch(line, true); break;
    case 115: if (doDoor(line, 'blazeOpen')) changeSwitch(line, true); break;
    case 116: if (doDoor(line, 'blazeClose')) changeSwitch(line, true); break;
    case 123: if (doPlat(line, 'blazeDWUS', 0)) changeSwitch(line, true); break;
    case 132: if (doFloor(line, 'raiseFloorTurbo')) changeSwitch(line, true); break;
    default: return false;
  }
  return true;
}

// ---------------------------------------------------------------- sector specials
function playerInSpecialSector(p) {
  const mo = p.mo, sec = mo.sector;
  if (mo.z !== sec.floorheight) return;
  switch (sec.special) {
    case 5: if (!p.powers[PW_IRONFEET] && !(G.leveltime & 0x1f)) { G.damageCtx = 'slime'; damageMobj(mo, null, null, 10); G.damageCtx = null; } break;
    case 7: if (!p.powers[PW_IRONFEET] && !(G.leveltime & 0x1f)) { G.damageCtx = 'slime'; damageMobj(mo, null, null, 5); G.damageCtx = null; } break;
    case 16: case 4:
      if ((!p.powers[PW_IRONFEET] || P_Random() < 5) && !(G.leveltime & 0x1f)) { G.damageCtx = 'slime'; damageMobj(mo, null, null, 20); G.damageCtx = null; } break;
    case 9: sec.special = 0; break;
    case 11: break;
  }
}

// sector light effects (used by the renderer to tint things standing in them)
function sectorLight(sec) {
  return sec.lightNow !== undefined ? sec.lightNow : sec.lightlevel;
}

function runThinkers() {
  const list = G.thinkers;
  for (let i = 0; i < list.length; i++) {
    const t = list[i];
    if (!t.removed) t.think(t);
  }
  if (list.some((t) => t.removed)) G.thinkers = list.filter((t) => !t.removed);
}
