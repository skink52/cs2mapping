# mg_monsoon: possible server / plugin interactions

Come back to this once a server runs the map. Each item: what could go wrong, how it shows up, the likely workaround.
Written 12 Nov 2026 from the script source (`src/`, version mv-0.1). **Nothing here has been observed**: the map has not been
compiled or run, on a listen server or a dedicated one. The script's behaviour is **simulated** (mock engine) only.

What the script does that plugins tend to trip over:
- sends a cvar list on activation (`CONFIG.CVARS`) plus `bot_quota_mode` / `bot_quota`;
- ends rounds itself (`GameRules.TerminateRound`, with two fallbacks);
- parks pawns (`MOVETYPE_NONE`, hidden, scaled down) in helicopter seats, on mounted guns and at the plotting board, teleports
  them every tick with the vehicle, and gives them a custom camera;
- deals scripted damage (shells, rockets, gun hitscan, crashes) and blocks some damage in `OnModifyPlayerDamage`;
- gives and strips weapons (kits; the Zeus as the anti-tank trigger, re-given after 25 s);
- uses chat commands starting `!` or `/`;
- sends `say` lines for `!pos` and `!bots`.

## Round flow
1. **Plugins that end rounds or reset round cvars.** The script needs `mp_ignore_round_win_conditions 1` and ends the round with
   `TerminateRound`; 20 s later, if no new round started, it fires `FireWinCondition` at `mv_params`; 40 s later it resets its own
   state. Symptom: rounds end when one team is dead, or never. Console: `[mv] round over: ...`, then possibly
   `[mv] no new round 20 s after TerminateRound ...` and `[mv] still no new round: the script restarts its own`. Fix: plugin
   config. The cvars are sent once, on activation: a plugin that rewrites them at round start wins, and the script does not re-apply them.
2. **Warmup, round-time and freeze-time configs.** The script sets `mp_freezetime 0` and `mp_roundtime 21` and runs its own
   20-minute clock from `CONFIG.CONQUEST.ROUND_SECONDS`. A server `mp_roundtime` under 20 ends the round early through CS2's own timer
   only if win conditions are not ignored. Warmup behaviour is untested.
3. **Map votes / RTV** changing the map mid-round cut the game; nothing to clean up.
4. **Match / competitive configs** (`mp_maxrounds`, half-time side swap): a side swap moves players between a howitzer base and a
   rocket base; the script reads the team each respawn, so it should follow. Untested.

## Respawn and death
5. **No-respawn plugins** break the game: every role depends on `mp_respawn_on_death_t/ct 1`. Symptom: players stay dead. Fix: exception for this map.
6. **Spawn protection / immunity.** The script sets `mp_respawn_immunitytime 0`. A plugin's god mode on spawn makes players in
   the briefing room and just-deployed players unkillable longer than intended; scripted shell damage would be absorbed.
7. **Respawn-wave or delayed-respawn plugins** stack on top of the briefing-room countdown (10 s first, 5 s after).
8. **Death-event plugins** (rewards, damage reports) see scripted kills (shell, rocket, crash) as `player_death` with a large hit,
   credited to the gunner or pilot the script names. A helicopter crash kills everyone aboard at once, credited to the last attacker
   within 10 s: reward plugins may read that as a multi-kill.
9. **Admin slay / respawn / teleport** on a seated player: the script drops the seat and restores the pawn on `OnPlayerReset`
   and on death. A teleport without a reset leaves the script moving the pawn back to the seat next tick.

## Kill credit and ranks
10. **Rank plugins** may ignore kills whose weapon is not a gun (scripted damage). Which weapon name the kill feed shows for a
    shell or rocket is unknown until tested.
11. **Team-kill punishment** (`mp_autokick`, `mp_tkpunish`, slay-on-TK): friendly splash is off (`ARTY.FRIENDLY_SPLASH false`)
    and the script blocks friendly damage to battery crews and players in the briefing room, but a helicopter crash kills
    teammates aboard. Whether CS2 counts those as team kills by the pilot or the enemy depends on the credit rule: untested.
12. **Damage plugins** hooking damage may block scripted hits. Symptom: explosions with no casualties. The script itself logs
    its own blocks: `[mv] blocked N damage to aboard / fast-rope / briefing room / battery crew (...)`, first 40 only.
13. **Assists**: the loader and the fire-mission caller get a non-lethal share of the damage so CS2 awards an assist. A plugin
    that normalises or caps damage per hit breaks that. (Unverified on the sibling map as well.)

## Pawn handling (pawns parked in seats)
14. **AFK managers (high risk).** A pilot's pawn is frozen at the seat and only its view moves; a battery crewman at the board
    does not move at all for minutes; riders sit still. Position-based AFK checks will flag all of them. The map has no AFK
    check of its own. Fix: input-based AFK detection, or an exception.
15. **Anti-stuck / noblock / anti-camp** plugins that move, unfreeze or collide-toggle pawns fight the seat code. Symptom: players
    falling out of helicopters, or standing on the pad while "flying". The script sets `mp_solid_teammates 1`.
16. **Third-person, FOV and camera plugins** fight the custom camera (chase view, gun cameras, the board view).
17. **Model / skin changers** (player model plugins, agents): the script may set team uniform models when the map caches them
    (none are cached in this version) and `!uniform` toggles back to the stock model; a model plugin applied after it wins.
    Scaling the pawn to 0.02 while seated may interact with plugins that set model scale.
18. **Team balancers** moving a seated player mid-flight: the script sees the team change at the next reset; until then a
    pilot could be flying the other team's helicopter. `mp_autoteambalance 1` is set by the map; plugin balancers are extra.
19. **Speed / gravity / movement plugins** (bhop, speedometers that set velocity): the loader's slow walk is a velocity cap by
    teleport and the fast-rope caps fall speed the same way.

## HUD and input
20. **Loadout givers, knife and weapon-skin plugins** put weapons on parked pawns (a viewmodel over the instruments) and undo
    kits. The anti-tank kit depends on holding exactly a Zeus. Fix: disable on this map.
21. **Weapon restriction plugins** that strip the Zeus, M249, Negev, G3SG1 or SCAR-20 break those kits.
22. **Center-text / hint / advert plugins** draw over the objective bar (top centre), the hold bar and prompts (centre) and the
    instruments (bottom centre).
23. **Chat command clashes**: `!infantry !artillery !arty !air !pilot !rifle !mg !at !swap !spawn !pos !uniform !bots !roles
    !help`, and the same with `/`. `!help`, `!spawn`, `!swap` and `!bots` are common plugin commands. The script reads chat; it
    does not suppress the message, so both would react.
24. **`!bots <n>` is open to every player** (`CONFIG.BOTS_CHAT true`): anyone can set the quota from 0 to 24. Set `BOTS_CHAT false`
    on a public server, or `BOT_QUOTA_MAX` lower.
25. **USE key plugins** (E to pick up, E menus): E is boarding, kits, stations and, held, the fire mission and gun repair.

## Bots
26. **Bot plugins and `bot_quota` configs** fight the script, which sets `bot_quota_mode fill` and `bot_quota 10` on activation
    and again on `!bots`. A server cfg applied after map start wins until someone types `!bots`.
27. **Bot behaviour in seats**: a bot assigned as AI pilot, gunner or crew is parked like a human while the script acts for it.
    What CS2's bot AI does meanwhile (shooting from the seat, trying to walk) is untested.
28. **Nav mesh size**: the sibling map lost server FPS with a 44k-area nav. This map confines nav generation with 85 NONAV
    volumes; whether they took effect shows in the build log's area count and in bot behaviour. Untested.
29. **Bots replaced by humans**: `bot_quota_mode fill` kicks a bot when a human joins; if that bot was an AI pilot in the air the
    script releases the seat (the helicopter auto-lands at 200 u/s). Simulated only.

## Performance
30. **Server load**: about 0.1 ms per tick at 32 players **on the mock engine**, whose traces cost nothing like the engine's.
    The real cost is unknown. The script traces every tick per flying helicopter (velocity trace plus four rotor traces), per shell
    and rocket, and per gun burst. The console prints
    `[mv] script time X ms/tick avg, Y max over N ticks, P players, errors E` once a minute; under about 5 ms is comfortable.
31. **Entity count**: 6,388 map entities, of them about 600 named ones the script uses (pools of particles, sounds, tracers,
    rockets, shells, markers). Plugins that iterate all entities every tick get slower.
32. **Client load**: 5,743 static props, rain particle systems over seven areas, a tree-filled 3D skybox. Unmeasured.
33. **Download size**: the content addon is about 1.15 GB of sources before compiling, 544 MB of it converted third-party
    models the map does not place. For a server's FastDL or Workshop item only the compiled game folder matters; its size is
    unknown until the first build.

## Things to check together on first server launch
- [ ] Console at map start: `[mv] mg_monsoon script mv-0.1 ...`, `[mv] points: spawns 16/16, helicopters 3/3, guns 4/3, mounts 8, ...`, no `[mv] missing entity`
- [ ] A rifle kill, a shell kill, a rocket kill and a crash kill each appear in the kill feed with the right killer and victim
- [ ] A rank plugin records each of those
- [ ] Respawn after a death goes through the briefing room and deploys within about 5 s
- [ ] The AFK plugin leaves pilots, riders and battery crews alone for a whole round
- [ ] Rounds end at 0 tickets and at the 20-minute limit, and a new round starts without the fallback console lines
- [ ] No weapons or viewmodels on seated players after a plugin's round-start loadout
- [ ] The server cfg's cvars and the map's `CVARS` list do not fight (check `mp_ignore_round_win_conditions`, `bot_quota`)
- [ ] The `[mv] script time` line with a full server: send it
- [ ] Note for dedicated servers: script `echo` / log output may not reach `console.log` under `-condebug` (seen on another
      project on this PC); read the live console
