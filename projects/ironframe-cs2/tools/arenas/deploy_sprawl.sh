#!/bin/sh
# Copies the Sprawl build (out/sprawl/addon, from tools/arenas/build_sprawl.sh) into CS2's addon folders mg_ironframe_sprawl, after the
# shared assets of the main build (out/addon: frame / weapon models, fx, panorama, sounds; never its maps/ or _gen/).
# First run creates the addon from Valve's template like tools/deploy.sh. The map is overwritten (Sprawl is fully generated: nobody
# edits it in Hammer); Hammer must not have it open. SPRAWL_SCRIPT=1 also copies out/sprawl/addon/maps/scripts (the script built
# for Sprawl's arena.json: node ../../create/build/build.mjs out/sprawl/build.json (paths in it are relative to out/sprawl/)).
# SPRAWL_NO_UI=1 leaves panorama / sounds / resource alone (a map + model refresh while the HUD or the script is being worked on).
#
# Models, materials and particles go through tools/cache_check.py --sync-only: only files that are missing or different are copied,
# so a content file's date is when it last changed (cp -r re-dated all ~4 000 of them at every deploy). Their compiled *_c are
# built in THIS addon by `python -I tools/cache_check.py <the deployed vmap> --compile` (resourcecompiler without -f: recompiles
# what is out of date, skips the rest). Never copy *_c from the Dunes game addon: `cp -rn` kept whatever was copied first (stale
# after a re-pivot or a reconvert), and the compiler takes a copy from another addon for out of date anyway, so CS2's tools
# recompiled them at map load. sh tools/arenas/rebuild_sprawl.sh runs build, this, the asset compile, the check and the map compile.
set -e
cd "$(dirname "$0")/../.."
ADDON=mg_ironframe_sprawl; MAP=$ADDON
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
# the arena's own bloom (tools/arenas/post.py), patched from the template's file at every deploy
python -I tools/arenas/post.py "$TPL/content/postprocess/basic_linear_post.vpost" "$CONTENT/postprocess/ifr_sprawl.vpost" sprawl
python -I tools/cache_check.py --addon $ADDON --sync-only      # materials, models, particles of out/addon, then out/sprawl/addon (which wins)
if [ -z "$SPRAWL_NO_UI" ]; then   # SPRAWL_NO_UI=1: map + models only (the HUD layout belongs with the script build it was made for)
  for d in panorama sounds soundevents resource; do [ -d "out/addon/$d" ] && cp -r "out/addon/$d" "$CONTENT/"; done
  for d in panorama resource; do [ -d "out/sprawl/addon/$d" ] && cp -r "out/sprawl/addon/$d" "$CONTENT/"; done
fi
# an identical vmap is left alone: a fresh date on it makes cache_check --vpk say "vpk built before the vmap was written" (11 Nov 2026)
cmp -s out/sprawl/addon/maps/$MAP.vmap "$CONTENT/maps/$MAP.vmap" || cp out/sprawl/addon/maps/$MAP.vmap "$CONTENT/maps/$MAP.vmap"
[ -n "$SPRAWL_SCRIPT" ] && cp out/sprawl/addon/maps/scripts/*.js "$CONTENT/maps/scripts/"
[ -d out/game ] && cp -r out/game/. "$GAME/" 2>/dev/null || true
echo "deployed Sprawl to $CONTENT and $GAME"
