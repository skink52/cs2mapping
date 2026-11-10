#!/bin/sh
# Dunes, everything except the map itself (skink52 edits it in Hammer): deploy the content (script, HUD, models, particles, sounds),
# re-make out/patched_assets.vmap (the live map's objectives patch + cache props for every model the script can use), sync and compile
# what is out of date in the Dunes addon and check it against that patched map, then compile the script and the HUD.
# ~5 min; run under the watchdog. The live vmap is NOT touched: apply out/patched_assets.vmap by hand (docs/STATUS.md) and build the map.
set -e
cd "$(dirname "$0")/.."
step() { echo; echo "== $(date +%T) $*"; }
step "deploy content"; IF_ARENA=dunes sh tools/deploy.sh
step "patched map with the full cache"; python -I tools/patch_cache.py out/patched_objectives.vmap out/patched_assets.vmap out/addon
step "sync + compile out-of-date assets, check against the patched map"
rc=0; python -I tools/cache_check.py out/patched_assets.vmap --addon mg_ironframe_dunes --sync --compile --quiet --json out/cache_check_dunes.json || rc=$?
step "script + HUD"; sh tools/compile_ui.sh mg_ironframe_dunes || rc=1
echo "== $(date +%T) Dunes assets done (exit $rc)"
exit $rc
