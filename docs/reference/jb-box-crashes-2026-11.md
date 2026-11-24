# JB box crashes, 20-24 Nov 2026: what the map side knows, what it changed, and what we need from the box

For the box operator's assistant. Written by the map side (the authors of Space Racer / Neon Racer / Depth Racer, IRONFRAME Dunes /
Sprawl, Hellmatch and Hellmatch ZE). Goal: find the exact limit behind the HUD crashes and the source of the Dunes memory growth,
so the maps can be tuned to them instead of guessed at. Please answer in the format at the end (section 8).

State as of 24 Nov 2026, 12:40 AEDT: everything we can do without data from the box is done. **None of the changes below are on the Workshop yet**: the box still runs the old versions
until each map is updated (section 6, item 6 tells us which versions it mounts).

## 1. The crashes and where each stands

| When (AEDT) | Map | Exit | Cause | Map side |
|---|---|---|---|---|
| 20 Nov 23:37 | mg_space_racer | 139 SEGV | serializer overflow in the custom HUD's panel-ID field (your report) | HUD class cap + cleanup made, not uploaded |
| 23 Nov 01:07 | mg_ironframe_dunes | 137 OOM kill (cgroup) | memory; last allocation in HLTVServerAsync, 2 min 21 s after the map load | one cause fixed, the rest open (section 4); not uploaded |
| 24 Nov 01:53 | mg_space_racer | 139 SEGV | `CCSCustomHudLayout.m_vecClassNames` overflow, then fatal `PackEntity` (your report) | HUD class cap + cleanup made, not uploaded |
| 24 Nov 02:40 | mg_ironframe_dunes | 139 SEGV | the same `m_vecClassNames` overflow on IRONFRAME's own HUD (your report) | HUD class cap + cleanup made, not uploaded |

**The HUD overflow is the cause of the three segfaults.** Each map's script switches CSS classes on its `custom_hud_layout`
per player, and that state is what overflowed. The exact limit is still unknown, so the cap below is a provisional number.

## 2. What the maps do now (all seven addons, deployed and compiled on our side, not uploaded)

Maps changed: mg_space_racer, mg_neon_racer, mg_depth_racer (one shared script), mg_ironframe_dunes, mg_ironframe_sprawl
(one shared script), mg_freedm (Hellmatch), mg_hellescape (Hellmatch ZE).

1. **Class cap.** Each script counts the classes it has switched on for all players together and never goes past
   `CONFIG.HUD_CLASS_CAP` = **3000** (provisional). Every player with a HUD gets an equal share; the screen state (race / lobby /
   results, fight / garage, status bar root) always goes out; anything past the share waits and is sent when there is room.
   When the cap is reached the console says once a map: `HUD class cap reached: N players share 3000 classes; parts of the HUD wait`.
2. **Hidden screens are cleared.** Classes on hidden panels are still networked, and every HUD left many on: the racers' lobby
   text during the race, race readouts and dots in the lobby, the results board into the next race, the vote box; IRONFRAME's
   unused radar dots and released teammate marks; Hellmatch's status bar in the lobby.
3. **Fewer classes per item.** Racer minimap car dots 4 -> 2 and only the **12 nearest cars**; IRONFRAME radar dots are
   ally-coloured by default (one class less) and the radar draws the **nearest 12 mechs** (was every mech, up to 64).
   Animation classes dropped (racer pop / pulse, IRONFRAME pops except the hit markers, which need theirs to show).
5. **Known lines as one picture.** A pixel-text row costs one class per letter. Lines whose text is known ahead (racers: the car
   line, ability names, centre messages, track names; Hellmatch / ZE: every fixed text in their scripts, e.g. the spectator
   prompts) are now one picture on the row panel: one class instead of 10-45. Lines with names, times or counts stay letter by letter.
4. **No map runs the GOTV client as a player any more.** CS2 reports `IsBot()` false for it, so every script took it for a human:
   IRONFRAME put it on a team and gave it a mech, cameras and a HUD; the racers auto-joined it to a team and, like Hellmatch and
   Hellmatch ZE, drew a HUD for it, whose classes counted against the same overflowing state. It is now recognised by name
   (`tv_name` when the script can read it, else SourceTV / CSTV / GOTV) and left out. If the box sets a custom `tv_name` the
   scripts read it, but please tell us the value (section 6, item 4).

Classes switched on at once, all players (mock engine, peak):

| Map | 12 humans: before -> now (busiest player now) | 64 humans: before -> now |
|---|---|---|
| Space / Neon / Depth Racer | 3 617 -> 1 924 (190) | 22 995 -> ~3 000 (cap) |
| IRONFRAME Dunes / Sprawl | ~1 300-2 250 (varies run to run) -> 1 075 (126) | ~10 200 -> ~3 000 (cap) |
| Hellmatch | 1 277 -> 971 (120) | 6 240 -> ~2 950 (cap) |
| Hellmatch ZE | (not measured before) -> ~1 300 (140) | (not measured before) -> ~2 950 (cap) |

**Note on the live Dunes crash with five humans** (your review): five IRONFRAME players held roughly 150-190 classes each, about
950 together, far under our 3000 cap, so the cap as shipped would not have prevented it. Our working hypothesis is a vector of about
**1024 entries counting real clients only** (bots and GOTV may not count, which would explain why our local floods never overflowed).
If that holds, the cap must come down to under 1000 and the HUDs need text labels (dialog variables) instead of letter classes;
a real-client test on our side and your exact error lines (section 6, item 1) will settle it.

At 12 humans no map reaches the cap, so the HUDs look as before. Near a full server parts of each player's HUD wait (lower text
lines, other cars' minimap dots, distant radar dots). **Whether 3000 is safe, too low or too high depends on the real limit**:
section 6, item 1 is what we need for that.

## 3. HUD overflow: what we measured locally

Local dedicated server (Windows, same CS2 build family), bots plus GOTV, no human clients:

- A layout keeps at most ~1024 distinct **panel ids** and ~1024 distinct **class names**, both for the life of the map. Past either,
  the engine logs `[custom_hud] The maximum number of panel ids has been reached ...` / `... class names has been reached ...` and
  ignores the new ones. **No crash.** Name length made no difference (48-character names hit the same count). Our maps use far
  fewer names (about 200-450).
- 20 480 (player, panel, class) entries switched on, over 60 bot slots or all on the GOTV slot: **no overflow, no crash.**
- So the overflow seems to need something the local test lacks. Our best guess is **real human clients**, with per-player class
  state being serialized for each of them. The crashes came at the moments with the most HUD state (race results, mid-round), which
  fits. If the limit counts entries for human clients, the old Space Racer numbers point at roughly 4 096; unconfirmed.

## 4. Dunes memory (the 23 Nov OOM)

Local soak (bots joining and leaving, GOTV on, `tv_delay 30`): the cs2 process's memory on de_dust2 before and after each 200-300 s
Dunes visit (the last sample of each de_dust2 phase). Single runs swing by about 100 MiB, so read the numbers as sizes, not exact values.

| Test | Memory kept after visit 1 / visit 2 |
|---|---|
| Stock de_mirage (control) | +64 / +10 MiB |
| de_mirage with all 33 of IRONFRAME's game cvars | +74 / -21 |
| Dunes, GOTV **off** | +103 / +2 |
| Dunes **without its script** | +141 / +27 |
| Dunes, full play, before the GOTV fix | +500 / +340 |
| Dunes, full play, after the GOTV fix | +355 / +214 |
| Dunes, script loaded but every part of its tick off from the first tick (no mechs, no props) | +190 / +57 |
| the same plus 200 idle props spawned from its template | +178 / +32 |

- With GOTV on and Dunes being played, a visit keeps a few hundred MiB the process never gives back, arriving in one step about
  2:00-2:20 after the map loads (`tv_delay 0` and forced round restarts change nothing; nothing in the script fires at that time).
  The live kill came 2:21 after the load.
- The script loaded but idle, its game cvars, and idle spawned entities add little. The memory comes with play itself (mechs and
  props being drawn, moved and animated) while GOTV is on. What GOTV keeps is engine-side; we can't narrow it further locally.
- Fixed: the GOTV client being run as a player (section 2, item 4), which was the largest single part we found.
- Until we know more, each Dunes visit ratchets the process's memory up. **A restart between maps above a memory mark (or a nightly
  restart) avoids the OOM.** With an 11 700 MiB limit and no swap, 21 h of uptime plus one Dunes visit was enough.
- Section 6, item 7 (memory samples around a Dunes visit on the box) tells us whether the box shows the same step and how big.

## 5. What would help most, in order

1. The exact overflow lines (section 6, item 1): they may state the real limit outright.
2. The human count at each crash (item 2): with our per-player numbers that brackets the limit.
3. Memory samples around a Dunes visit (item 7): to see whether the box shows the same step as our local soak.

## 6. What we need from the box

1. **The exact console lines around each segfault** (24 Nov 01:53 and 02:40, and 20 Nov 23:37): the overflow line(s) in full,
   with any numbers (bits, bytes, element counts, field size), the `PackEntity` line, and the 30 lines before them. Redact player
   names / IPs as usual, but keep every number and entity / field name.
2. **For each crash:** humans connected, bots, GOTV / CSTV clients connected (`tv_status` if it was logged), `sv_maxplayers` / `-maxplayers`.
3. **How often the soft limits fired** on each crashed map run: the counts of `[custom_hud] The maximum number of panel ids has been
   reached` and `... class names has been reached`, and their first timestamps. After our update: also any
   `HUD class cap reached` lines (they mean our cap is holding HUD parts back on that map).
4. **GOTV settings:** `tv_enable`, `tv_delay`, `tv_maxclients`, `tv_name`, `tv_broadcast`, `tv_snapshotrate`, and whether a demo
   plugin records (`tv_record`) the whole time.
5. **Any plugin on the box that touches a custom HUD** (`custom_hud_layout`, `SetHasClass*`, `SetDialogVariable*`), or that adds
   its own HUD entity on these maps.
6. **Which map versions were running:** the Workshop item ids and their update times as the box had them mounted (so we know when
   the updated maps arrive).
7. For the memory issue, if you can: **cgroup memory samples every 30 s** (`memory.stat` anon and file, or the process RSS) with a
   line at each map change and each GOTV start / stop, over a few hours that include a Dunes visit.

## 7. Experiments that would settle the HUD limit (only if you have a staging box)

We can supply a probe build of Dunes. Its script has test inputs (off in every release build) that switch on HUD classes in fixed
steps and log the running total:

- `ifr_dbg_hudflood`: 512 more (player, panel, class) entries a call, few distinct names, spread over player slots 1-60.
- `ifr_dbg_hudflood_uniq` / `_long`: 512 / 128 more, each with its own class name (short / 48 characters).
- `ifr_dbg_hudflood_gotvmany`: 512 more on slot 0 only.

Each is a `RunScriptInput` on the map's `point_script` named `ifr_script`. On our server `ent_fire ifr_script RunScriptInput <name>`
from RCON reached nothing; a plugin calling `AcceptInput("RunScriptInput", ..., "<name>")` on that entity works. With **two or three
real clients connected**, firing `ifr_dbg_hudflood` every few seconds until the console shows the overflow (or the step before it)
gives the real limit. The flood targets slots 1-60, so the connected clients must sit in those slots.

## 8. Answer format

```
crash: <date time>  map: <map>
console (verbatim, redacted names/IPs only):
  <lines>
humans: N  bots: N  gotv clients: N  maxplayers: N
soft-limit lines on that run: panel ids N (first at hh:mm:ss), class names N (first at hh:mm:ss), HUD class cap reached: N
gotv: tv_enable=.. tv_delay=.. tv_maxclients=.. tv_name=.. tv_broadcast=.. recording=yes/no
plugins touching custom HUDs: <none | list>
workshop items mounted: <id> <updated>
memory samples: <attached file name | none>
```
