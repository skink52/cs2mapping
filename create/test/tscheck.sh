#!/bin/sh
# Type-check cs_script files against Valve's point_script.d.ts:  sh tscheck.sh <script.js> [more.js ...]   (needs: npm i -g typescript)
here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
files=""
for f in "$@"; do files="$files\"$(cd "$(dirname "$f")" && pwd)/$(basename "$f")\","; done
cat > "$tmp/tsconfig.json" <<JSON
{ "compilerOptions": { "allowJs": true, "checkJs": true, "noEmit": true, "target": "es2022", "module": "es2022", "moduleResolution": "bundler",
  "strict": false, "noImplicitAny": false, "skipLibCheck": true, "paths": { "cs_script/point_script": ["$here/point_script.d.ts"] } },
  "files": [${files}"$here/point_script.d.ts"] }
JSON
tsc -p "$tmp/tsconfig.json"; rc=$?
rm -rf "$tmp"
[ $rc -eq 0 ] && echo "tscheck: OK"
exit $rc
