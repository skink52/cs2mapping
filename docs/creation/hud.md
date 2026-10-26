# HUDs, screen overlays, loading screens and radar

## The custom HUD (`custom_hud_layout`)

CS2 maps can add their own HUD with no plugins: a `custom_hud_layout` entity points at a Panorama layout, and the map's cs_script switches CSS
classes and text on its panels, for everyone or per player.

**Files** (in the addon's content folder; they compile with the map, or with `resourcecompiler -f -i <file>`):

```
panorama/layout/custom_game/<name>.xml      -> the entity's layout keyvalue points at the compiled .vxml
panorama/styles/custom_game/<name>.css
panorama/images/custom_game/<name>/*.png    -> url("file://{images}/custom_game/<name>/x.png") in the css
```

**Minimal layout** (the shape used for every env_screenoverlay replacement):

```xml
<root>
	<styles>
		<include src="file://{resources}/styles/custom_game/mymap_overlays.css" />
	</styles>
	<Panel class="Root" hittest="false">
		<Panel id="IntroOverlay" class="ScreenOverlay Hidden" hittest="false" />
	</Panel>
</root>
```

```css
.Root { width: 100%; height: 100%; }
.ScreenOverlay { width: 100%; height: 100%; background-size: 100% 100%; background-repeat: no-repeat; opacity: 0.8;
                 transition-property: opacity; transition-duration: 0.1s; }
.ScreenOverlay.Hidden { opacity: 0; }
#IntroOverlay { background-image: url("file://{images}/custom_game/mymap/intro.png"); }
```

```js
// maps/scripts/overlays.js on a point_script; map I/O: RunScriptInput Show_IntroOverlay / Hide_IntroOverlay
import { Instance, CustomHudLayout } from "cs_script/point_script";
const layout = () => { const e = Instance.FindEntityByName("mymap_overlay_layout"); return e instanceof CustomHudLayout ? e : undefined; };
for (const id of ["IntroOverlay"]) {
    Instance.OnScriptInput(`Show_${id}`, () => layout()?.SetHasClass(id, "Hidden", false));
    Instance.OnScriptInput(`Hide_${id}`, () => layout()?.SetHasClass(id, "Hidden", true));
}
```

Working examples: `ports/mg_mario_party/panorama/` + `scripts/overlays.js` (20 game-select overlays), and the mg_swag_multigames port (17 overlays,
including a "tunnel vision" black screen with a hole). The CS:GO overlay textures are decoded from VTF to PNG; the panel's opacity stands in for the
material's `$alpha`.

### Script API

`SetHasClass(panelId, cls, on)` (everyone), `SetHasClassForPlayer(slot, panelId, cls, on)`, `SetDialogVariableString` / `SetDialogVariableStringForPlayer` for text
(`{s:name}` in a Label), `Reset()` / `ResetForPlayer(slot)`, `SetInputCaptureEnabled(slot, on)` + `Instance.OnCustomHudClicked` for clickable buttons.
Patterns (send only changes, reset on activate/team change, per-tick budgets): [../reference/cs_script-notes.md](../reference/cs_script-notes.md#hud-custom_hud_layout).
Panel types, scoreboard classes and other engine-side limits: [cs2-gotchas, HUD](../reference/cs2-gotchas.md#hud-radar-loading-screens-and-workshop).

## Generating a game HUD

Original addons write the xml/css from Python. [`create/panorama.py`](../../create/panorama.py) holds the helpers (`Hud.rule`, `P`, `place`, `show_when`,
pixel-text rows, `char_line`, `preload`, `hide_with_scoreboard`, `write` with its asserts) and a worked example (`panorama.example('out/addon')`).
[`create/pixfont.py`](../../create/pixfont.py) is an original 8×8 pixel font; [`create/retro.py`](../../create/retro.py) the palette, dithering and ×k upscaling.

### Layout rules that survived CS2

- **No id on the top panel** (CS2 rejected Puppet Brawl's layout with "root panel with id"): wrap everything in an id-less panel.
- **State classes**: everything the script switches starts with `st` (`stOn`, `stLobby`, `stPick`…) and has **no rule of its own**, only in combination with a
  panel class (`.Card.stBrkFull`). Space Racer's HUD was thrown around the screen because the root's state class "Pick" matched the picker panel's class, so
  the whole root took that rule. `panorama.Hud.write(dynamic=…)` fails the build on a lone rule for a switched class.
- **Root hidden until a state is set:** `.MyRoot { opacity: 0 }`, `.MyRoot.stOn { opacity: 1 }`, so a half-initialised HUD never flashes.
- **Static layout:** Panorama scales every screen to 1080 high. One fixed 1080-high screen panel; every panel a fixed size pinned from the top and from the left,
  centre or right edge; no vertical centring/bottom alignment, no `margin-bottom`, no fit-children boxes; negative margins only inside `flow-children: right`
  glyph rows.
- **Show/hide:** opacity is the safest (Space Racer, Puppet Brawl). Class-toggled `visibility: collapse` / `visible` also works in game (Hellmatch uses it
  throughout: `.FdmRoot`/`.FdmRoot.On`, lobby mode, scoreboard hiding).
- Changing `horizontal-align` through a class doesn't move a panel; move things with `transform: translatex()/translatey()`, not class-driven margins.
- `@keyframes` names must be quoted. **An animation replays only when its name changes:** to re-trigger a "pop", alternate two identical keyframes
  (`pop` / `pop2`) (Space Racer `popFx`). Space Racer also uses `scale3d` keyframes, `animation-iteration-count: infinite`, `background-repeat: repeat`
  with `background-size: 6px 6px` (scanlines), `text-transform`/`letter-spacing` on Labels; whether CS2 accepts all of them is unconfirmed (the HUD
  works without the animation if not).
- Children are clipped to their parent (minimap dots in an 8 px parent vanished): make the parent as big as the travel, or `overflow: noclip`.
- Every display panel `hittest="false"`. Panel-id prefixes must not end in a digit (`x2` + "0" clashes with `x` + "20").
- Label font as CS2's HUD: `font-family: Stratum2, "Stratum2 Bold", Arial`.
- CS2 hosts custom HUDs in `<Panel class="WindowRoot"><CSGOCustomHud id="CustomHud" style="width:100%;height:100%;flow-children:none;">`; its own
  stylesheet doesn't style your class names. Hide your HUD while Tab is held with `.HUD_SCOREBOARD_VISIBLE .MyRoot.hidescores { visibility: collapse; }`
  (`hidescores` = a per-player opt-in class, Hellmatch `!hud scores`; `Hud.hide_with_scoreboard`).
- A layout that fails to compile is ignored silently: CS2 keeps the last good `.vxml` (Puppet Brawl ran a 3-day-old HUD). Compile it with
  `resourcecompiler.exe -f -i "…\panorama\layout\custom_game\<name>.xml"` (and the `.css`) and check for "1 compiled"; the command-line build's pre-pass
  never compiles them. Changes need a full reload (`disconnect`, load again).

### CS2's own HUD zones (keep clear)

CS2's HUD can't be hidden from a map and draws over yours. At 1080 high (as `create/hud_check.py` checks them):

| Zone | Area |
|---|---|
| Kill feed | x W−430 … W, y 72 … ~190 for 3 lines (~36 px per line) |
| Team counter / top bar | x W/2 ± 360, y 0 … 66 |
| Money / health row | y 1000 … 1080 |
| Chat | x 0 … 576 (hand-measured box x 18–571), y 600 … 1010 while typing; ~800 … 1010 when only the last lines show (lobby); 40% of the width on 4:3 |

### Text

- **Pixel text** (Space Racer): every character is a small image panel; the script switches its glyph class (`g65` = A) and the row's colour class (`cW`, `cY`),
  only for characters that changed; rows are `flow-children: right` with `margin-right: −size/10`. Glyph PNGs are 10×10 font pixels saved ×6 (60 px; raise if
  blurry), one per colour per character (`panorama.Hud.glyph_font`, `gtext`, `stext`).
- **Whole-string images** (Hellmatch): frequent fixed strings (obituaries, mode names, VICTORY…) are pre-rendered as one image each and shown with one class
  (`.TImg.t<n>`); per-character panels only for dynamic text. The string list comes from the core and is baked into the script as an index (`HUD_STRING_INDEX`).
- **Wrapping:** fixed rows have a slot count (Hellmatch 32/24/40/2×56). Script-side wrapping needs real glyph widths: the HUD generator writes them to JSON,
  the build bakes them (`HUD_GLYPH_W`), and the wrap splits at spaces to fit both pixel width and slot count. Names capped at 12 characters on the HUD only.
  (A kill message cut at 40 characters was a full 40-slot row, not a Label limit.)
- **Per-player text size without re-layout** (Hellmatch `!text`): a size class on the screen panel and `transform: scale3d(s, s, 1)` with `transform-origin` at
  the edge each line is anchored to (`0% 0%` left, `100% 0%` right, `50% 0%` centre); the second line of a pair also gets `translatey(9·(s−1) px)` so pairs
  never overlap.
- Pixel art is upscaled ×6 nearest-neighbour before saving so CS2's texture filtering keeps it sharp.

### Positions, gauges and maps

- **Doom-style status bar** (Hellmatch): the original 320×200 screen mapped to a 1440×1080 panel (one Doom pixel = 4.5 × 5.4 px), images switched by class.
- **Class grids for script positioning** (mg_trenchwarfare): precomputed classes `.XCol.x0..x191 { transform: translatex(…) }` and `.XSq.y0..y191 { translatey(…) }`
  (192 steps over 768 px) place a crosshair on a sight map; the script sets one class per axis.
- **Rotating needles:** 72 classes `.GLayer.aN { transform: rotateZ(N·5deg) }` with a 0.12 s transition (mg_trenchwarfare cockpit dials).
- **Minimap dots** (Space Racer, mg_deku_tree): a picture panel plus dots moved by transforms; other cars' dots step 2 map pixels and refresh at 8 Hz
  (`MINIMAP_DOT_HZ`; 4 halves the biggest share of HUD traffic).
- **Cost:** budgets of 600 (Hellmatch) or 900 (Space Racer, where pixel text sends one change per letter) class changes per server tick, HUD refreshed for half the
  players on even ticks and half on odd: [cs_script-notes](../reference/cs_script-notes.md#hud-custom_hud_layout).

### Checking the layout before CS2

`python3 -I create/hud_check.py --addon out/addon --name <layout> [--states states.json] [--out build/hud]` (from Space Racer's `hud_render.py`) lays the xml/css
out like Panorama at 1920, 2333 (21:9) and 1440 (4:3) wide, draws it with the real pictures, marks CS2's zones, and exits 1 on any layout-rule break,
unsupported panel type, duplicate id, id on the top panel, or overlap with CS2's HUD. Run it in the build right after the HUD generator, as a gate.
The states JSON sets classes/text per panel, so every screen state (lobby, race, vote, help) is checked. A text row too long for its slots should fail
the mock test too. Alternative: Hellmatch's `preview/hud_preview.py` renders the real xml/css in headless Chromium by translating Panorama-isms
(`flow-children: right` → flex row, `visibility: collapse` → `display:none`, `<Panel>` → `<div>`, `file://{images}/` → local path); cheap, but it doesn't
model Panorama's alignment rules.

## Loading screens

- **Credit text:** `game\csgo_addons\<addon>\maps\<map>.txt`, first line `COMMUNITYMAPCREDITS:`, then the lines (no rebuild needed).
- **Slides:** `panorama/images/map_icons/screenshots/1080p/<map>.png`, `<map>_1.png` … `_9`. CS2's loading screen (`panorama/scripts/loadingscreen.vts`) plays
  them as a slideshow, 4 s each, from a random one. Ship **at least two**: with one, CS2 showed none of your art. Naming, both ways of producing them
  (Hammer5Tools' `<map>_png.png` + `.vtex`, or plain PNGs) and what's verified: [pipeline.md](../porting/pipeline.md#loading-screen-background-images).
- **Original addons use plain PNGs with no `.vtex`:** referenced from the HUD css preload panel, `<map>.png` compiles to `<map>_png.vtex_c` (Space Racer saw
  `mg_space_racer_png.vtex_c` … `_3_png.vtex_c`); they show from the second load after copying.
- **Preload panel** (exact form, Space Racer/Hellmatch; `panorama.Hud.preload`): a 1 px collapsed parent with one child per picture,
  `width: 1px; height: 1px; opacity: 0; visibility: collapse; background-image: url("file://{images}/<path>")` for `map_icons/screenshots/1080p/<map>[_n].png`,
  `overheadmaps/<map>_radar.psd`, `map_icons/map_icon_<map>.svg`. Pictures are only compiled if something references them.
- **Safe area** on a 1920×1080 slide: slides are scaled to cover the screen, so a 4:3 screen loses 240 px each side and 21:9 crops top and bottom (keep content in
  y 128–952); CS2 draws a 300 px column 20 px from the right (map name, icon, mode, the slide blurred behind it) and the loading bar. Keep content in
  x 252–1348, y 104–948 (Space Racer keeps a fixed logo + controls panel there and changes the panel below per slide).
- [`create/loading.py`](../../create/loading.py): `slides` (cover-scales any pictures to 1920×1080, **deletes stale `<map>*.png` slides first** so an old extra
  slide can't ship, `--css-check` fails if the HUD css doesn't preload every slide), `overlay` (draws CS2's column, bar and the 4:3/21:9 edges on a slide),
  `icon`, `radar`, `workshop`.
- **Map icon:** `panorama/images/map_icons/map_icon_<map>.svg` (white, 64×64), compiled as `map_icon_<map>.vsvg`.

## Radar (minimap)

- Image, two routes: a flat PSD `panorama/images/overheadmaps/<map>_radar.psd` (8-bit RGB, 3 channels, planar raw data, empty colour-mode/resources/layer
  sections; compiles as `<map>_radar_psd` with no `.vtex`, when preloaded; `loading.py radar`), or the port pipeline's `<map>_radar_psd.png` + `.vtex`
  (max 1024, `m_bNoLod 1`, `m_vClamp "0 0 0"`; `tools/radar.py`).
- Overview: `resource/overviews/<map>.txt` in the **game** folder: `material`, `pos_x`/`pos_y` = world position of the image's top-left corner,
  `scale` = world units per pixel, `rotate`, `zoom`; `"verticalsections"` for stacked maps. The `material` value differs between tools and is unverified
  ([cs2-gotchas](../reference/cs2-gotchas.md#hud-radar-loading-screens-and-workshop)).
- Fit the region to the ground play space, not the whole terrain (mg_trenchwarfare: aerodromes left off, pos −4300/4700, scale 8.40 for 1024 px).
- Don't place `cs_minimap_boundary` entities: CS2 then draws its own minimap instead of your image.
- mg_trenchwarfare's painted radar adds a 16×16 lettered grid (A–P across, 1–16 down) and a `!pos` chat command that prints the player's grid square, to check
  alignment in game. `sv_disable_radar 1` turns the radar off (games with parked pawns: the radar would show everyone in the booth).
