#!/bin/sh
# Rebuilds the Hellmatch ZE addon sources from the Freedoom checkout into out/addon (content) and out/game (game folder
# extras). Levels: every ze/<map>.json (or HZE_LEVELS=map01,e1m1). About 6-8 minutes on the PC (the OPL music render
# is most of it on the first run; it is cached in build/music). Run it under the hang watchdog (see the project README).
#   PYTHON=python (default; python3 may be the Windows Store stub)   FREEDOOM_DIR (default C:/source1/freedoom)
#   HZE_SPRITES=1 rebuilds the sprite models with sprites.py instead of reusing Hellmatch's
set -e
cd "$(dirname "$0")/.."
PY=${PYTHON:-python}
export FREEDOOM_DIR=${FREEDOOM_DIR:-C:/source1/freedoom}
export PYTHONIOENCODING=utf-8
step() { echo "== $(date +%H:%M:%S) $*"; }
rm -rf out/addon out/game && mkdir -p out/addon/maps out/game build

step "levels (convert once, place twice) + sidecars"
$PY tools/convert.py out/addon ${HZE_LEVELS:-}
step "core test module"
node tools/build.mjs
node -e "
const C=require('./build/core_test.cjs');
const hud=new Set(['PUNG','PISG','PISF','SHTG','SHTF','SHT2','CHGG','CHGF','MISG','MISF','SAWG','PLSG','PLSF','BFGG','BFGF','ZIMP','ZIMF','ZDMN','ZSKL']);
const w=new Map(), h=new Set();
for (const st of C.STATES) { if (st.name==='NULL') continue; const k=st.sprite+'_'+(st.frame < 26 ? String.fromCharCode(97+st.frame) : String(st.frame-26)); if (hud.has(st.sprite)) h.add(st.sprite+String.fromCharCode(65+st.frame)+'0'); else w.set(k,(w.get(k)||false)||st.bright); }
require('fs').writeFileSync('build/world_frames.json', JSON.stringify([...w.entries()]));
require('fs').writeFileSync('build/hud_frames.json', JSON.stringify([...h].filter((n)=>!/^Z(IMP|IMF|DMN|SKL)/.test(n))));
"
step "sprite models"
if [ -n "$HZE_SPRITES" ]; then
  $PY tools/sprites.py out/addon build/world_frames.json
else
  $PY tools/hm_assets.py sprites out/addon build/world_frames.json
fi
step "HUD strings, zombie view art, HUD"
$PY tools/hud_strings.py build/hud_strings.json
$PY tools/zviews.py build/zviews --sheet preview/zviews_sheet.png
$PY tools/hud.py out/addon build/hud_frames.json
step "music"
$PY tools/music.py out/addon
step "sounds + sky"
$PY tools/extras.py out/addon SKY1
step "loading screens, radar, overview, icon"
$PY tools/loading.py out/addon out/game
$PY tools/lobby.py
$PY tools/vmf.py out/addon
step "map"
TEMPLATE=${HZE_TEMPLATE:-ref/mg_freedm_template.vmap}
MAP=$($PY -c "import sys; sys.path.insert(0, 'tools'); import names; print(names.MAP)")   # mg_hellescape
$PY tools/merge_snd.py ref/soundevents_addon_template.vsndevts out/addon/soundevents/soundevents_addon.vsndevts --tag FreeDM
$PY tools/vmap.py "$TEMPLATE" build/map_base.vmap out/addon
$PY tools/vmap_env.py build/map_base.vmap out/addon/maps/$MAP.vmap out/addon
step "script"
node tools/build.mjs
for f in README_HELLESCAPE.md TESTING_HELLESCAPE.md; do [ -f "$f" ] && cp "$f" out/addon/; done
cp test/types/point_script.d.ts out/addon/maps/scripts/ 2>/dev/null || true
cp "$FREEDOOM_DIR/COPYING.adoc" out/addon/FREEDOOM_LICENSE.txt
cp "$FREEDOOM_DIR/CREDITS" out/addon/FREEDOOM_CREDITS.txt
# the Workshop upload carries the compiled GAME folder, so the licence and credits go there too
cp LICENSE LICENSE-CC-BY-NC-4.0.txt out/addon/FREEDOOM_LICENSE.txt out/addon/FREEDOOM_CREDITS.txt out/addon/MUSIC_CREDITS.txt out/game/
for f in README_HELLESCAPE.md; do [ -f "$f" ] && cp "$f" out/game/; done
step "copy plan (Hellmatch compiled files that can be reused)"
$PY tools/hm_assets.py plan out/addon --out build/copy_plan.json
step "done"
