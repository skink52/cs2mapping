import { Instance, CSPlayerPawn, CSPlayerController, CSInputs, CSMoveType } from "cs_script/point_script";

// mg_crash_bandicoot_course: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_crash_bandicoot_course_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   Score_<pts> replaces game_score (ApplyScore)
//   Speed_<mult> replaces player_speedmod ModifySpeed (activator only, 1 = back to normal)
//   Gravity_<scale> replaces trigger_gravity (activator only, 1 = back to normal; the trigger fires Gravity_1 on leaving)

// ---------------------------------------------------------------- shared think loop
/** @type {(() => boolean)[]} each returns true while it still needs ticks */
const THINKERS = [];
let thinking = false;
function wakeThink() { if (!thinking) { thinking = true; Instance.SetNextThink(Instance.GetGameTime()); } }
Instance.SetThink(() => {
    let active = false;
    for (const t of THINKERS) if (t()) active = true;
    if (active) Instance.SetNextThink(Instance.GetGameTime()); else thinking = false;
});

// ---------------------------------------------------------------- game_score replacement (entity removed in CS2)
// Outputs that fired <game_score>.ApplyScore now fire Score_<points>; the activator's scoreboard score goes up.
for (const pts of [4000]) {
    Instance.OnScriptInput("Score_" + pts, ({ activator }) => {
        const pawn = activator instanceof CSPlayerPawn ? activator : undefined;
        const ctrl = pawn ? pawn.GetPlayerController() : (activator instanceof CSPlayerController ? activator : undefined);
        if (ctrl && ctrl.IsValid()) ctrl.AddScore(pts);
    });
}

// ---------------------------------------------------------------- player_speedmod replacement (dead in CS2)
// While a player has a multiplier, their ground speed is driven from their own movement keys at 250 x mult.
const BASE_SPEED = 250, WALK_FACTOR = 0.52, DUCK_FACTOR = 0.34;
/** @type {Map<number, number>} player slot -> speed multiplier */
const speedBySlot = new Map();
function speedPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
THINKERS.push(() => {
    for (const [slot, mult] of speedBySlot) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { speedBySlot.delete(slot); continue; }
        if (!pawn.GetGroundEntity()) continue;
        const fwd = (pawn.IsInputPressed(CSInputs.FORWARD) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.BACK) ? 1 : 0);
        const side = (pawn.IsInputPressed(CSInputs.RIGHT) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.LEFT) ? 1 : 0);
        if (fwd === 0 && side === 0) continue;
        const yaw = pawn.GetEyeAngles().yaw * Math.PI / 180;
        let dx = Math.cos(yaw) * fwd + Math.sin(yaw) * side;
        let dy = Math.sin(yaw) * fwd - Math.cos(yaw) * side;
        const len = Math.hypot(dx, dy); dx /= len; dy /= len;
        let speed = BASE_SPEED * mult;
        if (pawn.IsInputPressed(CSInputs.WALK)) speed *= WALK_FACTOR;
        if (pawn.IsDucking()) speed *= DUCK_FACTOR;
        pawn.Move({ velocity: { x: dx * speed, y: dy * speed, z: pawn.GetAbsVelocity().z } });
    }
    return speedBySlot.size > 0;
});
for (const s of [0.1]) {
    Instance.OnScriptInput("Speed_" + s, ({ activator }) => {
        const pawn = speedPawn(activator);
        const ctrl = pawn ? pawn.GetPlayerController() : undefined;
        if (!ctrl) return;
        if (s === 1) speedBySlot.delete(ctrl.GetPlayerSlot()); else speedBySlot.set(ctrl.GetPlayerSlot(), s);
        wakeThink();
    });
}

// ---------------------------------------------------------------- trigger_gravity replacement (does nothing to players in CS2)
// CS2 players have no gravity scale, so while a player is airborne the script gives back the part of sv_gravity the
// scale removes (0.2 -> 80% of 800 pushed back up every tick). Leaving the trigger (OnEndTouch -> Gravity_1) or respawning resets it.
const SV_GRAVITY = 800;
/** @type {Map<number, number>} player slot -> gravity scale (only non-1 values are stored) */
const gravityBySlot = new Map();
let gravityLast = 0;
function gravityPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
THINKERS.push(() => {
    const now = Instance.GetGameTime();
    const dt = Math.min(Math.max(now - gravityLast, 0), 0.1);
    gravityLast = now;
    for (const [slot, g] of gravityBySlot) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { gravityBySlot.delete(slot); continue; }
        if (pawn.GetGroundEntity() || pawn.GetMoveType() !== CSMoveType.WALK) continue;
        const v = pawn.GetAbsVelocity();
        pawn.Move({ velocity: { x: v.x, y: v.y, z: v.z + (1 - g) * SV_GRAVITY * dt } });
    }
    return gravityBySlot.size > 0;
});
for (const g of [-2.0, 1.0]) {
    Instance.OnScriptInput("Gravity_" + g, ({ activator }) => {
        const ctrl = gravityPawn(activator)?.GetPlayerController();
        if (!ctrl) return;
        if (g === 1) gravityBySlot.delete(ctrl.GetPlayerSlot()); else gravityBySlot.set(ctrl.GetPlayerSlot(), g);
        if (gravityBySlot.size > 0) { gravityLast = Instance.GetGameTime(); wakeThink(); }
    });
}
// every life starts at normal gravity (CS:GO reset the scale on respawn too)
Instance.OnPlayerReset(({ player }) => {
    const slot = player.GetPlayerController()?.GetPlayerSlot();
    if (slot !== undefined) gravityBySlot.delete(slot);
});
