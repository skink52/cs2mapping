// mech mode: game-mode settings a map applies itself. CONFIG.mode = { name: "deathmatch", commands: ["mp_respawn_on_death_t 1", ...],
//   every_round: true, give: ["weapon_ak47"] (given to every player at spawn) }
// The commands run on activation and (every_round) at each round start: the mode's own cfg resets several of them (cs2-map-mcp found
// mp_freezetime and friends come back after the map loads). game_type / game_mode can't be switched from a map: start the server with
// them (gen_gameplay.MODES has the launch line). Ported from cs2-map-mcp's modes.py mode script (Rmgs123, MIT); fresh code.

function modeInstall() {
  const M = CONFIG.mode; if (!M) return;
  function apply() { for (const c of M.commands || []) Instance.ServerCommand(c); mechLog("mode " + (M.name || "") + " applied"); }
  apply();
  if (M.every_round !== false) onStart(apply);
  if (M.give && M.give.length) {
    Instance.OnPlayerReset((e) => {
      const pawn = e.player;
      if (!pawn || !pawn.IsValid()) return;
      for (const w of M.give) if (!pawn.FindWeapon(w)) pawn.GiveNamedItem(w);   // CS2 gives a duplicate otherwise
    });
  }
}
