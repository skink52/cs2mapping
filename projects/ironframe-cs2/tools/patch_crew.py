"""Adds the hangar crew (tools/hangar_crew.py: posed pilots, workers, technicians as static props) around the garage bays of
a map, and nothing else. Additive and re-runnable like tools/patch_cache.py: the props live in their own vis group
(ifr_crew_patch), which a re-run replaces.

    python -I tools/patch_crew.py <the map as last saved in Hammer .vmap> <out .vmap> [addon out dir = out/addon]

Close Hammer, back up the map, run, then copy the output over the map. Per bay (info_target ifr_bay_N: origin = the mech's
feet; the open side is the script's camera side, 00_config.js BAY_CAMERA_YAW, else the entity's yaw) three people stand on a ring just outside the turning mech (RING u from the centre): one ahead
to the left, one ahead to the right, one at a foot behind; who stands where changes from bay to bay (seeded by N), so
twelve bays are not twelve copies. prop_static, solid 0 (nobody walks there: the garage is a camera), not lightmapped.
Sprawl gets them with the hangar itself (tools/arenas/import_region.py copies the region from Dunes' saved map).
What was placed is printed; look at one bay in the game before trusting the ring radius against the bay's own furniture.
"""
import os, sys, json, math, random
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
CREATE = os.path.normpath(os.path.join(HERE, '..', '..', '..', 'create'))
sys.path.insert(0, CREATE); sys.path.insert(0, HERE)
import vmapgen as G

GROUP = 'ifr_crew_patch'
RING = 215.0
# (angle from the bay's open side, radius factor, who may stand there, facing: 'in' = at the mech, 'out' = away from it, +- jitter)
SPOTS = [
    (48.0, 1.0, ('worker_marshal', 'pilot_look', 'tech_ease'), 'in', 12),
    (-52.0, 1.05, ('pilot_ease', 'tech_slate', 'pilot_look'), 'out', 40),
    (150.0, 0.8, ('worker_kneel', 'tech_slate', 'worker_kneel'), 'in', 10),
]


def vec(v):
    try: return [float(x) for x in v][:3]
    except Exception: return None


def camera_yaws():
    """the script's fixed camera side per bay (src/cs2/00_config.js BAY_CAMERA_YAW): the people in front stand on that side"""
    import re
    t = open(os.path.join(PROJ, 'src', 'cs2', '00_config.js'), encoding='utf-8').read()
    m = re.search(r'BAY_CAMERA_YAW:\s*\{([^}]*)\}', t)
    return {int(k): float(v) for k, v in re.findall(r'(\d+)\s*:\s*(-?[\d.]+)', m.group(1))} if m else {}


def main(src, out, addon='out/addon'):
    crew = json.load(open(os.path.join(addon, '_gen', 'crew.json')))['crew']
    d = G.open_map(src, addon)
    CAM = camera_yaws()
    bays = []
    for c in G.entities(d):
        nm = G.props_of(c).get('targetname', '')
        if not nm.startswith('ifr_bay_'): continue
        o, a = vec(c.get('origin')), vec(c.get('angles')) or [0, 0, 0]
        if o is None: sys.exit('patch_crew: %s has no origin' % nm)
        num = int(nm.rsplit('_', 1)[1])
        bays.append((num, o, CAM.get(num, a[1])))     # the camera's side when the script fixes it, else the mapper's yaw
    if not bays: sys.exit('patch_crew: no ifr_bay_N in %s' % src)
    n = 0
    for num, o, yaw in sorted(bays):
        rnd = random.Random(7700 + num)
        used = set()
        for k, (ang, rf, who, face, jit) in enumerate(SPOTS):
            pick = [w for w in who if w in crew and w not in used] or [w for w in who if w in crew]
            if not pick: continue
            key = pick[(num + k) % len(pick)]; used.add(key)
            a = math.radians(yaw + ang + rnd.uniform(-8, 8)); r = RING * rf * rnd.uniform(0.96, 1.08)
            x, y = o[0] + r * math.cos(a), o[1] + r * math.sin(a)
            to_mech = math.degrees(math.atan2(o[1] - y, o[0] - x))
            fy = (to_mech if face == 'in' else to_mech + 180.0) + rnd.uniform(-jit, jit)
            G.ent('prop_static', (round(x, 1), round(y, 1), o[2]), angles=(0.0, round(fy % 360.0, 1), 0.0), group=GROUP,
                  model=crew[key]['model'], solid='0', bakelighting='0')
            n += 1
    G.finish(d, out, group=GROUP, first_run_cleanup=False)
    print('patch_crew: %d people at %d bays (ring %.0f u) -> %s' % (n, len(bays), RING, out))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 'out/addon')
