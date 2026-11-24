# Server test, 24 Nov 2026: HUD crash fixes

The goal is to confirm the new builds don't crash the box with several humans, and that the HUD still looks right.

## 1. Upload (about 20 min)

All seven are release builds, ready as they are. Upload each **game** folder (`game\csgo_addons\<addon>`) as an update to its
Workshop item, the usual way. Do the three that crashed first.

| # | Addon | Workshop item | Built | Size |
|---|---|---|---|---|
| 1 | mg_ironframe_dunes | 3841773892 | map 13:36, script 17:11 | 3.0 GB |
| 2 | mg_space_racer | 3821296722 | script 17:14 | 123 MB |
| 3 | mg_ironframe_sprawl | (yours) | map 14:06, script 17:12 | 2.8 GB |
| 4 | mg_neon_racer | (yours) | script 17:15 | 129 MB |
| 5 | mg_depth_racer | (yours) | script 17:17 | 95 MB |
| 6 | mg_freedm (Hellmatch) | (yours) | script 17:17 | 233 MB |
| 7 | mg_hellescape (Hellmatch ZE) | (yours) | script 17:17 | 141 MB |

Change note for all seven:

> Crash fix: the HUD now stays inside CS2's per-entity network limit, so many players can no longer crash the server
> (PackEntity). The GOTV / demo recorder is no longer counted as a player.

For Dunes and Sprawl, add: *The HUD is spread over 8 layout entities, so it stays complete with more players.*

Then send the box's AI [jb-box-crashes-2026-11-reply3.md](jb-box-crashes-2026-11-reply3.md). Ask it for the time each new
version is mounted.

## 2. The test (about 30 min, as many humans as you can get)

Ask the box's AI to watch its console during the test. Have someone note the human count every few minutes.

| Step | What to do | What should happen |
|---|---|---|
| A | **Space Racer:** one full race through to the results screen, then the map vote | No crash. Everyone sees the lobby, race HUD, results and vote screens |
| B | **Dunes, round 1:** everyone opens and closes the garage, fights, dies and respawns | Garage mouse works for **everyone**, not just the first player. Radar and health show for everyone |
| C | **Dunes, round end:** watch the podium | Podium shows for everyone, once |
| D | **Dunes, round 2:** play it out | No crash |
| E | **Sprawl:** one round, same checks as B and C | Same |
| F | **Anyone:** `cl_showfps 1` in Dunes, then compare with Space Racer | FPS about the same as before |

**The key check is B.** Each player after the first is put on a different HUD copy (`ifr_hud2`, `ifr_hud3`, ...). If one player
has **no HUD at all** in IRONFRAME, or their garage mouse doesn't work, that copy isn't drawing. Note who it was and the order
they joined.

Also watch for anything **doubled**: two radars, overlapping text, or another player's HUD.

### Console lines

| Line | Meaning |
|---|---|
| `HUD on: ... 8 layout copies` (`[ironframe]`, at map load) | Good: Dunes and Sprawl found all 8 copies |
| `HUD byte budget reached ...` | Fine: some HUD parts wait instead of crashing. Note the player count |
| `EncodeField overflowed` or `FATAL ERROR: PackEntity` | **Bad:** the crash is still happening. Note the map, the human count and the time |

## 3. Afterwards, send me

1. Crashed or not, per map, with the human count.
2. Anyone with a missing HUD or broken garage mouse in IRONFRAME, and their join order.
3. Anything doubled or out of place, with a screenshot if you can.
4. FPS in Dunes compared with before.
5. Any `HUD byte budget reached` or `EncodeField` lines from the box's console.
6. Memory samples around the Dunes visits, if the box's AI can export them (not needed today).

## If IRONFRAME's HUD copies don't draw

Tell me and I'll switch Dunes and Sprawl back to one HUD copy. That's a script-only change, about 10 minutes plus an upload. It
keeps the crash fix, but past about 5 players some HUD parts wait.

---

Ready-state checks done 24 Nov 17:18 (all seven scripts rebuilt: the demo-recorder check no longer reads `tv_name`, which Workshop scripts may not and which filled the console with errors; Dunes and Sprawl also carry the kill-count fix):

- All seven compiled scripts are up to date with their sources. Each has the 12,500-byte budget and the demo-recorder name.
- In Dunes and Sprawl, the test switches are off (`HUD_TEST_COPY: 0`, `SOAK_SWITCHES: false`).
- Dunes' mock test passed.
- CS2 is closed.
- `mg_freedm\backup_round00.txt` is an old round save CS2 wrote on 15 Oct and is harmless.
