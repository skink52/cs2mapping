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
- Because inputs are plain strings, one script can expose a family of inputs from a data table (`Speed_<x>`, `SetDest_<tele>__<dest>`,
  `Equip_<equip>`...). The pipeline generates those tables from the map.
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
  multipliers and doesn't fire for zero-damage hits. The older `OnBeforePlayerDamage` (mg_fred_all's gate) is marked deprecated in Valve's
  `point_script.d.ts`, as are `OnBeforeReload`/`OnReload` (use `OnScriptReload`).
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
- CS2 counted an **assist** only when the assisting player had dealt a sizeable non-lethal share first (≥55 damage worked).
- **End a round with a winner:** `EntFireAtName({ name: "<info_map_parameters name>", input: "FireWinCondition", value: CSRoundEndReason.TERRORISTS_WIN })`
  (or `CTS_WIN`, `DRAW`). Fallback: `Instance.SetRoundRemainingTime(1)`. Keep `mp_ignore_round_win_conditions 1` while the script runs the round and set it to `0` just before firing (Hellmatch, verified). Run the CS2 round clock ~15 s
  longer than the game's own clock.
- `Instance.SetRoundRemainingTime(s)` / `GetRoundRemainingTime()` set and read the round clock directly (no need for a huge `mp_roundtime`).
  `IsWarmupPeriod()`, `IsFreezePeriod()`, `IsTeamIntroPeriod()` tell you the phase.
- Money off: `mp_playercashawards 0`, `mp_teamcashawards 0`, `mp_startmoney 0`, `mp_maxmoney 0`, `mp_afterroundmoney 0`. Auto teams without the menu:
  `mp_force_assign_teams 1`, `sv_disable_teamselect_menu 1`. No starting pistols: `mp_t_default_secondary ""`, `mp_ct_default_secondary ""`.
- Talking to a server plugin: `Instance.ServerCommand("<plugin_cmd> {slot} …")` is the only channel.

## Players: parking, cameras and input

- **Pawn parking** (games where the player isn't the pawn): freeze the pawn with `pawn.SetMoveType(CSMoveType.NONE)` in a sealed booth, hide it with
  `SetModelScale`, drive the view with a camera, read input from the pawn. Restore with `CSMoveType.WALK`. Abort all CS2 damage to parked pawns except your own kills.
- **Custom camera:** `const cam = pawn.GetCustomCamera(); cam.SetParent(undefined); cam.SetMode(CustomCameraMode.CONTROLLED)` and move it with `Teleport`/`Move`.
  `CONTROLLED_POSITION` keeps mouse look client-side (instant); `CONTROLLED` takes the angles from the entity; `FOLLOW_POSITION` takes
  `SetFollowConfig({ followEntity, cameraOffset, clipCameraOffset })` (chase cams). Restore with `SetMode(CustomCameraMode.DISABLED)` and `SetParent(pawn)`.
- **Input:** `pawn.IsInputPressed(CSInputs.X)`, `WasInputJustPressed`, `WasInputJustReleased`. Usable: FORWARD, BACK, LEFT, RIGHT, JUMP, DUCK, USE, ATTACK, ATTACK2,
  RELOAD, WALK, LOOK_AT_WEAPON (F). The number keys (weapon slots) can't be read. Read edges every tick: 20 Hz polling missed quick taps.
  Masked calls (`IsInputPressed(A | B)`) are undocumented and unconfirmed: the helicopter port assumed ALL, Space Racer assumes "any of", detects it at runtime and
  logs which (`40_players.js justPressed`). Safest: test one key per call.
- **Chat commands:** `Instance.OnPlayerChat(({ player, text }) => …)`. Accept `!` and `/`. Scripts can't send private chat or hide the typed line;
  script `say` speaks as the host and hits the chat flood limit, so space lines ~1 s apart.
- `Instance.RegisterCheatCommand(name, cb)` adds console commands that work with `sv_cheats 1` (test hooks: `pb_cpu_match`).

## Spawning and moving things

- `pointTemplate.ForceSpawn(origin, angles)` returns the spawned `Entity[]`. **Pool** props (hide with a null model and park them) instead of spawning and killing;
  cap spawns per tick (Hellmatch: 20) to avoid hitches.
- `Move` every tick for anything that moves (the client interpolates); `Teleport` only for the first placement and real jumps.
- `entity.Glow(color)` / `Unglow()` outline props (unverified in game).
- `point_worldtext` from script: `EntFireAtName({ name, input: "SetMessage", value })` (use " " for empty).
- Sounds: pre-placed `point_soundevent`s; `EntFireAtTarget({ target: snd, input: "SetSourceEntity", value: "<entity name>" })`, then `StartSound`/`StopSound`.
  Whether the listener is the parked pawn or the custom camera is unverified.
- **Bone-merged agent on a script-driven rig** (Puppet Brawl): a `point_template` holding an invisible `prop_dynamic` rig plus an agent `prop_dynamic` with parent = rig and
  Parent Attachment `!bonemerge` (both not solid). Fallback: the `FollowEntity` input. Unverified.

## HUD (custom_hud_layout)

- Methods: `SetHasClass(panelId, cls, on)` for everyone, `SetHasClassForPlayer(slot, panelId, cls, on)`, `SetDialogVariableString[ForPlayer]`, `Reset()`, `ResetForPlayer(slot)`,
  `SetInputCaptureEnabled(slot, on)` with `Instance.OnCustomHudClicked(({ player, layout, buttonId }) => …)`.
- Cost: cache what each panel last showed and send only changes. Hellmatch caps class changes at 600 per server tick and resumes next tick where it stopped.
- Layout rules and Panorama quirks: [../creation/hud.md](../creation/hud.md).

## Performance

- CS2 warns "point_script … thinking for" on slow ticks. Native calls cost the most: don't call `IsValid` on every prop every tick (check every 8th/16th tick, or catch
  the error on use), cache `GetGameTime()` once per tick, skip moving things that haven't moved.
- Declare every field an object will ever have in its constructor (V8 hidden classes).
- Keep the think loop alive: reschedule in `finally`, and wrap each arena/instance's tick in its own try/catch.
- Log script time once a minute (`Date.now()` deltas). Space Racer: 64 players ≈ 0.14 ms and ~215 engine calls per tick (measured on the mock engine, not a CS2 server).

## Testing without CS2

- Type-check: `sh create/test/tscheck.sh <script.js>` (Valve's `point_script.d.ts`, needs `npm i -g typescript`).
- Smoke test: `node create/test/mock_point_script.mjs <script.js> [entities.json] players=16 seconds=300` runs the real script on a stand-in engine with
  joins, inputs, damage, kills, respawns, chat and a disconnect, and fails on any exception or call outside the API. `create/dump_entities.py <vmap> entities.json`
  gives it the map's named entities.
- Bigger games keep the rules in plain JS (`src/core/`, no engine calls) and the CS2 side separately (`src/cs2/`), so the game itself runs in Node for balance sims
  (see [../creation/guide.md](../creation/guide.md)). Run mocks as ES modules, not a `vm` context (timings were ~2.5× too slow).

## Physics and odd entities (from the ports)

- Physics props that must slide or chase (Mario Party's chain chomp): `DisableMotion`, then `Move` them every tick with `TraceBox` per axis to slide along walls.
  `phys_thruster` and setting velocity both lost to floor friction.
- Ball games: hits from `OnBulletImpact({ weapon, position, hitEntity })` and `OnKnifeAttack`, low gravity by measuring and cancelling the engine's gravity
  on the ball (see the gotchas). Frozen-spawn physics balls need a nudge from script.
- Grenades: CS2 triggers don't see them; track from `OnGrenadeThrow({ projectile })` and test segment-vs-box each tick.
- `game_ui` replacement for vehicles: test each key separately (the helicopter port treated a combined mask as ALL; Space Racer probes it at runtime — see Input above; unconfirmed in CS2), drive thrusters with Activate/Deactivate, limit turn rate by
  measuring yaw change (there is no angular-velocity read).
- AFK: activity = any input or a view change > ~2°; warn at 20 s, move to spectate at 30 s, only count idling while actually playing. Position-based AFK plugins
  flag parked pawns.
