// ---------------------------------------------------------------- rendering Doom things as props
// Every visible map object gets a pooled prop_dynamic whose model is the voxel/sprite model
// for its current sprite frame. Props are spawned from one point_template and recycled.

const NULL_MODEL = "models/fdm/null.vmdl";
const SKIN_FUZZ = 16;
const HIDE_POS = { x: 0, y: 0, z: -15000 };
const WORLD_EDGE = 16380;

let propTemplate;
const ANIM_TICS = 8;
// how a human player's own marine is placed: "move" (interpolated), "snap" (teleport each tick), "off" (not drawn)
let OWN_BODY = CONFIG.OWN_BODY;
function setOwnBody(mode) { OWN_BODY = mode; }
let propSerial = 0;
const freeProps = [];
let spawnBudget = 0;

function findPropTemplate() {
  propTemplate = live(propTemplate) || live(Instance.FindEntityByName(CONFIG.PROP_TEMPLATE));
  if (!propTemplate) warnOnce("tpl", "no point_template named " + CONFIG.PROP_TEMPLATE + " - nothing can be drawn");
  return propTemplate;
}

function newProp() {
  if (spawnBudget <= 0) return undefined;
  const tpl = findPropTemplate();
  if (!tpl) return undefined;
  spawnBudget--;
  const ents = /** @type {any} */ (tpl).ForceSpawn(HIDE_POS, { pitch: 0, yaw: 0, roll: 0 });
  if (!ents || !ents.length) { warnOnce("spawnfail", "the prop template spawned nothing"); return undefined; }
  const ent = ents[0];
  const name = "fdm_p" + (++propSerial);
  try { ent.SetEntityName(name); } catch (err) { /* ignore */ }
  return { ent, name, model: "", skin: 0, color: -1, hidden: true, lastPos: null, yaw: 0, stamp: 0, dead: false, fx: false };
}

function takeProp() {
  while (freeProps.length) {
    const p = freeProps.pop();
    if (live(p.ent)) return p;
  }
  return newProp();
}

function releaseProp(p) {
  if (!live(p.ent)) return;
  if (!p.hidden) {
    try { p.ent.SetModel(NULL_MODEL); p.ent.Teleport({ position: HIDE_POS }); } catch (err) { /* ignore */ }
    p.model = NULL_MODEL; p.hidden = true;
  }
  freeProps.push(p);
}

// sprite -> frame -> model path (or null), worked out once per sprite frame
const spriteModelCache = new Map();
function spriteModel(sprite, frame) {
  let frames = spriteModelCache.get(sprite);
  if (!frames) { frames = []; spriteModelCache.set(sprite, frames); }
  let m = frames[frame];
  if (m === undefined) {
    const key = sprite + "_" + (frame < 26 ? String.fromCharCode(97 + frame) : String(frame - 26));   // frames past Z are keyed 0 1 2
    m = frames[frame] = SPRITE_MODELS[key] ? "models/fdm/spr/" + key.toLowerCase() + ".vmdl" : null;
  }
  return m;
}

// sprites whose models were carved from their 8 rotations face the way the thing looks
const ROTATING = new Set(Object.entries(SPRITE_MODELS).filter(([, shape]) => shape === "rot8").map(([key]) => key.split("_")[0]));

class ArenaView {
  constructor(arena) {
    this.arena = arena;
    this.props = new Map();     // mobj id -> prop
    this.fxCount = 0;
    this.movers = [];
    this.anims = [];
    this.stamp = 0;             // goes up every update; props drawn this update carry it (no per-update Set)
    this.off = arena.level.off;
    this.findMovers();
    this.findAnims();
  }

  findAnims() {
    for (const [name, frames, tics] of this.arena.level.anims) {
      const ent = live(Instance.FindEntityByName(name));
      if (!ent) { warnOnce("anim" + name, "animated surface " + name + " is missing from the map"); continue; }
      this.anims.push({ ent, frames, tics: tics || ANIM_TICS, last: -1 });
    }
  }

  findMovers() {
    const L = this.arena.level;
    for (const s of L.sectors) {
      for (const plane of ["f", "c"]) {
        if (plane === "f" ? !s.floorMover : !s.ceilMover) continue;
        const name = "fdm_" + L.id + "_" + plane + s.id;
        const ent = live(Instance.FindEntityByName(name));
        if (!ent) { warnOnce("mover" + name, "mover " + name + " is missing from the map"); continue; }
        const base = ent.GetAbsOrigin();
        this.movers.push({ ent, sector: s, plane, base, h0: plane === "f" ? s.floorheight : s.ceilingheight, last: null });
      }
    }
  }

  world(x, y, z) { return { x: this.off[0] + x, y: this.off[1] + y, z: this.off[2] + z * ZSCALE }; }

  update(alpha) {
    const a = this.arena;
    // movers
    for (const m of this.movers) {
      const h = m.plane === "f" ? m.sector.floorheight : m.sector.ceilingheight;
      if (h === m.last) continue;
      m.last = h;
      if (!live(m.ent)) continue;
      m.ent.Teleport({ position: { x: m.base.x, y: m.base.y, z: m.base.z + (h - m.h0) * ZSCALE } });
    }
    // animated flats and walls: one skin per Doom animation frame, 8 tics each; scrolling walls step their
    // shifted-texture frames every few tics (1 pixel a tic, like Doom)
    for (const an of this.anims) {
      const skin = Math.floor(a.leveltime / an.tics) % an.frames;
      if (skin === an.last || !live(an.ent)) continue;
      an.last = skin;
      Instance.EntFireAtTarget({ target: an.ent, input: "Skin", value: skin });
    }
    // things
    const stamp = ++this.stamp;
    let drawn = 0;
    for (const mo of a.mobjs) {
      if (mo.info.kind === "teleportdest") continue;
      let p = this.props.get(mo.id);
      const isFx = mo.info.kind === "fx";
      if (!p) {
        if (isFx && this.fxCount >= CONFIG.MAX_EFFECT_PROPS) continue;
        p = takeProp();
        if (!p) continue;
        if (isFx) { this.fxCount++; p.fx = true; } else p.fx = false;
        this.props.set(mo.id, p);
        p.hidden = false; p.lastPos = null; p.model = ""; p.color = -1; p.skin = -1;
        mo.teleported = true;
      }
      p.stamp = stamp; drawn++;
      if (p.dead) continue;
      // no IsValid() per prop per tick: a prop removed under us makes a call throw (or do nothing); then it is
      // checked once and left alone from then on, as before
      try { this.drawThing(mo, p, alpha); } catch (err) { if (!live(p.ent)) { p.hidden = true; p.dead = true; } else throw err; }
    }
    if (drawn === this.props.size) return;   // every prop still has its thing: nothing to give back
    for (const [id, p] of this.props) {
      if (p.stamp === stamp) continue;
      this.props.delete(id);
      if (p.fx) this.fxCount--;
      releaseProp(p);
    }
  }

  drawThing(mo, p, alpha) {
    const ent = p.ent;
    const own = !!(mo.player && !mo.player.isBot);
    const model = (own && OWN_BODY === "off") ? NULL_MODEL : (spriteModel(mo.sprite, mo.frame) || NULL_MODEL);
    if (model !== p.model) { ent.SetModel(model); p.model = model; }
    // colour: sector light, full bright frames, player colours as skins, invisibility as fuzz
    const pl = mo.player;
    let skin = 0;
    if (mo.flags & MF_SHADOW) skin = SKIN_FUZZ;
    else if (mo.sprite === "PLAY") skin = pl ? pl.color : (mo.corpseColor || 0);
    if (pl) mo.corpseColor = pl.color;
    if (skin !== p.skin) {
      Instance.EntFireAtTarget({ target: ent, input: "Skin", value: skin });
      p.skin = skin;
    }
    const light = mo.bright ? 255 : (mo.sector ? sectorLight(mo.sector) : 160);
    const lv = Math.max(16, Math.min(255, light & 0xF0 | 8));
    if (lv !== p.color) { ent.SetColor({ r: lv, g: lv, b: lv, a: 255 }); p.color = lv; }
    // position, interpolated between the last two Doom tics
    let x = mo.x, y = mo.y, z = mo.z, yaw = mo.angle;
    if (!mo.teleported && alpha < 1) {
      x = mo.px + (mo.x - mo.px) * alpha; y = mo.py + (mo.y - mo.py) * alpha; z = mo.pz + (mo.z - mo.pz) * alpha;
      yaw = mo.pangle + angleDiff(mo.pangle, mo.angle) * alpha;
    }
    if (!ROTATING.has(mo.sprite)) yaw = 0;
    const lp = p.lastPos;
    if (lp && lp.x === x && lp.y === y && lp.z === z && p.yaw === yaw) return;
    const pos = this.world(x, y, z);
    // never past the edge of the CS2 world (it refuses such positions): hidden until the thing is back inside
    if (pos.x > WORLD_EDGE || pos.x < -WORLD_EDGE || pos.y > WORLD_EDGE || pos.y < -WORLD_EDGE || pos.z > WORLD_EDGE || pos.z < -WORLD_EDGE) {
      if (lp) ent.Teleport({ position: HIDE_POS });
      p.lastPos = null; mo.teleported = true;
      return;
    }
    const ang = { pitch: 0, yaw, roll: 0 };
    if (mo.teleported || !lp || (own && OWN_BODY === "snap")) { ent.Teleport({ position: pos, angles: ang }); mo.teleported = false; }
    else ent.Move({ position: pos, angles: ang });
    p.lastPos = { x, y, z }; p.yaw = yaw;
  }

  destroy() {
    for (const p of this.props.values()) releaseProp(p);
    this.props.clear();
    this.fxCount = 0;
    // put movers back to their map positions
    for (const m of this.movers) if (live(m.ent)) m.ent.Teleport({ position: m.base });
    for (const an of this.anims) if (live(an.ent)) Instance.EntFireAtTarget({ target: an.ent, input: "Skin", value: 0 });
  }
}
