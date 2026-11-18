# Hellmatch ZE (zombie escape)

A standalone CS2 zombie-escape addon built on Hellmatch's Doom engine in cs_script, using Freedoom content. Two arenas run at
once, one for T and one for CT, on the same linear Freedoom single-player level. Humans fight through timed holds, doors, lifts
and a boss to an escape. A human killed by a zombie comes back as a zombie (a Freedoom creature with first-person abilities) in
the **other** side's arena. The last side with humans alive, or the first to escape, wins.

Status: design done, build in progress. Design and findings: [`../hellmatch-cs2/docs/ZE_DESIGN.md`](../hellmatch-cs2/docs/ZE_DESIGN.md).
Where it stands and what's next: [`docs/STATUS.md`](docs/STATUS.md).

> **About the code:** the code in this project was written by an AI coding agent (Claude, by Anthropic). skink52 directs the
> project, tests it in CS2, does the Hammer work and publishes the map, but is not the author of the code.

This is a separate addon from Hellmatch (`projects/hellmatch-cs2`), which it does not modify. It starts from a copy of Hellmatch's
`src/core` and `src/cs2`.

## Credits and licences

All game content (levels, textures, sprites, sounds, music) is from the **Freedoom project** and its contributors, under their
BSD licence (`FREEDOOM_LICENSE.txt`, contributors in `FREEDOOM_CREDITS.txt`). The project's own code, art and sound are free for
non-commercial use (PolyForm Noncommercial 1.0.0 / CC BY-NC 4.0), see `LICENSE`. An unofficial fan project, not affiliated with
or endorsed by the Freedoom project, id Software, Bethesda or Valve.
