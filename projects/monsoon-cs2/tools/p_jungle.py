"""Jungle and paddy dressing: elephant grass (3 clusters), rice clumps, marsh reeds, a bamboo clump, a rubber tree with a tapping
cut and cup, a fallen log, a dead tree, a vine curtain, a root tangle, the capture-point flag pole (3 colours) and the flag supply
crates (kit station). Foliage is alpha-tested cards in a 'cut' atlas: painted RGBA strips (below) sampled per card.
Origins on the ground. Grass, rice, reeds and vines have no collision.

Flag skins: build_prop has no material groups, so the pole is built three times (flag_pole_n white, flag_pole_t red, flag_pole_ct
blue: same mesh, same atlas layout) and `python p_jungle.py` then writes models/mv/flag_pole/flag_pole.vmdl: flag_pole_n's meshes,
archetype "" (prop_dynamic), material groups t and ct remapping to the other two vmats -> Skin 0 neutral, 1 T, 2 CT.
"""
import os, sys, json
import numpy as np
from PIL import Image, ImageDraw
import geo
import mv_geo as MG
import mv_shaders as M
import shaders as S
from noise import fbm, smoothstep

_IMG = {}
SS = 3      # supersampling of the painted strips


# ---------------------------------------------------------------- painted strips (RGBA 0..1)
def _begin(W, H, bg):
    rgb = Image.new('RGB', (W * SS, H * SS), tuple(int(c * 255) for c in bg)); a = Image.new('L', (W * SS, H * SS), 0)
    return rgb, a, ImageDraw.Draw(rgb), ImageDraw.Draw(a)


def _end(rgb, a, W, H):
    rgb = rgb.resize((W, H), Image.LANCZOS); a = a.resize((W, H), Image.LANCZOS)
    out = np.zeros((H, W, 4), np.float32)
    out[..., :3] = np.asarray(rgb, np.float32) / 255.0; out[..., 3] = np.asarray(a, np.float32) / 255.0
    return out


def _col(c): return tuple(int(np.clip(x, 0, 1) * 255) for x in c)


def _lerp(a, b, t): return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def _blade(d, da, x0, yb, hgt, lean, wid, c0, c1, n=9, droop=0.0, power=1.8):
    """tapered blade from (x0, yb) upward: leans by `lean` px at the tip, droops (tip falls back) by droop * hgt"""
    ts = np.linspace(0, 1, n)
    cx = x0 + lean * ts ** power
    cy = yb - hgt * (ts - droop * ts ** 3)
    hw = wid * 0.5 * (1 - ts) ** 0.65 + 0.6 * SS * (1 - ts)
    for k in range(n - 1):
        quad = [(cx[k] - hw[k], cy[k]), (cx[k] + hw[k], cy[k]), (cx[k + 1] + hw[k + 1], cy[k + 1]), (cx[k + 1] - hw[k + 1], cy[k + 1])]
        d.polygon(quad, fill=_col(_lerp(c0, c1, ts[k]))); da.polygon(quad, fill=255)
    return cx[-1], cy[-1]


def _leaf(d, da, cx, cy, ang, L, Wd, col, vein=None, n=9):
    """lanceolate leaf from its stalk end (cx, cy) along ang (radians, image space)"""
    ts = np.linspace(0, 1, n)
    hw = Wd * 0.5 * np.sin(np.pi * ts ** 0.8) ** 0.8
    ca, sa = np.cos(ang), np.sin(ang)
    left = [(cx + ca * t * L - sa * h, cy + sa * t * L + ca * h) for t, h in zip(ts, hw)]
    right = [(cx + ca * t * L + sa * h, cy + sa * t * L - ca * h) for t, h in zip(ts, hw)][::-1]
    d.polygon(left + right, fill=_col(col)); da.polygon(left + right, fill=255)
    if vein is not None:
        d.line([(cx, cy), (cx + ca * L * 0.92, cy + sa * L * 0.92)], fill=_col(vein), width=max(1, SS // 2))


def grass_img(kind='elephant', seed=1, W=256, H=512):
    key = (kind, seed)
    if key in _IMG: return _IMG[key]
    rng = np.random.RandomState(seed)
    pal = dict(elephant=((0.20, 0.27, 0.09), (0.50, 0.56, 0.22), (0.66, 0.60, 0.34)),
               rice=((0.17, 0.33, 0.08), (0.45, 0.62, 0.17), (0.74, 0.70, 0.30)),
               reed=((0.20, 0.28, 0.10), (0.44, 0.52, 0.22), (0.58, 0.52, 0.30)))[kind]
    rgb, a, d, da = _begin(W, H, pal[0])
    w, h = W * SS, H * SS
    n = dict(elephant=64, rice=56, reed=30)[kind]
    tips = []
    for i in range(n):
        depth = i / (n - 1.0)
        x0 = float(np.clip(rng.normal(0.5, 0.17), 0.10, 0.90)) * w
        if kind == 'elephant':
            hg = h * rng.uniform(0.55, 1.0) * (0.85 + 0.15 * depth); lean = rng.normal(0, 0.13) * w + (x0 - w / 2) * 0.6
            wid = rng.uniform(4.0, 7.5) * SS; droop = rng.uniform(0.0, 0.22)
        elif kind == 'rice':
            x0 = float(np.clip(rng.normal(0.5, 0.07), 0.3, 0.7)) * w
            hg = h * rng.uniform(0.55, 0.98); lean = rng.normal(0, 0.24) * w
            wid = rng.uniform(5.0, 9.0) * SS; droop = rng.uniform(0.05, 0.32)
        else:
            hg = h * rng.uniform(0.55, 0.98); lean = rng.normal(0, 0.05) * w + (x0 - w / 2) * 0.25
            wid = rng.uniform(3.0, 5.5) * SS; droop = rng.uniform(0.0, 0.08)
        lean = float(np.clip(lean, -x0 + 6 * SS, w - x0 - 6 * SS))
        dry = rng.rand() < (0.22 if kind != 'rice' else 0.08)
        t = 0.25 + 0.75 * depth * rng.uniform(0.6, 1.0)
        c1 = _lerp(pal[0], pal[2] if dry else pal[1], t)
        c0 = _lerp(pal[0], c1, 0.35)
        tx, ty = _blade(d, da, x0, h + 4, hg, lean, wid, c0, c1, droop=droop)
        tips.append((tx, ty, depth, x0, hg))
    for i in range(26):          # short ragged blades across the foot so the base is not a block
        x0 = rng.uniform(0.06, 0.94) * w
        hg = h * rng.uniform(0.12, 0.38); lean = float(np.clip(rng.normal(0, 0.08) * w, -x0 + 4 * SS, w - x0 - 4 * SS))
        c1 = _lerp(pal[0], pal[1], rng.uniform(0.3, 0.9))
        _blade(d, da, x0, h + 4, hg, lean, rng.uniform(3.0, 6.0) * SS, _lerp(pal[0], c1, 0.4), c1, droop=rng.uniform(0, 0.2))
    if kind == 'elephant':      # feathery plumes on some of the tallest stems
        for tx, ty, depth, x0, hg in tips:
            if hg > 0.8 * h and rng.rand() < 0.5:
                for k in range(9):
                    aa = -np.pi / 2 + rng.normal(0, 0.5)
                    _leaf(d, da, tx, ty + 14 * SS, aa, rng.uniform(14, 30) * SS, 3.2 * SS, _lerp((0.62, 0.55, 0.36), (0.80, 0.74, 0.55), rng.rand()))
    if kind == 'rice':          # drooping ears of grain
        for tx, ty, depth, x0, hg in tips:
            if rng.rand() < 0.45:
                for k in range(7):
                    px = tx + rng.normal(0, 2.5) * SS; py = ty + k * 4.0 * SS + rng.uniform(-1, 1) * SS
                    r = 2.4 * SS
                    d.ellipse([px - r, py - r * 1.4, px + r, py + r * 1.4], fill=_col(_lerp((0.66, 0.62, 0.22), (0.84, 0.76, 0.36), rng.rand())))
                    da.ellipse([px - r, py - r * 1.4, px + r, py + r * 1.4], fill=255)
    if kind == 'reed':          # cat-tail heads and a few long strap leaves
        for tx, ty, depth, x0, hg in tips:
            if rng.rand() < 0.4:
                r = 4.6 * SS; l = rng.uniform(26, 40) * SS; y0 = ty + rng.uniform(10, 26) * SS
                box = [tx - r, y0, tx + r, y0 + l]
                d.rounded_rectangle(box, radius=r, fill=_col(_lerp((0.24, 0.15, 0.08), (0.38, 0.25, 0.13), rng.rand())))
                da.rounded_rectangle(box, radius=r, fill=255)
    _IMG[key] = _end(rgb, a, W, H)
    return _IMG[key]


def spray_img(kind='bamboo', seed=1, W=256, H=256):
    """a leafy spray growing up from the bottom centre. bamboo: thin twigs with narrow leaves; crown: broad glossy leaves in whorls"""
    key = ('spray', kind, seed, W, H)
    if key in _IMG: return _IMG[key]
    rng = np.random.RandomState(seed)
    dark, mid, lite = dict(bamboo=((0.16, 0.26, 0.07), (0.33, 0.47, 0.14), (0.55, 0.62, 0.24)),
                           crown=((0.08, 0.18, 0.06), (0.17, 0.33, 0.10), (0.36, 0.48, 0.16)))[kind]
    rgb, a, d, da = _begin(W, H, mid)
    w, h = W * SS, H * SS
    if kind == 'bamboo':
        for i in range(7):
            ang = -np.pi / 2 + (i - 3) * 0.24 + rng.normal(0, 0.06)
            L = h * rng.uniform(0.50, 0.74)
            pts = [(w / 2 + np.cos(ang) * L * t + np.sin(t * 2.5) * 6 * SS * (i % 2 * 2 - 1), h - 2 + np.sin(ang) * L * t + 0.18 * L * t * t) for t in np.linspace(0, 1, 9)]
            d.line(pts, fill=_col((0.36, 0.38, 0.16)), width=2 * SS); da.line(pts, fill=255, width=2 * SS)
            for k, (px, py) in enumerate(pts[2:]):
                for sgn in (-1, 1):
                    la = ang + sgn * rng.uniform(0.5, 1.1) + 0.25
                    _leaf(d, da, px, py, la, rng.uniform(24, 38) * SS, rng.uniform(6.0, 8.5) * SS, _lerp(dark, lite, rng.uniform(0.15, 1.0)), vein=_lerp(mid, lite, 0.8))
    else:
        nodes = [(w / 2, h * 0.80, -np.pi / 2)]
        for i in range(5):
            ang = -np.pi / 2 + (i - 2) * 0.62 + rng.normal(0, 0.1)
            L = h * rng.uniform(0.26, 0.40)
            ex, ey = w / 2 + np.cos(ang) * L, h * 0.80 + np.sin(ang) * L
            d.line([(w / 2, h * 0.80), (ex, ey)], fill=_col((0.26, 0.22, 0.14)), width=3 * SS); da.line([(w / 2, h * 0.80), (ex, ey)], fill=255, width=3 * SS)
            for t in (0.45, 0.72, 1.0): nodes.append((w / 2 + np.cos(ang) * L * t, h * 0.80 + np.sin(ang) * L * t, ang))
        order = rng.permutation(len(nodes))
        for pass_ in range(2):
            for j in order:
                nx, ny, na = nodes[j]
                for k in range(3):          # trifoliate leaves on a short stalk
                    sa = na + rng.normal(0, 0.9)
                    sx, sy = nx + np.cos(sa) * 12 * SS, ny + np.sin(sa) * 12 * SS
                    for q in (-0.55, 0.0, 0.55):
                        c = _lerp(dark, lite, rng.uniform(0.0, 0.55) + 0.4 * pass_)
                        _leaf(d, da, sx, sy, sa + q, rng.uniform(26, 38) * SS, rng.uniform(12, 17) * SS, c, vein=_lerp(c, lite, 0.6))
    _IMG[key] = _end(rgb, a, W, H)
    return _IMG[key]


def vine_img(seed=1, W=192, H=768):
    key = ('vine', seed)
    if key in _IMG: return _IMG[key]
    rng = np.random.RandomState(seed)
    dark, mid, lite = (0.10, 0.20, 0.06), (0.22, 0.36, 0.11), (0.40, 0.52, 0.18)
    rgb, a, d, da = _begin(W, H, mid)
    w, h = W * SS, H * SS
    for i in range(14):
        x0 = rng.uniform(0.1, 0.9) * w; L = h * rng.uniform(0.5, 1.0); ph = rng.uniform(0, 6); amp = rng.uniform(4, 12) * SS
        ys = np.linspace(0, L, 40)
        xs = np.clip(x0 + amp * np.sin(ys / h * rng.uniform(9, 16) + ph) + ys / h * rng.normal(0, 0.06) * w, 8 * SS, w - 8 * SS)
        pts = list(zip(xs, ys))
        wd = int(rng.uniform(1.6, 3.2) * SS)
        d.line(pts, fill=_col((0.24, 0.20, 0.12)), width=wd); da.line(pts, fill=255, width=wd)
        if i % 3 == 2: continue       # a bare aerial root
        for k in range(3, 40, 2):
            sgn = 1 if (k // 2) % 2 else -1
            la = np.pi / 2 - sgn * rng.uniform(0.5, 1.2)
            _leaf(d, da, xs[k], ys[k], la, rng.uniform(18, 30) * SS, rng.uniform(11, 17) * SS, _lerp(dark, lite, rng.uniform(0.1, 1.0)), vein=lite)
    _IMG[key] = _end(rgb, a, W, H)
    return _IMG[key]


def cargo_net_img(W=256):
    key = ('cnet', W)
    if key in _IMG: return _IMG[key]
    rgb, a, d, da = _begin(W, W, (0.36, 0.33, 0.22))
    w = W * SS; step = w // 8
    for x in range(-w, 2 * w, step):
        for dd, aa in ((d, (92, 84, 56)), (da, 255)):
            dd.line([(x, 0), (x + w, w)], fill=aa, width=3 * SS); dd.line([(x, w), (x + w, 0)], fill=aa, width=3 * SS)
    _IMG[key] = _end(rgb, a, W, W)
    return _IMG[key]


def card_shader(imgs, base_dark=0.45):
    """cut-out cards: part param img picks the strip, tone varies the brightness; darker toward the foot (self shadow)"""
    def sh(ctx):
        cw = np.array([[c['w'], c['h']] for c in ctx.chart_info])[ctx.chart]
        u = np.clip(ctx.S[:, 0] / cw[:, 0], 0, 1); v = np.clip(ctx.S[:, 1] / cw[:, 1], 0, 1)
        ids = S.part_param(ctx, 'img', 0).astype(int); tone = S.part_param(ctx, 'tone', 0.5); dk = S.part_param(ctx, 'foot', base_dark)
        col = np.zeros((ctx.n, 3), np.float32); al = np.zeros(ctx.n, np.float32)
        for i in np.unique(ids):
            sel = ids == i; img = imgs[i % len(imgs)]; H, W = img.shape[:2]
            px = np.clip((u[sel] * (W - 1)).astype(int), 0, W - 1); py = np.clip(((1 - v[sel]) * (H - 1)).astype(int), 0, H - 1)
            rgba = img[py, px]; col[sel] = rgba[:, :3]; al[sel] = rgba[:, 3]
        col = col * (0.80 + 0.40 * tone)[:, None] * (1 - dk * (1 - smoothstep(0.0, 0.55, v)))[:, None]
        n = fbm(ctx.P[:, 0] * 0.05, ctx.P[:, 1] * 0.05, ctx.P[:, 2] * 0.05, 2, seed=77)
        col = col * (0.93 + 0.14 * n[:, None])
        return dict(color=np.clip(col, 0, 1), rough=np.full(ctx.n, 0.78, np.float32), metal=al, height=np.zeros(ctx.n, np.float32))
    return sh


# ---------------------------------------------------------------- grass, rice, reeds
def clump(lod=0, seed=1, n=10, radius=28.0, height=92.0, width=56.0, nimg=3, elong=1.0, lean=0.16, ring=0.0):
    """a cluster of leaning cards; ring > 0 pushes cards out from the centre (a hollow tuft reads fuller from above)"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    for k in range(n):
        ang = rng.uniform(0, np.pi) if k % 3 else k * 1.05
        r = radius * (ring + (1 - ring) * np.sqrt(rng.rand())); th = rng.uniform(0, 2 * np.pi) if k else 0.0
        c = np.array([r * np.cos(th) * elong, r * np.sin(th), -2.0]) if k else np.array([0.0, 0.0, -2.0])
        ud = np.array([np.cos(ang), np.sin(ang), 0.0]); nd = np.array([-np.sin(ang), np.cos(ang), 0.0])
        if np.dot(nd, c) < 0: nd = -nd
        w = width * rng.uniform(0.85, 1.15); h = height * rng.uniform(0.82, 1.08)
        tilt = rng.uniform(0.02, lean)
        v = np.array([0, 0, h]) + nd * h * tilt
        m.add(MG.card(c - ud * w / 2, ud * w, v, 'card', geo.frame(seed=seed + k, tone=rng.rand(), img=int(rng.randint(nimg))),
                      bend=nd * h * rng.uniform(0.04, lean), nv=3))
    return m


def rice(lod=0, seed=1, patch=False):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    spots = [(0.0, 0.0)] if not patch else [(-18, -12), (16, -16), (-14, 16), (18, 12), (0, 0)]
    for i, (x, y) in enumerate(spots):
        c = clump(lod, seed * 7 + i, n=3 if patch else 4, radius=2.5, height=29.0, width=27.0, nimg=2, lean=0.22)
        c.transform(geo.rot('z', rng.uniform(0, 180)), (x + rng.uniform(-3, 3), y + rng.uniform(-3, 3), 0)); m.add(c)
    return m


# ---------------------------------------------------------------- bamboo, trees
def bamboo_clump(lod=0, seed=21):
    """a clump of living bamboo: 11 culms up to 300 u arching outward, leaf sprays on the upper half"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    sides = 7 if lod == 0 else 5
    for k in range(11):
        a = rng.uniform(0, 2 * np.pi); r = 20 * np.sqrt(rng.rand())
        base = np.array([r * np.cos(a), r * np.sin(a), -4.0])
        H = rng.uniform(190, 300) if k else 300.0
        out = np.array([np.cos(a), np.sin(a), 0.0]) * rng.uniform(20, 70) * (H / 300.0)
        ts = np.linspace(0, 1, 8)
        pts = base + ts[:, None] * np.array([0, 0, H]) + (ts ** 2.2)[:, None] * out
        r0 = rng.uniform(2.2, 3.4)
        d = pts[-1] - pts[0]
        m.add(geo.tube(pts, r0 * (1 - 0.72 * ts), sides=sides, mat='culm', part=geo.frame(R=geo.look_frame(d), o=base, seed=seed + k, live=rng.uniform(0.75, 1.0), tone=0.3)))
        for j in range(6):       # leaf sprays hanging off the upper culm
            t = rng.uniform(0.45, 1.0); p = base + t * np.array([0, 0, H]) + t ** 2.2 * out
            sa = rng.uniform(0, 2 * np.pi); sd = np.array([np.cos(sa), np.sin(sa), 0.0])
            w = rng.uniform(58, 80); h = rng.uniform(60, 84)
            ud = np.array([-sd[1], sd[0], 0.0])
            v = sd * h * 0.85 + np.array([0, 0, h * rng.uniform(0.15, 0.5)])
            m.add(MG.card(p - ud * w / 2, ud * w, v, 'card', geo.frame(seed=seed + k * 9 + j, tone=rng.rand(), img=int(rng.randint(2)), foot=0.1),
                          bend=np.array([0, 0, -h * rng.uniform(0.3, 0.7)]), nv=3, up=0.6))
    # dead sheaths and a couple of cut stumps at the foot
    for k in range(4):
        a = rng.uniform(0, 2 * np.pi)
        p = np.array([24 * np.cos(a), 24 * np.sin(a), -3.0])
        m.add(geo.tube([p, p + np.array([0, 0, rng.uniform(10, 26)])], 2.6, sides=sides, mat='culm', part=geo.frame(R=geo.rot('y', -90), o=p, seed=seed + 60 + k, live=0.0, tone=0.8)))
    return m


def rubber_tree(lod=0, seed=22):
    """plantation rubber tree: straight pale trunk to 420 u, a tapping cut spiralling half way round at chest height with a latex
    run and a cup on a wire, a crown of leaf cards on six limbs"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    sides = 12 if lod == 0 else 8
    top = np.array([10.0, -6.0, 330.0])
    ts = np.linspace(0, 1, 9)
    pts = np.array([0, 0, -6.0]) + ts[:, None] * (top - np.array([0, 0, -6.0])) + np.sin(ts * np.pi)[:, None] * np.array([4.0, 3.0, 0])
    rad = 10.5 - 4.5 * ts; rad[0] = 13.0; rad[1] = 11.0
    m.add(geo.tube(pts, rad, sides=sides, mat='rbark', part=geo.frame(seed=seed)))
    ends = []
    for k in range(6):
        a = k * 2 * np.pi / 6 + rng.uniform(-0.3, 0.3)
        p0 = pts[-1] - np.array([0, 0, rng.uniform(0, 60)])
        p1 = p0 + np.array([np.cos(a) * rng.uniform(60, 105), np.sin(a) * rng.uniform(60, 105), rng.uniform(50, 100)])
        m.add(MG.limb(p0, p1, 5.2, 1.6, 'rbark', seed + 10 + k, sides=6 if lod == 0 else 5, n=4, wob=3.0))
        ends.append(p1); ends.append((p0 + p1) / 2 + np.array([0, 0, 14.0]))
    m.add(MG.limb(pts[-1], pts[-1] + np.array([4, -3, 86.0]), 5.6, 1.4, 'rbark', seed + 20, sides=6, n=4, wob=2.5))
    ends.append(pts[-1] + np.array([4, -3, 86.0]))
    for k in range(46):          # crown cards: tilted plates around the limb ends, every third one upright so the crown has depth
        c = ends[k % len(ends)] + rng.normal(0, 18, 3) * np.array([1, 1, 0.6])
        a = rng.uniform(0, 2 * np.pi); tilt = np.radians(rng.uniform(62, 88) if k % 3 == 0 else rng.uniform(8, 50))
        ud = np.array([np.cos(a), np.sin(a), 0.0]); hd = np.array([-np.sin(a), np.cos(a), 0.0])
        if np.dot(hd[:2], c[:2] - top[:2]) < 0: hd = -hd
        w = rng.uniform(112, 146)
        v = (hd * np.cos(tilt) + np.array([0, 0, np.sin(tilt)])) * w
        m.add(MG.card(c - ud * w / 2 - v * 0.35, ud * w, v, 'card', geo.frame(seed=seed + 40 + k, tone=rng.rand(), img=int(rng.randint(2)), foot=0.15),
                      bend=np.array([0, 0, -w * rng.uniform(0.05, 0.22)]), nv=2, up=0.7))
    # tapping panel on the +x side: the cut, the latex run, the spout and the cup
    R0 = 10.9
    th = np.radians(np.linspace(-78, 78, 12))
    zc = np.linspace(66, 44, 12)
    cut = np.stack([(R0 + 0.2) * np.cos(th) + 1.2, (R0 + 0.2) * np.sin(th) + 0.8, zc], 1)
    tp = geo.frame(seed=seed + 70)
    m.add(geo.tube(cut, 1.0, sides=5, mat='cutbark', part=tp))
    m.add(geo.tube(cut + np.array([0, 0, -1.1]), 0.6, sides=4, mat='latex', part=tp))
    end = cut[-1]
    m.add(geo.tube([end + np.array([0.3, 0, -1]), end + np.array([0.6, -0.4, -9]), end + np.array([1.0, -0.6, -15])], 0.7, sides=4, mat='latex', part=tp))
    cup_c = end + np.array([4.2, -0.6, -22.0])
    m.add(MG.plate(end + np.array([0.5, -2.0, -15.5]), (4.5, 0, -1.2), (0, 3.0, 0), 'tin', tp, thick=0.4))
    m.add(geo.lathe([(0, 0), (2.6, 0), (3.6, 5.0), (3.2, 5.0), (2.3, 0.6), (0, 0.6)], sides=10, mat='clay', part=tp).transform(None, cup_c))
    m.add(geo.disk(cup_c + np.array([0, 0, 3.6]), [cup_c + np.array([3.1 * np.cos(q), 3.1 * np.sin(q), 3.6]) for q in np.linspace(0, 2 * np.pi, 10, endpoint=False)], (0, 0, 1), 'latex', tp))
    ring = [np.array([(R0 + 0.3) * np.cos(q) + 0.9, (R0 + 0.3) * np.sin(q) + 0.6, cup_c[2] + 4.4]) for q in np.linspace(0, 2 * np.pi, 13)]
    m.add(geo.tube(ring, 0.25, sides=4, mat='tin', part=tp, caps=False))
    return m


def dead_tree(lod=0, seed=23):
    """bare, bleached snag 380 u tall with broken limbs"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    sides = 10 if lod == 0 else 7
    ts = np.linspace(0, 1, 10)
    pts = np.array([0, 0, -6.0]) + ts[:, None] * np.array([18.0, -10.0, 386.0]) + np.stack([np.sin(ts * 5) * 6, np.cos(ts * 4) * 5, 0 * ts], 1)
    rad = 15 - 11.5 * ts ** 0.8; rad[0] = 19
    m.add(geo.tube(pts, rad, sides=sides, mat='dead', part=geo.frame(seed=seed, stripped=1.0)))
    for k, t in enumerate((0.42, 0.55, 0.66, 0.78, 0.9)):
        i = int(t * 9); p0 = pts[i]
        a = k * 2.3 + rng.uniform(-0.4, 0.4); L = rng.uniform(70, 130) * (1.2 - t * 0.5)
        p1 = p0 + np.array([np.cos(a) * L, np.sin(a) * L, L * rng.uniform(0.25, 0.8)])
        m.add(MG.limb(p0, p1, rad[i] * 0.55, 1.6, 'dead', seed + 5 + k, sides=6, n=5, wob=5.0, stripped=1.0))
        if k % 2 == 0:
            q0 = p0 + (p1 - p0) * 0.6
            q1 = q0 + np.array([np.cos(a + 1.1) * L * 0.45, np.sin(a + 1.1) * L * 0.45, L * 0.35])
            m.add(MG.limb(q0, q1, rad[i] * 0.3, 0.9, 'dead', seed + 15 + k, sides=5, n=3, wob=3.0, stripped=1.0))
    for k in range(5):           # root flare
        a = k * 2 * np.pi / 5 + 0.4
        m.add(MG.limb((np.cos(a) * 10, np.sin(a) * 10, 22), (np.cos(a) * 42, np.sin(a) * 42, -5), 7.5, 2.5, 'dead', seed + 30 + k, sides=6, n=4, sag=-0.12, stripped=0.6))
    return m


def log_fallen(lod=0, seed=24):
    """mossy fallen trunk along x, 230 u, a torn root plate at -x, two limb stubs"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    sides = 12 if lod == 0 else 8
    xs = np.linspace(-112, 118, 9)
    pts = np.stack([xs, 4 * np.sin(xs * 0.012), 12.5 - 2.0 * (xs + 112) / 230 + 1.5 * np.sin(xs * 0.03)], 1)
    rad = 14.0 - 4.0 * (xs + 112) / 230
    m.add(geo.tube(pts, rad, sides=sides, mat='bark', part=geo.frame(seed=seed), rnoise=lambda th, s: 1 + 0.07 * np.sin(3 * th + s * 0.05) + 0.04 * np.sin(7 * th)))
    for k in range(7):
        a = k * 2 * np.pi / 7 + rng.uniform(-0.2, 0.2); L = rng.uniform(22, 40)
        m.add(MG.limb((-110, 0, 12), (-122 - rng.uniform(0, 14), np.cos(a) * L, 12 + np.sin(a) * L), 5.5, 1.2, 'bark', seed + 3 + k, sides=5, n=3, wob=2.0))
    m.add(MG.limb((20, 2, 20), (34, 20, 58), 5.0, 3.2, 'bark', seed + 20, sides=6, n=3, wob=1.5))
    m.add(MG.limb((70, -3, 16), (88, -34, 30), 4.0, 2.4, 'bark', seed + 21, sides=6, n=3, wob=1.5))
    return m


def root_tangle(lod=0, seed=25):
    """a rotted stump with buttress roots arching out over the ground"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    sides = 8 if lod == 0 else 6
    m.add(geo.tube([(0, 0, -4), (1, 0, 20), (3, 1, 44), (4, 2, 52)], [17, 14, 12.5, 9], sides=10, mat='bark', part=geo.frame(seed=seed),
                   rnoise=lambda th, s: 1 + 0.12 * np.sin(4 * th + s * 0.1)))
    for k in range(10):
        a = k * 2 * np.pi / 10 + rng.uniform(-0.25, 0.25); L = rng.uniform(46, 86)
        ts = np.linspace(0, 1, 7)
        r_ = 9 + (L - 9) * ts
        z = 40 * (1 - ts) ** 1.7 + 9 * np.sin(ts * np.pi) * rng.uniform(0.2, 1.3) - 3 * ts
        a2 = a + 0.5 * np.sin(ts * 3 + k) * ts
        pts = np.stack([np.cos(a2) * r_, np.sin(a2) * r_, z], 1)
        m.add(geo.tube(pts, 6.8 - 4.6 * ts, sides=sides, mat='bark', part=geo.frame(seed=seed + 1 + k)))
        if k % 3 == 0:
            j = 3
            q1 = pts[j] + np.array([np.cos(a + 1.2) * 30, np.sin(a + 1.2) * 30, -pts[j][2] - 2])
            m.add(MG.limb(pts[j], q1, 3.2, 1.2, 'bark', seed + 30 + k, sides=5, n=4, sag=-0.15))
    return m


def vine_curtain(lod=0, seed=26, W=150.0, H=200.0):
    """lianas hanging from a sagging vine 200 u up: five overlapping cards in three layers, plus a few bare rope-like roots.
    Origin on the ground under the middle; the curtain runs along x."""
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    top = lambda x: H - 6 - 14 * (1 - (2 * x / W) ** 2)
    xs = np.linspace(-W / 2 - 14, W / 2 + 14, 9)
    m.add(geo.tube(np.stack([xs, 2 * np.sin(xs * 0.05), [top(np.clip(x, -W / 2, W / 2)) + 6 + (8 if abs(x) > W / 2 else 0) for x in xs]], 1), 2.6, sides=6, mat='bark', part=geo.frame(seed=seed)))
    for k, (x, y) in enumerate(((-52, -5), (0, -7), (52, -4), (-26, 6), (27, 7))):
        w = rng.uniform(58, 70); h = top(x) + 2 - rng.uniform(0, 26)
        yaw = rng.uniform(-0.22, 0.22)
        ud = np.array([np.cos(yaw), np.sin(yaw), 0.0])
        p_top = np.array([x, y, top(x) + 4]) - ud * w / 2
        # card v runs upward: start at the bottom so the image top (where the strands start) is at the vine
        m.add(MG.card(p_top - np.array([0, 0, h]), ud * w, np.array([0, rng.uniform(-6, 6), h]), 'card',
                      geo.frame(seed=seed + k, tone=rng.rand(), img=k % 2, foot=0.0), nv=3, up=0.15))
    for k in range(5):
        x = rng.uniform(-W / 2, W / 2); L = rng.uniform(90, 190)
        m.add(MG.limb((x, rng.uniform(-6, 6), top(x) + 4), (x + rng.uniform(-10, 10), rng.uniform(-8, 8), top(x) + 4 - L), 1.1, 0.5, 'bark', seed + 40 + k, sides=4, n=5, wob=2.0))
    return m


# ---------------------------------------------------------------- flag pole, supply crates
FLAG_COL = dict(n=(0.86, 0.85, 0.80), t=(0.70, 0.09, 0.07), ct=(0.10, 0.22, 0.56))


def flag_pole(lod=0, seed=27, team='n'):
    """capture-point flag: a 200 u bamboo pole in a cairn of stones with two sandbags, a cotton flag flying toward +x"""
    import p_sandbag
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    m.add(geo.tube([(0, 0, -6), (0.5, 0.2, 100), (0, 0, 200)], [2.7, 2.4, 1.9], sides=8, mat='bamboo', part=geo.frame(R=geo.rot('y', -90), seed=seed, tone=0.45)))
    for k in range(8):
        a = k * 2 * np.pi / 8 + rng.uniform(-0.2, 0.2); r = rng.uniform(7, 12)
        s = geo.rbox(rng.uniform(8, 13), rng.uniform(7, 10), rng.uniform(5, 9), r=2.6, seg=2, mat='stone', part=geo.frame(seed=seed + k, mono=1.0))
        s.transform(geo.euler(rng.uniform(0, 360), rng.uniform(-12, 12), rng.uniform(-12, 12)), (r * np.cos(a), r * np.sin(a), 2.5 + (k % 2) * 3.5)); m.add(s)
    for k, (a, r) in enumerate(((200, 17), (320, 16))):
        b = p_sandbag.bag(seed=seed + 20 + k, squash=0.2, lod=lod)
        b.transform(geo.euler(a + 90, 0, 0), (r * np.cos(np.radians(a)), r * np.sin(np.radians(a)), 0)); m.add(b)
    # the flag: 60 x 38, rippling, hanging a little
    nu, nv = 12, 6
    U, V = np.meshgrid(np.linspace(0, 1, nu + 1), np.linspace(0, 1, nv + 1), indexing='ij')
    X = 2.2 + 60 * U * (1 - 0.06 * np.sin(V * 3.0))
    Y = (4.5 * np.sin(U * 9.0 + V * 1.5) + 2.0 * np.sin(U * 17.0 + 1.0)) * U ** 0.8
    Z = 158 + 38 * V - 9.0 * U ** 1.6 - 1.5 * np.sin(U * 9.0)
    m.add(MG.sheet(np.stack([X, Y, Z], -1), 'flag', geo.frame(seed=seed + 40)))
    for z in (196, 159): m.add(geo.tube([(0, -2.2, z), (2.4, 0, z - 0.5), (0, 2.2, z)], 0.35, sides=4, mat='rope', part=geo.frame(seed=seed + 41)))
    m.add(geo.tube([(0, 0, 200), (0, 0, 203)], [2.3, 0.4], sides=8, mat='bamboo', part=geo.frame(R=geo.rot('y', -90), seed=seed + 2, tone=0.8)))
    return m


def crate(L=48.0, W=28.0, H=22.0, seed=1, lid=0.0):
    """slatted wooden crate: plank body, corner battens, rope handles; lid > 0 lifts and skews the lid"""
    m = geo.Mesh()
    p = geo.frame(seed=seed, tone=0.5)
    m.add(geo.plank(L, W, H - 2.2, mat='wood', seed=seed, r=0.5, div=(3, 1, 1), t=(0, 0, (H - 2.2) / 2)))
    for s in (-1, 1):
        for xx in (-L / 2 + 5, L / 2 - 5):
            m.add(geo.plank(H - 2.6, 4.0, 1.2, mat='wood', seed=seed + 3 + int(xx) + s, R=geo.rot('y', 90), t=(xx, s * (W / 2 + 0.5), (H - 2.6) / 2), r=0.3, div=(1, 1, 1)))
        m.add(MG.cyl((s * (L / 2 + 0.6), -5, H * 0.62), (s * (L / 2 + 0.6), 5, H * 0.62), 0.8, 'rope', p, sides=6))
    for k in range(3):
        yy = -W / 2 + W / 6 + k * W / 3
        lidm = geo.plank(L + 1.5, W / 3 - 0.5, 2.0, mat='wood', seed=seed + 20 + k, r=0.4, div=(2, 1, 1), t=(0, yy, H - 1.0))
        if lid: lidm.transform(geo.euler(6 * lid, 0, 4 * lid * (k - 1)), (2 * lid, 0, 1.4 * lid))
        m.add(lidm)
    return m


def supply_crate(lod=0, seed=28):
    """flag kit station: three crates (one on top, lid ajar), a tarp over the far side, ammo cans, a radio, a jerry can"""
    import p_base
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    m.add(crate(seed=seed + 1).transform(geo.rot('z', 3), (0, -16, 0)))
    m.add(crate(seed=seed + 2).transform(geo.rot('z', -6), (3, 16, 0)))
    m.add(crate(44, 26, 20, seed=seed + 3, lid=1.0).transform(geo.rot('z', 14), (-2, -6, 22.4)))
    m.add(MG.drape(-34, 22, 2, 50, [(-22, 2, 28, 30, 22.6), (-24, -19, 6, 7, 43.0)], 'tarp', geo.frame(seed=seed + 5), n=22, blur=1.5, lift=0.9, wrinkle=1.6, seed=seed))
    for k, (x, y, a) in enumerate(((36, -22, 10), (38, -11, -8), (37, -16, 95))):
        c = p_base.ammo_can(lod, seed + 10 + k); c.transform(geo.rot('z', a), (x, y, 0 if k < 2 else 10.6)); m.add(c)
    m.add(p_base.jerry_can(lod, seed + 14).transform(geo.rot('z', 70), (-36, -22, 0)))
    m.add(p_base.radio_prc25(lod, seed + 15).transform(geo.rot('z', -20), (10, -8, 42.6)))
    m.add(geo.tube([(27, -20, 0.6), (30, -30, 0.5), (22, -36, 0.5), (14, -31, 0.6), (18, -24, 0.6)], 0.7, sides=5, mat='rope', part=p))
    ST = MG.text_img(['SUPPLIES', 'E: RIFLE  MG  AT'], 256, 96, color=(0.08, 0.08, 0.07), fonts=MG.STENCIL, size=30)
    R3 = geo.rot('z', 3)
    o = R3 @ np.array([-17.0, -14.6, 5.0]) + np.array([0, -16, 0])
    m.add(geo.decal('st', o, R3 @ np.array([1.0, 0, 0]), (0, 0, 1), (34, 12.5), lift=0.12))
    return m, dict(st=ST)


# ---------------------------------------------------------------- specs
def _sh(flag='n'):
    return {'card': None, 'culm': M.bamboo, 'bamboo': M.bamboo, 'bark': M.jungle_bark, 'rbark': lambda c: M.jungle_bark(c, pale=1.0),
            'dead': lambda c: S.bark(c, char_amount=0.12), 'cutbark': lambda c: dict(color=np.tile(S._c(0.36, 0.17, 0.10), (c.n, 1)) * (0.8 + 0.3 * c.ao[:, None]), rough=np.full(c.n, 0.8, np.float32)),
            'latex': lambda c: dict(color=np.tile(S._c(0.90, 0.89, 0.84), (c.n, 1)) * (0.75 + 0.25 * c.ao[:, None]), rough=np.full(c.n, 0.35, np.float32)),
            'tin': S.galvanised, 'clay': lambda c: M.concrete(c, tone=S._c(0.46, 0.29, 0.21), damage=0.2),
            'stone': lambda c: M.khmer_stone(c, tone=S._c(0.44, 0.43, 0.39), moss=0.6), 'burlap': S.burlap, 'rope': M.rope,
            'flag': lambda c: M.flag_cloth(c, base=S._c(*FLAG_COL[flag])), 'wood': M.wood, 'tarp': M.tarp, 'od': M.od_paint, 'gunsteel': M.gun_steel,
            'canvas': lambda c: S.canvas(c)}


def _spec(fn, imgs=None, size=1024, cut=1024, hulls=None, surface='wood', lod1=False, flag='n', thr=30.0, **kw):
    a = fn(lod=0, **kw)
    dimg = {}
    if isinstance(a, tuple): a, dimg = a
    lods = [a]
    if lod1:
        b = fn(lod=1, **kw)
        lods.append(b[0] if isinstance(b, tuple) else b)
    sh = _sh(flag); sh['card'] = card_shader(imgs or [grass_img()])
    spec = dict(lods=lods, size=size, decal_size=256, ground=0.0, surface=surface, metal=False, shaders=sh, decal_imgs=dimg, stock={},
                hulls=hulls if hulls is not None else [], normal_strength=1.0,
                atlases={'main': dict(size=size), 'cut': dict(size=cut, alpha=lambda b: b['metal'], metal=False, fill=0.9, backfaces=True)})
    if lod1: spec['lod_thresholds'] = [0.0, thr]
    else: spec['single_lod'] = True
    return spec


def specs():
    eg = lambda: [grass_img('elephant', 1), grass_img('elephant', 2), grass_img('elephant', 3)]
    rc = lambda: [grass_img('rice', 4, 192, 256), grass_img('rice', 5, 192, 256)]
    rd = lambda: [grass_img('reed', 6), grass_img('reed', 7)]
    B = MG.pts_box
    return {
        'elephant_grass_a': lambda: _spec(clump, eg(), surface='grass', seed=31, n=10, radius=28, height=92, width=58),
        'elephant_grass_b': lambda: _spec(clump, eg(), surface='grass', seed=32, n=15, radius=46, height=96, width=60, elong=1.5),
        'elephant_grass_c': lambda: _spec(clump, eg(), surface='grass', cut=512, seed=33, n=6, radius=13, height=84, width=50),
        'rice_clump_a': lambda: _spec(rice, rc(), surface='grass', cut=512, seed=34),
        'rice_clump_b': lambda: _spec(rice, rc(), surface='grass', cut=512, seed=35, patch=True),
        'reeds': lambda: _spec(clump, rd(), surface='grass', cut=1024, seed=36, n=9, radius=20, height=72, width=38, nimg=2, lean=0.08),
        'bamboo_clump': lambda: _spec(bamboo_clump, [spray_img('bamboo', 8), spray_img('bamboo', 9)], size=1024, cut=1024, lod1=True,
                                      hulls=[B(-20, -20, 0, 20, 20, 150)]),
        'rubber_tree': lambda: _spec(rubber_tree, [spray_img('crown', 10), spray_img('crown', 11)], size=1024, cut=1024, lod1=True,
                                     hulls=[B(-9, -9, 0, 11, 9, 170), B(-3, -10, 170, 16, 4, 330)]),
        'log_fallen': lambda: _spec(log_fallen, size=1024, lod1=True, hulls=[B(-112, -13, 0, 118, 13, 24), B(-134, -30, 0, -108, 30, 44)]),
        'dead_tree': lambda: _spec(dead_tree, size=1024, lod1=True, hulls=[B(-13, -13, 0, 15, 12, 190), B(0, -16, 190, 22, 6, 380)]),
        'vine_curtain': lambda: _spec(vine_curtain, [vine_img(12), vine_img(13)], size=512, cut=1024),
        'root_tangle': lambda: _spec(root_tangle, size=1024, lod1=True, hulls=[B(-16, -16, 0, 18, 16, 50), B(-52, -52, 0, 52, 52, 9)]),
        'flag_pole_n': lambda: _spec(flag_pole, size=1024, flag='n', team='n', hulls=[B(-3, -3, 0, 3, 3, 200), B(-16, -16, 0, 16, 16, 10)]),
        'flag_pole_t': lambda: _spec(flag_pole, size=1024, flag='t', team='t', hulls=[B(-3, -3, 0, 3, 3, 200), B(-16, -16, 0, 16, 16, 10)]),
        'flag_pole_ct': lambda: _spec(flag_pole, size=1024, flag='ct', team='ct', hulls=[B(-3, -3, 0, 3, 3, 200), B(-16, -16, 0, 16, 16, 10)]),
        'supply_crate': lambda: _spec(supply_crate, size=1024, hulls=[B(-26, -32, 0, 28, 32, 24), B(-26, -22, 24, 22, 10, 45)]),
    }


# ---------------------------------------------------------------- flag_pole.vmdl with skins
def write_flag_skins(out):
    """models/mv/flag_pole/flag_pole.vmdl: flag_pole_n's meshes and hulls, archetype "" so it works as prop_dynamic, material groups
    t and ct remapping flag_pole_n's vmat to the red / blue ones (Skin 0 neutral, 1 T, 2 CT). Run after the three are built."""
    import re
    src = os.path.join(out, 'models', 'mv', 'flag_pole_n', 'flag_pole_n.vmdl')
    txt = open(src).read()
    base = 'materials/models/mv/flag_pole_n/flag_pole_n.vmat'
    assert base in txt, 'flag_pole_n.vmdl has no main vmat remap'
    groups = ''
    for team in ('t', 'ct'):
        to = 'materials/models/mv/flag_pole_%s/flag_pole_%s.vmat' % (team, team)
        assert os.path.exists(os.path.join(out, to)), to
        groups += ('\t\t\t\t\t{\n\t\t\t\t\t\t_class = "MaterialGroup"\n\t\t\t\t\t\tname = "%s"\n\t\t\t\t\t\tremaps =\n\t\t\t\t\t\t[\n'
                   '\t\t\t\t\t\t\t{\n\t\t\t\t\t\t\t\tfrom = "%s"\n\t\t\t\t\t\t\t\tto = "%s"\n\t\t\t\t\t\t\t},\n\t\t\t\t\t\t]\n\t\t\t\t\t},\n') % (team, base, to)
    key = '\t\t\t\t\t\tglobal_default_material = ""\n\t\t\t\t\t},\n'
    assert key in txt
    txt = txt.replace(key, key + groups, 1)
    txt = re.sub(r'model_archetype = "[^"]*"', 'model_archetype = ""', txt)
    txt = re.sub(r'primary_associated_entity = "[^"]*"', 'primary_associated_entity = "prop_dynamic"', txt)
    d = os.path.join(out, 'models', 'mv', 'flag_pole'); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'flag_pole.vmdl'), 'w', newline='\n').write(txt)
    pj = os.path.join(os.path.dirname(os.path.abspath(out)), 'props.json')
    info = json.load(open(pj)) if os.path.exists(pj) else {}
    if 'flag_pole_n' in info:
        info['flag_pole'] = dict(info['flag_pole_n'], model='models/mv/flag_pole/flag_pole.vmdl', skins=['neutral', 't', 'ct'], dynamic=True)
        json.dump(info, open(pj, 'w'), indent=1)
    print('flag_pole: models/mv/flag_pole/flag_pole.vmdl (skins neutral, t, ct)')


if __name__ == '__main__':
    write_flag_skins(os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.environ.get('MV_OUT', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'addon'))))
