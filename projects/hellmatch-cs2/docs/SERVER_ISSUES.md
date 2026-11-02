# FreeDM CS2: possible CounterStrikeSharp / server interactions

Come back to this once the server is running the map. Each item: what could go wrong, how it shows up,
and the likely workaround.

## Round flow
1. **Plugins that end rounds or reset round cvars.** The script needs mp_ignore_round_win_conditions 1
   while arenas run and ends the round itself with SetRoundRemainingTime. Minigame plugins often re-apply
   their own cvars on round start, which would overwrite the script's.
   Symptom: round ends early when pawns die, or never ends. Fix: plugin config, or the script re-applies cvars 1 s after round start.
2. **Round time / freeze time set by a plugin or game-mode config.** The script expects ~10 min and uses freeze time
   to build arenas. Fix: agree on values; the script reads remaining time rather than assuming.
3. **Warmup.** Doom rounds shouldn't start in warmup. Script checks IsWarmupPeriod. Warmup-handling plugins may differ.
4. **Map-vote / RTV / map-chooser plugins.** Fine, but a vote that changes map mid-round cuts all arenas.

## Respawn and death
5. **Respawn rules.** FFA/TDM need CS2 respawn (mp_respawn_on_death_t/ct 1). Plugins that enforce
   no-respawn (common on minigame servers) or their own respawn timing will break respawn modes.
   Symptom: player stays dead after a Doom frag. Fix: plugin exception for this map, or the plugin respawns instead.
6. **Spawn protection / immunity.** mp_respawn_immunitytime or a godmode-on-spawn plugin would block the
   scripted kill if a Doom death happens right after a CS2 respawn → no kill credit and the player
   is stuck. Fix: immunity 0 on this map.
7. **Death-event plugins** (rewards on kill, HP/money on kill, last-request triggers, "revenge" messages,
   damage reports printing "999 damage"). Every Doom frag is a real player_death with a 1000-damage hit.
   Fix: disable those features on this map.
8. **Admin slay / respawn / teleport commands** used on a Doom player. Script must re-park on OnPlayerReset;
   a slay counts as a CS2 death with no Doom credit.

## Kill credit and ranks
9. **Rank plugins** may: ignore kills with no weapon / world weapon icon; give odd weapon stats;
   count FFA same-team kills as teamkills unless mp_teammates_are_enemies is 1; ignore kills while a
   plugin thinks it's warmup; need a minimum player count. Check what a Doom frag shows in the rank log.
10. **Teamkill punishment** (mp_autokick, mp_tkpunish, slay-on-TK plugins, TK votes). FFA rounds depend on
    mp_teammates_are_enemies 1. If a plugin forces it to 0, FFA frags become teamkills.
11. **Damage plugins** (godmode, damage multipliers, friendly-fire handlers, "no team damage") hooking
    OnTakeDamage may block or change the scripted kill hit. Symptom: frag shows in Doom but no CS2 kill.
12. **Scoreboard / score plugins.** CS2 gives score per kill itself; the script won't AddScore in real-kill mode.
    Plugins that also give points on kills will double up (cosmetic).

## Pawn handling (pawns are frozen in a hidden booth while playing)
13. **AFK managers (high risk).** Every Doom player's pawn stands frozen, so position-based AFK plugins will
    flag everyone and move/kick them. Fix: disable AFK plugin on this map, or the map's own AFK check
    replaces it (it uses Doom input).
14. **Anti-stuck / noblock / anti-camp plugins** teleporting or unfreezing pawns (changing MoveType, pushing apart).
    Symptom: player's view snaps or their pawn wanders. Fix: disable on this map.
15. **Gravity / speed / FOV / third-person plugins.** Gravity/speed don't matter (pawn frozen). FOV plugins change
    the Doom FOV (fine). Third-person commands would break the custom camera.
16. **Team balancers** moving players between T/CT mid-round. Script handles OnPlayerTeamChanged (removes from
    arena or swaps Doom team), but it disrupts team modes. Prefer balancing only at round start.

## HUD and input
17. **Weapon menus / loadout givers / knife plugins** (!guns, !knife, round-start loadouts). Weapons in hand show a CS2
    viewmodel and ammo HUD over Doom. Script strips weapons from parked pawns, but a plugin giving weapons every
    round would fight it. Fix: disable on this map.
18. **Center-text / hint / advert / HUD plugins** draw over the Doom HUD. Cosmetic; maybe disable adverts on this map.
19. **Chat command clashes**: !spec, !afk, !stats may already belong to plugins. Rename if needed.
20. **Spectator rules** (mp_forcecamera, plugin spec restrictions) only affect the brief CS2-dead window in
    respawn modes.

## Performance and stability
21. **Server load (mock, Node, 18 Oct).** Script time per server tick (64-tick server = 15.6 ms for everything):
    16 players avg 0.44 ms (99% under 1.6), 32 players 0.87 ms (99% under 2.3), 64 players 2.5 ms (99% under 7.2;
    worst ~15 ms at round start while arenas are built). ~560 engine calls per tick at 64 players, mostly ~175 prop
    moves that CS2 networks to every client (not measurable in the mock). The console prints the real figure once a
    minute: `[hellmatch] script time: avg X ms, max Y ms per server tick`. Under ~5 ms avg is comfortable.
22. **Plugins iterating all entities** each tick (some do) get slower with the map's extra entities (items, effects pools).
23. **Round restart / mp_restartgame** from plugins clears spawned entities. Script rebuilds on round start; test it.

## Things to check together on first server launch
- [ ] Doom frag appears in CS2 killfeed with correct killer and victim
- [ ] Rank plugin records the kill (FFA and team rounds)
- [ ] Respawn after a frag works within ~2 s in FFA/TDM
- [ ] AFK plugin leaves Doom players alone
- [ ] Round ends when all arenas finish, and at the 10-minute limit
- [ ] No weapons/viewmodels on parked pawns after a plugin's round-start loadout
