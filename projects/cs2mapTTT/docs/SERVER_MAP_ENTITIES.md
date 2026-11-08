# Server-side TTT: how the server handles map entities

Reference for the server-side TTT plugin (planned, not written yet). The target server runs **CounterStrikeSharp** on Metamod; section 6c maps each step to it. The plugin takes over everything `addon/maps/scripts/ttt.js` does
(cvars, roles, team allocation, HUD, karma, shop, bodies, round flow). The **map keeps its own IO**: traps, testers, texts and win
sequences stay as entities and outputs in the map. This file is the contract between those entities and the server, so a converted
map works the same under the plugin as it does under ttt.js today.

Written 4 Nov 2026 from `ttt.js`, `tools/ttt_convert.py` and `maps/*.json`. Nothing here is tested against a plugin yet.

## Handoff: what the plugin author gets

The plugin author gets two files: this one and `ttt.js`. Use the `ttt.js` version with the server off switch (4 Nov 2026 or later, with `SERVER_WAIT` in its
`CONFIG`); the same file ships in all four maps.
`ttt.js` is the working reference implementation: where this file and `ttt.js` differ, `ttt.js` is what was tested in game.
Repo paths named here, such as `tools/ttt_convert.py`, are background only; the plugin doesn't need them.

**The maps keep ttt.js, and the plugin switches it off.** There is one workshop upload per map, for every kind of server. Without the plugin,
ttt.js starts TTT `SERVER_WAIT` seconds (3) after the map loads. With the plugin, the plugin sends it one message first and it never starts (§0).

| Map | TTT messages it sends | Data in `MAP_DATA` | Own io script |
|---|---|---|---|
| ttt_minecraft | chk, role, txt, txtoff, own, unown, cred, btnoff, ptouch, duck, win; 5 traitor buttons | yes, full | `ttt_minecraft_io` (needs §6 carry owner) |
| ttt_skyscraper (port of ttt_cg_skyscraper_2017) | alpha only | yes, alphas only (key `ttt_skyscraper`, the name the Workshop build loads as) | `ttt_cg_skyscraper_2017_io` |
| ttt_island17_pezversion | none | none, a plain map | none |
| ttt_terrortrain | none | none, a plain map | `ttt_terrortrain_io` |

**Where the map data is:** in `ttt.js` between `// MAP_DATA_BEGIN` and `// MAP_DATA_END`. It is one JSON object keyed by map name,
and each value has the shape in §3. Copy it out as a JSON file per map, or as one file. A map with no key gets no map logic, only the normal TTT game.

## The contract in one paragraph

`tools/ttt_convert.py` already turns every GMod `ttt_*` entity into plain CS2 entities plus a string protocol.
**Map → server:** the map sends `ttt_script` the input `RunScriptInput` with a parameter `ttt:<op>:<id>`, and the activator is the player
(or prop) that caused it. **Server → map:** the server fires `Trigger` on a `logic_relay` named `<id>__<event>`, passing the activator
through, and the relay's outputs do the map's work. **Per-map data** (button spots, tester boxes, roles, texts, damage owners, credits)
is in the `MAP_DATA` block of `ttt.js`, keyed by map name. Besides switching ttt.js off (§0), the plugin needs exactly three things:
catch inputs to `ttt_script`, fire relays by name with an activator, and load the current map's data.

## 0. Switching ttt.js off (required)

Send the `ttt_script` entity the input `RunScriptInput` with the parameter **`ttt:server`**, no activator needed:

```
ttt_script  RunScriptInput  "ttt:server"
```

- **When:** as soon as the map's entities have spawned, and again at every round start. The repeat costs nothing and covers a late load.
  It must arrive within `SERVER_WAIT` seconds of the map loading. Players need longer than that to connect, so sending it at map spawn is plenty.
- **What ttt.js does:** before it has started, nothing at all. It sets no cvars, fires no relays, draws no HUD and changes no damage.
  If it had already started, it hands players back (drops carried props, closes the shop, restores the CS2 HUD, model scale, colour and alpha)
  and then stops. Either way it stays off until the next map load, and its log says
  `[ttt] a server TTT plugin runs this server; ttt.js is off until the map changes`.
- `ttt_server` (underscore) does the same. It is for testing at the console, where unquoted `ttt:server` is split at the colon:
  `ent_fire ttt_script RunScriptInput ttt_server` with `sv_cheats 1`. A plugin calling the input directly can use either.
- **Who can send it:** the map never does, and players can't: `ent_fire` needs `sv_cheats`. A server with cheats on can, which doesn't matter.
- **Why not a cvar:** map scripts can't read cvars, and the only console commands they can add need `sv_cheats`.
- The plugin's own input hook (§1) will see `ttt:server` go past. Ignore it there, and don't block it from reaching the script.

Check in game: the server console shows the line above on every map load, and never `[ttt] started`.

## 1. Catching map → server messages

**Use the forwarded commands (5 Nov 2026).** Once switched off (§0), ttt.js passes every map message it receives on to the server as a
server command, so the plugin needs no entity IO hook:

```
echo ttt_srv_msg <slot> <activator name> <op> <id>   slot: the activator's player slot, or -1 (a prop or none)
                                                     activator name: its targetname for a non-player, "-" for a player or none
echo ttt_srv_hello                                   sent once at script load: answer with ttt:server (§0) at once
```

They go through `echo` (8 Nov 2026) because a dedicated server drops any command a Workshop map sends that is not on Valve's allow list
(`DISALLOWED WORKSHOP COMMANDS` in the console), and `echo` is on it. Listen for the server-only `echo` command and act on lines whose
first word is `ttt_srv_msg` or `ttt_srv_hello`; keep the plain commands registered too, for older map builds. The console splits
arguments at `:`, so don't put colons in them; ids are joined back from the remaining arguments. A server without a plugin just prints
the echo lines in its console and nothing else changes.
Why: on CounterStrikeSharp 1.0.379, reading entity IO connections crashes the server (CSS issue #975; `HookEntityOutput("*","*")` crashed
a test server on round restarts), and the `CEntityInstance_AcceptInput` / `AddEntityIOEvent` hooks never see zero-delay map outputs.
Maps from before this change don't forward; they need the new ttt.js. The input-hook text below is kept for other plugin frameworks.

Hook entity input dispatch (the engine's `AcceptInput` path) and filter on **target name `ttt_script`, input `RunScriptInput`**.
Read the parameter string and the activator. Split the parameter on `:` into `ttt`, `<op>`, `<id>`.
Ids are map targetnames and never contain `:`; split on the first two colons only, to be safe.

Keep the entity name `ttt_script`. Every converted map already targets it, so maps need no re-conversion.

The entity exists in every map, because the maps keep ttt.js. An input hook only sees inputs whose target was found by name.
Hooking **output firing** instead (the engine's output fire path, as CounterStrikeSharp's entity output hooks do) also works: read each
connection's target name, input and parameter there. That doesn't depend on the target entity at all.

The script also receives every message after the plugin's hook, and ignores them once it is off. Don't block them.

The map messages it sends to itself also come back through here. Minecraft's tester `__found` relays send `ttt:role:<id>` straight back to
`ttt_script`, so handling must be re-entrant and keep the activator.

**ttt.js must not also run.** §0 handles it. A server with an old copy of a map from before the off switch would run both.  The server console shows it:
`[ttt] started` appears a few seconds after map load. Tell the server owner to update the map.

A map's own `<map>_io.js` point_scripts (pushable props and the like) are separate entities and keep running. The plugin leaves them alone.

## 2. Firing server → map relays

```
fire  <id>__<event>  Trigger  activator=<entity>  delay=0
```

Use the engine's own entity IO queue (the same path as `ent_fire`), so delays and `!activator` in the relay's outputs work.
**Always pass the activator.** Many map outputs target `!activator` (teleport the tester victim, give the trap-presser an item, set alpha).
A missing relay is normal: the converter only makes a relay for events the original map used. Firing a name with no entity is a no-op.

## 3. Per-map data

ttt.js gets it baked into its `MAP_DATA` block (see the handoff section). The plugin should load it from its own config folder at map
start, one JSON per map or one file keyed by map name, so new maps can be added without rebuilding the plugin. Match on the bare map name
(ttt.js also strips any folder prefix). A map with no data is a plain map with no TTT entities: everything below is skipped.

| Key | Type | Used by |
|---|---|---|
| `buttons` | list of `{id, pos[3], desc, once, wait, range, off}` | traitor buttons, §4.1 |
| `checks` | `{id: {mins[3], maxs[3], on}}` | testers, §4.2 |
| `roles` | `{id: "inn" \| "tra" \| "det" \| "any"}` | role tests, §4.3 |
| `texts` | `{id: {msg, rcv}}` | map texts, §4.4 |
| `owners` | `{id: {damager, name}}` | trap kill credit, §4.5 |
| `credits` | `{id: n}` | credit cost, §4.6 |
| `wins` | 0/1 | map-forced wins, §4.7 |
| `settings` | 0/1 | round-phase relays, §5 |
| `ptouch` | `{trigger: {ent, mins[3], maxs[3], half[3], off[3]}}` | physics-object triggers, §4.8 |
| `alphas` | list of ints | player alpha, §4.9 |
| `duck` | 0/1 | crawl prompt, §4.10 |
| `post_time` | seconds, optional, hand-set | round end delay, §5 |

Unknown keys must be ignored, so the converter can add more later.

**Later, to drop the sidecar file:** put the same data as keyvalues on the map's entities, so a workshop map needs nothing on the server.
Not done yet because it is untested whether CS2 keeps unknown keyvalues on a `logic_relay` through compile and whether a plugin can read them
at spawn. Test that before relying on it.

## 4. Each mechanic

All per-round state below resets at round start (§5).

### 4.1 Traitor buttons (`ttt_traitor_button`)

GMod buttons are pressed from a distance by looking at them; they have no physical entity in CS2. The server does the whole thing.

- **State per button:** `used`, `next` (cooldown end), `off` (starts as JSON `off`).
- **Aim test**, per traitor, per tick while they hold Use: from the eye position, the distance to `pos` must be under `range`, and the
  dot product of the view direction with the direction to `pos` must be over a cone (ttt.js: `BUTTON_CONE`, eased to 0.85 under
  `BUTTON_NEAR` units). Pick the best-aligned button. Skip buttons that are `off`, used when `once`, or still cooling down.
- **Press:** only alive traitors, only in the active phase. Set `used`, set `next = now + max(0.5, wait)`, fire `<id>__pressed` with the
  traitor's pawn as activator, show the traitor `Traitor trap: <desc>`.
- **Hint:** while a traitor's aim lands on a usable button, show `[E] Traitor trap: <desc>`.
- **Inputs:** `ttt:btnoff:<id>` sets off, `ttt:btnon:<id>` clears it, `ttt:btntog:<id>` flips it. Kill and Lock both map to `btnoff`.

In ttt.js, Use goes to body search first; a traitor only presses a button when not aiming at a body. Keep that order.

### 4.2 Testers (`ttt_traitor_check`)

- **State per tester:** enabled, starting as JSON `on`.
- `ttt:chkon:<id>` / `ttt:chkoff:<id>` enable or disable it.
- `ttt:chk:<id>`: if enabled, count **alive traitors** whose origin is inside the box (`mins`/`maxs`, widened by 16 units on x and y and
  36 on z around the body centre), then fire `<id>__found` with the original activator.

**Known gap, fix in the plugin:** GMod fires `TraitorsFound` with the count as the output value, and maps compare it
(`logic_compare`, `math_counter`). ttt.js fires `__found` always and the count is lost, because a relay's `Trigger` doesn't pass a value on.
The plugin should pass the count. Two ways, pick when writing it:

1. Fire `<id>__found` with the count as the input value, and the converter changes those relay outputs' empty parameters to keep it.
   Needs a check that CS2 relays forward the caller's value at all.
2. The converter splits the event, and the server fires `<id>__found` with count `n` plus `<id>__found0` or `<id>__found1` by result.
   No value passing needed. Preferred unless option 1 is confirmed in game.

**None of the current maps need the count.** All five of ttt_minecraft's `__found` relays either send `ttt:role:<id>` back with
the same activator (a role test decides) or trigger two relays unconditionally. Firing `__found` every time, as ttt.js does, is correct for them.
The count only matters for maps converted later.

### 4.3 Role tests (`ttt_logic_role`)

`ttt:role:<id>`: the activator's player passes if alive and their role matches the JSON value (`any` = any assigned role).
Fire `<id>__pass` or `<id>__fail`, activator passed through. A non-player activator fails.

### 4.4 Map texts (`ttt_game_text`)

`ttt:txt:<id>` shows `msg` for about 5 s, unless `ttt:txtoff:<id>` came earlier this round or `msg` is empty.
`rcv`: 0 the activator only, 1 everyone, 2 detectives, 3 traitors, 4 innocents and detectives.
Route it to the plugin's HUD message line; chat is the fallback.

### 4.5 Trap kill credit (`ttt_damageowner`)

- `ttt:own:<id>`: remember the activator's player as owner of trap `<id>`. `ttt:unown:<id>`: forget it.
- On player damage with **no player attacker**, read the inflictor's targetname. If it equals some trap's `damager` and that trap has an
  owner, the hit (and a kill from it) is credited to the owner, with weapon name `name` ("the lava pool").
  Karma, the kill feed, body search ("killed by the traitor tester") and the round report all use that.
- Several traps can share one `damager` (ttt_minecraft's two tester traps both hurt with `Ttest_Hurt`). The first owned one wins.

### 4.6 Credit cost (`ttt_credit_adjust`)

`ttt:cred:<id>`: if the activator's player has at least `n` credits, take them and fire `<id>__ok`; otherwise fire `<id>__fail`.

### 4.7 Map-forced wins (`ttt_win`)

`ttt:win:t`, `ttt:win:i`, `ttt:win:d` (no id). Only in the active phase: end the round as a traitor win, innocent win or draw.
The round must end through a real CS2 round end, because maps reset on it (§5).

### 4.8 Physics objects into triggers (the gold block into the tester)

CS2 triggers filtered to one named physics object are unreliable, so the converter moved those triggers' `OnStartTouch` outputs onto a
relay `<trigger>__touch` and made the trigger send `ttt:ptouch:<trigger>`.

- `ttt:ptouch:<trigger>`: fire `<trigger>__touch` (activator: the object, or the first entity named `ent` if none came).
- **Poll as well**, every 8 ticks or so: for each entry, test each entity named `ent` as a box (origin plus `off`, half-size `half`)
  against `mins`/`maxs`. Fire on the frame it goes from outside to inside.
- At most once a second per trigger, and only in the active phase (win sequences must not run in prep).
- If a player is carrying that object, make them drop it before firing.

### 4.9 Player alpha (`!activator Alpha`)

`ttt:alpha:<n>`: set the activator pawn's render alpha to `n`, and the weapon it holds. Keep the role tint (detectives) in the colour.
Reset to 255 on respawn and round start. CS2 still shows the target-ID name; that can't be hidden per player.

### 4.10 Crawl prompt (`+duck` client commands)

`ttt:duck:on`: show the activator `Crouch (hold Ctrl) to crawl through` for 30 s or until `ttt:duck:off`. CS2 servers can't force crouch.

## 5. Round flow the map depends on

- **Every TTT round must end in a real CS2 round end** (`FireWinCondition` on `info_map_parameters`, or the plugin's own equivalent).
  CS2 then restarts the round, respawns map entities and fires `OnMultiNewRound`. Ending a TTT round only inside the plugin leaves the map broken.
- At round start, reset all state in §4 (buttons, testers, texts off, trap owners, ptouch), then, if `settings` is 1, fire `ttt_ms__prep`
  0.05 s later. The converter put the **round reset** in `ttt_ms__prep`: it re-enables, recolours and re-spawns whatever the map's traps
  changed, because CS2 keeps some of that between rounds (ttt_minecraft's lava stayed lava). Skipping it breaks the second round.
- When roles are dealt, fire `ttt_ms__start`. When the round ends, fire `ttt_ms__end`. Both only if the relay exists.
- Round-end delay: JSON `post_time` overrides the plugin default. ttt_minecraft sets 20 s: its diamond win teleports everyone to the End
  7 s after the win, and the sequence needs the time to play out.
- ttt.js also sets server cvars (`applyCvars`), such as `mp_ignore_round_win_conditions 1`, so CS2 doesn't end rounds on its own team rules.
  The plugin must set the equivalent; roles are not teams, and players stay on T and CT.

## 6. Other entities the plugin meets

| Entity | What to do |
|---|---|
| `info_map_parameters` | Round end goes through it. The converter adds one (`ttt_params`, buying off) if the map had none. Work without it. |
| `custom_hud_layout` `ttt_hud` | ttt.js's HUD. The plugin brings its own HUD; it may reuse this layout or ignore it. |
| `point_template` `ttt_body_tpl` / `ttt_body_tpl_t`, ragdolls `ttt_body_src*` | Bodies for ttt.js. A plugin can create ragdolls itself; leave these unused. |
| Map `weapon_*` | GMod TTT weapons were renamed to CS2 ones. ttt.js counts unowned ones at round start to decide whether to hand out a primary. |
| Carryable props | ttt.js carries `CARRY_CLASSES` on held Use. While carried, the prop's owner is the carrier (cleared on drop, 1.5 s after a throw). Map io scripts skip props owned by a player, so the plugin must set the owner too. |
| `<map>_io.js` point_scripts | The map's own. They abort damage from slow pushable props; the plugin's damage handling must not undo that. |

## 6b. What a plugin can do better than ttt.js

ttt.js is a map script, so several of its features are workarounds for what map scripts can't do. A plugin has real server access.
Don't port these workarounds one to one: replace them with the proper version. Items marked *unverified* are expected to work but
weren't tested for this project.

| Feature | What ttt.js does (map-script limit) | What the plugin should do instead |
|---|---|---|
| **Hidden kills** | Every lethal player hit is turned into a world kill: damage gets `PREVENT_DEATH`, then the script kills the player itself with no attacker (`HIDE_KILLER`, `runKills`). Nobody is credited, so CS2's own kill data can't leak the killer. | Suppress the death event to clients instead (CounterStrikeSharp: `EventPlayerDeath` in `HookMode.Pre`, `info.DontBroadcast = true`). The killfeed never reaches anyone, while the server keeps the real attacker for karma, DNA, logs and admin tools. Drop the world-kill trick. |
| **Killfeed** | An opaque HUD panel is drawn over the killfeed area (`HUD_IN_KILLFEED`). It fails for players with `cl_draw_only_deathnotices 1`, who see victims' names. | Not needed once death events aren't broadcast. Check that no other message leaks deaths: CS2's damage report in the console on death, round-end summaries, and the alive count in the top bar (ttt.js covers it, `COVER_TOPBAR`). *Unverified.* |
| **Scores** | Kill score changes are saved up and only added at round end (`scoreDelta`), so the scoreboard doesn't show who killed whom. | Same idea, or control the scoreboard columns directly. |
| **Bodies** | The dying player is shrunk to 2% (`SetModelScale(0.02)`) to hide CS2's client ragdoll, and a server ragdoll is spawned from a template entity in the map (`ttt_body_tpl`). | Create the ragdoll from the plugin, with no template needed, and stop the client ragdoll if possible. Avoid `SetModel` then `Teleport` on a freshly spawned `prop_ragdoll`: that crashed the server (TESTING.md, 29 Oct). |
| **Private messages** | Scripts can't send private chat, so role info, shop and search results go on the HUD only. | Send private chat or centre text to one player. |
| **Dead chat and voice** | Relies on `sv_deadtalk 0` / `sv_alltalk 0`; dead chat still carries CS2's `*DEAD*` tag. | Filter chat and voice per player: the dead hear and read only the dead (CounterStrikeSharp `SetListenOverride` for voice). |
| **Karma** | Kept by player name for the current map only: scripts can't keep data across maps or read Steam IDs. | Keep it by Steam ID, across maps and restarts. |
| **Round end** | `FireWinCondition` on `info_map_parameters`, with a fallback that restarts the round if CS2 hasn't ended it within 3 s. | End the round directly (CounterStrikeSharp `TerminateRound`), still as a real CS2 round end (§5). |
| **Commands and admin** | Chat commands only (`!ttt`, `!rules`); the typed line can't be hidden; no permissions. | Real commands with admin permissions (slay, force roles, karma reset), with the command text hidden from chat. |
| **Esc scoreboard** | Can't be hidden: it shows who is dead. | Check whether the plugin can hide or fake the dead state on it. *Unverified.* |

## 6c. CounterStrikeSharp mapping

The target server runs CounterStrikeSharp (CSS). These are the CSS pieces for each step. Names are from the CSS API as known in
late 2026; check them against the CSS version on the server before relying on them. None was tested for this project.

| Step | CounterStrikeSharp |
|---|---|
| §0 switch ttt.js off | `RegisterListener<Listeners.OnEntitySpawned>`: when a `point_script` named `ttt_script` spawns, on the next frame (`Server.NextFrame`) call `ent.AcceptInput("RunScriptInput", null, null, "ttt:server")`. Send it again in `EventRoundStart`. `AcceptInput` goes straight to the entity, so the colon is safe here. |
| §1 catch map messages | Hook input dispatch: `VirtualFunctions.AcceptInputFunc.Hook(handler, HookMode.Pre)`. In the handler, keep calls whose entity name is `ttt_script` and input is `RunScriptInput`, read the value string and the activator, and return `HookResult.Continue` so ttt.js still gets them (it ignores them once off). `HookEntityOutput` only sees named outputs per class, so it is the weaker fallback. |
| §2 fire relays | Find the `logic_relay` by name (`Utilities.FindAllEntitiesByDesignerName<CLogicRelay>("logic_relay")`, match `Entity.Name`), then `relay.AcceptInput("Trigger", activatorPawn, null, "")`. |
| §4.1 traitor buttons | Read Use per tick from the pawn's button state (`player.Buttons` has `PlayerButtons.Use`); eye position from the pawn's origin plus view offset, angles from `EyeAngles`. Run the aim cone test in `Listeners.OnTick`. |
| §4.5 trap kill credit | Damage hook: `VirtualFunctions.CBaseEntity_TakeDamageOldFunc.Hook(..., HookMode.Pre)`; the `CTakeDamageInfo` gives the inflictor entity, whose name is matched against the trap's `damager`. |
| §5 round flow | `EventRoundStart` / `EventRoundEnd`; end rounds with the game rules' `TerminateRound(delay, RoundEndReason)` (game rules from the `cs_gamerules` proxy entity). |
| §6b hidden kills | `RegisterEventHandler<EventPlayerDeath>(handler, HookMode.Pre)` with `info.DontBroadcast = true`. |
| §6b dead voice | `player.SetListenOverride(other, ListenOverride.Mute)` per pair, or `player.VoiceFlags`. |
| §6b karma | Key it by `player.SteamID`; save it to a file or database. |

## 7. Checklist for the plugin

0. Send `ttt_script RunScriptInput ttt:server` at map spawn and every round start (§0).
1. Hook inputs to `ttt_script` (or hook output firing, §1); parse `ttt:<op>:<id>`; ignore `ttt:server`.
2. Fire `<id>__<event>` Trigger with an activator through the entity IO queue.
3. Load the map data (from `ttt.js`'s `MAP_DATA`); ignore unknown keys; no entry means no map TTT entities.
4. Reset per-round state, then fire `ttt_ms__prep` at each round start; `ttt_ms__start` and `ttt_ms__end` at their phases.
5. End rounds through a real CS2 round end.
6. Traitor buttons by aim cone; testers by box count; ptouch by poll plus input; trap owners in the damage hook.
7. Stop ttt.js from running alongside on maps that still ship it.
8. Set the owner of carried props to the carrier, or ttt_minecraft's io script will push props out of players' hands.
9. In-game test on ttt_minecraft: a traitor button, the tester with a traitor and an innocent, a trap kill credited to the presser,
   the gold block into the crafting trigger, the diamond win, and a second round to prove the reset. On skyscraper, test the invisibility button that works. The other one, btn1, starts locked in the original map and nothing unlocks it.

## Things in ttt.js to read alongside this

All are in `ttt.js`: `mapInput` and the block after it (every op), `aimButton` / `pressButton` / `buttonHint`, `ptouchFire` / `ptouchPoll`,
`trapOwner` and the two damage hooks, `mapRoundStart`, `endRound`, `applyCvars`, `setAlpha`, and `drop` / `releaseOwner` for carry ownership.

## Op table

| Op | Id | Server action | Relay fired |
|---|---|---|---|
| `btnoff` / `btnon` / `btntog` | button | set button off / on / flip | none |
| `chkon` / `chkoff` | tester | enable / disable | none |
| `chk` | tester | count traitors in box | `<id>__found` |
| `role` | role test | test activator's role | `<id>__pass` / `<id>__fail` |
| `txt` / `txtoff` | text | show / mute for the round | none |
| `own` / `unown` | trap | set / clear owner | none |
| `cred` | credit | take credits | `<id>__ok` / `<id>__fail` |
| `ptouch` | trigger | object reached trigger | `<id>__touch` |
| `alpha` | value | set activator alpha | none |
| `duck` | `on` / `off` | crawl prompt | none |
| `win` | `t` / `i` / `d` | end the round | none (`ttt_ms__end`) |
| (server) | button | traitor pressed it | `<id>__pressed` |
| (server) | none | round prep / start / end | `ttt_ms__prep` / `__start` / `__end` |
