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
    # boxy props with ribs (CONEX, gun trails, trailers) saturate the baker's edge mask (mean ~0.9), which stripped all their paint
    # to rust; keep only the top of the distribution as real edges there (11 Nov)
    e0 = ctx.edge
    if len(e0) and float(np.mean(e0)) > 0.5:
        q = float(np.percentile(e0, 85))
        ctx.edge = np.clip((e0 - q) / max(1.0 - q, 1e-3), 0, 1).astype(e0.dtype) if q < 0.999 else np.zeros_like(e0)
    out = S.rust_steel(ctx, paint=paint, chip=chip, rivets=rivets, mud_top=mud_top, edge_k=edge_k)
    ctx.edge = e0
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
    live = part_param(ctx, 'live', 0.0)      # living culm (bamboo_clump): green, yellowing toward the nodes
    col = mix(col, mix(_c(0.26, 0.40, 0.14), _c(0.46, 0.50, 0.20), smoothstep(0.75, 1.0, np.abs(k - 0.5) * 2)), live)
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


# ---------------------------------------------------------------- 11 Nov: temple stone, jungle bark, wreck paint, cloth
def khmer_stone(ctx, tone=_c(0.50, 0.45, 0.36), moss=0.8, course=18.0, block=34.0):
    """mossy weathered sandstone masonry: dry-laid courses (z) with staggered vertical joints, per-block tone, iron staining, black
    algae streaks under ledges, pale lichen, moss on tops / in joints / near the ground. Part params: carve 0..1 (relief scrollwork
    over the chart, for lintels and pediments), mono 1 (a single block: no joints)."""
    P = ctx.P; N = ctx.N
    carve = part_param(ctx, 'carve', 0.0); mono = part_param(ctx, 'mono', 0.0)
    side = (np.abs(N[:, 2]) < 0.7).astype(np.float32)
    hc = np.where(np.abs(N[:, 0]) > np.abs(N[:, 1]), P[:, 1], P[:, 0])
    row = np.floor(P[:, 2] / course); zf = P[:, 2] / course - row
    off = hash01(row.astype(np.int64), 7) * block
    hb = (hc + off) / block; hf = hb - np.floor(hb)
    j_side = np.maximum(smoothstep(0.07, 0.0, np.minimum(zf, 1 - zf)), smoothstep(0.04, 0.0, np.minimum(hf, 1 - hf)))
    gx = P[:, 0] / block; gy = P[:, 1] / (block * 0.62)
    fx = gx - np.floor(gx); fy = gy - np.floor(gy)
    j_top = np.maximum(smoothstep(0.04, 0.0, np.minimum(fx, 1 - fx)), smoothstep(0.06, 0.0, np.minimum(fy, 1 - fy)))
    joint = (j_side * side + j_top * (1 - side)) * (1 - mono)
    bid = np.where(side > 0, row * 131 + np.floor(hb), np.floor(gx) * 57 + np.floor(gy) * 13).astype(np.int64)
    bt = hash01(bid, 3)
    n = fbm(P[:, 0] * 0.05, P[:, 1] * 0.05, P[:, 2] * 0.05, 5, seed=401)
    g = fbm(P[:, 0] * 0.5, P[:, 1] * 0.5, P[:, 2] * 0.5, 3, seed=402)
    col = tone * (0.80 + 0.26 * (n[:, None] * 0.5 + 0.5)) * (0.86 + 0.26 * bt[:, None])
    iron = smoothstep(0.1, 0.6, fbm(P[:, 0] * 0.03, P[:, 1] * 0.03, P[:, 2] * 0.03, 3, seed=403))
    col = mix(col, _c(0.50, 0.33, 0.24) * (0.85 + 0.3 * bt[:, None]), iron * 0.45)
    streak = smoothstep(0.05, 0.6, fbm(P[:, 0] * 0.32, P[:, 1] * 0.32, P[:, 2] * 0.014, 3, seed=404)) * side
    col = mix(col, col * 0.33, streak * 0.6)
    lich = smoothstep(0.52, 0.72, fbm(P[:, 0] * 0.13, P[:, 1] * 0.13, P[:, 2] * 0.13, 4, seed=405) * 0.5 + 0.5)
    col = mix(col, _c(0.63, 0.64, 0.54), lich * 0.4)
    up = np.clip(N[:, 2], 0, 1); zr = P[:, 2] - ctx.lo[2]
    mm = np.clip(up * 0.9 + ctx.cav * 0.7 + smoothstep(46, 0, zr) * 0.55 + joint * 0.6, 0, 1)
    mm = mm * smoothstep(0.30, 0.62, fbm(P[:, 0] * 0.07, P[:, 1] * 0.07, P[:, 2] * 0.07, 4, seed=406) * 0.5 + 0.5) * moss
    col = mix(col, mix(_c(0.14, 0.22, 0.07), _c(0.31, 0.38, 0.13), g * 0.5 + 0.5), mm)
    f1 = cells(P[:, 0] * 0.6, P[:, 1] * 0.6, P[:, 2] * 0.6, seed=11)[0]
    pit = smoothstep(0.25, 0.0, f1) * (bt > 0.35)
    h = 0.18 * n + 0.22 * g - 1.1 * joint - 0.35 * pit + 0.25 * mm
    if np.any(carve > 0):
        su, sv = ctx.S[:, 0], ctx.S[:, 1]
        cw = np.array([[c['w'], c['h']] for c in ctx.chart_info])[ctx.chart]
        big = (cw[:, 0] > 16) & (cw[:, 1] > 10)
        scroll = np.sin(su * 0.52 + 2.2 * np.sin(sv * 0.42)) * np.cos(sv * 0.55 + 1.3 * np.sin(su * 0.21))
        petal = np.cos(su * 1.05) * np.cos(sv * 1.05)
        rel = smoothstep(-0.15, 0.35, scroll) * 0.75 + smoothstep(0.2, 0.8, petal) * 0.25
        band = np.maximum(smoothstep(2.6, 2.0, np.minimum(sv, cw[:, 1] - sv)), smoothstep(2.6, 2.0, np.minimum(su, cw[:, 0] - su)))   # plain frame
        rel = np.where(band > 0.5, 0.8, rel) * big
        k = carve * big
        h = h * (1 - 0.5 * k) + 1.3 * k * rel
        col = col * (1 - 0.34 * k * (1 - rel))[:, None]
    col = mix(col, col * 1.18 + 0.02, ctx.edge * 0.35 * (1 - mm))
    rough = 0.93 - 0.18 * mm
    col, rough, h, _ = mud_layer(ctx, col, rough, h, top=5.0, amount=0.5, splash=0.3)
    return dict(color=np.clip(ao_tint(col, ctx, 0.62), 0, 1), rough=rough, height=h)


def laterite(ctx): return khmer_stone(ctx, tone=_c(0.46, 0.33, 0.25), moss=0.9, course=14.0, block=28.0)


def jungle_bark(ctx, pale=0.0):
    """living tropical bark: S.bark without the charring, more moss and lichen; pale > 0 = smooth pale trunk (rubber tree)"""
    out = S.bark(ctx, char_amount=0.0)
    P = ctx.P
    col = out['color']
    if pale:
        blot = smoothstep(0.35, 0.65, fbm(P[:, 0] * 0.09, P[:, 1] * 0.09, P[:, 2] * 0.045, 4, seed=411) * 0.5 + 0.5)
        pc = mix(_c(0.56, 0.54, 0.47), _c(0.40, 0.42, 0.36), blot)
        ring = smoothstep(0.75, 1.0, np.sin(P[:, 2] * 0.5 + 3 * fbm(P[:, 0] * 0.1, P[:, 1] * 0.1, P[:, 2] * 0.02, 2, seed=412)) * 0.5 + 0.5)
        pc = mix(pc, pc * 0.78, ring * 0.5)
        col = mix(col, ao_tint(pc, ctx, 0.5), pale); out['height'] = out['height'] * (1 - 0.75 * pale)
    lich = smoothstep(0.6, 0.72, fbm(P[:, 0] * 0.2, P[:, 1] * 0.2, P[:, 2] * 0.2, 3, seed=413) * 0.5 + 0.5)
    col = mix(col, _c(0.50, 0.58, 0.44), lich * 0.3)
    moss = smoothstep(0.5, 0.75, fbm(P[:, 0] * 0.06, P[:, 1] * 0.06, P[:, 2] * 0.06, 4, seed=414) * 0.5 + 0.5) * np.clip(0.35 + ctx.N[:, 2] * 0.9, 0, 1)
    col = mix(col, _c(0.20, 0.29, 0.10), moss * (0.75 - 0.35 * pale))
    out['color'] = np.clip(col, 0, 1)
    return out


def sea_camo(ctx, chip=0.16, burnt=0.0):
    """USAF South-East Asia scheme on aluminium: tan / green / dark green blotches, pale grey underside, chipped to bare metal,
    optionally fire-blackened (part params burnt, burnt_x, burnt_w: a burn centred on x; or the argument for all of it)"""
    P = ctx.P
    n = fbm(P[:, 0] * 0.011, P[:, 1] * 0.011 + 9.0, P[:, 2] * 0.016, 3, seed=421)
    paint = np.where((n > 0.12)[:, None], _c(0.47, 0.40, 0.27), np.where((n > -0.14)[:, None], _c(0.25, 0.31, 0.17), _c(0.13, 0.19, 0.12)))
    paint = np.where((ctx.N[:, 2] < -0.35)[:, None], _c(0.62, 0.64, 0.63), paint).astype(np.float32)
    out = S.rust_steel(ctx, paint=paint, chip=chip, rivets=True, mud_top=8.0, edge_k=0.8)
    bare = smoothstep(0.25, 0.6, out['metal'])        # where the paint is gone it is aluminium, not rust
    al = _c(0.58, 0.59, 0.58) * (0.8 + 0.3 * fbm(P[:, 0] * 0.3, P[:, 1] * 0.3, P[:, 2] * 0.3, 3, seed=422)[:, None])
    col = mix(out['color'], al, bare * 0.85)
    b = np.maximum(part_param(ctx, 'burnt', 0.0), burnt)
    if np.any(b > 0):
        bx = part_param(ctx, 'burnt_x', 0.0); bw = np.maximum(part_param(ctx, 'burnt_w', 200.0), 1.0)
        fire = smoothstep(1.0, 0.25, np.abs(P[:, 0] - bx) / bw + 0.35 * fbm(P[:, 0] * 0.02, P[:, 1] * 0.02, P[:, 2] * 0.02, 4, seed=423)) * b
        soot = mix(_c(0.05, 0.05, 0.05), _c(0.30, 0.17, 0.10), smoothstep(0.2, 0.7, fbm(P[:, 0] * 0.4, P[:, 1] * 0.4, P[:, 2] * 0.4, 3, seed=424)))
        col = mix(col, soot, fire * 0.92)
        out['rough'] = out['rough'] * (1 - fire) + 0.92 * fire; out['metal'] = out['metal'] * (1 - fire)
    out['color'] = np.clip(col, 0, 1)
    return out


def stripes(ctx, a=_c(0.70, 0.12, 0.10), b=_c(0.85, 0.84, 0.78), pitch=18.0, chip=0.3):
    """barrier pole paint: alternating bands along the part's x axis"""
    k = (np.floor(ctx.L[:, 0] / pitch).astype(np.int64) % 2 == 0)
    paint = np.where(k[:, None], a, b).astype(np.float32)
    return S.rust_steel(ctx, paint=paint, chip=chip, mud_top=0.0)


def flag_cloth(ctx, base=_c(0.85, 0.84, 0.80)):
    """thin faded cotton: weave, soft folds, a frayed dirty fly edge (chart u = hoist to fly)"""
    out = S.canvas(ctx, base=base, mud_top=0.0, stains=0.08)
    cw = np.array([[c['w'], c['h']] for c in ctx.chart_info])[ctx.chart]
    u = ctx.S[:, 0] / np.maximum(cw[:, 0], 1e-3)
    fray = smoothstep(0.86, 1.0, u + 0.05 * fbm(ctx.P[:, 0] * 0.6, ctx.P[:, 1] * 0.6, ctx.P[:, 2] * 0.6, 2, seed=431))
    fold = fbm(ctx.P[:, 0] * 0.15, ctx.P[:, 1] * 0.15, ctx.P[:, 2] * 0.05, 3, seed=432)
    col = out['color'] * (0.92 + 0.14 * fold[:, None])
    out['color'] = np.clip(mix(col, col * 0.6 + _c(0.10, 0.09, 0.07), fray * 0.6), 0, 1)
    return out


MUD_DRY_ = _c(0.36, 0.30, 0.23)


def silk(ctx, a=_c(0.80, 0.80, 0.74), b=_c(0.42, 0.45, 0.30)):
    """parachute canopy: gores alternate between two colours around the part's origin (apex), seams dark, mildew and mud"""
    P = ctx.P
    o = np.array([p['o'] for p in ctx.parts], np.float32)[ctx.part]
    gores = part_param(ctx, 'gores', 24.0)
    ang = (np.arctan2(P[:, 1] - o[:, 1], P[:, 0] - o[:, 0]) / (2 * np.pi) + 0.5) * gores
    k = np.floor(ang).astype(np.int64) % 2 == 0
    fr = ang - np.floor(ang)
    seam = smoothstep(0.05, 0.0, np.minimum(fr, 1 - fr))
    # no mud_layer here: the canopy lies within a few units of the ground and the mud band swallowed all of it (11 Nov)
    out = S.canvas(ctx, base=_c(0.96, 0.96, 0.96), mud_top=-50.0, stains=0.2)
    w = fbm(P[:, 0] * 0.02, P[:, 1] * 0.02, 0.0, 3, seed=442) * 0.5 + 0.5
    col = np.where(k[:, None], a, b) * (0.86 + 0.2 * w[:, None]) * (0.75 + 0.25 * ctx.ao[:, None])
    dirt = smoothstep(0.55, 0.8, fbm(P[:, 0] * 0.09, P[:, 1] * 0.09, 2.0, 4, seed=443) * 0.5 + 0.5)
    col = mix(col, MUD_DRY_ * 1.0, dirt * 0.45)
    mild = smoothstep(0.5, 0.75, fbm(P[:, 0] * 0.05, P[:, 1] * 0.05, P[:, 2] * 0.05, 4, seed=441) * 0.5 + 0.5)
    col = mix(col, col * 0.62 + _c(0.05, 0.07, 0.03), mild * 0.5)
    col = col * (1 - 0.35 * seam[:, None])
    out['color'] = np.clip(col, 0, 1); out['height'] = out['height'] + 0.25 * seam; out['rough'] = np.clip(out['rough'] - 0.25, 0.3, 1)
    return out


def ash(ctx):
    """burnt rubber / charred debris"""
    P = ctx.P
    n = fbm(P[:, 0] * 0.4, P[:, 1] * 0.4, P[:, 2] * 0.4, 4, seed=451)
    col = mix(_c(0.05, 0.05, 0.05), _c(0.34, 0.33, 0.31), smoothstep(0.1, 0.7, n))
    col, rough, h, _ = mud_layer(ctx, col, np.full(ctx.n, 0.95, np.float32), 0.3 * n, top=6.0, amount=0.8, splash=0.4)
    return dict(color=np.clip(ao_tint(col, ctx, 0.6), 0, 1), rough=rough, height=h)


def cardboard(ctx):
    out = S.canvas(ctx, base=_c(0.52, 0.42, 0.28), mud_top=5.0, stains=0.7)
    out['height'] = out['height'] + 0.03 * (np.sin(ctx.S[:, 1] * 3.0) * 0.5 + 0.5)
    return out
