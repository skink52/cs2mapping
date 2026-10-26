"""Procedural PBR materials evaluated per texel (object space). Colours are sRGB 0..1, height in units."""
import numpy as np
from noise import fbm, perlin, ridged, cells, hash01, smoothstep

def _c(*rgb): return np.array(rgb, np.float32)

def mix(a, b, t):
    t = np.asarray(t, np.float32)
    if t.ndim == 1: t = t[:, None]
    return a * (1 - t) + b * t

def part_param(ctx, key, default=0.0):
    vals = np.array([p.get(key, default) for p in ctx.parts], np.float32)
    return vals[ctx.part]

def seed_of(ctx):
    return part_param(ctx, 'seed', 0.0)

MUD_DRY = _c(0.36, 0.30, 0.23)
MUD_WET = _c(0.17, 0.13, 0.09)

def mud_layer(ctx, col, rough, hgt, top=8.0, amount=1.0, splash=0.5):
    """mud coat rising from the model's base (z <= top), splashes above"""
    P = ctx.P
    z = P[:, 2] - ctx.lo[2]
    n = fbm(P[:, 0] * 0.09, P[:, 1] * 0.09, P[:, 2] * 0.09, 4, seed=71)
    sp = fbm(P[:, 0] * 0.35, P[:, 1] * 0.35, P[:, 2] * 0.35, 3, seed=72)
    m = smoothstep(top + 3, top - 3, z + n * 6) * amount
    m = np.maximum(m, smoothstep(0.55, 0.7, sp * 0.5 + 0.5) * smoothstep(top * 3.5, top, z) * splash)
    m = np.maximum(m, ctx.cav * 0.5 * amount)
    m = np.clip(m, 0, 1)
    wet = smoothstep(top * 0.6, 0, z) * 0.8 + 0.2 * smoothstep(0.3, 0.7, n * 0.5 + 0.5)
    mc = mix(MUD_DRY, MUD_WET, wet)
    mc = mc * (0.85 + 0.3 * (fbm(P[:, 0] * 0.8, P[:, 1] * 0.8, P[:, 2] * 0.8, 3, seed=73)[:, None] * 0.5 + 0.5))
    col = mix(col, mc, m)
    rough = rough * (1 - m) + m * (0.85 - 0.5 * wet)
    hgt = hgt + m * (0.15 + 0.25 * fbm(P[:, 0] * 0.5, P[:, 1] * 0.5, P[:, 2] * 0.5, 4, seed=74))
    return col, rough, hgt, m


def ao_tint(col, ctx, k=0.45):
    return col * (1 - k + k * ctx.ao[:, None])


# ---------------------------------------------------------------- wood
def wood(ctx, base=None, weather=0.82, mud_top=6.0, mud=1.0, wet=0.45):
    L = ctx.L; P = ctx.P; sd = seed_of(ctx)
    tone = part_param(ctx, 'tone', 0.5)
    x, y, z = L[:, 0], L[:, 1], L[:, 2]
    oy = (hash01(sd.astype(int), 1) - 0.5) * 30 + 14; oz = (hash01(sd.astype(int), 2) - 0.5) * 30 - 12
    r = np.sqrt((y + oy) ** 2 + (z + oz) ** 2)
    warp = fbm(x * 0.02 + sd, y * 0.15, z * 0.15, 3, seed=3) * 2.5
    ring = (r * 0.55 + warp) % 1.0
    late = smoothstep(0.75, 0.95, ring) * (1 - smoothstep(0.95, 1.0, ring))
    streak = fbm(x * 0.03 + sd * 3.1, y * 2.2, z * 2.2, 4, seed=5)
    fine = fbm(x * 0.15, y * 9.0, z * 9.0, 2, seed=6)
    fresh = _c(0.56, 0.45, 0.32); grey = _c(0.41, 0.385, 0.35); dark = _c(0.25, 0.21, 0.16)
    w = np.clip(weather + (tone - 0.5) * 0.6 + streak * 0.25, 0, 1)
    col = mix(fresh, grey, w)
    col = mix(col, dark, np.clip(late * 0.55 + (fine * 0.5 + 0.5) * 0.15, 0, 1))
    col = col * (0.88 + 0.24 * (tone[:, None] * 0.5 + 0.5)) * (0.92 + 0.12 * streak[:, None])
    # end grain
    Rx = np.array([p['R'][:, 0] for p in ctx.parts])[ctx.part]
    endg = np.abs(np.einsum('ij,ij->i', ctx.N, Rx))
    e = smoothstep(0.6, 0.85, endg)
    rings_end = (r * 1.4 + warp) % 1.0
    col = mix(col, mix(_c(0.55, 0.45, 0.33), _c(0.28, 0.22, 0.16), smoothstep(0.6, 0.9, rings_end)), e)
    # cracks along the grain
    crack = smoothstep(0.93, 0.985, ridged(x * 0.012 + sd, y * 0.9, z * 0.9, 3, seed=9)) * (1 - e)
    col = mix(col, _c(0.12, 0.10, 0.08), crack * 0.9)
    hgt = (-0.06 * late - 0.25 * crack + 0.03 * fine) * (1 - e) + e * (-0.05 * smoothstep(0.6, 0.9, rings_end))
    # worn, rounded edges are lighter; cavities darker
    col = mix(col, col * 1.18 + 0.03, ctx.edge * 0.5)
    rough = 0.78 + 0.12 * (fine * 0.5 + 0.5)
    if wet:
        wm = smoothstep(0.2, 0.8, fbm(P[:, 0] * 0.05, P[:, 1] * 0.05, P[:, 2] * 0.05, 3, seed=11) * 0.5 + 0.5) * wet
        col = col * (1 - 0.35 * wm[:, None]); rough = rough - 0.35 * wm
    # moss / lichen in shaded cavities
    moss = smoothstep(0.55, 0.75, fbm(P[:, 0] * 0.12, P[:, 1] * 0.12, P[:, 2] * 0.12, 4, seed=13) * 0.5 + 0.5) * (1 - ctx.ao) * 1.4
    col = mix(col, _c(0.24, 0.27, 0.13), np.clip(moss, 0, 0.6))
    col, rough, hgt, _ = mud_layer(ctx, col, rough, hgt, top=mud_top, amount=mud)
    col = ao_tint(col, ctx)
    return dict(color=np.clip(col, 0, 1), rough=np.clip(rough, 0.05, 1), height=hgt)


def splinter(ctx):
    """freshly broken wood (shattered trunk tops, shell-split posts)"""
    P, S = ctx.P, ctx.S
    f = fbm(S[:, 0] * 0.9, S[:, 1] * 0.05, 0, 4, seed=21)
    fib = ridged(S[:, 0] * 2.5, S[:, 1] * 0.12, 0.5, 3, seed=22)
    col = mix(_c(0.74, 0.62, 0.45), _c(0.52, 0.40, 0.27), np.clip(f * 0.5 + 0.5, 0, 1))
    col = mix(col, _c(0.34, 0.26, 0.17), smoothstep(0.75, 0.95, fib) * 0.6)
    char = smoothstep(0.55, 0.8, fbm(P[:, 0] * 0.06, P[:, 1] * 0.06, P[:, 2] * 0.06, 3, seed=23) * 0.5 + 0.5)
    col = mix(col, _c(0.10, 0.08, 0.07), char * 0.7)
    hgt = 0.35 * fib + 0.15 * f
    col = ao_tint(col, ctx, 0.55)
    return dict(color=np.clip(col, 0, 1), rough=0.85 - 0.1 * char, height=hgt)


# ---------------------------------------------------------------- bark (blasted trees)
def bark(ctx, char_amount=0.5):
    P, S = ctx.P, ctx.S
    su, sv = S[:, 0], S[:, 1]
    sd = seed_of(ctx)
    furrow = ridged(su * 0.32 + sd, sv * 0.045, sd * 0.1, 4, seed=31)
    plates = fbm(su * 0.15, sv * 0.06, sd, 4, seed=32)
    h = 0.9 * furrow + 0.3 * plates
    base = mix(_c(0.24, 0.21, 0.18), _c(0.42, 0.39, 0.35), np.clip(furrow * 0.9 + plates * 0.2, 0, 1))
    lich = smoothstep(0.62, 0.72, fbm(P[:, 0] * 0.18, P[:, 1] * 0.18, P[:, 2] * 0.18, 4, seed=33) * 0.5 + 0.5)
    base = mix(base, _c(0.52, 0.55, 0.46), lich * 0.45 * np.clip(furrow, 0, 1))
    zr = P[:, 2] - ctx.lo[2]
    moss = smoothstep(60, 0, zr + fbm(P[:, 0] * 0.05, P[:, 1] * 0.05, P[:, 2] * 0.05, 3, seed=34) * 30) * smoothstep(-0.2, 0.6, ctx.N[:, 0] * 0.6 + ctx.N[:, 1] * 0.8)
    base = mix(base, _c(0.20, 0.25, 0.10), moss * 0.7)
    char = smoothstep(0.5, 0.75, fbm(P[:, 0] * 0.03, P[:, 1] * 0.03, P[:, 2] * 0.03 + sd, 4, seed=35) * 0.5 + 0.5) * char_amount
    base = mix(base, _c(0.07, 0.06, 0.055), char * 0.85)
    strip = smoothstep(0.62, 0.8, fbm(su * 0.05, sv * 0.02, sd + 3, 3, seed=36) * 0.5 + 0.5) * part_param(ctx, 'stripped', 0.0)
    base = mix(base, _c(0.62, 0.53, 0.40) * (0.8 + 0.2 * plates[:, None]), strip)
    h = h * (1 - strip) + strip * 0.2 * fbm(su * 1.5, sv * 0.08, 0, 3, seed=37)
    col = ao_tint(base, ctx, 0.55)
    col, rough, h, _ = mud_layer(ctx, col, np.full(ctx.n, 0.9, np.float32), h * 0.8, top=10, amount=0.9, splash=0.4)
    return dict(color=np.clip(col, 0, 1), rough=rough, height=h)


# ---------------------------------------------------------------- burlap sandbags
def burlap(ctx):
    P, S = ctx.P, ctx.S
    su, sv = S[:, 0], S[:, 1]
    sd = seed_of(ctx); tone = part_param(ctx, 'tone', 0.5)
    p = 0.42
    a = np.cos(su * 2 * np.pi / p); b = np.cos(sv * 2 * np.pi / p)
    checker = np.sign(np.sin(su * np.pi / p) * np.sin(sv * np.pi / p))
    weave = np.where(checker > 0, np.abs(a) * 0.6, np.abs(b) * 0.6) + 0.2 * (a * b)
    fib = fbm(su * 3.0, sv * 3.0, sd, 2, seed=41)
    crease = ridged(P[:, 0] * 0.11 + sd, P[:, 1] * 0.11, P[:, 2] * 0.11, 3, seed=42)
    h = 0.05 * weave + 0.015 * fib - 0.35 * smoothstep(0.75, 0.98, crease)
    fresh = _c(0.60, 0.49, 0.33); old = _c(0.43, 0.38, 0.30); grey = _c(0.40, 0.39, 0.35)
    t = np.clip(tone, 0, 1)
    col = mix(mix(fresh, old, t), grey, np.clip((t - 0.6) * 2.5, 0, 1))
    col = col * (0.82 + 0.25 * weave[:, None]) * (0.95 + 0.1 * fib[:, None])
    stain = fbm(P[:, 0] * 0.07, P[:, 1] * 0.07, P[:, 2] * 0.07 + sd, 4, seed=43)
    col = mix(col, _c(0.27, 0.22, 0.16), smoothstep(0.1, 0.6, stain) * 0.5)
    col = mix(col, col * 0.75, smoothstep(0.75, 0.98, crease)[:, None])
    rough = np.full(ctx.n, 0.93, np.float32)
    col, rough, h, _ = mud_layer(ctx, col, rough, h, top=part_param(ctx, 'mud_top', 7.0), amount=0.85, splash=0.6)
    col = ao_tint(col, ctx, 0.6)
    return dict(color=np.clip(col, 0, 1), rough=rough, height=h)


# ---------------------------------------------------------------- metals
def rust_steel(ctx, paint=None, chip=0.5, rivets=False, mud_top=10.0, burnt=0.0, edge_k=0.9):
    P, S = ctx.P, ctx.S
    sd = seed_of(ctx)
    n1 = fbm(P[:, 0] * 0.08, P[:, 1] * 0.08, P[:, 2] * 0.08, 5, seed=51)
    n2 = fbm(P[:, 0] * 0.6, P[:, 1] * 0.6, P[:, 2] * 0.6, 3, seed=52)
    pits = cells(P[:, 0] * 0.9, P[:, 1] * 0.9, P[:, 2] * 0.9, seed=5)[0]
    rust_a = _c(0.28, 0.16, 0.09); rust_b = _c(0.44, 0.26, 0.13); rust_c = _c(0.18, 0.11, 0.07)
    rust = mix(mix(rust_a, rust_b, np.clip(n2 * 0.5 + 0.5, 0, 1)), rust_c, smoothstep(0.2, 0.6, n1))
    h = -0.12 * smoothstep(0.35, 0.0, pits) + 0.05 * n2
    col = rust; metal = np.full(ctx.n, 0.15, np.float32); rough = 0.85 + 0.1 * n2
    if paint is not None:
        streak = fbm(P[:, 0] * 0.25, P[:, 1] * 0.25, P[:, 2] * 0.02, 4, seed=53)
        pm = smoothstep(chip - 0.15, chip + 0.05, n1 * 0.5 + 0.5 + 0.25 * n2) * (1 - ctx.edge * edge_k)
        pc = paint * (0.85 + 0.2 * (n2[:, None] * 0.5 + 0.5))
        pc = mix(pc, pc * 0.7 + rust_a * 0.3, smoothstep(0.1, 0.6, streak) * 0.6)   # rust streaks
        col = mix(rust, pc, pm)
        h = h * (1 - pm) + pm * (0.08 + 0.01 * n2)
        rough = rough * (1 - pm) + pm * (0.62 + 0.15 * n2)
        metal = metal * (1 - pm)
        bare = ctx.edge * edge_k * smoothstep(0.4, 0.8, n2 * 0.5 + 0.5) * pm
        col = mix(col, _c(0.36, 0.35, 0.33), bare * 0.7); metal = np.maximum(metal, bare * 0.8); rough = rough - bare * 0.3
    if rivets:
        cw = np.array([[c['w'], c['h']] for c in ctx.chart_info])[ctx.chart] if hasattr(ctx, 'chart_info') else None
        if cw is not None:
            su, sv = S[:, 0], S[:, 1]
            du = np.minimum(su, cw[:, 0] - su); dv = np.minimum(sv, cw[:, 1] - sv)
            sp = 3.6; ins = 1.6; rr = 0.62
            big = (cw[:, 0] > 10) & (cw[:, 1] > 10)
            # rivet rows along each chart edge
            ru = np.abs(((sv + sp / 2) % sp) - sp / 2); rv = np.abs(((su + sp / 2) % sp) - sp / 2)
            d1 = np.sqrt((du - ins) ** 2 + ru ** 2); d2 = np.sqrt((dv - ins) ** 2 + rv ** 2)
            d = np.minimum(np.where(du < dv, d1, 99), np.where(dv <= du, d2, 99))
            bump = np.clip(1 - (d / rr) ** 2, 0, 1) ** 0.5 * big
            h = h + 0.45 * bump
            col = col * (1 + 0.12 * bump[:, None])
            seam = smoothstep(0.35, 0.0, np.minimum(du, dv)) * big
            h = h - 0.18 * seam
            pu = part_param(ctx, 'panel_u', 0.0); pv = part_param(ctx, 'panel_v', 0.0)
            has = (pu > 0) & big
            if has.any():
                pu_ = np.where(pu > 0, pu, 1e9); pv_ = np.where(pv > 0, pv, 1e9)
                gu = np.abs(((su + pu_ / 2) % pu_) - pu_ / 2); gv = np.abs(((sv + pv_ / 2) % pv_) - pv_ / 2)
                lap = (gu < 0.25) | (gv < 0.25)
                d3 = np.minimum(np.sqrt((gu - ins) ** 2 + rv ** 2), np.sqrt((gv - ins) ** 2 + ru ** 2))
                b3 = np.clip(1 - (d3 / rr) ** 2, 0, 1) ** 0.5 * has * (du > ins + 1) * (dv > ins + 1)
                h = h + 0.45 * b3 - 0.15 * lap * has
                col = col * (1 + 0.12 * b3[:, None])
    if burnt:
        b = smoothstep(0.45, 0.75, fbm(P[:, 0] * 0.025, P[:, 1] * 0.025, P[:, 2] * 0.025, 4, seed=55) * 0.5 + 0.5) * burnt
        col = mix(col, mix(_c(0.06, 0.055, 0.05), rust_a, smoothstep(0.6, 0.9, n2 * 0.5 + 0.5)), b)
        metal = metal * (1 - b); rough = rough * (1 - b) + b * 0.9
    col, rough, h, m = mud_layer(ctx, col, rough, h, top=mud_top, amount=0.95, splash=0.7)
    metal = metal * (1 - m)
    col = ao_tint(col, ctx, 0.5)
    return dict(color=np.clip(col, 0, 1), rough=np.clip(rough, 0.1, 1), metal=np.clip(metal, 0, 1), height=h)


def wire(ctx):
    P = ctx.P
    n = fbm(P[:, 0] * 0.4, P[:, 1] * 0.4, P[:, 2] * 0.4, 3, seed=61)
    col = mix(_c(0.22, 0.14, 0.09), _c(0.42, 0.26, 0.14), np.clip(n * 0.5 + 0.5, 0, 1))
    col = mix(col, _c(0.30, 0.30, 0.29), smoothstep(0.5, 0.8, n) * 0.5)
    return dict(color=col, rough=0.75 + 0.1 * n, metal=0.35 + 0.3 * smoothstep(0.4, 0.8, n), height=0.02 * n)


def brass(ctx):
    P = ctx.P
    n = fbm(P[:, 0] * 0.2, P[:, 1] * 0.2, P[:, 2] * 0.2, 4, seed=63)
    tarn = smoothstep(-0.2, 0.5, n)
    col = mix(_c(0.80, 0.62, 0.32), _c(0.40, 0.30, 0.16), tarn * 0.8)
    col = mix(col, _c(0.20, 0.30, 0.22), smoothstep(0.55, 0.8, n) * 0.4)
    rough = 0.35 + 0.4 * tarn
    out = dict(color=col, rough=rough, metal=0.95 - 0.3 * tarn, height=0.01 * n)
    c, r, h, m = mud_layer(ctx, out['color'], out['rough'], out['height'], top=3, amount=0.8, splash=0.4)
    out.update(color=ao_tint(c, ctx, 0.4), rough=r, height=h, metal=out['metal'] * (1 - m))
    return out


def painted_steel(ctx, paint, chip=0.62, mud_top=8.0, rivets=False, burnt=0.0, edge_k=0.9):
    return rust_steel(ctx, paint=paint, chip=chip, rivets=rivets, mud_top=mud_top, burnt=burnt, edge_k=edge_k)


# ---------------------------------------------------------------- cloth
def canvas(ctx, base=_c(0.66, 0.60, 0.48), mud_top=12.0, stains=0.6):
    P, S = ctx.P, ctx.S
    su, sv = S[:, 0], S[:, 1]
    p = 0.3
    weave = 0.5 + 0.5 * np.cos(su * 2 * np.pi / p) * np.cos(sv * 2 * np.pi / p)
    n = fbm(P[:, 0] * 0.03, P[:, 1] * 0.03, P[:, 2] * 0.03, 5, seed=81)
    w = fbm(P[:, 0] * 0.2, P[:, 1] * 0.2, P[:, 2] * 0.2, 3, seed=82)
    col = base * (0.9 + 0.12 * weave[:, None]) * (0.92 + 0.12 * w[:, None])
    col = mix(col, base * 0.62, smoothstep(0.1, 0.7, n) * stains)
    drip = fbm(P[:, 0] * 0.5, P[:, 1] * 0.5, P[:, 2] * 0.03, 3, seed=83)
    col = mix(col, base * 0.7, smoothstep(0.3, 0.8, drip) * 0.35)
    h = 0.02 * weave + 0.05 * w
    rough = np.full(ctx.n, 0.9, np.float32)
    col, rough, h, _ = mud_layer(ctx, col, rough, h, top=mud_top, amount=0.8, splash=0.5)
    return dict(color=np.clip(ao_tint(col, ctx, 0.5), 0, 1), rough=rough, height=h)


# ---------------------------------------------------------------- painted decals / signs from an image
def decal_image(ctx, img, base_shader, mask_rgb=None, chart_ids=None, strength=1.0):
    """samples an RGBA image (0..1) over the chosen charts' local UV, over a base material"""
    out = base_shader(ctx)
    if chart_ids is None: return out
    sel = np.isin(ctx.chart, chart_ids)
    if not sel.any(): return out
    cw = np.array([[c['w'], c['h']] for c in ctx.chart_info])[ctx.chart[sel]]
    u = np.clip(ctx.S[sel, 0] / cw[:, 0], 0, 1); v = np.clip(ctx.S[sel, 1] / cw[:, 1], 0, 1)
    H, W = img.shape[:2]
    px = np.clip((u * (W - 1)).astype(int), 0, W - 1); py = np.clip(((1 - v) * (H - 1)).astype(int), 0, H - 1)
    rgba = img[py, px]
    a = rgba[:, 3] * strength
    # weather the paint
    n = fbm(ctx.P[sel, 0] * 0.4, ctx.P[sel, 1] * 0.4, ctx.P[sel, 2] * 0.4, 3, seed=91)
    a = a * smoothstep(-0.6, -0.1, n)
    c = out['color']
    c[sel] = c[sel] * (1 - a[:, None]) + rgba[:, :3] * a[:, None] * (0.6 + 0.4 * ctx.ao[sel, None])
    out['color'] = c
    return out


def earth(ctx, wet=0.6):
    """trench clay / mud bank with stones and roots"""
    P = ctx.P
    n = fbm(P[:, 0] * 0.05, P[:, 1] * 0.05, P[:, 2] * 0.05, 5, seed=101)
    d = fbm(P[:, 0] * 0.4, P[:, 1] * 0.4, P[:, 2] * 0.4, 3, seed=102)
    f1, f2, cid = cells(P[:, 0] * 0.35, P[:, 1] * 0.35, P[:, 2] * 0.35, seed=7)
    stone = (hash01(cid, 3) > 0.82) & (f1 < 0.32)
    col = mix(_c(0.40, 0.32, 0.23), _c(0.26, 0.20, 0.14), np.clip(n * 0.6 + 0.5, 0, 1))
    col = col * (0.85 + 0.25 * (d[:, None] * 0.5 + 0.5))
    strata = np.sin(P[:, 2] * 0.35 + n * 3) * 0.5 + 0.5
    col = mix(col, _c(0.47, 0.39, 0.28), smoothstep(0.75, 0.95, strata) * 0.35)
    col = np.where(stone[:, None], mix(_c(0.50, 0.48, 0.44), _c(0.32, 0.31, 0.29), hash01(cid, 4)[:, None]), col)
    root = smoothstep(0.92, 0.99, 1 - np.abs(fbm(P[:, 0] * 0.08, P[:, 1] * 0.3, P[:, 2] * 0.08, 3, seed=103)))
    col = mix(col, _c(0.20, 0.15, 0.10), root * 0.8)
    h = 0.4 * d + 0.5 * stone * (0.32 - f1) / 0.32 + 0.2 * root
    w = np.clip(wet * (0.6 + 0.4 * smoothstep(40, 0, P[:, 2] - ctx.lo[2])), 0, 1)
    col = col * (1 - 0.4 * w[:, None])
    rough = 0.9 - 0.45 * w * smoothstep(-0.2, 0.4, d)
    rough = np.where(stone, 0.7, rough)
    return dict(color=np.clip(ao_tint(col, ctx, 0.6), 0, 1), rough=rough, height=h)


def galvanised(ctx, mud_top=14.0):
    return rust_steel(ctx, paint=_c(0.55, 0.56, 0.55), chip=0.42, mud_top=mud_top)


def track(ctx):
    out = rust_steel(ctx, mud_top=40)
    su, sv = ctx.S[:, 0], ctx.S[:, 1]
    p = 8.6
    g = (su % p)
    groove = smoothstep(0.7, 0.0, np.minimum(g, p - g))
    w = part_param(ctx, 'tw', 26.0)
    pin = np.clip(1 - ((np.minimum(g, p - g)) ** 2 + (np.minimum(sv, np.abs(w - sv)) - 2.0) ** 2) / 1.2, 0, 1)
    out['height'] = out['height'] - 0.5 * groove + 0.4 * pin + 0.25 * smoothstep(1.5, 3.0, np.minimum(g, p - g)) * (1 - groove)
    out['color'] = out['color'] * (1 - 0.35 * groove[:, None])
    return out


def decal_proj(ctx, img, base_shader, origin, u_axis, v_axis, size, facing=None, strength=1.0, weather=True):
    """projects an RGBA image (0..1) onto texels inside the rectangle origin + [0,1]x[0,1] * size along u/v axes
    (model space); facing: only texels whose normal points along this vector"""
    out = base_shader(ctx) if callable(base_shader) else base_shader
    o = np.asarray(origin, np.float32); ua = np.asarray(u_axis, np.float32); va = np.asarray(v_axis, np.float32)
    d = ctx.P - o
    u = d @ ua / size[0]; v = d @ va / size[1]
    sel = (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)
    if facing is not None:
        sel &= (ctx.N @ np.asarray(facing, np.float32)) > 0.5
    if not sel.any(): return out
    H, W = img.shape[:2]
    px = np.clip((u[sel] * (W - 1)).astype(int), 0, W - 1); py = np.clip(((1 - v[sel]) * (H - 1)).astype(int), 0, H - 1)
    rgba = img[py, px]
    a = rgba[:, 3] * strength
    if weather:
        n = fbm(ctx.P[sel, 0] * 0.4, ctx.P[sel, 1] * 0.4, ctx.P[sel, 2] * 0.4, 3, seed=91)
        a = a * smoothstep(-0.7, -0.2, n)
    c = out['color']
    c[sel] = c[sel] * (1 - a[:, None]) + rgba[:, :3] * a[:, None] * (0.65 + 0.35 * ctx.ao[sel, None])
    out['color'] = c
    if 'rough' in out and np.ndim(out['rough']):
        r = out['rough']; r[sel] = r[sel] * (1 - a * 0.4); out['rough'] = r
    return out
