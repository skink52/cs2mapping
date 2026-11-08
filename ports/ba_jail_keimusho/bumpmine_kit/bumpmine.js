import { Instance, CSPlayerPawn, CSPlayerController, CSGrenadeType, CSGearSlot, CustomHudLayout, BaseModelEntity } from "cs_script/point_script";

// CS2 bump mines (cs_script). weapon_bumpmine doesn't exist in CS2, so a thrown decoy becomes one.
// From ba_jail_keimusho's bump mine game (cs2mapping repo, by skink52); generic copy for other maps. Setup: AGENT_SETUP.md.
//
// RunScriptInput inputs on this point_script (targetname bumpscript):
//   bump_on    start the game (mines only work while it's on, unless ALWAYS_ON)
//   bump_off   stop it: charges cleared, HUD hidden
//   bump_give  the activator (a player) gets CHARGES bump mines, as decoys
//   bump_debug toggle console prints of every give/throw/landing
// A player with charges throws the decoy; on its first bounce the decoy is removed and one of the pooled props
// bumpmine_1..POOL_SIZE (CS:GO's w_eq_bumpmine_dropped model) is put there. ARM_DELAY later the first player within
// TRIGGER_RADIUS (thrower included, as in CS:GO) is launched away from it and the mine is used up. They get the next decoy
// until the charges run out. In flight the decoy is hidden and a mine prop follows it, spinning.
// Each mine prop has two point_soundevents, <prop>_land and <prop>_det, started by name.
// HUD (custom_hud_layout bumphud): "BUMP MINE READY - MOUSE1 THROW" while the player holds the decoy in ARENA,
// once per player per round for at most HUD_SECONDS; hidden on death, spawn, round start/end, bump_off and when the player
// stops holding the decoy or leaves ARENA.

// ---------------------------------------------------------------- CONFIG (edit for your map)
// ARENA: only players inside this box get, throw and see bump mines (other decoys on the map stay normal decoys).
//   null = the whole map. Set min/max to your arena's corners in Hammer units (with some room above the floor).
const ARENA = null;   // e.g. { min: { x: -2530, y: -4600, z: -420 }, max: { x: -1490, y: -3900, z: 40 } }
// ALWAYS_ON: true = live from round start, no bump_on needed (bump_off still turns it off for the rest of the round).
const ALWAYS_ON = false;
// tuning (these are the values tested in game on ba_jail_keimusho)
const CHARGES = 3;                    // mines per bump_give
const ARM_DELAY = 0.3;
const MINE_LIFE = 60;
const TRIGGER_RADIUS = 36;            // horizontal, units
const TRIGGER_BELOW = 24, TRIGGER_ABOVE = 72;
const LAUNCH_SPEED = 900;             // horizontal, away from the mine
const LAUNCH_UP = 750;
const POOL_PREFIX = "bumpmine_";
const POOL_SIZE = 8;
const REGIVE_DELAY = 0.6;
const HUD_NAME = "bumphud";
const HUD_SECONDS = 5;                // the card shows at most this long, once per player per round
const MAX_SLOTS = 64;
const LAND_FALLBACK = 3.0;            // no bounce event this long after the throw: place the mine where the decoy is
let debug = false;
function dbg(t) { if (debug) Instance.Msg("[bumpmine] " + t); }

/** @type {Map<number, number>} player slot -> charges left */
const charges = new Map();
/** @type {Map<any, any>} decoy projectile -> the pooled mine flying with it */
const flying = new Map();
/** @type {{ ent: any, home: any, live: boolean, flying: boolean, thrownAt?: number, armAt: number, dieAt: number, pos: any, name: string }[]} */
let pool = [];
/** @type {{ at: number, slot: number }[]} */
let regive = [];
let thinking = false;
let gameOn = false;
/** @type {Map<number, string>} slot -> last HUD state sent ("" = hidden, "on" = shown); no entry = unknown, always send */
const hudSent = new Map();
/** @type {Map<number, number>} slot -> game time the card must be gone by (shown this round); no entry = not shown yet this round */
const hudShownUntil = new Map();
/** @type {number[]} game times at which every slot's card is hidden again (after a round start the new round's HUD entity may not exist yet) */
let hudWipes = [];

function inArena(p) {
    if (!ARENA) return true;
    return p.x >= ARENA.min.x && p.x <= ARENA.max.x && p.y >= ARENA.min.y && p.y <= ARENA.max.y && p.z >= ARENA.min.z && p.z <= ARENA.max.z;
}
function hud() { const e = Instance.FindEntityByName(HUD_NAME); return e instanceof CustomHudLayout ? e : undefined; }
function setHud(slot, text) {
    if (hudSent.get(slot) === text) return;
    const h = hud(); if (!h) return;
    h.SetHasClassForPlayer(slot, "BumpReady", "stOn", !!text);
    hudSent.set(slot, text);
}

// hide the card for one slot / every slot, whatever the cache says
function hideHud(slot) { hudSent.delete(slot); setHud(slot, ""); }
function wipeHud() {
    const h = hud();
    if (h) { h.Reset(); for (let s = 0; s < MAX_SLOTS; s++) h.SetHasClassForPlayer(s, "BumpReady", "stOn", false); }
    hudSent.clear();
    for (let s = 0; s < MAX_SLOTS; s++) hudSent.set(s, "");
}
function hudWanted(slot, pw, now) {
    if (!gameOn || !pw || !pw.IsValid() || !pw.IsAlive() || !charges.get(slot) || !inArena(pw.GetAbsOrigin())) return "";
    const w = pw.GetActiveWeapon();
    if (!w || !w.IsValid() || w.GetClassName() !== "weapon_decoy") return "";
    const until = hudShownUntil.get(slot);
    if (until === undefined) { hudShownUntil.set(slot, now + HUD_SECONDS); return "on"; }
    return now < until ? "on" : "";
}

function toPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
function wake() { if (!thinking) { thinking = true; Instance.SetNextThink(Instance.GetGameTime()); } }

function buildPool() {
    pool = [];
    for (let i = 1; i <= POOL_SIZE; i++) {
        const ent = Instance.FindEntityByName(POOL_PREFIX + i);
        if (ent && ent.IsValid() && ent instanceof BaseModelEntity) { ent.SetColor({ r: 255, g: 255, b: 255, a: 0 }); pool.push({ ent, home: ent.GetAbsOrigin(), live: false, flying: false, armAt: 0, dieAt: 0, pos: undefined, name: POOL_PREFIX + i }); }
    }
}
function retire(mine) {
    mine.live = false; mine.flying = false;
    if (mine.ent.IsValid()) { mine.ent.Teleport({ position: mine.home, velocity: { x: 0, y: 0, z: 0 } }); mine.ent.SetColor({ r: 255, g: 255, b: 255, a: 0 }); }
}
function giveDecoy(slot) {
    const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
    if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) return;
    const w = pawn.FindWeaponBySlot(CSGearSlot.GRENADES);
    if (!w || w.GetClassName() !== "weapon_decoy") pawn.GiveNamedItem("weapon_decoy", false);
}

Instance.OnScriptInput("bump_give", ({ activator }) => {
    const pawn = toPawn(activator);
    const slot = pawn?.GetPlayerController()?.GetPlayerSlot();
    dbg(`give: slot=${slot} gameOn=${gameOn} inArena=${pawn ? inArena(pawn.GetAbsOrigin()) : "-"}`);
    if (slot === undefined || !gameOn || !inArena(pawn.GetAbsOrigin())) return;
    charges.set(slot, CHARGES);
    regive.push({ at: Instance.GetGameTime() + 0.1, slot });
    wake();
});

Instance.OnGrenadeThrow(({ weapon, projectile }) => {
    // the thrower comes from the projectile: with one decoy in hand the weapon is already gone (no owner) when this fires
    let owner = projectile && projectile.IsValid() ? projectile.GetThrower() : undefined;
    if (!owner || !owner.IsValid()) owner = weapon && weapon.IsValid() ? weapon.GetOwner() : undefined;
    const slot = owner?.GetPlayerController()?.GetPlayerSlot();
    const isDecoy = projectile && projectile.IsValid() && projectile.GetGrenadeType() === CSGrenadeType.DECOY;
    dbg(`throw: slot=${slot} decoy=${isDecoy} gameOn=${gameOn} charges=${slot === undefined ? "-" : charges.get(slot)} inArena=${owner ? inArena(owner.GetAbsOrigin()) : "-"}`);
    if (slot === undefined || !gameOn || !charges.get(slot) || !isDecoy) return;
    if (!inArena(owner.GetAbsOrigin())) return;
    const left = charges.get(slot) - 1;
    if (left > 0) { charges.set(slot, left); regive.push({ at: Instance.GetGameTime() + REGIVE_DELAY, slot }); }
    else charges.delete(slot);
    const mine = takeMine();
    if (!mine) return;
    mine.live = false; mine.flying = true; mine.thrownAt = Instance.GetGameTime();
    projectile.SetColor({ r: 255, g: 255, b: 255, a: 0 });
    flying.set(projectile, mine);
    wake();
});

// Map entities are re-created every round, so pool entries from an earlier round go stale (the mines then never appeared after the
// first round). Re-find the pool whenever it's empty or any entry is no longer valid.
function poolOk() { return pool.length > 0 && pool.every((p) => p.ent && p.ent.IsValid()); }
function takeMine() {
    if (!poolOk()) buildPool();
    if (pool.length === 0) {
        const named = Instance.FindEntitiesByClass("prop_dynamic").map((e) => e.GetEntityName()).filter((n) => n && n.toLowerCase().includes("bump"));
        Instance.Msg("[bumpmine] no bumpmine_1..8 props found - mine not placed (prop_dynamics named *bump*: " + (named.join(", ") || "none") + ")");
        return undefined;
    }
    let mine = pool.find((p) => !p.live && !p.flying);
    if (!mine) mine = pool.filter((p) => !p.flying).reduce((a, b) => (!a || b.dieAt < a.dieAt ? b : a), undefined);
    if (mine) { mine.flying = true; mine.ent.SetColor({ r: 255, g: 255, b: 255, a: 255 }); }
    return mine;
}

function land(projectile, mine) {
    flying.delete(projectile);
    const pos = projectile.IsValid() ? projectile.GetAbsOrigin() : mine.ent.GetAbsOrigin();
    if (projectile.IsValid()) projectile.Remove();
    const now = Instance.GetGameTime();
    mine.flying = false; mine.live = true; mine.armAt = now + ARM_DELAY; mine.dieAt = now + MINE_LIFE; mine.pos = pos;
    mine.ent.Teleport({ position: pos, angles: { pitch: 0, yaw: Math.random() * 360, roll: 0 }, velocity: { x: 0, y: 0, z: 0 } });
    Instance.EntFireAtName({ name: mine.name + "_land", input: "StartSound", delay: 0.02 });
    dbg(`landed ${mine.name} at ${pos.x.toFixed(0)} ${pos.y.toFixed(0)} ${pos.z.toFixed(0)}`);
    wake();
}
Instance.OnGrenadeBounce(({ projectile }) => {
    const mine = flying.get(projectile);
    if (mine) land(projectile, mine);
});

Instance.SetThink(() => {
    const now = Instance.GetGameTime();
    regive = regive.filter((r) => { if (now < r.at) return true; giveDecoy(r.slot); return false; });
    hudWipes = hudWipes.filter((t) => { if (now < t) return true; wipeHud(); return false; });
    for (const [p, mine] of flying) {
        if (!p.IsValid()) { flying.delete(p); retire(mine); continue; }
        const v = p.GetAbsVelocity();
        if (now - mine.thrownAt > LAND_FALLBACK || (now - mine.thrownAt > 0.3 && Math.hypot(v.x, v.y, v.z) < 20)) { land(p, mine); continue; }
        const o = p.GetAbsOrigin(), spin = (now * 720) % 360;
        mine.ent.Move({ position: o, angles: { pitch: 0, yaw: spin, roll: 0 } });
    }
    const pawns = [];
    for (const c of Instance.GetAllPlayerControllers()) {
        const pw = c.GetPlayerPawn();
        if (pw && pw.IsValid() && pw.IsAlive()) pawns.push(pw);
        const slot = c.GetPlayerSlot();
        setHud(slot, hudWanted(slot, pw, now));
    }
    for (const mine of pool) {
        if (!mine.live) continue;
        if (!mine.ent || !mine.ent.IsValid()) { mine.live = false; continue; }
        if (now > mine.dieAt || !mine.ent.IsValid()) { retire(mine); continue; }
        if (now < mine.armAt) continue;
        for (const pw of pawns) {
            const o = pw.GetAbsOrigin();
            const dx = o.x - mine.pos.x, dy = o.y - mine.pos.y, dz = o.z - mine.pos.z;
            if (dx * dx + dy * dy > TRIGGER_RADIUS * TRIGGER_RADIUS || dz < -TRIGGER_BELOW || dz > TRIGGER_ABOVE) continue;
            let len = Math.hypot(dx, dy), ux, uy;
            if (len < 4) { const yaw = pw.GetEyeAngles().yaw * Math.PI / 180; ux = Math.cos(yaw); uy = Math.sin(yaw); }
            else { ux = dx / len; uy = dy / len; }
            pw.Teleport({ velocity: { x: ux * LAUNCH_SPEED, y: uy * LAUNCH_SPEED, z: LAUNCH_UP } });
            Instance.EntFireAtName({ name: mine.name + "_det", input: "StartSound" });
            retire(mine);
            break;
        }
    }
    const hudOn = [...hudSent.values()].some((t) => t !== "");
    if (gameOn || regive.length || hudWipes.length || hudOn || flying.size || pool.some((p) => p.live)) Instance.SetNextThink(now);
    else thinking = false;
});

Instance.OnScriptInput("bump_on", () => { gameOn = true; dbg("game on"); wake(); });
// debug: "ent_fire bumpscript RunScriptInput bump_debug" (or the bump_debug console command with sv_cheats 1) prints every give/throw/landing
Instance.OnScriptInput("bump_debug", () => { debug = !debug; Instance.Msg("[bumpmine] debug " + (debug ? "on" : "off")); });
Instance.RegisterCheatCommand("bump_debug", () => { debug = !debug; Instance.Msg("[bumpmine] debug " + (debug ? "on" : "off")); });
Instance.RegisterCheatCommand("bump_on", () => { gameOn = true; Instance.Msg("[bumpmine] game on"); wake(); });
Instance.OnScriptInput("bump_off", () => { gameOn = false; charges.clear(); wipeHud(); });

function reset() {
    gameOn = ALWAYS_ON;
    charges.clear(); flying.clear(); regive = [];
    hudShownUntil.clear();
    wipeHud();
    // again once the new round's entities exist (the HUD entity is re-created each round too)
    const now = Instance.GetGameTime();
    hudWipes = [now + 0.5, now + 2];
    pool = [];                      // re-found on first use: at round start the new round's props may not exist yet
    wake();
}
Instance.OnActivate(reset);
Instance.OnRoundStart(reset);
Instance.OnRoundEnd(() => { wipeHud(); });
Instance.OnPlayerReset(({ player }) => {
    const slot = player.GetPlayerController()?.GetPlayerSlot();
    if (slot !== undefined) { charges.delete(slot); hideHud(slot); }
});
Instance.OnPlayerKill(({ player }) => {
    const slot = player?.GetPlayerController()?.GetPlayerSlot();
    if (slot !== undefined) { charges.delete(slot); hideHud(slot); }
});
Instance.OnPlayerActivate(({ player }) => {
    const slot = player?.GetPlayerSlot();
    if (slot === undefined) return;
    const h = hud(); if (h) h.ResetForPlayer(slot);
    hideHud(slot);
});
Instance.OnPlayerDisconnect(({ playerSlot }) => { charges.delete(playerSlot); hudShownUntil.delete(playerSlot); hideHud(playerSlot); });
