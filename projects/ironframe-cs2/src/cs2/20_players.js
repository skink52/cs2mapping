// ===================================================================================================================
// IRONFRAME CS2 adapter, part 2: people, pawns, cameras, input.
// Every connected controller has a "person" record. While a person pilots a mech their real pawn is invisible
// (DestroyWeapons, then colour alpha 0), set to FLYGRAVITY (the map runs sv_gravity 0) and dragged after the mech by
// velocity each tick (Dogfight's ride); it keeps the health, takes the damage and makes the kills. The view is the pawn's
// custom camera in FOLLOW_POSITION on the mech's upper-body prop; the mouse aims (eye angles), the script rebuilds the
// crosshair ray. Dead and spectating people get a CONTROLLED camera the script moves. People not in a mech (garage,
// intro) stand frozen in the sealed booth.
// ===================================================================================================================
const TEAM_T = 2, TEAM_CT = 3;
const KEYS = { fwd: CSInputs.FORWARD, back: CSInputs.BACK, left: CSInputs.LEFT, right: CSInputs.RIGHT, boost: CSInputs.WALK, qb: CSInputs.DUCK,
  jump: CSInputs.JUMP, ra: CSInputs.ATTACK, la: CSInputs.ATTACK2, rs: CSInputs.RELOAD, ls: CSInputs.USE, cycle: CSInputs.LOOK_AT_WEAPON, scores: CSInputs.SHOW_SCORES };

/** @typedef {{slot:number, ctrl:any, pawn:any, human:boolean, team:number, status:string, cam:any, camKind:string, camSent:{back:number,up:number,target:any}|null,
 *  camBack:number, camUp:number, lastEye:{yaw:number,pitch:number}, lastInput:number, afkWarned:boolean, wantMt:number, deathAt:number, deathPos:any, deathKiller:number,
 *  specTarget:number, specYaw:number, garage:any, pilot:any, ready:boolean, hudReset:boolean, camScale:number, garageSeenThisLife:boolean, kick:any, eye:{yaw:number,pitch:number}, lastRideErr:number, snaps:number, joinedAt:number}} Person */
/** @type {Map<number, Person>} */
const people = new Map();
let boothEnt, boothOrigin;
const allowDamage = new Set();      // slots whose pawn may take damage right now (inside our own TakeDamage)
let damageDepth = 0;
const awaitRespawn = new Map();     // slot -> game time of the scripted kill (respawn watchdog)
let respawnFailures = 0, realKills = true;
const pendingKills = [];            // kill events from the core, applied a few ticks apart so the killfeed rolls

function person(slot) { return people.get(slot); }
function boothPos(slot) {
  if (!boothOrigin) { boothEnt = live(boothEnt) || ifrFind(CONFIG.BOOTH); boothOrigin = boothEnt ? boothEnt.GetAbsOrigin() : (ARENA && ARENA.booth ? v3(ARENA.booth[0], ARENA.booth[1], ARENA.booth[2]) : v3(0, 0, -12000)); }
  const col = slot % 8, row = Math.floor(slot / 8) % 8;
  return v3(boothOrigin.x + (col - 3.5) * 96, boothOrigin.y + (row - 3.5) * 96, boothOrigin.z + 8);
}

function newPerson(slot, ctrl) {
  return { slot, ctrl, pawn: undefined, human: !ctrl.IsBot(), team: 0, status: 'none', cam: undefined, camKind: '', camSent: null, camBack: 520, camUp: 180,
    lastEye: { yaw: 0, pitch: 0 }, lastInput: gameTime(), afkWarned: false, wantMt: CSMoveType.NONE, deathAt: 0, deathPos: null, deathKiller: -1, specTarget: -1,
    specYaw: 0, garage: null, pilot: null, ready: false, hudReset: true, camScale: 1, garageSeenThisLife: false, kick: null, eye: { yaw: 0, pitch: 0 }, lastRideErr: 0, snaps: 0, joinedAt: gameTime() };
}

// Walk every controller: new people join, people whose controller object changed are replaced (a slot reused without a
// disconnect), teams are re-read. Once a second and on events.
function scanPeople() {
  let ctrls = [];
  try { ctrls = Instance.GetAllPlayerControllers() || []; } catch (err) { return; }
  const seen = new Set();
  for (const c of ctrls) {
    if (!live(c)) continue;
    let slot; try { slot = c.GetPlayerSlot(); } catch (err) { continue; }
    seen.add(slot);
    let pe = people.get(slot);
    if (pe && pe.ctrl !== c) { dropPerson(slot, 'slot reused'); pe = undefined; }
    if (!pe) { pe = newPerson(slot, c); people.set(slot, pe); onPersonJoined(pe); }
    let team = 0; try { team = c.GetTeamNumber(); } catch (err) { /* ignore */ }
    if (team !== pe.team) onTeamChanged(pe, team);
    pe.pawn = pawnOf(slot);
  }
  for (const slot of Array.from(people.keys())) if (!seen.has(slot)) dropPerson(slot, 'gone');
}

function onPersonJoined(pe) {
  dlog('joined: ' + nameOf(pe.slot) + (pe.human ? '' : ' (bot)'));
  if (pe.human) srvOnJoin(pe.slot);
}

function onTeamChanged(pe, team) {
  const was = pe.team; pe.team = team;
  if (was === TEAM_T || was === TEAM_CT) leaveGame(pe, 'team change');
  if (team === TEAM_T || team === TEAM_CT) {
    pe.status = 'intro'; pe.hudReset = true; pe.joinedAt = gameTime();
    if (game) guard('addPlayer', () => game.addPlayer(pe.slot, { team, human: pe.human, name: nameOf(pe.slot), pilot: pe.pilot }));
  } else pe.status = 'none';
}

function dropPerson(slot, why) {
  const pe = people.get(slot);
  if (!pe) return;
  leaveGame(pe, why);
  people.delete(slot);
  for (let i = pendingKills.length - 1; i >= 0; i--) if (pendingKills[i].victim === slot) pendingKills.splice(i, 1);
  awaitRespawn.delete(slot);
  if (hudOff) hudOff(slot);
}

function leaveGame(pe, why) {
  if (game) guard('removePlayer', () => game.removePlayer(pe.slot));
  renderDropMech(pe.slot);
  releaseCamera(pe);
  const pawn = live(pe.pawn);
  if (pawn) guard('unpark', () => { if (pawn.IsAlive()) { pawn.SetMoveType(CSMoveType.WALK); pawn.SetColor({ r: 255, g: 255, b: 255, a: 255 }); } });
  pe.status = 'none'; pe.camKind = ''; pe.camSent = null;
}

// ---------------------------------------------------------------- the pawn: hidden, parked, ridden
function hidePawn(pawn) { pawn.DestroyWeapons(); pawn.SetArmor(0); pawn.SetHasHelmet(false); pawn.SetColor({ r: 255, g: 255, b: 255, a: 0 }); }
function parkPawn(pe) {
  const pawn = live(pe.pawn); if (!pawn) return;
  guard('park', () => { hidePawn(pawn); pawn.Teleport({ position: boothPos(pe.slot), velocity: ZERO }); pawn.SetMoveType(CSMoveType.NONE); pe.wantMt = CSMoveType.NONE; });
}
// the pawn starts riding the mech at pos (a spawn)
function mountPawn(pe, pos) {
  const pawn = live(pe.pawn); if (!pawn) return;
  guard('mount', () => {
    // the mech is back but CS2 still counts the pawn dead (its own respawn comes later or never): revive it now, or CS2's
    // death screen stays over the view (9 Nov 2026 playtest)
    if (!pawn.IsAlive() && typeof pawn.Reset === 'function') pawn.Reset();
    hidePawn(pawn);
    if (pawn.GetParent()) pawn.SetParent(undefined);
    pe.wantMt = CSMoveType.FLYGRAVITY; pawn.SetMoveType(pe.wantMt);
    pawn.Teleport({ position: v3(pos.x, pos.y, pos.z + CONFIG.RIDE_PAWN_UP), velocity: ZERO });
  });
}
// a dead pawn shows CS2's observer view, not our custom camera (garage, spectating, death orbit): bring it back, hidden and parked in the
// booth. Returns whether the pawn is alive now. (Nov 2026 playtest: !garage while dead showed no hangar view.)
function revivePawn(pe) {
  const pawn = live(pe.pawn) || pawnOf(pe.slot); if (!pawn || !pe.human) return !!(pawn && pawn.IsAlive());
  if (pawn.IsAlive()) return true;
  if (typeof pawn.Reset !== 'function') return false;
  guard('revive', () => { pawn.Reset(); });
  pe.pawn = pawn; pe.cam = undefined; pe.camKind = ''; pe.camSent = null;
  if (pawn.IsAlive()) { parkPawn(pe); return true; }
  return false;
}
// every tick for a piloting person: velocity toward the mech, a snap beyond RIDE_SNAP (Dogfight ridePawn)
function ridePawn(pe, m) {
  const pawn = pe.pawn;
  const target = v3(m.pos.x, m.pos.y, m.pos.z + CONFIG.RIDE_PAWN_UP);
  const pawnPos = pawn.GetAbsOrigin();
  const err = vsub(target, pawnPos), e = vlen(err);
  pe.lastRideErr = e;
  if (e > CONFIG.RIDE_SNAP) { pawn.Teleport({ position: target, velocity: m.vel }); pe.snaps++; return; }
  let corr = vmul(err, CONFIG.RIDE_GAIN);
  const cl = vlen(corr); if (cl > CONFIG.RIDE_MAX) corr = vmul(corr, CONFIG.RIDE_MAX / cl);
  let v = vadd(m.vel, corr);
  const vl = vlen(v); if (vl > CONFIG.RIDE_MAX_SPEED) v = vmul(v, CONFIG.RIDE_MAX_SPEED / vl);
  pawn.Move({ velocity: v });
  if (((ifrTickNo + pe.slot) & 15) === 0 && pawn.GetMoveType() !== pe.wantMt) pawn.SetMoveType(pe.wantMt);
}

// ---------------------------------------------------------------- cameras
function camOf(pe) {
  const pawn = live(pe.pawn); if (!pawn || typeof pawn.GetCustomCamera !== 'function') return undefined;
  pe.cam = live(pe.cam) || live(pawn.GetCustomCamera());
  if (!pe.cam) warnOnce('nocam', 'GetCustomCamera returned nothing: players will see from their hidden pawn');
  return pe.cam;
}
function releaseCamera(pe) {
  const cam = live(pe.cam);
  if (cam) guard('cam release', () => { if (cam.GetParent()) cam.SetParent(undefined); cam.SetMode(CustomCameraMode.DISABLED); });
  pe.camKind = ''; pe.camSent = null;
}
// the mech follow camera: FOLLOW_POSITION on the upper-body prop; the config is sent only when it changes
function followCamera(pe, upperEnt, back, up, hipZ, side, fast) {
  if (!pe.human) return;
  const cam = camOf(pe); if (!cam) return;
  const target = live(upperEnt) || pe.pawn;
  const changed = pe.camKind !== 'follow' || !pe.camSent || pe.camSent.target !== target || pe.camSent.hip !== (hipZ || 0) || Math.abs((pe.camSent.side || 0) - (side || 0)) >= CONFIG.CAM_MIN_STEP || Math.abs(pe.camSent.back - back) >= CONFIG.CAM_MIN_STEP || Math.abs(pe.camSent.up - up) >= CONFIG.CAM_MIN_STEP;
  if (!changed) return;
  if (!fast && (ifrTickNo + pe.slot) % CONFIG.CAM_RATE_TICKS !== 0 && pe.camKind === 'follow' && pe.camSent && pe.camSent.target === target) return;
  if (cam.GetParent()) cam.SetParent(undefined);
  cam.SetFollowConfig({ followEntity: target, followEyes: false, followOffset: v3(0, 0, hipZ || 0), cameraOffset: v3(-back, side || 0, up),
    clipCameraOffset: CONFIG.CAM_CLIP, cameraOffsetReturnStrength: CONFIG.CAM_CLIP ? CONFIG.CAM_CLIP_RETURN : 1 });
  if (pe.camKind !== 'follow') cam.SetMode(CustomCameraMode.FOLLOW_POSITION);
  pe.camKind = 'follow'; pe.camSent = { back, up, target, hip: hipZ || 0, side: side || 0 };
}
// a script-placed camera (death orbit, spectating, garage backdrop): CONTROLLED, moved every tick
function controlledCamera(pe, pos, lookAt) {
  if (!pe.human) return;
  const cam = camOf(pe); if (!cam) return;
  if (pe.camKind !== 'controlled') { if (cam.GetParent()) cam.SetParent(undefined); cam.SetMode(CustomCameraMode.CONTROLLED); pe.camKind = 'controlled'; pe.camSent = null; }
  const d = vsub(lookAt, pos), h = Math.sqrt(d.x * d.x + d.y * d.y);
  const ang = { pitch: -Math.atan2(d.z, Math.max(1, h)) * R2D, yaw: Math.atan2(d.y, d.x) * R2D, roll: 0 };
  cam.Move({ position: clampWorld(pos), angles: ang });
}
// where the camera is and looks for a follow-camera person (the crosshair ray): the followed point plus the offset turned by
// the eye angles (point_script.d.ts: cameraOffset is rotated by the player's eye angles; x forward, y left, z up)
// 10 Nov 2026 playtest (shots below the reticle): the up axis was f x r, which points DOWN (x forward, y left, z up is right-handed:
// forward x right = -up), so the ray started 2 x `up` (320-420 u) under the real camera; the side kick was left out too
// The followed point is the upper prop's real origin + the hip offset sent (the prop sits off m.pos by the waist pivot, the clip's hip dip
// and the weight bob); without the prop, the mech's hip. clipCameraOffset pulls CS2's camera in toward that point in front of a wall: the
// same line trace here, so the ray starts where the camera really is (a pulled-in camera sees the reticle from lower down).
function cameraRay(pe, m) {
  const e = pe.eye, cs = pe.camSent;
  const ue = cs ? live(renderUpperEnt(pe.slot)) : undefined, uo = ue ? ue.GetAbsOrigin() : null;
  const hip = uo && vfinite(uo) ? v3(uo.x, uo.y, uo.z + (cs.hip || 0)) : renderUpperPos(m);
  const f = fwdOf(e.yaw, e.pitch), r = rightOf(e.yaw);
  const u = v3(r.y * f.z - r.z * f.y, r.z * f.x - r.x * f.z, r.x * f.y - r.y * f.x);   // r x f = up (pitched with the view)
  const back = cs ? cs.back : pe.camBack, up = cs ? cs.up : pe.camUp, side = cs ? cs.side || 0 : 0;
  let pos = vadd(vadd(vadd(hip, vmul(f, -back)), vmul(u, up)), vmul(r, -side));   // cameraOffset y is LEFT = -right
  if (CONFIG.CAM_CLIP) {
    const tr = Instance.TraceLine({ start: hip, end: pos, ignorePlayers: true });
    if (tr && tr.didHit && !tr.startedInSolid && Number.isFinite(tr.fraction)) pos = vadd(hip, vmul(vsub(pos, hip), Math.max(0, tr.fraction - 0.02)));
  }
  return { pos, dir: f };
}

// ---------------------------------------------------------------- input
// the input struct the core wants (docs/INTERFACES.md 3): movement relative to the camera yaw, held keys, edges for taps
function sampleInput(pe, input) {
  const pawn = pe.pawn;
  const fwd = pawn.IsInputPressed(KEYS.fwd), back = pawn.IsInputPressed(KEYS.back);
  const left = pawn.IsInputPressed(KEYS.left), right = pawn.IsInputPressed(KEYS.right);
  const eye = pawn.GetEyeAngles();
  pe.eye.yaw = eye.yaw; pe.eye.pitch = eye.pitch;
  input.mx = (right ? 1 : 0) - (left ? 1 : 0);        // + right of the camera (core: mx right+, my forward+)
  input.my = (fwd ? 1 : 0) - (back ? 1 : 0);          // + forward (camera yaw)
  input.yaw = eye.yaw; input.pitch = eye.pitch;
  input.boost = pawn.IsInputPressed(KEYS.boost);
  input.qb = pawn.WasInputJustPressed(KEYS.qb);
  input.jump = pawn.IsInputPressed(KEYS.jump);
  input.fire[0] = pawn.IsInputPressed(KEYS.ra); input.fire[1] = pawn.IsInputPressed(KEYS.la);
  input.fire[2] = pawn.IsInputPressed(KEYS.rs); input.fire[3] = pawn.IsInputPressed(KEYS.ls);
  input.cycle = pawn.WasInputJustPressed(KEYS.cycle);
  const moved = Math.abs(angleDiff(pe.lastEye.yaw, eye.yaw)) > 2 || Math.abs(eye.pitch - pe.lastEye.pitch) > 2;
  pe.lastEye.yaw = eye.yaw; pe.lastEye.pitch = eye.pitch;
  input.any = fwd || back || left || right || input.boost || input.qb || input.jump || input.fire[0] || input.fire[1] || input.fire[2] || input.fire[3] || input.cycle || moved;
  if (input.any) { pe.lastInput = gameTime(); pe.afkWarned = false; }
  // the crosshair ray for the core's aim (world-space camera position and direction)
  const m = game.mechs.get(pe.slot);
  if (m) { const ray = cameraRay(pe, m); input.camPos = ray.pos; input.camDir = ray.dir; }
}
// menu keys with edge detection for people not piloting (garage, spectators, votes): returns a bitmask of KEYS pressed this tick
function menuKeys(pe) {
  const pawn = live(pe.pawn); if (!pawn) return 0;
  let k = 0;
  if (pawn.WasInputJustPressed(KEYS.fwd)) k |= 1; if (pawn.WasInputJustPressed(KEYS.back)) k |= 2;
  if (pawn.WasInputJustPressed(KEYS.left)) k |= 4; if (pawn.WasInputJustPressed(KEYS.right)) k |= 8;
  if (pawn.WasInputJustPressed(KEYS.jump)) k |= 16; if (pawn.WasInputJustPressed(KEYS.qb)) k |= 32;
  if (pawn.WasInputJustPressed(KEYS.cycle)) k |= 64; if (pawn.WasInputJustPressed(KEYS.ra)) k |= 128;
  if (pawn.WasInputJustPressed(KEYS.la)) k |= 256; if (pawn.WasInputJustPressed(KEYS.ls)) k |= 512;
  if (k) { pe.lastInput = gameTime(); pe.afkWarned = false; }
  return k;
}
const MK = { up: 1, down: 2, left: 4, right: 8, ok: 16, back: 32, cycle: 64, fire: 128, fire2: 256, use: 512 };

// ---------------------------------------------------------------- damage and kills through the real pawn
// every hit the core reports: the pawn's 100 health tracks the mech's AP so assists and the killfeed are CS2's own
function applyDamageEvent(ev) {
  const vp = person(ev.victim); if (!vp) return;
  const victim = live(vp.pawn); if (!victim || !victim.IsAlive()) return;
  const m = game.mechs.get(ev.victim); if (!m) return;
  const hp = victim.GetHealth();
  const wantHp = Math.max(1, Math.ceil(100 * Math.max(0, m.ap) / Math.max(1, m.apMax)));
  const dmg = hp - wantHp;
  if (dmg <= 0) return;
  const ap = person(ev.attacker);
  let attacker = ap ? live(ap.pawn) : undefined;
  if (ap && (!attacker || !attacker.IsAlive())) attacker = live(ap.ctrl);
  const inflictor = attacker;   // the attacker's own pawn: CS2 credits damage, assists and kills through the attacker / inflictor pair
  damageDepth++; allowDamage.add(ev.victim);
  try {
    victim.TakeDamage({ damage: dmg, damageTypes: ev.impact >= 500 ? CSDamageTypes.BLAST : CSDamageTypes.BULLET,
      damageFlags: CSDamageFlags.IGNORE_ARMOR | CSDamageFlags.SUPPRESS_EFFECTS | CSDamageFlags.SUPPRESS_PHYSICS_FORCE, attacker: attacker || undefined, inflictor: inflictor || undefined });
  } finally { damageDepth--; allowDamage.delete(ev.victim); }
}
// a kill from the core: queued, applied with FORCE_DEATH a few ticks apart (the killfeed rolls; a kill blocked by CS2 is logged once)
function queueKill(ev) {
  // the script's own AI mechs (slots 64+) have no pawn, and CS2 counts a kill only when a pawn dies: a human pilot's kill of one is queued
  // for a stand-in (npcKill)
  if (!person(ev.victim)) { const kp = ev.killer >= 0 ? person(ev.killer) : undefined; if (kp && kp.human) pendingKills.push({ victim: -1, killer: ev.killer, weapon: ev.weapon, at: gameTime(), npc: true }); return; }
  pendingKills.push({ victim: ev.victim, killer: ev.killer, weapon: ev.weapon, at: gameTime() });
}
function npcKillScore(killer) {
  const kp = killer >= 0 ? person(killer) : undefined; if (!kp || GameRules.IsWarmupPeriod()) return;
  const c = live(kp.ctrl); if (c) guard('npc score', () => c.AddScore(CONFIG.NPC_KILL_SCORE));
}
// ---- stand-in kills (11 Nov 2026, skink52: "Still no kill credits in game for killing bots"). The enemies of a Sortie and the fill of a map
// where CS2 bots did not join are the script's own AI mechs: nothing of CS2's dies with them, so the scoreboard's kills column and the
// killfeed stayed empty (AddScore only moves the score column). Now a CS2 bot's pawn takes the kill from the pilot: a real kill, with the
// killfeed line carrying that bot's name. Picked: a bot whose own mech is down (its pawn waits in the booth), else one on the other CS2
// team, else the one used longest ago; STANDIN_BACK s later the pawn is revived and personTick mounts it on its mech again or parks it. The
// bot's deaths column counts these. No CS2 bot in the game: CS2 score (NPC_KILL_SCORE) as before. !bots shows the counts.
const standRevive = [];           // [{slot, at}]: stand-ins to bring back
const standStats = { real: 0, score: 0 };
function standInFor(kp, now) {
  let best, bestRank = -1;
  for (const pe of people.values()) {
    if (pe.human || !(pe.team === TEAM_T || pe.team === TEAM_CT)) continue;
    const pawn = live(pe.pawn); if (!pawn) continue;
    if (!pawn.IsAlive() && (typeof pawn.Reset !== 'function' || now - (/** @type {any} */ (pe).standAt || 0) < 0.3)) continue;
    const m = game.mechs.get(pe.slot);
    const rank = (m && m.alive ? 0 : 4) + (pe.team !== kp.team ? 2 : 0) + Math.min(0.99, (now - (/** @type {any} */ (pe).standAt || -1e9)) / 600);
    if (rank > bestRank) { best = pe; bestRank = rank; }
  }
  return best;
}
function npcKill(k, now) {
  const kp = person(k.killer); if (!kp || !kp.human || GameRules.IsWarmupPeriod()) return;
  let attacker = live(kp.pawn);
  if (!attacker || !attacker.IsAlive()) attacker = live(kp.ctrl);
  const sp = CONFIG.STANDIN_KILLS && realKills && attacker ? standInFor(kp, now) : undefined;
  let done = false;
  if (sp) {
    const pawn = sp.pawn;
    guard('stand-in kill', () => {
      if (!pawn.IsAlive()) pawn.Reset();
      if (!pawn.IsAlive()) return;
      damageDepth++; allowDamage.add(sp.slot);
      try {
        pawn.TakeDamage({ damage: 1000, damageTypes: CSDamageTypes.BULLET, damageFlags: CSDamageFlags.FORCE_DEATH | CSDamageFlags.IGNORE_ARMOR | CSDamageFlags.SUPPRESS_PHYSICS_FORCE,
          attacker, inflictor: attacker });
      } finally { damageDepth--; allowDamage.delete(sp.slot); }
      done = !pawn.IsAlive();
    });
    /** @type {any} */ (sp).standAt = now;
    if (done) standRevive.push({ slot: sp.slot, at: now + CONFIG.STANDIN_BACK });
    else warnOnce('standin', 'a stand-in kill did not kill the bot pawn (a plugin or damage filter?): CS2 score instead');
  }
  if (done) { standStats.real++; if (standStats.real === 1) log('AI mech kills are credited as real CS2 kills through CS2 bot stand-ins'); }
  else { standStats.score++; npcKillScore(k.killer); if (!sp && standStats.score === 1) log('no CS2 bot to stand in for an AI mech kill: CS2 score only (kills column unchanged)'); }
  dlog('npc kill: killer ' + k.killer + ' stand-in ' + (sp ? sp.slot : 'none') + ' real ' + done);
}
function standTick(now) {
  while (standRevive.length && standRevive[0].at <= now) {
    const r = standRevive.shift(), pe = person(r.slot); if (!pe || pe.human) continue;
    const pawn = live(pe.pawn) || pawnOf(pe.slot); if (!pawn) continue;
    guard('stand-in back', () => { if (!pawn.IsAlive() && typeof pawn.Reset === 'function') pawn.Reset(); });
    pe.pawn = pawn; pe.status = 'standin';       // personTick: back on its mech, or parked
  }
}
let killNextAt = 0;
function flushKills() {
  const now = gameTime();
  standTick(now);
  if (!pendingKills.length || now < killNextAt) return;
  const k = pendingKills.shift();
  killNextAt = now + 0.05;
  if (k.npc) { npcKill(k, now); return; }
  const vp = person(k.victim); const victim = vp ? live(vp.pawn) : undefined;
  if (!victim) return;
  // a CS2 bot whose pawn is down as a stand-in: back first, so the pilot who destroyed its mech still gets the kill
  if (!victim.IsAlive() && !vp.human && realKills && typeof victim.Reset === 'function') guard('bot back', () => victim.Reset());
  if (!victim.IsAlive()) return;
  const kp = k.killer >= 0 && k.killer !== k.victim ? person(k.killer) : undefined;
  if (!realKills || GameRules.IsWarmupPeriod()) { guard('fake kill', () => { victim.Kill(); }); if (kp && realKills === false) npcKillScore(k.killer); return; }
  let attacker = kp ? live(kp.pawn) : undefined;
  if (kp && (!attacker || !attacker.IsAlive())) attacker = live(kp.ctrl);
  const inflictor = attacker;   // the killer's pawn (a prop as inflictor gave no credit in game, Nov 2026 playtest)
  dlog('kill: victim ' + k.victim + ' killer ' + k.killer + ' person ' + !!kp + ' attacker ' + (attacker ? attacker.constructor.name : 'none') + ' real ' + realKills + ' warm ' + GameRules.IsWarmupPeriod());
  damageDepth++; allowDamage.add(k.victim);
  try {
    victim.TakeDamage({ damage: 1000, damageTypes: CSDamageTypes.BULLET, damageFlags: CSDamageFlags.FORCE_DEATH | CSDamageFlags.IGNORE_ARMOR | CSDamageFlags.SUPPRESS_PHYSICS_FORCE,
      attacker: attacker || undefined, inflictor: inflictor || undefined });
  } catch (err) { warnOnce('kill', 'TakeDamage failed: ' + err); } finally { damageDepth--; allowDamage.delete(k.victim); }
  if (live(victim) && victim.IsAlive()) { warnOnce('killblocked', 'a scripted kill did not kill (a plugin or damage filter?): falling back to Kill()'); guard('kill2', () => victim.Kill()); }
  awaitRespawn.set(k.victim, now);
}
// the respawn watchdog: a human's killed pawn is brought back by the script (revivePawn) once CS2 has had the kill for REVIVE_AFTER s, so
// the garage and the death orbit have a camera; only without Pawn.Reset does it wait 8 s for CS2, and after 3 misses real kills are given up
// (that used to trip on mp_respawnwavetime 10 and switch kill credit off for the whole map)
function respawnWatch(now) {
  for (const [slot, at] of awaitRespawn) {
    const pe = person(slot); const pawn = pe ? live(pe.pawn) : undefined;
    if (pawn && pawn.IsAlive()) { awaitRespawn.delete(slot); respawnFailures = 0; continue; }
    if (pe && pe.human && now - at >= CONFIG.REVIVE_AFTER && revivePawn(pe)) { awaitRespawn.delete(slot); respawnFailures = 0; continue; }
    if (now - at < 8) continue;
    awaitRespawn.delete(slot);
    if (pe && !pe.human) continue;    // CS2 bots: their pawn comes back when their mech does (mountPawn)
    respawnFailures++;
    if (respawnFailures >= 3 && realKills) { realKills = false; log('WARNING: players are not respawning after scripted kills (check mp_respawn_on_death_t/ct): kills no longer go through CS2'); }
  }
}
