# mg_trenchwarfare: Workshop page and pre-upload checklist

AI-generated (Claude) for skink52. Remaster step 10 (12 Nov 2026). Shape from [docs/creation/workshop.md](../../../docs/creation/workshop.md).
Licence and IP detail: [WORKSHOP_COMPLIANCE.md](WORKSHOP_COMPLIANCE.md); the models and their sources: [ASSETS.md](ASSETS.md).

**State: not uploaded, and not uploadable yet.** Every licence question now has an answer (steps 11 and 12, 12 Nov 2026), but the
three replacement weapons and the replacement template sounds are staged, not deployed, and the remaster has not been played yet
([TESTING.md](TESTING.md)); the [checklist](#pre-upload-checklist) says what is left.
A private-server build is fine as it is.

## Files

| What | Repo copy (this file) | Staged copy (deployed by `tools/deploy_tw.py`, list `out/step10/deploy_files.txt`) | Lands in |
|---|---|---|---|
| Steam description (BBCode) | [Description](#description-bbcode) | `out/step10/addon/mg_trenchwarfare STEAM DESCRIPTION.txt` | content addon root, as `mg_trenchwarfare STEAM DESCRIPTION.txt` |
| Credits | [CREDITS.txt](#creditstxt) | `out/step10/addon/CREDITS.txt` | content and game addon roots |
| Licence files | `../LICENSE`, `../LICENSE-CC-BY-NC-4.0.txt` | the same files | content and game addon roots |

`out/` is not in git, so this file is the repo's copy of the description and the credits: change both copies together.
The Workshop item is the compiled **game** folder (`game\csgo_addons\mg_trenchwarfare`), so CREDITS and both licence files go there as well.
The description file in the content addon is skink52's per-map copy: if they have edited it there, keep theirs. Take its line out
of `out/step10/deploy_files.txt` instead of overwriting it.

## Page

- **Title:** `mg_trenchwarfare - WW1 Western Front`
- **Tags:** Map; game mode Custom. Pick from Steam's list at upload; no other game's name in any tag.
- **Visibility:** private or friends-only for the first upload, until TESTING.md sections A-T pass on the uploaded item.
- **Preview image:** 1024 x 1024 under 1 MB, of this addon only and taken after the weapon replacements. Use `python3 ../../create/loading.py workshop <in.png> <out.jpg>`.
  Before in-game captures exist, the loading slides (`panorama/images/map_icons/screenshots/1080p/mg_trenchwarfare*.png`) are the gallery, labelled as renders.
- **Description:** below, 7,436 of Steam's 8,000 characters with every credit filled in (step 12). Shorten "Server requirements" first if more is added.
- **Change notes:** the first upload's notes are the "What's new in the remaster" list. Paste what was posted, exactly, under
  [Change notes as posted](#change-notes-as-posted).

## Pre-upload checklist

From [WORKSHOP_COMPLIANCE.md](WORKSHOP_COMPLIANCE.md) "Steps for a Workshop build". Tick each one and record what was decided, here or in that file.

- [ ] **Gewehr 98 (`weapon_awp`) must be replaced.** The deployed model is a rip from another game. **Replacement built, test-compiled
      (0 failed) and credited (12 Nov 2026, step 11):** "Free Mauser Gewehr 98" by lawlordp, CC BY 4.0, via Objaverse
      ([ASSETS.md](ASSETS.md#weapon-replacements-step-11); janovich3D's was rejected: its author did not model it). Left: deploy
      `out/step11/deploy_files.txt`, force-compile the four vmdls it names, look at it in game. Tick when that is done.
- [ ] **Luger P08 (`weapon_glock`): CC BY-ND 4.0.** An adapted version may not be shared. **Replacement built, test-compiled (0 failed)
      and credited (step 11):** "Luger - Game ready asset" by Burdock, CC BY 4.0. Left: the same deploy and compile, and delete the old
      `luger_p08_bullet*` / `luger_p08_material*` materials (CC BY-ND content) from both addon roots, as the deploy list says. Tick then.
- [ ] **Lee-Enfield SMLE (`weapon_ssg08`) must be replaced.** The deployed mesh is TurboSquid 1907112 "Lee Enfield MK1 Low-poly PBR
      Free" (same date and the exact 10,337 faces), licensed for editorial use only, which rules out a game. **Replacement built,
      test-compiled (0 failed) and credited (12 Nov 2026, step 12):** "Lee Enfield MKIII" by Moony_State, CC BY 4.0, via Objaverse
      ([ASSETS.md](ASSETS.md#licence-replacements-step-12)). Left: deploy `out/step12/deploy_files.txt`, force-compile
      `lee_enfield.vmdl` and `lee_enfield_mag.vmdl`, look at it in game. Tick when that is done.
- [x] **Mondragón M1908 (`weapon_g3sg1`): source confirmed (step 12).** "Mondragón M1908" by DilanMendozaHer, Sketchfab
      2cfae8885fe747feaeb6068133f5fb38, CC BY 4.0: same 24,674 faces, 16 materials / 16 textures and the same parts layout as our
      Blockbench file. No model change; the credit is in CREDITS.txt and the description.
- [x] **Canon de 75 (`models/tw/ext/gm_canon75`): licence confirmed (step 12).** "France M1897 75mm Cannon(Custom modified)" by
      DopamineWarlock, Sketchfab eb6c4b6b18324e64992615e04b60d2ab (Objaverse 000-105), CC BY 4.0: the page soap's item links, and the
      shipped variant (24,552 faces = our LOD0). No swap; credited. (The fallback route, if ever needed: `tools/tw_models.py` `SWAPS`
      `gun_75mm` -> `ext/gun_75mm`, rerun `tools/patch_models.py` and the chain.)
- [ ] **Credits filled in.** Done in `out/step10/addon/CREDITS.txt`, the [CREDITS.txt](#creditstxt) copy below and the description
      (12 Nov 2026, step 12: every weapon, the Canon de 75, the sounds note; the `<<FILL IN ...>>` line is gone). Left: redeploy
      (step 10's list carries both files). Tick then.
- [ ] **Template sounds.** `sounds/bird_01-06`, `interior_01` and `vent_01` are Valve's CS2 addon template files (byte-identical;
      `interior_01` carries a commercial sound-library label), so their terms outside CS2 are unknown. The map never plays them, but the
      template's `ambient_example.*` events name them, so they compile into the addon. **Replaced by synthesised wavs of the same names**
      (`python tools/sounds.py --template-wavs out/step12/addon`, test-compiled 8 / 0 failed), staged in step 12. Left: deploy and
      force-compile `sounds/*.wav`. Tick then.
- [ ] **Stray files in both addon roots.** Remove these by hand; the deploy tools never delete:
      - any `models/tw/ext/gm_*` and `materials/models/tw/ext/gm_*` other than `gm_canon75`;
      - the old weapon `_c` files once the weapons are replaced (step 11 overwrites same-named files; the old Luger's
        `luger_p08_bullet*` / `luger_p08_material*` materials and any older `gewehr98_*` / `luger_p08_*` `.vtex_c` stay behind);
      - the unused tw1-tw35 HUD pictures and wavs listed in `out/step8/deploy_files.txt`.
- [ ] **CREDITS.txt, LICENSE and LICENSE-CC-BY-NC-4.0.txt** are in the game addon root (step 10's deploy list puts them there).
- [ ] **No other game's names, logos or screenshots** in the title, tags, description or images. Mention real equipment only
      (Gewehr 98, Lewis gun, SPAD VII, Fokker Dr.I).
- [ ] **TESTING.md** sections A-T passed, at least A (compile) and C-J (play). The status line in the description matches what was reached
      (the [docs/reference/compatibility.md](../../../docs/reference/compatibility.md) words: say "playtested" only after a real playtest).
- [ ] **After upload:** put the item id in the description (`host_workshop_map <id>`) and in [TESTING.md](TESTING.md) U1. Paste the posted change
      notes below.

## Description (BBCode)

The same text as the staged `mg_trenchwarfare STEAM DESCRIPTION.txt`; paste it into the Workshop page as it is.

```
[h1]mg_trenchwarfare - trench warfare on the Western Front[/h1]

Two trench lines across a shell-torn valley: German infantry on one side, British on the other, no man's land between them. Fight from the fire step, crew the mortars behind the lines, or fly from the aerodrome. Up to 64 players, with bots that fill a quiet server. Everything runs inside the map's own script: [b]no plugins needed[/b].

[i]Status: the remaster. Its rules were checked on a test harness and the map with automated checks; this version has not been through a public playtest yet. Please report anything odd (type !pos in chat and quote the line).[/i]

[h2]The front[/h2]
[list]
[*][b]Fire and support trenches[/b] for each side, with fire steps, dressing stations, shelters and duckboards
[*][b]No man's land[/b]: shell holes still smouldering, barbed wire, knocked-out tanks, mud and flooded craters
[*][b]Mortar pits[/b] behind each line: five crews per side
[*][b]Aerodromes[/b] on both flanks with five aircraft each: SPAD VII biplanes for the British, Fokker Dr.I triplanes for the Germans
[*][b]The wood[/b] to the north and the [b]mine galleries[/b] under the south end: both closed at the start, blown open during the round
[/list]

[h2]How a round goes[/h2]
You start in the briefing room with your orders, then move up to your post. After a death you are back in the briefing room for a moment, then deploy again. The way to the wood opens after 15 kills or 4 minutes, the mine galleries after 30 kills or 8 minutes, each with a blast and a headline. Rounds last 60 minutes.

[h2]Roles[/h2]
[b]Infantry[/b] ([b]!infantry[/b]) - Bolt-action rifle and pistol: Gewehr 98 and Luger for the Germans, Lee-Enfield and Colt M1911 for the British. Three kills without dying earn the Mondragon self-loader or the Lewis gun; [b]SHIFT+E[/b] or [b]!swap[/b] switches back to the rifle. Stand at a dressing station to heal.

[b]Mortar crews[/b] ([b]!mortar[/b]) - Crews of two. One plots at the map table: E to use the sight, WASD to move the marker over the printed trench map, MOUSE1 to lock, SPACE to fire. The other fetches a bomb from the ammunition box (E) and loads the tube. Shells take time to fall and spread with range; the loader shares the credit.

[b]Pilots[/b] ([b]!air[/b]) - Five aircraft per side. The mouse steers, W/S throttle, A/D roll, MOUSE1 fires the twin guns, MOUSE2 drops a bomb (two at a time, re-armed 18 s after use). Two lives per posting, then back to the trench. Rifles can bring you down.

[h2]Chat commands[/h2]
[code]!infantry  !rifle        infantry next deploy
!mortar  !artillery      a mortar crew next deploy (if a seat is free)
!air  !pilot             ask to be posted to the aerodrome
!random                  let the map choose your role
!roles                   the role card: your side's crews and aircraft
!swap  (or SHIFT+E)      streak weapon <-> rifle
!pos                     your position and radar square
!uniform                 period uniform on / off (applied in the briefing room)[/code]
A role command in the briefing room applies at once; in the field it waits for your next deploy.

[h2]Bots[/h2]
Bots fill the server to 16 players and leave as people join. They fight as infantry from the fire steps. When a side has fewer than four people, bots also fly one aircraft and crew two mortars for it, and hand the aircraft or the seat over to a player who asks for that role when they next deploy.

[h2]Server requirements[/h2]
[list]
[*]Map name [b]mg_trenchwarfare[/b], game type Custom. [code]host_workshop_map <id>[/code]
[*]The map sets its own cvars when it loads: respawn on death for both teams, no freeze time, 60-minute rounds, no buying, solid team-mates, no C4, [b]bot_quota_mode fill[/b] with [b]bot_quota 16[/b]. They are one list (CVARS) at the top of the script.
[*]The script holds pilots (shrunk, frozen, on a chase camera) while they fly and plotters frozen at the table. Plugins likely to conflict: AFK managers that judge by position, anti-stuck / noblock, third-person or FOV changers, loadout givers, no-respawn modes, spawn protection, team-kill punishment, and anything that blocks scripted damage.
[*]Rain is off by default; [b]ent_fire tw_rain FireUser1[/b] starts it, [b]FireUser2[/b] stops it.
[*]Server load: the console prints [b][tw] perf: ... ms/tick avg[/b] once a minute.
[/list]

[h2]What's new in the remaster[/h2]
[list]
[*]Mortars recoil when they fire; the wood and mine-gallery barricades stand until they are blown
[*]The ground: hundreds of fresh shell holes, tank tracks and lorry ruts, puddles and washed-out mud; smouldering craters in no man's land; optional rain
[*]A new HUD: canvas-and-brass cards, a wooden plotting board with a printed trench map, a walnut cockpit dash
[*]31 new sounds: mortar cough and falling whistle, heavy impacts, the rotary engine and the dive howl, the officer's whistle as you go over, rain on the shelter roofs, drumfire and distant guns along the front
[*]A French 75 field gun in the battery position, and smoother detail switching on the tanks, howitzer and aircraft
[*]Redrawn radar with a lettered grid, new loading screens and map icon
[*]Bots fill quiet servers, and fly and crew for a side that is short of people
[*]Fixed: an aircraft left hanging in the sky when its pilot left; deaths under a shot-down plane counted as team kills; role commands teleporting you out of a fight; AFK pilots and crews holding seats; the loader's assist lost to armour; the pistol firing at the map table; seats lost on a team switch
[/list]

[h2]How it was made[/h2]
The terrain, trenches, props, textures, HUD, radar, sounds (all synthesised) and the game script are generated by code. That code was written by an AI coding agent (Claude, by Anthropic) under skink52's direction. The soldier models were generated with Tripo and rigged by the project's tools.

Source: https://github.com/skink52/cs2mapping (projects/trenchwarfare-cs2)

[h2]Credits[/h2]
Map, script and original assets: skink52.

Models from Sketchfab under CC BY 4.0 (http://creativecommons.org/licenses/by/4.0/), converted for CS2: "Mortier de 58 mm type 2" by mrpolarbear; "A7V 'Wotan' tank" by IvanKoliada; "Renault FT 1917 game-ready model" by kraytay; "75mm Field Gun" by kisotsu; "Bl 8 Artillery Howitzer MkV" by Zanderart; "Army Stretcher" by 4mecharmi; "British WW1 Military Helmet (Broken and New)" by noodlepirate; "German Stahlhelm m16 (ww1)" by janovich3D; "German Field Telephone" by rayferric; "Burnt Stump" by dunathan; "Vintage petrol can" by jkillgore; "Spad S VII" and "Dr1" by manilov.ap; "Lewis Mk1" by MaX3Dd; Colt M1911 by Ole Gunnar Isager; "Free Mauser Gewehr 98" by lawlordp; "Luger - Game ready asset" by Burdock; "Lee Enfield MKIII" by Moony_State; "Mondragon M1908" by DilanMendozaHer; "France M1897 75mm Cannon(Custom modified)" by DopamineWarlock (the Canon de 75, reached through soap's Garry's Mod conversion, Steam Workshop item 3576805717).

Foliage, ground materials, particles and weapon animations are Counter-Strike 2 stock assets (Valve). All other art, sound and code is original.

Licence: free for non-commercial use, including community servers (donation and VIP servers are fine) as long as the map itself is not sold or paywalled. Code: PolyForm Noncommercial 1.0.0. Art, sounds and map: CC BY-NC 4.0, "mg_trenchwarfare by skink52". Full credits: CREDITS.txt in the addon.

Not affiliated with or endorsed by Valve.
```

## CREDITS.txt

The same text as the staged `out/step10/addon/CREDITS.txt`. It keeps every line of the addon's earlier CREDITS.txt and adds the weapon
models, the Canon de 75 and the synthesised-sound notes (step 12: every licence answered).

```
mg_trenchwarfare by skink52. Map generator, procedural props/textures, HUD and scripts were written by an AI (Claude).

Third-party models (Sketchfab, CC BY 4.0 - https://creativecommons.org/licenses/by/4.0/), converted for CS2:
- "Mortier de 58 mm type 2" by mrpolarbear
- "A7V 'Wotan' tank" by IvanKoliada
- "Renault FT 1917 game-ready model" by kraytay
- "75mm Field Gun" by kisotsu
- "Bl 8 Artillery Howitzer MkV" by Zanderart
- "Army Stretcher" by 4mecharmi
- "British WW1 Military Helmet (Broken and New)" by noodlepirate
- "German Stahlhelm m16 (ww1)" by janovich3D
- "German Field Telephone" by rayferric
- "Burnt Stump" by dunathan
- "Vintage petrol can" by jkillgore
- "Spad S VII" by manilov.ap
- "Dr1" by manilov.ap
- "Lewis Mk1" by MaX3Dd (weapon model, CT streak weapon on weapon_scar20)
- Colt M1911 by Ole Gunnar Isager (weapon model, CT pistol on weapon_hkp2000)
- "Free Mauser Gewehr 98" by lawlordp (shown as Milantique, now Foolish Me Studios),
  https://sketchfab.com/3d-models/free-mauser-gewehr-98-a4a6399f343143c883e090362bd6222d
  (weapon model, T rifle on weapon_awp; wood and steel re-coloured, bolt handle turned to the closed position, period scope added)
- "Luger - Game ready asset" by Burdock,
  https://sketchfab.com/3d-models/luger-game-ready-asset-365c3bfd19494dfea145fb4e5d15d0bc
  (weapon model, T pistol on weapon_glock; a magazine block added inside the grip for the reload)
- "Lee Enfield MKIII" by Moony_State (formerly Giuliano.Sgroi),
  https://sketchfab.com/3d-models/lee-enfield-mkiii-f6a2160daf134071a84e3cae5f831875
  (weapon model, CT rifle on weapon_ssg08; bayonet, sling and loose cartridge left out, textures reduced to 2048, period
  telescopic sight added)
- "Mondragon M1908" by DilanMendozaHer,
  https://sketchfab.com/3d-models/mondragon-m1908-2cfae8885fe747feaeb6068133f5fb38
  (weapon model, T streak weapon on weapon_g3sg1; drum magazines, spare magazine and cartridges left out, procedural wood
  and steel materials, period telescopic sight added)
- "France M1897 75mm Cannon(Custom modified)" by DopamineWarlock,
  https://sketchfab.com/3d-models/france-m1897-75mm-cannoncustom-modified-eb6c4b6b18324e64992615e04b60d2ab
  (the Canon de 75 field gun, models/tw/ext/gm_canon75; reached through soap's Garry's Mod conversion, Steam Workshop
  item 3576805717 "WW1 French Canon de 75mm 1897", which credits this model; converted to a CS2 static prop with new LODs)
Changes: converted to CS2 models, re-scaled, rigged as weapons where listed, LOD meshes added to some.
Stock CS2 foliage, ground materials and sounds by Valve.
Stock CS2 textures re-used on the procedural props (boards, rust, mud, maple bark) by Valve.

Original to this addon: terrain, trenches, mine galleries and the procedural props; the four soldier player models (generated
with Tripo, rigged by this project's tools); HUD art, radar, plotting-board maps, loading slides and map icon; the game script.
Sounds: every file in sounds/tw/ (mortars, impacts, aircraft, whistles, rain on tin, the front's ambience) is synthesised by this
project's code from noise and tones, with no recorded samples, and so are sounds/bird_01-06, interior_01 and vent_01 (stand-ins
for the CS2 addon template's files of the same names). Other sounds are Counter-Strike 2 stock.

Licence: free for non-commercial use, including game servers (donation / VIP servers are fine) as long as the map itself is not
sold or paywalled. Code: PolyForm Noncommercial 1.0.0 (LICENSE). Art, models, sounds and maps made for this project:
CC BY-NC 4.0 (LICENSE-CC-BY-NC-4.0.txt), "mg_trenchwarfare by skink52". Third-party models above keep their own licences.
Source: https://github.com/skink52/cs2mapping (projects/trenchwarfare-cs2)

Not affiliated with or endorsed by Valve.
```

## Change notes as posted

Paste each update's notes here exactly as posted, newest first (template: [WORKSHOP_CHANGELOG.md](../../../docs/creation/templates/WORKSHOP_CHANGELOG.md)).

- Nothing posted yet.
