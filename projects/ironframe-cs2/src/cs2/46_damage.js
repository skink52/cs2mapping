// ===================================================================================================================
// IRONFRAME CS2 adapter, part 4b: battle damage on the models and death gibs.
//  - Skin by armour: the frame vmdls carry material groups 0 default, 1 scorched, 2 wrecked (create/damage_tex.py).
//    AP > 60 % default, 30-60 % scorched, < 30 % wrecked (a dead mech is always wrecked). The Skin input is sent only on change.
//  - Smoke below 50 % AP (a 'trail' pool loop on the upper body), plus sparks and small fires every 0.6-1.2 s below 25 %,
//    at random hit-sphere positions of the frame. Both stop on death, repair (AP back up) and when the rig is dropped.
//  - Gibs: on death the explosion is followed 0.15 s later by the upper body and weapons vanishing and 6-10 armour chunks
//    (models.json#fx gib_1..) flying out on script ballistics: bounce twice, smoulder, sink and return to the pool after
//    8 s. At most GIB_CAP live chunks. Chunks Move every tick near a human, every 3rd tick otherwise (never 3 Teleports in
//    a row: propPlace does that bookkeeping). The legs stay as the wreck for the death camera.
// ===================================================================================================================
const GIB_CAP = 64, GIB_LIFE = 8, GIB_SINK_FROM = 6, GIB_FLASH = 0.15, GIB_G = 900;
const DMG_SMOKE = 0.5, DMG_FIRE = 0.25, DMG_SCORCH = 0.6, DMG_WRECK = 0.3;
const GIB_KEYS = ['gib_1', 'gib_2', 'gib_3', 'gib_4', 'gib_5', 'gib_6'];
/** @type {any[]} */ const gibs = [];
/** @type {any[]} */ const gibPending = [];   // {slot, at, pos, cls}
let gibSerial = 0;

function dmgFrac(m) { return m.apMax > 0 ? Math.max(0, Math.min(1, m.ap / m.apMax)) : 1; }
function dmgLevel(m) { if (!m.alive) return 2; const f = dmgFrac(m); return f > DMG_SCORCH ? 0 : f > DMG_WRECK ? 1 : 2; }
function propSkin(p, level) {
  if (!p || (p.skin | 0) === level || !live(p.ent)) return;
  ifrFire(p.ent, 'Skin', level); p.skin = level;
}
// called from renderMech: switch the body props' material group when the damage level changes
function rigDamageSkin(r, m) {
  if (!r.fr || !r.fr.skins) return;   // only converted frames carry the groups (models.json frames[k].skins = 3)
  const lv = dmgLevel(m);
  if (r.legs) propSkin(r.legs, lv);
  if (r.upper && !r.upHid) propSkin(r.upper, lv);
}

// smoke / sparks / fire for a damaged live mech; called every tick per mech from the loops pass
function dmgFx(m, r) {
  const key = 'dmg' + m.slot;
  const frac = dmgFrac(m);
  const want = m.alive && frac < DMG_SMOKE && r.upper && !r.upHid && !r.far;
  if (!want) { if (r.dmgSmoke) { pfxLoopStop('trail', key); r.dmgSmoke = false; } return; }
  if (!r.dmgSmoke || ((ifrTickNo + m.slot) & 31) === 0) {   // (re)start; a loop stolen by a human booster or a reset is noticed here
    const p = pfxLoopStart('trail', key, r.upper, [0, 0, (m.cls ? m.cls.height : 288) * 0.45], 0);
    r.dmgSmoke = !!p;
  }
  if (frac >= DMG_FIRE) return;
  const now = gameTime();
  if (now < (r.dmgNext || 0)) return;
  r.dmgNext = now + 0.6 + Math.random() * 0.6;
  const sp = (r.fr && r.fr.spheres) || [[0, 0, 150, 40]];
  const s = sp[(Math.random() * sp.length) | 0];
  const up = r.upper.lastPos || m.pos, yaw = r.upper.lastAng ? r.upper.lastAng.yaw : m.torsoYaw;
  const pos = localToWorld(up, yaw, 0, [s[0] + (Math.random() - 0.5) * s[3], s[1] + (Math.random() - 0.5) * s[3], s[2] + (Math.random() - 0.5) * s[3]]);
  pfxBurst(Math.random() < 0.4 ? 'boom' : 'spark', pos, Math.random() < 0.4 ? 0.8 : 0.5);
  if (Math.random() < 0.5) sndAt('hit_metal', pos);
}
function dmgStop(slot) { pfxLoopStop('trail', 'dmg' + slot); const r = rigs.get(slot); if (r) r.dmgSmoke = false; }

// ---- gibs
function gibOnDeath(ev) {
  const r = rigs.get(ev.slot); if (!r || !r.upper || r.gibbed) return;
  const m = game.mechs.get(ev.slot); if (!m) return;
  if (!nearHuman(m.pos, CONFIG.FX.fxDist)) return;   // far from everyone: the plain wreck, no debris
  r.gibbed = true; dmgStop(ev.slot);
  gibPending.push({ slot: ev.slot, at: gameTime() + GIB_FLASH, cls: (m.cls && m.cls.height) || 288 });
}
function gibSpawn(job) {
  const r = rigs.get(job.slot); const m = game.mechs.get(job.slot);
  if (!r || !r.upper || !m) return;
  const origin = r.upper.lastPos ? v3(r.upper.lastPos.x, r.upper.lastPos.y, r.upper.lastPos.z) : m.pos;
  const h = job.cls, sc = Math.max(0.6, Math.min(2.6, h / 250));
  const centre = v3(origin.x, origin.y, origin.z + h * 0.55);
  // the upper body and its weapons vanish (the legs stay as the wreck)
  for (let i = 0; i < r.weapons.length; i++) if (r.weapons[i]) { releaseProp(r.weapons[i]); r.weapons[i] = undefined; }
  if (r.upper && live(r.upper.ent)) { propModel(r.upper, NULL_MODEL); r.upHid = true; }
  pfxBurst('boom', centre, 1.2); sndAt('boom_small', centre);
  const n = 6 + ((Math.random() * 5) | 0);
  let nSmoke = 0;
  for (let i = 0; i < n && gibs.length < GIB_CAP; i++) {
    const key = GIB_KEYS[(Math.random() * GIB_KEYS.length) | 0], model = FX_MODELS[key];
    if (!model) break;
    const p = takeProp(); if (!p) break;
    propModel(p, model); propScale(p, sc * (0.8 + Math.random() * 0.5));
    const ang = Math.random() * 360 * D2R, sp = 600 + Math.random() * 800;
    const g = { id: ++gibSerial, p, born: gameTime(), last: gameTime(), idx: gibSerial,
      pos: v3(centre.x + (Math.random() - 0.5) * 60 * sc, centre.y + (Math.random() - 0.5) * 60 * sc, centre.z + (Math.random() - 0.5) * 60 * sc),
      vel: v3(Math.cos(ang) * sp, Math.sin(ang) * sp, 350 + Math.random() * 650),
      pitch: Math.random() * 360, yaw: Math.random() * 360, roll: Math.random() * 360,
      sp: (Math.random() - 0.5) * 900, sy: (Math.random() - 0.5) * 900, sr: (Math.random() - 0.5) * 900,
      bounces: 0, rest: false, gz: null, gzTick: -9, size: sc, smoke: false, rad: 22 * sc };
    if (nSmoke < 3 && Math.random() < 0.45 && pfxLoopStart('trail', 'gib' + g.id, p, [0, 0, 0], 0)) { g.smoke = true; nSmoke++; }
    gibs.push(g);
    gibPlace(g, true);
  }
}
function gibPlace(g, first) {
  propPlace(g.p, g.pos, { pitch: g.pitch, yaw: g.yaw, roll: g.roll });
}
function gibRemove(i) {
  const g = gibs[i];
  if (g.smoke) pfxLoopStop('trail', 'gib' + g.id);
  releaseProp(g.p);
  gibs.splice(i, 1);
}
function gibGround(g, now) {
  // heightfield / world trace; refreshed every 3rd tick per chunk, only while falling
  if (g.gz === null || (ifrTickNo - g.gzTick >= 3 && g.vel.z <= 0)) {
    g.gz = IF_groundAt(game, g.pos.x, g.pos.y, g.pos.z + 40, 0, null); g.gzTick = ifrTickNo;
  }
  return g.gz;
}
function gibTick(now) {
  for (let i = gibPending.length - 1; i >= 0; i--) if (gibPending[i].at <= now) { const j = gibPending.splice(i, 1)[0]; guard('gib spawn', () => gibSpawn(j)); }
  for (let i = gibs.length - 1; i >= 0; i--) {
    const g = gibs[i], age = now - g.born;
    if (age >= GIB_LIFE || !live(g.p.ent)) { gibRemove(i); continue; }
    const near = nearHuman(g.pos, CONFIG.FAR_DIST);
    if (!near && ((ifrTickNo + g.idx) % 3) !== 0) continue;   // far chunks update every 3rd tick with a 3x step
    const dt = Math.min(0.1, now - g.last); g.last = now;
    if (!g.rest) {
      g.vel.z -= GIB_G * dt;
      g.pos.x += g.vel.x * dt; g.pos.y += g.vel.y * dt; g.pos.z += g.vel.z * dt;
      g.pitch += g.sp * dt; g.yaw += g.sy * dt; g.roll += g.sr * dt;
      const gz = gibGround(g, now);
      if (g.pos.z - g.rad < gz && g.vel.z < 0) {
        g.pos.z = gz + g.rad; g.bounces++;
        if (g.bounces === 1 && near && Math.random() < 0.5) pfxBurst('spark', g.pos, 0.3);
        if (g.bounces >= 3 || Math.abs(g.vel.z) < 120) { g.rest = true; g.vel = v3(0, 0, 0); g.sp = g.sy = g.sr = 0; }
        else { g.vel.z = -g.vel.z * 0.4; g.vel.x *= 0.55; g.vel.y *= 0.55; g.sp *= 0.5; g.sy *= 0.5; g.sr *= 0.5; }
      }
    }
    let place = g.pos;
    if (age > GIB_SINK_FROM) { const k = (age - GIB_SINK_FROM) / (GIB_LIFE - GIB_SINK_FROM); place = v3(g.pos.x, g.pos.y, g.pos.z - k * g.rad * 2.2); if (g.smoke && k > 0.3) { pfxLoopStop('trail', 'gib' + g.id); g.smoke = false; } }
    propPlace(g.p, place, { pitch: g.pitch, yaw: g.yaw, roll: g.roll });
  }
}
function gibReset() { gibs.length = 0; gibPending.length = 0; }
