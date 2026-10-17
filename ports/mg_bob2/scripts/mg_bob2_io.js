import { Instance, CSPlayerPawn, CSPlayerController } from "cs_script/point_script";

// mg_bob2: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_bob2_io_script` -> RunScriptInput <input name>, with the activator passed through.
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
        "speed": 1000.0,
        "mins": [
            -204.5,
            3720.5,
            1587.0
        ],
        "maxs": [
            51.5,
            5840.5,
            1589.0
        ]
    },
    "2": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 1000.0,
        "mins": [
            -205.0,
            3924.501953125,
            1811.0
        ],
        "maxs": [
            51.5,
            6023.0,
            1813.0
        ]
    },
    "3": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 5000.0,
        "mins": [
            -204.5,
            6104.5,
            1586.0
        ],
        "maxs": [
            51.5,
            6192.5,
            1668.0
        ]
    },
    "4": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 1000.0,
        "mins": [
            -268.5,
            3601.5,
            1811.0
        ],
        "maxs": [
            51.5,
            3924.5,
            1813.0
        ]
    },
    "5": {
        "dir": [
            0.9744,
            0.0,
            0.225
        ],
        "speed": 1000.0,
        "mins": [
            582.693115234375,
            6019.0,
            2663.0
        ],
        "maxs": [
            601.505126953125,
            6147.0,
            2668.4306640625
        ]
    },
    "6": {
        "dir": [
            0.9744,
            0.0,
            0.225
        ],
        "speed": 1000.0,
        "mins": [
            1856.908447265625,
            6687.0,
            2663.0
        ],
        "maxs": [
            1901.50048828125,
            6815.0,
            2679.220458984375
        ]
    },
    "7": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 350.0,
        "mins": [
            7525.0,
            -1742.0,
            1660.0
        ],
        "maxs": [
            7589.0,
            -398.0,
            1661.0
        ]
    },
    "8": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 350.0,
        "mins": [
            5029.0,
            -398.0,
            1660.0
        ],
        "maxs": [
            7589.0,
            -334.0,
            1661.0
        ]
    },
    "9": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 350.0,
        "mins": [
            4965.0,
            -1934.0,
            1660.0
        ],
        "maxs": [
            5029.0,
            -334.0,
            1661.0
        ]
    },
    "10": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 350.0,
        "mins": [
            4965.0,
            -1998.0,
            1660.0
        ],
        "maxs": [
            7077.0,
            -1934.0,
            1661.0
        ]
    },
    "11": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 1750.0,
        "mins": [
            -1967.5,
            7570.0,
            -103.0
        ],
        "maxs": [
            -1199.5,
            8373.0,
            665.0
        ]
    },
    "12": {
        "dir": [
            -0.6428,
            0.766,
            0.0
        ],
        "speed": 650.0,
        "mins": [
            9111.0,
            8665.0,
            2890.7900390625
        ],
        "maxs": [
            9367.0,
            8916.0,
            3244.51953125
        ]
    },
    "13": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 370.0,
        "mins": [
            6658.0,
            7751.98046875,
            2890.5
        ],
        "maxs": [
            6884.0,
            7881.98046875,
            3224.5
        ]
    },
    "14": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 900.0,
        "mins": [
            7324.0703125,
            6756.0,
            2890.6015625
        ],
        "maxs": [
            7587.0,
            6884.0,
            3262.500732421875
        ]
    },
    "15": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 1100.0,
        "mins": [
            -2774.0,
            2730.0,
            511.0
        ],
        "maxs": [
            -2710.0,
            2794.01171875,
            523.0
        ]
    },
    "16": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 400.0,
        "mins": [
            -1059.0,
            2264.0,
            495.0
        ],
        "maxs": [
            -995.0,
            2328.0,
            503.0
        ]
    },
    "17": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 400.0,
        "mins": [
            -1059.0,
            3196.0,
            495.0
        ],
        "maxs": [
            -995.0,
            3260.0,
            502.97747802734375
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
