# Nanite Temple: in-game test checklist (first build, 3 Nov 2026)

Only report what fails. Load with `map mg_nanite_temple` (bots off; `bot_add` later to fill squads: bots are players here). Solo works: one player is
one squad, the showdown runs down its clock. Chat `!skip` kills every guardian in the room you stand in (CONFIG.DEV_COMMANDS; off for release).

1. **Console on load** prints `[nanite] v0.1.0 ready: 12 vaults, 8 staging rooms, 8 balconies, pool 160` with nothing `MISSING`.
   Then once a minute `[nanite] script time: avg X ms, max Y ms per server tick`. Note X and Y with your player count.
2. **Lobby.** Spawn in the entrance hall: fountain, banners, kiosks, graffiti, puddles, ivy, candles visible; no pink checkerboards;
   no black props (probe volume) and the weapon is lit.
3. **Run start.** With 2+ players, 12 s after the round starts: chat line `THE TEMPLE OPENS...` and a teleport into a vault.
   Nobody stuck in another player or a wall at the landing (ring spread).
4. **Enemies.** Guardians spawn over a second or two (drones = floating heads, sentinels = seated statues, lancers = holo panels,
   golems = ruined towers). They move, bob and turn to face you. **Shooting them hurts them** (flash white, die with a burst of shards,
   chat money `+`); this is the biggest unknown: it relies on the eye-to-impact line crossing their body. Knife works too.
   They hurt you (drones lunge, sentinels flash magenta then fire, lancers throw amber bolts you can dodge, golems slam through armor).
5. **Room clear.** Last guardian down: chat `vault cleared`, the amber plate is the exit; stand on it ~1.2 s and the squad moves.
   Three vaults, then the staging room (buy menu opens: B), then the breach into the arena after 35 s.
6. **Classes.** `!vector`: crouch + E dashes along the crosshair (cyan shards along the path). `!warden`: empty the mag, press R: a golden
   wire sphere (the aegis) around you; shots from outside do less. `!echo`: F: faster for 5 s, mag refilled, magenta vignette; take lethal damage
   during it and you rewind to where it began on 50 hp. The lobby kiosks (E) pick classes too: east Vector, west Warden, north Echo.
7. **Showdown.** Land on a balcony; squads can hurt each other, same-squad hits do nothing; `THE BARRIERS CLOSE IN` every 45 s and
   standing far from the centre hurts. Last squad: `SQUAD N WINS`, the CS2 round ends 6 s later for the right side.
8. **Performance.** Note FPS in a vault (12 rooms x ~180 props) and in the arena; any hitch when a wave spawns.

Known gaps in this build: no sounds or music, no loading screens or radar, no Tripo boss model yet.
