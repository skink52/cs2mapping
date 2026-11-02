// ===================================================================================
// Part 1: level structures (built from the converter's level data), blockmap, BSP lookup
// ===================================================================================

class Sector {
  constructor(i, d) {
    this.id = i;
    this.floorheight = d[0]; this.ceilingheight = d[1];
    this.lightlevel = d[2]; this.special = d[3]; this.tag = d[4]; this.sky = !!d[5];
    this.lines = [];
    this.specialdata = null;      // active floor/ceiling mover
    this.blockbox = [0, 0, 0, 0]; // top, bottom, left, right in blockmap cells
    this.soundorg = { x: 0, y: 0, z: 0 };
    this.validcount = 0;
    this.floorMover = false; this.ceilMover = false;
    this.renderFloor = d[0]; this.renderCeil = d[1];
    this.soundtraversed = undefined; this.soundtarget = undefined; this.lightNow = undefined;   // set later; one shape
  }
}

class Line {
  constructor(i, d, verts, sectors) {
    this.id = i;
    const v1 = d[0], v2 = d[1];
    this.x1 = verts[v1 * 2]; this.y1 = verts[v1 * 2 + 1];
    this.x2 = verts[v2 * 2]; this.y2 = verts[v2 * 2 + 1];
    this.dx = this.x2 - this.x1; this.dy = this.y2 - this.y1;
    this.flags = d[2]; this.special = d[3]; this.tag = d[4];
    this.frontsector = d[5] >= 0 ? sectors[d[5]] : null;
    this.backsector = d[6] >= 0 ? sectors[d[6]] : null;
    this.bbox = [Math.max(this.y1, this.y2), Math.min(this.y1, this.y2), Math.min(this.x1, this.x2), Math.max(this.x1, this.x2)];
    this.slopetype = this.dx === 0 ? 1 : this.dy === 0 ? 0 : (this.dy / this.dx > 0 ? 2 : 3); // horiz, vert, pos, neg
    this.validcount = 0;
    this.switchUntil = 0;
  }
}

class Level {
  constructor(data) {
    this.data = data;
    this.id = data.id;
    this.off = data.off;
    this.anims = data.an || [];      // [name of the animated-surface prop, frame count]
    const V = data.v;
    this.sectors = data.s.map((d, i) => new Sector(i, d));
    this.lines = data.l.map((d, i) => new Line(i, d, V, this.sectors));
    this.nodes = data.n;
    this.ssSector = data.ss;
    this.things = data.t;
    for (const s of data.mf) this.sectors[s].floorMover = true;
    for (const s of data.mc) this.sectors[s].ceilMover = true;
    for (const l of this.lines) {
      if (l.frontsector) l.frontsector.lines.push(l);
      if (l.backsector && l.backsector !== l.frontsector) l.backsector.lines.push(l);
    }
    // blockmap
    let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
    for (let i = 0; i < V.length; i += 2) {
      minx = Math.min(minx, V[i]); maxx = Math.max(maxx, V[i]);
      miny = Math.min(miny, V[i + 1]); maxy = Math.max(maxy, V[i + 1]);
    }
    this.bmaporgx = minx - 8; this.bmaporgy = miny - 8;
    this.bmapwidth = Math.floor((maxx - this.bmaporgx) / BLOCKSIZE) + 1;
    this.bmapheight = Math.floor((maxy - this.bmaporgy) / BLOCKSIZE) + 1;
    const n = this.bmapwidth * this.bmapheight;
    this.blockLines = new Array(n);
    for (let i = 0; i < n; i++) this.blockLines[i] = [];
    for (const l of this.lines) this.addLineToBlockmap(l);
    // sector sound origins + blockboxes
    for (const s of this.sectors) {
      let t = -Infinity, b = Infinity, le = Infinity, r = -Infinity;
      for (const l of s.lines) {
        t = Math.max(t, l.bbox[0]); b = Math.min(b, l.bbox[1]); le = Math.min(le, l.bbox[2]); r = Math.max(r, l.bbox[3]);
      }
      if (!s.lines.length) { t = b = le = r = 0; }
      s.soundorg.x = (le + r) / 2; s.soundorg.y = (t + b) / 2;
      const clampx = (v) => Math.max(0, Math.min(this.bmapwidth - 1, v));
      const clampy = (v) => Math.max(0, Math.min(this.bmapheight - 1, v));
      s.blockbox[0] = clampy(Math.floor((t - this.bmaporgy + MAXRADIUS) / BLOCKSIZE));
      s.blockbox[1] = clampy(Math.floor((b - this.bmaporgy - MAXRADIUS) / BLOCKSIZE));
      s.blockbox[2] = clampx(Math.floor((le - this.bmaporgx - MAXRADIUS) / BLOCKSIZE));
      s.blockbox[3] = clampx(Math.floor((r - this.bmaporgx + MAXRADIUS) / BLOCKSIZE));
    }
  }

  addLineToBlockmap(l) {
    // conservative: every cell the line's segment passes through
    const bx0 = Math.floor((l.bbox[2] - this.bmaporgx) / BLOCKSIZE), bx1 = Math.floor((l.bbox[3] - this.bmaporgx) / BLOCKSIZE);
    const by0 = Math.floor((l.bbox[1] - this.bmaporgy) / BLOCKSIZE), by1 = Math.floor((l.bbox[0] - this.bmaporgy) / BLOCKSIZE);
    for (let by = by0; by <= by1; by++) {
      for (let bx = bx0; bx <= bx1; bx++) {
        if (bx < 0 || by < 0 || bx >= this.bmapwidth || by >= this.bmapheight) continue;
        const x0 = this.bmaporgx + bx * BLOCKSIZE, y0 = this.bmaporgy + by * BLOCKSIZE;
        if (boxOnLineSide([y0 + BLOCKSIZE, y0, x0, x0 + BLOCKSIZE], l) === -1)
          this.blockLines[by * this.bmapwidth + bx].push(l);
      }
    }
  }

  // R_PointInSubsector -> sector
  sectorAt(x, y) {
    const nodes = this.nodes;
    let child = nodes.length - 1;
    for (;;) {
      const n = nodes[child];
      const side = ((y - n[1]) * n[2] < n[3] * (x - n[0])) ? 0 : 1;
      child = side === 0 ? n[4] : n[5];
      if (child & 0x8000) return this.sectors[this.ssSector[child & 0x7fff]];
    }
  }
}

// ---------------------------------------------------------------- geometry utilities
function pointOnLineSide(x, y, l) {
  if (l.dx === 0) return x <= l.x1 ? (l.dy > 0 ? 1 : 0) : (l.dy < 0 ? 1 : 0);
  if (l.dy === 0) return y <= l.y1 ? (l.dx < 0 ? 1 : 0) : (l.dx > 0 ? 1 : 0);
  const left = l.dy * (x - l.x1);
  const right = (y - l.y1) * l.dx;
  return right < left ? 0 : 1;
}

// returns 0 or 1 if box entirely on one side, -1 if it crosses
function boxOnLineSide(box, l) {
  let p1, p2;
  switch (l.slopetype) {
    case 0: // horizontal
      p1 = box[0] > l.y1 ? 1 : 0; p2 = box[1] > l.y1 ? 1 : 0;
      if (l.dx < 0) { p1 ^= 1; p2 ^= 1; }
      break;
    case 1: // vertical
      p1 = box[3] < l.x1 ? 1 : 0; p2 = box[2] < l.x1 ? 1 : 0;
      if (l.dy < 0) { p1 ^= 1; p2 ^= 1; }
      break;
    case 2: // positive slope
      p1 = pointOnLineSide(box[2], box[0], l); p2 = pointOnLineSide(box[3], box[1], l);
      break;
    default:
      p1 = pointOnLineSide(box[3], box[0], l); p2 = pointOnLineSide(box[2], box[1], l);
      break;
  }
  return p1 === p2 ? p1 : -1;
}

function pointOnDivlineSide(x, y, dl) {
  if (dl.dx === 0) return x <= dl.x ? (dl.dy > 0 ? 1 : 0) : (dl.dy < 0 ? 1 : 0);
  if (dl.dy === 0) return y <= dl.y ? (dl.dx < 0 ? 1 : 0) : (dl.dx > 0 ? 1 : 0);
  const left = dl.dy * (x - dl.x), right = (y - dl.y) * dl.dx;
  return right < left ? 0 : 1;
}

// fraction along v2 where v1 crosses it
function interceptVector(v2, v1) {
  const den = v1.dy * v2.dx - v1.dx * v2.dy;
  if (den === 0) return 0;
  const num = (v1.x - v2.x) * v1.dy + (v2.y - v1.y) * v1.dx;
  return num / den;
}

function approxDistance(dx, dy) {
  dx = Math.abs(dx); dy = Math.abs(dy);
  return dx < dy ? dx + dy - dx / 2 : dx + dy - dy / 2;
}

function pointToAngle(x1, y1, x2, y2) {
  let a = Math.atan2(y2 - y1, x2 - x1) / DEG;
  if (a < 0) a += 360;
  return a;
}

function normAngle(a) {
  a %= 360;
  return a < 0 ? a + 360 : a;
}

function angleDiff(a, b) { // signed shortest b - a
  let d = (b - a) % 360;
  if (d > 180) d -= 360; else if (d < -180) d += 360;
  return d;
}

// one shared result object (every caller reads it straight away, before the next call): no garbage per line checked
const OPENING = { top: 0, bottom: 0, range: 0, lowfloor: 0 };
function lineOpening(l) {
  const front = l.frontsector, back = l.backsector;
  const op = OPENING;
  if (!back) { op.top = 0; op.bottom = 0; op.range = 0; op.lowfloor = 0; return op; }
  const top = Math.min(front.ceilingheight, back.ceilingheight);
  const bottom = Math.max(front.floorheight, back.floorheight);
  op.top = top; op.bottom = bottom; op.range = top - bottom;
  op.lowfloor = Math.min(front.floorheight, back.floorheight);
  return op;
}

// Doom's P_Random-style generator (0..255)
let rngState = (Date.now() ^ 0x9e3779b9) >>> 0;
function P_Random() {
  rngState ^= rngState << 13; rngState >>>= 0;
  rngState ^= rngState >>> 17;
  rngState ^= rngState << 5; rngState >>>= 0;
  return rngState & 255;
}
