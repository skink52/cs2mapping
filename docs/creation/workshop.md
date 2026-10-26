# Publishing to the Steam Workshop

## Upload

- The Workshop item is the compiled **game** folder (`game\csgo_addons\<addon>`), not content. Licence/credit files must be copied there (or put in the description).
- Game mode **Custom**.
- Description in Steam BBCode, 8,000-character limit. The mapper manages titles and descriptions.
- Images: under ~1 MB each (preview icon 1024² or 1080², gallery 1920×1080), added after publishing via the item page's "Add/edit images & videos".
  A GIF can't be the thumbnail; use a PNG/JPG.
- Video: only YouTube links (upload there first).
- Before uploading a **renamed** map, delete the old name's files (`maps/<old>.vpk`, `_cameras.txt`, `_retakes.txt`, overview txt, compiled panorama images) from content and game.
- Ports: credit the original mapper in the loading screen text and description ([../porting/conventions.md](../porting/conventions.md)).

## Keeping it safe to publish (IP)

Practical rules used for every original addon (not legal advice):
- No other game's names, logos, characters, screenshots or ripped assets in the title, tags, images or the addon. Genre mechanics (grid bombs, anti-grav racing,
  laps, boost pads) belong to nobody; expression (names, characters, art, music) does.
- Everything shipped is original (generated) or CS2 stock, or under a licence that allows it, with credits (`CREDITS.md` in the addon root, licence text in the description).
- Say "Not affiliated with or endorsed by …" for any game the rules are inspired by. Under BSD-style licences don't use the upstream project's name to endorse
  (Hellmatch replaced Freedoom's logo art and renamed away from "FreeDM").
- Fan-ripped models (e.g. a weapon mesh named "BF1 All weapons") are a DMCA risk: replace them with CC-licensed or generated ones before publishing.
- Synthesised sound and music avoid copyright claims on YouTube trailers too.

Examples: the bomb-arena game (original tilesets and chibi T/CT characters instead of GPL BomberClone art, title without "Bomberman"),
Space Racer (`docs/WORKSHOP_COMPLIANCE.md` in its repo), mg_deku_tree (no ROM assets, no fan models of the game's characters).

## Promotional material

Hellmatch's trailer pipeline (Python + ffmpeg): synthesised music, fire/ember effects, screen-melt transitions, text in the game's HUD font, GIF export with
palette generation (`gifsicle` to shrink). Keep logos of other projects out of every frame.
