# IRONFRAME: in-game test checklist

Everything here needs CS2 (the sims and the mock engine cover the rest). Report only what fails; anything not reported passed.
Load the map (`map mg_ironframe_dunes`, or on the test server `host_workshop_map <id>` in mode `mech`). The console must print
`[ironframe] v<x.y.z> ready: ...` with nothing `MISSING`.

## 1. Join and garage
- [ ] Intro slate shows (title, arena, the mode in big type over a bar in the mode's colour, the objective in two lines); after 6 s or any key the garage opens; the pawn is invisible and frozen (no body, no weapons, no CS2 HUD clutter).
- [ ] Garage keys: W/S move, A/D switch column, Space picks, Ctrl back, F upgrades. Rows show owned / buy / locked / equipped states; weight and EN bars update; an invalid loadout shows the reason on SORTIE.
- [ ] Stand-alone (no plugin): every part is owned; clicking an upgrade track (or Space / F on it) asks, CONFIRM upgrades it for free ("<part> MK I: next sortie"), and the next sortie carries it (the fight HUD's AP maximum rises after a frame upgrade). Upgrades last for the map, across rounds.
- [ ] The garage at 4:3 (or 16:10) and at 16:9: ARMORY and EQUIPPED WEAPONS on the left, frame statistics in the middle, UPGRADE TRACKS and ITEM INFORMATION on the right; nothing overlaps; EQUIPPED WEAPONS lists the four weapons (key, icon, name, DMG / rate / ammo). The first click on each button logs `HUD click <id>` in the console.
- [ ] `!garage` while piloting shows the whole reply ("In a mech: !spec first, or wait for your next death"); `!help` shows four pages one after another.
- [ ] Server: `!pilot` shows rank/XP/credits; buying a part deducts credits and the row turns owned; `!loadout 2` is used next life; a reconnect keeps everything.

## 2. Sortie and movement
- [ ] SORTIE drops the mech from the sky with thrusters and 3 s of shield glow; the camera is behind and above it, mouse aims, WASD moves relative to the camera.
- [ ] Shift boost: continuous glide with booster particles and the loop sound; EN drains and regenerates; an empty tank stalls (red EN bar) for 2.5 s.
- [ ] Ctrl quick-boost in the held direction (backwards with none); cooldown ~0.45 s; not in the air on a quad frame.
- [ ] Space jump/hover; heavy landing (fall > 1200 u/s) causes landing lag with the thud sound.
- [ ] No clipping through terrain, buildings or the arena wall; the ceiling pushes back softly; mechs don't shove each other hard.
- [ ] Clip brushes (Dunes: skink52's toolsclip fences and prop boxes) stop mechs, walking, boosting and quick-boosting; a mech slides along them and can stand on a clip box; the console `[ironframe] arena 1: sky ...` line shows ~6143. `!perf` lists the hull traces per tick.
- [ ] The pawn never shows (no floating weapon, no body in first person) and the view never snaps; `!perf` reports under ~3 ms at 64 players.

## 3. Weapons and lock
- [ ] Each hard-point fires on its key (Mouse1 RA, Mouse2 LA, R RS, E LS); ammo/heat/cooldown ladders in the HUD match.
- [ ] Rifle, gatling, shotgun, SMG, autocannon: tracers, muzzle flash, hit sparks, damage numbers consistent with the garage stats.
- [ ] Laser/rail: a beam line, charge sound, instant hit. Bazooka/grenade/grenade cannon: a visible shell, explosion, splash hurts near mechs (not the shooter beyond 50 %).
- [ ] Blade: lunge to a target under 900 u, big impact. Shield: raised with Mouse2, blocks frontal hits, drains EN.
- [ ] Soft lock: box + range on the nearest enemy in the cone; F cycles; gun assist bends rounds toward the target; losing LOS drops the lock after ~0.5 s.
- [ ] With no lock, rounds land on the reticle at 300 u, 1 500 u and 4 000 u, also with the camera pulled in against a wall; your own IFF diamond never sits on the reticle (offline: no diamond over your own mech). Rockets / missiles fired at the sky vanish, never burst on the sky.
- [ ] Hard lock: three beeps, then missiles track; the target hears the warning and sees the arrow; a decoy breaks every lock; a sideways quick-boost in the last half second dodges.
- [ ] Stagger: the meter fills, "STAGGERED" flashes, the mech slows and takes extra damage for 2 s.

## 4. Kills and rounds
- [ ] The mode is always visible: the mode tag top centre (TDM / CONQUEST / KOTH / CTF / FFA / SORTIE, its own colour) and the objective line under the scores. Conquest: chips A B C show the holder; standing in a point shows the capture strip ("CT CAPTURING B 64 %", red when contested). KOTH: the hill chip and "MOVES 1:12" in the objective line. CTF: T and CT flag chips (HOME / TAKEN 60 % / DROPPED 12); carrying shows "FLAG IN HAND 60 % HOME".
- [ ] After a round is won or lost, CS2's ROUND WON / ROUND LOST banner goes away when the next round starts (mp_maxrounds 999; with 0 and mp_timelimit 0 the match ended after round 1 and the banner stayed for good).
- [ ] A kill shows in CS2's killfeed with the right killer and victim; assists count; the scoreboard (Tab) has kills/deaths.
- [ ] Death: orbit camera 3 s, then the garage with the respawn countdown; SORTIE respawns at a safe drop.
- [ ] Team Battle ends at the kill target or time; Conquest points capture in ~8 s and bleed tickets; Sortie waves and boss appear at low population; the podium slate shows XP/credits.
- [ ] After the podium CS2 ends the round (winner's banner) and the next round starts with a mode vote; a second round works exactly like the first (props and effects reset).
- [ ] `mp_restartgame 1` and a script reload (`script_reload`) recover cleanly.

## 5. AI
- [ ] With 1-5 humans the mode is Sortie with AI allies and enemy waves; bots use boost, quick-boost, cover and lock-on; they don't get stuck on terrain or walls.
- [ ] As humans join, bots drop one by one; bot kills credit the human scoreboard correctly (bots' mgstat lines are ignored by the server).

## 6. Server (SlimeMG IronFrame)
- [ ] SlimeMG log: `ifr_srv -1 hello`, `ifr_server` sent, `ifr_pilot` payload per player; `map check` lists `map mgstat`.
- [ ] At round end: `mgstat <slot> mech_xp N`, `mech_credits`, `mech_wins` lines; `!rank`/`!top mech` on the server match.
- [ ] Mailbox rename works (the payload arrives); if not, set `IronFrame.MailboxMode "origin"` and retest.
- [ ] Teams are balanced by rating at round start; a rank < 5 player sees the rookie shield badge against high ranks.

## 7. Look and sound (AAA bar)
- [ ] Every frame model renders textured at the right scale (light 240, medium 288, heavy 336 u), faces its travel direction, weapons sit in the hands/shoulders; no pink checkerboards, no z-fighting, LODs don't pop.
- [ ] Weapons: each arm weapon's grip sits in the fist (standing / hovering), the barrel points where the crosshair does; shoulder units REST on the shoulders / back (seated slightly into them, never hovering over the mech, never deep in the body or head), in the garage preview and in the field (idle, walking, boosting, in the air, turning the torso, aiming up and down); the frames carry no weapons of their own any more (no rifles in the hands of the AC frames, no back units, no sabres on the Gundam backpacks, no gatling on the Mule). A mech holding a hand weapon keeps its arms still while it walks (the fists stay on the grips). The console must not say `weapon mount drift` (30_render.js rigMountCheck: a weapon the engine has off its mount is logged once and parented again). Offline first: `python -I tools/weapon_fit.py` (the seat / clearance / grip test against models.json#mounts, ~6 min, exit 1 on a failure; `--fit` recomputes the mounts, build_all.sh runs that), `node test/weapon_mounts.cjs` (parenting) and the sheets `preview/weapons/<frame>.png`, every shoulder unit `preview/weapons/shoulders_<frame>.png` (`python -I tools/review_mounts.py`); results in docs/WEAPON_FIT.md.
- [ ] Lighting: no black mechs, readable terrain, fog and sky look intentional at dusk/night; no flickering probes.
- [ ] Sounds are positional, not clipping, loops stop when they should (no stuck boosters after death).
- [ ] HUD at 16:9 and 21:9: nothing overlaps CS2's killfeed; text readable; radar dots match positions.
