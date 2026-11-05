// ---------------------------------------------------------------- drawing the race with pooled props
// Every car is a prop_dynamic from the pool (model = car class, or its boosting variant; skin = side colour), moved
// every tick with Move so the client interpolates. Wrecks, warp-outs and the Pulse are pooled effect props.

const NULL_MODEL = 'models/spr/null.vmdl';
const HIDE_POS = { x: 0, y: 0, z: -15000 };
// skin numbers by name, in the order tools/cars.py gave the car models their skins (neutral, t, ct, gold, then the shades)
const SKIN_INDEX = {};
(CAR_MODELS.skins || ['neutral', 't', 'ct', 'gold']).forEach((k, i) => { SKIN_INDEX[k] = i; });
// a car's skin: its driver's shade of the side colour (index into SHADES.t / SHADES.ct)
function carSkin(car) {
  const list = car.team === 0 ? SHADES.t : car.team === 1 ? SHADES.ct : null;
  if (!list) return SKIN_INDEX.neutral || 0;
  const sh = list[car.shade] || list[0];
  const i = SKIN_INDEX[sh.skin];
  return i === undefined ? SKIN_INDEX[car.team === 0 ? 't' : 'ct'] : i;
}
// the winners' neon glow: their shade's colour, brightened
function glowColor(car) {
  const list = car.team === 0 ? SHADES.t : car.team === 1 ? SHADES.ct : null;
  const c = list ? (list[car.shade] || list[0]).rgb : [255, 215, 60];
  const k = 255 / Math.max(1, c[0], c[1], c[2]);
  return { r: Math.round(c[0] * k), g: Math.round(c[1] * k), b: Math.round(c[2] * k) };
}

let propTemplate;
let propSerial = 0;
const freeProps = [];
let spawnBudget = 0;

function findPropTemplate() {
  propTemplate = live(propTemplate) || live(Instance.FindEntityByName(CONFIG.PROP_TEMPLATE));
  if (!propTemplate) warnOnce('tpl', 'no point_template named ' + CONFIG.PROP_TEMPLATE + ' - nothing can be drawn');
  return propTemplate;
}

function newProp() {
  if (spawnBudget <= 0) return undefined;
  const tpl = findPropTemplate();
  if (!tpl) return undefined;
  spawnBudget--;
  const ents = /** @type {any} */ (tpl).ForceSpawn(HIDE_POS, { pitch: 0, yaw: 0, roll: 0 });
  if (!ents || !ents.length) { warnOnce('spawnfail', 'the prop template spawned nothing'); return undefined; }
  const ent = ents[0];
  const name = 'spr_p' + (++propSerial);
  try { ent.SetEntityName(name); } catch (err) { /* ignore */ }
  return { ent, name, model: '', skin: -1, hidden: true, lastPos: null, lastAng: null, alpha: -1, resetTic: -1, glow: '', scale: 1, boostAt: 0 };
}

function takeProp() {
  while (freeProps.length) {
    const p = freeProps.pop();
    if (live(p.ent)) return p;
  }
  return newProp();
}

function releaseProp(p) {
  if (!p || !live(p.ent)) return;
  if (p.glow) { try { p.ent.Unglow(); } catch (err) { /* ignore */ } p.glow = ''; }
  if (!p.hidden) {
    try { p.ent.SetModel(NULL_MODEL); p.ent.Teleport({ position: HIDE_POS }); } catch (err) { /* ignore */ }
    p.model = NULL_MODEL; p.hidden = true;
  }
  freeProps.push(p);
}

function propModel(p, model) {
  if (p.model === model || !live(p.ent)) return;
  p.ent.SetModel(model); p.model = model;
}
function propSkin(p, skin) {
  if (p.skin === skin || !live(p.ent)) return;
  Instance.EntFireAtTarget({ target: p.ent, input: 'Skin', value: skin }); p.skin = skin;
}
// the outline glow: '' = none, else 'r,g,b'
function propGlow(p, col) {
  const key = col ? col.r + ',' + col.g + ',' + col.b : '';
  if (p.glow === key) return;
  if (col) p.ent.Glow(col); else p.ent.Unglow();
  p.glow = key;
}
function propAlpha(p, a) {
  if (p.alpha === a || !live(p.ent)) return;
  p.ent.SetColor({ r: 255, g: 255, b: 255, a }); p.alpha = a;
}

class ArenaView {
  constructor(arena) {
    this.arena = arena;
    this.off = arena.track.off || [0, 0, 0];
    this.props = new Map();      // car slot -> prop
    this.fx = [];                // { prop, kind, until, frames, start, x, y, z, yaw }
    this.pulseProp = null;
    this.shells = new Map();     // car slot -> prop: the Aegis shell round a Bastion
    this.boltProps = new Map();  // bolt id -> prop: Seeker Bolts in flight
    this.crProps = new Map();    // creature id -> [prop per body segment] (Depth Racer)
    this.wallProps = new Map();  // wall id -> prop: walls of light (Neon Racer)
    this.hzProps = new Map();    // 'm' + mine id / 'c' + cloud id -> prop: Depth Charges and ink clouds (Depth Racer)
    this.wakes = new Map();      // car slot -> prop: the Undertow's wake behind a Bastion
    this.btProps = new Map();    // car slot -> prop: the boost trail behind a boosting car (Neon Racer; one prop, moved)
    this.anchors = null;
    this.fxDone = false;         // the per-car sound / shake bits of the last race step have been handled (results)
  }

  world(x, y, z) { return { x: this.off[0] + x, y: this.off[1] + y, z: this.off[2] + z }; }

  // the flames: gold and longer on a boost pad (or a turbo start), the car's own colour when it boosts (Mouse 1, Nova)
  carModel(car) {
    const m = CAR_MODELS.cars[car.cls] || CAR_MODELS.cars.hornet;
    return car.padTimer > 0 ? m.pad : car.boosting || car.novaTimer > 0 || car.jet > 0 ? m.boost : m.base;
  }

  // (CS2 calls are the expensive part here: a prop's entity is checked every 16th tick, not every tick - an engine
  // call that fails on a prop that went away drops it, and a car whose pose hasn't changed isn't moved at all)
  update(now) {
    const a = this.arena;
    for (const car of a.order) {
      const p = this.props.get(car.slot);
      try { this.drawCar(car, p, now); } catch (err) {
        // the prop's entity went away: forget it (a new one is taken next tick); a prop that is still there is kept
        const q = this.props.get(car.slot);
        if (q && !live(q.ent)) this.props.delete(car.slot);
        else warnOnce('carprop:' + String(err), 'drawing a car failed: ' + err);
      }
    }
    for (const [slot, sh] of this.shells) if (!a.cars.get(slot) || !a.cars.get(slot).visible) { releaseProp(sh); this.shells.delete(slot); }
    this.drawPulse();
    this.drawBolts();
    if (a.walls.length || this.wallProps.size) this.drawWalls();
    if (RULES.boostTrail > 0) this.drawBoostTrails();
    if (a.mines.length || a.clouds.length || this.hzProps.size) this.drawHazards(now);
    this.drawWakes(now);
    if (this.arena.creatures.length) this.drawCreatures(now);
    // effects
    for (let k = this.fx.length - 1; k >= 0; k--) {
      const e = this.fx[k];
      if (now >= e.until || ((tickNo + k) & 15) === 0 && !live(e.prop.ent)) { releaseProp(e.prop); this.fx.splice(k, 1); continue; }
      const frame = Math.min(e.frames.length - 1, Math.floor((now - e.start) / (e.until - e.start) * e.frames.length));
      try { propModel(e.prop, e.frames[frame]); } catch (err) { this.fx.splice(k, 1); }
    }
  }

  drawCar(car, p, now) {
    const T = this.arena.track;
    if (!car.visible) {
      if (p) { this.props.delete(car.slot); releaseProp(p); }
      return;
    }
    if (!p) { p = takeProp(); if (!p) return; this.props.set(car.slot, p); p.hidden = false; p.lastPos = null; p.lastAng = null; p.model = ''; p.skin = -1; p.alpha = -1; }
    else if (((tickNo + car.slot) & 15) === 0 && !live(p.ent)) { this.props.delete(car.slot); return; }
    {
      propModel(p, car.state === 'wrecked' ? CAR_MODELS.cars[car.cls].base : this.carModel(car));
      propSkin(p, carSkin(car));
      // last round's top places glow (not while wrecked or warping out)
      propGlow(p, CONFIG.WINNER_GLOW && car.glow > 0 && car.glow <= CONFIG.GLOW_PLACES && car.state !== 'wrecked' && car.state !== 'gone' ? glowColor(car) : null);
      propAlpha(p, car.state === 'wrecked' ? 90 : car.ghost > 0 && car.state === 'racing' ? 140 : car.state === 'finished' ? 160 : 255);
      // angles: yaw from the heading (+ spin), pitch and roll from the road under the car, plus the lean into a turn.
      // On the road the car rests on the surface under its four corners in its own frame (nose, tail, left, right:
      // Track.surfaceAt, which includes the bank and ramps): the pitch is the slope nose to tail, the roll the slope
      // side to side, and the car is lifted so that no corner is in the road - a crest, the foot of a climb, a banked
      // bend or a car sideways across a steep incline (a drift, a spin, a shove) all keep the hull on the surface.
      // Before 4 Nov the pitch followed the road's own direction whatever way the car faced, so a car turned across a
      // steep incline dug one side into it.
      let pitch, lift = 0, bankRoll = 0;
      if (car.state === 'falling') pitch = Math.min(60, car.stateTime * 50);
      else if (car.air) pitch = clamp(-deg(Math.atan2(car.vz, Math.max(200, car.speed))) * 0.7, -25, 25);
      else {
        const i = car.seg, half = CAR_LEN * 0.45, halfW = CAR_R;
        const rel = normRad(car.yaw + car.spinYaw - Math.atan2(T.ty[i], T.tx[i]));     // the car's heading against the road's
        const cr = Math.cos(rel), sr = Math.sin(rel);
        // a point f ahead and l to the left of the car, in road coordinates (progress, lateral offset)
        const zc = (f, l) => T.surfaceAt(car.s + f * cr - l * sr, car.d + f * sr + l * cr);
        const zMid = zc(0, 0), zf = zc(half, 0), zr = zc(-half, 0), zl = zc(0, halfW), zrt = zc(0, -halfW);
        pitch = -deg(Math.atan2(zf - zr, 2 * half));
        bankRoll = deg(Math.atan2(zl - zrt, 2 * halfW));            // left corner lower = lean left = negative roll (5 Nov: the sign was flipped and cars leaned out of banked bends)
        lift = Math.max(0, (zf + zr) / 2 - zMid, (zl + zrt) / 2 - zMid) + CONFIG.CAR_CLEAR + CONFIG.CAR_CLEAR_SLOPE * Math.abs(zf - zr) / (2 * half);
      }
      // roll (+ = right side down): the road's lean under the car (bankRoll: left side low = negative) plus leaning
      // into the turn (turning right = yaw falling = lean right)
      const turnRoll = clamp(-(car.yawRate || 0) * CONFIG.CAR_LEAN, -CONFIG.CAR_LEAN_MAX, CONFIG.CAR_LEAN_MAX);
      const roll = car.state === 'falling' ? 0 : CONFIG.PROP_ROLL_SIGN * (bankRoll + turnRoll);
      const yaw = deg(car.yaw + car.spinYaw);
      const pos = this.world(car.x, car.y, car.z + lift);
      if (car.state === 'wrecked') pos.z -= Math.min(8, car.stateTime * 6);
      // Teleport only for the first placement and real jumps (respawns); everything else Moves, the grid included -
      // unless the car is exactly where it was (waiting on the grid, a wreck that has settled)
      // (a reset after a fall teleports once: an arena that has stopped stepping keeps the car's last fx bits)
      const lp = p.lastPos, la = p.lastAng, reset = (car.fx & 128) !== 0 && p.resetTic !== this.arena.raceTic;
      if (reset) p.resetTic = this.arena.raceTic;
      if (!lp || reset || Math.abs(pos.x - lp.x) + Math.abs(pos.y - lp.y) + Math.abs(pos.z - lp.z) > CONFIG.TELEPORT_DIST) p.ent.Teleport({ position: pos, angles: { pitch, yaw, roll } });
      else if (pos.x !== lp.x || pos.y !== lp.y || pos.z !== lp.z || pitch !== la.pitch || yaw !== la.yaw || roll !== la.roll) p.ent.Move({ position: pos, angles: { pitch, yaw, roll } });
      p.lastPos = pos;
      if (!la) p.lastAng = { pitch, yaw, roll }; else { la.pitch = pitch; la.yaw = yaw; la.roll = roll; }
      // the Aegis shell follows the car while it is up
      let sh = this.shells.get(car.slot);
      if (car.aegis > 0 && car.state === 'racing') {
        if (!sh) { sh = takeProp(); if (sh) { this.shells.set(car.slot, sh); sh.hidden = false; sh.lastPos = null; sh.model = ''; sh.alpha = -1; } }
        else if (((tickNo + car.slot) & 15) === 0 && !live(sh.ent)) { this.shells.delete(car.slot); sh = null; }
        if (sh) {
          try {
            propModel(sh, CAR_MODELS.fx.aegis);
            const sa = { pitch: 0, yaw: (now * 90) % 360, roll: 0 };
            if (!sh.lastPos) sh.ent.Teleport({ position: pos, angles: sa }); else sh.ent.Move({ position: pos, angles: sa });
            sh.lastPos = pos;
          } catch (err) { if (!live(sh.ent)) this.shells.delete(car.slot); }
        }
      } else if (sh) { releaseProp(sh); this.shells.delete(car.slot); }
    }
  }

  // the Pulse wave
  drawPulse() {
    const a = this.arena, T = a.track;
    if (a.pulse.active && RULES.pulseEnabled) {
      if (!this.pulseProp) { this.pulseProp = takeProp(); if (this.pulseProp) { this.pulseProp.hidden = false; this.pulseProp.lastPos = null; this.pulseProp.model = ''; this.pulseProp.alpha = -1; } }
      const pp = this.pulseProp;
      if (pp && ((tickNo & 15) !== 0 || live(pp.ent))) {
        propModel(pp, CAR_MODELS.fx.pulse);
        const pt = T.point(a.pulse.total);
        const pos = this.world(pt.x, pt.y, pt.z + 2);
        // follow the road: its slope and its bank (the fence and floor strip lie on the surface)
        const j = (pt.i + 1) % T.n;
        const ang = { pitch: -deg(Math.atan2(T.z[j] - T.z[pt.i], T.step)), yaw: deg(Math.atan2(pt.ty, pt.tx)), roll: CONFIG.PROP_ROLL_SIGN * -deg(Math.atan(T.bk[pt.i])) };
        if (!pp.lastPos) pp.ent.Teleport({ position: pos, angles: ang }); else pp.ent.Move({ position: pos, angles: ang });
        pp.lastPos = pos;
      }
    } else if (this.pulseProp) { releaseProp(this.pulseProp); this.pulseProp = null; }
  }

  // walls of light (Neon Racer): a prop per segment, placed once (they don't move); the slab model is scaled to the
  // segment's length. Light Trails and Firewalls are bright and tall, boost trails low and dim.
  drawWalls() {
    const a = this.arena, seen = new Set(), fx = CAR_MODELS.fx;
    for (let k = a.walls.length - 1; k >= 0; k--) {
      const w = a.walls[k];
      if (w.kind === 'boost') continue;                  // (drawn as one prop per boosting car: drawBoostTrails)
      seen.add(w.id);
      let p = this.wallProps.get(w.id);
      if (!p) {
        if (this.wallProps.size >= CONFIG.MAX_WALL_PROPS) continue;
        p = takeProp(); if (!p) continue;
        p.hidden = false; p.lastPos = null; p.model = ''; p.alpha = -1;
        this.wallProps.set(w.id, p);
        try {
          const model = w.kind === 'firewall' ? fx.wallw : fx.wall;
          const base = w.kind === 'firewall' ? 500 : 180;
          propModel(p, model); propAlpha(p, 255);
          const len = Math.hypot(w.x1 - w.x0, w.y1 - w.y0);
          p.ent.SetModelScale(clamp(len / base, 0.4, 2.0));
          p.ent.Teleport({ position: this.world((w.x0 + w.x1) / 2, (w.y0 + w.y1) / 2, w.z), angles: { pitch: 0, yaw: deg(Math.atan2(w.y1 - w.y0, w.x1 - w.x0)), roll: 0 } });
          p.lastPos = { x: 0, y: 0, z: 0 };
        } catch (err) { this.wallProps.delete(w.id); releaseProp(p); }
      } else if ((tickNo & 15) === 0 && !live(p.ent)) { this.wallProps.delete(w.id); continue; }
      // the last half second: the wall fades (alpha), then goes
      const left = w.until - a.time;
      if (left < 0.5) { try { propAlpha(p, Math.max(40, Math.round(255 * left / 0.5))); } catch (err) { /* ignore */ } }
    }
    for (const [id, p] of this.wallProps) if (!seen.has(id)) { try { p.ent.SetModelScale(1); } catch (err) { /* ignore */ } releaseProp(p); this.wallProps.delete(id); }
  }

  // the boost trail behind every boosting car (Neon Racer): one low slab per car, as long as the last boostTrail
  // seconds of its path, moved with the car while it boosts and left where it is for the trail's life after (the
  // segments the race keeps for hits are not drawn one by one). A bot's boost flickers on and off from tick to tick,
  // and a prop taken, placed and hidden every tick is one CS2 stops drawing, so the prop stays through the gaps.
  drawBoostTrails() {
    const a = this.arena, fx = CAR_MODELS.fx;
    if (!fx.trail_s) return;
    for (const car of a.order) {
      let p = this.btProps.get(car.slot);
      const on = car.btOn && car.boosting && car.state === 'racing' && !car.air;
      if (on || (p && car.state === 'racing' && a.time - p.boostAt < RULES.boostTrail)) {
        if (!p) { p = takeProp(); if (!p) continue; this.btProps.set(car.slot, p); p.hidden = false; p.lastPos = null; p.model = ''; p.alpha = -1; p.scale = 0; propModel(p, fx.trail_s); propAlpha(p, 170); }
        else if (((tickNo + car.slot) & 15) === 0 && !live(p.ent)) { this.btProps.delete(car.slot); continue; }
        if (on) p.boostAt = a.time; else continue;          // not boosting: the trail stays where it was laid
        try {
          const len = clamp(car.speed * RULES.boostTrail, 200, 600), sc = Math.round(len / 40) * 40 / 400;   // (the model is 400 long)
          if (p.scale !== sc) { p.ent.SetModelScale(sc); p.scale = sc; }
          const back = len / 2 + CAR_LEN * 0.5;
          const pos = this.world(car.x - Math.cos(car.yaw) * back, car.y - Math.sin(car.yaw) * back, car.z + 2), ang = { pitch: 0, yaw: deg(car.yaw), roll: 0 };
          if (!p.lastPos) p.ent.Teleport({ position: pos, angles: ang }); else p.ent.Move({ position: pos, angles: ang });
          p.lastPos = pos;
        } catch (err) { if (!live(p.ent)) this.btProps.delete(car.slot); }
      } else if (p) { try { p.ent.SetModelScale(1); } catch (err) { /* ignore */ } releaseProp(p); this.btProps.delete(car.slot); }
    }
  }

  // Depth Charges (blinking once armed) and ink clouds (two frames, fading)
  drawHazards(now) {
    const a = this.arena, seen = new Set(), fx = CAR_MODELS.fx;
    const place = (key, x, y, z, yaw, model, alpha) => {
      seen.add(key);
      let p = this.hzProps.get(key);
      if (!p) {
        if (this.hzProps.size >= CONFIG.MAX_HAZARD_PROPS) return;
        p = takeProp(); if (!p) return;
        p.hidden = false; p.lastPos = null; p.model = ''; p.alpha = -1;
        this.hzProps.set(key, p);
        try { p.ent.Teleport({ position: this.world(x, y, z), angles: { pitch: 0, yaw: deg(yaw), roll: 0 } }); p.lastPos = { x: 0, y: 0, z: 0 }; } catch (err) { this.hzProps.delete(key); releaseProp(p); return; }
      } else if ((tickNo & 15) === 0 && !live(p.ent)) { this.hzProps.delete(key); return; }
      try { propModel(p, model); propAlpha(p, alpha); } catch (err) { this.hzProps.delete(key); }
    };
    for (const m of a.mines) place('m' + m.id, m.x, m.y, m.z, m.yaw, m.armed && (tickNo >> 3) & 1 ? fx.mine1 : fx.mine0, 255);
    for (const cl of a.clouds) {
      const left = cl.until - a.time;
      place('c' + cl.id, cl.x, cl.y, cl.z, 0, (tickNo >> 3) & 1 ? fx.ink1 : fx.ink0, left < 1 ? Math.max(60, Math.round(230 * left)) : 230);
    }
    for (const [key, p] of this.hzProps) if (!seen.has(key)) { releaseProp(p); this.hzProps.delete(key); }
  }

  // the Undertow's wake: a strip of water chevrons behind the Bastion while the current runs
  drawWakes(now) {
    const a = this.arena, fx = CAR_MODELS.fx;
    if (!fx.wake) return;
    for (const car of a.order) {
      let p = this.wakes.get(car.slot);
      if (car.undertow > 0 && car.state === 'racing') {
        if (!p) { p = takeProp(); if (!p) continue; this.wakes.set(car.slot, p); p.hidden = false; p.lastPos = null; p.model = ''; p.alpha = -1; propModel(p, fx.wake); propAlpha(p, 200); }
        else if (((tickNo + car.slot) & 15) === 0 && !live(p.ent)) { this.wakes.delete(car.slot); continue; }
        try {
          const pos = this.world(car.x - Math.cos(car.yaw) * 300, car.y - Math.sin(car.yaw) * 300, car.z + 3), ang = { pitch: 0, yaw: deg(car.yaw), roll: 0 };
          if (!p.lastPos) p.ent.Teleport({ position: pos, angles: ang }); else p.ent.Move({ position: pos, angles: ang });
          p.lastPos = pos;
        } catch (err) { if (!live(p.ent)) this.wakes.delete(car.slot); }
      } else if (p) { releaseProp(p); this.wakes.delete(car.slot); }
    }
  }

  // Seeker Bolts: a prop per bolt, moved every tick, two frames flickering
  drawBolts() {
    const a = this.arena, seen = new Set();
    for (const b of a.bolts) {
      seen.add(b.id);
      let p = this.boltProps.get(b.id);
      if (!p) {
        if (this.boltProps.size >= 8) continue;
        p = takeProp(); if (!p) continue;
        p.hidden = false; p.lastPos = null; p.model = ''; p.alpha = -1;
        propAlpha(p, 255);
        this.boltProps.set(b.id, p);
      }
      if ((tickNo & 15) === 0 && !live(p.ent)) { this.boltProps.delete(b.id); continue; }
      propModel(p, (tickNo >> 2) & 1 ? CAR_MODELS.fx.bolt1 : CAR_MODELS.fx.bolt0);
      const pos = this.world(b.x, b.y, b.z), ang = { pitch: 0, yaw: deg(b.yaw), roll: 0 };
      if (!p.lastPos) p.ent.Teleport({ position: pos, angles: ang }); else p.ent.Move({ position: pos, angles: ang });
      p.lastPos = pos;
    }
    for (const [id, p] of this.boltProps) if (!seen.has(id)) { releaseProp(p); this.boltProps.delete(id); }
  }

  // sea creatures: a prop per body segment while a pass is on, moved every tick
  drawCreatures(now) {
    const fx = CAR_MODELS.fx;
    for (const cr of this.arena.creatures) {
      let ps = this.crProps.get(cr.id);
      if (!cr.active) {
        if (ps) { for (const p of ps) releaseProp(p); this.crProps.delete(cr.id); }
        continue;
      }
      if (!ps) {
        ps = [];
        for (let j = 0; j < cr.segs.length; j++) {
          const p = takeProp(); if (!p) break;
          p.hidden = false; p.lastPos = null; p.model = ''; p.alpha = -1; propAlpha(p, 255);
          ps.push(p);
        }
        this.crProps.set(cr.id, ps);
      }
      const last = cr.segs.length - 1;
      for (let j = 0; j < ps.length; j++) {
        const p = ps[j], s = cr.segs[j];
        if (((tickNo + j) & 15) === 0 && !live(p.ent)) continue;
        let model;
        if (cr.kind === 'manta') model = Math.floor(now * 3) % 2 ? fx.cr_manta1 : fx.cr_manta0;
        else if (cr.kind === 'whale') model = j === 0 ? fx.cr_whale_head : j === last ? fx.cr_whale_tail : fx.cr_whale_body;
        else model = j === 0 ? fx.cr_serpent_head : j === last ? fx.cr_serpent_tail : fx.cr_serpent_body;
        if (model) propModel(p, model);
        const pos = this.world(s.x, s.y, s.z), ang = { pitch: 0, yaw: deg(s.yaw), roll: 0 };
        if (!p.lastPos) p.ent.Teleport({ position: pos, angles: ang }); else p.ent.Move({ position: pos, angles: ang });
        p.lastPos = pos;
      }
    }
  }

  // an effect at a track position: frames = list of models, shown over `seconds`
  effect(x, y, z, yaw, frames, seconds, now) {
    if (this.fx.length >= CONFIG.MAX_EFFECT_PROPS) return;
    const prop = takeProp();
    if (!prop) return;
    prop.hidden = false; prop.lastPos = null; prop.model = ''; prop.alpha = -1;
    propModel(prop, frames[0]);
    propAlpha(prop, 255);
    prop.ent.Teleport({ position: this.world(x, y, z), angles: { pitch: 0, yaw: deg(yaw), roll: 0 } });
    this.fx.push({ prop, frames, start: now, until: now + seconds });
  }

  wreckEffect(car, now) {
    const fx = CAR_MODELS.fx;
    this.effect(car.x, car.y, car.z + 20, car.yaw, [fx.boom0, fx.boom1, fx.boom2, fx.boom3], RULES.wreckShow, now);
  }
  warpEffect(car, now) {
    const fx = CAR_MODELS.fx;
    this.effect(car.x, car.y, car.z, car.yaw, [fx.warp0, fx.warp1], 0.5, now);
  }

  destroy() {
    for (const p of this.props.values()) releaseProp(p);
    this.props.clear();
    for (const p of this.shells.values()) releaseProp(p);
    this.shells.clear();
    for (const p of this.boltProps.values()) releaseProp(p);
    this.boltProps.clear();
    for (const ps of this.crProps.values()) for (const p of ps) releaseProp(p);
    this.crProps.clear();
    for (const p of this.wallProps.values()) { try { p.ent.SetModelScale(1); } catch (err) { /* ignore */ } releaseProp(p); }
    this.wallProps.clear();
    for (const p of this.hzProps.values()) releaseProp(p);
    this.hzProps.clear();
    for (const p of this.wakes.values()) releaseProp(p);
    this.wakes.clear();
    for (const p of this.btProps.values()) { try { p.ent.SetModelScale(1); } catch (err) { /* ignore */ } releaseProp(p); }
    this.btProps.clear();
    for (const e of this.fx) releaseProp(e.prop);
    this.fx = [];
    if (this.pulseProp) { releaseProp(this.pulseProp); this.pulseProp = null; }
    if (this.anchors) { this.anchors.release(); this.anchors = null; }
  }
}
