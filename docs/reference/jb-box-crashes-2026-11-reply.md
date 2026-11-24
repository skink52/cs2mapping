# Reply to the box's crash review (24 Nov 2026)

Thanks, this is useful. All the box crashes ran the last Workshop uploads, from before any of the fixes in our spec
(`jb-box-crashes-2026-11.md`); none of those fixes are on the Workshop yet. The box doesn't run our server plugin (SlimeMG), and
doesn't need to: every fix is inside the maps' own scripts, so it reaches the box with the Workshop updates alone.

## The five-human Dunes crash changes the picture

IRONFRAME's HUD holds about 150-190 classes switched on per player, so five players is roughly 950 in all. That is nowhere near
the 3000 cap we built in, so **the cap as shipped would not have prevented that crash.** Our working hypothesis is now:

- the overflowing vector holds about **1024 entries, counting real clients only** (bots and the GOTV client may not count, which
  would explain why our local probes reached 20 480 entries on bot / GOTV slots without an overflow);
- five IRONFRAME players at ~190 each sits right at 1024; on the pre-fix maps the GOTV client also had a full HUD of its own.

We agree 4096 was only a guess, and this is a hypothesis too until a number confirms it.

## Since your review (24 Nov, not uploaded yet)

Per-player HUD state cut further in all seven maps: known lines drawn as one picture, animation classes dropped, IRONFRAME radar and
racer minimap down to the 12 nearest. Classes on at once at 12 humans now: racers 1 924 (busiest player 190), IRONFRAME 1 075 (126),
Hellmatch 971 (120), Hellmatch ZE ~1 300 (140). Under a ~1024 limit over real clients that is still only about 5-8 humans, so if the
hypothesis holds the next step is text labels instead of letter classes.

## What the entity's schema says (s2v.app, CCSCustomHudLayout)

- `m_vecPanelIds` and `m_vecClassNames` are **one string table each for the whole layout**: every panel id / class name used during the
  map is added once and never removed. These are the two fields that overflowed (20 Nov panel ids, 24 Nov class names).
- Each player's switched-on classes and dialog-variable texts live in `m_vecPlayerLayoutStates` (a `CCSCustomHudLayoutState` per player,
  sent to that player and whoever observes them); there is also a global state.
- In field order the two tables come right after the per-player states. So the overflow is either **a table's own size** or **the
  whole entity's packed size** (Source's classic per-entity limit is 16 KB) running out while writing the field after the per-player
  states. That distinction decides the fix: fewer and shorter names / ids, or less per-player state and dialog text.
- Our maps' tables over one map (mock): racers 268 class names (1.3 KB) + 477 panel ids (4.9 KB); IRONFRAME 686 names (4.8 KB, still
  growing) + 348 ids (3.1 KB); Hellmatch 241 + 224 (it never crashed). A third-party skins plugin (NyriumSkins 0.2.2) reports the same
  `m_vecClassNames` PackEntity crash and fixed it by bounding its per-player HUD data, without numbers.

**Please check against the error lines:** do they give a size in bits or bytes, an element count, or a buffer name? That tells us which
of the two it is.

## How we will confirm it

A probe build of Dunes switches classes on for the connected human player(s) 64 at a time and logs the total until the console
shows the overflow or the server dies. That needs one real client on our local server, so it runs as soon as one can join.

## What would settle it from your side

1. **The exact serializer error lines, verbatim**: the overflow and `PackEntity` lines from all three crashes with every number
   (element counts, bits, field names) and the 10 lines before each. You say the box summaries have them; they weren't in the
   review, and they may state the limit outright.
2. **Humans connected at both Space Racer crashes** (20 Nov 23:37 and 24 Nov 01:53 AEDT).
3. When you can: the full-run counts of `[custom_hud] The maximum number of ...` lines on each crashed map run.

## Agreed

- Validate the GOTV exclusion and the HUD reduction separately. The GOTV exclusion is now in **all seven** of our maps, not only
  Dunes (the racers, Hellmatch and Hellmatch ZE also drew a HUD for the GOTV client).
- Memory: compare the settled baseline after normal Dunes visits with GOTV on. Our latest local results (spec section 4): the
  retained memory comes with play itself (mechs and props drawn, moved, animated) while GOTV is on; the script loaded but idle,
  its game cvars and idle spawned entities add little. A restart between maps above a memory mark avoids the OOM meanwhile.
- HUD: check normal races, results screens and spectating with real clients on the Linux build once the limit is known; if it is
  ~1024 over real clients, we will move text to dialog variables and shared state to all-player classes rather than rely on a cap.
