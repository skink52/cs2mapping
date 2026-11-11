import { Instance, Entities, Console, CSPlayerPawn, CSPlayerController, CSGrenadeType, CSGearSlot, CustomHudLayout, BaseModelEntity } from "cs_script/point_script";

// ba_jail_keimusho: CS:GO bump mines rebuilt in cs_script (weapon_bumpmine doesn't exist in CS2).
// The floor buttons (bumpminebutton) fire the equip "awp spawner" (strip + weapon_decoy) and bumpscript -> RunScriptInput
// bump_give. That player now holds CHARGES bump mines: each decoy they throw becomes a bump mine where it first lands
// (the decoy is removed, a pooled prop bumpmine_<n> with CS:GO's w_eq_bumpmine_dropped model is put there) and they get
// the next decoy until the charges run out. ARM_DELAY after landing a mine is live: the first player to step on it
// (thrower included, as in CS:GO) is launched away from it and the mine is used up.
// Only while the game is on (start button -> bump_on, end button -> bump_off) and only inside the arena box (ARENA), so
// spleef's decoys stay decoys. In the hand it stays a decoy; in flight the decoy is hidden and a bump mine prop follows it.
// HUD (custom_hud_layout bumphud): "BUMP MINE READY - MOUSE1 THROW" + charges while the player holds the decoy in the arena,
// once per player per round and for at most HUD_SECONDS; hidden on death, spawn, round start/end, bump_off and when the player
// stops holding the decoy or leaves the arena. It used to stick round to round: the round-start reset cleared the "last sent"
// cache, so the hide that followed looked like no change and was never sent.

const CHARGES = 3;
const ARM_DELAY = 0.3;
const MINE_LIFE = 60;
const TRIGGER_RADIUS = 36;            // horizontal, units
const TRIGGER_BELOW = 24, TRIGGER_ABOVE = 72;
const LAUNCH_SPEED = 900;             // horizontal, away from the mine
const LAUNCH_UP = 750;
const POOL_PREFIX = "bumpmine_";
const POOL_SIZE = 8;
const REGIVE_DELAY = 0.6;
const ARENA = { min: { x: -2530, y: -4600, z: -420 }, max: { x: -1490, y: -3900, z: 40 } };
const HUD_NAME = "bumphud";
const HUD_SECONDS = 5;                // the card shows at most this long, once per player per round
const MAX_SLOTS = 64;
const LAND_FALLBACK = 3.0;            // no bounce event this long after the throw: place the mine where the decoy is
let debug = false;
function dbg(t) { if (debug) Console.Log("[bumpmine] " + t); }

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
/** @type {Map<number, string>} slot -> last HUD state sent ("" = hidden, otherwise the charges text); no entry = unknown, always send */
const hudSent = new Map();
/** @type {Map<number, number>} slot -> game time the card must be gone by (shown this round); no entry = not shown yet this round */
const hudShownUntil = new Map();
/** @type {number[]} game times at which every slot's card is hidden again (after a round start the new round's HUD entity may not exist yet) */
let hudWipes = [];

function inArena(p) {
    return p.x >= ARENA.min.x && p.x <= ARENA.max.x && p.y >= ARENA.min.y && p.y <= ARENA.max.y && p.z >= ARENA.min.z && p.z <= ARENA.max.z;
}
function hud() { const e = Entities.FindByName(HUD_NAME)[0]; return e instanceof CustomHudLayout ? e : undefined; }
function setHud(slot, text) {
    if (hudSent.get(slot) === text) return;
    const h = hud(); if (!h) return;
    if (text) h.SetDialogVariableStringForPlayer(slot, "bumpcharges", text);
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
    if (until === undefined) { hudShownUntil.set(slot, now + HUD_SECONDS); return "x" + charges.get(slot); }
    return now < until ? "x" + charges.get(slot) : "";
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
        const ent = Entities.FindByName(POOL_PREFIX + i)[0];
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
        const named = Entities.FindByClass("prop_dynamic").map((e) => e.GetEntityName()).filter((n) => n && n.toLowerCase().includes("bump"));
        Console.Log("[bumpmine] no bumpmine_1..8 props found - mine not placed (prop_dynamics named *bump*: " + (named.join(", ") || "none") + ")");
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
    Entities.FireInput({ name: mine.name + "_land", input: "StartSound", delay: 0.02 });
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
            Entities.FireInput({ name: mine.name + "_det", input: "StartSound" });
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
Instance.OnScriptInput("bump_debug", () => { debug = !debug; Console.Log("[bumpmine] debug " + (debug ? "on" : "off")); });
Console.RegisterCheatCommand("bump_debug", () => { debug = !debug; Console.Log("[bumpmine] debug " + (debug ? "on" : "off")); });
Console.RegisterCheatCommand("bump_on", () => { gameOn = true; Console.Log("[bumpmine] game on"); wake(); });
Instance.OnScriptInput("bump_off", () => { gameOn = false; charges.clear(); wipeHud(); });

function reset() {
    gameOn = false;
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
