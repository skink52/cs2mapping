"""Stage C step / stage D pass `waterprobe`: one light probe volume per water surface.

Each probe volume bakes its own cubemap and probes, so a water surface crossed by several volumes shows every volume edge as a step in
its reflection and fog lighting (piratewars' 3x3 squares, tomgreens' pools). Every func_water whose top is crossed by two or more
env_combined_light_probe_volumes, none of which holds the whole surface, gets a thin volume of its own around the surface (48 u past the
edges, from up to 256 u below the top to 16 u above it) at a priority above every volume it crosses.
Method from github.com/Ninja-Chris/cs2-slop-porting 3.5 (MIT), 2 Nov 2026.
"""
import numpy as np

PAD = 48.0
PROPS = dict(StartDisabled=0, cubemaptexture='', bakenearz='2.0', bakefarz='4096.0', lightgroup='', moveable=0, lightprobetexture='',
             voxel_size='32.0', flood_fill=1, voxelize=1, light_probe_volume_from_cubemap=0, storage=-1, edge_fade_dists='0 0 0', clientSideEntity=1)


def _vec(s):
    try: return np.array([float(x) for x in (s or '0 0 0').split()[:3]])
    except ValueError: return np.zeros(3)


def volumes(m):
    out = []
    for e in m.by_class('env_combined_light_probe_volume'):
        o = np.array(m.origin(e), float)
        try: lvl = int(float(m.P(e, 'indoor_outdoor_level', '0') or 0))
        except ValueError: lvl = 0
        out.append((o + _vec(m.P(e, 'box_mins', '-72 -72 -72')), o + _vec(m.P(e, 'box_maxs', '72 72 72')), lvl))
    return out


def run(m, c):
    vols = volumes(m); n = 0
    for w in m.by_class('func_water'):
        bb = m.bounds(w)
        if not bb: continue
        w0, w1 = np.array(bb[0], float), np.array(bb[1], float); top = w1[2]
        cross = [(a, b, l) for a, b, l in vols if a[2] <= top <= b[2] and a[0] < w1[0] and w0[0] < b[0] and a[1] < w1[1] and w0[1] < b[1]]
        if len(cross) < 2 or any(a[0] <= w0[0] and a[1] <= w0[1] and w1[0] <= b[0] and w1[1] <= b[1] for a, b, l in cross): continue
        mn = np.array([w0[0] - PAD, w0[1] - PAD, top - min(max(w1[2] - w0[2], 16.0), 256.0)])
        mx = np.array([w1[0] + PAD, w1[1] + PAD, top + 16.0])
        o = (mn + mx) / 2
        lvl = max(l for _, _, l in cross) + 1
        m.new_entity('env_combined_light_probe_volume', o.tolist(), dict(PROPS, box_mins='%f %f %f' % tuple(mn - o), box_maxs='%f %f %f' % tuple(mx - o),
                                                                         indoor_outdoor_level=lvl))
        vols.append((mn, mx, lvl)); n += 1
    if n: c.log.append('waterprobe: %d water surfaces crossed by several probe volumes got one volume of their own (priority above the ones they cross)' % n)
    return n
