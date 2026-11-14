// ===================================================================================================================
// IRONFRAME CS2 adapter, part 3: drawing with pooled props.
// Every mech is two pooled prop_dynamics from the point_template (legs + upper body, models from MODELS.frames), plus up
// to four weapon props parented to the upper body at their mounts (models.json#mounts; they ride along for free). Both body
// props are Moved every tick (client interpolation); Teleport only for jumps > TELEPORT_DIST (a spawn, a snap) and never
// 3 ticks running (CS2 stops drawing). Projectiles, missiles, beams and markers are pooled props with fx models.
// Paint: SetColor tint (the vmats carry g_flModelTintAmount 1). Far mechs (no human within FAR_DIST) move every 2nd tick.
// ===================================================================================================================
const NULL_MODEL = 'models/ifr/null.vmdl';
const HIDE_POS = v3(0, 0, -15000);
const FRAMES = /** @type {any} */ ((typeof MODELS === 'object' && MODELS && MODELS.frames) || {});
const WEAPON_MODELS = /** @type {any} */ ((typeof MODELS === 'object' && MODELS && MODELS.weapons) || {});
const FX_MODELS = /** @type {any} */ ((typeof MODELS === 'object' && MODELS && MODELS.fx) || {});
// Weapon prop origin (= its grip / mount base, tools/weapon_props.py repivot) in the upper model frame: models.json#mounts from
// tools/weapon_fit.py (arm weapons: grip at the palm; shoulder units: on the shoulder, clear of body and head) per frame and weapon,
// [right x, y, z, left x, y, z]; else the frame's hard-point. Slots 0 / 2 are the right side (ra, rs), 1 / 3 the left.
const WEAPON_MOUNTS = /** @type {any} */ ((typeof MODELS === 'object' && MODELS && MODELS.mounts && MODELS.mounts.frames) || {});
function weaponMountPos(frameKey, wkey, slot, hp) {
  const f = WEAPON_MOUNTS[frameKey], mt = f && f[wkey];
  if (mt && mt.length >= 6) { const o = (slot === 0 || slot === 2) ? 0 : 3; return [mt[o], mt[o + 1], mt[o + 2]]; }
  return hp || [0, 0, 0];
}

let propTemplate, propSerial = 0, spawnBudget = 0, propCount = 0;
const freeProps = [];
/** @typedef {{ent:any, name:string, model:string, hidden:boolean, lastPos:any, lastAng:any, tpRun:number, scale:number, color:string, parent:any, skin?:number, mnt?:any}} Prop */

function findPropTemplate() {
  propTemplate = live(propTemplate) || ifrFind(CONFIG.PROP_TEMPLATE);
  if (!propTemplate) warnOnce('tpl', 'no point_template named ' + CONFIG.PROP_TEMPLATE + ': nothing can be drawn');
  return propTemplate;
}
function newProp() {
  if (spawnBudget <= 0 || propCount >= CONFIG.MAX_POOL) return undefined;
  const tpl = findPropTemplate(); if (!tpl) return undefined;
  spawnBudget--;
  const ents = /** @type {any} */ (tpl).ForceSpawn(HIDE_POS, ZERO_ANG);
  if (!ents || !ents.length) { warnOnce('spawnfail', 'the prop template spawned nothing'); return undefined; }
  const ent = ents.find((e) => e instanceof BaseModelEntity) || ents[0];
  const name = 'ifr_p' + (++propSerial);
  guard('name', () => ent.SetEntityName(name));
  propCount++;
  return { ent, name, model: '', hidden: true, lastPos: null, lastAng: null, tpRun: 0, scale: 1, color: '', parent: undefined };
}
function takeProp() { while (freeProps.length) { const p = freeProps.pop(); if (live(p.ent)) return p; } return newProp(); }
function releaseProp(p) {
  if (!p || !live(p.ent)) return;
  guard('release', () => {
    // a prop that rode on a parent is wherever the parent took it: its lastPos (where it was parented) is stale, so the next
    // placement must be a Teleport, not a Move from a position it never had
    if (p.parent) { p.ent.SetParent(undefined); p.parent = undefined; p.lastPos = null; p.lastAng = null; }
    p.mnt = undefined;
    if (p.scale !== 1) { p.ent.SetModelScale(1); p.scale = 1; }
    if (p.color) { p.ent.SetColor({ r: 255, g: 255, b: 255, a: 255 }); p.color = ''; }
    if (p.skin) { ifrFire(p.ent, 'Skin', 0); p.skin = 0; }
    if (!p.hidden) { p.ent.SetModel(NULL_MODEL); p.model = NULL_MODEL; p.hidden = true; }   // the null model is invisible: no Teleport needed (keeps lastPos/tpRun honest)
  });
  freeProps.push(p);
}
function propModel(p, model) { if (p.model === model || !model) return; p.ent.SetModel(model); p.model = model; p.hidden = false; }
function propScale(p, s) { if (Math.abs(p.scale - s) < 0.01) return; p.ent.SetModelScale(s); p.scale = s; }
function propColor(p, rgb, a) {
  const key = rgb ? rgb[0] + ',' + rgb[1] + ',' + rgb[2] + ',' + (a === undefined ? 255 : a) : '';
  if (p.color === key) return;
  p.ent.SetColor(rgb ? { r: rgb[0], g: rgb[1], b: rgb[2], a: a === undefined ? 255 : a } : { r: 255, g: 255, b: 255, a: 255 }); p.color = key;
}
// place a prop: Move normally, Teleport for a big jump or the first placement (never 3 ticks running)
function propPlace(p, pos, ang) {
  if (!vfinite(pos)) return;
  const pp = clampWorld(pos);
  const big = !p.lastPos || vdist(p.lastPos, pp) > CONFIG.TELEPORT_DIST;
  if (big && p.tpRun < 2) { p.ent.Teleport({ position: pp, angles: ang }); p.tpRun++; }
  else { p.ent.Move({ position: pp, angles: ang }); p.tpRun = 0; }
  p.lastPos = pp; p.lastAng = ang; p.hidden = false;
}
// ---- parenting. SetParent keeps the child's WORLD offset from where the engine has the parent at that moment, so the child
// must be put at parent transform x local offset using the transform the ENGINE reports (GetAbsOrigin / GetAbsAngles), not
// the one the script last asked for: then the local offset is right wherever the parent is (parked, mid-drop, pitched, or a
// pooled prop whose placement was a Move). 10 Nov 2026 playtest: "shoulder weapons occasionally float".
// axes of a QAngle (Source AngleVectors): forward, left, up
function angAxes(a) {
  const p = (a.pitch || 0) * D2R, y = (a.yaw || 0) * D2R, r = (a.roll || 0) * D2R;
  const sp = Math.sin(p), cp = Math.cos(p), sy = Math.sin(y), cy = Math.cos(y), sr = Math.sin(r), cr = Math.cos(r);
  return { f: v3(cp * cy, cp * sy, -sp), l: v3(sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, sr * cp), u: v3(cr * sp * cy + sr * sy, cr * sp * sy - sr * cy, cr * cp) };
}
// the engine's transform of a prop (falls back to what the script last set)
function propXform(prop) {
  let o, a;
  try { o = prop.ent.GetAbsOrigin(); a = prop.ent.GetAbsAngles(); } catch (err) { o = undefined; }
  if (!vfinite(o) || !a || !Number.isFinite(a.yaw)) { o = prop.lastPos; a = prop.lastAng || ZERO_ANG; }
  return vfinite(o) ? { o, a } : null;
}
// world position of a point `l` ([x, y, z] in the parent's model frame) under a transform
function xformPoint(x, l) {
  const ax = angAxes(x.a), o = x.o;
  return v3(o.x + ax.f.x * l[0] + ax.l.x * l[1] + ax.u.x * l[2], o.y + ax.f.y * l[0] + ax.l.y * l[1] + ax.u.y * l[2], o.z + ax.f.z * l[0] + ax.l.z * l[1] + ax.u.z * l[2]);
}
// parent p to parentProp at the local offset `local` (the parent's model frame), same angles as the parent
function propParentLocal(p, parentProp, local) {
  if (p.parent === parentProp) return true;
  const x = propXform(parentProp); if (!x) return false;
  const pos = clampWorld(xformPoint(x, local));
  p.ent.Teleport({ position: pos, angles: { pitch: x.a.pitch || 0, yaw: x.a.yaw || 0, roll: x.a.roll || 0 } }); p.lastPos = pos; p.tpRun = 0;
  p.ent.SetParent(parentProp.ent); p.parent = parentProp;
  p.mnt = { local: [local[0], local[1], local[2]], at: pos, parentAt: x.o, t: gameTime() };
  return true;
}
// the older call: a world position and angles, meant for where the script last PLACED the parent (lastPos / lastAng)
function propParent(p, parentProp, pos, ang) {
  if (p.parent === parentProp) return;
  const po = parentProp.lastPos, pa = parentProp.lastAng || ang || ZERO_ANG;
  if (vfinite(po) && vfinite(pos)) {
    const ax = angAxes(pa), d = vsub(pos, po);
    if (propParentLocal(p, parentProp, [d.x * ax.f.x + d.y * ax.f.y + d.z * ax.f.z, d.x * ax.l.x + d.y * ax.l.y + d.z * ax.l.z, d.x * ax.u.x + d.y * ax.u.y + d.z * ax.u.z])) return;
  }
  p.ent.Teleport({ position: clampWorld(pos), angles: ang }); p.lastPos = pos; p.tpRun = 0;
  p.ent.SetParent(parentProp.ent); p.parent = parentProp;
}

// ---------------------------------------------------------------- mechs
/** @typedef {{slot:number, key:string, fr:any, legs:Prop|undefined, upper:Prop|undefined, weapons:(Prop|undefined)[], paint:number[]|null, far:boolean, wreckT:number, lastHip:number, glowing:boolean, upHid?:boolean, gibbed?:boolean, dmgSmoke?:boolean, dmgNext?:number, legsClip:string, upperClip:string, legsUntil:number, upperUntil:number, iff?:Prop, dyn?:any, loco?:any, legsRate?:number, upperRate?:number, legsPh?:number, legsT0?:number, want?:boolean, mountOk?:boolean}} MechRig */
/** @type {Map<number, MechRig>} */
const rigs = new Map();
const PAINTS = {};
for (const p of (PARTS.parts || [])) if (p.kind === 'paint') PAINTS[p.id] = p.tint;

function frameModel(m) {
  const fr = FRAMES[m.frame && m.frame.model];
  return fr || null;
}
function renderUpperEnt(slot) { const r = rigs.get(slot); return r && r.upper ? live(r.upper.ent) : undefined; }
function renderUpperProp(slot) { const r = rigs.get(slot); return r ? r.upper : undefined; }
// Both split models (legs, upper) keep the feet origin, so both are placed at the mech position. The hip height is only
// for the camera and the crosshair ray: the frame's hip_z when it is plausible (hand-held weapons owned by upper bones
// make it too low on some AC rigs), else 45 % of the class height.
function renderHipZ(m) {
  const fr = frameModel(m); const h = m.cls ? m.cls.height : 288;
  const hz = fr && Number.isFinite(fr.hip_z) ? fr.hip_z : 0;
  return Math.max(hz, h * 0.45);
}
function renderUpperPos(m) { return v3(m.pos.x, m.pos.y, m.pos.z + renderHipZ(m)); }

function renderClaimMech(m) {
  let r = rigs.get(m.slot);
  if (r && r.key === (m.frame && m.frame.model)) { if (r.want) rigFill(r, m); return r; }
  if (r) renderDropMech(m.slot);
  const key = m.frame && m.frame.model;
  const fr = FRAMES[key];
  r = { slot: m.slot, key, fr, legs: undefined, upper: undefined, weapons: [undefined, undefined, undefined, undefined], paint: null, far: false, wreckT: 0, lastHip: 0, glowing: false, legsClip: '', upperClip: '', legsUntil: 0, upperUntil: 0, want: true, mountOk: false };
  if (!fr) { warnOnce('frame ' + key, 'no model for frame ' + key + ': drawn as a placeholder'); }
  const paintId = m.loadout ? m.loadout[8] : 0;
  r.paint = PAINTS[paintId] || null;
  rigFill(r, m);
  rigs.set(m.slot, r);
  return r;
}
// Takes the props a rig still lacks (body halves, then a prop per mounted weapon). The pool hands out SPAWN_BUDGET new props a
// tick, so at a round start most rigs are filled over a few ticks: until 10 Nov 2026 a prop the pool could not give at claim
// time was never asked for again (a mech without its upper body or a weapon for the rest of its life).
function rigFill(r, m) {
  const fr = r.fr, pv0 = fr && fr.pivot;
  let want = false;
  if (!r.upper) {
    r.upper = takeProp();
    if (r.upper) {
      propModel(r.upper, (fr && fr.upper) || FX_MODELS.placeholder || NULL_MODEL);
      propPlace(r.upper, pv0 ? pivotOrigin(m.pos, m.torsoYaw, pv0) : m.pos, { pitch: 0, yaw: m.torsoYaw, roll: 0 });
      if (r.paint) propColor(r.upper, r.paint);
    } else want = true;
  }
  if (fr && fr.legs && !r.legs) {
    r.legs = takeProp();
    if (r.legs) {
      propModel(r.legs, fr.legs);
      propPlace(r.legs, pv0 ? pivotOrigin(m.pos, m.legYaw, pv0) : m.pos, { pitch: 0, yaw: m.legYaw, roll: 0 });
      if (r.paint) propColor(r.legs, r.paint);
    } else want = true;
  }
  // weapons ride on the upper body at their mount (models.json#mounts, in the upper model's own frame): propParentLocal reads
  // the upper's transform from the engine, so it does not matter where the upper is or how it is turned at this moment
  if (r.upper && !r.upHid && !r.gibbed && m.alive) {
    const hp = (fr && fr.hardpoints) || { ra: [40, -70, 60], la: [40, 70, 60], rs: [-20, -50, 120], ls: [-20, 50, 120] };
    const keys = ['ra', 'la', 'rs', 'ls'];
    for (let i = 0; i < 4; i++) {
      if (r.weapons[i]) continue;
      const w = m.weapons[i] && m.weapons[i].part;
      const model = w && WEAPON_MODELS[w.key];
      if (!model) continue;
      const wp = takeProp(); if (!wp) { want = true; continue; }
      propModel(wp, model);
      { const ac = typeof srvAccentOf === 'function' ? srvAccentOf(m.slot) : null; if (ac) propColor(wp, ac); }      // the loadout's accent colour (70_server.js)
      if (propParentLocal(wp, r.upper, weaponMountPos(r.key, w.key, i, hp[keys[i]]))) r.weapons[i] = wp;
      else { releaseProp(wp); want = true; }
    }
  } else if (!r.upper) want = true;
  r.want = want;
}
// One look per rig, once the mech has moved: is every weapon where its mount says, by the engine's own numbers? A weapon found
// off its mount is said once in the log (evidence for the next playtest) and parented again. Where a parented child's reported
// origin does not follow its parent (the offline mock), the check turns itself off.
let mountCheckOff = false;
function rigMountCheck(r) {
  if (mountCheckOff || r.mountOk || r.want || !r.upper || r.upHid) return;
  const x = propXform(r.upper); if (!x) return;
  let done = true;
  for (let i = 0; i < 4; i++) {
    const wp = r.weapons[i]; if (!wp || !wp.mnt || !live(wp.ent)) continue;
    if (gameTime() < wp.mnt.t + 1 || vdist(x.o, wp.mnt.parentAt) < 48) { done = false; continue; }   // not moved yet: nothing to learn
    let got; try { got = wp.ent.GetAbsOrigin(); } catch (err) { got = undefined; }
    if (!vfinite(got)) continue;
    if (vdist(got, wp.mnt.at) < 1) { mountCheckOff = true; return; }
    const off = vdist(got, xformPoint(x, wp.mnt.local));
    if (off > 8) {
      warnOnce('mount ' + r.key + ' ' + i, 'weapon mount drift: frame ' + r.key + ' slot ' + i + ' model ' + wp.model + ' was ' + off.toFixed(0) + ' u off its mount (parented again)');
      const local = wp.mnt.local;
      wp.ent.SetParent(undefined); wp.parent = undefined;
      propParentLocal(wp, r.upper, local);
    }
  }
  if (done) r.mountOk = true;
}
function renderDropMech(slot) {
  const r = rigs.get(slot); if (!r) return;
  // effects first: boosters and trails are parented to the upper prop, and releasing it moves it under the map (HIDE_POS), so
  // they used to ride along there for a tick ("ifr_pfx_boost_NNN ... outside of cell bounds", 11 Nov 2026 console)
  fxMechGone(slot);
  if (r.iff) { releaseProp(r.iff); r.iff = undefined; }
  for (const w of r.weapons) if (w) releaseProp(w);
  // a body half given back is Teleported by its next user (not Moved from here: it would slide in with its weapons)
  if (r.legs) { r.legs.lastPos = null; releaseProp(r.legs); }
  if (r.upper) { r.upper.lastPos = null; releaseProp(r.upper); }
  rigs.delete(slot);
}
// is any human's camera near this position? (far mechs are drawn at half rate, effects skipped)
function nearHuman(pos, dist) {
  for (const pe of people.values()) {
    if (!pe.human) continue;
    const m = game.mechs.get(pe.slot);
    const p = m ? m.pos : (pe.deathPos || null);
    if (p && vdist(p, pos) < dist) return true;
  }
  return false;
}
// ---- clips (models.json frames[k].anims {legs:[...], upper:[...]}, anim_len {clip: s}): loops follow the mech's state,
// one-shots (land, qb_l/qb_r, fire_r/fire_l/fire_s, stagger) play for their length, then the loop comes back. Inputs are
// sent only when the clip changes.
function rigHas(r, part, clip) { const a = r.fr && r.fr.anims; return !!(a && a[part] && a[part].indexOf(clip) >= 0); }
function rigClip(r, part, clip, loop) {
  const prop = part === 'legs' ? r.legs : r.upper;
  if (!prop || !live(prop.ent) || !rigHas(r, part, clip)) return;
  const key = part === 'legs' ? 'legsClip' : 'upperClip';
  if (r[key] === clip && loop) return;
  r[key] = clip;
  if (part === 'legs') { r.legsPh = 0; r.legsT0 = gameTime(); }
  ifrFire(prop.ent, loop ? 'SetAnimationLooping' : 'SetAnimationNotLooping', clip);
}
function rigOneShot(slot, part, clip) {
  const r = rigs.get(slot); if (!r || !rigHas(r, part, clip)) return;
  const len = (r.fr.anim_len && r.fr.anim_len[clip]) || 0.4;
  if (part === 'legs') r.legsUntil = gameTime() + len; else r.upperUntil = gameTime() + len;
  guard('clip', () => { rigRate(r, part, 1); rigClip(r, part, clip, false); });   // one-shots at their natural rate (len, hip curve)
}
// Locomotion: the legs clip is chosen from the movement (walk / run by speed, walk_back / strafe_l / strafe_r by the angle
// between the velocity and the legs' facing), the matching upper sway starts with it (both clips move the hips by the same
// drop, so they must play together at the same rate), and the playback rate follows ground speed / the clip's natural
// speed (models.json stride) so the feet don't slide. Upper one-shots (fire recoils) are skipped while walking: they
// don't carry the hip drop and would part the body at the waist.
function rigLocoClip(r, m, sp) {
  const S = r.fr && r.fr.stride;
  if (!S || !S.walk || !rigHas(r, 'legs', 'walk')) return null;
  const va = Math.atan2(m.vel.y, m.vel.x) * R2D, rel = angleDiff(m.legYaw, va);
  let clip = 'walk';
  if (Math.abs(rel) > 125 && rigHas(r, 'legs', 'walk_back')) clip = 'walk_back';
  else if (Math.abs(rel) > 55 && Math.abs(rel) <= 125) clip = rel > 0 ? (rigHas(r, 'legs', 'strafe_l') ? 'strafe_l' : 'walk') : (rigHas(r, 'legs', 'strafe_r') ? 'strafe_r' : 'walk');
  else if (S.run && sp > (S.walk.speed + S.run.speed) * 0.5 && rigHas(r, 'legs', 'run')) clip = 'run';
  const st = S[clip] || S.walk;
  const rate = Math.max(0.4, Math.min(2.4, sp / Math.max(40, st.speed || 180)));
  return { clip, rate: Math.round(rate * 20) / 20, period: st.period || 1, steps: (r.fr.steps && (r.fr.steps[clip] || r.fr.steps.walk)) || [0.4, 0.9],
    sway: (r.fr.sway && r.fr.sway[clip]) || (clip === 'run' ? 'run_sway' : 'walk_sway') };
}
function rigRate(r, part, rate) {
  const prop = part === 'legs' ? r.legs : r.upper; if (!prop || !live(prop.ent)) return;
  const key = part === 'legs' ? 'legsRate' : 'upperRate';
  if (Math.abs((r[key] || 1) - rate) < 0.05) return;
  r[key] = rate; ifrFire(prop.ent, 'SetPlaybackRate', rate);
}
const IFR_ARMED_SWAY = false;   // arm swing while walking with a hand weapon mounted (see rigAnimate)
function rigAnimate(r, m) {
  const now = gameTime();
  const sp = Math.sqrt(m.vel.x * m.vel.x + m.vel.y * m.vel.y);
  const walking = m.onGround && !m.boosting && sp > 60;
  const loco = walking ? rigLocoClip(r, m, sp) : null;
  r.loco = loco;
  if (r.legs && now >= (r.legsUntil || 0)) {
    if (loco) {
      const changed = r.legsClip !== loco.clip;
      rigClip(r, 'legs', loco.clip, true); rigRate(r, 'legs', loco.rate);
      // The arm swing of the *_sway clips takes the palms 13-66 u off the grips (docs/WEAPON_FIT.md, hands drift): the weapon
      // props are rigid on the upper body, they do not follow the hand bones. A mech holding a hand weapon therefore keeps the
      // idle upper clip while it walks (steady guns; fire recoils play as when standing). No upper clip moves the torso (the
      // hip motion is the script's, rigHip), so the halves stay joined either way. IFR_ARMED_SWAY = true brings the swing back.
      if (IFR_ARMED_SWAY || !(r.weapons[0] || r.weapons[1])) {
        if (changed || r.upperClip !== loco.sway) { r.upperUntil = 0; if (rigHas(r, 'upper', loco.sway)) { r.upperClip = ''; rigClip(r, 'upper', loco.sway, true); } }
        if (rigHas(r, 'upper', loco.sway)) rigRate(r, 'upper', loco.rate);
        return;
      }
    } else {
      rigClip(r, 'legs', !m.onGround ? (m.boosting ? 'boost' : 'air') : m.boosting ? 'boost' : sp > 80 && rigHas(r, 'legs', 'move') ? 'move' : 'hover', true);
      rigRate(r, 'legs', 1);
    }
  }
  if (now >= (r.upperUntil || 0)) { rigClip(r, 'upper', 'idle', true); rigRate(r, 'upper', 1); }
}
// ---- weight: the props lean into acceleration and braking, roll into strafes and turns, drop at the hips on every
// footfall (the stride from models.json frames[k].stride when there is one), compress on landing and flinch when hit.
// Footfalls make a stomp, a camera bump for the pilot and close by. Everything decays smoothly (no clip needed).
const IFR_W_STEP_AMP = { light: 7, medium: 10, heavy: 14, boss: 24 };
// ---- hip motion out of the clips (models.json hip_curve / sway_curve, written by create/mech_anim.py): the legs clips keep the
// pelvis on the origin and solve the feet against this curve, so the script moves BOTH props by it (vertical dip, lateral
// sway) in step with the clip. Loops: 16 samples over the clip, periodic Catmull-Rom; one-shots (land, qb_l, qb_r): 16
// samples at i/15 of the clip length. The phase follows the rate the engine was given (r.legsRate).
const IFR_LOOP_CURVES = { walk: 1, walk_back: 1, strafe_l: 1, strafe_r: 1, run: 1 };
function ifrCatmull(s, u, periodic) {
  const n = s.length; if (!n) return 0;
  const at = (k) => periodic ? s[((k % n) + n) % n] : s[Math.max(0, Math.min(n - 1, k))];
  const i = Math.floor(u), t = u - i;
  const p0 = at(i - 1), p1 = at(i), p2 = at(i + 1), p3 = at(i + 2);
  return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t);
}
function rigHip(r, dt) {
  const fr = r.fr, clip = r.legsClip; if (!fr || !fr.hip_curve || !clip) return null;
  const hc = fr.hip_curve[clip]; if (!hc) return null;
  const sc = fr.sway_curve && fr.sway_curve[clip];
  const len = Math.max(0.05, (fr.anim_len && fr.anim_len[clip]) || 1);
  if (IFR_LOOP_CURVES[clip]) {
    r.legsPh = ((r.legsPh || 0) + dt * (r.legsRate || 1) / len) % 1;
    const u = r.legsPh * hc.length;
    return { z: ifrCatmull(hc, u, true), y: sc ? ifrCatmull(sc, u, true) : 0 };
  }
  const t = Math.min(1, (gameTime() - (r.legsT0 || 0)) * (r.legsRate || 1) / len);
  const u = t * (hc.length - 1);
  return { z: ifrCatmull(hc, u, false), y: sc ? ifrCatmull(sc, u, false) : 0 };
}
function rigWeight(r, m) {
  const dt = (r.far ? 2 : 1) / 64;
  const d = r.dyn || (r.dyn = { vx: m.vel.x, vy: m.vel.y, lean: 0, roll: 0, yaw: m.legYaw, phase: 0, half: 0, comp: 0, compV: 0, fl: 0, flRoll: 0 });
  const ax = (m.vel.x - d.vx) / dt, ay = (m.vel.y - d.vy) / dt; d.vx = m.vel.x; d.vy = m.vel.y;
  const f = fwdOf(m.legYaw, 0), rt = rightOf(m.legYaw);
  const af = ax * f.x + ay * f.y, as = ax * rt.x + ay * rt.y;
  const sp = Math.sqrt(m.vel.x * m.vel.x + m.vel.y * m.vel.y), turn = angleDiff(d.yaw, m.legYaw) / dt; d.yaw = m.legYaw;
  const cls = (m.cls && m.cls.key) || (m.frame && m.frame.class) || 'medium', heavy = cls === 'heavy' || cls === 'boss';
  const k = heavy ? 0.75 : cls === 'light' ? 1.25 : 1;
  const leanT = Math.max(-9, Math.min(9, af / 2600 * 7 * k)) + (m.boosting && sp > 500 ? 9 : 0) + (!m.onGround ? 3 : 0);
  const rollT = Math.max(-10, Math.min(10, as / 2600 * 7 * k + turn * 0.03));
  const a = 1 - Math.exp(-dt / (heavy ? 0.22 : 0.14));
  d.lean += (leanT - d.lean) * a; d.roll += (rollT - d.roll) * a;
  let bob = 0;
  if (r.loco) {
    const prev = d.phase % 1;
    d.phase += dt * r.loco.rate / Math.max(0.2, r.loco.period);
    const cur = d.phase % 1;
    for (const f of r.loco.steps) if ((prev <= cur && f > prev && f <= cur) || (prev > cur && (f > prev || f <= cur))) rigFootfall(r, m, cls);
  } else if (m.onGround && !m.boosting && sp > 60) {
    const sw = r.fr && r.fr.stride && r.fr.stride.walk;
    const stride = (sw && (typeof sw === 'number' ? sw : sw.length)) || ((m.cls && m.cls.height) || 288) * 1.15;
    d.phase += dt * sp / Math.max(60, stride);
    const half = Math.floor(d.phase * 2);
    if (half !== d.half) { d.half = half; rigFootfall(r, m, cls); }
    const s = d.phase * 2 - half;                        // 0..1 within a step: down right after the plant, up mid-step
    bob = -(IFR_W_STEP_AMP[cls] || 10) * Math.max(0, Math.cos(s * Math.PI)) * Math.min(1, sp / 300);
  } else if (m.onGround && !m.boosting && Math.abs(turn) > 35) {
    // turning on the spot (the legs dragged round by the torso limit, core leg_twist): it shifts its weight and plants a foot
    // every ~40 degrees, so a standing turn is steps and not a turntable (11 Nov 2026, list item A)
    d.phase += dt * Math.min(240, Math.abs(turn)) / 80;
    const half = Math.floor(d.phase * 2);
    if (half !== d.half) { d.half = half; rigFootfall(r, m, cls); }
    bob = -(IFR_W_STEP_AMP[cls] || 10) * 0.6 * Math.max(0, Math.cos((d.phase * 2 - half) * Math.PI));
  } else d.half = Math.floor(d.phase * 2);
  // body language at the start of a move: a crouch into the boost, a push off the ground at take-off (the spring brings it back)
  const air = !m.onGround;
  if (m.boosting && !d.wasBoost && !air) d.compV -= heavy ? 210 : 160;
  if (air && d.wasAir === false && m.vel.z > 120) d.compV -= heavy ? 170 : 130;
  d.wasBoost = !!m.boosting; d.wasAir = air;
  d.compV += (-d.comp * 90 - d.compV * 14) * dt; d.comp += d.compV * dt;   // landing compression: a damped spring
  d.fl *= Math.exp(-dt / 0.09); d.flRoll *= Math.exp(-dt / 0.09);
  return { pitch: d.lean + d.fl, roll: d.roll + d.flRoll, dz: bob + d.comp };
}
function rigFootfall(r, m, cls) {
  if (!r.legs || !r.legs.lastPos) return;
  sndOn(cls === 'light' ? 'step_light' : cls === 'medium' ? 'step_medium' : 'step_heavy', r.legs);
  const strength = cls === 'heavy' || cls === 'boss' ? 1 : cls === 'medium' ? 0.65 : 0.4;
  for (const pe of people.values()) {
    if (!pe.human) continue;
    const pm = game.mechs.get(pe.slot); if (!pm) continue;
    const dd = vdist(pm.pos, m.pos);
    if (pe.slot === m.slot) camKick(pe.slot, 0, -9 * strength, 0);
    else if (dd < 1600) camKick(pe.slot, 0, -5 * strength * (1 - dd / 1600), 0);
  }
}
/** a quick boost throws the body: a roll into the dash (side +1 = left) and a dip; both decay by themselves */
function rigDash(slot, side) { const r = rigs.get(slot); if (!r || !r.dyn) return; r.dyn.flRoll += -side * 7; r.dyn.compV -= 140; }
function rigLand(slot, hard) { const r = rigs.get(slot); if (!r || !r.dyn) return; r.dyn.compV -= hard ? 520 : 220; }
function rigFlinch(slot, impact, from) {
  const r = rigs.get(slot); if (!r || !r.dyn) return; const d = r.dyn;
  const m = game.mechs.get(slot); const amt = Math.min(7, 1.2 + (impact || 0) / 160);
  let side = Math.random() < 0.5 ? -1 : 1;
  if (m && from) { const rt = rightOf(m.torsoYaw); side = ((from.x - m.pos.x) * rt.x + (from.y - m.pos.y) * rt.y) > 0 ? -1 : 1; }
  d.fl -= amt * 0.6; d.flRoll += side * amt;
}
// the waist joint's height in the model frame: models.json waist_z (the pelvis bone; tools/frames.py), else the lowest point of the upper
// model (hip_z, which is the hands on a frame with long arms) kept between 40 and 60 % of the class height
function waistZ(m, fr) {
  if (fr && Number.isFinite(fr.waist_z) && fr.waist_z > 20) return fr.waist_z;
  const h = m.cls ? m.cls.height : 288, hz = fr && Number.isFinite(fr.hip_z) ? fr.hip_z : 0;
  return Math.max(0.4 * h, Math.min(0.6 * h, hz));
}
// a model-frame vector (x forward, y left, z up) turned by Source angles (pitch + = nose down, roll + = top to the right): AngleVectors
function angRot(a, v) {
  const p = (a.pitch || 0) * D2R, y = (a.yaw || 0) * D2R, r = (a.roll || 0) * D2R;
  const sp = Math.sin(p), cp = Math.cos(p), sy = Math.sin(y), cy = Math.cos(y), sr = Math.sin(r), cr = Math.cos(r);
  const fx = cp * cy, fy = cp * sy, fz = -sp;
  const lx = sr * sp * cy - cr * sy, ly = sr * sp * sy + cr * cy, lz = sr * cp;
  const ux = cr * sp * cy + sr * sy, uy = cr * sp * sy - sr * cy, uz = cr * cp;
  return v3(fx * v[0] + lx * v[1] + ux * v[2], fy * v[0] + ly * v[1] + uy * v[2], fz * v[0] + lz * v[1] + uz * v[2]);
}
function pivotOrigin(p, yaw, pv) {
  const c = Math.cos(yaw * D2R), sn = Math.sin(yaw * D2R);
  return v3(p.x - (c * pv[0] - sn * pv[1]), p.y - (sn * pv[0] + c * pv[1]), p.z);
}
// ---- IFF marker: a diamond hovering over each live mech near a human, tinted by team; bounty targets and flag carriers
// are bigger and pulse (scale step every 8 ticks)
const IFF_COLORS = { T: [255, 150, 40], CT: [60, 220, 255], red: [255, 50, 50] };
function iffColor(m) {
  let mode = 'tb'; try { mode = game.matchFor(m.slot).mode; } catch (e) { /* default */ }
  if (mode === 'sk') return IFF_COLORS.red;
  // Sortie is co-op: the wave (team 0) is red, every pilot and AI ally is friendly cyan (all AI, allies included, used to be red:
  // 10 Nov 2026 playtest, "it doesnt seem to show who is an enemy and who is friendly")
  if (mode === 'so') return m.team === TEAM_T || m.team === TEAM_CT ? IFF_COLORS.CT : IFF_COLORS.red;
  return m.team === TEAM_CT ? IFF_COLORS.CT : IFF_COLORS.T;
}
function renderIff(m, r) {
  const hot = m.streak >= 5 || m.carrier;
  const sc = hot ? ((ifrTickNo >> 3) & 1 ? 1.9 : 1.5) : 1;
  // a pilot's own marker is kept off their reticle (40_fx.js iffPlace; 10 Nov 2026 playtest)
  const pos = m.alive && !r.far ? iffPlace(m, v3(m.pos.x, m.pos.y, m.pos.z + (m.cls ? m.cls.height : 288) + 40 + 30 * sc)) : null;
  if (!pos || !FX_MODELS.iff) { if (r.iff) { releaseProp(r.iff); r.iff = undefined; } return; }
  if (!r.iff) { r.iff = takeProp(); if (!r.iff) return; }
  const ic = iffColor(m);   // the self-lit material ignores SetColor: pick the pre-coloured model instead
  propModel(r.iff, (ic === IFF_COLORS.CT ? FX_MODELS.iff_ct : ic === IFF_COLORS.red ? FX_MODELS.iff_red : FX_MODELS.iff_t) || FX_MODELS.iff);
  propScale(r.iff, sc);
  propPlace(r.iff, pos, { pitch: 0, yaw: (ifrTickNo * 4) % 360, roll: 0 });
}
function renderMech(m) {
  const r = renderClaimMech(m);
  if (!r.upper) return;
  r.far = !nearHuman(m.pos, CONFIG.FAR_DIST);
  guard('iff', () => renderIff(m, r));
  if (r.far && ((ifrTickNo + m.slot) & 1)) return;
  let legAng = { pitch: 0, yaw: m.legYaw, roll: 0 };
  let upAng = { pitch: -m.pitch * 0.5, yaw: m.torsoYaw, roll: 0 };
  let legPos = m.pos, upPos = m.pos;
  let dzJoin = 0;
  if (m.alive) guard('weight', () => { const w = rigWeight(r, m); legAng.pitch += w.pitch * 0.35; legAng.roll += w.roll * 0.45;
    // the lean is measured along the legs; the upper body takes it in its own frame (it may be turned up to ~65 deg from the legs)
    { const dy = angleDiff(m.torsoYaw, m.legYaw) * D2R, c = Math.cos(dy), s = Math.sin(dy);
      upAng.pitch += w.pitch * c + w.roll * s; upAng.roll += -w.pitch * s + w.roll * c; }
    dzJoin = w.dz * 0.65;
    const h = rigHip(r, (r.far ? 2 : 1) / 64);      // the clip's hip dip + sway moves both halves together
    let hx = 0, hy = 0, hz = 0;
    if (h) { const ly = m.legYaw * D2R; hz = h.z; hx = -Math.sin(ly) * h.y; hy = Math.cos(ly) * h.y; }
    const so = Number.isFinite(m.stepOff) ? m.stepOff : 0;   // a step just taken is eased in (core 20_mech.js stepOff; the camera follows the upper prop)
    upPos = v3(m.pos.x + hx, m.pos.y + hy, m.pos.z + hz + w.dz + so); legPos = v3(m.pos.x + hx, m.pos.y + hy, m.pos.z + hz + w.dz * 0.35 + so); });
  if (!m.alive) {   // a wreck: tilts and sinks for the death camera seconds
    const t = Math.min(1, (gameTime() - (m.deathT || gameTime())) / CONFIG.DEATH_CAM_SECONDS);
    legAng = { pitch: 0, yaw: m.legYaw, roll: 35 * t }; upAng = { pitch: 25 * t, yaw: m.torsoYaw, roll: 40 * t };
    upPos = v3(m.pos.x, m.pos.y, m.pos.z - 60 * t); legPos = v3(m.pos.x, m.pos.y, m.pos.z - 20 * t);
  }
  // both halves turn about the frame's waist pivot (models.json frames[k].pivot, model-frame x/y), not the model origin,
  // so legs and upper body stay joined whatever their yaws
  const pv = (r.fr && r.fr.pivot) || null;
  if (pv) { legPos = pivotOrigin(legPos, legAng.yaw, pv); upPos = pivotOrigin(upPos, upAng.yaw, pv); }
  // ... and they stay joined at the WAIST whatever their pitch and roll: each prop turns about its own origin at the feet, so a lean, the
  // aim pitch or a flinch used to swing the upper body 20-40 u off the legs at hip height (10 Nov 2026 playtest: "legs being
  // disconnected"). The upper prop is placed so that its waist point (pivot x / y at hip height) sits on the legs' waist point.
  if (m.alive && r.legs && !r.upHid) {
    const wz = waistZ(m, r.fr), J = [pv ? pv[0] : 0, pv ? pv[1] : 0, wz];
    const a = angRot(legAng, J), b = angRot(upAng, J);
    upPos = v3(legPos.x + a.x - b.x, legPos.y + a.y - b.y, legPos.z + a.z - b.z + dzJoin);
  }
  if (r.legs) propPlace(r.legs, legPos, legAng);
  if (!r.upHid) propPlace(r.upper, upPos, upAng);
  if (!r.mountOk && m.alive) guard('mount check', () => rigMountCheck(r));
  guard('skin', () => rigDamageSkin(r, m));
  if (m.alive && r.fr && r.fr.anims) guard('anim', () => rigAnimate(r, m));
  if (m.protect > 0 && r.upper && !r.glowing) { guard('glow', () => r.upper.ent.Glow({ r: 120, g: 200, b: 255, a: 255 })); r.glowing = true; }
  else if (!(m.protect > 0) && r.glowing) { guard('unglow', () => r.upper.ent.Unglow()); r.glowing = false; }
}

// ---------------------------------------------------------------- projectiles, missiles, beams, markers
const fxProps = { tracer: [], missile: [], beam: [], ring: [] };    // kind -> Prop[] in use (index = pool entity index)
const fxUsed = new Map();   // core object -> Prop
const fxPoolOf = new Map();   // core object -> pool kind it was drawn by
function renderPooled(list, kind, model, place) {
  // mark and sweep: every alive core object near a human gets a prop (up to the cap); dead ones give theirs back
  const cap = CONFIG.FX[kind] || 48;
  const seen = new Set();
  let n = 0;
  for (const o of list) {
    if (!o || !o.alive) continue;
    const pos = o.pos || o.from;
    if (!pos || !nearHuman(pos, CONFIG.FX.fxDist)) continue;
    if (n++ >= cap) break;
    let p = fxUsed.get(o);
    if (!p) { p = takeProp(); if (!p) continue; propModel(p, model); fxUsed.set(o, p); fxPoolOf.set(o, kind); }
    seen.add(o);
    place(p, o);
  }
  for (const [o, p] of fxUsed) if (fxPoolOf.get(o) === kind && !seen.has(o)) { if (kind === 'missile') missileFxStop(o); releaseProp(p); fxUsed.delete(o); fxPoolOf.delete(o); }
}
// ---- beams (laser rifle, laser cannon, rail, sniper, drones). CS2 scales a prop uniformly, so one bar scaled to the shot's
// length got wider with range: 84 u wide at 2 600 u, and l / 180 on a 100 u model also stopped at 56 % of the way (10 Nov 2026
// playtest: "the lasers have a large width"). Now tools/fx.py builds a ladder of fixed-length beams per colour (models.json#fx
// beam_c_<L> cyan / beam_r_<L> red, L = 64 .. 11 585 u in x1.41 steps, 0..L along +x: a thin self-lit core in additive glow
// shells, tapered at both ends). beamPick takes the rung nearest length / width on a log scale and scales it to the exact
// length: the scale, and so the width, stays within 0.84-1.19 of the wanted width whatever the range.
const BEAM_W_MAX = 1.5, BEAM_TAIL = 0.045, BEAM_TAIL_W = 0.7;
const BEAM_LADDERS = (() => {
  /** @type {{c: {len:number, model:string}[], r: {len:number, model:string}[]}} */
  const lad = { c: [], r: [] };
  for (const k of Object.keys(FX_MODELS)) {
    const mt = /^beam_([cr])_(\d+)$/.exec(k);
    if (mt && typeof FX_MODELS[k] === 'string' && +mt[2] > 0) lad[mt[1]].push({ len: +mt[2], model: FX_MODELS[k] });
  }
  lad.c.sort((a, b) => a.len - b.len); lad.r.sort((a, b) => a.len - b.len);
  return lad;
})();
function beamPick(lad, l, w) {
  const want = Math.max(1, l) / Math.max(0.5, w || 1);
  let best = lad[0], bd = Infinity;
  for (const r of lad) { const dd = Math.abs(Math.log(r.len / want)); if (dd < bd) { bd = dd; best = r; } }
  return { model: best.model, scale: Math.max(0.5, Math.min(1.8, l / best.len)) };
}
function renderProjectiles() {
  const tracer =FX_MODELS.tracer || NULL_MODEL, heavy = FX_MODELS.tracer_heavy || tracer, missile = FX_MODELS.missile || NULL_MODEL;
  const beam = FX_MODELS.beam || NULL_MODEL, beamRed = FX_MODELS.beam_red || beam;
  if (game.missiles) renderPooled(game.missiles, 'missile', missile, (p, o) => {
    const d = o.dir || v3(1, 0, 0);
    propPlace(p, o.pos, { pitch: -Math.asin(Math.max(-1, Math.min(1, d.z))) * R2D, yaw: Math.atan2(d.y, d.x) * R2D, roll: 0 });
    if (!missileFx.has(o)) missileFxStart(o, p);
  });
  if (game.projectiles) renderPooled(game.projectiles, 'tracer', tracer, (p, o) => {
    if (o.heavy) propModel(p, heavy);
    const d = o.dir || v3(1, 0, 0);
    propScale(p, o.heavy ? 3.2 : 2.2);   // tracers read from 100 m away: bigger than life
    propPlace(p, o.pos, { pitch: -Math.asin(Math.max(-1, Math.min(1, d.z))) * R2D, yaw: Math.atan2(d.y, d.x) * R2D, roll: 0 });
  });
  if (game.beams) renderPooled(game.beams, 'beam', '', (p, o) => {   // '' = no model at the claim: the rung is picked here
    const d = vsub(o.to, o.from), l = Math.max(1, vlen(d)), dn = vmul(d, 1 / l);
    const lad = o.red ? (BEAM_LADDERS.r.length ? BEAM_LADDERS.r : BEAM_LADDERS.c) : (BEAM_LADDERS.c.length ? BEAM_LADDERS.c : BEAM_LADDERS.r);
    if (lad.length) {
      // width: 1 normally, up to BEAM_W_MAX when the core marks the shot (o.w: a full charge, a cannon), and thinned
      // out for its last ticks so it fades instead of popping off
      let w = Math.max(1, Math.min(BEAM_W_MAX, +o.w || 1));
      if (o.life > 0 && o.life < BEAM_TAIL) w *= BEAM_TAIL_W;
      const pk = beamPick(lad, l, w);
      propModel(p, pk.model); propScale(p, pk.scale);
    } else {   // a build without the ladder (models.json#fx beam_c_* / beam_r_*): the old single bar
      propModel(p, o.red ? beamRed : beam);
      propScale(p, Math.max(0.2, Math.min(60, l / 180)));
    }
    propPlace(p, o.from, { pitch: -Math.asin(Math.max(-1, Math.min(1, dn.z))) * R2D, yaw: Math.atan2(dn.y, dn.x) * R2D, roll: 0 });
  });
  if (game.effects) renderPooled(game.effects, 'ring', FX_MODELS.ring || NULL_MODEL, (p, o) => {
    if (o.kind === 'crate') return featCratePlace(p, o);
    if (o.kind === 'drone' || o.kind === 'mine') {
      propModel(p, (o.kind === 'drone' ? FX_MODELS.drone : FX_MODELS.mine) || FX_MODELS.ring || NULL_MODEL);
      propScale(p, 1);
      propPlace(p, o.kind === 'drone' ? v3(o.pos.x, o.pos.y, o.pos.z + Math.sin(ifrTickNo * 0.1 + (o.slot | 0)) * 8) : o.pos, { pitch: 0, yaw: o.kind === 'drone' ? (ifrTickNo * 6) % 360 : 0, roll: 0 });
      return;
    }
    propModel(p, o.kind === 'bubble' ? (FX_MODELS.bubble || FX_MODELS.ring || NULL_MODEL) : o.kind === 'landing' ? (FX_MODELS.landing || FX_MODELS.ring || NULL_MODEL) : (FX_MODELS.ring || NULL_MODEL));
    propScale(p, Math.max(0.3, Math.min(20, (o.radius || 300) / 150)));
    propPlace(p, o.pos, ZERO_ANG);
  });
}
function renderAll() {
  spawnBudget = CONFIG.SPAWN_BUDGET;
  for (const m of game.mechs.values()) {
    if (m.alive && m.simOff) {
      // a script-AI mech the core skipped this tick (load shedding, core cfg.load): drawn a tick ahead along its velocity, so it
      // moves every tick on screen although it is simulated every other one
      const p = m.pos, v = m.vel, d = 1 / 64;
      m.pos = IF_v3(p.x + v.x * d, p.y + v.y * d, p.z + v.z * d);
      guard('mech draw', () => renderMech(m));
      m.pos = p;
    } else if (m.alive || (m.deathT && gameTime() - m.deathT < CONFIG.DEATH_CAM_SECONDS + 0.5)) guard('mech draw', () => renderMech(m));
    else if (rigs.has(m.slot)) renderDropMech(m.slot);
  }
  for (const slot of Array.from(rigs.keys())) if (!game.mechs.has(slot)) renderDropMech(slot);
  guard('fx draw', renderProjectiles);
}
function renderReset() {
  gibReset();
  for (const slot of Array.from(rigs.keys())) renderDropMech(slot);
  for (const [o, p] of fxUsed) { releaseProp(p); fxUsed.delete(o); }
  freeProps.length = 0; propCount = 0; propSerial = 0; propTemplate = undefined;
}
