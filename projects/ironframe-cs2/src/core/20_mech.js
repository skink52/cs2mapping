// ===================================================================================================================
// IRONFRAME core, part 2: the mech. State (docs/INTERFACES.md section 3.2 names, plus internals), the loadout applied
// to numbers, and the movement model of DESIGN.md section 4: walk, boost / assault boost, quick boost, jump / hover, EN
// with regen pause and stall, landing lag, stagger speed, arena box, heightfield ground with a step limit and the
// world sweep near struct cells. Every field is declared in the constructor (one hidden class for 128 mechs).
// ===================================================================================================================

class IF_Weapon {
  constructor(hp) {
    this.hp = hp; this.part = null; this.w = null; this.type = ''; this.id = 0;
    this.ammo = 0; this.mag = 0; this.magSize = 0; this.cd = 0; this.heat = 0; this.overheat = false;
    this.charge = 0; this.charging = false; this.reloading = false; this.reloadT = 0; this.windup = 0; this.braceT = 0; this.pending = false;
    this.raised = false; this.charges = 0; this.chargeCd = 0; this.salvo = 0; this.salvoT = 0; this.salvoTarget = -1;
    this.dmgMult = 1; this.statMult = 1; this.lastShot = -99; this.wasFire = false; this.firing = false;
    this.traceT = -99; this.traceDir = IF_v3(1, 0, 0); this.traceDist = 0; this.traceZ = 0; this.penalty = 0; this.bonusCharges = 0;
    this.healLeft = 0; this.healRate = 0; this.healTarget = -1; this.healT = 0;
    this.shots = 0; this.hits = 0; this.dmg = 0;   // round statistics (balance tables)
    this.burstLeft = 0; this.burstT = 0; this.mlock = []; this.mlDone = 0; this.mlHold = 0; this.salvoN = 0; this.salvoTargets = null;
    this.mslWait = false; this.loftTop = 0; this.loftTick = -9999;   // missile: held on a building lock; the loft apex of the current salvo
  }
  setup(part, level, caps) {
    this.part = part; this.w = part ? part.w : null; this.type = this.w ? this.w.type : ''; this.id = part ? part.id : 0;
    this.cd = 0; this.heat = 0; this.overheat = false; this.charge = 0; this.charging = false; this.reloading = false; this.reloadT = 0;
    this.windup = 0; this.braceT = 0; this.pending = false; this.raised = false; this.salvo = 0; this.salvoT = 0; this.salvoTarget = -1;
    this.wasFire = false; this.firing = false; this.traceT = -99; this.healLeft = 0; this.healRate = 0; this.healTarget = -1; this.healT = 0;
    this.shots = 0; this.hits = 0; this.dmg = 0;
    this.burstLeft = 0; this.burstT = 0; this.mlock.length = 0; this.mlDone = 0; this.mlHold = 0; this.salvoN = 0; this.salvoTargets = null;
    this.mslWait = false; this.loftTop = 0; this.loftTick = -9999;
    if (!this.w) { this.ammo = 0; this.mag = 0; this.magSize = 0; this.charges = 0; this.chargeCd = 0; this.dmgMult = 1; this.statMult = 1; return; }
    const w = this.w, up = part.upgrade || { stat: '', pct: 0 };
    const pct = IF_clamp(up.pct * level, -100, up.stat === 'damage' ? caps.dps_pct : 100);
    this.dmgMult = up.stat === 'damage' ? 1 + pct / 100 : 1;
    this.statMult = up.stat === 'damage' ? 1 : 1 + pct / 100;
    this.magSize = w.mag || 0; this.mag = this.magSize;
    this.ammo = w.ammo !== undefined ? w.ammo - this.magSize : 0;
    this.charges = w.charges || 0;
    this.bonusCharges = (w.type === 'ability' && up.stat === 'charges') ? Math.floor(level / 3) : 0;
    this.charges += this.bonusCharges;
    this.chargeCd = 0;
  }
  // the time between shots of a rate / cd weapon
  get period() { const w = this.w; return w ? (w.rate ? 1 / w.rate : (w.cd || 1)) : 1; }
  get empty() { return !this.w; }
  // ammo left including the magazine (-1 = unlimited)
  get ammoLeft() { return this.w && this.w.ammo !== undefined ? this.ammo + this.mag : -1; }
}

class IF_Mech {
  constructor(slot) {
    // identity
    this.slot = slot; this.team = 0; this.human = false; this.npc = slot >= IF_NPC_SLOT0; this.fill = false; this.isBoss = false; this.name = 'slot ' + slot; this.alive = false;
    this.pilot = null; this.rank = 0; this.rating = 0; this.tier = 'normal';
    // build (set by IF_mechApplyLoadout)
    this.frame = null; this.cls = null; this.legs = null; this.loadout = [0, 0, 0, 0, 0, 0, 0, 0, 0]; this.loadoutStr = ''; this.pendingLoadout = '';
    this.gen = null; this.bst = null; this.fcs = null; this.paint = null; this.mods = null; this.boss = false; this.scale = 1;
    this.weapons = [new IF_Weapon(0), new IF_Weapon(1), new IF_Weapon(2), new IF_Weapon(3)];
    this.apMax = 1; this.enMax = 1; this.enRegen = 0; this.enOutput = 1; this.enLoad = 0; this.enScale = 1; this.stallTime = 2.5; this.weight = 0; this.load = 1;
    this.walkSpeed = 1; this.boostSpeed = 1; this.qbSpeed = 1; this.qbCost = 450; this.drainMult = 1; this.carrier = false; this.hoverMult = 1; this.assaultMult = 1.25;
    this.radius = 90; this.height = 288; this.landLagTime = 0.45; this.staggerMax = 1400; this.lockSoft = 0.3; this.lockHard = 0.9;
    this.meleeMult = 1; this.cannonMoveAcc = 0.6; this.loaded = false;
    // pose
    this.pos = IF_v3(0, 0, 0); this.vel = IF_v3(0, 0, 0); this.legYaw = 0; this.torsoYaw = 0; this.pitch = 0; this.aimPitch = 0;
    this.aimOrigin = IF_v3(0, 0, 0); this.aimDir = IF_v3(1, 0, 0); this.wish = IF_v3(0, 0, 0); this.wishLen = 0;
    this.onGround = true; this.boosting = false; this.assault = false; this.qbTime = 0; this.qbCd = 0; this.qbAt = -99; this.qbDir = IF_v3(1, 0, 0); this.hover = false; this.braced = false;
    this.qbJet = 0; this.qbChained = false; this.qbCdTime = 0.45; this.weightF = 0;   // AC_FEEL: QB jet, two-step chain, reload by class/weight
    this.airTime = 0; this.fallSpeed = 0; this.groundZ = 0; this.speed = 0; this.stepOff = 0; this.legMode = 0; this.wallT = 0; this.wallNx = 0; this.wallNy = 0; this.gcX = 1e9; this.gcY = 1e9; this.gcZ = 0; this.gcH = 0; this.gcHint = 0;
    // player-clip ground cache (IF_clipStep) and the reticle point under the screen centre (IF_reticle, 40_combat.js)
    this.cgX = 1e9; this.cgY = 1e9; this.cgZ = 0; this.cgG = -1e9; this.clipBlocks = 0;
    this.reticle = IF_v3(0, 0, 0); this.retTick = -1; this.retReach = 0; this.retDist = 0; this.retHit = false;
    // vitals
    this.ap = 1; this.en = 1; this.enStalled = 0; this.enPause = 0; this.enPauseTime = 0.6; this.stagger = 0; this.staggered = 0; this.staggerDecayT = 0;
    this.staggerEndT = -99; this.protect = 0; this.landLag = 0; this.decoyT = 0; this.rookieMult = 1; this.bossPhase = 0;
    // lock, threats
    this.lock = { target: -1, stage: 0, t: 0, los: false, graceT: 0, serial: 0, candidate: -1, skip: -1 };
    this.threats = []; this.threatPool = [];
    this.lockedBy = 0;        // how many enemies hold a hard lock on this mech (HUD warning)
    // lifecycle
    this.streak = 0; this.dropT = 0; this.deathT = -1; this.deathPos = IF_v3(0, 0, 0); this.respawnT = 0; this.wantSpawn = false; this.spawnT = -99;
    this.killer = -1; this.lastDamageT = -99; this.lastFireT = -99; this.aliveT = 0;
    // input (humans: setInput each tick; bots: IF_Ai fills it). mx right+, my forward+, yaw/pitch degrees, camPos/camDir optional
    this.input = { mx: 0, my: 0, yaw: 0, pitch: 0, boost: false, qb: false, jump: false, fire: [false, false, false, false], cycle: false, cycleHeld: false, any: false,
                   camPos: null, camDir: null, camDist: 0 };
    this.prevQb = false; this.prevCycle = false; this.prevJump = false;
    // melee lunge, repair, bubble
    this.lungeT = 0; this.lungeDir = IF_v3(1, 0, 0); this.lungeHp = -1; this.lungeTarget = -1; this.lungeHit = false; this.lungeSpeed = 2400;
    this.healLeft = 0; this.healRate = 0; this.bubble = -1;
    // burn (flamethrower), orbit drones and mines live
    this.burnT = 0; this.burnDps = 0; this.burnAcc = 0; this.burnBy = -1; this.burnHp = 0; this.burnId = 0; this.burnKey = ''; this.droneN = 0; this.mineN = 0;
    // damage bookkeeping per attacker slot (assists) and the round summary
    this.dmgBy = new Float64Array(IF_MAX_MECHS); this.dmgT = new Float64Array(IF_MAX_MECHS);
    this.sum = { xp: 0, credits: 0, kills: 0, deaths: 0, assists: 0, captures: 0, damage: 0, pveKills: 0, bossKills: 0, won: false, streakBest: 0,
                 bountyKills2: 0, bountyKills3: 0, survive: 0, score: 0,
                 // round statistics for the server (80_game.js pilotStats; SERVER_CONTRACT.md section 2b): numbers only (the reset zeroes them)
                 shots: 0, hits: 0, qb: 0, mslFired: 0, dodges: 0, staggers: 0, od: 0, crates: 0, flagReturns: 0, dmgTaken: 0, lifeBest: 0 };
    this.wsum = {};           // weapon part key -> [kills, damage] this round
    // pose history ring (lag mercy)
    this.hist = new Float32Array(IF_POSE_HISTORY * 3); this.histN = 0;
    // ai state (IF_Ai)
    this.ai = null; this.squad = -1;
    // adapter conveniences
    this.wreckT = 0;
  }

  get protectedNow() { return this.protect > 0 || this.dropT > 0; }
  get center() { return this.pos.z + this.height * 0.5; }
  // the pose k ticks ago (k < IF_POSE_HISTORY) written into o
  poseAgo(k, o) {
    if (this.histN <= k) { o.x = this.pos.x; o.y = this.pos.y; o.z = this.pos.z; return o; }
    const i = ((this.histN - 1 - k) % IF_POSE_HISTORY) * 3;
    o.x = this.hist[i]; o.y = this.hist[i + 1]; o.z = this.hist[i + 2]; return o;
  }
  pushPose() {
    const i = (this.histN % IF_POSE_HISTORY) * 3;
    this.hist[i] = this.pos.x; this.hist[i + 1] = this.pos.y; this.hist[i + 2] = this.pos.z; this.histN++;
  }
  spendEn(x) {
    this.en -= x; this.enPause = this.enPauseTime;
    if (this.en <= 0) { this.en = 0; if (this.enStalled <= 0) { this.enStalled = this.stallTime; this.enEmptyFlag = true; } }
  }
  canSpend(x) { return this.enStalled <= 0 && this.en >= Math.min(x, this.enMax * 0.1); }
}
IF_Mech.prototype.enPauseTime = 0.6;
IF_Mech.prototype.enEmptyFlag = false;

// The upgrade level of a part for a pilot (0 stand-alone)
function IF_upgradeLevel(pilot, id, caps) {
  if (!pilot || !pilot.upgrades) return 0;
  const l = pilot.upgrades[id] !== undefined ? pilot.upgrades[id] : pilot.upgrades[String(id)];
  return IF_clamp(IF_fin(+l, 0) | 0, 0, caps.levels);
}

// Apply a parsed loadout (ids[9], already validated) to the mech's numbers. Returns false when a part is missing.
function IF_mechApplyLoadout(game, m, ids) {
  const P = game.P, caps = P.caps, MV = game.move, pilot = m.pilot;
  const frame = P.byId.get(ids[0]), gen = P.byId.get(ids[5]), bst = P.byId.get(ids[6]), fcs = P.byId.get(ids[7]);
  if (!frame || !gen || !bst || !fcs || !frame.class) return false;
  const cls = P.classes[frame.class], legs = P.legs[frame.legs] || P.legs.biped;
  if (!cls) return false;
  const mods = frame.mods || {};
  const lvl = (id) => IF_upgradeLevel(pilot, id, caps);
  m.frame = frame; m.cls = cls; m.legs = legs; m.gen = gen; m.bst = bst; m.fcs = fcs; m.paint = P.byId.get(ids[8]) || null; m.mods = mods;
  m.boss = !!frame.boss; m.scale = frame.scale || 1;
  for (let i = 0; i < 9; i++) m.loadout[i] = ids[i];
  m.loadoutStr = ids.join(',');
  // frame
  const apPct = Math.min(caps.ap_pct, (frame.upgrade ? frame.upgrade.pct : 0) * lvl(frame.id));
  m.apMax = Math.round(cls.ap * (mods.ap || 1) * (1 + apPct / 100));
  m.radius = cls.radius * m.scale; m.height = cls.height * m.scale;
  m.landLagTime = cls.land_lag * legs.land_lag_mult;
  m.staggerMax = Math.round(cls.stagger * legs.stagger_mult * (mods.stagger || 1));
  m.meleeMult = mods.melee || 1; m.cannonMoveAcc = mods.cannon_move_acc || legs.cannon_move_acc;
  // weights and EN
  let weight = 0, enLoad = 0;
  for (let i = 0; i < 9; i++) { const p = ids[i] ? P.byId.get(ids[i]) : null; if (p) { weight += p.weight || 0; enLoad += p.en || 0; } }
  m.weight = weight; m.load = cls.load * (mods.load || 1) + ((bst.b && bst.b.load_bonus) || 0);
  m.enLoad = enLoad; m.enOutput = gen.g.output; m.enScale = enLoad > m.enOutput ? m.enOutput / enLoad : 1;
  const genPct = (gen.upgrade ? gen.upgrade.pct : 0) * lvl(gen.id);
  m.enMax = Math.round(gen.g.capacity * (1 + genPct / 100));
  m.enRegen = gen.g.regen * (mods.regen || 1) * m.enScale;
  m.stallTime = gen.g.stall !== undefined ? gen.g.stall : MV.stall;
  // booster
  const b = bst.b, eff = 1 - Math.min(caps.mobility_pct, (bst.upgrade ? bst.upgrade.pct : 0) * lvl(bst.id)) / 100;
  // AC6-style weight: above weight_ideal of the load limit boost speed drops (up to weight_boost_loss at the limit) and the
  // QB reload grows (up to x(1 + weight_qb_cd)); below it the loadout weight changes nothing (docs/AC_FEEL.md)
  const wi = MV.weight_ideal !== undefined ? MV.weight_ideal : 1;
  m.weightF = wi < 1 && m.load > 0 ? IF_clamp((weight / m.load - wi) / (1 - wi), 0, 1) : 0;
  m.walkSpeed = cls.walk * (mods.walk || 1);
  m.boostSpeed = cls.boost * b.thrust * (mods.boost || 1) * (1 - (MV.weight_boost_loss || 0) * m.weightF);
  m.qbCdTime = (cls.qb_cd || MV.qb_cd) * (1 + (MV.weight_qb_cd || 0) * m.weightF);
  m.qbSpeed = cls.qb * b.qb_mult * (mods.qb || 1);
  m.qbCost = MV.qb_cost * b.qb_cost_mult * eff;
  m.drainMult = b.drain_mult * eff; m.hoverMult = b.hover; m.assaultMult = b.assault_mult || MV.assault_mult;
  // fcs
  const f = fcs.f, fl = 1 + Math.max(-30, (fcs.upgrade ? fcs.upgrade.pct : 0) * lvl(fcs.id)) / 100;
  m.lockSoft = f.soft * fl; m.lockHard = f.hard * fl;
  // weapons
  for (let hp = 0; hp < 4; hp++) {
    const id = ids[1 + hp];
    m.weapons[hp].setup(id ? P.byId.get(id) || null : null, id ? lvl(id) : 0, caps);
  }
  IF_traitApply(game, m);
  m.loaded = true;
  return true;
}

// Ground height under (x, y): the heightfield away from struct cells, a world trace near them (counted). zHint is the
// mech's current z (the trace starts above it).
// A per-mech cache (m) reuses the last traced ground within 40 u (the heightfield slope carries it), so a walking mech
// near structures traces about every third tick, not every tick.
function IF_groundAt(game, x, y, zHint, height, m) {
  const nav = game.nav;
  if (nav.nearStruct(x, y) && game.world && game.world.traceLine) {
    if (m && Math.abs(x - m.gcX) < 40 && Math.abs(y - m.gcY) < 40 && Math.abs(zHint - m.gcHint) < 150) return m.gcZ + nav.height(x, y) - m.gcH;
    const a = game._ta, b = game._tb;
    a.x = x; a.y = y; a.z = zHint + height * 0.5; b.x = x; b.y = y; b.z = zHint - 600;
    const r = game.trace(a, b);
    const z = r && r.hit && r.pos && Number.isFinite(r.pos.z) ? r.pos.z : nav.height(x, y);
    if (m) { m.gcX = x; m.gcY = y; m.gcZ = z; m.gcH = nav.height(x, y); m.gcHint = zHint; }
    return z;
  }
  return nav.height(x, y);
}

// ---- player clips. Clip brushes (toolsclip / toolsplayerclip) block only player movement: Instance.TraceLine / TraceSphere have no
// mask and ignore them, Instance.TracePlayer (a pawn's hull, 32 x 32 x 72) does not. world.traceClip(a, b, slot) is that hull trace
// (null when the adapter has no pawn to trace with); it returns {hit, solid (started in solid), pos (hull origin = feet at the stop),
// normal, frac}. The world doesn't say where clips are, so they are learned: every cfg.clip.discover ticks a moving mech sweeps one
// hull along its next stretch of travel; a hit a line trace doesn't share (or doesn't reach) is a clip and marks its cells and
// cfg.clip.near cells around (game.clipMap). Inside marked cells the full check runs every tick: a hull sweep at each of
// cfg.clip.heights above the feet (the step height is left free, the sweep looks one mech radius ahead) and a hull trace down for clip
// tops to stand on. Budget: ~8 hull traces per tick at 64 moving mechs plus ~3 per mech near a clip.
function IF_clipMark(game, x, y) {
  const nav = game.nav, r = (game.cfg.clip && game.cfg.clip.near) | 0;
  if (!game.clipMap || game.clipMap.length !== nav.n) game.clipMap = new Uint8Array(nav.n);
  const i0 = nav.ci(x), j0 = nav.cj(y);
  for (let dj = -r; dj <= r; dj++) for (let di = -r; di <= r; di++) {
    const i = i0 + di, j = j0 + dj;
    if (i >= 0 && j >= 0 && i < nav.w && j < nav.h) game.clipMap[j * nav.w + i] = 1;
  }
}
function IF_clipNear(game, x, y) { const M = game.clipMap; return !!M && M[game.nav.idx(x, y)] === 1; }
function IF_traceClip(game, a, b, slot) {
  game.stats.clipTraces = (game.stats.clipTraces || 0) + 1;
  if (game.clipTick !== game.tickN) { game.clipLast = game.clipTick === game.tickN - 1 ? game.clipUsed : 0; game.clipTick = game.tickN; game.clipUsed = 0; }
  game.clipUsed++;
  try { const r = game.world.traceClip(a, b, slot); return r && !r.solid ? r : null; } catch (err) { return null; }
}
const IF_clipOut = { x: 0, y: 0, z: 0, g: 0 };
function IF_clipStep(game, m, ox, oy, oz, nx, ny, nz, g, stepMax, dt) {
  const C = game.cfg.clip, a = game._ta, b = game._tb, o = IF_clipOut;
  o.x = nx; o.y = ny; o.z = nz; o.g = g;
  const hull = C.hull || 16, look = Math.max(0, m.radius - hull), hs = C.heights || [88, 208];
  const near = IF_clipNear(game, ox, oy) || IF_clipNear(game, nx, ny);
  if (!near) {
    // discovery: one hull along the next `discover` ticks of travel (plus the reach of the mech's body), staggered over the mechs
    const every = Math.max(1, C.discover | 0);
    if (((game.tickN + m.slot) % every) !== 0) return null;
    const T = every * dt, vx = m.vel.x * T, vy = m.vel.y * T, vz = m.vel.z * T, hl = Math.sqrt(vx * vx + vy * vy);
    if (hl < 8 && Math.abs(vz) < 8) return null;
    // walking: the hull rides above the step height; falling: at the feet (a clip top under the mech)
    const h = !m.onGround && vz < -8 ? 8 : Math.max(hs[0], stepMax + 8);
    a.x = ox; a.y = oy; a.z = oz + h;
    b.x = ox + vx + (hl > 1 ? vx / hl * look : 0); b.y = oy + vy + (hl > 1 ? vy / hl * look : 0); b.z = Math.max(oz + vz, game.nav.height(b.x, b.y)) + h;
    const r = IF_traceClip(game, a, b, m.slot);
    if (!r || !r.hit || !Number.isFinite(r.frac)) return null;
    // a clip or ordinary world (the sphere sweep's and the ground's job)? Ask a line, which doesn't see clips: under a top / slope the
    // hull stopped on, a line straight down meets the world within 40 u; along a wall, a line at the hull's middle meets it as early
    const len = Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2 + (b.z - a.z) ** 2), hd = r.frac * len;
    const hx = IF_lerp(a.x, b.x, r.frac), hy = IF_lerp(a.y, b.y, r.frac), hz = IF_lerp(a.z, b.z, r.frac);
    let lr = null;
    if (game.world.traceLine) {
      if (r.normal && r.normal.z > 0.6) { a.x = hx; a.y = hy; a.z = hz + 2; b.x = hx; b.y = hy; b.z = hz - 40; lr = game.trace(a, b); if (lr && lr.hit) return null; }
      else { a.z += 36; b.z += 36; lr = game.trace(a, b); if (lr && lr.hit && Number.isFinite(lr.frac) && lr.frac * len <= hd + 40) return null; }
    }
    IF_clipMark(game, hx, hy);
    game.stats.clipFound = (game.stats.clipFound || 0) + 1;
    // fall through: this tick gets the full check too
  }
  // ---- horizontal: a hull sweep at each height band from the old feet to the new ones plus the body's reach (look) ahead; the reach runs
  // along the pilot's wish when that leans forward, so a mech pressing into a wall while its velocity runs along it still feels it. A wall
  // hit is a plane (the hull centre at contact, the horizontal normal): the new feet are pushed back to `look` in front of it. That stops a
  // head-on move and keeps the along-wall part of an angled one (sliding) without a second sweep. (The first version stopped the move at
  // the hit: an angled mech stuck to the wall, and one moving nearly along it sank its body in: test/playtest_combat.cjs.)
  // Budget: the upper band runs every other tick (overhangs: the look-ahead covers two ticks); when the last tick used more than
  // cfg.clip.budget hull traces, a slow mech (under half its reach a tick) sweeps every other tick too. Worst case on the mock engine (its
  // random traces mark every cell): 117 -> ~70 hull traces a tick at 64 mechs.
  const dx = nx - ox, dy = ny - oy, L = Math.sqrt(dx * dx + dy * dy), odd = ((game.tickN + m.slot) & 1) === 1;
  const busy = game.clipLast > (C.budget || 64) && L <= look * 0.5;
  if (L > 0.5 && !(busy && odd)) {
    let lx = dx / L, ly = dy / L;
    if (m.wishLen > 0.1 && m.wish.x * lx + m.wish.y * ly > 0) { lx = m.wish.x / m.wishLen; ly = m.wish.y / m.wishLen; }
    let hit = 0;
    for (let k = 0; k < hs.length; k++) {
      const h = Math.max(hs[k], stepMax + 8);
      if (k > 0 && (h + 72 > m.height + 40 || odd)) break;   // a short mech: the first band covers it; the upper one every other tick
      a.x = ox; a.y = oy; a.z = oz + h; b.x = o.x + lx * look; b.y = o.y + ly * look; b.z = o.z + h;
      const r = IF_traceClip(game, a, b, m.slot);
      if (!r || !r.hit || !Number.isFinite(r.frac)) continue;
      const n = r.normal;
      if (n && n.z > 0.6) continue;                          // a walkable slope or a top, not a wall
      const px = IF_lerp(a.x, b.x, r.frac), py = IF_lerp(a.y, b.y, r.frac), nl = n ? Math.sqrt(n.x * n.x + n.y * n.y) : 0;
      if (nl > 0.1) {
        const qx = n.x / nl, qy = n.y / nl, gap = (o.x - px) * qx + (o.y - py) * qy;
        if (gap < look) { o.x += qx * (look - gap); o.y += qy * (look - gap); }
        const vn = m.vel.x * qx + m.vel.y * qy; if (vn < 0) { m.vel.x -= qx * vn; m.vel.y -= qy * vn; }
      } else { o.x = ox; o.y = oy; m.vel.x = 0; m.vel.y = 0; }   // no usable normal: stay put
      // the clip map follows the wall as the mech slides along it (discovery sweeps run along the velocity, parallel to the wall then)
      IF_clipMark(game, px, py);
      hit++;
    }
    if (hit) {
      if (m.qbJet > 0) m.qbJet = 0;
      m.clipBlocks++;
      if (Math.abs(o.x - ox) + Math.abs(o.y - oy) > 0.5) o.g = IF_groundAt(game, o.x, o.y, oz, m.height, m);
      else o.g = IF_groundAt(game, ox, oy, oz, m.height);
    }
  }
  // ---- clip tops to stand on: a hull down from step height over the feet to the world ground (cached while the mech stays put)
  const top = Math.max(oz, o.z) + stepMax;
  if (Math.abs(o.x - m.cgX) < 8 && Math.abs(o.y - m.cgY) < 8 && Math.abs(o.z - m.cgZ) < 8) { if (m.cgG > o.g && m.cgG <= top) o.g = m.cgG; }
  else if (top > o.g + 2) {
    a.x = o.x; a.y = o.y; a.z = top; b.x = o.x; b.y = o.y; b.z = o.g;
    const r = IF_traceClip(game, a, b, m.slot);
    const cg = r && r.hit && r.pos && Number.isFinite(r.pos.z) && (!r.normal || r.normal.z > 0.5) ? r.pos.z : -1e9;
    m.cgX = o.x; m.cgY = o.y; m.cgZ = o.z; m.cgG = cg;
    if (cg > o.g + 1) o.g = cg;
  }
  return o;
}

// One movement step for a live mech.
function IF_mechStep(game, m, dt) {
  const MV = game.move, inp = m.input, A = game.arena.bounds;
  // ---- timers
  if (m.qbCd > 0) m.qbCd -= dt;
  if (m.qbTime > 0) m.qbTime -= dt;
  if (m.landLag > 0) m.landLag -= dt;
  if (m.decoyT > 0) m.decoyT -= dt;
  if (m.protect > 0 && m.dropT <= 0) m.protect -= dt;
  if (m.staggered > 0) { m.staggered -= dt; if (m.staggered <= 0) { m.staggered = 0; m.stagger = 0; m.staggerEndT = game.time; } }
  else if (m.staggerDecayT > 0) m.staggerDecayT -= dt;
  else if (m.stagger > 0) m.stagger = Math.max(0, m.stagger - MV.stagger_decay * dt);
  m.aliveT += dt;
  const staggered = m.staggered > 0, lagged = m.landLag > 0, braced = m.braced, lunging = m.lungeT > 0;
  // ---- aim: torso follows the camera; pitch for the prop is clamped, the gun line keeps the camera pitch
  m.torsoYaw = IF_normAngle(IF_fin(inp.yaw, m.torsoYaw));
  m.aimPitch = IF_clamp(IF_fin(inp.pitch, 0), -89, 89);
  m.pitch = IF_clamp(m.aimPitch, -MV.torso_pitch, MV.torso_pitch);
  const eyeZ = m.pos.z + m.height * 0.8;
  m.aimOrigin.x = m.pos.x; m.aimOrigin.y = m.pos.y; m.aimOrigin.z = eyeZ;
  const cd = inp.camDir, cp = inp.camPos;
  if (cd && cp && Number.isFinite(cd.x) && Number.isFinite(cp.x)) {
    const far = inp.camDist > 1 ? inp.camDist : 6000;
    const tx = cp.x + cd.x * far - m.aimOrigin.x, ty = cp.y + cd.y * far - m.aimOrigin.y, tz = cp.z + cd.z * far - m.aimOrigin.z;
    const l = Math.sqrt(tx * tx + ty * ty + tz * tz);
    if (l > 1) { m.aimDir.x = tx / l; m.aimDir.y = ty / l; m.aimDir.z = tz / l; } else IF_fwd(m.aimDir, m.torsoYaw, m.aimPitch);
  } else IF_fwd(m.aimDir, m.torsoYaw, m.aimPitch);
  // ---- wish direction (camera relative)
  const yr = m.torsoYaw * IF_D2R, fx = Math.cos(yr), fy = Math.sin(yr), rx = fy, ry = -fx;
  let mx = IF_clamp(IF_fin(inp.mx, 0), -1, 1), my = IF_clamp(IF_fin(inp.my, 0), -1, 1);
  if (m.dropT <= 0 && (braced || lunging)) { mx = 0; my = 0; }
  let wx = fx * my + rx * mx, wy = fy * my + ry * mx;
  let wl = Math.sqrt(wx * wx + wy * wy);
  if (wl > 1) { wx /= wl; wy /= wl; wl = 1; }
  m.wish.x = wx; m.wish.y = wy; m.wishLen = wl;
  // The legs never twist far from the torso (10 Nov 2026 playtest: "legs ... rotating through 360 looks weird": they faced the travel
  // direction whatever the torso did, up to 180 deg off it). Moving within leg_fwd deg of the torso's facing they face the travel
  // direction; moving backwards (past 180 - leg_fwd) they face the other way and back-pedal; in between they keep leg_strafe deg
  // toward the travel side and side-step (the adapter picks walk / strafe / walk_back from the angle between velocity and legs). A
  // hard limit of leg_twist deg drags them along when the torso spins faster than they turn. legMode: 0 forward, 1 strafe, 2 back.
  {
    const fwdC = MV.leg_fwd !== undefined ? MV.leg_fwd : 60, hy = 8;
    let tgt = m.torsoYaw, rate = MV.leg_turn * 0.5;
    if (wl > 0.1) {
      const rel = IF_angleDiff(m.torsoYaw, IF_yawOf(wx, wy)), ar = Math.abs(rel);
      const mode = m.legMode === 0 ? (ar <= fwdC + hy ? 0 : ar >= 180 - fwdC ? 2 : 1) : m.legMode === 2 ? (ar >= 180 - fwdC - hy ? 2 : ar <= fwdC ? 0 : 1)
        : (ar <= fwdC - hy ? 0 : ar >= 180 - fwdC + hy ? 2 : 1);
      m.legMode = mode;
      tgt = mode === 0 ? m.torsoYaw + rel : mode === 2 ? m.torsoYaw + IF_normAngle(rel + 180) : m.torsoYaw + (rel > 0 ? 1 : -1) * (MV.leg_strafe !== undefined ? MV.leg_strafe : 30);
      rate = MV.leg_turn;
    } else if (m.boosting) rate = 0;
    if (rate > 0) m.legYaw = IF_turnAngle(m.legYaw, IF_normAngle(tgt), rate * dt);
    const tw = IF_angleDiff(m.torsoYaw, m.legYaw), mx2 = MV.leg_twist !== undefined ? MV.leg_twist : 75;
    if (Math.abs(tw) > mx2) m.legYaw = IF_normAngle(m.torsoYaw + (tw > 0 ? mx2 : -mx2));
  }
  // ---- speed multiplier
  let speedMul = 1;
  if (staggered) speedMul = MV.stagger_speed;
  // A hard landing plants the mech for the landing animation (11 Nov 2026, skink52: it slid sideways through it at half speed): no walking
  // and the slide is braked. Only a fall faster than MV.land_fall_speed sets landLag, a small hop does not. A quick boost breaks out.
  const planted = lagged && m.onGround && m.qbTime <= 0;
  if (planted) { speedMul = 0; const kb = Math.max(0, 1 - 14 * dt); m.vel.x *= kb; m.vel.y *= kb; }
  else if (lagged) speedMul *= 0.5;
  if (m.featSpeed != null) speedMul *= m.featSpeed;   // 0 = rooted (Bastion siege mode)
  // ---- boost
  const canBoost = !staggered && !lagged && !braced && m.enStalled <= 0 && m.en > 0 && m.dropT <= 0;
  m.boosting = !!inp.boost && canBoost;
  m.assault = m.boosting && !m.onGround && my > 0.5;
  if (m.boosting) {
    // AC4 / AC6: skating on the ground costs no EN (regen runs at boost_regen_mult meanwhile); gliding in the air drains
    const gd = MV.ground_boost_drain !== undefined ? MV.ground_boost_drain : MV.boost_drain;
    let drain = (m.onGround && !m.assault ? gd : MV.boost_drain) * m.drainMult * (m.assault ? MV.assault_drain_mult : 1) * (m.carrier ? 1.5 : 1);
    if (m.onGround && wl < 0.1) drain *= 0.35;   // idling with the boosters lit costs little
    if (drain > 0) m.spendEn(drain * dt);
    if (m.en <= 0) m.boosting = false;
  }
  let target = (m.boosting ? m.boostSpeed * (m.assault ? m.assaultMult : 1) : m.walkSpeed) * speedMul;
  // ---- quick boost (edge)
  const qbPress = !!inp.qb && !m.prevQb; m.prevQb = !!inp.qb;
  // AC6: mashing QB in the last stagger_qb_out s of a stagger breaks out of it
  const qbOut = staggered && MV.stagger_qb_out > 0 && m.staggered <= MV.stagger_qb_out;
  // AC4 two-step: one extra QB inside the reload, qb_chain s after the first, at least qb_chain_angle off its line, x qb_chain_cost EN
  let chain = false;
  if (qbPress && m.qbCd > 0 && !m.qbChained && MV.qb_chain > 0 && game.time - m.qbAt >= MV.qb_chain && wl > 0.1 && !(m.frame && m.frame.trait === 'ronin')) {
    const c = (wx * m.qbDir.x + wy * m.qbDir.y) / wl;
    chain = c <= Math.cos((MV.qb_chain_angle || 60) * IF_D2R);
  }
  const qbCost = m.qbCost * (chain ? (MV.qb_chain_cost || 1) : 1);
  if (qbPress && (m.qbCd <= 0 || chain) && (!staggered || qbOut) && !braced && !lunging && m.dropT <= 0 && m.canSpend(qbCost) && (m.onGround || m.legs.qb_air)) {
    if (qbOut) { m.staggered = 0; m.stagger = 0; m.staggerEndT = game.time; speedMul = 1; }
    if (lagged) { m.landLag = 0; speedMul = 1; }      // the dodge is the way out of a landing
    let dx = wx, dy = wy;
    if (wl < 0.1) { dx = -fx; dy = -fy; }
    else { dx /= wl; dy /= wl; }
    m.vel.x = dx * m.qbSpeed; m.vel.y = dy * m.qbSpeed;
    if (!m.onGround) m.vel.z = Math.max(m.vel.z, -200);
    m.qbCd = m.qbCdTime; m.qbTime = MV.qb_steer_time; m.qbAt = game.time; m.qbDir.x = dx; m.qbDir.y = dy; m.qbDir.z = 0;
    m.qbJet = MV.qb_jet || 0; m.qbChained = chain;
    m.spendEn(qbCost);
    m.sum.qb++;
    game.emit({ t: 'qb', slot: m.slot, chain });
  }
  // ---- horizontal velocity
  const steer = m.qbTime > 0 ? 0.5 : 1;
  const hv = Math.sqrt(m.vel.x * m.vel.x + m.vel.y * m.vel.y);
  if (m.qbJet > 0 && (staggered && m.staggered > 0 || lunging)) m.qbJet = 0;
  if (m.qbJet > 0 && !lunging) {
    // AC QB: the jet holds QB speed along its line for qb_jet s (AC6 jet duration 0.26-0.54 s); a wall ends it
    m.qbJet -= dt;
    if (hv < m.qbSpeed * 0.5) m.qbJet = 0;
    else { m.vel.x = m.qbDir.x * m.qbSpeed; m.vel.y = m.qbDir.y * m.qbSpeed; }
  } else if (lunging) {
    // the blade lunge carries the mech at a fixed speed along the lunge direction
    const ls = m.lungeSpeed;
    m.vel.x = m.lungeDir.x * ls; m.vel.y = m.lungeDir.y * ls;
    m.lungeT -= dt;
  } else if (wl > 0.1 && !braced) {
    const dvx = wx / wl * target, dvy = wy / wl * target;
    const accel = MV.walk_accel * steer * (m.onGround ? 1 : 0.55) * (m.boosting ? 1.3 : 1);
    if (hv > target * 1.05) {
      // carrying excess speed (quick boost momentum): bleed it with friction while steering a little
      const k = Math.max(0, 1 - (m.onGround ? MV.friction : 2.5) * dt);
      m.vel.x = m.vel.x * k + (dvx - m.vel.x) * Math.min(1, accel * dt / Math.max(1, hv)) * 0.5;
      m.vel.y = m.vel.y * k + (dvy - m.vel.y) * Math.min(1, accel * dt / Math.max(1, hv)) * 0.5;
    } else {
      m.vel.x = IF_approach(m.vel.x, dvx, accel * dt);
      m.vel.y = IF_approach(m.vel.y, dvy, accel * dt);
    }
  } else {
    const k = Math.max(0, 1 - (m.onGround ? MV.friction : (m.boosting ? 0.6 : 1.5)) * dt);
    m.vel.x *= k; m.vel.y *= k;
  }
  // ---- vertical: jump / hover
  const jumpPress = !!inp.jump && !m.prevJump; m.prevJump = !!inp.jump;
  const canHover = !!inp.jump && !staggered && !lagged && !braced && m.dropT <= 0 && m.enStalled <= 0 && m.en > 0;
  m.hover = false;
  if (canHover) {
    const thrust = MV.jump_thrust * m.legs.jump_mult * m.hoverMult;
    if (jumpPress && m.onGround) m.vel.z = Math.max(m.vel.z, 380 * m.legs.jump_mult);
    // the jets push up to a climb speed, not without limit (10 Nov 2026 playtest: "the jets are too powerful": a held jump accelerated
    // at +500 u/s2 to the arena ceiling)
    const climb = (MV.hover_climb || 2500) * m.legs.jump_mult * Math.min(1.2, m.hoverMult);
    if (m.vel.z < climb) m.vel.z = Math.min(climb, m.vel.z + thrust * dt);
    m.spendEn(MV.hover_drain * m.legs.hover_drain_mult * m.drainMult * dt);
    m.hover = m.en > 0;
  }
  const gmul = m.hover ? 0.5 : m.assault ? (MV.assault_gravity !== undefined ? MV.assault_gravity : 1) : (m.qbJet > 0 && !m.onGround ? 0.3 : 1);
  if (!m.onGround || m.vel.z > 0 || m.hover) m.vel.z -= MV.gravity * gmul * dt;
  const term = m.dropT > 0 ? game.cfg.spawn.dropTerminal : MV.terminal;
  if (m.vel.z < -term) m.vel.z = -term;
  if (m.vel.z > 2500) m.vel.z = 2500;
  // ---- integrate
  const ox = m.pos.x, oy = m.pos.y, oz = m.pos.z;
  let nx = ox + m.vel.x * dt, ny = oy + m.vel.y * dt, nz = oz + m.vel.z * dt;
  // arena box: soft push from wall_soft, hard clamp at the wall
  const soft = MV.wall_soft, push = 1800;
  if (nx < A.min[0] + soft) { m.vel.x += push * dt * (1 - (nx - A.min[0]) / soft); if (nx < A.min[0]) { nx = A.min[0]; if (m.vel.x < 0) m.vel.x = 0; } }
  if (nx > A.max[0] - soft) { m.vel.x -= push * dt * (1 - (A.max[0] - nx) / soft); if (nx > A.max[0]) { nx = A.max[0]; if (m.vel.x > 0) m.vel.x = 0; } }
  if (ny < A.min[1] + soft) { m.vel.y += push * dt * (1 - (ny - A.min[1]) / soft); if (ny < A.min[1]) { ny = A.min[1]; if (m.vel.y < 0) m.vel.y = 0; } }
  if (ny > A.max[1] - soft) { m.vel.y -= push * dt * (1 - (A.max[1] - ny) / soft); if (ny > A.max[1]) { ny = A.max[1]; if (m.vel.y > 0) m.vel.y = 0; } }
  const ceil = A.max[2] - m.height;
  if (nz > ceil - soft) { m.vel.z -= push * dt * (1 - (ceil - nz) / soft); if (nz > ceil) { nz = ceil; if (m.vel.z > 0) m.vel.z = 0; } }
  // ---- ground and walls from the heightfield (step limit), the world sweep near struct cells
  // The step height: anything lower is walked over (the mech follows the ground), anything higher is a wall. A third of the body, at
  // least MV.step_min (10 Nov 2026 playtest: "hitting a tiny bump in the map just stops you in your tracks").
  let g = IF_groundAt(game, nx, ny, oz, m.height, m);
  const stepMax = Math.max((MV.step_min || 80) * m.scale, m.height * (MV.step_frac || 0.3));
  if (g > oz + stepMax && g > nz + stepMax) {
    // a wall: try sliding along each axis
    const gx = IF_groundAt(game, nx, oy, oz, m.height), gy = IF_groundAt(game, ox, ny, oz, m.height);
    if (gx <= oz + stepMax) { ny = oy; m.vel.y = 0; g = gx; }
    else if (gy <= oz + stepMax) { nx = ox; m.vel.x = 0; g = gy; }
    else { nx = ox; ny = oy; m.vel.x = 0; m.vel.y = 0; g = IF_groundAt(game, ox, oy, oz, m.height); }
  }
  const mv2 = (nx - ox) * (nx - ox) + (ny - oy) * (ny - oy);
  // (a slow mover is swept every other tick, except for half a second after a wall contact: it would creep into the wall on the ticks between)
  if (m.wallT > 0) m.wallT -= dt;
  if (game.world && game.world.traceSphere && game.nav.nearStruct(nx, ny) && (m.wallT > 0 ? mv2 > 0.01 : mv2 > 4 && (mv2 > 225 || ((game.tickN + m.slot) & 1) === 0))) {
    // The body sphere rides ABOVE the step height: it used to sit 4 u over the feet, so every kerb, slab edge and bump over 4 u stopped
    // the mech dead (the bug behind the playtest line above; Sprawl's kerbed avenues are all near structures). What is below the step
    // height is the ground trace's: the mech steps onto it. A walkable face (normal mostly up) met while walking is ground too. A sweep
    // that starts inside something (pushed there by a step or the separation) retries smaller, then lets the mech out rather than pin it.
    const a = game._ta, b = game._tb, r = m.radius, lift = stepMax + r;
    a.x = ox; a.y = oy; a.z = oz + lift; b.x = nx; b.y = ny; b.z = nz + lift;
    let hit = game.traceSphere(a, b, r);
    if (hit && hit.hit && hit.solid) {
      if (m.wallT > 0) {
        // touching the wall it just met: no move into it (slide along, a nudge out), the rest of the move is free
        const d = (nx - ox) * m.wallNx + (ny - oy) * m.wallNy, vn = m.vel.x * m.wallNx + m.vel.y * m.wallNy;
        if (d < 0) { nx -= m.wallNx * d; ny -= m.wallNy * d; }
        if (vn < 0) { m.vel.x -= m.wallNx * vn; m.vel.y -= m.wallNy * vn; }
        nx += m.wallNx * 2; ny += m.wallNy * 2; m.wallT = 0.5;
        g = IF_groundAt(game, nx, ny, oz, m.height);
        hit = null;
      } else { hit = game.traceSphere(a, b, r * 0.5); if (hit && hit.solid) hit = null; }
    }
    if (hit && hit.hit && hit.normal && Number.isFinite(hit.frac) && !(m.onGround && hit.normal.z > 0.7)) {
      { const hn = hit.normal, hl = Math.sqrt(hn.x * hn.x + hn.y * hn.y); if (hl > 0.5) { m.wallNx = hn.x / hl; m.wallNy = hn.y / hl; m.wallT = 0.5; } }
      const f = IF_clamp(hit.frac, 0, 1) * 0.98;
      nx = ox + (nx - ox) * f; ny = oy + (ny - oy) * f; nz = oz + (nz - oz) * f;
      const n = hit.normal, vn = m.vel.x * n.x + m.vel.y * n.y + m.vel.z * n.z, vz0 = m.vel.z;
      if (vn < 0) { m.vel.x -= n.x * vn; m.vel.y -= n.y * vn; m.vel.z -= n.z * vn; }
      // a sloped prop face turned a boost into a launch (Nov 2026: mechs thrown to the roof): a contact adds at most 200 u/s upward
      if (m.vel.z > vz0 && m.vel.z > 0) m.vel.z = Math.min(m.vel.z, Math.max(0, vz0) + 200);
      g = IF_groundAt(game, nx, ny, oz, m.height);
    }
  }
  // player clips: CS2's line / sphere traces pass through them (10 Nov 2026 playtest: mechs walked through skink52's clip brushes)
  if (game.world && game.world.traceClip && game.cfg.clip && game.cfg.clip.on) {
    const c = IF_clipStep(game, m, ox, oy, oz, nx, ny, nz, g, stepMax, dt);
    if (c) { nx = c.x; ny = c.y; nz = c.z; g = c.g; }
  }
  m.groundZ = g;
  const wasAir = !m.onGround;
  // on the ground the mech follows the terrain within the step height; in the air it lands when it reaches it
  const landed = (!wasAir && m.vel.z <= 0 && Math.abs(nz - g) <= stepMax) || nz <= g;
  if (landed) {
    if (wasAir) {
      m.fallSpeed = Math.max(0, -m.vel.z);
      const hard = m.fallSpeed > MV.land_fall_speed && m.dropT <= 0;
      if (hard) m.landLag = m.landLagTime;
      if (m.airTime > 0.15 || hard) game.emit({ t: 'land', slot: m.slot, hard });
      if (m.dropT > 0) { m.dropT = 0; m.protect = game.cfg.spawn.protect; }
    }
    // a step taken while walking is eased for the eye: stepOff is the height the drawn mech (and the camera on it) still lags behind the
    // real one; it decays in ~0.1 s. A slope is not a step (the rise a 50 deg slope gives this tick is left out).
    if (!wasAir) {
      const dzs = g - oz, slope = Math.sqrt((nx - ox) * (nx - ox) + (ny - oy) * (ny - oy)) * 1.2 + 4;
      if (Math.abs(dzs) > slope) m.stepOff = IF_clamp(m.stepOff - (dzs - (dzs > 0 ? slope : -slope)), -stepMax * 1.5, stepMax * 1.5);
    }
    nz = g; if (m.vel.z < 0) m.vel.z = 0;
    m.onGround = true; m.airTime = 0;
  } else { m.onGround = false; m.airTime += dt; }
  if (m.stepOff !== 0) { m.stepOff *= Math.exp(-dt / (MV.step_smooth || 0.09)); if (Math.abs(m.stepOff) < 0.5) m.stepOff = 0; }
  if (nz < A.min[2] - 2000) nz = A.min[2] - 2000;
  m.pos.x = nx; m.pos.y = ny; m.pos.z = nz;
  m.speed = Math.sqrt(m.vel.x * m.vel.x + m.vel.y * m.vel.y);
  if (m.dropT > 0) m.dropT += dt;
  // ---- EN regen
  if (m.enStalled > 0) { m.enStalled -= dt; if (m.enStalled <= 0) { m.enStalled = 0; m.enPause = 0; m.en = Math.min(m.enMax, m.en + m.enMax * (MV.stall_refill || 0)); } }
  else if (m.enPause > 0) m.enPause -= dt;
  else if (m.en < m.enMax) m.en = Math.min(m.enMax, m.en + m.enRegen * (m.onGround ? MV.ground_regen_mult : (MV.air_regen_mult !== undefined ? MV.air_regen_mult : 1)) * (m.boosting && MV.boost_regen_mult !== undefined ? MV.boost_regen_mult : 1) * dt);
  if (m.enEmptyFlag) { m.enEmptyFlag = false; game.emit({ t: 'en_empty', slot: m.slot }); }
  m.pushPose();
}

// Soft separation: overlapping mechs are pushed apart at MV.separation u/s (never solid; 64 players). O(n^2) over the live list.
function IF_separate(game, list, n, dt) {
  const push = game.move.separation * dt;
  for (let i = 0; i < n; i++) {
    const a = list[i];
    for (let j = i + 1; j < n; j++) {
      const b = list[j];
      const dx = b.pos.x - a.pos.x, dy = b.pos.y - a.pos.y;
      const r = a.radius + b.radius;
      const d2 = dx * dx + dy * dy;
      if (d2 >= r * r) continue;
      if (Math.abs(b.pos.z - a.pos.z) > Math.max(a.height, b.height)) continue;
      let d = Math.sqrt(d2), ux, uy;
      if (d < 1) { const an = (a.slot * 0.7 + b.slot * 1.3); ux = Math.cos(an); uy = Math.sin(an); d = 1; } else { ux = dx / d; uy = dy / d; }
      const k = Math.min(push, (r - d) * 0.5);
      const wa = b.boss ? 1 : (a.boss ? 0 : 0.5), wb = 1 - wa;
      a.pos.x -= ux * k * wa * 2; a.pos.y -= uy * k * wa * 2;
      b.pos.x += ux * k * wb * 2; b.pos.y += uy * k * wb * 2;
    }
  }
  // the push never carries a mech through the arena wall
  const A = game.arena.bounds;
  for (let i = 0; i < n; i++) { const p = list[i].pos; p.x = IF_clamp(p.x, A.min[0], A.max[0]); p.y = IF_clamp(p.y, A.min[1], A.max[1]); }
}
