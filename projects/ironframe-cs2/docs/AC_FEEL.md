# IRONFRAME: Armored Core feel targets

The numbers behind the "feels like Armored Core" pass (10 Nov 2026, approved by skink52). What AC4 / for Answer (2006-08), AC V /
Verdict Day (2012-13) and AC VI (2023) do, measured where a text source gives a number, against what IRONFRAME did and does now.
Text sources only (fan wikis, guides, forum measurements); no game files or videos were used.

**Reading the numbers.** AC VI shows speeds in km/h-like units and has the most published data, so most hard numbers are AC VI.
AC4/fA and AC V numbers are rarely published as text; where none was found the row says so and the target is a design call.
Scale: our medium mech is 288 u tall and an AC is about 10 m, so **1 m = 28.8 u** (not the real 39.37) and **1 km/h ≈ 8 u/s**.
Time is in seconds at the 64 Hz core tick. "Old" is the value before this pass, "new" is the current one.

## Sources

| # | Source | What it gave |
|---|---|---|
| S1 | [AC6 wiki: Booster](https://armoredcore6.wiki.fextralife.com/Booster) | thrust 5 417-6 801, upward EN 405-800, QB thrust 17 500-22 200, **QB jet 0.26-0.54 s**, **QB EN 480-740**, **QB reload 0.30-0.91 s**, QB reload ideal weight, AB thrust 7 584-10 085, **AB EN 320-558**. The table has no EN column for horizontal thrust. |
| S2 | [AC6 wiki: Builds](https://armoredcore6.wiki.fextralife.com/Builds) | four NPC builds: AP 8 480 / 10 460 / 11 880 / 15 270, **boost 341 / 310 / 268 / 205**, **QB speed 337 / 339 / 313 / 301**, QB EN 587-862, **QB reload 0.51-2.16 s**, EN capacity 2 460-3 690, EN supply 2 091-5 287, **EN recharge delay 1.08-1.76 s** |
| S3 | [AC6 wiki: Stats](https://armoredcore6.wiki.fextralife.com/Stats) | boost speed rises with thrust and falls with weight; attitude recovery rises as weight falls; QB reload "lower values allow consecutive use" |
| S4 | [AC6 wiki: Generator](https://armoredcore6.wiki.fextralife.com/Generator) | capacity 2 000-4 420, recharge 250-2 000, supply recovery 312-833, **post-recovery EN supply 280-3 300** |
| S5 | [AC6 wiki: FCS](https://armoredcore6.wiki.fextralife.com/FCS) | close / medium / long assist 10-90 / 12-80 / 3-92, missile lock correction 65-150, multi-lock 40-120 |
| S6 | AC6 wiki weapon pages: [TURNER](https://armoredcore6.wiki.fextralife.com/RF-024+TURNER), [LUDLOW](https://armoredcore6.wiki.fextralife.com/MG-014+LUDLOW), [ZIMMERMAN](https://armoredcore6.wiki.fextralife.com/SG-027+ZIMMERMAN), [XUAN-GE](https://armoredcore6.wiki.fextralife.com/DF-BA-06+XUAN-GE), [VE-66LRA](https://armoredcore6.wiki.fextralife.com/VE-66LRA), [ASHMEAD](https://armoredcore6.wiki.fextralife.com/PB-033M+ASHMEAD), [Arms Units](https://armoredcore6.wiki.fextralife.com/Arms_Units) | damage / impact / accumulated impact / **direct hit adjustment**: rifle 105 / 65 / 25 / 185 % at 3.4/s, 18-round mag, 2.2 s reload; MG 42 / 41 / 19 / 195 % at 10/s; shotgun 900 / 840 / 420 / 205 %; bazooka 895 / 980 / 765 / 185 %, 4.2 s reload; laser rifle 466 (charged 1 677, 2.8 s) / 194 / 81 / 140 %; pile bunker 1 688 (charged 4 630) / 1 150, 150 %; gatling 25 / 25; burst rifle 224 / 245; missiles 216 x 4 / 175 x 4 |
| S7 | [Steam forum: stagger measurements](https://steamcommunity.com/app/1888160/discussions/0/3827551893137303922) | player stopwatch tests: **stagger is a fixed 2 s**; the meter drops fast only after about 5 s without a hit; it hard-resets about 3.5 s after a stagger; attitude recovery barely matters; **mashing QB leaves a stagger at about 1.75 s** |
| S8 | [Bandai Namco: AC6 beginner's guide, combat theory](https://en.bandainamcoent.eu/armored-core/news/armored-core-6-fires-of-rubicon-beginners-guide-basic-strategy-and-combat-theory) | the impact gauge fills, then the staggered enemy "takes critical damage" while it lasts; your own AC can be staggered |
| S9 | [Gfinity: impact bar](https://www.gfinityesports.com/guides/armored-core-6-impact-bar-stagger) and [Prima: making the most of stagger](https://primagames.com/tips/armored-core-6-how-to-make-the-most-of-enemy-acs-stagger-in-ac6) | a staggered target takes "almost double" damage depending on the weapon; build stagger with high-impact weapons, punish with high direct-hit weapons |
| S10 | Armored Core fandom wiki, *Boost* / *Boosters* (search-result text; the pages refuse automated reads) | quick boost arrived in AC4; in AC4 boosting on the ground stopped consuming energy and only slows its regeneration |
| S11 | [GamesRadar: AC V beginner's guide](https://www.gamesradar.com/armored-core-v-beginners-guide) | AC V: glide boost and high boost drain the energy meter (glide faster); energy refills much faster in scan mode |

Not found as text: AC4/fA QB distances, overed-boost charge time and speeds, the AC V / VD numbers, camera distances, FOV
changes and hit-stop timings. Those rows below are marked *no source* and the target is a judgement call.

## 1. Ground and boost movement

| Item | AC value | Src | Old | New | Why |
|---|---|---|---|---|---|
| Boost speed (light / medium / heavy) | 341 / 310 / 205-268 km/h = 2 730 / 2 480 / 1 640-2 140 u/s | S2 | 1 500 / 1 300 / 1 100 | **1 720 / 1 500 / 1 260** (+15 %) | AC6 is about twice our pace relative to body size. We stay below it: 64 mechs, projectile speeds of 7 000-10 000 u/s, the CS2 pawn ride and readability. +15 % and a free ground boost close part of the gap without retuning every gun. |
| Crossing 10 000 u boosting from rest (light / medium / heavy) | about 4 / 4 / 5-6 s at AC6 speeds | S2 | 6.6 / 7.8 / 9.7 s, arriving with 1 430 / 1 050 / 490 EN of 3 400 | **5.8 / 6.8 / 8.5 s, arriving with a full tank** | free ground boost (below) |
| Boost EN on the ground | none: AC4 slows regen instead; the AC6 booster sheet has no EN cost for thrust, only for upward thrust, QB and AB | S10, S1 | 300 EN/s (x0.35 idling) | **0 EN/s; regen x0.5 while boosting** (`ground_boost_drain`, `boost_regen_mult`) | The single biggest AC4/AC6 feel: you skate all the time and EN is for dodges, climbs and energy guns. |
| Boost EN in the air | AC6: upward 405-800 EN/s; AC V: glide/high boost drain | S1, S11 | 300 EN/s | **180 EN/s** (`boost_drain`) | Air time still costs; hover (jump) stays at 500 EN/s. |
| Assault boost speed | AB thrust / boost thrust = 1.4-1.5 | S1 | x1.25 boost | x1.25 (BT-Lancer x1.4) | unchanged; already the AC4 OB-lite. |
| Assault boost EN | 320-558 EN/s on a 2 000-4 400 tank (about 5-10 s) | S1, S4 | 600 EN/s | **360 EN/s** (2 x 180) | about 9 s from a full tank, inside the AC6 band. |
| Assault boost altitude | AC6 AB flies level | *no source* (series behaviour) | full gravity | **gravity x0.2 while assaulting** (`assault_gravity`) | AB is a straight flight line, not a ballistic hop. |
| QB speed (light / medium / heavy) | 337 / 339 / 301-313 km/h = 2 700 / 2 710 / 2 400-2 500 u/s | S2 | 2 800 / 2 500 / 2 200 | unchanged | Already on the AC6 numbers. |
| QB jet (the speed is held, then bleeds) | 0.26-0.54 s | S1 | none: an instant impulse that friction ate at once | **0.18 s at QB speed, steering locked** (`qb_jet`); a wall ends it | Our QB was a twitch. |
| QB distance from rest (light / medium / heavy) | jet x QB speed = 0.26-0.54 s x 2 400-2 700 u/s = 620-1 460 u (22-51 m), about 2.2-5 body heights | S1 | 305 / 283 / 239 u (1 body height) | **831 / 772 / 653 u** (about 2.7 body heights) | At the short end of AC6 (64 players need dodges you can still track). |
| QB reload by weight class | 0.30-0.91 s at ideal weight, up to 2.16 s overweight | S1, S2 | 0.45 s for everyone | **light 0.38, medium 0.45, heavy 0.55 s** (`classes.*.qb_cd`), and x1.0-1.6 by loadout weight (below) | Lights dodge more often, heavies commit. |
| QB EN | 480-740 per QB = 17-30 % of a tank | S1, S2 | 450 of 3 400 (13 %); 8 QBs from full | **600 (18 %); 6 QBs from full** | With faster regen and free skating, the dodge is the thing EN buys. |
| QB chaining | AC4 / fA "two-step" QB chains | *no source for timings* | none | **one extra QB inside the reload**: at least 0.12 s after the first, at least 60 deg off its line, x1.25 EN; then the full reload (`qb_chain*`). Not on Ronin (its double tap is the phase dash). Humans only; bots never chain. | The fA L-shaped double dodge. |
| Weight vs mobility | boost speed falls with weight; QB reload grows past an "ideal weight" | S1, S3 | weight was only a cap | **above 70 % of the load limit: boost -0 to -10 %, QB reload x1 to x1.6** (`weight_ideal`, `weight_boost_loss`, `weight_qb_cd`) | Loadout weight is now felt, not just a garage limit. The starter kits sit below 70 % (no change for them). |
| Walk | AC6 walking is a fallback | *no number found* | 520 / 440 / 360 | unchanged | |
| Gravity, terminal fall | *no source* | 800 u/s2, 1 800 u/s | unchanged | 2.8 body heights/s2: already "heavy and fast". |
| Air QB | AC4-6 QB in the air keeps altitude | *series behaviour* | vel.z >= -200 at the press | plus gravity x0.3 during the jet | the air dodge reads as a dash, not a fall. |
| Landing recovery | *no number found* | 0.35-0.6 s at > 1 200 u/s fall | unchanged | |

## 2. Energy

| Item | AC value | Src | Old | New | Why |
|---|---|---|---|---|---|
| Capacity | 2 000-4 420 (builds 2 460-3 690) | S2, S4 | 2 800-4 400 | unchanged | already in band |
| Regen delay after a spend | 1.08-1.76 s ("EN recharge delay") | S2 | 0.6 s | **0.9 s** (`regen_pause`) | AC rhythm: burst, breathe, refill. Shorter than AC6 for a shooter pace. |
| Regen rate | supply 2 091-5 287 on a 2 460-3 690 tank: a full refill in about 0.5-1.5 s once it starts | S2, S4 | 440-740 EN/s (GN-Standard: empty to full 5.1 s) | **700-1 180 EN/s, x1.6** (GN-Standard 900: 3.4 s) | halfway to AC6; our EN also feeds lasers, plasma and shields, so a full AC6 refill would make energy guns free. |
| Redline (empty tank) | a longer "supply recovery" delay, then "post-recovery EN supply" 280-3 300 | S4 | 1.2-3.0 s stall, then regen from 0 | stall unchanged; **+20 % of the tank at once when it ends** (`stall_refill`) | the AC6 post-recovery kick: running dry hurts, but you are not helpless after. |
| Boosting and regen | AC4: regen slows while boosting | S10 | regen paused by every drain | regen x0.5 while skating | see section 1 |

## 3. Lock-on and FCS

| Item | AC value | Src | Old | New | Why |
|---|---|---|---|---|---|
| Gun lock | AC4-6: guns track as soon as the target is in the lock box; FCS assist by range band | S5 | soft lock 0.15-0.4 s | **0.1-0.3 s** (std 0.2, long 0.3, close 0.1, seeker 0.25) | guns should feel locked the moment you aim |
| Missile lock | per FCS "missile lock correction" 65-150 | S5 | soft + hard = 0.85-1.6 s | 0.75-1.5 s (hard part unchanged) | |
| Range bands | AC6 assists by close / mid / long; weapon ideal / effective range (rifle 160 / 296 m: ideal = 54 % of effective) | S5, S6 | full damage to max range | **ideal-range fall-off** (`falloff` in parts.json, second pass below) | |
| Lead | AC6 FCS predicts, more at long assist | S5 | gun assist steers by the FCS gimbal toward the lead point | unchanged | |

## 4. Weapons

| Item | AC value | Src | Old | New | Why |
|---|---|---|---|---|---|
| Medium AP | 10 460-11 880 (light 8 480, heavy 15 270) | S2 | class AP 7 800 / 9 000 / 11 000 | **9 500 / 10 800 / 12 900** | AC6 build AP, and a longer duel so stagger and the punish window matter |
| Rifle DPS / AP | 105 x 3.4 = 357 AP/s vs 10 000: 3.6 %/s per arm | S6 | 1 190 AP/s vs 9 000 (13 %/s) | unchanged guns, AP +20 % (11 %/s) | about 3x AC6 on purpose: 64-player rounds need kills. Twin-rifle 1v1 TTK: 7.6 -> about 11 s (BALANCE.md). |
| DPS ratios | MG / rifle 1.2, bazooka / rifle 0.6, laser / rifle 1.4 (uncharged) | S6 | gatling 1.4, SMG 1.2, bazooka 0.76, laser 0.47 | unchanged | close enough; heavy single shots carry impact instead |
| Impact / damage | rifle 0.62, MG 1.0, shotgun 0.93, bazooka 1.1, laser 0.42 | S6 | rifle 0.18, gatling 0.15, shotgun 0.58, bazooka 0.5 | shotgun 0.5 (impact 70 -> 60) | kept low on rifles: DESIGN.md "shotguns, bazookas and blades stagger, rifles finish" (stagger lock fix in BALANCE.md) |
| Stagger duration | fixed 2 s | S7 | 2.0 s | unchanged | |
| Stagger meter decay | held about 5 s, then drained in about 3-3.5 s | S7 | drained at 300/s after 1.2 s | **held 2.0 s, then 450/s** (`stagger_decay_delay`, `stagger_decay`) | pressure builds across exchanges, the AC6 way, shortened for a shooter |
| Stagger damage bonus | per weapon "direct hit adjustment" 140-205 % (kinetic high, energy low) | S6, S8, S9 | x1.5 for everything | **per weapon `dha`**: blades 2.0, sniper 1.8, rifle / burst / bazooka 1.7, SMG / grenade / rail / autocannon / pile / grenade cannon 1.6, gatling / shotgun / flak / mines 1.5, cluster / laser cannon / energy shotgun 1.4, laser rifle 1.35, plasma / missiles 1.3, flamer / drones 1.2 (default `stagger_dmg` 1.5) | punish with the right tool. The shotgun is 1.5, not the AC6 2.05: it staggers and punishes itself, and went to 89 % with 1.8. |
| Punish window | stagger 2 s; QB mashing ends it at about 1.75 s | S7 | 2 s, no way out | **QB in the last 0.25 s breaks the stagger** (`stagger_qb_out`); `damage` events carry `crit: true` during a stagger | |
| Magazines / reloads | rifle 18 rounds, 2.2 s; MG 30, 1.5-2.0 s; bazooka 4.2 s | S6 | rifle 30 / 2.0 s, SMG 60 / 1.8, bazooka 4 / 3.5 | unchanged | |
| Charge weapons | laser rifle charge 2.8 s for x3.6 | S6 | 1.2 s for x2.4 | unchanged; **laser EN per shot 180 -> 230** | the faster regen had the laser at 77 % |

## 5. Camera

| Item | AC value | Src | Old | New | Why |
|---|---|---|---|---|---|
| Distance | *no source* (AC6 is about 15-20 m behind by eye) | - | 460 / 520 / 600 u (16-21 m) | unchanged | |
| Boost FOV kick | AC4-6 widen the view at speed (*no number found*) | - | +90 u dolly while the boost key is held | **speed dolly**: back +120 u at boost speed, up to +192 u in a QB, +80 u in assault boost, eased over 0.25 s (`CAM_BOOST_BACK`, `CAM_ASSAULT_BACK`, `CAM_SPEED_LAG`, 90_main.js) | cs_script's custom camera has no FOV control; pulling back with speed gives the same "rush". |
| QB kick | *no source* | back 70 u + side 90 u | **back 40 + side 90** (chain QB 25 + 110) | the dolly now carries the push; the kick is the jolt |
| Hit shake | *no source* | heavy hits, stagger, landing kicks | unchanged | |

## 6. Feedback

| Item | AC value | Src | Old | New |
|---|---|---|---|---|
| Hit-stop | *no source*; AC6 has none on guns, a short freeze on melee | - | none | **gap** (a per-player time freeze is impossible in CS2; a melee camera punch is the stand-in) |
| Hit markers | AC6 marks hits and stagger | S8 | hit / heavy (impact >= 500 or the stagger tick) / kill | **heavy also on every direct hit** (`crit`) |
| Lock / missile warning / stagger sounds | AC4-6 lock tones and the missile alarm | - | `ui_lock1-3`, `ui_locked_warn`, `ui_stagger`, `ui_en_empty` exist | unchanged |

## The ten biggest feel gaps (ranked) and what this pass did

1. **Boosting cost EN all the time.** AC4 and AC6 skate for free; ours drained 300 EN/s, so pilots walked to save EN. *Done*: free ground boost, regen x0.5 meanwhile, 180 EN/s in the air.
2. **Quick boost was a twitch, not a dash.** One-tick impulse eaten by friction: about 1 body height. *Done*: 0.18 s jet, 2.7 body heights, steering locked during the jet.
3. **No stagger punish.** A flat x1.5 for every weapon, no reason to switch to a finisher. *Done*: per-weapon direct-hit multiplier, crit flag and heavy hit marker, QB break-out in the last 0.25 s.
4. **The stagger meter forgot too fast.** 1.2 s grace then a slow drain: pressure never built. *Done*: held 2 s, then a quick drain.
5. **EN rhythm.** 0.6 s pause then a 5 s trickle; AC is burst, breathe, fast refill. *Done*: 0.9 s pause, regen x1.6, +20 % of the tank after a redline, QB 600 EN (6 per tank).
6. **Weight did nothing but cap the garage.** *Done*: above 70 % of the load limit boost speed drops up to 10 % and the QB reload grows up to x1.6; QB reload per class.
7. **No QB chaining.** *Done*: the two-step (one extra QB inside the reload, 60 deg off line, x1.25 EN). Bots do not use it yet.
8. **Speed and duel length.** Half AC6 speed and about 3x AC6 kill speed. *Partly done*: boost +15 %, AP +20 % (AC6 build AP). The rest is held back on purpose (64 players, bullet speeds).
9. **No boost FOV kick.** *Done as a camera dolly with speed* (no FOV API); assault boost flies level.
10. **No range bands.** AC6 damage drops past each weapon's ideal range; ours was full damage to max range. *Done in the second pass* (below).

Also missing and lower ranked: hit-stop on melee, an assault-boost ignition (AC4 OB charge), accumulated impact
(AC6 keeps part of each hit's impact longer than the rest).


## Second pass (10 Nov 2026, coordinator follow-up)

**Anti-stomp.** With the longer AC duels a fully upgraded pilot won 84-89 % of mirror AI duels (sides swapped), against skink52's rule of
fair progression. Caps AP +15 -> **+5 %**, DPS +10 -> **+3 %**, mobility 8 -> **3 %**, and the ladders flattened so level 5 lands on the cap:
frame AP 3 -> 1 %/level, weapon damage 2 -> 0.6, generator capacity 4 -> 1, booster efficiency 3 -> 0.6, FCS lock time -3 -> -1, shield block 2 -> 1,
repair / bubble 3 -> 1. `balance.cjs` now alternates sides in that duel (48 fights): the test arena's sides are not equal, and the old
always-side-A duel over-read it. A "maxed" pilot with zero upgrades still reads 56-57 % (seed noise), so the result is a 10-point edge.
The garage rounds the fractional percentages (`60_garage.js`).

**Ideal-range fall-off** (AC6 ideal vs effective range, S6). Top-level `falloff` in parts.json, keyed by weapon key: full damage and
impact out to `ideal` x range, then linear down to `min` at the range. Rifle and burst rifle 0.5 / 0.55 (full to 2 250 u, AC6's rifle
ideal is 54 % of its effective range); SMG 0.45 / 0.55, gatling 0.5 / 0.55, shotgun 0.5 / 0.5, energy shotgun 0.6 / 0.6, laser rifle
0.6 / 0.7, autocannon 0.55 / 0.6. Explosives, missiles, lobs, melee, rail and sniper keep full damage (they are the long-range or
splash tools). The garage item info shows `Range: ideal / max` (e.g. `2250 / 4500`). Code: `IF_falloff` in `40_combat.js`.

**Melee lunge (AC feel).** With a lock the blade lunge reaches a target anywhere inside the 900 u melee lock range and homes on it
during the dash, slowing so it arrives instead of passing; default lunge time 0.25 -> 0.2 s. The AI holds a 720 u band with a blade
and swings from the lock range. A 1 200 u lock range was tried and made blades worse.

**Weapon outliers** (`balance.cjs` family round robin, hard AI): flamer range 1 000 -> 1 400, 115 -> 140, burn 320 -> 400 AP/s;
blade rate 0.67 -> 1.0, EN 300 -> 240, hit radius 180 -> 240; pile bunker rate 0.2 -> 0.33, 4 200 -> 5 200, EN 450 -> 350, hit radius
170 -> 220; laser rifle 700 -> 650, EN/shot 230 -> 270; shotgun 120 -> 112 per pellet; rifle 170 -> 155; rail 1 200 -> 950; plasma
700 -> 780; bazooka 1 800 -> 2 000; VM-6 420 -> 470 per missile, turn 90 -> 120 deg/s.

**Hard AI two-step.** AI tiers have `chain` odds (easy 0, normal 0.3, hard 0.85): after a QB, with a missile still closing in (time
to impact < 1.5 s), the bot chains a second QB across the first. Chaining against every hard lock was tried first: it burned the
bots' EN and lost them rifle duels (Ronin, which cannot chain, went to 69 % in the hard round robin), so it is missiles only.

New `test/mechanics.cjs` checks: rifle full damage inside its ideal range and about 55 % near max range; the blade lunge reaches and
tracks a side-stepping target at 850 u; the hard AI chains against a dual-missile salvo. The laser full-charge and flamer-range checks
now read the part data instead of fixed numbers.

## Third pass: upgrade value, shoulder cannons (10 Nov 2026)

- **Upgrade cost** follows the flatter ladder: a step costs `floor(price x caps.upgrade_cost_pct / 100) x (level + 1)` with pct **30**
  (was 100; the power per level fell to about a third). Core `IF_upgradeCost` (70_progress.js, used by the garage and canUpgrade) and the plugin's
  `Catalog.UpgradeCost` (slime-mg-gm `IronFrame/Loadout.cs`, reads `caps.upgrade_cost_pct`) do the same integer maths; nothing else in C# hardcodes
  costs. A full MK V track is 4.5 x the part's price: a 3 000 cr weapon is 13 500 cr, about 34 TDM rounds or 3.3 days for a regular player
  (5 rounds plus 3 contracts a day); table in BALANCE.md "Progression".
- **Presentation**: track rows show the tier (`-`, `I` .. `V`; the slot fits 3 characters), the confirm reads "Upgrade X to MK III for N CR?",
  a maxed track reads `MK V`, a maxed frame `AURA MK V`: a frame at MK V wears its aura in the aura's accent colour (`auraMk5Tint`, 47_auras.js,
  no stats).
- **AC-Drum** (92 %) is an AC-style shoulder cannon: 400 -> 300 per shot, impact 160 -> 100, bipeds and reverse joints brace 0.2 s per shot
  (quads fire on the move). Flak went to 81 % after it and is braced 0.3 s too. Damage alone barely moved AC-Drum (it was the only always-on gun
  shoulder in a table of dodgeable missiles: 80 damage still read 63 %); the brace is the real cost.
- **Anti-stomp measure**: the duel is paired (each seed in both orientations); the 56 % "zero-upgrade" reading was seed and side noise, the
  paired control reads 50 %.

## Fourth pass: third playtest, Sprawl (10 Nov 2026 evening)

skink52: "the jets are too powerful - flying lasts way too long / recharge is too quick", "hitting a tiny bump in the map just stops you
in your tracks", "rockets still sometimes hit the roof ... i don't know how to target them", "if i hold mouse1+2 and look straight at an
enemy, they always win", "camera angle also makes it hard to shoot up / down". Tests: `node test/playtest3.cjs` (39).

- **Jets.** A held jump accelerated at +500 u/s2 without limit (the arena ceiling in ~4 s) for 6.8 s of a standard tank, and the tank
  refilled in 2.9 s. Now: `hover_climb` 650 u/s climb cap, `hover_drain` 500 -> 900 EN/s (3.8 s, ~2 300 u of height), air `boost_drain`
  180 -> 300 (assault 360 -> 600), `ground_regen_mult` 1.3 -> 1.0, new `air_regen_mult` 0.35, `regen_pause` 0.9 -> 1.1 s. Empty to full on
  the ground: 4.9 s (5.6 s after a redline stall).
- **Steps.** The body sphere swept 4 u over the feet, so near structures (all of Sprawl's streets) any kerb over 4 u stopped the mech.
  It now rides above the step height (`step_min` 80 u, `step_frac` 0.3 of the body: 80 / 86 / 101 u light / medium / heavy); lower things
  are walked over, the step is eased for the eye (`m.stepOff`, `step_smooth` 0.09 s, added by 30_render.js to both props, so the camera
  follows). After a wall contact the sweep runs every tick for 0.5 s (a slow mover crept into walls on the skipped ticks) and a sweep that
  starts inside something no longer pins the mech.
- **Rockets.** (1) Every lofted pack (VM-6, the starter shoulder; VM-12; Swarm) ended its loft AT the apex height at full turn radius
  (~2 000 u) and then only nulled the sight-line rate: apex ~4 400 u (the ceiling) and 0 hits of 12 on anything nearer than ~5 000 u. Now a
  lofted missile is `agile` until it first points within 12 deg of its target (launch speed held, turn x3), the loft ends a turn-radius
  under the apex, and pursuit runs past 25 deg off (was 60): apex 1 400-1 900 u, 12 of 12 at 1 200-5 500 u; a timed quick boost still
  shakes about 60 %. (2) A roof over the launcher (deck, tunnel, hangar): one trace up per salvo, the apex goes under it or the pack
  leaves straight. (3) The heightfield is each cell's TOP surface: its bilinear blend made a phantom ramp from every roof to the street
  and a solid block under every deck, which rounds, missiles, the reticle and the lock's sight line all hit. With a world to trace, the
  heightfield only counts away from structures (`nav.heightOpen`, `rayFrac(..., open)`). (4) A launcher always fires: press with nothing
  in the FCS cone = unguided at the reticle; hold on a target = guided the moment the lock completes; release early = unguided.
- **Showdowns.** The fill was `normal` for every stand-alone lobby (rank 4-17 weapons, 73 % standing accuracy) against a starter kit whose
  M2 was a 1 500 u shotgun. Fill skill 0-2 (`IF_Ai.fillSkill`): lobby rank base (stand-alone: easy) + `game.fillAdj` (+0.06 per human
  kill of a fill bot, -0.18 per human killed by one, per human; bots re-tier at respawn). Starter loadout 1 = two rifles. A pilot
  tracking perfectly with M1 + M2 at 1 500 u: 18-18 against normal before, 30-6 now, 18-0 against easy.
- **Camera.** `up` 160 / 180 / 210 -> 215 / 250 / 290 (the mech's head ~10 deg under the reticle, was 2 deg: targets just below the
  horizon sat behind the pilot's own mech). Looking up past `CAM_UP_ORBIT` 10 deg the camera no longer orbits down into the ground (where
  CS2's clip pull-in parked it inside the mech): the offset is counter-rotated so only the view turns. Unverified in CS2.

## Every changed number (old -> new)

- `classes`: ap light 7 800 -> 9 500, medium 9 000 -> 10 800, heavy 11 000 -> 12 900; boost 1 500 -> 1 720, 1 300 -> 1 500, 1 100 -> 1 260; new `qb_cd` 0.38 / 0.45 / 0.55 (boss 0.8).
- `move`: boost_drain 300 -> 180 (air); new ground_boost_drain 0, boost_regen_mult 0.5, assault_gravity 0.2, qb_jet 0.18, qb_chain 0.12, qb_chain_cost 1.25,
  qb_chain_angle 60, stall_refill 0.2, stagger_qb_out 0.25, weight_ideal 0.7, weight_boost_loss 0.1, weight_qb_cd 0.6; qb_cost 450 -> 600; regen_pause 0.6 -> 0.9;
  stagger_decay 300 -> 450; stagger_decay_delay 1.2 -> 2.0. `qb_cd` 0.45 stays as the fallback.
- Generators regen: GN-Standard 560 -> 900, GN-Surge 740 -> 1 180, GN-Reservoir 440 -> 700, GN-Ignition 600 -> 960.
- FCS soft lock: Standard 0.3 -> 0.2, Horizon 0.4 -> 0.3, Brawler 0.15 -> 0.1, Seeker 0.35 -> 0.25.
- Weapons: new `dha` on all 28 damage weapons (values in section 4); shotgun impact 70 -> 60; laser rifle en_shot 180 -> 230.
- Frames (ap mods, to keep the round robin in 40-60 %): Stryder 1.13 -> 1.19, Lisa 1.2 -> 1.26, Atlas 0.924 -> 0.89, Cerberus Atlas 0.935 -> 0.89 (descriptions updated).
- Adapter: `CAM_BOOST_BACK` 90 -> 120, new `CAM_ASSAULT_BACK` 80 and `CAM_SPEED_LAG` 0.25; QB camera kick back 70 -> 40 (chain 25, side 110).

## Results

**After the second pass (current):** frames normal 40-59 % (no flags), hard 40-61 % (Ogre 61 HIGH, Unicorn 40 LOW: on the edge);
weapon families 34-70 %, no flags (flamer 47 %, blade 42 %, laser 52 %, shotgun 52 %, pile bunker 51 %, sniper 70 %); shoulders: VM-6 38 %,
AC-Drum 92 % (the old always-on-gun finding); maxed vs stock 67 % (48 fights, sides alternating; 56-57 % with zero upgrades);
mechanics 163/163; sim 64 x 120 s all modes ok; mock 32 players / 60 s `OK: no errors`, 0.83 ms/tick avg.

**After the first pass:**

- Frame round robin `node test/frames.cjs 8 normal`: 44-58 % (was 37-59 %, Stryder LOW); hard tier 39-59 %, Unicorn 39 % LOW (was 39-62 %: Stryder HIGH, Noblesse and Cerberus Atlas LOW).
- Weapon families (`test/balance.cjs 2 2`, BALANCE.md): rifle 72 -> 58 %, shotgun 68 -> 67 %, blade 11 -> 20 %, laser 61 -> 73 %, flamer 11 -> 8 %; flamer and blade stay flagged low (AI kiting, as before). Twin-rifle TTK 7.6 -> 11.5 s.
- Maxed vs stock duels 72 -> 84 %: the caps hold (+15.0 % AP, +10.0 % DPS) but longer fights let the edge show more. Worth watching in game.
- `node test/sim.cjs 64 120 all` ok (all six modes end, no stuck mechs); mock 32 players / 60 s `OK: no errors` (1.9 ms/tick avg against 1.6 for the pre-pass script on the same run).
- Tests that changed: `test/mechanics.cjs` gained 15 checks for this pass (159 total); `test/balance.cjs` allows one AP of rounding in the anti-stomp check (it reported +15.0 % "OVER" before this pass too).
