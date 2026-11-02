# Hellmatch CS2 test: what to check

Each line says what to look for. **Only report what fails** (what you saw, the level, console lines if any): anything you don't mention counts as passed, so there's no need to send yes/no lists back. (The game was called "FreeDM Arena" before 17 Oct 2026; the map is now `mg_hellmatch`.)

## A. Open and build
- [ ] `maps/mg_hellmatch.vmap` opens in Hammer without errors. You should see the three lobby rooms far below and the 32 levels laid out above.
- [ ] Select the `point_script` and the `custom_hud_layout` and check that their file fields aren't red (missing). If one is, pick the file again in the asset browser and tell me what path it chose.
- [ ] The materials compile, both the walls and `materials/fdm/pal/*`. A pink/black checker means a material failed: send me the name.
- [ ] The models compile (`models/fdm/m01/*`, `models/fdm/spr/*`). If one fails, open it in ModelDoc and send the error.
- [ ] The map builds.

## B. Local test (listen server)
Run `map mg_hellmatch` with `bot_quota 5`, or invite a friend. Start the game normally, not in warmup.
- [ ] Console line `[hellmatch] v0.2.0 ready: 32 levels, 505 sprite models, HUD on, prop template on`.
- [ ] After freeze time you're in an arena level and your view moves with WASD.
- [ ] The textures look sharp and pixelated, not blurry or dark/black.
- [ ] Movement feels old-school: fast running, sliding along walls, stairs.
- [ ] The status bar shows at the bottom (face, numbers, gun sprite).
- [ ] Shooting works. Other players and bots look like blocky green/red/blue marines.
- [ ] Items are 3D and pickups work (message top-left, yellow flash).
- [ ] Sounds play and come from the right direction. If you hear nothing, check whether they play quietly from far away. That would mean the listener is at your parked body, not your view.
- [ ] Doors open with E. Lifts work, for example the MAP04 platforms.
- [ ] Sky: brown cloudy sky through openings.
- [ ] Fog: distant areas fade to black.

## C. Engine questions only a real run can answer
Answered items stay here as a reference (the → lines), so a problem that comes back can be checked against them.
1. **Does `cl_draw_only_deathnotices 1` hide the CS2 HUD?** If the radar, health or timer still show, tell me.
    → ANSWERED 18 Oct: it hides the custom HUD too, so it stays off; the normal CS2 HUD isn't much in the way.
2. **Is your own body in the way?** Look down while walking: you may see the top of your own marine. If it's distracting I can hide it.
    → ANSWERED: solved (own body hidden), then the wall see-through issues that followed were solved too.
3. **Player colours.** Bots should be different colours in free-for-all and red/blue in team modes. If everyone is green, the model skins aren't switching.
    → ANSWERED 18 Oct: bots get different colours per mode. Dead bodies revert to the green model; that's acceptable for now, as the death animation is a handy sign the kill landed before the CS2 credit arrives.
4. **Invisibility powerup.** The player should turn into a dark see-through shape.
    → Not yet seen in a game.
5. **Scrolling walls** (MAP13, MAP20). Do they scroll, and in the right direction?
    → ANSWERED 18 Oct: walls don't scroll and water doesn't move. Not worth fixing now; look at it alongside the next real bug fix.
6. **Kill credit.** Does an arena frag show in the CS2 killfeed with the right killer? About 2 s later, does the victim respawn into the arena?
    → ANSWERED 18 Oct: works. The CS2 kill comes ~0.5 s after the arena kill; respawning works.
7. **Round end.** Does the CS2 round end a few seconds after every arena finishes?
    → ANSWERED 18 Oct: yes, and the team credit works.
8. **Teleporters** (MAP01). Does your view face the new direction after teleporting?
    → ANSWERED 18 Oct: yes.
9. **Music.** A track should start when the round starts (console: `[hellmatch] music: DM.. <title>`), play for everyone, follow `snd_menumusic_volume` (the Main Menu Music slider; the in-game Music slider does nothing), move on to another track when it ends, and stop when the round ends.
    → ANSWERED: solved; the music follows the Main Menu Music slider.
10. **Rename.** The loading screen shows the HELLMATCH title and the new map icon; the chat says "HELLMATCH: <mode> - ..." at round start; `!help` shows the controls.
    → ANSWERED 18 Oct: the loading screen works.
11. **Lobby.** The bhop area is gone and the lobby is a plain room again (east wall at the original spot, no holes).
    → ANSWERED 18 Oct: the lobby is plain (the spawn torches stay, which is good).
12. **Kill messages.** A long kill message at the top left (for example "...WAS MOWED DOWN BY ...'S CHAINGUN.") wraps onto a second line instead of being cut off. Names longer than 12 characters are shortened on the game HUD only; chat and the scoreboard show the full name.
    → ANSWERED 18 Oct: works.
13. **Walls up close** (MAP28 especially). Press against walls, ledges too high to step onto, pillars and closed doors while looking around. You should keep seeing wall, never the sky or the room behind it.
    → ANSWERED 18 Oct: very rarely you can still see through, but no gameplay effect; no more work for now. Report it if it gets worse.
14. **Spectating.** In a free for all or team deathmatch round, type `!spec`. Above the status bar you should see "SPECTATING <name>" and under it "TYPE !BACK TO PLAY" (the two lines must not overlap). Type `!help`: for 8 seconds the keys and chat commands replace those lines, and the controls show top left. Type `!back`: you're back in. In team elimination or last man standing the bottom line says "YOU PLAY NEXT ROUND" instead and `!back` keeps you watching.
    → ANSWERED 18 Oct: works as the script intends. Joining CS2's own spectator team (free camera) is a bit buggy; players will learn not to, so it's not an issue.
15. **Joining mid-round.** Join a running round from a second account or have a friend join. Within about a second of picking T or CT you should be in an arena (or watching, in a one-life round), never standing in the lobby with a knife, and every line on the HUD should be complete (no missing letters).
    → ANSWERED 18 Oct: appears to work. Keep it on the list to re-check in every bug-fix update.
16. **Theme music.** Every round should open with the Hellmatch theme (console: `[hellmatch] music: THEME Hellmatch Theme (trailer)`), then a track from the pool follows after a 2-second gap. The generated tracks (GEN01-GEN04) play in free-for-all, team deathmatch and Boss Battle rounds; tell me which ones you like and which to drop.
    → ANSWERED 18 Oct: the theme plays at round start. Planned change for the next bug-fix update: see the list at the bottom.
17. **Boss Battle** (18 Oct build). Force it for a test: in `maps/scripts/freedm.js` set `MODE_WEIGHTS` to `{ ffa: 0, tdm: 0, boss: 100, elim: 0, lms: 0 }` (then `disconnect` and run the map again). Check: the round starts with a weapon; "WAVE 1 OF 5" shows in the centre and the top right says "WAVE 1 OF 5" / "N MONSTERS  LIVES 3"; monsters appear with a teleport flash and sound, walk, open doors, shoot and bite; they look like blocky 3D versions of the Freedoom creatures and face the way they walk; the frag box counts your kills; a death takes a life ("LIVES 2") and you respawn; waves follow each other ("WAVE CLEARED", 6 s pause); the 5th wave says "BOSS INCOMING" (chat names the boss); killing it ends the arena with "VICTORY"; the CS2 round score goes to the side with more monster kills. Also check: nobody can hurt a teammate (T or CT) in this mode; being killed by a monster shows in the killfeed as a death with no killer (no -1); the console has no `point_script ... thinking for` spikes when a wave arrives; a spectre (stealth worm) is a dark see-through shape; the arch-vile's (flame bringer's) fire column shows on its target.
    → ANSWERED 18 Oct (default weights): feels healthy and balanced; maybe could be harder, to be judged in live 16-player tests.
18. **Monsters in deathmatch.** Set `MONSTER_CHANCE: 1` the same way: every arena then has a few monsters loose in the level ("+ MONSTERS" in the round's chat line). Killing one gives no frag; dying to one costs none and shows a world death in the killfeed. Watch for monsters stuck in walls or floating; tell me the level and where.
    → ANSWERED 18 Oct (default weights): seen occasionally, no problems reported.
19a. **Boss Battle on big levels (18 Oct 08:xx build).** (Not tested yet.) The chat line at round start should name only the larger levels (MAP24, MAP32, MAP27, MAP23, MAP11, MAP30, MAP09, MAP01, MAP21, MAP04, MAP18, MAP20, MAP31, MAP10, MAP05, MAP22) for Boss Battle rounds. Also check: a teleporter never leaves you overlapping a teammate (you'd both be unable to move; if it happens, say which level), monsters that fall behind reappear near you with a teleport flash within ~25 s, `!spec` then `!back` in a Boss Battle round keeps you watching ("YOU PLAY NEXT ROUND") instead of giving you fresh lives.
19b. **Next-mode vote (18 Oct afternoon build).** At the end of a round the centre should say "VOTE NEXT MODE: 10" counting down, the bottom two lines list the modes with their keys and totals ("M1 FFA 0  M2 TDM 0  E ELIM 0" / "R LMS 0  F BOSS 0"), and the top right "YOUR VOTE COUNTS X..." (3 if you topped your arena). Press M1, M2, E, R or F: a `>` marks your pick, the total goes up by your weight and the top right shows "YOUR VOTE: ...". Pressing another key moves your vote; `!tdm` etc in chat do the same. This must work both while you're still looking at your arena and after CS2 restarts the round (standing in the lobby). When it closes: chat says "NEXT MODE: ... (votes ...)", the centre "NEXT: ...", and the next round plays that mode. Play the same mode twice: on the third ballot it must be missing. Holding fire through the end of the round must not cast a vote (the first second is ignored).
19c. **New bosses, boss music, monster score (18 Oct evening build; needs the map rebuilt, see below).** Force Boss Battle as in 17. The 5th wave's chat line names the boss: besides "assault tripod", "large technospider" and "pain lords" you should now also get "twin tripods" (two cyberdemons; 6+ players) and "summoner swarm" (several summoners spitting deadflares). The arena wins when all of them are dead. Boss Battle rounds play the boss tracks after the theme (console: `[hellmatch] music: E1M8 On the Next Day`, E2M8, E3M8, E4M8), never the deathmatch tracks; other modes never play them. In Boss Battle the scoreboard Score goes up by 2 per monster you kill and 10 for a boss. A flame bringer (arch-vile) stays visible while it attacks (it used to vanish for a moment).
    Map rebuild for this one: the map got 4 music entities (fdm_mus_e1m8 .. e4m8) and 3 model-cache props (fdm_cache_vile_0..2); build it the usual way (Hammer closed, command line), then check the console has no "no point_soundevent named fdm_mus_e..." warning.
19d. **Text size and top-bar avatars (19 Oct build; the HUD stylesheet changed, so build the map).** Type `!text` a few times: the red text lines (top left messages, top right lines, centre, the two lines above the status bar) go large, huge, small, tiny, normal; the message line says "TEXT SIZE: ...". Paired lines must never overlap, nothing should move off screen at huge, and the size stays through rounds and in the lobby. Top bar: the script asks each player's game to show a player count instead of the avatars (`cl_hud_playercount_showcount 1`). If the avatars are still there, CS2 refused it (the console may say so): tell me, and players can type it themselves. Note: when it works it is saved in the player's own settings.
19e. **19 Oct evening build (map build needed: 4 new props, new models and materials).** (a) Theme: plays at the start of the map's first round and of its first Boss Battle round, not otherwise (console `music: THEME`). (b) Boss Battle round end: chat "MAP.. top monster slayers: 1. ... 2. ... 3. ..."; the others in that arena die and the killfeed credits the top 3 (about half to 1st, a third to 2nd, the rest to 3rd); the Kills column goes up for them. (c) Water, lava, nukage, slime, blood and the falls now animate (they were stuck on one frame). (d) Scrolling walls move left: MAP13 (the face wall), MAP20 (the spine wall), MAP32 (the computer walls); a few pixels per step, so a little steppy. (e) Boss Battle about a third harder (difficulty 1.35): bigger waves arriving faster, tougher bosses, larger escort. Say if it's now too hard or still too easy.
19. **Frame rate.** With 4 arenas of 16 (bot_quota 60) and Boss Battle, props per arena go up to ~40 monsters plus their shots; tell me if the `script time` console line goes over ~5 ms or the fps drops at wave arrivals.

## D. Server (CounterStrikeSharp)
Use `claude/freedm_cs2_server_issues.md` in the project. The biggest risks are AFK managers, no-respawn plugins, spawn protection and teamkill punishment.

## Known gaps (planned next)
- Monster kills are not CS2 kills (nothing to kill in CS2): they add Score points in Boss Battle, but the Kills column and rank plugins don't count them without a server plugin (`MONSTER_KILL_COMMAND`); Boss Battle rounds still credit the CS2 round to a side.
- The Boss Battle difficulty (wave sizes, boss health) is tuned on bots only; expect to adjust `MONSTERS` and the budget in `36_monsters.js` after real games.
- Monster corpses stay only while they are among the last 24 (each is a prop in CS2).
- Flickering lights are steady.
- Bots navigate doors, lifts and teleporters but are still simple. Elimination rounds end after 4 minutes at most.
- Weapon keys: only next/previous (R, mouse 2, F). CS2 doesn't give scripts the number keys.

## Planned list of 18 Oct: done 19 Oct (see 19e)
- Theme only on the map's first round and first Boss Battle round; monster-kill podium; water/animated surfaces fixed (their skins never matched); scrolling walls as stepped frames; mid-round joining re-checked in the mock (churn, hudwipe, resetfirst, spec: nobody left in the lobby, screens match).
