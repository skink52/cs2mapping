import { Instance, CSPlayerPawn, CSPlayerController } from "cs_script/point_script";

// mg_metal_course_level_2: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_metal_course_level_2_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   PushIn_<n> / PushOut_<n>   replaces the trigger_push brushes (CS:GO "set speed" behaviour)
//   Cmd_<n>     replaces point_servercommand (chat messages / cvars)
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
            1.0,
            0.0,
            0.0
        ],
        "speed": 850.0,
        "mins": [
            2112.0,
            4928.0,
            128.0
        ],
        "maxs": [
            2176.0,
            4992.0,
            256.0
        ]
    },
    "2": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 1.0,
        "mins": [
            3968.0,
            6208.0,
            -8.0
        ],
        "maxs": [
            4736.0,
            6528.0,
            320.0
        ]
    },
    "3": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1200.0,
        "mins": [
            4928.0,
            6912.0,
            -8.0
        ],
        "maxs": [
            5248.0,
            7296.0,
            192.0
        ]
    },
    "4": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1200.0,
        "mins": [
            3520.0,
            5376.0,
            96.0
        ],
        "maxs": [
            3584.0,
            6016.0,
            256.0
        ]
    },
    "5": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 70.0,
        "mins": [
            6080.0,
            7616.0,
            128.0
        ],
        "maxs": [
            6144.0,
            7936.0,
            320.0
        ]
    },
    "6": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 70.0,
        "mins": [
            5824.0,
            7616.0,
            128.0
        ],
        "maxs": [
            5952.0,
            7936.0,
            320.0
        ]
    },
    "7": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 70.0,
        "mins": [
            5632.0,
            7616.0,
            128.0
        ],
        "maxs": [
            5696.0,
            7936.0,
            320.0
        ]
    },
    "8": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 100.0,
        "mins": [
            -832.0,
            576.0,
            64.0
        ],
        "maxs": [
            -768.0,
            896.0,
            320.0
        ]
    },
    "9": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 100.0,
        "mins": [
            -1024.0,
            704.0,
            128.0
        ],
        "maxs": [
            -896.0,
            768.0,
            320.0
        ]
    },
    "10": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 100.0,
        "mins": [
            -1152.0,
            576.0,
            64.0
        ],
        "maxs": [
            -1088.0,
            896.0,
            320.0
        ]
    },
    "11": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1200.0,
        "mins": [
            1609.0,
            4032.0,
            165.0
        ],
        "maxs": [
            1810.1102294921875,
            4544.0,
            341.0
        ]
    },
    "12": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 250.0,
        "mins": [
            640.0,
            3520.0,
            128.0
        ],
        "maxs": [
            704.0,
            3584.0,
            152.0
        ]
    },
    "13": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1200.0,
        "mins": [
            -1664.0,
            1152.0,
            208.0
        ],
        "maxs": [
            -1536.0,
            1792.0,
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

// ---------------------------------------------------------------- point_servercommand replacement
// CS2 servers block most point_servercommand commands, so the map's chat messages / cvars are sent from script instead.
/** @type {string[]} */
const COMMANDS = [
    "say --> Map By ScHoOuFi, CS2 By Skink52 <--",
    "say --> Spawn Protection Enabled <--",
    "say --> Spawn Protection in 40 Seconds <--",
    "sv_airaccelerate 900"
];
COMMANDS.forEach((cmd, i) => {
    Instance.OnScriptInput("Cmd_" + i, () => { Instance.ServerCommand(cmd); });
});

// ---------------------------------------------------------------- game_score replacement (entity removed in CS2)
// Outputs that fired <game_score>.ApplyScore now fire Score_<points>; the activator's scoreboard score goes up.
for (const pts of [150]) {
    Instance.OnScriptInput("Score_" + pts, ({ activator }) => {
        const pawn = activator instanceof CSPlayerPawn ? activator : undefined;
        const ctrl = pawn ? pawn.GetPlayerController() : (activator instanceof CSPlayerController ? activator : undefined);
        if (ctrl && ctrl.IsValid()) ctrl.AddScore(pts);
    });
}

// ---------------------------------------------------------------- he2-he13 glow follow
// Each grenade heN has info_particle_system glows named heglow_heN_<k> (particles/heglow/*.vpcf, which follow their entity).
// The glows are unparented and moved every tick: on the grenade, at the carrier's chest, then on the thrown projectile.
const HE_NAMES = Array.from({ length: 12 }, (_, i) => "he" + (i + 2));
const HE_CARRY_Z = 40;
let hePairs = [];
let heReady = false;
let heTries = 0;

function heMove(ent, pos) {
    if (ent.Teleport) ent.Teleport({ position: pos }); else ent.Move({ position: pos });
}

function heInit() {
    hePairs = [];
    for (const n of HE_NAMES) {
        const w = Instance.FindEntityByName(n);
        if (!w || !w.IsValid()) continue;
        const wp = w.GetAbsOrigin();
        for (let k = 1; k <= 8; k++) {
            const g = Instance.FindEntityByName("heglow_" + n + "_" + k);
            if (!g || !g.IsValid()) continue;
            const gp = g.GetAbsOrigin();
            hePairs.push({ name: n, w, g, owner: undefined, proj: undefined, thrown: false, wait: 0,
                ofs: { x: gp.x - wp.x, y: gp.y - wp.y, z: gp.z - wp.z } });
            Instance.EntFireAtTarget({ target: g, input: "ClearParent" });
        }
    }
    heReady = hePairs.length > 0 || ++heTries > 50;
}

function heFindProjectile(owner, name) {
    if (!owner || !owner.IsValid()) return undefined;
    for (const pr of Instance.FindEntitiesByClass("hegrenade_projectile")) {
        if (hePairs.some((q) => q.proj === pr && q.name !== name)) continue;
        const po = pr.GetOwner();
        if (po && po.IsValid() && po === owner) return pr;
    }
    return undefined;
}

if (typeof Instance.OnGrenadeThrow === "function") {
    Instance.OnGrenadeThrow((e) => {
        const n = e && e.weapon && e.weapon.IsValid() ? e.weapon.GetEntityName() : "";
        if (!n || !e.projectile) return;
        for (const q of hePairs) if (q.name === n && !q.proj) q.proj = e.projectile;
    });
}

Instance.OnRoundStart(() => { heReady = false; heTries = 0; wakeThink(); });

THINKERS.push(() => {
    if (!heReady) { heInit(); return true; }
    for (let i = hePairs.length - 1; i >= 0; i--) {
        const q = hePairs[i];
        if (!q.g || !q.g.IsValid()) { hePairs.splice(i, 1); continue; }

        if (q.w && q.w.IsValid()) {
            const o = q.w.GetOwner();
            if (o && o.IsValid() && o instanceof CSPlayerPawn) {
                q.owner = o;
                const p = o.GetAbsOrigin();
                heMove(q.g, { x: p.x + q.ofs.x, y: p.y + q.ofs.y, z: p.z + HE_CARRY_Z + q.ofs.z });
            } else {
                const p = q.w.GetAbsOrigin();
                heMove(q.g, { x: p.x + q.ofs.x, y: p.y + q.ofs.y, z: p.z + q.ofs.z });
            }
            continue;
        }

        if (!q.proj) q.proj = heFindProjectile(q.owner, q.name);
        if (q.proj && q.proj.IsValid()) {
            const p = q.proj.GetAbsOrigin();
            heMove(q.g, { x: p.x + q.ofs.x, y: p.y + q.ofs.y, z: p.z + q.ofs.z });
            q.thrown = true;
            continue;
        }
        if (q.thrown || ++q.wait > 10) {
            Instance.EntFireAtTarget({ target: q.g, input: "Kill" });
            hePairs.splice(i, 1);
        }
    }
    return true;
});
wakeThink();
