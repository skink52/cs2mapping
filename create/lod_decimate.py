"""Faithful LODs for static props: LOD1..LOD4 decimated from LOD0 itself (vertex clustering with a quadric per cell; corners keep their
face's normal and get UVs re-projected through the face's own UV mapping, so tiled stock textures and hard edges hold). A swap moves
the surface by about a cell at most; each level's cell is the largest that stays within its error budget (MAX_CELL, about a pixel at the
distance it switches in) while aiming for TARGET of LOD0's triangles. Thresholds 20/60/120/240 (ModelDoc's default scale; 20 was where
the old unfaithful LOD1 pops were seen at ~300 u).
Why: tw22-24 pushed every switch 16x out (LOD_SCALE) because the old generated LOD1s weren't copies of LOD0, so the map drew ~18M
triangles of LOD0 props whenever you looked across no man's land.
Props whose geometry is thinner than a cell (barbed wire) keep their generated LOD1 (`--keep-lod1`), switched at 30.
usage: python3 tools/lod_decimate.py <addon root> <out root> <model dir under models/> [...] [--keep-lod1 name,name]
       writes <out>/models/.../<name>_lod1d.smd, _lod2d.smd and the rewritten <name>.vmdl"""
import os, re, sys
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

THRESH = (20.0, 60.0, 120.0, 240.0)
MAX_CELL = (0.5, 1.6, 3.2, 6.5)
TARGET = (0.35, 0.12, 0.04, 0.015)
KEEP_THRESH = 30.0
MIN_GAIN = 0.8          # a LOD must have at most this share of the previous LOD's triangles, else it's left out


def read_smd(path):
    head, mats, rows = [], [], []
    with open(path) as f:
        lines = f.read().split('\n')
    i = lines.index('triangles'); head = lines[:i + 1]; i += 1
    while i < len(lines) and lines[i].strip() != 'end':
        mat = lines[i].strip()
        for k in range(3):
            v = lines[i + 1 + k].split()
            rows.append([float(x) for x in v[1:9]]); mats.append(mat)
        i += 4
    A = np.array(rows).reshape(-1, 3, 8)
    return head, np.array(mats).reshape(-1, 3)[:, 0], A


def weld_pos(A, fm):
    """per-corner rows -> shared positions per material (UV and normal seams ignored: corners keep their own normal, UVs are
    re-projected). Materials never merge, so decal quads keep their offset from the surface under them (no z-fighting)."""
    C = A.reshape(-1, 8); M = np.repeat(fm, 3)
    _, first, inv = np.unique(np.concatenate([np.round(C[:, :3], 3), M[:, None]], 1), axis=0, return_index=True, return_inverse=True)
    return C[first, :3], inv.ravel().reshape(-1, 3), M[first]


def cluster(P, F, A, fm, cell, VM):
    """P: welded positions, F: faces into P, A: original per-corner rows [nf,3,8], fm: face material, VM: vertex material"""
    q = np.floor((P - P.min(0)) / cell).astype(np.int64)
    _, cid = np.unique(np.concatenate([q, VM[:, None]], 1), axis=0, return_inverse=True); cid = cid.ravel(); nc = cid.max() + 1
    a, b, c = P[F[:, 0]], P[F[:, 1]], P[F[:, 2]]
    nrm = np.cross(b - a, c - a); area = np.linalg.norm(nrm, axis=1)
    nrm = nrm / np.maximum(area, 1e-12)[:, None]; dd = -(nrm * a).sum(1)
    Q = np.zeros((nc, 3, 3)); bq = np.zeros((nc, 3))
    for k in range(3):
        cc = cid[F[:, k]]
        np.add.at(Q, cc, area[:, None, None] * nrm[:, :, None] * nrm[:, None, :])
        np.add.at(bq, cc, -(area * dd)[:, None] * nrm)
    cnt = np.bincount(cid, minlength=nc).astype(float)
    mean = np.zeros((nc, 3)); np.add.at(mean, cid, P); mean /= cnt[:, None]
    reg = (np.trace(Q, axis1=1, axis2=2) * 0.05 + 1e-9)[:, None, None] * np.eye(3)
    NP = np.linalg.solve(Q + reg, (bq + reg[:, 0, 0][:, None] * mean)[..., None])[..., 0]
    NP = mean + np.clip(NP - mean, -cell * 0.75, cell * 0.75)
    NF = cid[F]
    keep = (NF[:, 0] != NF[:, 1]) & (NF[:, 1] != NF[:, 2]) & (NF[:, 2] != NF[:, 0])
    idx = np.nonzero(keep)[0]
    _, u = np.unique(np.sort(NF[idx], 1), axis=0, return_index=True); idx = idx[np.sort(u)]
    # new triangle per surviving original face: positions from the clusters, each corner keeps the face's own normal,
    # UVs re-projected through the face's own (planar) UV mapping, so tiled stock textures stay at their scale
    out_P = NP[NF[idx]]                                          # [m,3,3]
    o = A[idx]; p0, p1, p2 = o[:, 0, :3], o[:, 1, :3], o[:, 2, :3]
    e1, e2 = p1 - p0, p2 - p0
    d11 = (e1 * e1).sum(1); d12 = (e1 * e2).sum(1); d22 = (e2 * e2).sum(1); den = d11 * d22 - d12 * d12
    den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    UVo = o[:, :, 6:8]; out_UV = np.zeros((len(idx), 3, 2))
    for k in range(3):
        r = out_P[:, k] - p0; r1 = (r * e1).sum(1); r2 = (r * e2).sum(1)
        w1 = (d22 * r1 - d12 * r2) / den; w2 = (d11 * r2 - d12 * r1) / den; w0 = 1 - w1 - w2
        out_UV[:, k] = w0[:, None] * UVo[:, 0] + w1[:, None] * UVo[:, 1] + w2[:, None] * UVo[:, 2]
    out_N = o[:, :, 3:6]
    fn = np.cross(out_P[:, 1] - out_P[:, 0], out_P[:, 2] - out_P[:, 0])
    ok = (fn * out_N.sum(1)).sum(1) > 1e-9                       # drop faces that flipped or collapsed
    return out_P[ok], out_N[ok], out_UV[ok], fm[idx][ok], NP


def write_smd(path, head, mats, P, N, UV, fmat):
    out = list(head)
    for f in range(len(P)):
        out.append(mats[fmat[f]])
        for k in range(3):
            out.append('0 %.4f %.4f %.4f %.4f %.4f %.4f %.5f %.5f' % (P[f, k, 0], P[f, k, 1], P[f, k, 2], N[f, k, 0], N[f, k, 1], N[f, k, 2], UV[f, k, 0], UV[f, k, 1]))
    out.append('end'); out.append('')
    open(path, 'w', newline='\n').write('\n'.join(out))


def deviation(P0, F0, P1):
    """p95 distance from original vertices to the nearest decimated vertex (cheap proxy for surface error)"""
    from scipy.spatial import cKDTree
    d, _ = cKDTree(P1).query(P0)
    return float(np.percentile(d, 95))


def vmdl_rewrite(text, name, rel_dir, meshes, thresholds):
    rmf = ''
    for m in meshes:
        rmf += ('\t\t\t\t\t{\n\t\t\t\t\t\t_class = "RenderMeshFile"\n\t\t\t\t\t\tname = "%s"\n\t\t\t\t\t\tfilename = "%s/%s.smd"\n\t\t\t\t\t\timport_scale = 1.0\n'
                '\t\t\t\t\t\timport_filter =\n\t\t\t\t\t\t{\n\t\t\t\t\t\t\texclude_by_default = false\n\t\t\t\t\t\t\texception_list = [  ]\n\t\t\t\t\t\t}\n\t\t\t\t\t},\n') % (m, rel_dir, m)
    groups = ''
    for m, t in zip(meshes, thresholds):
        groups += ('\t\t\t\t\t{\n\t\t\t\t\t\t_class = "LODGroup"\n\t\t\t\t\t\tmesh_references =\n\t\t\t\t\t\t[\n\t\t\t\t\t\t\t{\n'
                   '\t\t\t\t\t\t\t\tmesh_name = "%s"\n\t\t\t\t\t\t\t\tcopy_and_simplify = false\n\t\t\t\t\t\t\t},\n\t\t\t\t\t\t]\n'
                   '\t\t\t\t\t\tswitch_threshold = %.1f\n\t\t\t\t\t},\n') % (m, t)
    rml = '\t\t\t{\n\t\t\t\t_class = "RenderMeshList"\n\t\t\t\tchildren =\n\t\t\t\t[\n%s\t\t\t\t]\n\t\t\t},\n' % rmf
    lgl = '\t\t\t{\n\t\t\t\t_class = "LODGroupList"\n\t\t\t\tchildren =\n\t\t\t\t[\n%s\t\t\t\t]\n\t\t\t},\n' % groups
    blk = lambda cls: re.compile(r'\t\t\t\{\n\t\t\t\t_class = "%s"\n.*?\n\t\t\t\},\n' % cls, re.S)
    assert blk('RenderMeshList').search(text), 'no RenderMeshList in ' + name
    text = blk('LODGroupList').sub('', text)
    return blk('RenderMeshList').sub(lambda m: rml + lgl, text, count=1)


def process(addon, out, mdir, keep):
    name = os.path.basename(mdir.rstrip('/'))
    src = os.path.join(addon, 'models', mdir); dst = os.path.join(out, 'models', mdir); os.makedirs(dst, exist_ok=True)
    rel = 'models/' + mdir.strip('/')
    vm = open(os.path.join(src, name + '.vmdl')).read()
    l0 = name + '_lod0' if os.path.exists(os.path.join(src, name + '_lod0.smd')) else name
    head, fm_names, A = read_smd(os.path.join(src, l0 + '.smd'))
    mats = sorted(set(fm_names)); mi = {m: i for i, m in enumerate(mats)}; fm = np.array([mi[m] for m in fm_names])
    meshes, th, report = [l0], [0.0], ['lod0 %d' % len(A)]
    if name in keep:
        meshes.append(name + '_lod1'); th.append(KEEP_THRESH); report.append('lod1 kept')
    else:
        P, F, VM = weld_pos(A, fm)
        prev = len(F); lo = 0.05
        for k, (mc, t, tg) in enumerate(zip(MAX_CELL, THRESH, TARGET)):
            res = cluster(P, F, A, fm, mc, VM); cell = mc
            if len(res[0]) < tg * len(A):                        # budget allows more than needed: smallest cell that reaches the target
                a_, b_ = lo, mc
                for _ in range(10):
                    mid = (a_ * b_) ** 0.5; r = cluster(P, F, A, fm, mid, VM)
                    if len(r[0]) <= tg * len(A): b_, res, cell = mid, r, mid
                    else: a_ = mid
            OP, ON, OU, OM, NP = res; lo = cell
            if len(OP) > prev * MIN_GAIN: report.append('lod%d skipped (%d)' % (k + 1, len(OP))); continue
            mname = '%s_lod%dd' % (name, k + 1)
            write_smd(os.path.join(dst, mname + '.smd'), head, mats, OP, ON, OU, OM)
            meshes.append(mname); th.append(t); prev = len(OP)
            report.append('lod%d %d (%.0f%%, cell %.2f, p95 %.2f u)' % (k + 1, len(OP), 100.0 * len(OP) / len(A), cell, deviation(P, F, OP.reshape(-1, 3))))
    open(os.path.join(dst, name + '.vmdl'), 'w', newline='\n').write(vmdl_rewrite(vm, name, rel, meshes, th))
    print('%-28s %s' % (name, ', '.join(report)))


if __name__ == '__main__':
    args = sys.argv[1:]; keep = set()
    if '--keep-lod1' in args:
        i = args.index('--keep-lod1'); keep = set(args[i + 1].split(',')); del args[i:i + 2]
    addon, out = args[0], args[1]
    for d in args[2:]: process(addon, out, d, keep)
