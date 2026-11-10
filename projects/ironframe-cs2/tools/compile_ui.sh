#!/bin/sh
# Compiles the script and the HUD (panorama layout + styles; their pictures compile as references) of one IRONFRAME addon in place and
# checks that every compiled file is newer than its source. usage: sh tools/compile_ui.sh mg_ironframe_dunes|mg_ironframe_sprawl
# The script bakes hud.json, so script and panorama must always be deployed and compiled together (docs/HUD.md).
set -e
cd "$(dirname "$0")/.."
ADDON=${1:?addon name}
C="/c/source1/links/content_addons/$ADDON"; G="/c/source1/links/game_addons/$ADDON"
mkdir -p logs
python ../../tools/rcompile.py asset --force --log "logs/compile_ui_$ADDON.log" \
  "$C/maps/scripts/ironframe.js" "$C/panorama/layout/custom_game/ironframe.xml" "$C/panorama/styles/custom_game/ironframe.css"
bad=0
for p in "maps/scripts/ironframe.js:maps/scripts/ironframe.vjs_c" "panorama/layout/custom_game/ironframe.xml:panorama/layout/custom_game/ironframe.vxml_c" "panorama/styles/custom_game/ironframe.css:panorama/styles/custom_game/ironframe.vcss_c"; do
  s="$C/${p%%:*}"; o="$G/${p##*:}"
  if [ ! -f "$o" ] || [ "$s" -nt "$o" ]; then echo "STALE: $o"; bad=1; else echo "ok: $o ($(date -r "$o" +%H:%M:%S))"; fi
done
n=0; m=0
# only pictures the layout or the styles name are compiled (as their references); the rest are spares from tools/hud_images.py
for f in "$C"/panorama/images/custom_game/ifr/*.png; do b=$(basename "$f" .png)
  grep -q "ifr/$b\.png" "$C/panorama/styles/custom_game/ironframe.css" "$C/panorama/layout/custom_game/ironframe.xml" || continue
  n=$((n+1)); [ -f "$G/panorama/images/custom_game/ifr/${b}_png.vtex_c" ] || { m=$((m+1)); echo "MISSING picture: $b"; }; done
echo "pictures: $n used, $m not compiled"
[ $m -gt 0 ] && bad=1
exit $bad
