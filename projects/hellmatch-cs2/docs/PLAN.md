# FreeDM for CS2 — design plan and handover (session 1, 15 Oct 2026)

## STATUS (end of session 1, ~01:20 15 Oct): first complete build, untested in CS2
Delivered dist/freedm_addon.zip (16 MB) + dist/freedm_source.zip. Rebuild everything with `sh tools/build_all.sh`.
- All 32 FreeDM maps converted (static chunks + rigid door/lift blocks, unlit per-light materials, 4x textures).
- Full Doom DM playsim in JS (src/core): movement, all weapons, items, armor, powerups, doors/lifts/floors/crushers,
  teleports, telefrags, barrels, sector damage, altdeath respawns, body queue, obituaries, Doom bots with sector-graph
  pathfinding (doors, lifts, teleporters).
- Round manager: arena split (fill 16, min 6), 4 modes (35/35/20/10), map picking by size, late join, AFK, spectating,
  elimination 4-minute limit.
- CS2 adapter (src/cs2): pawn parking + CustomPlayerCamera (CONTROLLED_POSITION), input, prop pool from one
  point_template, voxel sprite models, Doom HUD (custom_hud_layout, per-player classes), point_soundevent + SetSourceEntity
  sounds, real CS2 kills via TakeDamage (respawn modes immediate, elimination batched at round end), cvar handling.
- 190 sprite models (voxel carve / lathe / box / crossed planes), 16 colour skins + fuzz, Doom status bar HUD.
- Verified here: playsim soak tests (all modes, 64 bots), tsc against Valve's point_script.d.ts, full script run
  against a mock cs_script engine (rounds, kills, respawns, round end), geometry/model/HUD renders in a browser preview.
- Next session: Zach's first in-CS2 test using TESTING_FREEDM.md; then fix whatever the import/compile reveals.
- Improvement queue: animated flats/walls (split floors on the 64 grid + texture animation), sector light effects,
  music (MIDI -> OPL render), number-key weapon switching experiment, bot polish, HUD frag scoreboard on Tab.

## Where things stand
- Freedoom source repo cloned (github.com/freedoom/freedoom). It holds every asset as source files:
  levels/dm01-32.wad (FreeDM maps, nodes built), patches/flats/sprites/graphics as PNG,
  sounds as WAV, lumps/playpal, lumps/textures/textures.cfg (texture composition), musics as MIDI.
- Wrote tools/wad.py (WAD + map lump parser) and surveyed all 32 FreeDM maps:
  every map has 8-10 deathmatch starts, 30-340 sectors, and only a handful of
  specials (117 fast doors, 62/123 lifts, 87/89/54 perpetual platforms in dm04,
  97 teleporters, 48 scrolling walls, 11 exit switch; sector damage 7/16, light effects).
- Pulled the full cs_script API (source2.wiki function list, Sep 2026). Key pieces this design relies on:
  CustomPlayerCamera (FOLLOW_POSITION / CONTROLLED), IsInputPressed / WasInputJustPressed,
  CustomHudLayout.SetHasClassForPlayer / SetDialogVariableStringForPlayer,
  PointTemplate.ForceSpawn, Entity.Move, BaseModelEntity.SetModel / SetColor, OnModifyPlayerDamage.

## Architecture
1. **Whole Doom playsim in cs_script.** Doom movement (thrust, 0.90625 friction, 24-unit step-up,
   sliding, falling, view bob, squat), all 9 weapons with Doom's frame/tic tables, hitscan via
   blockmap path traversal, projectiles, splash damage with sight checks, armor, powerups, item
   pickup/respawn (altdeath default), doors/lifts/plats/floors, teleporters, telefrags, damaging
   floors, frags. Runs at 35 Hz; rendering interpolated at server tick.
2. **CS2 pawns are only input + camera.** On joining a game the pawn is parked frozen in a sealed
   booth; the script reads its inputs and eye angles; the view is a CustomPlayerCamera following a
   per-player invisible camera entity the script moves. CS2 damage to pawns is aborted.
3. **Rendering**
   - Level geometry: converted from the WADs into unlit models (point-sampled look kept by 4x
     nearest-neighbour upscaled textures), one material per texture x sector light level,
     black distance fog for Doom's light diminishing, Z scaled 1.2 (Doom's tall pixels).
   - Doors/lifts: each moving sector becomes its own rigid "block" model the script moves
     (matches Doom's pegging, so textures slide like the original).
   - Players, items, projectiles, effects: **voxel models built from the Freedoom sprites**
     (players carved from the 8 sprite rotations, items extruded). One shared palette material;
     16 player colours as model skins (Doom's green-range translation); sector light via SetColor.
   - Sky: toolsskybox on F_SKY1 ceilings, each map enclosed in a sky shell so the 4 games
     never see each other.
4. **HUD**: custom_hud_layout with the real Freedoom STBAR, digits, face, arms, keys, weapon
   sprites (psprites) and red/gold/green screen flashes, all as 4x-scaled Freedoom images,
   switched per player with CSS classes.
5. **Instances**: 4 games x 16 players in one map. Every converted level sits at its own spot in the
   world, so any game can run any level (rotation picks one no other game is using).
   Lobby room with 4 pads + auto-join + chat commands (!join N, !leave).
6. **Sounds**: Freedoom WAVs as sound events, played through a pool of point_soundevent entities.
7. **Delivery**: generated addon tree (models, materials, sounds, panorama, scripts/freedm.js) +
   a VMF to import into Hammer (entities: point_script, custom_hud_layout, templates, map
   props, lobby/booth brushes), since this session cannot write .vmap directly.
8. Safety: every tick wrapped in try/catch per instance, entity handles re-validated each tick,
   rebuild after round restarts, entity pools with hard caps (effects dropped, never spawned unbounded).

## Round structure (minigame server, 2-64 players) — added 15 Oct
One CS2 round = one Doom round. The CS2 round ends when every arena has finished
(script calls SetRoundRemainingTime(~5s) after a results screen) or the CS2 timer runs out
(default 10 min, set by the script at round start). On timeout, unfinished arenas are decided on
current score.

**Round start (after freeze time)**
1. Collect eligible players: on T/CT, alive pawn, not flagged AFK from last round.
2. Arena sizes (Zach, 15 Oct): **fill arenas to 16 first; minimum 6 per arena (3T + 3CT)**.
   A smaller arena is allowed only when the other three are already full (49+ players).
   - arenas = ceil(players / 16), max 4.
   - Fill 16, 16, ... and give the remainder to the last arena.
   - If the last arena has fewer than 6 and there are fewer than 4 arenas, move players from the
     previous arena into it until it has 6. Example: 20 -> 14 + 6, 22 -> 16 + 6, 38 -> 16 + 16 + 6.
   - With 4 arenas (49-64 players) the last one keeps its remainder (49 -> 16/16/15/2 so no arena has 1).
   - Fewer than 6 players in total: one arena with everyone.
   - Examples: 6-16 -> 1 arena, 17 -> 11 + 6, 32 -> 16 + 16, 40 -> 16 + 16 + 8, 64 -> 4 x 16.
3. Shuffle players randomly before filling so opponents change every round. In team modes each arena
   gets equal numbers of CS2 Ts and CTs (Doom teams = CS2 teams, see Kill credit).
   Optional "avoid repeats": weight the shuffle against last round's pairings.
4. Each arena gets a random map nobody else is using, from a pool sized to its player count
   (small maps for small groups, big maps for 12-16). No map repeats until the pool cycles.
5. Pick the game mode for the round (one mode for all arenas, so the round reads clearly; config can
   allow per-arena modes). Weighted random, never the same mode 3 rounds running:
   - **FFA**: first to N frags. N scales with arena size: min(20, 6 + 2 x players), so 20 at 7+ players.
   - **Team deathmatch**: Red vs Blue (random, balanced), first team to N total frags:
     min(32, 4 x players), so 32 at 8+ players.
   - **Team elimination**: one life each, last team standing. Needs 4+ players.
   - **Last man standing** (FFA, one life). Optional, can be weighted to 0.
   Team modes fall back to FFA in arenas with fewer than 4 players. 2-3 players get a duel/FFA.
   Teams are shown by Doom player colour (red/blue suits) plus a HUD tag. They are independent of CS2 T/CT.
6. Spawn everyone at that arena's deathmatch starts (spread out, no telefrag at round start),
   with a 3-second "FIGHT" countdown and brief spawn protection.

**During the round**
- Status bar FRAG box shows your frags (FFA) or team score (team modes). A small top-right panel shows
  the leader / both team scores and the target.
- Doom-style kill messages per arena ("X was splattered by Y's rocket"), also in chat if configured.
- Kill credit: every frag is credited to the killer (suicides, crushers, slime and telefrags follow Doom
  rules) AND turned into a **real CS2 kill** so rank plugins count kills and deaths (Zach, 15 Oct).
  See "Real CS2 kills" below.
- Friendly fire off in team modes (configurable). Suicide = -1 frag (Doom rule).
- When an arena finishes: winner banner, then its players become spectators of arenas still running.
  Attack / mouse2 = next / previous player, Use = next arena. Eliminated players spectate the same way.

**Late joiners and leavers**
- Players joining mid-round: put into the smallest running respawn-mode arena (FFA/TDM) if one exists
  and it is under 16, otherwise spectate until next round.
- Disconnect / team change / AFK removal: player removed. Team elimination checks immediately,
  so a leaver can't stall a round. An arena that drops to 1 player (or 1 team) ends.

**AFK protection**
- Activity = any movement/fire/use input or a view-angle change of more than ~2 degrees.
- 20 s idle: HUD warning. 30 s idle: pulled out of the arena (counts as eliminated in elimination
  modes), becomes a spectator, and is flagged AFK. AFK players are skipped at the next round start
  until they press a key.
- Players still idle at round start (nothing pressed through freeze time + 10 s) are dropped the same way.
- Optional: move long-term AFK to CS2 spectator with JoinTeam(1) (off by default).

**Lobby**
- The 4-pad lobby from the original plan is no longer needed for joining. The lobby room stays
  as the CS2 spawn area and the place where pawns wait during freeze time / between rounds.
  Chat commands remain: !spec, !afk, !stats.

## Next steps (in order)
1. Asset extraction: palette, compose wall textures from textures.cfg, flats, sprites (grAb offsets), HUD graphics, sounds.
2. Map converter: sector triangulation, walls with Doom texture alignment, sky, mover blocks, SMD + vmdl + vmat, runtime level data.
3. Playsim core (engine-agnostic JS) + Node test harness with a mock cs_script API.
4. CS2 adapter: instances, cameras, input, entity pools, HUD, sounds.
5. Voxel model generator, HUD panorama files, VMF, README, zip.

## Real CS2 kills (rank-plugin credit)
Every Doom frag becomes a CS2 player_death with the right attacker, made by the script calling
victimPawn.TakeDamage({ damage: 1000, attacker: killerPawn, damageTypes, damageFlags: FORCE_DEATH }).
The damage hook aborts all other damage to pawns, but lets these scripted kills through (per-slot flag
set just before the call).
- **Respawn modes (FFA, TDM)**: Doom death plays (scream, fall, death view) for ~1 s, then the CS2
  pawn is killed with credit. CS2 respawns it (script sets mp_respawn_on_death_t/ct 1 and
  mp_respawn_immunitytime 0 for these rounds). OnPlayerReset re-parks the pawn and the Doom player
  respawns at a DM start with brief spawn protection. Doom's "press Use to respawn" is replaced by
  this automatic respawn. The CS2 dead window (~1-2 s) shows CS2's own death view; the HUD says "Respawning".
- **Elimination modes (Team elim, LMS)**: pawns stay alive while their arena runs, so eliminated players
  keep the script's spectator camera and can watch any arena. When the arena finishes, the script
  applies the kills in the order they happened, each credited to its killer (every pawn is still alive, so
  every attacker is valid). Winners stay alive.
- Suicides / slime / crushers / falling: killed with attacker = self or none, so CS2 counts a suicide like Doom's -1.
- FFA rounds: script sets mp_teammates_are_enemies 1 so same-CS2-team kills count as normal kills,
  not teamkills (no TK penalty, kick or rank loss). Team rounds set it back to 0; friendly fire off in Doom.
- mp_ignore_round_win_conditions 1 while any arena runs, so CS2 never ends the round because
  pawns died. The script ends the round with SetRoundRemainingTime once every arena is done.
- No AddScore when real kills are on, otherwise the scoreboard double-counts.
- Test needed: whether TakeDamage with an attacker gives proper killfeed + player_death credit,
  and what weapon icon shows (probably world/none).
- Fallback if scripted kills don't credit properly: plugin-side helper (CounterStrikeSharp) or AddScore-only.

## Doom teams = CS2 teams
Team modes use each player's CS2 side (T = Red, CT = Blue), as in "3T vs 3CT". The arena split balances
Ts and CTs per arena. If the server's sides are uneven, the odd player goes to the arena where it
evens out; a still-uneven arena gives the smaller team +25% health (config) rather than moving
anyone with JoinTeam (JoinTeam mid-round may kill the pawn). FFA ignores sides.

## Decisions so far (Zach)
- Arena split: fill to 16 first, min 6 (exception: 4th arena when the other 3 are full).
- Real CS2 kills/deaths required (rank plugins).
- Mode mix: FFA 35 / TDM 35 / Team elimination 20 / LMS 10.
- Server runs CounterStrikeSharp. Possible conflicts are listed in SERVER_ISSUES.md, to work through once the server is up.

## Still open (no answer needed until it matters)
- Weapon keys: R / F / mouse2 cycling as baseline. OK?
- Music: convert the MIDI (quality may be lower) or skip?
- Doom bots for testing and filling small rounds: wanted?

## Queue: needs Zach at his PC
1. Link this chat to the PC (desktop app) or unzip the addon into content\csgo_addons\fdm_freedm.
2. Hammer: import the generated VMF, check the point_script / custom_hud_layout keys, build the map.
3. First local test (listen server, a few bots off): movement + camera, HUD images, sounds audible,
   textures crisp, doors/lifts move, sky, fog.
4. Answer the engine questions that can only be seen in game: viewmodel in custom camera, CS2 HUD hiding,
   sound listener position, scrolling-wall material, death camera mode.
5. Scripted-kill test: does TakeDamage with an attacker give killfeed + player_death credit?
6. Server launch with CounterStrikeSharp: go through SERVER_ISSUES.md checklist.

## Can be built without the PC (in this order)
Asset extraction → map converter → Doom playsim + Node test harness → CS2 adapter (instances, round
manager, kill credit, AFK, spectating) → voxel models → HUD → VMF + README → zip.

## Weapon switching (CS2 gives scripts no number-key input)
Baseline: R = next weapon, F (inspect) = previous weapon, mouse2 = next weapon, E or Space = use.
Experimental option: give the frozen pawn knife/pistol/rifle and read active-weapon changes
for number keys 1-3 + mouse wheel (needs a test: does the CS2 viewmodel show in a custom camera?).
