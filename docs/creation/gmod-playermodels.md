# GMod player models in CS2

How a Garry's Mod workshop player model becomes a working CS2 player model (CS2's own animations, hit boxes, ragdoll, weapon attachments,
first-person arms), unattended and repeatable. Tools: [`create/playermodels/`](../../create/playermodels/README.md). Background on the
CS2 agent template: [models.md, Player models](models.md#player-models).

## Workflow

```
SteamCMD (anonymous)          fetch.py            pick in catalog.json          pipeline.py --compile
workshop_download_item 4000 -> .gma/.bin -> extract -> scan: every .mdl ->  slug + mdl  -> convert -> previews -> resourcecompiler -> report
```

1. **Find candidates.** `browse.py catalog.json` lists the Workshop items tagged Model that aren't in the catalog yet (top rated over
   7/30/90/365 days, plus "playermodel" searches: top rated, trending, most subscribed; the browse pages embed their item list as JSON).
   Keep humanoid player models on the **ValveBiped** skeleton (`player_manager.AddValidModel` in the item's lua), human proportions,
   materials inside the item. Add the picks to `catalog.json` (`chosen` false, `looked_at` <batch>) before the scan.
2. **Download + scan** (`fetch.py catalog.json --scan --suggest`; `--suggest` applies step 3's rules and lists the passing models per item). For each item it lists every model with: registered name, ValveBiped yes/no, height,
   head-joint height, **scale** (CS2 head joint 70.8 u / the model's), vertex count, VMTs and colour VTFs missing from the item.
3. **Choose** (edit `catalog.json`: `chosen`, `slug`, `mdl`; `skin`, `bodygroups`, `depends` if needed). Rules that worked for batch 1:
   - scan scale (CS2 head joint / the model's) 1.0-1.15. HL2-sized GMod humans (head joint 64.6 u) read 1.096; under 0.9 or over 1.3 is not
     CS2-sized (a 43 u cartoon read 2.2). The converter's fitted uniform scale comes out lower (about 1.04): it fits all the joints, not the head.
   - nothing in `missing_vmt` / `missing_vtf`. **Base-game materials:** many GMod models use Half-Life 2's or CS:S's own textures (citizen
     faces, the skeleton, CS:S terrorists). SteamCMD's anonymous Garry's Mod dedicated server (app 4020, 6.5 GB) ships them in
     `sourceengine/` (hl2_textures, hl2_misc, content_hl2, content_cstrike); `vpk.py` extracted their `materials/` (3.1 GB) to
     `<work>/basegame/`, which the scan and the converter search last (`fetch.paths` key `basegame`, env `PM_BASEGAME`).
   - vertex count: CS2 agents are ~20-40k. Under ~100k is fine; the 270k-300k RE Requiem soldiers were left for a decimation pass.
   - skip `c_arms` / `_vm` / `_hands` models (first-person arms come from the CS2 template), `_npc` / `_ragdoll` duplicates.
   - batch 4's rejects, worth spotting before converting: **capes and coats on their own bones** (Batman Arkham City: CS2 has no such
     bones, so the cape stays on its bind position and stretches into a sheet behind the model); **HL1-style rigid low-poly** models
     (under ~1k vertices, one bone per part: fists and limbs fold, as hlew_security showed); models that need **CS:S or HL2 textures**
     beyond the eyes and mouth (`t_arctic`, `t_guerilla`, citizen `*_facemap`: the PC has no CS:S/HL2 VPKs).
4. **Convert** (`pipeline.py catalog.json --compile`), then look at `preview/contact_sheet.png`, each `<slug>_bind.png` / `_posed.png`, and
   **`<slug>_hands.png`** (hands in CS2's pose, wrists bent back): broken fingers or a hand through the cuff are the failures to catch.
   Small pokes are acceptable; a wrung finger or a folded wrist is not.
5. **In game:** compile the addon (the pipeline already compiled the vmdls), put one hidden `prop_dynamic` per model in the map so it's
   precached, and `pawn.SetModel("models/player/gmod/<slug>/<slug>.vmdl")` from cs_script (see [models.md](models.md#player-models) step 8).
   On the minigames server (slime-mg-gm) the shop precaches and sets them; its test `tests/run.py --no-restart --only none --gmod-models`
   puts every compiled model on bots that fight on ar_shoots (8 models a round plus 2 stock-agent control bots) and checks from the game
   log that each model goes on, takes hits by hitgroup and logs no errors. Run it after each batch. What it can't see: textures,
   first-person arms, ragdoll looks (a client).

## How the conversion works

The CS2 animation graph drives one fixed skeleton (`worldmodel.vnmskel`), so the mesh has to be moved onto that skeleton's bind pose; the
skeleton can't be changed to fit the mesh. Method from `projects/cs21.6/tools/models.py` (1.6 player models), extended to skinned meshes:

- **Orientation and floor.** The source is turned about Z so its toes point +X (CS2 agents face +X; this batch's models faced +Y, turned 90°),
  and its lowest vertex goes to z = 0.
- **No stretching (default, `rigid`).** The model keeps its own proportions: one **uniform** scale, nothing else changes size. Each ValveBiped
  bone's piece of the mesh is only *turned* so the bone points along the matching CS2 bone (GMod reference pose -> CS2 A-pose), and stays joined to
  its parent at its own length (forward kinematics down the model's own skeleton). The uniform scale is the least-squares fit of the model's
  joints to CS2's (about 1.04 for HL2-sized humans), the horizontal offset likewise; the feet stay on the floor. A vertex with several weights
  blends its bones' turns, so joints stay closed. Pelvis, spine, neck and head aren't turned at all (upright as modelled).
  - The cost: the model's joints don't sit exactly on CS2's. Batch 1: limbs about 2 u off, head and pelvis about 4 u (CS2's skeleton has a longer
    torso and neck than GMod's). CS2 bends the mesh about its own joints, so elbows, wrists and the neck bend a little off the model's creases.
    The report lists every joint's offset (`joint_offsets`).
  - **Arms and hands go onto CS2's pivots.** With the whole-body fit alone, hands sat 2-3 u off CS2's hand and finger bones: fine in the bind
    pose, wrung apart as soon as CS2's pose curled the fingers (finger bones are ~1.5 u long, so a 2 u pivot error throws a finger across the
    hand). So each arm is moved as one rigid piece until its shoulder sits on CS2's `arm_upper`, and the hand with its fingers goes onto CS2's
    wrist, scaled uniformly (`hand_scale`, 0.8-1.25, batch 1 ~1.0) so its middle knuckle meets CS2's. Finger joints then land within ~0.5 u;
    the forearm absorbs the ~1 u left over (its wrist end follows the hand by the skin weights). Check hands in `_posed.png`, not `_bind.png`.
  - **Wrist blend.** GMod sleeve cuffs are weighted to the forearm only, so a hand bent back (palm under a rifle barrel) pushed through the cuff.
    The last 3 u of the forearm, cuff included, now follow the hand, rising to 60% at the wrist (`WRIST_BLEND`); the cuff lifts with the hand
    (checked bent back 55° and 75°).
  - **Torso recentred.** GMod chests sit 2-3.5 u further forward on the spine than a stock agent's (chest centre +2 to +3.3 u vs -0.35 u),
    which put CS2's hand poses inside them. The upper torso moves back as one piece until its chest is centred like the agent's (`spine1` half
    way, so the waist shears gradually); legs stay, arms are re-seated after. Batch 1: 0.1-3.7 u.
- **Fit warnings** (report `warnings`, batch status `WARN`), measured against the template's own (stock-agent-shaped) body:
  chest front more than `CHEST_WARN` 4 u further forward than the agent's (armour bulk, can't be fixed without reshaping); in CS2's preview pose a
  wrist more than `HAND_WARN` 3 u behind the chest surface (hand inside the torso; fine models read 0 to -5); an arm or leg joint more than
  `LIMB_WARN` 6 u from CS2's (a rig that doesn't match); finger segments' skin centred more than `FINGER_WARN` 1.8 u off their CS2 finger bones
  (median; fine models 0.4-1.7, the old pivot bug ~2) - a hint to look at `_hands.png`, not a verdict. Batch 1: SWAT and V.A.R.T. warn (chest +5.8 / +5.2, right hand 3.8 / 3.5 u in).
  - `--fit` (old method, `mode='fit'`): pieces stretched along the bone to CS2's bone lengths and placed on the CS2 joints. Joints match exactly,
    but against the uniform scale it shortened the arms and legs 8-12% and stretched the upper chest and neck 1.5-1.65x (tall collars). Not used.
  - **Hands** are turned with a frame (knuckle direction + index-to-pinky line) so palms face where CS2's do; the **forearm** twists gradually
    from 0 at the elbow to the hand's roll at the wrist, so there's no candy-wrap at either end.
  - **Fingers** follow their CS2 finger bones (relaxed curl), rolled with the palm; the thumb with the palm normal.
  - **Feet** keep their soles flat: they only turn about Z toward CS2's toe direction.
- **Bone map.** `Bip01_Pelvis → pelvis`, `Spine, Spine1, Spine2, Spine4 → spine_0..3`, `Neck1 → neck_0`, `Head1 → head_0`,
  `L_Clavicle/UpperArm/Forearm/Hand → clavicle_L/arm_upper_L/arm_lower_L/hand_L`, `L_Thigh/Calf/Foot/Toe0 → leg_upper_L/leg_lower_L/ankle_L/ball_L`,
  `L_Finger0..02 → finger_thumb_0..2_L`, `Finger1x/2x/3x/4x → index/middle/ring/pinky`. Helper bones (`*_Bicep`, `*_Ulna`, `*_Wrist`, `*_Elbow`,
  `*_Trapezius`) move with their main bone; anything else (jiggle bones, accessories) follows its nearest mapped parent and is listed in the report.
- **Weights.** Up to 3 per vertex (CS2's limit, as in VVD). Weight on `arm_upper_*`, `arm_lower_*`, `leg_upper_*` is spread along the CS2
  twist chain (`*_TWIST`, `*_TWIST1`) by the vertex's position along the bone, like the stock agents.
- **Low-poly limbs: twist split.** A limb with vertex rings only at its ends (a two-ring forearm: elbow ring and wrist ring) flattens into a
  twisted ribbon when CS2 rolls it (support hand turning palm-up under a gun): one ring gets the full twist, the other none. Triangles whose
  twist parameter (upper arm 0-1, forearm 1-2, thigh 0-1) changes by more than `TWIST_STEP` 0.34 along an edge are split at that edge (only
  steep edges, so neighbours split alike: no T-junction cracks), midpoint weights averaged; up to 3 passes. Batch 3's SCP Class-D: 270 triangles.
- **Hard-skinned elbows/knees.** Rigs where every vertex follows one bone fold into a wedge at a bent elbow or knee. Vertices >= 95% one side
  and within `JOINT_SOFTEN` 2.5 u of the joint give up to half their weight to the other side. Blended vertices are untouched.
- **3-finger rigs** (thumb, index, middle; no ring/pinky): the palm's side-to-side line uses the outermost finger the rig has. Before, these
  hands silently skipped alignment and the fingers bent about the wrong points; a hand that still can't be aligned is now a warning.
- **Mesh.** LOD0 of each body part's **option 0** (the game's default: a blank option 0 means the part is off) or the catalog's `bodygroups`,
  skin family `skin`. Earlier runs took the first option *with geometry*, which put party hats, riot shields and extra gear on 11 models. VTX triangles are clockwise; they're flipped and the DMX
  writer double-checks against the normals. Flexes, jiggle bones, LODs and the GMod `c_arms` are dropped.
- **Eyes.** `EyeRefract`/`Eyes` meshes get UVs projected from the MDL eyeball (`u, v = (p - centre)·(right, up) · iris_scale + 0.5`) onto the
  iris texture.
- **HL2 shared eye/mouth textures.** Many HL2-styled models use Half-Life 2's own `eyeball_l/r` and `mouth` textures, which GMod supplies and the
  item doesn't (batch 2: 6 of 12 rejects failed only on these). The converter generates stand-ins: an eye texture laid out like Source's iris
  projection (sclera at the clamped edge, brown iris, pupil, highlight) and a dark mouth interior. Other missing base-game textures (body sheets,
  faces) still disqualify a model.
- **Hit boxes.** The template's (stock agent) hit box set, so every model is hit like an agent, except the **head** capsule: a model keeps its own
  neck length, so its head sat 2.5-3.3 u from the agent's head capsule (aiming at a chin could miss). It moves onto the model's head (from the
  eyeballs vs CS2's eyeball joints; without eyeballs from the head mesh below its top fifth), the neck capsule half as far, at most 5 u
  (`HEAD_HITBOX_MAX`). Report: `head_hitbox_shift`, `hitbox_fit` (share of each body group outside every capsule). Bulky armour stays outside
  the body capsules, as on stock agents. `fit_hitboxes.py` applies this to already-converted models.
- **Materials.** `$basetexture` (or `$iris`) → `TextureColor`; `csgo_character.vfx` for opaque, `csgo_complex.vfx` with `F_ALPHA_TEST` / `F_TRANSLUCENT`
  for `$alphatest` / `$translucent`, `F_RENDER_BACKFACES` for `$nocull`. `$bumpmap` → `TextureNormal` with **green flipped** (Source 1 normal maps
  are Y-, Source 2 wants Y+). With `$phong`, the bump map's alpha (phong mask) → roughness `225 - 0.55·mask`. Textures capped at 2048.
- **Model.** The template's vmdl (agent skeleton, animgraph, hit boxes, physics shapes + 14 ragdoll joints, attachments, bodygroups) with
  `thirdperson_body` pointing at `<slug>_body.dmx` (written into a copy of the template's body DMX, so the joint list and bind pose are the agent's) and
  the first-person arms, sleeves and preview pose pointing at one shared copy.

### The template

`C:\source1\playermodels\template\` = the mg_50arenas Power Ranger rebuild: tm_phoenix decompiled with Source 2 Viewer, face morphs and
`eye_test` removed, `thirdperson_default_gloves` removed, the 14 ragdoll joints added (the decompile has none). Any agent prepared that way works
([models.md](models.md#rebuilding-a-csgo-player-model-as-a-cs2-agent) steps 1-4). It's Valve data: it stays on the PC, out of git.

## Rigged FBX imports (not from GMod)

A rigged humanoid FBX goes through the same converter (Nov 2026, It Takes Two's Cody and May from The Models Resource):
`fbx_export.py` (Blender, headless) renames the skeleton to ValveBiped (Hips -> Pelvis, Spine/Spine1/Spine2 -> Spine/Spine2/Spine4,
Left/RightShoulder/Arm/ForeArm/Hand, UpLeg/Leg/Foot/ToeBase, Hand{Thumb,Index,Middle,Ring,Pinky}1-3 -> Finger0-4, ArmRoll/ForeArmRoll ->
Bicep/Ulna helpers; face and prop bones follow their nearest mapped parent), keeps 3 weights per vertex, converts metres to inches and flips V,
and writes an npz that `srcmdl.SrcModel` loads. `fbxprep.py` builds the materials from the `.mtl` beside the FBX (colour, DirectX normal map
like Source's, `map_d` opacity as an alpha test). Catalog item: `"fbx"`, `"url"` (source page), `"id": 0`, plus the usual slug/name/mode.
Everything after that (fit, hit boxes, compile, pose sheets, gallery) is the GMod path. Chibi proportions: check the shoulder height against
the head first; Cody's rigid fit lifted his arms 9 u to CS2's shoulder (level with his head), `"mode": "own"` kept them at his own height.
GLBs work too (Briar, a League of Legends rip with a Riot skeleton: L_Hip/L_KneeUpper/L_Clavicle/L_Shoulder/L_Elbow, Spine1/Spine2/Chest):
the exporter maps those names (a skeleton with its own clavicle makes 'Shoulder' the upper arm), leaves out meshes with no skin weights
(a stray Icosphere), saves the textures embedded in the material nodes (unlit glTF materials included; glTF normal maps flipped to Y-)
and `"drop_materials"` removes props (her pillory, lying at her feet in the bind pose).
Riot rigs skin parts of the body to `<bone>_SNAP` helpers parented to the root (Briar's kneecaps: `L_Hip_SNAP`); in game they follow
their base bone, so the exporter reparents each `_SNAP` onto it. Left on the root they mapped to the pelvis and her knees folded into a
forward spike when bent. To see knees and elbows bend, render the pose sheet from the side: `POSE_VIEWS=side,three`.
League of Legends (Nov 2026, batch 12, 142 champions): `lol_export.py` drives modelviewer.lol's own Export button in Edge through
Playwright (base skin, T-Pose, "Minimal Size" GLB; about 9 s each, resumable), `lol_catalog.py` adds each GLB to the catalog with
`"drop_orphans": true` (weapons and props hung off the root would float: Aatrox's sword, Caitlyn's rifle, Annie's Tibbers). T-pose does not
shrink the files (textures dominate) and the converter reads the rest pose anyway. Older Riot skeletons name bones every way: UpArm / uparm /
uparm1 / forarm, a bare hip / waist / C_Hip / even "pevis" as the pelvis, no pelvis at all (the lowest spine is used), L_leg + L_calf
(leg = thigh), fingers as Index1-3, index/_b/_c or Hand_Finger_Index_b_jnt; the exporter maps all of them. `"fold_bones"` swings chains
CS2 can't animate (Ahri's nine tails) back and down and pins them rigidly to their nearest body bone, like a hat; `"drop_bones"` removes
them instead. Left out (no CS2 player fit): snake, centaur, no-legs floaters, a dog pack, a mech, spider legs, insect arms, plus the
quadrupeds and blobs lol_export skips. Yordles scale to human head height, so they come out big-headed like the fun skins (Poppy's hammer
makes her about 230 u tall: review).
Related: trenchwarfare's `tools/soldiers.py` makes CS2 players from Mixamo-rigged GLBs by stretching each bone to CS2's length (fine for
generated soldiers; not used here, where models keep their proportions).

## Rights

Workshop authors keep their rights, and many GMod player models are themselves ported from commercial games (batch 1 includes characters from
Breaking Bad, House M.D., Resident Evil 4, Half-Life and Counter-Strike: Source). Converted models are for **private/local testing**. Before
anything goes in a published map: the author's permission, and nothing ripped from a commercial game (see [workshop.md](workshop.md)).
The catalog records each item's id, title and author; keep that with any model you use.

## Status

All converted models, with a picture of each in CS2's pose: [create/playermodels/MODELS.md](../../create/playermodels/MODELS.md). Per batch: [BATCH1.md](../../create/playermodels/BATCH1.md),
[BATCH2.md](../../create/playermodels/BATCH2.md), [BATCH3.md](../../create/playermodels/BATCH3.md), [BATCH4.md](../../create/playermodels/BATCH4.md),
[BATCH5.md](../../create/playermodels/BATCH5.md), [BATCH6.md](../../create/playermodels/BATCH6.md) (fun skins) (tables from `batchnotes.py`, review notes by hand).
691 models, all compiled ([BATCH9.md](../../create/playermodels/BATCH9.md): 291 from 396 new Workshop items, X-Men incl. Rogue). Earlier: 396 models, all compiled ([BATCH7.md](../../create/playermodels/BATCH7.md), [BATCH8.md](../../create/playermodels/BATCH8.md): the rest of the packs already started). The compiled addon is 2.4 GB: a server ships a selection, not all of them.
**On a server (6 Nov 2026):** all 80 worn by bots that fought on ar_shoots (slime-mg-gm `--gmod-models`): every model goes on, the
animgraph runs (they move and shoot), hits register by hitgroup and nothing logs an error. The hit spread over all models matches stock
agents in the same fights (head 7.6 % against 9.0, chest 21.5/24.1, stomach 35.7/34.7, arms 8.5/9.8, legs 26.5/22.0), so the hit boxes
sit where CS2's do. **Still to check with a client:** the `csgo_character` materials under CS2 lighting, the first-person arms (the
template's gloves), the ragdoll, and the rifle hand on bulky-torso models.

## Notes

- VMTs with a key twice (`$baseTexture` given twice, the second the normal map): Source keeps the **first**; the reader does the same
  (Michael Scott's face came out blue before). 55 of the downloaded VMTs had duplicate keys.
- **Re-downloading an item `cleanup.py` deleted:** SteamCMD reports "Success" and then removes the files on exit, because its
  `steamapps/workshop/appworkshop_4000.acf` still lists the item as installed. Move that file aside (SteamCMD rebuilds it) before
  fetching such items again. Items trimmed by `cleanup.py --prune` must have their extract deleted to get the whole pack back.
- **Hit boxes:** CS2's stock agent capsules, kept as they are (the mesh is skinned to the same skeleton, so body, arm and leg capsules
  follow it). Only the head (and half the neck) moves onto the model's head, from its eyes or head mesh, at most 5 u: GMod heads sit
  a median 3.6 u below a CS2 agent's (shorter HL2 necks). A head within 1 u of stock keeps the stock capsules exactly
  (`HEAD_HITBOX_MIN`). A model with no head mesh (the B2 battle droid, whose "head" is the top of its chest) gets its head hit box on
  the top 8 u of its body, up to 12 u (`HEAD_HITBOX_MAX_NOHEAD`).
- **Head pivot:** GMod heads pivot ~4 u below CS2's `head_0`, so when CS2 tilts the head to aim it swings a little about a pivot above
  it (the neck looks dragged to the model's right). `HEAD_SNAP = True` moves the head onto `head_0` (neck ~4 u longer, no drag); it is
  **off**: skink52 keeps the models' own heads (6 Nov).
- **PlayerColor / team tint** (`$blendtintbybasealpha 1`, GMod's colourable models and the TF2 mercs): the texture's alpha masks parts
  the game tints at run time (greyscale in the texture). CS2 has no such proxy, so the converter bakes in the VMT's own tint or GMod's
  default player colour (0.24, 0.34, 0.41) (`GMOD_PLAYER_COLOR`); the TF2 mercs come out BLU.
- Legacy `.bin` downloads can lack the LZMA end marker; `gma.py` decompresses them as a stream. SteamCMD sometimes answers "Busy": run again.
- `cleanup.py` after a batch: deletes the SteamCMD copies of catalog items (the extract has everything), the extracts of unused items, and with
  `--prune` everything in used items that the chosen models don't need. Batches 1-3: 8.6 GB freed, then 2.0 GB more by `--prune`; a pruned item still reconverts. Don't run it while a batch is
  converting (`fetch.extract` now uses an existing extract first, but other steps may still want the download).
- `create/s2/kv3.mjs` can't read models compiled by the Nov 2026 `resourcecompiler` (KV3 types 26/27 in DATA/MDAT; older compiled models read
  fine), so compiled output is checked by the compile log for now.
- Workshop titles can hold any script and newlines: the tools read the catalog as UTF-8 and print UTF-8; titles are stored on one line.
- Inverted-hull outlines (a mesh named `Outline`, a black copy pushed out along the normals with its faces turned inward, as on the
  Postal Dude) look solid black in the software preview but are fine in CS2: its back faces are culled, as in Source.
- **Additive materials** (`$additive 1`: glows, sparks, tesla arcs) are left out: Source adds them as light, CS2's character shader
  would draw them as solid sheets (the Fallout 3 Tesla armour's arcs came out as purple slabs).
- **Limb warning at 5 u** (was 6): CS2 bends a limb at its own joint, so a model whose hip or knee sits 5+ u from CS2's bends mid-thigh
  and reads as stretched (GFL2 Leva at 5.4-6.0 u, dropped). No per-bone stretching happens; the mismatch is in where it bends.
- **Fun skins** (batch 6): `fetch.py --suggest --scale 0.8,1.6` lets stylised models through the size rule. What worked: human-shaped
  cartoon and meme characters with ordinary limb proportions (Kermit, Rick, Meeseeks, TF2 mercs, Homer, troll-face stick figure).
  What didn't: big heads/bellies with short arms (Peter Griffin 29 u, Grug 21, Shrek 17, Weegee 11 u off): CS2's weapon pose puts
  their hands in their faces. Those wait for a skeleton-length test (can a model keep its own bone lengths in CS2's animations?
  a test model `skeltest` with 8 u longer thighs is built; it needs a CS2 client started with `-netconport 2121` to screenshot).
  Non-ValveBiped rigs (Minecraft Steve, Domo, Left Shark) fail the converter outright.
- Capes, coats and props on their own bones (Batman, Boba Fett, the Lich King, Big Dew's chips) stretch or scatter: CS2 has no such
  bones. Drop them in review (or later: jiggle bones / cloth in ModelDoc).
- **In game (6 Nov 2026, skink52's client, ar_shoots, bots):** materials on `csgo_complex` were invisible on player models (the
  grim reaper's robe, Rogue): every material is `csgo_character` now (279 models reconverted). Skeleton test (`skeltest`, css_swat
  with knee bones 8 u lower): it bent at the lower knee with grounded feet, so **CS2 keeps a model's bone lengths**. That would let
  the converter keep each model's own joint positions (no bends mid-thigh, no head drag, cartoon proportions possible): next step.
- **Default mode 'own' (6 Nov 2026, from skink52's in-game and still-pose reviews):**
  - **Legs on the model's own joints** (`OWN_PARTS`: leg_*, ankle_*, ball_*): CS2's leg joints go to where the model has them, so
    knees and hips bend at the model's own joints. Better on Wesker, the NCR ranger and Rogue in game; worse on cartoon feet, so
    `"fun": true` models stay 'rigid' (catalog `"mode"` overrides either way).
  - **Arms on CS2's pivots across, at the model's own height** (`ARM_KEEP_HEIGHT`): own arm joints (the model's narrower shoulders,
    own arm lengths) put the hands off the gun in CS2's weapon poses, so each arm still moves onto CS2's shoulder sideways and
    forward, but keeps the model's shoulder height; CS2's arm joints are raised or lowered to it. Fixes the dropped shoulders and
    traps (the NCR ranger's arms had moved 4.9 u down) and Rogue's caved armpit. Third person: the gun sits that much higher or lower.
  - **Shoulder blend** (`SHOULDER_BLEND` 7 u): torso vertices near a moved shoulder follow the arm's move, fading out.
  - Neck and head stay on CS2's joints (own neck joints stretched the NCR ranger's neck); torso recentring as before.
  - Rejected in game: everything on own joints (hands converge in front of the chest), the head snapped onto CS2's head joint.
- **Pose sheets:** every model's previews include `<slug>_poses.png`: CS2's shooting pose, a running stride, a deep crouch, arms
  raised overhead (shoulders, armpits) and a body twist with the head turned (neck), textured, in one fixed frame (`poses.py`).
- **Backup:** the library as it was before the 6 Nov shoulder-fix reconversion (content + game addon, reports) is on
  `E:\backup\gmod_playermodels_2026-11-06` (11 GB). Any model can also be rebuilt the old way with `"mode": "rigid"`.
- **Duplicates are kept and flagged** (skink52): `dupes.py` writes `possible_dupes`, shown as "possible duplicate of `<id>`" in the
  warnings of MODELS.md and the server catalog. Score: quality (vertices up to 40k, minus flat textures) + ratings (log lifetime
  subscribers and favourites from Steam's GetPublishedFileDetails, no key needed).
- **Speed:** the converter is single-threaded; `pipeline.py --jobs 6` runs six models at once (6-core PC: ~60% CPU, 3-4x faster).
  `--timeout` (default 30 min) kills a model that never finishes (Batman Animated spun for 2 h). Models with no mesh at chest
  height (Hollow Knight's vessel, FragTrap) skip the chest check instead of crashing.
- Some packs register their models in lua the scan doesn't read (Rogue, Marvel Rivals): add them by hand (`mdl` in the catalog).
- A model's hands look fine in the bind pose even when they will break: the failures only show once CS2 poses them. Look at `_hands.png`.
