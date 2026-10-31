import { Instance, CSPlayerPawn, CSPlayerController, CSInputs, CSMoveType, CSGearSlot } from "cs_script/point_script";

// ba_jail_keimusho: samurai mask power-up (CS:GO trigger_once next to the knife named "knife").
// In CS:GO the T who touched it got player_speedmod x3, gravity 0.5, alpha 0 (invisible), 200 HP and the samurai mask.
// None of those AddOutputs / player_speedmod work in CS2, so the trigger fires samuraiscript -> RunScriptInput samurai_on
// and this script applies them. Everything resets on death, respawn and round start.

const SPEED_MULT = 3;
const GRAVITY_SCALE = 0.5;
const HEALTH = 200;
const MASK_NAME = "mask2";
const FLOOR_KNIFE = "knife";

const SV_GRAVITY = 800;
const BASE_SPEED = 250;
const WEAPON_SPEED = {
    weapon_glock: 240, weapon_hkp2000: 240, weapon_usp_silencer: 240, weapon_p250: 240, weapon_elite: 240, weapon_fiveseven: 240,
    weapon_tec9: 240, weapon_cz75a: 240, weapon_deagle: 230, weapon_revolver: 220, weapon_taser: 220,
    weapon_mac10: 240, weapon_mp9: 240, weapon_bizon: 240, weapon_mp5sd: 235, weapon_ump45: 230, weapon_p90: 230, weapon_mp7: 220,
    weapon_ak47: 215, weapon_galilar: 215, weapon_m4a1: 225, weapon_m4a1_silencer: 225, weapon_famas: 220, weapon_aug: 220, weapon_sg556: 210,
    weapon_awp: 200, weapon_ssg08: 230, weapon_g3sg1: 215, weapon_scar20: 215,
    weapon_nova: 220, weapon_xm1014: 215, weapon_mag7: 225, weapon_sawedoff: 210, weapon_m249: 195, weapon_negev: 150,
    weapon_hegrenade: 245, weapon_flashbang: 245, weapon_smokegrenade: 245, weapon_molotov: 245, weapon_incgrenade: 245, weapon_decoy: 245,
};
const FRICTION_COMP = 1 / (1 - 5.2 / 64);
const WALK_FACTOR = 0.52, DUCK_FACTOR = 0.34;

/** @type {Map<number, boolean>} player slots with the power-up */
const powered = new Map();
/** @type {import("cs_script/point_script").Entity | undefined} */
let mask;
let maskSlot = -1;
let thinking = false;
let lastThink = 0;

function toPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
function weaponSpeed(pawn) {
    const w = pawn.GetActiveWeapon();
    if (!w || !w.IsValid()) return BASE_SPEED;
    return WEAPON_SPEED[w.GetClassName()] ?? BASE_SPEED;
}
function wake() {
    if (thinking) return;
    thinking = true; lastThink = Instance.GetGameTime();
    Instance.SetNextThink(lastThink);
}

function release(slot) {
    if (!powered.has(slot)) return;
    powered.delete(slot);
    const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
    if (pawn && pawn.IsValid()) pawn.SetColor({ r: 255, g: 255, b: 255, a: 255 });
    if (slot === maskSlot) { maskSlot = -1; mask = undefined; }
}

function grabMask(slot) {
    const m = Instance.FindEntityByName(MASK_NAME);
    if (!m || !m.IsValid()) return;
    mask = m; maskSlot = slot;
    m.SetParent(undefined);
    Instance.EntFireAtTarget({ target: m, input: "DisableCollision" });
}

Instance.OnScriptInput("samurai_on", ({ activator }) => {
    const pawn = toPawn(activator);
    const ctrl = pawn?.GetPlayerController();
    if (!pawn || !ctrl || !pawn.IsAlive()) return;
    const slot = ctrl.GetPlayerSlot();
    powered.set(slot, true);
    pawn.SetHealth(HEALTH);
    // the map strips the player at the same moment and the floor knife is picked up by walking over it;
    // the map strips the player at the same moment and the floor knife is picked up by walking over it, so the
    // invisibility, knife check and mask follow run a moment later
    Instance.EntFireAtName({ name: "samuraiscript", input: "RunScriptInput", value: "samurai_check", activator: pawn, delay: 0.3 });
    wake();
});

Instance.OnScriptInput("samurai_check", ({ activator }) => {
    const pawn = toPawn(activator);
    const ctrl = pawn?.GetPlayerController();
    if (!pawn || !ctrl || !pawn.IsAlive() || !powered.has(ctrl.GetPlayerSlot())) return;
    pawn.SetColor({ r: 255, g: 255, b: 255, a: 0 });
    if (!pawn.FindWeaponBySlot(CSGearSlot.KNIFE)) {
        pawn.GiveNamedItem("weapon_knife", true);
        const k = Instance.FindEntityByName(FLOOR_KNIFE);
        if (k && k.IsValid() && !k.GetOwner()) k.Remove();
    }
    grabMask(ctrl.GetPlayerSlot());
});

Instance.SetThink(() => {
    const now = Instance.GetGameTime();
    const dt = Math.min(Math.max(now - lastThink, 0), 0.1);
    lastThink = now;
    for (const slot of [...powered.keys()]) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { release(slot); continue; }
        let { x, y, z } = pawn.GetAbsVelocity();
        let changed = false;
        const onGround = !!pawn.GetGroundEntity();
        if (!onGround && pawn.GetMoveType() === CSMoveType.WALK) { z += (1 - GRAVITY_SCALE) * SV_GRAVITY * dt; changed = true; }
        if (onGround) {
            const fwd = (pawn.IsInputPressed(CSInputs.FORWARD) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.BACK) ? 1 : 0);
            const side = (pawn.IsInputPressed(CSInputs.RIGHT) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.LEFT) ? 1 : 0);
            if (fwd !== 0 || side !== 0) {
                const yaw = pawn.GetEyeAngles().yaw * Math.PI / 180;
                let dx = Math.cos(yaw) * fwd + Math.sin(yaw) * side;
                let dy = Math.sin(yaw) * fwd - Math.cos(yaw) * side;
                const len = Math.hypot(dx, dy); dx /= len; dy /= len;
                let speed = weaponSpeed(pawn) * SPEED_MULT * FRICTION_COMP;
                if (pawn.IsInputPressed(CSInputs.WALK)) speed *= WALK_FACTOR;
                if (pawn.IsDucking()) speed *= DUCK_FACTOR;
                x = dx * speed; y = dy * speed; changed = true;
            }
        }
        if (changed) pawn.Move({ velocity: { x, y, z } });
        if (slot === maskSlot && mask && mask.IsValid()) {
            const eye = pawn.GetEyePosition();
            const yaw = pawn.GetEyeAngles().yaw;
            mask.Move({ position: { x: eye.x, y: eye.y, z: eye.z - 2 }, angles: { pitch: 0, yaw: yaw + 180, roll: 0 } });
        }
    }
    if (powered.size > 0) Instance.SetNextThink(now); else thinking = false;
});

Instance.OnPlayerReset(({ player }) => {
    const slot = player.GetPlayerController()?.GetPlayerSlot();
    if (slot !== undefined) release(slot);
});
Instance.OnPlayerKill(({ player }) => {
    const slot = player.GetPlayerController()?.GetPlayerSlot();
    if (slot !== undefined) release(slot);
});
Instance.OnRoundStart(() => {
    for (const slot of [...powered.keys()]) release(slot);
    mask = undefined; maskSlot = -1;
});
