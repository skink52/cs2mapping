# Tripo pilot: three original IRONFRAME mechs

Goal: a consistent, publishable roster (our own assets instead of other games' ports). Pilot one mech per weight class,
put them through the normal pipeline (convert, rig, clips, review sheet), then decide on the rest.

Studio settings (from the Trench Warfare runs, docs/reference/external-tools.md): Text mode, HD, model H3.1, PBR on,
Triangle topology, polycount box: **light 12000, medium 15000, heavy 18000**. Then Tripo's **auto-rig (biped/humanoid)**
if offered, and export **GLB** (rigged). Expect ~55 credits per model. No glyphs/text in any prompt (Tripo paints gibberish).

Shared style line (keep it identical in all three, so the roster matches):
> industrial military combat mech, armored core style, hard-surface sci-fi, gunmetal grey and off-white armour panels with
> worn edges, small hazard-yellow accents, glowing cyan sensor eye, neutral colours, no logos, no runes, no glyphs, no
> letters, no text, standing in an A-pose with arms slightly away from the body, full body, clean silhouette

## 1. Light: "Kestrel" (fast skirmisher)
> slim bipedal light combat mech, narrow armoured torso, long digitigrade-style legs with large thruster pods on the
> calves, small angular head with a single visor, two slender arms with three-fingered hands, twin thruster vents on
> the back, agile racing silhouette, + shared style line

## 2. Medium: "Warden" (all-rounder)
> balanced bipedal medium combat mech, broad layered chest armour, sturdy straight legs with knee armour plates,
> pauldrons over the shoulders with mounting points on top, compact head with a horizontal visor slit, two arms with
> five-fingered armoured hands, a backpack with booster nozzles, + shared style line

## 3. Heavy: "Bastion" (tank)
> massive bipedal heavy combat mech, wide boxy torso with thick sloped armour, short powerful legs with huge flat feet,
> very large shoulder blocks, a low head recessed between the shoulders, thick arms with heavy armoured hands, exhaust
> stacks on the back, fortress-like silhouette, + shared style line

After each: download the GLB into `C:\source1\ironframe_work\tripo\<name>.glb` and tell Claude; the pipeline
(`create/glb2cs2_multi.py` / `create/playermodels/fbx_export.py` for rigged GLBs -> skeleton -> `create/mech_anim.py`
clips -> review sheet) takes it from there.

# Humanoid replacements for Krasnaya, Lisa, Supplice (10 Nov 2026 evening)

> **Not needed (skink52, 10 Nov 2026):** with the built-in weapons stripped, Krasnaya, Lisa and Supplice keep their current models. Nothing below was generated; kept for reference only.

skink52: "Supplice, krasnaya, and lisa also could just be our tripo models - we can go for a full humanoid type theme for the mechs."
Three new models replace the AC ports `ac4a_hari`, `ac4a_oldking`, `ac4_berlioz` as the `model` of parts.json frames 1, 3, 6
(ids, keys, stats, traits and auras stay). Weapons are attached by the game, so every prompt asks for empty hands and a clean
back / shoulders.

**State: NOT generated. 0 credits spent, no task ids.** The CLI is signed in (`tripo.cmd doctor` ok, region ov) but its API wallet
is empty (`tripo.cmd balance` -> 0; Tripo keeps studio credits and API credits apart). The one real attempt (Krasnaya, 17:36)
stopped at the CLI's balance pre-check: `Insufficient credits`, api_code 2010, exit 4, nothing submitted (`tripo.cmd history` and
`usage` are empty). Two ways on, both skink52's call:
- **Studio, as for the first four** (studio.tripo3d.ai; ~55 studio credits per model): Text mode, HD, model H3.1, PBR on, Triangle
  topology, polycount box as below, then auto-rig (biped / humanoid), export rigged **GLB**. Paste the full prompt below. Save as
  `C:\source1\ironframe_work\tripo\tripo_krasnaya.glb`, `tripo_lisa.glb`, `tripo_supplice.glb`.
- **CLI, after `tripo.cmd topup`** (API credits; list price 30 for the H3.1 generation with a detailed texture, plus the rig step,
  which the CLI does not estimate): `python -I C:\source1\ironframe_work\scripts\tripo_gen.py krasnaya|lisa|supplice [--try N]`
  under the watchdog (expect ~8 min each). It runs `tripo make "<prompt>" --model H3.1 -p pbr=true -p face_limit=<N>
  -p texture_quality=detailed -p negative_prompt=... --then rig-check,rig:spec=mixamo,out_format=glb` and copies the rigged GLB to
  the same three paths; task ids and credits land in `C:\source1\ironframe_work\tripo\cli\<name>_tryN\result.json`.
  The prompts live in `C:\source1\ironframe_work\scripts\tripo_prompts.json` (same text as here).

Budget set for this job: three models plus at most one retry each (six generations). Each prompt = frame line + common line +
the shared style line above (unchanged, so the roster matches).

Common line (all three):
> humanoid proportions, upright stance, two arms and two legs, empty open hands with armoured fingers, nothing held, no weapons,
> bare flat shoulder tops, flat clean back with no backpack

Negative prompt (CLI only; the studio has no box for it):
> weapon, gun, rifle, cannon, sword, blade, shield, missile pod, backpack, cape, cloth, wings, tail, text, letters, numbers, logo,
> glyphs, runes, base, pedestal, extra limbs

Silhouettes are kept clear of the first four (Sandviper: boxy sensor-head scout; Kestrel: slim racer with calf thruster pods;
Warden: broad chest, pauldrons, antennae; Bastion: boxy fortress):

## 4. Krasnaya, light, 12000 (key `tripo_krasnaya`): the duelist
Trait Opener (first hit after a quick boost +20 %), aura crimson ribbons from the shoulders: a fencer, tall and narrow, crest fin.
> tall slender humanoid light combat mech, fencer duelist silhouette, narrow wedge-shaped chest with a pointed prow, wasp waist,
> long straight legs with sharp knee spikes and narrow pointed feet, small swept-back shoulder caps, sleek helmet head with one
> long backward-swept crest fin and a narrow visor slit, thin tapered forearms, + common line, + shared style line

## 5. Lisa, light, 12000 (key `tripo_lisa`): the jumper
Trait Double jump, aura blade wings on the back (needs the flat back): compact, huge thighs, piston shins, beak head. Humanoid
knees (the Mixamo rig and mech_anim's clips bend a human knee); parts.json `legs: "reverse"` is only the stat profile and can stay.
> compact humanoid light combat mech built for jumping, athletic sprinter silhouette, broad hunched shoulders, short beak-like
> sensor head set low between raised collar plates, very thick powerful thighs, long shins with exposed hydraulic shock pistons,
> wide splayed two-toed feet with heel spurs, short arms with slim forearms, + common line, + shared style line

## 6. Supplice, medium, 15000 (key `tripo_supplice`): the interceptor
Trait Overshoot (assault boost 25 % cheaper), aura plasma plumes from the boosters: V torso, flared thruster shins, T visor.
> sleek humanoid medium combat mech, high-speed interceptor silhouette, broad V-shaped torso with a large chest air intake
> tapering to narrow hips, angular swept shoulder armour, long legs whose shins flare wide toward the ankle into bell-shaped
> thruster housings with vents at the heels, tall narrow helmet head with a T-shaped visor and a centre fin, two flush thruster
> nozzles recessed in the upper back, + common line, + shared style line

| model | task ids | credits | result |
|---|---|---|---|
| tripo_krasnaya | none (try 1 refused: insufficient API credits) | 0 | not generated |
| tripo_lisa | none | 0 | not generated |
| tripo_supplice | none | 0 | not generated |

Once the GLBs exist, the steps are in `out/handover_tripo.md` (frames.json entries, conversion, review, compile, weapon fit, auras,
the three parts.json `model` lines, both addons).
