# Working with an AI agent (Claude) on CS2 maps

What has worked for porting and building CS2 maps with Claude, and the practical limits. Applies to both halves of this repo.

## How the work is split

- **Claude** (cloud workspace, Python/Node): decompiling, editing `.vmap` files directly, generating models, materials, textures, HUD, sounds, scripts,
  radars and loading screens, checking its own output (mesh checks, renders, type-checks, mock runs), and keeping the records in this repo.
- **The mapper** (Windows PC): anything that runs Valve's tools — the map importer, `resourcecompiler` builds, Hammer, playing the map — by double-clicking
  the batch files Claude prepares, then reporting what happened in game.
- Claude reaches the PC's folders through the Claude desktop app's linked-computer bridge (files only; it can't start programs there unless a shell is
  offered). If the PC isn't linked, nothing on it can be read or updated: open the chat in the desktop app on that PC and send a message.

## House rules

- **Hammer stays closed** while Claude edits a map. Hammer keeps the map in memory and overwrites edits on its next save.
- **Back up the `.vmap`** before editing it (`csgo_addons\prefabs+backups\`).
- **Always start from the mapper's latest save.** The mapper edits in Hammer between deliveries; generating from an old copy loses those edits.
- **Send only changed files.**
- **Build from the command line, one map at a time** (`run_build.bat`), with the copy out of the temp outroot finished before the next compile.
- **Test checklists:** the mapper only reports failures; anything not mentioned passed.
- **Ask or check the repos** when information is missing, so every chat uses the same facts. This repo is the shared memory: record pipeline changes,
  port fixes and CS2 discoveries here in the same session.
- Public repos carry a short "AI-generated code" disclaimer.

## Transfer limits and traps

- Uploads of 25 MB+ failed; keep files/zips under ~20 MB (big maps' assets are split into `.2`/`.3`/`.4.zip`).
- Re-sending a changed file from the same staged path can send the old upload. Use a fresh path, then read it back and compare.
- Files written through the output folder can gain metadata (PNG `caBX` chunk, MP3 `GEOB`, WAV block, ~5.8 KB), so compare images by pixels and audio
  by samples, not by hash.
- Bulk deliveries come with an unpack `.bat` that applies each zip once (and records it), never containing the user's `.vmap` or the live script.
- Steam's image CDN is blocked from the workspace: the mapper saves Workshop images on the PC first.
- Page fetchers read hidden "item removed/incompatible" text on every Workshop page; never report an item as removed from that text.
- Claude can't delete files on the PC without a permission prompt; otherwise it moves them to a `_to_delete` folder or lists them for the mapper.

## Long and unattended work

- `run_import_then_build.bat`: stage B, then wait for a `build_go.txt` flag Claude writes after stage C, then stage D. Claude follows up with scheduled checks.
- Scheduled resume reminders keep multi-hour jobs going if usage runs out mid-task; working notes in the project repo (`NOTES.md`, `STATUS.md`) let a new chat pick up.
- Big jobs are split into stages with a task list; each delivery has a version string the script prints, so the mapper can tell which build is running.

## Verifying without the game

- Mesh sanity: `create/check_mesh.py`. Map views: `tools/vmap_preview.py`. Model turntables from the prop builder.
- Scripts: `create/test/tscheck.sh` (Valve's API types) and `create/test/mock_point_script.mjs` (stand-in engine).
- HUD: render the layout like Panorama at several aspect ratios with CS2's own HUD areas marked (Space Racer's `preview/hud_render.py`).
- Everything not verified in game is written down as unverified until the mapper confirms it.
