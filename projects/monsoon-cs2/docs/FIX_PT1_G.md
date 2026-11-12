# Playtest 1, batch G (era weapons and the upgrade system): progress

Row 19 of [PLAYTEST_1.md](PLAYTEST_1.md): "there are no custom weapons or anything. is there a buy zone? If not - era appropriate
weapons would be good - with kills leading to optional upgrades such as sniper rifles etc." Design: [WEAPONS.md](WEAPONS.md).
Updated after every step. Levels in the words of `docs/reference/compatibility.md`: nothing here is in-game verified.

| # | Step | Status | Notes |
|---|---|---|---|
| G0 | Research: repo weapon builder, custom-weapons.md, mg_trenchwarfare's route, cs_script weapon calls, what sources are on disk | done | see WEAPONS.md "What the repo can make" |
| G1 | `docs/WEAPONS.md`: loadouts per class and side, route per weapon, buy zone answer, upgrade economy | done | buy zone: none (`mv_params buying 3` + money/buytime cvars); stock-skeleton exports on disk limit remodels to P2000 / SCAR-20 / G3SG1 / AWP / SSG 08 / Glock |
| G2 | `tools/mv_weapons.py`: `scripts/weapons.vdata` (era stats, world models of the remodels) from the stock decompile | done | 13 entries edited, every key checked to exist; the M14 / M1911 models named only once built into the addon |
| G3 | Script: `src/25_weapons.js` (requisition, armory, unlock kits, perks, ledger), hooks in players / main / conquest / heli / arty, CONFIG | done | mv-0.7; F (LOOK_AT_WEAPON) added to the key read; per-side launcher `AT_TEAM` (M79) |
| G4 | HUD: `mv_req` rows in the contract + `tools/mv_hud.py`; HUD gate | done | 110 panel ids, hud_check 8 states 0 problems (`out/hud/hud_infantry.png`, `hud_capture.png` show the row and the armory card) |
| G5 | Mock: weapons in the stand-in, new `scenario=weapons`; balance fight reads the held weapon | done | `node test/mock.mjs 14 300 scenario=weapons humans=6` (9 pieces); invariants: REQ in 0..CAP, no upgrade kit / weapon without its unlock |
| G6 | Gates: build, api --strict, tscheck, mock 32 300, every scenario, HUD gate, sim_balance with upgrades | done | final run 13 Nov ~01:45 on mv-0.7 (4112 lines): api 0 problems, tscheck OK, tsc OK; mock 32x300, 32x600, 4x600, 64x300 humans=32 (0.121 ms/tick avg), MOCK_NORESTART 32x600, edge, churn, restart, reload, review2, review3, pt1, weapons: all PASS; `tools/mv_hud.py` gate 0 problems (110 ids); sim_balance T 48 % / 50 % (below) |
| G7 | Weapon assets: M1911 (Colt rebuild at the monsoon path), M14 on the SCAR-20 skeleton (BC2 conversion), M21 (the M14 + a period scope) on the G3SG1 skeleton | built | `tools/weapons_mv/m1911.json`, `m14.json`, `m21.json` (the US sniper upgrade moved from the M40 on the AWP to the M21 on the G3SG1: a remodel now, semi-auto animations that fit); M14 GLB by `tools/mv_weapon_glb.py`; renders `out/weapons/m14_compare.png`, `m21_compare.png`, `m1911_compare.png`; staged in out/addon; not compiled yet |
| G8 | Deploy (backup, copy, sha256, `out/deploy/pt1_G_<stamp>.json`) and compile from `C:\source1\cs2port` | done (compiled) | 13 Nov 01:45: no cs2.exe, no other resourcecompiler. 86 files, all sha256 ok, record `out/deploy/pt1_G_20261113_014553.json`, backups `out/deploy/backups/pt1_G_20261113_014553/` (only the script, xml and css existed before). Compiled one file at a time (log `C:\source1\cs2port\logs\pt1_G_compile.log`): m1911, m14, m21 and their `_mag` vmdls, `scripts/weapons.vdata`, the HUD xml, the css (308 compiled, the two new PNGs with it: `pl_req_png.vtex_c`, `req_ready_png.vtex_c`), `mg_monsoon.js`: each OK, 0 failed. The two PNGs on their own: resourcecompiler takes no bare PNG ("0 compiled"), harmless. `materials/models/weapons/ww1/scope/brass.vmat` was deployed but nothing uses it (the axis-style scope has no brass faces) |
| G9 | Docs: SCRIPT.md, CONTRACT.md, ASSETS.md (append), PLAYTEST_1 row 19 note for the lead | done | WEAPONS.md, SCRIPT.md (structure, requisition, CONFIG guide, tests, not-yet-tested), CONTRACT.md (files, kit stations, chat), ASSETS.md "Weapons"; PLAYTEST_1.md row 19 and NOTES.md left to the lead |

## Notes while working

- 13 Nov 2026 01:15: no `cs2.exe`, no `resourcecompiler.exe` running. Batch P is rebuilding props (its files untouched here).

## Balance (`node test/sim_balance.mjs 40 32`, seeds 101 + 7 i, 13 Nov 2026)

| | bots (32 bots) | mixed (22 humans + 10 bots) |
|---|---|---|
| **batch G** (upgrades on, M79 for the US) T win rate | **48 %** | **50 %** |
| round length median | 12:46 | 17:21 |
| helicopter life median | 72 s | 137 s |
| helicopters lost T : CT | 184 : 222 | 242 : 171 |
| baseline (`cfg.REQ.ON=false cfg.AT_TEAM={}`: no upgrades, the US AT man with the RPG numbers) T win rate | 45 % | 48 % |
| baseline helicopters lost T : CT, to AT | 197 : 213, 108 | 311 : 195, 243 |

Both sets in the 45-55 % band. The MISS lines are the ones every earlier review had (the rate model's kill shares; flag D in bot
rounds). The M79 is lighter on the Mi-8s than the old US launcher (mixed: 243 -> 172 helicopters lost to AT), which is why T gains ~2-3
points. The infantry fight in the sim is the rate model with an ASSUMED factor per upgrade class (mock.mjs `FIGHTW`), so the upgrades'
real weight is for playtest 2 to tell.

## Economy (4 balance rounds per set, `req` in the mock's balance JSON)

- Earned per round, all 32 players: ~3,700 REQ (bots) / ~3,500 (mixed): about 115 per player, 80 % from kills, 10-15 % captures,
  the rest assists, helicopters, guns. Roughly 6-9 REQ per player-minute: the frag pouch after ~2 kills, the sniper rifle after ~5.
- Unlocks per round: 24 (bots: each of 24 bots buys once; 16 pouches, 6 carbines, 2 sniper rifles = the BOT_BUY.SNIPERS cap) / 31-34
  (mixed: 12-14 pouches, 6-9 carbines, 1-6 shotguns, 6-8 sniper rifles over the round, never more than the 1-in-8 limit at once).
- Points lost to the 100 cap: 400-650 a round (mostly bots that bought their one thing): the cap is doing its job against hoarding.

## Map entities

None added. The armory works at the existing kit stations (`mv_kit_<tg>`, `mv_kit_<a..e>`: E kits, F armory); no map regeneration needed.
Optional for the lead's next map pass: display props of the remodelled rifles on the base arms racks (needs the compiled weapon models
as `prop_dynamic` world models; not done, the racks already read as arms racks).

## What only CS2 can confirm

- The addon's `scripts/weapons.vdata` (from the 25 Oct 2026 decompile) taking over the stock entries on this map: era stats, and the
  M1911 / M14 / M21 models in first and third person with the stock P2000 / SCAR-20 / G3SG1 animations (hand fit, the op-rod handle on
  the SCAR's bolt bone, the M14 magazine on the reload). A newer CS2 than that decompile would have its other weapon stats pinned back.
- CS2's own HUD and kill feed still name the stock weapons (SCAR-20 for the M14, ...): only the script's HUD uses the era names.
- F (`LOOK_AT_WEAPON`) at a rack plays the inspect animation while it opens the armory; that the edge is read on a quick tap.
- The frag pouch (one HE + one smoke, CS2's default grenade limits); bots throwing them, and bots with the scoped rifles / shotgun.
- The M79's lob in a player's hands (the script's own projectile and the rocket prop as the 40 mm round); the Zeus as the trigger.
- A rejoining player keeping his name (the ledger key); anyone can take a departed player's name within 15 min.
- The REQ row and the armory card on screen (rendered offline by hud_check only).
