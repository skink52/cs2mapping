// ===================================================================================================================
// IRONFRAME CS2 adapter, part 4: particles and sounds.
// Particles are map-placed info_particle_system pools (ifr_pfx_<kind>_NN): claimed, Teleported (or parented to a mech
// prop), started with the Start input and stopped later with Stop. Entity I/O is queued, so a Start and its Stop must
// never land in the same tick: stops are scheduled at least one tick after the start (Dogfight FX_EM rule).
// Sounds are point_soundevents (ifr_snd_<key>): one-shots are sourced on a pooled anchor prop teleported to the spot
// (SetSourceEntity then StartSound), per-mech loops use the per-slot entities ifr_snd_<key>_NN sourced on the upper-body
// prop, pilot-only tones use StartSoundOnSingleClient with the slot. Everything is capped per tick and by distance.
// ===================================================================================================================
const SND = (typeof SOUNDS === 'object' && SOUNDS && SOUNDS.events) || {};
const PFX_POOLS = { boost: 128, muzzle: 64, boom: 24, spark: 16, gboom: 8, trail: 128 };
const pfx = {};             // kind -> [{ent, name, busy, parent, stopAt, startedTick, owner}]
const pfxStops = [];        // {p, at} pending Stop inputs
let sndEnts = {};           // key -> ent (singles) ; key -> [ents] (per_slot / ring)
let sndAnchors = [];        // pooled props used as sound sources for one-shots
let sndAnchorNext = 0, sndThisTick = 0;
const sndMissing = new Set();
const mechLoops = new Map();   // slot -> {boost: bool}

function pad2(n) { return (n < 10 ? '0' : '') + n; }
function pad3(n) { return (n < 100 ? '0' : '') + pad2(n); }
function pfxName(kind, i) { return CONFIG.PFX_PREFIX + kind + '_' + (PFX_POOLS[kind] >= 100 ? pad3(i) : pad2(i)); }

function fxInit() {
  let found = 0, want = 0;
  for (const kind of Object.keys(PFX_POOLS)) {
    pfx[kind] = [];
    for (let i = 0; i < PFX_POOLS[kind]; i++) {
      want++;
      const ent = ifrFind(pfxName(kind, i));
      if (!ent) continue;
      found++;
      pfx[kind].push({ ent, name: pfxName(kind, i), busy: false, parent: undefined, stopAt: 0, startedTick: -9, owner: -1 });
    }
  }
  sndEnts = {};
  let sfound = 0, swant = 0;
  for (const key of Object.keys(SND)) {
    const ev = SND[key];
    const n = ev.per_slot || ev.ring || 0;
    if (n) { const list = []; for (let i = 0; i < n; i++) { swant++; const e = ifrFind(CONFIG.SOUND_PREFIX + key + '_' + pad2(i)); if (e) { sfound++; list.push(e); } } sndEnts[key] = list; }
    else { swant++; const e = ifrFind(CONFIG.SOUND_PREFIX + key); if (e) { sfound++; sndEnts[key] = e; } }
  }
  sndAnchors = [];
  pfxStops.length = 0; mechLoops.clear();
  return { pfx: found + '/' + want, snd: sfound + '/' + swant };
}
function fxReset() { for (const kind of Object.keys(pfx)) for (const p of pfx[kind]) { p.busy = false; p.parent = undefined; p.owner = -1; } pfxStops.length = 0; mechLoops.clear(); sndAnchors = []; missileFx.clear(); auraReset(); }

// ---- particles
function pfxTake(kind, owner) {
  const list = pfx[kind]; if (!list || !list.length) return undefined;
  let best; let bestAt = Infinity;
  for (const p of list) { if (!p.busy) return p; if (p.stopAt < bestAt) { bestAt = p.stopAt; best = p; } }
  // all busy: take the one ending soonest (effects are dropped, never spawned unbounded)
  if (best && owner === undefined) { pfxStopNow(best); return best; }
  // a human's booster may take one an AI mech is using
  if (typeof owner === 'number' && loopOwnerHuman(owner >> 1)) {
    const v = list.find((p) => p.busy && typeof p.owner === 'number' && !loopOwnerHuman(p.owner >> 1));
    if (v) { guard('pfx steal', () => { if (v.parent) { v.ent.SetParent(undefined); v.parent = undefined; } }); pfxStopNow(v); return v; }
  }
  return undefined;
}
function pfxStopNow(p) {
  if (!live(p.ent)) { p.busy = false; return; }
  const at = Math.max(gameTime() + 1 / 64, p.startedTick === ifrTickNo ? gameTime() + 1 / 32 : 0);
  pfxStops.push({ p, at });
  p.busy = false; p.owner = -1;
}
// a one-shot at a position: Start now, Stop after seconds
function pfxBurst(kind, pos, seconds) {
  if (!nearHuman(pos, CONFIG.FX.fxDist)) return;
  const p = pfxTake(kind); if (!p || !live(p.ent)) return;
  guard('pfx ' + kind, () => {
    if (p.parent) { p.ent.SetParent(undefined); p.parent = undefined; }
    p.ent.Teleport({ position: clampWorld(pos) });
    ifrFire(p.ent, 'Start');
    p.busy = true; p.startedTick = ifrTickNo; p.stopAt = gameTime() + seconds;
  });
}
// a looping effect riding a prop (boosters, missile trails): started once, stopped with pfxLoopStop
function pfxLoopStart(kind, owner, prop, localPos, yaw) {
  const list = pfx[kind]; if (!list) return undefined;
  let p = list.find((x) => x.busy && x.owner === owner);
  if (p) return p;
  // the particle is put at the parent's real transform (30_render.js propXform: what the engine reports) before SetParent keeps that
  // offset. It used prop.lastPos, and HIDE_POS without one: the boosters then burned 15 000 u under the map (10 Nov 2026 console:
  // "ifr_pfx_boost_013 ... m_cellZ ... outside of cell bounds @(... -16891)"). No transform yet: try again next tick.
  if (!live(prop.ent)) return undefined;
  const x = propXform(prop); if (!x) return undefined;
  p = pfxTake(kind, owner); if (!p || !live(p.ent)) return undefined;
  guard('pfx loop ' + kind, () => {
    p.ent.Teleport({ position: clampWorld(xformPoint(x, localPos || [0, 0, 0])) });
    p.ent.SetParent(prop.ent); p.parent = prop;
    ifrFire(p.ent, 'Start');
    p.busy = true; p.owner = owner; p.startedTick = ifrTickNo; p.stopAt = Infinity;
  });
  return p;
}
function pfxLoopStop(kind, owner) {
  const list = pfx[kind]; if (!list) return;
  for (const p of list) if (p.busy && p.owner === owner) { guard('pfx unparent', () => { if (p.parent) { p.ent.SetParent(undefined); p.parent = undefined; } }); pfxStopNow(p); }
}
function fxTick(now) {
  sndThisTick = 0;
  gibTick(now);
  for (const kind of Object.keys(pfx)) for (const p of pfx[kind]) if (p.busy && p.stopAt <= now) pfxStopNow(p);
  for (let i = pfxStops.length - 1; i >= 0; i--) {
    const s = pfxStops[i];
    if (s.at > now) continue;
    pfxStops.splice(i, 1);
    guard('pfx stop', () => { if (live(s.p.ent)) { ifrFire(s.p.ent, 'Stop'); s.p.ent.Teleport({ position: HIDE_POS }); } });
  }
}
// boosters and trails follow the mech state (the director: other code never toggles loops)
function fxMechLoops(m) {
  const r = rigs.get(m.slot); if (!r || !r.upper) return;
  const want = m.alive && (m.boosting || m.hover || m.dropT > 0);
  const st = mechLoops.get(m.slot) || { boost: false };
  if (want && !st.boost) {
    const bs = (r.fr && r.fr.boosters) || [[-60, 0, 90]];
    pfxLoopStart('boost', m.slot * 2, r.upper, bs[0], m.torsoYaw);
    if (bs[1]) pfxLoopStart('boost', m.slot * 2 + 1, r.upper, bs[1], m.torsoYaw);
    sndLoopStart('boost_loop', m.slot, r.upper);
    st.boost = true;
  } else if (!want && st.boost) {
    pfxLoopStop('boost', m.slot * 2); pfxLoopStop('boost', m.slot * 2 + 1);
    sndLoopStop('boost_loop', m.slot);
    st.boost = false;
  }
  mechLoops.set(m.slot, st);
  dmgFx(m, r);
}
// missile trail particle + rocket loop (sound ring), started when the missile gets its prop, stopped when it goes
const missileFx = new Map(); let mslLoopNext = 0;
function missileFxStart(o, prop) {
  const ring = sndEnts.msl_loop; const ri = Array.isArray(ring) && ring.length ? (mslLoopNext++ % ring.length) : -1;
  missileFx.set(o, ri);
  guard('trail', () => pfxLoopStart('trail', o, prop, [-40, 0, 0], 0));
  if (ri >= 0) sndLoopStart('msl_loop', o, prop);   // lent by missile object (a free ring entity, or none)
}
function missileFxStop(o) {
  if (!missileFx.has(o)) return; const ri = missileFx.get(o); missileFx.delete(o);
  pfxLoopStop('trail', o); if (ri >= 0) sndLoopStop('msl_loop', o);
}
// the shooter's camera kicks with every shot (heavier weapons kick harder); explosions shake everyone close
function camRecoil(ev) {
  if (!loopOwnerHuman(ev.slot)) return;
  let part; for (const p of (PARTS.parts || [])) if (p.key === ev.weapon) { part = p; break; }
  const w = part && part.w, dmg = w ? (w.damage || 0) * (w.pellets || 1) * (w.count || 1) : 200;
  const k = Math.min(1, dmg / 2400);
  camKick(ev.slot, 8 + 45 * k, 3 + 14 * k, (Math.random() - 0.5) * 10 * k);
}
function explodeShake(pos, radius) {
  const reach = 900 + radius * 4;
  for (const pe of people.values()) {
    if (!pe.human) continue; const pm = game.mechs.get(pe.slot); if (!pm) continue;
    const dd = vdist(pm.pos, pos); if (dd > reach) continue;
    const k = 1 - dd / reach; camKick(pe.slot, 40 * k, -30 * k, (Math.random() - 0.5) * 80 * k);
  }
}
// ---- the pilot's own IFF marker (10 Nov 2026 playtest: the diamond over one's own mech sat under the reticle and hid the target; the
// chase camera's ray passes `up` over the hip, the marker hovers at the head). Props have no per-client visibility (point_script.d.ts:
// per-team visibility only on CSRadarPoint), so: with no other human in the arena copy nobody else needs it and it isn't drawn; else it
// is lifted until it sits IFF_CLEAR_DEG over the pilot's camera ray (as the pilot sees it); the others see it a little higher.
const IFF_CLEAR_DEG = 8;
// pos lifted (only up, never into the mech) until it is IFF_CLEAR_DEG off the ray cam + t dir; pos itself when already clear; null when
// 600 u of lift don't clear it (looking steeply up past it)
function iffClearOfReticle(pos, cam, dir) {
  const dl = Math.sqrt(dir.x * dir.x + dir.y * dir.y + dir.z * dir.z) || 1, dx = dir.x / dl, dy = dir.y / dl, dz = dir.z / dl;
  const c = Math.cos(IFF_CLEAR_DEG * Math.PI / 180);
  const cosAt = (z) => { const vx = pos.x - cam.x, vy = pos.y - cam.y, vz = z - cam.z, l = Math.sqrt(vx * vx + vy * vy + vz * vz) || 1; return (vx * dx + vy * dy + vz * dz) / l; };
  if (cosAt(pos.z) < c) return pos;
  for (let lift = 8; lift <= 600; lift += 8) if (cosAt(pos.z + lift) < c) return { x: pos.x, y: pos.y, z: pos.z + lift };
  return null;
}
let iffHumansTick = -1;
const iffHumans = new Map();   // arena copy -> humans in it, counted once a tick
function iffOthersWatching(slot) {
  if (iffHumansTick !== ifrTickNo) {
    iffHumansTick = ifrTickNo; iffHumans.clear();
    for (const pe of people.values()) if (pe.human) { const k = game.arenaIndexOf(pe.slot); iffHumans.set(k, (iffHumans.get(k) || 0) + 1); }
  }
  return (iffHumans.get(game.arenaIndexOf(slot)) || 0) > 1;
}
// where mech m's marker goes this tick (null: none); 30_render.js renderIff
function iffPlace(m, pos) {
  const pe = people.get(m.slot);
  if (!pe || !pe.human || pe.status !== 'mech') return pos;
  if (!iffOthersWatching(m.slot)) return null;
  const cp = m.input && m.input.camPos, cd = m.input && m.input.camDir;
  return cp && cd && vfinite(cp) && vfinite(cd) ? iffClearOfReticle(pos, cp, cd) : pos;
}
function fxMechGone(slot) { auraGone(slot); pfxLoopStop('trail', 'burn' + slot); pfxLoopStop('trail', 'dmg' + slot); pfxLoopStop('boost', slot * 2); pfxLoopStop('boost', slot * 2 + 1); pfxLoopStop('muzzle', slot); sndLoopStop('boost_loop', slot); mechLoops.delete(slot); }
function fxMuzzle(slot, pos, dir) {
  const p = pfxTake('muzzle'); if (!p || !live(p.ent) || !nearHuman(pos, CONFIG.FX.fxDist)) return;
  guard('muzzle', () => {
    if (p.parent) { p.ent.SetParent(undefined); p.parent = undefined; }
    p.ent.Teleport({ position: clampWorld(pos), angles: { pitch: -Math.asin(Math.max(-1, Math.min(1, dir.z))) * R2D, yaw: Math.atan2(dir.y, dir.x) * R2D, roll: 0 } });
    ifrFire(p.ent, 'Start'); p.busy = true; p.startedTick = ifrTickNo; p.stopAt = gameTime() + 0.08; p.owner = slot;
  });
}

// ---- sounds
function sndEnt(key) { const e = sndEnts[key]; if (!e) { if (!sndMissing.has(key)) { sndMissing.add(key); dlog('no sound entity for ' + key); } return undefined; } return e; }
function sndAnchor() {
  if (sndAnchors.length < CONFIG.FX.anchors) { const p = takeProp(); if (p) { propModel(p, NULL_MODEL); sndAnchors.push(p); } }
  if (!sndAnchors.length) return undefined;
  const p = sndAnchors[sndAnchorNext % sndAnchors.length]; sndAnchorNext++;
  return live(p.ent) ? p : undefined;
}
// a one-shot at a position (3D) or sourced on a prop
function sndAt(key, pos, prio) {
  // prio (a human's own weapon, explosions): always played; the rest share the per-tick cap
  if ((!prio && sndThisTick >= CONFIG.FX.soundsPerTick) || !nearHuman(pos, CONFIG.FX.sndDist)) return;
  const e = sndEnt(key); if (!e || Array.isArray(e)) return;
  const a = sndAnchor(); if (!a) return;
  // anchors are invisible null models: Move is fine once placed (a prop Teleported 3 ticks running is a CS2 pitfall)
  guard('snd ' + key, () => { const pp = clampWorld(pos); if (a.tpRun >= 2) a.ent.Move({ position: pp }); else { a.ent.Teleport({ position: pp }); a.tpRun++; } a.lastPos = pp; ifrFire(e, 'SetSourceEntity', a.name); ifrFire(e, 'StartSound'); sndThisTick++; });
}
function sndOn(key, prop) {
  if (sndThisTick >= CONFIG.FX.soundsPerTick) return;
  const e = sndEnt(key); if (!e || Array.isArray(e) || !prop || !live(prop.ent)) return;
  if (prop.lastPos && !nearHuman(prop.lastPos, CONFIG.FX.sndDist)) return;
  guard('snd ' + key, () => { ifrFire(e, 'SetSourceEntity', prop.name); ifrFire(e, 'StartSound'); sndThisTick++; });
}
// loop entities (ifr_snd_<key>_NN) are lent to owners (a mech slot, a missile) from a free list: AI slots 64+ used to wrap
// onto the human slots' entities and steal their booster loops (9 Nov 2026 playtest). Humans may take an AI's entity.
const loopLent = {};
function loopOwnerHuman(owner) { return typeof owner === 'number' && owner >= 0 && owner < 64 && !!(person(owner) && person(owner).human); }
function sndLoopStart(key, owner, prop) {
  const list = sndEnts[key]; if (!Array.isArray(list) || !list.length || !prop || !live(prop.ent)) return;
  const L = loopLent[key] || (loopLent[key] = { byOwner: new Map(), owners: new Array(list.length) });
  let idx = L.byOwner.get(owner);
  if (idx === undefined) {
    idx = -1; for (let i = 0; i < L.owners.length; i++) if (L.owners[i] === undefined) { idx = i; break; }
    if (idx < 0 && loopOwnerHuman(owner)) {
      for (let i = 0; i < L.owners.length; i++) if (!loopOwnerHuman(L.owners[i])) { idx = i; break; }
      if (idx >= 0) { const old = L.owners[idx]; L.byOwner.delete(old); const ev = list[idx]; guard('loop steal', () => ifrFire(ev, 'StopSound')); }
    }
    if (idx < 0) return;
    L.owners[idx] = owner; L.byOwner.set(owner, idx);
  }
  const e = list[idx]; if (!live(e)) return;
  guard('loop ' + key, () => { ifrFire(e, 'SetSourceEntity', prop.name); ifrFire(e, 'StartSound'); });
}
function sndLoopStop(key, owner) {
  const list = sndEnts[key]; const L = loopLent[key]; if (!Array.isArray(list) || !L) return;
  const idx = L.byOwner.get(owner); if (idx === undefined) return;
  L.byOwner.delete(owner); L.owners[idx] = undefined;
  const e = list[idx]; if (!live(e)) return;
  guard('loop stop ' + key, () => ifrFire(e, 'StopSound'));
}
// a tone only one player hears
function sndTone(slot, key) {
  const pe = person(slot); if (!pe || !pe.human) return;
  const e = sndEnt(key); if (!e || Array.isArray(e)) return;
  guard('tone ' + key, () => ifrFire(e, 'StartSoundOnSingleClient', slot));
}
let musicKey = '';
function music(key) {
  if (musicKey === key) return;
  if (musicKey) { const old = sndEnt(musicKey); if (old && !Array.isArray(old)) guard('music stop', () => ifrFire(old, 'StopSound')); }
  musicKey = key;
  if (!key) return;
  const e = sndEnt(key); if (e && !Array.isArray(e)) guard('music', () => ifrFire(e, 'StartSound'));
}

// ---- the event -> effect table (called from the main loop for every core event)
const WEAPON_PFX = { bazooka: 'gboom', grenade: 'boom', grenadecannon: 'gboom', flak: 'boom', plasma: 'spark', vm6: 'boom', vm12: 'boom', dualmsl: 'boom', handmsl: 'spark', blade: 'spark', lasercannon: 'boom' };
const partByKey = new Map();
function fireSoundKey(key) {
  if (!key) return 'rifle';
  if (!partByKey.size) for (const p of (PARTS.parts || [])) if (p.key) partByKey.set(p.key, p);
  const p = partByKey.get(key), snd = p && ((p.w && p.w.sound) || p.sound);
  return snd || key;
}
function fxEvent(ev) {
  switch (ev.t) {
    case 'fire': {
      { const rr = rigs.get(ev.slot); if (!(rr && rr.loco)) rigOneShot(ev.slot, 'upper', ev.hp === 1 ? 'fire_l' : ev.hp >= 2 ? 'fire_s' : 'fire_r'); }
      if (ev.pos) { fxMuzzle(ev.slot, ev.pos, ev.dir || v3(1, 0, 0)); sndAt(fireSoundKey(ev.weapon), ev.pos, loopOwnerHuman(ev.slot) || ev.hp >= 2); camRecoil(ev); }
      if (ev.weapon === 'flamethrower' && ev.pos && ev.dir && ((ifrTickNo + ev.slot) & 3) === 0) pfxBurst('spark', vadd(ev.pos, vmul(ev.dir, 450)), 0.3);
      break;
    }
    case 'ability': { const r = rigs.get(ev.slot); if (r && r.upper) sndOn(fireSoundKey(ev.weapon || ev.kind), r.upper); break; }
    case 'burn': {   // a burning mech trails smoke (the missile-trail pool) until the burn ends
      const r = rigs.get(ev.slot);
      if (ev.on && r && r.upper) pfxLoopStart('trail', 'burn' + ev.slot, r.upper, [0, 0, 120], 0); else pfxLoopStop('trail', 'burn' + ev.slot);
      break;
    }
    case 'hit': if (ev.pos && nearHuman(ev.pos, 4000)) { pfxBurst('spark', ev.pos, 0.4); if (ev.kind !== 'ground' || ((ifrTickNo + (ev.slot | 0)) & 3) === 0) sndAt(ev.kind === 'ground' ? 'hit_ground' : 'hit_metal', ev.pos); } break;
    case 'explode': if (ev.pos) { explodeShake(ev.pos, ev.radius || 0); const big = (ev.radius || 0) >= 350; pfxBurst(big ? 'gboom' : 'boom', ev.pos, big ? 3 : 2); sndAt(big ? 'boom_large' : 'boom_small', ev.pos, true); } break;
    case 'death': if (ev.pos) { pfxBurst('gboom', ev.pos, 3); sndAt('mech_death', ev.pos); } dmgStop(ev.slot); gibOnDeath(ev); break;
    case 'stagger': { rigOneShot(ev.slot, 'upper', 'stagger'); const r = rigs.get(ev.slot); if (r && r.upper && r.upper.lastPos) { pfxBurst('spark', r.upper.lastPos, 0.6); sndOn('stagger_clang', r.upper); } sndTone(ev.slot, 'ui_stagger'); break; }
    case 'qb': { const mq = game.mechs.get(ev.slot); if (mq) { const side = Math.sin((Math.atan2(mq.vel.y, mq.vel.x) * R2D - mq.legYaw) * D2R); rigOneShot(ev.slot, 'legs', side > 0 ? 'qb_l' : 'qb_r'); } const r = rigs.get(ev.slot); if (r && r.upper) sndOn('qb', r.upper); break; }
    case 'land': { rigOneShot(ev.slot, 'legs', 'land'); rigOneShot(ev.slot, 'upper', 'land'); rigLand(ev.slot, ev.hard); const r = rigs.get(ev.slot); if (r && r.legs) { sndOn(ev.hard ? 'land_heavy' : 'land_light', r.legs); if (ev.hard && r.legs.lastPos) pfxBurst('spark', r.legs.lastPos, 0.5); } break; }
    case 'spawn': { const r = rigs.get(ev.slot); if (r && r.upper) { sndOn('drop_entry', r.upper); } sndTone(ev.slot, 'ui_spawn'); break; }
    case 'lock': if (ev.stage >= 0) sndTone(ev.slot, 'ui_lock' + Math.min(3, Math.max(1, ev.stage + 1))); break;
    case 'threat': sndTone(ev.slot, ev.kind === 'close' ? 'ui_msl_close' : ev.kind === 'launch' ? 'ui_launch_warn' : 'ui_locked_warn'); break;
    case 'kill': sndTone(ev.killer, 'ui_kill'); break;
    case 'damage': if (ev.attacker >= 0 && ev.attacker !== ev.victim) sndTone(ev.attacker, 'ui_hit'); break;
    case 'en_empty': sndTone(ev.slot, 'ui_en_empty'); break;
    case 'capture': { sndTone(ev.slot, 'ui_capture'); const pt = (ARENA.points || [])[ev.point]; if (pt) { sndAt('capture_done', v3(pt.pos[0], pt.pos[1], pt.pos[2])); } break; }
    case 'wave': for (const pe of people.values()) sndTone(pe.slot, 'ui_round_start'); break;
    case 'bounty': for (const pe of people.values()) sndTone(pe.slot, 'bounty'); break;
    case 'sound': if (ev.only !== undefined) sndTone(ev.only, ev.key); else if (ev.pos) sndAt(ev.key, ev.pos); else if (ev.slot !== undefined) { const r = rigs.get(ev.slot); if (r && r.upper) sndOn(ev.key, r.upper); } break;
    default: break;
  }
}
