# GMod hats and accessories in CS2

How a Garry's Mod Workshop hat (a Pointshop / PAC3 / "hat pack" prop) becomes a CS2 hat that a server puts on any player and
that follows the head through every animation. Tools: [`create/hats/`](../../create/hats/README.md). The server side (shop,
rules, wearing) is slime-mg-gm's `Credits/Hats.cs` (its `docs/hats.md`; repo github.com/TypicalAdlib/slime-mg-gm).
The player model converter it borrows from: [gmod-playermodels.md](gmod-playermodels.md).

## How a CS2 server attaches a cosmetic to the head (research, 6 Nov 2026)

- **No head attachment.** The CS2 agent's attachments (template vmdl `AttachmentList`) are `knife`, `grenade0`-`grenade4`, `c4`,
  `primary`, `eholster`, `pistol`, `clip_limit`, `weapon`, `weapon_hand_r`, `weapon_hand_l`, `weapon_center`. Nothing on the head,
  so `SetParent` + `SetParentAttachment` can't put a prop on it. `SetParent` to the pawn alone follows the pawn's origin: no crouch,
  no head turn or lean.
- **Bone merge does it.** A `prop_dynamic` whose model has bones named like the pawn's, `FollowEntity`'d onto the pawn, takes the
  pawn's pose for every bone they share (Source's bone merge, which the `!bonemerge` parent attachment also does in Hammer; Puppet
  Brawl drives agents that way, [cs_script-notes](../reference/cs_script-notes.md)). CounterStrikeSharp:
  ```cs
  var hat = Utilities.CreateEntityByName<CDynamicProp>("prop_dynamic_override");
  hat.SetModel("models/hats/fedora/fedora.vmdl");            // precached at map start (OnServerPrecacheResources)
  hat.Collision.SolidType = SolidType_t.SOLID_NONE;
  hat.DispatchSpawn();
  hat.AcceptInput("FollowEntity", pawn, pawn, "!activator");
  ```
  Checked on the local server (slime-mg-gm `hats` test, 6 Nov): the prop's scene parent is the pawn after `FollowEntity`.
  `DispatchSpawn` puts the model's own collision back (`SOLID_OBB`), so set `SOLID_NONE` (and `FSOLID_NOT_SOLID`) **after** spawning.
  This is what the public cs2-store plugin's "equipment" items do (their hats are models rigged to the agent skeleton). So a hat
  model is the hat mesh **skinned to the agent skeleton with every vertex on `head_0`**, written in the agent's bind pose: wherever
  the animation graph puts `head_0`, the hat goes. It works on any model that has `head_0` with the agent's bind pose: stock
  agents and every GMod conversion (they are skinned to the same skeleton).
- **Player models whose head isn't the agent's.** The GMod conversions keep their own heads (shorter HL2 necks: a median 3.6 u
  lower, up to ~4 u forward or back; `head_hitbox_shift` in their reports), still skinned to `head_0`. A bone-merged hat can't be
  offset at run time, so each hat carries **12 shifted copies** as the choices of one bodygroup `fit` (0, -1.5, -3, -4.5 u down x
  0, -2, +2 u back/forward), and the server sets `SetBodygroup "fit,<k>"` per player model (the choice nearest that model's head
  shift).
- **First person.** CS2 draws the local player's own body (legs, arms), and whether it hides the head bone-merged props for
  the wearer isn't known without a client. The server hides the hat from its wearer itself: CounterStrikeSharp's
  `Listeners.CheckTransmit` removes the hat entity from the wearer's transmit list, and from spectators watching the wearer in
  first person (`ObserverServices.ObserverMode == OBS_MODE_IN_EYE`, target = the wearer). Third person (`thirdperson`, death cams)
  then shows no hat for the wearer: acceptable. **Still to check with a client:** the hat really invisible in first person, and its
  shadow.
- **Lifetime.** Removed on death (a bone-merged prop stays on the dead pawn, not the ragdoll: it would float where the pawn was),
  team change, disconnect and map end; made again on spawn. After a `SetModel` (shop player model, deathrun trapper) the follow is
  done again so the merge binds the new skeleton, and the fit choice follows the new model.
- Not tried: hats on the ragdoll (would need the ragdoll entity; CS2's death ragdoll is client-side).

## Workflow

```
browse.py (candidates) -> catalog items -> fetch.py --scan (SteamCMD, extract, every .mdl + Pointshop lua) -> suggest.py (hats
from the scan) -> hat2cs2.py (place, write, preview) -> review sheets -> catalog overrides / chosen false -> hat2cs2.py --compile
```

1. **Find packs**: `browse.py catalog.json` searches the Workshop (hat, pointshop hats, accessories, masks, glasses, ...; top rated
   and most subscribed). Packs worth having: Pointshop hat packs (they carry placement data), the GMod Tower accessories pack (88
   models), Splatoon gear, PAYDAY masks.
2. **Scan**: `fetch.py catalog.json --scan` downloads (SteamCMD anonymous), extracts and lists every model with its bones,
   vertices, size, missing materials and the Pointshop item that places it.
3. **Pick**: `suggest.py catalog.json --batch N` adds one copy of each head-worn prop (packs share models; the copy with Pointshop
   data wins), skipping player models, arms, weapons, tails, wings, jetpacks.
4. **Convert**: `hat2cs2.py catalog.json [--only a,b] [--sheet] [--compile]`.
5. **Review** (6 Nov: skink52 marked every hat on a review page, 4 rounds, OK / off with moves in game units / drop; 102 of 193 kept)
   `<work>/preview/sheet_<n>.jpg` (a stock agent three-quarter and side, Gordon from the conversions) and each
   `<id>.png` (agent three views, Gordon, a female citizen). Fix with catalog keys, drop with `chosen: false`.

6. **Hand over**: `listhats.py` rebuilds [HATS.md](../../create/hats/HATS.md) (a picture of each hat), `pack.py --prune` zips the
   collection for the server manager, who picks hats for the server (slime-mg-gm `docs/hats.md#adding-hats`). Hats stay local, like
   the player models: only the ones a server nominates are uploaded.

## How a hat is placed

All in the stock agent's bind pose (CS2 faces +x, z up). The reference head is **tm_leet_variantf** (Elite Crew, bare head;
`s2/agent_mesh.mjs` extracts it from CS2's VPK into `<work>/agents/`): eye centre (2.19, 0, 72.82) from the eyeball joints, head
top 78.0, width 7.8 above the eyes, face front at eye height from its mesh. (The player model template's body is a Power Ranger
helmet, so it isn't used for heads.)

1. **Pointshop lua** (`luahats.py`): `ITEM.Attachment` (usually `eyes`) or `ITEM.Bone`, and `ITEM:ModifyClientsideModel` replayed in
   order: `pos = pos + ang:Forward()/Right()/Up() * n` (also through `local MPos = Vector(..)` locals, as PS1's editor writes them),
   `ang:RotateAroundAxis(ang:Axis(), deg)`, `SetModelScale(n)` / `Matrix():Scale(Vector)`. Comments are skipped (several packs
   comment out the GMod Tower originals' lines). The attachment is taken from an HL2 citizen player model (`<work>/ref/male_09.mdl`:
   eyes attachment at (0, -3.6, 67.7), facing -y), and the citizen's head is mapped onto the agent's: eye centre onto eye centre,
   turned +90° about z (GMod models face -y), scaled 1.04 (eye-to-top height and head width averaged). Any catalog item's lua for
   the same model path counts (a model shipped in four packs gets the first placement found).
2. **Facing.** Worn things are mirror-symmetric left to right, so the horizontal axis a model mirrors across is its left-right axis
   (`facing()`: mean nearest-neighbour distance to its mirror image). Left-right on x means it faces +-y: GMod models for players
   face -y (turned +90°); glasses face the end most of their vertices are at (the lenses, not the thin temples). Left-right on y:
   faces +x (Source's own convention). A lua placement with no yaw of its own also gets this turn: the GMod Tower glasses
   (aviators, Kleiner's) came out sideways otherwise, in GMod too presumably.
3. **Autofit** (no lua) by kind, from the file name (`KINDS`): **hat**: the crown's opening (25th percentile of the bottom 35 %'s
   distance from the crown axis, so a brim doesn't count) sized to the head radius x 1.12, its bottom `HAT_SEAT` 0.8 u above the eyes (1.8 left caps floating), centred
   on the head; **glasses**: width 0.92 x the head's, lens front 0.9 u in front of the face at eye height; **mask**: flat ones 1.15 x
   head width, front 1.4 u before the face; deep ones (helmets, bags, heads) 1.3 x, centred on the head; **headphones**: the gap
   between the cups a little over the head's width, the band on the top of the head; **face** (moustaches): under the nose.
4. **Catalog overrides** (CS2 head space, x forward, y left, z up): `offset` [x, y, z] u, `rotate` [pitch, yaw, roll] degrees and
   `scale` about the hat's centre; `pre_rotate` [rx, ry, rz] turns the source model before placing; `kind` overrides the file-name
   kind; `autofit: true` ignores the lua; `skin`, `bodygroups`, `depends` as for player models.

## The output

`<out>` = content addon `gmod_hats`: `models/hats/<id>/<id>.vmdl` + `<id>_fit0..11.dmx` (the template's body DMX, so the joint
list and bind pose are the agent's; weights all `head_0`), `materials/models/hats/<id>/` (vmat + png, through
`gmod2cs2.write_material`: VMT handling, `$blendtintbybasealpha` PlayerColor tint baked in, additive materials left out, green
flipped on normal maps). The vmdl: `BoneMarkupList` with `bone_cull_type "None"`, one `RenderMeshFile` per fit, a `BodyGroup`
`fit` with a choice per mesh. No animgraph: the pawn drives it.

## Rights

Workshop authors keep their rights, and many hats are rips from games (PAYDAY 2 masks, Splatoon gear, Nintendo hats in the GMod
Tower pack). Converted hats are for **private/local testing** until the author agrees; the catalog records each item's id, title
and author. Same rule as [gmod-playermodels.md](gmod-playermodels.md#rights).

## Notes

- The SH Accessories Content pack (881305303) ships only materials (its models are elsewhere); "100 Glasses" (2188556382) didn't
  download (no files). PointShop (635501783) is lua only.
- Splatoon gear is modelled for Inklings (20-30 u): autofit scales it down by the crown opening; the hairclips are tiny side clips.
- A hat needs `head_0` in the player model. Every stock agent and every GMod conversion has it; a custom model built on another
  skeleton would get the hat at its origin.
