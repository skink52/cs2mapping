"""Outdoor builders: streets with kerbs and sidewalks, junction squares, fences / railings along a path, scattered props, a sloped bank.

  street(path_xy, width=256, sidewalk=96, kerb=8, z=0, materials=None) -> [(name, shape)]   road + both sidewalks swept along the path
  junction(centre_xy, size=384, z=0, kerb=8, sidewalk=96)                   -> [(name, shape)]   a square with sidewalk corners
  fence(path_xyz, height=48, post_every=96, post=4, rails=2, mat)           -> [(name, shape)]   posts + rails (railing = fence(..., rails=1))
  bank(top_xy_path, drop=128, run=256, z_top=0, mat)                        -> [(name, shape)]   a slope down from the path's left side
  scatter(area_xyxy, spacing=128, models=[...], seed=1, avoid=[boxes], z=fn(x, y) | number, yaw=True) -> [{model, origin, angles}]
  place(scatter_result, cls='prop_static')                                   props into the vmaplib map
  write(shapes, group)                                                       CMapMesh nodes
Terrain itself is vmapgen.Terrain (heightmap tiles, crack-free seams, surf_z for placing things on it); give scatter z=terrain.surf_z.

Ported from streets.py (add_street, add_junction), builders.py (fences, railings, banks) and terrain.py scatter in cs2-map-mcp by
Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT); fresh code on primitives.sweep / prism. Not ported: their street sets / kerb profiles data.
"""
import math, random
import primitives as P

MATS = {'road': 'materials/concrete/concrete_floor_04.vmat', 'sidewalk': 'materials/dev/reflectivity_40.vmat',
        'kerb': 'materials/dev/reflectivity_70.vmat', 'fence': 'materials/dev/reflectivity_10.vmat', 'bank': 'materials/dev/reflectivity_30.vmat'}


def street(path, width=256.0, sidewalk=96.0, kerb=8.0, z=0.0, depth=16.0, materials=None, closed=False):
    m = dict(MATS, **(materials or {}))
    pts = [(p[0], p[1], z) for p in path]
    w = width / 2
    out = [('road', P.sweep(pts, [(-w, -depth), (w, -depth), (w, 0), (-w, 0)], closed, m['road']))]
    if sidewalk:
        for side, sg in (('left', -1), ('right', 1)):
            sec = [(sg * w, -depth), (sg * (w + sidewalk), -depth), (sg * (w + sidewalk), kerb), (sg * w, kerb)]
            out.append(('sidewalk_' + side, P.materials(P.sweep(pts, sec, closed, m['sidewalk']),
                                                       lambda i, n: m['kerb'] if abs(n[2]) < 0.5 else None)))
    return out


def junction(centre, size=384.0, z=0.0, kerb=8.0, sidewalk=96.0, depth=16.0, materials=None):
    m = dict(MATS, **(materials or {}))
    cx, cy = centre; h = size / 2
    out = [('junction', P.box((cx - h, cy - h, z - depth), (cx + h, cy + h, z), m['road']))]
    if sidewalk:
        for sx in (-1, 1):
            for sy in (-1, 1):
                x0, x1 = sorted((cx + sx * h, cx + sx * (h + sidewalk))); y0, y1 = sorted((cy + sy * h, cy + sy * (h + sidewalk)))
                out.append(('corner', P.box((x0, y0, z - depth), (x1, y1, z + kerb), m['sidewalk'])))
    return out


def _seg_points(path, every):
    pts = []
    for (a, b) in zip(path, path[1:]):
        L = math.dist(a[:2], b[:2]); n = max(1, int(round(L / every)))
        for i in range(n): t = i / n; pts.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(3)))
    pts.append(tuple(path[-1]))
    return pts


def fence(path, height=48.0, post_every=96.0, post=4.0, rails=2, rail=3.0, mat=None):
    mat = mat or MATS['fence']
    path = [(p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in path]
    out = [('post', P.box((x - post / 2, y - post / 2, z), (x + post / 2, y + post / 2, z + height), mat)) for x, y, z in _seg_points(path, post_every)]
    for r in range(rails):
        zr = height * (r + 1) / (rails + (0 if rails == 1 else 0.5)) - rail
        out.append(('rail', P.sweep([(x, y, z + zr) for x, y, z in path], P.rect(rail, rail), False, mat)))
    return out


def bank(path, drop=128.0, run=256.0, z_top=0.0, mat=None, depth=32.0):
    """slope from the path (top edge) down `drop` over `run` to its left, as one swept solid (players slide off steep ones)"""
    mat = mat or MATS['bank']
    sec = [(0.0, -depth), (0.0, 0.0), (-run, -drop), (-run, -drop - depth)]
    return [('bank', P.sweep([(x, y, z_top) for x, y in path], sec, False, mat))]


def scatter(area, spacing=128.0, models=('models/props/de_dust/hr_dust/dust_crates/dust_crate_style_01_32x32x32.vmdl',), seed=1,
            avoid=(), z=0.0, yaw=True, max_tries=30):
    """Poisson-disk points (at least `spacing` apart) inside area (x0, y0, x1, y1), none inside the `avoid` boxes (x0, y0, x1, y1)"""
    rnd = random.Random(seed)
    x0, y0, x1, y1 = area
    cell = spacing / math.sqrt(2); grid = {}; pts = []; active = []
    def ok(p):
        if not (x0 <= p[0] <= x1 and y0 <= p[1] <= y1): return False
        if any(b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3] for b in avoid): return False
        gx, gy = int((p[0] - x0) // cell), int((p[1] - y0) // cell)
        for i in range(gx - 2, gx + 3):
            for j in range(gy - 2, gy + 3):
                q = grid.get((i, j))
                if q and math.dist(p, q) < spacing: return False
        return True
    def add(p):
        pts.append(p); active.append(p); grid[(int((p[0] - x0) // cell), int((p[1] - y0) // cell))] = p
    for _ in range(100):
        p = (rnd.uniform(x0, x1), rnd.uniform(y0, y1))
        if ok(p): add(p); break
    while active:
        a = active[rnd.randrange(len(active))]; found = False
        for _ in range(max_tries):
            r = rnd.uniform(spacing, 2 * spacing); th = rnd.uniform(0, 2 * math.pi)
            p = (a[0] + r * math.cos(th), a[1] + r * math.sin(th))
            if ok(p): add(p); found = True; break
        if not found: active.remove(a)
    zf = z if callable(z) else (lambda x, y, c=float(z): c)
    return [{'model': rnd.choice(list(models)), 'origin': [p[0], p[1], zf(p[0], p[1])], 'angles': [0.0, rnd.uniform(0, 360) if yaw else 0.0, 0.0]} for p in pts]


def place(items, cls='prop_static', group='scatter', **keys):
    return [P.entity(cls, it['origin'], it['angles'], group=group, strict=False, model=it['model'], **keys) for it in items]


def write(shapes, group='world'):
    return [P.add(s, group) for _, s in shapes]
