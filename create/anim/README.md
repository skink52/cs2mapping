# create/anim/: animated bodies for CS2 addons

> **AI-generated code.** From [cs2-fighter](https://github.com/skink52/cs2-fighter/tree/anim-v3) (Puppet Brawl, branch `anim-v3`,
> `tools/anim/`) by skink52, MIT, made project-neutral: no moves, fighters or game paths.

Make your own animations for CS2's player-agent skeleton (from mocap or from keyed poses), check them, and ship them as an
invisible **rig** model that a script plays clips on, with a stock agent bone-merged on top for the looks.

Node 22+ (ES modules, no npm packages). ffmpeg on PATH only for `preview.mjs` / `gallery.mjs`.
Run from this folder: `node <tool>.mjs`. The compiled-file readers it uses are in [`../s2/`](../s2).

## The pipeline end to end

1. **Skeleton (once).** Extract the 77-bone agent skeleton from CS2's VPK (it isn't shipped: it is Valve's data and git-ignored here):
   `node ../s2/skeleton.mjs agents/models/tm_professional/tm_professional_varf.vmdl_c cs2_skeleton.json --vpk "<CS2>/game/csgo"`.
   Every tool reads `cs2_skeleton.json` next to them, or the file in `CS2_SKELETON`. All CS2 agents share this skeleton.
2. **Agent meshes for previews (optional).** `node ../s2/agent_mesh.mjs agents/models/ctm_swat/ctm_swat_varianth.vmdl_c agentmesh/ctm_swat_varianth.json --vpk "<CS2>/game/csgo"`.
3. **Mocap (optional).** CMU motion capture as BVH from [github.com/Shriinivas/cmubvh](https://github.com/Shriinivas/cmubvh)
   (free to use; 120 Hz; files named like `13_17.bvh`). Put the takes you need in `bvh/` or point `CS2_BVH_DIR` at them.
   Don't commit them. `analyze.mjs` lists the punches and kicks in a take, `gallery.mjs` draws them on an agent so you can pick one.
4. **Make poses and clips** in a small script of your own (a "move list" for your game), using:
   - `posture(spec)`: a whole pose from a short spec (pelvis, chest, feet, hands, look-at, hand shapes); `sampleSpecs([[frame, spec]...], n)` for keyed motion on smooth curves.
   - `mocapPoses(spec, {start, end, n})`: cut a take, aim it along +X, stand it on the support foot, retime it with key pairs
     `[[outFrame, takeFrame]...]` (take frames at 120 Hz), blend out of `start` and into `end` (the blend fades to zero at the key
     frame so the real motion shows), lock the support foot, clamp feet to the floor.
   - `Clip`: `fromMocap`, `warp` (key pairs), `speed`, `blendIn/blendOut`, `closeLoop`, `plantFeet`, `extractRoot` (forward travel → root motion for the script),
     and `finish()` = hand shapes, `armsOutOfBody`, `limitHips`, `spreadTwist` (the agent's TWIST bones), `limitAnkles`.
5. **Check** every clip: `node validate.mjs out/addon/models/mygame/rig/anims` (or `checkClip({poses})` in code). It reports knees and elbows
   bending the wrong way, thighs twisted or into the torso, ankles out of range, hands/elbows/knees inside the body, worst first.
6. **Review** on a real agent: `node preview.mjs --smd anims/jab.smd --agent ctm_swat_varianth --sheet jab.png --every 3` (or `--mp4`).
7. **Write the rig**: `writeRig({ addonDir, modelDir: "models/mygame/rig", name: "mygame_rig", clips, idle: "stand" })` writes
   `mygame_rig.vmdl`, `mygame_rig_ref.smd`, `anims/<clip>.smd` + `anims/<clip>_m.smd` (mirrored) and a dark material.
   From SMDs you already have: `node rig_vmdl.mjs <addon content> models/mygame/rig mygame_rig anims/*.smd --loop stand,walk --idle stand`.
   Then compile the vmdl (the addon build's `models|*.vmdl` pass, or `resourcecompiler.exe -i ...\mygame_rig.vmdl`).

Coordinates are CS2 model space: **+X forward, +Y left, +Z up**, units at model scale 1 (the agent is about 72 tall). Clips are 64 fps by default.

## What the rig vmdl contains (and why)

- `RenderMeshFile` → the reference SMD: the bind pose plus **one 0.04-unit triangle per bone**, weighted 1.0 to it, hidden inside the body.
  ModelDoc culls bones with no geometry, and drops a mesh made only of tool materials, so every bone needs a real triangle.
- `MaterialGroupList` remaps the SMD material `<name>_dot` to a real (dark) vmat.
- `BoneMarkupList { bone_cull_type = "None" }` so every bone survives, `anim_graph_name = ""` (plain sequences, no anim graph).
- `AnimationList` with one `AnimFile` per clip: `looping`, `fade_in_time = fade_out_time` (0.12 s loops, 0.05 s others; set `fade` per clip; Puppet Brawl used 0.03 s for hit reactions),
  `framerate = 64.0`, `source_filename = "<modelDir>/anims/<clip>.smd"`. Every clip also gets a `<clip>_m` twin (left and right swapped).
- An extra entry `name = "idle"` with `is_default_idle_anim = true`, so the prop_dynamic's `StartingAnim` / `IdleAnim` can say `idle`.
- SMD animation frames turn the root bone −90° about Z (cancels ModelDoc's import turn), Euler order R = Rz·Ry·Rx.

## Driving the rig in game

**Hammer**, one `point_template` per body (spawn as many copies as you need with `ForceSpawn`):

| Entity | Keyvalues |
|---|---|
| `prop_dynamic` (the rig) | `targetname` e.g. `rig_src_1`, `model` = `models/mygame/rig/mygame_rig.vmdl`, `solid` 0 (Not Solid), `StartingAnim` `idle`, `StartingAnimationLoopMode` `ANIM_LOOP_MODE_LOOPING`, `IdleAnim` `idle`, `IdleAnimationLoopMode` `ANIM_LOOP_MODE_LOOPING`, `use_animgraph` 0 |
| `prop_dynamic` (the agent) | `model` = a stock agent, e.g. `agents/models/ctm_swat/ctm_swat_varianth.vmdl`, `solid` 0, **`parentname` = the rig, `parentAttachmentName` = `!bonemerge`**, `useLocalOffset` 1, local origin/angles 0 |
| `point_template` | `Template01` = the rig, `Template02` = the agent, `spawnGroupType` `INSERT_INTO_POINT_TEMPLATE_SPAWN_GROUP` |

**Script** (cs_script), as Puppet Brawl does it (`src/cs2_adapter.js`):

- `const ents = tpl.ForceSpawn(pos, angles)`; find the rig by `GetModelName()` containing the rig's name, the other `prop_dynamic` is the agent.
  Rename them (`SetEntityName`) so they can be found again. If `agent.GetParent() !== rig`, fire `FollowEntity` on the agent with value = the rig's name (fallback; never needed so far).
- **Play a clip**: `Instance.EntFireAtTarget({ target: rig, input: "SetAnimationLooping", value: "walk" })` for loops,
  `"SetAnimationNotLooping"` for one-shots. Fire it **only when the clip changes** (or must restart): re-firing every tick restarts the clip.
  Facing the other way? Play `"walk_m"`.
- **Speed / hitstop**: `EntFireAtTarget({ target: rig, input: "SetPlaybackRate", value: 0 })` freezes the pose (hitstop); `1` is normal speed,
  `0.33` slow motion. Round the rate (Puppet Brawl: to 0.02) and send it only when it changes.
- Move with `Teleport` on the rig (the agent follows); scale with `SetModelScale` on the rig only; tint (`SetColor`) and outline (`Glow`) the agent.
- Pool bodies and park unused ones out of sight with `Teleport` instead of killing and re-spawning them.

Seen working in CS2 (Puppet Brawl, last in-game test 17 Oct 2026): agents bone-merged from the template animate with the rig; the
bone-keeping reference mesh (without it the rig compiled with no bones and agents stayed in T-pose); clips started with
`SetAnimationLooping` / `SetAnimationNotLooping` (the inputs used since the first delivery). **Not confirmed in game:** blending between
clips via `fade_in_time`/`fade_out_time`, `SetPlaybackRate` 0 as a visible freeze, the `_m` clips on their own, and the `FollowEntity` fallback.

## Files

| File | What it does |
|---|---|
| `m3.mjs` | Vectors, quaternions, 3×3, transforms, easing, monotone cubic curves. No dependencies. |
| `rig.mjs` | Loads the skeleton (`CS2_SKELETON` or `cs2_skeleton.json`); FK, `setWorld`/`setWorldRot` (children follow), `mirrorPose`, SMD frame writer with the root fix. |
| `smd.mjs` | `readSMD(file)` → poses (missing bones = bind). |
| `bvh.mjs` | BVH reader and forward kinematics. |
| `retarget.mjs` | BVH → agent skeleton by rest-matched world rotations (twist carries), pelvis scaled by leg length. CMU joint names by default; `opts.map/legs/axes` for other sources. |
| `clip.mjs` | `Clip` class (see step 4), `mocapPose`, `blendPose`, `normalisePoses`, `turn`, `shift`. `CS2_BVH_DIR` = where take ids are looked up. |
| `mocap_move.mjs` | `mocapPoses(spec, …)` and its parts: `cutTake`, `aimCut`, `displace`, `lockFoot`, `steerTip`, `floorFeet`, `tipOf` (tips `fist_L`, `foot_R`, `knee_L` or any bone). |
| `post.mjs` | Hinge IK `ik2` (knees/elbows bend about one axis; knee kept above the floor), `spreadTwist`, `armsOutOfBody`, `limitHips`, `curlFingers`. `CS2_FREE_IK=1` = plain two-bone IK for comparison. |
| `pose.mjs` | `movePelvis`, `rotatePelvis`, `bendSpine`, `twistSpine`, `lookAt`, `placeFoot`, `placeHand`, `footOnShin`, `footAngles`, `limitAnkles` (toes up 25°, pointed 60°, turn 25°, roll 25°). |
| `posture.mjs` | `posture(spec)`, `setHand`, `sampleSpecs` / `sampleKeys` (keyed postures). |
| `hands.mjs` | Hand shapes `fist`, `tight`, `relaxed`, `open`, `chop`, `claw` (and blends), thumb wrap fitted per side. |
| `validate.mjs <smd or folder>... [--min s]` | The joint checker (CLI and `checkPose` / `checkClip`). |
| `rig_vmdl.mjs` | `writeRig(...)` and CLI: the rig vmdl, reference SMD, clip + mirrored SMDs, dark vmat/PNG. |
| `render.mjs` | Software renderer: skinned agent meshes, floor, lines, text labels. |
| `preview.mjs --smd x.smd --agent a.json` | Contact sheet PNG / MP4 of a clip on an agent (`--view side/front/back/three/top/near`, `--mirror`). `CS2_AGENT_DIR` = where agent names are looked up. |
| `analyze.mjs <take.bvh>` | Finds punches and kicks in a CMU take (time, take frame, limb, reach, height). |
| `gallery.mjs out.png punch\|kick\|all <take.bvh>... --agent a.json` | Strips of those strikes on an agent, to choose a mocap moment. |
| `test_smoke.mjs [out dir]` | Self-contained test: synthetic skeleton (agent bone names, made-up sizes) and BVH → retarget, posture/IK, mocap blend, finish, mirror, validator, SMD round trip, rig vmdl, preview, VPK reader. `CS2_SKELETON=cs2_skeleton.json node test_smoke.mjs` runs it on the real skeleton. |

Kept in Puppet Brawl (game-specific, use them as examples): the stances, move and state lists, falls, the baking of hit/hurt boxes from the
same animation (`bake.mjs`: 16 joints projected to the fight plane, 64 Hz, embedded in the script), and its review sheets with hit circles.
