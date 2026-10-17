// vehicles.js  --  jb_water_prison_cs2
//
// Stand-in for vehicle_gameui5. game_ui is still in the CS2 FGD but its
// implementation is gone, so PressedForward / UnpressedForward / PressedBack /
// PressedMoveLeft / PressedMoveRight never fire and the car just sits there.
// This script reads the driver's keys itself and fires the exact same
// Activate / Deactivate inputs on the exact same phys_thruster entities the
// game_ui used to drive.
//
//   +USE on vehicle_button5  ->  take the controls
//   W / S / A / D            ->  vehicle_thruster_forward5 / _backward5 /
//                                vehicle_left_thrusters5 / _right_thrusters5
//   +USE again               ->  let go
//
// The driver RIDES the car: on the press that takes the controls the script
// records where they're standing relative to vehicle_base5 and holds them at
// exactly that offset, rebuilt from the car's origin every tick so it can't
// drift. No SetParent anywhere - it re-reads world position as a local offset
// and flings people.
//
// ---------------------------------------------------------------------------
// v2 - two things the first pass got wrong, both now understood:
//
// 1. THE DRIVER WAS BEING KILLED BY THEIR OWN CAR. Pulled the brushwork out of
//    the vmap to see why. The cockpit floor is at z 82, so a standing driver
//    occupies z 82-154. carhealth (trigger_hurt, 1000 damage) is a slab at
//    z 98-105 covering x 1574-1658, y 3304-3534 - that's the whole car, cockpit
//    included, at chest height. trigger_dmgfilter5 (x 1590-1638, y 3356-3516,
//    z 104-185) is what arms it, and the driver stands inside that too. So the
//    driver arms the hurt box and is standing in it. Fixed with
//    OnModifyPlayerDamage, which cancels damage to a driver when it came from
//    their own car - they stay perfectly shootable by other players.
//
// 2. IT DROVE LIKE A BRICK. Two reasons. The thrusters are genuinely weak:
//    350 forward/back, and turning is a 100/50 couple (see THRUSTER FORCES at
//    the bottom of this file). And the cockpit is 40 units wide with a 32-wide
//    player locked in the middle of it, so a frozen driver is a solid immovable
//    obstacle wedged inside the car's own collision - the car drags an anchor.
//    DRIVE_ASSIST below adds speed and turn rate directly to the physbox on top
//    of the thrusters, and everything is tunable live with vehicle_tune so you
//    can dial it in during a playtest instead of recompiling.
// ---------------------------------------------------------------------------
// v3 - confirmed in game: the car was fighting the driver's hull. Two changes.
//
//    The driver is now NOCLIP while at the controls instead of frozen-solid, so
//    the physbox has nothing to shove against. Noclip changes movement, not
//    solidity, so they should still be shootable - worth 10 seconds to confirm
//    with a bot, because if it isn't true the answer is `ride parent` below
//    rather than living with it.
//
//    The per-tick seat update now uses Move() instead of Teleport(). Teleport
//    resets the client's interpolation history, and doing that every single
//    tick is its own source of jank on top of the collision.
//
//    RIDE_MODE "parent" is also a real option now (it wasn't before): the
//    engine carries the driver, and the script writes no position at all after
//    entry. `vehicle_tune ride parent` to try it live.
// ---------------------------------------------------------------------------
// v4 - lift the driver out of the car instead of making them non-solid.
//
//    SEAT_LIFT rides them 150 units above where they were standing. The cockpit
//    floor is z 82 and the roof tops out at z 179, so 150 floats them clear of
//    the whole body by about 53 units - nothing of theirs is inside the car's
//    collision any more, so there's nothing to fight, and they stay SOLID and
//    shootable, which is what noclip put at risk. Back to movetype "none".
//
//    It also sidesteps the damage geometry for free: at that height they're
//    above carhealth (z 98-105) and above trigger_dmgfilter5 (z 104-185)
//    entirely. The damage filter stays in as a belt-and-braces for the moment
//    they're set back down.
//
//    Getting out puts them back on the cockpit floor rather than dropping them
//    off the roof. `vehicle_tune lift <n>` to change the height live - 97 sets
//    them down standing on the roof, 0 is the old in-cockpit position.
// ---------------------------------------------------------------------------
//
// SETUP: content/csgo_addons/jb_water_prison_cs2/scripts/vehicles.js, plus a
// point_script entity with script file = scripts/vehicles.js. No outputs need
// wiring - the script hooks vehicle_button5's OnPressed itself.

import { Instance, CSInputs, CSMoveType, CSDamageTypes } from "cs_script/point_script";

// ----- the cars -------------------------------------------------------------
// Copy the whole block and change the 5s to add vehicle 6. Note that the map
// has TWO phys_thrusters named vehicle_left_thrusters5 (force 100 at the front,
// 50 at the back) and two named vehicle_right_thrusters5 - that's the turning
// couple, and it's fine: EntFireAtName hits every entity with the name, exactly
// like the game_ui's output did.
const VEHICLES = [
  {
    id: 5,
    base:   "vehicle_base5",      // the func_physbox the thrusters push
    button: "vehicle_button5",    // func_button the driver presses
    thrusters: {
      forward:  "vehicle_thruster_forward5",
      backward: "vehicle_thruster_backward5",
      left:     "vehicle_left_thrusters5",
      right:    "vehicle_right_thrusters5",
    },
    idleSound:   "vehicle_idle_5",     // looping ambient_generic, start silent
    igniteSound: "vehicle_ignite_5",   // one-shot ambient_generic
    exitTeleport: "",                  // optional marker to drop the driver on

    // Anything here that damages the driver gets ignored while they're driving.
    hurtTrigger: "carhealth",          // trigger_hurt, 1000 dmg, z 98-105
    armTrigger:  "trigger_dmgfilter5", // what enables it
    wheels: [
      "wheel_front_left_5", "wheel_front_right_5",
      "wheel_rear_left_5",  "wheel_rear_right_5",
    ],

    // vehicle_thruster_forward5 sits at the back of the car pointing yaw 270,
    // so the car's nose points -Y, which is 270 degrees off the entity's own
    // yaw. This is what tells the drive assist which way "forward" is. If you
    // ever rotate the car in Hammer this number doesn't change - it's relative
    // to the body - but if you re-point the thrusters, it does.
    forwardYawOffset: 270,
  },
];

// ----- config ---------------------------------------------------------------
const DEBUG = false;   // set false once it's working

const CONTROLS = [
  { input: CSInputs.FORWARD, key: "forward"  },
  { input: CSInputs.BACK,    key: "backward" },
  { input: CSInputs.LEFT,    key: "left"     },
  { input: CSInputs.RIGHT,   key: "right"    },
];

// ----- getting in and out ---------------------------------------------------
const EXIT_ON_USE  = true;    // +use to let go
const EXIT_ON_DUCK = false;   // crouch to let go
const EXIT_ON_JUMP = false;   // what game_ui's "Jump Deactivates" flag did

// Seconds after letting go before the SAME player can take the controls again.
// Without it the +use that gets you out is seen by the button as a fresh press
// and puts you straight back in.
const REENTRY_COOLDOWN = 0.75;

// vehicle_button5 locks itself on press (its own Hammer output) so nobody can
// grab a car that's already being driven. Nothing unlocks it any more - the
// game_ui that used to is dead - so the script does.
const UNLOCK_DELAY = 0.25;

// ----- not dying in your own car --------------------------------------------
// Cancels damage to the driver that came from their own vehicle: the trigger_hurt
// they're standing in, the body, the wheels. Bullets, knives, grenades and every
// other player still hurt them completely normally.
const IMMUNE_TO_OWN_CAR = true;
// Also cancel crush / vehicle damage with no player behind it while driving -
// the car folding up against a wall with the driver inside it.
const IMMUNE_TO_OWN_CRUSH = true;

// ----- riding ---------------------------------------------------------------
//   "follow" - the script puts them on the seat every tick. Default. Exact,
//              self-correcting, and the only one that can't drift.
//   "parent" - hand them to the engine and write nothing per tick. Smoothest
//              of the three when it works. SetParent re-reads world position as
//              a local offset, so entry needs a correction step - the script
//              does that and checks where they actually landed, so it works
//              whichever convention the engine uses.
//   "stay"   - they don't move at all; the car drives off without them.
const RIDE_MODE = "follow";

// What the driver's body does while they're at the controls. THIS is what was
// making the car drive like it was towing something: a frozen player is still
// a solid body, and the cockpit is 40 units wide with a 32-wide player locked
// in the middle of it, so the physbox spent every tick resolving a collision
// against an immovable object inside itself.
//   "none"   - frozen and solid. The default again, because SEAT_LIFT below
//              takes the driver out of the car's collision by moving them
//              rather than by making them intangible, so being solid costs
//              nothing now and keeps them shootable.
//   "noclip" - movement collisions off. Still here as a fallback if anything
//              else ever ends up wedged, but it risks making the driver
//              unshootable, so it isn't the default.
//   "walk"   - not frozen at all. Don't; they'll walk out of the seat.
const DRIVER_MOVETYPE = "none";

// How far above their standing position the driver rides, in units. This is
// what stops the car fighting them: at 150 they're clear above a body whose
// roof tops out at z 179 from a cockpit floor at z 82, so nothing of theirs is
// inside the car at all. Their x/y offset is untouched - they sit directly over
// the spot they pressed +use on, and turn with the car exactly as before.
//   150  floats them about 53 units above the roof
//    97  sets them down standing ON the roof
//     0  the original in-cockpit position (and the original collision problem)
const SEAT_LIFT = 50;
// Getting out sets them back down on the cockpit floor instead of leaving them
// to fall off the top of the car. Ignored when exitTeleport is set.
const DROP_BACK_ON_EXIT = true;

const FOLLOW_CAR_YAW = true;      // swing the seat round as the car turns
const TURN_VIEW_WITH_CAR = false; // also rotate their view. Writing angles to a
                                  // player turns their BODY too - disorienting.
// Teleport() resets the client's interpolation history. Once per entry is fine;
// sixty-four times a second is a stutter all of its own, which is why the ride
// uses Move() now. Teleport is still what entry and the exit marker use.
const RIDE_WITH_TELEPORT = false;
// Don't write a position at all if the seat has moved less than this. A parked
// car then costs nothing per tick.
const RIDE_EPSILON = 0.03;
// How far the driver is allowed to end up from where the LAST write put them
// before the script stops being polite and uses an authoritative Teleport.
// This is measured against the previous target, not the current one, so it
// doesn't trip just because the car is moving quickly - only when the driver
// genuinely isn't where they were put. This is what stops the slow sink.
const RIDE_SNAP = 2;
// Re-assert the driver's movetype if something clears it. A driver who quietly
// goes back to WALK starts falling, and the seat write alone won't hold them.
const KEEP_MOVETYPE = true;
// "parent" only: re-assert the seat if the engine lets them drift this far.
const PARENT_DRIFT_FIX = 4;

// ----- drive assist ---------------------------------------------------------
// Added on top of the thrusters, not instead of them, so the car still behaves
// like a physics object - it rams people, bounces and tips exactly as before,
// it just has some actual power. Set ASSIST false to get the raw thruster feel
// back. All of these are live-tunable with vehicle_tune.
const DRIVE_ASSIST = true;
// Extra acceleration along the car's nose, units/sec^2. The thrusters alone
// give 350; this is on top.
let assistAccel = 700;
// Speed the assist stops pushing at, units/sec. A player runs at about 250.
// The thrusters can still push past this on their own.
let assistMaxSpeed = 520;
// Extra turn acceleration, degrees/sec^2, and the turn rate it stops at.
let assistTurnAccel = 260;
let assistMaxTurnRate = 110;
// Which component of the angular velocity vector is yaw. Source order is
// (pitch, yaw, roll) so "y" is right, but `vehicle_tune` prints all three
// against the measured turn rate - if the car won't turn, look there first.
let assistTurnAxis = "y";

// ----- parity with the old game_ui wiring -----------------------------------
// vehicle_button5's own OnPressed outputs still fire on their own:
//     Lock (0.01s) | vehicle_ignite_5 PlaySound | vehicle_base5 EnableMotion
// (plus vehicle_gameui5 Activate, the dead one). So the script leaves the
// engine-start side alone and only does the half that died with the game_ui.
// Set this false if you strip those outputs in Hammer.
const BUTTON_KEEPS_HAMMER_OUTPUTS = true;

const PLAY_IDLE_SOUND = true;
const IDLE_SOUND_DELAY = 1.2;      // game_ui PlayerOn -> vehicle_idle_5 PlaySound

const DISABLE_MOTION_ON_EXIT = true;
const DISABLE_MOTION_DELAY = 1.5;  // game_ui PlayerOff -> vehicle_base5 DisableMotion

const EXIT_TELEPORT_FACING = true;
// ----------------------------------------------------------------------------

Instance.Msg("[vehicles] script loaded");

const ZERO = { x: 0, y: 0, z: 0 };

const MOVETYPES = {
  none: CSMoveType.NONE,
  noclip: CSMoveType.NOCLIP,
  walk: CSMoveType.WALK,
};

let driverMoveType = DRIVER_MOVETYPE;
let rideMode = RIDE_MODE;
let rideWithTeleport = RIDE_WITH_TELEPORT;
let seatLift = SEAT_LIFT;
let assistEnabled = DRIVE_ASSIST;

// base name -> vehicle state
const vehicles = new Map();
// player slot -> base name
const driverVehicle = new Map();
// player slot -> game time before which they can't take the controls again
const reentryBlocked = new Map();
let outputHooks = [];
let lastThink = 0;

function log(text) { if (DEBUG) Instance.Msg(`[vehicles] ${text}`); }

function live(entity) { return entity && entity.IsValid() ? entity : undefined; }

function copyVector(v) { return { x: v.x, y: v.y, z: v.z }; }

function wrapDegrees(degrees) {
  let d = degrees % 360;
  if (d > 180) d -= 360;
  if (d < -180) d += 360;
  return d;
}

/** Spin a flat offset about Z. Yaw only - a car that tips shouldn't throw the
 *  driver into the sky, which is what using full rotation would do. */
function rotateZ(x, y, degrees) {
  const radians = degrees * Math.PI / 180;
  const cos = Math.cos(radians);
  const sin = Math.sin(radians);
  return { x: x * cos - y * sin, y: x * sin + y * cos };
}

function fire(name, input) {
  if (!name) return;
  Instance.EntFireAtName({ name, input });
}

function moveTypeFor(key) {
  return MOVETYPES[key] ?? CSMoveType.NONE;
}

// ----- discovery ------------------------------------------------------------

function discover() {
  for (const config of VEHICLES) {
    let vehicle = vehicles.get(config.base);
    if (!vehicle) {
      vehicle = {
        config,
        cache: {},
        active: {},
        driverSlot: -1,
        seat: undefined,
        lastSeatTarget: undefined,   // where the previous tick put the driver
        lastYaw: 0,        // used by the view-turn follow
        measuredYaw: 0,    // used only by the vehicle_tune readout
        lastDuck: false,
        lastJump: false,
        lastUse: false,
        release: 0,
        turnRate: 0,      // measured, for the tuning readout
        ownNames: new Set(),
      };
      vehicles.set(config.base, vehicle);
    }

    vehicle.cache = {};

    // Everything that counts as "your own car" for the damage filter.
    vehicle.ownNames = new Set(
      [config.base, config.button, config.hurtTrigger, config.armTrigger,
       ...(config.wheels ?? []), ...Object.values(config.thrusters ?? {})]
        .filter(Boolean)
        .map((name) => name.toLowerCase()));

    // Anything left running from last round, and a car nobody can get into
    // because the button locked itself and then the round ended.
    if (vehicle.driverSlot < 0) {
      for (const control of CONTROLS) {
        vehicle.active[control.key] = false;
        fire(config.thrusters[control.key], "Deactivate");
      }
      fire(config.idleSound, "StopSound");
      fire(config.button, "Unlock");
    }

    if (DEBUG) report(vehicle);
  }
}

function report(vehicle) {
  const config = vehicle.config;
  const missing = [];

  if (!vehicleBase(vehicle)) missing.push(`base "${config.base}"`);
  if (!Instance.FindEntityByName(config.button)) missing.push(`button "${config.button}"`);

  for (const control of CONTROLS) {
    const name = config.thrusters[control.key];
    if (!name || !Instance.FindEntityByName(name)) {
      missing.push(`thruster "${name ?? control.key}"`);
    }
  }
  for (const key of ["idleSound", "igniteSound", "exitTeleport", "hurtTrigger"]) {
    const name = config[key];
    if (name && !Instance.FindEntityByName(name)) missing.push(`${key} "${name}"`);
  }

  log(`vehicle ${config.id}: ` +
      (missing.length ? `MISSING ${missing.join(", ")}` : "all entities found"));
}

function resolve(vehicle, slotName, entityName) {
  const cached = live(vehicle.cache[slotName]);
  if (cached) return cached;
  if (!entityName) return undefined;

  vehicle.cache[slotName] = live(Instance.FindEntityByName(entityName));
  return vehicle.cache[slotName];
}

function vehicleBase(vehicle) { return resolve(vehicle, "base", vehicle.config.base); }

/**
 * Hook the +use button straight from script. func_button reports the player who
 * pressed it as the activator, so nothing needs wiring in Hammer and the
 * existing outputs on vehicle_button5 can stay exactly as they are.
 */
function hookButtons() {
  for (const id of outputHooks) {
    try { Instance.DisconnectOutput(id); } catch (error) { /* already gone */ }
  }
  outputHooks = [];

  for (const vehicle of vehicles.values()) {
    const name = vehicle.config.button;
    if (!name) continue;

    for (const button of Instance.FindEntitiesByName(name)) {
      const hook = Instance.ConnectOutput(button, "OnPressed",
        ({ activator }) => enterVehicle(pawnFromEntity(activator), vehicle));

      if (hook !== undefined) {
        outputHooks.push(hook);
        log(`vehicle ${vehicle.config.id}: entry hooked to "${name}" OnPressed`);
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

function vehicleForSlot(slot) {
  const baseName = driverVehicle.get(slot);
  return baseName === undefined ? undefined : vehicles.get(baseName);
}

// ----- not dying in your own car --------------------------------------------

/**
 * The driver stands on the cockpit floor at z 82, so their chest is at z 98-105
 * - which is exactly the slab carhealth occupies, and they're inside
 * trigger_dmgfilter5 so they arm it themselves. Rather than carve up the
 * brushwork, just refuse the damage when it came from their own car.
 *
 * Scoped deliberately tight: only damage whose inflictor or attacker is one of
 * that car's own entities. Getting shot, knifed, naded or run over by a DIFFERENT
 * car all still work normally, so a driver is not a safe driver.
 */
Instance.OnModifyPlayerDamage((event) => {
  if (!IMMUNE_TO_OWN_CAR) return;

  const slot = event.player?.GetPlayerController()?.GetPlayerSlot();
  if (slot === undefined) return;

  const vehicle = vehicleForSlot(slot);
  if (!vehicle) return;

  for (const source of [event.inflictor, event.attacker]) {
    const entity = live(source);
    if (!entity) continue;

    const name = (entity.GetEntityName() || "").toLowerCase();
    if (name && vehicle.ownNames.has(name)) {
      log(`vehicle ${vehicle.config.id}: ignored ${event.damage} damage from "${name}"`);
      return { abort: true };
    }
  }

  if (IMMUNE_TO_OWN_CRUSH) {
    const crush = (event.damageTypes & (CSDamageTypes.CRUSH | CSDamageTypes.VEHICLE)) !== 0;
    // A player behind it means somebody genuinely squashed them - let it through.
    const byPlayer = event.attacker && pawnFromEntity(event.attacker);
    if (crush && !byPlayer) {
      log(`vehicle ${vehicle.config.id}: ignored ${event.damage} crush damage`);
      return { abort: true };
    }
  }
});

// ----- driving --------------------------------------------------------------

function setThruster(vehicle, key, on) {
  if (vehicle.active[key] === on) return;
  vehicle.active[key] = on;

  const name = vehicle.config.thrusters[key];
  if (!name) return;

  fire(name, on ? "Activate" : "Deactivate");
  if (DEBUG) log(`vehicle ${vehicle.config.id} ${key} -> ${on ? "Activate" : "Deactivate"}`);
}

/**
 * Extra push on top of the thrusters. Uses Move() rather than Teleport() so the
 * client's interpolation history survives - Teleport on a moving physbox every
 * tick makes it stutter for everyone watching.
 */
function driveAssist(vehicle, pawn, dt) {
  if (!assistEnabled || dt <= 0) return;

  const base = vehicleBase(vehicle);
  if (!base) return;

  const nose = (base.GetAbsAngles().yaw + (vehicle.config.forwardYawOffset ?? 0)) * Math.PI / 180;
  const forward = { x: Math.cos(nose), y: Math.sin(nose) };

  let drive = 0;
  if (pawn.IsInputPressed(CSInputs.FORWARD)) drive += 1;
  if (pawn.IsInputPressed(CSInputs.BACK)) drive -= 1;

  let steer = 0;   // +yaw is left in Source's coordinate system
  if (pawn.IsInputPressed(CSInputs.LEFT)) steer += 1;
  if (pawn.IsInputPressed(CSInputs.RIGHT)) steer -= 1;

  const update = {};

  if (drive !== 0 && assistAccel > 0) {
    const velocity = base.GetAbsVelocity();
    const speed = Math.hypot(velocity.x, velocity.y);

    // Only push while under the cap, but always allow braking - pressing S at
    // full speed has to bite even though the speed is already at the limit.
    const along = velocity.x * forward.x + velocity.y * forward.y;
    if (speed < assistMaxSpeed || (drive > 0 ? along < 0 : along > 0)) {
      const step = assistAccel * dt * drive;
      update.velocity = {
        x: velocity.x + forward.x * step,
        y: velocity.y + forward.y * step,
        z: velocity.z,
      };
    }
  }

  if (steer !== 0 && assistTurnAccel > 0) {
    const angular = base.GetAbsAngularVelocity();
    const current = angular[assistTurnAxis] ?? 0;

    if (Math.abs(current) < assistMaxTurnRate || Math.sign(current) !== Math.sign(steer)) {
      update.angularVelocity = {
        x: angular.x, y: angular.y, z: angular.z,
        [assistTurnAxis]: current + assistTurnAccel * dt * steer,
      };
    }
  }

  if (update.velocity || update.angularVelocity) base.Move(update);
}

function captureSeat(vehicle, pawn) {
  const base = vehicleBase(vehicle);
  if (!base) return;

  const origin = base.GetAbsOrigin();
  const yaw = base.GetAbsAngles().yaw;
  const player = pawn.GetAbsOrigin();

  const dx = player.x - origin.x;
  const dy = player.y - origin.y;
  const flat = FOLLOW_CAR_YAW ? rotateZ(dx, dy, -yaw) : { x: dx, y: dy };

  vehicle.seat = { x: flat.x, y: flat.y, z: player.z - origin.z };
  vehicle.lastYaw = yaw;
  vehicle.measuredYaw = yaw;

  log(`vehicle ${vehicle.config.id}: seat offset ` +
      `[${vehicle.seat.x.toFixed(1)} ${vehicle.seat.y.toFixed(1)} ${vehicle.seat.z.toFixed(1)}]` +
      ` lift ${seatLift}`);
}

/**
 * Where the seat is in the world right now. vehicle.seat holds the RAW offset
 * captured on entry - the lift is applied here rather than baked in, so
 * changing it mid-drive takes effect immediately and exit can ask for the
 * un-lifted position by passing 0.
 */
function seatWorldPosition(vehicle, lift = seatLift) {
  const base = vehicleBase(vehicle);
  if (!base || !vehicle.seat) return undefined;

  const origin = base.GetAbsOrigin();
  const yaw = base.GetAbsAngles().yaw;

  const flat = FOLLOW_CAR_YAW
    ? rotateZ(vehicle.seat.x, vehicle.seat.y, yaw)
    : { x: vehicle.seat.x, y: vehicle.seat.y };

  return {
    x: origin.x + flat.x,
    y: origin.y + flat.y,
    z: origin.z + vehicle.seat.z + lift,
  };
}

function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}

/**
 * Hand the driver to the engine. SetParent re-reads the current world position
 * as a local offset, which is what flings people - so put them where they
 * belong, look at where they ACTUALLY ended up, and apply the difference once.
 * That correction is right whichever way the engine read the first write, and
 * after it nothing touches their position again.
 */
function attachParent(vehicle, pawn) {
  const base = vehicleBase(vehicle);
  const target = seatWorldPosition(vehicle);
  if (!base || !target) return;

  pawn.SetParent(base);
  pawn.Teleport({ position: target });

  const landed = pawn.GetAbsOrigin();
  const drift = distance(target, landed);
  if (drift > 1) {
    pawn.Teleport({
      position: {
        x: target.x + (target.x - landed.x),
        y: target.y + (target.y - landed.y),
        z: target.z + (target.z - landed.z),
      },
    });
    log(`vehicle ${vehicle.config.id}: parented, corrected ${drift.toFixed(0)}u of entry drift`);
  }
}

function rideVehicle(vehicle, pawn) {
  if (rideMode === "stay" || !vehicle.seat) return;

  const target = seatWorldPosition(vehicle);
  if (!target) return;

  const yaw = vehicleBase(vehicle).GetAbsAngles().yaw;
  const turned = wrapDegrees(yaw - vehicle.lastYaw);
  vehicle.lastYaw = yaw;

  // Parented: the engine is carrying them. Only step in if they've slipped.
  if (rideMode === "parent") {
    if (distance(target, pawn.GetAbsOrigin()) > PARENT_DRIFT_FIX) {
      pawn.Teleport({ position: target });
      log(`vehicle ${vehicle.config.id}: re-seated a drifting parented driver`);
    }
    return;
  }

  // The movetype can be cleared out from under us - a respawn, a round change,
  // anything else that touches the pawn. Once it's back to WALK gravity starts
  // winning and the driver sinks no matter what we write.
  if (KEEP_MOVETYPE) {
    const wanted = moveTypeFor(driverMoveType);
    if (pawn.GetMoveType() !== wanted) {
      pawn.SetMoveType(wanted);
      log(`vehicle ${vehicle.config.id}: driver's movetype had been reset, put it back`);
    }
  }

  const here = pawn.GetAbsOrigin();

  // Error is measured against where the LAST tick put them, not against where
  // they're going now - otherwise a fast car reads as permanent error and every
  // tick becomes a Teleport.
  const error = vehicle.lastSeatTarget ? distance(vehicle.lastSeatTarget, here) : 0;

  const move = {};
  // A stationary car shouldn't cost a position write per tick.
  if (distance(target, here) > RIDE_EPSILON) move.position = target;

  // Any velocity they've picked up is gravity or a shove, and it's what drags
  // them off the seat in between writes. Zero it whenever there's any.
  const velocity = pawn.GetAbsVelocity();
  if (velocity.x !== 0 || velocity.y !== 0 || velocity.z !== 0) move.velocity = ZERO;

  if (TURN_VIEW_WITH_CAR && FOLLOW_CAR_YAW && turned !== 0) {
    const eyes = pawn.GetEyeAngles();
    move.angles = { pitch: eyes.pitch, yaw: wrapDegrees(eyes.yaw + turned), roll: 0 };
  }

  vehicle.lastSeatTarget = target;

  if (!move.position && !move.velocity && !move.angles) return;

  // Move() rather than Teleport() by default: Teleport resets the client's
  // interpolation history, and doing that every tick is a stutter in its own
  // right. The catch is that a soft write can lose ground to the client's own
  // prediction, a few units at a time - which is exactly the slow sink. So when
  // they've actually come adrift, use the authoritative one.
  if (rideWithTeleport || error > RIDE_SNAP) pawn.Teleport(move);
  else pawn.Move(move);
}

// ----- the PlayerOn path ----------------------------------------------------

function enterVehicle(pawn, vehicle) {
  if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) return;

  const controller = pawn.GetPlayerController();
  if (!controller) return;

  const slot = controller.GetPlayerSlot();

  // Every early-out has to leave the car usable: the button locked itself on
  // this very press, and if we walk away now nothing will ever unlock it.
  const refuse = (why) => {
    log(`vehicle ${vehicle.config.id}: refused ${controller.GetPlayerName()} (${why})`);
    if (vehicle.driverSlot < 0) scheduleUnlock(vehicle);
  };

  if (vehicle.driverSlot >= 0) return refuse("already has a driver");
  if (driverVehicle.has(slot)) return refuse("already driving something");
  if (Instance.GetGameTime() < (reentryBlocked.get(slot) ?? 0)) return refuse("cooldown");
  if (!vehicleBase(vehicle)) return refuse(`no "${vehicle.config.base}"`);

  vehicle.driverSlot = slot;
  driverVehicle.set(slot, vehicle.config.base);

  // Seed the edge detect so the +use that got them in isn't also read as the
  // +use that gets them out on the very next tick.
  vehicle.lastUse = pawn.IsInputPressed(CSInputs.USE);
  vehicle.lastDuck = pawn.IsInputPressed(CSInputs.DUCK);
  vehicle.lastJump = pawn.IsInputPressed(CSInputs.JUMP);

  // Captured BEFORE the movetype changes, while they're still standing where
  // they pressed.
  captureSeat(vehicle, pawn);
  pawn.SetMoveType(moveTypeFor(driverMoveType));

  if (rideMode === "parent") {
    attachParent(vehicle, pawn);
  } else {
    // One Teleport to put them up on the seat. Everything after this is Move(),
    // which keeps the client's interpolation intact; this first one has to be a
    // Teleport precisely because it IS a jump.
    const target = seatWorldPosition(vehicle);
    if (target) {
      pawn.Teleport({ position: target, velocity: ZERO });
      vehicle.lastSeatTarget = target;
    }
  }

  if (!BUTTON_KEEPS_HAMMER_OUTPUTS) {
    fire(vehicle.config.button, "Lock");
    fire(vehicle.config.igniteSound, "PlaySound");
    fire(vehicle.config.base, "EnableMotion");
  }

  if (PLAY_IDLE_SOUND && vehicle.config.idleSound) {
    const token = vehicle.release;
    Instance.Delay(IDLE_SOUND_DELAY).then(() => {
      if (vehicle.driverSlot >= 0 && vehicle.release === token) {
        fire(vehicle.config.idleSound, "PlaySound");
      }
    });
  }

  log(`${controller.GetPlayerName()} took vehicle ${vehicle.config.id}`);
}

// ----- the PlayerOff path ---------------------------------------------------

function scheduleUnlock(vehicle) {
  Instance.Delay(UNLOCK_DELAY).then(() => {
    if (vehicle.driverSlot < 0) fire(vehicle.config.button, "Unlock");
  });
}

function teleportOut(vehicle, pawn) {
  const name = vehicle.config.exitTeleport;

  if (!name) {
    // No marker: put them back where they were standing when they got in - the
    // seat without the lift - so letting go drops you into the cockpit instead
    // of off the top of the car.
    if (DROP_BACK_ON_EXIT && seatLift !== 0 && vehicle.floorSpot) {
      pawn.Teleport({ position: vehicle.floorSpot, velocity: ZERO });
    }
    return;
  }

  const destination = live(Instance.FindEntityByName(name));
  if (!destination) {
    log(`vehicle ${vehicle.config.id}: exit teleport "${name}" missing, leaving driver in place`);
    return;
  }

  const move = { position: copyVector(destination.GetAbsOrigin()), velocity: ZERO };
  if (EXIT_TELEPORT_FACING) {
    move.angles = { pitch: 0, yaw: destination.GetAbsAngles().yaw, roll: 0 };
  }
  pawn.Teleport(move);
}

/**
 * Everything the game_ui's PlayerOff outputs used to do, plus the one they
 * missed: the map only deactivated forward / left / right, so a car let go of
 * while reversing kept reversing.
 */
function exitVehicle(vehicle, reason, teleport) {
  for (const control of CONTROLS) setThruster(vehicle, control.key, false);

  const slot = vehicle.driverSlot;
  // Worked out before the seat is cleared - teleportOut still needs it.
  const floorSpot = seatWorldPosition(vehicle, 0);
  vehicle.seat = undefined;
  vehicle.lastSeatTarget = undefined;
  vehicle.floorSpot = floorSpot;
  vehicle.release += 1;

  const token = vehicle.release;

  fire(vehicle.config.idleSound, "StopSound");
  scheduleUnlock(vehicle);

  if (DISABLE_MOTION_ON_EXIT) {
    Instance.Delay(DISABLE_MOTION_DELAY).then(() => {
      if (vehicle.driverSlot < 0 && vehicle.release === token) {
        fire(vehicle.config.base, "DisableMotion");
      }
    });
  }

  if (slot < 0) return;

  vehicle.driverSlot = -1;
  driverVehicle.delete(slot);
  reentryBlocked.set(slot, Instance.GetGameTime() + REENTRY_COOLDOWN);

  const controller = Instance.GetPlayerController(slot);
  const pawn = controller?.GetPlayerPawn();

  if (pawn && pawn.IsValid()) {
    // Unparent before anything else, or the world position we hand them next
    // gets re-based against a car that's still moving.
    if (pawn.GetParent()) pawn.SetParent(undefined);
    // Unfreeze before teleporting - moving a frozen player can leave them stuck
    // in place at the destination.
    if (pawn.IsAlive()) pawn.SetMoveType(CSMoveType.WALK);
    if (teleport && pawn.IsAlive()) teleportOut(vehicle, pawn);
  }

  log(`${controller?.GetPlayerName() ?? slot} left vehicle ${vehicle.config.id} (${reason})`);
}

function exitBySlot(slot, reason, teleport) {
  const vehicle = vehicleForSlot(slot);
  if (vehicle) exitVehicle(vehicle, reason, teleport);
  else driverVehicle.delete(slot);
}

function exitByPawn(pawn, reason, teleport) {
  const slot = pawn?.GetPlayerController()?.GetPlayerSlot();
  if (slot !== undefined) exitBySlot(slot, reason, teleport);
}

function exitAll(reason, teleport) {
  for (const vehicle of vehicles.values()) exitVehicle(vehicle, reason, teleport);
}

// ----- think ----------------------------------------------------------------

Instance.SetThink(() => {
  Instance.SetNextThink(Instance.GetGameTime());

  const now = Instance.GetGameTime();
  // Clamped: the first tick after a load or a lag spike would otherwise hand
  // the assist a huge dt and fire the car off like a rocket.
  const dt = Math.min(Math.max(now - lastThink, 0), 0.1);
  lastThink = now;

  for (const [slot, baseName] of [...driverVehicle]) {
    const vehicle = vehicles.get(baseName);
    if (!vehicle) { driverVehicle.delete(slot); continue; }

    const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
    if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) {
      exitVehicle(vehicle, "driver gone", false);
      continue;
    }

    const base = vehicleBase(vehicle);
    if (!base) {
      exitVehicle(vehicle, "car destroyed", false);
      continue;
    }

    // Raw inputs, not events: a frozen driver never physically jumps or
    // crouches, so OnPlayerJump and friends would never fire.
    const use = pawn.IsInputPressed(CSInputs.USE);
    const duck = pawn.IsInputPressed(CSInputs.DUCK);
    const jump = pawn.IsInputPressed(CSInputs.JUMP);
    const usePressed = use && !vehicle.lastUse;
    const duckPressed = duck && !vehicle.lastDuck;
    const jumpPressed = jump && !vehicle.lastJump;
    vehicle.lastUse = use;
    vehicle.lastDuck = duck;
    vehicle.lastJump = jump;

    if ((EXIT_ON_USE && usePressed) ||
        (EXIT_ON_DUCK && duckPressed) ||
        (EXIT_ON_JUMP && jumpPressed)) {
      exitVehicle(vehicle, "let go", true);
      continue;
    }

    // Each key tested on its own: IsInputPressed with a combined mask means ALL
    // of those keys at once, and nobody holds W+A+S+D.
    for (const control of CONTROLS) {
      setThruster(vehicle, control.key, pawn.IsInputPressed(control.input));
    }

    // Measured turn rate, purely so vehicle_tune can show it. Kept on its own
    // field - vehicle.lastYaw belongs to the ride and only moves in "follow".
    const yawNow = base.GetAbsAngles().yaw;
    if (dt > 0) vehicle.turnRate = wrapDegrees(yawNow - vehicle.measuredYaw) / dt;
    vehicle.measuredYaw = yawNow;

    driveAssist(vehicle, pawn, dt);
    rideVehicle(vehicle, pawn);
  }
});

// ----- lifecycle ------------------------------------------------------------

function start() {
  discover();
  hookButtons();
  lastThink = Instance.GetGameTime();
  Instance.SetNextThink(Instance.GetGameTime());
}

Instance.OnActivate(start);
Instance.OnScriptReload({ after: start });

Instance.OnRoundStart(() => {
  exitAll("round start", false);
  Instance.Delay(0.5).then(start);
});
Instance.OnBeginRoundRestart(() => exitAll("round restart", false));
Instance.OnPlayerKill(({ player }) => exitByPawn(player, "died", false));
Instance.OnPlayerReset(({ player }) => exitByPawn(player, "respawned", false));
Instance.OnPlayerDisconnect(({ playerSlot }) => {
  exitBySlot(playerSlot, "disconnected", false);
  reentryBlocked.delete(playerSlot);
});

Instance.OnScriptInput("EnterVehicle", ({ caller, activator }) => {
  const pawn = pawnFromEntity(activator);
  if (!pawn) return;

  const match = /(\d+)\s*$/.exec(caller?.GetEntityName() ?? "");
  const wanted = match ? Number(match[1]) : undefined;
  const vehicle = [...vehicles.values()].find((v) => v.config.id === wanted)
    ?? [...vehicles.values()][0];

  if (vehicle) enterVehicle(pawn, vehicle);
});

Instance.OnScriptInput("ExitVehicle", ({ activator }) => {
  const pawn = pawnFromEntity(activator);
  if (pawn) exitByPawn(pawn, "script input", true);
});

// ----- console (needs sv_cheats 1) ------------------------------------------

/**
 * Live tuning, so the car can be dialled in during a playtest instead of a
 * recompile per guess. `vehicle_tune` on its own prints everything.
 *
 *   vehicle_tune power 1100      extra acceleration, units/sec^2
 *   vehicle_tune top 600         speed the assist stops pushing at
 *   vehicle_tune turn 400        extra turn acceleration, deg/sec^2
 *   vehicle_tune turntop 140     turn rate it stops at
 *   vehicle_tune axis x|y|z      which angular component is yaw
 *   vehicle_tune assist 0|1      assist off / on, to feel the raw thrusters
 *   vehicle_tune movetype noclip|none|walk
 *   vehicle_tune lift 150        how far above the car the driver rides
 *   vehicle_tune ride follow|parent|stay
 *   vehicle_tune smooth 0|1      1 = Move() for the ride, 0 = Teleport()
 */
Instance.RegisterCheatCommand("vehicle_tune", (args) => {
  const [what, raw] = args.trim().split(/\s+/);
  const value = Number(raw);
  const number = (setter) => {
    if (!Number.isFinite(value)) { Instance.Msg(`[vehicles] ${what} needs a number`); return; }
    setter(value);
  };

  switch ((what ?? "").toLowerCase()) {
    case "power":    number((v) => { assistAccel = v; }); break;
    case "top":      number((v) => { assistMaxSpeed = v; }); break;
    case "turn":     number((v) => { assistTurnAccel = v; }); break;
    case "turntop":  number((v) => { assistMaxTurnRate = v; }); break;
    case "assist":   number((v) => { assistEnabled = v !== 0; }); break;
    case "axis":
      if (["x", "y", "z"].includes(raw)) assistTurnAxis = raw;
      else Instance.Msg(`[vehicles] axis must be x, y or z`);
      break;
    case "smooth":   number((v) => { rideWithTeleport = v === 0; }); break;
    case "lift":
      number((v) => {
        seatLift = v;
        // Re-seat anyone driving right now so the new height is felt at once.
        for (const [slot, baseName] of driverVehicle) {
          const vehicle = vehicles.get(baseName);
          const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
          if (!vehicle || !pawn || !pawn.IsValid()) continue;

          const target = seatWorldPosition(vehicle);
          if (target) {
            pawn.Teleport({ position: target, velocity: ZERO });
            vehicle.lastSeatTarget = target;
          }
        }
      });
      break;
    case "ride":
      if (["follow", "parent", "stay"].includes(raw)) {
        const leaving = rideMode;
        rideMode = raw;

        // Switching mid-drive has to tidy up after the mode being left.
        for (const [slot, baseName] of driverVehicle) {
          const vehicle = vehicles.get(baseName);
          const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
          if (!vehicle || !pawn || !pawn.IsValid()) continue;

          if (leaving === "parent" && pawn.GetParent()) pawn.SetParent(undefined);
          if (raw === "parent") attachParent(vehicle, pawn);
        }
      } else {
        Instance.Msg(`[vehicles] ride must be follow, parent or stay`);
      }
      break;
    case "movetype":
      if (MOVETYPES[raw] !== undefined) {
        driverMoveType = raw;
        // Apply it to whoever is driving right now, so the change is felt
        // immediately rather than on the next entry.
        for (const slot of driverVehicle.keys()) {
          const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
          if (pawn && pawn.IsValid() && pawn.IsAlive()) pawn.SetMoveType(moveTypeFor(raw));
        }
      } else {
        Instance.Msg(`[vehicles] movetype must be none, noclip or walk`);
      }
      break;
    case "": break;
    default: Instance.Msg(`[vehicles] unknown setting "${what}"`); break;
  }

  Instance.Msg(`[vehicles] assist=${assistEnabled ? "on" : "off"}` +
               ` power=${assistAccel} top=${assistMaxSpeed}` +
               ` turn=${assistTurnAccel} turntop=${assistMaxTurnRate}` +
               ` axis=${assistTurnAxis} movetype=${driverMoveType}` +
               ` ride=${rideMode} smooth=${rideWithTeleport ? 0 : 1} lift=${seatLift}`);

  for (const vehicle of vehicles.values()) {
    const base = vehicleBase(vehicle);
    if (!base) continue;

    const v = base.GetAbsVelocity();
    const a = base.GetAbsAngularVelocity();
    Instance.Msg(`  vehicle ${vehicle.config.id}: speed=${Math.hypot(v.x, v.y).toFixed(0)}` +
                 ` turning=${vehicle.turnRate.toFixed(0)} deg/s` +
                 ` angvel[x=${a.x.toFixed(1)} y=${a.y.toFixed(1)} z=${a.z.toFixed(1)}]`);
  }
  // If "turning" is clearly non-zero while all three angvel components sit at
  // zero, the assist is writing to a component the engine ignores - try the
  // other two with `vehicle_tune axis`.
});

Instance.RegisterCheatCommand("vehicle_dump", () => {
  Instance.Msg(`[vehicles] ${vehicles.size} vehicle(s), ${outputHooks.length} button hook(s)`);

  for (const vehicle of vehicles.values()) {
    const config = vehicle.config;
    const driver = vehicle.driverSlot >= 0
      ? Instance.GetPlayerController(vehicle.driverSlot)?.GetPlayerName() ?? vehicle.driverSlot
      : "-";
    const running = CONTROLS.filter((c) => vehicle.active[c.key]).map((c) => c.key);
    const seat = vehicle.seat
      ? `[${vehicle.seat.x.toFixed(1)} ${vehicle.seat.y.toFixed(1)} ${vehicle.seat.z.toFixed(1)}]`
      : "none";

    Instance.Msg(`  vehicle ${config.id}: base=${vehicleBase(vehicle) ? "ok" : "MISSING"}` +
                 ` driver=${driver} seat=${seat} running=[${running.join(",") || "none"}]` +
                 ` immune=[${[...vehicle.ownNames].join(" ")}]`);
    report(vehicle);
  }
});

Instance.RegisterCheatCommand("vehicle_enter", (args) => {
  const wanted = Number(args.trim());
  const vehicle = [...vehicles.values()].find((v) => v.config.id === wanted)
    ?? [...vehicles.values()][0];
  const pawn = Instance.GetAllPlayerControllers()[0]?.GetPlayerPawn();

  if (vehicle && pawn) {
    reentryBlocked.delete(pawn.GetPlayerController()?.GetPlayerSlot());
    enterVehicle(pawn, vehicle);
  }
});

Instance.RegisterCheatCommand("vehicle_exit", () => exitAll("vehicle_exit", true));

// If a car ever ends up locked with nobody in it (script error, tools reload
// mid-drive), this puts every one of them back in service.
Instance.RegisterCheatCommand("vehicle_reset", () => {
  exitAll("vehicle_reset", false);
  for (const vehicle of vehicles.values()) {
    fire(vehicle.config.button, "Unlock");
    fire(vehicle.config.base, "EnableMotion");
  }
  Instance.Msg(`[vehicles] reset ${vehicles.size} vehicle(s)`);
});

// ----- THRUSTER FORCES ------------------------------------------------------
//
// For reference, what the map currently gives the car. All six thrusters have
// spawnflags 30, which includes Ignore Mass, so "force" is read as acceleration
// in units/sec^2 rather than as a force:
//
//   vehicle_thruster_forward5    350   at the rear, yaw 270 (pushes -Y)
//   vehicle_thruster_backward5   350   at the rear, yaw 90
//   vehicle_left_thrusters5      100   front, yaw 0    (+X)
//   vehicle_left_thrusters5       50   rear,  yaw 180  (-X)
//   vehicle_right_thrusters5     100   front, yaw 180
//   vehicle_right_thrusters5      50   rear,  yaw 0
//
// 350 is about 2 m/s^2 - a car that takes its time. The turn is a 100/50 couple,
// which is where most of the "won't go where I point it" comes from.
//
// The assist above makes this tunable without recompiling, but once you know the
// numbers you like, the tidier home for them is the thrusters themselves: raise
// forward/back to around 800-1000 and the turning pair to 300/150, then turn
// the assist down or off. That keeps the whole car in Hammer where the rest of
// the map can see it, and the script back to being just the game_ui stand-in.
