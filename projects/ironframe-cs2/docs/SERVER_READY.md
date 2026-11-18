# IRONFRAME: server-ready tracker (started 18 Nov 2026)

skink52 (18 Nov): "What work is left to get ironframe maps working client & server side? Work on [it across usage resets] to get them
server ready and finalised." One row per item; update the status after each one (memory: fix batches with progress files).
Baseline 18 Nov 13:19: `sh build/run_tests.sh` 19 suites PASS; slime-mg-gm `tests/run.py --only ironframe` 3/3 PASS.

Status words: TODO, DOING, DONE (how far checked, in docs/reference/compatibility.md's words), NEEDS SKINK52 (a decision or a client).

## A. Release blockers (players cannot get the maps without these)
| # | Item | Status |
|---|---|---|
| A1 | Steam description for each map (`<addon> STEAM DESCRIPTION.txt`) | DONE 18 Nov: Sprawl's was missing; both now name their setting (tools/loading_art.py `PLACE`) |
| A2 | Workshop preview image | Exists: preview/workshop_icon.png (shared pixel icon, 1024). A per-map image is optional |
| A3 | Other maps' files in each game addon (Sprawl had Dunes' credits; both had all three radar overviews): they would ship in the upload | DONE 18 Nov: moved to backups/stray_maps_20261118; deploy.sh now copies out/game with `copy_changed.py --map $MAP` |
| A4 | Visibility: every frame / weapon port has `permission: none` (docs/CREDITS.md), so no public upload. Recommended: **Unlisted**, as Hellmatch (3821892329) is: the server mounts it, it is not in search | NEEDS SKINK52 |
| A5 | Workshop upload of both maps (skink52 uploads; the server can only mount Workshop items) | NEEDS SKINK52 (after A4) |
| A6 | slime-mg-gm: mode `mech` leaves `Pending`: map lines with the two Workshop ids, `DefaultMap`, a maps.md row, release (steps: slime-mg-gm docs/add-a-mode.md) | TODO once A5 gives ids |

## B. Verified only by tests: needs a client on the server (skink52, one session, ~20 min; TESTING.md)
| # | Item | Status |
|---|---|---|
| B1 | World sounds on the dedicated server (`!snd 1-4`). 18 Nov, skink52 on the test server: menu sounds and the pilot's own tones (ifr.ui.*, `use_world_position = false`) are heard; every positioned sound is silent, `!snd 1-4` too (2 and 4 go to one client). So the files reach the client and the send path is not it: positioned (3D) playback is. Next: the client console after `!snd 1` (the in-game console works while the server owns vconsole) | NEEDS SKINK52 |
| B2 | Pilot payload round trip: `ifr_pilot` multi-page mailboxes, loadout save / buy / upgrade reaching the DB | NEEDS SKINK52 |
| B3 | CS2 HUD hidden in a live mech and back when dead (`hud` op, bit 4), chat relay while hidden | DONE 18 Nov: in-game verified by skink52 (hides in the mech, garage HUD right) |
| B4 | Killfeed (humans only), kill credit for AI kills via bot stand-ins | NEEDS SKINK52 |
| B5 | Client frame cost: heavy overdrive, many HUDs | NEEDS SKINK52 |

## C. Server checks I can run unattended (dedicated test server, bots, no client)
| # | Item | Status |
|---|---|---|
| C1 | Sprawl on the dedicated server with CS2-bot fill: one full round, no crash, tick times | DONE 18 Nov 13:26-13:39 (simulated: bots only): 4 full Sortie rounds, no crash, script avg 2.8-3.5 ms a tick at 11-20 mechs, max 11-20 ms (87 ms once, the first minute) |
| C2 | Dunes the same, after the 14 Nov builds | DONE 18 Nov 13:40-13:53 (bots only, plugin with the F3 toggle): no crash, a full round, avg 2.8-3.5 ms at 10-18 mechs, max 13-21 ms |
| C3 | SlimeMG log: `ifr_srv hello`, `mgstat` lines at the round end, no DISALLOWED lines | DONE 18 Nov: hello on both maps, `mgstat_on`, rules / leaderboard / objective payloads each round, 0 DISALLOWED. No humans, so no stats written |

Server-test notes (18 Nov): the test server loads maps as loose files under game/csgo, and both addons share most paths
(script, materials): copy one map at a time (`server_copy.py remove` the other first) or the second map runs the first one's script.
Workshop mounting has no such clash. The console's "Long frame ... 30 ms elapsed" lines come from this PC (de_dust2 warmup has them too).

## E. Asked 18 Nov
| # | Item | Status |
|---|---|---|
| E2 | Bottom-left `F3  TOGGLE CHAT` tag (skink52 18 Nov), only in a live mech with the server present (`ifr_f3`, hud.py `f3tag`) | Built, 19 suites PASS (hud_ids walks it), Dunes deployed + compiled 14:40 and on the test server (needs a map reload). Not seen in game |
| E1 | In-game verified 18 Nov (skink52: "f3: works"). F3 toggles CS2's HUD + chat in the mech (CS2 binds F3 to `autobuy` by default; the plugin catches it, no bind needed); `!hud` the same; help card row `F3  !HUD` (`!VOTE` and `!MODE` share a row so the card stays clear of the chat box) | Plugin built, harness 3/3, on the test server. Map: Dunes script + HUD deployed and compiled 18 Nov 14:24 (in its next upload); Sprawl next (its own build, out/sprawl). Not seen in game |

## D. Polish still open (STATUS.md "To do"; not blockers)
IFF marker tint, vis near the Dunes train tunnels, hangar grime, post-processing, visible damage states and gibs, frame identities
(awaiting skink52's yes). The four Tripo frames are already in `ai_loadouts.normal / hard` (checked 18 Nov; STATUS's 10 Nov note is stale).
