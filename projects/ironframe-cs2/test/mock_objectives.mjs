// Objective markers on the mock engine (create/test/mock_point_script.mjs scenario=test/mock_objectives.mjs), run by tools/mock_objectives.sh:
// the humans vote OBJ_MODE (cq | kh | ctf) in round 1, so round 2 plays it. The runner reads the trace for the props and echo lines;
// this checks the counts it can see from inside: the script sent ifr_obj lines once the plugin said ifr_server, and round 2 is the mode.
const MODE = process.env.OBJ_MODE || 'ctf';
let voted = false, echoes0 = -1;
export default {
  tick(api) {
    if (!voted && api.time > 8) { voted = true; for (let s = 0; s < api.players.length; s++) if (api.players[s]) api.chat(s, '!vote ' + MODE); }
    if (echoes0 < 0 && api.time > 2) echoes0 = api.stats.calls['ServerCommand echo'] || 0;
  },
  check(api) {
    const out = [];
    const n = (api.stats.calls['ServerCommand echo'] || 0) - Math.max(0, echoes0);
    if (n < 5) out.push('objectives: only ' + n + ' echo lines after ifr_server (expected the ifr_obj state lines)');
    api.log('echo lines after 2 s: ' + n + ', rounds ' + api.rounds);
    return out;
  },
};
