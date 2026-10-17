// helicopter.js  --  ba_jail_skylight
//
// Same idea as bumper_cars.js, but for the heli. A game_ui replacement that
// reads the pilot's keys and drives six phys_thrusters instead of four.
// This is a SEPARATE script on its own point_script - it does not touch
// bumper_cars.js and the two can run side by side.
//
//   W / S / A / D  ->  heli_thruster_forward / backward / left / right
//   SPACE          ->  heli_thruster_up
//   CROUCH         ->  heli_thruster_down
//   +USE           ->  let go of the controls
//
// Every movement key is a thruster now, so +use is the only key left to get out
// with. That's the same key that gets you in, which needs care: the button's
// OnPressed and this script's own key polling both fire on that one press, and
// nothing guarantees which lands first. REENTRY_COOLDOWN below is what stops a
// single tap dropping you out and putting you straight back in.
//
// Entry is +use on a func_button named heli_control. The script hooks that
// button's OnPressed itself, so the button needs no outputs wired in Hammer.
//
// Like the cars, the pilot doesn't move - they stand at the controls and fly it
// remotely. Optionally their view is taken over by a camera on the heli.
//
// The pilot CAN'T shoot by default. While their guns are locked they're held on
// their knife and any damage they'd deal is cancelled. Firing the script input
// EnableHeliGuns unlocks them for the rest of the round - see "pilot's weapons"
// below for the Hammer wiring. Every new round starts locked again.

import {
  Instance, CSInputs, CSMoveType, CSGearSlot, CSWeaponType, CustomCameraMode,
} from "cs_script/point_script";

// ----- the aircraft ---------------------------------------------------------
// Copy the whole block to add a second one; nothing else needs changing.
const HELIS = [
  {
    body:         "heli",            // the physics body the thrusters push
    control:      "heli_control",    // func_button the pilot presses
    cameraAnchor: "heli_cam",        // optional: point entity parented to the heli
    exitTeleport: "",                // optional: marker to drop the pilot on
    thrusters: {
      forward:  "heli_thruster_forward",
      backward: "heli_thruster_backward",
      left:     "heli_thruster_left",
      right:    "heli_thruster_right",
      up:       "heli_thruster_up",
      down:     "heli_thruster_down",
    },
  },
];

// ----- config ---------------------------------------------------------------
const DEBUG = false;   // set false once it's working

const CONTROLS = [
  { input: CSInputs.FORWARD, key: "forward"  },
  { input: CSInputs.BACK,    key: "backward" },
  { input: CSInputs.LEFT,    key: "left"     },
  { input: CSInputs.RIGHT,   key: "right"    },
  { input: CSInputs.JUMP,    key: "up"       },
  { input: CSInputs.DUCK,    key: "down"     },
];

const FREEZE_PILOT = true;    // MOVETYPE_NONE while at the controls
const EXIT_ON_USE  = true;    // +use to let go
// Crouch is the descend thruster now. Turning this on would eject the pilot
// every time they tried to lose altitude.
const EXIT_ON_DUCK = false;

// Seconds after letting go before the same player can take the controls again.
// Without this, the +use that gets you out can be seen by the button as a fresh
// press and put you straight back in.
const REENTRY_COOLDOWN = 0.75;

// ----- pilot's weapons ------------------------------------------------------
// By default the pilot can't fire anything while they're at the controls. The
// weapon they had out is put away, they're kept on their knife (any attempt to
// switch back is undone the next tick), and damage they deal is cancelled. When
// they let go they get the weapon they had out handed back.
//
// Unlocking is driven from the map. In Hammer:
//   1. Give this point_script a name - it has none at the moment. heli_script
//      is used below. (Don't target "Heli" - that's the func_physbox.)
//   2. On helib3 add:  OnPressed -> heli_script -> RunScriptInput
//      with the parameter set to EnableHeliGuns. Match the delay on the
//      existing "Heli enable" output (15s) if the guns should come on with it.
// Because it's driven by helib3's OnPressed, it can only happen once the button
// has been unlocked - a locked press fires OnUseLocked, not OnPressed.
//
// Unlocked lasts until the end of the round, for whoever's flying. The next
// round starts locked again, the same way everything else here resets.
const PILOT_GUNS_LOCKED_BY_DEFAULT = true;
const ENABLE_GUNS_INPUT  = "EnableHeliGuns";    // RunScriptInput parameter
const DISABLE_GUNS_INPUT = "DisableHeliGuns";   // optional: lock them again
// Cancel any damage a locked pilot deals. Covers the knife, and anything that
// manages to get a shot off before the switch to the knife lands.
const BLOCK_LOCKED_PILOT_DAMAGE = true;

// ----- the view -------------------------------------------------------------
// Moves the pilot's own view onto the heli, which is the closest CS2 gets to a
// first-person feed.
//
// Uses the custom camera API from the 9 Sep 2026 CS2 update:
// pawn.GetCustomCamera() + SetMode(CustomCameraMode...). That update removed
// the older GetCamera / SetEnabled / SetIsControllingAngles calls this script
// used to make, which is what broke it.
const PILOT_CAMERA = true;
// How the view is attached to the heli:
//   "follow"   - the game itself keeps the view on the camera anchor and the
//                pilot aims with their mouse. Nothing to update each tick, so
//                it should be the smoothest. Use this one.
//   "position" - same result, but the script moves the camera onto the anchor
//                every tick. That's how this worked before the update. Try it
//                if "follow" misbehaves.
//   "locked"   - like "position", but the script also sets the view's angles,
//                so the view turns with the heli like sitting in the nose. On
//                the old API this spun the pilot's BODY round too. It hasn't
//                been tried on the new one.
const CAMERA_MODE = "follow";
// "follow" only: moves the view back from the anchor, relative to where the
// pilot is looking. x is forward, y is left, z is up. All zeros puts the view
// right on the anchor; { x: -200, y: 0, z: 60 } gives a chase view from behind
// and above. The game pulls it in so it doesn't clip into walls.
const CAMERA_FOLLOW_OFFSET = { x: -50, y: 0, z: -25 };
// Used only when there's no cameraAnchor entity: units forward of, and above,
// the heli body's own origin. ("follow" uses only the "up" part.)
const CAMERA_FALLBACK = { forward: 48, up: 12 };

// "position" and "locked" only. If the view points the wrong way, work through
// these in order. The heli_cam_debug console command shows what the script is
// actually reading:
//
//   1. CAMERA_UNPARENT - if the camera is attached to the pilot's own body,
//      anything absolute we set on it gets re-based to wherever they happen to
//      be facing.
//   2. CAMERA_ANGLE_OFFSET - dial the direction in from here instead of
//      guessing at the anchor's rotation in Hammer. yaw 90 / 180 / -90 first.
//   3. CAMERA_ANGLE_SOURCE "body" - take the facing off the heli itself and
//      ignore the anchor's rotation entirely.
//   4. CAMERA_MODE "follow" - stop fighting it and let the pilot aim with the
//      mouse from the heli's position. Often nicer to fly anyway.
const CAMERA_UNPARENT = true;
const CAMERA_ANGLE_SOURCE = "anchor";   // "anchor" | "body"
const CAMERA_ANGLE_OFFSET = { pitch: 0, yaw: 0, roll: 0 };

const EXIT_TELEPORT_FACING = true;
// ----------------------------------------------------------------------------

Instance.Msg("[heli] script loaded");

const ZERO = { x: 0, y: 0, z: 0 };

// body name -> heli state
const helis = new Map();
// player slot -> body name
const pilotHeli = new Map();
// player slot -> game time before which they can't take the controls again
const reentryBlocked = new Map();
// player slot -> { parent, unparented } captured when we took that player's
// camera. Keyed by slot, not by heli: the pawn gets replaced on respawn and
// round change, and a handle captured at entry is stale by the time we let go.
const cameraHeld = new Map();
// Set once we've reported that this game build has no custom camera API.
let cameraApiWarned = false;
// player slot -> { restore, warned } for a pilot whose guns we've put away.
//   restore : CSGearSlot of the weapon they had out, handed back when they let go
//   warned  : already logged that they have no knife to be held on
const holstered = new Map();
// Whether pilots may shoot. Reset to the default every round.
let pilotGunsEnabled = !PILOT_GUNS_LOCKED_BY_DEFAULT;
// ConnectOutput ids, cleared on reload so hooks don't stack
let outputHooks = [];

function log(text) { if (DEBUG) Instance.Msg(`[heli] ${text}`); }

function copyVector(v) { return { x: v.x, y: v.y, z: v.z }; }

function live(entity) { return entity && entity.IsValid() ? entity : undefined; }

function wrapDegrees(degrees) {
  let d = degrees % 360;
  if (d > 180) d -= 360;
  if (d < -180) d += 360;
  return d;
}

/** Cached name lookup that re-resolves once the handle goes stale. */
function resolve(heli, slotName, entityName) {
  const cached = live(heli.cache[slotName]);
  if (cached) return cached;
  if (!entityName) return undefined;

  heli.cache[slotName] = live(Instance.FindEntityByName(entityName));
  return heli.cache[slotName];
}

function heliBody(heli) { return resolve(heli, "body", heli.config.body); }

// ----- discovery ------------------------------------------------------------

function discover() {
  for (const config of HELIS) {
    let heli = helis.get(config.body);
    if (!heli) {
      heli = {
        config,
        cache: {},          // name slot -> entity handle
        active: {},         // thruster key -> is it running
        pilotSlot: -1,
        lastDuck: false,
        lastUse: false,
      };
      helis.set(config.body, heli);
    }

    heli.cache = {};   // force a fresh resolve of everything

    for (const control of CONTROLS) {
      const name = config.thrusters[control.key];
      if (!name) continue;

      // Anything left running from before.
      if (heli.pilotSlot < 0) {
        heli.active[control.key] = false;
        Instance.EntFireAtName({ name, input: "Deactivate" });
      }
    }

    if (DEBUG) report(heli);
  }
}

function report(heli) {
  const config = heli.config;
  const missing = [];

  if (!heliBody(heli)) missing.push(`body "${config.body}"`);
  if (!resolve(heli, "control", config.control)) missing.push(`button "${config.control}"`);

  for (const control of CONTROLS) {
    const name = config.thrusters[control.key];
    if (!name || !Instance.FindEntityByName(name)) missing.push(`thruster "${name ?? control.key}"`);
  }

  const anchor = config.cameraAnchor
    ? (Instance.FindEntityByName(config.cameraAnchor) ? "ok" : "MISSING (using fallback offset)")
    : "none (using fallback offset)";

  log(`${config.body}: camera anchor ${anchor}` +
      (missing.length ? ` | MISSING: ${missing.join(", ")}` : " | all entities found"));
}

/**
 * Hook the +use button straight from script. func_button fires OnPressed with
 * the player who pressed it as the activator, so nothing needs wiring in Hammer.
 */
function hookControls() {
  for (const id of outputHooks) {
    try { Instance.DisconnectOutput(id); } catch (error) { /* already gone */ }
  }
  outputHooks = [];

  for (const heli of helis.values()) {
    const name = heli.config.control;
    if (!name) continue;

    for (const button of Instance.FindEntitiesByName(name)) {
      const hook = Instance.ConnectOutput(button, "OnPressed",
        ({ activator }) => enterHeli(pawnFromEntity(activator), heli));

      if (hook !== undefined) {
        outputHooks.push(hook);
        log(`${heli.config.body}: entry hooked to "${name}" OnPressed`);
      }
    }
  }
}

function pawnFromEntity(entity) {
  if (!live(entity)) return undefined;

  for (const controller of Instance.GetAllPlayerControllers()) {
    const pawn = controller.GetPlayerPawn();
    if (pawn && pawn === entity) return pawn;
  }
  return undefined;
}

/** Player slot for a pawn OR a controller, e.g. a damage event's attacker. */
function slotOfEntity(entity) {
  if (!live(entity)) return undefined;

  for (const controller of Instance.GetAllPlayerControllers()) {
    if (controller === entity || controller.GetPlayerPawn() === entity) {
      return controller.GetPlayerSlot();
    }
  }
  return undefined;
}

// ----- pilot's weapons ------------------------------------------------------

function isKnife(weapon) {
  // By weapon TYPE, not gear slot - the zeus shares the knife slot and fires.
  const data = live(weapon) ? weapon.GetData() : undefined;
  return !!data && data.GetType() === CSWeaponType.KNIFE;
}

function gearSlotOf(weapon) {
  const data = live(weapon) ? weapon.GetData() : undefined;
  return data ? data.GetGearSlot() : CSGearSlot.INVALID;
}

function findKnife(pawn) {
  // FindWeaponBySlot hands back one item per slot, and that could be the zeus,
  // so fall back to looking the default knives up by name.
  const candidates = [
    pawn.FindWeaponBySlot(CSGearSlot.KNIFE),
    pawn.FindWeapon("weapon_knife"),
    pawn.FindWeapon("weapon_knife_t"),
  ];
  return candidates.find(isKnife);
}

/**
 * Keep a pilot whose guns are locked on their knife. Runs every tick they're at
 * the controls, so switching weapons (1/2/4, scroll) is undone before anything
 * they switch to has finished deploying and can fire.
 */
function holsterGuns(pawn, slot) {
  const active = live(pawn.GetActiveWeapon());
  const onKnife = isKnife(active);

  let held = holstered.get(slot);
  if (!held) {
    // What they had out when their guns were first put away - once only, so
    // a switch they try mid-flight doesn't overwrite it.
    held = { restore: active && !onKnife ? gearSlotOf(active) : CSGearSlot.INVALID, warned: false };
    holstered.set(slot, held);
  }

  if (onKnife) return;

  const knife = findKnife(pawn);
  if (knife) {
    pawn.SwitchToWeapon(knife);
  } else if (!held.warned) {
    held.warned = true;
    log(`slot ${slot} has no knife to hold them on - relying on the damage block`);
  }
}

/**
 * Forget that we put this pilot's guns away. Pass the pawn to also switch them
 * back to what they had out; leave it undefined when there's nothing sensible
 * to switch (died, respawned, round change).
 */
function unholsterGuns(slot, pawn) {
  const held = holstered.get(slot);
  if (!held) return;
  holstered.delete(slot);

  if (held.restore === CSGearSlot.INVALID) return;
  if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) return;

  const weapon = live(pawn.FindWeaponBySlot(held.restore));
  if (weapon) pawn.SwitchToWeapon(weapon);
}

function setPilotGuns(enabled, reason) {
  if (pilotGunsEnabled === enabled) return;
  pilotGunsEnabled = enabled;
  // The think loop does the actual holstering / handing back on the next tick.
  log(`pilot weapons ${enabled ? "UNLOCKED" : "locked"} (${reason})`);
}

// ----- flying ---------------------------------------------------------------

function setThruster(heli, key, on) {
  if (heli.active[key] === on) return;
  heli.active[key] = on;

  const name = heli.config.thrusters[key];
  if (!name) return;

  Instance.EntFireAtName({ name, input: on ? "Activate" : "Deactivate" });
  if (DEBUG) log(`${heli.config.body} ${key} -> ${on ? "Activate" : "Deactivate"}`);
}

/** Where the pilot's view should sit this tick. */
function cameraTransform(heli) {
  const anchor = resolve(heli, "cameraAnchor", heli.config.cameraAnchor);
  const body = heliBody(heli);

  // Position: the anchor if there is one, otherwise out in front of the body.
  let position;
  if (anchor) {
    position = copyVector(anchor.GetAbsOrigin());
  } else if (body) {
    const origin = body.GetAbsOrigin();
    const radians = body.GetAbsAngles().yaw * Math.PI / 180;
    position = {
      x: origin.x + Math.cos(radians) * CAMERA_FALLBACK.forward,
      y: origin.y + Math.sin(radians) * CAMERA_FALLBACK.forward,
      z: origin.z + CAMERA_FALLBACK.up,
    };
  } else {
    return undefined;
  }

  // Facing: sourced separately, so a mis-rotated anchor can't break the view.
  const source = CAMERA_ANGLE_SOURCE === "body" ? body : (anchor ?? body);
  if (!source) return undefined;

  const base = source.GetAbsAngles();
  return {
    position,
    angles: {
      pitch: base.pitch + CAMERA_ANGLE_OFFSET.pitch,
      yaw: wrapDegrees(base.yaw + CAMERA_ANGLE_OFFSET.yaw),
      roll: (CAMERA_MODE === "locked" ? base.roll : 0) + CAMERA_ANGLE_OFFSET.roll,
    },
  };
}

/**
 * The pawn's custom camera, or undefined if this game build doesn't have that
 * API. Checked rather than assumed, so a future rename costs the view only,
 * not the whole think loop. A missing function here is what stopped the heli
 * flying properly after the September update.
 */
function cameraFor(pawn) {
  if (typeof pawn.GetCustomCamera !== "function") {
    if (!cameraApiWarned) {
      cameraApiWarned = true;
      Instance.Msg("[heli] this build has no GetCustomCamera - flying without the pilot camera");
    }
    return undefined;
  }
  return live(pawn.GetCustomCamera());
}

/** "follow" mode: which entity the game should track, and the offset from it. */
function followTarget(heli) {
  const anchor = resolve(heli, "cameraAnchor", heli.config.cameraAnchor);
  if (anchor) return { entity: anchor, offset: copyVector(ZERO) };

  // The follow offset doesn't turn with the heli, so only the height is usable.
  const body = heliBody(heli);
  if (body) return { entity: body, offset: { x: 0, y: 0, z: CAMERA_FALLBACK.up } };

  return undefined;
}

/** Per-tick camera move, for the "position" and "locked" modes. */
function updateCamera(heli, pawn) {
  // "follow" is tracked by the game itself.
  if (!PILOT_CAMERA || CAMERA_MODE === "follow") return;

  // Always off the current pawn - a handle cached at entry doesn't survive a
  // respawn, and a stale one silently stops updating.
  const camera = cameraFor(pawn);
  if (!camera) return;

  const transform = cameraTransform(heli);
  if (!transform) return;

  // Position only, unless the locked view was explicitly asked for.
  const move = { position: transform.position };
  if (CAMERA_MODE === "locked") move.angles = transform.angles;

  camera.Teleport(move);
}

function enterHeli(pawn, heli) {
  if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) return;
  if (heli.pilotSlot >= 0) return;

  const controller = pawn.GetPlayerController();
  if (!controller) return;

  const slot = controller.GetPlayerSlot();
  if (pilotHeli.has(slot)) return;

  // The +use that just let them go is the same press the button reports.
  if (Instance.GetGameTime() < (reentryBlocked.get(slot) ?? 0)) return;

  heli.pilotSlot = slot;
  pilotHeli.set(slot, heli.config.body);

  // Seed the edge detect so holding crouch on the way in doesn't eject them.
  heli.lastDuck = pawn.IsInputPressed(CSInputs.DUCK);
  heli.lastUse = pawn.IsInputPressed(CSInputs.USE);

  if (FREEZE_PILOT) pawn.SetMoveType(CSMoveType.NONE);

  // Straight away rather than waiting for the next think.
  if (!pilotGunsEnabled) holsterGuns(pawn, slot);

  takeCamera(pawn, slot, heli);

  log(`${controller.GetPlayerName()} took the controls of ${heli.config.body}`);
}

function takeCamera(pawn, slot, heli) {
  if (!PILOT_CAMERA) return;

  const camera = cameraFor(pawn);
  if (!camera) return;

  if (CAMERA_MODE === "follow") {
    const target = followTarget(heli);
    if (!target) return;

    cameraHeld.set(slot, { parent: undefined, unparented: false });
    // Config first, then switch the mode on, so the first frame is already
    // in the right place.
    camera.SetFollowConfig({
      followEntity: target.entity,
      followOffset: target.offset,
      cameraOffset: copyVector(CAMERA_FOLLOW_OFFSET),
      clipCameraOffset: true,
    });
    camera.SetMode(CustomCameraMode.FOLLOW_POSITION);
    return;
  }

  cameraHeld.set(slot, { parent: camera.GetParent(), unparented: CAMERA_UNPARENT });
  if (CAMERA_UNPARENT) camera.SetParent(undefined);

  updateCamera(heli, pawn);
  camera.SetMode(CAMERA_MODE === "locked"
    ? CustomCameraMode.CONTROLLED              // position AND angles from the camera
    : CustomCameraMode.CONTROLLED_POSITION);   // position from the camera, pilot aims
}

/**
 * Hand the view back. Resolves the player's CURRENT pawn rather than trusting
 * anything cached, so this still works after the round swapped their body out.
 */
function giveBackCamera(slot) {
  const held = cameraHeld.get(slot);
  if (!held) return;
  cameraHeld.delete(slot);

  const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
  if (!pawn || !pawn.IsValid()) return;

  const camera = cameraFor(pawn);
  if (!camera) return;

  // Give the view back first and tidy up after, so a failure below can't leave
  // someone staring through a camera parked out on the heli.
  camera.SetMode(CustomCameraMode.DISABLED);
  if (held.unparented) camera.SetParent(held.parent);
}

function teleportOut(heli, pawn) {
  const name = heli.config.exitTeleport;
  if (!name) return;

  const destination = live(Instance.FindEntityByName(name));
  if (!destination) {
    log(`${heli.config.body}: exit teleport "${name}" missing, leaving pilot in place`);
    return;
  }

  const move = { position: copyVector(destination.GetAbsOrigin()), velocity: ZERO };
  if (EXIT_TELEPORT_FACING) {
    move.angles = { pitch: 0, yaw: destination.GetAbsAngles().yaw, roll: 0 };
  }
  pawn.Teleport(move);
}

/** The PlayerOff path: all five thrusters off, pilot handed back their body. */
function exitHeli(heli, reason, teleport) {
  for (const control of CONTROLS) setThruster(heli, control.key, false);

  const slot = heli.pilotSlot;
  if (slot < 0) return;

  giveBackCamera(slot);
  reentryBlocked.set(slot, Instance.GetGameTime() + REENTRY_COOLDOWN);

  heli.pilotSlot = -1;
  pilotHeli.delete(slot);

  const controller = Instance.GetPlayerController(slot);
  const pawn = controller?.GetPlayerPawn();

  // Before the early return below, so the entry is always cleared. Only a
  // normal let-go (the teleport cases) gets their weapon handed back - after a
  // death, respawn or round change there's nothing sensible to switch to.
  unholsterGuns(slot, teleport ? pawn : undefined);

  if (!pawn || !pawn.IsValid()) return;

  // Unfreeze before teleporting - moving a MOVETYPE_NONE player can leave them
  // stuck in place at the destination.
  if (FREEZE_PILOT && pawn.IsAlive()) pawn.SetMoveType(CSMoveType.WALK);
  if (teleport && pawn.IsAlive()) teleportOut(heli, pawn);

  log(`${controller?.GetPlayerName() ?? slot} let go of ${heli.config.body} (${reason})`);
}

function exitBySlot(slot, reason, teleport) {
  const bodyName = pilotHeli.get(slot);
  if (bodyName === undefined) return;

  const heli = helis.get(bodyName);
  if (heli) exitHeli(heli, reason, teleport);
  else pilotHeli.delete(slot);
}

function exitByPawn(pawn, reason, teleport) {
  const slot = pawn?.GetPlayerController()?.GetPlayerSlot();
  if (slot !== undefined) exitBySlot(slot, reason, teleport);
}

function exitAll(reason, teleport) {
  for (const heli of helis.values()) exitHeli(heli, reason, teleport);
}

// ----- think ----------------------------------------------------------------

Instance.SetThink(() => {
  Instance.SetNextThink(Instance.GetGameTime());

  for (const [slot, bodyName] of [...pilotHeli]) {
    const heli = helis.get(bodyName);
    if (!heli) { pilotHeli.delete(slot); continue; }

    const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
    if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) {
      exitHeli(heli, "pilot gone", false);
      continue;
    }

    if (!heliBody(heli)) {
      exitHeli(heli, "heli destroyed", true);
      continue;
    }

    // Crouch and use are read as raw inputs. A frozen pilot never physically
    // crouches, so an OnPlayerJump-style event would never fire.
    const duck = pawn.IsInputPressed(CSInputs.DUCK);
    const use = pawn.IsInputPressed(CSInputs.USE);
    const duckPressed = duck && !heli.lastDuck;
    const usePressed = use && !heli.lastUse;
    heli.lastDuck = duck;
    heli.lastUse = use;

    if ((EXIT_ON_DUCK && duckPressed) || (EXIT_ON_USE && usePressed)) {
      exitHeli(heli, "let go", true);
      continue;
    }

    // Locked: keep them on the knife. Unlocked mid-flight: hand back whatever
    // they had out (a no-op once that's been done).
    if (pilotGunsEnabled) unholsterGuns(slot, pawn);
    else holsterGuns(pawn, slot);

    // Each key tested on its own - IsInputPressed with a combined mask means
    // ALL of those keys at once.
    for (const control of CONTROLS) {
      setThruster(heli, control.key, pawn.IsInputPressed(control.input));
    }

    updateCamera(heli, pawn);
  }

  // Anyone still holding a camera who isn't flying gets it back. This is what
  // catches the round change, where the pawn is swapped out from under the
  // normal exit path and the old handle quietly goes invalid.
  for (const slot of [...cameraHeld.keys()]) {
    if (!pilotHeli.has(slot)) giveBackCamera(slot);
  }
});

// ----- lifecycle ------------------------------------------------------------

function start() {
  discover();
  hookControls();
  Instance.SetNextThink(Instance.GetGameTime());
}

Instance.OnActivate(start);
Instance.OnScriptReload({ after: start });

/** Everything that has to go back to how it started, every round. */
function resetForNewRound(reason) {
  exitAll(reason, false);
  holstered.clear();
  setPilotGuns(!PILOT_GUNS_LOCKED_BY_DEFAULT, reason);
}

Instance.OnRoundStart(() => {
  resetForNewRound("round start");
  Instance.Delay(0.5).then(start);
});
Instance.OnBeginRoundRestart(() => resetForNewRound("round restart"));
Instance.OnPlayerKill(({ player }) => exitByPawn(player, "died", false));
Instance.OnPlayerReset(({ player }) => exitByPawn(player, "respawned", false));
Instance.OnPlayerDisconnect(({ playerSlot }) => {
  exitBySlot(playerSlot, "disconnected", false);
  reentryBlocked.delete(playerSlot);
  holstered.delete(playerSlot);
});

// A locked pilot deals no damage - their knife included. Guarded so a game
// build without this hook still loads the rest of the script.
if (BLOCK_LOCKED_PILOT_DAMAGE && typeof Instance.OnModifyPlayerDamage === "function") {
  Instance.OnModifyPlayerDamage(({ attacker, inflictor, weapon }) => {
    if (pilotGunsEnabled) return;

    for (const source of [attacker, inflictor, live(weapon)?.GetOwner()]) {
      const slot = slotOfEntity(source);
      if (slot !== undefined && pilotHeli.has(slot)) {
        if (DEBUG) log(`blocked damage from locked pilot (slot ${slot})`);
        return { abort: true };
      }
    }
  });
} else if (BLOCK_LOCKED_PILOT_DAMAGE) {
  log("OnModifyPlayerDamage not available in this build - damage block is off");
}

// Pilot's weapons, driven from the map. See "pilot's weapons" at the top.
//   helib3  OnPressed -> heli_script -> RunScriptInput -> EnableHeliGuns
Instance.OnScriptInput(ENABLE_GUNS_INPUT, () => setPilotGuns(true, ENABLE_GUNS_INPUT));
Instance.OnScriptInput(DISABLE_GUNS_INPUT, () => setPilotGuns(false, DISABLE_GUNS_INPUT));

// Alternative wiring, if you'd rather drive it from the map than from the
// button hook:  <your entity>  ->  <point_script>  RunScriptInput  ->  EnterHeli
Instance.OnScriptInput("EnterHeli", ({ activator }) => {
  const pawn = pawnFromEntity(activator);
  if (pawn && helis.size > 0) enterHeli(pawn, [...helis.values()][0]);
});

Instance.OnScriptInput("ExitHeli", ({ activator }) => {
  const pawn = pawnFromEntity(activator);
  if (pawn) exitByPawn(pawn, "script input", true);
});

// ----- console (needs sv_cheats 1) ------------------------------------------

Instance.RegisterCheatCommand("heli_dump", () => {
  Instance.Msg(`[heli] ${helis.size} aircraft, ${outputHooks.length} button hook(s),` +
               ` pilot weapons ${pilotGunsEnabled ? "UNLOCKED" : "locked"}`);
  for (const heli of helis.values()) {
    const pilot = heli.pilotSlot >= 0
      ? Instance.GetPlayerController(heli.pilotSlot)?.GetPlayerName() ?? heli.pilotSlot
      : "-";
    const running = CONTROLS.filter((c) => heli.active[c.key]).map((c) => c.key);
    Instance.Msg(`  ${heli.config.body}: pilot=${pilot} running=[${running.join(",") || "none"}]`);
    report(heli);
  }
});

// The one that answers "why is it facing the wrong way". Rotate heli_cam in
// Hammer, rebuild, take the controls, run this, and compare: if the anchor's
// angles didn't change, Hammer isn't storing the rotation. If they did change
// but the view didn't move, the camera side is the problem - try CAMERA_UNPARENT
// or CAMERA_ANGLE_SOURCE "body". (Rotation only matters in "position"/"locked".)
Instance.RegisterCheatCommand("heli_cam_debug", () => {
  const pos = (p) => `${p.x.toFixed(0)} ${p.y.toFixed(0)} ${p.z.toFixed(0)}`;
  const ang = (q) => `${q.pitch.toFixed(1)} ${q.yaw.toFixed(1)} ${q.roll.toFixed(1)}`;
  const show = (e) => `pos[${pos(e.GetAbsOrigin())}] ang[${ang(e.GetAbsAngles())}]`;

  for (const heli of helis.values()) {
    const config = heli.config;
    const anchor = live(Instance.FindEntityByName(config.cameraAnchor));
    const body = heliBody(heli);
    const pilotPawn = heli.pilotSlot >= 0
      ? Instance.GetPlayerController(heli.pilotSlot)?.GetPlayerPawn()
      : undefined;
    const camera = pilotPawn && pilotPawn.IsValid() ? cameraFor(pilotPawn) : undefined;
    const wanted = cameraTransform(heli);

    Instance.Msg(`[heli] ${config.body} camera debug`);
    Instance.Msg(`  anchor "${config.cameraAnchor}": ${anchor ? show(anchor) : "NOT FOUND"}`);
    Instance.Msg(`  body   "${config.body}": ${body ? show(body) : "NOT FOUND"}`);

    if (camera) {
      const parent = camera.GetParent();
      const parentName = parent
        ? (parent.GetEntityName() || parent.GetClassName())
        : "none";
      const mode = camera.GetMode();
      const modeName = Object.keys(CustomCameraMode).find((k) => CustomCameraMode[k] === mode) ?? mode;
      // In "follow" the view is worked out from the follow config, so the
      // camera entity's own position here may not be where the view is.
      Instance.Msg(`  camera: ${show(camera)} parent[${parentName}] mode=${modeName}`);
    } else {
      Instance.Msg(`  camera: nobody at the controls`);
    }

    if (CAMERA_MODE === "follow") {
      const target = followTarget(heli);
      const name = target ? (target.entity.GetEntityName() || target.entity.GetClassName()) : "nothing";
      Instance.Msg(`  following: ${name} offset[${pos(CAMERA_FOLLOW_OFFSET)}]`);
    } else {
      Instance.Msg(`  script is asking for: ${wanted ? `pos[${pos(wanted.position)}] ang[${ang(wanted.angles)}]` : "n/a"}`);
    }
    Instance.Msg(`  settings: mode=${CAMERA_MODE} source=${CAMERA_ANGLE_SOURCE}` +
                 ` unparent=${CAMERA_UNPARENT} offset[${ang(CAMERA_ANGLE_OFFSET)}]`);
  }
});

Instance.RegisterCheatCommand("heli_take", () => {
  const pawn = Instance.GetAllPlayerControllers()[0]?.GetPlayerPawn();
  if (pawn && helis.size > 0) enterHeli(pawn, [...helis.values()][0]);
});

Instance.RegisterCheatCommand("heli_release", () => exitAll("heli_release", true));

// Flip the pilot's weapons lock without pressing helib3. Same as firing the
// EnableHeliGuns / DisableHeliGuns script inputs.
Instance.RegisterCheatCommand("heli_guns", () => setPilotGuns(!pilotGunsEnabled, "heli_guns"));

// If a camera ever does get stuck, this hands every held one back without
// touching anything else.
Instance.RegisterCheatCommand("heli_cam_reset", () => {
  const slots = [...cameraHeld.keys()];
  for (const slot of slots) giveBackCamera(slot);
  Instance.Msg(`[heli] released ${slots.length} camera(s)`);
});
