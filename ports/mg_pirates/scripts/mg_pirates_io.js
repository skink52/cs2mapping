import { Instance, CSPlayerPawn, CSPlayerController, CSGearSlot, CSInputs, CSMoveType } from "cs_script/point_script";

// mg_pirates: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_pirates_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   PushIn_<n> / PushOut_<n>   replaces the trigger_push brushes (CS:GO "set speed" behaviour)
//   (automatic) replaces game_player_equips without "Use Only" (CS:GO ran them on every spawn, CS2 does not)
//   GameUIOn_<name> / GameUIOff_<name>  replaces game_ui (Activate / Deactivate): keys polled every tick, outputs fired from here

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
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            -1100.0,
            -592.0,
            334.0
        ],
        "maxs": [
            -1084.0,
            -528.0,
            358.0
        ]
    },
    "2": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            -1100.0,
            48.0,
            334.0
        ],
        "maxs": [
            -1084.0,
            112.0,
            358.0
        ]
    },
    "3": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            -1100.0,
            368.0,
            334.0
        ],
        "maxs": [
            -1084.0,
            432.0,
            358.0
        ]
    },
    "4": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            -948.0,
            -1096.0,
            514.0
        ],
        "maxs": [
            -804.0,
            -1048.0,
            570.0
        ]
    },
    "5": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            -1100.0,
            -1104.0,
            494.0
        ],
        "maxs": [
            -1084.0,
            -1040.0,
            518.0
        ]
    },
    "6": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            -1100.0,
            -272.01171875,
            334.0
        ],
        "maxs": [
            -1084.0,
            -208.0,
            358.0
        ]
    },
    "7": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            -1128.0,
            -736.0,
            60.0
        ],
        "maxs": [
            -1112.0,
            -704.0,
            84.0
        ]
    },
    "8": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            -948.0,
            -1352.0,
            514.0
        ],
        "maxs": [
            -804.0,
            -1304.0,
            570.0
        ]
    },
    "9": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            -1128.0,
            -96.0,
            60.0
        ],
        "maxs": [
            -1112.0,
            -64.0,
            84.0
        ]
    },
    "10": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            -1100.0,
            -1360.0,
            494.0
        ],
        "maxs": [
            -1084.0,
            -1296.0,
            518.0
        ]
    },
    "11": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            -1128.0,
            544.0,
            60.0
        ],
        "maxs": [
            -1112.0,
            576.0,
            84.0
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
            1744.0,
            -240.0,
            0.0
        ],
        "maxs": [
            1968.0,
            -48.0,
            48.0
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
            1748.0,
            272.0,
            0.0
        ],
        "maxs": [
            1968.0,
            464.0,
            48.0
        ]
    },
    "14": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            1065.0,
            528.0,
            334.0
        ],
        "maxs": [
            1081.0,
            592.0,
            358.0
        ]
    },
    "15": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            1065.0,
            -112.0,
            334.0
        ],
        "maxs": [
            1081.0,
            -48.0,
            358.0
        ]
    },
    "16": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            1065.0,
            -432.0,
            334.0
        ],
        "maxs": [
            1081.0,
            -368.0,
            358.0
        ]
    },
    "17": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            785.0,
            1048.0,
            514.0
        ],
        "maxs": [
            929.0,
            1096.0,
            570.0
        ]
    },
    "18": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            1065.0,
            1040.0,
            494.0
        ],
        "maxs": [
            1081.0,
            1104.0,
            518.0
        ]
    },
    "19": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            813.0,
            -584.0,
            82.0
        ],
        "maxs": [
            957.0,
            -536.0,
            138.0
        ]
    },
    "20": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            813.0,
            56.0,
            82.0
        ],
        "maxs": [
            957.0,
            104.0,
            138.0
        ]
    },
    "21": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            813.0,
            696.0,
            82.0
        ],
        "maxs": [
            957.0,
            744.0,
            138.0
        ]
    },
    "22": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            785.0,
            -424.0,
            354.0
        ],
        "maxs": [
            929.0,
            -376.0,
            410.0
        ]
    },
    "23": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            785.0,
            -104.0,
            354.0
        ],
        "maxs": [
            929.0,
            -56.0,
            410.0
        ]
    },
    "24": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            785.0,
            216.0,
            354.0
        ],
        "maxs": [
            929.0,
            264.0,
            410.0
        ]
    },
    "25": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            785.0,
            536.0,
            354.0
        ],
        "maxs": [
            929.0,
            584.0,
            410.0
        ]
    },
    "26": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            1093.0,
            -576.0,
            60.0
        ],
        "maxs": [
            1109.0,
            -544.0,
            84.0
        ]
    },
    "27": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            1065.0,
            1296.0,
            494.0
        ],
        "maxs": [
            1081.0,
            1360.0,
            518.0
        ]
    },
    "28": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            1093.0,
            64.0,
            60.0
        ],
        "maxs": [
            1109.0,
            96.0,
            84.0
        ]
    },
    "29": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            785.0,
            1304.0,
            514.0
        ],
        "maxs": [
            929.0,
            1352.0,
            570.0
        ]
    },
    "30": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            1093.0,
            704.0,
            60.0
        ],
        "maxs": [
            1109.0,
            736.0,
            84.0
        ]
    },
    "31": {
        "dir": [
            0.0,
            0.0,
            -1.0
        ],
        "speed": 1.0,
        "mins": [
            1065.0,
            208.0,
            334.0
        ],
        "maxs": [
            1081.0,
            272.0108642578125,
            358.0
        ]
    },
    "32": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            -1964.0,
            152.0,
            0.0
        ],
        "maxs": [
            -1744.0,
            344.0,
            48.0
        ]
    },
    "33": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 800.0,
        "mins": [
            -1968.0,
            -360.0,
            0.0
        ],
        "maxs": [
            -1744.0,
            -168.0,
            48.0
        ]
    },
    "34": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            -976.0,
            536.0,
            82.0
        ],
        "maxs": [
            -832.0,
            584.0,
            138.0
        ]
    },
    "35": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            -976.0,
            -104.0,
            82.0
        ],
        "maxs": [
            -832.0,
            -56.0,
            138.0
        ]
    },
    "36": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            -976.0,
            -744.0,
            82.0
        ],
        "maxs": [
            -832.0,
            -696.0,
            138.0
        ]
    },
    "37": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            -948.0,
            376.0,
            354.0
        ],
        "maxs": [
            -804.0,
            424.0,
            410.0
        ]
    },
    "38": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            -948.0,
            56.0,
            354.0
        ],
        "maxs": [
            -804.0,
            104.0,
            410.0
        ]
    },
    "39": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            -948.0,
            -264.0,
            354.0
        ],
        "maxs": [
            -804.0,
            -216.0,
            410.0
        ]
    },
    "40": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 35000.0,
        "mins": [
            -948.0,
            -584.0,
            354.0
        ],
        "maxs": [
            -804.0,
            -536.0,
            410.0
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

// ---------------------------------------------------------------- spawn equips (game_player_equip without "Use Only")
// CS:GO ran these on every spawn ("Strip First" = start with nothing but their items). CS2 doesn't, so each (re)spawning
// player is handled one tick after OnPlayerReset (after CS2 has handed out its default loadout).
/** @type {{ strip: boolean, items: string[] }[]} */
const SPAWN_EQUIPS = [{"strip": true, "items": ["weapon_knife"]}];
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

// ---------------------------------------------------------------- game_ui replacement (outputs never fire in CS2)
// GameUIOn_<name> / GameUIOff_<name> take the activator as the driver. While held, the driver's keys are polled every tick and
// the game_ui's outputs fire on each change (axis outputs pass -1/0/1 unless the output had a parameter). Freeze Player = move
// type NONE while held; +use / jump deactivate when the game_ui had those flags. Several game_uis can share one driver.
/** @type {Record<string, { flags: number, outs: [string, string, string, string, number][] }>} */
const GAMEUI = {
 "4c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "4c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "4c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "4c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "4c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "54c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "54c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "54c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "54c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "54c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "t_2boat_controller": {
  "flags": 480,
  "outs": [
   [
    "PressedForward",
    "t_2smallboat_accelerator",
    "Activate",
    "",
    0.0
   ],
   [
    "UnpressedForward",
    "t_2smallboat_accelerator",
    "Deactivate",
    "",
    0.0
   ],
   [
    "UnpressedBack",
    "t_2smallboat_reverse",
    "Deactivate",
    "",
    0.0
   ],
   [
    "PressedBack",
    "t_2smallboat_reverse",
    "Activate",
    "",
    0.0
   ],
   [
    "PressedMoveLeft",
    "t_2smallboat_left",
    "Activate",
    "",
    0.0
   ],
   [
    "UnpressedMoveLeft",
    "t_2smallboat_left",
    "Deactivate",
    "",
    0.0
   ],
   [
    "UnpressedMoveRight",
    "t_2smallboat_right",
    "Deactivate",
    "",
    0.0
   ],
   [
    "PressedMoveRight",
    "t_2smallboat_right",
    "Activate",
    "",
    0.0
   ]
  ]
 },
 "t_boat_controller": {
  "flags": 480,
  "outs": [
   [
    "PressedForward",
    "t_smallboat_accelerator",
    "Activate",
    "",
    0.0
   ],
   [
    "UnpressedForward",
    "t_smallboat_accelerator",
    "Deactivate",
    "",
    0.0
   ],
   [
    "UnpressedBack",
    "t_smallboat_reverse",
    "Deactivate",
    "",
    0.0
   ],
   [
    "PressedBack",
    "t_smallboat_reverse",
    "Activate",
    "",
    0.0
   ],
   [
    "PressedMoveLeft",
    "t_smallboat_left",
    "Activate",
    "",
    0.0
   ],
   [
    "UnpressedMoveLeft",
    "t_smallboat_left",
    "Deactivate",
    "",
    0.0
   ],
   [
    "UnpressedMoveRight",
    "t_smallboat_right",
    "Deactivate",
    "",
    0.0
   ],
   [
    "PressedMoveRight",
    "t_smallboat_right",
    "Activate",
    "",
    0.0
   ]
  ]
 },
 "t_4c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "t_4c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "t_4c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "t_4c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "t_4c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "t_bc1c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "t_bc1c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "t_bc1c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "t_bc1c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "t_bc1c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "t_2bc1c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "t_2bc1c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "t_2bc1c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "t_2bc1c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "t_2bc1c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "t_3bc1c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "t_3bc1c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "t_3bc1c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "t_3bc1c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "t_3bc1c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "t_c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "t_c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "t_c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "t_c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "t_c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "t_1c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "t_1c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "t_1c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "t_1c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "t_1c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "t_2c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "t_2c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "t_2c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "t_2c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "t_2c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "t_3c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "t_3c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "t_3c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "t_3c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "t_3c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "t_54c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "t_54c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "t_54c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "t_54c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "t_54c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "2boat_controller": {
  "flags": 480,
  "outs": [
   [
    "PressedForward",
    "2smallboat_accelerator",
    "Activate",
    "",
    0.0
   ],
   [
    "UnpressedForward",
    "2smallboat_accelerator",
    "Deactivate",
    "",
    0.0
   ],
   [
    "UnpressedBack",
    "2smallboat_reverse",
    "Deactivate",
    "",
    0.0
   ],
   [
    "PressedBack",
    "2smallboat_reverse",
    "Activate",
    "",
    0.0
   ],
   [
    "PressedMoveLeft",
    "2smallboat_left",
    "Activate",
    "",
    0.0
   ],
   [
    "UnpressedMoveLeft",
    "2smallboat_left",
    "Deactivate",
    "",
    0.0
   ],
   [
    "UnpressedMoveRight",
    "2smallboat_right",
    "Deactivate",
    "",
    0.0
   ],
   [
    "PressedMoveRight",
    "2smallboat_right",
    "Activate",
    "",
    0.0
   ]
  ]
 },
 "boat_controller": {
  "flags": 480,
  "outs": [
   [
    "PressedForward",
    "smallboat_accelerator",
    "Activate",
    "",
    0.0
   ],
   [
    "UnpressedForward",
    "smallboat_accelerator",
    "Deactivate",
    "",
    0.0
   ],
   [
    "UnpressedBack",
    "smallboat_reverse",
    "Deactivate",
    "",
    0.0
   ],
   [
    "PressedBack",
    "smallboat_reverse",
    "Activate",
    "",
    0.0
   ],
   [
    "PressedMoveLeft",
    "smallboat_left",
    "Activate",
    "",
    0.0
   ],
   [
    "UnpressedMoveLeft",
    "smallboat_left",
    "Deactivate",
    "",
    0.0
   ],
   [
    "UnpressedMoveRight",
    "smallboat_right",
    "Deactivate",
    "",
    0.0
   ],
   [
    "PressedMoveRight",
    "smallboat_right",
    "Activate",
    "",
    0.0
   ]
  ]
 },
 "bc1c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "bc1c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "bc1c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "bc1c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "bc1c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "2bc1c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "2bc1c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "2bc1c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "2bc1c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "2bc1c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "3bc1c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "3bc1c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "3bc1c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "3bc1c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "3bc1c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "1c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "1c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "1c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "1c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "1c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "2c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "2c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "2c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "2c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "2c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 },
 "3c_controller": {
  "flags": 480,
  "outs": [
   [
    "YAxis",
    "3c_tilter",
    "InValue",
    "",
    0.01
   ],
   [
    "XAxis",
    "3c_rotater",
    "InValue",
    "",
    0.01
   ],
   [
    "PressedAttack",
    "3c_fire",
    "Trigger",
    "",
    0.0
   ],
   [
    "PressedAttack",
    "3c_effects",
    "Trigger",
    "",
    0.0
   ]
  ]
 }
};
/** @type {Map<string, { pawn: CSPlayerPawn, since: number, keys: Record<string, boolean> }>} */
const gameuiHeld = new Map();
/** @type {[string, CSInputs][]} */
const GAMEUI_KEYS = [["Forward", CSInputs.FORWARD], ["Back", CSInputs.BACK], ["MoveLeft", CSInputs.LEFT], ["MoveRight", CSInputs.RIGHT],
    ["Attack", CSInputs.ATTACK], ["Attack2", CSInputs.ATTACK2]];
function gameuiPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
/** @param {string} ui @param {string} out @param {CSPlayerPawn} pawn @param {string} [value] */
function gameuiFire(ui, out, pawn, value) {
    for (const [o, target, input, param, delay] of GAMEUI[ui].outs) {
        if (o !== out) continue;
        const v = param !== "" ? param : (value ?? "");
        if (target.toLowerCase() === "!activator") Instance.EntFireAtTarget({ target: pawn, input, value: v, activator: pawn, delay });
        else Instance.EntFireAtName({ name: target, input, value: v, activator: pawn, delay });
    }
}
/** @param {string} ui */
function gameuiRelease(ui) {
    const h = gameuiHeld.get(ui);
    if (!h) return;
    gameuiHeld.delete(ui);
    const p = h.pawn;
    for (const [key] of GAMEUI_KEYS) if (h.keys[key]) gameuiFire(ui, "Unpressed" + key, p);
    if (h.keys.MoveLeft || h.keys.MoveRight) gameuiFire(ui, "XAxis", p, "0");
    if (h.keys.Forward || h.keys.Back) gameuiFire(ui, "YAxis", p, "0");
    if (h.keys.Attack) gameuiFire(ui, "AttackAxis", p, "0");
    if (h.keys.Attack2) gameuiFire(ui, "Attack2Axis", p, "0");
    gameuiFire(ui, "PlayerOff", p);
    const stillFrozen = [...gameuiHeld].some(([u, o]) => o.pawn === p && (GAMEUI[u].flags & 32));
    if (GAMEUI[ui].flags & 32 && !stillFrozen && p.IsValid() && p.GetMoveType() === CSMoveType.NONE) p.SetMoveType(CSMoveType.WALK);
}
for (const ui of Object.keys(GAMEUI)) {
    Instance.OnScriptInput("GameUIOn_" + ui, ({ activator }) => {
        const pawn = gameuiPawn(activator);
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) return;
        const cur = gameuiHeld.get(ui);
        if (cur && cur.pawn === pawn) return;
        if (cur) gameuiRelease(ui);
        gameuiHeld.set(ui, { pawn, since: Instance.GetGameTime(), keys: {} });
        if (GAMEUI[ui].flags & 32) pawn.SetMoveType(CSMoveType.NONE);
        gameuiFire(ui, "PlayerOn", pawn);
        wakeThink();
    });
    Instance.OnScriptInput("GameUIOff_" + ui, () => gameuiRelease(ui));
}
THINKERS.push(() => {
    const now = Instance.GetGameTime();
    for (const [ui, h] of [...gameuiHeld]) {
        const p = h.pawn, f = GAMEUI[ui].flags;
        if (!p.IsValid() || !p.IsAlive()) { gameuiRelease(ui); continue; }
        if (now - h.since > 0.5 && ((f & 128 && p.IsInputPressed(CSInputs.USE)) || (f & 256 && p.IsInputPressed(CSInputs.JUMP)))) { gameuiRelease(ui); continue; }
        const was = { ...h.keys };
        for (const [key, bit] of GAMEUI_KEYS) {
            const down = p.IsInputPressed(bit);
            if (down !== !!h.keys[key]) { h.keys[key] = down; gameuiFire(ui, (down ? "Pressed" : "Unpressed") + key, p); }
        }
        const ax = (k) => (k.MoveRight ? 1 : 0) - (k.MoveLeft ? 1 : 0), ay = (k) => (k.Forward ? 1 : 0) - (k.Back ? 1 : 0);
        if (ax(was) !== ax(h.keys)) gameuiFire(ui, "XAxis", p, String(ax(h.keys)));
        if (ay(was) !== ay(h.keys)) gameuiFire(ui, "YAxis", p, String(ay(h.keys)));
        if (!!was.Attack !== !!h.keys.Attack) gameuiFire(ui, "AttackAxis", p, h.keys.Attack ? "1" : "0");
        if (!!was.Attack2 !== !!h.keys.Attack2) gameuiFire(ui, "Attack2Axis", p, h.keys.Attack2 ? "1" : "0");
    }
    return gameuiHeld.size > 0;
});
