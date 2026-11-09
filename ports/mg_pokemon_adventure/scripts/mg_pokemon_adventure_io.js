import { Instance, CSPlayerPawn, CSPlayerController } from "cs_script/point_script";

// mg_pokemon_adventure: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_pokemon_adventure_io_script` -> RunScriptInput <input name>, with the activator passed through.
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
            0.0,
            1.0
        ],
        "speed": 40.0,
        "mins": [
            1440.0,
            192.0,
            -320.0
        ],
        "maxs": [
            1536.0,
            288.0,
            -240.0
        ]
    },
    "2": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 40.0,
        "mins": [
            1536.0,
            -256.0,
            -256.0
        ],
        "maxs": [
            1632.0,
            -160.0,
            -176.0
        ]
    },
    "3": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 40.0,
        "mins": [
            1632.0,
            0.0,
            -192.0
        ],
        "maxs": [
            1728.0,
            96.0,
            -112.0
        ]
    },
    "4": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 2000.0,
        "mins": [
            -1937.0107421875,
            -832.0,
            4928.0
        ],
        "maxs": [
            -1350.47900390625,
            -449.1466064453125,
            5184.0
        ]
    },
    "5": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 2000.0,
        "mins": [
            -257.685546875,
            -672.0,
            5553.22998046875
        ],
        "maxs": [
            328.84765625,
            -289.15234375,
            5920.0
        ]
    },
    "6": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 2000.0,
        "mins": [
            -3264.0,
            -1728.0,
            4256.0
        ],
        "maxs": [
            -2660.5498046875,
            -1414.3603515625,
            4480.0
        ]
    },
    "7": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 1500.0,
        "mins": [
            -1280.0,
            128.0,
            3968.0
        ],
        "maxs": [
            -1152.0,
            8416.0,
            4096.0
        ]
    },
    "8": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            3904.0,
            12224.0,
            -704.0
        ],
        "maxs": [
            4288.0,
            12288.0,
            -576.0
        ]
    },
    "9": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            3904.0,
            11968.0,
            -704.0
        ],
        "maxs": [
            3968.0,
            12224.0,
            -576.0
        ]
    },
    "10": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            3584.0,
            11968.0,
            -704.0
        ],
        "maxs": [
            3904.0,
            12032.0,
            -576.0
        ]
    },
    "11": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            3520.0,
            11264.0,
            -704.0
        ],
        "maxs": [
            3584.0,
            12032.0,
            -576.0
        ]
    },
    "12": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            3200.0,
            11264.0,
            -704.0
        ],
        "maxs": [
            3520.0,
            11328.0,
            -576.0
        ]
    },
    "13": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            2112.0,
            11264.0,
            -704.0
        ],
        "maxs": [
            3008.0,
            11328.0,
            -576.0
        ]
    },
    "14": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            6528.0,
            3904.0,
            -672.0
        ],
        "maxs": [
            6592.0,
            4672.0,
            -576.0
        ]
    },
    "15": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            6592.0,
            4608.0,
            -672.0
        ],
        "maxs": [
            6784.0,
            4672.0,
            -576.0
        ]
    },
    "16": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            6720.0,
            4672.0,
            -672.0
        ],
        "maxs": [
            6784.0,
            4928.0,
            -576.0
        ]
    },
    "17": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            6272.0,
            4864.0,
            -672.0
        ],
        "maxs": [
            6720.0,
            4928.0,
            -576.0
        ]
    },
    "18": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            6272.0,
            4928.0,
            -672.0
        ],
        "maxs": [
            6336.0,
            5184.0,
            -576.0
        ]
    },
    "19": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            6272.0,
            5184.0,
            -672.0
        ],
        "maxs": [
            6592.0,
            5504.0,
            -576.0
        ]
    },
    "20": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            6528.0,
            5504.0,
            -672.0
        ],
        "maxs": [
            6592.0,
            5696.0,
            -576.0
        ]
    },
    "21": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            6368.0,
            4000.0,
            -800.0
        ],
        "maxs": [
            6400.0,
            4384.0,
            -768.0
        ]
    },
    "22": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            6400.0,
            4352.0,
            -808.0
        ],
        "maxs": [
            6752.0,
            4384.0,
            -768.0
        ]
    },
    "23": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            6400.0,
            4000.0,
            -800.0
        ],
        "maxs": [
            6720.0,
            4032.0,
            -768.0
        ]
    },
    "24": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            6720.0,
            4000.0,
            -800.0
        ],
        "maxs": [
            6752.0,
            4352.0,
            -768.0
        ]
    },
    "25": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            6400.0,
            3968.0,
            -672.0
        ],
        "maxs": [
            6528.0,
            4416.0,
            -576.0
        ]
    },
    "26": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            6592.0,
            3968.0,
            -672.0
        ],
        "maxs": [
            6720.0,
            4416.0,
            -576.0
        ]
    },
    "27": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1200.0,
        "mins": [
            6400.0,
            4032.0,
            -3520.0
        ],
        "maxs": [
            6720.0,
            4352.0,
            -832.0
        ]
    }
};
// CS:GO trigger_push on players = base velocity (CTriggerPush::Touch, gamemovement.cpp, player_command.cpp CheckMovingGround):
//  - horizontal push moves the player during their move but is not part of their own velocity, so running, air strafing,
//    friction and the 250 run-speed cap all work on the player's own speed (own + push = total). Emulated here by moving the
//    position by push*dt each tick (hull trace, slides along walls) and leaving the engine's velocity alone.
//  - leaving every push hands the push over as momentum: velocity += (1 + dt/2) * push.
//  - vertical push is an acceleration (v.z += push.z * dt), not a set speed; an upward push on the ground lifts the player
//    1u every tick, so they slide with no friction. CS2 can't unground a player, so ground friction is undone instead: only what
//    this tick actually took off and never past last tick's speed. Assuming the full friction grew speed about 9% a tick wherever the real
//    friction was lower (slides, water), which is what made an up push feel like a forward boost.
const MAX_VELOCITY = 3500;
const FRICTION = 5.2, STOP_SPEED = 80;   // sv_friction, sv_stopspeed
const PUSH_HULLS = [{ mins: { x: -16, y: -16, z: 2 }, maxs: { x: 16, y: 16, z: 72 } },   // standing, then ducked
                    { mins: { x: -16, y: -16, z: 2 }, maxs: { x: 16, y: 16, z: 54 } }];
/** @type {Map<number, Set<string>>} player slot -> push zones the player is in */
const pushBySlot = new Map();
/** @type {Map<number, {x: number, y: number}>} player slot -> horizontal push applied last tick */
const pushBase = new Map();
/** @type {Map<number, number>} player slot -> horizontal speed last tick while an up push holds them on the ground */
const pushGround = new Map();
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
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { pushBySlot.delete(slot); pushBase.delete(slot); pushGround.delete(slot); continue; }
        const pos = pawn.GetAbsOrigin();
        for (const id of [...zones]) if (!inside(pos, PUSH[id])) zones.delete(id);   // safety net if EndTouch was missed (e.g. trigger disabled)
        const v = pawn.GetAbsVelocity();
        if (zones.size === 0) {   // out of every push: the push becomes the player's own momentum
            const b = pushBase.get(slot), f = 1 + dt * 0.5;
            if (b && (b.x || b.y)) pawn.Move({ velocity: { x: clampV(v.x + b.x * f), y: clampV(v.y + b.y * f), z: v.z } });
            pushBySlot.delete(slot); pushBase.delete(slot); pushGround.delete(slot); continue;
        }
        let bx = 0, by = 0, bz = 0;
        for (const id of zones) { const zone = PUSH[id]; bx += zone.speed * zone.dir[0]; by += zone.speed * zone.dir[1]; bz += zone.speed * zone.dir[2]; }
        bx = clampV(bx); by = clampV(by); bz = clampV(bz);
        /** @type {{position?: {x: number, y: number, z: number}, velocity?: {x: number, y: number, z: number}}} */
        const mv = {};
        const onGround = pawn.GetGroundEntity() !== undefined;
        if (bz !== 0 && !onGround) mv.velocity = { x: v.x, y: v.y, z: clampV(v.z + bz * dt) };
        if (bz > 0 && onGround) {   // lifted off the ground in CS:GO: undo this tick's ground friction
            const s = Math.hypot(v.x, v.y), last = pushGround.get(slot) ?? s;
            const loss = Math.max(last, STOP_SPEED) * FRICTION * dt, s0 = Math.min(last, s + loss);   // never faster than last tick
            if (s > 0.1 && s0 > s) mv.velocity = { x: v.x * s0 / s, y: v.y * s0 / s, z: v.z };
            pushGround.set(slot, Math.max(s, s0));
        } else pushGround.delete(slot);
        if (bx || by) { const p = pushMove(pawn, pos, { x: bx * dt, y: by * dt, z: 0 }); if (p) mv.position = p; }
        pushBase.set(slot, { x: bx, y: by });
        if (mv.position || mv.velocity) pawn.Move(mv);
    }
    return pushBySlot.size > 0;
});
