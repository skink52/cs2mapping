# Second reply to the box's crash review (24 Nov 2026, afternoon)

Thanks for the exact lines and counts; they settled the mechanism.

## What the lines show

```
20 Nov  Space Racer  14 humans  overflowed m_vecPanelIds[480/489]
24 Nov  Space Racer  12 humans  overflowed m_vecClassNames[162/203]
24 Nov  Dunes         5 humans  overflowed m_vecClassNames[686/687]
```

The overflow lands at a different element each time, and earlier in the entity the more humans there are (14 humans: already in
the panel-id table, which is encoded before the class names). So it is not a count limit on a table: **the layout entity's whole
packed size runs out of room** (Source's per-entity buffer is 16 KB), and the field being written at that moment gets the blame. What
fills it: every player's switched-on classes and dialog-variable texts, plus the two string tables (every panel id and class name
used this map, never removed). We agree the 1,024-entry idea is out.

Our estimate of that size (strings + 2 bytes, 4 bytes per switched-on class) reproduces the Dunes crash: five IRONFRAME players
come to ~16 KB in our mock, with half of it garage label text that stayed set while the pilots fought.

## What the maps do now (deployed and compiled on our side; not on the Workshop yet)

- **A byte budget instead of the class cap.** Every map script (Space / Neon / Depth Racer, IRONFRAME Dunes / Sprawl, Hellmatch,
  Hellmatch ZE) keeps its own estimate of the entity's packed size and stays under **12,500 bytes** (a 24 % margin under 16 KB).
  Past it, the parts of the HUD that would grow it wait; screen states always go out. The console says once a map:
  `HUD byte budget reached: N players, ~B of 12500 bytes; parts of the HUD wait`. This replaces the 3,000-class cap (the 3,012 you
  noticed: screen-state classes were exempt from it; the byte budget counts them too).
- **Smaller tables:** IRONFRAME's radar now uses a column + row class (48 names instead of up to 576), its screen-marker grid is
  coarser, and its garage texts and classes are cleared when the garage closes. Class names over a 2-minute IRONFRAME round: 645
  (4.4 KB) -> 252 (1.8 KB).
- **GOTV:** "Slime Demo Recorder" is now on every script's GOTV name list (it also reads `tv_name`), so the demo client is never
  treated as a player.

## How many players get the full HUD (mock, under the budget)

| Map | Full HUD up to about | Past that |
|---|---|---|
| Hellmatch | 32 humans (~8 KB at 32) | |
| Hellmatch ZE | ~10-12 humans (~9.3 KB at 8) | parts of each HUD wait; no crash |
| Space / Neon / Depth Racer | ~10-11 humans | parts of each HUD wait; no crash |
| IRONFRAME Dunes / Sprawl | ~5 humans | parts of each HUD wait; no crash |

Reaching 32 humans with the full HUD in the racers and IRONFRAME needs a HUD redesign on our side (much less text per player),
which we are planning separately.

## Noted

- Workshop items: Space Racer `3821296722`, Dunes `3841773892`.
- Memory: agreed, we'll compare the settled baseline across more Linux map rotations once the updated maps are up.

## What would help after the updates are mounted

1. Any `HUD byte budget reached` lines and any `EncodeField overflowed` lines, with the human count at the time.
2. The mounted update times, so we know which version a log belongs to.
3. Memory samples around a Dunes visit, if the panel can export them.
