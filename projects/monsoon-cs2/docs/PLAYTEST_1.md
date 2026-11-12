# mg_monsoon playtest 1 (skink52, 12 Nov 2026): findings and fix tracker

The first in-game run of the pass-4 build (mv-0.5). Screenshots are in `out/playtest1/` (not in git): p1 tunnel entrance, p2 foliage line, p3 sandbags,
p4 hut textures, p5 trunk colour, p6 underground, p7 temple vines.
The bar is AAA quality. Fixes run in batches of 1-2 agents. Each batch keeps its own progress file, updated after every item, so a usage reset loses little.

Status: `open` / `in progress (batch)` / `fixed (compiled)` / `fixed (in-game verified)` / `won't fix (reason)`.

| # | Finding | Batch | Status |
|---|---|---|---|
| 1 | Flags don't move and can't be captured | S | fixed (simulated, compiled; FIX_PT1_S.md) |
| 2 | Apache rotors don't spin | S | fixed (simulated, compiled; FIX_PT1_S.md) |
| 3 | Helicopters may be slightly too large | S | won't fix (both within 2-4 % of real size at the map's 40 u/m scale; knobs in FIX_PT1_S.md) |
| 4 | T helicopter (Mi-8) has significant invisible / see-through parts | S | fixed (simulated, compiled; FIX_PT1_S.md) |
| 5 | Helicopters need weapons (check whether they exist but can't be found; make firing obvious) | S | fixed (simulated, compiled; FIX_PT1_S.md) |
| 6 | `!air` works, `!help` doesn't; no other commands are discoverable | S | fixed (simulated, compiled; FIX_PT1_S.md) |
| 7 | Bridge machine gun sounds tinny; use the M249 sound | S | fixed (simulated, compiled; FIX_PT1_S.md) |
| 8 | Tunnel entrance very blocky (p1) | W | fixed (generated + offline checks; map compile pending; FIX_PT1_W.md) |
| 9 | Underground blockiness, floating arches (p6) | W | fixed (generated + offline checks; map compile pending; FIX_PT1_W.md) |
| 10 | Some T spawns stuck in the rocket/mortar battery wall | W | fixed (generated + offline checks; map compile pending; FIX_PT1_W.md) |
| 11 | Line across foliage (p2) | W | fixed (generated + offline checks; map compile pending; FIX_PT1_W.md) |
| 12 | Colour bug from grass on tree trunks: pale bands (p5) | W | fixed (generated + offline checks; map compile pending; FIX_PT1_W.md) |
| 13 | Vines on poles around the Khmer temple float in the air (p7) | W | fixed (generated + offline checks; map compile pending; FIX_PT1_W.md) |
| 14 | Sandbags look wrong (p3) | W | fixed (generated + offline checks; map compile pending; FIX_PT1_W.md) |
| 15 | Water should have depth: a real func_water | W | fixed (generated + offline checks; map compile pending; FIX_PT1_W.md) |
| 16 | Generated prop textures are low resolution across the board (p4) | P (round 2) | open |
| 17 | Hay and hay bales are not photorealistic | P (round 2) | open |
| 18 | Temple animal statues are the wrong vibe: source a proper model | P (round 2) | open |
| 19 | No custom weapons, no buy zone: era weapons, kills unlock optional upgrades (e.g. snipers) | G (round 2) | fixed (simulated, compiled; WEAPONS.md, FIX_PT1_G.md) |

Batches: S = script and helicopters (`docs/FIX_PT1_S.md`), W = world geometry (`docs/FIX_PT1_W.md`), P = prop quality, G = era weapons and
upgrade system. After S and W finish, one integrated deploy and map compile.
