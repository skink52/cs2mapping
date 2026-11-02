# Nanite Temple (mg_nanite_temple): a CS2 roguelike

Up to 64 players in squads of up to eight fight through three randomised vaults of an ancient basalt temple threaded with
neon data conduits, buy up in a staging room with CS2's own buy menu, then every surviving squad is thrown into one arena for a
last-squad-standing showdown. CS2 gunplay and menus stay exactly as they are; everything else is new. Runs entirely inside the
map's own script (cs_script): no plugins.

> **AI-generated code.** Written by an AI (Claude) directed by skink52. Built and mock-tested offline; **NOT YET TESTED IN CS2**
> as of 3 Nov 2026. See [docs/TESTING.md](docs/TESTING.md).

## How it plays

- **Lobby.** Both teams spawn in the temple's entrance hall. Twelve seconds after the round starts (two or more players) the script sorts
  everyone into squads of about five (eight at 64 players) across both CS2 teams and teleports each squad into a vault.
- **Vaults (three floors).** Each vault is drawn from a pool of twelve rooms of nine kinds (colonnade, cross, grid, split, ring, shrine, garden,
  archive, ruin), so no two runs chain the same rooms. Kill the guardians (shard drones, sentinels, lancers, golems; the third floor adds a
  golem escort) and the amber exit plate opens: stand on it and the squad moves to its next vault. A vault that takes longer than 150 s
  seals and pushes the squad on. Dead squad members respawn beside their squad.
- **Staging.** After the third vault the squad waits in a neon buy room: nanites (CS2 money, earned per kill and per cleared vault) buy real
  CS2 weapons through the normal buy menu. When every squad is through (or the vault clock runs out) there are 35 s left to buy.
- **The breach.** Every surviving squad lands on a balcony of the central amphitheatre. No respawns. Holographic barriers close in every
  45 s. Last squad standing wins; the CS2 round goes to the side most of its members are on.

## Classes (chat `!vector`, `!warden`, `!echo`, or press E at a lobby kiosk; `!class` shows yours)

| Class | Active | Passive |
|---|---|---|
| Vector | crouch + E: dash 256 units along the crosshair, striking anything the path crosses | a melee kill resets the dash |
| Warden | reload on an empty magazine: a 128-unit aegis for 6 s; hits on anyone inside from outside are cut 70 % | the warden's armor grows by a quarter of what the aegis stops |
| Echo | F (inspect): +40 % speed and a full magazine for 5 s | a lethal hit while it runs is held off: Echo rewinds to where it began, on 50 hp |

## Build

```
sh tools/build_all.sh          # out/addon + out/game, type check, mock run
sh tools/deploy.sh             # into content\csgo_addons\mg_nanite_temple and game\csgo_addons\mg_nanite_temple (Hammer closed)
```
Then compile the map (Hammer, or `C:\source1\cs2port\build_maps.ps1 mg_nanite_temple` run with `C:\source1\cs2port` as the working directory; the
first full compile took 2.5 min, 326 assets, 6 MB vpk). The script compiles with the map; after a
script-only change compile `maps/scripts/nanite.js` with `resourcecompiler -f -i`, `disconnect` and load the map again.

Layout: [tools/layout.py](tools/layout.py) (rooms, staging, arena; also baked into the script as `LAYOUT`), map writer [tools/vmap.py](tools/vmap.py),
set dressing [tools/dress.py](tools/dress.py), game rules [src/core](src/core) (pure JS, simulated in Node), CS2 adapter [src/cs2](src/cs2).
Design and decisions: [docs/DESIGN.md](docs/DESIGN.md).

## Settings

`CONFIG` at the top of the script: `APPLY_CVARS` (set false on servers that keep their own config), squad sizes, floor/staging/showdown
times, wave sizes, nanite rewards, class numbers. Cvars the script sets: `mp_ignore_round_win_conditions 1`, `mp_teammates_are_enemies 1`,
`mp_friendlyfire 1` (the script gates all player damage by squad), `mp_respawn_on_death_t/ct` (1 in the vaults, 0 at the breach),
`mp_buytime 36000`, `mp_buy_anywhere 0` (buying only in the staging rooms), money cvars, `bot_quota 0`.

## Credits

Stock Counter-Strike 2 models and materials (Valve), referenced from the game files, not shipped. CS:GO decals (Valve) carried over from the
ba_jail_lightsout import as static overlays. Code and tools: skink52 with Claude. Licence: [LICENSE](LICENSE). Not affiliated with or
endorsed by Valve.
