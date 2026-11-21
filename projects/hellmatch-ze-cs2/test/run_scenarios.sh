#!/bin/sh
# Runs the ZE mock scenarios one by one (each its own process) against test/out/<name>.js (default hellescape, built by
# test/build_test.mjs) with the Hellmatch HUD/music fixtures. Prints one line per scenario; exit 1 if any failed.
#   sh test/run_scenarios.sh [script name]
cd "$(dirname "$0")/.." || exit 1
NAME=${1:-hellescape}
export MOCK_ASSETS=test/fixtures/fdm FDM_SCRIPT=test/out/$NAME.js
fail=0
run() {   # file humans bots seconds options
  out=$(node test/mock_cs2.mjs "$2" "$3" "$4" "seed=7,nomodels,scenario=test/scenarios/$1.mjs${5:+,$5}" 2>&1)
  line=$(printf '%s\n' "$out" | grep '^SCENARIO ' | tail -1)
  [ -n "$line" ] || line="SCENARIO $1.mjs: FAILED (no result line)"
  echo "$line"
  printf '%s\n' "$out" | grep -E '^SCENARIO PROBLEM|THROW|error in' | head -8
  case "$line" in *OK*) ;; *) fail=1 ;; esac
}
run swap_credit 4 4 40
run draw 4 0 40
run disconnect 4 0 20
run latejoin 4 2 25
run teamchange 4 2 20
run afk 4 2 45 afk
run warmup 4 2 20 warmup
run class_choice 4 4 40
run boss_takeover 4 4 52
run ze_ammo 4 4 30 zemap=map01
run ze_stats 4 4 50 stats,zemap=map01
run ze_stats 4 4 50 stats,warmup,zemap=map01
run ze_stats 4 4 50 zemap=map01
# Round 4: lost soul floats + damage tint (4.1/4.3), zombie respawns connected to the humans + doors (4.2), no zombie
# collisions (4.4), the escape finale (4.5) with and without stats / in warmup, the clock rule, no finale record
run ze_float 4 4 24 zemap=map01
run ze_respawn 4 12 45 zemap=map06
run ze_collide 4 4 20 zemap=map01
run finale_escape 4 4 30 stats,zemap=map01
run finale_escape 4 4 30 stats,warmup,zemap=map01
run finale_fight 4 4 30 stats,zemap=map01
run finale_fight 4 4 30 stats,warmup,zemap=map01
run finale_fight 4 4 30 zemap=map01
run finale_clock 4 4 20 stats,zemap=map01
run finale_none 4 4 15 zemap=map01
run finale_escape 4 4 30 zemap=map01
run finale_fight 4 4 30 stats,zemap=map01
run finale_fight 4 4 30 stats,warmup,zemap=map01
run finale_fight 4 4 30 zemap=map01
run finale_none 4 4 30 zemap=map01
run finale_clock 4 4 30 zemap=map01
exit $fail
