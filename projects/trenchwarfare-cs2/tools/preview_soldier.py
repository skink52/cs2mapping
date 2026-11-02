"""Contact sheet for a converted soldier: bind pose coloured by main bone over the CS2 joints (front, side) and a test pose
(elbows, knees, wrists, fingers bent by skinning on the CS2 skeleton) to catch bad weights."""
import numpy as np
from PIL import Image, ImageDraw

def rot(axis, deg):
    a = np.radians(deg); axis = np.asarray(axis, float) / np.linalg.norm(axis)
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K

def pose_matrices(T, bends):
    """world (R, t) per joint after rotating each named joint by (axis, deg) about itself (parents first)"""
    names = list(T.W)
    M = {n: (np.eye(3), np.zeros(3)) for n in names}
    parent = {}
    import dmx9
    dm = dmx9.DMX.load(T.body)
    def walk(j, p):
        parent[j.name] = p
        for c in j['children'] or []:
            if c.type == 'DmeJoint': walk(c, j.name)
    for c in dm.root['skeleton']['children']:
        if c.type == 'DmeJoint': walk(c, None)
    order = []
    def depth(n): return 0 if parent.get(n) is None else 1 + depth(parent[n])
    for n in sorted(names, key=depth):
        R, t = (np.eye(3), np.zeros(3)) if parent.get(n) is None else M[parent[n]]
        if n in bends:
            ax, deg = bends[n]; p = T.J(n); Rb = rot(ax, deg)
            # new = R@(Rb@(x-p)+p)+t
            R2 = R @ Rb; t2 = R @ (p - Rb @ p) + t
            M[n] = (R2, t2)
        else:
            M[n] = (R, t)
    return M

def skin(V, W, M):
    out = np.zeros_like(V)
    for i, ws in enumerate(W):
        for b, w in ws:
            R, t = M[b]; out[i] += w * (R @ V[i] + t)
    return out

def splat(P, C, ax, ay, az, W=420, H=560, lo=None, sc=None):
    x, y, z = P @ ax, P @ ay, P @ az
    if lo is None: lo = np.array([x.min(), y.min()]); sc = min(W, H) * 0.9 / max(x.max() - x.min(), y.max() - y.min())
    px = ((x - lo[0]) * sc + W * 0.05).astype(int); py = (H - ((y - lo[1]) * sc + H * 0.05)).astype(int)
    ok = (px >= 0) & (px < W) & (py >= 0) & (py < H); o = np.argsort(z[ok])
    im = np.full((H, W, 3), 35, np.uint8); im[py[ok][o], px[ok][o]] = C[ok][o]
    return Image.fromarray(im), lo, sc

def sheet(T, V, F, W, path):
    bones = sorted({b for ws in W for b, _ in ws})
    rng = np.random.default_rng(3); pal = {b: rng.integers(60, 255, 3) for b in bones}
    C = np.array([pal[max(ws, key=lambda x: x[1])[0]] for ws in W], np.uint8)
    Pc = V[F].mean(1); Cc = C[F[:, 0]]
    X, Y, Z = np.eye(3)
    s = 0.6
    bends = {}
    for side, sg in (('L', 1), ('R', -1)):
        bends['arm_lower_' + side] = ((0, -sg, 0), -95)
        bends['arm_upper_' + side] = ((1, 0, 0), sg * 35)
        bends['leg_lower_' + side] = ((0, 1, 0), 70)
        bends['leg_upper_' + side] = ((0, 1, 0), -50)
        bends['hand_' + side] = ((0, 0, 1), 40)
        for f in ('index', 'middle', 'ring', 'pinky'):
            for k in (0, 1, 2): bends['finger_%s_%d_%s' % (f, k, side)] = ((0, sg, 0), 50)
    M = pose_matrices(T, bends)
    Vp = skin(V, W, M); Pp = Vp[F].mean(1)
    ims = []
    for P, PC in ((V, Pc), (Vp, Pp)):
        for ax, ay, az in ((Y * -1, Z, X * -1), (X, Z, Y)):
            im, lo, sc = splat(np.vstack([P, PC]), np.vstack([C, Cc]), ax, ay, az)
            if P is V:
                d = ImageDraw.Draw(im)
                for n, (R, t) in T.W.items():
                    x = (t @ ax - lo[0]) * sc + 420 * 0.05; y = 560 - ((t @ ay - lo[1]) * sc + 560 * 0.05)
                    d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 255, 255))
            ims.append(im)
    out = Image.new('RGB', (420 * 4, 560))
    for i, im in enumerate(ims): out.paste(im, (420 * i, 0))
    out.save(path)
