"""Build the shareable bump mine kit (zip) from ba_jail_keimusho's working setup.

  python make_kit.py [out_dir]      (default C:\\source1\\share)

Takes the kit's own files from this folder (script, HUD, sound events, installer, docs), the converted CS:GO bump mine model,
materials and sounds from the keimusho content addon (they aren't in git: Valve assets), the .vmap library from tools/, and
builds prefab/bumpmine_prefab.vmap from keimusho's own entities (full Hammer key sets), renamed for the kit.
"""
import json, os, shutil, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
import dmx, vmapedit as V  # noqa: E402

ADDON = r'C:\source1\links\content_addons\ba_jail_keimusho'
OUT = sys.argv[1] if len(sys.argv) > 1 else r'C:\source1\share'
NAME = 'cs2_bumpmine_kit'
KIT = os.path.join(OUT, NAME)

if os.path.isdir(KIT):   # empty it (the folder itself may be some shell's working directory)
    for f in os.listdir(KIT):
        p = os.path.join(KIT, f)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
C = os.path.join(KIT, 'content')
def put(src, rel):
    dst = os.path.join(KIT, rel); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(src, dst)

# --- kit sources
for f, rel in [('README.md', 'README.md'), ('AGENT_SETUP.md', 'AGENT_SETUP.md'), ('install_bumpmine.py', 'install_bumpmine.py'),
               ('bumpmine.js', 'content/maps/scripts/bumpmine.js'),
               ('bumpmine_hud.xml', 'content/panorama/layout/custom_game/bumpmine_hud.xml'),
               ('bumpmine_hud.css', 'content/panorama/styles/custom_game/bumpmine_hud.css'),
               ('soundevents_bumpmine.vsndevts', 'soundevents_bumpmine.vsndevts')]:
    put(os.path.join(HERE, f), rel)
for f in ('dmx.py', 'kv2.py', 'vmapedit.py'):
    put(os.path.join(REPO, 'tools', f), 'lib/' + f)
put(os.path.join(REPO, 'ports', 'ba_jail_keimusho', 'scripts', 'keimusho_bumpmine.js'), 'reference/keimusho_bumpmine.js')

# --- converted CS:GO assets (model source + materials + sounds), exactly what keimusho compiles
assets = ['models/weapons/w_eq_bumpmine_dropped.vmdl']
for d in ('models/weapons/w_eq_bumpmine_dropped_refs', 'materials/models/weapons/v_models/bump_mine', 'sounds/bumpmine'):
    for root, _, files in os.walk(os.path.join(ADDON, d)):
        for f in files:
            assets.append(os.path.relpath(os.path.join(root, f), ADDON).replace('\\', '/'))
for rel in assets:
    if rel.endswith('.bak') or rel.endswith('meshinfo.txt'): continue
    put(os.path.join(ADDON, rel), 'content/' + rel)

# --- prefab from keimusho's entities
src = V.Map(os.path.join(ADDON, 'maps', 'ba_jail_keimusho.vmap'))
pm = V.Map(os.path.join(REPO, 'tools', 'box_template.vmap'))
for ch in list(pm.children(pm.world)): pm.remove_node(ch)
byname = {}
for e in src.entities(): byname.setdefault(src.name(e), e)
layout = [('bumpscript', (0, 0, 64)), ('bumphud', (32, 0, 64)), ('awp spawner', (64, 0, 64))]
layout += [('bumpmine_%d' % i, (0, 0, 0)) for i in range(1, 9)]
layout += [('bumpmine_%d_%s' % (i, k), (0, 0, 16)) for i in range(1, 9) for k in ('land', 'det')]
memo, nid = {}, [pm.next_node_id()]
full = []
for name, pos in layout:
    j = pm.import_subtree(src, byname[name], memo, nid)
    dmx.geta(pm.E[j], b'connectionsData')[2] = []
    dmx.set_(pm.E[j], b'origin', dmx.T_V3, [float(x) for x in pos])
    dmx.set_(pm.E[j], b'angles', dmx.T_QANG, [0.0, 0.0, 0.0])
    dmx.set_(pm.E[j], b'customVisGroup', dmx.T_STR, b'bumpmine')
    cls = pm.cls(j)
    if cls == 'point_script': pm.setp(j, 'cs_script', 'maps/scripts/bumpmine.vjs')
    if cls == 'custom_hud_layout': pm.setp(j, 'layout', 'panorama/layout/custom_game/bumpmine_hud.vxml')
    if cls == 'game_player_equip': pm.setp(j, 'targetname', 'bumpmine_equip')
    if cls == 'point_soundevent':
        pm.setp(j, 'soundName', {'keimusho.bumpmine.land': 'bumpmine.land', 'keimusho.bumpmine.detonate': 'bumpmine.detonate'}[pm.P(j, 'soundName')])
    dmx.geta(pm.E[pm.world], b'children')[2].append(j)
    keys = {a[0].decode(): a[2].decode('utf-8', 'replace') for a in pm.props(j)['attrs'] if isinstance(a[2], bytes)}
    full.append({'name': pm.name(j), 'cls': cls, 'origin': list(pos), 'keys': keys})
# the template's asset list (and thumbnail) belong to another map: write the prefab's own
if pm.doc.prefix:
    import collections
    cnt = collections.Counter(f['cls'] for f in full)
    types = [b'entity'] * len(cnt) + [b'soundevent', b'soundevent']
    names = [c.encode() for c in sorted(cnt)] + [b'bumpmine.detonate', b'bumpmine.land']
    counts = [cnt[c] for c in sorted(cnt)] + [8, 8]
    new = {b'map_asset_references': [b'maps/scripts/bumpmine.vjs', b'models/weapons/w_eq_bumpmine_dropped.vmdl',
                                     b'panorama/layout/custom_game/bumpmine_hud.vxml'],
           b'map_subasset_reference_types': types, b'map_subasset_reference_names': names, b'map_subasset_reference_counts': counts}
    pm.doc.prefix[0] = [pa for pa in pm.doc.prefix[0] if not pa[0].startswith(b'asset_preview_thumbnail')]
    for pa in pm.doc.prefix[0]:
        if pa[0] in new: pa[2] = new[pa[0]]
pm.prune()
os.makedirs(os.path.join(KIT, 'prefab'), exist_ok=True)
pm.save(os.path.join(KIT, 'prefab', 'bumpmine_prefab.vmap'))
chk = V.Map(os.path.join(KIT, 'prefab', 'bumpmine_prefab.vmap'))
assert len(chk.entities()) == len(layout), (len(chk.entities()), len(layout))
json.dump(full, open(os.path.join(KIT, 'prefab', 'bumpmine_entities.json'), 'w'), indent=1)

# --- zip
z = os.path.join(OUT, NAME + '.zip')
if os.path.exists(z): os.remove(z)
with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for root, _, files in os.walk(KIT):
        for f in sorted(files):
            p = os.path.join(root, f)
            zf.write(p, os.path.join(NAME, os.path.relpath(p, KIT)))
n = sum(len(f) for _, _, f in os.walk(KIT))
print('kit: %s (%d files)\nzip: %s (%d bytes)\nprefab: %d entities' % (KIT, n, z, os.path.getsize(z), len(layout)))
