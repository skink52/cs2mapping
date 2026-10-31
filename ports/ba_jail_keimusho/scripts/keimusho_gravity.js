import { Instance, CSPlayerPawn, CSPlayerController, CSMoveType } from "cs_script/point_script";

// ba_jail_keimusho: water race gravity. The CS:GO trigger set "!activator AddOutput gravity -1" on start touch and
// "gravity 1" on end touch; CS2 players have no gravity keyvalue, so the trigger now fires gravityscript ->
// RunScriptInput Gravity_-1 / Gravity_1. While airborne (or swimming) a player with a scale g gets (1 - g) x sv_gravity
// added back each second: g = -1 falls upward at normal gravity, so jumping in the water sticks you to the ceiling.

const SCALES = [-1, 1];
const SV_GRAVITY = 800;
/** @type {Map<number, number>} player slot -> gravity scale */
const scaleBySlot = new Map();
let thinking = false;
let lastThink = 0;

function toPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}

for (const g of SCALES) {
    Instance.OnScriptInput("Gravity_" + g, ({ activator }) => {
        const slot = toPawn(activator)?.GetPlayerController()?.GetPlayerSlot();
        if (slot === undefined) return;
        if (g === 1) scaleBySlot.delete(slot); else scaleBySlot.set(slot, g);
        if (!thinking && scaleBySlot.size > 0) { thinking = true; lastThink = Instance.GetGameTime(); Instance.SetNextThink(lastThink); }
    });
}

Instance.SetThink(() => {
    const now = Instance.GetGameTime();
    const dt = Math.min(Math.max(now - lastThink, 0), 0.1);
    lastThink = now;
    for (const [slot, g] of scaleBySlot) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { scaleBySlot.delete(slot); continue; }
        if (pawn.GetGroundEntity() || pawn.GetMoveType() !== CSMoveType.WALK) continue;
        const v = pawn.GetAbsVelocity();
        pawn.Move({ velocity: { x: v.x, y: v.y, z: v.z + (1 - g) * SV_GRAVITY * dt } });
    }
    if (scaleBySlot.size > 0) Instance.SetNextThink(now); else thinking = false;
});

Instance.OnPlayerReset(({ player }) => {
    const slot = player.GetPlayerController()?.GetPlayerSlot();
    if (slot !== undefined) scaleBySlot.delete(slot);
});
Instance.OnRoundStart(() => scaleBySlot.clear());
