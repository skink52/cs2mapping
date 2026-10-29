"""Move a CS:GO 3D skybox (now ordinary geometry in the imported map, since CS2 ignores sky_camera) into its own skybox map.

  python3 skysplit.py <map.vmap in> <main.vmap out> <skybox.vmap out> <map name> [x0,y0,z0,x1,y1,z1]

Without a box, the skybox is the connected group of meshes around the sky_camera (bounds within 16 u of each other).
Every top-level node whose bounds (an entity's origin when it has no mesh) lie inside the box goes to the skybox map; everything
else stays. The skybox map keeps copies of light_environment, env_sky and env_fog_controller, keeps the sky_camera (Editor only
off, scale 16) and gets mapUsageType skybox. The main map loses the sky_camera and gets a skybox_reference at the origin
(targetMapName maps/<map>_3dskybox.vmap, fixupNames 1, worldGroupID skyboxWorldGroup0). Build the skybox map as its own
queue line (`<addon> <map>_3dskybox`)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx, vmapedit as V

KEEP_BOTH = {'light_environment', 'env_sky', 'env_fog_controller'}


def node_box(m, n):
    b = m.bounds(n)
    if b: return b
    o = m.origin(n)
    return o, o


def auto_box(m, cam):
    tops = [(n, node_box(m, n)) for n in m.children(m.world) if m.type(n) != b'CMapEntity' or m.bounds(n)]
    lo = [min(cam[k], cam[k]) - 64 for k in range(3)]; hi = [cam[k] + 64 for k in range(3)]
    grow = True
    while grow:
        grow = False
        for n, (a, b) in tops:
            if all(a[k] <= hi[k] + 16 and b[k] >= lo[k] - 16 for k in range(3)) and not all(a[k] >= lo[k] and b[k] <= hi[k] for k in range(3)):
                lo = [min(lo[k], a[k]) for k in range(3)]; hi = [max(hi[k], b[k]) for k in range(3)]; grow = True
    return lo, hi


def split(src, main_out, sky_out, name, box=None):
    main = V.Map(src); sky = V.Map(src)
    cams = main.by_class('sky_camera')
    if not cams: raise SystemExit('no sky_camera in %s' % src)
    if box is None: box = auto_box(main, main.origin(cams[0]))
    lo, hi = box

    def inside(m, n):
        a, b = node_box(m, n)
        return all(a[k] >= lo[k] - 1 and b[k] <= hi[k] + 1 for k in range(3))

    moved = kept = 0
    for n in list(main.children(main.world)):
        c = main.cls(n) if main.type(n) == b'CMapEntity' else ''
        if c == 'sky_camera': main.remove_node(n)
        elif c not in KEEP_BOTH and inside(main, n): main.remove_node(n); moved += 1
    for n in list(sky.children(sky.world)):
        c = sky.cls(n) if sky.type(n) == b'CMapEntity' else ''
        if c == 'sky_camera':
            dmx.set_(sky.E[n], b'editorOnly', dmx.T_BOOL, False); sky.setp(n, 'scale', sky.P(n, 'scale', '16') or '16')
        elif c in KEEP_BOTH or inside(sky, n): kept += 1
        else: sky.remove_node(n)
    w = sky.E[sky.world]
    if dmx.get(w, b'mapUsageType') is not None: dmx.set_(w, b'mapUsageType', dmx.T_STR, b'skybox')
    else: w['attrs'].append([b'mapUsageType', dmx.T_STR, b'skybox'])
    main.new_entity('skybox_reference', (0, 0, 0), {'targetname': 'skybox', 'targetMapName': 'maps/%s_3dskybox.vmap' % name,
                                                   'fixupNames': '1', 'worldGroupID': 'skyboxWorldGroup0'})
    main.prune(); sky.prune()
    main.save(main_out); sky.save(sky_out)
    return 'skybox split: %d top-level nodes moved to %s_3dskybox.vmap (box %s .. %s), skybox_reference added, sky_camera moved' % (
        moved, name, ' '.join('%g' % x for x in lo), ' '.join('%g' % x for x in hi))


if __name__ == '__main__':
    a = sys.argv[1:]
    bx = None
    if len(a) > 4:
        v = [float(x) for x in a[4].split(',')]; bx = (v[:3], v[3:])
    print(split(a[0], a[1], a[2], a[3], bx))
