"""Bot support, applied straight onto the user's latest vmap (no regeneration):
- func_nav_markup WALKABLESEED volumes (closed toolsnavattribute box child) in the lobby, both trench systems, the woods clearings and
  the mine tunnels. Nav generation (-nav) floods out from the seeds; without one in an area that area gets no nav and bots stand still there.
- removes func_bomb_target entities (two stray bomb sites in no man's land turned the map into a defuse scenario for bots and C4).
Re-running replaces the previous seeds (vis group tw_nav).
Usage: patch_bots.py <user vmap> <out vmap>"""
import sys
import numpy as np
import dmx, vmaplib
from vmaplib import ent, polymesh, box_faces
import layout as LY

SRC, OUTPATH = sys.argv[1], sys.argv[2]
GROUP = 'tw_nav'
NAVATTR = 'materials/tools/toolsnavattribute.vmat'
d = dmx.DMX.load(SRC); root = d.root; world = root.get('world')
vmaplib.init(d, '')
kids = [a for a in world.attrs if a[0] == 'children'][0]

kept, named, removed = [], {}, []
for c in kids[2]:
    if c.get('customVisGroup', '') == GROUP: continue
    if c.type == 'CMapEntity':
        ep = c.get('entity_properties'); cls = ep.get('classname')
        if cls == 'func_bomb_target': removed.append(cls); continue
        nm = ep.get('targetname') or ''
        if nm: named[nm] = c.get('origin')
    kept.append(c)


def seed(x, y, z, hw=20.0, h=34.0):
    s = ent('func_nav_markup', (0, 0, 0), group=GROUP, navProperty_NavGen='WALKABLESEED', flags='1')
    v, faces = box_faces(x - hw, y - hw, z, x + hw, y + hw, z + h, inward=False)
    s.attr('children')[2].append(vmaplib.mesh_node(polymesh(v, faces, [NAVATTR] * 6, scale=1.0), GROUP, attach=False))


n = 0
for tg in ('t', 'ct'):                                   # trench systems: fire-trench bays, support trench (teleport = floor + ~14)
    for i in (1, 5, 8, 12, 15, 16, 18, 20):
        o = named.get('trench_%s_%d' % (tg, i))
        if o: seed(o[0], o[1], o[2] - 8); n += 1
for nm in ('info_player_terrorist', 'info_player_counterterrorist'):   # lobby
    for c in kept:
        if c.type == 'CMapEntity' and c.get('entity_properties').get('classname') == nm:
            o = c.get('origin'); seed(o[0], o[1], o[2] - 6, hw=16); n += 1; break
for s in (-1, 1):
    for y in (3700.0, 4150.0):                            # woods clearing
        x = s * 1210.0; seed(x, y, LY.ground_at(x, y) + 4, hw=16); n += 1
    x0, y0, x1, y1 = LY.TUN_LANDING                       # tunnel landing under each sap
    seed(s * (x0 + x1) / 2, (y0 + y1) / 2, LY.TUN_FLOOR + 4, hw=16); n += 1
seed(0.0, -3368.0, LY.TUN_FLOOR + 4, hw=24); n += 1        # mine chamber

kids[2] = kept + vmaplib.new_children
counts = {}
for c in kids[2]:
    if c.type == 'CMapEntity':
        cls = c.get('entity_properties').get('classname'); counts[cls] = counts.get(cls, 0) + 1
pre = {a[0]: a for a in d.prefix[0]}
ar = pre['map_asset_references'][2]
if NAVATTR not in ar: ar.append(NAVATTR)
names = sorted(counts)
if 'map_subasset_reference_types' in pre:
    pre['map_subasset_reference_types'][2] = ['entity'] * len(names)
    pre['map_subasset_reference_names'][2] = names
    pre['map_subasset_reference_counts'][2] = [counts[k] for k in names]
d.elements = [root]
d.save(OUTPATH)
print('patched: %d nav seeds, removed %s' % (n, ', '.join(removed) or 'nothing'))
