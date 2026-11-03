"""Close hairline gaps between the meshes of a collapsed map. Vertices that drifted off the grid (Hammer edits on uncollapsed prefab
geometry: ba_jail_skylight 3 Nov 2026, floors 0.125 high, walls 0.035 low, trims anywhere in between) are put back where the prefab
or the integer grid has them, and vertices of different meshes that almost touch are welded to one position. Only vertex positions
change: every mesh keeps the edge and face structure Hammer saved (a rebuild through splitfaces.mesh_write crashed Hammer's
post-load fixup, 3 Nov 2026), so a move that would make two vertices of one face coincide is undone instead.

  python meshweld.py <map.vmap> [<out.vmap>] [--prefab <prefab.vmap>]... [--radius 1.0] [--grid 0.25] [--weld 0.75] [--verbose]

Per vertex, first match wins: (1) already on a prefab vertex: untouched. (2) a prefab vertex on the integer grid within --radius.
(3) each coordinate within --grid of an integer goes onto it (the others stay: a diagonal wall's y is meant to be off grid).
(4) the nearest prefab vertex within --radius when no other prefab vertex is nearly as close. Then across meshes, for two vertices
closer than --weld, per coordinate: the integer side wins; two different integers are real geometry (the pair is left); neither
integer, the mesh with more faces wins. Rotated, scaled and displacement (subdivision) meshes are only read. Without <out.vmap>
nothing is written. Hammer must not have the map open when writing. The compile's own vertex welding does not close these gaps:
0.035 is enough for light to leak through a wall-floor join."""
import sys, os, math, bisect, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx, vmapedit as V
from vmapedit import xform

def world_origins(m):
    O = {}
    def walk(i, o):
        for c in m.children(i):
            p = m.g(c, b'origin', [0, 0, 0]); w = (o[0] + p[0], o[1] + p[1], o[2] + p[2]); O[c] = w; walk(c, w)
    walk(m.world, (0.0, 0.0, 0.0)); return O

def load(path):
    """-> (Map, [mesh]); mesh = dict(n, nf, o, plain, pos (the position stream, local), w (world ndarray per vertex), faces [[vertex index]])"""
    m = V.Map(path); O = world_origins(m); meshes = []
    for n, p in m.walk():
        if m.type(n) != b'CMapMesh': continue
        md = m.g(n, b'meshData')
        if md is None: continue
        vd = m.g(md, b'vertexData')
        st = next((st for st in dmx.get(m.E[vd], b'streams') if m.E[st]['name'].startswith(b'position')), None) if vd is not None else None
        if st is None: continue
        pos = dmx.get(m.E[st], b'data')
        sd = m.g(md, b'subdivisionData'); subdiv = bool(sd is not None and m.g(sd, b'streams'))
        ang = m.g(n, b'angles', [0, 0, 0]); sc = m.g(n, b'scales', [1, 1, 1]); o = np.array(O[n], float)
        plain = not any(abs(a) > 1e-6 for a in ang) and not any(abs(s - 1) > 1e-6 for s in sc) and not subdiv
        if plain: w = np.array([(v[0] + o[0], v[1] + o[1], v[2] + o[2]) for v in pos], float)
        else: w = np.array([xform([v[0] * sc[0], v[1] * sc[1], v[2] * sc[2]], O[n], ang) for v in pos], float)
        g = lambda k: dmx.get(m.E[md], k)
        vdi, evi, eni, fei = g(b'vertexDataIndices'), g(b'edgeVertexIndices'), g(b'edgeNextIndices'), g(b'faceEdgeIndices')
        faces = []
        for e0 in fei or []:
            loop = []; e = e0
            for _ in range(4096):
                loop.append(vdi[evi[e]]); e = eni[e]
                if e == e0: break
            faces.append(loop)
        meshes.append(dict(n=n, nf=len(faces), o=o, plain=plain, pos=pos, w=w, orig=w.copy(), faces=faces))
    return m, meshes

def ongrid(v, eps=1e-3): return all(abs(c - round(c)) < eps for c in v)

class Index:
    def __init__(s, pts):
        s.pv = np.unique(np.asarray(pts, float), axis=0) if len(pts) else np.zeros((0, 3))
        if len(s.pv): s.pv = s.pv[np.lexsort((s.pv[:, 2], s.pv[:, 1], s.pv[:, 0]))]
        s.px = s.pv[:, 0]
        s.grid = np.array([ongrid(v) for v in s.pv], bool) if len(s.pv) else np.zeros(0, bool)
    def within(s, v, r):
        lo = bisect.bisect_left(s.px, v[0] - r); hi = bisect.bisect_right(s.px, v[0] + r)
        if hi <= lo: return np.zeros((0, 3)), np.zeros(0), np.zeros(0, bool)
        seg = s.pv[lo:hi]; d = np.linalg.norm(seg - v, axis=1); k = d < r
        return seg[k], d[k], s.grid[lo:hi][k]

def nearmiss(meshes, lim, samples=0, log=None):
    """vertex pairs from different meshes closer than lim (and not coincident), counted by mesh pair. A pair where either
    vertex already coincides with some vertex of the other mesh is not a gap (a floor's 0.125 skirt next to a trim that sits
    exactly on the floor top) and is left out."""
    allv = sorted((tuple(v), x['n']) for x in meshes for v in x['w'])
    have = {(tuple(np.round(v, 3)), x['n']) for x in meshes for v in x['w']}
    by = collections.Counter(); shown = 0
    for i, (v, n) in enumerate(allv):
        j = i + 1
        while j < len(allv) and allv[j][0][0] - v[0] < lim:
            u, n2 = allv[j]; j += 1
            if n2 != n and 1e-3 < math.dist(u, v) < lim and (tuple(np.round(v, 3)), n2) not in have and (tuple(np.round(u, 3)), n) not in have:
                by[tuple(sorted((n, n2)))] += 1
                if shown < samples: log('  left: %s (node %d) vs %s (node %d) d=%.3f' % (tuple(round(c, 3) for c in v), n, tuple(round(c, 3) for c in u), n2, math.dist(u, v))); shown += 1
    return by

def face_ok(x, k):
    """every face using vertex k still has distinct corners and some area"""
    for loop in x['faces_of'][k]:
        P = x['w'][loop]
        for a in range(len(loop)):
            for b in range(a + 1, len(loop)):
                if np.linalg.norm(P[a] - P[b]) < 1e-4: return False
        nrm = np.zeros(3)
        for i in range(1, len(P) - 1): nrm += np.cross(P[i] - P[0], P[i + 1] - P[0])
        if np.linalg.norm(nrm) / 2 < 1e-4: return False
    return True

def run(path, out, prefabs, radius=1.0, grid=0.25, weld=0.75, log=print, verbose=False):
    m, meshes = load(path)
    for x in meshes:
        x['faces_of'] = collections.defaultdict(list)
        for loop in x['faces']:
            for k in loop: x['faces_of'][k].append(loop)
    pts = []
    for p in prefabs: pts += [v for x in load(p)[1] for v in x['w']]
    idx = Index(pts)
    log('%s: %d meshes, %d vertices; %d prefab vertices from %d prefab(s)' % (os.path.basename(path), len(meshes), sum(len(x['w']) for x in meshes), len(idx.pv), len(prefabs)))
    before = nearmiss(meshes, weld); log('before: %d near-miss vertex pairs across meshes (closer than %g)' % (sum(before.values()), weld))
    moved = collections.Counter(); how = collections.Counter(); skipped = [0]; undone = [0]
    def move(x, k, tgt, rule):
        if not x['plain']: skipped[0] += 1; return False
        old = x['w'][k].copy(); x['w'][k] = np.array(tgt, float)
        if not face_ok(x, k): x['w'][k] = old; undone[0] += 1; return False
        moved[x['n']] += 1; how[rule] += 1; return True
    # pass 1: prefab / grid
    for x in meshes:
        for k, v in enumerate(x['w']):
            c, d, g = idx.within(v, radius) if len(idx.pv) else (np.zeros((0, 3)), np.zeros(0), np.zeros(0, bool))
            if len(d) and d.min() < 1e-3: continue
            if g.any():
                i = int(np.argmin(np.where(g, d, np.inf))); move(x, k, c[i], 'prefab grid vertex'); continue
            gp = np.array([round(c_) if 1e-3 < abs(c_ - round(c_)) < grid else c_ for c_ in v]); dg = np.linalg.norm(gp - v)
            if dg > 1e-3: move(x, k, gp, 'grid point'); continue
            if len(d):
                o = np.argsort(d)
                if len(o) == 1 or d[o[1]] >= max(2 * d[o[0]], d[o[0]] + 0.25): move(x, k, c[o[0]], 'nearest prefab vertex')
    # pass 2: weld across meshes
    allv = sorted((tuple(v), x['n'], k) for x in meshes for k, v in enumerate(x['w'])); bym = {x['n']: x for x in meshes}
    for i, (v, n, k) in enumerate(allv):
        j = i + 1
        while j < len(allv) and allv[j][0][0] - v[0] < weld:
            u, n2, k2 = allv[j]; j += 1
            if n2 == n: continue
            a, b = bym[n], bym[n2]; va, vb = a['w'][k], b['w'][k2]; d = np.linalg.norm(va - vb)
            if d <= 1e-3 or d >= weld: continue
            tgt = []; rule = 'welded to grid vertex'
            for ca, cb in zip(va, vb):                 # per axis: the integer side wins; neither integer: the mesh with more faces
                if abs(ca - cb) < 1e-3: tgt.append(ca); continue
                ia, ib = abs(ca - round(ca)) < 1e-3, abs(cb - round(cb)) < 1e-3
                if ia and not ib: tgt.append(ca)
                elif ib and not ia: tgt.append(cb)
                elif not ia and not ib: tgt.append(ca if a['nf'] >= b['nf'] else cb); rule = 'welded off-grid pair'
                else: tgt = None; break                # two different grid values: real geometry
            if tgt is None: continue
            tgt = np.array(tgt)
            if np.linalg.norm(tgt - va) > 1e-3: move(a, k, tgt, rule)
            if np.linalg.norm(tgt - vb) > 1e-3: move(b, k2, tgt, rule)
    after = nearmiss(meshes, weld, 25 if verbose else 0, log)
    log('moved %d vertices in %d meshes (%s); %d moves undone because a face would lose its area; %d vertices of rotated/scaled/displacement meshes left' % (
        sum(moved.values()), sum(1 for c in moved.values() if c), ', '.join('%d %s' % (c, r) for r, c in how.most_common()), undone[0], skipped[0]))
    log('after: %d near-miss vertex pairs across meshes' % sum(after.values()))
    top = after.most_common(8)
    if top: log('  remaining, by mesh pair (node ids): ' + ', '.join('%d-%d: %d' % (k[0], k[1], c) for k, c in top))
    log('  most-changed meshes: ' + ', '.join('%d faces (node %d): %d verts' % (bym[n]['nf'], n, c) for n, c in moved.most_common(8) if c))
    if out:
        changed = 0
        for x in meshes:
            if not x['plain'] or not moved[x['n']]: continue
            for k, v in enumerate(x['w']):
                if np.linalg.norm(v - x['orig'][k]) > 1e-9:
                    x['pos'][k] = [float(v[0] - x['o'][0]), float(v[1] - x['o'][1]), float(v[2] - x['o'][2])]; changed += 1
        m.save(out); log('wrote %s (%d vertex positions changed, nothing else)' % (out, changed))
    return sum(before.values()), sum(after.values())

if __name__ == '__main__':
    a = sys.argv[1:]; prefabs = []; opts = {}
    while '--prefab' in a:
        i = a.index('--prefab'); prefabs.append(a[i + 1]); del a[i:i + 2]
    for key in ('radius', 'grid', 'weld'):
        if '--' + key in a:
            i = a.index('--' + key); opts[key] = float(a[i + 1]); del a[i:i + 2]
    if '--verbose' in a: a.remove('--verbose'); opts['verbose'] = True
    run(a[0], a[1] if len(a) > 1 else None, prefabs, **opts)
