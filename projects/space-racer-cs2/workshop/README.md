# Space Racer: Steam Workshop page

Everything for the Workshop page, ready to upload.

| File | What it is |
|---|---|
| `icon.png` | The preview image (1024 x 1024; Steam shrinks it for lists). |
| `screenshot_1_loop.png` | Crosswire: driving into the spiral loop, the exit deck overhead (race HUD). |
| `screenshot_2_pack.png` | Solar Oval early in a race: a pack of cars, boosting, just topped up by the Pulse. |
| `screenshot_3_jump.png` | Skyway: in the air over a jump gap, the landing ahead. |
| `screenshot_4_grid.png` | The grid flyover with the small car picker and the countdown line. |
| `screenshot_5_results.png` | The results board at the end of a race. |
| `screenshot_6_lobby.png` | The lobby: the four car cards over the next track. |
| `screenshot_7_tracks.png` | All eight tracks from the driver's seat. |
| `screenshot_8_info.png` | The map's own loading screen: the first of its four slides (controls and the four cars). |
| `description_bbcode.txt` | The page text, in Steam's BBCode (about 6,400 of the 8,000 characters allowed). |

All pictures are PNGs under Steam's 1 MB limit.

## Uploading

1. Publish the map from the CS2 Workshop Tools as usual. Use `icon.png` as the preview image, and paste all of
   `description_bbcode.txt` into the description box (the `[h1]`, `[b]`, `[list]` codes are Steam's formatting).
2. Title: **Space Racer** (or *Space Racer | 32-Car Anti-Grav Racing*).
3. Tags: pick the closest ones the upload offers (custom map / minigame). Keep other racing games' names out of the
   title, tags and description (see `docs/WORKSHOP_COMPLIANCE.md`).
4. Open the item's page on Steam and use **Add/edit images & videos** to add the eight screenshots in order.

## About the screenshots

They are renders of the real track and car models with the real HUD laid over them
(`preview/workshop_shots.py`; the icon is `tools/workshop.py`), not captures from CS2. CS2's own HUD (chat, kill
feed, money / health) is not in them, and cars are drawn level with the road on banked bends. They show the game
as it is, but in-game captures (F12, Steam's screenshot key) can replace any of them once you have good ones.

## Rebuilding

```
python3 -I tools/workshop.py workshop                       # icon.png
python3 -I preview/workshop_shots.py out/addon workshop     # the eight screenshots (after a full build)
```
