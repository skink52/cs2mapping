"""Damage for converted lasers: every CS:GO env_laser with damage > 0 that has no trigger_hurt along it gets a trigger_hurt
box (8 units wide) between its end points, named <laser>_hurt (or laserhurt_N when unnamed), same start state as the beam, and
every Enable / Disable / Toggle sent to the beam is also sent to the hurt. Run after stage C (the beams are already func_brushes).

usage: laserhurt.py <vmap in> <csgo vmf> <vmap out>
"""
import os, sys, re
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx, vmapedit as V, vmf as vmfmod, beams

src, vmfp, dst = sys.argv[1:4]
m = V.Map(src)
root = vmfmod.parse(open(vmfp, encoding='utf-8', errors='replace').read())
ents = [n for n in root.ch if n.name == 'entity']
names = {}
for e in ents:
    n = e.get('targetname')
    if n: names.setdefault(n.lower(), e)
def org(e): return [float(x) for x in e.get('origin', '0 0 0').split()]
hurts = []
for h in m.by_class('trigger_hurt'):
    bb = m.bounds(h)
    if bb: hurts.append((np.array(bb[0]) - 8, np.array(bb[1]) + 8))
def hurt_along(a, b):
    for t in np.linspace(0, 1, 9):
        p = np.array(a) * (1 - t) + np.array(b) * t
        if any((p >= lo).all() and (p <= hi).all() for lo, hi in hurts): return True
    return False
tm = V.Map(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'laser_template.vmap')); tnode = tm.children(tm.world)[0]
done = set(); added = []; k = 0
targeted = {}
for e, cc in list(m.all_conns()):
    targeted.setdefault(dmx.get(cc, b'targetName').decode().lower(), []).append((e, cc))
for e in ents:
    if e.get('classname') != 'env_laser' or float(e.get('damage', '0') or 0) <= 0: continue
    t = names.get((e.get('LaserTarget') or '').lower())
    if t is None: continue
    a, b = org(e), org(t)
    key = tuple(sorted([tuple(round(x) for x in a), tuple(round(x) for x in b)]))
    if key in done or hurt_along(a, b): continue
    done.add(key); k += 1
    nm = e.get('targetname', '')
    hname = (nm + '_hurt') if nm else 'laserhurt_%d' % k
    sf = int(e.get('spawnflags', '0') or 0); on = bool(sf & 1) or not nm
    mid = [(x + y) / 2 for x, y in zip(a, b)]
    ent = m.new_entity('trigger_hurt', mid, {'targetname': hname, 'spawnflags': '1', 'StartDisabled': '0' if on else '1',
                       'damage': e.get('damage'), 'damagecap': '20', 'damagetype': '0', 'damagemodel': '0', 'nodmgforce': '0',
                       'forgivedelay': '3', 'thinkalways': '0'})
    j = beams.build_mesh(m, tm, tnode, a, b, 8.0, 'materials/tools/toolstrigger.vmat')
    dmx.geta(m.E[ent], b'children')[2].append(j)
    hurts.append((np.minimum(a, b) - 8, np.maximum(a, b) + 8))
    n_io = 0
    for src_e, cc in targeted.get(nm.lower(), []) if nm else []:
        inp = dmx.get(cc, b'inputName').decode().lower()
        if inp in ('enable', 'disable', 'toggle'):
            m.add_conn(src_e, dmx.get(cc, b'outputName').decode(), hname, inp.capitalize(), dmx.get(cc, b'overrideParam').decode(),
                       dmx.get(cc, b'delay'), dmx.get(cc, b'timesToFire')); n_io += 1
    added.append('%s (damage %s%s%s)' % (hname, e.get('damage'), '' if on else ', starts off', ', %d I/O copied' % n_io if n_io else ''))
open(dst, 'wb').write(m.dumps())
print('added %d trigger_hurt along lasers: %s' % (len(added), '; '.join(added)))
