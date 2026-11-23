"""Move a CS:GO 3D skybox (now ordinary geometry in the imported map, since CS2 ignores sky_camera) into its own skybox map.

  python3 skysplit.py <map.vmap in> <main.vmap out> <skybox.vmap out> <map name> [x0,y0,z0,x1,y1,z1] [--bsp <map.bsp>]

Without a box, the skybox is the connected group of meshes around the sky_camera (bounds within 16 u of each other).
Every top-level node whose bounds (an entity's origin when it has no mesh) lie inside the box goes to the skybox map; everything
else stays. The skybox map keeps copies of light_environment, env_sky and env_fog_controller, keeps the sky_camera (Editor only
off, scale 16) and gets mapUsageType skybox. The main map loses the sky_camera and gets a skybox_reference at the origin
(targetMapName maps/<map>_3dskybox.vmap, fixupNames 1, worldGroupID skyboxWorldGroup0). Build the skybox map as its own
queue line (`<addon> <map>_3dskybox`).

With --bsp the room comes from the compiled CS:GO map instead of a box: vbsp gives every sealed region its own area (area portals split
it further), so the empty BSP leaves of the sky_camera's area, and of the areas its area portals lead to, are the room. A top-level node
whose bounds touch the room's leaves (within 1 u) goes to the skybox map; one that also touches another area's empty leaves (a wall shared
with the play space) stays in the main map and is copied into the skybox map too. It refuses (and says why) when a spawn stands in the
room or the room is the whole map. Idea and leaf / area reading from CS2-Porter sky3d.py (MIT, copyright bcanusar), adapted to vmap nodes
(their bounds, not brush planes). The BSP's lumps must not be LZMA-compressed.

Both maps also get their moondome shells (stage C's rebuilt sky brushes) switched to tools/toolsskybox: a moondome draws the sky texture
itself and hides the 3D skybox behind it, toolsskybox shows the 3D skybox and env_sky (skink52, 29 Oct 2026).

  python3 skysplit.py --sky <map.vmap in> <map.vmap out>      only the moondome -> toolsskybox swap (a map already split)
  python3 skysplit.py --room <map.vmap> <map.bsp>             read only: what the auto box and the BSP room would each move"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx, vmapedit as V

KEEP_BOTH = {'light_environment', 'env_sky', 'env_fog_controller'}
SKYBOX_MAT = b'materials/tools/toolsskybox.vmat'


def moondome_to_skybox(m):
    """moondome shells -> toolsskybox (they would hide the 3D skybox); returns the number of meshes changed"""
    n = 0
    for node, _ in m.walk():
        if m.type(node) != b'CMapMesh': continue
        md = m.E[m.g(node, b'meshData')]
        mats = dmx.get(md, b'materials')
        if mats and any(b'moondome' in x for x in mats):
            dmx.set_(md, b'materials', dmx.ARR + dmx.T_STR, [SKYBOX_MAT if b'moondome' in x else x for x in mats]); n += 1
    return n


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


# ---------------------------------------------------------------- the room from the BSP (CS2-Porter sky3d.py, MIT, copyright bcanusar), adapted
LUMP_PLANES, LUMP_NODES, LUMP_LEAFS, LUMP_MODELS, LUMP_AREAS, LUMP_AREAPORTALS = 1, 5, 10, 14, 20, 21
CONTENTS_SOLID = 0x1
SPAWNS = ('info_player_terrorist', 'info_player_counterterrorist', 'info_player_start', 'info_player_deathmatch', 'info_teleport_destination')
TOUCH = 1.0


def _lumps(path):
    with open(path, 'rb') as f: d = f.read()
    if d[:4] != b'VBSP': raise ValueError('%s is not a Source 1 BSP' % path)
    L = [struct.unpack_from('<iii4s', d, 8 + 16 * i) for i in range(64)]

    def lump(i):
        o, n, v, cc = L[i]
        if cc != bytes(4) or d[o:o + 4] == b'LZMA': raise ValueError('lump %d of %s is LZMA-compressed' % (i, path))
        return d[o:o + n], v
    return lump


def bsp_room(path, cam):
    """(room leaf boxes, other areas' empty leaf boxes, room area set, point -> area) or None when the camera is in solid / no area"""
    lump = _lumps(path)
    pl = lump(LUMP_PLANES)[0]; planes = [struct.unpack_from('<4f', pl, o) for o in range(0, len(pl) - 19, 20)]
    nd = lump(LUMP_NODES)[0]; nodes = [struct.unpack_from('<3i', nd, o) for o in range(0, len(nd) - 31, 32)]
    head = struct.unpack_from('<i', lump(LUMP_MODELS)[0], 36)[0]
    lf, ver = lump(LUMP_LEAFS); size = 56 if ver == 0 else 32
    leaves = []
    for o in range(0, len(lf) - size + 1, size):
        contents, _cl, af = struct.unpack_from('<ihh', lf, o)
        leaves.append((contents, af & 0x1FF, struct.unpack_from('<3h', lf, o + 8), struct.unpack_from('<3h', lf, o + 14)))

    def leaf_at(p):
        n = head
        while n >= 0:
            pn, c0, c1 = nodes[n]; a, b, c, dd = planes[pn]
            n = c0 if a * p[0] + b * p[1] + c * p[2] - dd >= 0 else c1
        return -n - 1
    leaf = leaf_at(cam)
    if not 0 <= leaf < len(leaves) or leaves[leaf][0] & CONTENTS_SOLID or not leaves[leaf][1]: return None
    ar = lump(LUMP_AREAS)[0]; po = lump(LUMP_AREAPORTALS)[0]
    links = [struct.unpack_from('<2i', ar, o) for o in range(0, len(ar) - 7, 8)]
    other = [struct.unpack_from('<2H', po, o)[1] for o in range(0, len(po) - 11, 12)]
    seen, todo = {leaves[leaf][1]}, [leaves[leaf][1]]
    while todo:
        x = todo.pop()
        if not 0 <= x < len(links): continue
        cnt, first = links[x]
        for y in other[first:first + cnt]:
            if y and y not in seen: seen.add(y); todo.append(y)
    room = [(lo, hi) for c, a, lo, hi in leaves if a in seen and not c & CONTENTS_SOLID]
    rest = [(lo, hi) for c, a, lo, hi in leaves if a and a not in seen and not c & CONTENTS_SOLID]

    def area_at(p):
        l = leaves[leaf_at(p)]
        return 0 if l[0] & CONTENTS_SOLID else l[1]
    return room, rest, seen, area_at


def _touch(a, b, boxes):
    return any(all(a[k] <= hi[k] + TOUCH and b[k] >= lo[k] - TOUCH for k in range(3)) for lo, hi in boxes)


def room_classifier(m, bsp, cam):
    """(node -> 'room' / 'both' / None, room bounds); SystemExit with the reason when the BSP room can't be used"""
    r = bsp_room(bsp, cam)
    if r is None: raise SystemExit('sky_camera at %s is in solid or in no area of %s' % (cam, bsp))
    room, rest, areas, area_at = r
    if not rest: raise SystemExit("the sky_camera's area is the whole map (no sealed room of its own): give a box")
    for e in m.by_class(*SPAWNS):
        if area_at(m.origin(e)) in areas: raise SystemExit("%s at %s stands in the sky_camera's area: give a box" % (m.cls(e), m.origin(e)))
    rlo = [min(b[0][k] for b in room) for k in range(3)]; rhi = [max(b[1][k] for b in room) for k in range(3)]
    near = [b for b in rest if all(b[0][k] <= rhi[k] + 64 and b[1][k] >= rlo[k] - 64 for k in range(3))]

    def where(mm, n):
        a, b = node_box(mm, n)
        if not _touch(a, b, room): return None
        return 'both' if _touch(a, b, near) else 'room'
    return where, (rlo, rhi)


def split(src, main_out, sky_out, name, box=None, bsp=None):
    main = V.Map(src); sky = V.Map(src)
    cams = main.by_class('sky_camera')
    if not cams: raise SystemExit('no sky_camera in %s' % src)
    if bsp:
        where, box = room_classifier(main, bsp, main.origin(cams[-1]))   # the last sky_camera is the one the game showed (CS2-Porter)
    elif box is None:
        box = auto_box(main, main.origin(cams[0]))
    lo, hi = box

    def inside(m, n):
        a, b = node_box(m, n)
        return all(a[k] >= lo[k] - 1 and b[k] <= hi[k] + 1 for k in range(3))
    to_sky = (lambda m, n: where(m, n) is not None) if bsp else inside
    from_main = (lambda m, n: where(m, n) == 'room') if bsp else inside

    moved = kept = 0
    for n in list(main.children(main.world)):
        c = main.cls(n) if main.type(n) == b'CMapEntity' else ''
        if c == 'sky_camera': main.remove_node(n)
        elif c not in KEEP_BOTH and from_main(main, n): main.remove_node(n); moved += 1
    for n in list(sky.children(sky.world)):
        c = sky.cls(n) if sky.type(n) == b'CMapEntity' else ''
        if c == 'sky_camera':
            dmx.set_(sky.E[n], b'editorOnly', dmx.T_BOOL, False); sky.setp(n, 'scale', sky.P(n, 'scale', '16') or '16')
        elif c in KEEP_BOTH or to_sky(sky, n): kept += 1
        else: sky.remove_node(n)
    w = sky.E[sky.world]
    if dmx.get(w, b'mapUsageType') is not None: dmx.set_(w, b'mapUsageType', dmx.T_STR, b'skybox')
    else: w['attrs'].append([b'mapUsageType', dmx.T_STR, b'skybox'])
    main.new_entity('skybox_reference', (0, 0, 0), {'targetname': 'skybox', 'targetMapName': 'maps/%s_3dskybox.vmap' % name,
                                                   'fixupNames': '1', 'worldGroupID': 'skyboxWorldGroup0'})
    sm, ss = moondome_to_skybox(main), moondome_to_skybox(sky)
    main.prune(); sky.prune()
    main.save(main_out); sky.save(sky_out)
    return 'skybox split: %d top-level nodes moved to %s_3dskybox.vmap (%s %s .. %s), skybox_reference added, sky_camera moved; moondome shells -> toolsskybox: %d main, %d skybox' % (
        moved, name, 'BSP room' if bsp else 'box', ' '.join('%g' % x for x in lo), ' '.join('%g' % x for x in hi), sm, ss)


def compare(src, bsp):
    """read only: what the auto box and the BSP room would each move"""
    m = V.Map(src); cams = m.by_class('sky_camera')
    if not cams: return 'no sky_camera in %s' % src
    cam = m.origin(cams[-1]); lo, hi = auto_box(m, cam)
    cand = [n for n in m.children(m.world) if m.type(n) != b'CMapEntity' or m.cls(n) not in KEEP_BOTH | {'sky_camera'}]
    auto = {n for n in cand if all(node_box(m, n)[0][k] >= lo[k] - 1 and node_box(m, n)[1][k] <= hi[k] + 1 for k in range(3))}
    head = 'auto box %s .. %s: %d nodes' % ([round(x) for x in lo], [round(x) for x in hi], len(auto))
    try: where, (rlo, rhi) = room_classifier(m, bsp, cam)
    except SystemExit as ex: return head + ' | BSP room: %s' % ex
    res = {n: where(m, n) for n in cand}
    room = {n for n, w in res.items() if w == 'room'}; both = {n for n, w in res.items() if w == 'both'}
    return head + ' | BSP room %s .. %s: %d nodes move, %d shared (copied) | only in the auto box: %d, only in the BSP room: %d' % (
        [round(x) for x in rlo], [round(x) for x in rhi], len(room), len(both), len(auto - room - both), len(room - auto))


if __name__ == '__main__':
    a = sys.argv[1:]
    bsp = None
    if '--bsp' in a:
        i = a.index('--bsp'); bsp = a[i + 1]; a = a[:i] + a[i + 2:]
    if a and a[0] == '--room':
        print(compare(a[1], a[2])); sys.exit()
    if a and a[0] == '--sky':
        m = V.Map(a[1]); k = moondome_to_skybox(m); m.prune(); m.save(a[2])
        print('moondome shells -> toolsskybox: %d meshes' % k); sys.exit()
    bx = None
    if len(a) > 4:
        v = [float(x) for x in a[4].split(',')]; bx = (v[:3], v[3:])
    print(split(a[0], a[1], a[2], a[3], bx, bsp))
