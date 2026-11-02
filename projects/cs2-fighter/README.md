# Puppet Brawl for CS2 (mg_cs2_fighter)

A 2.5D street fighter that runs entirely inside one Counter-Strike 2 map as a cs_script, with no server plugins.
Fighters are CS2 agent models driven by an invisible animation rig, fighting on a neon night-market stage that
everyone else in the map can watch. Duel (winner stays on) and 2v2 tag team, CPU opponents, combos, specials,
throws, perfect blocks and a custom Panorama HUD.

> **About the code:** the code in this repository (the game, the generators and the build tools) was written by an
> AI coding agent (Claude, by Anthropic). skink52 directed the project, tested it in CS2, did the Hammer work and
> publishes the map, but is not the author of the code. Please keep that in mind when reading or reusing it.

Everything here is original work: the name, fighters, moves, stage art and rules. The genre conventions it uses
(health bars, rounds, specials, combos) belong to nobody.

## Layout

| Folder | What it is |
|---|---|
| `src/` | The game. `core_*.js` is plain JavaScript with no engine calls (fighters, moves, rounds, CPU), so it runs in Node for tests and in the browser preview. `cs2_*.js` is the CS2 side: players, camera, rig props, HUD, sounds. |
| `tools/` | Generators: animation clips for the rig (`anim_export.mjs`), props and materials, the HUD, the map, and a lossless reader/writer for Hammer's binary .vmap (`dmx9.py`). |
| `test/` | Mechanics tests, a mock of CS2's script API that runs the real built script, balance runs and preview renderers. |
| `assets/` | The addon README and the sound event list. |
| `ref/` | The map as last delivered (built onto Hammer saves). |
| `preview/` | Rendered previews. |

## Building

```
node tools/build.mjs                      # dist/addon/scripts/puppet_brawl.js and the test module
node tools/anim_export.mjs                # rig model + animation clips into dist/addon
python3 tools/make_props.py dist/addon    # props, materials, effect models
python3 tools/make_hud.py dist/addon      # Panorama layout + styles
node test/mechanics.mjs && node test/sim_cs2.mjs
```

The addon folder on the PC is `content/csgo_addons/mg_cs2_fighter`. Only changed files are copied there.

## Licence

Free for non-commercial use: copy, change, share and run it, including on game servers (donation/VIP servers are fine). Not to be sold, paywalled or built into a paid product or service. Code: [PolyForm Noncommercial 1.0.0](LICENSE). Art, models, sounds and maps: [CC BY-NC 4.0](LICENSE-CC-BY-NC-4.0.txt). `tools/vendor/datamodel.py` stays MIT.

## Shared files

`test/tscheck/point_script.d.ts`, `tools/dmx9.py` are master copies from [cs2mapping](https://github.com/skink52/cs2mapping) (`create/libsync.json`). Change them there and run `python3 create/libsync.py push`, or if a fix lands here first, `libsync.py pull` it into cs2mapping. `libsync.py check` shows drift.
