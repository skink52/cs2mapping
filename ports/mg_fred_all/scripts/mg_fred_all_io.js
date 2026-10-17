import { Instance, CSPlayerPawn, CSPlayerController } from "cs_script/point_script";

// mg_fred_all: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_fred_all_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   PushIn_<n> / PushOut_<n>   replaces the trigger_push brushes (CS:GO "set speed" behaviour)
//   EnableDamage / DisableDamage   enemy damage gate (fintrigger at the Fin room enables it; every round starts with it off)

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
        "speed": 800.0,
        "mins": [
            -912.0,
            3520.0,
            -512.0
        ],
        "maxs": [
            -720.0,
            3904.0,
            -128.0
        ]
    },
    "2": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 10000.0,
        "mins": [
            1648.0,
            -1088.0,
            638.84375
        ],
        "maxs": [
            1712.0,
            -1024.0,
            1024.0
        ]
    },
    "3": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 10000.0,
        "mins": [
            1584.0,
            -1280.0,
            256.0
        ],
        "maxs": [
            1648.0,
            -1216.0,
            640.0
        ]
    },
    "4": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 10000.0,
        "mins": [
            1648.0,
            -1280.0,
            128.0
        ],
        "maxs": [
            1712.0,
            -1216.0,
            512.0
        ]
    },
    "5": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 800.0,
        "mins": [
            197.12890625,
            1280.0,
            -512.0
        ],
        "maxs": [
            389.1300048828125,
            1664.0,
            -128.0
        ]
    },
    "6": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 800.0,
        "mins": [
            2992.0,
            1280.0,
            -384.0
        ],
        "maxs": [
            3184.0,
            1664.0,
            0.0
        ]
    },
    "7": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 800.0,
        "mins": [
            4784.0,
            4992.0,
            -384.0
        ],
        "maxs": [
            4976.0,
            5376.0,
            0.0
        ]
    },
    "8": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 800.0,
        "mins": [
            1989.130126953125,
            4992.0,
            -512.0
        ],
        "maxs": [
            2181.1298828125,
            5376.0,
            -128.0
        ]
    },
    "9": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 800.0,
        "mins": [
            4163.5703125,
            4160.0,
            -384.0
        ],
        "maxs": [
            4355.5703125,
            4544.0,
            0.0
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
            3120.0,
            2432.0,
            -448.0
        ],
        "maxs": [
            4016.0,
            3648.0,
            1472.0
        ]
    },
    "11": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 800.0,
        "mins": [
            5781.64990234375,
            288.0,
            -384.0
        ],
        "maxs": [
            5973.64990234375,
            672.0,
            0.0
        ]
    },
    "12": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 800.0,
        "mins": [
            2986.780029296875,
            288.0,
            -512.0
        ],
        "maxs": [
            3178.780029296875,
            672.0,
            -128.0
        ]
    },
    "13": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 800.0,
        "mins": [
            5161.21875,
            -544.0,
            -384.0
        ],
        "maxs": [
            5353.2197265625,
            -160.0,
            0.0
        ]
    },
    "14": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 800.0,
        "mins": [
            4850.83984375,
            -1456.0,
            -390.228759765625
        ],
        "maxs": [
            5069.1611328125,
            -1072.0,
            6.228759765625
        ]
    },
    "15": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 9999.0,
        "mins": [
            -688.0,
            -736.0,
            192.0
        ],
        "maxs": [
            -304.0,
            -320.0,
            320.0
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

// ---------------------------------------------------------------- enemy damage gate
// Players can't hurt players on the other team until someone reaches the finish (fintrigger -> RunScriptInput EnableDamage).
// Every round starts with it off again. World damage (trigger_hurt, falling) and self damage are not affected.
let enemyDamage = false;
Instance.OnScriptInput("EnableDamage", () => { enemyDamage = true; });
Instance.OnScriptInput("DisableDamage", () => { enemyDamage = false; });
Instance.OnRoundStart(() => { enemyDamage = false; });
Instance.OnBeforePlayerDamage((event) => {
    if (enemyDamage) return;
    const a = event.attacker, v = event.player;
    if (!a || !v) return;
    if (!(a instanceof CSPlayerPawn || a instanceof CSPlayerController)) return;
    const at = a.GetTeamNumber(), vt = v.GetTeamNumber();
    if (at >= 2 && vt >= 2 && at !== vt) return { abort: true };
});
