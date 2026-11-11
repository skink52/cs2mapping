import { Instance, Console, CSPlayerPawn, CSPlayerController, CSInputs, CSMoveType, CSGearSlot } from "cs_script/point_script";

// mg_color_multigames: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_color_multigames_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   PushIn_<n> / PushOut_<n>   replaces the trigger_push brushes (CS:GO "set speed" behaviour)
//   Cmd_<n>     replaces point_servercommand (chat messages / cvars)
//   Speed_<mult> replaces player_speedmod ModifySpeed (activator only, 1 = back to normal)
//   Gravity_<scale> replaces trigger_gravity (activator only, 1 = back to normal; the trigger fires Gravity_1 on leaving)
//   (automatic) replaces game_player_equips without "Use Only" (CS:GO ran them on every spawn, CS2 does not)
//   Color_<r>_<g>_<b> replaces !activator Color (player tint)

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
        "speed": 400.0,
        "mins": [
            5424.0,
            -4736.0,
            384.0
        ],
        "maxs": [
            5536.0,
            -4704.0,
            1088.0
        ]
    },
    "2": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 400.0,
        "mins": [
            4112.0,
            -4736.0,
            384.0
        ],
        "maxs": [
            4224.0,
            -4704.0,
            1088.0
        ]
    },
    "3": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 2000.0,
        "mins": [
            -400.0,
            2768.0,
            -1992.0
        ],
        "maxs": [
            -304.0,
            2864.0,
            -1856.0
        ]
    },
    "4": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 2000.0,
        "mins": [
            -208.0,
            2512.0,
            -1992.0
        ],
        "maxs": [
            -112.0,
            2608.0,
            -1856.0
        ]
    },
    "5": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 2000.0,
        "mins": [
            -400.0,
            2256.0,
            -1992.0
        ],
        "maxs": [
            -304.0,
            2352.0,
            -1856.0
        ]
    },
    "6": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 2000.0,
        "mins": [
            -208.0,
            2000.0,
            -1992.0
        ],
        "maxs": [
            -112.0,
            2096.0,
            -1856.0
        ]
    },
    "7": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1000.0,
        "mins": [
            4112.0,
            -4704.0,
            384.0
        ],
        "maxs": [
            4224.0,
            -4512.0,
            1088.0
        ]
    },
    "8": {
        "dir": [
            0.0,
            0.0,
            1.0
        ],
        "speed": 1000.0,
        "mins": [
            5424.0,
            -4704.0,
            384.0
        ],
        "maxs": [
            5536.0,
            -4512.0,
            1088.0
        ]
    },
    "9": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 400.0,
        "mins": [
            4112.0,
            -4512.0,
            384.0
        ],
        "maxs": [
            4224.0,
            -4480.0,
            1088.0
        ]
    },
    "10": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 400.0,
        "mins": [
            5424.0,
            -4512.0,
            384.0
        ],
        "maxs": [
            5536.0,
            -4480.0,
            1088.0
        ]
    },
    "11": {
        "dir": [
            0.0,
            1.0,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -1792.0,
            1568.0,
            -224.0
        ],
        "maxs": [
            -1568.0,
            5088.0,
            -216.0
        ]
    },
    "12": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -3552.0,
            1568.0,
            -224.0
        ],
        "maxs": [
            -3328.0,
            5088.0,
            -216.0
        ]
    },
    "13": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -3552.0,
            1568.0,
            -224.0
        ],
        "maxs": [
            -1568.0,
            1792.0,
            -216.0
        ]
    },
    "14": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -3552.0,
            4864.0,
            -224.0
        ],
        "maxs": [
            -1568.0,
            5088.0,
            -216.0
        ]
    },
    "15": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 600.0,
        "mins": [
            -480.0,
            1536.0,
            -1984.0
        ],
        "maxs": [
            -32.0,
            1568.0,
            -1504.0
        ]
    },
    "16": {
        "dir": [
            -1.0,
            0.0,
            0.0
        ],
        "speed": 600.0,
        "mins": [
            512.0,
            3936.0,
            3872.0
        ],
        "maxs": [
            8768.0,
            5856.0,
            4224.0
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
    "bot_quota 0",
    "mp_freezetime 0",
    "sv_airaccelerate 150",
    "sv_gravity 800",
    "mp_autokick 0",
    "say **YOU'VE CHOSEN ICESKATE**",
    "say **Map made by xGrandx**",
    "sv_gravity 800",
    "say **YOU'VE CHOSEN SHOTGUNS**",
    "say **Idea: MoneyB**",
    "say **YOU'VE CHOSEN BREAKWALL**",
    "say **YOU'VE CHOSEN KNIFE**",
    "say **Everyone gets an awp in 15 seconds!**",
    "say **YOU'VE CHOSEN SQUASH**",
    "say **3**",
    "say **2**",
    "say **1**",
    "say **START**",
    "say **YOU'VE CHOSEN GRENADES**",
    "say You will get a grenade every 5 seconds!",
    "say **3**",
    "say **2**",
    "say **1**",
    "say **0**",
    "say **YOU'VE CHOSEN SLIDE RACE**",
    "say **YOU'VE CHOSEN CLIMB**",
    "say ***SONG: My Horse Is Amazing***",
    "say ***SONG: Nyan Cat***",
    "say ***SONG: Tetris Remix***",
    "say ***SONG: Zelda Remix 1***",
    "say ***SONG: Zelda Remix 2***",
    "say ***SONG: Zelda Remix 3***",
    "say **YOU'VE CHOSEN AWP**",
    "say **YOU'VE CHOSEN BHOP**",
    "say **YOU'VE CHOSEN HEADSHOT**",
    "say **YOU'VE CHOSEN RACE**",
    "say **3**",
    "say **2**",
    "say **1**",
    "say **START**",
    "say **KNIFE has been chosen!**",
    "say **SHOTGUNS has been chosen!**",
    "say **ICESKATE has been chosen!**",
    "say **BREAKWALL has been chosen!**",
    "say **AWP has been chosen!**",
    "say **BHOP has been chosen!**",
    "say **HEADSHOT has been chosen!**",
    "say **RACE has been chosen!**",
    "say **SQUASH has been chosen!**",
    "say **GRENADES has been chosen!**",
    "say **SLIDE RACE has been chosen!**",
    "say **CLIMB has been chosen!**",
    "say **Idea: MoneyB**",
    "say **START**",
    "say **1**",
    "say **2**",
    "say **3**",
    "say **START**",
    "say **1**",
    "say **2**",
    "say **3**",
    "say You will get a grenade every 5 seconds!",
    "say **YOU'VE CHOSEN RANDOM**",
    "say **Map is now loading...**"
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
for (const s of [1.0, 2.0, 3.0]) {
    Instance.OnScriptInput("Speed_" + s, ({ activator }) => {
        const pawn = speedPawn(activator);
        const ctrl = pawn ? pawn.GetPlayerController() : undefined;
        if (!ctrl) return;
        if (s === 1) speedBySlot.delete(ctrl.GetPlayerSlot()); else speedBySlot.set(ctrl.GetPlayerSlot(), s);
        wakeThink();
    });
}

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
for (const g of [0.3, 1.0]) {
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

// ---------------------------------------------------------------- spawn equips (game_player_equip without "Use Only")
// CS:GO ran these on every spawn ("Strip First" = start with nothing but their items). CS2 doesn't, so each (re)spawning
// player is handled one tick after OnPlayerReset (after CS2 has handed out its default loadout).
/** @type {{ strip: boolean, items: string[] }[]} */
const SPAWN_EQUIPS = [{"strip": false, "items": ["item_kevlar"]}];
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

// ---------------------------------------------------------------- !activator Color replacement (output dropped by the importer)
for (const c of ["0_0_255", "0_255_0", "255_0_0"]) {
    const [r, g, b] = c.split('_').map(Number);
    Instance.OnScriptInput("Color_" + c, ({ activator }) => {
        const pawn = activator instanceof CSPlayerPawn ? activator : activator instanceof CSPlayerController ? activator.GetPlayerPawn() : undefined;
        if (pawn && pawn.IsValid()) pawn.SetColor({ r, g, b, a: 255 });
    });
}
