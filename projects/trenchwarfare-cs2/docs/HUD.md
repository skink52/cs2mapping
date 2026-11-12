# mg_trenchwarfare HUD

AI-generated (Claude) for skink52. Remaster step 8 (12 Nov 2026). Status: **simulated** (layout check `tools/hud_check.py`, the mock
engine reading the same xml / css). Nothing in this layout has been compiled or seen in CS2 yet. How it is built, the art and what
only CS2 can confirm: [PRESENTATION.md](PRESENTATION.md). Names shared with the map and the script: [CONTRACT.md](CONTRACT.md).

## HUD contract

Every panel id the script writes, how, and the classes it switches. `tools/tw_hud.py` reads the table between the markers and exits 1
if the layout lacks an id, if a class has no css rule, if the script (`src/modules/*.js`: `hText`, `hClass`, `hSwap`, `placeMarker`)
writes an id that is not in the table, or if a table id is no longer written by the script. `tools/check_contract.py` and
`test/mock.mjs` check the script against the same xml / css independently.

Kinds: **text** = `hText` (dialog variable `v` of a `{s:v}` Label, `SetDialogVariableStringForPlayer`); **class** = `hClass`
(`SetHasClassForPlayer` on / off); **swap** = `hSwap` (one class of a group at a time: marker steps, needle angles, the map picture).
A step range `x0..x191` means every class from the first to the last. The layout has no other dynamic ids; static art has no id
except the containers named in the css (`tw_dash`, `tw_dashrow`, `tw_side`, `tw_counter`, `tw_lamps`, `tw_fly_help`, `tw_tside`, and the
four dial faces `tw_g_bank`, `tw_g_asi`, `tw_g_alt`, `tw_g_rpm`).

<!-- HUD-CONTRACT-BEGIN -->
| Panel id(s) | Kind | Classes / steps | Written by (module: function) | What it is |
|---|---|---|---|---|
| `tw_banner` | class | `show` | 90_main: thinkPlayer (5 s after `banner()`) | headline plate, top centre: the role after a deploy, a front headline when an area opens |
| `tw_banner_title`, `tw_banner_sub` | text | | 40_hud: banner, headline | headline and its second line |
| `tw_brief` | class | `show` | 90_main: thinkPlayer (briefing room) | the orders sheet while waiting to move up |
| `tw_brief_role`, `tw_brief_l1`, `tw_brief_l2`, `tw_brief_l3`, `tw_brief_count` | text | | 90_main: thinkPlayer | role, three lines of orders, the countdown |
| `tw_status` | class | `show` | 90_main: thinkPlayer; 60_air: drawFlight (hides it) | role card under the radar |
| `tw_st_role`, `tw_st_l1`, `tw_st_l2`, `tw_st_l3` | text | | 90_main: thinkPlayer | role and three status lines (rifle / streak / kills, crew / tube / mortar kills, lives) |
| `tw_toast` | class | `show` | 90_main: thinkPlayer | one-line message under the crosshair |
| `tw_toast_text` | text | | 40_hud: toast | the message (up to two lines) |
| `tw_info` | class | `show` | 90_main: thinkPlayer | orders card, right (role commands, `!roles`) |
| `tw_info_title`, `tw_info_l1`, `tw_info_l2`, `tw_info_l3`, `tw_info_l4`, `tw_info_l5`, `tw_info_foot` | text | | 40_hud: info, roleCard; 90_main: `!roles` | card title, five lines, footnote |
| `tw_prompt` | class | `show` | 90_main: thinkPlayer | the context prompt (dressing station, ammunition box, table) |
| `tw_prompt_text` | text | | 90_main: thinkPlayer (from tickMortar / tickAir) | the prompt |
| `tw_target` | class | `show` | 70_mortar: drawSight; 90_main: thinkPlayer (hides it) | the mortar plotting board |
| `tw_tmap` | swap | `mt`, `mct` | 70_mortar: enterSight | the team's trench map (enemy line at the top) |
| `tw_ret`, `tw_lock`, `tw_imp0`, `tw_imp1`, `tw_imp2`, `tw_pit` | class + swap | `on`; `x0..x191` | 70_mortar: placeMarker | marker column: shown, and its step across (0 = left) |
| `tw_rety`, `tw_locky`, `tw_imp0y`, `tw_imp1y`, `tw_imp2y`, `tw_pity` | swap | `y0..y191` | 70_mortar: placeMarker | the marker inside its column: step down (0 = top) |
| `tw_t_range`, `tw_t_grid`, `tw_t_tube`, `tw_t_state` | text | | 70_mortar: drawSight | range, grid square, tube state, what to do next |
| `tw_fly` | class | `show` | 60_air: drawFlight, endFlight | the flight instruments |
| `tw_n_asi`, `tw_n_alt`, `tw_n_rpm`, `tw_n_bank`, `tw_card` | swap | `a0..a71` | 60_air: drawFlight | needle / compass card turned by N x 5 degrees (`rotateZ`) |
| `tw_alt_drum`, `tw_hdg_txt`, `tw_ammo_txt`, `tw_fly_info` | text | | 60_air: drawFlight | altitude drum, heading, rounds left, lives / kills / re-arm line |
| `tw_bomb1`, `tw_bomb2` | class | `on` | 60_air: drawFlight | bomb lamps |
<!-- HUD-CONTRACT-END -->

56 ids, 4 groups of stepped classes (`x0..x191`, `y0..y191`, `a0..a71`, `mt` / `mct`), 2 toggles (`show`, `on`); the layout holds 67
panel ids in all (the 56, plus the 11 static ones above), far under CS2's 1024 per layout. Marker steps: step k sits at
`(k + 0.5) x 640 / 192` px on the 640 px map = `CONFIG.TARGET_STEPS` (192, `out/hud.json` `steps`); the map covers
`CONFIG.TARGET_EXT` (4600) either side of the centre (`tools/render_sight.py`).

## Where things are (1080 high; x at 1920 wide)

| Panel | Box | Notes |
|---|---|---|
| `tw_banner` | centre, y 84, 880 x 120 | under CS2's team counter (ends y 66), left of the kill feed (x 1490+) |
| `tw_brief` | centre, y 214, 760 x 430 | a printed field-message form; 760 wide so it clears the chat box (x < 576) while someone types |
| `tw_status` | left 18, y 330, 400 x 150 | under CS2's radar, above the chat |
| `tw_info` | right 22, y 214, 520 x 330 | under the kill feed (ends y 190) |
| `tw_prompt` / `tw_toast` | centre, y 598 / 662, 700 x 52 / 760 x 70 | under the crosshair, inside the centre column the chat leaves free |
| `tw_target` | centre + 80, y 196, 920 x 690 | the plotting board: 640 px map, the ledger card right (x 580-1500 at 1920: clear of the chat and under the kill feed) |
| `tw_fly` | full screen | help line right y 724, info line centre y 764, dash centre y 800 (760 x 196, five 128 px gauges), side plate (rounds, bomb lamps) at x W/2 + 390, y 812 |

The checked widths are 1920 and 2333 (21:9); pictures are also drawn at 1440 (4:3). CS2's own HUD places (kill feed, team counter,
money / health row, the chat box while typing) come from `hud_check.py`'s `cs2_zones()`.
