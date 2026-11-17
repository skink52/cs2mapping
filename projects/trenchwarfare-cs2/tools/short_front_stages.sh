#!/bin/sh
# short front: regenerate and run the patch stages by hand (until deploy_tw.py --chain knows them). Each step watched; stops at the first failure.
cd /c/source1/cs2mapping/projects/trenchwarfare-cs2 || exit 1
W="python C:/source1/cs2port/autoport/watchdog.py --heartbeat 60 --stall 300"
C=out/short_front/step5/chain
FROM=${1:-gen}
step() { echo "== $1 $(date +%T)"; }
if [ "$FROM" = gen ]; then
  step gen
  $W --label "sf gen" --expect 180 --max 600 --log $C/w_gen.log -- python -u tools/make_map.py out/short_front/step5/user_moved.vmap out/short_front/step5/gen_short2.vmap out/addon > $C/gen.log 2>&1 || exit 1
  FROM=w1
fi
if [ "$FROM" = w1 ]; then
  step world_1
  python -u tools/patch_world_1.py --find --user-m2 --user-w5 --in out/short_front/step5/gen_short2.vmap --out $C/1_world_1.vmap --targets $C/1_world_1.targets.json > $C/1_world_1.log 2>&1 || exit 1
  python -u tools/patch_guard.py out/short_front/step5/gen_short2.vmap $C/1_world_1.vmap $C/1_world_1.targets.json --strict --report $C/1_world_1.guard.json | tail -1
  step models
  python -u tools/patch_models.py --no-guard --in $C/1_world_1.vmap --out $C/2_models.vmap > $C/2_models.log 2>&1 || exit 1
  FROM=terrain
fi
if [ "$FROM" = terrain ]; then
  step terrain
  $W --label "sf terrain" --expect 300 --max 1200 --log $C/w_terrain.log -- python -u tools/patch_terrain.py --in $C/2_models.vmap --out $C/3_terrain.vmap --targets $C/3_terrain.targets.json > $C/3_terrain.log 2>&1 || exit 1
  FROM=seams
fi
if [ "$FROM" = seams ]; then
  step seams
  $W --label "sf seams" --expect 240 --max 900 --log $C/w_seams.log -- python -u tools/patch_seams.py --in $C/3_terrain.vmap --out $C/4_seams.vmap --targets $C/4_seams.targets.json --report $C/4_seams.report.json > $C/4_seams.log 2>&1 || exit 1
  FROM=w3
fi
if [ "$FROM" = w3 ]; then
  step world_3
  $W --label "sf world_3" --expect 240 --max 900 --log $C/w_world3.log -- python -u tools/patch_world_3.py --find --pit-sandbags both --in $C/4_seams.vmap --out $C/5_world_3.vmap --targets $C/5_world_3.targets.json --report $C/5_world_3.report.json > $C/5_world_3.log 2>&1 || exit 1
  FROM=sounds
fi
if [ "$FROM" = sounds ]; then
  step sounds
  python -u tools/patch_sounds.py --in $C/5_world_3.vmap --out $C/6_sounds.vmap --targets $C/6_sounds.targets.json > $C/6_sounds.log 2>&1 || exit 1
  FROM=nav
fi
if [ "$FROM" = nav ]; then
  step nav
  $W --label "sf nav" --expect 300 --max 1200 --log $C/w_nav.log -- python -u tools/patch_nav.py --estimate --stage out/addon --in $C/6_sounds.vmap --out $C/7_nav.vmap --targets $C/7_nav.targets.json --report $C/7_nav.report.json > $C/7_nav.log 2>&1 || exit 1
  FROM=fog
fi
if [ "$FROM" = fog ]; then
  step fog
  python -u tools/patch_fog_2.py --in $C/7_nav.vmap --out $C/8_fog.vmap --targets $C/8_fog.targets.json --report $C/8_fog.report.json > $C/8_fog.log 2>&1 || exit 1
fi
step done
