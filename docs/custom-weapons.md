# Custom WW1 weapons for CS2 (vdata + cs_script, no plugins) — handover

Status 25 Oct 2026. Working in the `testing` addon; everything below is verified in game unless marked.

## What exists

| Weapon | Side | Replaces vdata entry | Model | Notes |
|---|---|---|---|---|
| Lee-Enfield SMLE | CT | `weapon_ssg08` | `models/weapons/ww1/lee_enfield/lee_enfield.vmdl` | 10 rd, 5 spare mags, Allied (Periscopic Prism style) offset scope, brass fittings |
| Gewehr 98 | T | `weapon_awp` (stat-for-stat SSG08 clone, 5 rd, 6 spare) | `models/weapons/ww1/gewehr98/gewehr98.vmdl` | Axis (Goerz/Oigee style) scope. Mesh is a BF1 rip ("BF1 All weapons") — replace before Workshop |
| Luger P08 | T | `weapon_glock` (8 rd, burst off) | `models/weapons/ww1/luger_p08/luger_p08.vmdl` | from `luger_p08.glb` |
| Colt M1911 | CT | `weapon_hkp2000` (7 rd) | `models/weapons/ww1/colt_m1911/colt_m1911.vmdl` | from `colt_m1911.glb` (display model reassembled) |
| Lewis Mk I | CT | `weapon_scar20` (planned) | `lewis_mk1.glb` | not built yet |
| Mondragón M1908 | T | `weapon_g3sg1` (planned, new weathered textures) | `mondragon-m1908/` | not built yet |

Shared materials: `materials/models/weapons/ww1/scope/{scope,brass,glass}.vmat` (procedural weathered steel/brass, dark glass).

## Folders to link (Claude desktop "Add folder")

1. `C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\testing` — the addon. Holds
   `scripts\weapons.vdata`, `scripts\ww1_weapons.js`, `models\weapons\ww1\*`, `materials\models\weapons\ww1\*`, `maps\testing.vmap`.
   To move the weapons into the real map's addon, copy `scripts\weapons.vdata`, `scripts\ww1_weapons.js`, `models\weapons\ww1` and
   `materials\models\weapons\ww1` into that addon's content root and add a point_script pointing at `scripts/ww1_weapons.js`.
2. `C:\source2\trenchwarfare assets` — source models (`*.glb`, `lee enfield\`, `Gewehr98\`, `mondragon-m1908\`), the original decompiled
   `weapons.vdata`, `stock\` (Source 2 Viewer "Decompile & Export" of the stock weapon vmdl_c files: ssg08, awp, glock18, hkp2000, scar20,
   g3sg1 — vmdl + body/anim/hull DMX + `_mag.vmdl`), and `tools\` (the builder, same files as `tools/weapons/` in this repo).
3. Optionally `C:\source2\trenchwarfare assets\build_out` as the builder's output root before copying into the addon.

## How it works

- `content\csgo_addons\<addon>\scripts\weapons.vdata` overrides stock weapon entries (model, clip, reserve, zoom, damage…). Edited keys:
  `m_szWorldModel`, `m_iMaxClip1`, `m_nPrimaryReserveAmmoMax` (spare mags when `m_bReserveAmmoAsClips`), `m_nZoomLevels/m_nZoomFOV1/2`,
  `m_bHideViewModelWhenZoomed` (scope overlay), `m_bUnzoomsAfterShot`, `m_bHasBurstMode`. Keep `m_szAnimSkeleton` stock. Keep only the
  uncompiled `.vdata` in `scripts\` — a `vdata_c` beside it wins. The vdata compiles on map build.
- cs_script (`ww1_weapons.js`) hands out the loadout per team (T: awp+glock, CT: ssg08+hkp2000) and strips other rifles/pistols every 0.25 s.
  cs_script cannot change viewmodels or vdata subclasses — one entity class = one model, which is why two classes are used per slot.
- Each custom model is the stock weapon's ModelDoc vmdl (from the S2V export) with the mesh, hull, mag and anim file paths swapped, muzzle
  attachment and hitbox recomputed. The mesh is rigged to the stock skeleton (`weapon` → `weapon_offset` → `clip|magazine`, `slide|rail`
  → `bolt|bolt_action`, `trigger`, `hammer`, `ag1_hand_r`) so the stock shoot/reload/dropped/inspect animations drive bolt, trigger, mag.
  Weapon models sit at the hand via `weapon_offset`; bone positions are fixed by the stock anims, so the mesh is moved to the bones, not vice versa.
- Known limits: first-person hand placement comes from the arms animation (can't fix per weapon); the Luger's toggle translates like a slide;
  the Gewehr has an internal mag so its reload shows an invisible stub mag.

## Builder (`tools/weapons/`, needs python3 + numpy + Pillow; copy of `C:\source2\trenchwarfare assets\tools`)

`python build_weapon.py <cfg>.json` → `<out>/models/weapons/ww1/<name>/` (vmdl, `_body.dmx`, `_hull.dmx`, `_mag.vmdl` + mesh/hull, copied stock
anim DMX) plus `<name>_debug_side/top.png` overlays against the stock mesh. For GLB inputs it also writes one vmat per glTF material with the
embedded textures; for FBX use `material.py` separately. `preview.py <name>` renders flat-shaded checks.

Config keys (see `lee.json`, `gewehr.json`, `luger.json`, `colt.json`): `fbx`/`glb`, `scale`, `axes` (permutation so the muzzle is +X, e.g.
`zxy` for these FBX, `Yxz`/`XYz` for the GLBs), `stock` + `stock_prefix` (`weapon_snip`/`weapon_pist`), `shift_wo` (offset that puts the
mesh into weapon_offset space — align bolt/bore axis `bore_wo`, bolt handle, trigger and grip to the stock bone/vertex positions printed by the
analysis), `part_bone`/`part_bone_idx`, `rules` (box selections of faces or whole components → bone; `mag:true`; `drop`; `move`/`rot180z`
for reassembling display models), `mag_parts`, `part_moves`, `drop_parts`, `boxes` (generated geometry), `scope` (`style` allied|axis,
`x0`, `y`, `y_post`, `mounts`, `clear` — seats itself on the receiver and clears the lifted bolt handle automatically).

Modules: `fbxparse.py`/`fbxmesh.py` (binary FBX 7.4), `glbmesh.py`, `dmx.py` (binary DMX 9 / model 22 read+write, byte-exact round trip),
`dmxmodel.py` (mesh/hull DMX in S2V layout), `hull.py` (convex hulls, ~50 verts — the full mesh as a hull crashed on weapon drop),
`scope2.py` (period scopes: lathe profiles, turrets, lens ends, bracket mounts), `weather.py` (procedural weathered steel/brass textures),
`material.py` (csgo_complex vmat + texture export).

## Conventions learned the hard way

- DMX texcoords are top-left origin: FBX/OBJ/glTF-bottom-left UVs must be V-flipped when writing DMX (not when writing OBJ).
- Normal maps: Source 2 wants OpenGL (Y+). Both FBX texture sets were DirectX → green flipped; glTF ones are already OpenGL.
- Enable `F_METALNESS_TEXTURE 1` in the vmat when a metalness map exists.
- Physics hull = small convex hull, never the full mesh. Pistol mag models have no skeleton; sniper mags have a `clip` bone.
- Model refs in vdata use `resource_name:"models/…vmdl"`; mesh material paths are addon-root relative (`materials/models/…vmat`).
