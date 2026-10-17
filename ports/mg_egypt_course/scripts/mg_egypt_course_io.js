import { Instance, CSPlayerPawn, CSPlayerController } from "cs_script/point_script";

// mg_egypt_course: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_egypt_course_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   Score_<pts> replaces game_score (ApplyScore)

// ---------------------------------------------------------------- game_score replacement (entity removed in CS2)
// Outputs that fired <game_score>.ApplyScore now fire Score_<points>; the activator's scoreboard score goes up.
for (const pts of [100]) {
    Instance.OnScriptInput("Score_" + pts, ({ activator }) => {
        const pawn = activator instanceof CSPlayerPawn ? activator : undefined;
        const ctrl = pawn ? pawn.GetPlayerController() : (activator instanceof CSPlayerController ? activator : undefined);
        if (ctrl && ctrl.IsValid()) ctrl.AddScore(pts);
    });
}
