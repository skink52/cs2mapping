"""Adds a hidden cache prop_dynamic (tw_uniform_N, below the lobby) for every soldier player model in <addon>/models/tw/players so
the script can SetModel to it, straight onto the user's latest vmap (nothing else changes). Re-running only adds missing ones.
Usage: patch_uniforms.py <user vmap> <out vmap> <addon>"""
import os, sys
import dmx, vmaplib
from vmaplib import ent

SRC, OUTPATH, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
GROUP = 'tw_gen'
d = dmx.DMX.load(SRC); root = d.root; world = root.get('world')
vmaplib.init(d, OUT)
kids = [a for a in world.attrs if a[0] == 'children'][0]
have, used = set(), set()
for c in kids[2]:
    if c.type == 'CMapEntity':
        ep = c.get('entity_properties'); nm = ep.get('targetname') or ''
        if nm.startswith('tw_uniform_'): have.add(ep.get('model')); used.add(nm)
pdir = os.path.join(OUT, 'models/tw/players')
models = sorted('models/tw/players/%s/%s.vmdl' % (n, n) for n in os.listdir(pdir)
                if os.path.isfile(os.path.join(pdir, n, n + '.vmdl')))
added = []
k = 1
for m in models:
    if m in have: continue
    while 'tw_uniform_%d' % k in used: k += 1
    used.add('tw_uniform_%d' % k)
    ent('prop_dynamic', (-800 + 160 * k, 640, -3600), (0, 0, 0), group=GROUP, targetname='tw_uniform_%d' % k, model=m, solid='0',
        rendercolor='255 255 255', skin='default', DefaultAnim='', disableshadows='1', fademindist='-1', fademaxdist='0', StartDisabled='0',
        HoldAnimation='0', RandomAnimation='0')
    added.append(m)
kids[2] = kids[2] + vmaplib.new_children
counts = {}
for c in kids[2]:
    if c.type == 'CMapEntity':
        cls = c.get('entity_properties').get('classname'); counts[cls] = counts.get(cls, 0) + 1
pre = {a[0]: a for a in d.prefix[0]}
ar = pre['map_asset_references'][2]
for m in added:
    if m not in ar: ar.append(m)
names = sorted(counts)
if 'map_subasset_reference_types' in pre:
    pre['map_subasset_reference_types'][2] = ['entity'] * len(names)
    pre['map_subasset_reference_names'][2] = names
    pre['map_subasset_reference_counts'][2] = [counts[n] for n in names]
d.elements = [root]
d.save(OUTPATH)
print('uniform cache props added:', added or 'none')
