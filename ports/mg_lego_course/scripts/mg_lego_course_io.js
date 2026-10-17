import { Instance, CSPlayerPawn, CSPlayerController } from "cs_script/point_script";

// mg_lego_course: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_lego_course_io_script` -> RunScriptInput <input name>, with the touching player as activator.
//
//   Cmd_<n>     replaces the two point_servercommand entities (map credits in chat, sv_airaccelerate 150)
//   Score_<pts> replaces game_score score1 (ApplyScore on the laser finish triggers)

// ---------------------------------------------------------------- point_servercommand replacement
// CS2 servers block most point_servercommand commands, so the map's chat messages / cvars are sent from script instead.
// Outputs that used to fire <servercommand>.Command(...) now fire Cmd_<n> on this script (same delays).
/** @type {string[]} */
const COMMANDS = [
    "say *** Map by The_Prodigy ***",
    "say *** Spawn Protection will be enabled in 40 seconds ***",
    "say *** Spawn Protection Enabled! ***",
    "say *** 10 seconds ***",
    "say *** 5 seconds ***",
    "say *** 3 seconds ***",
    "say *** 2 seconds ***",
    "say *** 4 seconds ***",
    "say *** 1 second ***",
    "say *** Map ported to CS:GO by Hallucinogenic Troll ***",
    "sv_airaccelerate 150",
    "say *** Map by The_Prodigy ***",
    "say *** Ported to CS:GO by Hallucinogenic Troll ***",
    "say *** Ported to CS2 by skink52 ***",
    "say *** Ported to CS2 by skink52 ***"
];
COMMANDS.forEach((cmd, i) => {
    Instance.OnScriptInput("Cmd_" + i, () => { Instance.ServerCommand(cmd); });
});

// ---------------------------------------------------------------- game_score replacement (entity removed in CS2)
// Outputs that fired <game_score>.ApplyScore now fire Score_<points>; the activator's scoreboard score goes up.
for (const pts of [500]) {
    Instance.OnScriptInput("Score_" + pts, ({ activator }) => {
        const pawn = activator instanceof CSPlayerPawn ? activator : undefined;
        const ctrl = pawn ? pawn.GetPlayerController() : (activator instanceof CSPlayerController ? activator : undefined);
        if (ctrl && ctrl.IsValid()) ctrl.AddScore(pts);
    });
}
