#!/bin/sh
# Copy generator source from a working folder into the git checkout (outputs and previews stay out of git).
# Safe against stale working folders: nothing in the checkout is deleted, a file is copied only when the working copy is
# newer, and repo-owned files are never copied: README.md, NOTES.md, the licences, and the shared files mastered in
# cs2mapping (create/libsync.json - change those there and run libsync.py push).
# usage: sh sync_repo.sh [checkout=/home/claude/trenchwarfare-cs2]   (run from the working folder's copy of this script)
cd "$(dirname "$0")" || exit 1
R=${1:-/home/claude/trenchwarfare-cs2}
[ "$(cd "$R" && pwd -P)" = "$(pwd -P)" ] && { echo "this is the checkout itself - nothing to sync"; exit 0; }
[ -d "$R/.git" ] || { echo "no git checkout at $R"; exit 1; }
cd "$R" && git pull -q --rebase --autostash && cd - >/dev/null || { echo "git pull failed in $R - sync stopped"; exit 1; }
SHARED=$(python3 -c "import json,sys;print('\n'.join(v['trenchwarfare-cs2'] for v in json.load(open(sys.argv[1]))['copies'].values() if 'trenchwarfare-cs2' in v))" "$R/../cs2mapping/create/libsync.json" 2>/dev/null)
[ -n "$SHARED" ] || echo "note: cs2mapping/create/libsync.json not found next to $R - shared files are copied like any other"
n=0
for f in $(find tools src test docs -type f ! -path '*/__pycache__/*' ! -name '_run.mjs' ! -name '_perf.mjs' 2>/dev/null) sync_repo.sh; do
  echo "$SHARED" | grep -qx "$f" && continue
  [ -e "$R/$f" ] && { [ ! "$f" -nt "$R/$f" ] || cmp -s "$f" "$R/$f"; } && continue
  mkdir -p "$R/$(dirname "$f")" && cp -p "$f" "$R/$f" && n=$((n + 1)) && echo "  $f"
done
echo "$n file(s) copied; README.md, NOTES.md and licences are edited in the checkout only"
