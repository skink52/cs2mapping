# IRONFRAME: interfaces between the parts

The project is built by several hands at once, so the seams are fixed here first. Every file below names its owner module.
Plain JavaScript everywhere (no TypeScript, no modules inside the script: `create/build/build.mjs` concatenates `src/core/*.js`
then baked `const` data then `src/cs2/*.js` under one import line). Core files must not touch the CS2 API; adapter files may.
Top-level names must be unique across all files (one shared scope). Prefixes: core `IF_*` constants, adapter `ifr*` functions.

## 1. Baked data (`build.json` `data`)
| Const | File | Writer |
|---|---|---|
| `PARTS` | `data/parts.json` | hand-written (this folder) |
| `ARENA` | `out/addon/_gen/arena.json` | `tools/vmap.py` (§2) |
| `HUD` | `out/addon/_gen/hud.json` | `tools/hud.py` (§5) |
| `SOUNDS` | `out/addon/_gen/sounds.json` | `tools/sounds.py` |
| `MODELS` | `out/addon/_gen/models.json` | `tools/frames.py` + `tools/weapon_props.py` + `tools/fx.py` (§4) |
| `VERSION` | `data/version.json` | `{"version": "0.1.0", "stamp": "..."}` |

## 2. Arena data (`arena.json`)
```json
{ "id": "dunes", "name": "Dunes", "title": "IRONFRAME: Dunes",
  "bounds": {"min": [-7000, -7000, 0], "max": [7000, 7000, 5000]},
  "drops": {"t": [[x, y, z, yaw], ...], "ct": [[...]], "ffa": [[...]]},          // 8+ per team, z = ground + 1500 is the drop start
  "points": [{"id": "A", "pos": [x, y, z], "radius": 700}, ...],                  // Conquest, 3; the beacon for Sortie is points[1]
  "booth": [x, y, z], "cache": [x, y, z],                                          // pawn booth and cache room origins (far below)
  "nav": {"cell": 256, "x0": -7168, "y0": -7168, "w": 56, "h": 56,
          "height": [...w*h ground z...], "walk": [...0/1...], "struct": [...0/1: traces needed here...], "cover": [...0..255...]},
  "landmarks": [{"name": "Refinery", "pos": [x, y, z]}]
}
```
The core uses `nav.height` (bilinear) as the ground wherever `struct` is 0, and asks the world for a trace where it is 1 or
when a mech is within 2 cells of a `struct` cell. Bots path on `walk` with a flow field toward their objective.

## 3. Core API (`src/core`, owner: core)

```js
// world: supplied by the adapter (CS2 traces) or by the sim (heightfield only)
//   traceLine(a, b)        -> {hit: bool, pos, normal, frac, mech: slot|-1}   (mech hits come from the core's own spheres; the world only reports geometry)
//   traceSphere(a, b, r)   -> same
//   traceClip(a, b, slot)  -> {hit, solid (started in solid), pos (hull feet at the stop), normal, frac} | null   optional: a player-hull trace
//                             (CS2 Instance.TracePlayer, the only trace that collides with clip brushes); null = no pawn to trace with (skip)
//   now()                  -> seconds
// game.skyZ (optional, set by the adapter after measuring): the sky shell's height; rounds cruise under it and vanish at it (core IF_capZ / IF_atSky)
// input.camPos / camDir (humans): the follow camera's position and view direction; shots converge on the point under the reticle (IF_reticle)
const game = new IF_Game({ parts: PARTS, arena: ARENA, cfg: IF_DEFAULT_CFG /* overridden by CONFIG.core */, world, rng });
game.setMode(modeKey, humans)            // 'tb' | 'cq' | 'sk' | 'so'; the core also has game.pickMode(humans, votes)
game.addPlayer(slot, { team: 2|3, human: bool, name, pilot })    // pilot: {rank, owned:Set, upgrades:{id:lvl}, loadouts:[str,str,str], active, flags} or null (stand-alone)
game.removePlayer(slot)
game.setLoadout(slot, loadoutStr)        // returns 0 or a deny code (SERVER_CONTRACT §4); applies on next spawn
game.requestSpawn(slot)                  // when the player is ready (garage closed)
game.setInput(slot, input)               // every tick for humans: {mx, my, yaw, pitch, boost, qb, jump, fire:[r,l,rs,ls], cycle, any}
game.tick(dt, now)                       // advances everything; fills game.events
game.events                              // array, cleared by the adapter after reading; see §3.1
game.mechs                               // Map slot -> IF_Mech (read-only for the adapter; see §3.2)
game.projectiles, game.missiles, game.beams, game.effects   // pools; alive flags; adapter mirrors them to props
game.match                               // {mode, phase:'warmup'|'running'|'podium'|'over', timeLeft, scores:{2,3}, tickets, points:[{id, owner, progress}], killTarget, winner, podium:[slots]}
game.pilotSummary(slot)                  // {xp, credits, kills, assists, captures, damage, pveKills, bossKills, won, streakBest} for the round
game.garage                              // IF_Garage: catalogue queries for the UI: list(kind), canBuy(slot,id), budgets(loadoutStr), describe(id)
IF_Progress.validate(loadoutStr, pilot, parts) -> 0 | denyCode      // the same rules as the plugin; vectors in data/contract_vectors.json
IF_Progress.rankFor(xp), IF_Progress.xpFor(rank), IF_Progress.roundXp(summary, ctx)
```

### 3.1 Events (`game.events` entries)
`{t:'spawn', slot}`, `{t:'death', slot, killer, pos}`, `{t:'kill', victim, killer, assist:[slots], weapon}` (the adapter turns this into
`TakeDamage FORCE_DEATH`), `{t:'damage', victim, attacker, amount, pos, impact, weapon, crit}` (crit: a direct hit on a staggered mech) (adapter: scaled `TakeDamage`),
`{t:'fire', slot, hp:0..3, weapon, pos, dir}`, `{t:'hit', pos, normal, kind}`, `{t:'explode', pos, radius, kind}`,
`{t:'beam', from, to, kind, slot}`, `{t:'stagger', slot}`, `{t:'lock', slot, target, stage:0|1|2}` (stage 2 = hard; the target gets a warning),
`{t:'threat', slot, kind:'lock'|'launch'|'close'}`, `{t:'capture', point, team, slot}`, `{t:'qb', slot, chain}` (chain: the two-step QB), `{t:'land', slot, hard}`,
`{t:'en_empty', slot}`, `{t:'ability', slot, kind}`, `{t:'bounty', slot, streak}`, `{t:'round_end', winner, podium, podiumInfo:[{slot, name, team, npc, kills (PvE included), score}]}` (AI fill included), `{t:'wave', n}`,
`{t:'sound', key, pos|slot, only:slot?}`, `{t:'say', slot|-1, text}` (HUD line), `{t:'garage', slot, open}`.

### 3.2 Mech state (`IF_Mech`, read by the adapter)
`slot, team, human, alive, frame (part), cls (class row), legs (leg type row), loadout (ids[9]), pos{x,y,z}, vel, legYaw, torsoYaw, pitch,
onGround, boosting, qbTime, hover, ap, apMax, en, enMax, enStalled, stagger, staggerMax, staggered, protect, landLag, weapons[4]
{part, ammo, mag, cd, heat, charge, reloading}, lock {target:-1|slot, stage, t}, threats[], streak, dropT (falling in), deathT`.

## 4. Models (`models.json`, owner: tools)
```json
{ "frames": { "<model key>": { "legs": "models/ifr/frames/<key>/<key>_legs.vmdl" | null, "upper": "models/ifr/frames/<key>/<key>_upper.vmdl",
              "height": 288, "hip_z": 150, "spheres": [[x,y,z,r], ...], "hardpoints": {"ra": [x,y,z], "la": [...], "rs": [...], "ls": [...]},
              "muzzles": {"ra": [...], "la": [...]}, "boosters": [[x,y,z], ...], "anims": ["idle", "walk", "boost", "land"] | [] } },
  "weapons": { "<part key>": "models/ifr/weapons/<key>.vmdl" },
  "fx": { "tracer": "...", "beam": "...", "ring": "...", "missile": "..." },
  "mounts": { "tol": 4, "res": 2.5, "grips": {"<weapon>": [x,y,z]},
              "frames": { "<model key>": { "<weapon>": [right x,y,z, left x,y,z] } } } }
```
Positions are in the frame's model frame after scaling (x forward, y left, z up, origin at the feet). Spheres cover the mech for
the core's hit tests (3–6 per frame). `tools/frames.py` writes them from the mesh.
Weapon props have their model origin at the grip (arm) / mount base (shoulder), `tools/weapon_props.py` GRIPS + repivot. `mounts`
(written by `tools/weapon_fit.py --fit`, kept by frames.py / weapon_props.py / fx.py) is where each weapon prop's origin goes on each
frame, in the upper model frame: the right slot (ra / rs) then the left (la / ls); 30_render.js `weaponMountPos()` reads it and falls
back to `hardpoints`. The garage preview must use the same function.

## 5. HUD (`hud.json`, owner: tools/hud.py; driver `src/cs2/50_hud.js`)
`hud.json` = `{ "layout": "panorama/layout/custom_game/ironframe.vxml", "panels": {id: {classes: [...], vars: [...]}}, "ladders": {name: steps}, "text_slots": {...} }`.
Driver API for the rest of the adapter:
```js
ifrHudSet(slot, panelId, cls, on)        // per-player class; mirrored, change-only, governed (900 writes/tick, odd/even halves)
ifrHudVar(slot, name, text)              // dialog variable; quantised text helpers: ifrHudNum(slot, name, n, step)
ifrHudLadder(slot, name, frac)           // gauges: picks the step class, clears the previous one
ifrHudLine(slot, text, seconds)          // bottom message line
ifrHudReset(slot)                        // full redraw request (activate / team change / spawn)
ifrHudTick()                             // flushes the governor; call last in the think
```

## 6. Server channel (`src/cs2/70_server.js`)
`ifrSrvSend(slot, op, args[])` (echo ifr_srv), `ifrStat(slot, key, n)` (echo mgstat), `ifrServerMode` flag, `ifrMailRead(slot)` → payload
string or null, handlers registered for `ifr_server`, `ifr_pilot`, `ifr_deny`, `mgstat_on`, `mgstat_off`. See SERVER_CONTRACT.md.

## 7. Entity names (map, owner: tools/vmap.py; all with vis group `ifr_gen`)
`ifr_script` (point_script), `ifr_hud` (custom_hud_layout, layout `panorama/layout/custom_game/ironframe.vxml`), `ifr_tpl_prop` (+ `ifr_tpl_prop_src`),
`ifr_cache_N`, `ifr_booth`, `ifr_mail_00..63` (info_target), `ifr_snd_<key>` (point_soundevent), `ifr_pfx_<kind>_NN` (info_particle_system pools:
`boost` 128, `muzzle` 64, `boom` 24, `spark` 16, `gboom` 8, `trail` 128), `ifr_map_params` (info_map_parameters), `ifr_sky`, `ifr_drop_<t|ct>_N`
(info_target drop points), `ifr_point_<A|B|C>` (info_target), spawns `info_player_terrorist`/`counterterrorist` 32 each in the booth.
