#!/bin/sh
# The objective map patch in one go: <map .vmap (a backup copy, never the live file)> -> tools/patch_cache.py (cache props for every model the
# script uses, the objective markers included) -> tools/arenas/objectives.py (zone and flag-stand dressing, ifr_flag_*, ifr_point_*_edge) -> <out>.
# Run tools/objective_fx.py first (it compiles the marker models and the self-lit materials the dressing uses).
# usage: sh tools/patch_objectives.sh <backup .vmap> [out = out/patched_objectives.vmap] [arena = dunes]
set -e
cd "$(dirname "$0")/.."
SRC=${1:?usage: sh tools/patch_objectives.sh <backup .vmap> [out] [arena]}; OUT=${2:-out/patched_objectives.vmap}; AR=${3:-dunes}
echo "== patch_cache $(date +%T)"
python -I tools/patch_cache.py "$SRC" out/tmp_objectives_cache.vmap out/addon
echo "== objectives $(date +%T)"
python -I tools/arenas/objectives.py out/tmp_objectives_cache.vmap "$OUT" out/addon --arena "$AR"
rm -f out/tmp_objectives_cache.vmap
echo "== done $(date +%T)"; ls -la "$OUT"
