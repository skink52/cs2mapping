# Tripo3D prompts (studio.tripo3d.ai)

Limits: prompt ≤ 1024 chars, negative ≤ 255. Export **GLB** (quad mode forces FBX). CT = British WWI, T = German WWII (user's choice;
the map's T weapons are WWI — for a WWI German swap the helmet/tunic/boots for M1916 Stahlhelm, M1915 Bluse, 1909 leather belt + 3-cell
rifle pouches, ankle boots, and drop "WWII/Wehrmacht/1943").

## Player models
Settings: PBR on, Smart Low Poly, 15,000 tris (or 8,000 quads), then humanoid Auto Rig. Part segmentation can split the head for face swaps.
Long coats are avoided (a coat skirt between the legs breaks rigging).
Note: tw16/17 removed SetModel agents because the local body drew in first person — build these on a decompiled stock agent vmdl
(cs2mapping docs/creation/models.md, "CS:GO player models rebuilt as CS2 agents") so first-person arms/body hiding come from the template.

### CT – British 1916
```
Full-body realistic game character, WWI British Army infantry private, 1916 Western Front trench soldier, adult male, realistic human proportions, neutral calm face, clean-shaven. Strict symmetrical A-pose: standing straight, feet shoulder-width apart flat on ground, arms straight and angled 45 degrees down from shoulders, palms facing down, fingers straight and slightly spread, thumbs apart, arms not touching torso, head facing forward. Brodie Mk I steel helmet, wide flat brim, khaki hessian cover, leather chinstrap. Khaki wool 1902 Pattern service dress tunic, four flapped pockets, brass buttons. Khaki wool trousers, khaki puttees wrapped ankle to knee, brown leather hobnailed ammunition boots. 1908 Pattern khaki cotton webbing: waist belt, crossed shoulder braces, five-cell ammunition pouches on each side of chest, water bottle on right hip, haversack and entrenching tool on left hip, gas respirator bag slung at left side. Worn faded fabric, dried mud on boots and puttees. Empty hands, no weapon.
```

### CT – British 1918 winter (alt)
```
Full-body realistic game character, WWI British Army infantry corporal, 1918 Western Front winter trench soldier, weathered adult male, realistic human proportions, thick moustache, light stubble, tired neutral face. Strict symmetrical A-pose: standing straight, feet shoulder-width apart flat on ground, arms straight and angled 45 degrees down from shoulders, palms facing down, fingers straight and slightly spread, thumbs apart, arms not touching torso, head facing forward. Brodie Mk I steel helmet, wide flat brim, rough sandbag hessian cover with frayed edges, leather chinstrap. Sleeveless brown leather jerkin buttoned over khaki wool service dress tunic. Khaki wool trousers, khaki puttees ankle to knee, brown hobnailed ammunition boots. Khaki 1908 Pattern webbing belt with ammunition pouches, brown leather 1903 bandolier across left shoulder, small box respirator haversack worn high on chest, water bottle on right hip. Heavy mud on lower legs, stained worn cloth. Empty hands, no weapon.
```

### T – German 1943
```
Full-body realistic game character, WWII German Wehrmacht Heer infantry soldier, 1943 trench soldier, adult male, realistic human proportions, neutral calm face, clean-shaven. Strict symmetrical A-pose: standing straight, feet shoulder-width apart flat on ground, arms straight and angled 45 degrees down from shoulders, palms facing down, fingers straight and slightly spread, thumbs apart, arms not touching torso, head facing forward. M40 Stahlhelm steel helmet, matte field-grey, flared skirt, leather chinstrap. Field-grey wool M40 Feldbluse tunic, four pleated patch pockets with scalloped flaps, plain collar, grey buttons. Field-grey trousers tucked into black jackboots. Black leather Y-straps, belt with plain buckle, two triple-cell black ammunition pouches on front belt, bread bag and felt-covered canteen at right rear hip, entrenching tool and bayonet scabbard on left hip, fluted cylindrical gas mask canister on lower back. Worn wool, muddy boots. Empty hands, no weapon, no insignia or emblems.
```

### T – German 1944 veteran (alt)
```
Full-body realistic game character, WWII German Wehrmacht Heer infantry soldier, 1944 veteran trench soldier, weathered adult male, realistic human proportions, light stubble, gaunt neutral face. Strict symmetrical A-pose: standing straight, feet shoulder-width apart flat on ground, arms straight and angled 45 degrees down from shoulders, palms facing down, fingers straight and slightly spread, thumbs apart, arms not touching torso, head facing forward. M42 Stahlhelm steel helmet, rough matte field-grey, straight-cut rim, leather chinstrap. Field-grey wool M43 Feldbluse tunic, straight-flap pockets, plain collar. Field-grey M43 trousers, short brown leather ankle boots with field-grey canvas gaiters. Black leather Y-straps and belt, two triple-cell ammunition pouches, bread bag and canteen at right hip, folding entrenching tool in leather carrier on left hip, rolled tent quarter, fluted gas mask canister on lower back. Faded worn wool, dried mud on boots. Empty hands, no weapon, no insignia or emblems.
```

### Negative (player models)
```
weapon, rifle, gun, props in hands, T-pose, crossed arms, arms touching body, fused fingers, merged limbs, extra limbs, asymmetric pose, pedestal, base, cartoon, chibi, stylized, low detail, swastika, eagle emblem, camouflage, blurry texture
```

## First-person arms
Settings: PBR on, Smart Low Poly, 8,000 tris, **no Auto Rig** — the mesh is split at the cuff into gloves_arms + sleeves and skinned to the
stock agent's first-person arm bones. v1 (27 Oct) came out forearm + hand only (sleeve ~2.5 hand lengths, baggy cuffs, 2M tris unreduced):
v2 below asks for the full arm with proportions spelled out. Tripo stands the result upright (hands down) whatever the prompt says.

### CT – British (v2)
```
Realistic game asset: two complete detached human arms of a WWI British infantry soldier, 1916, like mannequin arms removed at the shoulder joint. Each arm is FULL LENGTH, about 75 cm: rounded shoulder cap, upper arm, elbow, forearm, wrist, hand. Arm length is 8 times hand length; the sleeve from shoulder to wrist is 6 times hand length. Both arms hang straight down side by side, parallel, vertical, 15 cm apart, elbows straight, palms facing inward, fingers straight and slightly spread, thumbs apart. Fitted, slim sleeves of khaki wool serge service dress tunic following the arm shape, not baggy, plain cuff at the wrist, slight folds at the elbow, shoulder seam at the top. Bare adult male hands, realistic anatomy, defined knuckles, short nails, weathered tanned skin, dirt and dried mud on fingers and cuffs. Clean separation between cuff and skin. No torso, no head, no gloves, no weapon, no jewellery.
```

### T – German (v2)
```
Realistic game asset: two complete detached human arms of a WWII German Wehrmacht infantry soldier, 1943, like mannequin arms removed at the shoulder joint. Each arm is FULL LENGTH, about 75 cm: rounded shoulder cap, upper arm, elbow, forearm, wrist, hand. Arm length is 8 times hand length; the sleeve from shoulder to wrist is 6 times hand length. Both arms hang straight down side by side, parallel, vertical, 15 cm apart, elbows straight, palms facing inward, fingers straight and slightly spread, thumbs apart. Fitted, slim sleeves of field-grey wool M40 Feldbluse tunic following the arm shape, not baggy, plain cuff with one small grey button at the wrist, slight folds at the elbow, shoulder seam at the top. Bare adult male hands, realistic anatomy, defined knuckles, short nails, pale weathered skin, dirt and dried mud on fingers and cuffs. Clean separation between cuff and skin. No torso, no head, no gloves, no weapon, no insignia.
```

### Negative (arms v2)
```
short arms, forearm only, cut off at elbow, baggy sleeves, wide cuffs, torso, head, gloves, weapon, fused fingers, extra fingers, missing fingers, fist, merged arms, arms touching, asymmetric, cartoon, stylized, low detail, base, rings, watch
```
