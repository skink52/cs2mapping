import { Instance, Entities, Console, GameRules, CSPlayerPawn, CSPlayerController, CSInputs, CSGearSlot, CSDamageFlags, CSRoundEndReason } from "cs_script/point_script";

// mg_nature_multigames: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_nature_multigames_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   PushIn_<n> / PushOut_<n>   replaces the trigger_push brushes (CS:GO "set speed" behaviour)
//   Cmd_<n>     replaces point_servercommand (chat messages / cvars)
//   Speed_<mult> replaces player_speedmod ModifySpeed (activator only, 1 = back to normal)
//   (automatic) replaces game_player_equips without "Use Only" (CS:GO ran them on every spawn, CS2 does not)
//   RoundEnd_<n>_<Draw|T|CT> replaces game_round_end EndRound_* (FireWinCondition, then a forced end)
//   WeaponStrip replaces player_weaponstrip Strip / StripWeaponsAndSuit (activator only)

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
        "speed": 700.0,
        "mins": [
            -10688.0,
            9920.0,
            3888.0
        ],
        "maxs": [
            -10256.0,
            12431.80078125,
            3964.98046875
        ]
    },
    "2": {
        "dir": [
            1.0,
            0.0,
            0.0
        ],
        "speed": 999.0,
        "mins": [
            -9963.1513671875,
            2560.22998046875,
            3964.24072265625
        ],
        "maxs": [
            -9524.8515625,
            2811.77001953125,
            4095.76123046875
        ]
    },
    "3": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 600.0,
        "mins": [
            -9091.0,
            -4933.0,
            1831.0
        ],
        "maxs": [
            -7374.0,
            -3255.0,
            2012.0
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
    "sm_say ***Will you survive?.... Test your luck.",
    "sm_say ***Teleporting Everyone In 15 Seconds***",
    "sm_say ***Teleporting Everyone In 15 Seconds***",
    "sm_say [Picking Random Level]",
    "sm_say ***Waiting 5 Seconds To Prevent Levels From Breaking***",
    "sm_say [Soccer]",
    "sm_say [Waterski]",
    "sm_say [Deathrun]",
    "sm_cvar mp_teammates_are_enemies 1",
    "sm_say ***Everyone is Your Enemy, Even Your Teammates***",
    "sm_say ***You Have 20 Seconds To Exit The Zoo***",
    "sm_say ***You Have 20 Seconds to Get to the End",
    "sm_say ***Killing AFKs In 5 Seconds***",
    "sm_say [Awp]",
    "sm_say [Battle Slider]",
    "sm_say ***Enabling Knives in 5 Seconds***",
    "sm_say ***Enabling Shotguns in 5 Seconds***",
    "sm_say [Knife]",
    "sm_say [Skipping Rope]",
    "sm_say [Music: Die Young (Edit) by Ke$sha & Becky G]",
    "sm_say [Music: La La La (White Panda X Gazzo Remix)]",
    "sm_say [Music: Always This Late (Illenium Remix) by ODESZA]",
    "sm_say [Music: Pop Culture by Madeon]",
    "sm_say [Music: Idols by Virutal Riot]",
    "sm_say [Music: Cool Kids (Gazzo & Two Friends Remix)]",
    "sm_cvar cs_enable_player_physics_box 1",
    "sm_cvar phys_pushscale 900",
    "sm_say ***Map by Punky***",
    "sm_cvar sv_airaccelerate 250",
    "sm_say ***Adjust the Music Volume in Your CS:GO Settings***",
    "sm_cvar mp_teammates_are_enemies 0",
    "sm_say ***CT's Have Scored***",
    "sm_say ***GOAL!!!!***",
    "sm_say ***T's Have Scored***",
    "sm_say ***GOAL!!!!***",
    "sm_say ***Enabling Rope Killer In 5 Seconds***"
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
for (const s of [1.5, 3.0]) {
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

// ---------------------------------------------------------------- game_round_end replacement (not in CS2)
// FireWinCondition on the map's info_map_parameters ends the round with a winner. If the round hasn't ended 1.5 s later
// (mp_ignore_round_win_conditions 1, warmup), kill the losing team, then make the winners the team that wins when the
// clock runs out, and run it out (mg_mario_party's method).
const ROUNDEND_PARAMS = "port_map_params";
/** @type {Record<string, { mode: string, after: { t: string, i: string, p: string, d: number }[] }>} */
const ROUNDEND = {
    "0_CT": {
        "mode": "CT",
        "after": []
    },
    "0_T": {
        "mode": "T",
        "after": []
    }
};
let roundEndOver = false;
let roundEndCvar = false;
/** @param {number} team */
function roundEndKillTeam(team) {
    for (let slot = 0; slot < 64; slot++) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (pawn && pawn.IsValid() && pawn.IsAlive() && pawn.GetTeamNumber() === team)
            pawn.TakeDamage({ damage: 100000, damageFlags: CSDamageFlags.FORCE_DEATH | CSDamageFlags.IGNORE_ARMOR });
    }
}
/** @param {string} key */
async function roundEnd(key) {
    const r = ROUNDEND[key];
    if (!r || roundEndOver) return;
    const reason = r.mode === 'T' ? CSRoundEndReason.TERRORISTS_WIN : r.mode === 'CT' ? CSRoundEndReason.CTS_WIN : CSRoundEndReason.DRAW;
    Entities.FireInput({ name: ROUNDEND_PARAMS, input: "FireWinCondition", value: reason });
    for (const o of r.after) Entities.FireInput({ name: o.t, input: o.i, value: o.p, delay: o.d });
    await Instance.Delay(1.5);
    if (roundEndOver) return;
    if (r.mode !== 'Draw') {
        const winner = r.mode === 'T' ? 2 : 3;
        roundEndKillTeam(winner === 2 ? 3 : 2);
        await Instance.Delay(1.0);
        if (roundEndOver) return;
        Console.ServerCommand(`mp_default_team_winner_no_objective ${winner}`);
        roundEndCvar = true;
    }
    GameRules.SetRoundRemainingTime(0);
}
for (const key of Object.keys(ROUNDEND)) Instance.OnScriptInput("RoundEnd_" + key, () => { roundEnd(key); });
Instance.OnRoundStart(() => { roundEndOver = false; });
Instance.OnRoundEnd(() => {
    roundEndOver = true;
    if (roundEndCvar) { Console.ServerCommand("mp_default_team_winner_no_objective -1"); roundEndCvar = false; }
});
