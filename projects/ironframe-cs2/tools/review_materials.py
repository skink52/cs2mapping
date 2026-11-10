"""Before/after material review for IRONFRAME frames: a small deferred PBR software renderer (tangent-space normal maps, GGX
specular, metalness, roughness, AO, a sky/ground environment for reflections) so roughness / metal / wear changes are visible.
The same lights for both renders. 'before' reads the originals backed up by tools/upgrade_materials.py (<work>/mat_orig/<key>/),
'after' the current out/addon materials.

usage: python -I tools/review_materials.py [--only key,..] [--lod 1] [--after-only] [--tag x]
  writes preview/materials/<key>.png (top: full body before | after; bottom: close-up before | after) and
  preview/materials/contact_sheet.png (every frame, before over after). Prints one line per frame."""
import json, math, os, re, sys, time
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import mech_render as MR                                              # noqa: E402
OUT = os.path.join(PROJ, 'out', 'addon')
CAT = json.load(open(os.path.join(PROJ, 'data', 'frames.json'), encoding='utf-8'))
BACK = os.path.join(os.environ.get('IF_WORK', CAT['paths']['work']), 'mat_orig')
PREV = os.path.join(PROJ, 'preview', 'materials')


def nrm(v): return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-9)


# ---------------------------------------------------------------- materials
_img = {}
def load_png(path, mode, cap=1024):
    k = (path, mode)
    if k not in _img:
        im = Image.open(path).convert(mode)
        if max(im.size) > cap: im = im.resize((cap, cap) if im.size[0] == im.size[1] else (cap, int(cap * im.size[1] / im.size[0])), Image.BILINEAR)
        _img[k] = np.asarray(im, np.float32) / 255.0
    return _img[k]


def material(key, mat, mode):
    """-> dict(col, nrm, rough, metal, ao, tint) arrays (or scalars) for a vmat name, 'before' from the backup folder"""
    stem = re.sub(r'\.vmat$', '', mat)
    d_cur = os.path.join(OUT, 'materials', 'ifr', 'frames', key); d_bk = os.path.join(BACK, key)
    vp = os.path.join(d_bk if mode == 'before' and os.path.exists(os.path.join(d_bk, stem + '.vmat')) else d_cur, stem + '.vmat')
    if not os.path.exists(vp): return dict(col=np.full((2, 2, 3), 0.5, np.float32), nrm=None, rough=0.7, metal=0.0, ao=None, tint=None)
    txt = open(vp, encoding='utf-8').read()
    def tex(k, m):
        r = re.search(r'^\s*%s\s+"([^"]+\.png)"' % k, txt, re.M)
        if not r: return None
        base = os.path.basename(r.group(1))
        p = os.path.join(d_bk, base) if mode == 'before' and os.path.exists(os.path.join(d_bk, base)) else os.path.join(OUT, r.group(1).replace('/', os.sep))
        return load_png(p, m) if os.path.exists(p) else None
    m = dict(col=tex('TextureColor', 'RGB'), nrm=tex('TextureNormal', 'RGB'), rough=tex('TextureRoughness', 'L'), metal=tex('TextureMetalness', 'L'),
             ao=tex('TextureAmbientOcclusion', 'L'), tint=None)
    if m['col'] is None: m['col'] = np.full((2, 2, 3), 0.5, np.float32)
    if m['rough'] is None: m['rough'] = 0.7
    if m['metal'] is None or 'F_METALNESS_TEXTURE' not in txt:
        g = re.search(r'g_flMetalness "([\d.]+)"', txt); m['metal'] = float(g.group(1)) if g else 0.0
    ct = re.search(r'g_vColorTint "\[([\d.]+) ([\d.]+) ([\d.]+)', txt)
    if ct: m['col'] = m['col'] * np.array([float(x) for x in ct.groups()], np.float32)
    m['illum'] = tex('TextureSelfIllumMask', 'L') if 'F_SELF_ILLUM 1' in txt else None
    return m


def sample(t, u, v):
    """bilinear sample of HxW(xC) at u, v (0..1, wrapped; v from the top)"""
    if not isinstance(t, np.ndarray): return np.full(u.shape, t, np.float32)
    h, w = t.shape[:2]
    x = (u % 1.0) * w - 0.5; y = (v % 1.0) * h - 0.5
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); fx = x - x0; fy = y - y0
    x0 %= w; y0 %= h; x1 = (x0 + 1) % w; y1 = (y0 + 1) % h
    if t.ndim == 3: fx = fx[:, None]; fy = fy[:, None]
    return (t[y0, x0] * (1 - fx) + t[y0, x1] * fx) * (1 - fy) + (t[y1, x0] * (1 - fx) + t[y1, x1] * fx) * fy


# ---------------------------------------------------------------- render
def raster(P3, W, H, cam, fwd, right, upv, fl, ctr2):
    """G-buffer: triangle id, perspective-correct barycentrics, depth"""
    rel = P3 - cam
    xc, yc, zc = rel @ right, rel @ upv, rel @ fwd
    SX = xc / zc * fl + ctr2[0]; SY = ctr2[1] - yc / zc * fl
    ntri = len(P3) // 3
    tid = np.full((H, W), -1, np.int64); zb = np.full((H, W), np.inf, np.float32); bar = np.zeros((H, W, 3), np.float32)
    X = SX.reshape(-1, 3); Y = SY.reshape(-1, 3); Z = zc.reshape(-1, 3)
    for t in range(ntri):
        if (Z[t] <= 1).any(): continue
        x, y = X[t], Y[t]
        x0 = max(0, int(math.floor(x.min()))); x1 = min(W - 1, int(math.ceil(x.max()))); y0 = max(0, int(math.floor(y.min()))); y1 = min(H - 1, int(math.ceil(y.max())))
        if x1 < x0 or y1 < y0: continue
        d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(d) < 1e-9: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        a = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d; b = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d; c = 1 - a - b
        m = (a >= -1e-4) & (b >= -1e-4) & (c >= -1e-4)
        if not m.any(): continue
        iz = 1.0 / Z[t]; ip = a * iz[0] + b * iz[1] + c * iz[2]; zz = 1.0 / ip
        sub = zb[y0:y1 + 1, x0:x1 + 1]; m &= zz < sub
        if not m.any(): continue
        sub[m] = zz[m]
        tid[y0:y1 + 1, x0:x1 + 1][m] = t
        bb = np.stack([a * iz[0] / ip, b * iz[1] / ip, c * iz[2] / ip], -1)
        bar[y0:y1 + 1, x0:x1 + 1][m] = bb[m]
    return tid, bar, zb


def env(r, rough):
    """sky / horizon / ground radiance in direction r (z up), blurred toward its average by roughness"""
    z = r[:, 2:3]
    sky = np.array([0.50, 0.60, 0.78]) * 1.15; hor = np.array([1.00, 0.93, 0.84]) * 1.35; gnd = np.array([0.30, 0.26, 0.22]) * 0.55
    sharp = np.where(z > 0, hor + (sky - hor) * np.clip(z * 1.6, 0, 1) ** 0.6, hor * 0.6 + (gnd - hor * 0.6) * np.clip(-z * 3, 0, 1))
    avg = np.array([0.62, 0.62, 0.62])
    k = np.clip(rough, 0, 1)[:, None] ** 0.7
    return sharp * (1 - k) + avg * k


def shade(mech, key, mode, gb, cam, lights):
    tid, bar, zb = gb
    H, W = tid.shape
    img = np.zeros((H, W, 3), np.float32); al = (tid >= 0).astype(np.float32)
    pix = np.nonzero(tid >= 0); t = tid[pix]; bb = bar[pix]
    P3 = mech['Pw'].reshape(-1, 3, 3); N3 = mech['Nw'].reshape(-1, 3, 3); U3 = mech['UV'].reshape(-1, 3, 2)
    p = (P3[t] * bb[..., None]).sum(1); n = nrm((N3[t] * bb[..., None]).sum(1)); uv = (U3[t] * bb[..., None]).sum(1)
    u, v = uv[:, 0], (1.0 - uv[:, 1])                              # SMD v is bottom-up
    # per-triangle tangent frame from positions and uvs (normal map +Y = up the image = +v_smd)
    e1 = P3[:, 1] - P3[:, 0]; e2 = P3[:, 2] - P3[:, 0]; d1 = U3[:, 1] - U3[:, 0]; d2 = U3[:, 2] - U3[:, 0]
    r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]; r = np.where(np.abs(r) < 1e-12, 1e-12, r)
    T = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / r[:, None]; B = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / r[:, None]
    Tt, Bt = T[t], B[t]
    Tt = nrm(Tt - n * (Tt * n).sum(1, keepdims=True)); hand = np.sign((np.cross(n, Tt) * Bt).sum(1, keepdims=True)); hand[hand == 0] = 1; Bt = np.cross(n, Tt) * hand
    vd = nrm(cam[None] - p)
    flip = (n * vd).sum(1) < 0
    n[flip] *= -1
    alb = np.zeros((len(t), 3), np.float32); ro = np.zeros(len(t), np.float32); me = np.zeros(len(t), np.float32); ao = np.ones(len(t), np.float32)
    nn = n.copy(); il = np.zeros(len(t), np.float32)
    mats = np.array(mech['mats'])[t]
    for mname in np.unique(mats):
        s = mats == mname; m = material(key, mname, mode)
        alb[s] = sample(m['col'], u[s], v[s]); ro[s] = sample(m['rough'], u[s], v[s]); me[s] = sample(m['metal'], u[s], v[s])
        if m['ao'] is not None: ao[s] = sample(m['ao'], u[s], v[s])
        if m.get('illum') is not None: il[s] = sample(m['illum'], u[s], v[s])
        if m['nrm'] is not None:
            tn = sample(m['nrm'], u[s], v[s]) * 2 - 1
            nn[s] = nrm(Tt[s] * tn[:, 0:1] + Bt[s] * tn[:, 1:2] * np.where(flip[s], -1, 1)[:, None] + n[s] * tn[:, 2:3])
    alb = alb ** 2.2
    N = nn
    NoV = np.clip((N * vd).sum(1), 1e-3, 1)
    F0 = 0.04 * (1 - me[:, None]) + alb * me[:, None]
    diff = alb * (1 - me[:, None])
    a2 = np.clip(ro, 0.05, 1) ** 4
    col = np.zeros_like(alb)
    # ambient: hemisphere + reflections, both occluded by the AO map (as CS2 does with AO on indirect light only)
    hemi = 0.5 + 0.5 * N[:, 2:3]
    amb = (np.array([0.42, 0.46, 0.55]) * hemi + np.array([0.20, 0.17, 0.14]) * (1 - hemi)) * 0.9
    Fr = F0 + (np.maximum(1 - ro[:, None], F0) - F0) * (1 - NoV[:, None]) ** 5
    R = nrm(2 * (N * vd).sum(1, keepdims=True) * N - vd)
    col += (diff * amb + env(R, ro) * Fr * (1 - 0.6 * ro[:, None]) * 0.75) * ao[:, None]
    for ld, lc in lights:
        NoL = np.clip(N @ ld, 0, 1)
        h = nrm(ld[None] + vd); NoH = np.clip((N * h).sum(1), 0, 1); VoH = np.clip((vd * h).sum(1), 0, 1)
        D = a2 / (math.pi * (NoH ** 2 * (a2 - 1) + 1) ** 2)
        k = (np.clip(ro, 0.05, 1) + 1) ** 2 / 8
        G = NoL / (NoL * (1 - k) + k) * NoV / (NoV * (1 - k) + k)
        F = F0 + (1 - F0) * (1 - VoH[:, None]) ** 5
        spec = (D * G)[:, None] * F / np.maximum(4 * NoL * NoV, 1e-3)[:, None]
        col += (diff / math.pi * math.pi + spec * math.pi) * (NoL[:, None] * lc)
    col += alb * il[:, None] * 3.0
    img[pix] = col
    return img, al


def cam_setup(mech, W, H, yaw, elev, dist_mul, fov, target_z=0.5, target_off=(0, 0)):
    P, Nn = mech['P'], mech['N']
    lo, hi = P.min(0), P.max(0)
    ctr = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, 0.0])
    ya = math.radians(yaw); c, s = math.cos(ya), math.sin(ya)
    Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    mech['Pw'] = (P - ctr) @ Rz.T; mech['Nw'] = Nn @ Rz.T
    h = mech['height']; tgt = np.array([0, target_off[0] * h, target_z * h])
    el = math.radians(elev); d = h * dist_mul
    cam = tgt + np.array([d * math.cos(el), 0, d * math.sin(el)])
    f = tgt - cam; f /= np.linalg.norm(f); r = np.cross(f, [0, 0, 1]); r /= np.linalg.norm(r); u = np.cross(r, f)
    fl = 0.5 * H / math.tan(math.radians(fov) / 2)
    return cam, f, r, u, fl


LIGHTS = [(nrm(np.array([0.55, -0.6, 0.62])), np.array([1.0, 0.92, 0.82]) * 2.6),
          (nrm(np.array([-0.5, 0.75, 0.25])), np.array([0.55, 0.65, 0.85]) * 0.5)]


def tonemap(img, al, bg):
    x = img * 0.9
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    y = np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0, 1) ** (1 / 2.2)
    out = bg * (1 - al[..., None]) + y * al[..., None]
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def background(W, H):
    g = np.linspace(0, 1, H)[:, None, None]
    return np.broadcast_to(np.array([0.20, 0.22, 0.25]) * (1 - g) + np.array([0.11, 0.115, 0.125]) * g, (H, W, 3)).copy()


def frame_views(key, lod, modes):
    mech = MR.load(key, lod=lod)
    out = {}
    for view, (W, H, yaw, elev, dm, fov, tz) in {'full': (520, 680, 35, -4, 2.7, 30, 0.5), 'close': (520, 520, 30, -8, 0.9, 30, 0.66)}.items():
        cam, f, r, u, fl = cam_setup(mech, W, H, yaw, elev, dm, fov, tz)
        gb = MR_G = raster(mech['Pw'], W, H, cam, f, r, u, fl, (W / 2, H / 2))
        for m in modes:
            img, al = shade(mech, key, m, gb, cam, LIGHTS)
            out[(view, m)] = tonemap(img, al, background(W, H))
    return out


def label(im, text, xy=(8, 6)):
    d = ImageDraw.Draw(im); d.rectangle([xy[0] - 4, xy[1] - 3, xy[0] + 7 * len(text), xy[1] + 12], fill=(0, 0, 0)); d.text(xy, text, fill=(255, 230, 120))


def main():
    a = sys.argv[1:]
    only = set(a[a.index('--only') + 1].split(',')) if '--only' in a else None
    lod = int(a[a.index('--lod') + 1]) if '--lod' in a else 1
    tag = a[a.index('--tag') + 1] if '--tag' in a else ''
    modes = ['after'] if '--after-only' in a else ['before', 'after']
    models = json.load(open(os.path.join(OUT, '_gen', 'models.json'), encoding='utf-8'))['frames']
    keys = [k for k in CAT['frames'] if k in models] + [k for k in models if k not in CAT['frames']]
    if only: keys = [k for k in keys if k in only]
    os.makedirs(PREV, exist_ok=True)
    thumbs = []
    for i, k in enumerate(keys):
        t0 = time.time()
        try: v = frame_views(k, lod, modes)
        except Exception as e: print('[%d/%d] %s FAILED %s' % (i + 1, len(keys), k, e), flush=True); continue
        W = 520 * len(modes); sheet = Image.new('RGB', (W, 680 + 520), (20, 20, 24))
        for j, m in enumerate(modes):
            sheet.paste(v[('full', m)], (520 * j, 0)); sheet.paste(v[('close', m)], (520 * j, 680))
            label(sheet, '%s  %s' % (k, m), (520 * j + 10, 8))
        sheet.save(os.path.join(PREV, '%s%s.png' % (k, tag)), optimize=True)
        thumbs.append((k, [v[('full', m)].resize((208, 272), Image.LANCZOS) for m in modes]))
        print('[%d/%d] %s %.0fs' % (i + 1, len(keys), k, time.time() - t0), flush=True)
    if len(thumbs) > 1:
        cols = 10; rows = (len(thumbs) + cols - 1) // cols
        cs = Image.new('RGB', (cols * 208, rows * 272 * len(modes) + rows * 16), (20, 20, 24))
        for i, (k, ims) in enumerate(thumbs):
            x = (i % cols) * 208; y = (i // cols) * (272 * len(modes) + 16)
            for j, im in enumerate(ims): cs.paste(im, (x, y + 16 + 272 * j))
            ImageDraw.Draw(cs).text((x + 4, y + 2), k, fill=(255, 230, 120))
        cs.save(os.path.join(PREV, 'contact_sheet%s.png' % tag), optimize=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
