import { Instance, CSPlayerPawn, CSPlayerController, CSMoveType } from "cs_script/point_script";

// ttt_minecraft: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `ttt_minecraft_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   PushIn_<n> / PushOut_<n>   replaces the trigger_push brushes (CS:GO "set speed" behaviour)
//   Gravity_<scale> replaces trigger_gravity (activator only, 1 = back to normal; the trigger fires Gravity_1 on leaving)
//   (automatic) players push physics props in proportion to the prop mass

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
            1,
            0,
            0
        ],
        "speed": 250,
        "mins": [
            -3584,
            -256,
            -256
        ],
        "maxs": [
            -2816,
            2016,
            -160
        ]
    },
    "2": {
        "dir": [
            1,
            0,
            0
        ],
        "speed": 250,
        "mins": [
            -3584,
            -1280,
            -256
        ],
        "maxs": [
            -2688,
            -257.94122314453125,
            -160
        ]
    },
    "3": {
        "dir": [
            0,
            1,
            0
        ],
        "speed": 250,
        "mins": [
            -2688,
            -768,
            -256
        ],
        "maxs": [
            -2176,
            -256,
            -160
        ]
    },
    "4": {
        "dir": [
            1,
            0,
            0
        ],
        "speed": 250,
        "mins": [
            -2688,
            -768,
            -256
        ],
        "maxs": [
            -2176,
            -256,
            -160
        ]
    },
    "5": {
        "dir": [
            1,
            0,
            0
        ],
        "speed": 250,
        "mins": [
            -2688,
            -1280,
            -256
        ],
        "maxs": [
            -2176,
            -768,
            -160
        ]
    },
    "6": {
        "dir": [
            1,
            0,
            0
        ],
        "speed": 250,
        "mins": [
            -3584,
            -1792,
            -256
        ],
        "maxs": [
            -2176,
            -1280,
            -160
        ]
    },
    "7": {
        "dir": [
            1,
            0,
            0
        ],
        "speed": 250,
        "mins": [
            -3584,
            -2272,
            -256
        ],
        "maxs": [
            -1536,
            -1792,
            -160
        ]
    },
    "8": {
        "dir": [
            0.7071,
            0.7071,
            0
        ],
        "speed": 250,
        "mins": [
            -2176,
            -1792,
            -256
        ],
        "maxs": [
            -1536,
            -1152,
            -160
        ]
    },
    "9": {
        "dir": [
            -0.7071,
            0.7071,
            0
        ],
        "speed": 250,
        "mins": [
            256,
            -1792,
            -256
        ],
        "maxs": [
            1280,
            -768,
            -160
        ]
    },
    "10": {
        "dir": [
            -1,
            0,
            0
        ],
        "speed": 250,
        "mins": [
            1280,
            -1792,
            -256
        ],
        "maxs": [
            2048,
            1536,
            -160
        ]
    },
    "11": {
        "dir": [
            -0.7071,
            -0.7071,
            0
        ],
        "speed": 250,
        "mins": [
            768,
            1024,
            -256
        ],
        "maxs": [
            1280,
            1536,
            -160
        ]
    },
    "12": {
        "dir": [
            0,
            -1,
            0
        ],
        "speed": 250,
        "mins": [
            -2816,
            1536,
            -256
        ],
        "maxs": [
            2048,
            2016,
            -160
        ]
    },
    "13": {
        "dir": [
            0.7071,
            -0.7071,
            0
        ],
        "speed": 250,
        "mins": [
            -2816,
            1023.98828125,
            -256
        ],
        "maxs": [
            -2320,
            1536,
            -160
        ]
    },
    "14": {
        "dir": [
            -1,
            0,
            0
        ],
        "speed": 250,
        "mins": [
            256,
            -2272,
            -256
        ],
        "maxs": [
            2048,
            -1792,
            -160
        ]
    },
    "15": {
        "dir": [
            0,
            1,
            0
        ],
        "speed": 250,
        "mins": [
            -768,
            -2272,
            -256
        ],
        "maxs": [
            256,
            -2048,
            -160
        ]
    },
    "16": {
        "dir": [
            0,
            1,
            0
        ],
        "speed": 250,
        "mins": [
            -1536,
            -2272,
            -256
        ],
        "maxs": [
            -768,
            -1920,
            -160
        ]
    },
    "17": {
        "dir": [
            -1,
            0,
            0
        ],
        "speed": 300,
        "mins": [
            -564,
            208,
            -5280
        ],
        "maxs": [
            -556,
            288,
            -5216
        ]
    },
    "18": {
        "dir": [
            1,
            0,
            0
        ],
        "speed": 300,
        "mins": [
            -656,
            208,
            -5280
        ],
        "maxs": [
            -652,
            288,
            -5216
        ]
    },
    "19": {
        "dir": [
            1,
            0,
            0
        ],
        "speed": 128,
        "mins": [
            480,
            -480,
            576
        ],
        "maxs": [
            488,
            -416,
            664
        ]
    },
    "20": {
        "dir": [
            -1,
            0,
            0
        ],
        "speed": 128,
        "mins": [
            512,
            -480,
            576
        ],
        "maxs": [
            520,
            -416,
            664
        ]
    },
    "21": {
        "dir": [
            0,
            -1,
            0
        ],
        "speed": 128,
        "mins": [
            488,
            -424,
            576
        ],
        "maxs": [
            512,
            -416,
            664
        ]
    },
    "22": {
        "dir": [
            0,
            1,
            0
        ],
        "speed": 128,
        "mins": [
            488,
            -480,
            576
        ],
        "maxs": [
            512,
            -472,
            664
        ]
    },
    "23": {
        "dir": [
            0,
            1,
            0
        ],
        "speed": 300,
        "mins": [
            -448,
            64,
            -5056
        ],
        "maxs": [
            -320,
            160,
            -4960
        ]
    },
    "24": {
        "dir": [
            0,
            0,
            -1
        ],
        "speed": 600,
        "mins": [
            -480,
            512,
            -5248
        ],
        "maxs": [
            -288,
            568,
            -5024
        ]
    },
    "25": {
        "dir": [
            0,
            0,
            -1
        ],
        "speed": 600,
        "mins": [
            -480,
            328,
            -5088
        ],
        "maxs": [
            -288,
            384,
            -4992
        ]
    },
    "26": {
        "dir": [
            0,
            0,
            -1
        ],
        "speed": 600,
        "mins": [
            736,
            -576,
            368
        ],
        "maxs": [
            800,
            -448,
            576
        ]
    },
    "27": {
        "dir": [
            1,
            0,
            0
        ],
        "speed": 400,
        "mins": [
            720,
            -576,
            368
        ],
        "maxs": [
            752,
            -448,
            576
        ]
    },
    "28": {
        "dir": [
            0,
            1,
            0
        ],
        "speed": 300,
        "mins": [
            -448,
            128,
            -5152
        ],
        "maxs": [
            -320,
            352,
            -5056
        ]
    },
    "29": {
        "dir": [
            1,
            0,
            0
        ],
        "speed": 300,
        "mins": [
            -16,
            624,
            480
        ],
        "maxs": [
            -12,
            672,
            544
        ]
    },
    "30": {
        "dir": [
            -1,
            0,
            0
        ],
        "speed": 300,
        "mins": [
            76,
            624,
            480
        ],
        "maxs": [
            84,
            672,
            544
        ]
    },
    "31": {
        "dir": [
            0,
            1,
            0
        ],
        "speed": 400,
        "mins": [
            736,
            -608,
            368
        ],
        "maxs": [
            768,
            -560,
            576
        ]
    },
    "32": {
        "dir": [
            0,
            -1,
            0
        ],
        "speed": 400,
        "mins": [
            736,
            -464,
            368
        ],
        "maxs": [
            768,
            -416,
            576
        ]
    },
    "33": {
        "dir": [
            -1,
            0,
            0
        ],
        "speed": 640,
        "mins": [
            -1920,
            672,
            -256
        ],
        "maxs": [
            -1856,
            768,
            -128
        ]
    },
    "34": {
        "dir": [
            1,
            0,
            0
        ],
        "speed": 640,
        "mins": [
            -2048,
            672,
            -256
        ],
        "maxs": [
            -1984,
            768,
            -128
        ]
    },
    "35": {
        "dir": [
            0,
            0,
            -1
        ],
        "speed": 320,
        "mins": [
            -2048,
            640,
            -256
        ],
        "maxs": [
            -1856,
            832,
            -128
        ]
    },
    "36": {
        "dir": [
            1,
            0,
            0
        ],
        "speed": 650,
        "mins": [
            -2080,
            384,
            -160
        ],
        "maxs": [
            -1856,
            544,
            -64
        ]
    },
    "37": {
        "dir": [
            0,
            -1,
            0
        ],
        "speed": 650,
        "mins": [
            -1992,
            532,
            -160
        ],
        "maxs": [
            -1952,
            572,
            -80
        ]
    },
    "38": {
        "dir": [
            0,
            1,
            0
        ],
        "speed": 640,
        "mins": [
            -1984,
            672,
            -256
        ],
        "maxs": [
            -1920,
            704,
            -128
        ]
    },
    "39": {
        "dir": [
            0,
            -1,
            0
        ],
        "speed": 250,
        "mins": [
            -1984,
            832,
            -256
        ],
        "maxs": [
            -1920,
            864,
            -128
        ]
    },
    "40": {
        "dir": [
            0,
            1,
            0
        ],
        "speed": 16,
        "mins": [
            -1184,
            768,
            0
        ],
        "maxs": [
            -1088,
            992,
            56
        ]
    },
    "41": {
        "dir": [
            1,
            0,
            0
        ],
        "speed": 16,
        "mins": [
            -1152,
            896,
            -32
        ],
        "maxs": [
            -288,
            1056,
            24
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

// ---------------------------------------------------------------- physics prop pushing
// Props listed here are pushed by players in proportion to mass: speed into the face x REF / (REF + mass).
/** @type {Record<string, number>} prop name (lower case) -> mass */
const PHYS = {
    "brickblock_1": 0.4,
    "brickblock_2": 0.4,
    "clay": 0.4,
    "diablock": 0.4,
    "diaore_1": 0.4,
    "diaore_2": 0.4,
    "diaore_3": 0.4,
    "diaore_4": 0.4,
    "diaore_5": 0.4,
    "diaore_6": 0.4,
    "diaore_7": 0.4,
    "diaore_8": 0.4,
    "diaore_9": 0.4,
    "goldblock": 8.2,
    "minecart": 144.1
};
const PHYS_REF = 20, PHYS_MIN_SPEED = 10, PHYS_MIN_INTO = 20, PHYS_EXTERNAL = 400, PHYS_SAFE = 150;
const PHYS_REACH = 8, PHYS_KEEP = 3, PHYS_SPIN_GAIN = 0.5, PHYS_SPIN_K = 400, PHYS_SPIN_MAX = 2;
const PHYS_STAND = { mins: { x: -16, y: -16, z: 4 }, maxs: { x: 16, y: 16, z: 72 } };
const PHYS_DUCK = { mins: { x: -16, y: -16, z: 4 }, maxs: { x: 16, y: 16, z: 54 } };
/** @type {Map<number, { vx: number, vy: number, nx: number, ny: number }>} slot -> last push (approach velocity, push direction) */
const physBySlot = new Map();
let physLast = 0;
function physMass(ent) {
    if (!ent || !ent.IsValid()) return undefined;
    if (ent.GetOwner() instanceof CSPlayerPawn) return undefined;        // held by a player (cs2mapTTT carry sets the owner)
    const cls = ent.GetClassName();
    if (cls !== "prop_physics" && cls !== "prop_physics_multiplayer" && cls !== "prop_physics_override" && cls !== "func_physbox") return undefined;
    return PHYS[ent.GetEntityName().toLowerCase()];
}
THINKERS.push(() => {
    const now = Instance.GetGameTime();
    const dt = Math.min(Math.max(now - physLast, 0.001), 0.1);
    physLast = now;
    for (let slot = 0; slot < 64; slot++) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { physBySlot.delete(slot); continue; }
        const v = pawn.GetAbsVelocity();
        const sp = Math.hypot(v.x, v.y);
        const last = physBySlot.get(slot);
        let dx, dy, reach;
        if (last) { dx = last.nx; dy = last.ny; reach = PHYS_KEEP; }
        else if (sp >= PHYS_MIN_INTO) { dx = v.x / sp; dy = v.y / sp; reach = PHYS_REACH; }
        else continue;
        const o = pawn.GetAbsOrigin();
        const hull = pawn.IsCrouched() || pawn.IsCrouching() ? PHYS_DUCK : PHYS_STAND;
        const tr = Instance.TraceBox({ mins: hull.mins, maxs: hull.maxs, start: o, end: { x: o.x + dx * reach, y: o.y + dy * reach, z: o.z }, ignoreEntity: pawn, ignorePlayers: true });
        const prop = tr.didHit && !tr.startedInSolid ? tr.hitEntity : undefined;
        const mass = physMass(prop);
        if (mass === undefined) { physBySlot.delete(slot); continue; }
        let nx = tr.normal.x, ny = tr.normal.y;
        const nl = Math.hypot(nx, ny);
        if (nl < 0.5) { physBySlot.delete(slot); continue; }          // standing on it, not pushing it
        nx = -nx / nl; ny = -ny / nl;                                   // into the prop
        if (nx * dx + ny * dy < 0) { nx = -nx; ny = -ny; }
        // the engine stops the player against the prop, so keep the faster of the live and remembered approach speeds
        let vx = v.x, vy = v.y;
        if (last && last.vx * nx + last.vy * ny > vx * nx + vy * ny) { vx = last.vx; vy = last.vy; }
        const into = vx * nx + vy * ny;
        if (into < PHYS_MIN_INTO) { physBySlot.delete(slot); continue; }
        physBySlot.set(slot, { vx, vy, nx, ny });
        const pv = prop.GetAbsVelocity();
        if (Math.hypot(pv.x, pv.y) > PHYS_EXTERNAL) continue;
        const speed = Math.max(PHYS_MIN_SPEED, into * PHYS_REF / (PHYS_REF + mass));
        const po = prop.GetAbsOrigin();
        const lever = (o.x - po.x) * ny - (o.y - po.y) * nx;
        const spin = Math.max(-PHYS_SPIN_MAX, Math.min(PHYS_SPIN_MAX, PHYS_SPIN_GAIN * speed * lever / PHYS_SPIN_K));
        const a = prop.GetAbsAngles();
        prop.Teleport({ velocity: { x: nx * speed, y: ny * speed, z: pv.z }, angles: { pitch: a.pitch, yaw: a.yaw + spin * dt * 180 / Math.PI, roll: a.roll } });
    }
    return true;
});
Instance.OnActivate(() => { physLast = Instance.GetGameTime(); wakeThink(); });
Instance.OnModifyPlayerDamage(({ inflictor }) => {
    if (physMass(inflictor) === undefined) return;
    const pv = inflictor.GetAbsVelocity();
    if (Math.hypot(pv.x, pv.y, pv.z) < PHYS_SAFE) return { abort: true };
});
