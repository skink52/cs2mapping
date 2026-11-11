import { Instance, Console, Entities, GameRules, CSPlayerPawn, CSPlayerController, CSGearSlot, CSDamageFlags, CSRoundEndReason } from "cs_script/point_script";

// mg_minecraft_multigames: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_minecraft_multigames_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   PushIn_<n> / PushOut_<n>   replaces the trigger_push brushes (CS:GO "set speed" behaviour)
//   Cmd_<n>     replaces point_servercommand (chat messages / cvars)
//   Score_<pts> replaces game_score (ApplyScore)
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
            1.0,
            0.0,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -1661.0,
            -5841.0,
            -4615.0
        ],
        "maxs": [
            -1532.0,
            -5721.0,
            -4556.0
        ]
    },
    "2": {
        "dir": [
            0.0175,
            0.9998,
            0.0
        ],
        "speed": 500.0,
        "mins": [
            -1660.0,
            -6344.0,
            -4622.0
        ],
        "maxs": [
            -1564.0,
            -6223.0,
            -4563.0
        ]
    },
    "3": {
        "dir": [
            0.0,
            -1.0,
            0.0
        ],
        "speed": 700.0,
        "mins": [
            5188.0,
            -1378.0,
            1476.0
        ],
        "maxs": [
            5252.0,
            -1250.0,
            1548.0
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
    "say @[Map] Map by Blogger(Dog)",
    "say @[Map] Special thanks to DexKekcuk #13",
    "say @[Map] Secret room Disable",
    "say @[Map] Secret room Enable",
    "say @[Map] Arena fight",
    "say @[Map] Random weapon...",
    "say @[Map] Random game...",
    "say @[Map] Defends",
    "say @[Map] 25000 HP ",
    "say @[Map] People winner",
    "say @[Map] Thank you played on this map",
    "say @[Map] People Winner",
    "say @[Map] Long Jump",
    "say @[Map] Awp",
    "say @[Music] Aero Chord - 4U",
    "say @[Music] minence & Supermans Feinde - Night Goes On (feat. Q'AILA)",
    "say @[Music] Krewella - Alive",
    "say @[Music] Melanie Martinez - Sippy Cup ",
    "say @[Music] Tritonal - Getaway",
    "say @[Music] Vanic X K.Flay - Can't Sleep",
    "say @[Music] Zedd ft. Foxes - Clarity (Vicetone Remix)",
    "say @[Time] 3 minute before the knifes",
    "say @[Time] 2 minute before the knifes",
    "say @[Time] 1 minute before the knifes",
    "say @[Time] 10 seconds before the knifes",
    "say @[Map] Survival",
    "say @[Map] Luke open 10 seconds",
    "mp_startmoney 90000",
    "mp_freezetime 4",
    "sv_airaccelerate 150",
    "mp_roundtime 7",
    "sv_gravity 800",
    "mp_buytime 300",
    "sv_infinite_ammo 0",
    "sv_ignoregrenaderadio 1",
    "sm_cvar phys_pushscale 900",
    "sm_cvar cs_enable_player_physics_box 1",
    "sv_staminalandcost 0",
    "sv_staminajumpcost 0",
    "mp_warmup_end",
    "bot_kick",
    "say @[Map] Boss Battle",
    "say @[Map] 25000HP",
    "@[Map] Random Game...",
    "say @[Map]  AFK TIMER in 30 sec",
    "say @[Map] AFK TIMER activated",
    "say @[Map] RANDOM GAME WILL BE CHOSEN",
    "say @[Map] AFK TIMER in 10 sec",
    "say @[Time] 4 minute 30 seconds before the arrival of the main ghast",
    "say @[Time] 3 minute 30 seconds before the arrival of the main ghast",
    "say @[Time] 2 minute 30 seconds before the arrival of the main ghast",
    "say @[Time] 1 minute 30 seconds before the arrival of the main ghast",
    "say @[Time] People lost",
    "say @[Time] 30 seconds before the arrival of the main ghast",
    "say @[Time] 4 minute 30 seconds before the arrival of the main ghast",
    "say @[Time] 3 minute 30 seconds before the arrival of the main ghast",
    "say @[Time] 2 minute 30 seconds before the arrival of the main ghast",
    "say @[Time] 1 minute 30 seconds before the arrival of the main ghast",
    "say @[Time] People lost",
    "say @[Time] 30 seconds before the arrival of the main ghast",
    "say @[Map] TNT Sirvival",
    "say @[Map] 30 Seconds Before the battle",
    "say @[Map] 20 Seconds Before the battle",
    "say @[Map] 10 Seconds Before the battle",
    "say @[Map] 5 Seconds Before the battle",
    "say @[Map] Battle",
    "say @[Map] Explode 10 seconds",
    "say @[Map] Spawn Fight",
    "say @[Map] Random weapon",
    "say @[Map] Weapon Deagle",
    "say @[Map] Weapon Knife",
    "say @[Map] Weapon M4A1",
    "say @[Map] Weapon Nova",
    "say @[Map] Weapon P90",
    "say @[Map] Weapon Awp",
    "say @[Map] Hunger Games Labyrinth",
    "say @[Map] Sky Knife",
    "say @[Map] Level made by DexKekcuk #13",
    "say @[Creeper] BOOOMMM!!!",
    "say @[Security] Step away from the box, you do not have the right to take the gun ",
    "say @[Security] Stand back or be killed ",
    "say @[Map] Train 1 Break",
    "say @[Map] Train 2 Break",
    "say @[Map] Ghast number two defeated",
    "say @[Map] Ghast number one defeated"
];
COMMANDS.forEach((cmd, i) => {
    Instance.OnScriptInput("Cmd_" + i, () => { Console.ServerCommand(cmd); });
});

// ---------------------------------------------------------------- game_score replacement (entity removed in CS2)
// Outputs that fired <game_score>.ApplyScore now fire Score_<points>; the activator's scoreboard score goes up.
for (const pts of [100, 900]) {
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
const SPAWN_EQUIPS = [{"strip": true, "items": []}, {"strip": true, "items": []}];
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
    "0_Draw": {
        "mode": "Draw",
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

// ---------------------------------------------------------------- player_weaponstrip replacement (not in CS2)
Instance.OnScriptInput("WeaponStrip", ({ activator }) => {
    const pawn = activator instanceof CSPlayerPawn ? activator : activator instanceof CSPlayerController ? activator.GetPlayerPawn() : undefined;
    if (pawn && pawn.IsValid() && pawn.IsAlive()) pawn.DestroyWeapons();
});
