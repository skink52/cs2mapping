#!/bin/sh
# Script + HUD only, for one title: full build into out/addon (each title has its own tracks / music data baked into the script),
# then the script, the HUD styles and (when it changed) the HUD layout go into the content addon, backed up first, and are compiled
# in place. The map itself is not touched (no Hammer build needed for a script / HUD change).
# usage: SPR_THEME=space|neon|depth sh tools/deploy_hud.sh      (needs python3 on the path: see README)
set -e
cd "$(dirname "$0")/.."
THEME=${SPR_THEME:-space}
case "$THEME" in neon) NAME=neon_racer ;; depth) NAME=depth_racer ;; *) NAME=space_racer ;; esac
ADDON=mg_$NAME
C="/c/source1/links/content_addons/$ADDON"; G="/c/source1/links/game_addons/$ADDON"
[ -d "$C" ] || { echo "no content addon $C"; exit 2; }
# CS2 in tools mode on this addon would hot-reload the script mid-round
if tasklist //V //FI "IMAGENAME eq cs2.exe" //FO CSV 2>/dev/null | grep -i -q -- "-tools"; then echo "HELD: cs2 -tools is open"; exit 3; fi
SPR_THEME=$THEME sh tools/build_all.sh > "build/build_$THEME.log" 2>&1 || { tail -5 "build/build_$THEME.log"; exit 1; }
STAMP=$(date +%Y%m%d_%H%M%S); BK="backups/hud_$ADDON.$STAMP"; mkdir -p "$BK"
FILES="maps/scripts/$NAME.js panorama/styles/custom_game/$NAME.css"
cmp -s "out/addon/panorama/layout/custom_game/$NAME.xml" "$C/panorama/layout/custom_game/$NAME.xml" || FILES="$FILES panorama/layout/custom_game/$NAME.xml"
for f in $FILES; do
  [ -f "$C/$f" ] && { mkdir -p "$BK/$(dirname "$f")"; cp -p "$C/$f" "$BK/$f"; }
  cp "out/addon/$f" "$C/$f"; echo "copied $f"
done
# the whole-line pictures (tools/hud.py, 24 Nov 2026): compiled as the styles' references
if [ -d out/addon/panorama/images/custom_game/spr/l ]; then
  mkdir -p "$C/panorama/images/custom_game/spr/l"
  [ -d "$C/panorama/images/custom_game/spr/l" ] && cp -p -r "$C/panorama/images/custom_game/spr/l" "$BK/l_old" 2>/dev/null || true
  rm -f "$C/panorama/images/custom_game/spr/l/"*.png; cp out/addon/panorama/images/custom_game/spr/l/*.png "$C/panorama/images/custom_game/spr/l/"
  echo "copied $(ls out/addon/panorama/images/custom_game/spr/l | wc -l) line pictures"
fi
ARGS=""; for f in $FILES; do ARGS="$ARGS $C/$f"; done
python ../../tools/rcompile.py asset --force --log "build/compile_hud_$ADDON.log" $ARGS
bad=0
for f in $FILES; do
  case "$f" in *.js) o="${f%.js}.vjs_c" ;; *.css) o="${f%.css}.vcss_c" ;; *.xml) o="${f%.xml}.vxml_c" ;; esac
  if [ ! -f "$G/$o" ] || [ "$C/$f" -nt "$G/$o" ]; then echo "STALE: $G/$o"; bad=1; else echo "ok: $o"; fi
done
echo "backup: $BK"
exit $bad
