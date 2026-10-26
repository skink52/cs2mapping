import { Instance, CSPlayerPawn, CSPlayerController, CSGearSlot } from "cs_script/point_script";

// mg_n64_goldeneye: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.
// Everything here is driven by `mg_n64_goldeneye_io_script` -> RunScriptInput <input name>, with the activator passed through.
//
//   Cmd_<n>     replaces point_servercommand (chat messages / cvars)
//   (automatic) replaces game_player_equips without "Use Only" (CS:GO ran them on every spawn, CS2 does not)

// ---------------------------------------------------------------- shared think loop
/** @type {(() => boolean)[]} each returns true while it still needs ticks */
const THINKERS = [];
let thinking = false;
function wakeThink() { if (!thinking) { thinking = true; Instance.SetNextThink(Instance.GetGameTime()); } }
Instance.SetThink(() => {
    let active = false;
    for (const t of THINKERS) if (t()) active = true;
    if (active) Instance.SetNextThink(Instance.GetGameTime()); else thinking = false;
});

// ---------------------------------------------------------------- point_servercommand replacement
// CS2 servers block most point_servercommand commands, so the map's chat messages / cvars are sent from script instead.
/** @type {string[]} */
const COMMANDS = [
    "say *** Map Made by [TsM]RoB ***",
    "sv_infinite_ammo 2",
    "sv_autobunnyhopping 0",
    "say *** Press E on a wall to gain a Nade ***"
];
COMMANDS.forEach((cmd, i) => {
    Instance.OnScriptInput("Cmd_" + i, () => { Instance.ServerCommand(cmd); });
});

// ---------------------------------------------------------------- spawn equips (game_player_equip without "Use Only")
// CS:GO ran these on every spawn ("Strip First" = start with nothing but their items). CS2 doesn't, so each (re)spawning
// player is handled one tick after OnPlayerReset (after CS2 has handed out its default loadout).
/** @type {{ strip: boolean, items: string[] }[]} */
const SPAWN_EQUIPS = [{"strip": true, "items": ["weapon_knife"]}];
/** @type {Set<CSPlayerPawn>} */
const spawnQueue = new Set();
Instance.OnPlayerReset(({ player }) => {
    if (player && player.IsValid()) { spawnQueue.add(player); wakeThink(); }
});
THINKERS.push(() => {
    for (const pawn of spawnQueue) {
        spawnQueue.delete(pawn);
        if (!pawn.IsValid() || !pawn.IsAlive()) continue;
        for (const eq of SPAWN_EQUIPS) {
            if (eq.strip) pawn.DestroyWeapons();
            for (const item of eq.items) {
                if (item === "weapon_knife" ? pawn.FindWeaponBySlot(CSGearSlot.KNIFE) : pawn.FindWeapon(item)) continue;
                pawn.GiveNamedItem(item, false);
            }
        }
    }
    return false;
});
