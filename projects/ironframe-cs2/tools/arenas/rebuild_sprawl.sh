#!/bin/sh
# Sprawl, the whole way, in one command: vmap (generator + cache patch + precache check) -> deploy (content sync) -> compile the
# shared models / particles and Sprawl's own materials in the Sprawl addon (only what is out of date) -> cache_check (every model
# and particle the script can use: precached by the map, compiled, not stale; a gap stops here, before the map compile)
# -> map compile (full preset, no vis, ~6 min) -> final check (vpk newer than the vmap).
# Re-run it after anything that changes models.json / auras.json / objectives.json (a new frame, a recompiled frame, new fx).
# It takes ~10 min, so run it in the background under the watchdog, with a log of its own:
#   python C:\source1\cs2port\autoport\watchdog.py --label "sprawl rebuild" --expect 600 --heartbeat 60 --stall 600 --max 2400 \
#     --log logs/sprawl_rebuild_watch.log -- sh tools/arenas/rebuild_sprawl.sh
# Switches: SPRAWL_SKIP_BUILD=1 keeps out/sprawl/addon/maps/*.vmap (deploy + compile + check only);
#           SPRAWL_NO_UI=1 leaves the addon's panorama / sounds alone; SPRAWL_SCRIPT=1 also copies the Sprawl script (deploy_sprawl.sh);
#           SPRAWL_NO_MAP=1 stops after the asset check (no map compile).
# Exit: 0 built and clean; 1 a step failed or cache_check found gaps; 3 everything staged but the .vpk is in use (CS2 has the map
# loaded): leave the map in CS2 (`disconnect` or load another map), then run the map compile line this prints.
set -e
cd "$(dirname "$0")/../.."
ADDON=mg_ironframe_sprawl
CS2="C:/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive"
VMAP="$CS2/content/csgo_addons/$ADDON/maps/$ADDON.vmap"
VPK="$CS2/game/csgo_addons/$ADDON/maps/$ADDON.vpk"
mkdir -p logs
step() { echo; echo "== $(date +%T) $*"; }
if [ -z "$SPRAWL_SKIP_BUILD" ]; then step "vmap: generator + cache patch + precache check"; sh tools/arenas/build_sprawl.sh; fi
step "deploy (content sync + vmap)"; sh tools/arenas/deploy_sprawl.sh
step "compile what is out of date in the Sprawl addon, then check every model / particle the script can use"
python -I tools/cache_check.py "$VMAP" --compile --also "materials/ifr/sprawl/*.vmat" --also "materials/ifr/sky/*sprawl*.vmat" --quiet --json out/cache_check_sprawl.json
# what only the MAP uses (the hangar crew props that come with the imported hangar, the arena's own post-processing file): the map
# compile does not build them (11 Nov 2026: "Failed loading resource models/ifr/crew/..._c"), and they are not script models, so
# cache_check does not either
step "map-only assets (crew, post-processing)"
CONTENT_DIR="/c/source1/links/content_addons/$ADDON"
EXTRA=$(ls "$CONTENT_DIR"/models/ifr/crew/*.vmdl "$CONTENT_DIR"/postprocess/ifr_sprawl.vpost 2>/dev/null || true)
if [ -n "$EXTRA" ]; then python ../../tools/rcompile.py asset $EXTRA --log logs/sprawl_extra_rc.log | tail -n 3; fi
if [ -n "$SPRAWL_NO_MAP" ]; then echo "SPRAWL_NO_MAP: assets clean, map not compiled"; exit 0; fi
MAPCMD="python ../../tools/rcompile.py map \"$VMAP\" --preset full --novis --threads 11 --log logs/sprawl_rc.log"
if [ -f "$VPK" ] && ! python -c "import sys; open(sys.argv[1], 'r+b').close()" "$VPK" 2>/dev/null; then
  echo "STAGED: the vmap, the content and the compiled assets are in place, but $VPK is in use (CS2 has the map loaded)."
  echo "Leave the map in CS2, then run (from projects/ironframe-cs2, ~6 min, under the watchdog):"
  echo "  $MAPCMD"
  echo "  python -I tools/cache_check.py \"$VMAP\" --vpk --quiet"
  exit 3
fi
step "map compile (full, no vis, ~6 min; log logs/sprawl_rc.log)"
python ../../tools/rcompile.py map "$VMAP" --preset full --novis --threads 11 --log logs/sprawl_rc.log
step "final check"
python -I tools/cache_check.py "$VMAP" --vpk --quiet
if [ -n "$SPRAWL_SCRIPT" ]; then step "script + HUD (tools/compile_ui.sh)"; sh tools/compile_ui.sh "$ADDON"; fi
echo "== $(date +%T) Sprawl rebuilt: $VPK"
