#!/bin/sh
# Sprawl map from scratch into out/sprawl/addon (never out/addon, which is Dunes'): template -> vmap.py (layout, ground, plaza,
# highways, everything the script needs) -> sprawl_ops.py (city layer: mapops batch) -> copies.py (3 arena copies stacked in z)
# -> the hangar -> patch_cache.py (a cache prop for every model the script can draw) -> cache_check.py (stops the build on a gap).
# The script / HUD / models for the addon still come from the shared build (tools/build_all.sh); the shared _gen lists (models.json,
# auras.json, objectives.json, sounds.json, fx_particles.json) are taken from out/addon/_gen so the cache room lists every model.
# 10 Nov 2026 playtest: auras.json and objectives.json were not copied, so the map precached none of the 65 aura models (ERROR
# models at the mechs' feet) and none of the 65 objective markers. The whole rebuild (this, deploy, asset compile, map compile)
# is one command: sh tools/arenas/rebuild_sprawl.sh
set -e
cd "$(dirname "$0")/../.."
OUT=${SPRAWL_OUT:-out/sprawl/addon}; MAPF=$OUT/maps/mg_ironframe_sprawl.vmap
TEMPLATE=${IF_TEMPLATE:-C:/source1/cs2port/tools/addon_template/content/maps/xxx_mapname_xxx.vmap}
mkdir -p $OUT/maps $OUT/_gen $OUT/models/ifr
# another tool may be writing models.json right now (models.json.lock; older than 15 min = stale): wait for it, up to 5 min
python -c "import os,time,sys; l='out/addon/_gen/models.json.lock'; t=time.time()
while os.path.exists(l) and time.time()-os.path.getmtime(l)<900 and time.time()-t<300: time.sleep(1)"
for f in models.json sounds.json fx_particles.json auras.json objectives.json; do [ -f out/addon/_gen/$f ] && cp out/addon/_gen/$f $OUT/_gen/; done
# one null model for every map: the shared one (tools/fx.py). vmap.py writes its own only when there is none, which gave Sprawl a second
# null.vmdl under the same name that overwrote the shared one in the addon at every deploy.
if [ -f out/addon/models/ifr/null.vmdl ]; then cp out/addon/models/ifr/null.vmdl $OUT/models/ifr/null.vmdl; rm -f $OUT/models/ifr/null.smd; fi
IF_ARENA=sprawl python -I tools/vmap.py "$TEMPLATE" "$MAPF" $OUT ${SPRAWL_PICTURES:+}
python -I tools/arenas/sprawl_ops.py "$MAPF" $OUT
# the detail pass (street furniture, vehicles, road paint, the square, the decks; vis group ifr_detail): docs/SPRAWL_NOTES.md "Detail pass"
python -I tools/arenas/sprawl_detail.py "$MAPF" $OUT --stats $OUT/_gen/sprawl_detail_stats.json
python -I tools/arenas/objectives.py "$MAPF" "$MAPF" $OUT --arena sprawl    # zone rings, letter masts, flag stands (before the copies: they copy it)
python -I tools/arenas/copies.py "$MAPF" $OUT --stack 8664      # 3 copies stacked like Dunes (z 0, -8664, +8664)
# the garage hangar (12 bays) skink52 built in Hammer on Dunes: copied as it is from Dunes' saved map (vis group ifr_hangar)
python -I tools/arenas/import_region.py "${IF_HANGAR_SRC:-/c/source1/links/content_addons/mg_ironframe_dunes/maps/mg_ironframe_dunes.vmap}" "$MAPF" -7500 -6500 -14500 -2400 6500 -11000 --into ifr_hangar
# every model the script can SetModel to that the generator's cache room does not hold yet (objective markers, anything newer than
# the generator's lists), and the particle pools: then the check. A gap stops the build here (set -e): Sprawl can't ship with one.
python -I tools/patch_cache.py "$MAPF" "$MAPF.patched" $OUT
mv "$MAPF.patched" "$MAPF"
python ../../create/check_mesh.py "$MAPF" | tail -3
python -I tools/cache_check.py "$MAPF" --addon mg_ironframe_sprawl --map-only --quiet
