# IRONFRAME <-> SlimeMG: the map/server contract

The IRONFRAME maps (`mg_ironframe_*`, one shared script, point_script **`ifr_script`**) and the SlimeMG `IronFrame` module
(slime-mg-gm `plugins/SlimeMG/IronFrame/`) talk through the only two channels a Workshop map and a CounterStrikeSharp plugin
have on a dedicated server:

- **map -> server: console lines sent as `echo ...`.** A dedicated server without `-disable_workshop_command_filtering` drops every
  command a Workshop map runs that isn't on Valve's allow list; `echo` is on it. The plugin listens to `echo` (`AddCommandListener`,
  `HookMode.Pre`) and acts on lines whose first word is one of ours. Never anything else (no `say`, no custom commands).
- **server -> map: `RunScriptInput <name>` on `ifr_script`** (`AcceptInput("RunScriptInput", activator, caller, name)`), where
  `name` is one of a **fixed** set below (the script registers each with `Instance.OnScriptInput(name, cb)`), the **activator**
  is the player's pawn when the message is about a player, and any **payload** is carried by a per-slot mailbox entity's
  targetname (`AddOutput "targetname ..."`, read by the script with `GetEntityName()`; see §4). Payload strings never contain
  spaces, quotes or semicolons.

Both sides must keep these names and formats. The server team can't change the map side (a Workshop re-upload by skink52);
the map side can't change the plugin. Anything new is added, never renamed. Files marked `MAP CONTRACT` on the plugin side:
`IronFrame/Contract.cs`, `IronFrame/Payload.cs`, `IronFrame/Career.cs`, `IronFrame/Objectives.cs`; on the map side `src/cs2/70_server.js`, the
`IF_Career` block of `src/core/70_progress.js` and the objective section of `src/cs2/45_features.js` (§7). Shared data: `data/parts.json`,
`data/career.json` and the vectors `data/contract_vectors.json` (copies in the plugin's `configs/plugins/SlimeMG/ironframe/`).

Since 11 Nov 2026 (sections 8-10): customisation that follows the pilot (the **profile** payload and seven ops), the server's **leaderboard**
and the operator's **match rules**. An older plugin sends none of them and the map behaves as before; an older map ignores them.

## 1. Lifecycle

| When | Who | What |
|---|---|---|
| script loads (OnActivate) | map | `echo ifr_srv -1 hello <protocol> <version>` e.g. `echo ifr_srv -1 hello 1 0.1.0` |
| `ifr_script` spawns, every round start, and on `hello` | plugin | `RunScriptInput ifr_server` (no activator): the script enters **server mode** (progression on, stats on, garage against server data). Also `mgstat_on` via `MapScriptInputs` for the stat lines (§2). |
| each human connects / spawns / asks, and after `ifr_server` for everyone present | plugin | mailbox write (§4) then `RunScriptInput ifr_pilot` with the pawn as activator: "this player's pilot state is in their mailbox" |
| the script never heard `ifr_server` within 10 s of `hello` | map | **stand-alone mode**: every part unlocked, no saving, no stats |

In stand-alone mode no `echo` line other than `hello` is ever sent. In server mode the script keeps sending `hello` once a minute
until `ifr_server` arrives (a plugin hot-reload).

## 2. Stats: `echo mgstat <slot> <stat> [n]` (existing SlimeMG contract)

Sent only after `mgstat_on` and never for bots or during warmup, exactly as Hellmatch and the racers do. Stat keys (mode `mech`):

| Key | When |
|---|---|
| `mech_xp <n>` | at round end, the player's XP for the round (the plugin applies rank maths, daily bonus, catch-up) |
| `mech_credits <n>` | at round end |
| `mech_assists <n>` | at round end |
| `mech_captures <n>` | Conquest captures, at round end |
| `mech_damage <n>` | AP dealt this round (thousands, rounded) |
| `mech_pve_kills <n>`, `mech_boss_kills <n>` | Sortie, at round end |
| `mech_wins` | the player was on the winning team (ends in `_wins`: marks the stat_rounds row won) |
| `mech_rounds` | the player finished a round in a mech |
| `best_streak <n>` | best kill streak (keeps the max) |

PvP kills and deaths come from the game events (real `TakeDamage` kills) and are **not** sent.

## 2b. Extended round statistics (added 10 Nov 2026; map side only)

At each round end, after the lines of section 2, the script sends more `echo mgstat <slot> <stat> <n>` lines for every human (core
`pilotStats`, adapter `srvRoundStats`), paced at `SRV_STATS_PER_TICK` (24) lines a tick so a full server does not send ~2 000 commands in
one tick. The plugin needs no list of them: `mgstat` stores any `[a-z0-9_]{1,32}` name per pilot and mode (`mode_stats`), and `best_*`
keeps the maximum. Zero values are not sent. No name ends in `_wins` or starts with `wins_` (those also mark the round as won; `mech_wins`
of section 2 is the only one). `node test/server_stats.cjs` pins the name rules; the mock engine prints `mgstat stats sent (...)`.

| Stat | Meaning |
|---|---|
| `mech_shots`, `mech_hits` | trigger pulls (one per fire event) and damaging hits: accuracy = hits / shots only as a trend (a shotgun shot can hit 12 times) |
| `mech_qb`, `mech_msl_fired`, `mech_msl_dodged` | quick boosts, missiles launched, enemy missiles shaken by a quick boost |
| `mech_staggers`, `mech_overdrives`, `mech_crates`, `mech_flag_returns` | staggers dealt, overdrive blasts, supply crates taken, own flags returned |
| `mech_dmg_taken` | damage taken, in thousands |
| `best_round_damage`, `best_round_kills`, `best_life_s` | the best single round: damage dealt, kills, longest life in seconds |
| `mech_<mode>_rounds`, `mech_won_<mode>` | rounds played / won per mode (`tb`, `cq`, `kh`, `ctf`, `sk`, `so`) |
| `mech_f_<frame>_rounds`, `_kills`, `_won` | per frame flown at the round end (the frame's part key: `whiteglint`, `bastion`, ...) |
| `mech_w_<weapon>_kills`, `_dmg` | per weapon part key (`rifle`, `vm6`, ...): kills, and damage in thousands |

Not sent yet: seconds on an objective, per-weapon shots. Ideas for the server side (leaderboards, titles from these): STATUS.md S2-S4.

## 3. Garage and career: `echo ifr_srv <slot> <op> [args]`

`slot` = `GetPlayerSlot()` of the human (the plugin ignores bots and unauthenticated players, as `mgstat` does). The plugin
answers every op with a mailbox write + `RunScriptInput ifr_pilot` (full state) or `ifr_deny` (code in the mailbox).

| Op | Args | Plugin does |
|---|---|---|
| `hello` | `<protocol> <version>` (slot `-1`) | send `ifr_server`, then `ifr_pilot` for every human present |
| `want` | — | re-send this player's state (`ifr_pilot`) |
| `save` | `<k> <loadout>` | validate loadout `<loadout>` (§5) against owned parts and budgets, store it as loadout slot k (**1-6** since 11 Nov 2026), make it active; reply `ifr_pilot` or `ifr_deny` |
| `active` | `<k>` | make loadout k (1-6) active |
| `buy` | `<part>` | buy part id if rank and credits allow; reply |
| `upg` | `<part>` | raise the part's upgrade level by one if owned, below cap, credits allow; reply |
| `paint` | `<paint>` | set the paint id (free cosmetics are always owned) |
| `round` | `<mode> <team> <won> <kills> <deaths> <assists> <xp> <credits>` | the round summary (also mirrored in `mgstat`); the plugin logs it and may award the daily bonus |
| `name` | `<k> [text]` | name loadout k (§8; no text clears it); reply the profile |
| `accent` | `<k> <id>` | accent colour id (career.json `accents`, 0 none) of loadout k; reply the profile |
| `callsign` | `[text]` | the pilot's callsign (no text clears it); reply the profile |
| `title` / `badge` | `<id>` | wear an earned honour of that kind (0 takes it off); reply the profile |
| `pref` | `<bits>` | preferences: bits 0-2 the camera preset id, bit 3 (8) hints off; reply the profile |
| `fav` | `<part>` | the favourite frame (0 clears); reply the profile |
| `top` | — | reply the profile (the pilot's place) and send the leaderboard (§10) again |

Unknown ops are logged and ignored. Every op is rate-limited by the plugin (10 per player per 10 s) and never trusted for
money: the plugin recomputes costs from its own copy of `parts.json`. The map therefore sends `want` at most once every 2 s a pilot
(one round start fires `ifr_server` several times: the rules and each leaderboard page), and a customisation op only when its own
checks pass (the same rules as the plugin's, so a refusal rarely costs a round trip).

## 4. Mailboxes: server -> map payloads

The map has 64 `info_target` entities named `ifr_mail_00` .. `ifr_mail_63` (one per player slot) in the cache room. The script
caches their handles at load (and re-finds them after a round restart). To send a payload to slot N the plugin:

1. `ent.AcceptInput("AddOutput", null, null, "targetname ifr_mail_NN:<payload>")` on the slot's mailbox (the plugin finds the
   entities by the prefix once per round, keeping them by index), and
2. fires `RunScriptInput ifr_pilot` (or `ifr_deny`) on `ifr_script` with the player's pawn as the activator.

The script reads `GetEntityName()` on its cached handle, takes everything after the first `:`, and parses it. If the engine ever
refuses the rename (unverified until the first server test), the fallback is Dogfight's origin encoding: the plugin `Teleport`s
`ifr_mail_NN_k` (k = 0..3) to origins whose x/y/z carry integers 0..8191 and the script decodes them; the payload fields are
small integers so both encodings carry the same data (`Payload.cs` / `70_server.js` implement both behind one interface).

### Pilot payload (`ifr_pilot`)
```
p1.<rank>.<xp>.<credits>.<active>.<owned>.<upgrades>.<L1>.<L2>.<L3>.<flags>
```
- `rank` 1..50, `xp` total, `credits` integer, `active` 1..6 (4-6: that loadout is in the profile payload, §8).
- `owned`: hex bitset over part ids (bit i = part id i owned; ids < 1024), lowercase, no `0x`.
- `upgrades`: `id-lvl` pairs joined by `,` (e.g. `101-2,1-5`), or `0` for none.
- `L1..L3`: loadouts (§5), `0` for an empty slot.
- `flags`: decimal bitfield: 1 = daily bonus available, 2 = rookie shield, 4 = staff.

### Deny payload (`ifr_deny`)
```
d1.<code>.<part-or-slot>
```
Codes: 1 not owned, 2 rank too low, 3 not enough credits, 4 over weight, 5 over EN, 6 at cap, 7 bad loadout (or a bad slot / id of a
customisation op), 8 rate limit, 9 text not allowed (nothing drawable in it, or the operator's block list), 10 honour not earned.

### Payload kinds and what a pilot costs
| String prefix | Origin page kind | Input, activator | What | Origin pages (9 values each; 4 teleports + 1 input a page) |
|---|---|---|---|---|
| `p1` | 1 | `ifr_pilot`, the pawn | career (above) | 4, +1 per 4-5 upgraded parts |
| `d1` | 2 | `ifr_deny`, the pawn | a refusal | 1 |
| `q1` | 3 | `ifr_pilot`, the pawn | the profile (§8) | 3 with nothing set, 4 typical (three contracts, a name), 10 at the very most |
| `r1` | 4 | `ifr_server`, none (mailbox 00) | match rules (§9) | 1 |
| `t1` | 5 | `ifr_server`, none (mailbox 00) | leaderboard (§10) | 1 + one per row: 6 for five rows |
| `o1` | 6 | `ifr_pilot`, the pawn | owned parts (origin mode only) | 2 |

`ifr_pilot` tells the kinds apart by the page header / the string prefix. **Owned parts**: the origin form of `p1` has no room for the
owned bitset, so the plugin sends `o1` (`o1.<id,id,...>`; ints `[1, blocks = 7, (lo13, hi13) x blocks]`, block b = part ids 100 b + 0..25 as
bits) at a load, on `want` and after a purchase; until it arrives the map counts the starter kit and every part in a loadout as owned.
Part ids must keep `id % 100 < 26` and `id < 700` (the plugin warns at load otherwise).
**When each is sent**: a load / `want` / a fresh script (`hello`, script spawn): `o1`, `q1`, `p1` (about 10 pages a pilot). A round start
and every spawn: `p1` only (4 pages; the script keeps profiles across rounds). XP / credits: `p1`. A customisation op: `q1` only.
`save` / `active` / `paint`: `p1`, preceded by `q1` while any of loadouts 4-6 is in use. Contract progress, a new honour or a new
leaderboard place: `q1`, at most once per `ProfileSeconds` (5) a pilot. The career payload always goes last: the map acts on it.
The order relies on `RunScriptInput` being handled before the next page is written (as the multi-page `p1` always has): unverified on a
real server.

## 5. Loadout string

```
<frame>,<rarm>,<larm>,<rshoulder>,<lshoulder>,<generator>,<booster>,<fcs>,<paint>
```
Nine part ids from `data/parts.json`, `0` for an empty hard-point. Validity (both sides, same rules, `parts.json#caps`):
every id exists and is of the right slot kind; the arm `shield` only on the left arm; sum of weights ≤ frame load;
every id owned (server mode). The core's `Progress.validate(loadout, pilot)` and the plugin's `Loadout.Validate` return the same
deny code for the same input; `test/contract.cjs` and `tests/run.py --only ironframe` both run the shared vectors in
`data/contract_vectors.json`.

## 5b. Decided on the plugin side (9 Nov 2026, slime-mg-gm `IronFrame/`; the map must match)

- **Validation order and refs** (`Loadout.Validate`, pinned by `data/contract_vectors.json`, generated by `tools/contract_vectors.py`):
  7 ref 0 (not nine fields of 1-4 digits) -> 7 ref p (1-based position: a 0 outside slots 2-5, unknown id, wrong kind, the shield in
  position 2) -> 1 ref id (server mode: not owned, lowest position first) -> 4 ref 0 (weight > class load + booster `load_bonus`) ->
  5 ref 0 (EN > generator output x 1.5). **Rank is not checked at validation**: it gates `buy`/`upg` (deny 2) only, so a starter or
  gifted part above the pilot's rank sorties (`starter.owned` has the rank-2 decoy 209). Deny refs: the part id for 1/2/3/6, the
  position or k for 7, 0 otherwise. `buy` of an owned part is a no-op (`ifr_pilot`); unknown ids are 7; deny 3 also means "buying isn't
  open to this player's tier".
- **XP -> rank**: `step(n) = floor(rank_base + rank_mult * n^rank_pow)` is the XP from rank n to n+1; `xpFor(r) = sum(step(n), n = 1..r-1)`
  (`xpFor(1) = 0, xpFor(2) = 780, xpFor(3) = 1889, xpFor(4) = 3424, xpFor(10) = 25386, xpFor(50) = 1270507`); `rankFor(xp)` = the largest
  r <= 50 with `xpFor(r) <= xp`. The plugin owns rank; the map shows the payload's rank and may show "XP to next" from the formula.
- **Upgrade cost** `floor(cost x caps.upgrade_cost_pct / 100) x (level + 1)` (integer maths, pct 30 in parts.json; core `IF_upgradeCost`, plugin `Catalog.UpgradeCost`); since 11 Nov 2026 `cost` here is `max(cost, caps.upgrade_floor_cost)` (2000 in parts.json: a free starter part's steps are 600, 1200, 1800, 2400, 3000; they were free before, and levels a pilot already has stay). The server's `IronFrame.UpgradeFloorCost` is 0 = the catalogue's floor; any other value is charged by the server while the map's garage still shows the catalogue's price, so leave it 0.
- **Payload details**: `owned` = hex of `sum(2^id)` (lower case, no leading zeros, `0` for none; read with BigInt); `upgrades` ascending
  by id; `flags` 1 daily available, 2 rookie (rank < 10), 4 staff. Origin fallback: paged (entity 0 = page, pages, kind; three ints per
  entity, 0..8191; pilot ints `[rank, active, flags, xp lo13, xp hi13, credits lo13, credits hi13, n, (id, lvl) x n, L1[9], L2[9], L3[9]]`,
  deny `[code, ref]`), one `RunScriptInput` per page; worked pages in `contract_vectors.json` "origin".
- **Catalog note**: deny 5 is unreachable with the v1 numbers (the hungriest build is 1980 EN <= 2100). The plugin warns at load if a
  `starter.loadouts` entry isn't valid for a new pilot (none since the 9 Nov 10:48 fix of starter.loadouts).

## 6. Mode, cfg and map group (plugin repo)

- Mode key **`mech`**, map group `mg_slime_mech`, cfg `cfg/slime/mech.cfg` (custom game type 3 mode 0, `mp_roundtime 10`,
  `mp_timelimit 30`, `mp_maxrounds 0`, `mp_ignore_round_win_conditions 1` **owned by the map**, `sv_gravity 0` owned by the map,
  `mp_respawn_on_death_t/ct 1`, `mp_respawn_immunitytime 0`, `mp_teammates_are_enemies 0`, `sv_disable_radar 1`,
  `mp_free_armor 0`, `mp_buytime 0`, `mp_startmoney 0`, `bot_quota 0`); every cvar reset in `common.cfg`.
- `MapScriptInputs["ifr_script"] = ["mgstat_on"]`; `IronFrame.Enabled true`; PlayerModels/Hats rules `mode:mech` → `Allow false`
  (pawns are invisible mechs).
- `ForcedCvars` for `mode:mech`: none beyond air accelerate (the map owns its physics cvars; `MapOwnedCvars` lists `sv_gravity`,
  `sv_maxvelocity`, `sv_accelerate` for this mode).
- Tables (prefix `slime_mg_`): `ironframe_pilots` (steamid PK, name, xp, rank, credits, active, flags, daily DATE, updated),
  `ironframe_parts` (steamid, part, level, PK (steamid, part)), `ironframe_loadouts` (steamid, k, loadout VARCHAR(64), PK (steamid, k)),
  `ironframe_log` (id, created, steamid, op, args, result). Migrations are the module's own numbered steps (`Db.Migrate("ironframe", ...)`).
- Commands: `!garage` (chat menu mirror of the in-map garage: loadout slot, buy/upgrade lists), `!pilot` / `!rank` (rank, XP, credits),
  `!loadout <1-3>`; console `css_ironframe_give <target> <credits>` (Manager), `slime_ifr_test ...` test hooks behind the guard.
- The `Guard.MapCommands` list already lets `echo` through; `ifr_srv` is only ever read from `echo`.

## 7. Objective zones: live state for the plugin's beams (added 10 Nov 2026)

Positions come from the **map**, never from these lines (docs/ARENAS.md "Objective markers"): `info_target` `ifr_point_<ID>` (ID A..E, the
zone centre on the ground), optional `ifr_point_<ID>_edge` (radius = horizontal distance to it, else 700), `ifr_flag_t` / `ifr_flag_ct`
(flag stands), `ifr_arena_<k>` (stacked arena copies). Both the script (`src/cs2/15_arenas.js`) and the plugin (`IronFrame/ZoneDraw.cs`)
read the same entities. Only the live state travels:

| When | Who | What |
|---|---|---|
| a copy's round starts (or its mode changes) | map | `echo ifr_obj <copy> mode <mode>`; copy 1..4, mode `tb cq kh ctf sk so` (only `cq`, `kh`, `so`, `ctf` draw) |
| a zone changes (progress in 5 % steps), at most 4 per second per zone, and every 5 s | map | `echo ifr_obj <copy> pt <ID> <active 0/1> <owner 0/2/3> <capTeam 0/2/3> <progress 0..100> <contested 0/1> <nT> <nCT>` (KOTH sends every point, `active 1` on the hill) |
| a flag changes state or moves > 150 u, at most 4 per second, and every 5 s | map | `echo ifr_obj <copy> flag <t/ct> <home/carried/dropped> <x> <y> <z> <carrierSlot>` (the live position of a carried / dropped flag; -1 = no carrier; AI carriers have slots >= 64 and no pawn) |
| a copy's round ends (podium) | map | `echo ifr_obj <copy> end` |
| the plugin draws (it found markers): after `ifr_server`, after a new `mode` line | plugin | `RunScriptInput ifr_objdraw` (no activator): the script stops drawing its own rings, arcs and columns (keeps the letters and the flags) and resends the full state |

The script sends `ifr_obj` lines in server mode only (after `ifr_server`); a plugin without the renderer ignores them (unknown echo word).
Plugin side: `IronFrame.DrawZones` (default true) turns the beams and `ifr_objdraw` off; budget and colours in slime-mg-gm `docs/ironframe.md`
"Objective zones". Map side: `src/cs2/45_features.js` (objEcho, onObjDrawInput). Tests: `sh tools/mock_objectives.sh` (map),
slime-mg-gm `tests/run.py --static` (`--ifr-zones-selftest`) and `--only ironframe` (live, fake markers on de_dust2).

## 8. Customisation that follows the pilot: the profile (added 11 Nov 2026)

Tables: `data/career.json` (text alphabet, accent colours, camera presets, honours, contract stat labels, mode codes): **ids and codes are
the contract; add at the end, never renumber**. Rules stated once in `tools/contract_vectors.py`, pinned by `contract_vectors.json`
(`texts`, `profiles`, `honours`): `node test/career.cjs` (map) and `slime_ifr_test vectors` (plugin) run the same file.

```
q1.<callsign>.<title>.<badge>.<earned>.<prefs>.<fav>.<place>.<accents>.<L4>.<L5>.<L6>.<names>.<daily>
```
- `callsign`: up to 12 characters of the alphabet (`A-Z 0-9 space -`), spaces as `_`; empty = none (the map shows the player's name).
- `title`, `badge`: the worn honour ids (0 none). `earned`: hex of `sum(2^id)` over earned honours (ids 1..24).
- `prefs`: decimal; bits 0-2 the camera preset id (career.json `camera`: 0 Standard x1, 1 Close x0.8, 2 Tight x0.9, 3 Wide x1.15, 4 Far x1.3),
  bit 3 (8) hints off. `fav`: a frame's part id (0 none). `place`: the pilot's place among all pilots by XP (0 unknown).
- `accents`: six hex digits, the accent id of loadouts 1..6 (0 none). `L4..L6`: loadouts (§5), `0` empty. `names`: six names joined by
  `,` (up to 10 characters, spaces as `_`, may be empty).
- `daily`: today's contracts, `code-progress-goal-reward` joined by `,` (at most 3), or `0`; code = index + 1 in career.json
  `contract_stats` (0: a stat the map has no label for, shown as CONTRACT).
- Text: `clean(text, max)` = a-z to capitals (ASCII only), `_` to space, anything outside the alphabet dropped, runs of spaces to one,
  trimmed, cut to max, trimmed. Both sides clean; the plugin's result is what is stored.
- Origin ints (kind 3): `[2, title, badge, earned & 8191, earned >> 13, prefs, fav, place, acc1 | acc2 << 4 | acc3 << 8, acc4 | acc5 << 4 | acc6 << 8,
  callsign x 6, n daily, (code, progress, goal, reward) x n, mask of L4-L6 present, 9 ids each, mask of names present (6 bits), 5 ints each]`;
  a text is two characters an int: `code1 + 40 x code2`, code = alphabet index + 1, 0 past the end. Every int is clipped to 0..8191, so a
  place, a goal or a reward above 8191 reads as 8191 in origin mode.
- **Honours** (titles and badges, career.json `honours`: id, kind, name, a badge's `tag` of up to 4 letters, `stat`, `goal`): earned when
  the pilot's career counter of `stat` reaches `goal`. The counters are the plugin's (`ironframe_career`), fed by the `mgstat` lines of
  §2 / §2b (`best_*` keeps the best value) and by game-event kills (`kills`). The map never decides what is earned.
- **Where the map shows it**: the callsign replaces the player's name everywhere (kill line, podium, spectator bar, messages); the badge's
  tag leads the name on the kill line (`DESTROYED  [ACE] RAVEN 7`); the title stands beside the kills on the podium cards and beside the
  name on the pilot strip under the streak meter, which also shows the daily contract nearest to done; the accent colour tints the
  weapons of that loadout (the frame wears the paint); the camera preset scales the follow camera's distance; hints off silences the
  onboarding tips. The garage's SLOTS tab (six slots, accent, name) and PILOT tab (everything else, contracts, top pilots) edit them;
  chat: `!callsign <text>`, `!name <text>`, `!title [name|none]`, `!badge [name|none]`, `!cam [preset]`, `!hints [on|off]`, `!contracts`, `!top`.
- **Stand-alone** (no plugin): the same profile object lives for the session (`pe.localProfile`), every honour can be worn, six loadout
  slots are kept until the map ends, nothing is sent.

## 9. Match rules from the operator (added 11 Nov 2026)

With every `ifr_server` the plugin first writes the rules to **mailbox 00** (no activator); the script reads mailbox 00 when the input has
no activator and takes only kinds 4 and 5 from it (slot 0's own pilot pages are never mistaken for rules).
```
r1.<rotation>.<round seconds>.<ai min x 10>.<ai max x 10>.<xp percent>.<flags>
```
- `rotation`: mode keys joined by `,` (`tb cq kh ctf sk so`, up to 8 entries) or `0`. With a rotation the next mode is the entry after the
  last mode played (wrapping); a vote for a mode in the rotation wins; the map's own choice by head count is off.
- `round seconds`: 60..3600 for every mode, `0` = the map's own. `ai min` / `ai max`: bounds of the AI fill's skill (0 easy .. 2 hard) x 10.
- `xp percent`: round XP x this / 100 after the round cap; credits follow the XP. `flags`: 1 the plugin hides CS2's HUD on pawns, 2 a
  leaderboard follows (information only).
- Origin ints (kind 4, one page): `[1, rot lo, rot hi, round seconds, ai min x 10, ai max x 10, xp percent, flags]`; rot: 3 bits a mode
  code (index + 1 in career.json `modes`), four codes an int. `r1.0.0.0.20.100.<flags>` = no rules.
- A plugin that sends no rules (or a map without mailbox 00) leaves the map's own behaviour. Rules apply from the next round start.

## 10. Leaderboard (added 11 Nov 2026)

After the pilots' payloads at a round start (and on `top`), read from the DB at most every `LeaderboardSeconds` (30):
```
t1.<total pilots>.<NAME>,<rank>,<xp>.<NAME>,<rank>,<xp>...
```
up to five rows, best first; `NAME` is the callsign, else the player's name cleaned to the alphabet, else `PILOT`. Origin ints (kind 5):
`[1, rows, total, (name x 6, rank, xp & 8191, xp >> 13) per row]`, one page per row after the first. It goes to mailbox 00 with
`ifr_server` and no activator (one input a page). The pilot's own place is `place` of the profile (§8). The map shows the rows beside
the podium (with `YOU  # place`), in the garage's PILOT tab and on `!top`; stand-alone they are hidden.

## 11. Chat commands passed on by the plugin (added 11 Nov 2026)

CounterStrikeSharp takes every chat line that starts with `/` for itself and hides it: the map's own chat hook never sees `/help` or
`/garage`. The plugin passes these on: `RunScriptInput ifr_cmd_<name>` on `ifr_script`, **the player's pawn as the activator**, no payload.
Names: `help garage back od cam hints bots mode` (80_chat.js `CHAT_FROM_SERVER`); the map runs its own `!<name>` for that player, without
arguments. A `!` line reaches both sides, so the map drops the second of the same command from one player within 0.8 s.
Plugin side: `css_help` / `css_commands` also send `help`; `css_garage` sends `garage` instead of opening the plugin's chat garage while the
map's script is there; `css_back css_od css_cam css_hints css_bots css_controls css_keys css_ironframe css_mech` are forwarders. A map
without these inputs ignores them.

## 12. CS2's own HUD (added 12 Nov 2026)

`echo ifr_srv <slot> hud <1|0>`: 1 = this pilot is in a live mech, 0 = not (dead, garage, intro, watching). Sent on a change and again every
5 s. The plugin (`IronFrame.HideHudInMech`, default on) sets or clears bit 4 of the pawn's `m_iHideHUD`; no reply. CS2 honours that one bit
only (seen in game, every bit tried): it hides the score bar, the health number and the chat box together, so while it is set the map
shows plain chat lines on its own message line. Stand-alone (no plugin) nothing is hidden.
