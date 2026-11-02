// ===================================================================================
// Space Racer - the game itself. Plain JavaScript, no engine calls, so it runs in CS2 and in Node.
// Part 0: constants, the four cars, helpers.
// ===================================================================================

const TICRATE = 64;                 // sim steps per second (one per CS2 server tick)
const DT = 1 / TICRATE;
const CAR_R = 40;                   // car collision radius (units)
const CAR_LEN = 115;                // for drawing / grid spacing
const TEAM_NAMES = ['T', 'CT'];

// The four cars (top speeds +556 u/s = +200 km/h on the speedo since 29 Oct 2026, accel x1.45, brakes x1.3). Speeds in units/s, accel in units/s^2, turn in radians/s at mid speed, grip = how fast sideways
// speed is bled off (per second); mass only matters when cars bump.
const CARS = {
  hornet:  { key: 'hornet',  name: 'HORNET',  maxSpeed: 1620,  accel: 928, brake: 1300, turn: 2.7,  grip: 12, driftGrip: 3.2, mass: 1.0, shield: 108, charge: 100, boost: 1.32, padMult: 1.0, driftCharge: 2.5, spinCost: 18, ram: 1.0, chargeMult: 1.0, draftMult: 1.0, draftRegen: 0,
             perk: 'DRIFT CHARGE', desc: 'LIGHT AND SHARP. DRIFTING FILLS CHARGE FAST. CHEAP SPIN ATTACK.',
             ability: 'bolt', abilityName: 'SEEKER BOLT', abilityCd: 6, abilityCost: 20 },
  meteor:  { key: 'meteor',  name: 'METEOR',  maxSpeed: 1646, accel: 776, brake: 1170,  turn: 2.35, grip: 10, driftGrip: 3.0, mass: 1.6, shield: 110, charge: 100, boost: 1.28, padMult: 1.0, driftCharge: 1.0, spinCost: 30, ram: 1.8, chargeMult: 1.0, draftMult: 1.0, draftRegen: 0,
             perk: 'RAM', desc: 'HEAVY AND FAST IN A STRAIGHT LINE. BUMPS HURT THEM, NOT YOU.',
             ability: 'quake', abilityName: 'SHOCKWAVE', abilityCd: 12, abilityCost: 40 },
  comet:   { key: 'comet',   name: 'COMET',   maxSpeed: 1596,  accel: 761, brake: 1235,  turn: 2.4,  grip: 11, driftGrip: 3.0, mass: 1.0, shield: 110, charge: 130, boost: 1.38, padMult: 1.38, driftCharge: 1.0, spinCost: 30, ram: 1.0, chargeMult: 1.3, draftMult: 1.0, draftRegen: 0,
             perk: 'AFTERBURN', desc: 'BIGGEST CHARGE TANK, STRONGEST BOOST, PADS LAST LONGER.',
             ability: 'nova', abilityName: 'NOVA BURN', abilityCd: 12, abilityCost: 40 },
  bastion: { key: 'bastion', name: 'BASTION', maxSpeed: 1599,  accel: 798, brake: 1235,  turn: 2.3,  grip: 11, driftGrip: 3.0, mass: 1.3, shield: 115, charge: 100, boost: 1.33, padMult: 1.0, driftCharge: 1.0, spinCost: 30, ram: 1.0, chargeMult: 1.0, draftMult: 2.0, draftRegen: 1.5,
             perk: 'SLIPSTREAM', desc: 'TOUGHEST SHIELD. DRAFTING FILLS CHARGE AND REPAIRS. TEAMMATES BEHIND YOU GAIN TOO.',
             ability: 'aegis', abilityName: 'AEGIS', abilityCd: 12, abilityCost: 30 },
};
const CAR_KEYS = ['hornet', 'meteor', 'comet', 'bastion'];

// rules that are not per car
const RULES = {
  boostDrain: 33,           // charge per second while boosting (100 lasts 3 s)
  padTime: 1.2,             // seconds of free boost from a boost pad
  padKick: 190,             // instant speed from a boost pad
  padSpeed: 1.42,           // top speed multiplier while a pad boost lasts
  chargeRate: 55,           // charge per second on a charge platform
  chargeShield: 8,          // shield per second on a charge platform
  draftCharge: 8,           // charge per second in a slipstream
  draftSpeed: 1.06,         // top speed multiplier in a slipstream
  driftChargeRate: 10,      // charge per second while sliding in a drift
  spinTime: 0.5, spinCooldown: 3.0, spinDamage: 20,
  spinReach: 35,            // a spinning car hits cars this much further away than touching (its swinging tail)
  spinKnock: 640,             // a spin hit shoves the other car sideways: its speed change is this x attacker mass / its mass
  spinStagger: 0.55,        // ... then it skids for this long (grip and steering cut) so the shove carries it across the road
  staggerGrip: 0.25, staggerSteer: 0.5, spinSlow: 0.12,  // grip and steering it keeps while skidding; forward speed lost
  contactMax: 20,           // most shield one bump or rail hit can take
  contactSoft: 380,         // closing speed below which a bump is free (250 before the +200 km/h)
  contactDamage: 0.016,     // shield per unit of closing speed above that (0.024 before)
  regenDelay: 4, regenRate: 2.2,   // shield repairs slowly once nothing has hit you for this long
  startProtect: 6.0,        // seconds after the lights with no damage (the first corner is crowded)
  attackLock: 6.0,          // ... and no spin attacks or Shockwaves, so the start is a race, not a brawl
  spinImmune: 1.5,          // a car just hit by a spin can't be spun again for this long (no chain wrecks)
  railRestitution: 0.3,     // bounce off the rails
  railSoft: 220,            // rail / flight-corridor hits slower than this (into the wall) are free (140 before the +200 km/h)
  railDamage: 0.026,        // shield per unit of speed into the wall above that (0.04 before)
  contactRestitution: 0.45,
  wreckShow: 1.5,           // seconds a wreck stays visible
  fallTime: 1.2,            // seconds falling before the reset
  fallPenalty: 35,          // shield lost for falling off (into a gap, off a rail-less edge; 20 before v0.6.0)
  outPenalty: 55,           // shield lost for flying clean over the rails out of the map (overshooting a jump or a bend)
  railHeight: 30,           // the rails' height (tools/tracks.py RAIL_H): a car in the air higher than this over the road
                            // clears them and leaves the track
  pulseSpeed: 2300, pulseCharge: 40, pulseEnabled: true,
  startCharge: 40,
  coastDrag: 0.35,          // per second when not accelerating
  reverseMax: 220,
  wrongWayTime: 1.0,        // seconds driving backwards before the warning
  koCreditWindow: 2.0,      // seconds: the last car to hit a wreck within this gets the kill
  slickGrip: 0.3,
  turnFade: 2400,           // turning fades with speed over 450 u/s: rate / (1 + (v - 450) / turnFade)  (1500 before the +200 km/h)
  gravity: 1500,            // units/s^2 in the air (jumps; 1150 before the +200 km/h)
  rampThrow: 0.65,          // a ramp throws the car up at (speed along x slope x this): with gravity, keeps jumps about as long as
                            // before the +200 km/h (+20%) instead of 2.5x (distance goes with speed squared)
  rampKick: 60,             // extra upward speed off a ramp lip
  airControl: 0.35,         // steering left in the air
  airGrip: 2.5,             // how fast the car's heading pulls its flight round in the air (on the road: grip, about 11).
                            // Steer through a jump that lands on a bend, or sail out over the rails
  landSafe: 1050,           // landing faster than this (units/s downwards) scrapes the shield
  bankTurn: 0.6, bankGrip: 1.5,   // banked bends: extra turning and grip per unit of lean (tan of the angle)
  // the secret turbo start: gas down on the third beep (1 s before GO) or after it, and held: a launch. The window
  // opens a little before that beep, and the beep reaches a player a little late (ping, reaction), so 1.25 s.
  launchWindow: 1.25,
  launchKick: 350, launchTime: 1.0,   // ... gives this much speed at once and a pad-strength boost for this long
  stallAfter: 1.9, stallTime: 0.5,    // gas held down since before the second beep: the engine stalls for a moment
  botLaunch: 0.55,          // a bot's chance of a turbo start = skill x this
  // drifting fills charge only through a held slide one way (not while boosting, not by flicking left-right)
  driftStreak: 0.35,
  // big air: a clean landing after this long in the air pays some charge
  bigAirTime: 0.7, bigAirCharge: 15,
  // ---- flight sections (Neon Racer): S climbs, W dives (like a plane), no input sinks slowly; the corridor's edge bounces like a rail
  flyClimb: 520, flyDive: 640, flySink: 70, flyResp: 5, flyRest: 0.3,
  // ---- sea creatures (Depth Racer): warn a driver this far (road units) before a crossing
  creatureWarn: 4200,
  creatureAirKnock: 0.3,    // a car hit in the air (over a jump) is shoved this much as hard as on the road, and stops climbing
  // ---- the cars' E abilities (CARS[*].ability; cooldown and charge cost per car)
  // SEEKER BOLT (Hornet): a bolt fired forward along the road, curving towards the first car ahead; the car it hits is
  // shoved, skids and loses shield (an Aegis shell stops it)
  boltSpeed: 900, boltRange: 3000, boltTurn: 280, boltRadius: 34, boltDamage: 10, boltKnock: 260, boltStagger: 0.6, boltSlow: 0.25, boltLift: 30,
  // SHOCKWAVE (Meteor): every car close by is shoved sideways (harder the closer), skids and loses shield
  quakeRadius: 320, quakeKnock: 300, quakeDamage: 6, quakeStagger: 0.3,
  // NOVA BURN (Comet): all the charge at once - a kick and a long overdrive - and a trail of fire behind
  novaKick: 300, novaSpeed: 1.5, novaTime: 0.7, novaTimePerCharge: 0.012,
  fireGap: 0.15, fireFor: 0.8, fireTime: 2.0, fireRadius: 90, fireDamage: 4, fireEvery: 0.5,   // fire for the first second
  // AEGIS (Bastion): an energy shell - no damage, no shoves, cars bounce off - and a shield top-up for teammates near
  aegisTime: 2.5, aegisMass: 4, aegisBump: 1, aegisShare: 20, aegisRange: 500,
};

function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
function lerp(a, b, t) { return a + (b - a) * t; }
function normRad(a) { while (a > Math.PI) a -= 2 * Math.PI; while (a < -Math.PI) a += 2 * Math.PI; return a; }
function deg(r) { return r * 180 / Math.PI; }
function rad(d) { return d * Math.PI / 180; }
function fmtTime(sec) {
  const m = Math.floor(sec / 60), s = sec - m * 60;
  return m + ':' + (s < 10 ? '0' : '') + s.toFixed(2);
}
function ordinal(n) {
  const s = ['TH', 'ST', 'ND', 'RD'], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

// deterministic random for tests (replaced by Math.random in CS2 if wanted)
let _seed = 12345;
function rnd() { _seed = (_seed * 1103515245 + 12345) & 0x7fffffff; return _seed / 0x7fffffff; }
function seedRandom(s) { _seed = s | 0; }
function pick(arr) { return arr[Math.floor(rnd() * arr.length)]; }
function shuffle(a) {
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}
