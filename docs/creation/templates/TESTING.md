# <Game> CS2 test: what to check

Each line says what to look for. **Only report what fails** (what you saw, where, the console lines if any): anything you don't mention counts as passed.
Version under test: **v<x.y.z>** (<date>). Rebuild fully after copying files (`disconnect`, then load the map again).

## Check these first (fixes in this version)

- [ ] <fix> — expect <exact result>.

## A. Hammer

- [ ] `maps/<map>.vmap` opens without errors. Expect: <what the layout looks like>.
- [ ] The `point_script` and `custom_hud_layout` file fields aren't red.
- [ ] The build has no missing materials (`materials/<prefix>/…`) or models (`models/<prefix>/…`). A pink checker = a material failed: send its name.

## B. First run (listen server, `bot_quota 0`)

- [ ] Console: `[<tag>] v<x.y.z> ready: <counts>, HUD on, prop template on`. Any `WARNING` or `MISSING` line matters.
- [ ] <first thing the player sees>
- [ ] HUD: <where each part sits>. CS2's chat (bottom-left) and kill feed (top-right) have nothing of ours under them.

## C. With bots (`bot_quota <n>`)

- [ ] Kill credit: <what the killfeed / scoreboard should show>; console `CS2 kill: a -> b`.
- [ ] Once a minute: `[<tag>] script time: avg X ms, max Y ms per server tick (N players …)`. Send the line.

## D. Engine questions only a real run can answer

Answered items stay here (the → lines), so a problem that comes back can be checked against them.

1. **<Question>** <what to look at>.
    → ANSWERED <date>: <answer>.

## Known unknowns (only CS2 can answer)

- <Things the mock, renders and type check can't settle: interpolation, translucency, sound position relative to the custom camera, Panorama features used for the first time…>
