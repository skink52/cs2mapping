#!/bin/sh
# Builds everything from your own installs into out/addon (content) and out/game (game folder files).
# usage: tools/build_all.sh <Half-Life dir> <CS2 dir (".../Counter-Strike Global Offensive")>
set -e
HL="$1"; CS2="$2"
ADDON="$CS2/content/csgo_addons/mg_cs16"
cd "$(dirname "$0")/.."
mkdir -p build out/addon out/game
[ -x build/cliphull ] || gcc -O2 -o build/cliphull tools/goldsrc/cliphull.c -lm
[ -f build/soundevents_weapons.json ] || python3 tools/dump_soundevents.py "$CS2/game/csgo/pak01_dir.vpk" build weapons
python3 tools/sounds.py "$HL/cstrike" "$HL/valve" "$ADDON/soundevents/soundevents_addon.vsndevts" build/soundevents_weapons.json out/addon
python3 tools/convert_map.py "$ADDON/maps/mg_cs16.vmap" "$HL/cstrike" "$HL/valve" out/addon
# loading screens: renders of the converted maps (dust2 T spawn, train T spawn, nuke CT spawn)
python3 preview/scene.py out/addon/maps/mg_cs16.vmap out/addon preview/build
python3 preview/shot.py build/load '[{"x":-832,"y":-704,"z":196,"yaw":159,"pitch":0,"fov":85},{"x":3872,"y":1568,"z":-156,"yaw":270,"pitch":0,"fov":85},{"x":5264,"y":-5648,"z":-284,"yaw":180,"pitch":0,"fov":85}]' 1920 1080
python3 tools/loading.py out/addon/maps/mg_cs16.vmap out/addon out/game build/load_0.png build/load_1.png build/load_2.png
python3 tools/hud.py "$HL/cstrike" out/addon
python3 tools/models.py "$HL/cstrike" "$CS2/content/csgo_addons/mg_mario_party/models/player/custom_player/kuristaja/octodad/cs2" out/addon build/models
node tools/build.mjs
node test/core_test.cjs
node test/mock_cs2.mjs 64 300
