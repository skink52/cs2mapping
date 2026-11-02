# Instructions for Claude sessions on cs2mapTTT

- Primary repo for the drop-in TTT cs_script. Reusable discoveries (cs_script API, CS2 behaviour, tools) also go to github.com/skink52/cs2mapping
  (`docs/reference/cs_script-notes.md`, `cs2-gotchas.md`, `CHANGELOG.md`), per that repo's CLAUDE.md.
- Everything the game needs lives in `addon/` (copied into any map's addon folder). Only map edit: the entities in `tools/ttt_patch.json` (point_script required; HUD and body template optional).
- TTT maps: `tools/ttt_convert.py` then `tools/build_data.py` (data lives in `maps/<map>.json`; never hand-edit the MAP_DATA block).
- `CONFIG` at the top of `ttt.js` holds every tunable. Keep the script working with no HUD (fallbacks) and with no `info_map_parameters`.
- Before pushing: `sh test/run_mock.sh ../cs2mapping` must print OK for every scenario.
- Record in-game results in `TESTING.md` (verified / failed). Keep the AI-generated disclaimer in README.md. No personal details; handle skink52.
- Send only changed files when delivering to the PC; Hammer closed and the vmap backed up before patching a map.
