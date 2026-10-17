import { Instance, Entity, CSPlayerPawn, CSPlayerController } from "cs_script/point_script";

// CS2 port of mvp_health_increase.nut (logic_script "mvp_health_change").
// Triggered by: mvp_assign_powers_predator -> mvp_health_change -> RunScriptInput -> IncreaseHealth
//
// Original VScript:
//   activator.SetMaxHealth(600);
//   activator.SetHealth(600);

const PREDATOR_HEALTH = 600;

/**
 * Triggers pass the player pawn as the activator; accept a controller too, just in case.
 * @param {Entity | undefined} ent
 * @returns {CSPlayerPawn | undefined}
 */
function toPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}

Instance.OnScriptInput("IncreaseHealth", ({ activator }) => {
    const pawn = toPawn(activator);
    if (pawn && pawn.IsValid()) {
        pawn.SetMaxHealth(PREDATOR_HEALTH);
        pawn.SetHealth(PREDATOR_HEALTH);
    }
});
