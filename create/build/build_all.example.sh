#!/bin/sh
# build_all.example.sh: the reference build order for an original CS2 addon made by generators. Copy it into your
# project as tools/build_all.sh and replace the "your ..." lines with your own generators.
#
# The idea: the game core (src/core) is the source of truth; asset generators read from it, and each generator checks
# the contract with the next one (the HUD check stops the build, loading.py checks the HUD preloads every slide,
# the mock fails on unknown panel ids / models). Everything goes into out/addon (content) and out/game (files for the
# compiled addon folder), never into the repo.
#
# Switches (environment):
#   <X>_NAME=<name>             map / script / HUD file name (here: NAME, default mygame -> mg_mygame.vmap, scripts/mygame.js)
#   <X>_CURRENT_VMAP=<path>     the map as last saved by Hammer: generated entities are layered onto it (keeps hand edits)
#   <X>_SOUNDEVENTS=<path>      the addon's soundevents_addon.vsndevts to merge into (default: a template)
#   CREATE=<path to cs2mapping/create>
#
# From space-racer-cs2/tools/build_all.sh and hellmatch-cs2/tools/build_all.sh (MIT), made project-neutral.
set -e
cd "$(dirname "$0")/.."
CREATE=${CREATE:-../cs2mapping/create}
NAME=${MYGAME_NAME:-mygame}
MAP=${MYGAME_MAP:-mg_$NAME}
export CS2_ADDON_OUT=out/addon
rm -rf out/addon out/game && mkdir -p out/addon/maps out/addon/_gen out/game build

# 1. test module first: generators may need lists from the core (frames, strings, levels)
node "$CREATE/build/build.mjs" build.json --name "$NAME"
#    e.g. node -e "const C=require('./build/core_test.cjs'); require('fs').writeFileSync('build/hud_strings.json', JSON.stringify(C.HUD_STRINGS))"

# 2. models and materials (your generators; create/voxel.py, create/build_prop.py, create/glb2cs2_multi.py ...)
python3 -I tools/models.py out/addon                      # your models -> out/addon/models, _gen/models.json

# 3. HUD, then the HUD check as a gate: any layout problem or overlap with CS2's own HUD stops the build
python3 -I tools/hud.py out/addon "$NAME" "$MAP"          # your HUD (create/panorama.py helpers)
python3 -I "$CREATE/hud_check.py" --addon out/addon --name "$NAME" --states hud_states.json --out build/hud_check

# 4. sounds and music, merged into the addon's sound events (re-runnable: only our block is replaced)
python3 -I tools/sounds.py out/addon                      # your sounds (create/chiptune.py, create/synth.py, create/sndevents.py)
python3 -I "$CREATE/merge_snd.py" "${MYGAME_SOUNDEVENTS:-ref/soundevents_addon_template.vsndevts}" \
    out/addon/soundevents/soundevents_addon.vsndevts --tag "$NAME"

# 5. sky, loading slides (>= 2, checked against the HUD's preload list), radar, icon
python3 -I "$CREATE/skies.py" build/sky.png dusk 1        # or your own sky
python3 -I tools/slides.py build/slides                   # your slide pictures -> build/slides/*.png
python3 -I "$CREATE/loading.py" slides out/addon "$MAP" build/slides/*.png --css-check
python3 -I "$CREATE/loading.py" radar out/addon "$MAP" build/radar.png -4096 -4096 4096 4096 --game out/game
python3 -I "$CREATE/loading.py" icon out/addon "$MAP"

# 6. the map: the user's last Hammer save if given, else the template; then our entities / environment layer
SRC=${MYGAME_CURRENT_VMAP:-ref/hammer_template.vmap}
python3 -I tools/vmap.py "$SRC" "out/addon/maps/$MAP.vmap" out/addon "$NAME"   # your map writer (create/vmaplib.py)
python3 -I "$CREATE/check_mesh.py" "out/addon/maps/$MAP.vmap"
python3 -I "$CREATE/dump_entities.py" "out/addon/maps/$MAP.vmap" build/entities.json

# 7. the script last (it bakes in the generated data), then type-check and run it on the mock engine
node "$CREATE/build/build.mjs" build.json --name "$NAME"
sh "$CREATE/test/tscheck.sh" "out/addon/maps/scripts/$NAME.js"
node "$CREATE/test/mock_point_script.mjs" "out/addon/maps/scripts/$NAME.js" build/entities.json players=16 seconds=120

# 8. docs that ship with the addon (the Workshop upload carries the compiled GAME folder, so credits go there too)
cp docs/README_ADDON.md "out/addon/README_$NAME.md" 2>/dev/null || true
cp docs/TESTING.md "out/addon/TESTING_$NAME.md" 2>/dev/null || true
cp docs/CREDITS.md out/addon/CREDITS.md 2>/dev/null || true
cp out/addon/CREDITS.md out/game/ 2>/dev/null || true
echo "built out/addon (map maps/$MAP.vmap, script maps/scripts/$NAME.js)"
