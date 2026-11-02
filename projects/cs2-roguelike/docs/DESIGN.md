# CS2 roguelike (working title) — design and suggestions, 3 Nov 2026

Status: proposal. Nothing built yet. This expands the brief (ancient basalt temple + cyber infusion, 8 PvE sectors
feeding one 64-player PvP showdown, three classes, minimal HUD) and marks where CS2 forces a different method.
"How the other addons did it" refers to [docs/creation/guide.md](../../../docs/creation/guide.md),
[cs_script-notes.md](../../../docs/reference/cs_script-notes.md) and [cs2-gotchas.md](../../../docs/reference/cs2-gotchas.md).

## 1. Reality check: what the brief assumes vs what CS2 gives us

| Brief says | CS2 fact | What we do instead |
|---|---|---|
| A procedural engine builds the grid "via the VMAP compiler" per match | A map is static once compiled. No runtime geometry. | **Offline generator** (Python, `create/vmapgen.py`) writes the whole superset of rooms once. **Runtime roguelike** comes from the script: which gates open (the maze), which spawns/altars/traps are live, altar offers, elite modifiers. One seed per round, so the Node mock can replay a run exactly. |
| `info_enemy_spawn` AI pathing nodes, "enemy AI" | CS2 has no NPCs. Bots are players (T/CT only) and **take player slots**: 64 humans = 0 bots. | **Enemies are script-driven props** (Hellmatch's monster state machines, pooled `prop_dynamic` + `SetModel`/`Move`). Real guns hurt them through `OnBulletImpact` (hit entity, weapon damage from `GetData()`, range falloff we compute); knives through `OnKnifeAttack` + a sphere trace. They hurt players with `TakeDamage`, so armor, hit flashes and the killfeed all work. Below 64 players, CS2 bots may fill squads (optional). |
| 8 teams | Two sides only. | Squads are a script concept. `mp_teammates_are_enemies 1`, `OnModifyPlayerDamage` aborts same-squad hits. The CS2 round goes to the side of the winning squad (`FireWinCondition`). |
| Walls "retract into the floor" to open the colosseum | Movers with baked lighting leave their shadows behind; big movers are flaky. | Sectors live in separate void boxes anyway, so the breach is a **synchronised teleport** (screen flash, 3-2-1, everyone lands on their staging balcony of the arena). Cheap, robust, dramatic enough. |
| Dynamic coloured lights for neon | Dynamic lights cost; 4 shadow slots per area. | Neon = **self-illuminated materials** (`csgo_vertexlitgeneric` + `F_SELF_ILLUM`, emissive strips) plus small **unshadowed** cyan `light_omni2` with capped range. Looks like the brief, costs nothing. |
| Monk dome "zeroes projectile velocity" | Bullets are hitscan. | Dome = a **damage field**: hits on players inside from attackers outside are cut (we pick 60–80 %) in `OnModifyPlayerDamage`; grenades crossing the boundary are removed (`OnGrenadeThrow` + per-tick segment test); **enemy projectiles are script-flown so the dome stops them literally**. |
| Chrono-Raider +40 % "weapon cycling" | No fire-rate or reload-speed control from script. | Keep the +40 % speed (per-tick ground velocity, the `Speed_<x>` method) and swap cycling for **instant clip refill on activation** (`SetClipAmmo`). Chromatic edge tint = a per-player Panorama overlay panel. The death save is `PREVENT_DEATH` in `OnModifyPlayerDamage`, then `SetHealth(50)` and `Teleport` to the logged spot. |
| HUD boxes "above the weapon display" | Panorama custom HUDs are top-anchored, no bottom alignment. | Same look, positioned with fixed margins at the 1080 layout height (`create/hud_check.py` gates it). |
| Player models per class | `SetModel` to a stock agent drew the player's own body in first person (mg_trenchwarfare). | v1: keep stock models. Class shows on the HUD, a coloured glow/tint, and the ability VFX. Custom agents only if we rebuild on a decompiled agent vmdl (models.md), later. |

## 2. Match structure (keep it, scale it)

- **Scaling:** squads of 2–8, 2–8 squads, from the player count (Hellmatch's arena-table pattern). 64 = 8×8. 20 = 4×5. Never one squad.
- **Stage 1, three floors per sector (~3 min each):** a sector is a 4×4 grid of 512-unit cells; the script opens one maze through it per floor
  (every cell has four portcullis gates; closed ones stay down). Clear a room → its gates open with the stone-drop sequence. Floor 3 ends at a
  shrine boss. Quick squads wait in their **neon staging balcony**, which is a buy zone.
- **Stage 2, the breach:** when all sectors are clear or the floor clock runs out, teleport. Squads land on eight balconies around the amphitheatre.
  3-minute showdown; holographic barriers close inward every 45 s (script damage ring) so it ends. Last squad standing; ties by nanites.
- **Gunplay stays CS2:** no custom weapons in v1. Loot is real CS2 weapons (altars/chests `GiveNamedItem`), real buy menu in staging
  (nanites **are** CS2 money: `AddMoneySpendableNow`, `func_buyzone`, buy time only during staging). Upgrades modify things the player can feel but
  that don't fight CS2's feel: armor cap, lifesteal on kill, reload-on-kill, reserve ammo, grenade refunds, dash range, dome radius. PvP damage
  modifiers stay within ±15 %.
- **Altars:** +E on a pedestal shows three offers on the HUD. Number keys can't be read from script, so pick with **A / D to cycle, E to take**
  (Space Racer's picker). Offer pools per class + general.

## 3. Enemies (the PvE half)

Theme: the temple's guardians, corrupted by the nanite infusion, so **stone and hologram constructs**, not humanoids. That is deliberate: rigid
bodies need no skeletal animation (the Tripo rigging problems in mg_trenchwarfare's notes), read clearly at range, and bob/tilt/slide from script.

| Type | Role | Body | Attack |
|---|---|---|---|
| Shard drone | fast swarm | holo tetra, 300 tris, self-illum | melee lunge (TakeDamage 8–12) |
| Sentinel | turret | anubis `statue01_head` on a basalt base (stock) | hitscan tracer prop, telegraphed 0.6 s glow |
| Lancer | ranged | cracked stone slab with a cyan core | script-flown bolt, dodgeable, stopped by the dome |
| Golem | tank | `generic/stone_statue_01` (stock, breakable pieces exist) | slow, slam AoE, armor-ignoring |
| Shrine warden (boss) | floor 3 | the one Tripo model (≈ 4k tris) | phases: lancers, slam, drone summon |

Weak points: Sentinel head, Golem core — bonus damage from `OnBulletImpact` position vs a stored local point on the body.

## 4. World and assets

- **Grid:** floor plane z = 0 everywhere, cells 512×512, wall thickness 32, ceilings 256/384. Every vault is authored on that grid, so stitching is
  exact and the "deep trim" (Anubis trim kit, 37 pieces) covers the floor-wall joint in every cell. Sectors: 2048² each, in their own void boxes with
  moondome + skybox shells; central arena 4096², three tiers.
- **Stock kits that fit the brief (counted in `pak01_dir.vpk`):** `models/anubis` + `models/de_anubis` (334: pillars, column kits, arches, trims,
  statues, signs, lights), `materials/de_ancient` (356: carved stone, blends), `de_train/hr_t/server_a` racks, `de_overpass` wiresets/conduits,
  `de_vertigo` rigid conduit, cs_office/nuke monitors, `de_cache` self-illum glass for holo panels, `generic/stone_statue_01`.
  There is no torii gate, brazier or hex dome in stock.
- **Ours, procedural (`create/build_prop.py`: box/lathe geometry with baked PBR, LODs, hulls; edges are sharp by construction):** torii gate frame,
  portcullis (pooled, script-moved), carved conduit trim with emissive channel, holo pedestal + emitter, neon strip, hex dome shell (`fx_models`).
- **Tripo (1905 credits, budget ≤ 200 for v1):** the Shrine warden, maybe two drone variants. Rules below.
- **Lighting:** baked; one probe volume per room; ≤ 2 shadowed lights per room; cyan omni lights unshadowed, range ≤ 160.
- **Vis/audio:** one Lowest hint over everything, Low per room; a soundscape per sector; `env_gradient_fog` black fade inside the temple.

### Tripo without sloppy edges

The sloppiness came from decimating ~950k-triangle meshes with vertex clustering (`create/glbmesh.py`): clusters merge across creases, so every hard
edge rounds off and the baked texture smears over it. Three changes:
1. **Ask Tripo for the low poly.** Generate at high quality, then run Tripo's own retopology/low-poly conversion (`face_limit` 3–6k, quad on) and
   export that GLB. Their remesher keeps creases; we decimate little or not at all.
2. **Crease-aware decimation** in `glbmesh.py`: never cluster two vertices whose faces meet at > 35°, keep split normals at creases, snap near-planar
   clusters to the plane. Verify on a stone block before any new generation.
3. **Bake high→low normals** so chamfers and carvings stay crisp on the low mesh (`create/bake.py` has the baker).
Hard-surface pieces (blocks, trims, gates, pedestals) are **not** Tripo jobs at all: build_prop makes them exact.

## 5. HUD (custom_hud_layout)

Left: ability tile with clockwise cooldown mask (a radial sprite sequence, 24 frames) and a tenths countdown. Centre: HP / AR, class, passive pips.
Right: `NANITES 1250` under the match timer, `AREA  PVE SECTOR 04`. Top-centre buff icons. Everything in the 4:3-safe band, checked by hud_check.
CS2's own HUD stays visible (hiding it also blocks weapon switching).

## 6. Build order

1. Project scaffold (`projects/cs2-roguelike/`): README, licences, `tools/`, `src/core` (pure JS rules) + `src/cs2` (adapter), mock tests.
2. **Vault generator → one sector compiled and walked.** Grid, 12 vaults from the Anubis kit, trims, gates as pooled props, lighting, probes, nav seed.
3. Script skeleton: squads, sector assignment, maze gating, floor clock, staging/buy, the breach teleport, round end. Mock-tested with 64 players.
4. Enemies: pool, state machines, bullet hits, drops. Balance in the Node sim.
5. Classes and upgrades. 6. HUD. 7. Central arena. 8. Our props, then the Tripo boss. 9. Polish, loading screens, radar, workshop docs.

## 7. Unverified until tested in CS2

`OnBulletImpact` reporting a pooled `prop_dynamic` as `hitEntity` (needs the prop solid); `Glow()`; `AddMoneySpendableNow` with the buy menu
in a map-driven round; `SetClipAmmo` mid-reload; `PREVENT_DEATH` save at exactly lethal damage with armor; 64 real players plus ~200 live enemy props
per tick (Hellmatch: 2–2.5 ms/tick at 64 players on a pessimistic mock).
