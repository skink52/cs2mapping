# Puppet Brawl for CS2: mg_cs2_fighter

Puppet Brawl is a 2.5D street fighter that runs inside CS2 on a cs_script point_script. You only need the addon; no plugins or server mods.

Up to four players fight on a neon night-market stage, using CS2 agent models. Everyone else in the map can stand on the bleachers and watch the fight happen live, because it takes place on a real stage in the world. The map takes 1–8 players for testing: 4 fight and the rest watch. There are 24 spawns.

## What's in the addon

| Path | What it is |
|---|---|
| `maps/mg_cs2_fighter.vmap` | The arena: a stage under a torii gate, neon shop fronts, lanterns, bleachers, 4 control pads, 8 host buttons, all lights and all game entities |
| `scripts/puppet_brawl.js` | The game. Hammer compiles it to `puppet_brawl.vjs` |
| `models/puppet_brawl/rig/` | `pb_rig.vmdl`: an invisible skeleton that holds all 52 fight animations (SMD files in `anims/`) |
| `models/puppet_brawl/props/`, `pb_ball.vmdl` | Neon signs, neon tubes, lanterns, pad rings and the glowing ball (used if an effect model is missing) |
| `models/puppet_brawl/pb_proj_*.vmdl` | The projectiles: TIMBER's glowing wooden knot, BRASS's brass cog, MOTLEY's harlequin juggling ball |
| `models/puppet_brawl/pb_fx_*.vmdl` | Effect shapes: the shockwave ring, the hit-flash star and the projectile trail orb (additive glow) |
| `materials/puppet_brawl/` | Textures and materials for those props |
| `panorama/layout/custom_game/puppet_brawl.xml` and `panorama/styles/custom_game/puppet_brawl.css` | The fight HUD: health bars, timer, announcer, lobby and move list |
| `soundevents/soundevents_addon.vsndevts` | Your original file with 12 `pb.*` sounds added at the end. They use stock CS2 sounds |

A backup of the original template map is kept as `maps/mg_cs2_fighter_template_backup.vmap`.

## The fighters

Each fighter always uses the same agent. When two players pick the same fighter, the second copy gets a colour wash so you can tell them apart.

| Fighter | Agent | Style |
|---|---|---|
| TIMBER | Professional (T) | Balanced brawler, orange |
| BRASS | SWAT (CT), 7% bigger | Slow, heavy, armoured charge, cyan |
| PIROUETTE | FBI (CT) | Fast kicks and flips, pink |
| MOTLEY | Elite Crew (T), 5% smaller | Tricky, long reach, green |

### How the bodies work

An invisible rig (`pb_rig.vmdl`) plays the animation, and the agent model is bone-merged on top of it. One animation set therefore drives all four agents.

Each fighter has a point_template named `pb_tpl_<id>` containing the rig and its agent. The script spawns one per player and hides spare ones under the floor.

## First run (Hammer and CS2)

1. Open **Hammer** with the mg_cs2_fighter addon and load `mg_cs2_fighter.vmap`.
2. Open `models/puppet_brawl/rig/pb_rig.vmdl` in **ModelDoc** once and save it, so it compiles.
   - The props compile on their own when the map loads them. If an effect or projectile model shows as an error, open its `.vmdl` (`pb_proj_knot`, `pb_proj_cog`, `pb_proj_jball`, `pb_fx_ring`, `pb_fx_burst`, `pb_fx_orb`) in ModelDoc and save it.
   - If Hammer shows a pink or red error model, open that `.vmdl` in ModelDoc too.
3. **Build the map**: Map → Build, full compile with lighting.
4. In CS2 run `map mg_cs2_fighter`. The console should print `[puppet_brawl] v… ready: stage … 4 pads, 4 watch spots, HUD on, 11 sounds`.
5. Walk down to the glowing pads behind the barrier, stand on one and press **E**.
6. For a solo test, type `sv_cheats 1` then `pb_cpu_match` to watch two CPUs fight. `pb_stop` (or the STOP CPUs button) ends any CPU game and sends the CPUs away.
   - Or press the **ADD CPU** button, then **START**.

## Controls

| Action | Key |
|---|---|
| Move | **A / D**. Walking away from the opponent also guards |
| Block | Hold away (you walk back while guarding), or **SHIFT** (guard in place). Down+away guards low without moving. After you block a hit, the guard holds still for a moment before you can walk back again |
| Hit zones | Every hit is HIGH, MID or LOW from where it lands. A standing guard stops high and mid; a crouching guard stops mid and low. Sweeps are always low; overheads and jump-in attacks are always high |
| Perfect block | Press guard just before a hit lands: no chip damage, you recover at once, the attacker is left open, and you get 2 health back |
| Jump | **W** or **SPACE** |
| Crouch | **S** or **CTRL** (down+back blocks low) |
| Punch / kick | **MOUSE1** / **MOUSE2** |
| Combos | P,P = jab into the 1-2 finisher. P,P,K = carry on into the kick finisher. P,K = jab into a mix-up ender (a low or an overhead). K,K = snap kick into the kick finisher. Strings come out on a hit, a block or a miss, and finishers can cancel into specials on contact |
| Special | **R**. Toward+R and down+R give different specials. Motions also work, e.g. down, forward, punch |
| Throw | **F** up close. Tap F or punch right after being grabbed to break the throw |
| Dash / backdash | Double-tap toward or away |
| Tag (tag team) | **SHIFT+R** while you're on stage |
| Leave | Hold **E** |

**In the lobby:**
- A/D picks a fighter, MOUSE1 readies up, MOUSE2 un-readies.
- The first player in is the host. The host's R changes the mode and F adds or clears CPU fighters.

**Host buttons:** these are the glowing green blocks on either side of the pad platform: MODE, ADD CPU, REMOVE CPU, START, STOP CPUs, CPU EASY / NORMAL / HARD and RESET. Each one says in chat what it did (or why it couldn't). Turn that off with `BUTTON_CHAT`.

**Taking over a CPU:** press E on a pad that a CPU is using.

## Combo finishers

| Fighter | P,P (then K for P,P,K) | P,K mix-up | K,K |
|---|---|---|---|
| TIMBER | Splitter (back-hand hook, high) | Root Sweep (LOW, knocks down) | Timber Fall (high roundhouse, knocks down) |
| BRASS | Rivet Hammer (OVERHEAD smash) | Gear Grind (LOW stomp-sweep, knocks down) | Boiler Kick (mid push kick, huge pushback) |
| PIROUETTE | Pas de Deux (quick two-punch, high) | Plie Sweep (LOW, knocks down) | Arabesque (high kick, launches) |
| MOTLEY | Slapstick (double slap, high) | Jester Drop (OVERHEAD axe kick) | Banana Sweep (LOW sweep, knocks down) |

After a jab, P,P and P,K look the same until the second hit, so the defender has to guess whether to stand or crouch. Every fighter also has the shared sweep (down+K, low) and jab (high).

The fighter cards show a live combo counter (hits and damage), each player's best combo of the match and how many perfect blocks they've made.

## Effects for the crowd

- **Projectiles** have their own models: TIMBER throws a glowing, cracked wooden knot, BRASS lobs a spinning brass cog, MOTLEY throws a striped juggling ball. Each one spins in the fight plane and leaves a fading trail in the fighter's colour. When one breaks it bursts with its own particles: embers, electric arcs or confetti.
- **Hits** flash a star in place of the old ball. Heavy hits and specials also throw metal sparks.
- **Specials** send a coloured shockwave ring along the floor and a ring through the air, and set off the fighter's own particles: TIMBER embers, BRASS sparks, PIROUETTE a crackle of light, MOTLEY confetti. Combo finishers get a smaller floor ring.
- **Big moments:** a KO gets a white shockwave and a firework. Knockdowns kick up dust, a perfect block flashes a blue ring with a zap, a tag-in sends a ring across the stage, and a match win sets off fireworks at both ends.
- **Stage announcer:** two world-text lines hang under the torii beam, facing the bleachers. The big line repeats the announcer (ROUND 1, FIGHT!, K.O., ... WINS). The small line calls each special and perfect block, e.g. `BOB - COG TOSS`.
- Particles are stock CS2 effects (`impact_metal`, `fx_electricspark_*`, `firework_crate_explosion_01`, `moneycrate_burst_confetti`, `impact_dirt_child_smoke_puff`, `env_embers_small`). They spawn from the `pb_tpl_fx_*` templates under the back street. At most 14 are alive at a time.
- `FX` (false = plain glowing balls and none of the above) and `FX_PARTICLES` (false = keep the models and rings but no particles) switch these off.

## The HUD

The HUD has a back-alley arcade look:
- Hard-edged charcoal cards with heavy black outlines and a seat-colour bar.
- Blood-to-fire health bars with segment ticks and a white damage chip. The bar throbs when health is low.
- Diamond round markers and an amber-framed clock.
- An announcer with a hard drop shadow (FIGHT! and K.O. tilt and slam in).
- A steel-plate lobby with an amber hazard strip.

## Modes

- **Duel**: 1v1, winner stays on. Players waiting their turn stand at the back of the stage.
- **Tag team**: 2v2, but only one fighter per team is on the stage. Pads 1–2 are RED and pads 3–4 are BLUE.
  - The partner waits at the back of the stage. The fighter on stage tags them in with **SHIFT+R** (3-second cooldown between tags).
  - A benched partner slowly wins back half of the damage they took before tagging out.
  - When the fighter on stage is knocked out, the partner steps in. The round ends when both fighters on a team are out.
  - A 2v1 gives the solo fighter double health. Rounds last 99 seconds; on time, the team with more health left wins.
- **FFA** (all four at once) is still in the game but is no longer on the MODE button. Add `"ffa"` to `MODES` in the script settings to bring it back. Set `TAG_TEAM` to false for the old four-at-once 2v2.

## Settings worth knowing

These live in the `CONFIG` block at the top of `scripts/puppet_brawl.js`:

| Setting | What it does |
|---|---|
| `WORLD_SCALE` (0.72) | Fighter size. 0.72 is normal CS2 agent height |
| `CAMERA_MODE` | `"auto"` follows the fight. `"fixed"` uses an info_target named `pb_camera`. `"off"` stays first person |
| `CAMERA_HEIGHT`, `CAMERA_MIN_DIST` | How high and how close the fight camera sits |
| `FIGHTER_DEPTH`, `QUEUE_DEPTH` | How far FFA fighters spread front to back, and where the duel queue waits |
| `TEAM_GLOW` | Red and blue outlines in teams mode |
| `WEAPONS` | `"strip"` removes guns while fighting and gives them back afterwards |
| `ARENA_COMMANDS` | Server settings run at start and every round: kicks bots, stops rounds ending, respawns, no starting pistols. Use `[]` to leave the server alone |
| `BODY_YAW` | Turns every fighter by this many degrees. Only needed if the agents face sideways (try 90 or -90) |
| `FX`, `FX_PARTICLES` | Effects for the crowd (see above) |
| `STAGE_TEXT`, `STAGE_SUB` | Names of the two world texts over the stage |

Game rules sit in the same CONFIG block: `ROUND_TIME`, `ROUNDS_TO_WIN`, `CPU_LEVEL`, `BACK_BLOCKS` (false makes blocking SHIFT-only and away walks back), `PERFECT_BLOCK` and `PERFECT_WINDOW`.

## Test checklist (please report back)

- [ ] `[puppet_brawl]` lines in the console: any warnings? Copy them to me.
- [ ] Do the agents **move with the animations**? If they stand frozen in an A-pose or T-pose, the bonemerge didn't attach. Tell me and I'll switch to the fallback.
- [ ] Is the agent **the right size and facing the right way**? (Facing is turned by the script, so a sideways agent means the rig's forward axis is off.)
- [ ] Do punches go **straight out at the opponent** now?
- [ ] Is the lighting too dark or too bright? Are the neon signs glowing?
- [ ] From the bleachers, can you see the stage clearly?
- [ ] Do pads, buttons and `pb_cpu_match` work? Does hold-E leave?
- [ ] Do the sounds play (hits, KO, bell)?
- [ ] Do the knot, cog and juggling ball show and spin? Are the rings and hit stars coloured, or plain white? (White means the effect material ignores tint; tell me.)
- [ ] Do the particles fire, e.g. a firework on a KO? Does the stage text under the torii show ROUND / FIGHT / K.O. and the special names?

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| "must hold the rig prop" warning | The template is missing one of its two props. Undo any edits to `pb_tpl_*` in Hammer |
| `pb_rig` looks empty in ModelDoc | Normal: the rig is invisible (only specks hidden inside the body). Check the Animations list has 52 clips and the skeleton has bones |
| Fighters face the camera or away from it | Set `BODY_YAW` to 90 (or -90) |
| Fighters invisible | `pb_rig.vmdl` hasn't compiled. Open it in ModelDoc and check the compile log |
| Agent frozen, not animating | The bone-merge failed. The script also sends FollowEntity as a backup; send me the console output |
| Pink checkerboard props | That model or material didn't compile. Open it in ModelDoc or the Material Editor |
| Projectiles are plain balls | `pb_tpl_proj_*` is missing from the map, or the projectile model didn't compile |
| Stage text stays blank | Check that `pb_stage_text` and `pb_stage_sub` exist. If they still say nothing, the world text didn't take the SetMessage input; tell me |
| No HUD | Check that `pb_hud` points to `panorama/layout/custom_game/puppet_brawl.vxml` (the `.xml` compiles to `.vxml`) |
| Script not running | The point_script `pb_script` must use `scripts/puppet_brawl.vjs`. Check the console for a JavaScript error line |
