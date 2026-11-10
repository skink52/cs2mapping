"""Textured perspective software renderer for IRONFRAME mech frames (loading slides, Workshop icon).
load(key) reads the converted SMDs (legs + upper, posed from a clip frame) and render() draws them with a perspective camera:
per-pixel albedo texture, smooth normals, key / fill / rim lights, a fake specular and a fresnel rim glow.
python -I tools/mech_render.py <frame key> <out.png> [yaw]      quick test render (RGBA)"""
import glob, json, math, os, re, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
OUT = os.path.join(PROJ, 'out', 'addon')
sys.path.insert(0, HERE)
import review_frames as RF

_tex = {}
def texture(key, mat):
    k = (key, mat)
    if k not in _tex:
        stem = re.sub(r'\.vmat$', '', mat)
        g = glob.glob(os.path.join(OUT, 'materials/ifr/frames', key, stem + '_color*.png')) or glob.glob(os.path.join(OUT, 'materials/ifr/frames', key, stem + '*.png'))
        t = None
        if g:
            try:
                im = Image.open(g[0]).convert('RGB')
                if max(im.size) > 1024: im = im.resize((1024, 1024))
                t = np.asarray(im, np.float32) / 255
            except Exception: pass
        _tex[k] = t if t is not None else np.full((2, 2, 3), 0.55, np.float32)
    return _tex[k]


def read_mesh_full(path):
    """RF.read_mesh plus normals and uvs; one material per triangle"""
    L = open(path).read().split('\n')
    nodes, frames = RF.read_nodes_frames(L)
    i = L.index('triangles') + 1
    mats, V, N, UV, BI, BW = [], [], [], [], [], []
    while i < len(L) and L[i] != 'end':
        mats.append(L[i].strip())
        for k in range(3):
            t = L[i + 1 + k].split()
            V.append([float(x) for x in t[1:4]]); N.append([float(x) for x in t[4:7]]); UV.append([float(t[7]), float(t[8])])
            if len(t) > 9:
                n = int(t[9]); bw = [(int(t[10 + 2 * j]), float(t[11 + 2 * j])) for j in range(n)][:3]
            else: bw = [(int(t[0]), 1.0)]
            bw += [(0, 0.0)] * (3 - len(bw)); BI.append([b for b, _ in bw]); BW.append([w for _, w in bw])
        i += 4
    return dict(nodes=nodes, bind=frames[0], V=np.array(V), N=np.array(N), UV=np.array(UV), BI=np.array(BI), BW=np.array(BW), mats=mats)


def posed_vn(mesh, fr):
    nodes = mesh['nodes']
    Wb = RF.world_mats(nodes, mesh['bind']); Wp = RF.world_mats(nodes, fr if fr is not None else mesh['bind'])
    S = np.array([Wp[k] @ np.linalg.inv(Wb[k]) for k in range(len(nodes))])
    V, Nn = mesh['V'], mesh['N']; ov = np.zeros_like(V); on = np.zeros_like(V)
    for k in range(3):
        M = S[mesh['BI'][:, k]]; w = mesh['BW'][:, k:k + 1]
        ov += w * (np.einsum('nij,nj->ni', M[:, :3, :3], V) + M[:, :3, 3]); on += w * np.einsum('nij,nj->ni', M[:, :3, :3], Nn)
    f = lambda a: np.stack([-a[:, 1], a[:, 0], a[:, 2]], 1)
    on = f(on); on /= np.linalg.norm(on, axis=1, keepdims=True) + 1e-9
    return f(ov), on


def load(key, lod=2, upper_clip='idle', legs_clip='hover', frame_pick=0):
    ents = json.load(open(os.path.join(OUT, '_gen', 'models.json')))['frames']
    e = ents[key]
    d = os.path.join(OUT, 'models/ifr/frames', key)
    P, N, UV, MAT = [], [], [], []
    for g, clip in (('legs', legs_clip), ('upper', upper_clip)):
        v = e.get(g)
        if not v: continue
        m = read_mesh_full(RF.lod_file(d, os.path.basename(v)[:-5], lod))
        fr = None
        p = os.path.join(d, 'anims', '%s_%s.smd' % (g, clip))
        if clip and os.path.exists(p):
            _, f = RF.clip_frames(p); ks = sorted(f); fr = f[ks[min(frame_pick, len(ks) - 1)]]
        Pv, Nv = posed_vn(m, fr)
        P.append(Pv); N.append(Nv); UV.append(m['UV']); MAT += m['mats']
    return dict(P=np.concatenate(P), N=np.concatenate(N), UV=np.concatenate(UV), mats=MAT, height=e['height'], key=key)


def norm(v): v = np.asarray(v, float); return v / (np.linalg.norm(v) + 1e-12)
def norm_rows(v): return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-9)


def render(mech, W, H, yaw=35, elev=-4, dist_mul=2.6, fov=32, shift=(0, 0), fit=None, lights=None, rim=((0.1, 0.8, 1.0), (1.0, 0.2, 0.7)), exposure=1.0):
    """the mech turned `yaw` degrees about its centre (0 = facing the camera), camera at `elev` degrees (negative = looking up from below).
    Returns (rgb float linear, alpha 0/1, depth)."""
    P, Nn, UV = mech['P'], mech['N'], mech['UV']
    ntri = len(P) // 3
    lo, hi = P.min(0), P.max(0)
    ctr = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, mech['height'] * 0.5])
    ya = math.radians(yaw); c, s = math.cos(ya), math.sin(ya)
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    Pw = (P - ctr) @ R.T; Nw = Nn @ R.T
    el = math.radians(elev); cam_d = mech['height'] * dist_mul
    cam = np.array([cam_d * math.cos(el), 0, cam_d * math.sin(el)])
    f = norm(-cam); r = norm(np.cross(f, [0, 0, 1])); u = np.cross(r, f)
    rel = Pw - cam
    xc, yc, zc = rel @ r, rel @ u, rel @ f
    fl = 0.5 * H / math.tan(math.radians(fov) / 2)
    SX = xc / zc * fl + W / 2 + shift[0] * W; SY = H / 2 - yc / zc * fl + shift[1] * H
    if fit:    # fit=(box_w, box_h, anchor_x, anchor_bottom_y): scale + move the projected bounds into that box (feet on anchor_bottom_y)
        bx0, bx1, by0, by1 = SX.min(), SX.max(), SY.min(), SY.max()
        sc = min(fit[0] / (bx1 - bx0), fit[1] / (by1 - by0))
        SX = (SX - (bx0 + bx1) / 2) * sc + fit[2]; SY = (SY - by1) * sc + fit[3]
    L = lights or dict(key=(norm([0.45, -0.75, 0.5]), np.array([1.0, 0.80, 0.66]) * 1.35), fill=(norm([0.2, 0.9, 0.15]), np.array([0.35, 0.30, 0.9]) * 0.35),
                       rim=(norm([-0.85, -0.25, 0.35]), np.array(rim[0]) * 1.7), rim2=(norm([-0.55, 0.85, 0.05]), np.array(rim[1]) * 1.3))
    img = np.zeros((H, W, 3), np.float32); zb = np.full((H, W), np.inf, np.float32); al = np.zeros((H, W), np.float32)
    zt = zc.reshape(-1, 3)
    V3x = SX.reshape(-1, 3); V3y = SY.reshape(-1, 3)
    N3 = Nw.reshape(-1, 3, 3); UV3 = UV.reshape(-1, 3, 2); P3 = Pw.reshape(-1, 3, 3); iz3 = (1.0 / zc).reshape(-1, 3)
    texs = {m: texture(mech['key'], m) for m in set(mech['mats'])}
    for t in range(ntri):
        if (zt[t] <= 1).any(): continue
        x = V3x[t]; y = V3y[t]
        x0 = int(max(0, math.floor(x.min()))); x1 = int(min(W - 1, math.ceil(x.max()))); y0 = int(max(0, math.floor(y.min()))); y1 = int(min(H - 1, math.ceil(y.max())))
        if x1 < x0 or y1 < y0: continue
        d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(d) < 1e-9: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        a = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d; b = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d; cc = 1 - a - b
        m = (a >= -1e-3) & (b >= -1e-3) & (cc >= -1e-3)
        if not m.any(): continue
        w = iz3[t]; ip = a * w[0] + b * w[1] + cc * w[2]; zz = 1.0 / ip
        sub = zb[y0:y1 + 1, x0:x1 + 1]; m &= zz < sub
        if not m.any(): continue
        sub[m] = zz[m]
        pa, pb, pc = (a * w[0] / ip)[m], (b * w[1] / ip)[m], (cc * w[2] / ip)[m]
        uv = pa[:, None] * UV3[t, 0] + pb[:, None] * UV3[t, 1] + pc[:, None] * UV3[t, 2]
        nv = norm_rows(pa[:, None] * N3[t, 0] + pb[:, None] * N3[t, 1] + pc[:, None] * N3[t, 2])
        pp = pa[:, None] * P3[t, 0] + pb[:, None] * P3[t, 1] + pc[:, None] * P3[t, 2]
        tex = texs[mech['mats'][t]]; th, tw = tex.shape[:2]
        tu = (uv[:, 0] % 1.0) * (tw - 1); tv = (uv[:, 1] % 1.0) * (th - 1)
        alb = tex[tv.astype(int), tu.astype(int)] ** 2.2 * 1.6                                   # linearise (and lift: these textures are dark)
        vd = norm_rows(cam - pp)
        nv = np.where(((nv * vd).sum(1) < 0)[:, None], -nv, nv)
        col = alb * np.array([0.07, 0.08, 0.16]) * (0.55 + 0.45 * nv[:, 2:3])
        for nm, (ld, lc) in L.items():
            df = np.clip(nv @ ld, 0, 1)
            col += alb * (df[:, None] * lc)
            h = norm_rows(ld[None] + vd); sp = np.clip((nv * h).sum(1), 0, 1) ** 36
            col += (sp[:, None] * lc) * 0.22
        fr = (1 - np.clip((nv * vd).sum(1), 0, 1)) ** 3
        col += fr[:, None] * np.array(rim[0]) * 0.22
        img[y0:y1 + 1, x0:x1 + 1][m] = col
        al[y0:y1 + 1, x0:x1 + 1][m] = 1
    return img * exposure, al, zb


def to_rgba(img, al, gamma=1 / 2.2):
    """tone-map to 0..255 RGBA (alpha antialiased by a 3x3 blur of the coverage mask)"""
    rgb = np.clip(img / (1 + img * 0.35) * 1.35, 0, 1) ** gamma
    from PIL import ImageFilter
    a = Image.fromarray((al * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))
    return Image.merge('RGBA', [Image.fromarray((rgb[..., i] * 255).astype(np.uint8)) for i in range(3)] + [a])


if __name__ == '__main__':
    import time
    key = sys.argv[1]; out = sys.argv[2]; yaw = float(sys.argv[3]) if len(sys.argv) > 3 else 35
    t = time.time(); m = load(key, lod=int(os.environ.get('LOD', 2)))
    img, al, zb = render(m, 900, 1000, yaw=yaw, elev=-6)
    to_rgba(img, al).save(out); print('%.1fs' % (time.time() - t), len(m['P']) // 3, 'tris')
