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
Patterns (send only changes, reset on activate/team change, per-tick caps): [../reference/cs_script-notes.md](../reference/cs_script-notes.md#hud-custom_hud_layout).

### Layout rules that survived CS2

- The root HUD panel may not have an id (CS2 rejected Puppet Brawl's layout with "root panel with id"); wrap everything in an id-less root panel.
- **State classes on the root must not share a name with any other panel's class**: the whole root takes that rule (Space Racer's HUD was thrown around
  the screen by a root class "Pick" matching the picker panel). Prefix root state classes (`stLobby`, `stPick`…).
- Panorama scales every screen to 1080 high. Robust layout: one fixed 1080-high screen panel, every panel a fixed size pinned from the top and from the
  left, centre or right edge; no vertical centring, no negative margins, no fit-children boxes. Show and hide with **opacity**, not collapse.
- Changing `horizontal-align` through a class doesn't move a panel (transform and size changes do). `@keyframes` names must be quoted.
- A layout that fails to compile is ignored silently: CS2 keeps the last good `.vxml` (Puppet Brawl ran a 3-day-old HUD). Compile one layout with
  `resourcecompiler.exe -f -i "…\panorama\layout\custom_game\<name>.xml"` and check it ends "1 compiled".
- Children are clipped to their parent (minimap dots in an 8 px parent vanished when moved): make the parent as big as the travel, or `overflow: noclip`.
- Move things with `transform: translatex()/translatey()`, not class-driven margins (not always re-laid out).
- Labels held ~32 characters before truncating; wrap long messages into rows.
- Pictures are only compiled if referenced: preload loading-screen pictures, radar and map icon from a hidden 1 px `visibility: collapse` panel in the HUD.
- CS2 hosts custom HUDs in `<Panel class="WindowRoot"><CSGOCustomHud id="CustomHud" style="width:100%;height:100%;flow-children:none;">`; its own stylesheet
  doesn't style your class names.
- Panel-id prefixes must not end in a digit (`x2` + "0" clashes with `x` + "20").
- CS2's own HUD can't be hidden from a map and draws over yours. Keep clear of: chat box x 18–571, y 609–1000 (at 1080 high; 40% of the width on 4:3),
  kill feed from y 75 down (~36 px per line), team counter to y ~65, money/health row along the bottom.
- Changes need a full map reload (`disconnect`, load again) to show.

### Text and pictures

- Pixel-font HUDs (Space Racer): every character is a small image panel whose glyph class (`g65` = A) and the row's colour class are switched; whole rows are cached.
- Doom-style status bar (Hellmatch): the original 320×200 screen mapped to a 1440×1080 panel (one Doom pixel = 4.5 × 5.4 px), images switched by class.
- Minimap with a position dot (mg_deku_tree): a CSS grid panel; the dot moves with transforms.
- Check the layout before CS2: Space Racer's `preview/hud_render.py` lays the generated xml/css out like Panorama at 1920, 2333 and 1440 wide and fails the
  build when a panel breaks the rules above or sits under CS2's own HUD.

## Loading screens

- **Credit text:** `game\csgo_addons\<addon>\maps\<map>.txt`, first line `COMMUNITYMAPCREDITS:`, then the lines (no rebuild needed).
- **Pictures:** `panorama/images/map_icons/screenshots/1080p/<map>.png`, `<map>_1.png` … `_9`. Ship **at least two**: with one, CS2 kept its default art
  (Space Racer, Hellmatch). They play as a slideshow, 4 s each. The ports use Hammer5Tools' layout (`<map>_png.png` + `.vtex` at 1080/720/360p); see
  [../porting/pipeline.md](../porting/pipeline.md#loading-screen-background-images).
- Safe area on a 1920×1080 slide: CS2 draws a 300 px column 20 px from the right (name, icon, progress) and crops 4:3/ultrawide; keep content in x 252–1348, y 104–948.
- Compiling: reference the pictures from a never-shown rule in the HUD stylesheet (they show from the second load), or `run_build.bat "assets <addon>"`.
- **Map icon:** `panorama/images/map_icons/map_icon_<map>.svg` (white icon).

## Radar (minimap)

- Image: `panorama/images/overheadmaps/<map>_radar_psd.png` + `.vtex` (max 1024, no LOD, clamp), or a flat PSD `<map>_radar.psd`.
- Overview: `resource/overviews/<map>.txt` in the **game** folder: `material`, `pos_x`/`pos_y` = world position of the image's top-left corner,
  `scale` = world units per pixel, `rotate`, `zoom`; `"verticalsections"` for stacked maps.
- Don't place `cs_minimap_boundary` entities: CS2 then draws its own minimap instead of your image.
- `tools/radar.py` renders it from the geometry (standable floors, textured, height-shaded); mg_trenchwarfare's `make_radar.py` adds a lettered grid and a `!pos`
  chat command to check alignment in game. `sv_disable_radar 1` turns it off.
