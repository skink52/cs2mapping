# mg_trenchwarfare: Workshop page and pre-upload checklist

AI-generated (Claude) for skink52. Remaster step 10 (12 Nov 2026). Shape from [docs/creation/workshop.md](../../../docs/creation/workshop.md).
Licence and IP detail: [WORKSHOP_COMPLIANCE.md](WORKSHOP_COMPLIANCE.md); the models and their sources: [ASSETS.md](ASSETS.md).

**State: not uploaded, and not uploadable yet.** The [checklist](#pre-upload-checklist) below has open licence items (three weapon
models, the Canon de 75's licence), and nothing of the remaster has been compiled or played yet ([TESTING.md](TESTING.md)).
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
- **Description:** below, about 7,400 of Steam's 8,000 characters. The credits still to fill in must fit. Shorten "Server requirements" first if they don't.
- **Change notes:** the first upload's notes are the "What's new in the remaster" list. Paste what was posted, exactly, under
  [Change notes as posted](#change-notes-as-posted).

## Pre-upload checklist

From [WORKSHOP_COMPLIANCE.md](WORKSHOP_COMPLIANCE.md) "Steps for a Workshop build". Tick each one and record what was decided, here or in that file.

- [ ] **Gewehr 98 (`weapon_awp`) must be replaced.** The current model is a rip from another game. Replacement: the CC BY "Gewehr 98 (ww1)"
      by janovich3D (or lawlordp / vburnashev) from Sketchfab. The download needs skink52's account. Steps are in [ASSETS.md](ASSETS.md) "Gewehr 98
      replacement plan" (GLB into `C:\source2\projects\trenchwarfare\Gewehr98\`, `tools/weapons/gewehr.json` to `glb`, re-fit against the
      stock AWP, rebuild). Then credit it.
- [ ] **Luger P08 (`weapon_glock`): CC BY-ND 4.0.** An adapted version may not be shared. Replace it with a CC BY Luger, or get FSkala's written
      permission and keep the note here.
- [ ] **Lee-Enfield SMLE (`weapon_ssg08`): author unknown.** Find the CGTrader page and author and record them. Check that its royalty-free licence
      allows shipping the model inside a free game addon; if it does not, replace the model.
- [ ] **Mondragón M1908 (`weapon_g3sg1`): source unverified.** Most likely DilanMendozaHer on Sketchfab, CC BY. Confirm the source and credit it, or replace the model.
- [ ] **Canon de 75 (`models/tw/ext/gm_canon75`): licence to confirm.** It came through GMod Workshop 3576805717 by soap, who credits the original
      Sketchfab modeller ("France M1897 75mm cannon"). Open the Sketchfab page and record the author, link and licence.
      - CC BY, CC BY-SA, CC0 or CC BY-NC: credit it.
      - ND or no licence: deploy the fallback. In `tools/tw_models.py`, set the `SWAPS` entry `gun_75mm` to `ext/gun_75mm`, then rerun
        `tools/patch_models.py` and the chain.
- [ ] **Credits filled in.** Update `out/step10/addon/CREDITS.txt` and the [CREDITS.txt](#creditstxt) copy below:
      - the Canon de 75 line;
      - the replacement Gewehr 98 and Luger;
      - the Lee-Enfield and Mondragón authors;
      - drop the "being sorted out" notes.
      In the description, replace the `<<FILL IN BEFORE UPLOAD ...>>` line with the same credits, then redeploy.
- [ ] **Template sounds.** Check the origin of `sounds/bird_01-06`, `interior_01` and `vent_01` (from the addon template). Delete them by hand if
      the map does not use them, and drop their CREDITS line.
- [ ] **Stray files in both addon roots.** Remove these by hand; the deploy tools never delete:
      - any `models/tw/ext/gm_*` and `materials/models/tw/ext/gm_*` other than `gm_canon75`;
      - the old weapon `_c` files once the weapons are replaced;
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

Models from Sketchfab under CC BY 4.0 (http://creativecommons.org/licenses/by/4.0/), converted for CS2: "Mortier de 58 mm type 2" by mrpolarbear; "A7V 'Wotan' tank" by IvanKoliada; "Renault FT 1917 game-ready model" by kraytay; "75mm Field Gun" by kisotsu; "Bl 8 Artillery Howitzer MkV" by Zanderart; "Army Stretcher" by 4mecharmi; "British WW1 Military Helmet (Broken and New)" by noodlepirate; "German Stahlhelm m16 (ww1)" by janovich3D; "German Field Telephone" by rayferric; "Burnt Stump" by dunathan; "Vintage petrol can" by jkillgore; "Spad S VII" and "Dr1" by manilov.ap; "Lewis Mk1" by MaX3Dd; Colt M1911 by Ole Gunnar Isager.

<<FILL IN BEFORE UPLOAD (docs/WORKSHOP.md checklist): the Canon de 75 credit (original Sketchfab author, licence, link; converted via Steam Workshop item 3576805717 by soap), the replacement Gewehr 98 and Luger credits, and the Lee-Enfield and Mondragon authors. Delete this line.>>

Foliage, ground materials, particles and weapon animations are Counter-Strike 2 stock assets (Valve). All other art, sound and code is original.

Licence: free for non-commercial use, including community servers (donation and VIP servers are fine) as long as the map itself is not sold or paywalled. Code: PolyForm Noncommercial 1.0.0. Art, sounds and map: CC BY-NC 4.0, "mg_trenchwarfare by skink52". Full credits: CREDITS.txt in the addon.

Not affiliated with or endorsed by Valve.
```

## CREDITS.txt

The same text as the staged `out/step10/addon/CREDITS.txt`. It keeps every line of the addon's earlier CREDITS.txt and adds the weapon
models, the Canon de 75 and the synthesised-sound note.

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
Changes: converted to CS2 models, re-scaled, rigged as weapons where listed, LOD meshes added to some.
Stock CS2 foliage, ground materials and sounds by Valve.
Stock CS2 textures re-used on the procedural props (boards, rust, mud, maple bark) by Valve.

Canon de 75 field gun (models/tw/ext/gm_canon75):
- "WW1 French Canon de 75mm 1897" from Steam Workshop item 3576805717 (Garry's Mod) by soap, who credits the original
  Sketchfab modeller ("France M1897 75mm cannon"). The original author and the exact Creative Commons licence are still
  being confirmed; this credit will be completed before a public release. Converted to a CS2 static prop with new LODs.

Other weapon models (licences being sorted out before a public release):
- Luger P08 (weapon_glock) by FSkala, Sketchfab, CC BY-ND 4.0.
- Lee-Enfield SMLE (weapon_ssg08) from a CGTrader royalty-free download; author to be recorded.
- Mondragon M1908 (weapon_g3sg1): most likely "Mondragon M1908" by DilanMendozaHer, Sketchfab, CC BY 4.0; to be confirmed.
- Gewehr 98 (weapon_awp): source not cleared; it will be replaced by a Creative Commons model before a public release.

Original to this addon: terrain, trenches, mine galleries and the procedural props; the four soldier player models (generated
with Tripo, rigged by this project's tools); HUD art, radar, plotting-board maps, loading slides and map icon; the game script.
Sounds: every file in sounds/tw/ (mortars, impacts, aircraft, whistles, rain on tin, the front's ambience) is synthesised by this
project's code from noise and tones, with no recorded samples. sounds/bird_01-06, interior_01 and vent_01 came with the addon
template the map was started from (believed to be Valve's; origin being checked). Other sounds are Counter-Strike 2 stock.

Licence: free for non-commercial use, including game servers (donation / VIP servers are fine) as long as the map itself is not
sold or paywalled. Code: PolyForm Noncommercial 1.0.0 (LICENSE). Art, models, sounds and maps made for this project:
CC BY-NC 4.0 (LICENSE-CC-BY-NC-4.0.txt), "mg_trenchwarfare by skink52". Third-party models above keep their own licences.
Source: https://github.com/skink52/cs2mapping (projects/trenchwarfare-cs2)

Not affiliated with or endorsed by Valve.
```

## Change notes as posted

Paste each update's notes here exactly as posted, newest first (template: [WORKSHOP_CHANGELOG.md](../../../docs/creation/templates/WORKSHOP_CHANGELOG.md)).

- Nothing posted yet.
