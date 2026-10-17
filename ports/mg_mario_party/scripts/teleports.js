import { Instance, Entity, CSPlayerPawn, CSPlayerController } from "cs_script/point_script";

// CS2 replacement for trigger_teleport's SetRemoteDestination input.
// CS2 removed that input (it isn't in the FGD or the game), so Hammer flags it as an error
// and it would do nothing in-game. This script does the same job:
//
//   logic_timer -> logic_case PickRandomShuffle -> OnCaseNN -> mvp_teleport_script RunScriptInput <destination name>
//       remembers which info_teleport_destination is current for that teleporter (what SetRemoteDestination used to do)
//
//   teleport trigger OnStartTouch -> mvp_teleport_script RunScriptInput teleport_<trigger name>
//       sends the touching player to that teleporter's current destination

/** Each teleporter and the info_teleport_destinations its logic_case picks between. */
const TELEPORTERS = [
    { trigger: "mvp_predator_teleporer_t", destPrefix: "mvp_predator_dest_", count: 10 },         // mvp_predator_tele_case
    { trigger: "mvp_gun_room_tele",        destPrefix: "mvp_gun_room_to_game_dest_", count: 16 }, // mvp_marine_tele_case
    { trigger: "mvp_predator_teles",       destPrefix: "mvp_pipe_dest_", count: 11 },             // mvp_pipe_tele_case
];

/** @type {Record<string, string>} teleporter name -> current destination name */
const current = {};

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

for (const tp of TELEPORTERS) {
    // The timers re-pick every 0.05s, so this default only matters for the first instant of a round.
    current[tp.trigger] = tp.destPrefix + "1";

    for (let i = 1; i <= tp.count; i++) {
        const destName = tp.destPrefix + i;
        Instance.OnScriptInput(destName, () => {
            current[tp.trigger] = destName;
        });
    }

    Instance.OnScriptInput("teleport_" + tp.trigger, ({ activator }) => {
        const pawn = toPawn(activator);
        if (!pawn || !pawn.IsValid()) return;
        const dest = Instance.FindEntityByName(current[tp.trigger]);
        if (!dest || !dest.IsValid()) return;

        // Same as trigger_teleport: move to the destination, face its direction, stop all movement.
        const angles = dest.GetAbsAngles();
        pawn.Teleport({
            position: dest.GetAbsOrigin(),
            angles: { pitch: 0, yaw: angles.yaw, roll: 0 },
            velocity: { x: 0, y: 0, z: 0 },
        });
        pawn.SetEyeAngles(angles);
    });
}
