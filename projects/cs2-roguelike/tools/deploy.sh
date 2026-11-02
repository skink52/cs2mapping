#!/bin/sh
# deploy.sh: copies the built addon (out/addon, out/game) into CS2's addon folders through C:\source1\links.
# First run: creates game\csgo_addons\<addon> from Valve's addon template (without readonly_tools_asset_info.bin / addoninfo.txt,
# which make an addon read-only in the Workshop Tools launcher) and copies the template's postprocess + soundevents content.
# Hammer must be closed. Only our files are copied; a map the mapper saved in Hammer is never overwritten unless NT_FORCE_MAP=1.
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
if [ -f "$CONTENT/maps/$MAP.vmap" ] && [ -z "$NT_FORCE_MAP" ]; then
  echo "NOTE: $CONTENT/maps/$MAP.vmap exists; keeping it (NT_FORCE_MAP=1 overwrites). Generated map left in out/addon/maps/."
  cp -r out/addon/materials out/addon/models "$CONTENT/" 2>/dev/null || true
  [ -d out/addon/panorama ] && cp -r out/addon/panorama "$CONTENT/"
  cp out/addon/maps/scripts/*.js "$CONTENT/maps/scripts/" 2>/dev/null || true
else
  cp -r out/addon/. "$CONTENT/"
fi
rm -rf "$CONTENT/_gen"
[ -d out/game ] && cp -r out/game/. "$GAME/" 2>/dev/null || true
echo "deployed to $CONTENT and $GAME"
