# CS2 bump mine kit

CS:GO-style bump mines for any CS2 map. CS2 has no `weapon_bumpmine`, so a map script rebuilds it.

- A button or trigger gives the player 3 bump mines. They show in the hand as decoy grenades.
- A thrown mine sticks where it first lands, using CS:GO's bump mine model with its glow and land sound.
- 0.3 s after landing it's armed. The first player to step on it, the thrower included, is launched away with CS:GO's detonate sound.
- A small HUD card reads "BUMP MINE READY - MOUSE1 THROW".

This setup comes from **ba_jail_keimusho** (skink52's CS2 port), where the bump mine game has been played and works in CS2.

**Setting it up:** give your AI agent (Claude Code, Codex, ...) this whole folder and say:

> Read AGENT_SETUP.md and add the bump mines to my map `<map name>` in content addon `<addon name>`. The arena is `<where>`; the
> buttons are `<names>`.

Or follow [AGENT_SETUP.md](AGENT_SETUP.md) yourself. It's written as a step-by-step guide and works by hand too.

## What's inside

| Path | What |
|---|---|
| `AGENT_SETUP.md` | Full setup: copy, configure, add entities, compile, test, troubleshoot. |
| `content/` | Copy into `content/csgo_addons/<your addon>/`. It holds the script, HUD, bump mine model (source), materials and sounds. |
| `soundevents_bumpmine.vsndevts` | The two sound events, to merge into your `soundevents_addon.vsndevts`. |
| `prefab/bumpmine_prefab.vmap` | The 27 entities ready to paste in Hammer. `bumpmine_entities.json` lists every key of every entity. |
| `install_bumpmine.py` + `lib/` | Optional: adds the entities and wiring to a `.vmap` without Hammer (Python 3, nothing else). |
| `reference/keimusho_bumpmine.js` | The original map's script, for comparison only. Don't install it. |

## Credits and licence

- The script, HUD, installer and docs are by skink52 ([cs2mapping](https://github.com/skink52/cs2mapping)). The code is AI-generated (Claude). The bump mine mechanics were tested in game on ba_jail_keimusho. The kit's additions (`ARENA = null`, `ALWAYS_ON` and the installer) were checked only off-game, with a type check, a simulated server and a test install.
- Free to use in your own maps, including Workshop uploads; credit appreciated. Not for sale.
- The bump mine model, textures and sounds are Valve's, from CS:GO, converted for CS2. Use them under Valve's terms for CS2 Workshop content.
