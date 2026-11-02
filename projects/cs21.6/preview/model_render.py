"""Small textured software renderer for checking converted player models (orthographic, z-buffered, simple light).

render(P, UV, groups, path, views): P (n,3) positions, UV (n,2) texture coordinates (v from the top of the picture),
groups [(faces (m,3) int array, texture HxWx3 uint8 array)], views like ('front', 'side', 'back').
"""
import numpy as np
from PIL import Image

VIEWS = {   # direction toward the viewer; the picture's right is (toward the viewer reversed) x up
    'front': np.array([1, 0, 0.]), 'back': np.array([-1, 0, 0.]), 'side': np.array([0, 1, 0.]),
    'three': np.array([0.87, 0.5, 0.]),
}


def render(P, UV, groups, path, views=('front', 'side', 'back'), H=900, marks=None):
    lo, hi = P.min(0), P.max(0)
    sc = (H - 40) / max(1e-6, hi[2] - lo[2])
    W = int(H * 0.62)
    out = Image.new('RGB', (W * len(views), H), (46, 50, 58))
    light = np.array([0.4, 0.3, 0.86]); light /= np.linalg.norm(light)
    for k, vname in enumerate(views):
        dv = VIEWS[vname]; hv = np.cross(-dv, [0, 0, 1.])
        X = (P - (lo + hi) / 2) @ hv * sc + W / 2
        Y = H - 20 - (P[:, 2] - lo[2]) * sc
        Z = P @ dv
        img = np.full((H, W, 3), (46, 50, 58), np.float32)
        zb = np.full((H, W), -1e9)
        for faces, tex in groups:
            th, tw = tex.shape[:2]
            for f in faces:
                x, y, z = X[f], Y[f], Z[f]
                p = P[f]
                n = np.cross(p[1] - p[0], p[2] - p[0]); nl = np.linalg.norm(n)
                if nl == 0: continue
                n /= nl
                if n @ dv <= 0: continue                      # back face
                shade = 0.45 + 0.55 * max(0.0, float(n @ light))
                x0, x1 = int(max(0, np.floor(x.min()))), int(min(W - 1, np.ceil(x.max())))
                y0, y1 = int(max(0, np.floor(y.min()))), int(min(H - 1, np.ceil(y.max())))
                if x1 < x0 or y1 < y0: continue
                gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
                d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
                if abs(d) < 1e-9: continue
                a = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
                b = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
                c = 1 - a - b
                inside = (a >= -1e-4) & (b >= -1e-4) & (c >= -1e-4)
                if not inside.any(): continue
                zz = a * z[0] + b * z[1] + c * z[2]
                sub = zb[y0:y1 + 1, x0:x1 + 1]
                m = inside & (zz > sub)
                if not m.any(): continue
                uv = UV[f]
                u = a * uv[0, 0] + b * uv[1, 0] + c * uv[2, 0]
                v = a * uv[0, 1] + b * uv[1, 1] + c * uv[2, 1]
                tx = np.clip((u % 1.0) * tw, 0, tw - 1).astype(int); ty = np.clip((v % 1.0) * th, 0, th - 1).astype(int)
                col = tex[ty, tx, :3].astype(np.float32) * shade
                sub[m] = zz[m]
                img[y0:y1 + 1, x0:x1 + 1][m] = col[m]
        if marks is not None:
            mx = (marks - (lo + hi) / 2) @ hv * sc + W / 2; my = H - 20 - (marks[:, 2] - lo[2]) * sc
            for a_, b_ in zip(mx.astype(int), my.astype(int)):
                img[max(0, b_ - 2):b_ + 3, max(0, a_ - 2):a_ + 3] = (255, 70, 50)
        out.paste(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)), (W * k, 0))
    out.save(path)
