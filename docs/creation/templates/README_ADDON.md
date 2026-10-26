# <Game> for CS2: setup

<One paragraph: what the game is, players, modes. "Runs entirely inside the map's own script: no plugins.">

## 1. Install

Copy the folders into `content\csgo_addons\<addon>\` (map, scripts, models, materials, panorama, sounds, soundevents) and
`game\csgo_addons\<addon>\` (resource/overviews, maps/<map>.txt). Close Hammer first and back up `maps\<map>.vmap`.

## 2. Build the map

1. Open `maps/<map>.vmap` in Hammer. Check the `point_script` (`cs_script`) and `custom_hud_layout` (`layout`) fields aren't red.
2. Build (or `run_build.bat` with `<addon>` in `build_queue.txt`).
3. The asset pre-pass skips these, so compile them directly:
   `game\bin\win64\resourcecompiler.exe -f -i content\csgo_addons\<addon>\<file>` for `maps/scripts/<name>.js` (or `scripts/<name>.js`),
   `panorama/layout/custom_game/<name>.xml`, `panorama/styles/custom_game/<name>.css`, and any model only the script uses.
4. `map <map>`. The console must print `[<tag>] v<x.y.z> ready: …` with nothing `MISSING`.

## 3. How it plays

<Rounds, modes, scoring, what bots do.>

## Controls

<Keys, spectator keys, chat commands (! or /).>

## Settings

<The script's CONFIG keys a mapper or server may change: APPLY_CVARS, round length, music volume...>

## Servers with plugins

<Cvars the map sets; plugin types that break it; measured script time and the console line that reports it.>

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Console prints an old version | Old compiled script/HUD: recompile the `.js`, `.xml`, `.css` (step 3), `disconnect`, load again |
| Pink checkerboard | That model or material didn't compile |
| No HUD | `custom_hud_layout` must point at `panorama/layout/custom_game/<name>.vxml`; a layout that fails to compile is ignored |
| Silent sounds | Events missing from `soundevents_addon.vsndevts`, or a `point_soundevent` missing |
| Script not running | `point_script` must use `maps/scripts/<name>.vjs`; look for a JavaScript error line |

## Credits

See `CREDITS.md`.
