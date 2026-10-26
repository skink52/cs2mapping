# Publishing to the Steam Workshop

Engine/platform facts (game folder is what uploads, renamed-map leftovers, `host_workshop_map`, "removed" text on fetched pages):
[cs2-gotchas, HUD/loading/Workshop](../reference/cs2-gotchas.md#hud-radar-loading-screens-and-workshop). This page is the publishing workflow.

## Upload

- The Workshop item is the compiled **game** folder (`game\csgo_addons\<addon>`). The build copies README, licence and CREDITS files into `out/game` (and
  `out/addon`) so they ship (Hellmatch's `build_all.sh` last lines; [`create/build/build_all.example.sh`](../../create/build/build_all.example.sh)).
- Game mode **Custom**. The mapper manages titles and descriptions.
- Before uploading a **renamed** map, delete the old name's files from content and game.
- Ports: credit the original mapper in the loading screen text and description ([../porting/conventions.md](../porting/conventions.md)).

## Page assets

- Images under 1 MB each: preview icon 1024² (or 1080²), gallery 1920×1080, added after publishing via the item page's "Add/edit images & videos".
  A GIF can't be the thumbnail; use PNG/JPG. `python3 create/loading.py workshop <in.png> <out.jpg> [WxH]` shades the top/bottom lightly and saves a JPEG
  under 1 MB (lowering quality until it fits).
- Video: only YouTube links (upload there first).
- **Screenshots before in-game captures exist** (Space Racer): software renders of the real models with the real HUD laid over them (`create/smd_view.py` +
  the HUD pictures from `create/hud_check.py`), labelled as renders that captures can replace. Icon drawn at 256 px in the palette and scaled ×4
  nearest-neighbour (~35 KB).
- Keep a `workshop/README.md` in the repo: file → purpose, upload steps, title and tags.

## Description

- Steam BBCode, 8,000-character limit (Space Racer used ~6,400). Keep it in the repo (`docs/WORKSHOP_DESCRIPTION.txt` or `workshop/description_bbcode.txt`).
- For script-run games add a **Server requirements** block (Hellmatch): map name and `host_workshop_map <id>`, game type Custom; the cvars the map sets
  and the `APPLY_CVARS` opt-out; plugin types that break it (AFK managers, no-respawn, spawn protection, TK punishment, anything blocking scripted damage);
  measured server load and how to check it (the once-a-minute "script time" console line); bots.
- How it was made (AI-written code directed by skink52), credits, licence text, "Not affiliated with or endorsed by …".
- Keep `docs/WORKSHOP_CHANGELOG.md` with each update's notes **exactly as posted** ([template](templates/WORKSHOP_CHANGELOG.md)).

## Keeping it safe to publish (IP)

Practical rules used for every original addon (not legal advice); checklist template: [templates/WORKSHOP_COMPLIANCE.md](templates/WORKSHOP_COMPLIANCE.md).
- No other game's names, logos, characters, screenshots or ripped assets in the title, tags, images or the addon. Genre mechanics (grid bombs, anti-grav racing,
  laps, boost pads) belong to nobody; expression (names, characters, art, music) does.
- Everything shipped is original (generated) or CS2 stock, or under a licence that allows it, with credits (`CREDITS.md` in the addon root, licence text in
  the description; [template](templates/CREDITS.md)).
- Say "Not affiliated with or endorsed by …" for any game the rules are inspired by. Under BSD-style licences don't use the upstream project's name to endorse
  (Hellmatch replaced Freedoom's logo art and renamed away from "FreeDM").
- Fan-ripped models (e.g. a weapon mesh named "BF1 All weapons") are a DMCA risk: replace them with CC-licensed or generated ones before publishing.
- Synthesised sound and music avoid copyright claims on YouTube trailers too.

Examples: the bomb-arena game (original tilesets and chibi T/CT characters instead of GPL BomberClone art, title without "Bomberman"),
Space Racer (`docs/WORKSHOP_COMPLIANCE.md` in its repo), mg_deku_tree (no ROM assets, no fan models of the game's characters).

## Promotional material

Hellmatch's trailer pipeline (Python + ffmpeg): synthesised music, fire/ember effects, screen-melt transitions, text in the game's HUD font, GIF export with
palette generation (`gifsicle` to shrink). Keep logos of other projects out of every frame.
