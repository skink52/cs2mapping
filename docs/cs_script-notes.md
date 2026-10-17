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
- `Instance.OnBeforePlayerDamage(e => ({ abort: true }))` cancels a hit (mg_fred_all's enemy-damage gate).
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
