# cs2mapTTT: Trouble in Terrorist Town for any CS2 map

> **AI-generated code.** Written by Claude (Anthropic) for skink52. Free for non-commercial use (see Licence). Tested on a mock engine only until the TESTING notes say otherwise.

One cs_script (`ttt.js`) plus an optional HUD. No server plugins. Works on any map once the map has a `point_script` pointing at it.

## Install (per map)

1. Copy `addon/` into `content\csgo_addons\<your addon>\` (merges into `maps\scripts\` and `panorama\`).
2. Add to the map (Hammer, anywhere):
   - `point_script`: targetname `ttt_script`, cs_script `maps/scripts/ttt.vjs`
   - `custom_hud_layout`: targetname `ttt_hud`, layout `panorama/layout/custom_game/ttt_hud.vxml` (optional but strongly recommended: roles, shop, messages)
   - `point_template` `ttt_body_tpl` → `prop_ragdoll` `ttt_body_src` (CT body, `agents/models/ctm_sas/ctm_sas.vmdl`) and `ttt_body_tpl_t` → `ttt_body_src_t` (T body, `agents/models/tm_phoenix/tm_phoenix.vmdl`) (optional: carryable server-side bodies; keys in `tools/ttt_patch.json`). Not `characters/models/…`: those are one-bone placeholders and show as a box.
   - or run `python3 patch_vmap.py <map.vmap> <out.vmap> "" tools/ttt_patch.json` from [cs2mapping/create](https://github.com/skink52/cs2mapping/tree/main/create) (re-runnable).
   - HUD backgrounds (optional): `python3 tools/hud_theme.py <banner.png>` cuts kf/sb/top/shop.png from a server banner into `addon/panorama/images/custom_game/ttt/` (git-ignored; flat colours without them).
3. Build the map. HUD: the cs2port `run_build.bat` compiles the xml and css; otherwise `resourcecompiler -f -i` them.

A map's `info_map_parameters` is used to end rounds if present; otherwise the round clock is used.

### Maps made for TTT (ttt_* entities)

`python3 tools/ttt_convert.py <in.vmap> <out.vmap> <map name> --cs2mapping ../cs2mapping` turns the GMod/CS:GO TTT entities CS2 doesn't have into
relays driven by `ttt.js`, re-aims every input at them, adds the TTT entities (and an `info_map_parameters` if missing), and writes `maps/<map>.json`.
Then `python3 tools/build_data.py` bakes all `maps/*.json` into `ttt.js` (one script for every map; it picks its entry by map name).

| Entity | In CS2 |
|---|---|
| `ttt_traitor_button` | Traitors aim at it and press E (hint on the HUD); fires `<id>__pressed`. RemoveOnPress, wait, usable_range, Lock/Unlock/Kill kept. |
| `ttt_traitor_check` | Box from its brush; CheckForTraitor fires `<id>__found` with the activator (the traitor count isn't passed on). |
| `ttt_logic_role` | TestActivator → `<id>__pass` / `<id>__fail` (Role 0 innocent, 1 traitor, 2 detective, 3 any). |
| `ttt_game_text` | Display → HUD message to activator / all / detectives / traitors / innocents. |
| `ttt_map_settings` | RoundPreparation / RoundStart / RoundEnd → `ttt_ms__prep` / `__start` / `__end`. |
| `ttt_damageowner` | Kills by its trigger_hurt credit the presser (DNA, body info shows the trap name). |
| `ttt_credit_adjust`, `ttt_win` | Credits taken from the activator (`__ok` / `__fail`); TraitorWin / InnocentWin end the round. |
| `weapon_ttt_*`, `weapon_zm_*` | Nearest CS2 weapon. |

`GIVE_PRIMARY: "auto"` skips the free primary when the map has its own weapons lying around (`MAP_WEAPONS_ENOUGH`).

## Gameplay

| | |
|---|---|
| Prep (25 s) | Players can't hurt each other (the world still can), dead respawn, a random primary when the map has few weapons. |
| Roles | 25% traitors (min 1), detectives from 8 players (1 per 8). Detectives are public (blue tint, Zeus). |
| Win | All traitors dead → innocents. All others dead → traitors. Clock out → innocents. |
| Clock | Haste: 3:30 + 20 s per innocent death, capped at 6:00. |
| Bodies | Tap E on a body: everyone learns name + role (Shift+E: covert, only you see it and it isn't confirmed; hold E carries the body without identifying it). Detective: weapon, time, and a 45 s DNA trail to the killer. With the body templates every death leaves a server-side ragdoll (T or CT agent by the victim's team; the client ragdoll is shrunk away). |
| Shop | Traitor/detective: hold F. W/S select, E buy, F/jump close. Credits from deaths. |
| CS2 HUD | Kept (`HIDE_NATIVE_HUD` off): normal weapon switching and chat. The TTT panel sits over the killfeed, and every death reads as a world death. `HIDE_NATIVE_HUD: true` hides CS2's HUD while alive in a live round (tap F = next weapon, Ctrl+F = chat for 15 s, chat mirrored on the TTT HUD). |
| Scoreboard | Tab shows the TTT scoreboard drawn over CS2's (`SCOREBOARD`): Terrorists / Missing in action / Confirmed dead / Spectators, karma. Living players see the dead as alive until the body is found; traitors see traitors in red, detectives show blue to all; the dead see everything. `COVER_TOPBAR` covers CS2's top bar (alive avatars, clock) with the TTT clock. The TTT panel over the killfeed is opaque. |
| Karma | Like GMod: hurting (0.5 per HP) or killing (60) your own side costs karma; innocents/detectives gain 15 for killing a traitor; each round +5, +30 more for a clean round; max 1000. Low karma scales your damage down (min 40%). Changes made during a round apply at the next round start (scoreboard, HUD and damage), so they don't reveal who you hit. Karma lasts for the map (a map script can't keep data across maps) and survives reconnects by player name. |
| Killers hidden | During the round every lethal player hit becomes a world kill: nobody is credited, and the TTT panel covers the feed anyway. Score changes (±1 per kill, +1 for surviving winners) are held back and added at round end, so the scoreboard leaks nothing. |
| Carry | Hold E on a physics prop or a body to pick it up; E drops, R throws. Can't stand on what you hold. |
| Chat | `!ttt` shows controls, `!rules` the rules (`RULES` in `ttt.js`). |

Tunables: the `CONFIG` block at the top of `ttt.js` (times, ratios, shop items, `APPLY_CVARS` off to keep a server's own config).

## Limits (CS2)

- A map can't stop CS2 sending kill notices; the TTT panel covers the feed instead (verified). On a CounterStrikeSharp server a tiny plugin removes them: a `HookMode.Pre` `EventPlayerDeath` handler setting
  `info.DontBroadcast = true` stops clients getting the death event (no killfeed); the server still sees it, and the scoreboard comes from networked
  player stats, so it keeps updating (expected, unverified in CS2). With that plugin, set `HIDE_KILLER: false` so kills credit the real killer.
- `HIDE_NATIVE_HUD` (off by default): the pawn input `SetHUDVisibility false` hides CS2's whole HUD (killfeed included); the TTT HUD draws health, armor, ammo and a crosshair. It also turns off CS2's weapon switching (number keys / wheel, found in game), so `F_CYCLE` makes a tap of F switch weapons from the script (`SwitchToWeapon`).
- Without the plugin: `HUD_IN_KILLFEED` (on) puts the HUD panel over the top-right killfeed area (verified 30 Oct: the opaque panel hides the feed completely; set false for the left-side layout). `TRY_HIDE_KILLFEED` sends the client cvar `cl_drawhud_force_deathnotices -1` (unreliable, may persist on the client), off by default.
- Server crash (29 Oct, from the minidump): `SetModel` on a freshly spawned `prop_ragdoll`, then `Teleport`, crashed in the ragdoll's Teleport (empty bone list). The template model was the one-bone placeholder `characters/models/ctm_sas`. Bodies now use the real agents and are never `SetModel`'d; `CARRY_BODIES` is on again (velocity only); `BODY_SET_MODEL` stays off.
- Without the body template, ragdolls are client-side: bodies are found by looking at where the player died and can't be moved.
- A client with `cl_draw_only_deathnotices 1` sees the killfeed instead of the TTT HUD: killers stay hidden (world deaths), but victims' names show. Only a server plugin (`DontBroadcast`, above) removes that.
- The Esc menu shows CS2's scoreboard (dead players marked); the custom HUD isn't drawn over menus.
- Chat from dead players carries CS2's `*DEAD*` tag (set by the engine). `sv_deadtalk 0` with `sv_alltalk 0` should keep dead text from the living (unverified in CS2).
- Bots shoot everyone (`mp_teammates_are_enemies 1`); use `bot_quota 0`.
- Dead/alive voice: `sv_deadtalk 0`, `sv_talk_enemy_dead 0` (set by `APPLY_CVARS`; unverified in CS2).
- Plugins that force teams, respawn, spawn protection or TK punishment break it.

## Test

`sh test/run_mock.sh <path to cs2mapping clone>`: type-check plus mock-engine scenarios (churn, silent slot changes, warmup, 64 players).

## Licence

Free for non-commercial use: copy, change, share and run it, including on game servers (donation/VIP servers are fine). Not to be sold, paywalled or built into a paid product or service. Code: [PolyForm Noncommercial 1.0.0](LICENSE). Art, models, sounds and maps: [CC BY-NC 4.0](LICENSE-CC-BY-NC-4.0.txt).
