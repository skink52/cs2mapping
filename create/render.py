"""Software preview renderer for baked models (z-buffer, normal mapped, AO, sun + sky, simple GGX-ish spec)."""
import numpy as np
from PIL import Image


def look_at(eye, target, up=(0, 0, 1)):
    eye = np.asarray(eye, float); f = np.asarray(target, float) - eye; f /= np.linalg.norm(f)
    r = np.cross(f, up); r /= np.linalg.norm(r); u = np.cross(r, f)
    return eye, np.stack([r, u, -f])


def render(meshes, eye, target, W=900, H=650, fov=40, sun=(-0.4, -0.6, 0.7), bg=(0.62, 0.66, 0.70), ground=None, exposure=1.0):
    """meshes: list of (mesh, uv, baked)"""
    eye, Rm = look_at(eye, target)
    fpx = 0.5 * W / np.tan(np.radians(fov) / 2)
    zbuf = np.full((H, W), np.inf); fid = np.full((H, W), -1, np.int64); mid = np.full((H, W), -1, np.int64)
    bary = np.zeros((H, W, 3))
    for mi, (m, uv, bk) in enumerate(meshes):
        cam = (m.V - eye) @ Rm.T
        z = -cam[:, 2]
        sx = W / 2 + fpx * cam[:, 0] / np.maximum(z, 1e-3); sy = H / 2 - fpx * cam[:, 1] / np.maximum(z, 1e-3)
        for f, (a, b, c) in enumerate(m.F):
            if z[a] < 1 or z[b] < 1 or z[c] < 1: continue
            xs = np.array([sx[a], sx[b], sx[c]]); ys = np.array([sy[a], sy[b], sy[c]])
            x0 = max(int(xs.min()), 0); x1 = min(int(xs.max()) + 1, W - 1); y0 = max(int(ys.min()), 0); y1 = min(int(ys.max()) + 1, H - 1)
            if x1 < x0 or y1 < y0: continue
            X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
            if abs(den) < 1e-9: continue
            l0 = ((ys[1] - ys[2]) * (X - xs[2]) + (xs[2] - xs[1]) * (Y - ys[2])) / den
            l1 = ((ys[2] - ys[0]) * (X - xs[2]) + (xs[0] - xs[2]) * (Y - ys[2])) / den
            l2 = 1 - l0 - l1
            ins = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
            if not ins.any(): continue
            # perspective-correct depth
            iz = l0 / z[a] + l1 / z[b] + l2 / z[c]
            zz = 1 / iz
            yy = Y.astype(int); xx = X.astype(int)
            closer = ins & (zz < zbuf[yy, xx])
            if not closer.any(): continue
            if 'alpha' in bk:
                pcs = np.stack([l0 / z[a], l1 / z[b], l2 / z[c]], -1) * zz[..., None]
                UVp = pcs @ uv[[a, b, c]]
                AH, AW = bk['alpha'].shape[:2]
                av = bk['alpha'][np.floor(UVp[..., 1] * AH).astype(int) % AH, np.floor(UVp[..., 0] * AW).astype(int) % AW]
                closer &= av >= 0.5
                if not closer.any(): continue
            zbuf[yy[closer], xx[closer]] = zz[closer]
            fid[yy[closer], xx[closer]] = f; mid[yy[closer], xx[closer]] = mi
            pc = np.stack([l0 / z[a], l1 / z[b], l2 / z[c]], -1) * zz[..., None]
            bary[yy[closer], xx[closer]] = pc[closer]
    img = np.zeros((H, W, 3)); img[:] = bg
    # sky gradient
    t = np.linspace(0, 1, H)[:, None]
    img[:] = np.array(bg) * (1 - 0.25 * t[..., None]) + 0.0
    L = np.asarray(sun, float); L /= np.linalg.norm(L)
    for mi, (m, uv, bk) in enumerate(meshes):
        sel = mid == mi
        if not sel.any(): continue
        f = fid[sel]; b = bary[sel]
        Fv = m.F[f]
        P = (m.V[Fv] * b[..., None]).sum(1)
        N = (m.N[Fv] * b[..., None]).sum(1); N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-9
        UV = (uv[Fv] * b[..., None]).sum(1)
        SH, SW = bk['color'].shape[:2]
        px = np.floor(UV[:, 0] * SW).astype(int) % SW; py = np.floor(UV[:, 1] * SH).astype(int) % SH
        col = bk['color'][py, px]; nm = bk['normal'][py, px]; ro = bk['rough'][py, px]; ao = bk['ao'][py, px]; me = bk['metal'][py, px]
        # tangent frame per face from uv derivatives
        p0, p1, p2 = m.V[Fv[:, 0]], m.V[Fv[:, 1]], m.V[Fv[:, 2]]
        t0, t1, t2 = uv[Fv[:, 0]], uv[Fv[:, 1]], uv[Fv[:, 2]]
        e1, e2 = p1 - p0, p2 - p0
        d1, d2 = t1 - t0, t2 - t0
        r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
        r = np.where(np.abs(r) < 1e-12, 1e-12, r)
        Tg = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / r[:, None]
        Bg = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / r[:, None]   # direction of increasing v_img (down the image)
        Tg -= N * np.einsum('ij,ij->i', Tg, N)[:, None]; Tg /= np.linalg.norm(Tg, axis=1, keepdims=True) + 1e-9
        Bg = -Bg   # +V (GL) = up the image
        Bg -= N * np.einsum('ij,ij->i', Bg, N)[:, None]; Bg /= np.linalg.norm(Bg, axis=1, keepdims=True) + 1e-9
        Nn = Tg * nm[:, 0:1] + Bg * nm[:, 1:2] + N * nm[:, 2:3]
        Nn /= np.linalg.norm(Nn, axis=1, keepdims=True) + 1e-9
        V = eye - P; V /= np.linalg.norm(V, axis=1, keepdims=True)
        ndl = np.clip(Nn @ L, 0, 1)
        Hh = (L + V); Hh /= np.linalg.norm(Hh, axis=1, keepdims=True)
        ndh = np.clip(np.einsum('ij,ij->i', Nn, Hh), 0, 1)
        a = np.clip(ro, 0.05, 1) ** 2
        D = a * a / (np.pi * (ndh * ndh * (a * a - 1) + 1) ** 2 + 1e-6)
        F0 = 0.04 * (1 - me[:, None]) + col * me[:, None]
        spec = F0 * (D * 0.25)[:, None]
        sky = 0.45 + 0.25 * Nn[:, 2]
        lin = (col ** 2.2)
        diff = lin * (1 - me[:, None]) * (ndl[:, None] * np.array([1.0, 0.95, 0.85]) * 1.6 + sky[:, None] * np.array([0.55, 0.6, 0.7]) * ao[:, None])
        c = (diff + spec * ndl[:, None] * 2.0) * exposure
        c = c / (1 + c)  # tonemap
        img[sel] = c ** (1 / 2.2) * 1.15
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def turntable(meshes, center, radius, out, n=4, elev=20, W=640, H=480, fov=40):
    tiles = []
    for k in range(n):
        ang = np.radians(35 + k * 360.0 / n)
        e = np.radians(elev)
        eye = np.asarray(center) + radius * np.array([np.cos(ang) * np.cos(e), np.sin(ang) * np.cos(e), np.sin(e)])
        tiles.append(render(meshes, eye, center, W, H, fov))
    cols = 2
    rows = (n + 1) // 2
    sheet = np.zeros((rows * H, cols * W, 3), np.uint8)
    for k, t in enumerate(tiles):
        r, c = divmod(k, cols); sheet[r * H:(r + 1) * H, c * W:(c + 1) * W] = t
    Image.fromarray(sheet).save(out)
