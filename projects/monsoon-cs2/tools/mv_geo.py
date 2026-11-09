"""Geometry helpers for the mg_monsoon props, on top of create/geo.py: lofts through rounded cross-sections, cylinders between
points, boxes, mirroring, face removal (door openings), decal text images, hull point sets."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import geo
from noise import fbm

FONTS = [r'C:\Windows\Fonts', '/usr/share/fonts/truetype/dejavu']


def font(names, size):
    for n in names:
        for d in FONTS:
            p = os.path.join(d, n)
            if os.path.exists(p):
                try: return ImageFont.truetype(p, size)
                except Exception: pass
    return ImageFont.load_default()


STENCIL = ['impact.ttf', 'arialbd.ttf', 'DejaVuSansCondensed-Bold.ttf']
SANS = ['arialbd.ttf', 'DejaVuSansCondensed-Bold.ttf']
SERIF = ['georgiab.ttf', 'DejaVuSerif-Bold.ttf']


def text_img(lines, w=512, h=128, color=(0.92, 0.90, 0.85), fonts=STENCIL, rough=True, size=None, align='c'):
    """RGBA 0..1 image of centred lines of text, optionally weathered like a hand stencil"""
    im = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(im)
    n = len(lines)
    fs = size or int(h / (n + 0.4) * 0.8)
    f = font(fonts, fs)
    for i, t in enumerate(lines):
        bb = d.textbbox((0, 0), t, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        f2 = f
        if tw > w * 0.92:
            f2 = font(fonts, int(fs * (w * 0.92) / max(tw, 1))); bb = d.textbbox((0, 0), t, font=f2); tw, th = bb[2] - bb[0], bb[3] - bb[1]
        y = (i + 0.5) * h / n - th / 2 - bb[1]
        x = (w - tw) / 2 - bb[0] if align == 'c' else (8 - bb[0] if align == 'l' else w - tw - 8 - bb[0])
        d.text((x, y), t, fill=255, font=f2)
    a = np.asarray(im, np.float32) / 255.0
    if rough:
        yy, xx = np.mgrid[0:h, 0:w]
        n1 = fbm(xx * 0.05, yy * 0.05, 1.0, 3, seed=5)
        a = a * np.clip(0.78 + 0.45 * n1, 0, 1)
        a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7)), np.float32) / 255
    rgba = np.zeros((h, w, 4), np.float32); rgba[..., :3] = color; rgba[..., 3] = a
    return rgba


def star_img(w=256, color=(0.92, 0.92, 0.9), bars=True):
    """US national insignia (white star, blue disc, bars) simplified"""
    im = Image.new('RGBA', (w, w), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    c = w / 2; r = w * 0.34
    d.ellipse([c - r, c - r, c + r, c + r], fill=(50, 60, 120, 255))
    pts = []
    for k in range(10):
        ang = -np.pi / 2 + k * np.pi / 5; rr = r * 0.9 if k % 2 == 0 else r * 0.36
        pts.append((c + rr * np.cos(ang), c + rr * np.sin(ang)))
    d.polygon(pts, fill=(235, 235, 230, 255))
    if bars:
        d.rectangle([0, c - r * 0.42, c - r * 0.5, c + r * 0.42], fill=(50, 60, 120, 255))
        d.rectangle([c + r * 0.5, c - r * 0.42, w, c + r * 0.42], fill=(50, 60, 120, 255))
        d.rectangle([0, c - r * 0.3, c - r * 0.5, c + r * 0.3], fill=(235, 235, 230, 255))
        d.rectangle([c + r * 0.5, c - r * 0.3, w, c + r * 0.3], fill=(235, 235, 230, 255))
    return np.asarray(im, np.float32) / 255.0


def rgba_disc(w=128, color=(0.75, 0.1, 0.1), ring=None):
    im = Image.new('RGBA', (w, w), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([2, 2, w - 3, w - 3], fill=tuple(int(c * 255) for c in color) + (255,))
    if ring: d.ellipse([w * 0.3, w * 0.3, w * 0.7, w * 0.7], fill=tuple(int(c * 255) for c in ring) + (255,))
    return np.asarray(im, np.float32) / 255.0


def red_star_img(w=256, color=(0.80, 0.10, 0.08), outline=(0.95, 0.92, 0.85)):
    """five-pointed star with a thin light outline"""
    im = Image.new('RGBA', (w, w), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    c = w / 2
    def star(r):
        pts = []
        for k in range(10):
            ang = -np.pi / 2 + k * np.pi / 5; rr = r if k % 2 == 0 else r * 0.38
            pts.append((c + rr * np.cos(ang), c + rr * np.sin(ang)))
        return pts
    d.polygon(star(w * 0.47), fill=tuple(int(x * 255) for x in outline) + (255,))
    d.polygon(star(w * 0.42), fill=tuple(int(x * 255) for x in color) + (255,))
    return np.asarray(im, np.float32) / 255.0


# ---------------------------------------------------------------- sections and lofts
def rrect_section(w, zlo, zhi, n_pow=3.0, n=24, y_off=0.0, flat_bottom=0.0):
    """closed loop of (y, z) points: superellipse of half width w between zlo and zhi; n_pow 2 = ellipse, higher = boxier.
    flat_bottom 0..1 flattens the lower half toward a box."""
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    e = 2.0 / n_pow
    y = np.sign(c) * np.abs(c) ** e * w
    z = np.sign(s) * np.abs(s) ** e
    if flat_bottom:
        zb = np.where(s < 0, -1.0 + (1 - flat_bottom) * (z + 1.0), z)
        z = zb
    zc = (zlo + zhi) / 2; h = (zhi - zlo) / 2
    return np.stack([y + y_off, zc + z * h], 1)


def loft(sections, mat, part=None, n=24, cap_front=True, cap_back=True, seam_split=1):
    """sections: list of (x, loop (n,2) of (y,z)); all loops must have n points in the same angular order.
    Returns a Mesh; seam_split > 1 splits the skin into that many charts along the loop (panel lines at chart edges)."""
    xs = [s[0] for s in sections]
    P = np.zeros((len(sections), n + 1, 3))
    for i, (x, loop) in enumerate(sections):
        loop = np.asarray(loop, float)
        P[i, :n, 0] = x; P[i, :n, 1] = loop[:, 0]; P[i, :n, 2] = loop[:, 1]
        P[i, n] = P[i, 0]
    m = geo.Mesh()
    k = max(1, int(seam_split))
    bounds = np.linspace(0, n, k + 1).astype(int)
    for j in range(k):
        a, b = bounds[j], bounds[j + 1]
        sub = P[:, a:b + 1]
        s = geo.surface(sub, mat, part)
        # orientation: normals should point away from the section centre
        cen = np.array([0.0, 0.0, 0.0]); cen[2] = P[..., 2].mean()
        fn = s.face_normals(); fc = s.V[s.F].mean(1); out = fc - np.array([fc[:, 0].mean() * 0, 0, cen[2]]); out[:, 0] = 0
        if np.einsum('ij,ij->i', fn, out).mean() < 0: s.F = s.F[:, ::-1]
        m.add(s)
    if cap_front:
        ring = P[-1, :n]; m.add(geo.disk(ring.mean(0), ring, np.array([1.0, 0, 0]) * np.sign(xs[-1] - xs[0]), mat, part))
    if cap_back:
        ring = P[0, :n]; m.add(geo.disk(ring.mean(0), ring, np.array([1.0, 0, 0]) * -np.sign(xs[-1] - xs[0]), mat, part))
    m.recompute_normals(angle=48)
    return m


def cyl(p0, p1, r, mat, part=None, sides=12, caps=True, r1=None):
    """cylinder (or cone when r1 is given) between two points"""
    p0 = np.asarray(p0, float); p1 = np.asarray(p1, float)
    d = p1 - p0; L = np.linalg.norm(d)
    if L < 1e-6: return geo.Mesh()
    pts = np.stack([p0, p0 + d * 0.5, p1])
    radii = [r, (r + (r1 if r1 is not None else r)) / 2, r1 if r1 is not None else r]
    return geo.tube(pts, radii, sides=sides, mat=mat, part=part, caps=caps)


def box(x0, y0, z0, x1, y1, z1, mat, part=None, r=0.4, seg=1, div=(1, 1, 1)):
    sx, sy, sz = x1 - x0, y1 - y0, z1 - z0
    return geo.rbox(sx, sy, sz, r=r, seg=seg, mat=mat, part=part, div=div, center=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))


def obox(center, size, R, mat, part=None, r=0.4, seg=1):
    m = geo.rbox(size[0], size[1], size[2], r=r, seg=seg, mat=mat, part=part)
    m.transform(R, center)
    return m


def plate(p0, u, v, mat, part=None, thick=0.6, double=False):
    """thin quad plate: origin p0, edge vectors u and v (3D), extruded by thick along u x v"""
    p0 = np.asarray(p0, float); u = np.asarray(u, float); v = np.asarray(v, float)
    nrm = np.cross(u, v); nrm /= np.linalg.norm(nrm)
    R = np.stack([u / np.linalg.norm(u), v / np.linalg.norm(v), nrm], 1)
    c = p0 + u / 2 + v / 2 + nrm * thick / 2
    m = geo.rbox(np.linalg.norm(u), np.linalg.norm(v), thick, r=min(0.3, thick * 0.4), seg=1, mat=mat, part=part)
    m.transform(R, c)
    return m


def mirror_y(m):
    c = m.copy()
    R = np.diag([1.0, -1.0, 1.0])
    c.transform(R)
    return c


def remove_faces(m, pred):
    """drop faces whose centroid satisfies pred(centroids (k,3)) -> bool"""
    cen = m.V[m.F].mean(1)
    keep = ~np.asarray(pred(cen), bool)
    m.F = m.F[keep]; m.FC = m.FC[keep]; m.FP = m.FP[keep]
    return m


def pts_box(x0, y0, z0, x1, y1, z1):
    return np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)], float)


def pts_of(m):
    return m.V.copy()


def tag(m, **kw):
    """set part parameters on every part of a mesh (seed, tone, soot ...)"""
    for p in m.parts: p.update(kw)
    return m


def lathe_x(profile, mat, sides=16, part=None, x0=0.0):
    """revolve (r, x) profile around the +x axis (geo.lathe revolves around z; rotate)"""
    m = geo.lathe([(r, x) for r, x in profile], sides=sides, mat=mat, part=part)
    m.transform(geo.rot('y', 90), (x0, 0, 0))
    return m
