#!/bin/sh
# Rebuilds the whole addon into out/addon.
#   SPR_NAME=<map name>          map / script / HUD file name (default space_racer -> mg_space_racer.vmap, scripts/space_racer.js)
#   SPR_CURRENT_VMAP=<path>      the map as last saved by Hammer: our entities are layered onto it (keeps hand edits)
#   SPR_SOUNDEVENTS=<path>       the addon's soundevents_addon.vsndevts to merge into (default: the stock template)
set -e
cd "$(dirname "$0")/.."
THEME=${SPR_THEME:-space}
export SPR_THEME=$THEME
case "$THEME" in
  neon)  NAME=${SPR_NAME:-neon_racer}; PV=preview/neon ;;
  depth) NAME=${SPR_NAME:-depth_racer}; PV=preview/depth ;;
  *)     NAME=${SPR_NAME:-space_racer}; PV=preview ;;
esac
mkdir -p $PV
MAP=${SPR_MAP:-mg_$NAME}
rm -rf out/addon && mkdir -p out/addon/maps build
python3 -I tools/tracks.py out/addon $PV/tracks.png
python3 -I tools/cars.py out/addon $PV/car_angles.png
python3 -I tools/hud.py out/addon "$NAME" "$MAP"
# lay the HUD out like Panorama would and stop the build if it breaks the layout rules (see tools/hud.py)
python3 -I preview/hud_render.py out/addon preview/chase_nullgap.png build/hud_check
python3 -I tools/loading.py out/addon "$MAP" $PV
python3 -I tools/sounds.py out/addon "${SPR_SOUNDEVENTS:-ref/soundevents_addon_template.vsndevts}"
SPR_NAME="$NAME" node tools/build.mjs
SRC=${SPR_CURRENT_VMAP:-ref/hammer_template.vmap}
python3 -I tools/vmap.py "$SRC" "out/addon/maps/$MAP.vmap" out/addon "$NAME"
if [ "$THEME" = neon ] || [ "$THEME" = depth ]; then
  UP=$(echo "$NAME" | tr a-z A-Z)
  cp docs/$THEME/README_ADDON.md out/addon/README_$UP.md 2>/dev/null || true
  cp docs/$THEME/TESTING.md out/addon/TESTING_$UP.md 2>/dev/null || true
else
  cp docs/README_ADDON.md out/addon/README_SPACE_RACER.md 2>/dev/null || true
  cp docs/TESTING.md out/addon/TESTING_SPACE_RACER.md 2>/dev/null || true
fi
cp docs/CREDITS.md out/addon/CREDITS.md 2>/dev/null || true
cp LICENSE LICENSE-CC-BY-NC-4.0.txt out/addon/
cp test/types/point_script.d.ts out/addon/maps/scripts/ 2>/dev/null || true
rm -rf out/addon/_gen/*.json.tmp
echo "built out/addon (map maps/$MAP.vmap, script maps/scripts/$NAME.js)"
