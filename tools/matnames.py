"""Importer-sanitised material refs (spaces -> underscores) -> the addon's real file names.  matnames.py <addon> <root>

Edits <root>/content/<addon>/maps/<addon>.vmap in place (on the PC that is the real addon, through the junction). When something is
renamed the map is first saved with mapbackup (kind before-matnames; undo: mapbackup.py restore <addon>), then written through a temp
file. Nothing is written when nothing is renamed. MATNAMES_NO_BACKUP=1 skips the backup (a staged copy in the cloud route)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmapedit as V, assets, safepath
A, R = safepath.addon_name(sys.argv[1]), sys.argv[2]
p = os.path.join(R, 'content', A, 'maps', A + '.vmap'); m = V.Map(p)
fs = json.load(open(os.path.join(R, 'content_files_%s.json' % A)))
have = set(f.lower() for f in fs); byu = {f.lower().replace(' ', '_'): f for f in fs if f.lower().endswith('.vmat')}
n = 0
for mat in sorted(set(assets.mesh_materials(m))):
    if mat.lower() in have: continue
    alt = byu.get(mat.lower())
    if alt and alt.lower() != mat.lower(): assets.replace_material(m, mat, alt); n += 1; print(mat, '->', alt)
if n:
    if not os.environ.get('MATNAMES_NO_BACKUP'):
        import mapbackup
        e = mapbackup.Store().save(p, kind='before-matnames')
        print('backup:', e['stamp'] if e else 'unchanged since the newest backup')
    m.save(p)
print('renamed', n)
