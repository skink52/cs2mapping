// ===================================================================================================================
// IRONFRAME core, part 0: constants and the default configuration. Plain JavaScript, no engine calls, one shared scope
// with the CS2 adapter: every top-level name here starts with IF_. The baked consts PARTS / ARENA / VERSION are defined
// AFTER the core by the build, so the core only reads them inside functions (never at top level).
//
// docs/DESIGN.md sections 3-7 are the spec, docs/INTERFACES.md section 3 the API. Units: CS2 world units, seconds, AP.
// ===================================================================================================================

const IF_TICKRATE = 64;
const IF_MAX_SLOTS = 64;           // pawn slots 0..63 (humans and CS2 bots); NPC mechs (Sortie waves, bosses) use 64..IF_MAX_MECHS-1
const IF_MAX_MECHS = 320;          // 64 pawn slots + 64 AI slots per arena copy (up to 4 copies: game cfg.npcSlot0 = 64 + 64 k)
const IF_NPC_SLOT0 = 64;
const IF_MAX_BULLETS = 1024;
const IF_MAX_MISSILES = 128;
const IF_MAX_BEAMS = 32;
const IF_MAX_EFFECTS = 256;       // bubbles, rings, landing marks, orbit drones (2 per mech) and mines (4 per mech)
const IF_POSE_HISTORY = 8;         // ticks of pose history per mech (lag mercy tests the pose 6 ticks ago)
const IF_LAG_TICKS = 6;

// hard-point indices in a loadout / mech.weapons: 0 right arm (Mouse1), 1 left arm (Mouse2), 2 right shoulder (R), 3 left shoulder (E)
const IF_HP_RA = 0, IF_HP_LA = 1, IF_HP_RS = 2, IF_HP_LS = 3;
// loadout string positions: frame, right arm, left arm, right shoulder, left shoulder, generator, booster, fcs, paint
const IF_LOADOUT_KINDS = ['frame', 'arm', 'arm', 'shoulder', 'shoulder', 'generator', 'booster', 'fcs', 'paint'];
const IF_LO_FRAME = 0, IF_LO_GEN = 5, IF_LO_BST = 6, IF_LO_FCS = 7, IF_LO_PAINT = 8;

// deny codes (docs/SERVER_CONTRACT.md section 4)
const IF_DENY = { OK: 0, NOT_OWNED: 1, RANK: 2, CREDITS: 3, WEIGHT: 4, EN: 5, CAP: 6, BAD: 7, RATE: 8, TEXT: 9, NOT_EARNED: 10 };
// EN overdraw a loadout may sortie with (regen is scaled by output / load meanwhile); beyond it deny 5. Shared with the
// plugin through data/contract_vectors.json rules.en_factor (tools/contract_vectors.py).
const IF_EN_FACTOR = 1.5;

const IF_TEAM_T = 2, IF_TEAM_CT = 3;
const IF_MODES = ['tb', 'cq', 'sk', 'so', 'kh', 'ctf'];
const IF_MODE_NAMES = { tb: 'Team Deathmatch', cq: 'Conquest', sk: 'Skirmish', so: 'Sortie', kh: 'King of the Hill', ctf: 'Capture the Flag' };

// The default configuration (IF_Game cfg; the adapter's CONFIG.core overrides keys, deep-merged one level). Movement
// numbers come from PARTS.move at construction (cfg.move overrides those).
const IF_DEFAULT_CFG = {
  dtMax: 0.05,                       // a tick longer than this is clamped (a hitch never teleports a mech)
  // Load shedding for full servers (12 Nov 2026: 64 mechs took 11-15 ms of a 15.6 ms tick, measured on the test server). Script-AI
  // mechs are split into two groups by slot that take turns: above aiHalfAbove live mechs each AI thinks every other tick; above
  // simHalfAbove its movement and lock-on also run every other tick, with twice the time step. Human mechs, weapons, bullets,
  // missiles and collisions between mechs always run every tick. The adapter draws a skipped AI mech a tick ahead from its
  // velocity when a human is near, so it does not judder (core m.simOff).
  load: { aiHalfAbove: 24, simHalfAbove: 40 },
  move: {},                          // overrides of PARTS.move keys
  npcSlot0: 64,                      // first AI slot of this game (arena copy k: 64 + 64 k)
  round: { tb: 600, cq: 600, sk: 600, so: 600, kh: 600, ctf: 720, warmup: 5, podium: 12 },
  kh: { target: 150, rotate: 120 },
  ctf: { captures: 3, pickup: 260, capture: 320, returnTime: 20, carrierDrain: 1.5 },
  tb: { killsPerHuman: 6, killMin: 40, killMax: 150 },
  cq: { tickets: 300, captureTime: 8, captureBonus: 0.5, captureMax: 3, decay: 0.08, bleedPerPoint: 1, killCost: 2, forwardDrops: true },
  sk: { target: 25, max: 16 },
  so: { waves: 9, bossEvery: 3, baseEnemies: 8, perWave: 2, maxEnemies: 16, extraPerPlayer: 0.25, allies: 8, pause: 8, nextAt: 2,
        beaconLoseTime: 30, bossPhases: [0.66, 0.33], weakMult: 3, respawn: 10 },
  spawn: { enemyDist: 2500, dropHeight: 1500, dropTerminal: 1100, protect: 3, respawn: 6, deathCam: 3 },
  dmg: { assistPct: 0.15, assistWindow: 8, splashInner: 0.4, splashEdge: 0.25, selfSplash: 0.5, impactAirborne: 1.0, friendlyFire: false, staggerGuard: 2.5, staggerGuardMult: 0.25 },
  lock: { graceLos: 0.5, keepCone: 1.25, seekEvery: 4, decoyTime: 2.5, lockWarnRange: 9000, closeThreat: 1200 },
  weapon: { traceCache: 0.2, traceCacheDeg: 3, missileFuse: 90, missileFuseMargin: 40, missileLife: 6, missileArm: 0.15,
            missileStagger: 0.09, airburstRadius: 0.7, lobLife: 6, beamTime: 0.12, meleeLungeTime: 0.2, meleeLockRange: 900,
            bulletBroadR: 260, shieldHalfArc: 70, qbDodgeWindow: 0.15,
            // the sky (10 Nov 2026 playtest: rockets burst on the sky ceiling): projectiles and missiles cruise at most skyPad under the sky
            // (game.skyZ, measured by the adapter; else arena.sky or bounds.max z + skyDefault) and never more than ceilPad over the arena
            // ceiling; anything reaching the sky vanishes without a blast. minConverge: a reticle point closer than this in front of the
            // muzzle (a wall in the camera's face) fires parallel to the camera ray instead
            skyPad: 300, ceilPad: 200, skyDefault: 1000, minConverge: 200 },
  // player clips (toolsclip / toolsplayerclip): only a player-hull trace (world.traceClip = Instance.TracePlayer) sees them. Every
  // `discover` ticks a moving mech sweeps a hull along its next `discover` ticks of travel; a hit that a line trace does not share is a
  // clip, and its cells (+ `near` cells around) get the full check every tick: hull sweeps at `heights` above the feet, a hull trace
  // down for clip tops to stand on. hull: the pawn hull half width (CS2 standing hull 32 x 32 x 72). budget: hull traces a tick above
  // which slow mechs sweep every other tick (20_mech.js IF_clipStep)
  clip: { on: true, discover: 8, near: 2, heights: [88, 208], hull: 16, budget: 64 },
  balance: { tolerance: 0.05, ratingRank: 20, ratingKd: 40 },
  ai: { floor: 22, fillTotal: 16, sortieAllies: 8, skirmishFill: 8, npcFill: true,
        tiers: {
          // aim model (50_ai.js header): react s, aimErr deg base, rangeErr per 1500 u past 1500, settle x over settleT s, moveErr deg per
          // deg/s of lateral target motion, qbErr deg fading over qbBlind s, velLag s, gain 1/s (turn lag), wander 1/s; lead fraction
          easy:   { react: 0.6,  aimErr: 2.0,  rangeErr: 0.7,  settle: 2.0, settleT: 1.1, moveErr: 0.07,  qbErr: 7, qbBlind: 0.8,  velLag: 0.45, gain: 5,  wander: 2.5,
                    think: 6, lead: 0.3, dodge: 0.25, qbDodge: 0.2, cover: 0.4, burst: 0.6, boostRes: 900,  rangeFrac: 0.75, decoy: 0.4, jump: 0.05, chain: 0 },
          normal: { react: 0.4,  aimErr: 1.3,  rangeErr: 0.6, settle: 1.5, settleT: 0.9, moveErr: 0.05,  qbErr: 6, qbBlind: 0.65,  velLag: 0.3,  gain: 8,  wander: 3,
                    think: 4, lead: 0.7, dodge: 0.6,  qbDodge: 0.6, cover: 0.7, burst: 0.8, boostRes: 700,  rangeFrac: 0.65, decoy: 0.7, jump: 0.12, chain: 0.3 },
          hard:   { react: 0.25, aimErr: 0.8,  rangeErr: 0.5, settle: 1.0, settleT: 0.6, moveErr: 0.035,  qbErr: 4.5, qbBlind: 0.45,  velLag: 0.2,  gain: 12, wander: 3.5,
                    think: 3, lead: 1.0, dodge: 0.9,  qbDodge: 0.9, cover: 0.9, burst: 1.0, boostRes: 500,  rangeFrac: 0.6,  decoy: 0.9, jump: 0.2, chain: 0.85 },
        },
        tierRank: { normal: 8, hard: 20 },  // average lobby rank at which the fill tier steps up
        skill: { up: 0.06, down: 0.18 },    // fill skill per human kill of a fill bot / per human killed by one (50_ai.js fillSkill)
        squadSize: 3, orbitSwitch: 4, coverTime: 4, coverAp: 0.4, missileDodgeTti: 0.45, stuckTime: 2.5, aimLostT: 0.35 },
  xp: { roundCap: 6000, survivePerS: 1 },
  stats: { traceBudget: 1.3 },
};

// Deep-ish merge: one level of nested objects (cfg.move.gravity ...), everything else replaced.
function IF_mergeCfg(base, over) {
  const out = {};
  for (const k in base) {
    const b = base[k];
    if (b && typeof b === 'object' && !Array.isArray(b)) {
      out[k] = Object.assign({}, b);
      const o = over && over[k];
      if (o && typeof o === 'object') for (const kk in o) {
        const bb = out[k][kk], oo = o[kk];
        out[k][kk] = (bb && typeof bb === 'object' && !Array.isArray(bb) && oo && typeof oo === 'object') ? Object.assign({}, bb, oo) : oo;
      }
    } else out[k] = over && over[k] !== undefined ? over[k] : b;
  }
  if (over) for (const k in over) if (!(k in out)) out[k] = over[k];
  return out;
}

// The parts catalog indexed once per game (PARTS is baked after the core, so this runs inside the IF_Game constructor).
function IF_indexParts(parts) {
  const byId = new Map(), byKey = new Map(), byKind = {};
  for (const p of parts.parts) {
    byId.set(p.id, p); byKey.set(p.key, p);
    (byKind[p.kind] || (byKind[p.kind] = [])).push(p);
  }
  return { byId, byKey, byKind, classes: parts.classes, legs: parts.leg_types, move: parts.move, caps: parts.caps, xp: parts.xp,
           starter: parts.starter, aiLoadouts: parts.ai_loadouts, raw: parts };
}

// Loadout string "f,ra,la,rs,ls,gen,bst,fcs,paint" -> ids[9] or null (format only; IF_Progress.validate does the rules)
function IF_parseLoadout(str) {
  if (typeof str !== 'string') return null;
  const f = str.split(',');
  if (f.length !== 9) return null;
  const ids = new Array(9);
  for (let i = 0; i < 9; i++) {
    const s = f[i];
    if (s.length < 1 || s.length > 4) return null;
    for (let c = 0; c < s.length; c++) { const ch = s.charCodeAt(c); if (ch < 48 || ch > 57) return null; }
    ids[i] = +s;
  }
  return ids;
}
