"""Radar / minimap from a compiled CS2 map's nav mesh: the walkable nav areas, grown a little in XY (the nav generator pulls
them in from the walls by the agent radius), shaded by height like radar.py's untextured floors (per pixel from each area's height plane; darker towards the bottom of
the map, higher areas drawn on top), outlined at the walkable edge and at height steps over 40 units, ladders marked.
Same framing as radar.py (0.5 percentile trimmed off each side, span x 1.06 + 256 units, square), so the png and
resource/overviews/<map>.txt drop in where radar.py's go. An option beside radar.py for compiled maps: no vmap needed,
but it only knows where a player can walk (no materials, no wall tops, no water).

nav format from ValveResourceFormat NavMesh/*.cs (MIT), idea from Hammer5Tools NavMeshRadarGenerator (MIT).
Nav versions read: 30-36 (the ones ValveResourceFormat reads); found on the PC (Nov 2026): 35 and 36. The binary KV3 blocks of
v36 are skipped by their v5 header sizes, not decoded.

  python tools/navradar.py <map.vpk|map.nav> <out.png> [--size 1024|2048] [--overview out.txt] [--expand 16] [--hull N]
                           [--ct X,Y] [--t X,Y] [--min-island N] [--info]
"""
import io, os, struct, sys
import numpy as np

MAGIC = 0xFEEDFACE
NO_MOVABLE = 0xFFFFFFFF
OVERVIEW = '''// Overview (radar) description for %(map)s: rendered from the compiled nav mesh (tools/navradar.py, walkable areas shaded by height)
// Radar image: content\\csgo_addons\\%(map)s\\panorama\\images\\overheadmaps\\%(map)s_radar_psd.png

"%(map)s"
{
	"material"	"overviews/%(map)s_radar"	// texture file
	"pos_x"		"%(px)d"	// upper left world coordinate
	"pos_y"		"%(py)d"
	"scale"		"%(scale).2f"
	"rotate"	"0"
	"zoom"		"1.0"

	// loading screen icons and positions
	"CTSpawn_x"	"%(ctx).2f"
	"CTSpawn_y"	"%(cty).2f"
	"TSpawn_x"	"%(tx).2f"
	"TSpawn_y"	"%(ty).2f"
}
'''


class NavError(ValueError): pass


class _R:
    def __init__(s, d): s.d = d; s.p = 0
    def get(s, fmt):
        v = struct.unpack_from('<' + fmt, s.d, s.p); s.p += struct.calcsize('<' + fmt)
        return v if len(v) > 1 else v[0]
    def bytes(s, n): b = s.d[s.p:s.p + n]; s.p += n; return b
    def cstr(s):
        e = s.d.index(b'\0', s.p); v = s.d[s.p:e].decode('ascii', 'replace'); s.p = e + 1; return v


def skip_kv3(r):
    """Skip one binary KV3 block (8-byte aligned, KV3 v5 header): header 120 bytes + buffer 1 + buffer 2 (their compressed
    sizes, or the uncompressed ones when the block is stored uncompressed, as the navs on the PC are)."""
    r.p = (r.p + 7) & ~7
    start = r.p
    magic = r.get('I')
    if magic & 0xFFFFFF00 != 0x4B563300 or magic & 0xFF != 5:
        raise NavError('KV3 block at %d: magic %08x, only binary KV3 v5 is skipped' % (start, magic))
    h = struct.unpack_from('<16sIHH4I2H4I2I4I4I4I', r.d, start + 4)
    method, nblocks, blob_bytes = h[1], h[12], h[13]
    b1, b2 = (h[16], h[18]) if method == 0 else (h[17], h[19])
    end = start + 120 + b1 + b2
    if nblocks:
        if method != 0: raise NavError('KV3 block at %d: compressed binary blobs, length unknown without decoding' % start)
        end += blob_bytes
    if end > len(r.d): raise NavError('KV3 block at %d runs past the end of the file' % start)
    r.p = end


def read_nav(data):
    """Parse a CS2 .nav (bytes) up to and including the ladders. Returns a dict:
    version, subversion, places, areas [{id, flags, hull, corners (N x 3), movable, connections [[(area, edge)] per edge],
    ladders_above, ladders_below}], ladders [{id, width, top, bottom, length, direction, areas (7 ids, 0 = none)}]."""
    r = _R(data)
    if len(data) < 13 or r.get('I') != MAGIC: raise NavError('not a nav file (magic)')
    ver = r.get('I')
    if not 30 <= ver <= 36: raise NavError('nav version %d not supported (30-36)' % ver)
    sub = r.get('I'); r.get('B')                                       # analysed flag
    places = []
    for _ in range(r.get('H')):
        places.append(r.bytes(r.get('H')).rstrip(b'\0').decode('utf-8', 'replace'))
    r.get('B')                                                         # has unnamed areas
    if ver >= 36: skip_kv3(r)                                          # movable mesh settings
    polys = None
    if ver >= 31:
        nc = r.get('I')
        corners = np.frombuffer(r.bytes(12 * nc), '<f4').reshape(nc, 3).astype(np.float64)
        polys = []
        for _ in range(r.get('I')):
            k = r.get('B')
            idx = np.frombuffer(r.bytes(4 * k), '<u4')
            if k and idx.max() >= nc: raise NavError('polygon corner index out of range')
            mov = r.get('I') if ver >= 35 else NO_MOVABLE
            polys.append((corners[idx], mov))
        if ver >= 32 and r.get('I') & 1:                               # corner gravity: not needed for a radar
            r.bytes(12 * r.get('I'))
    if ver >= 35:
        for _ in range(r.get('I')): r.cstr(); r.bytes(48)               # movable mesh id + 3x4 matrix
    if ver >= 36: skip_kv3(r)                                          # game data
    areas = []
    for _ in range(r.get('I')):
        aid, flags, hull = r.get('IqB')
        if ver >= 31:
            pi = r.get('I')
            if pi >= len(polys): raise NavError('area %d: polygon index %d out of range' % (aid, pi))
            C, mov = polys[pi]
        else:
            k = r.get('I'); C = np.frombuffer(r.bytes(12 * k), '<f4').reshape(k, 3).astype(np.float64); mov = NO_MOVABLE
        r.get('f')                                                     # unused, always 0
        conns = []
        for _ in range(len(C)):
            n = r.get('I'); a = np.frombuffer(r.bytes(8 * n), '<u4').reshape(n, 2)
            conns.append([tuple(map(int, x)) for x in a])
        r.bytes(17 * r.get('B'))                                       # hiding spots: id, pos, flags
        if r.get('I'): raise NavError('area %d: encounter paths not supported' % aid)
        above = list(np.frombuffer(r.bytes(4 * r.get('I')), '<u4'))
        below = list(np.frombuffer(r.bytes(4 * r.get('I')), '<u4'))
        areas.append(dict(id=aid, flags=flags, hull=hull, corners=C, movable=mov, connections=conns, ladders_above=above, ladders_below=below))
    ladders = []
    for _ in range(r.get('I')):
        lid, width = r.get('If'); top = r.get('3f'); bottom = r.get('3f'); length, direction = r.get('fI')
        ids = list(r.get('5I')) + (list(r.get('2I')) if ver >= 33 else [0, 0])
        ladders.append(dict(id=lid, width=width, top=top, bottom=bottom, length=length, direction=direction, areas=ids))
    return dict(version=ver, subversion=sub, places=places, areas=areas, ladders=ladders, end=r.p)


def load(path):
    """(map name, nav bytes) from a loose .nav or a compiled map .vpk (maps/<name>.nav inside it)."""
    base = os.path.splitext(os.path.basename(path))[0]
    if path.lower().endswith('.vpk'):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import vpk
        v = vpk.VPK(path)
        navs = sorted(f for f in v.files if f.startswith('maps/') and f.endswith('.nav'))
        if not navs: raise NavError('%s has no maps/*.nav' % path)
        name = 'maps/%s.nav' % base.lower()
        name = name if name in navs else navs[0]
        return os.path.splitext(os.path.basename(name))[0], v.read(name, {})
    with open(path, 'rb') as f: return base, f.read()


def islands(areas):
    """Connected groups of areas (by their connections), as lists of indices into areas, biggest first."""
    ix = {a['id']: i for i, a in enumerate(areas)}
    par = list(range(len(areas)))
    def find(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    for i, a in enumerate(areas):
        for edge in a['connections']:
            for other, _ in edge:
                j = ix.get(other)
                if j is not None: par[find(i)] = find(j)
    groups = {}
    for i in range(len(areas)): groups.setdefault(find(i), []).append(i)
    return sorted(groups.values(), key=len, reverse=True)


def expand(C, d):
    """Grow a convex nav polygon by d units in XY (mitred corners, mitre capped at 2d); z kept per corner."""
    P = np.asarray(C, np.float64)
    keep = [i for i in range(len(P)) if np.hypot(*(P[i, :2] - P[i - 1, :2])) > 1e-3]
    P = P[keep]
    if d <= 0 or len(P) < 3: return P
    x, y = P[:, 0], P[:, 1]
    sgn = 1.0 if (x * np.roll(y, -1) - np.roll(x, -1) * y).sum() > 0 else -1.0   # counter-clockwise: outward = right of edge
    E = np.roll(P[:, :2], -1, axis=0) - P[:, :2]
    N = np.stack([E[:, 1], -E[:, 0]], 1) * sgn
    N /= np.linalg.norm(N, axis=1)[:, None]
    n1, n2 = np.roll(N, 1, axis=0), N                                  # edges in and out of each corner
    m = n1 + n2
    k = 1.0 + (n1 * n2).sum(1)
    shift = m * (d / np.maximum(k, 0.5))[:, None]                      # |shift| <= 2d
    Q = P.copy(); Q[:, :2] += shift
    return Q


def frame(points, size, pct=0.5):
    """radar.py's framing: (pos_x, pos_y, scale, span) for points (N x 3)."""
    lo = np.percentile(points, pct, axis=0); hi = np.percentile(points, 100 - pct, axis=0)
    span = max(hi[0] - lo[0], hi[1] - lo[1]) * 1.06 + 256
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    return cx - span / 2, cy + span / 2, span / size, span


def render(nav, size=1024, ss=2, expand_units=16.0, hull=None, min_island=0, pct=0.5):
    """RGBA PIL image + (pos_x, pos_y, scale, span) + stats dict."""
    from PIL import Image, ImageDraw
    areas = nav['areas']
    hulls = sorted({a['hull'] for a in areas})
    if hull is None and hulls: hull = min(hulls, key=lambda h: (-sum(a['hull'] == h for a in areas), h))   # the most common hull
    areas = [a for a in areas if a['hull'] == hull and len(a['corners']) >= 3]
    groups = islands(areas)
    dropped = [g for g in groups if len(g) < min_island]
    drop = {i for g in dropped for i in g}
    areas = [a for i, a in enumerate(areas) if i not in drop]
    st = dict(version=nav['version'], hulls=hulls, hull=hull, areas=len(areas), islands=len(groups), islands_dropped=len(dropped), ladders=len(nav['ladders']))
    if not areas: raise NavError('no nav areas (hull %s): the map was compiled without a nav mesh' % hull)
    allp = np.concatenate([a['corners'] for a in areas])
    px, py, scale, span = frame(allp, size, pct)
    zlo, zhi = np.percentile(allp[:, 2], 2), np.percentile(allp[:, 2], 98)
    S = size * ss
    def to_img(P): return [((x - px) / scale * ss, (py - y) / scale * ss) for x, y in P[:, :2]]
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    idx = Image.new('I', (S, S), 0); di = ImageDraw.Draw(idx)            # which area is on top at each pixel (1-based)
    planes = np.zeros((len(areas) + 1, 3))
    order = sorted(range(len(areas)), key=lambda i: areas[i]['corners'][:, 2].mean())
    for i in order:
        C = areas[i]['corners']
        t = float(np.clip((C[:, 2].mean() - zlo) / max(zhi - zlo, 1), 0, 1))
        Q = expand(C, expand_units)
        if len(Q) < 3: continue
        pts = to_img(Q)
        d.polygon(pts, fill=(int(70 + 120 * t), int(80 + 120 * t), int(95 + 125 * t), 255))
        di.polygon(pts, fill=i + 1)
        A = np.c_[C[:, 0], C[:, 1], np.ones(len(C))]                    # height plane z = a x + b y + c, for the step lines
        planes[i + 1] = np.linalg.lstsq(A, C[:, 2], rcond=None)[0]
    I = np.asarray(idx, np.int64)
    ys, xs = np.mgrid[0:S, 0:S]
    wx = px + (xs + 0.5) / ss * scale; wy = py - (ys + 0.5) / ss * scale
    pl = planes[I]
    Z = pl[..., 0] * wx + pl[..., 1] * wy + pl[..., 2]
    cov = I > 0
    Z[~cov] = -1e9
    line = np.zeros((S, S), bool)
    for dy, dx in ((0, 1), (1, 0)):                                    # height steps over 40 units: line on the upper side
        a = Z[:S - dy, :S - dx]; b = Z[dy:, dx:]
        both = cov[:S - dy, :S - dx] & cov[dy:, dx:]
        step = both & (np.abs(a - b) > 40)
        line[:S - dy, :S - dx] |= step & (a > b); line[dy:, dx:] |= step & (b > a)
    outer = np.zeros((S, S), bool)                                     # walkable edge: the pixels just outside the areas
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        outer |= ~cov & np.roll(cov, (dy, dx), axis=(0, 1))
    for _ in range(max(0, ss - 1)):
        outer |= ~cov & (np.roll(outer, 1, 0) | np.roll(outer, 1, 1))
    A = np.array(img)
    T = np.clip((Z - zlo) / max(zhi - zlo, 1), 0, 1)[cov]              # per pixel from the area's height plane: smooth on ramps
    A[cov] = np.stack([70 + 120 * T, 80 + 120 * T, 95 + 125 * T, np.full_like(T, 255)], 1).astype(np.uint8)
    A[line | outer] = (20, 22, 28, 255)
    img = Image.fromarray(A, 'RGBA'); d = ImageDraw.Draw(img)
    for L in nav['ladders']:
        a = to_img(np.array([L['top']])); b = to_img(np.array([L['bottom']]))
        d.line(a + b, fill=(230, 170, 60, 255), width=max(2, 2 * ss))
        r = 2 * ss; x, y = a[0]; d.ellipse([x - r, y - r, x + r, y + r], fill=(230, 170, 60, 255))
    return img.resize((size, size), Image.LANCZOS), (px, py, scale, span), st


def overview(mapname, px, py, scale, span, ct=None, t=None):
    def frac(p):
        if p is None: return 0.5, 0.5
        return float(np.clip((p[0] - px) / span, 0, 1)), float(np.clip((py - p[1]) / span, 0, 1))
    (ctx, cty), (tx, ty) = frac(ct), frac(t)
    return OVERVIEW % dict(map=mapname, px=px, py=py, scale=scale, ctx=ctx, cty=cty, tx=tx, ty=ty)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='Radar png (+ overview txt) from a compiled map nav mesh')
    ap.add_argument('src', help='compiled map .vpk or a loose .nav'); ap.add_argument('out', help='output .png')
    ap.add_argument('--size', type=int, default=1024, choices=(1024, 2048))
    ap.add_argument('--overview', help='write resource/overviews text here')
    ap.add_argument('--expand', type=float, default=16.0, help='grow each area by this many units in XY (default 16, the agent radius)')
    ap.add_argument('--hull', type=int, help='nav hull index (default: the one with the most areas)')
    ap.add_argument('--min-island', type=int, default=0, help='drop connected groups with fewer areas than this')
    ap.add_argument('--ct', help='CT spawn world X,Y for the overview'); ap.add_argument('--t', help='T spawn world X,Y')
    ap.add_argument('--info', action='store_true', help='print the nav summary only')
    a = ap.parse_args(argv)
    name, data = load(a.src)
    nav = read_nav(data)
    hulls = {}
    for ar in nav['areas']: hulls[ar['hull']] = hulls.get(ar['hull'], 0) + 1
    print('%s: nav v%d.%d, %d areas (hulls %s), %d ladders, %d places, parsed %d of %d bytes'
          % (name, nav['version'], nav['subversion'], len(nav['areas']), hulls, len(nav['ladders']), len(nav['places']), nav['end'], len(data)))
    if a.info: return 0
    xy = lambda s: tuple(float(v) for v in s.split(',')) if s else None
    img, (px, py, scale, span), st = render(nav, a.size, expand_units=a.expand, hull=a.hull, min_island=a.min_island)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    img.save(a.out)
    print('radar %s: %d areas (hull %d), %d islands (%d dropped), pos %d %d, scale %.2f' % (a.out, st['areas'], st['hull'], st['islands'], st['islands_dropped'], px, py, scale))
    if a.overview:
        with open(a.overview, 'w', newline='\n') as f: f.write(overview(name, px, py, scale, span, xy(a.ct), xy(a.t)))
        print('overview %s' % a.overview)
    return 0


if __name__ == '__main__':
    sys.exit(main())
