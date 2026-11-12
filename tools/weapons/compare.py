"""Turntable + first-person scale renders for weapon models: GLB candidates, built bodies and the stock weapon they replace.

usage:
  compare.py glbs  <out.png> [--axes Yxz] <label>=<file.glb> ...
      contact sheet of raw candidates (textured, centred, same scale): side, 3/4, top; with size and triangle count.
  compare.py built <out.png> --stock <prefix_stock> [--stock-dir DIR] <label>=<body.dmx>[@<content root>] ...
      each body (DMX from build_weapon.py, or the current addon's) and the stock weapon in weapon_offset space, same cameras:
      side, 3/4, over-the-shoulder, an approximate first-person camera, then side-view overlays of every body (blue) on the stock (red).
      Textures come from the vmats' TextureColor under the content root given after '@' (default: the DMX's addon root).

Software z-buffer render (Lambert sun, two-sided), for looking at shape and scale before compiling; nothing is compiled.
Untrusted GLBs are only parsed (run with python -I).
"""
import io, math, os, re, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx, glbmesh

STOCK = os.environ.get('WW1_STOCK', 'C:/source2/projects/trenchwarfare/stock')
SUN = np.array([0.45, -0.35, 0.82]); SUN /= np.linalg.norm(SUN)
BG = (92, 100, 112)


class Mesh:
    """triangles with per-corner uv and a material key; textures: key -> float RGB array"""
    def __init__(self):
        self.P = []; self.UV = []; self.M = []; self.tex = {}

    def add(self, V, UV, F, key, tex):
        self.P.append(V[F]); self.UV.append(UV[F]); self.M += [key] * len(F); self.tex.setdefault(key, tex)

    def done(self):
        self.P = np.vstack(self.P); self.UV = np.vstack(self.UV); return self

    @property
    def lo(self): return self.P.reshape(-1, 3).min(0)

    @property
    def hi(self): return self.P.reshape(-1, 3).max(0)


def render(mesh, eye, at, size=(560, 320), fov=40.0, bg=BG):
    W, H = size
    eye = np.asarray(eye, float); f = np.asarray(at, float) - eye; f /= np.linalg.norm(f)
    r = np.cross(f, (0, 0, 1.0))
    if np.linalg.norm(r) < 1e-6: r = np.array([0, -1.0, 0])
    r /= np.linalg.norm(r); u = np.cross(r, f)
    fp = 0.5 * W / math.tan(math.radians(fov) / 2)
    img = np.zeros((H, W, 3), np.float32); img[:] = bg; zb = np.full((H, W), np.inf)
    C = (mesh.P - eye) @ np.stack([r, u, f]).T            # (n, 3, 3) camera space
    z = C[:, :, 2]
    n = np.cross(mesh.P[:, 1] - mesh.P[:, 0], mesh.P[:, 2] - mesh.P[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
    shade = 0.40 + 0.60 * np.abs(n @ SUN)
    sx = W / 2 + fp * C[:, :, 0] / np.maximum(z, 1e-3); sy = H / 2 - fp * C[:, :, 1] / np.maximum(z, 1e-3)
    for k in np.where(z.min(1) > 0.5)[0]:
        xs, ys = sx[k], sy[k]
        x0, x1 = max(int(xs.min()), 0), min(int(xs.max()) + 1, W - 1); y0, y1 = max(int(ys.min()), 0), min(int(ys.max()) + 1, H - 1)
        if x1 < x0 or y1 < y0: continue
        den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
        if abs(den) < 1e-9: continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l0 = ((ys[1] - ys[2]) * (X - xs[2]) + (xs[2] - xs[1]) * (Y - ys[2])) / den
        l1 = ((ys[2] - ys[0]) * (X - xs[2]) + (xs[0] - xs[2]) * (Y - ys[2])) / den
        l2 = 1 - l0 - l1
        m = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        if not m.any(): continue
        zz = l0 * z[k, 0] + l1 * z[k, 1] + l2 * z[k, 2]
        sub = zb[y0:y1 + 1, x0:x1 + 1]; m &= zz < sub
        if not m.any(): continue
        T = mesh.tex[mesh.M[k]]; th, tw = T.shape[:2]; uv = mesh.UV[k]
        uu = l0 * uv[0, 0] + l1 * uv[1, 0] + l2 * uv[2, 0]; vv = l0 * uv[0, 1] + l1 * uv[1, 1] + l2 * uv[2, 1]
        tx = np.clip((uu % 1) * tw, 0, tw - 1).astype(int); ty = np.clip((vv % 1) * th, 0, th - 1).astype(int)
        sub[m] = zz[m]
        img[y0:y1 + 1, x0:x1 + 1][m] = T[ty[m], tx[m]] * shade[k]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


GREY = np.full((2, 2, 3), 170, np.float32)


def _small(im, n=512):
    im = im.convert('RGB'); im.thumbnail((n, n)); return np.asarray(im, np.float32)


def load_glb(path, axes=None):
    """GLB -> Mesh (inches, Source axes as the builder loads it; uv top-left like glTF)"""
    g, b, parts = glbmesh.load_parts(path, 1.0, axes)
    texc = {}
    def base(mi):
        if mi in texc: return texc[mi]
        t = GREY
        if mi is not None:
            m = g['materials'][mi]; pbr = m.get('pbrMetallicRoughness', {})
            if 'baseColorTexture' in pbr:
                im = g['images'][g['textures'][pbr['baseColorTexture']['index']]['source']]; bv = g['bufferViews'][im['bufferView']]
                t = _small(Image.open(io.BytesIO(b[bv.get('byteOffset', 0):bv.get('byteOffset', 0) + bv['byteLength']])))
            elif 'baseColorFactor' in pbr:
                t = np.full((2, 2, 3), np.array(pbr['baseColorFactor'][:3]) ** (1 / 2.2) * 255, np.float32)
        texc[mi] = t; return t
    me = Mesh()
    for p in parts:
        uv = p.T.copy(); uv[:, 1] = 1 - uv[:, 1]           # load_parts flips to bottom-left; textures index top-left
        me.add(p.V, uv, p.F, 'glb%s' % p.material, base(p.material))
    return me.done(), g


def load_dmx(path, root=None, wo=(0, 0, 0)):
    """model DMX (ours or a S2V stock export) -> Mesh in weapon_offset space (subtract the weapon bone origin `wo`)"""
    h, els = dmx.read(path)
    me = Mesh(); root = root or re.split(r'[\\/]models[\\/]', path)[0]
    for mesh in [e for e in els if e.type == 'DmeMesh']:
        vd = mesh['currentState']
        P = np.asarray(vd['position$0'].items, float) - np.asarray(wo, float)
        pi = np.asarray(vd['position$0Indices'].items) if 'position$0Indices' in vd.attrs else None
        T = np.asarray(vd['texcoord$0'].items, float) if 'texcoord$0' in vd.attrs else np.zeros((len(P), 2))
        ti = np.asarray(vd['texcoord$0Indices'].items) if 'texcoord$0Indices' in vd.attrs else None
        for fs in mesh['faceSets'].items:
            mat = (fs['material']['mtlName'] if fs['material'] else '').replace('\\', '/')
            if mat and not mat.endswith('.vmat'): mat += '.vmat'
            tris = []; cur = []
            for i in np.asarray(fs['faces'].items):
                if i >= 0: cur.append(int(i)); continue
                tris += [(cur[0], cur[k], cur[k + 1]) for k in range(1, len(cur) - 1)]; cur = []
            if not tris: continue
            F = np.array(tris)
            Fp = pi[F] if pi is not None else F; Ft = ti[F] if ti is not None else F
            tex = GREY
            for rt in root.split(';'):      # several roots: first one holding the vmat wins (e.g. build dir;content addon)
                vp = os.path.join(rt, mat)
                if not os.path.exists(vp): continue
                mc = re.search(r'TextureColor"?\s+"([^"]+)"', open(vp, errors='ignore').read())
                cp = mc and os.path.join(rt, mc.group(1))
                if cp and os.path.exists(cp): tex = _small(Image.open(cp))
                break
            me.P.append(P[Fp]); me.UV.append(T[Ft]); me.M += [mat] * len(F); me.tex.setdefault(mat, tex)
    return me.done()


def stock_wo(prefix_stock, stock_dir=STOCK):
    """weapon bone origin (= weapon_offset origin in model space) of a stock weapon vmdl"""
    t = open(os.path.join(stock_dir, prefix_stock + '.vmdl')).read()
    i = t.index('_class = "Skeleton"')
    m = re.search(r'name = "weapon"\s*\n\s*origin = \[ ([^\]]*) \]', t[i:])
    return np.array([float(x) for x in m.group(1).split(',')])


def label(im, text):
    d = ImageDraw.Draw(im); d.rectangle((0, 0, im.size[0], 18), fill=(20, 20, 20)); d.text((4, 3), text, fill=(255, 255, 255)); return im


def column(images, size):
    col = Image.new('RGB', (size[0], size[1] * len(images)))
    for i, im in enumerate(images): col.paste(im, (0, i * size[1]))
    return col


def sheet(cols):
    W = Image.new('RGB', (sum(c.size[0] for c in cols), max(c.size[1] for c in cols)), (235, 235, 235))
    x = 0
    for c in cols: W.paste(c, (x, 0)); x += c.size[0]
    return W


def cmd_glbs(out, items, axes=None):
    size = (560, 300); loaded = []
    for lab, path in items:
        me, g = load_glb(path, axes)
        if not axes:   # auto-orient for the sheet only: longest extent -> X, middle -> Z (height), smallest -> Y
            order = np.argsort(-(me.hi - me.lo)); me.P = me.P[:, :, [order[0], order[2], order[1]]]
        loaded.append((lab, me))
    cols = []
    for lab, me in loaded:
        c = (me.lo + me.hi) / 2; ims = []; r = float(np.linalg.norm(me.hi - me.lo)) / 2   # each model fills its column
        for az, el in ((-90, 0), (-60, 20), (0, 89)):
            a, b = math.radians(az), math.radians(el)
            eye = c + 2.9 * r * np.array([math.cos(a) * math.cos(b), math.sin(a) * math.cos(b), math.sin(b)])
            ims.append(render(me, eye, c, size))
        ext = me.hi - me.lo
        cols.append(column([label(ims[0], '%s  %d tris  %.1f x %.1f x %.1f in' % (lab, len(me.M), *ext))] + ims[1:], size))
        print('%-28s tris %6d  extent %s in (glTF axes -> Source, scale 1)' % (lab, len(me.M), ext.round(2)))
    sheet(cols).save(out); print('wrote', out)


VIEWS_BUILT = (('side', (-90, 0)), ('3/4', (-60, 20)), ('shoulder', (200, 12)))


def cmd_built(out, items, prefix_stock, stock_dir=STOCK):
    size = (560, 300)
    wo = stock_wo(prefix_stock, stock_dir)
    sets = [('STOCK ' + prefix_stock, load_dmx(os.path.join(stock_dir, prefix_stock + '_body_hd1.dmx'), stock_dir, wo))]
    for lab, spec in items:
        path, _, root = spec.partition('@')
        sets.append((lab, load_dmx(path, root or None, wo)))
    allp = np.vstack([s[1].P.reshape(-1, 3) for s in sets]); lo, hi = allp.min(0), allp.max(0)
    c0 = (lo + hi) / 2; r = float(np.linalg.norm(hi - lo)) / 2
    pistol = 'pist' in prefix_stock
    # approximate first-person eye relative to weapon_offset (the grip): behind, right of and above it, looking down the bore
    # (screen right is -Y looking down +X, so the eye sits at +Y to show the weapon lower right, as the right-handed viewmodel does)
    fp_eye = np.array([-11.0, 3.0, 4.5]) if pistol else np.array([-16.0, 4.5, 6.0])
    fp_at = fp_eye + np.array([40.0, -4.0, -4.0])
    cols = []; masks = []
    for lab, me in sets:
        ims = []
        for name, (az, el) in VIEWS_BUILT:
            a, b = math.radians(az), math.radians(el)
            eye = c0 + 2.9 * r * np.array([math.cos(a) * math.cos(b), math.sin(a) * math.cos(b), math.sin(b)])
            ims.append(render(me, eye, c0, size))
        ims.append(render(me, fp_eye, fp_at, size, fov=68))
        masks.append(np.any(np.abs(np.asarray(ims[0], np.float32) - np.array(BG)) > 3, axis=2))
        ext = me.hi - me.lo
        label(ims[0], '%s  %d tris  len %.1f u  (x %.1f..%.1f, z %.1f..%.1f)' % (lab, len(me.M), ext[0], me.lo[0], me.hi[0], me.lo[2], me.hi[2]))
        label(ims[3], 'approx. first-person camera, viewmodel fov 68 (same for all)')
        cols.append(column(ims, size))
        print('%-34s tris %6d  length %.1f u  bounds(wo) %s .. %s' % (lab, len(me.M), ext[0], me.lo.round(1), me.hi.round(1)))
    ovs = []
    for (lab, _), mk in zip(sets[1:], masks[1:]):
        ov = np.full(mk.shape + (3,), 235, np.uint8)
        ov[masks[0]] = (220, 70, 60); ov[mk] = (60, 90, 220); ov[mk & masks[0]] = (150, 60, 160)
        ovs.append(label(Image.fromarray(ov), 'scale: %s blue, stock red, both purple' % lab))
    while len(ovs) < 4: ovs.append(Image.new('RGB', size, (235, 235, 235)))
    cols.append(column(ovs[:4], size))
    sheet(cols).save(out); print('wrote', out)


def main(a):
    if len(a) < 2 or a[0] not in ('glbs', 'built'): print(__doc__); return
    cmd, out, rest = a[0], a[1], a[2:]
    opts = {}
    while rest and rest[0].startswith('--'):
        opts[rest[0][2:]] = rest[1]; rest = rest[2:]
    items = [x.split('=', 1) for x in rest]
    if cmd == 'glbs': cmd_glbs(out, items, opts.get('axes'))
    else: cmd_built(out, items, opts['stock'], opts.get('stock-dir', STOCK))


if __name__ == '__main__':
    main(sys.argv[1:])
