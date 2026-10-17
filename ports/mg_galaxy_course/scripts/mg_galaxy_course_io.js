import { Instance, CSPlayerPawn, CSPlayerController } from "cs_script/point_script";

// mg_galaxy_course: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_galaxy_course_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   Cmd_<n>     replaces point_servercommand (chat messages / cvars)

// ---------------------------------------------------------------- point_servercommand replacement
// CS2 servers block most point_servercommand commands, so the map's chat messages / cvars are sent from script instead.
/** @type {string[]} */
const COMMANDS = [
    "say **SELF DESTRUCT BUTTON HAS BEEN PRESSED!**",
    "say **RUN TO THE ESCAPE POD!**",
    "say **Map made by xGrandx**",
    "say **Spawn room is now closing!**"
];
COMMANDS.forEach((cmd, i) => {
    Instance.OnScriptInput("Cmd_" + i, () => { Instance.ServerCommand(cmd); });
});
