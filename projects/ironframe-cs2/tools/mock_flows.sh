#!/bin/sh
# The scripted-flow mock run (test/mock_flows.mjs): builds a copy of the script with 70 s core rounds, then runs the mock engine with
# one scripted human (Sortie's beacon can't be lost, so round 1 lasts the full 70 s). usage: sh tools/mock_flows.sh [entities.json] [extra mock options]
#   entities.json: default out/addon/_gen/entities.json; give the Hammer map's dump (create/dump_entities.py) to test the hangar bays
set -e
cd "$(dirname "$0")/.."
ENTS=${1:-out/addon/_gen/entities.json}; [ $# -gt 0 ] && shift
mkdir -p build
node -e "
const fs=require('fs');let s=fs.readFileSync('out/addon/maps/scripts/ironframe.js','utf8');
const k='  core: {},';if(!s.includes(k))throw new Error('CONFIG core line not found');
s=s.replace(k,'  core: { round: { tb: 70, cq: 70, sk: 70, so: 70, kh: 70, ctf: 70, warmup: 5, podium: 12 }, so: { waves: 9, bossEvery: 3, baseEnemies: 8, perWave: 2, maxEnemies: 16, extraPerPlayer: 0.25, allies: 8, pause: 8, nextAt: 2, beaconLoseTime: 9999, bossPhases: [0.66, 0.33], weakMult: 3, respawn: 10 } },');
if(!s.includes('DEBUG: false'))throw new Error('CONFIG DEBUG not found');s=s.replace('DEBUG: false','DEBUG: true');   // the ifr_test_npckill input (stand-in kills)
fs.writeFileSync('build/ironframe_flows.js',s);"
run() { IF_FLOW_ENTS="$ENTS" node ../../create/test/mock_point_script.mjs build/ironframe_flows.js "$ENTS" players=6 noinputs=ifr_server,ifr_pilot,ifr_deny,ifr_test_npckill,ifr_cmd_help,ifr_cmd_garage,ifr_cmd_back,ifr_cmd_od,ifr_cmd_cam,ifr_cmd_hints,ifr_cmd_bots,ifr_cmd_mode \
  scenario=test/mock_flows.mjs hud=out/addon/panorama/layout/custom_game/ironframe.xml panelids=950 "$@"; }   # panelids: CS2 stops updating HUD panels past 1024 referenced ids (docs/HUD.md)
echo "== flows (CS2 restarts the round)"; run seconds=125 "$@"
echo "== flows (CS2 never starts round 2: the script's fallback)"; FLOW_NORESTART=1 run seconds=135 "$@"
