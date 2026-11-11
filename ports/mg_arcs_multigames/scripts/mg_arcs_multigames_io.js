import { Instance, Entities, Console, CSPlayerPawn, CSPlayerController, CSInputs, CSGearSlot } from "cs_script/point_script";

// mg_arcs_multigames: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_arcs_multigames_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   PushIn_<n> / PushOut_<n>   replaces the trigger_push brushes (CS:GO "set speed" behaviour)
//   Cmd_<n>     replaces point_servercommand (chat messages / cvars)
//   Speed_<mult> replaces player_speedmod ModifySpeed (activator only, 1 = back to normal)
//   (automatic) replaces game_player_equips without "Use Only" (CS:GO ran them on every spawn, CS2 does not)
//   Item_<equip> / ItemAll_<equip>  replaces item_* (armour) in game_player_equips: CS2 crashes on map load with an item in a weapon slot
//   Global_<On|Off|Toggle>_<n> replaces env_global (states kept across rounds; logic_autos reading them -> port_globalauto_<k>)

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
            -1.0,
            0.0,
            0.0
        ],
        "speed": 777.0,
        "mins": [
            -1088.0,
            3872.0,
            132.0
        ],
        "maxs": [
            -704.10888671875,
            4128.0,
            156.8179931640625
        ]
    },
    "2": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 777.0,
        "mins": [
            -3519.98046875,
            3872.0,
            132.0
        ],
        "maxs": [
            -3136.0,
            4128.0,
            156.8179931640625
        ]
    },
    "3": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 300.0,
        "mins": [
            768.0,
            2304.0,
            -312.0
        ],
        "maxs": [
            2304.0,
            2528.0,
            -308.0
        ]
    },
    "4": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 300.0,
        "mins": [
            2304.0,
            768.0,
            -312.0
        ],
        "maxs": [
            2528.0,
            2304.0,
            -308.0
        ]
    },
    "5": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 300.0,
        "mins": [
            768.0,
            544.0,
            -312.0
        ],
        "maxs": [
            2304.0,
            768.0,
            -308.0
        ]
    },
    "6": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 300.0,
        "mins": [
            544.0,
            768.0,
            -312.0
        ],
        "maxs": [
            768.0,
            2304.0,
            -308.0
        ]
    },
    "7": {
        "dir": [
            0.309,
            -0.9511,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -3040.0,
            6965.0,
            552.0
        ],
        "maxs": [
            -2649.0,
            7296.0,
            553.0
        ]
    },
    "8": {
        "dir": [
            0.5878,
            -0.809,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -2974.0,
            6685.0,
            552.0
        ],
        "maxs": [
            -2538.0,
            7100.0,
            553.0
        ]
    },
    "9": {
        "dir": [
            0.809,
            -0.5878,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -2787.0,
            6498.0,
            552.0
        ],
        "maxs": [
            -2372.0,
            6934.0,
            553.0
        ]
    },
    "10": {
        "dir": [
            0.9511,
            -0.309,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -2507.0,
            6432.0,
            552.0
        ],
        "maxs": [
            -2176.0,
            6823.0,
            553.0
        ]
    },
    "11": {
        "dir": [
            0.9511,
            0.309,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -1664.0,
            6432.0,
            552.0
        ],
        "maxs": [
            -1333.0,
            6823.0,
            553.0
        ]
    },
    "12": {
        "dir": [
            0.809,
            0.5878,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -1468.0,
            6498.0,
            552.0
        ],
        "maxs": [
            -1053.0,
            6934.0,
            553.0
        ]
    },
    "13": {
        "dir": [
            0.5878,
            0.809,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -1302.0,
            6685.0,
            552.0
        ],
        "maxs": [
            -866.0,
            7100.0,
            553.0
        ]
    },
    "14": {
        "dir": [
            0.309,
            0.9511,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -1191.0,
            6965.0,
            552.0
        ],
        "maxs": [
            -800.0,
            7296.0,
            553.0
        ]
    },
    "15": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -1152.0,
            7296.0,
            552.0
        ],
        "maxs": [
            -800.0,
            8320.0,
            553.0
        ]
    },
    "16": {
        "dir": [
            -0.309,
            0.9511,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -1191.0,
            8320.0,
            552.0
        ],
        "maxs": [
            -800.0,
            8651.0,
            553.0
        ]
    },
    "17": {
        "dir": [
            -0.809,
            0.5878,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -1468.0,
            8682.0,
            552.0
        ],
        "maxs": [
            -1053.0,
            9118.0,
            553.0
        ]
    },
    "18": {
        "dir": [
            -0.5878,
            0.809,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -1302.0,
            8516.0,
            552.0
        ],
        "maxs": [
            -866.0,
            8931.0,
            553.0
        ]
    },
    "19": {
        "dir": [
            -0.9511,
            0.309,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -1664.0,
            8793.0,
            552.0
        ],
        "maxs": [
            -1333.0,
            9184.0,
            553.0
        ]
    },
    "20": {
        "dir": [
            -0.9511,
            -0.309,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -2507.0,
            8793.0,
            552.0
        ],
        "maxs": [
            -2176.0,
            9184.0,
            553.0
        ]
    },
    "21": {
        "dir": [
            -0.809,
            -0.5878,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -2787.0,
            8682.0,
            552.0
        ],
        "maxs": [
            -2372.0,
            9118.0,
            553.0
        ]
    },
    "22": {
        "dir": [
            -0.5878,
            -0.809,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -2974.0,
            8516.0,
            552.0
        ],
        "maxs": [
            -2538.0,
            8931.0,
            553.0
        ]
    },
    "23": {
        "dir": [
            -0.309,
            -0.9511,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -3040.0,
            8320.0,
            552.0
        ],
        "maxs": [
            -2649.0,
            8651.0,
            553.0
        ]
    },
    "24": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -3040.0,
            7296.0,
            552.0
        ],
        "maxs": [
            -2688.0,
            8320.0,
            553.0
        ]
    },
    "25": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 300.0,
        "mins": [
            7232.0,
            -5184.0,
            -128.0
        ],
        "maxs": [
            7408.0,
            -3312.0,
            -116.0
        ]
    },
    "26": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 300.0,
        "mins": [
            7232.0,
            -3312.0,
            -128.0
        ],
        "maxs": [
            9104.0,
            -3136.0,
            -116.0
        ]
    },
    "27": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 300.0,
        "mins": [
            9104.0,
            -5008.0,
            -128.0
        ],
        "maxs": [
            9280.0,
            -3136.0,
            -116.0
        ]
    },
    "28": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 300.0,
        "mins": [
            7408.0,
            -5184.0,
            -128.0
        ],
        "maxs": [
            9280.0,
            -5008.0,
            -116.0
        ]
    },
    "29": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 800.0,
        "mins": [
            7376.0,
            -4736.0,
            64.0
        ],
        "maxs": [
            7712.0,
            -3584.0,
            176.0
        ]
    },
    "30": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 800.0,
        "mins": [
            8800.0,
            -4736.0,
            64.0
        ],
        "maxs": [
            9136.0,
            -3584.0,
            176.0
        ]
    },
    "31": {
        "dir": [
            0.809,
            0.5878,
            0.0
        ],
        "speed": 2000.0,
        "mins": [
            777.1766357421875,
            5328.0,
            64.0
        ],
        "maxs": [
            1060.30078125,
            7984.0,
            309.84765625
        ]
    },
    "32": {
        "dir": [
            -0.7314,
            0.682,
            0.0
        ],
        "speed": 2000.0,
        "mins": [
            4308.87890625,
            5328.0,
            64.0
        ],
        "maxs": [
            4592.0,
            7984.0,
            309.844970703125
        ]
    },
    "33": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 900.0,
        "mins": [
            9312.0,
            2816.0,
            -576.0
        ],
        "maxs": [
            9504.0,
            3008.0,
            -64.0
        ]
    },
    "34": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 900.0,
        "mins": [
            8992.0,
            2848.0,
            -192.0
        ],
        "maxs": [
            9120.0,
            2976.0,
            192.0
        ]
    },
    "35": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 900.0,
        "mins": [
            8320.0,
            2848.0,
            64.0
        ],
        "maxs": [
            8416.0,
            2944.0,
            448.0
        ]
    },
    "36": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 900.0,
        "mins": [
            6880.0,
            1952.0,
            320.0
        ],
        "maxs": [
            7008.0,
            2080.0,
            704.0
        ]
    },
    "37": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 900.0,
        "mins": [
            7232.0,
            1888.0,
            592.0
        ],
        "maxs": [
            7360.0,
            2016.0,
            976.0
        ]
    },
    "38": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 900.0,
        "mins": [
            7232.0,
            2176.0,
            864.0
        ],
        "maxs": [
            7360.0,
            2304.0,
            1216.0
        ]
    },
    "39": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 800.0,
        "mins": [
            9088.0,
            3648.0,
            96.0
        ],
        "maxs": [
            14912.0,
            6080.0,
            97.0
        ]
    },
    "40": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -2176.0,
            6432.0,
            552.0
        ],
        "maxs": [
            -1664.0,
            6784.0,
            553.0
        ]
    },
    "41": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -2176.0,
            8832.0,
            552.0
        ],
        "maxs": [
            -1664.0,
            9184.0,
            553.0
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

// ---------------------------------------------------------------- point_servercommand replacement
// CS2 servers block most point_servercommand commands, so the map's chat messages / cvars are sent from script instead.
/** @type {string[]} */
const COMMANDS = [
    "say @[Music] Calvin Harris - Feel So Close",
    "mp_freezetime 5",
    "mp_roundtime 5",
    "mp_round_restart_delay 5",
    "mp_roundtime_defuse 5",
    "sv_airaccelerate 150",
    "mp_startmoney 16000",
    "sv_enablebunnyhopping 1",
    "mp_warmup_end",
    "mp_solid_teammates 0",
    "mp_weapons_allow_map_placed 1",
    "say @[Music] Imagine Dragons - Radioactive",
    "say @[Music] Vicetone - Nevada (feat. Cozi Zuehlsdorff)",
    "say @[Music] Alan Walker - Faded",
    "say @[Music] Halsey - New Americana (OLWIK Deep House Remix)",
    "say @[Music] Marshmello - Alone",
    "say @[Music] The Script - Hall of Fame ft. will.i.am",
    "say @[Music] Rich Edwards - Where I'll Be Waiting",
    "ammo_57mm_max 1337",
    "ammo_buckshot_max 1337",
    "ammo_357sig_max 1337",
    "ammo_45acp_max 1337",
    "ammo_9mm_max 1337",
    "ammo_338mag_max 1337",
    "ammo_556mm_max 1337",
    "ammo_556mm_box_max 1337",
    "ammo_762mm_max 1337",
    "ammo_50ae_max 1337",
    "say @[Map] Map made by Arcaninesy",
    "say @[Map] Map ported by Blogger(Dog)",
    "say *** Ported to CS2 by skink52 ***",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Headshot mode enabled.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say Map by Arcaninesy",
    "say @[Game] Pushcircle [Buy]",
    "say Map by Arcaninesy",
    "say @[Game] Bunnyhop Battle",
    "say 30 seconds remaining.",
    "say You have one minute.",
    "say Three",
    "say Two",
    "say One",
    "say Good luck!",
    "say Map by Arcaninesy",
    "say @[Game] Defuse",
    "say Map by Arcaninesy",
    "say @[Game] Snipers",
    "say @[Map] AFK KILLER",
    "say Map by Arcaninesy",
    "say @[Game] Knife",
    "say Map by Arcaninesy",
    "say @[Game] Knife [Backstab]",
    "say Map by Arcaninesy",
    "say @[Game] Shotguns [Boxes]",
    "say Boxes disappear in 30 seconds.",
    "say Boxes disappear in 1 second.",
    "say Boxes disappear in 2 seconds.",
    "say Boxes disappear in 3 seconds.",
    "say Boxes disappear in 10 seconds.",
    "say Map by Arcaninesy",
    "say @[Game] Shotguns [Plus Signs]",
    "say Cover disappears in 30 seconds.",
    "say Cover disappears in 10 seconds.",
    "say Cover disappears in 3 seconds.",
    "say Cover disappears in 2 seconds.",
    "say Cover disappears in 1 second.",
    "say Map by Arcaninesy",
    "say @[Game] 1v1 [Knife]",
    "say Map by Arcaninesy",
    "say @[Game] 1v1 [Deagle]",
    "say Map by Arcaninesy",
    "say @[Game] Blind Elites",
    "say Map by Arcaninesy",
    "say @[Game] Blind Deagle",
    "say Map by Arcaninesy",
    "say @[Game] Boostknife [Backstab]",
    "say Map by Arcaninesy",
    "say @[Game] Boostknife",
    "say Map by Arcaninesy",
    "say @[Game] Arena [Scouts]",
    "say Map by Arcaninesy",
    "say @[Game] Arena [USP]",
    "say Map by Arcaninesy",
    "say @[Game] Arena [Shotguns]",
    "say Map by Arcaninesy",
    "say @[Game] Arena [Elites]",
    "say Map by Arcaninesy",
    "say @[Game] Arena [MP7]",
    "say Map by Arcaninesy",
    "say @[Game] Arena [M4A1]",
    "say Cannons disabled.",
    "say Cannons disabled in ten seconds.",
    "say Map by Arcaninesy",
    "say Cannon Surf [Shotguns]",
    "say Map by Arcaninesy",
    "say @[Game] Cannon Surf [Knives]",
    "say Cannons disabled.",
    "say Cannons disabled in ten seconds.",
    "say Map by Arcaninesy",
    "say @[Game] Iceskate [Backstab]",
    "say Map by Arcaninesy",
    "say @[Game] Iceskate",
    "say Map by Arcaninesy",
    "say @[Game] Buy",
    "say Map by Arcaninesy",
    "say @[Game] Snipers [Small]",
    "say @[Map] AFK KILLER",
    "say Map by Arcaninesy",
    "say @[Game] Trains",
    "say Random!",
    "say Locked against repetition.",
    "say Map by Arcaninesy",
    "say @[Game] Pushcircle [No Buy]",
    "say Headshot/backstab mode enabled.",
    "say Locked against repetition.",
    "say Locked against repetition.",
    "say No remaining players to teleport. Dividing walls have been broken."
];
COMMANDS.forEach((cmd, i) => {
    Instance.OnScriptInput("Cmd_" + i, () => { Console.ServerCommand(cmd); });
});

// ---------------------------------------------------------------- player_speedmod replacement (dead in CS2)
// While a player has a multiplier, their ground speed is driven from their own movement keys at 250 x mult.
const BASE_SPEED = 250, WALK_FACTOR = 0.52, DUCK_FACTOR = 0.34;
/** @type {Map<number, number>} player slot -> speed multiplier */
const speedBySlot = new Map();
function speedPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
THINKERS.push(() => {
    for (const [slot, mult] of speedBySlot) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { speedBySlot.delete(slot); continue; }
        if (!pawn.GetGroundEntity()) continue;
        const fwd = (pawn.IsInputPressed(CSInputs.FORWARD) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.BACK) ? 1 : 0);
        const side = (pawn.IsInputPressed(CSInputs.RIGHT) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.LEFT) ? 1 : 0);
        if (fwd === 0 && side === 0) continue;
        const yaw = pawn.GetEyeAngles().yaw * Math.PI / 180;
        let dx = Math.cos(yaw) * fwd + Math.sin(yaw) * side;
        let dy = Math.sin(yaw) * fwd - Math.cos(yaw) * side;
        const len = Math.hypot(dx, dy); dx /= len; dy /= len;
        let speed = BASE_SPEED * mult;
        if (pawn.IsInputPressed(CSInputs.WALK)) speed *= WALK_FACTOR;
        if (pawn.IsDucking()) speed *= DUCK_FACTOR;
        pawn.Move({ velocity: { x: dx * speed, y: dy * speed, z: pawn.GetAbsVelocity().z } });
    }
    return speedBySlot.size > 0;
});
for (const s of [1.5]) {
    Instance.OnScriptInput("Speed_" + s, ({ activator }) => {
        const pawn = speedPawn(activator);
        const ctrl = pawn ? pawn.GetPlayerController() : undefined;
        if (!ctrl) return;
        if (s === 1) speedBySlot.delete(ctrl.GetPlayerSlot()); else speedBySlot.set(ctrl.GetPlayerSlot(), s);
        wakeThink();
    });
}

// ---------------------------------------------------------------- spawn equips (game_player_equip without "Use Only")
// CS:GO ran these on every spawn ("Strip First" = start with nothing but their items). CS2 doesn't, so each (re)spawning
// player is handled one tick after OnPlayerReset (after CS2 has handed out its default loadout).
/** @type {{ strip: boolean, items: string[] }[]} */
const SPAWN_EQUIPS = [{"strip": true, "items": []}];
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

// ---------------------------------------------------------------- game_player_equip items (item_assaultsuit, item_kevlar...)
// An item_* in a game_player_equip weapon slot crashes the CS2 server on map load, so the items were taken out of the equips
// and are given from here: every output that triggers the equip also fires Item_<equip> (activator) or ItemAll_<equip>.
/** @type {Record<string, string[]>} */
const EQUIP_ITEMS = {
    "GIVE_KevlarHelmet": [
        "item_assaultsuit"
    ]
};
function itemPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
function giveItems(pawn, items) {
    if (pawn && pawn.IsValid() && pawn.IsAlive()) for (const it of items) pawn.GiveNamedItem(it, false);
}
for (const [equip, items] of Object.entries(EQUIP_ITEMS)) {
    Instance.OnScriptInput("Item_" + equip, ({ activator }) => giveItems(itemPawn(activator), items));
    Instance.OnScriptInput("ItemAll_" + equip, () => {
        for (let slot = 0; slot < 64; slot++) giveItems(Instance.GetPlayerController(slot)?.GetPlayerPawn(), items);
    });
}

// ---------------------------------------------------------------- env_global replacement (not in CS2)
// Global states live here, so they survive a round restart like CS:GO's env_global. Each logic_auto that read one is now a
// logic_relay; at round start the script triggers the ones whose state is on.
const GLOBAL_NAMES = ["1i", "3a", "2a", "1a", "1b", "2b", "3b", "3", "2", "1", "1l", "2l", "3l", "1c", "2c", "3c", "1d", "2d", "3d", "1e", "2e", "3e", "1f", "2f", "3f", "3g", "2g", "1g", "3h", "2h", "1h", "3j", "2j", "1j", "3k", "2k", "1k", "3m", "2m", "1m", "3n", "2n", "1n"];
const GLOBAL_ON = new Set([]);
/** @type {[string, number][]} relay name, global index */
const GLOBAL_AUTOS = [["port_globalauto_0", 0], ["port_globalauto_1", 1], ["port_globalauto_2", 2], ["port_globalauto_3", 3], ["port_globalauto_4", 4], ["port_globalauto_5", 5], ["port_globalauto_6", 6], ["port_globalauto_7", 7], ["port_globalauto_8", 8], ["port_globalauto_9", 9], ["port_globalauto_10", 10], ["port_globalauto_11", 12], ["port_globalauto_12", 11], ["port_globalauto_13", 13], ["port_globalauto_14", 14], ["port_globalauto_15", 15], ["port_globalauto_16", 16], ["port_globalauto_17", 17], ["port_globalauto_18", 18], ["port_globalauto_19", 19], ["port_globalauto_20", 20], ["port_globalauto_21", 21], ["port_globalauto_22", 22], ["port_globalauto_23", 23], ["port_globalauto_24", 24], ["port_globalauto_25", 25], ["port_globalauto_26", 26], ["port_globalauto_27", 27], ["port_globalauto_28", 29], ["port_globalauto_29", 30], ["port_globalauto_30", 28], ["port_globalauto_31", 31], ["port_globalauto_32", 32], ["port_globalauto_33", 33], ["port_globalauto_34", 34], ["port_globalauto_35", 35], ["port_globalauto_36", 36], ["port_globalauto_37", 38], ["port_globalauto_38", 39], ["port_globalauto_39", 37], ["port_globalauto_40", 40], ["port_globalauto_41", 41], ["port_globalauto_42", 42]];
GLOBAL_NAMES.forEach((_, i) => {
    Instance.OnScriptInput("Global_On_" + i, () => { GLOBAL_ON.add(i); });
    Instance.OnScriptInput("Global_Off_" + i, () => { GLOBAL_ON.delete(i); });
    Instance.OnScriptInput("Global_Toggle_" + i, () => { if (GLOBAL_ON.has(i)) GLOBAL_ON.delete(i); else GLOBAL_ON.add(i); });
});
Instance.OnRoundStart(() => {
    const on = GLOBAL_AUTOS.filter(([, i]) => GLOBAL_ON.has(i)).map(([relay]) => relay);   // states as the round began
    for (const relay of on) Entities.FireInput({ name: relay, input: "Trigger", delay: 0.1 });
});
