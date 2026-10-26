# <Game>: possible server / plugin interactions

Come back to this once a server runs the map. Each item: what could go wrong, how it shows up, the likely workaround.
(From Hellmatch's list; delete what doesn't apply.)

## Round flow
1. **Plugins that end rounds or reset round cvars.** The script needs `mp_ignore_round_win_conditions 1` and ends rounds with `FireWinCondition`.
   Symptom: rounds end early or never. Fix: plugin config, or the script re-applies its cvars ~1 s after round start.
2. **Warmup / round-time / freeze-time configs.** The script reads remaining time rather than assuming; warmup ends nothing.
3. **Map votes / RTV** changing map mid-round cut the game.

## Respawn and death
4. **No-respawn plugins** break respawn modes (player stays dead). Fix: exception for this map.
5. **Spawn protection / immunity** (`mp_respawn_immunitytime`, godmode on spawn) blocks the scripted kill → no credit, player stuck. Fix: immunity 0.
6. **Death-event plugins** (rewards, damage reports) see every scripted kill as a real `player_death` with a large hit.
7. **Admin slay / respawn / teleport** on a parked player: the script re-parks on `OnPlayerReset`.

## Kill credit and ranks
8. **Rank plugins** may ignore world-weapon kills, count FFA kills as teamkills unless `mp_teammates_are_enemies 1`, or need a minimum player count.
9. **Teamkill punishment** (`mp_autokick`, `mp_tkpunish`, slay-on-TK).
10. **Damage plugins** hooking OnTakeDamage may block the scripted hit. Symptom: kill in the game, none in CS2; the script logs "a scripted CS2 kill was blocked".

## Pawn handling (pawns frozen in a booth)
11. **AFK managers (high risk):** position-based AFK flags every frozen pawn. The map's own AFK check uses input.
12. **Anti-stuck / noblock / anti-camp** plugins that move or unfreeze pawns.
13. **Third-person / FOV plugins** fight the custom camera.
14. **Team balancers** moving players mid-round.

## HUD and input
15. **Loadout givers / knife plugins** put weapons on parked pawns (viewmodel over the game). Fix: disable on this map.
16. **Center-text / advert plugins** draw over the custom HUD.
17. **Chat command clashes** (!spec, !afk, !stats).

## Performance
18. **Server load** (<measured, and where: mock or CS2>). The console prints `[<tag>] script time: avg X ms, max Y ms per server tick` once a minute; under ~5 ms is comfortable.
19. **Plugins iterating all entities** every tick get slower with the map's pools.

## Things to check together on first server launch
- [ ] A game kill appears in the CS2 killfeed with the right killer and victim
- [ ] A rank plugin records it (FFA and team rounds)
- [ ] Respawn after a kill works within ~2 s in respawn modes
- [ ] The AFK plugin leaves parked players alone
- [ ] Rounds end when the game says so, and at the time limit
- [ ] No weapons/viewmodels on parked pawns after a plugin's round-start loadout
