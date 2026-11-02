# In-game test list (assume passed unless reported failed)

Setup: 3+ humans (or 2 + `MIN_PLAYERS 2` for a look), `bot_quota 0`, map with both entities.

1. Console shows `[ttt] loaded; HUD found`. HUD panel sits top right over the killfeed area, hidden while Tab is held.
   Key check: when someone dies, does the killfeed draw on top of the panel or underneath it? If on top, set `HUD_IN_KILLFEED: false` (left layout).
1b. `HIDE_NATIVE_HUD`: CS2's HUD (killfeed, health, ammo, radar) gone after spawn; TTT health/armor/ammo/crosshair shown; chat still visible? AWP scope overlay still drawn? Comes back after respawn?
2. Prep: players can't hurt each other, but trigger_hurts, falls and traps kill; dying respawns; random primary only on maps with few weapons.
3. Roles dealt after 25 s; traitors see each other on the HUD; detective tinted blue with a Zeus.
4. Killing a player in the round: killfeed shows only a world death; nobody's score changes until the round ends, then the ±1s and winner +1s land. Check the Assists column too.
5. E on a body: global message with name and role. Detective gets weapon/time and a DNA line that points at the killer.
6. Double-tap F as traitor: shop opens, W/S/E work, purchases apply (armor, assassin knife one-hit, M4A1-S, radar, nades, healthshots, AWP); F closes.
7. Last traitor dies → INNOCENTS WIN, round ends with CT win; all innocents die → TRAITORS WIN with T win.
8. Clock: 3:30 + 20 s per innocent death; time out → innocents win.
9. Karma drops after team damage; next round's damage scaled.
11. Hold E on a crate: it floats in front of you and follows; E drops, R throws; standing on it drops it.
12. With the body template: a death leaves one ragdoll (no second client ragdoll, no tiny one), it can be carried, and E on it still identifies it.
10. Late joiner during the round spectates; reconnect doesn't keep an old role.

Unverified mechanics to watch: velocity on `prop_ragdoll` (moves the whole body?), `SetModelScale(0.02)` hiding the client ragdoll, `PREVENT_DEATH` + world kill (does the victim ever stay on 1 hp?), `SetMoveType(NONE)` while shopping,
`FireWinCondition` reasons, voice cvars, `SHOP_CURSOR` clicks, custom HUD vs CS2's killfeed layer (`HUD_IN_KILLFEED`), whether an earlier hitter gets an assist on a world kill.

## Converted TTT maps (ttt_minecraft)

13. Traitor buttons: aiming at one as traitor shows `[E] traitor trap: ...`; E fires the trap; single-use ones go away.
14. Traitor tester / role doors (T1 room, traitor tester room): innocents fail, traitors pass, as the map intends.
15. Map texts: welcome text in prep, "traitor room available" at round start, cave hints to the activator only.
16. A trap kill: body info names the trap; detective DNA points at the traitor who pressed it.
17. ttt_cg_skyscraper_2017 / ttt_minecraft: map weapons on the floor, no free primary.
18. Gold block (minecraft): any role can carry it into the tester's crafting spot; the tester doors unlock, the block vanishes, the carrier lets go.
19. The io script doesn't shove a block or minecart while someone carries it; walking into one still pushes it.
20. T2 tunnel shows the crouch prompt; no sandbox-mode error texts at round start.
21. Both scripts: io script props don't hurt at low speed AND karma / hidden kills still work.

## Results 29 Oct 2026 (skink52)

- FAILED: shooting a player dead during the round crashed the server (prop_ragdoll SetModel + Teleport). Fixed: no model swap or Teleport on bodies, bodies not carryable.
- FAILED: with HIDE_NATIVE_HUD players couldn't switch away from the pistol. Fixed: HIDE_NATIVE_HUD off by default.
- 29 Oct (late): HIDE_NATIVE_HUD back on with script weapon switching: tap F = next weapon, hold F = shop. Test: switching works for every slot, grenades thrown normally, the shop opens on hold only, dropping (G) still works.
- 29 Oct (late): messagemode does nothing with CS2's HUD hidden (skink52). Now: CS2's HUD only hidden while alive in a live round; Ctrl+F = HUD back for 15 s to chat; chat mirrored on the TTT HUD. Test: Ctrl+F then Y types; mirrored lines appear; HUD comes back on death / round end.
- 30 Oct: HIDE_NATIVE_HUD off by default (skink52: world deaths are enough). CS2's HUD, weapon switching and chat stay normal; the TTT panel sits over the killfeed.
- 30 Oct: TTT scoreboard on Tab (covers CS2's; dead shown alive until the body is found), opaque killfeed cover (300 px tall), top-bar cover. Test: Tab board fully hides CS2's at your resolution; top-bar cover hides the alive avatars; killfeed fully covered with 6+ deaths; does chat from the dead show to the living ("*DEAD*" prefix would leak)?
- 30 Oct (later): Tab board works but looked plain: restyled (group bars, score + karma columns, one column up to 24 rows). Top cover didn't show: it only showed in a live round; now always. sv_alltalk 0 (was 1). Test: does a living player see a dead player's chat?
- 30 Oct (night): FAILED: bodies showed as orange boxes (template used the one-bone placeholder characters/models/ctm_sas); radar never updated for most slots; body-found chat cut at 40 chars; !ttt text out of date. Fixed: agents/models T/CT body templates (both vmaps re-converted), radar refresh per slot, chat up to 120 chars, help text. CARRY_BODIES back on. Test: bodies look like players and fall right; carry a body (watch for a crash); radar lines update; full body-found line in chat.
- 30 Oct (night): tap E = identify, hold E = carry (bodies too) without identifying, Shift+E = covert search. HUD restyled with backgrounds cut from the Slime Servers banner (tools/hud_theme.py). Test: hold E on a body never announces it; the images show (may need a second map load after the first compile).
- 30 Oct: VERIFIED: the opaque panel blocks the killfeed. Karma reworked: applied at round start (no mid-round leak), traitors no longer gain karma for killing innocents, +5 per round, kept over reconnects by name.
- 30 Oct (polish): !rules command; long HUD messages wrapped onto lines (MsgA 2 lines, MsgB 5); stale help/comment text fixed; README limits brought up to date. Test: !rules and !ttt fully readable.
- 30 Oct (ttt_minecraft port, cs2mapping `ports/ttt_minecraft`): lights rebuilt to their CS:GO strengths (were all equal), water see-through, clouds/portal/lava translucent, glowstone self-lit, main logic_auto fires now (was gated on `is_pc`): gold block placed at map start, clouds move, vclips off; door hinge cubes out of the doorways; Trap_water/Trap_lava output names fixed. Test: lighting close to CS:GO; water see-through from above and below; gold block in one of its random spots without a round; diamond ores appear when a round starts (not before: ttt_ms__start); lava trap kills water and enables lava; walking through hut doorways without snagging.
- 30 Oct (ttt_minecraft): End/win room + block holding box moved below the nether (were above the sky ceiling: visible from spawn, shadowed the island). Test: win teleport lands in the End; gold/diamond blocks still appear on the island; no stone box or shadow over spawn.
- 30 Oct (ttt_minecraft, later): nether moved to z -5408..-4864 and End/holding box to z -9248..-8192 (far below the island, no overlap); nether traitor button (ttt_auto_3) and Pigman_Furnace_Trigger data shifted with it. Test: nether portal in and out, nether traitor button prompt + trap, pigman furnace, win teleport, blocks still spawn on the island.
- 30 Oct: prop-touch triggers (lighthouse diamond block etc.) stay live-round only (skink52: no win effects outside rounds). A block placed during warmup/prep fires when the round goes live (poll state resets at round start). Test: diamond block on the lighthouse trigger in a live round -> win sequence.
