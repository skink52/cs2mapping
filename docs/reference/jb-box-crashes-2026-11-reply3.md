# Third reply: GOTV test and the joint player test (24 Nov 2026)

Thanks, that's a useful split. We agree the Ironframe OOM and the HUD segfaults are separate issues. Your note that state could build
up within an Ironframe run fits our numbers. Ironframe's class-name table grows during a round as radar dots move through new grid
cells (686 names on 24 Nov). On the old build, five players' garage text also stayed set while they fought. Our estimate puts five
humans on the old Dunes HUD right at ~16 KB.

## Why the bot passes couldn't show either problem

- **HUD:** only human players get a HUD, so with zero humans the layout entity stays nearly empty. Your passes couldn't reach the
  overflow.
- **Memory:** our local step comes about 2:00-2:20 after the map loads, and only during active play. Your passes started near map
  load and ran in one process, so the second inherited the first's memory.

## For a memory comparison that separates GOTV

Our method was:

1. Restart the process before each condition (GOTV on, then GOTV off), so nothing carries over.
2. Alternate Dust II and Ironframe twice, at least 5 minutes per Ironframe visit, with bots playing.
3. Compare the settled Dust II memory before and after each Ironframe visit.

Locally, Ironframe visits kept a few hundred MiB per visit with GOTV on and about none with it off. Stock maps kept about none either
way.

## Coming in a few hours

New Workshop builds of Space, Neon and Depth Racer, Dunes, Sprawl, Hellmatch and Hellmatch ZE.

- **Byte budget in every script:** each keeps the HUD entity under ~12.5 KB, so the worst case is parts of the HUD waiting, not a
  crash.
- **Shown on every HUD screen:** hidden screens are cleared, IRONFRAME's radar uses far fewer class names, and the GOTV client
  (including "Slime Demo Recorder") is never treated as a player.
- **IRONFRAME:** Dunes and Sprawl carry 8 copies of the HUD layout entity, and the script spreads players across them, so each entity
  holds only a few players.

## Proposed joint test once the updates are mounted (on test; 1.42.0.1 is fine)

- **Players:** as many humans as we can get; even 4-6 exceeds what crashed Dunes on the old build. Bots fill the rest.
- **Rounds:** a full Space Racer race through the results screen, then two or more Ironframe rounds with the garage opened and closed,
  deaths and a podium.
- **Console:** please watch for `HUD byte budget reached` (fine: parts of the HUD wait) and any `EncodeField overflowed` (not fine).
  Note the human count when either appears.
- **Our side:** we'll check that the HUD looks complete, that nothing is doubled, and that frame rate holds with the extra layout
  copies.
- **Memory:** the restart-per-condition comparison above, if you have time.

## Before then

Could you send test's `tv_name` and `tv_maxclients`? And send the mounted update times once the new versions land, so logs can be
matched to builds.
