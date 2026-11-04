#!/bin/sh
# usage: sh test/run_mock.sh [path to cs2mapping root, default ../..] [extra mock options]
CM=${1:-../..}; [ $# -gt 0 ] && shift
D=$(cd "$(dirname "$0")/.." && pwd); T=$(mktemp -d)
echo '[{"name":"ttt_hud","cls":"custom_hud_layout","origin":[0,0,0],"angles":[0,0,0]},{"name":"ttt_params","cls":"info_map_parameters","origin":[0,0,0],"angles":[0,0,0]},{"name":"ttt_body_tpl","cls":"point_template","origin":[0,0,0],"angles":[0,0,0]},{"name":"crate1","cls":"prop_physics","origin":[50,0,0],"angles":[0,0,0]}]' > "$T/ents.json"
JS="$D/addon/maps/scripts/ttt.js"; HUD="$D/addon/panorama/layout/custom_game/ttt_hud.xml"
sh "$CM/create/test/tscheck.sh" "$JS" || exit 1
for o in "players=16 seconds=900 seed=5 held churn" "players=24 seconds=900 seed=9 silent unassigned resetfirst" \
         "players=64 seconds=600 seed=2 held churn hudwipe" "players=8 seconds=300 warmup norespawn" "players=2 seconds=200"; do
  echo "== $o"; node "$CM/create/test/mock_point_script.mjs" "$JS" "$T/ents.json" $o noinputs=ttt:server hud="$HUD" "$@" | grep -E "^rounds|^script time|^OK|ERRORS|PROBLEMS" || exit 1
done
for f in "$D"/maps/*.json; do
  [ -f "$f" ] || continue; m=$(basename "$f" .json)
  sed "s|{\"$m\":|{\"mock_map\":|; s|,\"$m\":|,\"mock_map\":|" "$JS" > "$T/map_$m.js"
  echo "== map data $m (autoents)"; node "$CM/create/test/mock_point_script.mjs" "$T/map_$m.js" players=16 seconds=600 seed=3 held churn autoents noinputs=ttt:server hud="$HUD" | grep -E "^OK|ERRORS|PROBLEMS" || exit 1
done
# server off switch: a server TTT plugin sends ttt:server. Before the script starts (SERVER_WAIT), it must never touch the server;
# mid-game, it must hand players back and stop without errors.
echo "== server plugin at load"
out=$(MOCK_VERBOSE=1 node "$CM/create/test/mock_point_script.mjs" "$JS" "$T/ents.json" players=16 seconds=300 seed=4 held churn noinputs=ttt:server fire=ttt:server@1 hud="$HUD") || { echo "$out" | tail -20; exit 1; }
echo "$out" | grep -q "ttt.js is off" || { echo "FAIL: no off message"; exit 1; }
echo "$out" | grep -E "^Instance calls:" | grep -q "ServerCommand" && { echo "FAIL: ServerCommand while switched off"; exit 1; }
echo "$out" | grep -E "^EntFire:" | grep -q "ttt_" && { echo "FAIL: map relays fired while switched off"; exit 1; }
echo "$out" | grep -E "^OK" || exit 1
m="$D/maps/ttt_minecraft.json"; [ -f "$m" ] || m=$(ls "$D"/maps/*.json 2>/dev/null | head -1)
if [ -n "$m" ]; then m=$(basename "$m" .json)
  echo "== server plugin mid-game ($m map data)"
  out=$(MOCK_VERBOSE=1 node "$CM/create/test/mock_point_script.mjs" "$T/map_$m.js" players=16 seconds=400 seed=6 held churn autoents noinputs=ttt:server fire=ttt:server@200 hud="$HUD") || { echo "$out" | tail -20; exit 1; }
  echo "$out" | grep -q "\[ttt\] started" || { echo "FAIL: never started"; exit 1; }
  echo "$out" | grep -q "ttt.js is off" || { echo "FAIL: no off message"; exit 1; }
  echo "$out" | grep -E "^OK" || exit 1
fi
