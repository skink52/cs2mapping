# mg_monsoon: command sheet

The ordered commands and nothing else. Reasons, times and what to look for: [../docs/BUILD.md](../docs/BUILD.md).
Generation (1-8) has been run; compile and launch (10-12) have never been run for this map. AI-generated (Claude) for skink52.

Git Bash, from `C:\source1\cs2mapping\projects\monsoon-cs2\tools`. `WD` wraps anything over 2 minutes (background, own log file):

```sh
P=/c/source1/cs2mapping/projects/monsoon-cs2
WD="python C:/source1/cs2port/autoport/watchdog.py"
export MV_OUT=$P/out/addon
mkdir -p $P/out/logs
```

## 1. Props (about 40 min for all; 10-95 s each)

```sh
$WD --label "mv props" --expect 2400 --heartbeat 120 --stall 600 --max 7200 --log $P/out/logs/wd_props.log -- python -u build_all_props.py
python p_jungle.py                         # flag_pole with skins, after flag_pole_n/_t/_ct
python mv_flag_anim.py ../out/addon        # at once: p_jungle rewrites flag_pole.vmdl without the capture rig (flag_00..20)
python lod_decimate.py ../out/addon ../out/addon mv/bunker_large mv/bunker_small mv/cargo_pallet mv/checkpoint mv/culvert_bunker \
  mv/fdc_bunker mv/fuel_bladder mv/gp_tent mv/guard_tower mv/truss_span mv/guardian_statue mv/naga_balustrade \
  mv/sandbag_w_h1 mv/sandbag_w_h2 mv/sandbag_w_h3 mv/sandbag_w_h4 mv/sandbag_a118_h1 mv/sandbag_a118_h2 mv/sandbag_a232_h1 mv/sandbag_a232_h2
python prop_lint.py                        # 0 bad expected
```
One prop: `python -u build_all_props.py <name> [<name>...]`.

## 2. Apache

```sh
python apache_setup.py ../out/addon
```

## 3. GMod conversions (optional; already in out/addon)

```sh
$WD --label "mv gmod fetch" --expect 1800 --heartbeat 120 --stall 600 --max 5400 --log $P/out/logs/wd_gmod.log -- python -I -u gmod_assets.py fetch
$WD --label "mv gmod convert" --expect 1800 --heartbeat 120 --stall 600 --max 5400 --log $P/out/logs/wd_gmod_conv.log -- python -I -u gmod_assets.py convert
python -I gmod_assets.py view
python -I gmod_assets.py report
```

## 4. Map (3-8 min)

```sh
# first time:  IN=../out/template.vmap      later:  IN=<the live content\csgo_addons\mg_monsoon\maps\mg_monsoon.vmap>, PREV=<last generated vmap>
$WD --label "mv map" --expect 450 --heartbeat 60 --stall 600 --max 1500 --log $P/out/logs/wd_map.log -- \
  python -u make_map.py ../out/template.vmap ../out/addon/maps/mg_monsoon.vmap ../out/addon
python check_mesh.py ../out/addon/maps/mg_monsoon.vmap
python check_world.py ../out/addon/maps/mg_monsoon.vmap
```

## 5-7. Sounds, radar, board, skybox, HUD

```sh
python sounds.py ../out/addon "C:/source1/links/content_addons/addon_template/soundevents/soundevents_addon.vsndevts"
$WD --label "mv radar" --expect 150 --heartbeat 60 --stall 300 --max 600 --log $P/out/logs/wd_radar.log -- python -u make_radar.py ../out/addon ../out/game
python render_board.py ../out/addon
python make_sky.py
python mv_hud.py ../out/addon
```

## 8. Script and tests

```sh
cd $P
node tools/build_script.mjs
node test/mock.mjs 32 600
node test/mock.mjs 4 600
tsc -p test/tsconfig.json
cd /c/source1/cs2mapping
python create/test/api.py --strict --check projects/monsoon-cs2/out/addon/maps/scripts/mg_monsoon.js
sh create/test/tscheck.sh projects/monsoon-cs2/out/addon/maps/scripts/mg_monsoon.js
```

## 9. Deploy (CS2 tools mode closed on mg_monsoon)

```sh
cd $P
python -I tools/deploy_monsoon.py            # dry run
python -I tools/deploy_monsoon.py --apply
```

## 10. Compile assets, then HUD and script (cmd.exe, working folder C:\source1\cs2port)

```bat
cd /d C:\source1\cs2port
python C:\source1\cs2port\autoport\watchdog.py --label "mg_monsoon assets" --expect 1800 --heartbeat 120 --stall 600 --max 5400 --log C:\source1\cs2port\logs\mg_monsoon_assets_watch.log --watch C:\source1\cs2port\logs\mg_monsoon_assets.log -- powershell -NoProfile -ExecutionPolicy Bypass -File C:\source1\cs2port\build_maps.ps1 assets mg_monsoon

set RC="C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\bin\win64\resourcecompiler.exe"
set A=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\mg_monsoon
%RC% -f -i "%A%\panorama\layout\custom_game\mg_monsoon.xml"
%RC% -f -i "%A%\panorama\styles\custom_game\mg_monsoon.css"
%RC% -f -i "%A%\maps\scripts\mg_monsoon.js"
```

## 11. Compile the map (final: 2048 lightmaps, quality 2; 45-60 min estimated)

```bat
cd /d C:\source1\cs2port
python C:\source1\cs2port\autoport\watchdog.py --label "mg_monsoon final" --expect 3600 --heartbeat 120 --stall 900 --max 10800 --log C:\source1\cs2port\logs\mg_monsoon_final_watch.log --watch C:\source1\cs2port\logs\mg_monsoon_build.log -- powershell -NoProfile -ExecutionPolicy Bypass -File C:\source1\cs2port\build_maps.ps1 final mg_monsoon
```

Never: `C:\source1` as the working folder; `--log` pointed at `logs\mg_monsoon_build.log`; quitting CS2 mid-build.
Preview only: `powershell -File C:\source1\cs2port\build_maps.ps1 -DryRun final mg_monsoon`.
Quick first build (1024 lightmaps, quality 1): the same line with `mg_monsoon` in place of `final mg_monsoon`.

Then read `C:\source1\cs2port\logs\mg_monsoon_build.log` for: `OK in N min`, `DELETED`, `Error loading resource` / missing
materials, `Charting N unique meshes`, `Packing N UV charts`, `OUT OF MEMORY`, the nav area count.

## 12. Launch (skink52 starts the game)

```
cs2.exe -addon mg_monsoon -tools -steam -retail -insecure -noassetbrowser -vulkan
map mg_monsoon
```
Console must show `[mv] mg_monsoon script mv-0.1 ... - flags 5, bots on (quota 10)` and no `[mv] missing entity`. Then
[../docs/TESTING_MONSOON.md](../docs/TESTING_MONSOON.md).
