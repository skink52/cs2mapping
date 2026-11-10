# Fun features: Overdrive, supply drops, killstreaks

Core: `src/core/86_features.js` (numbers in `IF_FEAT`, override with `cfg.feat`, `cfg.feat.off` disables all). Adapter: `src/cs2/45_features.js`. Tests: `node test/features.cjs`.

- **Overdrive**: `m.overdrive` 0..1. Fill: damage dealt / (2 x victim apMax), damage taken / (4 x own apMax). Full + `input.od` held 0.6 s (RELOAD + USE pressed together, R + E; JUMP + both still works; or chat `!od`; shoulder fire is suppressed while held; bots fire at once) -> 1.2 s charge (speed x0.4) -> pulse radius 600, 2500 damage falling to 40 % at the edge, forced stagger, 900 u knockback. Meter resets to 0. Bots: 3+ enemies within 700, or staggered, AP < 35 % and an enemy near.
- **Supply drops** (tb/cq/kh/ctf/sk): first at 25-40 s, then every 60-90 s x clamp(12 / mechs alive, 0.6, 1.4); one crate at a time, 50 s life on the ground. Random open walkable point away from structures and mechs. Touch (260 u): repair +40 % AP (25), ammo (20), damage +25 % 15 s (20), shield -40 % taken 15 s (20), overdrive full (15); useless picks are re-rolled. Bots within 3500 and with no enemy within 1500 head for it.
- **Killstreaks** (per life, `m.fkills`, kills not erased by the rookie-shield rule): 3 radar ping 10 s (`m.radarT`, enemies within 6000 as bounty markers), 5 artillery (`m.artyReady`; fires at the next lock target at least 700 u away: 6 shells over 4 s, spread 450, 900 damage each), 8 ACE 20 s (+20 % speed, overdrive regen 0.08/s, meter at least 0.5). Exactly 3/5/8: nothing beyond 8.
- Events: `overdrive {slot, phase, pos}`, `crate {phase: drop|land|take, pos, slot, kind}`, `streak {slot, kind: radar|arty|ace|arty_fire, streak}`, `shell {pos, delay, slot}`.
- Crate model: `python -I tools/fx.py --crate-only` (models/ifr/fx/crate/crate.vmdl, `models.json#fx.crate`).

## Frame traits (src/core/87_traits.js, src/cs2/46_traits.js)

Every player frame has a stat profile (`mods` in data/parts.json; keys ap walk boost qb load stagger melee regen cannon_move_acc, plus the new
qb_cost, hover and armor) and one signature trait (`trait`, `trait_name`, `trait_desc`; `desc` mentions it). Tests: `node test/traits.cjs`.
Round robin: `node test/frames.cjs [seeds] [tier]` (1v1 AI duels, every frame pair, both sides, rifle + rifle); ap mods were tuned
against the mean of the normal and hard tiers.

| Frame | Trait | Input |
|---|---|---|
| Krasnaya | Opener: first hit within 1.2 s of a quick boost +20 % | passive |
| Stryder | Reflex: quick boost -30 % EN, cooldown 50 % faster | passive |
| Lisa | Double jump (250 EN) | JUMP again in the air |
| White Glint | Second wind: EN regen +40 % for 2.5 s after a quick boost | passive |
| Atlas | Field repair: 0.8 % AP/s after 5 s unhit (2 % before the Nov 2026 aim model) | passive |
| Supplice | Overshoot: assault boost 25 % cheaper | passive |
| RX-78 | Shield mastery: block +30 % | passive |
| Ogre | Plating: -15 % from the front arc | passive |
| Noblesse | Quick-load: shoulder reload 20 % faster | passive |
| Legion | Gun shield: 3 s, -25 % front damage, half speed, 20 s cooldown, 400 EN | hold F 0.5 s |
| Barbatos | Lifesteal: melee heals 15 % of its damage | passive |
| Mule | Brace: still 1 s = -30 % damage taken, 15 % tighter spread | stand still |
| Ronin | Phase dash: 0.35 s untouchable dash, 600 EN, 7 s cooldown | double-tap Ctrl |
| Unicorn | Overdrive meter +30 % fill | passive |
| Cerberus Atlas | Hardened: 3 s stagger immunity after a stagger ends | passive |
| Sandviper | Spotter: a lock held 1.5 s marks the target for 6 s; the marker's team sees it on radar (bounty dot, any range) and it takes +10 % from everyone | lock on |
| Kestrel | Slipstream: -35 % damage taken for 0.5 s from the start of each quick boost | passive |
| Warden | Aegis pulse: itself and allies within 900 u get a barrier of 10 % of their max AP for 6 s (absorbs after every other cut); 18 s cooldown, 300 EN | hold F 0.5 s |
| Bastion | Siege mode: rooted 4 s, +20 % damage dealt; a quick boost or leaving the ground ends it; 16 s cooldown (from the end), 300 EN | hold F 0.5 s on the ground |

Events `{t:'trait', slot, key, phase:'on'|'off'|'fire'}` (Sandviper's `on` carries `target`, Warden's `on` carries `allies`, the
slots that got a barrier; those pilots get a HUD line too, and a marked human gets a warning); bots use the active traits from featPre
(no AI hook): Warden pulses when it or an ally in range was hit in the last 0.5 s, Bastion digs in with a locked target 700-3200 u away
and AP above 30 %. The Spotter mark (`m.markT`, `m.markTeam`) and the Aegis barrier (`m.barrier`, `m.barrierT`) sit on whichever
mech receives them (reset in featReset). `m.featSpeed` 0 now roots a mech (20_mech.js read it as "unset" before).
Hooks: IF_mechApplyLoadout -> IF_traitApply; IF_applyDamage -> IF_traitDmg / IF_traitImp / IF_traitHit; setInput copies input.cycleHeld;
fireProj / fireLob spread x m.spreadMul; 45_features.js featInput -> traitInput, featPinged also shows Spotter marks; 90_main.js
handleEvent -> traitEvent.

## Frame auras (data/parts.json#auras, tools/auras.py, src/cs2/47_auras.js)

Every trait frame wears a signature effect that shows its trait, so the plainer models read as well as the showpieces.
Built offline by `python -I tools/auras.py` (models, flipbook materials, particles, previews); driven by the adapter with no
per-tick moves. Tests: `node test/auras.cjs`. Review: `preview/auras/sheet.png` + `<frame>_idle.gif` / `<frame>_flare.gif`.

| Frame | Aura | Colour | Idle | Flare / hold |
|---|---|---|---|---|
| Krasnaya | Crimson streamers: two ribbon pairs from the shoulders | rose | slack ribbons, energy pulses root to tip | quick boost: snap taut + flare; opener hit: flare + burst |
| Stryder | Static field: lightning crawling round the legs | indigo | sparse arcs | quick boost: crackle burst + sparks |
| Lisa | Blade wings: 4 angular energy blades a side on the back | orchid | folded down the back | double jump: half, spread, flare, spread, fold (1.45 s); quick boost: twitch |
| White Glint | Light feathers + halo | azure-white | feathers drifting off the shoulders | quick boost: gust; halo ring while Second wind runs (burst on the boost) |
| Atlas | Nanite swarm: two tilted mote rings round the torso | emerald | orbiting motes | Field repair on: hex shimmer over the upper body, denser swarm |
| Supplice | Plasma plumes from the boosters | magenta | short plumes | assault boost: long plumes (flare at the start); quick boost: flick |
| RX-78 | Beam aegis: hex beam plate on the left forearm | chartreuse | small plate | shield raised: full plate; every block: flash |
| Ogre | Forge plating: molten cracks over the front-facing plates | molten yellow | glowing cracks (front only, like the trait) | hit: flash |
| Noblesse | Gilded rings: gyroscope rings with orbiting glints at each shoulder | gold | turning rings | shoulder reload: fast spin; shoulder fire: flare |
| Legion | Bastion projector on the back | mint | projector lens turning | Gun shield on: projector bright + hex wall over the front arc (flashes when hit) |
| Barbatos | Crimson hunger: six dark smoky tendrils with crimson cores | blood crimson | tendrils | lifesteal hit: lash + drain beam from the victim |
| Mule | Hazard rig: shoulder beacons sweeping | hazard yellow | beacons | Brace on: hazard ground ring with dust, fast beacons |
| Ronin | Phase echo: a violet double exposure offset behind the torso | violet | faint echo, glitch bands | Phase dash: echo flares + 4 afterimages left along the dash |
| Unicorn | Psycho-frame: glowing seams over the torso | psycho green | brightness follows the overdrive meter | full meter: full state; overdrive charge / blast: flare |
| Cerberus Atlas | Iron sigil: rune ring + turning star at the feet | gold | dim sigil | Hardened: blazing sigil + rising light crown for the immunity |
| Sandviper | Radar scope: a flat scope ringing the hips (sweep with a trail, range rings, blips) | lime | sweeping scope | new mark: ping (scope grows, outer ring); scope hot while its mark lives |
| Kestrel | Slipstream trails: six rigid vapour trails straight back from shoulders, elbows and hips | sky blue | short wisps | quick boost: long bright trails for the 0.5 s window; a cut hit: hotter flick + burst |
| Warden | Aegis ward: two tilted ward rings round the chest | teal | turning rings | Aegis pulse: a ground shockwave out to the real 900 u range (3 steps, 0.3 s), then a hex barrier cylinder while its own barrier holds (flashes when hit) |
| Bastion | Siege anchors: capacitor bars on the back charging upward | ultraviolet | charging bars | Siege mode: four light stakes driven into the ground round the feet, joined by a square frame; bars bright, flash on every hit it lands |

- **Data** (`parts.json#auras.<frame key>`): `style` (the generator builder), `color` / `accent`, `idle` (idle brightness), `k`
  (per-state brightness), `cam` (dimming for parts marked `cam` on a human's own mech), `reduced` (the one part kept at reduced LOD),
  `parts` (`attach` upper | legs | none, `idle` base state or null, `states`), `flares` (`on` event, `part`, `seq` [[state, t]...],
  `''` = back to the base, `gap`, `if` condition, `pfx` particle pool, `fx` ghosts | drain), `holds` (`when` condition -> state),
  `level` (`od`: brightness follows the overdrive meter). Events: qb land land_hard damage hit fire_s stagger block assault_on
  trait:on|off|fire od:charge|blast. Conditions: trait wind assault shield reload od_full (polled every 4 ticks for full-LOD mechs).
  No core change: everything comes from existing events and mech fields (`trT.wind`, `assault`, shield `raised` / `hits`, `reloading`, `overdrive`).
- **MK V finish**: a pilot whose frame track is at the top level (`caps.levels`) wears the aura multiplied by its `accent` colour
  (`auraMk5Tint`, no stats); the garage track row reads `AURA MK V`.
- **New frame**: copy a block under its part key, pick a style and colours, run `python -I tools/auras.py --only <key>`, then
  `tools/patch_cache.py` (the map needs cache props for the new models).
- **Assets**: one small model per part state, built in the frame's own model frame from its converted mesh (shoulders, back, boosters,
  forearm and feet found from the geometry; shells reuse the low-LOD surface), so the script parents it with zero offset. Materials are
  `csgo_unlitgeneric` additive (Barbatos' tendrils, Ogre's cracks and Noblesse's rings alpha-blended so dark red / gold read in daylight)
  with a 16-cell `F_TEXTURE_ANIMATION` strip: the idle motion (pulses, arcs, orbiting motes, drifting feathers, turning sigils, the
  radar sweep) is the material's own (cells 128 px at most: resourcecompiler clamps textures to 2048). 65 models, 67 textures (11.3 Mpx),
  50-5600 triangles per frame (19 frames).
- **Runtime** (`47_auras.js`): props from the shared pool (`takeProp`), Teleported onto the parent's transform then `SetParent` (after
  the parent is placed; zero local offset), then only `SetModel` (state) and `SetColor` (brightness) when something changes. Afterimages
  and the drain beam are unparented one-offs that fade out in 2 steps.
- **LOD / budget** (`CONFIG.AURA`): every 16 ticks the mechs are ranked by distance to the nearest human: full (every part + flares) for
  humans' own mechs and the nearest 40 within 4000 u; reduced (one idle part) for the next 32 within 9000 u; none beyond. At most 160
  aura props, never when the shared pool is within 60 of `MAX_POOL`, 6 claims per tick, 12 one-offs, 400 u hysteresis.
- **Readability**: auras stay under the IFF marker (preview check: nothing in the head column above height + 18 u; the diamond floats at
  height + 70) and out of the pilot's crosshair corridor (preview check from the chase camera); no aura uses the IFF's orange, cyan or
  red (test). The pilot's own `cam` parts are dimmed (Lisa 0.55, Krasnaya / White Glint / Ronin 0.6, Legion's wall 0.5): CS2 can't hide
  a prop from one client, so other players see that mech's aura dimmed too.
- Hooks: `40_fx.js` fxMechGone -> auraGone (before the rig's props are reused), fxReset -> auraReset; `90_main.js` handleEvent ->
  auraEvent, frame -> auraTick after the mechs are drawn. Not tested in game yet (flipbook animation on props and tint > 1 unconfirmed).
