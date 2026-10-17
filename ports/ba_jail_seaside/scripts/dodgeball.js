// dodgeball.js
//
// Knife-launched dodgeball. Something presses the start button, and START_DELAY
// seconds later the balls go live: knife one and it flies wherever you were
// looking, killing anyone it passes through until it slows down and settles,
// at which point it's safe to walk up to and knife again.
//
// Setup:
//   1. This file goes in  content/csgo_addons/ba_jail_seaside/scripts/
//   2. Add a point_script entity, set its "cs_script" field to
//      scripts/dodgeball.vjs
//   3. Wire the buttons. This script does NOT listen to button outputs - it is
//      driven entirely by things fired AT it, which is far less fragile. Two
//      options, pick one per button:
//
//        a) RunScriptInput (recommended, works everywhere). On the button:
//               Output:  OnPressed
//               Target:  <the point_script entity's name>
//               Input:   RunScriptInput
//               Param:   dodgeball_start        (or dodgeball_stop)
//
//        b) A server command, via a point_servercommand the button triggers:
//               Command: dodgeball_start        (or dodgeball_stop)
//           NOTE: cs_script can only register console commands as CHEAT
//           commands, so this path does nothing unless sv_cheats is 1. Fine for
//           testing in tools mode, no good on the live server - use (a) there.
//
// WHY BALLS ARE FOUND BY PREFIX, NOT BY EXACT NAME: the balls are spawned by a
// point_template (dBall_temp / ForceSpawn), so they do not exist yet when this
// script activates and resolving them up front finds nothing. Discovery is
// therefore lazy - anything of class BALL_CLASS whose name starts with
// BALL_PREFIX counts, whenever it shows up. Prefix rather than exact match also
// means it keeps working if a template ever does mangle the names into
// "Dball_1&0001" style, which Source is known to do.
//
// HOW THE KILL WORKS: cs_script has no collision or touch callback, so this is
// not the engine's physics crush damage - that's mass-dependent, inconsistent at
// glancing angles, and gives the knifer no credit. The think function sweeps
// each ball's path every tick and applies a forced-death CRUSH hit to anyone it
// swept through. That's also what makes the speed threshold work: under
// KILL_SPEED the ball is simply inert, so "settles, then can be knifed again"
// needs no extra state at all.

import { Instance, CSDamageTypes, CSDamageFlags } from "cs_script/point_script";

// ----- config ---------------------------------------------------------------
const BALL_CLASS  = "func_physbox";   // "" to accept any class
const BALL_PREFIX = "Dball_";         // runtime names start with this; "" to accept any name

const START_DELAY = 4.5;              // seconds between the press and going live

const KNIFE_RANGE    = 65;            // units ahead of the eye the knife can reach
const KNIFE_COOLDOWN = 0.3;           // per ball, so swings can't be spammed
const LAUNCH_SPEED   = 5000;          // units/sec. Velocity is SET, not added, so
                                      // repeated swings can't compound it

const BALL_RADIUS = 32;               // roughly half the ball brush's width
const KILL_SPEED  = 400;              // below this the ball is harmless
const SELF_GRACE  = 0.2;              // seconds the knifer is immune to their own hit

const PLAYER_RADIUS = 16;             // standard CS2 player hull
const PLAYER_HEIGHT = 72;             // standing; a crouched player is a little short

const SCAN_INTERVAL = 0.5;            // seconds between sweeps for newly spawned balls

// Set this false to skip the arming step entirely - the balls are then always
// knifeable. Use it to test the launch-and-kill core on its own, with the whole
// button/start/stop question taken out of the picture, then turn it back on.
const REQUIRE_START = true;

const DEBUG       = false;            // flip to true to narrate start/stop/kills
const DEBUG_KNIFE = false;            // flip to true to log what every swing traced into
// ----------------------------------------------------------------------------

function log(text) { if (DEBUG) Instance.Msg(`[dodgeball] ${text}`); }

log("script loaded");

// ----- vector helpers -------------------------------------------------------
function forward(angle) {
  const pitch = (angle.pitch / 180) * Math.PI;
  const yaw   = (angle.yaw   / 180) * Math.PI;
  const cosPitch = Math.cos(pitch);
  return {
    x: cosPitch * Math.cos(yaw),
    y: cosPitch * Math.sin(yaw),
    z: -Math.sin(pitch),
  };
}
function add(a, b) { return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z }; }
function sub(a, b) { return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z }; }
function mul(a, s) { return { x: a.x * s,   y: a.y * s,   z: a.z * s   }; }
function len(a)    { return Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z); }

// ----- state ----------------------------------------------------------------
// entity -> { ent, name, prevPos, lastHit, knifer, kniferUntil }
let tracked = new Map();
let active = false;      // is the game live right now
let startAt = 0;         // game time the game goes live; 0 = nothing pending
let nextScan = 0;

// With REQUIRE_START off, the arming logic and the round-start teardown are
// both bypassed and the balls are permanently live.
function isLive() { return !REQUIRE_START || active; }

function nameOf(pawn) {
  const controller = pawn.GetPlayerController();
  return controller ? controller.GetPlayerName() : "?";
}

function alivePawns() {
  const out = [];
  for (const controller of Instance.GetAllPlayerControllers()) {
    const pawn = controller.GetPlayerPawn();
    if (pawn && pawn.IsValid() && pawn.IsAlive()) out.push(pawn);
  }
  return out;
}

// ----- ball discovery -------------------------------------------------------
function isBall(ent) {
  if (!ent || !ent.IsValid()) return false;
  if (BALL_CLASS && ent.GetClassName() !== BALL_CLASS) return false;
  if (!BALL_PREFIX) return true;
  const name = ent.GetEntityName() || "";
  return name.startsWith(BALL_PREFIX);
}

// The map's old server-command dodgeball logic drives the balls' motion state
// (Wake/EnableMotion on "GO!", Sleep/DisableMotion on "Game Over!"). Starting
// from the console bypasses that chain, so the balls can sit there motion-
// disabled and silently ignore a launch. Ask for motion ourselves.
function wake(ent) {
  Instance.EntFireAtTarget({ target: ent, input: "EnableMotion" });
  Instance.EntFireAtTarget({ target: ent, input: "Wake" });
}

function trackFor(ent) {
  let ball = tracked.get(ent);
  if (!ball) {
    ball = {
      ent,
      name: ent.GetEntityName() || "(unnamed)",
      prevPos: ent.GetAbsOrigin(),
      lastHit: 0,
      knifer: undefined,
      kniferUntil: 0,
    };
    tracked.set(ent, ball);
    log(`found ball "${ball.name}"`);
  }
  return ball;
}

function rescan(now) {
  if (now < nextScan) return;
  nextScan = now + SCAN_INTERVAL;

  for (const ent of Instance.FindEntitiesByClass(BALL_CLASS || "func_physbox")) {
    if (isBall(ent)) trackFor(ent);
  }
  // Template-spawned balls get Broken and re-spawned, so drop the dead ones.
  for (const [ent, ball] of tracked) {
    if (!ent.IsValid()) {
      tracked.delete(ent);
      log(`lost ball "${ball.name}"`);
    }
  }
}

// ----- start / stop ---------------------------------------------------------
function requestStart(reason) {
  if (active) { log(`start from ${reason} ignored - already live`); return; }
  const now = Instance.GetGameTime();
  startAt = now + START_DELAY;
  nextScan = 0;                    // pick up balls that spawned while we were idle
  log(`armed by ${reason} - going live in ${START_DELAY}s`);
  Instance.SetNextThink(now);      // wake the think function back up
}

function deactivate() {
  active = false;
  startAt = 0;
  // Don't leave anything careening around the room after the game ends.
  for (const [ent, ball] of tracked) {
    if (ent.IsValid()) ent.Teleport({ velocity: { x: 0, y: 0, z: 0 } });
    ball.knifer = undefined;
  }
}

function stopGame(reason) {
  if (active)       { deactivate(); log(`stopped by ${reason}`); }
  else if (startAt) { deactivate(); log(`pending start cancelled by ${reason}`); }
  else              { log(`stop from ${reason}, but nothing was running`); }
}

// ----- launching ------------------------------------------------------------
Instance.OnKnifeAttack((event) => {
  const owner = event.weapon.GetOwner();
  if (!owner || !owner.IsValid() || !owner.IsAlive()) return;

  const eye = owner.GetEyePosition();
  const dir = forward(owner.GetEyeAngles());

  // ignorePlayers so a body between the knifer and the ball doesn't eat the
  // swing. The world still blocks it, so you can't knife through a wall.
  const trace = Instance.TraceLine({
    start: eye,
    end: add(eye, mul(dir, KNIFE_RANGE)),
    ignorePlayers: true,
  });

  if (DEBUG_KNIFE) {
    const hit = trace.didHit && trace.hitEntity
      ? `"${trace.hitEntity.GetEntityName() || "(unnamed)"}" (${trace.hitEntity.GetClassName()})`
      : trace.didHit ? "world" : "nothing";
    Instance.Msg(`[dodgeball] ${nameOf(owner)} swung, traced ${hit}` +
                 `, live=${isLive()}` +
                 (REQUIRE_START ? ` (active=${active} pending=${startAt > 0})` : ""));
  }

  if (!isLive()) return;                      // dead until the game is live
  if (!trace.didHit || !trace.hitEntity) return;
  if (!isBall(trace.hitEntity)) return;

  const ball = trackFor(trace.hitEntity);
  const now = Instance.GetGameTime();
  if (now - ball.lastHit < KNIFE_COOLDOWN) return;

  ball.lastHit = now;
  ball.knifer = owner;
  ball.kniferUntil = now + SELF_GRACE;
  ball.prevPos = ball.ent.GetAbsOrigin();     // don't sweep from a stale position

  ball.ent.Teleport({ velocity: mul(dir, LAUNCH_SPEED) });
  log(`${nameOf(owner)} launched "${ball.name}"`);
});

// ----- the lethal sweep -----------------------------------------------------
function sweep(ball, from, to, pawns, now) {
  const step = sub(to, from);
  const dist = len(step);

  // Break this tick's travel into hops no longer than the ball's radius. At
  // 5000 u/s the ball covers ~78 units per tick, easily enough to skip clean
  // past somebody between two position samples.
  const hops = Math.max(1, Math.ceil(dist / BALL_RADIUS));
  const reach = BALL_RADIUS + PLAYER_RADIUS;

  for (let i = 1; i <= hops; i++) {
    const p = add(from, mul(step, i / hops));

    for (const pawn of pawns) {
      if (!pawn.IsValid() || !pawn.IsAlive()) continue;   // already killed this tick
      if (ball.knifer === pawn && now < ball.kniferUntil) continue;

      const o = pawn.GetAbsOrigin();                      // player origin is at the feet
      const dx = p.x - o.x;
      const dy = p.y - o.y;
      if (dx * dx + dy * dy > reach * reach) continue;
      if (p.z + BALL_RADIUS < o.z) continue;
      if (p.z - BALL_RADIUS > o.z + PLAYER_HEIGHT) continue;

      const attacker = ball.knifer && ball.knifer.IsValid() ? ball.knifer : undefined;
      pawn.TakeDamage({
        damage: 1000,
        damageTypes: CSDamageTypes.CRUSH,
        damageFlags: CSDamageFlags.FORCE_DEATH | CSDamageFlags.IGNORE_ARMOR,
        inflictor: ball.ent,
        attacker,
      });
      log(`"${ball.name}" killed ${nameOf(pawn)}`);
    }
  }
}

Instance.SetThink(() => {
  const now = Instance.GetGameTime();

  if (startAt > 0 && now >= startAt) {
    startAt = 0;
    active = true;
    nextScan = 0;
    rescan(now);
    for (const [ent, ball] of tracked) {
      if (!ent.IsValid()) continue;
      ball.prevPos = ent.GetAbsOrigin();
      wake(ent);
    }
    log(`live - ${tracked.size} ball(s) knifeable`);
  }

  // Nothing pending and nothing running: stop thinking entirely. requestStart
  // is what wakes this back up.
  if (REQUIRE_START && !active && startAt === 0) return;

  Instance.SetNextThink(now);           // every tick, so a fast ball can't slip a frame
  if (!isLive()) return;                // still counting down

  rescan(now);

  const pawns = alivePawns();
  for (const [ent, ball] of tracked) {
    if (!ent.IsValid()) continue;
    const from = ball.prevPos;
    const to = ent.GetAbsOrigin();
    ball.prevPos = to;
    if (pawns.length === 0) continue;
    if (len(ent.GetAbsVelocity()) < KILL_SPEED) continue;   // settled = harmless
    sweep(ball, from, to, pawns, now);
  }
});

// ----- wiring ---------------------------------------------------------------
// Everything that drives this script is fired AT the point_script rather than
// listened for on a button, so there are no output connections to manage.
Instance.OnScriptInput("dodgeball_start", () => requestStart("RunScriptInput"));
Instance.OnScriptInput("dodgeball_stop", () => stopGame("RunScriptInput"));

function start() {
  active = false;
  startAt = 0;
  nextScan = 0;
  tracked = new Map();
  if (!REQUIRE_START) {
    log("REQUIRE_START is off - balls are permanently knifeable");
    Instance.SetNextThink(Instance.GetGameTime());
  }
}

Instance.OnActivate(start);
Instance.OnScriptReload({ after: start });

Instance.OnRoundStart(() => {
  // This is the single most likely reason a game you just started has gone
  // quiet on you: a round restart tears it down. Now it says so.
  if (REQUIRE_START) {
    if (active || startAt) log("round start - tearing the game down");
    deactivate();
  }
  tracked = new Map();      // the template respawns them; rediscover from scratch
  nextScan = 0;
  if (!REQUIRE_START) Instance.SetNextThink(Instance.GetGameTime());
});

// ----- console commands (need sv_cheats 1) ---------------------------------
Instance.RegisterCheatCommand("dodgeball_start", () => requestStart("console"));
Instance.RegisterCheatCommand("dodgeball_stop", () => stopGame("console"));

Instance.RegisterCheatCommand("dball_dump", () => {
  const now = Instance.GetGameTime();
  rescan(0);
  Instance.Msg(`[dodgeball] active=${active}` +
               ` pending=${startAt > 0 ? (startAt - now).toFixed(2) + "s" : "no"}` +
               ` tracked=${tracked.size}`);
  for (const [ent, ball] of tracked) {
    if (!ent.IsValid()) { Instance.Msg(`  ${ball.name}: INVALID`); continue; }
    const speed = len(ent.GetAbsVelocity());
    Instance.Msg(`  "${ball.name}" (${ent.GetClassName()})` +
                 ` speed=${speed.toFixed(0)} lethal=${speed >= KILL_SPEED}`);
  }
});

// The important diagnostic: what func_physbox entities actually exist right
// now, and what are they really called at runtime?
Instance.RegisterCheatCommand("dball_scan", () => {
  const all = Instance.FindEntitiesByClass(BALL_CLASS || "func_physbox");
  Instance.Msg(`[dodgeball] ${all.length} x ${BALL_CLASS} in the map:`);
  for (const ent of all) {
    const name = ent.GetEntityName() || "(unnamed)";
    const o = ent.GetAbsOrigin();
    Instance.Msg(`  "${name}" matchesPrefix=${isBall(ent)}` +
                 ` at ${o.x.toFixed(0)} ${o.y.toFixed(0)} ${o.z.toFixed(0)}`);
  }
});
