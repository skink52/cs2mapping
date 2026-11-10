# IRONFRAME HUD: layout, driver API and budget

Generator `tools/hud.py` (+ `tools/hud_images.py`, `tools/hud_font.py`), driver `src/cs2/50_hud.js`, gate `create/hud_check.py`, tests
`test/hud_ids.cjs` (the panel-id budget), `test/hud_driver.cjs`, `test/hud_strings.cjs`, `test/hud_garage_turn.cjs`. Status: **written and verified
offline**; the Label text of 10 Nov 2026 (night) has NOT been seen in CS2 yet.

```
python -I tools/hud.py out/addon ironframe mg_ironframe_dunes        # xml + css + images + _gen/hud.json + build/hud_states.json; prints the id budget, fails over it
python -I ../../create/hud_check.py --addon out/addon --name ironframe --states build/hud_states.json --out build/hud/hud --check-widths 1440,1920,2333 \
  --glyph-space --allow-outside Txt --allow-outside Tx "--label-font=Noto Serif=<CS2>/game/csgo/panorama/fonts/notoserif-bold.ttf"   # ~1:40, under the watchdog
node test/hud_ids.cjs && node test/hud_driver.cjs && node test/hud_strings.cjs && node test/hud_garage_turn.cjs   # hud_strings -v lists every measured message
sh tools/mock_flows.sh        # both flows, with panelids=950 (the mock fails when the script names more panel ids)
```
Previews (16:9, 4:3 and 21:9): `preview/hud/hud_{fight,fight_cq,fight_ctf,fight_kh,lock,garage,garage_turn,intro,podium,death,spec}[_1440|_2333].png`, CS2 zones in
`hud_cs2.png`; the glyph-text set of the evening is in `preview/hud/before_idcap/`.

## The panel-id cap (10 Nov 2026, 19:50 playtest): 1024 ids per layout, and the budget
skink52: "none of my bars have anything in them, weapons section is empty", "the red marker ... is gone". The console was flooded with
`The maximum number of panel ids has been reached, no more can be referenced.` CS2's CustomHudLayout keeps a table of at most **1024 panel ids** the
script has named (SetHasClass / SetHasClassForPlayer / SetDialogVariableString...; `cmp ..., 0x400` next to the string in server.dll; the counter is a
member of the layout entity). It never frees: once full, every id not yet in it is silently never updated, and which panels die depends on
what was shown first (the garage, opened first, ate the table; the fight HUD got nothing). The "100 % neon type" was the cause: every character
cell of every dynamic text was a panel with an id (5 846 ids in the layout; a mock session named 2 644). It very likely also explains earlier
reports ("equipped weapons blank", "tracks don't respond", part of "messages cut off": cells past the cap never changing).

**The fix: one id per text.** Dynamic text is a real `<Label id=.. text="{s:v}">` set with `SetDialogVariableStringForPlayer(slot, id, 'v', text)`
(one engine call per changed text instead of one or two per character). Static captions keep the neon glyph pictures: they have no id.
Everything else already was one id per thing (a bar = one fill panel with `stL<k>` width classes; the lock bracket = two wrapper panels with a
translate class each; garage rows = a fixed window of 8 row panels; radar = 64 dot panels).

| Screen | ids before (glyph cells) | ids now | what they are |
|---|---|---|---|
| garage | 3 437 | 200 | 9 tabs, 8 rows x (button + picture + 4 texts), 8 tracks x (button + bar + 6 texts), equipped x4, frame stats, info, confirm, turn buttons |
| common (radar, mode, objectives, feed, line, pilot plate, streak) | 652 | 117 | 64 radar dots + 3 points + 2 drops, mode box, 3 chips, capture strip, badges, kill pop, 3 line rows, plate, meter |
| fight (vitals, weapons, reticle, lock, threats, buffs) | 540 | 91 | bars, 4 weapon boxes x (box + icon + 2 bars + 3 texts), lock (2 movers + state + 4 texts + 2 bars), 4 multi-lock marks x 3, 8 threats, 5 buffs |
| slates (intro, death, podium, spectator) | 941 | 35 | texts and 3 podium cards |
| cards (controls, loadout) | 275 | 17 | 2 cards, 4 icons, 11 texts |
| root | 1 | 1 | screen and team classes |
| **total in the layout** | **5 846** | **461** | budget 800 (the generator fails over it), tests fail over 950, CS2's cap 1024 |
| named in a session (mock: both flows / 64 players 120 s / the exhaustive walk) | 2 644 / 1 924 (fight only, 90 s) / - | 332 / 344 / 454 | |

- 11 Nov 2026 (S2 / S3): **480 ids** (+18): the pilot strip under the streak meter (`ifr_ident` + the Labels `ptag`, `dly`: badge tag, callsign,
  title; the daily contract nearest to done), the top pilots beside the podium (`ifr_lb` + `lbh`, `lb0n..lb4n`, `lb0v..lb4v`, `lbme`), one more
  garage tab (`ifr_gc8` PILOT + its Label; SORTIE moved to `ifr_gc9` and stays last). The PILOT and SLOTS tabs draw into the list's existing
  row Labels and the ITEM INFORMATION plate (a row's `help`): no ids of their own. `test/hud_ids.cjs` walks 473 of the 480.
- `tools/hud.py` registers every id (`reg()`, per screen), prints `panel ids the script can reference: 461 of budget 800 ...`, asserts that the
  xml holds no id it did not register, and exits non-zero over the budget. A new element that needs many ids fails the build, not a playtest.
- `test/hud_ids.cjs` walks every screen through the real driver and garage (every tab / row / column / question, every mode, 64 radar dots,
  every lock stage, cards, slates) and counts the ids the engine is handed; it also fails when an id of the layout is never referenced (a dead id
  or a hole in the walk). The mock engine counts too: `panelids=950` in `tools/mock_flows.sh` and `tools/build_all.sh`.
- The driver counts what it names (`ifrHudStats().ids`) and warns once in the console past 950; the init line says `HUD on: 461 panel ids`.
- One layout entity is enough (461 of 1024), so the HUD is NOT split over several `custom_hud_layout` entities (the cap looks per entity, from
  the disassembly only): no new map entity, nothing for 90_main.js to rebind. If the HUD ever outgrows one table, that is the next lever.
- Unknown: whether a round restart or `Reset()` frees the table. The budget assumes it never does.

**Text as Labels: what changed, what to check in CS2.** Font: `"Noto Serif", notoserif, Stratum2, Arial`, bold, upper-case, a `text-shadow` glow in the
text's colour (classes `.Tx.s<size>.c<colour>.Al<L|C|R>`; state colours are css rules on a parent, as before). Noto Serif Bold ships with CS2
(`game/csgo/panorama/fonts/notoserif-bold.ttf`, loaded by its `fonts.conf`); at the same cap height its capitals are within 2 % of the neon
glyphs' widths, so the layout held with a few boxes widened. The driver measures with the font's real advance widths (x 1.03; `hud.json glyphs.w`,
cached in `tools/hud_label_metrics.json`), so wrapping, paging, `..` shortening and `test/hud_strings.cjs` are as exact as before. Runs of spaces
are sent with no-break spaces. Player names now show non-ASCII letters (they were `?`). Unverified in CS2, in order of risk: (1) that
`"Noto Serif"` resolves (if not, the fallback is Stratum2, which is narrower: nothing is cut, the look is sans); (2) the vertical place of the
capitals in their boxes (assumes the line box is ascent + descent with the ascender at the Label's top; a few px either way if not);
(3) `text-shadow` with 8-digit colours and `white-space: nowrap` on Labels; (4) Panorama running wider than FreeType by more than 3 %.
Smaller changes that came with it: garage rows show the upgrade level on the small right-hand line (`MK III`, or `R ARM  +3` beside a slot tag)
instead of `+3` after the name; the equipped rows put it first (`MK II  DMG ...`) when the row has room; tab LOADOUT is SLOTS; KOTH chip
`CT SCORES`; CTF chip `DROP 12 S`; podium `KILLS 9 | ASSISTS 3`; a weapon whose description needs three rows shows its extra figures on the
comparison row when that is free.

## Evening playtest, 10 Nov 2026: what the HUD now teaches (offline-verified, not seen in CS2)
skink52: "many in game messages get cut off", "i don't know how to target [rockets]", "no real indication of current frags, or what overdrive /
killstreaks do, or how to use any of them", "not much is easy to understand or jump straight into", "garage ... face the mech towards player,
... option to rotate (2 buttons below their feet)".

**Messages.** What was cut, and why:
- in time: every `reply()` replaced the line at once, so "OVERDRIVE READY: hold ..." vanished the moment a bot took a crate or a trait procced.
  Now every message stays >= 1.6 s, later ones queue (8), and each has a rank: 0 ambient (other pilots' news, trait procs: only on a free line),
  1 normal, 2 important (gold type and edge: the pilot has to do something; cuts in, the interrupted message comes back). `reply()` ranks a
  message by the core event being handled (`replyCtx`, 45_features.js): no caller changed.
- in space: the line is three rows of 18 px capitals, 640 px (was two rows of 14 px, 600 px). `ifrHudWrapAll` wraps by pixel width AND cell
  count, breaks a word wider than a row, and `ifrHudLine` shows what does not fit as a second page: the line cannot drop text.
- real cuts found by the wider test: weapon box figures `100%  1200` (gatling) and `CHARGE 100%` (lasers) in a 112 px box; `120 / 600`
  (flamethrower); the garage's answer line (`Welcome back: pick a loadout and SORTIE`, one 420 px row: now two rows, `ghint2`); `ALL UNLOCKED`
  (stand-alone credits cell, never tested offline: now `UNLOCKED`); generator `CAPACITY .. REGEN .. OUTPUT ..`; `SHOULDER / PROJECTILE  RANK 5
  3 500 CR`; the sniper cannon's `IMP`; podium `TOTAL +XP +CR` at six figures; player names over ~12 wide letters in the lock box, kill pop,
  death slate, podium cards and spectator bar (now shortened with `..` by `ifrHudFitText`, never clipped).
- a cut in game is never silent: `ifrHudCut` logs `HUD text cut in <slot>: ...` once per slot.

**Lock and launchers** (core rules: a press with no enemy in the FCS cone fires unguided at the reticle; a press on a target whose lock is
building waits while held, `wp.mslWait`, and launches guided when it is done; releasing early fires unguided).
- The bracket sits ON the target: `ifr_lkx` / `ifr_lky` carry one translate class each (`stX<k>` / `stY<k>`, 20 px steps, eased 0.1 s) from
  `ifrHudProject` (the camera the adapter sends the core: `m.input.camPos / camDir`; 720 px per unit of tangent = CS2's 90 degrees across 4:3).
  States `stAcq` (thin amber corners, ACQUIRING) -> `stSoft` (SOFT LOCK) -> `stHard1..2` -> `stHard3` (red, flashing, LOCKED); name, a lock
  progress bar (`lkp`), the state word (`lstate`), range and target AP. Tones are the core's `lock` events (ui_lock2 / 3), as before.
- Every weapon box has a state row (`w<i>s`, classes `stLkNo / stLkAcq / stLkOn / stLkOut`): launchers `NO LOCK: UNGUIDED` / `HOLD: LOCK 60 %` /
  `KEEP HOLDING 60 %` / `LOCKED: FIRE` / `OUT OF RANGE` / `READY IN 5 S` / `NO AMMO` / `FIRING`; multi-lock `HOLD TO LOCK` / `NO TARGET IN
  RING` / `KEEP HOLDING: 2` / `3 LOCKED: RELEASE`; others `RELOAD 1.5 S`, `HEAT 85 %`, `OVERHEATED: WAIT`, `CHARGING 40 %`, `CHARGED: RELEASE`,
  `HOLD KEY TO BLOCK`. Multi-lock targets get a diamond each (`ifr_ml0..3`: amber blinking while locking, red when locked).

**Frags, streak, overdrive.**
- Pilot plate under the radar: YOUR TEAM / ENEMY (tickets in Conquest, your kills vs the leader in FFA), KILLS / DEATHS / ASSISTS. The mode
  box's scores sit on team-colour plates; yours is lit and underlined by the root's team class (no writes).
- Streak meter: 8 pips with gold marks at 3 / 5 / 8, `NEXT: 3 KILLS = RADAR PING` + `ENEMIES ON RADAR FOR 10 S` (numbers from `IF_FEAT.streak`).
- Overdrive block in the vitals: gauge, percentage, one line: `DEAL OR TAKE DAMAGE TO FILL` / `READY: HOLD R+E TOGETHER` (the block pulses gold) /
  `CHARGING: BLAST IN 0.8 S` (cyan; the old code compared `odPhase` with `'charge'`, the core sets 1, so this never showed).
- Buff badges say what they are and do: `DAMAGE +25 %` `12 S LEFT`, `ARTILLERY` `READY: LOCK A TARGET`, `ACE +20 % SPEED` `20 S: OVERDRIVE REFILLS`.
- Earning anything says what it is, what it does and how to use it (gold line): STREAK_TEXT, CRATE_TEXT, HINTS.od in 45_features.js.

**Jump-in help.**
- Controls card (`ifr_ctrl`, static, one class): first two spawns and first three death screens of a session, `!help` / `!keys`, and after
  holding Tab >= 0.8 s (shown on release; unverified that SHOW_SCORES reads in a mech). It covers the pilot plate while up.
- Loadout card (`ifr_load`, right side, every spawn, 8-12 s): M1 / M2 / R / E with icon, name and role (`IFR_HUD_ROLE`), the frame, its trait
  and the key that uses it (`IFR_HUD_TRAIT`; the test fails when a frame or weapon has no row).
- One-time hints per pilot and session (`ifrHudHint`, texts in `HINTS`): start, the mode's goal, first EN stall, stagger, soft lock, hard lock,
  launcher pressed with nothing in the ring, holding on a building lock, multi-lock, death -> garage, first capture zone, crate, overheat, shield.
- `AI EASY / NORMAL / HARD` (the fill skill) at the end of the objective line when it fits.

**Garage.** The mech faces the camera on opening and whenever the frame changes (no idle spin); E / R held turn it in any column (A / D still
do in the tabs); three Buttons under its feet (`ifr_grl` `<  E`, `ifr_grf` `FRONT`, `ifr_grr` `R  >`; a click = 45 degrees, eased; it
keeps turning while the mouse button is reported down); the camera pitch keeps the feet at y ~672 for every frame height and bay depth.
FRAMES are listed by class, the four Tripo frames first in each (they were rows 16-19).

## Layout (1080 high, every panel fixed and pinned; Panorama rules of docs/creation/hud.md)
**Type:** dynamic text = Labels (above); STATIC captions = neon glyph pictures, described in the rest of this paragraph (the dynamic rows of
glyph cells, their spacer classes and `glyphs.trunc` cell counts are gone). `tools/hud_font.py` bakes inscriptional serif capitals (Trajan-like; font path is one
setting: `create/fonts/Cinzel-*.ttf` if present, else Windows `timesbd.ttf`, or env `IFR_HUD_FONT`; Trajan itself is not shipped) into one png per
character and palette colour: near-white core tinted toward the colour, thin dark keyline, two baked gaussian halo layers (no run-time glow). Two masters
(cap 28 and 56 px) scaled to sizes XXL 56 / XL 36 / L 28 / M 22 / S 18 / XS 14 px cap height (14 is the floor). ~1000 pngs in `ifr/f/<cap>_<colour>_<code>.png`.
Team accent glow: `.IfrRoot.stTeamT .Txt.cAcc`; state colours are `tint(selector, colour)` rules.
**Proportional widths:** each glyph class sets its own width per size (`.sXS .G.g65 { width; margin-left/right: -pad }`, the picture includes the halo pad, so
the net advance is the glyph advance); `.G` without a class has width 0. A text slot is a box `ifr_<slot>` holding a row `ifr_<slot>_t` (`flow-children: right`,
`overflow: noclip`) = a spacer `_t_sp` + `max` cells `_t_<k>`. The driver (`ifrHudVar`) cuts the text at the cell count and at the box width using
`hud.json glyphs.w[size][code]`, writes one class `g<code>` per changed character (space = `g32`, width only; blank -> char 1 write, char -> char 2) and, for
right / centre text, one spacer class `sp<n>` (n x 2 px) that aligns it (changes only when the pixel offset changes). Left text never touches the spacer.
Cell size steps down (never below XS) until ~60 % of the slot's maxlen fits its box on average; `glyphs.trunc` lists slots whose typical capacity is below their
maxlen (the driver cuts by pixels, so real strings with narrow letters and spaces often fit more). A row taller than its box (halo bleed) is lifted with
`.Ny<k>` (translatey), never a negative margin. `hud_check` needs `--glyph-space --allow-outside Txt` for this layout.
**Pictures** (`tools/hud_images.py`): anti-aliased (4x supersampled, Lanczos), no pixel art. Weapon family icons (fight boxes, garage rows,
equipped panel), badges and part-card glyphs are backlit neon like the type (`neon()`: tinted near-white core, dark keyline, two baked halo
layers in the colour; cyan for weapons, the badge's own colour for badges, the paint's tint for paints). Part cards are a dark plate with a
sharp border and the neon glyph (or a frame's render, shrunk smoothly); the name is printed by the HUD, not on the card. All 34 weapon parts
have a family icon (the arsenal expansion 113-118 / 211-214 had none). Before / after: `preview/hud/before_neon_icons/`, `preview/hud/images_sheet.png`.
**Boxes:** sharp corners, 2 px accent border, faint inner glow (`InGlow`, a 3 px 8 %-alpha inner border; `box-shadow` is not used, unverified), garage plates carry
their title ON the top border (`gpanel`: wrapper 11 px taller, cover panel `LgBg` hides the line behind the legend). Top-bar captions stay inside.
**Glow strength:** three masters, crisp `c28` (XS, S: light halo, stays sharp), bright `b28` (M, L: halo ~45 % stronger and wider) and bright-big `b56` (XL, XXL); rows carry `Bt` / `Big`.
**No clipping:** `node test/hud_strings.cjs` loads the real `50_hud.js` + `60_garage.js`, drives the garage for every tab / row / focus column / money state / drafted part
(real `parts.json`) plus the fight, slates and message line with the longest realistic strings, and fails when the driver had to cut any string (`ifrHudCuts`).
Fixes were made at source: short weapon names for the narrow boxes (`hud.json short`, `ifrHudShort`), pixel-aware token / word wrapping (`ifrHudFitTokens`, `ifrHudWrapTokens`,
`ifrHudWrap`), shorter garage strings (tabs SHLD / LOADOUT, track labels GEN / BOOST / EFF, hint, tips, legend, DENY texts), a DMG / AMMO column header, info panel 440 x 196
with 3 description lines (frames show their trait), the message line 860 px at XS shifted right of the chat.
~5000 panel ids, ~7450 css rules.
Root `ifr_root` is invisible until `stOn`; screens are root classes `stFight stSpec stDeath stIntro stPodium stGarage`.
Groups: Fight (vitals, weapons, reticle, threats) shows in fight+spec; Common (radar, mode panel, badges, kill pop, line) in
fight+spec+death; each slate only in its screen. `.HUD_SCOREBOARD_VISIBLE .IfrRoot` collapses the whole HUD while Tab is held.
CS2 zones kept clear at 1920 and 2333: mode panel at y 72 under the team counter and left of the kill feed (the real feed stays
visible), bottom cluster above the money row, nothing left of x 576 below y 600 (the chat); slates and garage use chat_top 800.

| Element | Panels / classes |
|---|---|
| Vitals (bottom centre, left half) | AP ladder `ap` (green/amber/red by step) + `ap`/`apmax` text; EN ladder `en` + text, `ifr_enbar.stStall/stOver`, `ifr_entag.stOn`; stagger ladder `stg`, `ifr_stg.stStaggered` (flash + tag); QB ticks ladder `qb` (4); `ifr_lag.stOn`, `ifr_boost.stOn/stAssault` |
| Weapon boxes `ifr_w0..3` (ra, la, rs, ls) | icon `ifr_w<i>i.stW<family>`; texts `w<i>n` (name) `w<i>a` (ammo); ladders `w<i>m` (mag/heat/charge) `w<i>c` (cooldown); flags `stReload stEmpty stHot stCharge stNo stSel`, pulse `stPop/stPop2` |
| Reticle (centre) | `ifr_cone.stC0..4` (FCS cone size: a thin broken ring 128 px, scaled 0.7-1.1; Nov 2026: was 300-400 px), `ifr_lock.stSoft/stHard1..3` (3 beep stages), texts `tname rng`, ladder `tap`; `ifr_assist.stOn`; `ifr_shield.stOn` (spawn protection ring, 200 px); `ifr_stgring.stOn`; `ifr_mwarn.stOn` |
| Threats | `ifr_th0..7` (0 ahead, clockwise) `stLock stLaunch stClose` |
| Radar 280x280 (top left, where CS2's own radar sits; `sv_disable_radar 1` hides that one) | 64 dots `ifr_rd<n>`: grid `stG0..575` (24x24, one class = position, no class = hidden), `stA stE stBig stBoss stTgt`; points `ifr_rdA/B/C` + `stOwnT stOwnCT stCap`; drops `ifr_rdDa/De`; text `rrange` |
| Mode panel (top centre, 560 wide: clears the kill feed down to 4:3) | mode tag `ifr_mtag.stM<tb cq sk so kh ctf>` (own colour per mode) + text `mode` (TDM / CONQUEST / FFA / SORTIE / KOTH / CTF); texts `scoreT clock scoreCT`, objective line `sub`; `ifr_modebox.stBoss` + ladder `bap` |
| Objective tier (y 154; Conquest / Sortie / KOTH / CTF) | `ifr_obj.stOn`; 3 chips `ifr_ob0..2` (`stOn`, bar colour `stT stCT stCont`) with letter box `ifr_obk<i>.stOwnT/stOwnCT/stCap`, texts `ob<i>k` (A / B / C, T / CT) and `ob<i>t` (T HOLDS, CT 64 %, CONTESTED, TAKEN 60 %, DROPPED 12, T SCORING), ladder `ob<i>p`. Conquest A B C left to right; KOTH and the Sortie beacon in the middle; CTF the T flag left, the CT flag right |
| Capture strip (y 210) | `ifr_cap.stOn/stT/stCT/stCont/stWarn`, text `capl` (CT CAPTURING B 64 %, T NEUTRALISING A, B CONTESTED, FLAG IN HAND 60 % HOME, ENEMY HAS YOUR FLAG 40 %, T FLAG DROPPED 12 S), ladder `capbar` (40 steps); the zone the viewer stands in wins over the others |
| Feed | `ifr_kill` (text `kill`, `stOn stPop stPop2`), `ifr_xp` (`xp`), `ifr_streakb` + `streak`, `ifr_bounty`, `ifr_rookie`, line `ifr_line` (`stOn`; two rows `line line2`, 600 px, shifted 160 px right so the left end clears CS2's chat down to 4:3) |
| Slates | intro `arena imode` (full mode name, XL) `ifr_imbar.stM<mode>` (a bar in the mode colour) `iobj iobj2` (the objective) `ihint`; death `killer kweapon respawn`; podium `phead psub pn0-2 ps0-2 pt0-5l/v pfoot`, cards `ifr_pc0-2.stT/stCT/stMe`; spectator `spec` (y 716, under the reticle) |
| Garage (armory terminal; aspect-safe from 4:3 / 1440 wide to 21:9, Nov 2026) | root `ifr_gpage.stCol0/1/2` (focus: tabs / list / tracks). Left column (pinned left, x 20-568): top bar `gcred gkda`; ARMORY: 9 tab Buttons `ifr_gc<i>` (`stSel stOff`, text `gcn<i>`), 8 row Buttons `ifr_gr<i>` (`stSel stOwned stLocked stEquip stBuy stPoor stOff`, texts `gr<i>n gr<i>t gr<i>c gr<i>r`, icon `ifr_grp<i>.stP<partkey>`), scroll `glist`, thumb `ifr_gthumb.stOn/stS0..10`, Buttons `ifr_gup ifr_gdn`, `gtip gtip2`; EQUIPPED WEAPONS `ifr_ge0..3.stEmpty` (key tag M1 / M2 / R / E, icon `ifr_gep<i>`, `ge<i>n` name + level, `ge<i>s` DMG / rate or cooldown / magazine or EN). Centre column (pinned centre + 60, 400 wide; 580-980 at 1440): `gbay gbay2` (what the bay shows), confirm bar `ifr_gcbar.stOn` (`gconf gconfb` the question on two rows, `gconf2`, Buttons `ifr_gcy` / `ifr_gcx`), legend `glegend glegend2`, FRAME statistics `gfn gft` + 7 ladders `gs0..6` + `gs<i>v` (`ifr_gsb1/2.stOver`, `gwarn`). Right column (pinned right, 430 wide, from y 196 under the kill feed): top bar `gmap grank`; UPGRADE TRACKS: 8 Buttons `ifr_ur<i>` (`stSel stOff stMax stPoor stDis`, texts `ur<i>n s c l a b`, pip ladder `u<i>`), `gutitle`; ITEM INFORMATION `gpn gpt gpd gpd2 gpd3 gpk gcmp ghint` (a weapon: its description on two rows, extra figures on the third). 10 Nov 2026 playtest: at 4:3 the old right-pinned ITEM INFORMATION covered EQUIPPED WEAPONS (it looked blank) and the 880 px centre block lay over the tracks |

Buttons are the only hittest panels. 60_garage.js turns on `SetInputCaptureEnabled(slot, true)` (via `ifrHudCapture`) while the garage is open and
handles `Instance.OnCustomHudClicked`: a tab click selects the tab, a row / track click selects it and a second click on the selected one picks / asks to upgrade,
`ifr_gup/ifr_gdn` scroll a page, `ifr_gcy/ifr_gcx` confirm / cancel. The keyboard path works without the mouse.

### Garage (rebuilt Nov 2026 from skink52's UI brief)
Keys: three focus columns. Tabs: W/S change tab, Space opens the list, A/D (held) rotate the mech. List: W/S, Space equips (arms / shoulders: R and L in turn, R first;
a part already in one hand goes to the other; Nov 2026: every pick used to go to R) or asks
to buy, A back to tabs, D to the tracks, F asks to upgrade, Ctrl back. Tracks: W/S, Space or F asks to upgrade, A / Ctrl back. A buy or upgrade shows the confirm bar
("Buy <name> for <cost>? Space confirm / Ctrl cancel"). Tabs: Primary = arms, Secondary = shoulder weapons, Special = shoulder `ability` parts, Utility = generator / booster / FCS.
Tracks = the equipped parts' `upgrade` (frame AP, weapon damage, generator capacity, booster efficiency, FCS lock time, ability stats), level pips, `now -> next` from the core's formulas, cost `cost x (level+1)`.
Everything shown is real `parts.json` / core data; nothing is invented.
Preview: `60_garage.js` places the draft loadout (legs, upper, weapon props, paint) on a bay and points the player's controlled camera at it; the highlighted list item is swapped in
so an item can be looked at before it is bought. Bay = `info_target ifr_hangar` + ((slot%8 - 3.5) x 700, (slot/8%8 - 3.5) x 700); without it the bay is the booth position + 600 u up and a
one-time warning is logged. The map needs a lit hangar room with an `info_target` named `ifr_hangar`. Props are released when the garage closes or the player leaves (`ifrHudOff`).
State shape for `ifrHudGarage(slot, state)`: see the comment above the function in 50_hud.js (rows / tracks / info / weapons are pre-formatted by `garageDraw`).

## hud.json (baked as `HUD`)
`{layout, root, budget, panels: {id: {classes, vars, prio, ranges?: [[prefix, lo, hi]]}}, ladders: {name: {panel, steps}},
text_slots: {name: {panel, max}}, screens, weapons, families, radar: {cells, dots, size}, garage: {cats, rows, stats, parts}}`.
`prio` is the governor band of the panel (0 warnings, 1 lock, 2 gauges, 3 text). Ranges keep the 576 grid classes compact.

## Driver API (`50_hud.js`; every call is a no-op when no hud.json is baked)
Primitives: `ifrHudInit()`, `ifrHudSet(slot, panelId, cls, on)`, `ifrHudVar(slot, name, text)`, `ifrHudNum(slot, name, n, step,
prefix?, suffix?)` (rounds to step, hysteresis 0.6 step, thousands spaced), `ifrHudLadder(slot, name, frac)`, `ifrHudLine(slot,
text, seconds, queue?, prio?)` (three rows, wrapped and paged; `queue` = in order after what shows; prio 0 ambient / 1 normal / 2 important),
`ifrHudHint(slot, key, text, seconds?)` (once per pilot and session), `ifrHudHinted`, `ifrHudCount(slot, 'spawns' | 'deaths')`, `ifrHudCard(slot, 'controls' | 'loadout', seconds)`,
`ifrHudLoadout(slot, mech, seconds?)`, `ifrHudFitText(slotName, text, pre?, post?)` (shortens with `..`), `ifrHudWrapAll(slotName, text)`, `ifrHudProject(me, target)`, `ifrHudPop(slot, panelId)`, `ifrHudScreen(slot, name)`, `ifrHudTeam(slot, team)`, `ifrHudReset(slot)` (full
redraw; also what 90_main's `hudOff` calls), `ifrHudOff(slot)` (forget a slot), `ifrHudTick()` (flush; last in the think),
`ifrHudStats()`, `ifrHudPending(slot)`. Unknown panel / class / text slot / ladder names **throw**.

Helpers, with the exact input shapes (what 90_main.js / 60_garage.js pass today):
- `ifrHudVitals(slot, m)`: `m` = IF_Mech: `ap apMax en enMax enStalled(s) enOver? stagger staggerMax staggered(s) protect(s) dropT
  landLag(s) boosting assault qbCd(s)`.
- `ifrHudWeapons(slot, weapons)`: `m.weapons[4]` (ra, la, rs, ls) of IF_Weapon: `part w ammo(reserve) mag magSize cd heat overheat
  charge charging reloading charges firing raised lastShot` (a change of `lastShot` pulses the box; `firing`/`raised` = stSel).
- `ifrHudLock(slot, lock, threats, target, me)`: `lock` = `m.lock {target, stage 0|1|2, t}` (stage 1 shows stSoft then
  stHard1/2 as `t` nears `me.lockHard`, stage 2 = stHard3); `threats` = `m.threats [{kind:'lock'|'launch'|'close', dir 0..7 |
  angle deg | pos{x,y,z}}]` (any launch also lights MISSILE); `target` = the locked IF_Mech or null (`name ap apMax pos`);
  `me` = the viewer's IF_Mech (**pass `m` as the 5th argument**: the range, the cone size and threat directions from `pos` need it).
- `ifrHudRadar(slot, dots, myYaw, myPos)`: `dots [{x, y (world offsets from the viewer), team, kind:'mech'|'bounty'|'target'|'boss'}]`,
  `myYaw` = torso yaw, `myPos` = world position or null (empties the radar). Range `CONFIG.RADAR_RANGE` (6000). Ally colour =
  the team given to `ifrHudMode`. Points A/B/C come from `ARENA.points` with owners from the last `ifrHudMode`; the drop zones from
  `ARENA.drops.t/ct[0]`. Call every 8th tick (the adapter does).
- `ifrHudMode(slot, match, myTeam)`: `match` = `game.match {mode 'tb'|'cq'|'sk'|'so'|'kh'|'ctf', phase, timeLeft, scores{2,3}, tickets{2,3}?,
  points[{id, owner, progress, capTeam, contested, pos, radius, nT?, nCT?, scoring?}], killTarget, wave?, waves?, boss?{ap, apMax}, flags?{2, 3: {state, home, pos,
  carrier, returnT, returnMax?, carrierTeam?}}, hillLeft?, allPoints?, khTarget?, ctfCaptures?}`; `myTeam` 2|3 sets the accent (every 16th tick is fine). It draws the
  mode tag, the objective line, the objective chips and the capture strip; the fields marked ? are read defensively (with an older core a point counts as changing
  hands while 0 < progress < 1). "The zone I stand in" uses the viewer position from the last `ifrHudRadar` call.
- `ifrHudSlate(slot, kind, data)`: `'intro' {title, arena, mode, objective?}` (the objective defaults to the mode's goal with the round's numbers) · `'death' {killer, weapon, respawn (s; the countdown ticks in the
  driver)}` · `'podium' {winner, podium:[{slot, name, kills, team}] (90_main.js podiumCards: the core's round_end podiumInfo, AI fill included), me: pilotSummary, team}` (VICTORY/DEFEAT/ROUND OVER, kills/assists,
  captures, damage, best streak, total XP/CR) · `'spectator' {name, slot}` · `'none'` (fight HUD) · `'off'`.
- `ifrHudGarage(slot, state)`: `{tabs[], tab, col (0 tabs, 1 list, 2 tracks), rows[{name, type, c, r, state:'owned'|'locked'|'equipped'|'buy'|'poor', pic}] (visible 8), sel, scroll, total,
  tracks[{n, s, c, l, a, b, frac, state:'up'|'max'|'poor'|'dis'}], urow, utitle, budgets{weight, load, en, output, valid, deny, ap, walk, boost, qb}, lock, frame{name, type},
  top{map, credits, kda, rank}, bay, bay2, confirm{q, hint}|null, info{name, type, lines[3], key, cmp}, weapons[4]{pic, name, stats}, legend, tips[2], hint, pending}`. All strings are pre-formatted by `garageDraw`.
  Each section is drawn in its own try/catch (a throw is logged once as `garage HUD section <name>` and never blanks the others); the equipped weapons go first.
  `ifrHudCapture(slot, on)` toggles the mouse capture and remembers it: `ifrHudReset` turns it back on after `ResetForPlayer`, and `ifrHudKeepCapture(slot)` (60_garage.js,
  every 0.5 s while open) re-enables it when `IsInputCaptureEnabled` says it was dropped. 60_garage.js logs each button id the first time it is clicked (`HUD click <id>`).
- `ifrHudFeed(slot, {kill?, xp?, streak?, bounty?, rookie?})`: kill confirm pop (3 s), XP ticker (2.5 s), badges. Not called by
  the adapter yet: hook it to the `kill` event (`kill: nameOf(victim)`, `xp: 40`), `bounty`, `streak` and the rookie-shield flag.

## Budget (per player; harness figures)
Writes = engine calls: a class change, or a Label's text (one call per changed text). Full refresh of a fight
state with 20 radar dots, a lock and 2 threats: **135** (394 with glyph cells: a text is one call now, whatever its length); redraw after reset: **136**; busy tick (EN and AP step, a shot pulse, two dots moving a cell, a lock beep):
**19**; idle tick: 0 (the clock: 1 write a second). The lock bracket costs 2 writes per 20 px it moves on an axis. Garage first draw **140** (1 026 with glyph cells), a row move **2** (rows are pre-formatted).
Radar: 2 writes per dot that moved a cell, 2 per dot appearing, 1 per dot vanishing; the governor spreads a big refresh over ticks.
Governor: 900 writes per server tick server-wide (`CONFIG.HUD_BUDGET`), bands warnings > lock > gauges > text, odd/even player
half first on alternating ticks; the harness checks the cap, the halves, change-only, ladder clearing and the reset redraw.

## Open items for the adapter / core authors
- Pass `m` as the 5th argument of `ifrHudLock` (range, cone, threat directions). `m.threats` entries need a direction (`dir`,
  `angle` or `pos`), or only the MISSILE flag shows.
- `ifrHudFeed` is unused until the kill / XP / bounty events are wired; `m.enOver` (generator over-drawn) is read if the core sets it.
- Loading slides: hud.py preloads `map_icons/screenshots/1080p/<map>*.png`, the radar psd and the map icon only if they exist when
  it runs (a missing url breaks the css compile): run it after `loading.py` in the build.
- Unverified in CS2: `border-radius` on the radar dots, `scale3d` cone classes and the `transition` on grid moves (the HUD works
  without them), `text-shadow` on Labels.
