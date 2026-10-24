"""Importer-sanitised material refs (spaces -> underscores) -> the addon's real file names.  matnames.py <addon> <root>"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmapedit as V, assets
A, R = sys.argv[1], sys.argv[2]
p = os.path.join(R, 'content', A, 'maps', A + '.vmap'); m = V.Map(p)
fs = json.load(open(os.path.join(R, 'content_files_%s.json' % A)))
have = set(f.lower() for f in fs); byu = {f.lower().replace(' ', '_'): f for f in fs if f.lower().endswith('.vmat')}
n = 0
for mat in sorted(set(assets.mesh_materials(m))):
    if mat.lower() in have: continue
    alt = byu.get(mat.lower())
    if alt and alt.lower() != mat.lower(): assets.replace_material(m, mat, alt); n += 1; print(mat, '->', alt)
if n: open(p, 'wb').write(m.dumps())
print('renamed', n)
