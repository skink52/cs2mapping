# mg_monsoon weapons: era loadouts and earned upgrades (playtest 1, finding 19)

AI-generated (Claude) for skink52. Batch G of [PLAYTEST_1.md](PLAYTEST_1.md); progress in [FIX_PT1_G.md](FIX_PT1_G.md).
Status words as `docs/reference/compatibility.md`: everything here is **simulated** (mock engine) or **compiled** at most.

## Is there a buy zone?

**No, and there is no buy menu on purpose.** The map has no `func_buyzone`. CS2 makes buy zones round the spawn points of a map
that has none, which is why the script has always closed buying three ways: `mv_params` (info_map_parameters) is built with
`buying 3` (nobody), and the script sets `mp_buytime 0`, `mp_startmoney 0`, `mp_maxmoney 0`, `mp_afterroundmoney 0` and both cash
award cvars to 0 (CONFIG.CVARS). A buy menu would sell 2020s rifles for dollars, which is the opposite of what the finding asks.

Weapons come from the script instead: a free **era kit** at every deploy, and **requisition points** earned in the fight that unlock
**optional upgrades** at the arms racks (E / F on `mv_kit_*`) or by chat (`!armory`).

## What the repo can make (research, 13 Nov 2026)

- `tools/weapons/` (the mg_trenchwarfare builder) rigs a new mesh onto a **stock weapon skeleton** so the stock first-person and
  third-person animations drive it, and `scripts/weapons.vdata` points the stock weapon class at the new model and sets its stats.
  One weapon class = one model for both teams (vdata has no per-team key), so each era weapon needs its own class.
- It needs the stock weapon's ModelDoc export (Source 2 Viewer dev build, "Decompile & Export", a GUI step). On disk
  (`C:\source2\projects\trenchwarfare\stock`): **SSG 08, AWP, SCAR-20, G3SG1, Glock-18, P2000** only. No rifle, MG, SMG or shotgun
  skeleton is exported, so the M16, AK, M60, RPD, XM177, K-50M and Ithaca cannot be remodelled until skink52 exports those six
  (`weapon_rif_m4a1`, `weapon_rif_ak47`, `weapon_mach_m249`, `weapon_mach_negev`, `weapon_rif_m4a1_silencer`, `weapon_shot_nova`).
- Meshes on disk: the Colt M1911 (Ole Gunnar Isager, CC BY 4.0, built and **verified in game** in mg_trenchwarfare on the P2000
  skeleton), and the Bad Company 2 Vietnam pack (GMod Workshop 740797619, a game rip, private build only) already converted as props:
  AK-47, M14, M60, M79, RPG-7 (`out/addon/models/mv/ext/w_*`). The Objaverse index (`C:\source1\gmod_assets\trenchwarfare\weapons\
  objaverse_index`) lists CC models of every weapon here (M16 243 hits, SKS, M14, M60, RPD, RPG-7, M79, TT-33, SVD, Mosin, Ithaca,
  CAR-15, claymore); none is downloaded. Downloads need skink52's yes (they are the next step for the AAA pass, see "Next").
- The full stock `weapons.vdata` (decompiled 25 Oct 2026) is at `C:\source2\projects\trenchwarfare\weapons.vdata`; mg_trenchwarfare
  ships an edited copy. The map addon's own `scripts/weapons.vdata` overrides the stock entries for this map; a server's own vdata
  addon would win over it (cs2-gotchas).

So every weapon gets **era stats and an era name now** (vdata + script), the stock model where nothing better exists yet, and a
remodel where both a mesh and a skeleton exist: the M1911 and the M14 this batch.

## Starting kits (free, every deploy)

Class commands `!rifle` `!mg` `!at` `!marksman` (also E at an arms rack). Limits as before: MG and AT 1 in 4 of the team, marksman
1 in 6. Pistol for everyone.

| Kit | US (CT) | Class | NVA (T) | Class | Route |
|---|---|---|---|---|---|
| Rifleman | **M16A1**, 20-rd mags, 750 rpm | `weapon_m4a1` | **AK-47 / Type 56**, 30 rd, 600 rpm | `weapon_ak47` | vdata stats; stock models (CS2's AK-47 is the period rifle already; the M4A4 stands in for the M16A1 until the m4a1 skeleton is exported) |
| Machine gunner | **M60**, 100-rd belt, 550 rpm, 7.62 NATO | `weapon_m249` | **RPD**, 100-rd drum, 700 rpm | `weapon_negev` | vdata stats; stock models (BC2 M60 mesh on disk, waits for the m249 skeleton) |
| Anti-tank / grenadier | **M79** 40 mm grenade launcher: lobbed (real 76 m/s, real gravity), 8 s reload, small blast, light on helicopters | script (Zeus as trigger) | **RPG-7**: flat, 25 s reload, big blast | script (Zeus as trigger) | the script's own projectile (CONFIG.AT + AT_TEAM); the Zeus is only the trigger, as before |
| Marksman | **M14**, semi-auto, 20 rd, iron sights (one 55 deg zoom, no scope) | `weapon_scar20` | **SKS**, semi-auto, 10 rd, iron sights | `weapon_galilar` | M14: **remodel** (BC2 mesh on the SCAR-20 skeleton); SKS: vdata, stock Galil model (no SKS mesh on disk) |
| Pistol | **M1911A1**, 7 rd, .45 | `weapon_hkp2000` | **TT-33**, 8 rd, no burst | `weapon_glock` | M1911: **remodel** (the Colt, rebuilt at `models/weapons/mv/m1911/`); TT-33: vdata, stock Glock model |

The marksman kit was the scoped SVD / M21 (flag crates only); scoped rifles are now earned (below) and the starting marksman carries
the iron-sighted service rifle of the period, at any rack.

## Earned upgrades (requisition)

Requisition points (**REQ**) are earned in the fight and shown on the HUD (`mv_req`, under the status box). Spending is optional.

| Earned for | REQ |
|---|---|
| a kill (any weapon, artillery and helicopter guns included) | 10 |
| an assist (30+ damage to a man someone else killed within 10 s) | 5 |
| a capture (every man of the side in the circle when it flips) | 15 |
| killing an enemy who carries an upgrade (bounty) | +5 |
| an enemy helicopter destroyed (the credited player) | 25 |
| an enemy gun knocked out, a fire-mission assist, a gun repaired | 10 / 5 / 5 |

| Unlock (`!armory <id>`) | US | NVA | REQ | Team limit |
|---|---|---|---|---|
| `grenades`: frag pouch (a frag and a smoke at every deploy; CS2 allows one of each) | M26 + M18 smoke | RGD-5 + RDG-2 smoke | 20 | none |
| `shotgun` | **Ithaca 37**, 5 rd, slam-fire | **Ithaca 37** (captured) | 30 | 1 in 6 |
| `carbine` | **XM177E2** (CAR-15), 20 rd, short | **K-50M** SMG, 35 rd, 900 rpm | 35 | 1 in 5 |
| `sniper` | **M21** (accurised M14, semi-auto, scope) | **Mosin-Nagant M91/30 PU**, bolt, scope | 45 | 1 in 8 |
| `claymore` | M18A1 claymore | DH-10 | 25 | not in this batch (see "Next") |

Classes: Ithaca `weapon_nova` (both sides: one class = one model, and a captured US shotgun is right), XM177 `weapon_m4a1_silencer`
(its long moderator reads as the XM177's flash hider), K-50M `weapon_mac10`, M21 `weapon_g3sg1` (**remodel**: the BC2 M14 mesh with a
centred, all-blued period scope on the G3SG1 skeleton, whose semi-auto animations fit), Mosin PU `weapon_ssg08` (vdata on the stock SSG 08
model; the SSG 08 skeleton is exported, so it is the next remodel once a Mosin mesh is chosen). The M21 (semi, two body shots) against
the Mosin (bolt, one body shot) is the period's real asymmetry; the price and the 1-in-8 limit are the same.

How it plays:
- **Unlocks last the round.** A bought upgrade is yours until the round ends, through deaths and respawns. A primary upgrade is a kit:
  it joins your kit cycle at the racks and `!sniper` / `!carbine` / `!shotgun` pick it. The frag pouch is added to every deploy.
- **Where:** at an arms rack or a held flag crate press **F** (inspect) to open the armory card, F again for the next item, **E** to
  requisition it (or to take an upgrade you already own). `!armory` shows the card and the list in chat anywhere; `!armory <id>` buys from anywhere and the weapon is issued at
  the next rack or deploy (as a kit asked for in the field). `!req` shows your points.
- **No runaway snowball:** a balance cap (100), points do not multiply with a streak, the side 60+ tickets behind earns x1.3, a man
  with an upgrade is worth +5 to the enemy, team limits per upgrade, and at a new round the unlocks go and only 30 REQ carry over.
- **Bots** earn the same and, on deploying with enough REQ, buy one thing for their slot: most take the frag pouch or the carbine,
  one in four the shotgun, and at most one bot per side the sniper rifle (CS2 bots camp with scoped rifles). AI pilots, gunners and
  crews never buy.
- **Survives:** death (kept), team switch (unlocks are side-neutral: the same unlock gives the other side's weapon), round (unlocks
  cleared, 30 REQ carried), disconnect (kept by player name for 15 min and given back on rejoin; the round rule applies if a round
  ended meanwhile), script reload (carried like the kit preference).

## Stats (vdata, `tools/mv_weapons.py`)

Stock entries edited, everything else stock (25 Oct 2026 decompile). Damage is per bullet before armour; rpm = 60 / cycle.

| Weapon | Class | Dmg | Mag / spare | Cycle (rpm) | Auto | Zoom | Notes |
|---|---|---|---|---|---|---|---|
| M16A1 | m4a1 | 33 | 20 / 6 | 0.08 (750) | yes | - | recoil 21 (light 5.56) |
| AK-47 | ak47 | 36 | 30 / 4 | 0.10 (600) | yes | - | stock handling |
| M60 | m249 | 35 | 100 / 2 | 0.10 (600) | yes | - | armour ratio 1.7, speed 190 |
| RPD | negev | 33 | 100 / 2 | 0.086 (700) | yes | - | speed 190 (light MG) |
| M14 | scar20 | 52 | 20 / 4 | 0.15 | no | 1 x 55 deg, no overlay | two body shots |
| SKS | galilar | 46 | 10 / 5 | 0.14 | no | 1 x 60 deg, no overlay | |
| M1911A1 | hkp2000 | 40 | 7 / 5 | 0.20 | no | - | |
| TT-33 | glock | 34 | 8 / 5 | 0.17 | no | - | burst off, penetration 1.5 |
| Ithaca 37 | nova | 24 x 9 | 5 / 25 | 0.75 | no | - | |
| XM177E2 | m4a1_silencer | 31 | 20 / 6 | 0.075 | yes | - | range modifier 0.94 |
| K-50M | mac10 | 30 | 35 / 4 | 0.067 (900) | yes | - | range 4000 |
| M21 | g3sg1 | 85 | 20 / 3 | 0.35 | no | 2 (30 / 12) | two body shots, a head shot kills |
| Mosin PU | ssg08 | 110 | 5 / 4 | 1.5 | no | 2 (35 / 15) | one body shot through armour |

Script side (CONFIG): `KITS` (names, classes, limits), `PISTOL`, `AT` + `AT_TEAM` (M79 / RPG-7), `REQ` (earning, prices, cap, carry,
catch-up, ledger time), `UNLOCKS` (the table above), `BOT_BUY`, `BULLET_VS_HELI` (new classes).

How the files are made (all in `tools/`, run from there): `mv_weapon_glb.py` (converted prop SMD -> GLB in the stock skeleton's
weapon_offset space), the repo's `tools/weapons/build_weapon.py` with `weapons_mv/<name>.json` (WW1_STOCK = the stock export folder;
output `out/weapons/build/`, copied into `out/addon/models/weapons/mv/` and `materials/models/weapons/mv/`), `tools/weapons/compare.py
built` for the side / first-person renders (`out/weapons/<name>_compare.png`), then `mv_weapons.py` for the vdata (it names a model only
once it is in the addon).

## Assets this batch

| Weapon | Route | Source | Status |
|---|---|---|---|
| M1911A1 | remodel, P2000 skeleton | Colt M1911 by Ole Gunnar Isager (Sketchfab, CC BY 4.0), the mg_trenchwarfare build config with the monsoon path | see FIX_PT1_G.md G7 |
| M14 | remodel, SCAR-20 skeleton | Bad Company 2 Vietnam pack M14 (GMod Workshop 740797619, rip: private build only, ASSETS.md) via `tools/mv_weapon_glb.py` (SMD -> GLB) | see FIX_PT1_G.md G7 |
| M21 | remodel, G3SG1 skeleton | the same M14 mesh + `scope2.py` axis-style scope; all-blued (the axis style has no brass faces; `materials/models/weapons/ww1/scope/brass.vmat` here is a blued copy of `scope.vmat` in case a later style does) | see FIX_PT1_G.md G7 |
| every other weapon | vdata stats, stock model | - | `scripts/weapons.vdata` |

## Next (not this batch)

1. skink52: Source 2 Viewer (dev build) "Decompile & Export" of `weapon_rif_m4a1`, `weapon_rif_ak47`, `weapon_mach_m249`,
   `weapon_mach_negev`, `weapon_rif_m4a1_silencer`, `weapon_shot_nova`, `weapon_smg_mac10`, `weapon_rif_galilar` into
   `C:\source2\projects\trenchwarfare\stock` (the builder's `WW1_STOCK`).
2. Meshes: the BC2 M60 / AK-47 are on disk; M16A1, SKS, RPD, TT-33, Mosin PU, Ithaca, XM177, K-50M need sources (Objaverse CC
   candidates, or GMod 108432322 "Black Ops M16A1/M16A2", 2377172653 "RS2 Vietnam Rifles" from the catalog). Each download needs
   skink52's yes.
3. The M79 and RPG-7 in the hand: the Zeus is the trigger for both sides (one class = one model). A launcher model needs a second
   trigger class (e.g. `weapon_sawedoff` with 1 round and no pellet damage) per side.
4. Claymore / DH-10: placed with a thrown decoy (OnGrenadeBounce), a pooled prop `mv_claymore_1..8` (needs a model and a map
   regeneration), the script's own directional blast. Designed, not built.
