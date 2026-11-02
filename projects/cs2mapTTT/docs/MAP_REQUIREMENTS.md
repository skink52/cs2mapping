# What ttt.js needs for the ported TTT maps: status

Requirements from the cs2mapping ports (ttt_minecraft, ttt_cg_skyscraper_2017), 29 Oct 2026, and how cs2mapTTT covers them.
Mock-engine tested only; in-game checks are in [../TESTING.md](../TESTING.md).

| # | Requirement | Status |
|---|---|---|
| 1 | Round reset through logic_auto OnMultiNewRound and map cleanup | By design: every TTT round ends with `FireWinCondition` (or the round clock as fallback), a real CS2 round end, so CS2 restarts the round, respawns map entities and fires OnMultiNewRound. Check in game. |
| 2 | ttt.js and `<map>_io.js` both hook damage / reset | Two point_scripts each get their own callbacks. The io script only aborts damage from its pushable props under 150 u/s; ttt.js only changes player-on-player damage (karma, hidden kills) and lethal hits. No overlap expected; check in game that both run. |
| 3 | Both spawn sets used | Players stay on T and CT (roles are separate from teams), so both sets are used. |
| 4 | Gold block into the traitor tester | Carry: any role, no mass limit; if the aim trace misses a debris object, the nearest carryable entity on the aim line is taken. `ttt_convert.py` sends the OnStartTouch of every trigger filtered to one physics object through ttt.js (`ttt:ptouch:<trigger>` → `<trigger>__touch` relay); ttt.js also polls the object against the trigger box every 8 ticks during the round and fires the relay itself, at most once a second. The carrier lets go when the relay fires, when the object is killed, or when it stops moving (DisableMotion). |
| 5 | Sandbox error texts | `ttt_convert.py` removes logic_auto Display outputs for texts the TTT prep relay kills; the prep relay fires 0.05 s after round start. |
| 6 | T2 crawl tunnel `+duck` | `point_clientcommand` `+duck` / `-duck` → `ttt:duck:on/off`: a "Crouch to crawl through" prompt while inside and not ducked. Crouch can't be forced from a map. |
| 7 | Carried props vs. io-script pushing | ttt.js sets the held prop's owner to the carrier (cleared on drop, 1.5 s after a throw); the io script's `physMass` skips props owned by a player (cs2mapping `tools/physpush.py`; minecraft's io script patched). |
| 8 | Skyscraper invisibility button (btn1/btn3) | Restored 29 Oct (cs2mapping `tools/restore_ents.py`: the importer had dropped both 1-unit npcclip buttons). `!activator Alpha <n>` → `ttt:alpha:<n>` (pawn and held weapon), `AddOutput rendermode` dropped, restored on respawn. As in the BSP, btn1 starts locked and nothing unlocks it (its unlock goes to a btn2 the map doesn't have), so it can't be used unless the map is changed. CS2 can't hide the target-ID name per player. |
| 9 | CGBrush first 30 s | Depends on 1. |
| 10 | 132 carryable props | Covered by `CARRY_CLASSES`; test. |
