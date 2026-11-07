# create/playermodels: GMod player models -> CS2 player models

> **AI-generated code.** Written by Claude for skink52. MIT, like the rest of the repo. The workflow, the choices behind it and the
> first batch are in [docs/creation/gmod-playermodels.md](../../docs/creation/gmod-playermodels.md).

Python 3 with numpy and Pillow. No Blender, Crowbar or SourceIO needed: the Source 1 formats are read here. Run with `python3 -I`
(the inputs are downloaded files); each tool puts its own folder on the path.

| File | What it does |
|---|---|
| `pipeline.py <catalog.json> [--only slug,..] [--batch=N[,M]] [--no-download] [--no-preview] [--compile] [--jobs N] [--timeout S]` | The batch: every `chosen` catalog item downloaded, extracted, converted, previewed (incl. the hands check), compiled with `resourcecompiler`, reported (`<work>/reports/<slug>.json`, `summary.md`, `preview/contact_sheet.png`). One model failing doesn't stop the rest. |
| `browse.py <catalog.json> [--out f.json] [--all]` | Workshop items tagged Model that aren't in the catalog: top rated (7/30/90/365 days) and "playermodel" searches, from the item list the browse pages embed. Prints the ones that look like player models (id, size, subscribers, title, author); all go to `<work>/logs/candidates.json`. Downloads nothing. |
| `fetch.py <catalog.json> [--only id,..] [--no-download] [--scan] [--suggest]` | SteamCMD (anonymous) `workshop_download_item 4000 <id>`, then extracts `models/`, `materials/`, `lua/`. `--scan` lists every `.mdl` per item with its registered name (`player_manager.AddValidModel`, read as text), ValveBiped yes/no, height, head-joint height, a size-check scale (CS2 head joint / the model's) and the VMTs and colour VTFs missing from the item, into `<work>/logs/scan.json`. `--suggest` lists, per item, the models that pass the selection rules. |
| `gmod2cs2.py <model.mdl> <slug> --roots <dir,..> --template <dir> --out <content addon> [--skin N] [--bodygroup part=i] [--maxtex 2048] [--preview dir] [--report json] [--fit]` | One model: uniform scale only (no stretching), limbs turned into CS2's bind pose at their own lengths and skinned to the CS2 agent skeleton (`--fit`: the old stretch-onto-CS2-bones method), weights remapped (twist bones included), materials converted, body DMX written into a copy of the template's, vmdl from the template's with the paths swapped. Previews: `_source` (GMod pose), `_bind` (on the CS2 skeleton, joints dotted), `_posed` (skinned to the template's preview pose). |
| `poses.py` | Still poses for review (CS2's shooting pose, run, crouch, arms up, twist) on the skeleton a model is skinned to; the converter writes `<slug>_poses.png` with every model. |
| `handcheck.py <model.mdl> <template> <out.png>` | Close-up of both hands in CS2's preview pose and both wrists bent back 60° (rifle grip): where conversions break first. The pipeline writes `preview/<slug>_hands.png` per model; look at it before shipping. |
| `fit_hitboxes.py <catalog.json> [--only s,..] [--batch N] [--compile]` (or `--model m.mdl --vmdl v.vmdl --template dir`) | Moves converted models' head hit box onto their actual head (and the neck half as far), in place, from the template's own capsules (re-runnable). The converter does this too; this is for models converted before. |
| `hitboxes.py <template> <model.mdl>...` | Hit box fit: share of each body group's mesh outside every capsule, and the head-centre offset; the stock body as baseline. |
| `cleanup.py <catalog.json> [--prune] [--unchosen] [--dry-run]` | Frees disk: SteamCMD copies of catalog items, extracts of unused items, and with `--prune` every file in used items the chosen models don't need. Only catalog ids are touched. `--unchosen`: only the converted files of models no longer chosen (dropped in review). |
| `dupes.py <catalog.json>` | Possible duplicates: the same character from different items (names compared without packaging words). Scores each by quality (vertices, no flat textures) + Workshop ratings (lifetime subscribers and favourites, Steam's public details API) and writes `possible_dupes` into the catalog: MODELS.md and the server catalog flag them in the warnings. Duplicates are kept. `"distinct": true` marks another look of a character. |
| `batchnotes.py <catalog.json> <batch>` | Rebuilds `BATCH<n>.md`'s table from the reports, keeping the hand-written review below its marker. |
| `listmodels.py <catalog.json>` | Rebuilds `MODELS.md`: every converted model with a picture in CS2's pose (`img/<slug>.jpg`, cut from the posed preview), its CS2 path, source, status, warnings. Also `GALLERY.md` (picture grid, A-Z, fun skins first) and `img/poses/<slug>.jpg` (front view in every still pose). |
| `srcmdl.py <model.mdl>` | Source 1 studio model reader (MDL v44-49 + VVD + VTX v7): reference-pose bones, LOD0 skinned mesh, body parts, skin families, eyeballs. Prints a summary. |
| `vtf.py <in.vtf> <out.png>` | VTF 7.0-7.5 mip 0 decoder (DXT1/3/5 via Pillow, the 8-bit, 565, 4444, 5551 formats here) and a VMT reader (`patch` resolved). |
| `fbx_export.py` (Blender: `blender -b --factory-startup -P fbx_export.py -- <in.fbx/.glb> <out.npz> [--drop mat,mat]`) | A rigged humanoid FBX or GLB (Mixamo / Unreal / Riot bone names, e.g. The Models Resource rips) to an npz with the skeleton renamed to ValveBiped; `srcmdl.SrcModel` reads it like an MDL. |
| `fbxprep.py <catalog.json> <slug>` | For catalog items with `"fbx"`: runs the export (when the FBX is newer) and writes Source-style VMTs + PNGs from the `.mtl` (map_Kd, map_Bump, map_d -> alpha test) under `<work>/fbx/<slug>/`. The pipeline calls it; such items have `"id": 0` and a `"url"`. |
| `vpk.py <x_dir.vpk> [--list] [--prefix p] [--out DIR]` | Lists or extracts a Source 1 VPK (v1/v2). Used once for the base-game materials (HL2 + CS:S from the GMod dedicated server's `sourceengine/`) into `<work>/basegame/`. |
| `gma.py <file.gma\|.bin> [out dir]` | Lists or extracts a GMod addon archive (also the LZMA legacy `.bin`). Paths are sanitised; nothing in the archive is run. |
| `preview.py` | Textured software renderer for the previews (fork of `projects/cs21.6/preview/model_render.py`). |
| `catalog.json` | Every item looked at: workshop id, title, author, `chosen` (and `skip_reason`, `looked_at` batch if not), `batch`, `slug`, `mdl`, optional `skin`, `bodygroups`, `depends` (other item ids whose files it needs), and the `paths` block. An item can appear more than once (two characters from one pack). |
| `MODELS.md`, `BATCH<n>.md` | The list of every converted model, and per-batch tables + review notes. |

## Paths (catalog `paths`, environment overrides)

| Key | Env | Default on the PC |
|---|---|---|
| `steamcmd` | `STEAMCMD` | `C:\steamcmd\steamcmd.exe` (downloads land in `C:\steamcmd\steamapps\workshop\content\4000\<id>\`) |
| `work` | `PM_WORK` | `C:\source1\playermodels\` = `extract\<id>\`, `preview\`, `reports\`, `logs\`, `template\` |
| `template` | `PM_TEMPLATE` | `C:\source1\playermodels\template\` (decompiled agent with ragdoll joints, see the guide) |
| `out` | `PM_OUT` | content addon `gmod_playermodels` (`csgo_addons\gmod_playermodels\`) |

Output inside the addon: `models/player/gmod/<slug>/<slug>.vmdl` + `<slug>_body.dmx`, `models/player/gmod/shared/` (template first-person arms,
sleeves, preview pose: one copy for all), `materials/models/player/gmod/<slug>/*.vmat|png`.

## Quick start

```
cd create/playermodels
python -I browse.py catalog.json                                 # new Workshop candidates (add picks: chosen false, looked_at N)
python -I fetch.py catalog.json --scan --suggest --only <ids>    # download, list candidates, apply the rules (--scale 0.8,1.6: fun skins)
# edit catalog.json: chosen, batch, slug, mdl for each pick
python -I pipeline.py catalog.json --batch=3 --compile --jobs 6  # convert, preview, hands check, compile, report (6 at once)
# review contact_sheet_batch3.png + <slug>_hands.png (warned models first)
python -I dupes.py catalog.json && python -I batchnotes.py catalog.json 3 && python -I listmodels.py catalog.json
# minigames server (slime-mg-gm): tools/model_catalog.py (list + a posed picture per model), then
#   tests/run.py --no-restart --only none --gmod-models (bots wear every model and fight; tests/results/gmod_models.md)
python -I cleanup.py catalog.json --prune                         # free disk once the batch is done
```
Runs longer than two minutes go under `autoport/watchdog.py` on the PC (download ~10 s per item; conversion 5-60 s per model, previews 1-3 min).
