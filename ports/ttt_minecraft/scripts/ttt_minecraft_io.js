import { Instance, CSPlayerPawn, CSPlayerController, CSMoveType } from "cs_script/point_script";

// ttt_minecraft: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `ttt_minecraft_io_script` -> RunScriptInput <input name>, with the activator passed through.
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
            1.0,
            0.0,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            -3584.0,
            -256.0,
            -256.0
        ],
        "maxs": [
            -2816.0,
            2016.0,
            -160.0
        ]
    },
    "2": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            -3584.0,
            -1280.0,
            -256.0
        ],
        "maxs": [
            -2688.0,
            -257.94122314453125,
            -160.0
        ]
    },
    "3": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            -2688.0,
            -768.0,
            -256.0
        ],
        "maxs": [
            -2176.0,
            -256.0,
            -160.0
        ]
    },
    "4": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            -2688.0,
            -768.0,
            -256.0
        ],
        "maxs": [
            -2176.0,
            -256.0,
            -160.0
        ]
    },
    "5": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            -2688.0,
            -1280.0,
            -256.0
        ],
        "maxs": [
            -2176.0,
            -768.0,
            -160.0
        ]
    },
    "6": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            -3584.0,
            -1792.0,
            -256.0
        ],
        "maxs": [
            -2176.0,
            -1280.0,
            -160.0
        ]
    },
    "7": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            -3584.0,
            -2272.0,
            -256.0
        ],
        "maxs": [
            -1536.0,
            -1792.0,
            -160.0
        ]
    },
    "8": {
        "dir": [
            0.7071,
            0.7071,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            -2176.0,
            -1792.0,
            -256.0
        ],
        "maxs": [
            -1536.0,
            -1152.0,
            -160.0
        ]
    },
    "9": {
        "dir": [
            -0.7071,
            0.7071,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            256.0,
            -1792.0,
            -256.0
        ],
        "maxs": [
            1280.0,
            -768.0,
            -160.0
        ]
    },
    "10": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            1280.0,
            -1792.0,
            -256.0
        ],
        "maxs": [
            2048.0,
            1536.0,
            -160.0
        ]
    },
    "11": {
        "dir": [
            -0.7071,
            -0.7071,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            768.0,
            1024.0,
            -256.0
        ],
        "maxs": [
            1280.0,
            1536.0,
            -160.0
        ]
    },
    "12": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            -2816.0,
            1536.0,
            -256.0
        ],
        "maxs": [
            2048.0,
            2016.0,
            -160.0
        ]
    },
    "13": {
        "dir": [
            0.7071,
            -0.7071,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            -2816.0,
            1023.98828125,
            -256.0
        ],
        "maxs": [
            -2320.0,
            1536.0,
            -160.0
        ]
    },
    "14": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            256.0,
            -2272.0,
            -256.0
        ],
        "maxs": [
            2048.0,
            -1792.0,
            -160.0
        ]
    },
    "15": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            -768.0,
            -2272.0,
            -256.0
        ],
        "maxs": [
            256.0,
            -2048.0,
            -160.0
        ]
    },
    "16": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            -1536.0,
            -2272.0,
            -256.0
        ],
        "maxs": [
            -768.0,
            -1920.0,
            -160.0
        ]
    },
    "17": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 300.0,
        "mins": [
            -564.0,
            208.0,
            -1184.0
        ],
        "maxs": [
            -556.0,
            288.0,
            -1120.0
        ]
    },
    "18": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 300.0,
        "mins": [
            -656.0,
            208.0,
            -1184.0
        ],
        "maxs": [
            -652.0,
            288.0,
            -1120.0
        ]
    },
    "19": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 128.0,
        "mins": [
            480.0,
            -480.0,
            576.0
        ],
        "maxs": [
            488.0,
            -416.0,
            664.0
        ]
    },
    "20": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 128.0,
        "mins": [
            512.0,
            -480.0,
            576.0
        ],
        "maxs": [
            520.0,
            -416.0,
            664.0
        ]
    },
    "21": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 128.0,
        "mins": [
            488.0,
            -424.0,
            576.0
        ],
        "maxs": [
            512.0,
            -416.0,
            664.0
        ]
    },
    "22": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 128.0,
        "mins": [
            488.0,
            -480.0,
            576.0
        ],
        "maxs": [
            512.0,
            -472.0,
            664.0
        ]
    },
    "23": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 300.0,
        "mins": [
            -448.0,
            64.0,
            -960.0
        ],
        "maxs": [
            -320.0,
            160.0,
            -864.0
        ]
    },
    "24": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 600.0,
        "mins": [
            -480.0,
            512.0,
            -1152.0
        ],
        "maxs": [
            -288.0,
            568.0,
            -928.0
        ]
    },
    "25": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 600.0,
        "mins": [
            -480.0,
            328.0,
            -992.0
        ],
        "maxs": [
            -288.0,
            384.0,
            -896.0
        ]
    },
    "26": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 600.0,
        "mins": [
            736.0,
            -576.0,
            368.0
        ],
        "maxs": [
            800.0,
            -448.0,
            576.0
        ]
    },
    "27": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 400.0,
        "mins": [
            720.0,
            -576.0,
            368.0
        ],
        "maxs": [
            752.0,
            -448.0,
            576.0
        ]
    },
    "28": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 300.0,
        "mins": [
            -448.0,
            128.0,
            -1056.0
        ],
        "maxs": [
            -320.0,
            352.0,
            -960.0
        ]
    },
    "29": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 300.0,
        "mins": [
            -16.0,
            624.0,
            480.0
        ],
        "maxs": [
            -12.0,
            672.0,
            544.0
        ]
    },
    "30": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 300.0,
        "mins": [
            76.0,
            624.0,
            480.0
        ],
        "maxs": [
            84.0,
            672.0,
            544.0
        ]
    },
    "31": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 400.0,
        "mins": [
            736.0,
            -608.0,
            368.0
        ],
        "maxs": [
            768.0,
            -560.0,
            576.0
        ]
    },
    "32": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 400.0,
        "mins": [
            736.0,
            -464.0,
            368.0
        ],
        "maxs": [
            768.0,
            -416.0,
            576.0
        ]
    },
    "33": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 640.0,
        "mins": [
            -1920.0,
            672.0,
            -256.0
        ],
        "maxs": [
            -1856.0,
            768.0,
            -128.0
        ]
    },
    "34": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 640.0,
        "mins": [
            -2048.0,
            672.0,
            -256.0
        ],
        "maxs": [
            -1984.0,
            768.0,
            -128.0
        ]
    },
    "35": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 320.0,
        "mins": [
            -2048.0,
            640.0,
            -256.0
        ],
        "maxs": [
            -1856.0,
            832.0,
            -128.0
        ]
    },
    "36": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 650.0,
        "mins": [
            -2080.0,
            384.0,
            -160.0
        ],
        "maxs": [
            -1856.0,
            544.0,
            -64.0
        ]
    },
    "37": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 650.0,
        "mins": [
            -1992.0,
            532.0,
            -160.0
        ],
        "maxs": [
            -1952.0,
            572.0,
            -80.0
        ]
    },
    "38": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 640.0,
        "mins": [
            -1984.0,
            672.0,
            -256.0
        ],
        "maxs": [
            -1920.0,
            704.0,
            -128.0
        ]
    },
    "39": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            -1984.0,
            832.0,
            -256.0
        ],
        "maxs": [
            -1920.0,
            864.0,
            -128.0
        ]
    },
    "40": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 16.0,
        "mins": [
            -1184.0,
            768.0,
            0.0
        ],
        "maxs": [
            -1088.0,
            992.0,
            56.0
        ]
    },
    "41": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 16.0,
        "mins": [
            -1152.0,
            896.0,
            -32.0
        ],
        "maxs": [
            -288.0,
            1056.0,
            24.0
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
for (const g of [0.0, 1.0]) {
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
