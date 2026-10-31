import { Instance, CSPlayerPawn, CSPlayerController, CSGrenadeType, CSGearSlot } from "cs_script/point_script";

// ba_jail_keimusho: CS:GO bump mines rebuilt in cs_script (weapon_bumpmine doesn't exist in CS2).
// The floor buttons (bumpminebutton) fire the equip "awp spawner" (strip + weapon_decoy) and bumpscript -> RunScriptInput
// bump_give. That player now holds CHARGES bump mines: each decoy they throw becomes a bump mine where it first lands
// (the decoy is removed, a pooled prop bumpmine_<n> with CS:GO's w_eq_bumpmine_dropped model is put there) and they get
// the next decoy until the charges run out. ARM_DELAY after landing a mine is live: the first player to step on it
// (thrower included, as in CS:GO) is launched away from it and the mine is used up.

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

/** @type {Map<number, number>} player slot -> charges left */
const charges = new Map();
/** @type {Map<any, number>} decoy projectile -> thrower slot */
const flying = new Map();
/** @type {{ ent: any, home: any, live: boolean, armAt: number, dieAt: number, pos: any, name: string }[]} */
let pool = [];
/** @type {{ at: number, slot: number }[]} */
let regive = [];
let thinking = false;

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
        if (ent && ent.IsValid()) pool.push({ ent, home: ent.GetAbsOrigin(), live: false, armAt: 0, dieAt: 0, pos: undefined, name: POOL_PREFIX + i });
    }
}
function retire(mine) {
    mine.live = false;
    if (mine.ent.IsValid()) mine.ent.Teleport({ position: mine.home, velocity: { x: 0, y: 0, z: 0 } });
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
    if (slot === undefined) return;
    charges.set(slot, CHARGES);
    regive.push({ at: Instance.GetGameTime() + 0.1, slot });
    wake();
});

Instance.OnGrenadeThrow(({ weapon, projectile }) => {
    const owner = weapon.GetOwner();
    const slot = owner?.GetPlayerController()?.GetPlayerSlot();
    if (slot === undefined || !charges.get(slot) || projectile.GetGrenadeType() !== CSGrenadeType.DECOY) return;
    const left = charges.get(slot) - 1;
    if (left > 0) { charges.set(slot, left); regive.push({ at: Instance.GetGameTime() + REGIVE_DELAY, slot }); }
    else charges.delete(slot);
    flying.set(projectile, slot);
    wake();
});

Instance.OnGrenadeBounce(({ projectile }) => {
    if (!flying.has(projectile)) return;
    flying.delete(projectile);
    if (!projectile.IsValid()) return;
    const pos = projectile.GetAbsOrigin();
    projectile.Remove();
    if (pool.length === 0) buildPool();
    const now = Instance.GetGameTime();
    let mine = pool.find((p) => !p.live);
    if (!mine) mine = pool.reduce((a, b) => (a.dieAt < b.dieAt ? a : b), pool[0]);   // reuse the oldest
    if (!mine) return;
    mine.live = true; mine.armAt = now + ARM_DELAY; mine.dieAt = now + MINE_LIFE; mine.pos = pos;
    mine.ent.Teleport({ position: pos, angles: { pitch: 0, yaw: Math.random() * 360, roll: 0 }, velocity: { x: 0, y: 0, z: 0 } });
    Instance.EntFireAtName({ name: mine.name + "_land", input: "StartSound", delay: 0.02 });
    wake();
});

Instance.SetThink(() => {
    const now = Instance.GetGameTime();
    regive = regive.filter((r) => { if (now < r.at) return true; giveDecoy(r.slot); return false; });
    for (const p of flying.keys()) if (!p.IsValid()) flying.delete(p);
    const pawns = [];
    for (const c of Instance.GetAllPlayerControllers()) {
        const pw = c.GetPlayerPawn();
        if (pw && pw.IsValid() && pw.IsAlive()) pawns.push(pw);
    }
    for (const mine of pool) {
        if (!mine.live) continue;
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
    if (regive.length || flying.size || pool.some((p) => p.live)) Instance.SetNextThink(now);
    else thinking = false;
});

function reset() {
    charges.clear(); flying.clear(); regive = [];
    buildPool();
    for (const p of pool) retire(p);
}
Instance.OnActivate(reset);
Instance.OnRoundStart(reset);
Instance.OnPlayerReset(({ player }) => {
    const slot = player.GetPlayerController()?.GetPlayerSlot();
    if (slot !== undefined) charges.delete(slot);
});
