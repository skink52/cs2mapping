"""mg_monsoon materials for the procedural props, on top of create/shaders.py: period aircraft paint, glass, rubber, aluminium,
interiors, concrete, thatch, bamboo, pierced steel planking, tarpaulin, rust-streaked olive drab."""
import numpy as np
import shaders as S
from shaders import _c, mix, part_param, seed_of, mud_layer, ao_tint
from noise import fbm, ridged, cells, hash01, smoothstep

OD = _c(0.26, 0.29, 0.19)              # US olive drab (FS 34087), faded
OD_LIGHT = _c(0.34, 0.37, 0.25)
SOVIET_GREEN = _c(0.30, 0.37, 0.26)
KHAKI = _c(0.45, 0.40, 0.27)
GREY_INT = _c(0.44, 0.47, 0.42)        # interior zinc chromate green-grey
SAND = _c(0.60, 0.55, 0.42)
BLACK = _c(0.05, 0.05, 0.05)


def aircraft_paint(ctx, paint=OD, chip=0.05, soot=0.0, mud_top=6.0, rivets=True, fade=0.25, edge_k=0.7):
    """painted aluminium skin: faint panel/rivet lines (chart edges), sun fade, exhaust soot along -x behind the engine part,
    oil streaks downward, light chipping on edges, little rust (aluminium)"""
    P = ctx.P; sd = seed_of(ctx)
    out = S.rust_steel(ctx, paint=paint, chip=chip, rivets=rivets, mud_top=mud_top, edge_k=edge_k)
    col = out['color']
    n = fbm(P[:, 0] * 0.012, P[:, 1] * 0.012, P[:, 2] * 0.012, 4, seed=201) * 0.5 + 0.5
    # sun fade on upward faces
    upf = np.clip(ctx.N[:, 2], 0, 1)
    col = mix(col, col * 1.18 + 0.04, fade * upf * (0.6 + 0.4 * n))
    # oil / grime streaks running down (along -z), heavier under the belly
    streak = fbm(P[:, 0] * 0.35, P[:, 1] * 0.35, P[:, 2] * 0.03, 4, seed=202)
    g = smoothstep(0.15, 0.6, streak) * (0.35 + 0.65 * np.clip(-ctx.N[:, 2], 0, 1))
    col = mix(col, col * 0.55, g * 0.5)
    # soot: part param 'soot' > 0 marks exhaust-stained parts; streams aft (-x) and down
    so = part_param(ctx, 'soot', 0.0) * soot if soot else part_param(ctx, 'soot', 0.0)
    if np.any(so > 0):
        sx = part_param(ctx, 'soot_x', 0.0); sz = part_param(ctx, 'soot_z', 0.0)
        plume = smoothstep(0.0, -220.0, P[:, 0] - sx) * smoothstep(-60.0, 10.0, P[:, 2] - sz) * (0.6 + 0.4 * fbm(P[:, 0] * 0.05, P[:, 1] * 0.2, P[:, 2] * 0.2, 3, seed=203))
        col = mix(col, BLACK * 0.6 + col * 0.2, np.clip(plume * so, 0, 0.85))
        out['rough'] = out['rough'] + 0.2 * plume * so
    # the aluminium showing through chips is bright, not rusty
    out['metal'] = np.clip(out['metal'] * 0.6, 0, 1)
    out['color'] = np.clip(col, 0, 1)
    return out


def od_paint(ctx): return aircraft_paint(ctx, OD)
def soviet_paint(ctx): return aircraft_paint(ctx, SOVIET_GREEN, chip=0.07)
def khaki_paint(ctx): return S.painted_steel(ctx, KHAKI, chip=0.22, mud_top=10.0)
def gun_steel(ctx):
    """blued / parkerised gun steel: dark, slightly worn on edges"""
    out = S.rust_steel(ctx, paint=_c(0.16, 0.17, 0.17), chip=0.06, mud_top=4.0, edge_k=0.5)
    out['metal'] = np.clip(out['metal'] + 0.5, 0, 1); out['rough'] = np.clip(out['rough'] - 0.15, 0.2, 1)
    wear = ctx.edge * 0.6
    out['color'] = np.clip(mix(out['color'], _c(0.5, 0.5, 0.5), wear), 0, 1)
    return out


def glass(ctx, tint=_c(0.12, 0.16, 0.19)):
    """plexiglass: dark, very smooth, dusty at the edges and in the lower part"""
    P = ctx.P
    n = fbm(P[:, 0] * 0.08, P[:, 1] * 0.08, P[:, 2] * 0.08, 3, seed=211) * 0.5 + 0.5
    dust = smoothstep(0.55, 0.85, n) * 0.5 + ctx.edge * 0.3
    col = mix(tint, _c(0.46, 0.44, 0.40), dust * 0.5)
    # rain streaks / wiper arc keep the centre clear
    return dict(color=np.clip(col, 0, 1), rough=0.12 + 0.5 * dust, metal=np.full(ctx.n, 0.35, np.float32), height=0.0 * n)


def rubber(ctx):
    P = ctx.P
    n = fbm(P[:, 0] * 0.5, P[:, 1] * 0.5, P[:, 2] * 0.5, 3, seed=221)
    col = _c(0.09, 0.09, 0.085) * (0.85 + 0.3 * (n[:, None] * 0.5 + 0.5))
    col, rough, h, _ = mud_layer(ctx, col, 0.82 + 0.1 * n, 0.03 * n, top=12.0, amount=1.0, splash=0.6)
    return dict(color=np.clip(ao_tint(col, ctx, 0.6), 0, 1), rough=rough, height=h)


def aluminium(ctx):
    P = ctx.P
    n = fbm(P[:, 0] * 0.2, P[:, 1] * 0.2, P[:, 2] * 0.2, 4, seed=231) * 0.5 + 0.5
    col = mix(_c(0.60, 0.61, 0.60), _c(0.42, 0.43, 0.44), n) * (0.9 + 0.2 * ctx.ao[:, None])
    return dict(color=np.clip(col, 0, 1), rough=0.35 + 0.3 * n, metal=np.full(ctx.n, 0.9, np.float32), height=0.01 * n)


def interior(ctx, base=GREY_INT):
    """cabin interior: zinc-chromate painted metal, scuffed floor, grime in corners"""
    out = S.rust_steel(ctx, paint=base, chip=0.12, mud_top=3.0, edge_k=0.8)
    g = smoothstep(0.4, 0.9, 1 - ctx.ao) * 0.6
    out['color'] = np.clip(mix(out['color'], out['color'] * 0.45, g), 0, 1)
    return out


def seat_canvas(ctx): return S.canvas(ctx, base=_c(0.33, 0.36, 0.26), mud_top=2.0, stains=0.7)
def webbing(ctx): return S.canvas(ctx, base=_c(0.50, 0.48, 0.36), mud_top=2.0, stains=0.5)


def tarp(ctx, base=_c(0.30, 0.33, 0.24)):
    out = S.canvas(ctx, base=base, mud_top=14.0, stains=0.8)
    P = ctx.P
    sun = np.clip(ctx.N[:, 2], 0, 1) * (fbm(P[:, 0] * 0.02, P[:, 1] * 0.02, 0.0, 3, seed=241) * 0.5 + 0.5)
    out['color'] = np.clip(mix(out['color'], out['color'] * 1.25 + 0.05, sun * 0.5), 0, 1)
    return out


def concrete(ctx, tone=_c(0.56, 0.55, 0.50), damage=0.4):
    P = ctx.P
    n = fbm(P[:, 0] * 0.06, P[:, 1] * 0.06, P[:, 2] * 0.06, 5, seed=251)
    f1, f2, cid = cells(P[:, 0] * 0.25, P[:, 1] * 0.25, P[:, 2] * 0.25, seed=9)
    agg = smoothstep(0.12, 0.0, f1) * (hash01(cid, 2) > 0.7)
    col = tone * (0.86 + 0.22 * (n[:, None] * 0.5 + 0.5))
    col = mix(col, _c(0.38, 0.37, 0.35), agg * 0.6)
    # water stains running down, moss in the lower damp band, spalling on edges
    drip = smoothstep(0.2, 0.7, fbm(P[:, 0] * 0.4, P[:, 1] * 0.4, P[:, 2] * 0.02, 3, seed=252))
    col = mix(col, col * 0.6, drip * 0.5)
    zr = P[:, 2] - ctx.lo[2]
    moss = smoothstep(50, 0, zr + 25 * fbm(P[:, 0] * 0.05, P[:, 1] * 0.05, P[:, 2] * 0.05, 3, seed=253)) * smoothstep(0.5, 0.8, fbm(P[:, 0] * 0.1, P[:, 1] * 0.1, P[:, 2] * 0.1, 3, seed=254) * 0.5 + 0.5)
    col = mix(col, _c(0.22, 0.28, 0.12), moss * 0.7)
    spall = smoothstep(0.55, 0.8, ridged(P[:, 0] * 0.08, P[:, 1] * 0.08, P[:, 2] * 0.08, 3, seed=255)) * ctx.edge * damage
    col = mix(col, _c(0.62, 0.60, 0.55), spall * 0.8)
    h = 0.08 * n - 0.3 * agg - 0.6 * spall
    rough = 0.9 - 0.2 * moss
    col, rough, h, _ = mud_layer(ctx, col, rough, h, top=10.0, amount=0.8, splash=0.5)
    return dict(color=np.clip(ao_tint(col, ctx, 0.6), 0, 1), rough=rough, height=h)


def thatch(ctx):
    """palm / grass thatch: bundles laid in overlapping rows along the part's x axis (roof slope), sun-bleached on top"""
    L = ctx.L; P = ctx.P; sd = seed_of(ctx)
    u, v = L[:, 0], L[:, 1]
    row = 9.0
    r = (u / row) % 1.0
    strands = ridged(u * 0.4 + sd, v * 3.5, 0.3, 3, seed=261)
    bundle = fbm(u * 0.08, v * 0.8, sd, 3, seed=262)
    edge = smoothstep(0.0, 0.25, r) * (1 - smoothstep(0.85, 1.0, r))
    h = 0.6 * edge + 0.35 * strands + 0.2 * bundle
    bleach = np.clip(ctx.N[:, 2], 0, 1)
    col = mix(_c(0.42, 0.33, 0.18), _c(0.66, 0.56, 0.34), np.clip(strands * 0.8 + 0.2 * bundle, 0, 1))
    col = mix(col, _c(0.72, 0.66, 0.46), bleach * 0.4 * smoothstep(0.3, 0.8, fbm(P[:, 0] * 0.05, P[:, 1] * 0.05, P[:, 2] * 0.05, 3, seed=263) * 0.5 + 0.5))
    col = mix(col, _c(0.20, 0.17, 0.10), (1 - edge) * 0.4)       # shadow under each row
    moss = smoothstep(0.55, 0.8, fbm(P[:, 0] * 0.12, P[:, 1] * 0.12, P[:, 2] * 0.12, 3, seed=264) * 0.5 + 0.5) * (1 - bleach) * 0.6
    col = mix(col, _c(0.25, 0.30, 0.12), moss)
    return dict(color=np.clip(ao_tint(col, ctx, 0.6), 0, 1), rough=np.full(ctx.n, 0.95, np.float32), height=h)


def bamboo(ctx):
    """bamboo culms along the part's x axis: nodes every ~26 units, pale green-yellow, grey where weathered"""
    L = ctx.L; P = ctx.P; sd = seed_of(ctx)
    u = L[:, 0]
    node = 26.0 + 4.0 * np.sin(sd)
    k = (u / node) % 1.0
    ring = smoothstep(0.93, 0.97, k) + smoothstep(0.07, 0.03, k)
    age = part_param(ctx, 'tone', 0.5)
    fresh = _c(0.62, 0.60, 0.30); old = _c(0.56, 0.52, 0.40); grey = _c(0.45, 0.45, 0.40)
    col = mix(mix(fresh, old, age), grey, smoothstep(0.6, 1.0, age))
    fib = fbm(u * 0.05 + sd, L[:, 1] * 2.0, L[:, 2] * 2.0, 3, seed=271)
    col = col * (0.9 + 0.18 * fib[:, None])
    col = mix(col, _c(0.30, 0.27, 0.14), ring * 0.7)
    spots = smoothstep(0.6, 0.75, fbm(P[:, 0] * 0.3, P[:, 1] * 0.3, P[:, 2] * 0.3, 3, seed=272) * 0.5 + 0.5)
    col = mix(col, _c(0.28, 0.24, 0.16), spots * 0.5)
    h = 0.35 * ring + 0.03 * fib
    col, rough, h, _ = mud_layer(ctx, col, np.full(ctx.n, 0.55, np.float32), h, top=8.0, amount=0.7, splash=0.3)
    return dict(color=np.clip(ao_tint(col, ctx, 0.5), 0, 1), rough=rough, height=h)


def psp(ctx):
    """pierced steel planking: rows of oblong holes (alpha in 'metal' for the cut-out atlas), OD/rust steel"""
    out = S.rust_steel(ctx, paint=OD_LIGHT * 0.9, chip=0.35, mud_top=2.0)
    S_ = ctx.S
    su, sv = S_[:, 0], S_[:, 1]
    # plank 15 in wide (~38 u) with 3 rows of holes 3.3 u wide, pitch 5.5 along the plank
    pu = 5.5; pv = 12.7
    du = np.abs(((su + pu / 2) % pu) - pu / 2); dv = np.abs(((sv + pv / 2) % pv) - pv / 2)
    hole = (du < 1.7) & (dv < 1.7)
    alpha = (~hole).astype(np.float32)
    seam = smoothstep(0.6, 0.0, np.abs(((sv + 19.0) % 38.0) - 19.0))
    out['height'] = out['height'] - 0.2 * seam
    out['color'] = np.clip(out['color'] * (1 - 0.3 * seam[:, None]), 0, 1)
    out['metal'] = alpha          # alpha channel for the cut-out atlas (see build_prop decal convention)
    return out


def grass_card(ctx, img):
    """foliage card: colour and alpha from a painted strip (RGBA 0..1), alpha returned in 'metal' for the cut-out atlas"""
    S_ = ctx.S
    cw = np.array([[c['w'], c['h']] for c in ctx.chart_info])[ctx.chart]
    u = np.clip(S_[:, 0] / cw[:, 0], 0, 1); v = np.clip(S_[:, 1] / cw[:, 1], 0, 1)
    H, W = img.shape[:2]
    px = np.clip((u * (W - 1)).astype(int), 0, W - 1); py = np.clip(((1 - v) * (H - 1)).astype(int), 0, H - 1)
    rgba = img[py, px]
    tone = part_param(ctx, 'tone', 0.5)
    col = rgba[:, :3] * (0.8 + 0.4 * tone)[:, None]
    return dict(color=np.clip(col, 0, 1), rough=np.full(ctx.n, 0.85, np.float32), metal=rgba[:, 3], height=np.zeros(ctx.n, np.float32))


def sandbag_wet(ctx): return S.burlap(ctx)
def wood(ctx): return S.wood(ctx, weather=0.6, mud_top=10.0, wet=0.6)
def wood_dark(ctx): return S.wood(ctx, weather=0.95, mud_top=12.0, wet=0.7)
def earth(ctx): return S.earth(ctx, wet=0.8)
def steel(ctx): return S.rust_steel(ctx, paint=_c(0.36, 0.37, 0.36), chip=0.3, mud_top=10.0)
def rust(ctx): return S.rust_steel(ctx, mud_top=14.0)
def burnt_steel(ctx): return S.rust_steel(ctx, paint=OD, chip=0.4, burnt=0.9, mud_top=12.0)
def brass(ctx): return S.brass(ctx)
def rope(ctx):
    out = S.canvas(ctx, base=_c(0.52, 0.46, 0.34), mud_top=4.0, stains=0.4)
    tw = np.sin(ctx.S[:, 0] * 2.6 + ctx.S[:, 1] * 1.3) * 0.5 + 0.5
    out['height'] = out['height'] + 0.12 * tw; out['color'] = np.clip(out['color'] * (0.85 + 0.3 * tw[:, None]), 0, 1)
    return out
