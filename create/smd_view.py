"""smd_view.py: a software render of generated Source 2 models (SMD + vmdl + unlit vmat textures) as a player would
see them in CS2, without CS2: textured triangles with a z-buffer, alpha-tested _trans.png cut-outs, near-plane
clipping and an equirectangular sky behind everything. For checking framing, camera heights and how a scene reads.

Camera: CS2's view is 90 degrees across at 4:3, which is about 106 degrees across a 16:9 screen (fov_for()).
Materials are read the way generators write them: <vmat>_color.png (+ <vmat>_trans.png), paths from the vmdl's
material remaps; skins (material groups) can be picked by name.

usage:
  smd_view.py <addon_out> <out.png> --model models/x/a.vmdl[@x,y,z[,yaw]] [--model ...] --eye=x,y,z --at=x,y,z
              [--size 1280x720] [--fov 106] [--sky materials/x/sky_color.png] [--skin NAME] [--bg r,g,b]
  (yaw in degrees; --skin applies to every model; a sky path is relative to addon_out; write --eye=-200,0,80
   with "=" when a value starts with a minus sign)
import:
  import smd_view as V
  sc = V.Scene(out)
  sc.add('models/x/a.vmdl', off=(0, 0, 0), yaw=0.5, skin='red')
  img = sc.render(eye=(-200, -60, 80), at=(0, 0, 20), size=(1280, 720), sky='materials/x/sky_color.png')

From space-racer-cs2/preview/chase_view.py (MIT), made project-neutral.
"""
import os, re, sys, math, argparse
import numpy as np
from PIL import Image

NEAR = 5.0


def fov_for(w, h, fov43=90.0):
    """horizontal FOV CS2 shows on a w x h screen for its 90 degrees at 4:3 (same vertical view)"""
    half_v = math.atan(math.tan(math.radians(fov43 / 2)) * 3 / 4)
    return math.degrees(2 * math.atan(math.tan(half_v) * w / h))


def load_vmdl_mats(vmdl_text, skin=None):
    """{smd material name: vmat path} from a vmdl's DefaultMaterialGroup; with skin, that MaterialGroup's remaps
    (which map the default group's vmat paths to others) are applied on top"""
    m = re.search(r'_class = "DefaultMaterialGroup"\s*remaps =\s*\[(.*?)\]', vmdl_text, re.S)
    pairs = re.findall(r'from = "([^"]+)"\s*to = "([^"]+)"', m.group(1) if m else vmdl_text)
    default = {(f[:-5] if f.endswith('.vmat') else f): t for f, t in pairs}
    if skin:
        m = re.search(r'name = "%s"\s*remaps =\s*\[(.*?)\]' % re.escape(skin), vmdl_text, re.S)
        if not m: raise SystemExit('no material group "%s" in the model' % skin)
        remap = dict(re.findall(r'from = "([^"]+)"\s*to = "([^"]+)"', m.group(1)))
        default = {k: remap.get(v, v) for k, v in default.items()}
    return default


def vmdl_smd(vmdl_text):
    """the first RenderMeshFile filename in the vmdl"""
    m = re.search(r'_class = "RenderMeshFile".*?filename = "([^"]+)"', vmdl_text, re.S)
    return m.group(1) if m else None


def load_smd(path, mats, off=(0, 0, 0), yaw=0.0, pitch=0.0):
    """triangles [(vmat, [(x, y, z, u, v)] * 3)] in world space. The SMD holds (y, -x, z) to cancel ModelDoc's
    90-degree turn on import (s2.py writes it that way), so it is turned back here; then pitch, yaw, offset."""
    lines = open(path).read().split('\n')
    i = lines.index('triangles') + 1
    tris = []
    cy, sy = math.cos(yaw), math.sin(yaw); cp, sp = math.cos(pitch), math.sin(pitch)
    while i + 3 < len(lines) and lines[i] != 'end':
        m = lines[i].strip(); vs = []
        for k in range(3):
            f = lines[i + 1 + k].split()
            x, y, z = -float(f[2]), float(f[1]), float(f[3])
            x, z = x * cp + z * sp, -x * sp + z * cp
            x, y = x * cy - y * sy, x * sy + y * cy
            vs.append((x + off[0], y + off[1], z + off[2], float(f[7]), float(f[8])))
        tris.append((mats.get(m, ''), vs)); i += 4
    return tris


class Scene:
    def __init__(self, out):
        self.out = out
        self.tris = []
        self._tex = {}

    def add(self, vmdl, off=(0, 0, 0), yaw=0.0, pitch=0.0, skin=None):
        """add a model (path relative to the addon content root); yaw / pitch in radians"""
        txt = open(os.path.join(self.out, vmdl)).read()
        smd = vmdl_smd(txt) or vmdl.replace('.vmdl', '.smd')
        self.tris += load_smd(os.path.join(self.out, smd), load_vmdl_mats(txt, skin), off, yaw, pitch)
        return self

    def tex(self, vmat):
        """(colour float array, alpha 0..1 array or None) of an unlit vmat written as <name>_color.png / _trans.png"""
        if vmat in self._tex: return self._tex[vmat]
        c, a = None, None
        vp = os.path.join(self.out, vmat)
        if os.path.exists(vp):          # read the texture names from the vmat if it is there
            t = open(vp).read()
            mc = re.search(r'TextureColor\s+"([^"]+)"', t); ma = re.search(r'TextureTranslucency\s+"([^"]+)"', t)
            c = mc and os.path.join(self.out, mc.group(1)); a = ma and os.path.join(self.out, ma.group(1))
        c = c or os.path.join(self.out, vmat.replace('.vmat', '_color.png'))
        a = a or os.path.join(self.out, vmat.replace('.vmat', '_trans.png'))
        col = np.array(Image.open(c).convert('RGB')).astype(np.float32) if os.path.exists(c) else np.full((4, 4, 3), 128, np.float32)
        al = np.array(Image.open(a).convert('L')).astype(np.float32) / 255 if os.path.exists(a) else None
        self._tex[vmat] = (col, al)
        return self._tex[vmat]

    def render(self, eye, at, size=(1280, 720), fov=None, sky=None, bg=(8, 10, 22), roll=0.0):
        """picture from eye looking at `at` (world units); fov = horizontal degrees (default CS2's for this shape)"""
        W, H = size
        fov = fov or fov_for(W, H)
        cam = np.array(eye, float)
        fwd = np.array(at, float) - cam; fwd /= np.linalg.norm(fwd)
        right = np.cross(fwd, [0, 0, 1.0])
        if np.linalg.norm(right) < 1e-6: right = np.array([0, -1.0, 0])
        right /= np.linalg.norm(right); upv = np.cross(right, fwd)
        if roll:      # positive = right side down, as in Source
            r = math.radians(roll)
            right, upv = right * math.cos(r) - upv * math.sin(r), upv * math.cos(r) + right * math.sin(r)
        f = (W / 2) / math.tan(math.radians(fov / 2))
        img = np.zeros((H, W, 3), np.float32)
        img[:] = bg
        yy, xx = np.mgrid[0:H, 0:W]
        skyp = sky and (sky if os.path.isabs(sky) else os.path.join(self.out, sky))
        if skyp and os.path.exists(skyp):
            s = np.array(Image.open(skyp).convert('RGB')).astype(np.float32)
            D = fwd[None, None, :] * f + right[None, None, :] * (xx[..., None] - W / 2) + upv[None, None, :] * (H / 2 - yy[..., None])
            D /= np.linalg.norm(D, axis=2)[..., None]
            lon = np.arctan2(D[..., 1], D[..., 0]); lat = np.arcsin(np.clip(D[..., 2], -1, 1))
            su = ((lon / (2 * math.pi)) % 1 * s.shape[1]).astype(int) % s.shape[1]
            sv = np.clip(((0.5 - lat / math.pi) * s.shape[0]).astype(int), 0, s.shape[0] - 1)
            img[:] = s[sv, su]
        zb = np.full((H, W), 1e9, np.float32)
        for vmat, vs in self.tris:
            for tri in self._clip(vs, cam, fwd):
                self._raster(img, zb, vmat, tri, fwd, right, upv, f, W, H)
        return Image.fromarray(img.clip(0, 255).astype(np.uint8))

    @staticmethod
    def _clip(vs, cam, fwd):
        """clip a triangle against the near plane; returns triangles of (camera-relative point, u, v)"""
        pts = [(np.array(v[:3]) - cam, v[3], v[4]) for v in vs]
        out = []
        for k in range(3):
            a, b = pts[k], pts[(k + 1) % 3]
            da, db = a[0] @ fwd, b[0] @ fwd
            if da >= NEAR: out.append(a)
            if (da >= NEAR) != (db >= NEAR):
                t = (NEAR - da) / (db - da)
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t))
        return [(out[0], out[k], out[k + 1]) for k in range(1, len(out) - 1)]

    def _raster(self, img, zb, vmat, tri, fwd, right, upv, f, W, H):
        P = np.array([p[0] for p in tri])
        uv = [(p[1], p[2]) for p in tri]
        d = P @ fwd
        sx = W / 2 + (P @ right) / d * f; sy = H / 2 - (P @ upv) / d * f
        x0, x1 = int(max(0, math.floor(sx.min()))), int(min(W - 1, math.ceil(sx.max())))
        y0, y1 = int(max(0, math.floor(sy.min()))), int(min(H - 1, math.ceil(sy.max())))
        if x0 > x1 or y0 > y1: return
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        den = (sy[1] - sy[2]) * (sx[0] - sx[2]) + (sx[2] - sx[1]) * (sy[0] - sy[2])
        if abs(den) < 1e-9: return
        w0 = ((sy[1] - sy[2]) * (X - sx[2]) + (sx[2] - sx[1]) * (Y - sy[2])) / den
        w1 = ((sy[2] - sy[0]) * (X - sx[2]) + (sx[0] - sx[2]) * (Y - sy[2])) / den
        w2 = 1 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any(): return
        iz = w0 / d[0] + w1 / d[1] + w2 / d[2]          # perspective-correct depth and uv
        depth = 1 / np.maximum(iz, 1e-9)
        u = (w0 * uv[0][0] / d[0] + w1 * uv[1][0] / d[1] + w2 * uv[2][0] / d[2]) * depth
        v = (w0 * uv[0][1] / d[0] + w1 * uv[1][1] / d[1] + w2 * uv[2][1] / d[2]) * depth
        t, al = self.tex(vmat) if vmat else (np.full((4, 4, 3), 200, np.float32), None)
        th, tw = t.shape[:2]
        ui = np.floor((u % 1) * tw).astype(int) % tw; vi = np.floor((1 - v % 1) * th).astype(int) % th
        sub = zb[y0:y1 + 1, x0:x1 + 1]
        ok = inside & (depth < sub)
        if al is not None:
            ah, aw = al.shape
            ok &= al[(vi * ah // th) % ah, (ui * aw // tw) % aw] > 0.5
        sub[ok] = depth[ok]
        img[y0:y1 + 1, x0:x1 + 1][ok] = t[vi, ui][ok]


def vec(s):
    return tuple(float(v) for v in s.split(','))


def main(argv=None):
    ap = argparse.ArgumentParser(description='Software render of generated SMD models (see the docstring).')
    ap.add_argument('addon_out'); ap.add_argument('out_png')
    ap.add_argument('--model', action='append', required=True)
    ap.add_argument('--eye', required=True); ap.add_argument('--at', default='0,0,0')
    ap.add_argument('--size', default='1280x720'); ap.add_argument('--fov', type=float)
    ap.add_argument('--sky'); ap.add_argument('--skin'); ap.add_argument('--bg', default='8,10,22')
    a = ap.parse_args(argv)
    sc = Scene(a.addon_out)
    for m in a.model:
        path, _, pose = m.partition('@')
        p = vec(pose) if pose else (0, 0, 0)
        sc.add(path, off=p[:3], yaw=math.radians(p[3]) if len(p) > 3 else 0.0, skin=a.skin)
    W, H = (int(v) for v in a.size.split('x'))
    img = sc.render(vec(a.eye), vec(a.at), (W, H), a.fov, a.sky, vec(a.bg))
    img.save(a.out_png)
    print('smd view: %d triangles, fov %.1f -> %s' % (len(sc.tris), a.fov or fov_for(W, H), a.out_png))


if __name__ == '__main__':
    main()
