import { Instance, CSPlayerPawn, CSPlayerController } from "cs_script/point_script";

// mg_super_tower: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_super_tower_io_script` -> RunScriptInput <input name>, with the touching player as activator.
//
//   PushIn_<n> / PushOut_<n>   replaces the 16 trigger_push corridors (CS:GO "set speed" behaviour)

// ---------------------------------------------------------------- trigger_push replacement
// CS2's trigger_push keeps adding velocity every tick while you are inside it, so CS:GO pushes became rocket launchers.
// CS:GO's push simply moved you at the push speed in the push direction. Each former trigger_push is now a
// trigger_multiple that fires PushIn_<id> / PushOut_<id>; while a player is inside, their velocity along the push
// direction is held at the push speed (sideways / other movement is left alone), clamped to sv_maxvelocity (3500).
/** @type {Record<string, { dir: number[], speed: number, mins: number[], maxs: number[] }>} */
const PUSH = {
    "1": {
        "dir": [
            -1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            2576.0,
            -1304.0,
            -944.0
        ],
        "maxs": [
            2672.0,
            -1256.0,
            -832.0
        ]
    },
    "2": {
        "dir": [
            -1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            2576.0,
            -1048.0,
            -944.0
        ],
        "maxs": [
            2672.0,
            -1000.0,
            -832.0
        ]
    },
    "3": {
        "dir": [
            -1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            2576.0,
            -792.0,
            -944.0
        ],
        "maxs": [
            2672.0,
            -744.0,
            -832.0
        ]
    },
    "4": {
        "dir": [
            -1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            2576.0,
            -536.0,
            -944.0
        ],
        "maxs": [
            2672.0,
            -488.0,
            -832.0
        ]
    },
    "5": {
        "dir": [
            -1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            2576.0,
            -280.0,
            -944.0
        ],
        "maxs": [
            2672.0,
            -232.0,
            -832.0
        ]
    },
    "6": {
        "dir": [
            -1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            2576.0,
            -24.0,
            -944.0
        ],
        "maxs": [
            2672.0,
            24.0,
            -832.0
        ]
    },
    "7": {
        "dir": [
            -1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            2576.0,
            232.0,
            -944.0
        ],
        "maxs": [
            2672.0,
            280.0,
            -832.0
        ]
    },
    "8": {
        "dir": [
            -1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            2576.0,
            488.0,
            -944.0
        ],
        "maxs": [
            2672.0,
            536.0,
            -832.0
        ]
    },
    "9": {
        "dir": [
            1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            -3696.0,
            -1304.0,
            -944.0
        ],
        "maxs": [
            -3600.0,
            -1256.0,
            -832.0
        ]
    },
    "10": {
        "dir": [
            1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            -3696.0,
            -1048.0,
            -944.0
        ],
        "maxs": [
            -3600.0,
            -1000.0,
            -832.0
        ]
    },
    "11": {
        "dir": [
            1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            -3696.0,
            -792.0,
            -944.0
        ],
        "maxs": [
            -3600.0,
            -744.0,
            -832.0
        ]
    },
    "12": {
        "dir": [
            1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            -3696.0,
            -536.0,
            -944.0
        ],
        "maxs": [
            -3600.0,
            -488.0,
            -832.0
        ]
    },
    "13": {
        "dir": [
            1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            -3696.0,
            -280.0,
            -944.0
        ],
        "maxs": [
            -3600.0,
            -232.0,
            -832.0
        ]
    },
    "14": {
        "dir": [
            1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            -3696.0,
            -24.0,
            -944.0
        ],
        "maxs": [
            -3600.0,
            24.0,
            -832.0
        ]
    },
    "15": {
        "dir": [
            1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            -3696.0,
            232.0,
            -944.0
        ],
        "maxs": [
            -3600.0,
            280.0,
            -832.0
        ]
    },
    "16": {
        "dir": [
            1.0,
            0.0,
            -0.0
        ],
        "speed": 3650.0,
        "mins": [
            -3696.0,
            488.0,
            -944.0
        ],
        "maxs": [
            -3600.0,
            536.0,
            -832.0
        ]
    }
};
const MAX_VELOCITY = 3500;
/** @type {Map<number, Set<string>>} player slot -> push zones the player is in */
const pushBySlot = new Map();
let pushThinking = false;

/** @param {any} ent @returns {CSPlayerPawn | undefined} */
function toPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
function slotOf(pawn) { const c = pawn.GetPlayerController(); return c ? c.GetPlayerSlot() : -1; }
function startPushThink() {
    if (pushThinking || pushBySlot.size === 0) return;
    pushThinking = true;
    Instance.SetNextThink(Instance.GetGameTime());
}
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
Instance.SetThink(() => {
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
    if (pushBySlot.size > 0) Instance.SetNextThink(Instance.GetGameTime());
    else pushThinking = false;
});
