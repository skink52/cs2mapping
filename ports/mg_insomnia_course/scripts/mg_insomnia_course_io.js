import { Instance, CSPlayerPawn, CSPlayerController, CSMoveType } from "cs_script/point_script";

// mg_insomnia_course: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_insomnia_course_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   PushIn_<n> / PushOut_<n>   replaces the trigger_push brushes (CS:GO "set speed" behaviour)
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

// ---------------------------------------------------------------- trigger_push replacement
// CS2's trigger_push keeps adding velocity every tick while you are inside it, so CS:GO pushes became rocket launchers.
// CS:GO's push simply moved you at the push speed in the push direction. Each former trigger_push is now a
// trigger_multiple that fires PushIn_<id> / PushOut_<id>; while a player is inside, their velocity along the push
// direction is held at the push speed (sideways / other movement is left alone), clamped to sv_maxvelocity (3500).
/** @type {Record<string, { dir: number[], speed: number, mins: number[], maxs: number[] }>} */
const PUSH = {
    "1": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 350.0,
        "mins": [
            -1477.0,
            2544.0,
            458.0
        ],
        "maxs": [
            -1291.0,
            3439.309326171875,
            647.0
        ]
    },
    "2": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 260.0,
        "mins": [
            -1691.0,
            -1566.0,
            305.0
        ],
        "maxs": [
            -1580.0,
            -618.0,
            494.0
        ]
    },
    "3": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            74.0,
            1057.0,
            -123.0
        ],
        "maxs": [
            161.0,
            2504.0,
            66.0
        ]
    }
};
const MAX_VELOCITY = 3500;
/** @type {Map<number, Set<string>>} player slot -> push zones the player is in */
const pushBySlot = new Map();

/** @param {any} ent @returns {CSPlayerPawn | undefined} */
function toPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
function slotOf(pawn) { const c = pawn.GetPlayerController(); return c ? c.GetPlayerSlot() : -1; }
function startPushThink() { if (pushBySlot.size > 0) wakeThink(); }
for (const id of Object.keys(PUSH)) {
    Instance.OnScriptInput("PushIn_" + id, ({ activator }) => {
        const pawn = toPawn(activator);
        if (!pawn || !pawn.IsValid()) return;
        const slot = slotOf(pawn);
        if (slot < 0) return;
        if (!pushBySlot.has(slot)) pushBySlot.set(slot, new Set());
        pushBySlot.get(slot).add(id);
        startPushThink();
    });
    Instance.OnScriptInput("PushOut_" + id, ({ activator }) => {
        const pawn = toPawn(activator);
        if (!pawn || !pawn.IsValid()) return;
        const zones = pushBySlot.get(slotOf(pawn));
        if (zones) { zones.delete(id); if (zones.size === 0) pushBySlot.delete(slotOf(pawn)); }
    });
}
function inside(pos, z) {
    const m = 24;   // a little slack: the player box sticks out of the trigger before EndTouch fires
    return pos.x > z.mins[0] - m && pos.x < z.maxs[0] + m && pos.y > z.mins[1] - m && pos.y < z.maxs[1] + m && pos.z > z.mins[2] - 80 && pos.z < z.maxs[2] + m;
}
THINKERS.push(() => {
    for (const [slot, zones] of pushBySlot) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { pushBySlot.delete(slot); continue; }
        const pos = pawn.GetAbsOrigin();
        let v = pawn.GetAbsVelocity();
        let x = v.x, y = v.y, z = v.z, changed = false;
        for (const id of [...zones]) {
            const zone = PUSH[id];
            if (!inside(pos, zone)) { zones.delete(id); continue; }   // safety net if EndTouch was missed (e.g. trigger disabled)
            const [dx, dy, dz] = zone.dir;
            const along = x * dx + y * dy + z * dz;
            const target = Math.min(zone.speed, MAX_VELOCITY);
            const add = target - along;
            x += add * dx; y += add * dy; z += add * dz;
            changed = true;
        }
        if (zones.size === 0) pushBySlot.delete(slot);
        if (changed) pawn.Move({ velocity: { x, y, z } });
    }
    return pushBySlot.size > 0;
});

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
for (const g of [0.2, 0.3, 1.0]) {
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
