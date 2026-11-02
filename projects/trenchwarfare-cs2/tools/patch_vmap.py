"""Small changes applied straight onto the user's latest vmap (no regeneration, so nothing the generator places randomly moves):
- removes cs_minimap_boundary (CS2 drew its own top-down minimap from them instead of the radar)
- adds the separate propeller models (tools/split_props.py): tw_prop_<tg> prop_dynamic per flyable plane, a static one per hangar plane
Usage: patch_vmap.py <user vmap> <out vmap> <addon>"""
import os, sys, json, math
import numpy as np
import dmx, vmaplib
from vmaplib import ent

SRC, OUTPATH, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
GROUP = 'tw_gen'
d = dmx.DMX.load(SRC); root = d.root; world = root.get('world')
vmaplib.init(d, OUT)
HUB = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'prop_hubs.json')))
rng = np.random.RandomState(77)
kids = [a for a in world.attrs if a[0] == 'children'][0]
kept, have, planes, statics = [], set(), [], []
for c in kids[2]:
    if c.type == 'CMapEntity':
        ep = c.get('entity_properties'); cls = ep.get('classname'); m = ep.get('model') or ''
        if cls == 'cs_minimap_boundary': continue
        nm = ep.get('targetname') or ''
        if nm.startswith('tw_prop_') or m.endswith('_prop.vmdl'): have.add(nm or tuple(round(v) for v in c.get('origin')))
        if cls == 'prop_dynamic' and nm.startswith('tw_plane_') and not nm.startswith('tw_plane_smoke'):
            planes.append((nm[len('tw_plane_'):], m.split('/')[-2], c.get('origin'), c.get('angles')))
        if cls == 'prop_static' and m.endswith(('plane_dr1.vmdl', 'plane_spad7.vmdl')):
            statics.append((m.split('/')[-2], c.get('origin'), c.get('angles')))
    kept.append(c)


def hub_at(pl, o, yaw):
    hx, hy, hz = HUB[pl]; c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return (o[0] + hx * c - hy * s, o[1] + hx * s + hy * c, o[2] + hz)


refs = set()
for tg, pl, o, an in planes:
    if 'tw_prop_' + tg in have: continue
    mdl = 'models/tw/ext/%s/%s_prop.vmdl' % (pl, pl); refs.add(mdl)
    ent('prop_dynamic', hub_at(pl, o, an[1]), (0, an[1], rng.uniform(0, 180)), group=GROUP, targetname='tw_prop_' + tg, model=mdl, solid='0',
        rendercolor='255 255 255', skin='default', DefaultAnim='', disableshadows='0', fademindist='-1', fademaxdist='0', StartDisabled='0',
        HoldAnimation='0', RandomAnimation='0')
for pl, o, an in statics:
    h = hub_at(pl, o, an[1])
    if tuple(round(v) for v in h) in have: continue
    mdl = 'models/tw/ext/%s/%s_prop.vmdl' % (pl, pl); refs.add(mdl)
    ent('prop_static', h, (0, an[1], rng.uniform(0, 180)), group=GROUP, model=mdl, rendercolor='255 255 255', skin='default', solid='0',
        bakelighting='0', disableshadows='0', lodlevel='-1', baketoworld='0', rendertocubemaps='1')
kids[2] = kept + vmaplib.new_children
counts = {}
for c in kids[2]:
    if c.type == 'CMapEntity':
        cls = c.get('entity_properties').get('classname'); counts[cls] = counts.get(cls, 0) + 1
pre = {a[0]: a for a in d.prefix[0]}
ar = pre['map_asset_references'][2]
for m in sorted(refs):
    if m not in ar: ar.append(m)
names = sorted(counts)
if 'map_subasset_reference_types' in pre:
    pre['map_subasset_reference_types'][2] = ['entity'] * len(names)
    pre['map_subasset_reference_names'][2] = names
    pre['map_subasset_reference_counts'][2] = [counts[n] for n in names]
d.elements = [root]
d.save(OUTPATH)
print('patched: %d planes, %d hangar planes got propellers; removed minimap boundaries; %d new entities' % (len(planes), len(statics), len(vmaplib.new_children)))
