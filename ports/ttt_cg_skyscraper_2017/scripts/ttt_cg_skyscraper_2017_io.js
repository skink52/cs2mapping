import { Instance, CSPlayerPawn, CSPlayerController } from "cs_script/point_script";

// ttt_cg_skyscraper_2017: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `ttt_cg_skyscraper_2017_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   Cmd_<n>     replaces point_servercommand (chat messages / cvars)

// ---------------------------------------------------------------- point_servercommand replacement
// CS2 servers block most point_servercommand commands, so the map's chat messages / cvars are sent from script instead.
/** @type {string[]} */
const COMMANDS = [
    "sv_disable_immunity_alpha 1"
];
COMMANDS.forEach((cmd, i) => {
    Instance.OnScriptInput("Cmd_" + i, () => { Instance.ServerCommand(cmd); });
});
