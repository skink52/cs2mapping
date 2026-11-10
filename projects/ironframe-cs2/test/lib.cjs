// Shared test helpers: the core module, the arena, a heightfield "world" standing in for CS2 traces, a seeded rng.
const fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..');
const C = require(process.env.IF_CORE || path.join(ROOT, 'build', 'core_test.cjs'));
// the test arena (tools/test_arena.py -> build/arena_test.json, made on first use); IF_ARENA=<file> runs on another one,
// e.g. IF_ARENA=out/addon/_gen/arena.json for the generated map's own arena
// IF_ARENA_FILE (a .json arena) overrides the test arena; IF_ARENA is the arena NAME the deploy scripts export (tools/names.sh), so a
// plain IF_ARENA=dunes in the shell no longer breaks the tests (10 Nov 2026); an IF_ARENA ending in .json still works
const ARENA_ENV = process.env.IF_ARENA_FILE || (/\.json$/i.test(process.env.IF_ARENA || '') ? process.env.IF_ARENA : '');
const ARENA_FILE = ARENA_ENV ? path.resolve(ROOT, ARENA_ENV) : path.join(ROOT, 'build', 'arena_test.json');
if (!ARENA_ENV && !fs.existsSync(ARENA_FILE)) require('child_process').execFileSync('python', ['-I', path.join(ROOT, 'tools', 'test_arena.py'), ARENA_FILE]);
const ARENA = JSON.parse(fs.readFileSync(ARENA_FILE, 'utf8'));

function rng(seed) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
// the world: the arena heightfield (pillars included) ray-marched; counts its own calls
function makeWorld(arena) {
  const nav = new C.IF_Nav(arena.nav, arena.bounds);
  const w = {
    lines: 0, spheres: 0,
    traceLine(a, b) { w.lines++; return hit(a, b, 0); },
    traceSphere(a, b, r) { w.spheres++; return hit(a, b, r * 0.8); },
    now() { return 0; },
  };
  function hit(a, b, drop) {
    const f = nav.rayFrac(a.x, a.y, a.z - drop, b.x, b.y, b.z - drop, 48);
    const pos = { x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f, z: a.z + (b.z - a.z) * f };
    return { hit: f < 1, pos, normal: { x: 0, y: 0, z: 1 }, frac: f, mech: -1 };
  }
  return w;
}
function makeGame(opts) {
  opts = opts || {};
  const arena = opts.arena || ARENA;
  const world = opts.noWorld ? null : makeWorld(arena);
  const g = new C.IF_Game({ parts: opts.parts || C.PARTS, arena, cfg: opts.cfg || {}, world, rng: rng(opts.seed || 1) });
  g._testWorld = world;
  return g;
}
function input() { return { mx: 0, my: 0, yaw: 0, pitch: 0, boost: false, qb: false, jump: false, fire: [false, false, false, false], cycle: false, any: false, camPos: null, camDir: null }; }
// what the adapter files (src/cs2) take from the core when a test loads them in a sandbox: the pilot customisation codec and the deny codes
const careerGlobals = () => ({ IF_Career: C.IF_Career, IF_DENY: C.IF_DENY, CAREER: C.CAREER });
module.exports = { C, ARENA, rng, makeWorld, makeGame, input, ROOT, careerGlobals };
