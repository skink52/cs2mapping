"""Light probe coverage for static brush entities.

func_breakable and func_brush meshes that don't move (not parented to a door, mover, train, rotator, physics object...) are lit
from env_combined_light_probe_volume, not lightmaps. Any part of their mesh outside a probe volume is lit wrongly.

run(m, c, fix=False): reports every such entity whose mesh bounds aren't fully inside one probe volume (stage C step `probes`).
With fix=True (stage D pass `probecover`) it adds a probe volume around each group of uncovered entities instead.
"""
import vmapedit as V

STATIC = ('func_breakable', 'func_brush')
MOVERS = ('func_door', 'func_door_rotating', 'func_movelinear', 'func_rotating', 'func_tracktrain', 'func_train', 'func_physbox',
          'func_physbox_multiplayer', 'prop_dynamic', 'prop_physics', 'prop_physics_multiplayer', 'prop_physics_override', 'func_rot_button',
          'momentary_rot_button', 'func_button', 'func_pendulum', 'phys_hinge', 'phys_ballsocket', 'func_conveyor', 'func_platrot', 'func_plat')
PAD = 16.0

def _vec(s):
    try: return [float(x) for x in str(s).split()[:3]]
    except ValueError: return None

def probe_boxes(m):
    out = []
    for e in m.by_class('env_combined_light_probe_volume'):
        o = m.origin(e); a = _vec(m.P(e, 'box_mins', '')); b = _vec(m.P(e, 'box_maxs', ''))
        if a and b: out.append(([o[k] + a[k] for k in range(3)], [o[k] + b[k] for k in range(3)]))
    return out

def run(m, c, fix=False):
    names = {}
    for e in m.entities():
        if m.name(e): names.setdefault(m.name(e).lower(), []).append(e)
    boxes = probe_boxes(m); bad = []
    for e in m.by_class(*STATIC):
        par = m.P(e, 'parentname', '').split(',')[0].strip().lower()
        if par and any(m.cls(p) in MOVERS or m.cls(p).startswith('func_door') for p in names.get(par, [])): continue
        b = m.bounds(e)
        if not b: continue
        mn, mx = b
        if not any(all(lo[k] <= mn[k] + 1 and mx[k] - 1 <= hi[k] for k in range(3)) for lo, hi in boxes):
            bad.append((e, mn, mx))
    if not bad:
        if m.by_class(*STATIC): c.log.append('probes: every static func_breakable / func_brush is inside a light probe volume')
        return
    label = lambda e: '%s %s' % (m.cls(e), m.name(e) or '(unnamed)')
    if not fix:
        c.todo.append('%d static func_breakable / func_brush meshes are not fully inside an env_combined_light_probe_volume, so their lighting will be wrong '
                      '(stage_d.py ... probecover adds volumes): %s' % (len(bad), ', '.join(label(e) for e, _, _ in bad)[:700]))
        return
    groups = []                                  # merge entities whose padded boxes touch, so one volume covers a cluster
    for e, mn, mx in bad:
        lo = [x - PAD for x in mn]; hi = [x + PAD for x in mx]
        for g in groups:
            if all(lo[k] <= g[1][k] and hi[k] >= g[0][k] for k in range(3)):
                g[0] = [min(g[0][k], lo[k]) for k in range(3)]; g[1] = [max(g[1][k], hi[k]) for k in range(3)]; g[2].append(e); break
        else: groups.append([lo, hi, [e]])
    for lo, hi, ents in groups:
        o = [(lo[k] + hi[k]) / 2 for k in range(3)]
        span = max(hi[k] - lo[k] for k in range(3))
        props = dict(StartDisabled=0, cubemaptexture='', bakenearz='2.0', bakefarz='4096.0', lightgroup='', moveable=0, lightprobetexture='',
                     box_mins='%f %f %f' % tuple(lo[k] - o[k] for k in range(3)), box_maxs='%f %f %f' % tuple(hi[k] - o[k] for k in range(3)),
                     voxel_size='%.1f' % (32.0 if span < 1024 else 48.0), flood_fill=1, voxelize=1, light_probe_volume_from_cubemap=0, storage=-1,
                     indoor_outdoor_level=0, edge_fade_dists='0 32 0', clientSideEntity=1)
        m.new_entity('env_combined_light_probe_volume', o, props)
    c.log.append('probecover: added %d light probe volumes around %d static func_breakable / func_brush meshes that no volume fully covered: %s'
                 % (len(groups), len(bad), ', '.join(label(e) for e, _, _ in bad)[:700]))
    c.todo.append('probecover: check the new probe volumes look right next to the existing ones')
