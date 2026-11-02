import { Instance, CSPlayerPawn, CSPlayerController } from "cs_script/point_script";

// ttt_terrortrain: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `ttt_terrortrain_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   PushIn_<n> / PushOut_<n>   replaces the trigger_push brushes (CS:GO "set speed" behaviour)

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
        "speed": 1100.0,
        "mins": [
            -680.0,
            -4081.0,
            -85.0
        ],
        "maxs": [
            368.0,
            7133.0,
            6.0
        ]
    }
};
// CS:GO trigger_push on players = base velocity (CTriggerPush::Touch, gamemovement.cpp, player_command.cpp CheckMovingGround):
//  - horizontal push moves the player during their move but is not part of their own velocity, so running, air strafing,
//    friction and the 250 run-speed cap all work on the player's own speed (own + push = total). Emulated here by moving the
//    position by push*dt each tick (hull trace, slides along walls) and leaving the engine's velocity alone.
//  - leaving every push hands the push over as momentum: velocity += (1 + dt/2) * push.
//  - vertical push is an acceleration (v.z += push.z * dt), not a set speed; an upward push on the ground lifts the player
//    1u every tick, so they slide with no friction. CS2 can't unground a player, so ground friction is undone instead.
const MAX_VELOCITY = 3500;
const FRICTION = 5.2, STOP_SPEED = 80;   // sv_friction, sv_stopspeed
const PUSH_HULLS = [{ mins: { x: -16, y: -16, z: 2 }, maxs: { x: 16, y: 16, z: 72 } },   // standing, then ducked
                    { mins: { x: -16, y: -16, z: 2 }, maxs: { x: 16, y: 16, z: 54 } }];
/** @type {Map<number, Set<string>>} player slot -> push zones the player is in */
const pushBySlot = new Map();
/** @type {Map<number, {x: number, y: number}>} player slot -> horizontal push applied last tick */
const pushBase = new Map();
let pushTime = 0;

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
        if (zones) zones.delete(id);   // the think loop hands over the momentum once the set is empty
    });
}
function inside(pos, z) {
    const m = 24;   // a little slack: the player box sticks out of the trigger before EndTouch fires
    return pos.x > z.mins[0] - m && pos.x < z.maxs[0] + m && pos.y > z.mins[1] - m && pos.y < z.maxs[1] + m && pos.z > z.mins[2] - 80 && pos.z < z.maxs[2] + m;
}
function clampV(a) { return Math.max(-MAX_VELOCITY, Math.min(MAX_VELOCITY, a)); }
/** Move the hull from pos by d, sliding along what it hits (like the engine's own move). @returns {{x: number, y: number, z: number} | undefined} */
function pushMove(pawn, pos, d) {
    for (const hull of PUSH_HULLS) {
        let start = pos, ex = d.x, ey = d.y, ez = d.z, moved = false, solid = false;
        for (let i = 0; i < 3; i++) {
            const tr = Instance.TraceBox({ mins: hull.mins, maxs: hull.maxs, start, end: { x: start.x + ex, y: start.y + ey, z: start.z + ez },
                                           ignoreEntity: pawn, ignorePlayers: true });
            if (tr.startedInSolid) { solid = !moved; break; }
            const n = tr.normal;
            start = tr.didHit ? { x: tr.end.x + n.x * 0.03, y: tr.end.y + n.y * 0.03, z: tr.end.z + n.z * 0.03 } : tr.end;
            moved = true;
            if (!tr.didHit || tr.fraction >= 1) break;
            const rem = 1 - tr.fraction; ex *= rem; ey *= rem; ez *= rem;
            const into = ex * n.x + ey * n.y + ez * n.z;
            if (into < 0) { ex -= into * n.x; ey -= into * n.y; ez -= into * n.z; }
            if (Math.abs(ex) + Math.abs(ey) + Math.abs(ez) < 0.01) break;
        }
        if (!solid) return moved ? start : undefined;
    }
    return undefined;
}
THINKERS.push(() => {
    const now = Instance.GetGameTime();
    let dt = now - pushTime; pushTime = now;
    if (!(dt > 0.001 && dt < 0.1)) dt = 1 / 64;
    for (const [slot, zones] of pushBySlot) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { pushBySlot.delete(slot); pushBase.delete(slot); continue; }
        const pos = pawn.GetAbsOrigin();
        for (const id of [...zones]) if (!inside(pos, PUSH[id])) zones.delete(id);   // safety net if EndTouch was missed (e.g. trigger disabled)
        const v = pawn.GetAbsVelocity();
        if (zones.size === 0) {   // out of every push: the push becomes the player's own momentum
            const b = pushBase.get(slot), f = 1 + dt * 0.5;
            if (b && (b.x || b.y)) pawn.Move({ velocity: { x: clampV(v.x + b.x * f), y: clampV(v.y + b.y * f), z: v.z } });
            pushBySlot.delete(slot); pushBase.delete(slot); continue;
        }
        let bx = 0, by = 0, bz = 0;
        for (const id of zones) { const zone = PUSH[id]; bx += zone.speed * zone.dir[0]; by += zone.speed * zone.dir[1]; bz += zone.speed * zone.dir[2]; }
        bx = clampV(bx); by = clampV(by); bz = clampV(bz);
        /** @type {{position?: {x: number, y: number, z: number}, velocity?: {x: number, y: number, z: number}}} */
        const mv = {};
        if (bz !== 0) {
            if (pawn.GetGroundEntity() === undefined) mv.velocity = { x: v.x, y: v.y, z: clampV(v.z + bz * dt) };
            else if (bz > 0) {   // lifted off the ground in CS:GO: undo this tick's ground friction
                const s = Math.hypot(v.x, v.y), k = FRICTION * dt;
                if (s > 0.1) {
                    const s0 = s >= STOP_SPEED * (1 - k) ? s / (1 - k) : s + STOP_SPEED * k;
                    mv.velocity = { x: v.x * s0 / s, y: v.y * s0 / s, z: v.z };
                }
            }
        }
        if (bx || by) { const p = pushMove(pawn, pos, { x: bx * dt, y: by * dt, z: 0 }); if (p) mv.position = p; }
        pushBase.set(slot, { x: bx, y: by });
        if (mv.position || mv.velocity) pawn.Move(mv);
    }
    return pushBySlot.size > 0;
});
