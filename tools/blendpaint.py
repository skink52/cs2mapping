"""Blend paint for displacements: CS:GO displacement vertex alphas (WorldVertexTransition layer B) -> VertexPaintBlendParams on the CS2 meshes.

  python blendpaint.py <vmap in> <vmf> <vmap out> [--content <addon content root>] [--force] [--compare]

Valve's importer keeps the alphas on the displacements it imports as subdivision meshes (ba_jail_keimusho: 439 meshes painted in the
subdivisionData stream, 23 Nov 2026). It loses them where the displacement never came through and `disprestore.py` rebuilt it from the BSP
as a plain mesh (mg_pirates, ttt_island17, mg_crash_bandicoot_course: every blend displacement unpainted). This pass reads the alphas from
the VMF and paints:
  plain meshes        (disprestore output) the face-vertex stream, matched by vertex position to the displaced grid of the same material
  subdivision meshes  only when their subdivisionData paint is missing or all zero: each subdivision vertex gets the alpha at its place on
                      the displacement grid (through the texture coordinates, which are affine in the flat face position in both engines)
Values are alpha/255 in all four channels, as the importer writes them. Paint that is already there (importer's, or skink52's Hammer
edits) is never overwritten unless --force. --compare paints nothing: it reports how far its own values are from the paint the
importer wrote (the check of the method). Meshes that are rotated or scaled are skipped.
With --content it also reports blend materials whose .vmat has one layer (the `assets` pass rebuilds a missing WorldVertexTransition
material as single-layer csgo_complex): paint shows only on a two-layer material (csgo_lightmappedgeneric F_LAYERS 1, as the importer
writes, or a Valve blend shader).

The displacement grid and the subdivision-patch layout are from CS2-Porter blend.py (MIT, copyright bcanusar), adapted to this
pipeline's vmapedit / vmf model. Stage step / run_pass name: `blendpaint` (after disprestore).
"""
import argparse, collections, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import dmx, vmf as vmfmod, vmapedit as V

STREAM = b'VertexPaintBlendParams:0'
TOL = 0.75


# ---------------------------------------------------------------- VMF side (from CS2-Porter blend.py, MIT, copyright bcanusar), adapted
def _plane_pts(text):
    pts = re.findall(r'\(([^)]*)\)', text or '')
    try:
        P = [np.array([float(v) for v in p.split()]) for p in pts]
    except ValueError:
        return None
    return P if len(P) == 3 and all(len(p) == 3 for p in P) else None


def _polygon(planes, k):
    """face polygon of plane k of a convex brush: a big square on the plane clipped by the other (outward) planes"""
    n, d = planes[k]
    ref = np.array([0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(n, ref); u /= np.linalg.norm(u); v = np.cross(n, u); c = n * d; big = 131072.0
    poly = [c + u * su * big + v * sv * big for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for j, (pn, pd) in enumerate(planes):
        if j == k or not poly: continue
        out = []
        for i, a in enumerate(poly):
            b = poly[(i + 1) % len(poly)]
            da, db = pn @ a - pd, pn @ b - pd
            if da <= 0.01: out.append(a)
            if (da < -0.01 and db > 0.01) or (da > 0.01 and db < -0.01): out.append(a + (b - a) * (da / (da - db)))
        poly = out
    clean = []
    for p in poly:
        if not clean or np.abs(p - clean[-1]).max() > 0.05: clean.append(p)
    if len(clean) > 1 and np.abs(clean[0] - clean[-1]).max() <= 0.05: clean.pop()
    return clean


def _rows(node, name, width):
    blk = next((x for x in node.ch if x.name == name), None)
    if blk is None: return None
    out = []
    for i in range(4096):
        r = blk.get('row%d' % i)
        if r is None: break
        try: vals = [float(v) for v in r.split()]
        except ValueError: return None
        if len(vals) != width: return None
        out.append(vals)
    return out


def norm_mat(s):
    s = (s or '').replace('\\', '/').strip().lower()
    if s.startswith('materials/'): s = s[10:]
    if s.endswith('.vmat') or s.endswith('.vmt'): s = s.rsplit('.', 1)[0]
    return s.replace(' ', '_')


class Disp:
    """one displacement: n segments a side, alphas[i][j] (0..255), grids = the displaced (n+1)^2 positions under both corner orders"""
    def __init__(s, mat, n, alphas, grids):
        s.mat, s.n, s.alphas, s.grids = mat, n, np.asarray(alphas, float), grids

    def alpha(s, gi, gj):
        n = s.n; gi = min(max(gi, 0.0), n); gj = min(max(gj, 0.0), n)
        i0, j0 = min(int(gi), n - 1), min(int(gj), n - 1); fi, fj = gi - i0, gj - j0; a = s.alphas
        top = a[i0][j0] * (1 - fj) + a[i0][j0 + 1] * fj
        bot = a[i0 + 1][j0] * (1 - fj) + a[i0 + 1][j0 + 1] * fj
        return top * (1 - fi) + bot * fi

    def corners(s, h):
        g = s.grids[h]; n = s.n
        return {(0, 0): g[0, 0], (n, 0): g[n, 0], (n, n): g[n, n], (0, n): g[0, n]}


def _solids(root):
    for top in root.ch:
        if top.name not in ('world', 'entity'): continue
        for x in top.ch:
            if x.name == 'solid': yield x
            elif x.name == 'hidden': yield from (y for y in x.ch if y.name == 'solid')


def vmf_disps(vmfpath, painted_only=True):
    """every displacement with an alpha above 0.5 (all of them with painted_only=False) -> [Disp]"""
    with open(vmfpath, encoding='utf-8', errors='replace') as fh: root = vmfmod.parse(fh.read())
    out = []
    for solid in _solids(root):
        sides = [x for x in solid.ch if x.name == 'side']
        if not any(any(y.name == 'dispinfo' for y in x.ch) for x in sides): continue
        pts = [_plane_pts(x.get('plane')) for x in sides]
        if any(p is None for p in pts): continue
        planes = []
        for p0, p1, p2 in pts:
            nrm = np.cross(p2 - p0, p1 - p0); ln = np.linalg.norm(nrm)
            if ln < 1e-9: break
            nrm = nrm / ln; planes.append([nrm, float(nrm @ p0)])
        if len(planes) != len(sides): continue
        mid = np.mean([p for tri in pts for p in tri], axis=0)
        for pl in planes:
            if pl[0] @ mid - pl[1] > 0: pl[0] = -pl[0]; pl[1] = -pl[1]
        for k, side in enumerate(sides):
            di = next((y for y in side.ch if y.name == 'dispinfo'), None)
            if di is None: continue
            try:
                n = 1 << int(di.get('power', '3')); start = np.array([float(v) for v in (di.get('startposition') or '').strip('[] ').split()])
                elev = float(di.get('elevation', '0') or 0)
            except ValueError: continue
            w = n + 1
            alphas = _rows(di, 'alphas', w) or [[0.0] * w] * w
            if len(alphas) != w or (painted_only and not any(v > 0.5 for r in alphas for v in r)): continue
            normals = _rows(di, 'normals', 3 * w); dists = _rows(di, 'distances', w)
            offsets = _rows(di, 'offsets', 3 * w) or [[0.0] * (3 * w)] * w
            poly = _polygon(planes, k)
            if not normals or not dists or len(normals) != w or len(dists) != w or len(offsets) != w or len(poly) != 4 or len(start) != 3: continue
            s0 = min(range(4), key=lambda i: float((poly[i] - start) @ (poly[i] - start)))
            N = np.array(normals).reshape(w, w, 3); D = np.array(dists).reshape(w, w, 1); O = np.array(offsets).reshape(w, w, 3)
            ii, jj = np.meshgrid(np.arange(w) / n, np.arange(w) / n, indexing='ij'); ii = ii[..., None]; jj = jj[..., None]
            grids = []
            # the grid's first index runs from the start corner against the polygon winding (CS2-Porter, checked on real maps);
            # the other order is kept too and the mesh decides which one fits
            for step in (-1, 1):
                c = [poly[(s0 + step * q) % 4] for q in range(4)]
                base = (c[0] + (c[1] - c[0]) * ii) * (1 - jj) + (c[3] + (c[2] - c[3]) * ii) * jj
                grids.append(base + N * D + O + planes[k][0] * elev)
            out.append(Disp(norm_mat(side.get('material')), n, alphas, grids))
    return out


# ---------------------------------------------------------------- vmap side
class _PointIndex:
    """displaced grid positions -> (disp id, hypothesis, i, j)"""
    def __init__(s, disps, cell=4.0):
        s.cell = cell; s.g = collections.defaultdict(list)
        for di, d in enumerate(disps):
            for h, G in enumerate(d.grids):
                for i in range(d.n + 1):
                    for j in range(d.n + 1):
                        s.g[s._k(G[i, j])].append((di, h, i, j, G[i, j]))

    def _k(s, p): return tuple(int(math.floor(v / s.cell)) for v in p)

    def near(s, p, tol=TOL):
        kx, ky, kz = s._k(p)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for e in s.g.get((kx + dx, ky + dy, kz + dz), ()):
                        if np.abs(e[4] - p).max() <= tol: yield e


def _offset(m, par, nd):
    """world offset of a mesh's local coordinates (its origin + group origins), None when it is rotated or scaled"""
    if any(abs(x) > 1e-4 for x in m.g(nd, b'angles', [0, 0, 0])) or any(abs(x - 1) > 1e-4 for x in m.g(nd, b'scales', [1, 1, 1])): return None
    off = np.array(m.g(nd, b'origin', [0, 0, 0]), float); q = par.get(nd)
    while q is not None:
        if m.type(q) == b'CMapGroup':
            if any(abs(x) > 1e-4 for x in m.g(q, b'angles', [0, 0, 0])) or any(abs(x - 1) > 1e-4 for x in m.g(q, b'scales', [1, 1, 1])): return None
            off = off + np.array(m.g(q, b'origin', [0, 0, 0]), float)
        q = par.get(q)
    return off


def _streams(m, el):
    return {m.E[s]['name']: s for s in (m.g(el, b'streams') or [])} if el is not None else {}


def _new_stream(m, location, flags, data, binding):
    b = m.new_el(b'CDmePolygonMeshSubdivisiondataBinding', [[b'targetDataType', dmx.T_INT, 3], [b'targetStreamIndex', dmx.T_INT, 0],
                                                            [b'streamSourceType', dmx.T_INT, 0]], name=b'subdivisionBinding') if binding else -1
    return m.new_el(b'CDmePolygonMeshDataStream', [
        [b'standardAttributeName', dmx.T_STR, b''], [b'semanticName', dmx.T_STR, b'VertexPaintBlendParams'], [b'semanticIndex', dmx.T_INT, 0],
        [b'vertexBufferLocation', dmx.T_INT, location], [b'dataStateFlags', dmx.T_INT, flags], [b'subdivisionBinding', dmx.T_ELEM, b],
        [b'data', dmx.ARR + dmx.T_V4, data]], name=STREAM)


def _put(m, arr_el, location, flags, data, binding):
    st = _streams(m, arr_el)
    if STREAM in st: dmx.set_(m.E[st[STREAM]], b'data', dmx.ARR + dmx.T_V4, data)
    else: dmx.geta(m.E[arr_el], b'streams')[2].append(_new_stream(m, location, flags, data, binding))


def _nonzero(m, s): return s is not None and any(any(abs(x) > 1e-4 for x in v) for v in m.g(s, b'data') or [])


def _inv_bilinear(p, q):
    """(s, t) with p = bilinear(q00, q10, q11, q01) (CS2-Porter blend.py)"""
    s = t = 0.5
    for _ in range(12):
        x = [(1 - s) * (1 - t) * q[0][k] + s * (1 - t) * q[1][k] + s * t * q[2][k] + (1 - s) * t * q[3][k] - p[k] for k in (0, 1)]
        ds = [(1 - t) * (q[1][k] - q[0][k]) + t * (q[2][k] - q[3][k]) for k in (0, 1)]
        dt = [(1 - s) * (q[3][k] - q[0][k]) + s * (q[2][k] - q[1][k]) for k in (0, 1)]
        det = ds[0] * dt[1] - ds[1] * dt[0]
        if abs(det) < 1e-12: break
        s -= (x[0] * dt[1] - x[1] * dt[0]) / det; t -= (ds[0] * x[1] - ds[1] * x[0]) / det
    return min(max(s, 0.0), 1.0), min(max(t, 0.0), 1.0)


def _v4(a): a = round(float(a) / 255.0, 6); return [a, a, a, a]


def _mesh(m, md):
    g = lambda k: m.g(md, k) or []
    return dict(vdi=g(b'vertexDataIndices'), evi=g(b'edgeVertexIndices'), eni=g(b'edgeNextIndices'), efi=g(b'edgeFaceIndices'),
                evd=g(b'edgeVertexDataIndices'), fei=g(b'faceEdgeIndices'), fdi=g(b'faceDataIndices'),
                mats=[norm_mat(x.decode('utf-8', 'replace')) for x in g(b'materials')])


def _loops(M):
    out = []
    for f, e0 in enumerate(M['fei']):
        loop, e = [], e0
        for _ in range(256):
            loop.append(e); e = M['eni'][e]
            if e == e0: break
        out.append(loop)
    return out


def paint_plain(m, nd, off, disps, pidx, mats_ok, st, force=False):
    md = m.g(nd, b'meshData'); M = _mesh(m, md)
    fvd = m.g(md, b'faceVertexData'); fv = _streams(m, fvd)
    if _nonzero(m, fv.get(STREAM)) and not force: st['kept'] += 1; return 0
    pos = m.g(_streams(m, m.g(md, b'vertexData')).get(b'position:0'), b'data')
    mi = m.g(_streams(m, m.g(md, b'faceData')).get(b'materialindex:0'), b'data')
    if pos is None: return 0
    size = m.g(fvd, b'size') or len(M['evd'])
    vals = [[0.0, 0.0, 0.0, 0.0] for _ in range(size)]
    painted = 0
    for f, loop in enumerate(_loops(M)):
        j = mi[M['fdi'][f]] if mi is not None and f < len(M['fdi']) else 0
        mat = M['mats'][j] if 0 <= j < len(M['mats']) else ''
        if mat.startswith('tools/') or (mats_ok is not None and mat not in mats_ok): continue
        P = [np.array(pos[M['vdi'][M['evi'][e]]], float) + off for e in loop]
        cand = collections.defaultdict(dict)
        for k, p in enumerate(P):
            for di, h, i, jj, _q in pidx.near(p): cand[(di, h)].setdefault(k, (i, jj))
        if not cand: continue
        best = max(cand, key=lambda dh: (len(cand[dh]), disps[dh[0]].mat == mat))
        if len(cand[best]) < len(P): continue
        d = disps[best[0]]
        for k, e in enumerate(loop):
            i, jj = cand[best][k]; vals[M['evd'][e]] = _v4(d.alphas[i][jj])
        painted += 1
    if not painted or not any(v[0] > 1e-6 for v in vals): return 0
    _put(m, fvd, 1, 1, vals, False)
    st['plain_faces'] += painted; st['plain_meshes'] += 1
    return painted


def paint_subdiv(m, nd, off, by_mat, corner_idx, st, force=False, compare=False):
    """CS2-Porter's method: subdivision vertex -> its (s, t) inside the face through the texture coordinates -> displacement alpha"""
    md = m.g(nd, b'meshData'); M = _mesh(m, md)
    sd = m.g(md, b'subdivisionData'); sds = _streams(m, sd)
    has = _nonzero(m, sds.get(STREAM))
    if has and not force and not compare: st['kept'] += 1; return 0
    if compare and not has: return 0
    fvd = m.g(md, b'faceVertexData'); fv = _streams(m, fvd)
    pos = m.g(_streams(m, m.g(md, b'vertexData')).get(b'position:0'), b'data')
    tc = m.g(fv.get(b'texcoord:0'), b'data'); sub_tc = m.g(sds.get(b'texcoord:0'), b'data')
    mi = m.g(_streams(m, m.g(md, b'faceData')).get(b'materialindex:0'), b'data')
    levels = m.g(sd, b'subdivisionLevels') or []
    if not (pos and tc and sub_tc and levels): return 0
    faces, lv_of = {}, {}
    for f, loop in enumerate(_loops(M)):
        lv_of[f] = max((levels[M['evd'][e]] for e in loop if M['evd'][e] < len(levels)), default=0)
        if lv_of[f] <= 0 or len(loop) != 4: continue
        j = mi[M['fdi'][f]] if mi is not None and f < len(M['fdi']) else 0
        mat = M['mats'][j] if 0 <= j < len(M['mats']) else ''
        cs = [np.array(pos[M['vdi'][M['evi'][e]]], float) + off for e in loop]
        best = None
        for di in corner_idx(np.mean(cs, axis=0), mat):
            d = by_mat[di]
            for h in range(2):
                hc = d.corners(h); assign = {}; err = 0.0
                for k, p in enumerate(cs):
                    ij, e2 = min(((ij, float(np.abs(p - q).max())) for ij, q in hc.items()), key=lambda x: x[1])
                    assign[k] = ij; err = max(err, e2)
                if err <= 2.0 and len(set(assign.values())) == 4 and (best is None or err < best[0]): best = (err, d, assign)
        if best is None: st['subdiv_miss'] += 1; continue
        _, d, assign = best; n = d.n
        by_ij = {assign[k]: tc[M['evd'][e]][:2] for k, e in enumerate(loop)}
        faces[f] = (d, [by_ij[(0, 0)], by_ij[(n, 0)], by_ij[(n, n)], by_ij[(0, n)]])
    if not faces: return 0
    vals = [[0.0] * 4 for _ in sub_tc]; cursor = 0
    for e in sorted((e for e in range(len(M['efi'])) if M['efi'][e] >= 0), key=lambda e: M['evd'][e]):
        lv = lv_of.get(M['efi'][e], 0)
        if lv <= 0: continue
        side = (1 << (lv - 1)) + 1; blk = range(cursor, cursor + side * side); cursor += side * side
        face = faces.get(M['efi'][e])
        if face is None or cursor > len(sub_tc): continue
        d, q = face
        for r in blk:
            s_, t_ = _inv_bilinear(sub_tc[r][:2], q); vals[r] = _v4(d.alpha(s_ * d.n, t_ * d.n))
    if cursor != len(sub_tc): st['subdiv_layout'] += 1; return 0
    if compare:
        old = m.g(sds[STREAM], b'data')
        diff = [abs(a[0] - b[0]) for a, b in zip(vals, old)]
        st['cmp_values'] += len(diff); st['cmp_close'] += sum(x <= 0.02 for x in diff); st['cmp_max'] = max(st['cmp_max'], max(diff, default=0))
        return 0
    if not any(v[0] > 1e-6 for v in vals): return 0
    _put(m, sd, 0, 1, vals, False)
    fv_vals = m.g(fv.get(STREAM), b'data') if STREAM in fv else [[0.0] * 4 for _ in range(m.g(fvd, b'size') or len(M['evd']))]
    _put(m, fvd, 1, 1, fv_vals, True)   # the importer's form: a bound face-vertex stream (zeros), the values in subdivisionData
    st['subdiv_faces'] += len(faces); st['subdiv_meshes'] += 1
    return len(faces)


def vmat_layers(path):
    """1 or 2: how many blend layers a .vmat has (None when it can't be read)"""
    try:
        with open(path, encoding='utf-8', errors='replace') as fh: t = fh.read()
    except OSError: return None
    if re.search(r'"?F_LAYERS"?\s+"?[1-9]', t) or 'TextureLayer2Color' in t or re.search(r'shader\W+\S*blend', t, re.I): return 2
    return 1


def run(m, vmfpath, content=None, force=False, compare=False, log=None):
    disps = vmf_disps(vmfpath)
    st = collections.Counter(); st['cmp_max'] = 0.0
    if not disps: return st, []
    pidx = _PointIndex(disps)
    by_mat = disps
    cidx = collections.defaultdict(list)
    for di, d in enumerate(disps):
        c = d.grids[0][d.n // 2, d.n // 2]; cidx[tuple(int(math.floor(v / 64)) for v in c)].append(di)
    def corner_idx(p, mat):
        k = tuple(int(math.floor(v / 64)) for v in p)
        got = [di for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1) for di in cidx.get((k[0] + dx, k[1] + dy, k[2] + dz), ())]
        same = [di for di in got if disps[di].mat == mat]
        return same or got
    par = m.parent_of(); used = collections.Counter()
    for nd in list(par):
        if m.type(nd) != b'CMapMesh': continue
        md = m.g(nd, b'meshData')
        if md is None: continue
        off = _offset(m, par, nd)
        if off is None: continue
        sd = m.g(md, b'subdivisionData'); sub = sd is not None and bool(m.g(sd, b'streams'))
        if sub: k = paint_subdiv(m, nd, off, by_mat, corner_idx, st, force, compare)
        elif compare: continue
        else: k = paint_plain(m, nd, off, disps, pidx, None, st, force)
        if k:
            for x in m.g(md, b'materials') or []: used[norm_mat(x.decode('utf-8', 'replace'))] += 1
    single = []
    if content:
        for mat in sorted(used):
            if mat.startswith('tools/'): continue
            if vmat_layers(os.path.join(content, 'materials', mat + '.vmat')) == 1: single.append(mat)
    if log is not None and not compare:
        if st['plain_meshes'] or st['subdiv_meshes']:
            log.append('blendpaint: displacement alphas from the VMF -> VertexPaintBlendParams on %d restored (plain) meshes / %d faces and %d subdivision meshes / %d faces%s'
                       % (st['plain_meshes'], st['plain_faces'], st['subdiv_meshes'], st['subdiv_faces'], (' (%d meshes already painted, kept)' % st['kept']) if st['kept'] else ''))
    return st, single


def main(argv=None):
    ap = argparse.ArgumentParser(description='displacement vertex alphas from the VMF -> VertexPaintBlendParams')
    ap.add_argument('vmap'); ap.add_argument('vmf'); ap.add_argument('out', nargs='?')
    ap.add_argument('--content', help='addon content root: report blend materials whose vmat has one layer')
    ap.add_argument('--force', action='store_true', help='overwrite paint that is already there')
    ap.add_argument('--compare', action='store_true', help='paint nothing; compare with the paint the importer wrote')
    a = ap.parse_args(argv)
    if not a.compare and not a.out: ap.error('give <vmap out> (or --compare)')
    m = V.Map(a.vmap); log = []
    st, single = run(m, a.vmf, a.content, a.force, a.compare, log)
    if a.compare:
        print('compare: %d subdivision values, %d within 0.02 of the importer\'s, largest difference %.4f' % (st['cmp_values'], st['cmp_close'], st['cmp_max']))
        return 0
    for l in log: print(l)
    print('stats:', dict((k, v) for k, v in st.items() if v))
    if single: print('TO CHECK: single-layer vmat, paint has no effect until it is a two-layer blend: ' + ', '.join(single))
    if st['plain_meshes'] or st['subdiv_meshes']:
        m.prune(); print('wrote', a.out, m.save(a.out), 'bytes')
    else: print('nothing painted, %s not written' % a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
