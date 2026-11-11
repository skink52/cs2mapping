#!/bin/sh
# Run every ported map's cs_script through the stand-in engine (create/test/mock_point_script.mjs): a SIMULATED run, not CS2.
# It catches exceptions in the script's callbacks and known CS2 pitfalls; it does not prove anything works in game.
#   sh ci/mock_ports.sh [players=8] [seconds=30]
# Exit 0 when every script ends with "OK", 1 otherwise (each failing script and the tail of its output are listed).
cd "$(dirname "$0")/.." || exit 2
fail=0; n=0
for f in ports/*/scripts/*.js; do
  n=$((n + 1))
  out=$(node create/test/mock_point_script.mjs "$f" "${1:-players=8}" "${2:-seconds=30}" 2>&1)
  if [ $? -ne 0 ]; then fail=$((fail + 1)); echo "FAIL $f"; echo "$out" | tail -n 12 | sed 's/^/    /'; fi
done
echo "mock_ports: $n scripts, $fail failed (simulated engine, not CS2)"
[ "$fail" -eq 0 ]
