# WW1 rifle builder (CS2) — AI-agent generated (Claude)

FBX -> CS2 weapon vmdl rigged to a stock weapon skeleton (ssg08 / awp), reusing the stock animations.

Needs: python3 + numpy + Pillow. Stock files: Source 2 Viewer "Decompile & Export" of
weapons/models/<w>/weapon_snip_<w>.vmdl_c (+ _mag.vmdl) into the `stock` folder.

    python build_weapon.py lee.json
    python build_weapon.py gewehr.json
    python -c "from material import make_material; ..."   # see material.py

Config keys: shift_wo = offset added to mesh coords to land in weapon_offset bone space;
bore_wo = (y,z) of the bolt/bore axis in that space; part_bone = FBX part -> bone;
rules = box selections (faces or whole components) -> bone, mag:true marks the detachable magazine.
Output goes to the addon content root (models/, materials/). Debug overlays: <name>_debug_side/top.png.
