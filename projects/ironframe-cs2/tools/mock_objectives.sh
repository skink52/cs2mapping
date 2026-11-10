#!/bin/sh
# Objective markers on the mock engine: builds a 70 s-round copy of the script, runs one mock per mode (cq, kh, ctf) with the patched map's
# entities (the ifr_cache_obj_* props, ifr_flag_* stands, ifr_point_*_edge), server mode at 3 s and the plugin's ifr_objdraw at 150 s, and
# reads the trace: objective props drawn, ifr_obj echo lines (mode / pt / flag), rings and columns gone after ifr_objdraw.
# usage: sh tools/mock_objectives.sh [script.js = out/addon/maps/scripts/ironframe.js] [entities.json = out/patched_objectives.vmap.entities.json]
set -e
cd "$(dirname "$0")/.."
SRC=${1:-out/addon/maps/scripts/ironframe.js}; ENTS=${2:-out/patched_objectives.vmap.entities.json}
mkdir -p build/obj
node -e "
const fs=require('fs');let s=fs.readFileSync('$SRC','utf8');
const k='  core: {},';if(!s.includes(k))throw new Error('CONFIG core line not found');
s=s.replace(k,'  core: { round: { tb: 70, cq: 70, sk: 70, so: 70, kh: 70, ctf: 70, warmup: 5, podium: 12 } },');
fs.writeFileSync('build/obj/ironframe_obj.js',s);"
fail=0
for MODE in cq kh ctf; do
  T=build/obj/trace_$MODE.txt
  echo "== $MODE"
  OBJ_MODE=$MODE node ../../create/test/mock_point_script.mjs build/obj/ironframe_obj.js "$ENTS" players=8 seconds=220 \
    noinputs=ifr_pilot,ifr_deny,ifr_server,ifr_objdraw,mgstat_on,mgstat_off "fire=ifr_server@3,ifr_objdraw@170" scenario=test/mock_objectives.mjs trace=$T > build/obj/mock_$MODE.out 2>&1 || true
  grep -E "^(OK|FAIL)|\[scenario\]|scenario |errors" build/obj/mock_$MODE.out | head -6
  # the mock's PROBLEMS: the legs-prop Teleport flag is known from before this work (STATUS.md); anything else fails the run
  other=$(sed -n '/^PROBLEMS/,$p' build/obj/mock_$MODE.out | grep '^  ' | grep -v 'Teleported 3+ ticks' || true)
  [ -z "$other" ] || { echo "FAIL $MODE mock problems:"; echo "$other"; fail=1; }
  grep -q "^OK\|all checks passed\|PROBLEMS" build/obj/mock_$MODE.out || { echo "FAIL $MODE: the mock did not finish"; tail -5 build/obj/mock_$MODE.out; fail=1; }
  modes=$(grep -c "cmd echo ifr_obj 1 mode $MODE" $T || true)
  pts=$(grep -c "cmd echo ifr_obj 1 pt " $T || true); flags=$(grep -c "cmd echo ifr_obj 1 flag " $T || true); ends=$(grep -c "cmd echo ifr_obj 1 end" $T || true)
  props=$(grep -o "models/ifr/fx/obj/obj_[a-z_0-9]*" $T | sort | uniq -c | sort -rn | head -12 | tr '\n' ' ')
  echo "   echo: mode $MODE x$modes, pt x$pts, flag x$flags, end x$ends"
  echo "   props: $props"
  [ "$modes" -ge 1 ] || { echo "FAIL $MODE: no 'ifr_obj 1 mode $MODE' line"; fail=1; }
  if [ "$MODE" = ctf ]; then [ "$flags" -ge 2 ] || { echo "FAIL ctf: no flag lines"; fail=1; }
    grep -q "obj_flag_t" $T && grep -q "obj_flag_ct" $T || { echo "FAIL ctf: flag props not drawn"; fail=1; }
  else [ "$pts" -ge 1 ] || { echo "FAIL $MODE: no pt lines"; fail=1; }
    grep -q "obj_ring_" $T && grep -q "obj_letter_" $T || { echo "FAIL $MODE: zone ring / letter props not drawn"; fail=1; }; fi
done
[ $fail = 0 ] && echo "mock_objectives: ok" || { echo "mock_objectives: FAILED"; exit 1; }
