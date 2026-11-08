# Bump mine kit: setup instructions (for an AI agent or a person)

This guide adds working CS:GO-style bump mines to a CS2 map: a `cs_script` map script, a Panorama HUD card, the CS:GO bump mine
model, materials and sounds, and the map entities. Do the steps in order; each one says how to check it worked.

## How it works

1. A player presses a button (or walks into a trigger) that fires `bumpscript` → `RunScriptInput` → `bump_give`.
   The script gives them 3 charges and a `weapon_decoy`.
2. A thrown decoy is hidden and one of 8 pooled bump mine props (`bumpmine_1..8`) flies along with it, spinning.
3. At the first bounce the decoy is removed and the mine stays where it landed; `bumpmine_N_land` plays.
4. 0.3 s later the mine is armed. The first player within 36 units (thrower included) is launched 900 u/s away and 750 u/s up,
   `bumpmine_N_det` plays, and the mine goes back to the pool.
5. While they have charges left, the player gets the next decoy 0.6 s after each throw.
6. Mines expire after 60 s and at round start. The 9th mine reuses the oldest.
7. Mines only work while the game is on (`bump_on` … `bump_off`, or always with `ALWAYS_ON`) and only for players inside
   `ARENA`. Decoys anywhere else stay normal decoys.

The HUD card (`custom_hud_layout` named `bumphud`) shows "BUMP MINE READY - MOUSE1 THROW" while the player holds the decoy.
It shows once per round, for at most 5 s.

## Requirements

- CS2 with the **Counter-Strike 2 Workshop Tools** (Hammer, `resourcecompiler.exe`).
- The map's content addon: `...\Counter-Strike Global Offensive\content\csgo_addons\<addon>\` with the map in `maps\<map>.vmap`.
- **Python 3**, only if you use `install_bumpmine.py`. It needs no packages.
- **Close Hammer** before any script edits the `.vmap`. Hammer keeps the open map in memory and overwrites the file on its next save.

Below, `<CS2>` is the CS2 install folder (`...\steamapps\common\Counter-Strike Global Offensive`) and `<content>` is
`<CS2>\content\csgo_addons\<addon>`.

## Step 1: copy the files

Copy everything inside the kit's `content\` folder into `<content>\`, merging folders. **Keep the paths exactly as they are**,
because the model, materials and script refer to each other by path:

```
<content>\maps\scripts\bumpmine.js
<content>\models\weapons\w_eq_bumpmine_dropped.vmdl
<content>\models\weapons\w_eq_bumpmine_dropped_refs\...            (mesh, physics and animation .dmx)
<content>\materials\models\weapons\v_models\bump_mine\...          (2 .vmat + 7 .tga)
<content>\sounds\bumpmine\bumpmine_land_01.wav, bumpmine_detonate.wav
<content>\panorama\layout\custom_game\bumpmine_hud.xml
<content>\panorama\styles\custom_game\bumpmine_hud.css
```

If the addon already has a file at one of these paths, stop and ask the map's owner; another bump mine setup may already be there.

## Step 2: sound events

CS2 loads only an addon's `soundevents\soundevents_addon.vsndevts`.

- **If `<content>\soundevents\soundevents_addon.vsndevts` exists:** copy the three events from `soundevents_bumpmine.vsndevts`
  (`"bumpmine.base" = {...}`, `"bumpmine.land" = {...}`, `"bumpmine.detonate" = {...}`) into it, inside the outermost `{ }`, next to the
  other events. Leave the rest of the file alone.
- **If it doesn't exist:** copy `soundevents_bumpmine.vsndevts` to `<content>\soundevents\soundevents_addon.vsndevts`.

Check: the file has one `"bumpmine.land"` and one `"bumpmine.detonate"`, and its braces balance.

## Step 3: configure the script

Edit the CONFIG block at the top of `<content>\maps\scripts\bumpmine.js`:

| Setting | Default | Set it to |
|---|---|---|
| `ARENA` | `null` (whole map) | The bump mine area as a box: `{ min: { x, y, z }, max: { x, y, z } }` in Hammer units. Include some height above the floor so jumping players still count. Use a box whenever the map has other decoy uses. |
| `ALWAYS_ON` | `false` | `true` if mines should work from round start with no start button. |
| `CHARGES` | 3 | Mines per `bump_give`. |
| `LAUNCH_SPEED` / `LAUNCH_UP` | 900 / 750 | Launch strength, horizontal and up (units/s). |
| `ARM_DELAY`, `MINE_LIFE`, `TRIGGER_RADIUS` | 0.3 s, 60 s, 36 u | Arming time, lifetime, trigger size. |
| `HUD_SECONDS` | 5 | How long the HUD card shows (once per player per round). |

Don't change `POOL_PREFIX`, `POOL_SIZE` or `HUD_NAME` unless you rename the entities in step 4 to match.

## Step 4: add the entities

Pick **A** (script, no Hammer needed) or **B** (Hammer).

### A. `install_bumpmine.py` (Hammer closed)

```
python install_bumpmine.py "<content>\maps\<map>.vmap" --at X Y Z --give <give button name> --start <start button name> --stop <stop button name>
```

- `--at X Y Z` is where the pool lives: the script, HUD and 8 parked, invisible, non-solid mine props with their 16 sound entities.
  It **must be inside the playable world**: an open spot under or beside the arena, not out in the void or inside a solid brush.
  Keimusho parks them on the arena's lower floor.
- `--give NAME[:OUTPUT]` is a button or trigger that hands out mines. OUTPUT defaults to `OnPressed`; use `OnStartTouch` for a
  `trigger_multiple`. It can be repeated, and every entity with that name gets the output.
- `--start` / `--stop NAME[:OUTPUT[:DELAY]]` fire `bump_on` / `bump_off`. Leave out `--start` if you set `ALWAYS_ON = true`.
- `--strip` also adds `game_player_equip` `bumpmine_equip`, which strips all weapons and gives a decoy, fired by each give.
  Keimusho does this so players hold nothing but mines. Without it, players keep their weapons and the script only adds the decoy.
- `--dry-run` checks everything and writes nothing. `--remove` takes out everything the installer added.
- It writes a backup next to the map (`<map>.vmap.bak_bumpmine_<date>`), refuses to install twice and refuses unknown entity names.

To find the button and trigger names, open the map in Hammer, or ask the owner. The installer prints an error naming any entity it can't find.

### B. Hammer

1. Copy `prefab\bumpmine_prefab.vmap` into `<content>\maps\prefabs\`.
2. Open it in Hammer, select everything (Ctrl+A), copy, open your map and paste.
3. Move the whole group to a spot inside the playable world (see `--at` above). Keep the 8 props and 16 sound entities together;
   their exact place doesn't matter.
4. If you don't want weapons stripped, delete `bumpmine_equip`.
5. Wire your own buttons and triggers (Outputs tab):

| Entity | Output | Target | Input | Parameter | Delay |
|---|---|---|---|---|---|
| give button / trigger | `OnPressed` (button) or `OnStartTouch` (trigger) | `bumpscript` | `RunScriptInput` | `bump_give` | 0.05 |
| give button (only with `bumpmine_equip`) | same | `bumpmine_equip` | `TriggerForActivatedPlayer` | | 0 |
| start button | `OnPressed` | `bumpscript` | `RunScriptInput` | `bump_on` | 0 (keimusho: 3, after a countdown) |
| stop button | `OnPressed` | `bumpscript` | `RunScriptInput` | `bump_off` | 0 |

The activator of `bump_give` must be the player, which is the case for button presses and trigger touches.

If you place the entities by hand instead, these are the keys that matter. `prefab\bumpmine_entities.json` has the full key set of each.

| Entity | Class | Keys |
|---|---|---|
| `bumpscript` | `point_script` | `cs_script` = `maps/scripts/bumpmine.vjs` |
| `bumphud` | `custom_hud_layout` | `layout` = `panorama/layout/custom_game/bumpmine_hud.vxml`, `observable` = 1 |
| `bumpmine_1` … `bumpmine_8` | `prop_dynamic` | `model` = `models/weapons/w_eq_bumpmine_dropped.vmdl`, `solid` = 0 (not solid), `renderamt` = 0 (hidden until used), `disableshadows` = 1, `model_archetype` = "" (empty), `use_animgraph` = 1 |
| `bumpmine_N_land` (8) | `point_soundevent` | `soundName` = `bumpmine.land`, `sourceEntityName` = `bumpmine_N`, `startOnSpawn` = 0, `stopOnNew` = 1, `toLocalPlayer` = 0 |
| `bumpmine_N_det` (8) | `point_soundevent` | `soundName` = `bumpmine.detonate`, `sourceEntityName` = `bumpmine_N`, same flags |
| `bumpmine_equip` (optional) | `game_player_equip` | `spawnflags` = 3 (use only + strip all), `weapon0` = `weapon_decoy` |

Check: the map has exactly one `bumpscript`, one `bumphud`, `bumpmine_1`…`bumpmine_8` and 16 `point_soundevent`s named `bumpmine_N_land` / `bumpmine_N_det`.

## Step 5: compile

The model, script, HUD and sounds are compiled from source; nothing in the kit is precompiled.

- **Hammer:** open the map and build it normally (Build → Full). Hammer compiles the assets the map uses.
- **Command line, or if something is missing in game:** compile each asset explicitly. A command-line map build doesn't
  always compile Panorama files or materials Hammer never loaded.

```
set RC="<CS2>\game\bin\win64\resourcecompiler.exe"
%RC% -i "<content>\materials\models\weapons\v_models\bump_mine\*.vmat" -nop4
%RC% -i "<content>\models\weapons\w_eq_bumpmine_dropped.vmdl" -nop4
%RC% -i "<content>\sounds\bumpmine\*.wav" -nop4
%RC% -i "<content>\soundevents\soundevents_addon.vsndevts" -nop4
%RC% -i "<content>\maps\scripts\bumpmine.js" -nop4
%RC% -i "<content>\panorama\layout\custom_game\bumpmine_hud.xml" -nop4
%RC% -i "<content>\panorama\styles\custom_game\bumpmine_hud.css" -nop4
```

Then build the map. Don't run `resourcecompiler` from a folder that holds a `gameinfo.txt`, because it will treat that folder as the game.

Check: the build log has no errors for `w_eq_bumpmine_dropped`, `bump_mine_*`, `bumpmine.vjs` or `bumpmine_hud`. The game folder
(`<CS2>\game\csgo_addons\<addon>\`) has `models\weapons\w_eq_bumpmine_dropped.vmdl_c`, `maps\scripts\bumpmine.vjs_c` and
`panorama\layout\custom_game\bumpmine_hud.vxml_c`.

## Step 6: test in game

Load the map (`map <map>` with the addon mounted), then:

1. Console: `sv_cheats 1`, then `bump_debug` (prints every give, throw and landing). Run `bump_on` too if you have no start button.
2. Stand inside `ARENA` and press the give button. You should get a decoy and the HUD card "BUMP MINE READY - MOUSE1 THROW".
3. Throw it. A bump mine should fly instead of the decoy, stick where it lands and play the land sound.
4. Walk onto it. You should be launched with the detonate sound, and the next decoy arrives 0.6 s after each throw.
5. Throw a decoy outside `ARENA` (if set): it stays a normal decoy.
6. Start a new round: mines and HUD should clear, and everything should work again in the second round.

After changing the script or HUD, `disconnect` and load the map again; a reload alone may keep the old version.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Console: `[bumpmine] no bumpmine_1..8 props found` | The props are missing at runtime. Check they're named `bumpmine_1`…`8` and are inside the playable world. Also check the model compiled. **Don't add `prop_data` to the `.vmdl`**: the map compile deletes any `prop_dynamic` whose model has `prop_data`. The kit's `.vmdl` has it removed on purpose. |
| Mine invisible in flight but fine once landed | A prop moved every tick must have `model_archetype` empty. The script already uses `Move`, not `Teleport`, for the flying mine. |
| Nothing happens on give | The game isn't on (`bump_on` / `ALWAYS_ON`), the player is outside `ARENA`, or the output targets the wrong name. `bump_debug` shows which. |
| No sounds | The events aren't in `soundevents_addon.vsndevts`, or the `.wav`s didn't compile. Check `soundName` on the 16 `point_soundevent`s. |
| HUD card missing | The `custom_hud_layout` `layout` path is wrong, or the xml/css didn't compile (compile them explicitly, step 5). |
| Model shows as an error model | The materials didn't compile, or the folder isn't exactly `materials\models\weapons\v_models\bump_mine\`. |
| Mines vanish after round 1 | Map entities are re-created every round. The script already re-finds the pool; if you renamed entities, keep `POOL_PREFIX` in step. |

## Notes

- The flying mine is a `prop_dynamic` the script moves with `Move`. A prop `Teleport`ed every tick isn't drawn in CS2.
- The `.vmdl`'s bodygroups `studio` and `glow` (`on` / `off`) are named. The CS:GO import left them unnamed and they wouldn't compile.
- `reference\keimusho_bumpmine.js` is the original map's script. The kit's `bumpmine.js` adds `ARENA = null` and `ALWAYS_ON`, and drops the
  HUD charge count (the original's count label was never filled in).
