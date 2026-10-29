import { Instance, CSPlayerPawn, CSPlayerController, CSGearSlot } from "cs_script/point_script";

// mg_jahoukarail_2015: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_jahoukarail_2015_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   PushIn_<n> / PushOut_<n>   replaces the trigger_push brushes (CS:GO "set speed" behaviour)
//   Score_<pts> replaces game_score (ApplyScore)
//   (automatic) replaces game_player_equips without "Use Only" (CS:GO ran them on every spawn, CS2 does not)

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
        "speed": 1000.0,
        "mins": [
            287.03076171875,
            -2361.0,
            -241.7890625
        ],
        "maxs": [
            505.9697265625,
            -2312.0,
            -133.2109375
        ]
    },
    "2": {
        "dir": [
            0.9998,
            -0.0175,
            0.0
        ],
        "speed": 350.0,
        "mins": [
            2781.0,
            -854.0,
            8.0
        ],
        "maxs": [
            2790.0,
            -797.0,
            112.0
        ]
    },
    "3": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 350.0,
        "mins": [
            2771.0,
            -854.0,
            8.0
        ],
        "maxs": [
            2788.0,
            -797.0,
            112.0
        ]
    },
    "4": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 200.0,
        "mins": [
            3248.0,
            -256.0,
            6.0
        ],
        "maxs": [
            3272.0,
            -87.0,
            48.0
        ]
    },
    "5": {
        "dir": [
            -0.9998,
            -0.0175,
            0.0
        ],
        "speed": 200.0,
        "mins": [
            3057.0,
            -280.0,
            6.0
        ],
        "maxs": [
            3272.0,
            -256.0,
            48.0
        ]
    },
    "6": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 200.0,
        "mins": [
            3032.0,
            -400.0,
            -0.24855804443359375
        ],
        "maxs": [
            3057.0,
            -256.0,
            96.0
        ]
    },
    "7": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 200.0,
        "mins": [
            3033.0,
            -565.0,
            59.0
        ],
        "maxs": [
            3057.0,
            -400.0,
            96.0
        ]
    },
    "8": {
        "dir": [
            0.9998,
            0.0175,
            0.0
        ],
        "speed": 200.0,
        "mins": [
            3033.0,
            -589.0,
            59.0
        ],
        "maxs": [
            3192.0,
            -565.0,
            96.0
        ]
    },
    "9": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 200.0,
        "mins": [
            3297.0,
            -256.0,
            6.0
        ],
        "maxs": [
            3321.0,
            -87.0,
            48.0
        ]
    },
    "10": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 200.0,
        "mins": [
            3297.0,
            -280.0,
            6.0
        ],
        "maxs": [
            3511.0,
            -256.0,
            48.0
        ]
    },
    "11": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 200.0,
        "mins": [
            3511.0,
            -400.0,
            -0.26171875
        ],
        "maxs": [
            3536.0,
            -256.0,
            96.0
        ]
    },
    "12": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 200.0,
        "mins": [
            3512.0,
            -565.0,
            59.0
        ],
        "maxs": [
            3536.0,
            -400.0,
            96.0
        ]
    },
    "13": {
        "dir": [
            -0.9998,
            0.0175,
            0.0
        ],
        "speed": 200.0,
        "mins": [
            3383.55029296875,
            -589.0,
            59.0
        ],
        "maxs": [
            3536.0,
            -565.0,
            96.0
        ]
    },
    "14": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 1400.0,
        "mins": [
            2310.0,
            -190.0,
            -435.0
        ],
        "maxs": [
            2326.0,
            -92.0,
            -402.0
        ]
    },
    "15": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 750.0,
        "mins": [
            2753.0,
            -480.0,
            304.0
        ],
        "maxs": [
            2855.0,
            -108.0,
            400.0
        ]
    },
    "16": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 900.0,
        "mins": [
            2336.0,
            -94.0,
            -376.0
        ],
        "maxs": [
            2464.0,
            63.0,
            292.0
        ]
    },
    "17": {
        "dir": [
            0.9998,
            0.0175,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -16.0,
            424.0,
            0.0
        ],
        "maxs": [
            48.0,
            472.0,
            88.0
        ]
    },
    "18": {
        "dir": [
            0.9998,
            0.0175,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -16.0,
            312.0,
            0.0
        ],
        "maxs": [
            48.0,
            360.0,
            88.0
        ]
    },
    "19": {
        "dir": [
            0.9998,
            0.0175,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -16.0,
            88.0,
            0.0
        ],
        "maxs": [
            48.0,
            136.0,
            88.0
        ]
    },
    "20": {
        "dir": [
            0.9998,
            0.0175,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -16.0,
            200.0,
            0.0
        ],
        "maxs": [
            48.0,
            248.0,
            88.0
        ]
    },
    "21": {
        "dir": [
            0.9998,
            0.0175,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -16.0,
            -136.0,
            0.0
        ],
        "maxs": [
            48.0,
            -88.0,
            88.0
        ]
    },
    "22": {
        "dir": [
            0.9998,
            0.0175,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -16.0,
            -24.0,
            0.0
        ],
        "maxs": [
            48.0,
            24.0,
            88.0
        ]
    },
    "23": {
        "dir": [
            0.9998,
            0.0175,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -16.0,
            -360.0,
            0.0
        ],
        "maxs": [
            48.0,
            -312.0,
            88.0
        ]
    },
    "24": {
        "dir": [
            0.9998,
            0.0175,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -16.0,
            -248.0,
            0.0
        ],
        "maxs": [
            48.0,
            -200.0,
            88.0
        ]
    },
    "25": {
        "dir": [
            0.9998,
            0.0175,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -16.0,
            -472.0,
            0.0
        ],
        "maxs": [
            48.0,
            -424.0,
            88.0
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

// ---------------------------------------------------------------- game_score replacement (entity removed in CS2)
// Outputs that fired <game_score>.ApplyScore now fire Score_<points>; the activator's scoreboard score goes up.
for (const pts of [200]) {
    Instance.OnScriptInput("Score_" + pts, ({ activator }) => {
        const pawn = activator instanceof CSPlayerPawn ? activator : undefined;
        const ctrl = pawn ? pawn.GetPlayerController() : (activator instanceof CSPlayerController ? activator : undefined);
        if (ctrl && ctrl.IsValid()) ctrl.AddScore(pts);
    });
}

// ---------------------------------------------------------------- spawn equips (game_player_equip without "Use Only")
// CS:GO ran these on every spawn ("Strip First" = start with nothing but their items). CS2 doesn't, so each (re)spawning
// player is handled one tick after OnPlayerReset (after CS2 has handed out its default loadout).
/** @type {{ strip: boolean, items: string[] }[]} */
const SPAWN_EQUIPS = [{"strip": false, "items": ["weapon_knife"]}];
/** @type {Set<CSPlayerPawn>} */
const spawnQueue = new Set();
Instance.OnPlayerReset(({ player }) => {
    if (player && player.IsValid()) { spawnQueue.add(player); wakeThink(); }
});
THINKERS.push(() => {
    for (const pawn of spawnQueue) {
        spawnQueue.delete(pawn);
        if (!pawn.IsValid() || !pawn.IsAlive()) continue;
        for (const eq of SPAWN_EQUIPS) {
            if (eq.strip) pawn.DestroyWeapons();
            for (const item of eq.items) {
                if (!item.startsWith("item_") && (item === "weapon_knife" ? pawn.FindWeaponBySlot(CSGearSlot.KNIFE) : pawn.FindWeapon(item))) continue;
                pawn.GiveNamedItem(item, false);
            }
        }
    }
    return false;
});
