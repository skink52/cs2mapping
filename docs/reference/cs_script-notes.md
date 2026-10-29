# cs_script notes (what the port scripts rely on)

CS2 has no VScript. Map logic that CS:GO did with VScript, `AddOutput` tricks, or entities CS2 dropped is rebuilt in **cs_script**
(JavaScript, `import { Instance, ... } from "cs_script/point_script"`). These are the patterns every port script in `ports/*/scripts/` uses.
For the full API see Valve's [Scripting API page](https://developer.valvesoftware.com/wiki/Counter-Strike_2_Workshop_Tools/Scripting_API).

## Wiring a script into a map

- Source: `content\csgo_addons\<addon>\maps\scripts\<name>.js` (or `scripts\<name>.js` in the older jail ports). It compiles to `.vjs_c`.
- A `point_script` entity with `cs_script` = `maps/scripts/<name>.vjs` (note `.vjs`, not `.js`) and a targetname, e.g. `<addon>_io_script`.
- Map I/O talks to it with `RunScriptInput` and the input name as the parameter:
  `trigger OnStartTouch → <addon>_io_script RunScriptInput Speed_3`. The script listens with `Instance.OnScriptInput("Speed_3", ({ activator, caller }) => ...)`.
  The activator is passed through, so `!activator` logic works.
- Because inputs are plain strings, one script can expose a family of inputs from a data table. The pipeline generates `Cmd_<n>`, `Score_<n>`,
  `Speed_<x>`, `Gravity_<scale>` and `PushIn_<n>`/`PushOut_<n>` from the map (`gen_script.py`, `push_tail.js`, `gravity.py`). `SetDest_<tele>__<dest>`
  and `Equip_<equip>` exist only in hand-written ports (mg_mario_party's `mario_io.js`, mg_50arenas' `a50_io.js`).
- `RunScriptInput` carries only the input name, no value: encode numbers in the name and parse them in the script.
- Hammer's build log warns "Parameter 'x' corresponds to an entity target name, but is sent to input 'RunScriptInput'..." when an input
  name happens to match an entity name. That warning is harmless.
- The command-line build compiles `maps/scripts/*.js` with the other addon assets (`build_maps.ps1`).

## Activators: pawn or controller

Triggers pass the **player pawn**. Some outputs pass the controller. Every script normalises:

```js
function toPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
```

Per-player state is keyed by `pawn.GetPlayerController().GetPlayerSlot()` and cleared in `Instance.OnPlayerReset` (respawn, team
change or round restart) and `OnPlayerDisconnect`.

## Ticking

`Instance.SetThink(fn)` + `Instance.SetNextThink(Instance.GetGameTime())` runs `fn` every tick. Only keep it running while something
needs it: the generated scripts share one think loop with a list of thinkers, and stop asking for the next tick when none are active.

## Reading player input (game_ui is dead)

`pawn.IsInputPressed(CSInputs.FORWARD | BACK | LEFT | RIGHT | JUMP | DUCK | USE | WALK | ATTACK | ATTACK2 ...)`.
The vehicle scripts **poll every tick and diff against their own state** instead of relying on `WasInputJustPressed`. A poll can be a
tick late, but it can't miss a release. A missed release would leave a thruster running forever.
`pawn.GetEyeAngles()` gives the view direction (yaw for "forward").

## Moving things

- Players: `pawn.Teleport({ position, angles, velocity })` and `pawn.Move({ velocity })` / `pawn.Move({ position })`. `Move` keeps
  interpolation. Some scripts keep `Teleport` as a fallback flag in case `Move` looks rubber-bandy.
- Writing angles to a player also turns their body. For a vehicle camera, set only the position and let the pilot aim with the mouse (helicopter).
- `pawn.SetEyeAngles(angles)` after a teleport, to face the destination like `trigger_teleport` does.
- Physics props: setting velocity on a physics box loses to floor friction. For a box that has to slide (Mario Party's chain chomp),
  freeze its motion and move it with the script each tick. Script-flown projectiles (bullet bills) also stay motion-disabled and are
  moved each tick, with `Instance.TraceLine({ start, end, ignoreEntity, ignorePlayers })` to stop them at walls.
- Ground movement speed (player_speedmod replacement): set the horizontal velocity from the keys every tick while on the ground
  (`pawn.GetGroundEntity()`). Scale by the **held weapon's** run speed (`pawn.GetActiveWeapon().GetClassName()` → table), because CS:GO's
  speedmod scaled the weapon's max speed. Pre-multiply by `1 / (1 - 5.2/64)`, because the player's own movement applies `sv_friction 5.2`
  to the velocity you set before it moves.
- Gravity (trigger_gravity replacement): while airborne, add back `(1 - scale) * 800 * dt` of vertical velocity each tick.

## Weapons

- `pawn.GiveNamedItem("weapon_x")`. CS2 gives a duplicate if the player already has one, so check first:
  `pawn.FindWeapon("weapon_x")`, or `pawn.FindWeaponBySlot(CSGearSlot.KNIFE)` for knives (knife class names vary).
- `pawn.DestroyWeapons()` strips everything (spawn strip, `player_weaponstrip`).
- A weapon's targetname does **not** survive being picked up. To track a specific map weapon, watch the named entity while it's on the ground
  and record who takes it (`buff_new.js`).
- `pawn.GetActiveWeapon()?.GetData()` gives the CS weapon data (name, type, gear slot, price, damage...).
- `GiveNamedItem` doesn't fire the weapon's `OnPlayerPickup`, so a map output on pickup won't see script-given weapons.
- There's no setter for a player's speed multiplier. Ground speed is set through velocity (above); servers running CounterStrikeSharp can
  use a plugin that sets `VelocityModifier` instead.

## Entities and I/O from script

- `Instance.FindEntityByName`, `FindEntitiesByName`, `FindEntitiesByClass`.
- `Instance.EntFireAtName({ name, input, value, activator, delay })` / `EntFireAtTarget({ target, input, ... })`. For example `KillHierarchy` on a
  projectile also kills the trigger_hurt parented to it.
- `Instance.ConnectOutput(entity, "OnTrigger", cb)` to listen to an entity's output. The returned id goes to `DisconnectOutput` (Mario Party re-hooks its math_counters every round, because map entities respawn each round).
- `entity.SetEntityName(name)` replaces `!activator AddOutput "targetname x"` (filter_activator_name tricks).
- `entity.SetColor({ r, g, b, a })` replaces `Color` / `Alpha` / `rendermode` AddOutputs on players and props.

## Rounds, damage, score

- `Instance.OnRoundStart`, `OnRoundEnd`, `OnBeginRoundRestart` (reset per-round state). In CS2 map entities respawn each round, as in CS:GO,
  so anything hooked with `ConnectOutput` has to be hooked again in `OnRoundStart` (ba_jail_skylight's keypad, Mario Party's counters).
- Cancel or change a hit with `Instance.OnModifyPlayerDamage(ev => ({ abort: true }) | ({ damage: n }) | ({ damageFlags }))`. It runs after hitgroup
  multipliers and doesn't fire for zero-damage hits. The older `OnBeforePlayerDamage` is marked deprecated in Valve's `point_script.d.ts`
  (mg_fred_all's gate and the helicopter/vehicle scripts in ba_jail_skylight and jb_water_prison_cs2 still use it), as are `OnBeforeReload`/`OnReload`
  (use `OnScriptReload`). New scripts use `OnModifyPlayerDamage`.
- Map-specific gates (e.g. mg_fred_all's `EnableDamage`): a trigger fires `RunScriptInput <name>` on `<addon>_io_script`, the script sets a flag,
  the damage hook aborts hits while it's off, and `OnRoundStart` resets it.
- `controller.AddScore(n)` replaces `game_score`. It adds to the scoreboard's score column, not kills.
- `Instance.ServerCommand("...")` replaces `point_servercommand`. Chat lines sent this way show as "Console: …". Servers can block `say`
  from maps, in which case the chat line just doesn't appear.
- `math_counter` values reach outputs as floats ("5.000000"). Round them in script before comparing or passing to a `logic_case`.

## HUD overlays (env_screenoverlay replacement)

A `custom_hud_layout` entity points at `panorama/layout/custom_game/<x>.xml` (+ `styles/custom_game/<x>.css`). The script shows and hides
panels by id (`Show_<overlay>` / `Hide_<overlay>`). See `ports/mg_mario_party/panorama/` and `scripts/overlays.js`.

## Debugging

`Instance.Msg("...")` writes to the console. `Instance.DebugScreenText`, `DebugLine`, `DebugBox` and `DebugSphere` draw in game. `OnScriptReload`
keeps state through a hot reload when the `.js` is recompiled while the map is running.

# Patterns from the original addons

The sections below come from the games written entirely in cs_script (Hellmatch, Space Racer, mg_trenchwarfare, Puppet Brawl, mg_deku_tree).
They apply just as well to port scripts. Methods are from Valve's `point_script.d.ts`, which is kept in `create/test/` for type-checking.

## Kills, rounds and score

- **A real kill from script** (killfeed, scoreboard, rank plugins):
  `victim.TakeDamage({ damage: 1000, attacker, inflictor: attacker, damageTypes: CSDamageTypes.BULLET, damageFlags: CSDamageFlags.FORCE_DEATH | CSDamageFlags.IGNORE_ARMOR })`.
  Let it through your own `OnModifyPlayerDamage` gate. If the attacker's pawn is dead, pass its controller. `attacker` undefined = world kill (no −1).
- Scripted kills need `mp_respawn_immunitytime 0` (immunity blocks them), `mp_teammates_are_enemies 1` (otherwise same-side kills are teamkills, −1),
  and respawn cvars (`mp_respawn_on_death_t/ct 1`) if players should come back. Skip kills during warmup.
- Don't kill with `Kill()` or a `trigger_hurt` when credit matters (no attacker). For thrown/physics kills remember the last hitter (dodgeball: `OnDamaged` activator).
- Queue kill-share kills one every few ticks so the killfeed rolls; drop or give to world any queued kill whose victim's or killer's slot changed hands
  (that bug once turned real kills off for a whole map).
- Assists: mg_trenchwarfare's design assumes CS2 counts an assist only when the assisting player dealt a sizeable non-lethal share first
  (it gives ≥55 damage). **Unverified**: a design choice in that project's notes, not confirmed in game.
- **Hiding the killer** (cs2mapTTT, mock-tested only): in `OnModifyPlayerDamage`, when a player hit would be lethal (`damage >= victim.GetHealth()`), return
  the damage with `damageFlags | PREVENT_DEATH`; in `OnPlayerDamage`, if the victim is left on ≤1 hp, queue a world kill for the next tick
  (`TakeDamage({ damage: 1000, damageFlags: FORCE_DEATH | IGNORE_ARMOR })`, no attacker, behind a re-entry flag). The killfeed shows only the death;
  keep the real attacker from `OnPlayerDamage` for your own scoring (`AddScore`). Armor can still save the victim (health > 1), which is correct.
- Hidden kill credit leaks through the scoreboard if you `AddScore` the real killer during the round: hold score changes per player and apply them in
  `OnRoundEnd` (cs2mapTTT). Whether CS2 still gives an assist to an earlier hitter on a world kill is untested.
- **Hiding CS2's own HUD:** `Instance.EntFireAtTarget({ target: pawn, input: "SetHUDVisibility", value: false })` (`true` brings it back). All or nothing;
  the map's custom HUD stays. Used in game by the Dogfight addon (`flightNativeHud`, default on after a player test: "way better"); it re-sends it on every
  spawn because a spawn can give the HUD back. It's a server-side pawn input, not a client cvar, so it shouldn't need `sv_cheats` (assumed; Dogfight's
  tests were standalone). Dogfight skips it when a server plugin owns the HUD bits. Confirmed in CS2's server.dll (29 Oct 2026 build) as a
  `CBasePlayerPawn` input next to `SetFogController` and `SetHealth`; the pawn's networked `m_iHideHUD` is what it sets. cs2mapTTT uses it to drop the killfeed and draws its own health/ammo/crosshair.
- Without that input, the killfeed can't be removed: CS2's HUD draws over custom HUDs, and the client cvar `cl_drawhud_force_deathnotices -1` via
  `ClientCommand` is unreliable and may persist on the player's client. A HUD mask over the feed area is untested.
- Respawn only in some phases (prep/warmup): flip `mp_respawn_on_death_t/ct` from script per phase (cs2mapTTT).
- Round winner without an `info_map_parameters`: `mp_default_team_winner_no_objective 2|3`, `mp_ignore_round_win_conditions 0`, `SetRoundRemainingTime(1)` (cs2mapTTT fallback, unverified).
- A slot can change hands with no disconnect event: compare the controller object per slot each tick and reset per-player state when it changes (cs2mapTTT).
- After `TakeDamage`, check `victim.IsAlive()`; if the victim survived, log once that a scripted kill was blocked (plugin or damage settings)
  (Space Racer). Space Racer kills with `CSDamageTypes.VEHICLE` (killfeed icon unverified).
- `Instance.OnPlayerKill` also fires for deaths the script didn't cause (admin slay, world): update the game's own state there too (Hellmatch).
- Respawn watchdog: after a scripted kill in a respawn mode, wait for `OnPlayerReset`; if CS2 hasn't respawned a still-present player within 8 s,
  count a failure, and after several in a row (Hellmatch 3, Space Racer 2) stop using real kills and log "check mp_respawn_on_death_t/ct".
  Switching off after one failure was tripped by bot kicks. One-life modes can batch the CS2 kills until the round ends and apply them in order.
- **End a round with a winner:** `EntFireAtName({ name: "<info_map_parameters name>", input: "FireWinCondition", value: CSRoundEndReason.TERRORISTS_WIN })`
  (or `CTS_WIN`, `DRAW`). Fallback: `Instance.SetRoundRemainingTime(1)`. Keep `mp_ignore_round_win_conditions 1` while the script runs the round and set it to `0` just before firing (Hellmatch, verified). Run the CS2 round clock ~15 s
  longer than the game's own clock.
- Round fallback: if CS2 hasn't ended the round ~20 s after the game finished (warmup, or a plugin blocked `FireWinCondition`), start the next
  game round from the script (Space Racer `ROUND_END_WAIT`). `OnRoundEnd(({ winningTeam, reason }))` logs what CS2 decided.
- `Instance.SetRoundRemainingTime(s)` / `GetRoundRemainingTime()` set and read the round clock directly (no need for a huge `mp_roundtime`).
  `IsWarmupPeriod()`, `IsFreezePeriod()`, `IsTeamIntroPeriod()` tell you the phase.
- Money off: `mp_playercashawards 0`, `mp_teamcashawards 0`, `mp_startmoney 0`, `mp_maxmoney 0`, `mp_afterroundmoney 0`, plus
  `mp_buy_anywhere 0`, `mp_buytime 0`, `mp_death_drop_gun 0` (Hellmatch, Space Racer). `sv_disable_radar 1` if the radar would show parked pawns.
  Offer a switch (Hellmatch `APPLY_CVARS`) so a server can keep its own config. Auto teams without the menu:
  `mp_force_assign_teams 1`, `sv_disable_teamselect_menu 1`. No starting pistols: `mp_t_default_secondary ""`, `mp_ct_default_secondary ""`.
- Talking to a server plugin: `Instance.ServerCommand("<plugin_cmd> {slot} …")` is the only channel.

## Players: parking, cameras and input

- **Pawn parking** (games where the player isn't the pawn): freeze the pawn with `pawn.SetMoveType(CSMoveType.NONE)` in a sealed booth, hide it,
  drive the view with a camera, read input from the pawn. Restore with `CSMoveType.WALK`. Abort all CS2 damage to parked pawns except your own kills.
  Hiding: `SetModelScale(0.02)` (Puppet Brawl, mg_trenchwarfare), or `DestroyWeapons()` then `SetColor({ r: 255, g: 255, b: 255, a: 0 })`, restored
  with `a: 255` (Hellmatch, Space Racer; "own body hidden" confirmed in game). Don't use the alpha method on a pawn that still holds weapons
  (see [cs2-gotchas](cs2-gotchas.md#scripts-players-rounds-and-plugins)).
- **Custom camera:** `const cam = pawn.GetCustomCamera(); cam.SetParent(undefined); cam.SetMode(CustomCameraMode.CONTROLLED)` and move it with `Teleport`/`Move`.
  `CONTROLLED_POSITION` keeps mouse look client-side (instant); `CONTROLLED` takes the angles from the entity; `FOLLOW_POSITION` takes
  `SetFollowConfig({ followEntity, cameraOffset, clipCameraOffset })` (chase cams). Restore with `SetMode(CustomCameraMode.DISABLED)` and the parent you
  stored with `cam.GetParent()` when taking it. Puppet Brawl also calls `pawn.SetEyeAngles(...)` on take and `Move`s the camera every tick; guard with
  `typeof pawn.GetCustomCamera === "function"`. Spectators and unassigned players have no pawn, so no custom camera (the HUD still shows).
- **FOV:** CS2's FOV 90 is horizontal at 4:3, so on 16:9 the real horizontal FOV is `2·atan(tan(45°)·(16/9)/(4/3))` ≈ 106.3°; framing distance =
  half-width / tan(hfov/2) (Puppet Brawl, Space Racer previews).
- **Lag:** with `CONTROLLED_POSITION` mouse look is client-side, but movement and shots simulated by the script arrive one round trip late; a map
  script can't lag-compensate (Hellmatch).
- After a teleport, `SetEyeAngles`, then ignore client yaw that differs by more than 2° for ~0.35 s while the client accepts the new view (Hellmatch).
- **Input:** `pawn.IsInputPressed(CSInputs.X)`, `WasInputJustPressed`, `WasInputJustReleased`. Usable: FORWARD, BACK, LEFT, RIGHT, JUMP, DUCK, USE, ATTACK, ATTACK2,
  RELOAD, WALK, LOOK_AT_WEAPON (F). The number keys (weapon slots) can't be read. Read edges every tick: 20 Hz polling missed quick taps.
  Masked calls (`IsInputPressed(A | B)`) are undocumented and unconfirmed: the helicopter port assumed ALL, Space Racer assumes "any of", detects it at runtime and
  logs which (`40_players.js justPressed`). Safest: test one key per call.
- **Chat commands:** `Instance.OnPlayerChat(({ player, text }) => …)`. Accept `!` and `/`. Scripts can't send private chat or hide the typed line
  (show private help on that player's HUD instead); script `say` speaks as the host and hits the chat flood limit, so space lines ~1 s apart.
  Strip `;` and `"` from anything sent with `ServerCommand("say …")`: player and track names go into a console command (Hellmatch, Space Racer).
- `Instance.ClientCommand(slot, "cl_hud_playercount_showcount 1")` is sent by Hellmatch once per arriving human; whether CS2 accepts it from a server
  is **unverified** (client commands from script have been unreliable, see the gotchas).
- `Instance.RegisterCheatCommand(name, cb)` adds console commands that work with `sv_cheats 1` (test hooks: `pb_cpu_match`).

## Spawning and moving things

- `pointTemplate.ForceSpawn(origin, angles)` returns the spawned `Entity[]`. **Pool** props (hide with a null model and park them) instead of spawning and killing;
  cap spawns per tick (Hellmatch: 20) to avoid hitches. Spawned props have blank names: `SetEntityName('<prefix><n>')` each one if it has to be an input
  target (e.g. a `SetSourceEntity` sound source). Template keys that worked for pools: `spawnflags 2`, `asynchronous 0`,
  `spawnGroupType INSERT_INTO_POINT_TEMPLATE_SPAWN_GROUP`, `clientOnlyEntityBehavior CREATE_FOR_CURRENTLY_CONNECTED_CLIENTS_ONLY`; source `prop_dynamic`
  with the null model, `solid 0`, `fademindist -1` (Hellmatch, Space Racer).
- Prop skins: `EntFireAtTarget({ target: prop, input: "Skin", value: n })`; `n` is the material-group order in the vmdl (default group = 0, then each
  `MaterialGroup`). Used for team colours (Space Racer) and animated textures (Hellmatch steps one group per frame every 8 tics).
- Teleport a prop only when it jumped more than ~400 u (Space Racer `TELEPORT_DIST`) or on a real reset; otherwise `Move`; send nothing for unchanged poses.
- `Instance.TraceLine({ ignoreEntity })` accepts an `Entity[]` (`point_script.d.ts`): mg_trenchwarfare's planes died on spawn until the ground trace ignored every aircraft.
- Teleport targets: any point entity works (the script reads its origin); `info_teleport_destination` is handy because Hammer draws the player hull.
- `Move` every tick for anything that moves (the client interpolates); `Teleport` only for the first placement and real jumps.
- `entity.Glow(color)` / `Unglow()` outline props (unverified in game).
- `point_worldtext` from script: `EntFireAtName({ name, input: "SetMessage", value })` (use " " for empty).
- Sounds: pre-placed `point_soundevent`s; `EntFireAtTarget({ target: snd, input: "SetSourceEntity", value: "<entity name>" })`, then `StartSound`/`StopSound`.
  Whether the listener is the parked pawn or the custom camera is unverified. Sounds at arbitrary points: a ring of pooled invisible anchor props
  teleported to the spot and used as the source (Hellmatch 24, Space Racer 16), with a cap on sounds per tick.
- **Bone-merged agent on a script-driven rig** (Puppet Brawl): a `point_template` holding an invisible `prop_dynamic` rig plus an agent `prop_dynamic` with parent = rig and
  Parent Attachment `!bonemerge` (both not solid). The template `!bonemerge` parenting is verified (agents animated in game once the rig kept its bones);
  the fallback (`FollowEntity` with the rig's name when `agent.GetParent() !== rig`) is untested. Scale with `SetModelScale` on the rig only.
  Clips: `EntFireAtTarget({ target: rig, input: "SetAnimationLooping" | "SetAnimationNotLooping", value: clipName })` only when the clip changes, and
  `SetPlaybackRate` (rounded, sent only on change; 0 during hitstop).

## HUD (custom_hud_layout)

- Methods: `SetHasClass(panelId, cls, on)` for everyone, `SetHasClassForPlayer(slot, panelId, cls, on)`, `SetDialogVariableString[ForPlayer]`, `Reset()`, `ResetForPlayer(slot)`,
  `SetInputCaptureEnabled(slot, on)` with `Instance.OnCustomHudClicked(({ player, layout, buttonId }) => …)`.
- Cost: cache what each panel (and each text line) last showed and send only changes. Hellmatch caps class changes at 600 per server tick and resumes next
  tick where it stopped; Space Racer uses 900 and refreshes half the players on even ticks, half on odd. Hellmatch measured the HUD at 54% of script time
  before line caching (64 players: 6.2 → 2.9 ms/tick, mock engine).
- Layout rules and Panorama quirks: [../creation/hud.md](../creation/hud.md).

## Performance

- CS2 warns "point_script … thinking for" on slow ticks. Native calls cost the most: don't call `IsValid` on every prop every tick (check every 8th/16th tick, or catch
  the error on use), cache `GetGameTime()` once per tick, skip moving things that haven't moved.
- Declare every field an object will ever have in its constructor (V8 hidden classes).
- Keep the think loop alive: reschedule in `finally`, and wrap each arena/instance's tick in its own try/catch.
- Log script time once a minute (`Date.now()` deltas). Space Racer: 64 players ≈ 0.14 ms and ~215 engine calls per tick (measured on the mock engine, not a CS2 server).
  Hellmatch: 64 players 2.1–2.5 ms/tick average, ~560 engine calls/tick, measured in its own mock, which runs the script in a `vm` context (see Testing:
  those figures are probably pessimistic).
- Guard optional API: `typeof Instance[name] === "function"` before hooking `On*` events, and disable the HUD after a few throws (the HUD API is marked
  experimental) (Puppet Brawl). Retry `init()` every few seconds until the map entities are found; re-arm it ~0.5 s after `OnRoundStart` and after
  `OnScriptReload` (`OnScriptReload({ before: () => { cleanup(); return null; }, after: () => init() })`).
- Puppet Brawl imports only the names it uses from `cs_script/point_script`, on the theory that a name the runtime doesn't export stops the script
  loading. **Unverified**: other working scripts import `CustomHudLayout` without trouble.

## Testing without CS2

- Type-check: `sh create/test/tscheck.sh <script.js>` (Valve's `point_script.d.ts`, needs `npm i -g typescript`).
- Smoke test: `node create/test/mock_point_script.mjs <script.js> [entities.json] players=16 seconds=300` runs the real script on a stand-in engine with
  joins, inputs, damage, kills, respawns, chat and a disconnect, and fails on any exception or call outside the API. `create/dump_entities.py <vmap> entities.json`
  gives it the map's named entities.
- Bigger games keep the rules in plain JS (`src/core/`, no engine calls) and the CS2 side separately (`src/cs2/`), so the game itself runs in Node for balance sims
  (see [../creation/guide.md](../creation/guide.md)). Run mocks as ES modules, not a `vm` context: Space Racer measured `vm` timings ~2.5× too slow.
  Hellmatch's published numbers come from a `vm`-context mock, so treat them as an upper bound. Profile hot spots with `node --cpu-prof`.
- Prove a performance change alters nothing: run the mock with a fixed seed and a trace of every engine call (positions, models, HUD classes, sounds) before
  and after, and diff the traces (Hellmatch, Space Racer). The create mock's trace/perf/churn/HUD checks: [`create/test/`](../../create/test/).

## Physics and odd entities (from the ports)

- **Carrying / tethering by velocity spring** (seen in workshop map jb_watermelon_v2, id 3480208667, its medibeam gun drags a live player; cs2mapTTT uses
  the same idea for props and bodies): each tick, `ent.Teleport({ velocity })` toward the hold point with speed = gain × distance (cap it), angular velocity 0.
  Velocity-only Teleports don't hit the "teleported props aren't drawn" problem. Drop when too far, or when the holder stands on the object.
- Seen in that map's scripts but not in our `point_script.d.ts` copy: `Instance.OnGameEvent("round_start", cb)`, player inputs `AddAttribute`/`RemoveAttribute`
  (attribute filters), weapon inputs `SetAmmoAmount`/`SetReserveAmmoAmount`. Check Valve's current `point_script.d.ts` before relying on them.
- **Server-side bodies** (cs2mapTTT, untested in game): a `point_template` of a `prop_ragdoll` (stock agent model); on death `ForceSpawn` at the pawn, `SetModel` to the
  victim's `GetModelName()`, copy the velocity. Death is routed through the `PREVENT_DEATH` → queued kill path so the pawn can be shrunk (`SetModelScale(0.02)`,
  restored on `OnPlayerReset`) before dying, to hide the client ragdoll.
- **Killfeed off on CounterStrikeSharp servers:** a `HookMode.Pre` `EventPlayerDeath` handler with `info.DontBroadcast = true` (CSSharp docs example).
  Clients get no death event; the server and rank plugins still do; the scoreboard reads networked stats (expected to keep updating, unverified).

- Physics props that must slide or chase (Mario Party's chain chomp): `DisableMotion`, then `Move` them every tick with `TraceBox` per axis to slide along walls.
  `phys_thruster` and setting velocity both lost to floor friction.
- Ball games: hits from `OnBulletImpact({ weapon, position, hitEntity })` and `OnKnifeAttack`, low gravity by measuring and cancelling the engine's gravity
  on the ball (see the gotchas). Frozen-spawn physics balls need a nudge from script.
- Grenades: CS2 triggers don't see them; track from `OnGrenadeThrow({ projectile })` and test segment-vs-box each tick.
- `game_ui` replacement for vehicles: test each key separately (combined masks are unconfirmed, see Input above), drive thrusters with Activate/Deactivate,
  limit turn rate by measuring yaw change (there is no angular-velocity read).
- Script flight (mg_trenchwarfare): Source pitch + is nose down; steer yaw and pitch separately (a slerp flipped through the vertical); the ground trace
  ignores all aircraft; touching the ground is a crash.
- AFK: activity = any input or a view change > ~2°; warn at 20 s, move to spectate at 30 s, only count idling while actually playing. Position-based AFK plugins
  flag parked pawns.

## Vehicle flight that feels good (from the Dogfight jet mode, used in mg_trenchwarfare tw33)

- Mouse aim: read the eye every tick, raw; turn the nose toward it with a slerp, proportional and capped: `step = min(turnRate(v)·dt, GAIN·angle·dt)`
  (GAIN 4–5). One slerp gives a straight nose path with no overshoot or stepping. Bank comes from the yaw rate (rate-limited),
  A/D add a free roll on top that never changes the nose.
- Turn law: `rate·(refSpeed/max(v, minSpeed))^0.6`, clamped; times a stall factor for slow aircraft.
- Send angles continuous with the last ones (`anglesNear`: unwrap pitch/yaw/roll, or the equivalent (180−p, y+180, r+180) triple), or a
  yaw of 180 flickers between +180 and −180.
- Never sum or slerp two nearly opposite directions for an aim (bounds "turn home" blend, a reversal): the result's great circle tips over the
  top and the aircraft climbs vertically. Blend heading and climb separately, and cap the aim to 90° off the heading for a level turn.
- Guns that converge on the crosshair: rebuild the FOLLOW_POSITION camera position (followed point + cameraOffset turned by the eye angles),
  trace along the eye, aim the rounds at the hit point within a few degrees of the nose.
- `SetNextThink` first in the think and try/catch per player: one exception otherwise stops the script until the next round.

