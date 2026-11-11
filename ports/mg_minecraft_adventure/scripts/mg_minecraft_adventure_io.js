import { Instance, Entities, Console, CSPlayerPawn, CSPlayerController } from "cs_script/point_script";

// mg_minecraft_adventure: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_minecraft_adventure_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   PushIn_<n> / PushOut_<n>   replaces the trigger_push brushes (CS:GO "set speed" behaviour)
//   Score_<pts> replaces game_score (ApplyScore)

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
        "speed": 1500.0,
        "mins": [
            12728.0,
            -6000.0,
            2376.0
        ],
        "maxs": [
            12744.0,
            -5744.0,
            2456.0
        ]
    },
    "2": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1500.0,
        "mins": [
            12592.0,
            -5744.0,
            2376.0
        ],
        "maxs": [
            12744.0,
            -5728.0,
            2456.0
        ]
    },
    "3": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1500.0,
        "mins": [
            12592.0,
            -5728.0,
            2376.0
        ],
        "maxs": [
            12608.0,
            -5592.0,
            2456.0
        ]
    },
    "4": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1500.0,
        "mins": [
            12608.0,
            -5608.0,
            2376.0
        ],
        "maxs": [
            12864.0,
            -5592.0,
            2456.0
        ]
    },
    "5": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1500.0,
        "mins": [
            12848.0,
            -5592.0,
            2376.0
        ],
        "maxs": [
            12864.0,
            -5208.0,
            2456.0
        ]
    },
    "6": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1500.0,
        "mins": [
            12752.0,
            -5432.0,
            2376.0
        ],
        "maxs": [
            12768.0,
            -5208.0,
            2456.0
        ]
    },
    "7": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1500.0,
        "mins": [
            12600.0,
            -5432.0,
            2376.0
        ],
        "maxs": [
            12752.0,
            -5416.0,
            2456.0
        ]
    },
    "8": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1500.0,
        "mins": [
            12752.0,
            -5208.0,
            2376.0
        ],
        "maxs": [
            12864.0,
            -5192.0,
            2456.0
        ]
    },
    "9": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1500.0,
        "mins": [
            12600.0,
            -5416.0,
            2376.0
        ],
        "maxs": [
            12616.0,
            -4992.0,
            2456.0
        ]
    },
    "10": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1500.0,
        "mins": [
            12616.0,
            -5008.0,
            2376.0
        ],
        "maxs": [
            12744.0,
            -4992.0,
            2456.0
        ]
    },
    "11": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1500.0,
        "mins": [
            12728.0,
            -4992.0,
            2376.0
        ],
        "maxs": [
            12744.0,
            -4864.0,
            2456.0
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
for (const pts of [2, 5, 10, 15, 100]) {
    Instance.OnScriptInput("Score_" + pts, ({ activator }) => {
        const pawn = activator instanceof CSPlayerPawn ? activator : undefined;
        const ctrl = pawn ? pawn.GetPlayerController() : (activator instanceof CSPlayerController ? activator : undefined);
        if (ctrl && ctrl.IsValid()) ctrl.AddScore(pts);
    });
}

// ---------------------------------------------------------------- port_anim (animprops.py)
// Flipbook textures on tiled faces (CS2's texture animation can't wrap inside a sheet cell): each is a prop_dynamic with one
// material group per frame; the think below steps Skin. Props on moving entities are glued on at round start (the entity may
// have moved to its first path_track at spawn, so the prop is placed at the owner's current origin first).
/** @type {{name: string, frames: number, fps: number, owner: string, ownerClass: string}[]} */
const PORT_ANIM = [
    {
        "name": "port_anim_fire_0",
        "frames": 84,
        "fps": 15.0,
        "owner": "fire_tank",
        "ownerClass": "func_tracktrain",
        "spawn": [
            5776.0,
            -11952.0,
            3972.0
        ]
    },
    {
        "name": "port_anim_fire_1",
        "frames": 84,
        "fps": 15.0,
        "owner": "",
        "ownerClass": ""
    },
    {
        "name": "port_anim_lava_0",
        "frames": 78,
        "fps": 15.0,
        "owner": "lava_tank_1",
        "ownerClass": "func_tracktrain",
        "spawn": [
            8976.0,
            -8304.0,
            6884.0
        ]
    },
    {
        "name": "port_anim_lava_1",
        "frames": 78,
        "fps": 15.0,
        "owner": "lava_tank_2",
        "ownerClass": "func_tracktrain",
        "spawn": [
            8976.0,
            -8304.0,
            6300.0
        ]
    },
    {
        "name": "port_anim_lava_2",
        "frames": 78,
        "fps": 15.0,
        "owner": "lava_tank_3",
        "ownerClass": "func_tracktrain",
        "spawn": [
            9368.0,
            -8304.0,
            6592.0
        ]
    },
    {
        "name": "port_anim_lava_3",
        "frames": 78,
        "fps": 15.0,
        "owner": "lava_tank_5",
        "ownerClass": "func_tracktrain",
        "spawn": [
            8976.0,
            -8112.0,
            6592.0
        ]
    },
    {
        "name": "port_anim_lava_4",
        "frames": 78,
        "fps": 15.0,
        "owner": "lava_tank_6",
        "ownerClass": "func_tracktrain",
        "spawn": [
            9368.0,
            -8112.0,
            6300.0
        ]
    },
    {
        "name": "port_anim_lava_5",
        "frames": 78,
        "fps": 15.0,
        "owner": "lava_tank_7",
        "ownerClass": "func_tracktrain",
        "spawn": [
            9368.0,
            -8112.0,
            6884.0
        ]
    },
    {
        "name": "port_anim_lava_6",
        "frames": 78,
        "fps": 15.0,
        "owner": "lava_tank_7",
        "ownerClass": "func_tracktrain",
        "spawn": [
            8976.0,
            -7920.0,
            6884.0
        ]
    },
    {
        "name": "port_anim_lava_7",
        "frames": 78,
        "fps": 15.0,
        "owner": "lava_tank_8",
        "ownerClass": "func_tracktrain",
        "spawn": [
            8976.0,
            -7920.0,
            6300.0
        ]
    },
    {
        "name": "port_anim_lava_8",
        "frames": 78,
        "fps": 15.0,
        "owner": "lava_tank_9",
        "ownerClass": "func_tracktrain",
        "spawn": [
            9368.0,
            -7920.0,
            6592.0
        ]
    },
    {
        "name": "port_anim_lava_9",
        "frames": 78,
        "fps": 15.0,
        "owner": "",
        "ownerClass": ""
    }
];
const portAnimSkin = PORT_ANIM.map(() => -1);
function portAnimAttach() {
    for (const a of PORT_ANIM) {
        if (!a.owner) continue;
        const prop = Entities.FindByName(a.name)[0]; if (!prop) continue;
        const owners = Entities.FindByName(a.owner).filter(e => !a.ownerClass || e.GetClassName() === a.ownerClass);
        let owner = owners[0];
        if (owners.length > 1 && a.spawn) {            // duplicate names: the one spawned where this prop's owner was expected
            let best = 1e18;
            for (const e of owners) {
                const o = e.GetAbsOrigin(); const d = (o.x - a.spawn[0]) ** 2 + (o.y - a.spawn[1]) ** 2 + (o.z - a.spawn[2]) ** 2;
                if (d < best) { best = d; owner = e; }
            }
        }
        if (!owner) continue;
        try {
            prop.SetParent(undefined);
            prop.Teleport({ position: owner.GetAbsOrigin(), angles: owner.GetAbsAngles() });
            prop.SetParent(owner);
        } catch (e) { Console.Log("port_anim: could not attach " + a.name + ": " + e); }
    }
}
Instance.OnRoundStart(() => { portAnimAttach(); for (let i = 0; i < portAnimSkin.length; i++) portAnimSkin[i] = -1; wakeThink(); });
THINKERS.push(() => {
    const t = Instance.GetGameTime();
    for (let i = 0; i < PORT_ANIM.length; i++) {
        const a = PORT_ANIM[i]; const f = Math.floor(t * a.fps) % a.frames;
        if (f === portAnimSkin[i]) continue;
        portAnimSkin[i] = f;
        Entities.FireInput({ name: a.name, input: "Skin", value: String(f) });
    }
    return true;
});
wakeThink();
// ---------------------------------------------------------------- end port_anim
