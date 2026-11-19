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
exit $fail
