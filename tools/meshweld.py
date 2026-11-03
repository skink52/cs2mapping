"""Close hairline gaps between the meshes of a collapsed map. Vertices that drifted off the grid (Hammer edits on uncollapsed prefab
geometry: ba_jail_skylight 3 Nov 2026, floors 0.125 high, walls 0.035 low, trims anywhere in between) are put back where the prefab
or the integer grid has them, vertices of different meshes that almost touch are welded to one position, and the sliver faces
that spanned the gap (a 0.125-tall skirt all round a floor) are dropped once their corners coincide.

  python meshweld.py <map.vmap> [<out.vmap>] [--prefab <prefab.vmap>]... [--radius 1.0] [--grid 0.25] [--weld 0.75] [--verbose]

Per vertex, first match wins: (1) already on a prefab vertex: untouched. (2) a prefab vertex on the integer grid within --radius.
(3) each coordinate within --grid of an integer goes onto it (the others stay: a diagonal wall's y is meant to be off grid).
(4) the nearest prefab vertex within --radius when no other prefab vertex is nearly as close. Then across meshes, for two vertices
closer than --weld, per coordinate: the integer side wins; two different integers are real geometry (the pair is left); neither
integer and closer than --grid/2, the bigger mesh wins. Meshes are rebuilt from polygons (splitfaces.mesh_read / mesh_write):
a face left with under three distinct corners, no area, or a corner used twice (pinched) is dropped; a mesh the rebuild refuses (pinched / non-manifold) is left
as it was and listed. Rotated, scaled and displacement (subdivision) meshes are only read. Without <out.vmap> nothing is written.
Hammer must not have the map open when writing. The compile's own vertex welding does not close these gaps: 0.035 is enough for
light to leak through a wall-floor join."""
import sys, os, math, bisect, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx, vmapedit as V
import splitfaces as SF
from vmapedit import xform

KEY = 3   # decimals when welding corners of one mesh into a vertex (same as splitfaces)

def world_origins(m):
    O = {}
    def walk(i, o):
        for c in m.children(i):
            p = m.g(c, b'origin', [0, 0, 0]); w = (o[0] + p[0], o[1] + p[1], o[2] + p[2]); O[c] = w; walk(c, w)
    walk(m.world, (0.0, 0.0, 0.0)); return O

def load(path):
    """-> (Map, [mesh]); mesh = dict(n, nf, o, plain, polys, verts{key: world ndarray}, corners{key: [corner dict]})"""
    m = V.Map(path); O = world_origins(m); meshes = []
    for n, p in m.walk():
        if m.type(n) != b'CMapMesh': continue
        md = m.g(n, b'meshData')
        if md is None or m.g(md, b'vertexData') is None: continue
        ang = m.g(n, b'angles', [0, 0, 0]); sc = m.g(n, b'scales', [1, 1, 1]); o = np.array(O[n], float)
        plain = not any(abs(a) > 1e-6 for a in ang) and not any(abs(s - 1) > 1e-6 for s in sc) and not SF.mesh_has_subdivision(m, n)
        try: polys, mats = SF.mesh_read(m, n)
        except Exception: continue
        verts, corners = {}, collections.defaultdict(list)
        for pl in polys:
            for c in pl['corners']:
                k = tuple(np.round(c['pos'], KEY))
                if k not in verts:
                    verts[k] = (c['pos'] + o) if plain else np.array(xform([c['pos'][0] * sc[0], c['pos'][1] * sc[1], c['pos'][2] * sc[2]], O[n], ang), float)
                corners[k].append(c)
        meshes.append(dict(n=n, nf=len(polys), o=o, plain=plain, polys=polys, verts=verts, corners=corners, orig={k: v.copy() for k, v in verts.items()}))
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
    """vertex pairs from different meshes closer than lim (and not coincident), counted by mesh pair"""
    allv = sorted((tuple(v), x['n']) for x in meshes for v in x['verts'].values())
    by = collections.Counter(); shown = 0
    for i, (v, n) in enumerate(allv):
        j = i + 1
        while j < len(allv) and allv[j][0][0] - v[0] < lim:
            u, n2 = allv[j]; j += 1
            if n2 != n and 1e-3 < math.dist(u, v) < lim:
                by[tuple(sorted((n, n2)))] += 1
                if shown < samples: log('  left: %s (node %d) vs %s (node %d) d=%.3f' % (tuple(round(c, 3) for c in v), n, tuple(round(c, 3) for c in u), n2, math.dist(u, v))); shown += 1
    return by

def run(path, out, prefabs, radius=1.0, grid=0.25, weld=0.75, log=print, verbose=False):
    m, meshes = load(path)
    pts = []
    for p in prefabs: pts += [v for x in load(p)[1] for v in x['verts'].values()]
    idx = Index(pts)
    log('%s: %d meshes, %d vertices; %d prefab vertices from %d prefab(s)' % (os.path.basename(path), len(meshes), sum(len(x['verts']) for x in meshes), len(idx.pv), len(prefabs)))
    before = nearmiss(meshes, weld); log('before: %d near-miss vertex pairs across meshes (closer than %g)' % (sum(before.values()), weld))
    moved = collections.Counter(); how = collections.Counter(); skipped = [0]
    def move(x, k, tgt, rule):
        if not x['plain']: skipped[0] += 1; return False
        x['verts'][k] = np.array(tgt, float); moved[x['n']] += 1; how[rule] += 1; return True
    # pass 1: prefab / grid
    for x in meshes:
        for k, v in list(x['verts'].items()):
            c, d, g = idx.within(v, radius) if len(idx.pv) else (np.zeros((0, 3)), np.zeros(0), np.zeros(0, bool))
            if len(d) and d.min() < 1e-3: continue
            if g.any():
                i = int(np.argmin(np.where(g, d, np.inf))); move(x, k, c[i], 'prefab grid vertex'); continue
            gp = np.array([round(c) if 1e-3 < abs(c - round(c)) < grid else c for c in v]); dg = np.linalg.norm(gp - v)
            if dg > 1e-3: move(x, k, gp, 'grid point'); continue
            if len(d):
                o = np.argsort(d)
                if len(o) == 1 or d[o[1]] >= max(2 * d[o[0]], d[o[0]] + 0.25): move(x, k, c[o[0]], 'nearest prefab vertex')
    # pass 2: weld across meshes
    allv = sorted((tuple(v), x['n'], k) for x in meshes for k, v in x['verts'].items()); bym = {x['n']: x for x in meshes}
    for i, (v, n, k) in enumerate(allv):
        j = i + 1
        while j < len(allv) and allv[j][0][0] - v[0] < weld:
            u, n2, k2 = allv[j]; j += 1
            if n2 == n: continue
            a, b = bym[n], bym[n2]; va, vb = a['verts'][k], b['verts'][k2]; d = np.linalg.norm(va - vb)
            if d <= 1e-3 or d >= weld: continue
            tgt = []; rule = 'welded to grid vertex'
            for ca, cb in zip(va, vb):                 # per axis: the integer side wins; neither integer: the bigger mesh, if close
                if abs(ca - cb) < 1e-3: tgt.append(ca); continue
                ia, ib = abs(ca - round(ca)) < 1e-3, abs(cb - round(cb)) < 1e-3
                if ia and not ib: tgt.append(ca)
                elif ib and not ia: tgt.append(cb)
                elif not ia and not ib and abs(ca - cb) < grid / 2: tgt.append(ca if a['nf'] >= b['nf'] else cb); rule = 'welded off-grid pair'
                else: tgt = None; break                # two distinct grid values, or too far apart off grid: real geometry
            if tgt is None: continue
            tgt = np.array(tgt)
            if np.linalg.norm(tgt - va) > 1e-3: move(a, k, tgt, rule)
            if np.linalg.norm(tgt - vb) > 1e-3: move(b, k2, tgt, rule)
    # rebuild the changed meshes
    dropped = 0; pinched = 0; refused = []; rebuilt = 0
    for x in meshes:
        if not x['plain'] or not moved[x['n']]: continue
        for k, cs in x['corners'].items():
            for c in cs: c['pos'] = x['verts'][k] - x['o']
        keep = []
        for pl in x['polys']:
            ids = []
            for c in pl['corners']:
                kk = tuple(np.round(c['pos'], KEY))
                if not ids or ids[-1] != kk: ids.append(kk)
            if len(ids) > 1 and ids[0] == ids[-1]: ids.pop()
            if len(ids) < 3 or SF.poly_area(pl['corners']) < 1e-4: dropped += 1; continue
            if len(set(ids)) != len(ids): pinched += 1; continue
            keep.append(pl)
        err = SF.mesh_write(m, x['n'], keep, duplicate_edges=True) if keep else 'every face dropped'
        if err:
            refused.append('%d faces (node %d): %s' % (x['nf'], x['n'], err))
            for k, v in x['orig'].items(): x['verts'][k] = v.copy()
            for k, cs in x['corners'].items():
                for c in cs: c['pos'] = x['orig'][k] - x['o']
            if keep: SF.mesh_write(m, x['n'], x['polys'], duplicate_edges=True)
            moved[x['n']] = 0
        else:
            rebuilt += 1
            bad = SF.mesh_check(m, x['n'])
            if bad: refused.append('%d faces (node %d) rebuilt with problems: %s' % (x['nf'], x['n'], '; '.join(bad)))
    after = nearmiss(meshes, weld, 25 if verbose else 0, log)
    log('moved %d vertices in %d meshes (%s); %d sliver faces dropped, %d pinched faces dropped; %d meshes rebuilt; %d vertices of rotated/scaled/displacement meshes left' % (
        sum(moved.values()), sum(1 for c in moved.values() if c), ', '.join('%d %s' % (c, r) for r, c in how.most_common()), dropped, pinched, rebuilt, skipped[0]))
    for r in refused: log('  left as it was: ' + r)
    log('after: %d near-miss vertex pairs across meshes' % sum(after.values()))
    top = after.most_common(8)
    if top: log('  remaining, by mesh pair (node ids): ' + ', '.join('%d-%d: %d' % (k[0], k[1], c) for k, c in top))
    log('  most-changed meshes: ' + ', '.join('%d faces (node %d): %d verts' % (bym[n]['nf'], n, c) for n, c in moved.most_common(8) if c))
    if out:
        m.save(out); log('wrote ' + out)
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
