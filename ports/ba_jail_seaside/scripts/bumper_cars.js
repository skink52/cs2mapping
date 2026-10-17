// bumper_cars.js  --  ba_jail_skylight
//
// Replacement for the dead game_ui entity.
//
// game_ui still shows up in the CS2 FGD but its implementation is gone, so
// PressedForward / UnpressedForward / PressedMoveLeft / ... never fire. This
// script reads the driver's movement keys directly and fires the exact same
// Activate / Deactivate inputs on the exact same phys_thruster entities the
// carNui entities used to drive. Nothing about the thrusters changes.
//
// Like buff_weapons.js this POLLS the keys and diffs against its own state
// rather than listening for WasInputJustPressed. A poll can be late by a tick,
// but it can't miss an edge and it self-corrects - which matters here, because
// a missed "released" would leave a thruster running forever.
//
// By default the driver does not move at all - they stand at the controls and
// the car drives off without them. RIDE_MODE switches that to being carried
// along if you want it. What it never does is SetParent, which re-reads the
// player's world position as a local offset and flings them across the map.

import { Instance, CSInputs, CSMoveType } from "cs_script/point_script";

// ----- config ---------------------------------------------------------------
const DEBUG = false;   // set false once it's working

const CAR_PREFIX = "car";   // car3 / car3forward / car3seat

// Which key drives which thruster. These are the four game_ui outputs:
// PressedForward, PressedBack, PressedMoveLeft, PressedMoveRight.
const CONTROLS = [
  { input: CSInputs.FORWARD, suffix: "forward"  },
  { input: CSInputs.BACK,    suffix: "backward" },
  { input: CSInputs.LEFT,    suffix: "left"     },
  { input: CSInputs.RIGHT,   suffix: "right"    },
];

// Names the script will try for each car's entry trigger, in order.
const SEAT_SUFFIXES = ["seat", "trigger", "ui"];

// ----- entry buttons --------------------------------------------------------
// +use on a button named car1button puts the presser in car 1 (car2button ->
// car 2, and so on). Works with a func_button (OnPressed) or anything that has
// OnPlayerUse, e.g. a prop_dynamic. No outputs need wiring in Hammer - the
// script hooks the button by name, same as the seat triggers.
const BUTTON_SUFFIX = "button";

// Only this team can get in the cars. 2 = T, 3 = CT, null = anyone.
// Applies to every way of getting in (button, seat trigger, EnterCar input).
const REQUIRED_TEAM = 3;

// ----- riding ---------------------------------------------------------------
// What happens to the driver's body while they're at the controls:
//   "stay"   - they don't move at all. The car drives off on its own and they
//              watch it go, like a remote control. This is the default.
//   "follow" - they're carried along, keeping the gap they had when they got in.
//   "parent" - engine parenting. Smoothest, but SetParent re-reads the player's
//              world position as a local offset, so they get flung on entry.
const RIDE_MODE = "stay";

const FREEZE_DRIVER    = true;   // MOVETYPE_NONE, so they can't walk off mid-drive
const FOLLOW_CAR_YAW   = true;   // "follow" only: swing round with the car
const TURN_VIEW_WITH_CAR = false; // "follow" only: rotate their view too. Disorienting.
const RIDE_WITH_TELEPORT = true; // "follow" only: false uses Move(), can look smoother

// ----- getting out ----------------------------------------------------------
const EXIT_ON_DUCK  = true;   // crouch to disengage
const EXIT_ON_JUMP  = true;   // what game_ui's "Jump Deactivates" spawnflag did
const EXIT_ON_USE   = false;

const ENTER_ON_USE  = false;  // press E near a car; works with no trigger at all
const USE_RADIUS    = 96;     // units, for ENTER_ON_USE

// Where a driver lands when they deliberately get out. Death, disconnect and
// round change release them where they are and don't teleport.
const EXIT_TELEPORT = {
  1: "carblueteleport", 2: "carblueteleport", 3: "carblueteleport", 4: "carblueteleport",
  5: "carredteleport",  6: "carredteleport",  7: "carredteleport",  8: "carredteleport",
};

// The script reads the destination entity's own origin and puts the player
// there, so the point_teleport's Target keyvalue is irrelevant - it works as a
// plain marker. Set this true instead to fire its Teleport input with the
// player as !activator, which needs Target set to !activator in Hammer.
const EXIT_TELEPORT_BY_INPUT = false;
const EXIT_TELEPORT_FACING = true;   // also face them the way the marker points

// Car number -> required team (2 = T / red, 3 = CT / blue). null = anyone drives.
const TEAM_LOCK = null;
// const TEAM_LOCK = { 1: 3, 2: 3, 3: 3, 4: 3, 5: 2, 6: 2, 7: 2, 8: 2 };
// ----------------------------------------------------------------------------

Instance.Msg("[cars] script loaded");

const THRUSTER_PATTERN =
  new RegExp(`^${CAR_PREFIX}(\\d+)(forward|backward|back|left|right)$`, "i");

const ZERO = { x: 0, y: 0, z: 0 };

// car number -> car state
const cars = new Map();
// player slot -> car number
const driverCar = new Map();
// player slot -> was USE held last tick (only used when ENTER_ON_USE)
const useHeld = new Map();
// ConnectOutput ids, so a hot reload doesn't stack duplicate hooks
let outputHooks = [];

function log(text) { if (DEBUG) Instance.Msg(`[cars] ${text}`); }

function normaliseSuffix(suffix) {
  const lower = suffix.toLowerCase();
  return lower === "back" ? "backward" : lower;
}

/** GetAbsOrigin may hand back a live struct; snapshot anything we keep. */
function copyVector(v) { return { x: v.x, y: v.y, z: v.z }; }

function wrapDegrees(degrees) {
  let d = degrees % 360;
  if (d > 180) d -= 360;
  if (d < -180) d += 360;
  return d;
}

// ----- discovery ------------------------------------------------------------

/**
 * Cars are found from phys_thruster names, so adding car9 to the map needs no
 * change here. car3forward/backward/left/right + a body named car3.
 */
function discover() {
  cars.clear();

  for (const thruster of Instance.FindEntitiesByClass("phys_thruster")) {
    const name = thruster.GetEntityName();
    if (!name) continue;

    const match = THRUSTER_PATTERN.exec(name);
    if (!match) continue;

    const id = Number(match[1]);
    let car = cars.get(id);
    if (!car) {
      car = {
        id,
        bodyName: `${CAR_PREFIX}${id}`,
        body: undefined,      // cached handle, re-resolved when it goes invalid
        thrusters: {},        // suffix -> entity name
        active: {},           // suffix -> is it currently running
        driverSlot: -1,
        lastPos: undefined,   // where the car was last tick
        lastYaw: 0,
        lastJump: false,
        lastDuck: false,
        lastUse: false,
      };
      cars.set(id, car);
    }

    const suffix = normaliseSuffix(match[2]);
    car.thrusters[suffix] = name;
    car.active[suffix] = false;

    // Anything left running from last round.
    Instance.EntFireAtName({ name, input: "Deactivate" });
  }

  if (cars.size === 0) {
    Instance.Msg(`[cars] no cars found - expected phys_thruster entities named ` +
                 `"${CAR_PREFIX}1forward" and friends`);
    return;
  }

  log(`found ${cars.size} car(s): ${[...cars.keys()].sort((a, b) => a - b).join(", ")}`);

  for (const car of cars.values()) {
    const missing = CONTROLS
      .filter((control) => !car.thrusters[control.suffix])
      .map((control) => control.suffix);

    if (!carBody(car)) log(`car ${car.id}: WARNING no body entity named "${car.bodyName}"`);
    if (missing.length) log(`car ${car.id}: WARNING missing thrusters: ${missing.join(", ")}`);

    const destination = EXIT_TELEPORT[car.id];
    if (destination && !Instance.FindEntityByName(destination)) {
      log(`car ${car.id}: WARNING exit teleport "${destination}" not found`);
    }
  }
}

function carBody(car) {
  if (car.body && car.body.IsValid()) return car.body;
  car.body = Instance.FindEntityByName(car.bodyName);
  return car.body && car.body.IsValid() ? car.body : undefined;
}

/**
 * Hook each car's entry trigger straight from script - the trigger doesn't need
 * any outputs wired in Hammer, it just needs the right name.
 */
function hookSeatTriggers() {
  // Stale ids after a round restart are expected; don't let one kill the hookup.
  for (const id of outputHooks) {
    try { Instance.DisconnectOutput(id); } catch (error) { /* already gone */ }
  }
  outputHooks = [];

  for (const car of cars.values()) {
    for (const suffix of SEAT_SUFFIXES) {
      for (const trigger of Instance.FindEntitiesByName(`${CAR_PREFIX}${car.id}${suffix}`)) {
        // A leftover game_ui named carNui has no OnStartTouch; the connect just
        // does nothing, which is why "ui" is safe to leave in SEAT_SUFFIXES.
        const hook = Instance.ConnectOutput(trigger, "OnStartTouch",
          ({ activator }) => enterCar(pawnFromEntity(activator), car));

        if (hook !== undefined) {
          outputHooks.push(hook);
          log(`car ${car.id}: entry hooked to "${trigger.GetEntityName()}"`);
        }
      }
    }

    // +use buttons. A func_button fires OnPressed, a usable prop fires
    // OnPlayerUse; hook both and whichever exists does the work. If both ever
    // fire for one press, enterCar ignores the second - the car's already taken.
    const buttonName = `${CAR_PREFIX}${car.id}${BUTTON_SUFFIX}`;
    for (const button of Instance.FindEntitiesByName(buttonName)) {
      for (const output of ["OnPressed", "OnPlayerUse"]) {
        let hook;
        try {
          hook = Instance.ConnectOutput(button, output,
            ({ activator }) => enterCar(pawnFromEntity(activator), car, "button"));
        } catch (error) { continue; }

        if (hook !== undefined) {
          outputHooks.push(hook);
          log(`car ${car.id}: entry hooked to "${buttonName}" ${output}`);
        }
      }
    }
  }
}

/** Map a raw output activator back to a properly typed player pawn. */
function pawnFromEntity(entity) {
  if (!entity || !entity.IsValid()) return undefined;

  for (const controller of Instance.GetAllPlayerControllers()) {
    const pawn = controller.GetPlayerPawn();
    if (pawn && pawn === entity) return pawn;
  }
  return undefined;
}

// ----- driving --------------------------------------------------------------

function setThruster(car, suffix, on) {
  if (car.active[suffix] === on) return;
  car.active[suffix] = on;

  const name = car.thrusters[suffix];
  if (!name) return;

  Instance.EntFireAtName({ name, input: on ? "Activate" : "Deactivate" });
  if (DEBUG) log(`car ${car.id} ${suffix} -> ${on ? "Activate" : "Deactivate"}`);
}

/**
 * Step the driver by however far the car moved since last tick, keeping the gap
 * between them exactly as it was when they got in. No absolute position is ever
 * imposed on the player, which is the whole point - it's the difference between
 * riding the car and being teleported to it.
 */
function rideCar(car, pawn) {
  const body = carBody(car);
  if (!body) return;

  const position = body.GetAbsOrigin();
  const yaw = body.GetAbsAngles().yaw;

  // First tick after entering: record where the car is and move nobody.
  if (!car.lastPos) {
    car.lastPos = copyVector(position);
    car.lastYaw = yaw;
    return;
  }

  const turned = FOLLOW_CAR_YAW ? wrapDegrees(yaw - car.lastYaw) : 0;
  const player = pawn.GetAbsOrigin();

  // Where the driver sits relative to where the car *was*.
  let offsetX = player.x - car.lastPos.x;
  let offsetY = player.y - car.lastPos.y;
  const offsetZ = player.z - car.lastPos.z;

  // Swing that offset round by however much the car turned, so a driver sat off
  // the centre line stays in their seat instead of being left behind the turn.
  if (turned !== 0) {
    const radians = turned * Math.PI / 180;
    const cos = Math.cos(radians);
    const sin = Math.sin(radians);
    const rotatedX = offsetX * cos - offsetY * sin;
    const rotatedY = offsetX * sin + offsetY * cos;
    offsetX = rotatedX;
    offsetY = rotatedY;
  }

  const move = {
    position: { x: position.x + offsetX, y: position.y + offsetY, z: position.z + offsetZ },
  };

  if (TURN_VIEW_WITH_CAR && turned !== 0) {
    const eyes = pawn.GetEyeAngles();
    move.angles = { pitch: eyes.pitch, yaw: wrapDegrees(eyes.yaw + turned), roll: 0 };
  }

  if (RIDE_WITH_TELEPORT) pawn.Teleport(move);
  else pawn.Move(move);

  car.lastPos = copyVector(position);
  car.lastYaw = yaw;
}

function enterCar(pawn, car, via = "trigger") {
  if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) return;

  const controller = pawn.GetPlayerController();
  if (!controller) return;

  if (REQUIRED_TEAM !== null && pawn.GetTeamNumber() !== REQUIRED_TEAM) {
    log(`${controller.GetPlayerName()} blocked from car ${car.id} via ${via} ` +
        `(team ${pawn.GetTeamNumber()}, needs ${REQUIRED_TEAM})`);
    return;
  }

  if (car.driverSlot >= 0) {
    log(`${controller.GetPlayerName()} pressed ${via} for car ${car.id}, but it's taken`);
    return;
  }

  const slot = controller.GetPlayerSlot();
  if (driverCar.has(slot)) return;

  if (TEAM_LOCK && TEAM_LOCK[car.id] && pawn.GetTeamNumber() !== TEAM_LOCK[car.id]) {
    log(`${controller.GetPlayerName()} blocked from car ${car.id} (wrong team)`);
    return;
  }

  car.driverSlot = slot;
  driverCar.set(slot, car.id);

  // Seed the edge-detect state so holding a key on the way in doesn't count as a
  // press - crouch-walking into the seat shouldn't eject you the instant you sit.
  car.lastJump = pawn.IsInputPressed(CSInputs.JUMP);
  car.lastDuck = pawn.IsInputPressed(CSInputs.DUCK);
  car.lastUse = pawn.IsInputPressed(CSInputs.USE);

  // Undefined means "pick this up on the first ride tick", which is what keeps
  // the driver exactly where they were standing.
  car.lastPos = undefined;

  const body = carBody(car);
  if (RIDE_MODE === "parent" && body) pawn.SetParent(body);
  if (FREEZE_DRIVER) pawn.SetMoveType(CSMoveType.NONE);

  log(`${controller.GetPlayerName()} entered car ${car.id}`);
}

/** Put a driver who deliberately got out on their team's exit marker. */
function teleportOut(car, pawn) {
  const name = EXIT_TELEPORT[car.id];
  if (!name) return;

  if (EXIT_TELEPORT_BY_INPUT) {
    // Needs the point_teleport's Target set to !activator.
    Instance.EntFireAtName({ name, input: "Teleport", activator: pawn, caller: pawn });
    return;
  }

  const destination = Instance.FindEntityByName(name);
  if (!destination || !destination.IsValid()) {
    log(`car ${car.id}: exit teleport "${name}" missing, leaving driver in place`);
    return;
  }

  const position = destination.GetAbsOrigin();
  const move = { position: copyVector(position), velocity: ZERO };

  if (EXIT_TELEPORT_FACING) {
    // Pitch and roll are deliberately dropped - a tilted player view is nasty.
    move.angles = { pitch: 0, yaw: destination.GetAbsAngles().yaw, roll: 0 };
  }

  pawn.Teleport(move);
}

/** The PlayerOff path: every thruster off, driver released. */
function exitCar(car, reason, teleport) {
  for (const control of CONTROLS) setThruster(car, control.suffix, false);

  const slot = car.driverSlot;
  car.lastPos = undefined;
  if (slot < 0) return;

  car.driverSlot = -1;
  driverCar.delete(slot);

  const controller = Instance.GetPlayerController(slot);
  const pawn = controller?.GetPlayerPawn();
  if (!pawn || !pawn.IsValid()) return;

  if (RIDE_MODE === "parent") pawn.SetParent(undefined);
  // Unfreeze before teleporting - moving a MOVETYPE_NONE player can leave them
  // stuck in place at the destination.
  if (FREEZE_DRIVER && pawn.IsAlive()) pawn.SetMoveType(CSMoveType.WALK);
  if (teleport && pawn.IsAlive()) teleportOut(car, pawn);

  log(`${controller?.GetPlayerName() ?? slot} left car ${car.id} (${reason})`);
}

function exitBySlot(slot, reason, teleport) {
  const id = driverCar.get(slot);
  if (id === undefined) return;

  const car = cars.get(id);
  if (car) exitCar(car, reason, teleport);
  else driverCar.delete(slot);
}

function exitByPawn(pawn, reason, teleport) {
  const slot = pawn?.GetPlayerController()?.GetPlayerSlot();
  if (slot !== undefined) exitBySlot(slot, reason, teleport);
}

function exitAll(reason, teleport) {
  for (const car of cars.values()) exitCar(car, reason, teleport);
}

function nearestFreeCar(pawn) {
  const origin = pawn.GetAbsOrigin();
  let best;
  let bestDistance = USE_RADIUS;

  for (const car of cars.values()) {
    if (car.driverSlot >= 0) continue;

    const body = carBody(car);
    if (!body) continue;

    const target = body.GetAbsOrigin();
    const distance = Math.hypot(origin.x - target.x, origin.y - target.y, origin.z - target.z);
    if (distance > bestDistance) continue;

    bestDistance = distance;
    best = car;
  }
  return best;
}

// ----- think ----------------------------------------------------------------

Instance.SetThink(() => {
  // Every frame. The thruster state is diffed rather than edge-triggered, so a
  // slower tick would only add input lag, but there's no reason to add any.
  Instance.SetNextThink(Instance.GetGameTime());

  for (const [slot, id] of [...driverCar]) {
    const car = cars.get(id);
    if (!car) { driverCar.delete(slot); continue; }

    const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
    if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) {
      exitCar(car, "driver gone", false);
      continue;
    }

    // Crouch, jump and use are read as raw inputs, not as OnPlayerJump - a
    // frozen driver never actually jumps, so the event would never fire.
    const duck = pawn.IsInputPressed(CSInputs.DUCK);
    const jump = pawn.IsInputPressed(CSInputs.JUMP);
    const use = pawn.IsInputPressed(CSInputs.USE);
    const duckPressed = duck && !car.lastDuck;
    const jumpPressed = jump && !car.lastJump;
    const usePressed = use && !car.lastUse;
    car.lastDuck = duck;
    car.lastJump = jump;
    car.lastUse = use;

    if ((EXIT_ON_DUCK && duckPressed) ||
        (EXIT_ON_JUMP && jumpPressed) ||
        (EXIT_ON_USE && usePressed)) {
      exitCar(car, "got out", true);
      continue;
    }

    // Each key is tested on its own: IsInputPressed with a combined mask means
    // ALL of those keys, and nobody holds W+A+S+D at once.
    for (const control of CONTROLS) {
      setThruster(car, control.suffix, pawn.IsInputPressed(control.input));
    }

    if (RIDE_MODE === "follow") rideCar(car, pawn);
  }

  if (!ENTER_ON_USE) return;

  for (const controller of Instance.GetAllPlayerControllers()) {
    if (!controller.IsConnected()) continue;

    const slot = controller.GetPlayerSlot();
    if (driverCar.has(slot)) continue;

    const pawn = controller.GetPlayerPawn();
    if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { useHeld.delete(slot); continue; }

    const use = pawn.IsInputPressed(CSInputs.USE);
    const pressed = use && !useHeld.get(slot);
    useHeld.set(slot, use);

    if (!pressed) continue;

    const car = nearestFreeCar(pawn);
    if (car) enterCar(pawn, car);
  }
});

// ----- lifecycle ------------------------------------------------------------

function start() {
  discover();
  hookSeatTriggers();
  Instance.SetNextThink(Instance.GetGameTime());
}

Instance.OnActivate(start);
Instance.OnScriptReload({ after: start });   // keeps working after a hot reload in tools

Instance.OnRoundStart(() => {
  exitAll("round start", false);
  // Re-discover on a short delay - map entities aren't necessarily back yet on
  // the frame the round starts.
  Instance.Delay(0.5).then(start);
});
Instance.OnBeginRoundRestart(() => exitAll("round restart", false));
Instance.OnPlayerKill(({ player }) => exitByPawn(player, "died", false));
Instance.OnPlayerReset(({ player }) => exitByPawn(player, "respawned", false));
Instance.OnPlayerDisconnect(({ playerSlot }) => {
  exitBySlot(playerSlot, "disconnected", false);
  useHeld.delete(playerSlot);
});

// Lets the map fire this instead of using a named trigger:
//   <your trigger>  OnStartTouch  ->  <point_script>  CallScriptInput  ->  EnterCar
// The car is picked from the caller's name if it matches, else by proximity.
Instance.OnScriptInput("EnterCar", ({ caller, activator }) => {
  const pawn = pawnFromEntity(activator);
  if (!pawn) return;

  const name = caller?.GetEntityName() ?? "";
  const match = new RegExp(`^${CAR_PREFIX}(\\d+)`, "i").exec(name);
  const car = match ? cars.get(Number(match[1])) : nearestFreeCar(pawn);

  if (car) enterCar(pawn, car);
});

Instance.OnScriptInput("ExitCar", ({ activator }) => {
  const pawn = pawnFromEntity(activator);
  if (pawn) exitByPawn(pawn, "script input", true);
});

// ----- console (needs sv_cheats 1) ------------------------------------------

Instance.RegisterCheatCommand("cars_dump", () => {
  Instance.Msg(`[cars] ${cars.size} car(s), ${outputHooks.length} trigger hook(s)`);

  for (const car of [...cars.values()].sort((a, b) => a.id - b.id)) {
    const driver = car.driverSlot >= 0
      ? Instance.GetPlayerController(car.driverSlot)?.GetPlayerName() ?? car.driverSlot
      : "-";
    const running = CONTROLS
      .filter((control) => car.active[control.suffix])
      .map((control) => control.suffix);
    const destination = EXIT_TELEPORT[car.id];

    Instance.Msg(`  car ${car.id}: body=${carBody(car) ? "ok" : "MISSING"}` +
                 ` thrusters=[${CONTROLS.map((c) => car.thrusters[c.suffix] ?? "MISSING").join(", ")}]` +
                 ` exit=${destination ? (Instance.FindEntityByName(destination) ? destination : `${destination} MISSING`) : "none"}` +
                 ` driver=${driver} running=[${running.join(",") || "none"}]`);
  }
});

Instance.RegisterCheatCommand("cars_enter", (args) => {
  const car = cars.get(Number(args.trim()));
  if (!car) { Instance.Msg(`[cars] usage: cars_enter <number>`); return; }

  const pawn = Instance.GetAllPlayerControllers()[0]?.GetPlayerPawn();
  if (pawn) enterCar(pawn, car);
});

Instance.RegisterCheatCommand("cars_exit", () => exitAll("cars_exit", true));
