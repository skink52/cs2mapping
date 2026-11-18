# Hellmatch ZE (zombie escape): findings, risks and plan

Written 19 Nov 2026 from a read of `src/core`, `src/cs2`, `tools/`, `docs/STATUS.md`, `docs/PLAN.md`, the root `CLAUDE.md`,
`docs/reference/cs_script-notes.md` and `create/test/`. Nothing in the existing Hellmatch modes was changed.
Status words follow `docs/reference/compatibility.md`: everything below is **read from code**, nothing is simulated or in-game verified yet.

**Verdict: no blocker.** Monster AI, projectiles, melee, knockback, a growable shared prop pool, arena-to-arena moves and
cross-team kill credit all exist. The real gaps are a *player-controlled monster* (a "zombie class"), *trigger scripting* for
linear levels, *two copies of one level* (both sides play the same map), and the *level conversion* of Freedoom Phase 1/2 maps.

---

## 1. Findings

### 1.1 Arenas, round manager, mode switching. Where "ze" plugs in
- Modes are a table: `src/core/70_round.js:6-12` (`MODES`: name, teams, respawn, coop, minPlayers).
- A round: `RoundManager.startRound` (`70_round.js:116`) collects T/CT people, sizes arenas (`arenaSizes`, `:17`), picks one mode for
  all arenas (`pickMode` `:78`, or the vote's ranking `:138-147`), splits groups (`splitGroups` `:180`, balanced T/CT for team modes),
  plans map/loadout/monsters per arena (`planArenas` `:210`) and builds one arena per tic (`buildNext` `:231`).
- An `Arena` (`src/core/60_arena.js:24`) owns one loaded level, its players (`Map slot -> player`), mobjs, thinkers, an optional
  `MonsterDirector` (`:54`), and its own events. All playsim code reads the global `G`, set by `arena.run()` (`:62`), so arenas are
  fully independent.
- Per-tic rules and win checks are a `switch (a.modeKey)` in `RoundManager.arenaRules` (`70_round.js:443-520`); round end is
  `checkAllEnds` (`:566`) -> `roundOver` event -> `endDoomRound` on the CS2 side (`src/cs2/60_main.js:138`), which picks the CS2
  winning side and fires `FireWinCondition` on `fdm_map_params` (`60_main.js:152-163`).
- **ZE needs a cross-arena rule** (one side's deaths feed the other side's arena; the round ends on a two-arena condition). The
  per-arena `switch` can't express that, so ZE is not a sixth `MODES` row in the Hellmatch round manager. Plug-in point for the
  new addon: a `ZeRound` class with the same surface as `RoundManager` (`startRound`, `tic`, `leaveArena`, `joinArena`, `lateJoin`,
  `people`, `events`), always building exactly two arenas (T arena, CT arena) on two copies of one level, plus a `ZeDirector` per
  arena replacing `MonsterDirector`'s wave planner. The CS2 side (`60_main.js`) already talks to `rm` only through that surface.

### 1.2 Sprite prop pool: size, real limit, sharing. Zombie estimate
- There is **no fixed pool size**. `takeProp` (`src/cs2/20_render.js:38`) reuses a hidden prop from the global `freeProps` list
  (`:16`) or `ForceSpawn`s a new one from the `fdm_tpl_prop` point_template (`:25-36`), at most `SPAWN_BUDGET` = 20 new props per
  server tick (`src/cs2/00_config.js:98`). Props are never deleted: released ones get the null model and park at z -15000 (`:46-53`).
- **Shared across arenas**: one global `freeProps`; each `ArenaView` (`20_render.js:71`) maps its mobj ids to props
  (`this.props`) and gives them back when the thing is gone (`:148-154`) or the arena ends (`destroy`, `:197`).
- **Every mobj in an arena is drawn**, whatever its distance from any viewer (`20_render.js:129-147`): items, decorations,
  corpses, missiles, effects. No culling.
- Caps that exist: effects `MAX_EFFECT_PROPS` 120 per arena (`00_config.js:93`, checked at `20_render.js:134`); player body queue 32
  (`60_arena.js:173`); last 24 monster corpses per arena (STATUS 18 Oct); Boss Battle alive cap `min(36, 8+2n, 6+area/120000)`
  (`src/core/36_monsters.js:271`); lost souls 20 per arena.
- **The real limit is moving things per tick, not prop count.** A prop costs nothing per tick once still: `drawThing` returns early
  when the position is unchanged (`20_render.js:183`). Measured in the mock (STATUS 17-18 Oct): 64 players ~145 prop moves per tick;
  4 Boss Battle arenas (up to 4 x 36 monsters + 32 players) at 2.2 ms average script time per tick, worst 52 ms at wave spawns.
  CS2's own cost of the moves and their networking was never measured in game (STATUS open item).
- Freedoom single-player maps carry 100-400 things (items, decorations, monsters); all become props once at load (spread by the
  spawn budget), most then stay still.
- **Estimate for two arenas:** keep the moving load near the tested 64-player figure. Recommended default **48 live zombies per
  arena (AI + players together)**, configurable up to 64: 96-128 zombies over both arenas, plus up to 32 humans and their shots.
  AI fills `cap - zombiePlayers`, so AI yields to players as people die. Above that, wake/spawn zombies only in the active stage
  (sidecar spawn groups), which ZE wants for pacing anyway.

### 1.3 Things, monster AI, bots in `src/core`
All present:
- Doom state tables for all 17 Freedoom creatures, generated from the Doom source: `src/core/00_a_monsters.js`
  (`tools/monsters_gen.py`). Imp = serpentipede (`IMP`/TROO), demon = flesh worm (`DEMON`/SARG), lost soul = deadflare (`LOSTSOUL`/SKUL).
- Behaviour port in `src/core/35_enemy.js`: noise alerts (`:21`), `lookForPlayers` (`:65`), `checkMeleeRange` (`:87`),
  `checkMissileRange` (`:95`), 8-direction movement and door use (`:113-`), `spawnMissile` (`:174`), `A_FaceTarget` (`:191`),
  `A_Look` (`:198`), `A_Chase` (`:217`), plus all attack actions (claw/fireball, bite, skull charge, tracers, etc.).
- `MonsterDirector` (`src/core/36_monsters.js:39`): waves (`planWave` `:65`), bosses (`planBoss` `:92`; tripod, twin, spider,
  swarm, lords), out-of-sight teleport-in spawning and the alive cap (`tic` `:226-277`), anti-stall relocation (`unstick` `:318`).
- Doom bots for CS2 bots: `src/core/65_bot.js` (`botThink` `:111`), with sector-graph paths through doors, lifts and teleporters.
- Missing for ZE: (a) map-placed monsters are skipped at load (`60_arena.js:79`, "monsters come from the director"), so the
  WAD's own horde is ignored; (b) monsters target every entry in `G.playerMobjs` (`35_enemy.js:66`, filled at `60_arena.js:296`),
  so they would attack zombie players; (c) a bot has no "I am a zombie" behaviour.

### 1.4 Weapons, HUD, first-person sprite. What a monster-ability "weapon" needs
- Weapons are Doom's: `WEAPONINFO` states and the psprite machine (`setPsprite` `src/core/40_player.js:191`, `movePsprites` `:250`,
  `fireWeapon` `:237`), with action functions in `WEAPON_ACTIONS` (`40_player.js:284`; e.g. `A_FireMissile` `:384` calls
  `spawnPlayerMissile` `src/core/30_mobj.js:212`, which handles autoaim and free-look slope).
- HUD view sprite: `hudPlayer` swaps a CSS class on `fdm_wspr` / `fdm_wflash` per psprite state (`src/cs2/30_hud.js:233-236`),
  class `w_<sprite>_<frame>` (`weaponClass` `:204`). `tools/hud.py:90-100` makes one PNG + CSS rule per name in `WFRAMES`.
- A monster ability "weapon" needs: (1) new psprite states (sprite names like `ZCLW`, `ZFBL`) in the state table with tics;
  (2) action functions: claw = melee like `A_Punch` with the monster's damage (imp 3d8), fireball =
  `spawnPlayerMissile(p.mo, MT.TROOPSHOT)`, bite = melee 4d10, charge = timed `MF_SKULLFLY`-style lunge (as `A_SkullAttack`, aimed
  by view); (3) view art PNGs added to `WFRAMES` (placeholder: cropped/flipped frames of the monster's own attack sprite);
  (4) cooldown instead of ammo (`checkAmmo` treats `AM_NOAMMO` as always ready, so cooldown is a counter in the action).
- The **zombie body** also needs a player class: the player mobj keeps player physics and input, but its body states map to the
  monster's sprite states (spawn/see/melee/missile/pain/death) and take the monster's health, radius, height, speed and pain chance.
  `movePlayer` hard-codes `PLAY` states (`40_player.js:117`) and `fireWeapon` sets `PLAY_ATK1` (`:239`): those become class lookups.
  Rendering already rotates any 8-rotation sprite (`20_render.js:69,181`), so monster sprites draw correctly on a player mobj.

### 1.5 Damage thrust (knockback)
Exists. `damageMobj` (`src/core/30_mobj.js:254-263`): thrust = damage x 12.5 / mass along inflictor -> target, 4x and reversed for
a low-damage kill from below; none for the chainsaw or `MF_NOCLIP`. ZE wants knockback on zombies: tune with a per-class mass
(heavier = less push) and an optional `ZE.KNOCKBACK` multiplier applied only to zombie-player targets.

### 1.6 Moving a player between arenas; kill credit and scoring
- **Pawn parking**: the CS2 pawn stands frozen in a booth (`src/cs2/40_players.js:15-35`, `park`/`unpark`); the view is a
  `CustomPlayerCamera` following a script-moved camera; input is sampled from the pawn (`sampleInput` `:61`). The camera follows
  whatever `pe.player.mo` is, so **switching arenas is purely Doom-side**: `rm.leaveArena(pe)` (`70_round.js:292`) then
  `rm.joinArena(pe, otherArena)` (`:271`) and the pawn never moves. Note `leaveArena` marks one-life/co-op leavers with
  `pe.outRound` (`:302`); ZE must not use that path for the swap.
- **Kill credit**: every Doom frag becomes a real CS2 kill via `csKill(victim, killer)` (`src/cs2/60_main.js:215-232`,
  `TakeDamage` with `FORCE_DEATH`); in respawn modes after `KILL_DELAY` 1 s, then CS2 respawns the pawn (`mp_respawn_on_death_*`),
  `OnPlayerReset` re-parks it (`60_main.js:709-724`). Damage to pawns is otherwise aborted (`:738`).
- **ZE needs no team change.** A zombie keeps its CS2 team. A T player who died and attacks CT as a zombie is still on T, so:
  zombie (T) kills CT human -> a normal enemy kill for T; CT human kills that zombie -> normal enemy kill for CT; AI zombie kills a
  human -> world kill (as Boss Battle does, `60_arena.js:334-340`). Teamkill penalties never arise because every player kill is
  across T/CT. Keep `mp_teammates_are_enemies 0`.
- **Round win**: "the last side with humans alive" maps straight onto `FireWinCondition` with `TERRORISTS_WIN` / `CTS_WIN`
  (`60_main.js:160-163`). CT humans wiped by T-origin zombies -> T wins, exactly as asked.
- Scoreboard: kills/deaths are real CS2 kills; AI zombie kills by humans use `AddScore` like Boss Battle monsters (`monsterScore`
  `60_main.js:236`); a stage hold completed alive and an escape can add score the same way.

### 1.7 Can `tools/convert.py` take Freedoom Phase 1/2 maps?
- Not as written: it hard-codes `levels/dm%02d.wad` (`tools/convert.py:369`) and ids 1-32 (`:703`). The parser itself
  (`tools/wad.py`) reads any Doom-format map (THINGS, LINEDEFS, SIDEDEFS, VERTEXES, SECTORS, SEGS, SSECTORS, NODES, REJECT);
  the Freedoom repo holds Phase 1 as `levels/e1m1.wad`..`e4m9.wad` and Phase 2 as `levels/map01.wad`..`map32.wad`, same format and
  the same texture set (`textures.cfg`), so the change is a name list, not a new parser.
- The converter needs built BSP nodes (`convert.py:150-174`). The DM levels had them; the Phase 1/2 files must be checked after the
  clone. If any lack nodes, build them with ZDBSP (open source) into a work copy, never into the checkout.
- `Arena.load` (`60_arena.js:70-84`) keeps only hard-skill things (`flags & 4`), strips keys and all monsters. ZE needs: monsters
  kept per sidecar, keys kept or replaced by stage triggers, exits wired to the escape (`onExitLine` `:311` currently disables them).
- No Freedoom checkout exists on this PC (`C:\source1\...` searched); the deployed Hellmatch addon (`content\csgo_addons\mg_freedm`,
  1,658 model files, 381 MB) has the sprite/HUD/sound assets but only FreeDM level geometry.
- **Licence**: all Freedoom content (Phase 1, Phase 2, FreeDM) is under the same modified BSD licence (`FREEDOOM_LICENSE.txt`); the
  addon must ship the licence and `CREDITS`, and the Workshop description must carry the licence text (STATUS "Workshop": the upload
  carries only the game folder). Level authors are credited per map in Freedoom's `CREDITS`; ZE loading screens should name the map
  author. Hellmatch's own code stays PolyForm Noncommercial / CC BY-NC (`LICENSE`); the ZE addon reuses it under the same terms.
  Don't use the Freedoom name as the addon's name (Hellmatch rule, README "Credits").

### 1.8 Edge cases
- **Both sides wiped on the same tick** (or within the `KILL_DELAY` window): draw (`CSRoundEndReason.DRAW`). Tie-break options if a
  draw feels bad: the side that reached the later stage wins, then the side whose last human died later in tic order.
- **Disconnects**: a human leaving counts as that side losing a human (it can't stall the round); a zombie player leaving is just
  removed and the AI fill rises by one. Rejoining the same round: as a zombie in the arena opposite their CS2 side. A leaver's
  pending `csKill` is dropped (`forgetKills`, as now).
- **A zombie's original team**: stored on the person (`pe.zeSide` = 2|3, `pe.zeRole` = 'human'|'zombie'); the CS2 team stays the
  same, so it is always `pe.csTeam`. A zombie that switches CS2 team mid-round is removed and rejoins as a zombie for its new side.
- **Team imbalance**: 10 T vs 4 CT makes the CT horde fed by 10 potential zombies. Give the smaller side extra human health or
  armour (Hellmatch's +25% rule, PLAN "Doom teams = CS2 teams") and scale AI fill by the other side's head count.
- **Zombie dies**: respawns as a zombie at a spawn group behind the humans after `ZE.ZOMBIE_RESPAWN` seconds (no limit).
- **Humans who fall/crush/slime**: they become zombies too (world death), for the other side.
- **Late joiners**: join as a human only during the first stage hold; afterwards as a zombie for the opposite arena.
- **Escape done by one side while the other still fights**: that side wins at once (see the round rules in section 4).
- **AFK**: Hellmatch's AFK removal (`checkAfk`, `70_round.js:584`) counts an AFK human as lost.
- **Warmup**: no CS2 kills in warmup (existing rule); ZE rounds may run, nothing is credited.
- **Telefrags between a zombie arriving at a spawn and a human**: the human always wins (zombie spawns are checked with `fitSpot`).

---

## 2. Risks (performance and level content first)

1. **CS2-side cost of two busy arenas (high).** Script time is understood; the cost of ~150 prop `Move`s per tick plus sounds and
   their networking is not, and was never measured in game. Mitigation: the per-arena zombie cap (48), stage-gated spawn groups,
   a new distance cull in `ArenaView.update` (props for things more than `ZE.DRAW_DIST` from every viewer in that arena are hidden
   and stop moving), a timing line in the console (Hellmatch's 1-minute script-time line) and an in-game test with 32 bots early.
2. **Two copies of every ZE level (high, content).** Both sides play the same map at once, but a level sits at one fixed world spot
   with entities named per level (`fdm_<lvl>_f<sector>` movers, `20_render.js:97`; anim props). The round manager also refuses two
   arenas on one level. Plan: place each converted level twice (ids `e1m1t`, `e1m1c`; same model files, two placements, two sets
   of mover names). World space: the CS2 world is +-16384; Phase 1 maps are typically 4-7k units across, so 3-5 maps x 2 copies fit,
   but big Phase 2 maps may not. Pick maps by bounding box.
3. **Level fit for ZE (high, content).** Freedoom SP maps are non-linear (keys, backtracking, secret areas). Each map needs a
   sidecar that blocks side routes, turns key doors into timed holds and marks spawn groups. Expect half a day per map to author
   and playtest. Start with one short, linear Phase 1 map (E1M1 or E1M2 after a look at its layout and line count).
4. **Missing nodes in Phase 1/2 WADs (medium).** Converter depends on NODES/SSECTORS/SEGS. Fallback ZDBSP.
5. **Zombie-player feel (medium).** Doom's player physics with monster stats: a demon zombie with player thrust may be too fast;
   lost-soul dash through doors may clip. Tune per class; a charge that hits a wall stops (as `A_SkullAttack`).
6. **Deprecated API (medium).** Hellmatch uses `Instance.*` calls (`FindEntityByName`, `EntFireAtTarget`, `Msg`, ...). The repo rule
   (`CLAUDE.md`) forbids new code with deprecated calls: the ZE script must move them to `Entities.*`, `ent.FireInput`,
   `Console.Log`, `GameRules.*` and pass `create/test/api.py --strict --check` and `tscheck.sh`.
7. **Compile time and size (medium).** Hellmatch's sprite set is 346 MB and a full map build took 30+ minutes. The ZE addon reuses
   the compiled sprite/sound/HUD files by copy from the Hellmatch game addon (same `models/fdm/...` paths, no recompile) and only
   compiles its own level models and new HUD art.
8. **Kill-feed noise (low).** Every human death is a CS2 kill (often world); zombies dying often fill the feed. Acceptable.
9. **Balance on bots only (low, ongoing).** As with Boss Battle, first numbers come from bot runs.

---

## 3. Sidecar trigger file (one JSON per map, `ze/<map>.json`)

The WAD is never edited. Lines, sectors and things are referred to by their index in the WAD (stable while the WAD is unchanged);
`wad_sha1` makes the build refuse a sidecar written for a different WAD. Coordinates are Doom units.

```json
{
  "map": "E1M1",
  "wad": "levels/e1m1.wad",
  "wad_sha1": "<sha1 of the WAD file>",
  "title": "Outpost Outbreak",
  "author_credit": "from Freedoom CREDITS",
  "time_limit": 600,
  "humans": { "start": "player_starts", "health": 100, "loadout": ["pistol", "shotgun"], "keys": "remove" },
  "zombies": {
    "cap": 48,
    "map_monsters": { "use": true, "skill": "hard", "replace": { "CYBERDEMON": "BARON" }, "drop": ["SPIDERMASTERMIND"] },
    "player_classes": ["IMP", "DEMON", "LOSTSOUL"],
    "respawn_seconds": 4
  },
  "spawn_groups": {
    "yard":  { "points": [[1056, -3200, 90], [1180, -3240, 90]], "radius": 64, "ai": { "IMP": 3, "ZOMBIE": 4 } },
    "lab":   { "sector": 41, "ai": { "DEMON": 2, "IMP": 2 }, "trickle": { "every": 8, "max": 10 } }
  },
  "blocks": [
    { "id": "side_route", "lines": [210, 211], "until": "stage:2" }
  ],
  "stages": [
    { "id": 1, "name": "HOLD THE YARD", "start": "round",
      "hold": 30, "zone": { "sector": 12 },
      "zombie_spawns": ["yard"],
      "on_done": [ { "open_door": { "tag": 3 } }, { "message": "THE GATE IS OPENING" } ] },
    { "id": 2, "name": "REACH THE LAB", "start": { "line_crossed": 345 },
      "hold": 45, "zone": { "box": [900, -2100, 1300, -1800] },
      "zombie_spawns": ["lab"],
      "on_start": [ { "lower_lift": { "tag": 9 } } ],
      "on_done": [ { "open_door": { "tag": 5, "speed": "slow" } }, { "teleport_zombies": { "behind": true } } ] },
    { "id": 3, "name": "DEFEAT THE GUARDIAN", "start": { "stage_done": 2 },
      "boss": { "type": "BARON", "at": [2200, -900, 180], "health_scale": "players", "music": "boss" },
      "on_done": [ { "open_door": { "tag": 7 } } ] },
    { "id": 4, "name": "ESCAPE", "start": { "stage_done": 3 },
      "hold": 20, "zone": { "sector": 88 }, "escape": true,
      "on_start": [ { "lower_lift": { "tag": 12, "delay": 20 } } ] }
  ]
}
```

Rules:
- `start`: `"round"`, `{ "line_crossed": i }` (any live human crosses WAD line i), `{ "stage_done": n }`, `{ "use_line": i }`,
  `{ "zone_entered": {...} }`.
- `zone`: `{ "sector": i }` | `{ "sectors": [..] }` | `{ "box": [x1, y1, x2, y2] }`. A hold counts down while at least one live
  human is inside, pauses (does not reset) while none is, and shows a HUD bar.
- Actions: `open_door` / `close_door` / `lower_lift` / `raise_floor` / `lower_floor` (tag; run through the existing specials in
  `src/core/50_spec.js`), `message`, `spawn_group` (wake or spawn a group now), `teleport_zombies` (move zombies far behind the
  humans to the active stage's spawns), `unblock` (lift a `blocks` entry), `music`, `score` (`AddScore` to every live human).
- `blocks`: lines made impassable (and monster-blocking) until the condition, so side routes and backtracking are shut.
- `escape: true` on the last stage: humans alive in the zone when its hold ends have escaped.
- The build validates every index against the WAD (line/sector/thing exists, tag used by a door or lift sector) and writes the
  sidecar into the script's level data; the browser preview (`preview/`) draws stages, zones, blocks and spawn groups on the map.

---

## 4. Round rules (v1)

- Two arenas, always: the T arena and the CT arena, the same level (two copies). Each side starts as humans.
- Human killed by anything: after `KILL_DELAY`, CS2 kill (credited to the zombie's player if one did it, else world), then the
  player joins the other side's arena as a zombie (class picked by rotation or at random from `player_classes`; later by key).
- Zombies (AI and players) respawn forever. AI never spawns in sight of a human (existing `MonsterDirector` spot rules).
- Round ends when:
  1. one side has no live humans -> the other side wins (if both, same tick -> draw);
  2. a side completes the escape stage with at least one human -> that side wins at once;
  3. the clock runs out -> the side with more live humans wins; equal -> the side at the later stage; equal -> draw.
- Scores: CS2 kills as above; `AddScore` for AI zombie kills, a completed hold (each live human) and the escape.
- Humans keep Hellmatch weapons and pickups. Zombies can't pick items up.

---

## 5. Phased plan

**Addon**: a new standalone addon, working name **Hellmatch ZE**, map `mg_hellescape`, project folder `projects/hellmatch-ze-cs2/`
(own README with the AI disclaimer, licence files, row in the root `CLAUDE.md` / `README.md`), entity prefix `hze_`. It copies
`src/core` + `src/cs2` from Hellmatch as its starting point (the Hellmatch addon itself is not touched) and reuses the compiled
Hellmatch sprite, HUD and sound files by copy.

### Phase 0: scaffold (no Freedoom needed)
- Project folder, licences, README, STATUS.md with "Resume here", progress file.
- Copy the code, move it to the current cs_script API (risk 6), pass `api.py --strict --check` and `tscheck.sh`.
- Mock engine runs the copied code unchanged on a FreeDM level (proves the copy before any ZE change).

### Phase 1: first playable version (the version asked for)
1. Converter: Phase 1 name list (`e<e>m<m>`), nodes check, **two placements per level**, sidecar loader + validator; convert one
   Phase 1 map (the most linear short one, picked from the bounding box and line count).
2. Sidecar for that map: 3-4 stages (two holds, one boss, escape), blocks for side routes.
3. `ZeRound` + `ZeDirector`: two arenas, human -> zombie swap into the other arena, win rules (section 4), AI-only horde from the
   map's own monsters + spawn groups, cap 48, stage-gated spawns.
4. Zombie player classes: **imp** (claw + fireball) and **demon** (bite + charge) on the player mobj, with placeholder view art
   cut from the monsters' own attack frames; monsters ignore zombie players; zombies can't use items.
5. One **scripted boss** (baron-class, Doom AI) in stage 3, health scaled by humans alive.
6. Bots: human bots use Hellmatch's bot AI with "follow the stage zone"; zombie bots chase the nearest human by the sector graph
   and attack in range.
7. HUD: stage name, hold bar, humans alive per side, "YOU ARE A ZOMBIE (side)"; distance cull in the renderer (risk 1).
8. Tests: sim (bots-only rounds to the end on the converted map), mock (swap, cross-team credit, both-wiped draw, disconnect of the
   last human, late join), api/tsc checks, perf line at 32 and 64 players.
9. Hammer map build by skink52 (new map, lobby + booth + cache room from the Hellmatch template), in-game test checklist.

### Phase 2: content and classes
- Lost soul class (dash), class choice keys on respawn, proper view art (drawn in the Doom palette).
- 3-5 more Phase 1/2 maps with sidecars; map vote.
- Knockback tuning per class; zombie-only "rage" pickup at stage starts.

### Phase 3: player bosses
- A zombie player can take the boss over (first to press Use at the boss's spawn or picked by most human kills); AI drives it
  when the player dies or leaves.

### Phase 4: polish
- Loading screens, Workshop art and description (with Freedoom licence), music per stage, server stats (mgstat) hooks.

### Work order and resets
One task at a time (at most two in parallel with disjoint files), each with a progress file in `projects/hellmatch-ze-cs2/docs/`,
STATUS "Resume here" kept current so work resumes cleanly after a usage reset.
