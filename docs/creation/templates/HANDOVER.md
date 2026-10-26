# <Game> (<map>): status and handover, <date time, time zone>

Start any new chat about this map here. Fuller history: `NOTES_<topic>.md` (timestamped entries) and the project doc `claude/<game>_*.md`.

## Where things are

- **Repo:** github.com/skink52/<repo>, branch `<branch>` (commit `<sha>`). Other branches: <…>.
- **Addon on the PC:** `content\csgo_addons\<addon>` (and `game\csgo_addons\<addon>`).
- **Current version: v<x.y.z>.** Delivered files (sha1-checked on <date>): <list>. Unchanged since v<…>: <list>.
- **Last in-game test:** v<…> on <date>. Everything after it is **NOT YET TESTED IN CS2**.

## The mapper's next steps

1. Close CS2 and Hammer; back up the `.vmap`.
2. <Copy / unpack: which zip, where; the unpack bat applies each zip once.>
3. <Build: run_build.bat, or resourcecompiler -f -i on the .js / .xml / .css (the pre-pass skips them).>
4. Load `map <map>`; the console must print `v<x.y.z>`.
5. Work through `TESTING_<GAME>.md` "Check these first".

## What this version contains

- <Change, why, how verified (written / verified offline / tested in game).>

## Open items and unknowns

- <Untested in CS2: …>
- <Known issues, ideas not started.>

## Working rules

- **Mapper:** doesn't code; send only changed files; Hammer closed while map files are edited; builds from the command line, one at a time.
- **Bridge:** re-sending from the same staged path can send the old upload: use a fresh path, re-stage and compare sha1; PNGs gain a metadata chunk on commit,
  so compare by pixels; bulk files as zips under ~20 MB.
- **Build:** <commands>. **Tests:** <commands>. **Generators:** `python3 -I …`; switches `<X>_NAME`, `<X>_CURRENT_VMAP`, `<X>_SOUNDEVENTS`.
