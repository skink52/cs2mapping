# Weapon builder (CS2) — AI-agent generated (Claude)

FBX or GLB model → CS2 weapon vmdl rigged to a stock weapon skeleton (rifles, pistols, optional period scope), reusing the stock animations.

- Method, config keys and lessons: [docs/creation/custom-weapons.md](../../docs/creation/custom-weapons.md).
- Every file here with its usage line: [tools/README.md](../README.md#weapons-the-custom-weapon-builder-creation-not-porting).

    python3 build_weapon.py lee.json          # WW1_STOCK=<folder of decompiled stock weapon vmdl/dmx>
    python3 preview.py lee.json               # left/right/top renders of the built body

Output goes to the config's `out` folder under `sub` (models/…, materials/…), plus `<name>_debug_side/top.png` there.
Required config keys: `name`, `sub`, `out`, `stock`, `shift_wo`, `bore_wo`, and `fbx` or `glb`. Optional: `axes`, `scale`, `stock_prefix`, `part_bone`,
`part_bone_idx`, `part_moves`, `rules`, `boxes`, `mag_parts`, `drop_parts`, `scope`, `flipv`, `flip_green`, `texsize`.
