"""Radar / minimap for mg_trenchwarfare, fitted to the ground play space (trenches, no man's land, mortar line, the wood clearing, the mine
galleries; the aerodromes are left off). Same conventions as the cs2port radar that works in game: 1024 px png + vtex (max 1024, no lod),
game resource/overviews/<map>.txt with pos_x/pos_y = world position of the image's top-left corner and scale = world units per pixel.
usage: make_radar.py <vmap> <addon content out> <addon game out>"""
import os, sys, math, re
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage
import dmx
import layout as LY
from noise import fbm

VMAP = sys.argv[1]; OUT = sys.argv[2]; GAME = sys.argv[3]
SCALE = 8.40                     # world units per pixel of the 1024 image (written to the overview as is)
SPAN = SCALE * 1024              # square side in world units
X0, Y0 = -4300.0, 4700.0         # world position of the image's top-left corner (pos_x, pos_y)
OUT_N = 1024                     # shipped size
N = 2048                         # terrain raster
SS = 2                           # supersampling for the vector work
M = N * SS
UPP = SPAN / M                   # world units per canvas pixel

def px(x, y): return ((x - X0) / UPP, (Y0 - y) / UPP)
def plen(u): return u / UPP

# ---------------------------------------------------------------- world raster (2048, then upscaled)
xs = X0 + (np.arange(N) + 0.5) * SPAN / N; ys = Y0 - (np.arange(N) + 0.5) * SPAN / N
X, Y = np.meshgrid(xs, ys)
Z = np.zeros((N, N)); PZ = np.zeros((N, N)); PD = np.full((N, N), 1e9); TD = np.zeros((N, N))
for r0 in range(0, N, 256):
    sl = slice(r0, r0 + 256)
    Z[sl] = LY.height(X[sl], Y[sl])
    p_, d_ = LY.parapet(X[sl], Y[sl]); PZ[sl] = p_; PD[sl] = d_
    TD[sl] = LY.trench_dist(X[sl], Y[sl])[0]
bank = (PD >= 2) & (PD <= 116)
Zs = np.where(bank, np.maximum(Z, PZ), Z)
gy, gx = np.gradient(Zs, SPAN / N)
L = np.array([-0.55, 0.45, 0.70]); L /= np.linalg.norm(L)
nrm = np.stack([-gx, gy, np.ones_like(Zs)], -1); nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
shade = np.clip(nrm @ L, 0, 1) / L[2]
ax, ay = np.abs(X), np.abs(Y)
n1 = fbm(X / 700.0, Y / 700.0, 0.4, 4, seed=21); n2 = fbm(X / 160.0, Y / 160.0, 1.7, 3, seed=22)

forest = np.array([0.215, 0.255, 0.165]); field = np.array([0.30, 0.315, 0.215]); churn = np.array([0.33, 0.285, 0.215])
mudd = np.array([0.30, 0.255, 0.195]); grass = np.array([0.33, 0.37, 0.235])
col = np.empty((N, N, 3)); col[:] = forest
battle = (ax < 3550) & (ay < 3500)
col[battle] = field
nml = np.clip((1560 - ax) / 160.0, 0, 1)[..., None] * battle[..., None]
col = col * (1 - nml) + churn * nml
airf = (ax > 4300) & (ax < 6950) & (ay < 1150)
col[airf] = grass
# mowed strips on the landing grounds
stripe = ((np.floor(Y / 120.0) % 2) == 0) & airf
col[stripe] *= 1.06
col = col * (0.9 + 0.12 * n1[..., None] + 0.06 * n2[..., None])
# soft blend battle-zone edges into the wood
edge = ndimage.gaussian_filter(battle.astype(float), 12)
col = col * edge[..., None] + (forest * (0.9 + 0.12 * n1[..., None])) * (1 - edge[..., None])
# churned mud around craters and the trench lines
crater = np.clip((-Zs - 4) / 20.0, 0, 1) * battle
col = col * (1 - 0.55 * crater[..., None]) + mudd * 0.55 * crater[..., None]
spoil = np.clip(1 - np.abs(TD - 60) / 90.0, 0, 1) * (TD > 0)
col = col * (1 - 0.45 * spoil[..., None]) + np.array([0.36, 0.31, 0.24]) * 0.45 * spoil[..., None]
img = col * (0.62 + 0.48 * shade[..., None])
# contours every 8 units, stronger every 40
cz = Zs / 8.0
c1 = np.abs(cz - np.round(cz)) < 0.06
c5 = np.abs(Zs / 40.0 - np.round(Zs / 40.0)) < 0.012 * 5
img[c1 & ~(TD < 0)] *= 0.93
img[c5 & ~(TD < 0)] *= 0.86
trench = TD < 0
base = np.clip(img, 0, 1)
canvas = Image.fromarray((base * 255).astype(np.uint8)).resize((M, M), Image.BICUBIC).convert('RGBA')

# ---------------------------------------------------------------- what the generated map contains
d = dmx.DMX.load(VMAP)
props, waters = [], []
for c in d.root.get('world').get('children'):
    if c.type == 'CMapEntity':
        ep = c.get('entity_properties')
        if ep.get('classname') in ('prop_static', 'prop_dynamic') and c.get('origin')[2] > -1000:     # not the script's parked effects
            props.append((ep.get('model') or '', c.get('origin'), c.get('angles'), c.get('scales')))
    elif c.type == 'CMapMesh':
        md = c.get('meshData'); names = [a[0] for a in md.attrs]
        mats = list(md.get('materials')) if 'materials' in names else []
        if any('water' in m for m in mats):
            o = np.array(c.get('origin') or (0, 0, 0), float)
            for st in md.get('vertexData').get('streams'):
                if st.get('semanticName') == 'position': waters.append(np.array(st.get('data'), float)[:, :2] + o[:2])

layer = Image.new('RGBA', (M, M), (0, 0, 0, 0)); dr = ImageDraw.Draw(layer)

def poly(P, fill=None, outline=None, width=1):
    dr.polygon([px(*p) for p in P], fill=fill, outline=outline, width=width)

# standing water: crater pools drawn here, trench pools (mostly inside a trench) only clipped to the trench floor below
from scipy.spatial import ConvexHull
def in_trench_frac(W):
    k = 0
    for (x, y) in W:
        for (x0, y0, x1, y1, kk) in LY.rects():
            if x0 - 2 <= abs(x) <= x1 + 2 and y0 - 2 <= y <= y1 + 2: k += 1; break
    return k / max(len(W), 1)
TRENCH_POOLS = [W for W in waters if in_trench_frac(W) > 0.3]
waters_open = [W for W in waters if in_trench_frac(W) <= 0.3]
for W in waters_open:
    if len(W) < 3: continue
    try: h = W[ConvexHull(W).vertices]
    except Exception: continue
    poly(h, fill=(70, 86, 88, 235), outline=(118, 132, 128, 255), width=2)

# trenches: floor, fire-step, revetted walls, duckboards
RECTS = LY.rects()
for s in (-1, 1):
    for (x0, y0, x1, y1, k) in RECTS:
        a, b = sorted((s * x0, s * x1))
        fillc = (58, 49, 40, 255) if k != 'step' else (82, 70, 56, 255)
        dr.rectangle([px(a, y1), px(b, y0)], fill=fillc)
wall = Image.new('L', (M, M), 0); dw = ImageDraw.Draw(wall)
for s in (-1, 1):
    for (x0, y0, x1, y1, k) in RECTS:
        a, b = sorted((s * x0, s * x1))
        dw.rectangle([px(a, y1), px(b, y0)], fill=255)
wall_np = np.asarray(wall) > 0
rim = wall_np & ~ndimage.binary_erosion(wall_np, iterations=3)
outer = ndimage.binary_dilation(wall_np, iterations=5) & ~wall_np
la = np.asarray(layer).copy()
la[outer] = (196, 178, 136, 255)                    # sandbagged lip
la[rim] = (128, 112, 86, 255)                       # revetment boards
layer = Image.fromarray(la); dr = ImageDraw.Draw(layer)
# re-draw pools inside trenches on top of the floor, clipped
pool = Image.new('RGBA', (M, M), (0, 0, 0, 0)); dp = ImageDraw.Draw(pool)
for W in TRENCH_POOLS:
    if len(W) < 3: continue
    try: h = W[ConvexHull(W).vertices]
    except Exception: continue
    dp.polygon([px(*p) for p in h], fill=(56, 64, 60, 255))
pnp = np.asarray(pool).copy(); pnp[~(wall_np & ~rim)] = 0
layer = Image.alpha_composite(layer, Image.fromarray(pnp)); dr = ImageDraw.Draw(layer)
for s in (-1, 1):
    for (a_, b_, kind) in LY.segments():
        if kind == 'niche': continue
        A = (s * a_[0], a_[1]); B = (s * b_[0], b_[1])
        Lseg = math.hypot(B[0] - A[0], B[1] - A[1])
        if Lseg < 20: continue
        ux, uy = (B[0] - A[0]) / Lseg, (B[1] - A[1]) / Lseg
        t = 10.0
        while t < Lseg - 10:
            c0 = (A[0] + ux * t, A[1] + uy * t)
            p1 = px(c0[0] - uy * 13, c0[1] + ux * 13); p2 = px(c0[0] + uy * 13, c0[1] - ux * 13)
            dr.line([p1, p2], fill=(112, 92, 66, 255), width=2)
            t += 22.0

# shelters (elephant iron under earth)
for s in (-1, 1):
    for y in LY.SHELTER_Y:
        cx = s * (LY.XS + LY.HW + 4 + 48)
        dr.rounded_rectangle([px(cx - 50, y + 52), px(cx + 50, y - 52)], radius=plen(30), fill=(104, 94, 76, 255), outline=(150, 136, 108, 255), width=3)
        for k in range(-3, 4):
            dr.line([px(cx - 46, y + k * 13), px(cx + 46, y + k * 13)], fill=(124, 112, 92, 255), width=1)

# mortar pits: sandbag ring, floor, the tube
for s in (-1, 1):
    for (cx, cy) in LY.mortar_pits(s):
        r = 196
        dr.ellipse([px(cx - r - 26, cy + r + 26), px(cx + r + 26, cy - r - 26)], fill=(186, 168, 128, 255))
        dr.ellipse([px(cx - r, cy + r), px(cx + r, cy - r)], fill=(74, 63, 50, 255))
        for k in range(36):
            a = 2 * math.pi * k / 36
            p = px(cx + math.cos(a) * (r + 13), cy + math.sin(a) * (r + 13))
            dr.ellipse([p[0] - plen(9), p[1] - plen(6), p[0] + plen(9), p[1] + plen(6)], outline=(140, 124, 94, 255), width=1)
        p = px(cx, cy); rr = plen(26)
        dr.ellipse([p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr], fill=(46, 44, 40, 255), outline=(170, 160, 140, 255), width=2)
        dr.line([p, px(cx - s * 70, cy)], fill=(46, 44, 40, 255), width=int(plen(16)))

# wire: barbed fences and concertina coils as dark hatched runs
for (m, o, a, sc) in props:
    if 'wire_fence' in m or 'wire_coil' in m or 'cheval' in m:
        yaw = math.radians(a[1]); Lw = 128.0 * (sc[0] if sc else 1)
        if 'cheval' in m: Lw = 120.0
        ux, uy = math.cos(yaw), math.sin(yaw)
        A = (o[0] - ux * Lw / 2, o[1] - uy * Lw / 2); B = (o[0] + ux * Lw / 2, o[1] + uy * Lw / 2)
        dr.line([px(*A), px(*B)], fill=(34, 30, 26, 230), width=2)
        n = max(2, int(Lw / 18))
        for k in range(n + 1):
            c0 = (A[0] + (B[0] - A[0]) * k / n, A[1] + (B[1] - A[1]) * k / n)
            w = 9 if 'coil' in m else 6
            dr.line([px(c0[0] - uy * w - ux * w, c0[1] + ux * w - uy * w), px(c0[0] + uy * w + ux * w, c0[1] - ux * w + uy * w)], fill=(34, 30, 26, 200), width=1)

# small battlefield objects: wrecks, crates, logs (simple darker footprints)
for (m, o, a, sc) in props:
    nm = m.split('/')[-1]
    size = None
    if 'wreck_tank' in nm or 'tank_a7v' in nm or 'tank_renault' in nm: size = (150, 80, (70, 66, 56, 255))
    elif 'wreck_fieldgun' in nm or 'gun_75mm' in nm or 'howitzer' in nm: size = (90, 50, (66, 62, 54, 255))
    elif 'log_fallen' in nm: size = (150, 22, (74, 60, 44, 255))
    elif 'crate' in nm or 'tl_barrel' in nm or 'barrel_0' in nm: size = (34, 22, (110, 92, 66, 255))
    elif 'sandbag_low' in nm and abs(o[1]) > 3400: size = (64, 18, (186, 168, 128, 255))
    if size is None: continue
    yaw = math.radians(a[1]); ux, uy = math.cos(yaw), math.sin(yaw); hl, hw, fc = size[0] / 2, size[1] / 2, size[2]
    pts = [(o[0] + ux * hl - uy * hw, o[1] + uy * hl + ux * hw), (o[0] - ux * hl - uy * hw, o[1] - uy * hl + ux * hw),
           (o[0] - ux * hl + uy * hw, o[1] - uy * hl - ux * hw), (o[0] + ux * hl + uy * hw, o[1] + uy * hl - ux * hw)]
    poly(pts, fill=fc, outline=(30, 28, 24, 200))

# aerodromes: Bessonneau hangars and the parked aircraft
def biplane(cx, cy, heading, colr):
    ux, uy = math.cos(heading), math.sin(heading)
    def P(f, r): return px(cx + ux * f - uy * r, cy + uy * f + ux * r)
    dr.polygon([P(110, -9), P(110, 9), P(-120, 5), P(-120, -5)], fill=colr)                     # fuselage
    dr.polygon([P(55, -150), P(55, 150), P(15, 150), P(15, -150)], fill=colr)                    # wings
    dr.polygon([P(-95, -55), P(-95, 55), P(-125, 50), P(-125, -50)], fill=colr)                  # tailplane
    dr.ellipse([P(120, -6)[0] - 4, P(120, -6)[1] - 4, P(120, -6)[0] + 4, P(120, -6)[1] + 4], fill=(40, 36, 30, 255))
for s in (-1, 1):
    hx = s * LY.HANGAR_X
    for hy in (0.0,):
        dr.rectangle([px(hx - 380, 330), px(hx + 380, -330)], fill=(176, 166, 136, 255), outline=(120, 110, 88, 255), width=3)
        for k in range(7):
            x_ = hx - 380 + k * 760 / 6
            dr.line([px(x_, 330), px(x_, -330)], fill=(140, 130, 104, 255), width=2)
        dr.line([px(hx - 380, 0), px(hx + 380, 0)], fill=(150, 140, 112, 255), width=3)
    pc = (196, 180, 140, 255) if s > 0 else (170, 52, 40, 255)
    for (m, o, a, sc) in props:
        if ('plane_spad7' in m and s > 0 and o[0] > 0) or ('plane_dr1' in m and s < 0 and o[0] < 0):
            biplane(o[0], o[1], math.radians(a[1]), pc)

# the wood: every tree's crown, with a soft shadow, so the canopy reads as woodland and the clearing as open ground
crowns = Image.new('RGBA', (M, M), (0, 0, 0, 0)); dc = ImageDraw.Draw(crowns)
shadow = Image.new('L', (M, M), 0); dsh = ImageDraw.Draw(shadow)
TREE_R = {'maple': 150, 'poplar': 95, 'beech': 110, 'dogwood': 70, 'viburnum': 60, 'shattered': 34}
rng = np.random.RandomState(4)
trees = []
for (m, o, a, sc) in props:
    if 'weed' in m or 'grass' in m or 'leaves' in m: continue
    r = next((v for k, v in TREE_R.items() if k in m), None)
    if r is None: continue
    s_ = (sc[0] if sc else 1.0)
    trees.append((o[0], o[1], r * s_, 'shattered' in m or 'dogwood' in m or 'viburnum' in m))
trees.sort(key=lambda t: -t[2])
for (x, y, r, small) in trees:
    p = px(x + r * 0.35, y - r * 0.35); rr = plen(r)
    dsh.ellipse([p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr], fill=120 if not small else 70)
for (x, y, r, small) in trees:
    p = px(x, y); rr = plen(r)
    tone = rng.uniform(0.85, 1.15)
    base_c = np.array([46, 66, 36]) * tone if not small else np.array([70, 74, 52]) * tone
    for k, f in enumerate((1.0, 0.72, 0.42)):
        cc = np.clip(base_c * (1 + 0.18 * k), 0, 255).astype(int)
        off = rr * 0.18 * k
        dc.ellipse([p[0] - rr * f - off, p[1] - rr * f - off, p[0] + rr * f - off, p[1] + rr * f - off], fill=(*cc, 255))
shadow = shadow.filter(ImageFilter.GaussianBlur(plen(30)))
sh_np = np.asarray(shadow, np.float32) / 255.0

# ---------------------------------------------------------------- compose: ground, shadows, objects, crowns
g = np.asarray(canvas, np.float32)
g[..., :3] *= (1 - 0.45 * sh_np[..., None])
out = Image.fromarray(g.clip(0, 255).astype(np.uint8))
out = Image.alpha_composite(out, layer)
cr = np.asarray(crowns, np.float32)
cr[..., 3] *= 0.93
out = Image.alpha_composite(out, Image.fromarray(cr.astype(np.uint8)))

# ---------------------------------------------------------------- play space: what players can walk is bright, the rest is dimmed
play = Image.new('L', (M, M), 0); dpl = ImageDraw.Draw(play)
for s in (-1, 1):
    for (x0, y0, x1, y1, k) in RECTS:
        a, b = sorted((s * x0, s * x1)); dpl.rectangle([px(a - 30, y1 + 30), px(b + 30, y0 - 30)], fill=255)
    for (cx, cy) in LY.mortar_pits(s):
        dpl.rectangle([px(cx - 240, cy + 240), px(cx + 240, cy - 240)], fill=255)
EXIT_X, EXIT_Y, W_ = 1716.0, 2916.0, 55.0
B_ = (1080.0, 3560.0)
ct = [(EXIT_X + W_, EXIT_Y), (EXIT_X + W_, EXIT_Y + 120), (B_[0] + 40, B_[1] + 45), (1185, 3700), (1210, 3950), (1130, 4205), (905, 4350), (455, 4415), (0, 4395)]
south = [(EXIT_X - W_, EXIT_Y), (EXIT_X - W_, EXIT_Y + 70), (B_[0] - 40, B_[1] - 45), (850, 3478), (450, 3452), (0, 3472)]
mir = lambda P_: [(-p[0], p[1]) for p in P_]
outline = ct + mir(ct)[::-1][1:] + mir(south) + south[::-1][1:]
dpl.polygon([px(*p) for p in outline], fill=255)
for (x0, y0, x1, y1, k) in LY.tunnels(): dpl.rectangle([px(x0 - 20, y1 + 20), px(x1 + 20, y0 - 20)], fill=255)
play = play.filter(ImageFilter.GaussianBlur(plen(40)))
pm = np.asarray(play, np.float32)[..., None] / 255.0
o = np.asarray(out, np.float32)[..., :3]
lum = o.mean(-1, keepdims=True)
dim = (o * 0.62 + lum * 0.38) * 0.70
o = o * (0.30 + 0.70 * pm) + dim * (0.70 - 0.70 * pm)
# skirmish fence line on top (dashed, follows the generated fence)
out = Image.fromarray(o.clip(0, 255).astype(np.uint8)).convert('RGBA'); dr = ImageDraw.Draw(out)
for a_, b_ in zip(outline[:-1] + [outline[-1]], outline[1:] + [outline[0]]):
    if a_[1] <= EXIT_Y + 1 and b_[1] <= EXIT_Y + 1: continue
    Lseg = math.hypot(b_[0] - a_[0], b_[1] - a_[1]); n = max(1, int(Lseg / 60))
    for k in range(0, n, 2):
        p0 = (a_[0] + (b_[0] - a_[0]) * k / n, a_[1] + (b_[1] - a_[1]) * k / n)
        p1 = (a_[0] + (b_[0] - a_[0]) * (k + 1) / n, a_[1] + (b_[1] - a_[1]) * (k + 1) / n)
        dr.line([px(*p0), px(*p1)], fill=(214, 196, 150, 255), width=3)
for s in (-1, 1):       # exit ladders
    p = px(s * EXIT_X, EXIT_Y - 6)
    dr.rectangle([p[0] - plen(16), p[1] - plen(8), p[0] + plen(16), p[1] + plen(8)], fill=(214, 196, 150, 255))
    for k in (-1, 0, 1):
        dr.line([(p[0] + plen(10) * k, p[1] - plen(8)), (p[0] + plen(10) * k, p[1] + plen(8))], fill=(70, 58, 44, 255), width=2)

# mine galleries: translucent dark band with a dashed timber edge, lamps as warm dots
tl = Image.new('RGBA', (M, M), (0, 0, 0, 0)); dtl = ImageDraw.Draw(tl)
for (x0, y0, x1, y1, k) in LY.tunnels():
    dtl.rectangle([px(x0, y1), px(x1, y0)], fill=(28, 20, 14, 150))
out = Image.alpha_composite(out, tl); dr = ImageDraw.Draw(out)
def dash(a_, b_, col, w, step=36):
    Lseg = math.hypot(b_[0] - a_[0], b_[1] - a_[1]); n = max(1, int(Lseg / step))
    for k in range(0, n, 2):
        t0, t1 = k / n, (k + 1) / n
        dr.line([px(a_[0] + (b_[0] - a_[0]) * t0, a_[1] + (b_[1] - a_[1]) * t0),
                 px(a_[0] + (b_[0] - a_[0]) * t1, a_[1] + (b_[1] - a_[1]) * t1)], fill=col, width=w)
TR = LY.tunnels()
def inside(x, y): return any(x0 - 1 < x < x1 + 1 and y0 - 1 < y < y1 + 1 for (x0, y0, x1, y1, _) in TR)
for (x0, y0, x1, y1, k) in TR:
    for a_, b_, nx, ny in (((x0, y0), (x1, y0), 0, -1), ((x1, y0), (x1, y1), 1, 0), ((x1, y1), (x0, y1), 0, 1), ((x0, y1), (x0, y0), -1, 0)):
        L = math.hypot(b_[0] - a_[0], b_[1] - a_[1]); n = max(1, int(L / 16)); seg = None
        for i in range(n):
            mx = a_[0] + (b_[0] - a_[0]) * (i + 0.5) / n; my = a_[1] + (b_[1] - a_[1]) * (i + 0.5) / n
            open_ = inside(mx + nx * 8, my + ny * 8) or (k == 'sap' and ny == 1)
            p = (a_[0] + (b_[0] - a_[0]) * i / n, a_[1] + (b_[1] - a_[1]) * i / n)
            if not open_ and seg is None: seg = p
            if open_ and seg is not None: dash(seg, p, (196, 158, 104, 235), 2); seg = None
        if seg is not None: dash(seg, b_, (196, 158, 104, 235), 2)
for (x0, y0, x1, y1, k) in TR:
    if k in ('gallery', 'cross'):
        L = max(x1 - x0, y1 - y0); n = int(L // 230) + 1
        for i in range(n):
            f = (i + 0.5) / n
            x = x0 + (x1 - x0) * f if x1 - x0 > y1 - y0 else (x0 + x1) / 2
            y = (y0 + y1) / 2 if x1 - x0 > y1 - y0 else y0 + (y1 - y0) * f
            q = px(x, y); r = plen(9); dr.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=(255, 196, 110, 210))

# ladders out of the trenches (every ladder prop), dressing stations (red cross), sap entrances
def glyph_ladder(x, y, yaw):
    ux, uy = math.cos(yaw), math.sin(yaw); vx, vy = -uy, ux
    def P(f, r): return px(x + ux * f + vx * r, y + uy * f + vy * r)
    for r in (-11, 11): dr.line([P(-26, r), P(26, r)], fill=(232, 214, 160, 255), width=2 * SS)
    for f in (-18, -6, 6, 18): dr.line([P(f, -11), P(f, 11)], fill=(232, 214, 160, 255), width=SS + 1)
for (m, o, a, sc) in props:
    if m.endswith('/ladder.vmdl'): glyph_ladder(o[0], o[1], math.radians(a[1]))
for s_ in (-1, 1):
    for y in LY.SHELTER_Y:
        c = px(s_ * (LY.XS + LY.HW + 4 + 48), y); r = plen(34)
        dr.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=(236, 230, 214, 255), outline=(120, 30, 26, 255), width=SS)
        w = plen(9); h = plen(24)
        dr.rectangle([c[0] - w, c[1] - h, c[0] + w, c[1] + h], fill=(178, 34, 30, 255)); dr.rectangle([c[0] - h, c[1] - w, c[0] + h, c[1] + w], fill=(178, 34, 30, 255))
    c = px(s_ * LY.TUN_SAP_XC, LY.TUN_PORTAL_Y - 30); r = plen(40)
    dr.pieslice([c[0] - r, c[1] - r, c[0] + r, c[1] + r], 180, 360, fill=(30, 22, 16, 255), outline=(232, 214, 160, 255), width=2 * SS)
out.convert('RGB').save(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'radar_clean.png'))     # unlabelled, for the mortar sight (render_top.py)
# ---------------------------------------------------------------- lettering, compass, frame
def label(text, x, y, size, col=(232, 220, 186), alpha=200, rot=0, spacing=0.18, font='/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'):
    f = ImageFont.truetype(font, int(size * SS))
    chars = list(text); widths = [f.getbbox(ch)[2] - f.getbbox(ch)[0] if ch != ' ' else size * SS * 0.35 for ch in chars]
    sp = size * SS * spacing
    W = int(sum(widths) + sp * (len(chars) - 1)) + 8; H = int(size * SS * 1.5)
    t = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dt = ImageDraw.Draw(t)
    xx = 4
    for ch, w in zip(chars, widths):
        dt.text((xx + 2, 2 + SS), ch, font=f, fill=(0, 0, 0, int(alpha * 0.8)))
        dt.text((xx, 0), ch, font=f, fill=(*col, alpha))
        xx += w + sp
    if rot: t = t.rotate(rot, expand=True, resample=Image.BICUBIC)
    p = px(x, y); out.alpha_composite(t, (int(p[0] - t.size[0] / 2), int(p[1] - t.size[1] / 2)))
label("NO MAN'S LAND", 0, 0, 30, alpha=150, rot=90, spacing=0.5)
label('GERMAN LINES', -2760, -3040, 24, col=(222, 196, 170), alpha=190)
label('BRITISH LINES', 2760, -3040, 24, col=(214, 214, 186), alpha=190)
label('THE WOOD', 0, 3950, 26, alpha=200, spacing=0.35)
label('MINE GALLERIES', 0, -3640, 14, alpha=180, font='/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf')
label('MINENWERFER', -LY.MORTAR_X, 1980, 17, alpha=170)
label('TRENCH MORTARS', LY.MORTAR_X, 1980, 17, alpha=170)
label('PICCADILLY', LY.XS + 120, -60, 13, alpha=170, rot=90, font='/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf')
label('UNTER DEN LINDEN', -LY.XS - 120, -60, 13, alpha=170, rot=90, font='/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf')

# grid: 16 x 16 squares lettered A-P across, 1-16 down (the same squares the script's !pos reports)
dr = ImageDraw.Draw(out)
fG = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf', int(15 * SS))
for k in range(1, 16):
    t = M * k / 16
    dr.line([(t, 0), (t, M)], fill=(232, 220, 186, 46), width=SS); dr.line([(0, t), (M, t)], fill=(232, 220, 186, 46), width=SS)
for k in range(16):
    c = M * (k + 0.5) / 16
    dr.text((c - 5 * SS, 4 * SS), chr(65 + k), font=fG, fill=(232, 220, 186, 170))
    dr.text((4 * SS, c - 9 * SS), str(k + 1), font=fG, fill=(232, 220, 186, 170))
# compass (north = +y = up) and a 1000-unit scale bar, bottom left inside the frame
cx_, cy_ = px(X0 + 380, Y0 - SPAN + 700); R = plen(200)
dr.ellipse([cx_ - R, cy_ - R, cx_ + R, cy_ + R], outline=(214, 196, 150, 200), width=3)
for k in range(4):
    a = math.pi / 2 * k
    tip = (cx_ + math.sin(a) * R * 0.95, cy_ - math.cos(a) * R * 0.95)
    l_ = (cx_ + math.sin(a - 0.5) * R * 0.2, cy_ - math.cos(a - 0.5) * R * 0.2); r_ = (cx_ + math.sin(a + 0.5) * R * 0.2, cy_ - math.cos(a + 0.5) * R * 0.2)
    dr.polygon([tip, l_, (cx_, cy_)], fill=(232, 220, 186, 230)); dr.polygon([tip, r_, (cx_, cy_)], fill=(150, 136, 104, 230))
fN = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf', int(20 * SS))
dr.text((cx_ - 7 * SS, cy_ - R - 28 * SS), 'N', font=fN, fill=(232, 220, 186, 230))
x0_, y0_ = px(X0 + 700, Y0 - SPAN + 260); x1_, _ = px(X0 + 1700, Y0 - SPAN + 260)
for k in range(4):
    dr.rectangle([x0_ + (x1_ - x0_) * k / 4, y0_ - 5 * SS, x0_ + (x1_ - x0_) * (k + 1) / 4, y0_ + 5 * SS], fill=(232, 220, 186, 220) if k % 2 == 0 else (60, 54, 44, 220),
                 outline=(232, 220, 186, 220))
fS = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf', int(13 * SS))
dr.text((x0_, y0_ + 8 * SS), '0', font=fS, fill=(232, 220, 186, 220)); dr.text((x1_ - 30 * SS, y0_ + 8 * SS), '25 m', font=fS, fill=(232, 220, 186, 220))

# vignette + paper grain
o = np.asarray(out, np.float32)[..., :3]
yy, xx = np.mgrid[0:M, 0:M] / M - 0.5
vig = np.clip(1.08 - 0.55 * (xx ** 2 + yy ** 2) * 2.2, 0.55, 1)[..., None]
grain = np.asarray(Image.fromarray((ndimage.gaussian_filter(np.random.RandomState(9).rand(1024, 1024), 1.2) * 255).astype(np.uint8)).resize((M, M), Image.BICUBIC), np.float32)[..., None] / 255.0 - 0.5
o = o * vig * (0.97 + 0.05 * grain)
final = Image.fromarray(o.clip(0, 255).astype(np.uint8)).resize((OUT_N, OUT_N), Image.LANCZOS)
dst = os.path.join(OUT, 'panorama/images/overheadmaps'); os.makedirs(dst, exist_ok=True)
final.save(os.path.join(dst, 'mg_trenchwarfare_radar_psd.png'), optimize=True)
open(os.path.join(dst, 'mg_trenchwarfare_radar_psd.vtex'), 'w', newline='\n').write('''<!-- dmx encoding keyvalues2_noids 1 format vtex 1 -->
"CDmeVtex"
{
    "m_inputTextureArray" "element_array"
    [
        "CDmeInputTexture"
        {
            "m_name" "string" "SheetTexture"
            "m_fileName" "string" "panorama/images/overheadmaps/mg_trenchwarfare_radar_psd.png"
            "m_colorSpace" "string" "srgb"
            "m_typeString" "string" "2D"
            "m_imageProcessorArray" "element_array"
            [
            ]
        }
    ]
    "m_outputTypeString" "string" "2D"
    "m_outputFormat" "string" "BC7"
    "m_outputClearColor" "vector4" "0 0 0 0"
    "m_nOutputMinDimension" "int" "0"
    "m_nOutputMaxDimension" "int" "1024"
    "m_textureOutputChannelArray" "element_array"
    [
        "CDmeTextureOutputChannel"
        {
            "m_inputTextureArray" "string_array"
            [
                "SheetTexture"
            ]
            "m_srcChannels" "string" "rgba"
            "m_dstChannels" "string" "rgba"
            "m_mipAlgorithm" "CDmeImageProcessor"
            {
                "m_algorithm" "string" ""
                "m_stringArg" "string" ""
                "m_vFloat4Arg" "vector4" "0 0 0 0"
            }
            "m_outputColorSpace" "string" "srgb"
        }
    ]
    "m_vClamp" "vector3" "0 0 0"
    "m_bNoLod" "bool" "1"
}
''')
def frac(x, y): return (x - X0) / SPAN, (Y0 - y) / SPAN
ctx, cty = frac(LY.XF + 100, 0); tx, ty = frac(-LY.XF - 100, 0)
os.makedirs(os.path.join(GAME, 'resource/overviews'), exist_ok=True)
open(os.path.join(GAME, 'resource/overviews/mg_trenchwarfare.txt'), 'w', newline='\n').write('''// Overview (radar) for mg_trenchwarfare (tools/make_radar.py)
"mg_trenchwarfare"
{
	"material"	"overviews/mg_trenchwarfare_radar"	// texture file
	"pos_x"		"%d"	// upper left world coordinate
	"pos_y"		"%d"
	"scale"		"%.2f"
	"rotate"	"0"
	"zoom"		"1.0"

	// loading screen icons and positions
	"CTSpawn_x"	"%.2f"
	"CTSpawn_y"	"%.2f"
	"TSpawn_x"	"%.2f"
	"TSpawn_y"	"%.2f"
}
''' % (X0, Y0, SCALE, ctx, cty, tx, ty))
import json
json.dump(dict(x0=X0, y0=Y0, span=SPAN), open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'radar_region.json'), 'w'))
print('radar: %d trees, %d water patches, %d props -> %s (pos %d %d, scale %.2f)' % (len(trees), len(waters), len(props), dst, X0, Y0, SCALE))
