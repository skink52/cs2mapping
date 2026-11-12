# mg_trenchwarfare: state before the remaster (research, 12 Nov 2026)

Read-only survey for the remaster plan. Sources: `NOTES.md` (tw2..tw35), `README.md`, `docs/*.md`, the tools and the script, the map digest of
the user's vmap, both addon folders, the unpack bat and logs in `C:\source1\cs2port`, and the vmap backups. "Simulated" is the strongest claim
made here for anything about the script; nothing was checked in game.

## 0. Headline facts

- **The current vmap is the tw34 delivery, byte for byte.** `content\...\maps\mg_trenchwarfare.vmap` (67,206,918 B, 29 Oct 12:11) has the same
  CRC32 (2e3f90d0) as `C:\source1\cs2port\assets\tw\tw34_map_main.zip`'s vmap. The unpack log shows tw34 applied at 29 Oct 12:19. So the
  user has not saved in Hammer since 29 Oct 12:11. That file is the user's 28/29 Oct save plus `patch_fog.py` and `patch_lightmap.py`.
  A copy is in `backups\remaster_20261112\`, alongside the skybox vmap.
- **The script in the addon is the repo script.** `content\maps\scripts\mg_trenchwarfare.js` (29 Oct 12:56) is identical to `src/mg_trenchwarfare.js`.
  The compiled `game\maps\scripts\mg_trenchwarfare.vjs_c` is older (28 Oct 23:55) and the map vpk is from 29 Oct 12:39. **tw35 (BOTS_ON false) has
  never been compiled.**
- **No exact pre-edit baseline exists for `vmapgen.EditKeeper`** (section 7). The `out/` folder was lost in the 27 Oct handover, along with
  `gen_twN.vmap` and `user_edits.json`. Usable stand-ins are in `content\csgo_addons\prefabs+backups\`.

## 1. Features today (src = `src/mg_trenchwarfare.js`, 1305 lines)

| Feature | What it does | Where |
|---|---|---|
| Lobby -> deploy | Everyone spawns in the briefing room at z -2892 (32 T + 32 CT spawns) and is teleported to a post after `LOBBY_FIRST` 4 s or `LOBBY_RESPAWN` 1.5 s | src:25-26, `deploy` src:366, `pickTrench` src:348 |
| Role choice | On respawn: bots are always infantry. `!pref` comes first, then `MORTAR_CHANCE` 0.4, `ROTATE_CHANCE` 0.12, and `AIR_CHANCE` 0.12 + merit (+0.08 before a first flight). A chat request switches now or queues | `chooseRole` src:294, `requestRole` src:322, `airFree` src:316 |
| Infantry | Gets the team rifle and pistol, armour 50. The rifle is weapon_awp (Gewehr 98) for T and weapon_ssg08 (Lee-Enfield) for CT; the pistol is glock (Luger) or hkp2000 (Colt). A 3-kill streak gives g3sg1 (Mondragon) or scar20 (Lewis). `!swap` / SHIFT+E toggles weapons. Dressing stations heal 12 hp/s and 25 armour/s within 120 u | CONFIG src:29-37, `equip` src:335, kill handler src:1228-1251, `swapRifle` src:829, heal src:1148 |
| Mortar crews | 5 crews x 2 per side. Seat a works the plotting table, seat b the ammo box. The crew plots on a top-down sight (192 steps, A-P/1-16 grid), loads, then fires. Shells are simulated: gaussian spread 70 + 0.035/u, flight 2.2 s + d/1500, radius 330, 170 damage, x0.35 behind cover (trace). There is a whistle, a launch sound, an fx pool of 12, and shakes. The loader deals >= 55 non-lethal damage first to earn an assist | `tickMortar` src:1015, `fireMortar` src:914, `impact` src:942 (assist src:964), `drawSight` src:1071 |
| Biplane pilots | 5 planes per side (SPAD VII CT, Dr.I T), 2 lives, posted on respawn or by `!air` and air-spawned 1100 above their field. Arcade mouse-aim flight was ported from Dogfight in tw33: steerAim, turnRate, free A/D roll, bounds blend, PULL UP look-ahead. Guns: 500 rounds, 16 damage, converge on the crosshair. 2 bombs (radius 420, 240 damage, rearm 18 s). Tracers, gun pip, a one-sided bomb-sight ring, spinning props, engine and gun sounds, smoke below 45 hp. Touching the ground is a crash. Rifle hits on a plane hurt the pilot (x0.4) | aircraft section src:398-887 (`startFlight` 551, `tickAir` 659, `drawFlight` 810, `tickBombs` 873), `OnBulletImpact` src:1270 |
| HUD | One `custom_hud_layout` `tw_hud` with 69 panel ids: role brief, status, toast, info card, banner, prompt, mortar sight (map, pit, 3 impacts, lock, reticle), and flight dash with bank/ASI/alt/rpm dials, counter and bomb lamps. A per-player cache sends only changes | src:194-243. Built by `tools/tw_hud.py` + `tools/tw_cockpit.py` -> `panorama/layout|styles/custom_game/mg_trenchwarfare.xml|css` |
| Radar | Overview `pos -4300/4700, scale 8.40` with a 1024 px vtex. `!pos` prints position and grid square to check the alignment | `tools/make_radar.py`, CONFIG.RADAR src:23, `!pos` src:1284. Game: `resource/overviews/mg_trenchwarfare.txt` |
| Unlocks | `woodsopen` opens at 15 kills or 240 s, `undergroundopen` at 30 kills or 480 s. The script runs effects + Remove on the blockers and announces it in chat. Map entities return each round | CONFIG.UNLOCKS src:87-90, `tickUnlocks` src:848 |
| Uniforms / arms | `SetModel` 0.25 s after spawn, chosen by slot: T tw_de_a/b, CT tw_gb_a/b. `!uniform` opts out. Arms: stock T and CT gloves inside Tripo sleeves (tw30) | CONFIG.UNIFORMS src:78-81, `uniform` src:603 |
| Bots | Off by default (`BOTS_ON false`: `bot_quota 0` + `bot_kick`). When on, a leash teleports a bot that loiters 3 s near a closed blocker back to a fire-trench post | src:97-99, src:1195, `tickBot` src:286 |
| Ambience | Cosmetic no man's land bursts every 4-13 s, at least 550 u from players | `tickAmbient` src:861 |
| Rounds / score | Respawn deathmatch, `mp_roundtime 60`, no script-side win condition or team score. Per-player kills/merit are used only for role draws | CVARS src:91-93 |
| Chat | `!infantry/!rifle`, `!mortar/!artillery`, `!air/!pilot` (each shows the orders card), `!roles`, `!swap`, `!pos`, `!uniform`, `!random` | src:1276-1305 |

Weapons (`docs/weapons_handover.md`, built in the `testing` addon by `tools/weapons/` in cs2mapping): `content\scripts\weapons.vdata` and
`models\weapons\ww1\{colt_m1911,gewehr98,lee_enfield,lewis_mk1,luger_p08,mondragon_m1908}` (68 files). **The Gewehr 98 mesh is a BF1 rip and
must be replaced before Workshop.**

## 2. How the map is made and delivered

- **Generator:** `tools/make_map.py <user vmap> <out> <addon> [prev generated vmap]` (1447 lines) writes the whole map, terrain included, into vis
  group `tw_gen`. It covers terrain tiles with vertex-paint blends, trench pools, parapets, trench furniture, NML scatter, mortar pits, airfields and
  propellers, woodland, fog, spawns and heal points, the lobby with its banner, script/HUD/fx pools, environment and probes, sky shell and vis hints,
  mine tunnels, the woods skirmish, and lightmap volumes. Its layout constants are in `tools/layout.py` (XS 2150 support trench, 15 bays of 384,
  mortars at x +-3200, hangars at +-6150, tunnel floor -260). The keeper logic is built in (lines 29-83): user-moved generated objects are
  re-tagged `tw_user` and the originals they replaced go in `out/user_edits.json`.
- **rng issue:** one global `RandomState(1916)` drives 81 `rng.` calls, plus fixed seeds 77, 1915 and 1918 for pools, tunnels and the skirmish. User
  edits register as placer obstacles, so every later random draw shifts. tw20 found ~450 generated objects reshuffled. From tw20 on, every map change
  was a delta patch on the user's vmap (`patch_vmap.py`, `patch_uniforms.py`, `patch_unlocks.py`, `patch_bots.py`, `patch_fog.py`,
  `patch_lightmap.py`). Per-section rng is still a TODO. The last full regeneration was tw18 (git 770d831, 26 Oct 16:13).
- **Delivery:** numbered zips `twN_content_NN.zip` / `twN_map_main.zip` / `twN_game.zip` (each < 20 MB; 25 MB+ uploads failed) go to
  `C:\source1\cs2port\assets\tw\`. `C:\source1\cs2port\unpack_mg_trenchwarfare.bat` refuses to run while cs2.exe is up, backs up both vmaps
  (timestamped) to `content\csgo_addons\prefabs+backups\` (on E:), tar-extracts each zip once (loop tw2..tw99), logs to
  `logs\mg_trenchwarfare_applied.txt`, compiles the HUD xml/css, and offers `build_maps.ps1`. Until tw20 a trailing space in the applied
  list made every zip from tw7 on re-extract on every run. The applied list shows tw7..tw18 repeated, and older map zips may have overwritten
  newer states. tw32_map_main was never applied (superseded by tw34). Only tw34's two zips remain in `assets\tw`, beside the Tripo GLBs. Some
  deliveries (tw25-tw30 arms, tw31 LODs, tw35 script) were written straight into the addon.
- **User's Hammer edits** (NOTES tw6, tw7, tw26 and the vmap): 12 revetments on the shelter niche walls, a moved field telephone, 2 widened
  puddles, skirmish ladders at y 2904 (pitch -4) with their own toolsinvisibleladder meshes, `skybox_reference` at (0,0,0), 2 moved skirmish
  trees, 10 wire coils + 10 fences along the track, and their own random-explosion system (logic_auto, logic_timer -> logic_case PickRandom ->
  13 `env_explosion` explosion1..5, magnitude 100, damage on, all in no man's land |x| < 860). They also made the `woodsopen`/`undergroundopen`
  blockers and the 3D skybox map (light_environment, env_sky, sky_camera; content filled by `make_skybox.py`). The 2 `func_brush` at x +-1612,
  y -74 and 19 stock props (aztec rocks, barrels, crates, wheelbarrows, lanterns) are also theirs.
- **Vis groups in the current vmap:** tw_gen 6563 entities + 1304 meshes; tw_user 63 entities + 2 meshes; ungrouped (user) 40 entities + 5 meshes;
  tw_nav 25; woodsopen 2; 1 CMapNavData. tw_user has stayed at 63 since 26 Oct 16:57. **Edits the user made after tw18 to objects inside tw_gen
  carry no tag at all.**

## 3. Map digest (`python tools/mapdigest.py <vmap> --summary`, plus --class/--graph)

- 6693 entities, 1346 meshes, bounds x +-7424, y +-6400, z -2900..6400. Classes: prop_static 6124, prop_dynamic 128, point_soundevent 75,
  info_teleport_destination 70, light_omni2 63, info_particle_system 57, info_player_terrorist 32 / counterterrorist 32, func_nav_markup 25,
  info_target 16, env_combined_light_probe_volume 15, env_explosion 13, env_shake 12, visibility_hint 12, info_map_parameters 2, func_brush 2,
  and 1 each of logic_auto/timer/case, team intros, team_select, end_of_match, point_script, custom_hud_layout, light_environment, env_sky,
  env_cubemap_fog, post_processing_volume, env_soundscape, skybox_reference.
- **No triggers of any kind, no cs_minimap_boundary** (removed tw19), no func_bomb_target (removed tw27). The I/O graph is only the user's timer ->
  case -> explosion wiring. There are no dangling targets. Duplicate names: explosion1..5 (13 entities; OnCase06 fires `explosion*`),
  woodsopen x2 and undergroundopen x2 (intended).
- **Script-used names, all present:** trench_t/ct_1..20 (info_teleport_destination; the script header still says point_teleport), heal_t/ct_1..3,
  mortarpit_t/ct_1..5 (info_target at x +-3200), mortarcrew_<tg>_K_a/_b, plane_<tg>_1..5, tw_plane_<tg>_1..5 (prop_dynamic *_dyn.vmdl),
  tw_prop_<tg>_N, tw_bomb_<tg>_N_1..2, tw_tracer_<tg>_N_1..6, tw_bombsight/gunsight_<tg>_N, tw_plane_eng/gun/gun2/gun3_<tg>_N,
  tw_plane_smoke_<tg>_N, tw_boom_fx/dirt_fx/boom_snd/whistle_snd/tw_shake_1..12, tw_launch_snd/fx_<tg>_1..5, tw_uniform_1..4 (precache),
  tw_hud, tw_script, tw_params, tw_skybox, tw_sun, probes (lobby, bf, far_1..10, air_1..2, tunnel).
  **`mortar_<tg>_K` does not exist**: the mortars are prop_static (mortar_58mm x5 CT, minenwerfer x5 T), so `SetAnimation fire` (src:921) goes nowhere.
- **Spawns:** 32 + 32 in the lobby (x -600..600, y -420..160, z -2892). The point_script and HUD sit at z -2800.
- **Nav/bots:** 25 WALKABLESEED `func_nav_markup` (tw_nav: lobby, trench posts 1/5/8/12/15/16/18/20, woods clearing, tunnel landings, chamber). The
  compile gave 44,160 nav areas, with "Unconnected ladder #1/#2 bottom" at the woods ladders (+-1716, 2904, -72). Bots caused a frame hitch every
  ~0.5 s on a listen server, so they are off (tw35). Not verified: whether the blocker prop_dynamics cut nav, and the ladder links.
- A second, untagged `info_map_parameters` at (512, 328, 32) is still in the map (NOTES tw27).
- Props: 141 distinct models. 97 are ours (3447 instances), the rest stock (2805: poplar/maple vistas ~1100, nuke foliage, dogwood, weeds).
  prop_static bakelighting: 2727 lightmapped, 3378 probed, 19 default.

## 4. Script and tests

- `src/mg_trenchwarfare.js`: 1305 lines, 74.7 KB, one file. Sections: settings 20, helpers 104, state 170, HUD 194, roles 244, deploy 334,
  aircraft 398-887, mortars 888-1091, per tick 1092 (`think` 1096, `thinkPlayer` 1110), events 1192-1305.
- Every call goes through `Instance.*`: FindEntityByName 9, TraceLine 7, ServerCommand 4, Msg 4, SetNextThink 3, GetPlayerController 3,
  SetThink 2, FindEntitiesByName 2, EntFireAtName 1, GetGameTime 1, and 8 `Instance.On*` hooks.
  `python create/test/api.py --check` (and `--strict`): 0 invalid, 0 deprecated, **5 allowed by api_allow.txt** (baseline, "not yet moved").
  Those are EntFireAtName src:120, ServerCommand src:121, FindEntityByName src:127, FindEntitiesByName src:134 and Msg src:167, one line
  reported per call. The rest are wrapped in `fire()`/`say()`. `sh create/test/tscheck.sh`: **OK**.
- `test/mock.mjs` (174 lines) is a stand-in engine. It fails on a thrown error, an unknown HUD panel, a missing CSS class, or SetModel to a missing
  model. It needs `out/entities.json` and `out/addon/panorama/...xml|css`, which were lost, and it **does not run on Windows as written**: line 7 uses
  `new URL(import.meta.url).pathname`, which gives `C:\C:\...`, and line 97 does `import()` of a bare absolute path. In a scratch copy I staged
  `dump_entities.py` from the current vmap (446 entities), the addon's HUD xml/css and the 4 uniform vmdls, and fixed both lines with
  `fileURLToPath`/`pathToFileURL`. **`node test/mock.mjs 32 120` was clean in ~4 s:** errors [], 50 kills, 79 SetModel, 6 flights (avg 40.5 s),
  34 plane hits, 7786 mortar fire attempts, leashOk 7, points "trench 20/20, heal 3/3, plane spawns 5/5, aircraft 5/5". The repo files are unchanged.
- `test/point_script.d.ts` (shared libsync copy) and `test/tsconfig.json`. There is no per-bug-class scenario, balance sim or coverage table.

## 5. Assets

**Tools** (`tools/`, one line each):
make_map (whole vmap) · layout (shared layout constants) · placer (prop footprints, spatial hash) · vmaplib / vmesh / dmx / dmx9 (vmap writing) ·
check_mesh · dump_entities (mock input) · patch_vmap / patch_uniforms / patch_unlocks / patch_bots / patch_fog / patch_lightmap (delta patches on the
user's vmap) · make_radar (radar + overview) · render_top (mortar sight screens, crops make_radar's `out/radar_clean.png`) · make_skybox (1/16 terrain
ring + ~4000 vista trees) · tw_hud / tw_cockpit (HUD + dial art) · sounds (synth mortar sounds + vsndevts) · build_all_props / build_prop (bake one prop:
LODs, atlas, vmat, vmdl, hulls) · bake / shaders / geo / noise / render (object-space PBR baking, preview renderer) · stock (map chart materials to
Valve materials) · modelio (SMD/vmat/vmdl writer, LOD_SCALE 16, SINGLE_LOD) · lod_decimate (LOD1-4 by clustering + quadric, `--lightmapped-from`) ·
clean_stale · p_trench / p_sandbag / p_wire / p_trees / p_wreck / p_misc / p_trenchlife / p_minenwerfer (procedural prop specs) · glb2cs2_multi /
ext_smd / weather_ext (Sketchfab GLB -> props, weathered aircraft atlases) · split_props (propellers out of plane SMDs) · fx_models (bomb, tracer,
sights) · soldiers / arms / glbskin / dmx9 / weld_cracks / preview_soldier (Tripo GLB -> agent player models) · agent_gloves / fit_gloves /
bare_hands (first-person gloves in our sleeves) · vpkdir / vtexread (look at stock vtex) · preview_scene / fp.sh (map previews) · toolkit.json
(prop modules, single_lod list, fx and skybox config). The shared copies are listed in README "Shared files".

**Addon content** (`links\content_addons\mg_trenchwarfare`, recursive file counts): maps 4 (main vmap, 3dskybox vmap 9.2 MB, scripts/js,
content_examples/lighting_info.vmap template leftover) · models 531 (tw 463 in 78 folders incl. ext 13 and players 9; weapons 68): 112 vmdl,
348 smd, 68 dmx, 3 json · materials 926 (687 png, 239 vmat) · panorama 24 (20 HUD pngs, radar png+vtex, xml, css) · sounds 11 (3 tw wavs:
mortar_launch, mortar_whistle, plane_engine; 6 bird + interior + vent from the template) · soundevents 1 (tw.mortar_*, tw.plane_*,
tw.ambient_blast, tw.amb.* soundscape on stock vsnds) · scripts 1 (weapons.vdata) · postprocess 2 · backups 14 (Tripo arms + remaster
backup) · CREDITS.txt (13 Sketchfab CC BY 4.0 models) · use_stock_arms.bat.

**Addon game** (`links\game_addons\mg_trenchwarfare`): maps 6 (mg_trenchwarfare.vpk **525.6 MB**, 29 Oct 12:39; 3dskybox.vpk 89 MB;
txt/cameras/retakes) · models 112 vmdl_c · materials 716 · panorama 22 · sounds 11 · resource/overviews 1 · scripts 1 (vdata_c) · cfg 2 ·
postprocess 2 · _vrad3 74 · _bakeresourcecache 4 · addoninfo.txt (empty kv3) · ServerConfig.vdf (bot_quota 0).

**Known weak or risky assets:**
- Gewehr 98: BF1 rip.
- Tripo arms looked bad (tw28); tw_de_a has its weights copied from a donor rig, and 199 open strap edges remain after weld_cracks (tw31).
- Ext CC-BY props have no authored LODs (Renault FT 54.8k tris / 12.8k charts, Stahlhelm 27.5k, petrol can 28.9k).
- Generator UV islands inflate lightmap charts (revet_iron_128 550 per instance, sandbag_wall_128 188, duckboard_128 162).
- Single-LOD props: shattered trees, tunnel_set, hangar, stumps, log, shelter, wire_coil, wreck_tank.
- Sandbags, wire, wrecks and helmets are still baked rather than stock-textured.
- Only 3 custom sounds; the plane gun is m249.
- `wooden__spike__barricad_3d_model_free.glb` in `C:\source2\projects\trenchwarfare` is unused.
- Planned GLB sources (Sketchfab, weapons) are in `C:\source2\projects\trenchwarfare`.

## 6. Open issues and bugs (cause as NOTES gives it)

1. **Radar alignment:** unconfirmed in game. tw18 moved cs_minimap_boundary to the image corners, and tw19 removed it because CS2 drew its own lobby
   minimap from it. tw21 rebuilt the radar on the validated cs2port conventions (1024 px, pos = top-left, scale 8.40). The way to check is
   `!pos` against where the dot is drawn. The open item is still listed in "Status 27 Oct".
2. **Mortar crew dies on firing:** cause not found in the script. tw13 added the `OnModifyPlayerDamage` guard (src:1254): within 320 u of their pit,
   crews only take enemy damage, and blocked hits are logged as `[tw] blocked ...`. The next step is the console line from a playtest. The user's
   env_explosions are > 2300 u from every pit, so they are ruled out. Own shells skip teammates (`FRIENDLY_SPLASH false`).
3. **Mortar assist credit:** tw18 has the loader deal a non-lethal share (>= 55) before the firer's damage (src:964) so CS2 counts an assist.
   Not confirmed in game.
4. **Giant first-person weapons:** tw13/14 found the stock AWP was huge too. The suspect was `SetColor` render-mode changes in `hidePawn`, so tw14
   made it scale-only. tw16/17 removed agent SetModel entirely after it drew the local body in first person. **tw25 reintroduced SetModel**
   (uniforms on an agent template). After that the user only reported arms quality (tw28-30), not big weapons. Status: no recorded repeat,
   but no explicit check either.
5. **FPS:**
   - Looking over no man's land: ~17M prop triangles because LOD1 never switched (LOD_SCALE 16). tw31 decimated LODs, which raised the
     lightmap chart count 3.9M and caused the tw34 OOM. tw34 shared corners per cluster: the build packs 1.37M charts, 2048 lightmap, 19 min.
   - The real fix was taking out the fog particles: `r_drawparticles 0` cured the drop, and tw32/tw34 removed 19 fog sprites (none left in the map).
   - Next suspects if drops remain: 13 always-on smoke columns, ~1100 vista trees, and every prop casting shadows.
6. **Bot hitch:** a drop to 71 fps every ~0.5 s with bots on 44k nav areas. `bot_kick` fixed it, so `BOTS_ON false` (tw35, not yet compiled).
   The woods ladders have no nav link.
7. **The rng cascade** blocks full regeneration (section 2).
8. Minor:
   - The stale script header says point_teleport.
   - `SetAnimation` goes to a missing `mortar_<tg>_K`.
   - The second info_map_parameters is still in the map.
   - `build_maps.ps1` bakes at lightmapMaxResolution 1024; NOTES says to build this map in Hammer at 2048.
   - The mortar sight `TARGET_EXT 4600` depends on render_top output.
   - tw33 flight feel is mock-only.
   - tw26 bomb sight and unlocks are mock-only.

## 7. Risks for a remaster

- **Edits without a baseline.** There is no exact "what the user was given" vmap for the post-tw18 era. Candidates in
  `links\content_addons\prefabs+backups\` (on E:). In unpack order, a backup whose mtime is earlier than the previous unpack was written by an
  unpack (never saved in Hammer):
  - `mg_trenchwarfare_20261026_1051.vmap` (03:22, pure tw2 generation: 3 ungrouped entities, no tw_user).
  - `_1408` (13:37, ~tw9 output).
  - `_1544` (14:52, ~tw12).
  - `_1615` (15:38, ~tw13; tw_gen 6471, tw_user 51).
  - The tw18 output (extracted ~16:15) was not kept. `_1705` (16:57) is the user's save of it, and `_1552` (15:46) is the user save that tw18 was
    probably built from.
  - Possible rebuild of the exact tw18 baseline: `make_map.py` at git 770d831 with `_1552` as input and `_1615` as prev. Untested: it also needs
    the lost `out/user_edits.json` and `out/prop_hubs.json`, and the seeds must reproduce.
  - Otherwise treat today's vmap as the baseline and patch deltas only. The untagged edits inside tw_gen cannot be told apart by any diff.
- **Out-of-repo state lost on 27 Oct:**
  - `out/` (gen_twN.vmap, user_edits.json, `prop_hubs.json` for make_map, `radar_region.json` + `radar_clean.png` for render_top,
    `ext_src`/`ext_full` aircraft sources for weather_ext/split_props, entities.json, the `out/addon` build, props.json).
  - Container paths are hardcoded: vtexread `/mnt/user-data/uploads/game/csgo`, preview_scene `/tmp/claude-...`, toolkit.json
    `stock_preview_dir /tmp/claude-0/stockprev`, sync_repo.sh default `/home/claude/cs2mapping/...`, and render_top `../out/addon|game`.
    README commands say `python3`.
- **The addon is the only full copy of the built assets.** Models, materials and textures are not in git. A tools rebuild needs the GLBs
  (`C:\source2\projects\trenchwarfare`, `cs2port\assets\tw`), the Octodad template from mg_mario_party, and stock pak01 exports.
- **Deploy hazards:**
  - The user edits in Hammer, so never deploy into an addon that `cs2.exe -tools` has open.
  - The 67 MB vmap is over the 30 MB direct-write limit noted in tw27; that was in the old workspace and may not apply on the PC.
  - The unpack bat applies every unapplied `twN_*` zip in `assets\tw` in order, so stray zips with new numbers will apply.
- **Compiled vs source drift:** the game vjs_c and vpk predate tw35. The game models (112 vmdl_c) match the content vmdl count.
- **User systems to preserve:** the explosion timer/case set, the skirmish ladders + func_brush ladder volumes, the blockers' vis group
  `woodsopen` and the ungrouped undergroundopen, skybox_reference at 0,0,0, and the 3D skybox map.
- **Licensing:** Gewehr BF1 rip; 13 CC-BY Sketchfab models need credits kept (CREDITS.txt); Tripo soldier and arms GLBs.
- A sibling note, `docs/research/MONSOON_STANDARD.md`, already exists in this folder (not written by this survey).
