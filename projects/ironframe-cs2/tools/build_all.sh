#!/bin/sh
# Rebuilds the whole IRONFRAME addon into out/addon (content) and out/game, then type-checks and mock-runs the script.
#   IF_ARENA=dunes|sprawl|orbital   which map (default dunes); IF_CURRENT_VMAP=<path> the map as last saved in Hammer (generated content is layered onto it)
#   IF_NAME / IF_MAP                script and map names (tools/names.py)
# Every optional tool another agent may not have written yet is skipped with a SKIP line so the build runs today.
# Then: sh tools/deploy.sh (copies into CS2's addon folders) and the command-line map build (C:\source1\cs2port\build_maps.ps1 mg_ironframe_<arena>).
set -e
cd "$(dirname "$0")/.."
. ./tools/names.sh
CREATE=${CREATE:-../../create}
TEMPLATE=${IF_TEMPLATE:-C:/source1/cs2port/tools/addon_template/content/maps/xxx_mapname_xxx.vmap}
SRC=${IF_CURRENT_VMAP:-$TEMPLATE}
mkdir -p out/addon/maps/scripts out/addon/_gen out/game build logs preview/arenas
step() { echo; echo "== $*"; }
opt() { # opt <tool.py> <args...>: run a project tool if it exists
  if [ -f "tools/$1" ]; then t=$1; shift; python -I "tools/$t" "$@"; else echo "SKIP tools/$1 (not written yet)"; fi
}

step "parts check";        opt parts_check.py
if [ -z "$IF_SKIP_MODELS" ]; then   # IF_SKIP_MODELS=1 keeps the converted models (frames.py reconverts only missing ones anyway)
step "frames";             opt frames.py out/addon --skip-existing --no-preview --all   # --all until skink52 approves frames (status in data/frames.json); remove it then
step "weapon props";       opt weapon_props.py out/addon --all   # --all until skink52 approves weapons (status in data/weapons.json); remove it then
step "weapon mounts";      opt weapon_fit.py --fit || echo "weapon fit reported clearance / grip failures (docs/WEAPON_FIT.md, build/weapon_fit.json)"   # ~6 min: grips to the palms, shoulder units clear
step "fx";                 opt fx.py out/addon
else echo "SKIP models (IF_SKIP_MODELS)"; fi
step "hud"
if [ -f tools/hud.py ]; then
  python -I tools/hud.py out/addon "$NAME" "$MAP"
  python -I "$CREATE/hud_check.py" --addon out/addon --name "$NAME" --out build/hud || echo "hud_check reported problems (see build/hud)"
else echo "SKIP tools/hud.py (not written yet)"; fi
step "sounds";             opt sounds.py out/addon
step "sky";                python -I tools/sky.py out/addon "$IF_ARENA"
step "vmap ($IF_ARENA -> maps/$MAP.vmap)"
python -I tools/vmap.py "$SRC" "out/addon/maps/$MAP.vmap" out/addon
python "$CREATE/check_mesh.py" "out/addon/maps/$MAP.vmap"      # no -I: it imports dmx from its own folder
step "script build"
if [ -d src/core ] && [ -n "$(ls src/core 2>/dev/null)" ]; then
  node "$CREATE/build/build.mjs" build.json --name "$NAME"
  sh "$CREATE/test/tscheck.sh" "out/addon/maps/scripts/$NAME.js" || echo "tscheck reported problems"
  step "mock run (64 players, 240 s, held, churn, fire=ifr_server@5)"
  HUDXML="out/addon/panorama/layout/custom_game/$NAME.xml"
  if [ -f "$HUDXML" ]; then HUDARG="hud=$HUDXML panelids=950"; else HUDARG=""; echo "SKIP hud= (no $HUDXML yet)"; fi
  node "$CREATE/test/mock_point_script.mjs" "out/addon/maps/scripts/$NAME.js" out/addon/_gen/entities.json players=64 seconds=240 held churn "fire=ifr_server@5" $HUDARG
else echo "SKIP script build (src/core is empty)"; fi
step "docs and licences into out/"
cp README.md "out/addon/README_IRONFRAME.md"
[ -f docs/TESTING.md ] && cp docs/TESTING.md "out/addon/TESTING_IRONFRAME.md"
cp LICENSE LICENSE-CC-BY-NC-4.0.txt out/addon/ 2>/dev/null || true
cp LICENSE LICENSE-CC-BY-NC-4.0.txt out/game/ 2>/dev/null || true
echo; echo "built out/addon (maps/$MAP.vmap, maps/scripts/$NAME.js) for $TITLE"
