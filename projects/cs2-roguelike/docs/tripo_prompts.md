# Tripo3D prompts for Nanite Temple (studio.tripo3d.ai)

The CLI account (`tripo whoami`) shows 0 API credits: Tripo keeps studio credits and API credits apart, so these are written for the studio.
Settings for every prop: **PBR on, Smart Low Poly on**, face limit as given, **quad off** (GLB export; quad forces FBX), no rig.
Drop the GLB into `ref/tripo/<name>.glb`; `python tools/import_glb.py ref/tripo/<name>.glb <name> --length <units> --yaw 90 --glow cyan|magenta`
converts it (create/glb2cs2_multi.py) into `ref/models_src/` (binary, not in git; `tools/build_all.sh` copies it into the addon). `--yaw 90`
turns Tripo's front to CS2's +X; `--glow` builds a self-illum mask from the baked-in glow colour, since Tripo exports no emissive channel.
Then list the vmdl in `tools/vmap.py` TRIPO (the cache room compiles it) and point `ENEMIES` at it with the printed radius/height. Keep edges sharp: ask Tripo for the low poly rather than decimating a 1M-triangle mesh,
and bake normals from the high poly if a second pass is needed (see docs/DESIGN.md, "Tripo without sloppy edges").

## Shrine guardian (floor-3 boss), 8,000 triangles

```
Stylized realistic game enemy, a towering ancient temple guardian construct carved from dark basalt: a broad hunched stone torso on four short
massive legs, two long arms ending in blunt stone fists, a featureless head with one glowing circular eye socket. Deep carved geometric
channels run across the body and glow cyan from within, as if filled with liquid light. Weathered stone with chipped edges, moss in the
cracks, thin gold inlay lines, no cloth, no weapons. Symmetrical neutral stance, feet flat on the ground, arms slightly apart from the body.
Single object, no base, no pedestal, no background. Clean hard-surface edges, PBR materials.
```
Negative: `humanoid face, skin, hair, cloth, cape, weapon, sword, base, pedestal, floor, text, blurry, soft edges, cartoon, chibi, extra limbs`

## Shard drone (swarm enemy), 1,500 triangles

```
Game enemy drone made of a floating cluster of dark basalt shards arranged around a glowing cyan crystal core, like a broken statue head
held together by light. Sharp angular stone fragments with chipped edges and thin gold inlay, cyan emissive seams between the shards, no
wings, no face. Compact, roughly spherical silhouette, symmetrical. Single object, no base, no background, clean hard-surface edges, PBR.
```
Negative: `robot, metal armor, propeller, wings, eyes, face, base, stand, background, blurry, soft edges, cartoon`

## Sentinel (turret), 4,000 triangles

```
Ancient stone turret: a squat basalt plinth with a seated stylized guardian statue fused into it, its chest opened into a carved lens
ringed by magenta glowing glyph channels. Weathered dark stone, chipped edges, thin gold inlay, moss at the base. Symmetrical, facing forward,
single object on a flat square base that is part of the model, no background. Clean hard-surface edges, PBR materials.
```
Negative: `human face detail, cloth, weapon, gun barrel, background, blurry, soft edges, cartoon, extra limbs`

## Generated 3 Nov 2026 (studio, H3.1, PBR, 4K, triangles)

| model | prompt | polycount asked / got | import |
|---|---|---|---|
| nt_guardian (golem) | shrine guardian, as above (bipedal came out, kept) | 8,000 / 7,814 | `--length 110 --yaw 90 --glow cyan` -> 111 tall |
| nt_drone | shard drone, as above | 1,500 / 1,373 | `--length 44 --yaw 90 --glow cyan` |
| nt_sentinel | turret, second try: "framed by one smooth plain ring of magenta light and a few simple straight carved grooves. No runes, no glyphs, no letters, no symbols, no writing, no text anywhere on the model" (the first try ringed the lens with gibberish runes) | 4,000 / 3,778 | `--length 88 --yaw 90 --glow magenta` -> 77 tall |

220 studio credits in all (4 x 55). Lesson: say "no runes, no glyphs, no text" whenever a prompt mentions glyph channels, or Tripo paints nonsense script.
