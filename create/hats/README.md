# create/hats: GMod hats and accessories -> CS2 hats that bone-merge onto a player's head

> **AI-generated code.** Written by Claude for skink52. [PolyForm Noncommercial 1.0.0](../../LICENSE), like the rest of the repo. How it works, the research behind it
> (no head attachment on CS2 agents: bone merge with `FollowEntity`), placement and rights: [docs/creation/gmod-hats.md](../../docs/creation/gmod-hats.md).
> The server that wears them: slime-mg-gm `Credits/Hats.cs`, its `docs/hats.md`.

Python 3 with numpy, scipy and Pillow; Node 22.15+ once for the reference agent (`s2/agent_mesh.mjs`). Reuses the player model
converter in `../playermodels/` (srcmdl.py, vtf.py, gma.py, fetch.py's SteamCMD download, gmod2cs2.py's material and DMX writers,
preview.py) without changing it. Run with `python -I` (the inputs are downloaded files).

| File | What it does |
|---|---|
| `browse.py <catalog.json> [--pages N]` | Workshop search for hat / accessory packs (hat, pointshop hats, accessories, masks, glasses, tf2 hats...; top rated and most subscribed). Prints the ones not in the catalog, all to `<work>/logs/candidates.json`. Downloads nothing. |
| `fetch.py <catalog.json> [--only id,..] [--no-download] [--scan]` | SteamCMD (anonymous) download + extract of every catalog item into `<work>/extract/<id>/`; `--scan` lists each `.mdl` (bones, vertices, size, missing VMTs/VTFs) and the Pointshop item that places it, into `<work>/logs/scan.json`. |
| `suggest.py <catalog.json> --batch N [--only id,..] [--dry-run]` | Adds one copy of every head-worn prop in the scan to the catalog's `hats` (no player models, arms, weapons, tails, wings; nothing missing; a model shared by several packs once, the copy with Pointshop data first). |
| `hat2cs2.py <catalog.json> [--only id,..] [--no-preview] [--compile] [--sheet]` | Places each hat on the head (Pointshop lua, else autofit; catalog overrides), writes `models/hats/<id>/<id>.vmdl` + 12 fit DMXs and the materials into the `gmod_hats` content addon, previews (`<work>/preview/<id>.png`, `_tile.png`, `--sheet`: `sheet_<n>.jpg`), compiles, reports (`<work>/reports/<id>.json`). |
| `pack.py <catalog.json> [--prune] [--no-zip]` | The collection for a server manager: `--prune` deletes the dropped hats from the `gmod_hats` addon (both halves), then `<work>/dist/gmod_hats_collection_<date>.zip` = the kept hats compiled + source, `HATS.md` with the pictures, README.txt. The manager's steps: slime-mg-gm `docs/hats.md#adding-hats`. |
| `luahats.py <extract dir>` | Reads Pointshop 1 items (`ITEM.Model`, `ITEM.Attachment`/`Bone`, `ModifyClientsideModel` replayed: moves, turns, scale) as text. |
| `mdlextra.py` | MDL attachments (srcmdl.py doesn't read them): the HL2 citizen's `eyes`. |
| `agents.py` | Stock agents from `s2/agent_mesh.mjs` JSON: bind pose, meshes, the head's measures. |
| `hatpaths.py` | The paths below. |
| `catalog.json` | `items` (Workshop id, title, author, `looked_at`) and `hats`: `id`, `item`, `mdl`, `name`, `batch`, `chosen` (false = dropped, `skip_reason`), overrides `offset` [x,y,z] u, `rotate` [pitch,yaw,roll], `scale`, `pre_rotate` [rx,ry,rz], `kind`, `autofit`, `skin`, `bodygroups`, `depends`. |
| `listhats.py <catalog.json>`, `HATS.md`, `img/` | `HATS.md`: every converted hat with its picture (`img/<id>.jpg`), placement, compile status, source; the dropped ones and why. (The server's shop list is slime-mg-gm `tools/hat_catalog.py`.) |

## Paths (catalog `paths`, environment overrides)

| Key | Env | Default on the PC |
|---|---|---|
| `work` | `HATS_WORK` | `C:\source1\hats\` = `extract\<id>\`, `agents\` (reference agents, Valve data), `ref\male_09.*` (HL2 citizen), `preview\`, `reports\`, `logs\` |
| `out` | `HATS_OUT` | content addon `gmod_hats` (`csgo_addons\gmod_hats\`) |
| `template` | `PM_TEMPLATE` | `C:\source1\playermodels\template\` (read only: its body DMX is the skeleton every hat is written into) |
| `basegame` | `PM_BASEGAME` | `C:\source1\playermodels\basegame\` (HL2/CS:S materials, read only) |
| `steamcmd` | `STEAMCMD` | `C:\steamcmd\steamcmd.exe` |

## Quick start

```
cd create/hats
python -I browse.py catalog.json                         # packs to look at: add picks to "items"
python -I fetch.py catalog.json --scan                    # download, extract, list models + Pointshop placement
python -I suggest.py catalog.json --batch 2               # hats from the scan into "hats"
python -I hat2cs2.py catalog.json --sheet                 # place, write, preview: review sheet_<n>.jpg
# fix misplaced hats in catalog.json (offset/rotate/scale/pre_rotate/kind) or set "chosen": false; re-run with --only
python -I hat2cs2.py catalog.json --compile --no-preview  # compile the chosen ones (resourcecompiler)
python -I listhats.py catalog.json && python -I pack.py catalog.json --prune   # HATS.md + the collection zip for the manager
# one-off: the reference agent (Valve data, not in git)
node ../s2/agent_mesh.mjs agents/models/tm_leet/tm_leet_variantf.vmdl_c C:\source1\hats\agents\tm_leet_variantf.json --vpk "<CS2>\game\csgo"
```
Runs over two minutes go under `autoport/watchdog.py` (about 10 s per hat with previews, 3-5 s to compile one).
