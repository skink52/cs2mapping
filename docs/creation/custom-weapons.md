# Custom weapons for CS2 (vdata + cs_script, no plugins)

How mg_trenchwarfare's WW1 weapons were made: stock weapon entries overridden in `weapons.vdata`, new models rigged onto the stock weapon skeletons so the
stock animations drive them, and a cs_script that hands out the loadout. Builder: [`tools/weapons/`](../../tools/weapons) (python3 + numpy + Pillow).
Engine facts (viewmodel unreachable from script, Source 2 Viewer dev build for `vdata_c`, server vdata priority):
[cs2-gotchas, models and weapons](../reference/cs2-gotchas.md#models-modeldoc-and-weapons).

The weapon list and status (Lee-Enfield → `weapon_ssg08`, Gewehr 98 → `weapon_awp`, Luger → `weapon_glock`, Colt M1911 → `weapon_hkp2000`, Lewis →
`weapon_scar20`, Mondragón → `weapon_g3sg1`) and the PC folders of that session are a project handover:
[trenchwarfare-cs2 `docs/weapons_handover.md`](https://github.com/skink52/trenchwarfare-cs2/blob/main/docs/weapons_handover.md). Before the Workshop, the
Gewehr 98 mesh (a "BF1 All weapons" rip) must be replaced ([workshop.md](workshop.md#keeping-it-safe-to-publish-ip)).

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

## Builder

`python build_weapon.py <cfg>.json` → `<out>/models/weapons/ww1/<name>/` (vmdl, `_body.dmx`, `_hull.dmx`, `_mag.vmdl` + mesh/hull, copied stock
anim DMX) plus `<name>_debug_side/top.png` overlays against the stock mesh. For GLB inputs it also writes one vmat per glTF material with the
embedded textures; for FBX use `material.py` separately. `preview.py <name>` renders flat-shaded checks.

Config keys (see `lee.json`, `gewehr.json`, `luger.json`, `colt.json`): `name`, `sub` (model folder, e.g. `models/weapons/ww1/lee_enfield`),
`out` (output root; required), `fbx`/`glb`, `flipv` (FBX only: flip V once more; default off), `flip_green` (DirectX → OpenGL normal maps), `texsize` (default 2048), `scale`, `axes` (permutation so the muzzle is +X, e.g.
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

- UVs: the builder brings every source to a bottom-left V convention (`glbmesh.py` flips glTF's top-left V on load) and flips once when writing DMX
  (DMX texcoords are top-left). Leave `flipv` off for FBX: an extra flip caused the "textures misaligned" report.
- Normal maps: Source 2 wants OpenGL (Y+). Both FBX texture sets were DirectX → green flipped; glTF ones are already OpenGL.
- Enable `F_METALNESS_TEXTURE 1` in the vmat when a metalness map exists.
- Physics hull = small convex hull, never the full mesh. Pistol mag models have no skeleton; sniper mags have a `clip` bone.
- Model refs in vdata use `resource_name:"models/…vmdl"`; mesh material paths are addon-root relative (`materials/models/…vmat`).

## Also learned (from the weapons chats)

- cs_script can't reach the viewmodel (no `*viewmodel*` class exists at runtime); `CSWeaponBase.SetModel` only changes the third-person/dropped model and fails
  silently on a model that isn't loaded.
- Decompiling `scripts/weapons.vdata_c` needs the Source 2 Viewer **dev build** (release builds throw "Unknown KVType … 26"); use Decompile & Export.
- One entity class = one model: vdata has no per-team model key and scripts can't hand out vdata subclasses, so per-team rifles use two classes
  (`weapon_ssg08` → Lee-Enfield, `weapon_awp` → Gewehr 98 with every SSG08 gameplay stat copied into the AWP entry: damage, armour ratio, penetration,
  range modifier, cycle time, spread/recoil, move speed, price, kill award). `m_bHasBurstMode` turns burst off (Luger on the Glock entry).
- Without vdata, a magazine size can be emulated by counting `OnGunFire` and strip + regive (the HUD still shows the old count).
- A server's own vdata addon takes priority over a map's.
- **Iron-sight zoom** (Lewis/Mondragón, mg_trenchwarfare plan): 1 zoom level, FOV ~55, `m_bHideViewModelWhenZoomed false` (no scope overlay). Once vdata sets the
  magazine sizes, the script's `RIFLE_MAG` emulation goes.
- **Swapping weapons in a slot from script:** SHIFT+E or `!swap` toggles the streak weapon and the scoped rifle, keeping ammo (mg_trenchwarfare).
- Moving the weapons into another addon: copy `scripts/weapons.vdata`, `scripts/ww1_weapons.js`, `models/weapons/ww1`, `materials/models/weapons/ww1` into its
  content root and add a `point_script` for the js (mg_trenchwarfare used a `copy_ww1_weapons_<addon>.bat`).

