"""mg_monsoon sandbag walls (playtest 1, finding 14): whole-height wall segments that interlock end to end.

What the old walls did wrong (p3): each prop was 3-4 courses 19 u high, and a wall was 2-4 of them stacked and laid in a row, each
piece standing on the ground at its own centre. Bags were flat pillows (thin edges), courses were loose rows with gaps, the stacks
floated where the ground fell away, and the burlap was a flat tinted cloth.

Here one prop is the full height of the wall over 80 u of its length:
- bags are filled-bag shapes (a superellipsoid: flat contact faces, rounded edges), a choked and tied neck at one end, a folded flap
  at the other, fuller in the middle, a little random in size, lumpy;
- courses alternate headers (across the wall, tied ends turned in) and stretchers (two or three rows along it), English bond: every
  joint is covered by the bag above;
- each bag settles on the bags under it (a height field of the course below: its underside follows the grooves, its top sags with
  them), so nothing floats and nothing has gaps under it;
- the outer face is battered (it leans in: base 30 u thick, top 21), the inner face nearly plumb;
- two buried footing courses below z 0, so the segment can stand on uneven ground;
- bags are laid on a global running bond along the wall: a segment holds exactly the bags whose centres fall in its 80 u, so two
  segments placed end to end interlock (the half-bag teeth of one fill the other) with no straight joint and no gap;
- arcs (gun pits r 232, the quad .50 ring r 118) are bent from the same layout, the inner side toward the arc centre (+y);
- material: the converted GMod sandbag's bag-unwrap textures (2048 px, four bags per sheet: seams, the tie, dirt), tan and green,
  one bag of the sheet per bag (stock mode 'uv'); without the conversions the stock hessian cloth.

Origin: the middle of the segment's centre line at ground level (z 0). Local +x along the wall, +y inward (the friendly side), the
battered face toward -y. Bounds about x -50..50, y -15..15, z -10..height.
"""
import os
import numpy as np
import geo
import stock
from noise import fbm

EXT_TAN = 'materials/models/mv/ext/sandbag_cover/sandbag_tan.vmat'
EXT_GREEN = 'materials/models/mv/ext/sandbag_cover/sandbag_green.vmat'
stock.STOCK.setdefault('sandbag_tan', dict(vmat=EXT_TAN, mode='uv'))
stock.STOCK.setdefault('sandbag_green', dict(vmat=EXT_GREEN, mode='uv'))
SEG = 80.0                       # segment length: a multiple of both pitches
PITCH_H, PITCH_S = 10.0, 20.0    # header / stretcher spacing along the wall (bags 11 / 21 long: they press into each other)
FOOT = -10.0                     # the footing courses start here (buried)
HEIGHTS = {'h1': 27.0, 'h2': 38.0, 'h3': 57.0, 'h4': 76.0}
ARCS = (118.0, 232.0)


def _sp(t, e):
    return np.sign(t) * np.abs(t) ** e


def bag(L=21.0, Wd=11.2, H=6.0, seed=0, lod=0, quad=0):
    """one filled bag, long axis x (tied end +x), centred; T = its uv on one bag of the 2 x 2 bag-unwrap sheet (image convention)"""
    rng = np.random.RandomState(seed)
    nu, nv = (8, 10) if lod == 0 else (5, 6)
    E, O = np.meshgrid(np.linspace(-np.pi / 2, np.pi / 2, nu + 1), np.linspace(-np.pi, np.pi, nv + 1), indexing='ij')
    e1, e2 = 0.34, 0.55
    a1, a2, a3 = L / 2, Wd / 2, H / 2
    x = a1 * _sp(np.sin(E), e1); y = a2 * _sp(np.cos(E), e1) * _sp(np.cos(O), e2); z = a3 * _sp(np.cos(E), e1) * _sp(np.sin(O), e2)
    xn = x / a1
    # uv from the undeformed footprint: across the width -> u, along the length -> v with the tie at the top of the bag image
    U = 0.5 + 0.44 * y / a2; V = 0.07 + 0.86 * (0.5 - 0.5 * xn)
    qx, qy = quad % 2, quad // 2
    # tied end: choked into a neck that ends in a short gathered tail; folded end: a thinner flap; fuller in the middle
    t = np.clip((xn - 0.62) / 0.38, 0, 1)
    y *= 1 - 0.62 * t ** 1.4; z *= 1 - 0.66 * t ** 1.4; x += 2.2 * t ** 3
    f = np.clip((-xn - 0.78) / 0.22, 0, 1)
    z *= 1 - 0.22 * f
    z *= 1 - 0.10 * xn ** 4
    z = np.where(z < 0, z * 0.82, z)                 # the underside is flatter than the top
    P = np.stack([x, y, z], -1)
    n = fbm(P[..., 0] * 0.21 + seed * 0.37, P[..., 1] * 0.21, P[..., 2] * 0.21, 3, seed=seed % 89)
    rad = np.stack([x / a1, y / a2, z / a3], -1); rad /= np.linalg.norm(rad, axis=-1, keepdims=True) + 1e-9
    P = P + rad * (n * 0.45 * (1 - t ** 2))[..., None]
    m = geo.surface(P, 'burlap', geo.frame(seed=seed, tone=rng.rand()))
    m.T = np.stack([(qx + U.ravel()) / 2.0, (qy + V.ravel()) / 2.0], 1)
    return m, (a1, a2, a3)


def _top_profile(xl, yl, a1, a2, a3):
    """half thickness of the bag over its footprint (the superellipsoid's top) at bag-local (xl, yl); 0 outside"""
    e1, e2 = 0.34, 0.55
    r = 1 - np.abs(np.clip(xl / a1, -1, 1)) ** (2 / e1)
    q = np.clip(r, 0, 1) ** (e1 / e2) - np.abs(np.clip(yl / a2, -1, 1)) ** (2 / e2)
    return np.where((r > 0) & (q > 0), a3 * np.clip(q, 0, 1) ** (e2 / 2), 0.0)


def wall(height=38.0, length=SEG, radius=None, base=30.0, top=21.0, seed=1, lod=0):
    """the segment mesh and its points for the collision hull"""
    rng = np.random.RandomState(seed)
    res = 1.0
    gs = np.arange(-length / 2 - 26.0, length / 2 + 26.0 + res, res); gy = np.arange(-base / 2 - 16.0, base / 2 + 16.0 + res, res)
    Hf = np.full((len(gs), len(gy)), FOOT)
    core = (np.abs(gs)[:, None] < length / 2 - 12) & (np.abs(gy)[None, :] < top / 2 - 3)
    m = geo.Mesh(); k = 0; nbag = 0
    def support(H, S, Y):
        i = np.clip((S - gs[0]) / res, 0, len(gs) - 1.001); j = np.clip((Y - gy[0]) / res, 0, len(gy) - 1.001)
        i0 = i.astype(int); j0 = j.astype(int); fi = i - i0; fj = j - j0
        return (H[i0, j0] * (1 - fi) * (1 - fj) + H[i0 + 1, j0] * fi * (1 - fj) + H[i0, j0 + 1] * (1 - fi) * fj + H[i0 + 1, j0 + 1] * fi * fj)
    while True:
        zc = float(np.median(Hf[core]))
        if zc >= height - 2.5 or k > 30: break
        frac = float(np.clip((zc - FOOT) / (height - FOOT), 0, 1))
        yf = -base / 2 + (base - top) * 0.8 * frac               # the battered outer face
        yb = base / 2 - (base - top) * 0.2 * frac                # the inner face, nearly plumb
        Hs = Hf.copy()
        for _ in range(1):                                       # the bags below as one soft surface
            Hs[1:-1, 1:-1] = (Hs[1:-1, 1:-1] * 2 + Hs[:-2, 1:-1] + Hs[2:, 1:-1] + Hs[1:-1, :-2] + Hs[1:-1, 2:]) / 6.0
        Hn = Hf.copy()
        rows = []
        squash = 1.0 - 0.10 * (1 - frac)                         # lower bags carry the wall: a little flatter
        if k % 2 == 0:                                           # header course: across the wall, tied ends inward
            rows.append(('h', yf + 10.6, (k // 2) % 2 * PITCH_H / 2))
            if yb - yf - 21.0 > 7.0: rows.append(('s', yb - 5.6, ((k // 2) % 2) * PITCH_S / 2 + PITCH_S / 4))
        else:                                                    # stretcher course: two or three rows along the wall
            nr = max(2, int(round((yb - yf) / 11.0)))
            for r_, yr in enumerate(np.linspace(yf + 5.6, yb - 5.6, nr)):
                rows.append(('s', yr, ((k // 2) % 2) * PITCH_S / 2 + (r_ % 2) * PITCH_S / 4))
        for kind, yr, off in rows:
            pitch = PITCH_H if kind == 'h' else PITCH_S
            s0 = -length / 2 + off
            for s in np.arange(s0 - pitch * 2, length / 2 + 1e-6, pitch):
                if not (-length / 2 <= s < length / 2): continue
                sd = seed * 7919 + k * 131 + int(round((s + 1000) * 4)) + int(round(yr * 8))
                r2 = np.random.RandomState(sd % (2 ** 31))
                b, (a1, a2, a3) = bag(21.0 + r2.uniform(-0.8, 1.0), 11.2 + r2.uniform(-0.4, 0.5), 6.0 * squash + r2.uniform(-0.3, 0.3), seed=sd % 100000, lod=lod,
                                      quad=r2.randint(4))
                ang = (90.0 if kind == 'h' else 0.0) + r2.uniform(-3.0, 3.0)
                if kind == 'h': ang += 180.0 * (r2.rand() < 0.15)                  # most tied ends face in (+y)
                elif r2.rand() < 0.5: ang += 180.0
                ca, sa = np.cos(np.radians(ang)), np.sin(np.radians(ang))
                xl, yl, zl = b.V[:, 0], b.V[:, 1], b.V[:, 2]
                S = s + r2.uniform(-0.5, 0.5) + ca * xl - sa * yl; Y = yr + r2.uniform(-0.4, 0.4) + sa * xl + ca * yl
                # the bag rests on the highest support under its middle and sags into the grooves by at most 2.5 u (an end that
                # overhangs the course below bridges, it does not hang down)
                inner = (np.abs(xl) < a1 * 0.7) & (np.abs(yl) < a2 * 0.7)
                zr = float(np.percentile(support(Hs, S[inner], Y[inner]), 90)) if inner.any() else float(support(Hs, np.array([s]), np.array([yr]))[0])
                zs = np.clip(support(Hs, S, Y), zr - 2.5, zr)
                w_ = np.clip((zl + a3) / (2 * a3), 0, 1)                     # 0 underside .. 1 top
                base_ = zs * (1 - w_) + (zr + 0.3 * (zs - zr)) * w_            # the underside takes the grooves, the top sags 30 % of it
                b.V = np.stack([S, Y, base_ + np.abs(zl) + zl], 1)
                b.recompute_normals(angle=75)
                m.add(b); nbag += 1
                # its top into the next course's height field
                i0 = max(0, int((s - 14 - gs[0]) / res)); i1 = min(len(gs), int((s + 14 - gs[0]) / res) + 1)
                j0 = max(0, int((yr - 14 - gy[0]) / res)); j1 = min(len(gy), int((yr + 14 - gy[0]) / res) + 1)
                GS, GY = np.meshgrid(gs[i0:i1], gy[j0:j1], indexing='ij')
                dx, dy = GS - s, GY - yr
                xl_, yl_ = ca * dx + sa * dy, -sa * dx + ca * dy
                th = _top_profile(xl_, yl_, a1, a2, a3 * 0.91)
                top_ = zr + 0.3 * (np.clip(support(Hs, GS, GY), zr - 2.5, zr) - zr) + 2.0 * th
                Hn[i0:i1, j0:j1] = np.where(th > 0, np.maximum(Hn[i0:i1, j0:j1], top_), Hn[i0:i1, j0:j1])
        Hf = Hn; k += 1
    # faces wholly 3 u under the segment's base are never seen (the placement puts the base 1 u under the lowest ground it covers)
    keep = m.V[m.F][:, :, 2].max(1) > -3.0
    m.F = m.F[keep]; m.FC = m.FC[keep]; m.FP = m.FP[keep]
    if radius:
        r = float(radius)
        S, Y = m.V[:, 0].copy(), m.V[:, 1].copy(); ph = S / r
        m.V[:, 0] = (r - Y) * np.sin(ph); m.V[:, 1] = r - (r - Y) * np.cos(ph)
        c, s_ = np.cos(ph), np.sin(ph)
        Nx, Ny = m.N[:, 0].copy(), m.N[:, 1].copy()
        m.N[:, 0] = c * Nx - s_ * Ny; m.N[:, 1] = s_ * Nx + c * Ny
    return m, nbag, k


def spec(height='h2', radius=None, seed=1, length=SEG):
    out = os.environ.get('MV_OUT', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'addon'))
    ht = HEIGHTS[height] if isinstance(height, str) else float(height)
    m0, nb, nc = wall(ht, length, radius, seed=seed, lod=0)
    m1, _, _ = wall(ht, length, radius, seed=seed, lod=1)
    ext = os.path.isfile(os.path.join(out, EXT_TAN)) and os.path.isfile(os.path.join(out, EXT_GREEN))
    smap = {'burlap': ['sandbag_tan', 'sandbag_tan', 'sandbag_green'] if ext else stock.HES}
    # collision: the convex hull of the bags (a straight segment is a battered prism; an arc fills its few units of sagitta)
    V = m0.V
    pts = V[np.unique(np.concatenate([np.argsort(V[:, k])[:40] for k in range(3)] + [np.argsort(-V[:, k])[:40] for k in range(3)] +
                                     [np.argsort(V[:, 0] * a + V[:, 1] * b + V[:, 2] * c)[:30] for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)] +
                                     [np.argsort(-(V[:, 0] * a + V[:, 1] * b + V[:, 2] * c))[:30] for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]))]
    print('sandbag wall %s r %s: %d bags, %d courses, %d tris' % (height, radius, nb, nc, len(m0.F)))
    return dict(lods=[m0, m1], lod_thresholds=[0.0, 25.0], size=1024, ground=0.0, surface='sand', stock=smap, shaders={'burlap': None},
                hulls=[pts])


def specs():
    """the wall classes mv_places.bag_line / bag_arc use"""
    sp = {}
    for h in HEIGHTS:
        sp['sandbag_w_' + h] = (lambda h=h: spec(h, None, seed=11 + list(HEIGHTS).index(h)))
    for r in ARCS:
        for h in ('h1', 'h2'):
            sp['sandbag_a%d_%s' % (int(r), h)] = (lambda r=r, h=h: spec(h, r, seed=31 + int(r) + list(HEIGHTS).index(h)))
    return sp
