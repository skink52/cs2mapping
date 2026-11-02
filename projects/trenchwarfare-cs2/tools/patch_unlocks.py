"""Makes the blockers of the areas that open during a round scriptable, straight on the user's vmap: every prop_static in a vis group
named like an unlock (woodsopen, undergroundopen) becomes a prop_dynamic with that targetname (same model, place, angles, solid).
Usage: patch_unlocks.py <user vmap> <out vmap> <addon>"""
import sys
import dmx, vmaplib
from vmaplib import ent

SRC, OUTPATH, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
NAMES = ('woodsopen', 'undergroundopen')
d = dmx.DMX.load(SRC); root = d.root; world = root.get('world')
vmaplib.init(d, OUT)
done = []


def walk(node):
    kids = [a for a in node.attrs if a[0] == 'children']
    if not kids: return
    lst = kids[0][2]
    for i, c in enumerate(list(lst)):
        if c is None: continue
        if c.type == 'CMapEntity':
            ep = c.get('entity_properties'); grp = c.get('customVisGroup') or ''
            if ep.get('classname') == 'prop_static' and grp in NAMES:
                vmaplib.new_children.clear()
                ent('prop_dynamic', c.get('origin'), c.get('angles'), group=grp, targetname=grp, model=ep.get('model'),
                    solid=ep.get('solid') or '6', rendercolor=ep.get('rendercolor') or '255 255 255', skin='default', DefaultAnim='',
                    disableshadows='0', fademindist='-1', fademaxdist='0', StartDisabled='0', HoldAnimation='0', RandomAnimation='0')
                n = vmaplib.new_children[0]
                for a in n.attrs:
                    if a[0] == 'scales': a[2] = c.get('scales')
                lst[i] = n; done.append((grp, tuple(round(v) for v in c.get('origin'))))
        elif c.type in ('CMapGroup', 'CMapPrefab'):
            walk(c)


walk(world)
counts = {}
def count(node):
    for a in node.attrs:
        if a[0] != 'children': continue
        for c in a[2]:
            if c is None: continue
            if c.type == 'CMapEntity':
                cls = c.get('entity_properties').get('classname'); counts[cls] = counts.get(cls, 0) + 1
            elif c.type in ('CMapGroup', 'CMapPrefab'): count(c)
count(world)
pre = {a[0]: a for a in d.prefix[0]}
names = sorted(counts)
if 'map_subasset_reference_types' in pre:
    pre['map_subasset_reference_types'][2] = ['entity'] * len(names)
    pre['map_subasset_reference_names'][2] = names
    pre['map_subasset_reference_counts'][2] = [counts[n] for n in names]
d.elements = [root]
d.save(OUTPATH)
print('prop_static -> prop_dynamic:', done or 'none')
