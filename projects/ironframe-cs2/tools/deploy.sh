#!/bin/sh
# deploy.sh: copies the built addon (out/addon, out/game) into CS2's addon folders through C:\source1\links for IF_ARENA's map.
# First run: creates game\csgo_addons\<addon> from Valve's addon template (without readonly_tools_asset_info.bin / addoninfo.txt,
# which make an addon read-only in the Workshop Tools launcher) and copies the template's postprocess + soundevents content.
# Only files whose bytes changed are written (tools/copy_changed.py: a new date on an unchanged file makes CS2's tools reload it and
# every compiled file look stale). Hammer should be closed. Only our files are copied; a map the mapper saved in Hammer is never overwritten unless IF_FORCE_MAP=1.
set -e
cd "$(dirname "$0")/.."
. ./tools/names.sh
CONTENT="/c/source1/links/content_addons/$ADDON"
GAME="/c/source1/links/game_addons/$ADDON"
TPL="/c/source1/cs2port/tools/addon_template"
if [ ! -d "$GAME" ]; then
  mkdir -p "$GAME/cfg/maps" "$GAME/maps"
  cp "$TPL/game/cfg/maps/xxx_mapname_xxx.cfg" "$GAME/cfg/maps/$MAP.cfg"
  cp -r "$TPL/game/postprocess" "$TPL/game/soundevents" "$TPL/game/sounds" "$GAME/" 2>/dev/null || true
  echo "created $GAME"
fi
mkdir -p "$CONTENT/maps/scripts"
if [ ! -d "$CONTENT/postprocess" ]; then
  cp -r "$TPL/content/postprocess" "$CONTENT/"
  cp "$TPL/content/postprocess/xxx_mapname_xxx.vpost" "$CONTENT/postprocess/$MAP.vpost"
  cp -r "$TPL/content/soundevents" "$CONTENT/"
fi
if [ -f "$CONTENT/maps/$MAP.vmap" ] && [ -z "$IF_FORCE_MAP" ]; then
  echo "NOTE: $CONTENT/maps/$MAP.vmap exists; keeping it (IF_FORCE_MAP=1 overwrites). Generated map left in out/addon/maps/."
  for dd in materials models panorama particles sounds soundevents resource; do [ -d "out/addon/$dd" ] && python -I tools/copy_changed.py "out/addon/$dd" "$CONTENT/$dd"; done
  python -I tools/copy_changed.py out/addon/maps/scripts "$CONTENT/maps/scripts" --glob "*.js" --flat
else
  python -I tools/copy_changed.py out/addon "$CONTENT"
fi
rm -rf "$CONTENT/_gen"
[ -d out/game ] && python -I tools/copy_changed.py out/game "$GAME"
echo "deployed $TITLE to $CONTENT and $GAME"
