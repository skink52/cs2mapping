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
  return { ent, name, model: '', skin: -1, hidden: true, lastPos: null, lastAng: null, alpha: -1, resetTic: -1, glow: '' };
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
    this.anchors = null;
    this.fxDone = false;         // the per-car sound / shake bits of the last race step have been handled (results)
  }

  world(x, y, z) { return { x: this.off[0] + x, y: this.off[1] + y, z: this.off[2] + z }; }

  // the flames: gold and longer on a boost pad (or a turbo start), the car's own colour when it boosts (Mouse 1, Nova)
  carModel(car) {
    const m = CAR_MODELS.cars[car.cls] || CAR_MODELS.cars.hornet;
    return car.padTimer > 0 ? m.pad : car.boosting || car.novaTimer > 0 ? m.boost : m.base;
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
      // angles: yaw from the heading (+ spin), pitch from the slope, roll from the bank and the slide
      const i = car.seg;
      const rf = car.lift > 0 ? T.rampAt(i) : null;
      const rampTilt = rf ? -deg(Math.atan2(rf.h, (((rf.b - rf.a + T.n) % T.n) + 1) * T.step)) : 0;
      // on the road the car rests on its nose and tail: the slope between the road under each end, and where the road
      // curves up (the foot of a climb) it sits on its ends instead of on the road under its middle, so it doesn't sink
      let pitch, lift = 0;
      if (car.state === 'falling') pitch = Math.min(60, car.stateTime * 50);
      else if (car.air) pitch = clamp(-deg(Math.atan2(car.vz, Math.max(200, car.speed))) * 0.7, -25, 25);
      else {
        const half = CAR_LEN * 0.45, zMid = T.zAtS(car.s);
        const zf = T.zAtS(car.s + half), zr = T.zAtS(car.s - half);
        pitch = -deg(Math.atan2(zf - zr, 2 * half)) + rampTilt;
        if (!rf) lift = Math.max(0, (zf + zr) / 2 - zMid);
      }
      // roll (+ = right side down): the lean of a banked road (bank > 0 = left side low) plus leaning into the turn
      // (turning right = yaw falling = lean right)
      const bankRoll = car.air ? 0 : -deg(Math.atan(car.bank));
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
    for (const e of this.fx) releaseProp(e.prop);
    this.fx = [];
    if (this.pulseProp) { releaseProp(this.pulseProp); this.pulseProp = null; }
    if (this.anchors) { this.anchors.release(); this.anchors = null; }
  }
}
