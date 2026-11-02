"""Z-fighting: visible faces that lie in the same plane, face the same way and overlap, so the renderer flickers between them.

  python zfight.py <map.vmap> [<out.vmap>] [<addon content folder>]

Source's compiler hid such faces (vbsp keeps one of two coplanar faces), CS2 draws both. Skipped: tool materials (nodraw, clips, triggers, skybox
and the like), materials that are completely transparent (opacity 0, or a colour texture whose alpha is 0 everywhere) and overlay / decal shaders,
which are meant to sit on a surface. Faces back to back (opposite normals) don't fight, and an overlap pressed against a face pointing the other
way (two props' undersides on the same floor) can't be seen, so it doesn't count either.
Reports every overlapping pair grouped by material. With an out path:
- a face the other covers completely (>= 98% of its area) is set to toolsnodraw, as vbsp would have dropped it;
- where two different materials partly overlap, the smaller face (usually the trim, step or strip meant to show) moves NUDGE units out along its
  normal, so it draws on top. Only meshes with no rotation or scale are moved; the rest stay on the list.
Same-material partial overlaps are listed but left alone: the same texture flickering against itself barely shows.
The last line is: summary <TAB> pairs=N hidden=N nudged=N partial=N visible=N   (visible = different materials, still overlapping, >= 64 sq units)
"""
import collections, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx, vmapedit as V

NODRAW = 'materials/tools/toolsnodraw.vmat'
SKIP_PREFIX = ('materials/tools/', 'materials/dev/dev_nodraw', 'materials/editor/')
SKIP_WORDS = ('nodraw', 'invisible', 'trigger', 'clip', 'skybox', 'moondome', 'hint', 'occluder', 'areaportal', 'blocklight', 'decal', 'overlay')
PLANE_EPS = 0.05   # units: coplanar to float precision, so faces NUDGE apart no longer count
MIN_AREA = 4.0     # square units of overlap before a pair counts

def transparent(mat, content):
    """True for a material nobody sees, judged from its vmat and colour texture in the addon (stock CS2 materials count as visible)."""
    m = mat.lower()
    if m.startswith(SKIP_PREFIX) or any(w in m for w in SKIP_WORDS): return True
    if not content: return False
    p = os.path.join(content, m.replace('/', os.sep))
    try: txt = open(p, encoding='utf-8', errors='replace').read()
    except OSError: return False
    if re.search(r'shader\s+"?[\w]*(overlay|decal)', txt, re.I) or re.search(r'F_OVERLAY\s+"?1', txt): return True
    op = re.search(r'g_flOpacityScale\s+"?([\d.]+)', txt)
    if op and float(op.group(1)) == 0: return True
    tex = re.search(r'TextureColor\s+"([^"]+)"', txt)
    if tex and re.search(r'F_(TRANSLUCENT|ALPHA_TEST)\s+"?1', txt):
        try:
            from PIL import Image
            im = Image.open(os.path.join(content, tex.group(1).replace('/', os.sep)))
            if im.mode in ('RGBA', 'LA') and im.getchannel('A').getextrema()[1] == 0: return True
        except Exception: pass
    return False

def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

def plane(poly):
    n = (0.0, 0.0, 0.0)
    for i in range(len(poly)):   # Newell's method, robust for slightly bent faces
        a, b = poly[i], poly[(i + 1) % len(poly)]
        n = (n[0] + (a[1] - b[1]) * (a[2] + b[2]), n[1] + (a[2] - b[2]) * (a[0] + b[0]), n[2] + (a[0] - b[0]) * (a[1] + b[1]))
    l = math.sqrt(dot(n, n))
    if l < 1e-6: return None
    n = (n[0] / l, n[1] / l, n[2] / l)
    return n, dot(n, poly[0])

def to2d(poly, n):
    ax = max(range(3), key=lambda i: abs(n[i])); u, v = [i for i in range(3) if i != ax]
    pts = [(p[u], p[v]) for p in poly]
    if area2(pts) < 0: pts.reverse()
    return pts

def area2(pts): return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))) / 2

def clip(subj, clipper):
    """Sutherland-Hodgman: subj inside a convex clipper (both counter-clockwise)."""
    out = subj
    for i in range(len(clipper)):
        a, b = clipper[i], clipper[(i + 1) % len(clipper)]
        inp, out = out, []
        if not inp: break
        side = lambda p: (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        for j in range(len(inp)):
            p, q = inp[j], inp[(j + 1) % len(inp)]
            sp, sq = side(p), side(q)
            if sp >= 0: out.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq); out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out

def faces(m):
    """(mesh node, face index, material, world polygon) for every face of every mesh."""
    out = []
    for n, _ in m.walk():
        if m.type(n) != b'CMapMesh': continue
        md = m.g(n, b'meshData')
        if md is None: continue
        get = lambda k: dmx.get(m.E[md], k)
        vdi, evi, eni, fei, fdi = get(b'vertexDataIndices'), get(b'edgeVertexIndices'), get(b'edgeNextIndices'), get(b'faceEdgeIndices'), get(b'faceDataIndices')
        mats = [x.decode().lower() for x in get(b'materials') or []]
        pos = next((dmx.get(m.E[st], b'data') for st in dmx.get(m.E[get(b'vertexData')], b'streams') if m.E[st]['name'].startswith(b'position')), None)
        mi = next((dmx.get(m.E[st], b'data') for st in dmx.get(m.E[get(b'faceData')], b'streams') if m.E[st]['name'].startswith(b'materialindex')), None)
        if pos is None or not fei: continue
        o = world_origin(m, n)
        for f, e0 in enumerate(fei):
            loop = []; e = e0
            for _ in range(4096):
                p = pos[vdi[evi[e]]]; loop.append((p[0] + o[0], p[1] + o[1], p[2] + o[2])); e = eni[e]
                if e == e0: break
            k = mi[fdi[f]] if mi else 0
            out.append((n, f, mats[k] if k < len(mats) else '', loop))
    return out

ORIGINS = {}
def world_origin(m, n):
    """Mesh origin plus its parents' (entity meshes sit under their entity)."""
    if not ORIGINS:
        def walk(i, o):
            for c in m.children(i):
                p = m.g(c, b'origin', [0, 0, 0]); w = (o[0] + p[0], o[1] + p[1], o[2] + p[2]); ORIGINS[c] = w; walk(c, w)
        walk(m.world, (0.0, 0.0, 0.0))
    return ORIGINS.get(n, m.g(n, b'origin', [0, 0, 0]))

def find(m, content=None):
    ORIGINS.clear()
    cache = {}
    vis = lambda mat: not cache.setdefault(mat, transparent(mat, content))
    buckets = collections.defaultdict(list)
    for n, f, mat, poly in faces(m):
        if len(poly) < 3 or not vis(mat): continue
        pl = plane(poly)
        if not pl: continue
        nrm, d = pl
        key = (round(nrm[0], 2), round(nrm[1], 2), round(nrm[2], 2), round(d / PLANE_EPS))
        buckets[key].append((n, f, mat, poly, nrm, d))
    pairs = []; flats = {}
    def flat_of(key):
        if key not in flats: flats[key] = [(a, to2d(a[3], a[4])) for a in buckets.get(key, [])]
        return flats[key]
    def hidden_by_backs(poly, key):
        """Area of poly pressed against faces facing the other way in the same plane: a desk's underside on a floor. Nobody sees it, and vbsp removed it."""
        opp = (-key[0] + 0.0, -key[1] + 0.0, -key[2] + 0.0)
        cover = 0.0
        for dk in (-1, 0, 1):
            for _, q in flat_of((opp[0], opp[1], opp[2], -key[3] + dk)):
                if len(q) >= 3: cover += abs(area2(clip(poly, q)))
        return cover
    for key in list(buckets):
        flat = flat_of(key)
        nxt = flat_of(key[:3] + (key[3] + 1,))   # a plane right on a bucket edge lands in the next one
        if len(flat) + len(nxt) < 2: continue
        for i in range(len(flat)):
            (n1, f1, m1, p1, nr1, d1), q1 = flat[i]
            a1 = abs(area2(q1))
            if a1 < MIN_AREA: continue
            b1 = (min(x for x, _ in q1), min(y for _, y in q1), max(x for x, _ in q1), max(y for _, y in q1))
            for (n2, f2, m2, p2, nr2, d2), q2 in flat[i + 1:] + nxt:
                if n1 == n2 and f1 == f2 or abs(d1 - d2) > PLANE_EPS or dot(nr1, nr2) < 0.999: continue
                b2 = (min(x for x, _ in q2), min(y for _, y in q2), max(x for x, _ in q2), max(y for _, y in q2))
                if b1[2] <= b2[0] or b2[2] <= b1[0] or b1[3] <= b2[1] or b2[3] <= b1[1]: continue
                shared = clip(q1, q2) if len(q2) >= 3 else []
                ov = abs(area2(shared)) if len(shared) >= 3 else 0
                if ov < MIN_AREA or ov - hidden_by_backs(shared, key) < MIN_AREA: continue
                a2 = abs(area2(q2))
                pairs.append(dict(a=(n1, f1, m1, a1), b=(n2, f2, m2, a2), overlap=ov, normal=nr1, at=tuple(round(sum(c) / len(p1)) for c in zip(*p1))))
    return pairs

def hide(m, node, face):
    """Set one face's material to toolsnodraw."""
    md = m.g(node, b'meshData'); el = m.E[md]
    mats = dmx.geta(el, b'materials')[2]
    if NODRAW.encode() not in mats: mats.append(NODRAW.encode())
    k = mats.index(NODRAW.encode())
    fd = dmx.get(el, b'faceDataIndices')[face]
    for st in dmx.get(m.E[dmx.get(el, b'faceData')], b'streams'):
        if m.E[st]['name'].startswith(b'materialindex'): dmx.get(m.E[st], b'data')[fd] = k

NUDGE = 0.25   # units; enough for CS2's depth buffer at play distances, too small to see as a step

def unrotated(m, node):
    """True when the mesh and every parent above it have no rotation or scale, so a world normal is also its local one."""
    parent = m.parent_of()
    while node is not None and node != m.world:
        if any(abs(a) > 1e-4 for a in m.g(node, b'angles', [0, 0, 0])) or any(abs(s - 1) > 1e-4 for s in m.g(node, b'scales', [1, 1, 1])): return False
        node = parent.get(node)
    return True

def nudge(m, node, face, normal):
    """Move one face's vertices NUDGE units along its normal (neighbouring faces of that mesh lean by the same tiny amount)."""
    el = m.E[m.g(node, b'meshData')]
    get = lambda k: dmx.get(el, k)
    vdi, evi, eni, fei = get(b'vertexDataIndices'), get(b'edgeVertexIndices'), get(b'edgeNextIndices'), get(b'faceEdgeIndices')
    pos = next(dmx.get(m.E[st], b'data') for st in dmx.get(m.E[get(b'vertexData')], b'streams') if m.E[st]['name'].startswith(b'position'))
    e0 = fei[face]; e = e0; seen = set()
    for _ in range(4096):
        k = vdi[evi[e]]
        if k not in seen:
            seen.add(k); p = pos[k]; pos[k] = type(p)([p[0] + normal[0] * NUDGE, p[1] + normal[1] * NUDGE, p[2] + normal[2] * NUDGE])
        e = eni[e]
        if e == e0: break

def run(m, content=None, fix=False):
    pairs = find(m, content); hidden = set(); moved = set(); partial = []
    for p in pairs:
        (n1, f1, m1, a1), (n2, f2, m2, a2) = p['a'], p['b']
        small, big = (p['a'], p['b']) if a1 <= a2 else (p['b'], p['a'])
        if p['overlap'] >= 0.98 * small[3]:
            if fix and (small[0], small[1]) not in hidden and (big[0], big[1]) not in hidden:
                hide(m, small[0], small[1]); hidden.add((small[0], small[1]))
            continue
        if fix and m1 != m2 and (small[0], small[1]) not in moved and (big[0], big[1]) not in moved and unrotated(m, small[0]):
            nudge(m, small[0], small[1], p['normal']); moved.add((small[0], small[1])); continue
        partial.append(p)
    return pairs, hidden, moved, partial

def visible(p): return p['a'][2] != p['b'][2] and p['overlap'] >= 64

if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    src = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].endswith('.vmap') else None
    content = sys.argv[3] if len(sys.argv) > 3 else (sys.argv[2] if len(sys.argv) > 2 and not out else None)
    mp = V.Map(src)
    pairs, hidden, moved, partial = run(mp, content, bool(out))
    groups = collections.Counter(tuple(sorted((p['a'][2], p['b'][2]))) for p in pairs)
    for (x, y), n in groups.most_common(25): print('pair\t%d x %s | %s' % (n, x, y))
    for p in sorted(partial, key=lambda p: (not visible(p), -p['overlap']))[:30]:
        print('partial\t%s | %s at %s, %.0f sq units overlap%s' % (p['a'][2], p['b'][2], ' '.join(map(str, p['at'])), p['overlap'], '' if visible(p) else ' (minor)'))
    if out: mp.save(out)
    print('summary\tpairs=%d hidden=%d nudged=%d partial=%d visible=%d' % (len(pairs), len(hidden), len(moved), len(partial), sum(map(visible, partial))))
