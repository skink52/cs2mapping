// ===================================================================================
// Part 2: movement clipping, path traversal, hitscan, sight, radius damage (p_map / p_maputl)
// G is the arena currently being simulated.
// ===================================================================================

let G = null;

function blockX(x) { return Math.floor((x - G.level.bmaporgx) / BLOCKSIZE); }
function blockY(y) { return Math.floor((y - G.level.bmaporgy) / BLOCKSIZE); }

function setThingPosition(mo) {
  const sec = G.level.sectorAt(mo.x, mo.y);
  mo.sector = sec;
  if (!(mo.flags & MF_NOBLOCKMAP)) {
    const bx = blockX(mo.x), by = blockY(mo.y);
    const L = G.level;
    if (bx >= 0 && by >= 0 && bx < L.bmapwidth && by < L.bmapheight) {
      const cell = G.blockThings[by * L.bmapwidth + bx];
      mo.bcell = cell; mo.bindex = cell.length; cell.push(mo);
    } else mo.bcell = null;
  }
}

function unsetThingPosition(mo) {
  if (!(mo.flags & MF_NOBLOCKMAP) && mo.bcell) {
    const cell = mo.bcell, i = mo.bindex;
    const last = cell.pop();
    if (last !== mo) { cell[i] = last; last.bindex = i; }
    mo.bcell = null;
  }
}

function blockLinesIterator(bx, by, fn) {
  const L = G.level;
  if (bx < 0 || by < 0 || bx >= L.bmapwidth || by >= L.bmapheight) return true;
  const list = L.blockLines[by * L.bmapwidth + bx];
  for (let i = 0; i < list.length; i++) {
    const l = list[i];
    if (l.validcount === G.validcount) continue;
    l.validcount = G.validcount;
    if (!fn(l)) return false;
  }
  return true;
}

function blockThingsIterator(bx, by, fn) {
  const L = G.level;
  if (bx < 0 || by < 0 || bx >= L.bmapwidth || by >= L.bmapheight) return true;
  const list = G.blockThings[by * L.bmapwidth + bx];
  // copy-safe: callbacks may move/remove things
  for (let i = list.length - 1; i >= 0; i--) {
    const mo = list[i];
    if (!mo) continue;
    if (!fn(mo)) return false;
  }
  return true;
}

// ---------------------------------------------------------------- position checking
const TM = {
  thing: null, flags: 0, x: 0, y: 0, bbox: [0, 0, 0, 0], floorz: 0, ceilingz: 0, dropoffz: 0,
  ceilingline: null, spechit: [], blockline: null, hitThing: null,
};

function sameTeamNoFF(a, b) {
  if (!a || !b || a === b) return false;
  const pa = a.player, pb = b.player;
  if (!pa || !pb) return false;
  if (G.coop) return !G.friendlyFire;   // co-op: everyone is on the same side
  return G.teamsActive && !G.friendlyFire && pa.team >= 0 && pa.team === pb.team;
}

function PIT_CheckLine(ld) {
  const b = TM.bbox;
  if (b[3] <= ld.bbox[2] || b[2] >= ld.bbox[3] || b[0] <= ld.bbox[1] || b[1] >= ld.bbox[0]) return true;
  if (boxOnLineSide(b, ld) !== -1) return true;
  if (!ld.backsector) { TM.blockline = ld; return false; }
  if (!(TM.thing.flags & MF_MISSILE)) {
    if (ld.flags & ML_BLOCKING) { TM.blockline = ld; return false; }
    if (!TM.thing.player && (ld.flags & ML_BLOCKMONSTERS) && TM.thing.info && TM.thing.info.kind === 'monster') { TM.blockline = ld; return false; }
  }
  const op = lineOpening(ld);
  if (op.top < TM.ceilingz) { TM.ceilingz = op.top; TM.ceilingline = ld; }
  if (op.bottom > TM.floorz) TM.floorz = op.bottom;
  if (op.lowfloor < TM.dropoffz) TM.dropoffz = op.lowfloor;
  if (ld.special) TM.spechit.push(ld);
  return true;
}

function PIT_CheckThing(thing) {
  if (!(thing.flags & (MF_SOLID | MF_SPECIAL | MF_SHOOTABLE))) return true;
  const tt = TM.thing;
  const blockdist = thing.radius + tt.radius;
  if (Math.abs(thing.x - TM.x) >= blockdist || Math.abs(thing.y - TM.y) >= blockdist) return true;
  if (thing === tt) return true;
  // a charging lost soul slams into whatever it hits
  if (tt.flags & MF_SKULLFLY) {
    const damage = ((P_Random() % 8) + 1) * tt.info.damage;
    damageMobj(thing, tt, tt, damage);
    tt.flags &= ~MF_SKULLFLY;
    tt.momx = tt.momy = tt.momz = 0;
    setMobjState(tt, tt.info.spawnstate);
    return false;
  }
  if (tt.flags & MF_MISSILE) {
    if (tt.z > thing.z + thing.height) return true;
    if (tt.z + tt.height < thing.z) return true;
    if (tt.target === thing) return true;
    if (sameTeamNoFF(tt.target, thing)) return true;
    // monsters of one kind don't hurt each other with their own shots (the shot still bursts)
    const st = tt.target;
    if (st && !thing.player && !st.player && (st.type === thing.type ||
        (st.type === MT.KNIGHT && thing.type === MT.BARON) || (st.type === MT.BARON && thing.type === MT.KNIGHT))) return false;
    if (!(thing.flags & MF_SHOOTABLE)) return !(thing.flags & MF_SOLID);
    const damage = ((P_Random() % 8) + 1) * tt.info.damage;
    G.damageCtx = 'direct';
    damageMobj(thing, tt, tt.target, damage);
    G.damageCtx = null;
    TM.hitThing = thing;
    return false;
  }
  if (thing.flags & MF_SPECIAL) {
    const solid = thing.flags & MF_SOLID;
    if (TM.flags & MF_PICKUP) touchSpecialThing(thing, tt);
    return !solid;
  }
  if (G.ghostPlayers && thing.player && tt.player) return true;
  return !(thing.flags & MF_SOLID);
}

function checkPosition(thing, x, y) {
  TM.thing = thing; TM.flags = thing.flags; TM.x = x; TM.y = y;
  TM.bbox[0] = y + thing.radius; TM.bbox[1] = y - thing.radius;
  TM.bbox[3] = x + thing.radius; TM.bbox[2] = x - thing.radius;
  const sec = G.level.sectorAt(x, y);
  TM.ceilingline = null; TM.blockline = null; TM.hitThing = null;
  TM.floorz = TM.dropoffz = sec.floorheight;
  TM.ceilingz = sec.ceilingheight;
  TM.sector = sec;
  G.validcount++;
  TM.spechit.length = 0;
  if (TM.flags & MF_NOCLIP) return true;
  // blockX / blockY written out
  const L = G.level, ox = L.bmaporgx, oy = L.bmaporgy;
  let xl = Math.floor((TM.bbox[2] - MAXRADIUS - ox) / BLOCKSIZE), xh = Math.floor((TM.bbox[3] + MAXRADIUS - ox) / BLOCKSIZE);
  let yl = Math.floor((TM.bbox[1] - MAXRADIUS - oy) / BLOCKSIZE), yh = Math.floor((TM.bbox[0] + MAXRADIUS - oy) / BLOCKSIZE);
  for (let bx = xl; bx <= xh; bx++)
    for (let by = yl; by <= yh; by++)
      if (!blockThingsIterator(bx, by, PIT_CheckThing)) return false;
  xl = Math.floor((TM.bbox[2] - ox) / BLOCKSIZE); xh = Math.floor((TM.bbox[3] - ox) / BLOCKSIZE);
  yl = Math.floor((TM.bbox[1] - oy) / BLOCKSIZE); yh = Math.floor((TM.bbox[0] - oy) / BLOCKSIZE);
  for (let bx = xl; bx <= xh; bx++)
    for (let by = yl; by <= yh; by++)
      if (!blockLinesIterator(bx, by, PIT_CheckLine)) return false;
  return true;
}

let floatok = false;
function tryMove(thing, x, y) {
  floatok = false;
  if (!checkPosition(thing, x, y)) return false;
  if (!(thing.flags & MF_NOCLIP)) {
    if (TM.ceilingz - TM.floorz < thing.height) return false;
    floatok = true;
    if (TM.ceilingz - thing.z < thing.height) return false;
    if (TM.floorz - thing.z > MAXSTEP) return false;
    if (!(thing.flags & (MF_DROPOFF | MF_FLOAT)) && TM.floorz - TM.dropoffz > MAXSTEP) return false;
  }
  unsetThingPosition(thing);
  const oldx = thing.x, oldy = thing.y;
  thing.floorz = TM.floorz; thing.ceilingz = TM.ceilingz;
  thing.x = x; thing.y = y;
  setThingPosition(thing);
  if (!(thing.flags & MF_NOCLIP)) {
    const hits = TM.spechit.length ? TM.spechit.slice() : TM.spechit;
    for (let i = hits.length - 1; i >= 0; i--) {
      const ld = hits[i];
      const side = pointOnLineSide(thing.x, thing.y, ld);
      const oldside = pointOnLineSide(oldx, oldy, ld);
      if (side !== oldside && ld.special) crossSpecialLine(ld, oldside, thing);
    }
  }
  return true;
}

function thingHeightClip(thing) {
  const onfloor = thing.z === thing.floorz;
  checkPosition(thing, thing.x, thing.y);
  thing.floorz = TM.floorz; thing.ceilingz = TM.ceilingz;
  if (onfloor) thing.z = thing.floorz;
  else if (thing.z + thing.height > thing.ceilingz) thing.z = thing.ceilingz - thing.height;
  return thing.ceilingz - thing.floorz >= thing.height;
}

let nofit = false, crushchange = false;
function PIT_ChangeSector(thing) {
  if (thingHeightClip(thing)) return true;
  if (thing.health <= 0 && thing.info.kind === 'player') {
    setMobjState(thing, SN('GIBS'));
    thing.flags &= ~MF_SOLID; thing.height = 0; thing.radius = 0;
    return true;
  }
  if (thing.flags & MF_DROPPED) { removeMobj(thing); return true; }
  if (!(thing.flags & MF_SHOOTABLE)) return true;
  nofit = true;
  if (crushchange && !(G.leveltime & 3)) {
    G.damageCtx = 'crush';
    damageMobj(thing, null, null, 10);
    G.damageCtx = null;
    const mo = spawnMobj(thing.x, thing.y, thing.z + thing.height / 2, MT.BLOOD);
    mo.momx = (P_Random() - P_Random()) / 16; mo.momy = (P_Random() - P_Random()) / 16;
  }
  return true;
}

function changeSector(sector, crunch) {
  nofit = false; crushchange = crunch;
  const bb = sector.blockbox;
  // collect first: the callback can move things between cells
  const list = [];
  for (let x = bb[2]; x <= bb[3]; x++)
    for (let y = bb[1]; y <= bb[0]; y++) {
      const cell = G.blockThings[y * G.level.bmapwidth + x];
      for (let i = 0; i < cell.length; i++) list.push(cell[i]);
    }
  for (const th of list) if (!th.removed) PIT_ChangeSector(th);
  return nofit;
}

// ---------------------------------------------------------------- path traversal
const trace = { x: 0, y: 0, dx: 0, dy: 0 };
const PT_ADDLINES = 1, PT_ADDTHINGS = 2;
// intercepts collected by the current pathTraverse (collecting never calls back into the playsim, so one list is safe;
// the traverse keeps its own reference while it walks them, as callbacks can start another traverse)
let ptList = null, ptLong = false, ptPositive = false;
// the trace's bounding box, 1 unit larger all round. A line or thing that can only cross the trace's infinite
// extension outside this box would get an intercept beyond the trace's ends (frac < 0 or > 1), which the walk
// never reaches, so it is skipped before any maths. (Not for short traces' line test, which works differently.)
let ptMinX = 0, ptMaxX = 0, ptMinY = 0, ptMaxY = 0;

function ptAddLine(ld) {
  let s1, s2;
  if (ptLong) {
    const bb = ld.bbox;
    if (bb[2] > ptMaxX || bb[3] < ptMinX || bb[1] > ptMaxY || bb[0] < ptMinY) return true;
    s1 = pointOnDivlineSide(ld.x1, ld.y1, trace);
    s2 = pointOnDivlineSide(ld.x2, ld.y2, trace);
  } else {
    s1 = pointOnLineSide(trace.x, trace.y, ld);
    s2 = pointOnLineSide(trace.x + trace.dx, trace.y + trace.dy, ld);
  }
  if (s1 === s2) return true;
  // interceptVector(trace, line) written out (same arithmetic, no temporary object)
  const den = ld.dy * trace.dx - ld.dx * trace.dy;
  const frac = den === 0 ? 0 : ((ld.x1 - trace.x) * ld.dy + (trace.y - ld.y1) * ld.dx) / den;
  if (frac < 0) return true;
  ptList.push({ frac, line: ld, thing: null });
  return true;
}

function ptAddThing(th) {
  if (th.x - th.radius > ptMaxX || th.x + th.radius < ptMinX || th.y - th.radius > ptMaxY || th.y + th.radius < ptMinY) return true;
  let x1_, y1_, x2_, y2_;
  if (ptPositive) {
    x1_ = th.x - th.radius; y1_ = th.y + th.radius; x2_ = th.x + th.radius; y2_ = th.y - th.radius;
  } else {
    x1_ = th.x - th.radius; y1_ = th.y - th.radius; x2_ = th.x + th.radius; y2_ = th.y + th.radius;
  }
  const s1 = pointOnDivlineSide(x1_, y1_, trace), s2 = pointOnDivlineSide(x2_, y2_, trace);
  if (s1 === s2) return true;
  const vdx = x2_ - x1_, vdy = y2_ - y1_;
  const den = vdy * trace.dx - vdx * trace.dy;
  const frac = den === 0 ? 0 : ((x1_ - trace.x) * vdy + (trace.y - y1_) * vdx) / den;
  if (frac < 0) return true;
  ptList.push({ frac, line: null, thing: th });
  return true;
}

function byFrac(a, b) { return a.frac - b.frac; }

function pathTraverse(x1, y1, x2, y2, flags, trav) {
  G.validcount++;
  const L = G.level;
  trace.x = x1; trace.y = y1; trace.dx = x2 - x1; trace.dy = y2 - y1;
  const intercepts = [];
  ptList = intercepts;
  ptLong = Math.abs(trace.dx) > 16 || Math.abs(trace.dy) > 16;
  ptPositive = (trace.dx > 0) === (trace.dy > 0);
  ptMinX = Math.min(x1, x2) - 1; ptMaxX = Math.max(x1, x2) + 1;
  ptMinY = Math.min(y1, y2) - 1; ptMaxY = Math.max(y1, y2) + 1;
  const addLine = ptAddLine, addThing = ptAddThing;
  // walk every blockmap cell the segment touches (supercover)
  let bx = blockX(x1), by = blockY(y1);
  const bx2 = blockX(x2), by2 = blockY(y2);
  const stepX = Math.sign(x2 - x1), stepY = Math.sign(y2 - y1);
  const cellX0 = L.bmaporgx, cellY0 = L.bmaporgy;
  const tDeltaX = stepX ? BLOCKSIZE / Math.abs(x2 - x1) : Infinity;
  const tDeltaY = stepY ? BLOCKSIZE / Math.abs(y2 - y1) : Infinity;
  let tMaxX = stepX > 0 ? ((cellX0 + (bx + 1) * BLOCKSIZE) - x1) / (x2 - x1) : stepX < 0 ? ((cellX0 + bx * BLOCKSIZE) - x1) / (x2 - x1) : Infinity;
  let tMaxY = stepY > 0 ? ((cellY0 + (by + 1) * BLOCKSIZE) - y1) / (y2 - y1) : stepY < 0 ? ((cellY0 + by * BLOCKSIZE) - y1) / (y2 - y1) : Infinity;
  for (let guard = 0; guard < 1024; guard++) {
    if (flags & PT_ADDLINES) blockLinesIterator(bx, by, addLine);
    if (flags & PT_ADDTHINGS) {
      if (bx >= 0 && by >= 0 && bx < L.bmapwidth && by < L.bmapheight) {
        const cell = G.blockThings[by * L.bmapwidth + bx];
        for (let i = 0; i < cell.length; i++) {
          const th = cell[i];
          if (th.validcount === G.validcount) continue;
          th.validcount = G.validcount;
          addThing(th);
        }
      }
    }
    if (bx === bx2 && by === by2) break;
    if (tMaxX < tMaxY) { tMaxX += tDeltaX; bx += stepX; }
    else if (tMaxY < tMaxX) { tMaxY += tDeltaY; by += stepY; }
    else {
      // exact corner: visit both neighbours
      if (flags & PT_ADDLINES) { blockLinesIterator(bx + stepX, by, addLine); blockLinesIterator(bx, by + stepY, addLine); }
      tMaxX += tDeltaX; bx += stepX; tMaxY += tDeltaY; by += stepY;
    }
    if (Math.min(tMaxX, tMaxY) > 1.0001 && !(bx === bx2 && by === by2)) {
      if (flags & PT_ADDLINES) blockLinesIterator(bx, by, addLine);
      if (flags & PT_ADDTHINGS && bx >= 0 && by >= 0 && bx < L.bmapwidth && by < L.bmapheight) {
        const cell = G.blockThings[by * L.bmapwidth + bx];
        for (let i = 0; i < cell.length; i++) { const th = cell[i]; if (th.validcount !== G.validcount) { th.validcount = G.validcount; addThing(th); } }
      }
      break;
    }
  }
  ptList = null;
  if (intercepts.length > 1) intercepts.sort(byFrac);
  for (let i = 0; i < intercepts.length; i++) {
    const ic = intercepts[i];
    if (ic.frac > 1) break;
    if (!trav(ic)) return false;
  }
  return true;
}

// ---------------------------------------------------------------- slide move
function slideMove(mo) {
  let hitcount = 0;
  for (;;) {
    if (++hitcount === 3) { stairstep(mo); return; }
    let leadx, leady, trailx, traily;
    if (mo.momx > 0) { leadx = mo.x + mo.radius; trailx = mo.x - mo.radius; } else { leadx = mo.x - mo.radius; trailx = mo.x + mo.radius; }
    if (mo.momy > 0) { leady = mo.y + mo.radius; traily = mo.y - mo.radius; } else { leady = mo.y - mo.radius; traily = mo.y + mo.radius; }
    let bestfrac = 1.0001, bestline = null;
    const ptrSlide = (ic) => {
      const li = ic.line;
      if (!li) return true;
      if (!(li.flags & ML_TWOSIDED)) {
        if (pointOnLineSide(mo.x, mo.y, li)) return true; // don't hit the back side
      } else {
        const op = lineOpening(li);
        if (!(op.range < mo.height || op.top - mo.z < mo.height || op.bottom - mo.z > MAXSTEP)) return true;
      }
      if (ic.frac < bestfrac) { bestfrac = ic.frac; bestline = li; }
      return false;
    };
    pathTraverse(leadx, leady, leadx + mo.momx, leady + mo.momy, PT_ADDLINES, ptrSlide);
    pathTraverse(trailx, leady, trailx + mo.momx, leady + mo.momy, PT_ADDLINES, ptrSlide);
    pathTraverse(leadx, traily, leadx + mo.momx, traily + mo.momy, PT_ADDLINES, ptrSlide);
    if (bestfrac === 1.0001) { stairstep(mo); return; }
    bestfrac -= 1 / 32;
    if (bestfrac > 0) {
      const newx = mo.momx * bestfrac, newy = mo.momy * bestfrac;
      if (!tryMove(mo, mo.x + newx, mo.y + newy)) { stairstep(mo); return; }
    }
    bestfrac = 1 - (bestfrac + 1 / 32);
    if (bestfrac > 1) bestfrac = 1;
    if (bestfrac <= 0) return;
    let tmx = mo.momx * bestfrac, tmy = mo.momy * bestfrac;
    // hitSlideLine
    const ld = bestline;
    if (ld.slopetype === 0) tmy = 0;
    else if (ld.slopetype === 1) tmx = 0;
    else {
      const side = pointOnLineSide(mo.x, mo.y, ld);
      let lineangle = pointToAngle(0, 0, ld.dx, ld.dy);
      if (side === 1) lineangle += 180;
      const moveangle = pointToAngle(0, 0, tmx, tmy);
      let deltaangle = normAngle(moveangle - lineangle);
      if (deltaangle > 180) deltaangle += 180;
      const movelen = approxDistance(tmx, tmy);
      const newlen = movelen * Math.cos(deltaangle * DEG);
      tmx = newlen * Math.cos(lineangle * DEG); tmy = newlen * Math.sin(lineangle * DEG);
    }
    mo.momx = tmx; mo.momy = tmy;
    if (!tryMove(mo, mo.x + tmx, mo.y + tmy)) continue;
    return;
  }
  function stairstep(m) {
    if (!tryMove(m, m.x, m.y + m.momy)) tryMove(m, m.x + m.momx, m.y);
  }
}

// ---------------------------------------------------------------- aiming / shooting
const AIM = { shootthing: null, shootz: 0, topslope: 0, bottomslope: 0, attackrange: 0, aimslope: 0, linetarget: null, damage: 0 };

function PTR_AimTraverse(ic) {
  if (ic.line) {
    const li = ic.line;
    if (!(li.flags & ML_TWOSIDED)) return false;
    const op = lineOpening(li);
    if (op.bottom >= op.top) return false;
    const dist = AIM.attackrange * ic.frac;
    if (dist <= 0) return true;
    if (li.frontsector.floorheight !== li.backsector.floorheight) {
      const slope = (op.bottom - AIM.shootz) / dist;
      if (slope > AIM.bottomslope) AIM.bottomslope = slope;
    }
    if (li.frontsector.ceilingheight !== li.backsector.ceilingheight) {
      const slope = (op.top - AIM.shootz) / dist;
      if (slope < AIM.topslope) AIM.topslope = slope;
    }
    return AIM.topslope > AIM.bottomslope;
  }
  const th = ic.thing;
  if (th === AIM.shootthing) return true;
  if (!(th.flags & MF_SHOOTABLE)) return true;
  if (sameTeamNoFF(AIM.shootthing, th)) return true;
  if (th.player && th.player.spectating) return true;
  const dist = AIM.attackrange * ic.frac;
  if (dist <= 0) return true;
  let thingtopslope = (th.z + th.height - AIM.shootz) / dist;
  if (thingtopslope < AIM.bottomslope) return true;
  let thingbottomslope = (th.z - AIM.shootz) / dist;
  if (thingbottomslope > AIM.topslope) return true;
  if (thingtopslope > AIM.topslope) thingtopslope = AIM.topslope;
  if (thingbottomslope < AIM.bottomslope) thingbottomslope = AIM.bottomslope;
  AIM.aimslope = (thingtopslope + thingbottomslope) / 2;
  AIM.linetarget = th;
  return false;
}

function aimLineAttack(t1, angle, distance) {
  const x2 = t1.x + distance * Math.cos(angle * DEG), y2 = t1.y + distance * Math.sin(angle * DEG);
  AIM.shootthing = t1;
  AIM.shootz = t1.z + t1.height / 2 + 8;
  AIM.topslope = 100 / 160; AIM.bottomslope = -100 / 160;
  AIM.attackrange = distance; AIM.linetarget = null;
  pathTraverse(t1.x, t1.y, x2, y2, PT_ADDLINES | PT_ADDTHINGS, PTR_AimTraverse);
  return AIM.linetarget ? AIM.aimslope : 0;
}

function PTR_ShootTraverse(ic) {
  let frac, x, y, z;
  if (ic.line) {
    const li = ic.line;
    if (li.special) shootSpecialLine(AIM.shootthing, li);
    let hit = false;
    if (!(li.flags & ML_TWOSIDED)) hit = true;
    else {
      const op = lineOpening(li);
      const dist = AIM.attackrange * ic.frac;
      if (li.frontsector.floorheight !== li.backsector.floorheight) {
        if ((op.bottom - AIM.shootz) / dist > AIM.aimslope) hit = true;
      }
      if (!hit && li.frontsector.ceilingheight !== li.backsector.ceilingheight) {
        if ((op.top - AIM.shootz) / dist < AIM.aimslope) hit = true;
      }
      if (!hit) return true;
    }
    frac = ic.frac - 4 / AIM.attackrange;
    x = trace.x + trace.dx * frac; y = trace.y + trace.dy * frac;
    z = AIM.shootz + AIM.aimslope * (frac * AIM.attackrange);
    if (li.frontsector.sky) {
      if (z > li.frontsector.ceilingheight) return false;
      if (li.backsector && li.backsector.sky) return false;
    }
    spawnPuff(x, y, z);
    return false;
  }
  const th = ic.thing;
  if (th === AIM.shootthing) return true;
  if (!(th.flags & MF_SHOOTABLE)) return true;
  if (sameTeamNoFF(AIM.shootthing, th)) return true;
  if (th.player && th.player.spectating) return true;
  const dist = AIM.attackrange * ic.frac;
  if (dist <= 0) return true;
  if ((th.z + th.height - AIM.shootz) / dist < AIM.aimslope) return true;
  if ((th.z - AIM.shootz) / dist > AIM.aimslope) return true;
  frac = ic.frac - 10 / AIM.attackrange;
  x = trace.x + trace.dx * frac; y = trace.y + trace.dy * frac;
  z = AIM.shootz + AIM.aimslope * (frac * AIM.attackrange);
  if (th.flags & MF_NOBLOOD) spawnPuff(x, y, z);
  else spawnBlood(x, y, z, AIM.damage);
  if (AIM.damage) damageMobj(th, AIM.shootthing, AIM.shootthing, AIM.damage);
  return false;
}

function lineAttack(t1, angle, distance, slope, damage) {
  const x2 = t1.x + distance * Math.cos(angle * DEG), y2 = t1.y + distance * Math.sin(angle * DEG);
  AIM.shootthing = t1;
  AIM.shootz = t1.z + t1.height / 2 + 4;
  AIM.attackrange = distance; AIM.aimslope = slope; AIM.damage = damage;
  pathTraverse(t1.x, t1.y, x2, y2, PT_ADDLINES | PT_ADDTHINGS, PTR_ShootTraverse);
}

// ---------------------------------------------------------------- use lines
function useLines(player) {
  const mo = player.mo;
  const x2 = mo.x + USERANGE * Math.cos(mo.angle * DEG), y2 = mo.y + USERANGE * Math.sin(mo.angle * DEG);
  pathTraverse(mo.x, mo.y, x2, y2, PT_ADDLINES, (ic) => {
    const li = ic.line;
    if (!li.special) {
      const op = lineOpening(li);
      if (op.range <= 0) { startSound(mo, 'noway'); return false; }
      return true;
    }
    const side = pointOnLineSide(mo.x, mo.y, li);
    if (side === 1) return false;
    useSpecialLine(mo, li, side);
    return false;
  });
}

// ---------------------------------------------------------------- radius attack
function radiusAttack(spot, source, damage) {
  const dist = damage + MAXRADIUS;
  const yh = blockY(spot.y + dist), yl = blockY(spot.y - dist);
  const xh = blockX(spot.x + dist), xl = blockX(spot.x - dist);
  const victims = [];
  for (let y = yl; y <= yh; y++) for (let x = xl; x <= xh; x++)
    blockThingsIterator(x, y, (th) => { victims.push(th); return true; });
  for (const th of victims) {
    if (th.removed || !(th.flags & MF_SHOOTABLE)) continue;
    if (th.type === MT.CYBERDEMON || th.type === MT.MASTERMIND) continue;   // the big ones shrug off blasts
    if (sameTeamNoFF(source, th)) continue;
    const dx = Math.abs(th.x - spot.x), dy = Math.abs(th.y - spot.y);
    let d = Math.max(dx, dy) - th.radius;
    if (d < 0) d = 0;
    if (d >= damage) continue;
    if (checkSight(th, spot)) damageMobj(th, spot, source, Math.floor(damage - d));
  }
}

// ---------------------------------------------------------------- sight
function checkSight(t1, t2) {
  const s1 = t1.sector || G.level.sectorAt(t1.x, t1.y);
  const s2 = t2.sector || G.level.sectorAt(t2.x, t2.y);
  if (!s1 || !s2) return false;
  const sightzstart = t1.z + t1.height - t1.height / 4;
  let topslope = t2.z + t2.height - sightzstart;
  let bottomslope = t2.z - sightzstart;
  const dx = t2.x - t1.x, dy = t2.y - t1.y;
  const distTotal = Math.hypot(dx, dy);
  if (distTotal < 1) return true;
  topslope /= distTotal; bottomslope /= distTotal;
  return pathTraverse(t1.x, t1.y, t2.x, t2.y, PT_ADDLINES, (ic) => {
    const li = ic.line;
    if (!li.backsector || !(li.flags & ML_TWOSIDED)) return false;
    const fs = li.frontsector, bs = li.backsector;
    if (fs.floorheight === bs.floorheight && fs.ceilingheight === bs.ceilingheight) return true;
    const op = lineOpening(li);
    if (op.bottom >= op.top) return false;
    const dist = distTotal * ic.frac;
    if (dist <= 0) return true;
    if (fs.floorheight !== bs.floorheight) {
      const slope = (op.bottom - sightzstart) / dist;
      if (slope > bottomslope) bottomslope = slope;
    }
    if (fs.ceilingheight !== bs.ceilingheight) {
      const slope = (op.top - sightzstart) / dist;
      if (slope < topslope) topslope = slope;
    }
    return topslope > bottomslope;
  });
}

// ---------------------------------------------------------------- teleport move (telefrag)
function teleportMove(thing, x, y) {
  TM.thing = thing; TM.flags = thing.flags; TM.x = x; TM.y = y;
  TM.bbox[0] = y + thing.radius; TM.bbox[1] = y - thing.radius;
  TM.bbox[3] = x + thing.radius; TM.bbox[2] = x - thing.radius;
  const sec = G.level.sectorAt(x, y);
  TM.ceilingline = null;
  TM.floorz = TM.dropoffz = sec.floorheight; TM.ceilingz = sec.ceilingheight;
  G.validcount++;
  TM.spechit.length = 0;
  const xl = blockX(TM.bbox[2] - MAXRADIUS), xh = blockX(TM.bbox[3] + MAXRADIUS);
  const yl = blockY(TM.bbox[1] - MAXRADIUS), yh = blockY(TM.bbox[0] + MAXRADIUS);
  const stomp = [];
  for (let bx = xl; bx <= xh; bx++) for (let by = yl; by <= yh; by++)
    blockThingsIterator(bx, by, (th) => {
      if (!(th.flags & MF_SHOOTABLE) || th === thing) return true;
      const bd = th.radius + thing.radius;
      if (Math.abs(th.x - x) >= bd || Math.abs(th.y - y) >= bd) return true;
      stomp.push(th); return true;
    });
  // only players telefrag; a monster whose destination is occupied doesn't go through (Doom's PIT_StompThing)
  if (!thing.player && stomp.length) return false;
  G.damageCtx = 'telefrag';
  for (const th of stomp) damageMobj(th, thing, thing, 10000);
  G.damageCtx = null;
  unsetThingPosition(thing);
  thing.floorz = TM.floorz; thing.ceilingz = TM.ceilingz;
  thing.x = x; thing.y = y;
  setThingPosition(thing);
  return true;
}
