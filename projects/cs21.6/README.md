# CS 1.6 in CS2 (mg_cs16)

A CS2 minigames map that plays like Counter-Strike 1.6: de_dust2, de_train and de_nuke converted from the 1.6 maps into
one Hammer map, and a map script that brings the 1.6 rules, money, buy menu, HUD, radio and gun sounds.
Up to 64 players: small games play one map; bigger games split each team over two or three maps at once.

> **AI-generated code.** The tools and the map script were written by an AI (Claude) and are only partly tested in CS2.
> Check [docs/TESTING.md](docs/TESTING.md) before running it on a server.

> **No 1.6 content is in this repository.** The maps, textures, HUD pictures, menu texts and sounds are made on your
> own computer from your own Half-Life / Counter-Strike 1.6 install. Don't publish the built addon without the rights to
> that content.

## How it plays

- **Maps.** Fewer than 25 players: one map. 25 to 44: two maps. 45 or more: three (never more maps than the smaller
  team has players). Each team is split evenly over the maps that run; players stay on their map between rounds.
  The map set moves on every 10 rounds. `!dust2`, `!train`, `!nuke` ask for a map.
- **Rounds.** Each map plays a 1.6 bomb round (6 s freeze time, 3 min, C4 45 s, 1.6 win rules). The CS2 round ends when
  every map is decided; the side that won more maps wins it. Once one map is done the others get at most 90 seconds more
  (planted bombs still play out).
- **Money.** $800 start, $16000 max, 1.6 round rewards and losing-streak bonus (kept per map), +$300 a kill,
  -$3300 for a teammate. Round money arrives when the next round starts, as in 1.6.
- **Buying.** CS2's buy menu is off. Press **F** (inspect) in a buy zone during the buy time (freeze time + 90 s) for the
  1.6 buy menu, with 1.6 items, prices and pictures. Chat works too: `!buy`, `!ak47`, `!m4a1`, `!vesthelm`, `!primammo`,
  `!rebuy` (all the 1.6 buy names). A bought gun has one magazine, as in 1.6; one click on primary / secondary ammo fills it.
- **Damage.** 1.6 weapon damage and range falloff, 1.6 hit groups, 1.6 armour, knife (stab 65, x3 from behind),
  HE grenade, C4 blast and fall damage. CS2 still decides what was hit.
- **HUD.** The 1.6 HUD, made from the 1.6 sprites: health, armour, round timer, money with +/-, ammo, buy zone / C4 /
  defuse kit icons, centre messages. `!hud raised` (default, above CS2's own boxes), `!hud classic` (1.6 positions), `!hud off`.
- **Players.** The eight 1.6 player models, rebuilt on CS2's player skeleton so CS2's animations, hit boxes and ragdolls
  work with them, chosen in the 1.6 class menu (`!class` opens it again; `MODELS_16: false` uses CS2 agents instead).
  The bomb carrier wears the 1.6 bomb pack and CTs with a defuse kit wear the kit, as in 1.6.
  CTs get the USP instead of the P2000, everyone spawns with 1.6 spare ammo and no armour. 1.6 movement settings and
  jump height.
- **Sound.** 1.6 gun, knife, grenade and C4 sounds; 1.6 radio at round start, round end, bomb planted / defused,
  "Fire in the hole".
- **Bots.** CS2 bots play and buy 1.6 gear when they spawn.

The weapons are CS2's own, mapped to the 1.6 roster (e.g. CV-47 = AK-47, K&M .45 = USP-S, Schmidt TMP = MP9,
Krieg 550 = SCAR-20); their recoil and movement speed stay CS2's. The first-person hands are 1.6's (fingerless gloves,
bare forearms) on CS2's arm and finger bones, holding CS2's guns.

## Building

Needs Python 3 (numpy, Pillow) and Node.js. Paths below are examples.

```
HL=".../steamapps/common/Half-Life"                 # your 1.6 install
ADDON=".../content/csgo_addons/mg_cs16"             # the CS2 addon (made with the CS2 Workshop Tools)
gcc -O2 -o build/cliphull tools/goldsrc/cliphull.c -lm
python3 tools/dump_soundevents.py ".../game/csgo/pak01_dir.vpk" build weapons     # CS2's weapon sound events
python3 tools/sounds.py "$HL/cstrike" "$HL/valve" "$ADDON/soundevents/soundevents_addon.vsndevts" build/soundevents_weapons.json out/addon
python3 tools/convert_map.py "$ADDON/maps/mg_cs16.vmap" "$HL/cstrike" "$HL/valve" out/addon
python3 tools/models.py "$HL/cstrike" <CS2 agent decompiled to ModelDoc> out/addon     # 1.6 player models
python3 tools/loading.py out/addon/maps/mg_cs16.vmap out/addon out/game <shot pngs>   # radar, loading screens, icon
python3 tools/hud.py "$HL/cstrike" out/addon
node tools/build.mjs                                  # -> out/addon/maps/scripts/cs16.js
node test/core_test.cjs && node test/mock_cs2.mjs 64 600
```

`tools/build_all.sh <Half-Life dir> <CS2 dir>` runs all of it (with map renders for the loading screens).
Copy `out/addon` (without `_gen`) into the addon's content folder and `out/game` into
`game/csgo_addons/mg_cs16`, open `maps/mg_cs16.vmap` in Hammer and build. Re-running the converter
on its own output replaces only what it made (vis group `cs16_gen`).

| File | What it does |
|---|---|
| `tools/convert_map.py` | 1.6 BSPs → one `.vmap`: geometry, textures, skies (moondomes), clips, doors, ladders, breakables, decals, lights, spawns (32 per team), buy zones, bomb sites, vis hints, script entities; `_gen/maps.json` for the script |
| `tools/goldsrc/` | BSP / WAD readers, texture conversion, clip-hull recovery (`cliphull.c`), vis (`vishints.py`: sky faces hidden inside sky brushes left out, Low hints only where there's air or something drawn) |
| `tools/hud.py` | the 1.6 HUD and menus for Panorama from the 1.6 sprites, VGUI pictures and `cstrike_english.txt` |
| `tools/sounds.py` | 1.6 wavs for CS2, the radio events, CS2 weapon events re-pointed at 1.6 sounds |
| `tools/models.py`, `tools/goldsrc/mdl.py` | the 1.6 player models (.mdl) and the 1.6 view-model hands moved onto CS2's player skeleton, with their textures; needs one CS2 agent decompiled to ModelDoc with Source 2 Viewer (`.vmdl` + `_thirdperson_body.dmx`, first-person arms, sleeves, tools preview), whose skeleton, hit boxes, ragdoll, first-person arms and animation graph are reused |
| `tools/loading.py` | radar overview of the three maps, loading screens, map icon |
| `tools/build.mjs` | joins `src/` into the map script |
| `src/core/` | 1.6 rules as plain functions (damage, armour, money, buying, map split, round results) |
| `src/cs2/` | the CS2 side: settings (`00_config.js`), HUD, menus, buying, damage, sound, rounds, events |
| `test/` | rule checks against 1.6 numbers; a 64-player mock of CS2's script API |
| `preview/` | top-down and 3D check renders of the converted maps, a HUD preview |

Settings are at the top of `src/cs2/00_config.js` (round time, map split, which 1.6 rules apply, HUD, sounds).

## Credits

- de_dust2 by David Johnston (DaveJ), de_train by Chris Auty, de_nuke by Jo Bieg. Counter-Strike by Valve.
- 1.6 rule numbers checked against [ReGameDLL_CS](https://github.com/s1lentq/ReGameDLL_CS).
- Workflow and CS2 findings from skink52's cs2portdocs, hellmatch-cs2, space-racer-cs2 and cs2-fighter.

## Licence

Free for non-commercial use: copy, change, share and run it, including on game servers (donation/VIP servers are fine). Not to be sold, paywalled or built into a paid product or service. Code: [PolyForm Noncommercial 1.0.0](LICENSE). Art, models, sounds and maps: [CC BY-NC 4.0](LICENSE-CC-BY-NC-4.0.txt). See [LICENSE](LICENSE) for third-party parts that keep their own terms.

## Shared files

`test/types/point_script.d.ts`, `tools/dmx9.py`, `tools/vpk.py` are master copies from [cs2mapping](https://github.com/skink52/cs2mapping) (`create/libsync.json`). Change them there and run `python3 create/libsync.py push`, or if a fix lands here first, `libsync.py pull` it into cs2mapping. `libsync.py check` shows drift.
