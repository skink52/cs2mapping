#!/bin/sh
# Rebuilds the whole addon into out/addon (content) and out/game, then type-checks and mock-runs the script.
#   NT_CURRENT_VMAP=<path>  the map as last saved in Hammer: generated content is layered onto it (keeps hand edits)
#   NT_NAME / NT_MAP        script and map names (tools/names.py)
# Then: sh tools/deploy.sh (copies into CS2's addon folders) and a command-line build (C:\source1\cs2port\build_maps.ps1 mg_nanite_temple).
set -e
cd "$(dirname "$0")/.."
. ./tools/names.sh
CREATE=${CREATE:-../../create}
TEMPLATE=${NT_TEMPLATE:-C:/source1/cs2port/tools/addon_template/content/maps/xxx_mapname_xxx.vmap}
SRC=${NT_CURRENT_VMAP:-$TEMPLATE}
mkdir -p out/addon/maps/scripts out/addon/_gen out/game build logs
python tools/layout.py out/addon/_gen/layout.json
python tools/fx.py out/addon
python tools/sounds.py out/addon ${NT_SOUNDEVENTS:+--soundevents "$NT_SOUNDEVENTS"}
python tools/hud.py out/addon "$NAME" "$MAP"
python "$CREATE/hud_check.py" --addon out/addon --name "$NAME" --states build/hud_states.json --out build/hud
[ -d ref/models_src ] && cp -r ref/models_src/. out/addon/   # Tripo guardians (tools/import_glb.py)
python tools/vmap.py "$SRC" "out/addon/maps/$MAP.vmap" out/addon
python "$CREATE/check_mesh.py" "out/addon/maps/$MAP.vmap"
node "$CREATE/build/build.mjs" build.json --name "$NAME"
sh "$CREATE/test/tscheck.sh" "out/addon/maps/scripts/$NAME.js"
node "$CREATE/test/mock_point_script.mjs" "out/addon/maps/scripts/$NAME.js" out/addon/_gen/entities.json players=24 seconds=300 held "hud=out/addon/panorama/layout/custom_game/$NAME.xml"
cp README.md "out/addon/README_NANITE.md"; cp docs/TESTING.md "out/addon/TESTING_NANITE.md"
cp LICENSE LICENSE-CC-BY-NC-4.0.txt out/game/ 2>/dev/null || true
echo "built out/addon (maps/$MAP.vmap, maps/scripts/$NAME.js)"
