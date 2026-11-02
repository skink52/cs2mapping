// ===================================================================================
// Classes and enemies: data only. Behaviour lives in the adapter (abilities need the engine) and in 40_enemies.js (pure).
// ===================================================================================
const CLASSES = {
  // internal keys stay ninja / monk / chrono; the names players see are the callsigns
  ninja: { name: 'VECTOR', chat: ['vector', 'ninja'], key: 'crouch + E', blurb: 'Dash 256 units along your crosshair; a melee kill resets it.',
           active: 'DASH', cd: CONFIG.NINJA_DASH_CD, color: { r: 60, g: 230, b: 255 } },
  monk:  { name: 'WARDEN', chat: ['warden', 'monk'], key: 'R on an empty mag', blurb: 'Raise a 128-unit aegis: hits from outside are cut 70%; your armor grows by what it stops.',
           active: 'AEGIS', cd: CONFIG.MONK_DOME_CD, color: { r: 255, g: 180, b: 40 } },
  chrono:{ name: 'ECHO', chat: ['echo', 'chrono'], key: 'F', blurb: '+40% speed and a full mag for 5 s; a lethal hit rewinds you to where it began, on 50 hp.',
           active: 'REWIND', cd: CONFIG.CHRONO_CD, color: { r: 255, g: 60, b: 200 } },
};
const CLASS_KEYS = Object.keys(CLASSES);
const CLASS_BY_CHAT = {}; for (const k of CLASS_KEYS) for (const w of CLASSES[k].chat) CLASS_BY_CHAT[w] = k;

// enemy kinds: stone and hologram constructs (rigid props, no skeleton). model = the pooled prop's model (cached in the map).
// hp scales with the floor; speed in units/s; attack: melee (lunge) or shot (a hitscan tracer after a telegraph) or bolt (script-flown)
const ENEMIES = {
  // the temple's guardians: stone and hologram constructs. Stock CS2 models (their vmdl is cached in the map's cache room, see tools/vmap.py POOL_MODELS)
  drone:    { name: 'shard drone', model: 'models/anubis/structures/statue01_head.vmdl', hp: 60, speed: 300, radius: 20, height: 50, z: 56, scale: 0.8,
              attack: 'melee', dmg: 9, reach: 72, rate: 0.9, nanites: 100, color: { r: 60, g: 230, b: 255 } },
  sentinel: { name: 'sentinel', model: 'models/anubis/structures/statue01.vmdl', hp: 180, speed: 0, radius: 26, height: 98, z: 0, scale: 0.75,
              attack: 'shot', dmg: 14, reach: 1400, rate: 1.6, telegraph: 0.6, nanites: 200, color: { r: 210, g: 200, b: 190 } },
  lancer:   { name: 'lancer', model: 'models/anubis/signs/anubis_exhibition_panel_01.vmdl', hp: 120, speed: 120, radius: 22, height: 95, z: 10, scale: 0.9,
              attack: 'bolt', dmg: 22, reach: 1200, rate: 2.2, boltSpeed: 900, nanites: 180, color: { r: 255, g: 190, b: 60 } },
  golem:    { name: 'golem', model: 'models/anubis/structures/tower01_destroyed.vmdl', hp: 420, speed: 150, radius: 30, height: 100, z: 0, scale: 0.45,
              attack: 'melee', dmg: 30, reach: 100, rate: 1.8, nanites: 350, armorIgnore: true, color: { r: 200, g: 200, b: 200 } },
};
// what a floor's wave is made of (weights); the boss floor adds a golem escort
const WAVE_MIX = [
  { drone: 6, sentinel: 2, lancer: 1, golem: 0 },
  { drone: 5, sentinel: 2, lancer: 2, golem: 1 },
  { drone: 4, sentinel: 2, lancer: 3, golem: 2 },
];

// pooled effect models (tools/fx.py)
const FXM = { shard: 'models/nt/fx/nt_shard/nt_shard.vmdl', bolt: 'models/nt/fx/nt_bolt/nt_bolt.vmdl', dome: 'models/nt/fx/nt_dome/nt_dome.vmdl',
              beacon: 'models/nt/fx/nt_beacon/nt_beacon.vmdl', spark: 'models/nt/fx/nt_spark/nt_spark.vmdl' };

// CS2 weapon damage with range falloff (what a bullet does to an enemy; CS2 does its own maths on players)
function weaponDamage(base, rangeMod, dist) {
  return base * Math.pow(rangeMod || 0.85, dist / 500);
}
