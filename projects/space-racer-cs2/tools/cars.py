"""Original voxel cars for Space Racer: four classes, each as a normal and a boosting model, with T / CT colour skins;
plus the wreck explosion frames, the Pulse wave, the warp-out flash and the invisible null model. Also renders the
car pictures for the HUD car picker and a preview sheet.

usage: cars.py <addon_out_dir> [preview.png]
"""
import os, sys, json, math
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
import s2
import retro
from theme import NEON, DEPTH
from retro import *

OUT = sys.argv[1] if __name__ == '__main__' else None          # (importable: tools/workshop.py renders the cars too)
PREVIEW = sys.argv[2] if len(sys.argv) > 2 and __name__ == '__main__' else None
VOX = 3.4                      # units per voxel (a Hornet is about 115 units long)
HOVER = 12                     # units the hull floats above the road
MDIR = 'models/spr/cars'
PAL_DIR = 'materials/spr/cars'

def palette_neon(team):
    """Neon Racer: the same voxel cars, but a near-black hull with the team colour as glowing trim and edge lines"""
    t = np.array(team, np.float32)
    neon = tuple(np.clip(t * 1.0 + 15, 0, 255).astype(int))
    hull = tuple((t * 0.16 + 14).astype(int)); hull2 = tuple((t * 0.08 + 8).astype(int))
    if DEPTH:      # Depth Racer: deep-sea hulls (dark teal), the team colour glowing like bioluminescence
        hull = tuple((t * 0.08 + np.array((14, 46, 62))).astype(int)); hull2 = tuple((t * 0.04 + np.array((8, 26, 38))).astype(int))
    base = [hull, hull2, neon, (24, 26, 36), (150, 235, 255), (255, 220, 120), (255, 255, 230), tuple(neon),
            (255, 40, 80), (255, 255, 255), tuple(np.clip(t * 1.3 + 50, 0, 255).astype(int)), (6, 6, 10)]
    pal = np.zeros((64, 3), np.float32)
    for c, col in enumerate(base):
        for sh in range(4):
            k = SHADE[sh] if c not in GLOW + (2, 10) else (1.0 if sh == 0 else 0.92)
            pal[c * 4 + sh] = np.array(col, np.float32) * k
    return pal.clip(0, 255).astype(np.uint8)

def neon_edges(g):
    """hull voxels on the body's edges (open above and open to a side or end) become glowing trim lines"""
    o = np.pad(g.occ, 1)
    up_ = ~o[1:-1, 1:-1, 2:]
    lat = ~o[1:-1, 2:, 1:-1] | ~o[1:-1, :-2, 1:-1]
    # the outermost voxel across the car in each (x, z) column: the outline seen from above / behind
    ys = np.arange(g.W)[None, :, None]
    occ_y = np.where(g.occ, ys, -1); left = occ_y.max(1, keepdims=True)
    occ_y2 = np.where(g.occ, ys, 999); right = occ_y2.min(1, keepdims=True)
    outer = (ys == left) | (ys == right)
    top = g.occ & up_
    zt = np.where(top, np.arange(g.H)[None, None, :], -1).max(2, keepdims=True)
    edge = g.occ & up_ & lat & outer & np.isin(g.col, (0, 1, 3, 11))
    g.col[edge] = 2

# ---------------------------------------------------------------- palette: 12 colours x 4 shades (top, side, end, bottom)
# colour roles: 0 primary (team), 1 secondary (team, darker), 2 trim (light), 3 dark metal, 4 canopy glass,
# 5 engine glow, 6 flame core, 7 flame outer, 8 tail light (red), 9 light bar (white), 10 accent stripe, 11 black
SHADE = [1.0, 0.78, 0.64, 0.45]
GLOW = (5, 6, 7, 8, 9)
NCOL = 12
def palette(primary, secondary):
    if NEON: return palette_neon(primary)
    accent = tuple(min(255, int(c * 1.25 + 30)) for c in primary)
    base = [primary, secondary, (225, 228, 235), (52, 56, 66), (120, 220, 255), (255, 200, 90), (255, 250, 200), (255, 120, 20),
            (255, 40, 60), (255, 255, 255), accent, (18, 18, 22)]
    pal = np.zeros((64, 3), np.float32)
    for c, col in enumerate(base):
        for sh in range(4):
            k = SHADE[sh]
            if c in GLOW: k = 1.0 if sh == 0 else 0.94      # glowing parts barely shade
            pal[c * 4 + sh] = np.array(col, np.float32) * k
    return pal.clip(0, 255).astype(np.uint8)

SKINS = {
    'neutral': ((150, 155, 170), (90, 94, 108)),
    't': ((255, 150, 40), (170, 80, 20)),
    'ct': ((70, 150, 255), (30, 70, 170)),
    'gold': ((255, 215, 60), (180, 140, 20)),
}
# the shades a player can pick with !shade: reds for T, blues for CT (the first of each is the side's usual colour).
# Each becomes a skin on every car model, after the three above (so their skin numbers never move).
SHADES = {
    't': [('t', 'ORANGE'), ('t_red', 'RED'), ('t_crimson', 'CRIMSON'), ('t_coral', 'CORAL'), ('t_rose', 'ROSE'), ('t_maroon', 'MAROON')],
    'ct': [('ct', 'BLUE'), ('ct_navy', 'NAVY'), ('ct_cyan', 'CYAN'), ('ct_teal', 'TEAL'), ('ct_indigo', 'INDIGO'), ('ct_ice', 'ICE')],
}
SKINS.update({
    't_red': ((235, 45, 40), (140, 20, 18)),
    't_crimson': ((200, 20, 70), (110, 10, 40)),
    't_coral': ((255, 125, 110), (175, 62, 55)),
    't_rose': ((255, 90, 150), (160, 40, 90)),
    't_maroon': ((140, 30, 40), (75, 14, 20)),
    'ct_navy': ((40, 70, 190), (16, 28, 100)),
    'ct_cyan': ((40, 210, 255), (15, 110, 170)),
    'ct_teal': ((30, 190, 185), (10, 100, 105)),
    'ct_indigo': ((110, 85, 255), (55, 35, 155)),
    'ct_ice': ((175, 215, 255), (95, 135, 195)),
})
if NEON: SKINS['neutral'] = ((0, 210, 190), (0, 100, 96)) if DEPTH else ((0, 225, 255), (0, 110, 140))     # glow cyan / teal before a team is picked
SKIN_ORDER = ['t', 'ct', 'gold'] + [k for side in ('t', 'ct') for k, _ in SHADES[side][1:]]

def write_palettes():
    paths = {}
    for name, (p, s_) in SKINS.items():
        pal = palette(p, s_)
        img = np.zeros((64, 32, 3), np.uint8)
        for c in range(64):
            y, x = (c // 8) * 8, (c % 8) * 4
            img[y:y + 8, x:x + 4] = pal[c]
        paths[name] = s2.write_material(OUT, '%s/pal_%s' % (PAL_DIR, name), img, comment='Space Racer car palette ' + name)
    return paths

def pal_uv(c):
    # cell centre of entry c in the 32x64 palette image (8 columns of 4 px, 8 rows of 8 px)
    return ((c % 8) * 4 + 2) / 32.0, 1 - ((c // 8) * 8 + 4) / 64.0

# ---------------------------------------------------------------- voxel grid helpers
class Grid:
    def __init__(self, L, W, H):
        self.L, self.W, self.H = L, W, H
        self.occ = np.zeros((L, W, H), bool)
        self.col = np.zeros((L, W, H), np.int8)
        X, Y, Z = np.meshgrid(np.arange(L) + 0.5, np.arange(W) + 0.5 - W / 2, np.arange(H) + 0.5, indexing='ij')
        self.X, self.Y, self.Z = X, Y, Z          # x along the car (0 = rear), y across (0 = centre), z up (0 = bottom)
    def paint(self, mask, c):
        self.occ |= mask; self.col[mask] = c
    def cut(self, mask):
        self.occ &= ~mask
    def ellipsoid(self, cx, cy, cz, rx, ry, rz, c):
        m = ((self.X - cx) / rx) ** 2 + ((self.Y - cy) / ry) ** 2 + ((self.Z - cz) / rz) ** 2 <= 1
        self.paint(m, c); return m
    def box(self, x0, x1, y0, y1, z0, z1, c):
        m = (self.X >= x0) & (self.X < x1) & (self.Y >= y0) & (self.Y < y1) & (self.Z >= z0) & (self.Z < z1)
        self.paint(m, c); return m
    def taper(self, x0, x1, w0, w1, z0, h0, h1, c, yoff=0):
        """a hull slab from x0 to x1 whose half width goes w0 -> w1 and height h0 -> h1 (rounded cross-section)"""
        t = np.clip((self.X - x0) / max(x1 - x0, 1e-6), 0, 1)
        w = w0 + (w1 - w0) * t; h = h0 + (h1 - h0) * t
        m = (self.X >= x0) & (self.X < x1) & (((self.Y - yoff) / np.maximum(w, 0.01)) ** 2 + ((self.Z - z0) / np.maximum(h, 0.01)) ** 2 <= 1) & (self.Z >= z0)
        self.paint(m, c); return m
    def cylinder_x(self, x0, x1, cy, cz, r, c):
        m = (self.X >= x0) & (self.X < x1) & ((self.Y - cy) ** 2 + (self.Z - cz) ** 2 <= r * r)
        self.paint(m, c); return m

# ---------------------------------------------------------------- the four cars (all original designs)
# x = 0 is the tail. Everyone sees the cars mostly from behind (chase camera), so each tail has its own silhouette:
# Hornet twin booms + split fin, Meteor one huge engine under a wide wing, Comet three stacked engines + tall fin,
# Bastion four engines under a full-width light bar.
def car_hornet(g, boost):
    L = g.L
    g.taper(4, L - 2, 5.5, 1.2, 1.5, 3.2, 1.6, 0)                  # dart hull, narrowing to the nose
    g.taper(10, 22, 3.0, 2.2, 3.0, 2.6, 1.8, 4)                     # canopy
    g.box(8, 11, -2.6, 2.6, 2.5, 5.8, 1)                             # canopy frame
    g.box(6, 16, -9, -5.5, 1.8, 2.6, 1); g.box(6, 16, 5.5, 9, 1.8, 2.6, 1)     # swept wings
    g.box(9, 14, -11, -8.5, 1.8, 2.4, 10); g.box(9, 14, 8.5, 11, 1.8, 2.4, 10) # wing tips
    g.box(0, 9, -6.2, -4.6, 1.6, 3.4, 1); g.box(0, 9, 4.6, 6.2, 1.6, 3.4, 1)   # twin tail booms
    g.box(1, 5, -6.0, -4.8, 3.4, 7.6, 0); g.box(1, 5, 4.8, 6.0, 3.4, 7.6, 0)   # split fins
    g.box(1, 4, -6.0, -4.8, 7.0, 7.6, 10); g.box(1, 4, 4.8, 6.0, 7.0, 7.6, 10)
    g.box(0, 1, -6.2, -4.6, 2.0, 3.0, 8); g.box(0, 1, 4.6, 6.2, 2.0, 3.0, 8)   # boom tail lights
    for cy in (-2.4, 2.4):
        g.cylinder_x(1, 7, cy, 2.6, 1.7, 3)                           # engines
        g.cylinder_x(0, 1.5, cy, 2.6, 1.3, 5)                         # glow
        if boost: flame(g, 0, cy, 2.6, 1.2, flen(boost, 13))          # twin needle jets
    g.box(L - 6, L - 1, -1.2, 1.2, 1.2, 2.2, 2)                       # nose trim
    g.box(14, L - 4, -0.6, 0.6, 3.0, 3.4, 10)                        # spine stripe

def car_meteor(g, boost):
    L = g.L
    g.taper(3, L - 1, 7.5, 3.5, 1.4, 3.4, 2.4, 0)                   # wide wedge hull
    g.box(L - 8, L - 1, -7.5, 7.5, 1.0, 3.2, 3)                      # ram plate
    g.box(L - 3, L, -5, 5, 1.6, 2.8, 2)                              # plate edge trim
    g.taper(10, 20, 3.6, 2.4, 3.4, 2.4, 1.6, 4)                     # low canopy
    g.box(4, 12, -8.5, -6.5, 1.0, 4.0, 1); g.box(4, 12, 6.5, 8.5, 1.0, 4.0, 1)   # side armour
    g.cylinder_x(0, 6, 0, 3.0, 2.9, 3)                               # big engine
    g.cylinder_x(0, 1.5, 0, 3.0, 2.3, 5)
    if boost: flame(g, 0, 0, 3.0, 2.6, flen(boost, 13))                # one fat roaring flame
    g.box(2, 5, -7, -5, 3.4, 6.6, 1); g.box(2, 5, 5, 7, 3.4, 6.6, 1)   # wing struts
    g.box(0, 4, -8.5, 8.5, 6.6, 7.6, 0)                              # wide rear wing
    g.box(0, 1, -8.5, 8.5, 6.6, 7.6, 10)
    g.box(0, 1, -8.5, -6.5, 4.0, 5.2, 8); g.box(0, 1, 6.5, 8.5, 4.0, 5.2, 8)   # tail lights on the armour
    g.box(L - 8, L - 4, -6.5, -4.5, 3.2, 3.8, 10); g.box(L - 8, L - 4, 4.5, 6.5, 3.2, 3.8, 10)

def car_comet(g, boost):
    L = g.L
    g.taper(2, L - 1, 4.8, 2.0, 1.5, 3.6, 1.6, 0)                   # long teardrop
    g.taper(12, 24, 3.2, 2.2, 3.4, 2.8, 1.8, 4)                     # bubble canopy
    g.box(11, 13, -3.2, 3.2, 2.5, 6.2, 1)
    g.box(1, 9, -0.7, 0.7, 3.6, 10.5, 1)                             # tall tail fin
    g.box(1, 6, -0.7, 0.7, 9.5, 10.5, 10)
    g.box(1, 3, -0.8, 0.8, 7.0, 9.0, 8)                              # fin light
    g.box(14, 26, -7, -4.6, 1.6, 2.4, 1); g.box(14, 26, 4.6, 7, 1.6, 2.4, 1)   # canards
    g.box(14, 17, -7, -4.6, 1.6, 2.4, 10); g.box(14, 17, 4.6, 7, 1.6, 2.4, 10)
    for cy, cz in ((-2.6, 2.4), (2.6, 2.4), (0, 4.8)):
        g.cylinder_x(0, 5, cy, cz, 1.4, 3)
        g.cylinder_x(0, 1.5, cy, cz, 1.1, 5)
        if boost: flame(g, 0, cy, cz, 1.2, flen(boost, 17))           # three long plasma tails
    g.box(0, 1, -4.6, -3.6, 1.6, 2.6, 8); g.box(0, 1, 3.6, 4.6, 1.6, 2.6, 8)

def car_bastion(g, boost):
    L = g.L
    g.box(3, L - 4, -6.5, 6.5, 1.2, 5.0, 0)                          # armoured block hull
    g.taper(L - 6, L, 6.5, 3.0, 1.2, 3.6, 2.0, 0)                   # blunt nose
    g.box(3, L - 3, -7.5, -6.0, 0.8, 3.4, 1); g.box(3, L - 3, 6.0, 7.5, 0.8, 3.4, 1)   # side skirts
    g.box(14, 22, -3.0, 3.0, 5.0, 7.2, 4)                            # slit canopy
    g.box(14, 22, -3.4, 3.4, 4.6, 5.0, 1)
    g.box(4, 13, -6.0, 6.0, 5.0, 6.0, 1)                             # rear deck
    g.box(L - 12, L - 7, -6.0, 6.0, 5.0, 5.8, 2)                     # front trim bar
    g.box(3, 4, -6.5, 6.5, 4.4, 5.0, 9)                              # full-width rear light bar
    g.box(3, 4, -6.5, -5.0, 1.4, 2.4, 8); g.box(3, 4, 5.0, 6.5, 1.4, 2.4, 8)   # tail lights
    g.box(6, 12, -6.6, -6.4, 2.0, 4.0, 10); g.box(6, 12, 6.4, 6.6, 2.0, 4.0, 10)
    for cy, cz in ((-3.6, 2.8), (-1.2, 2.8), (1.2, 2.8), (3.6, 2.8)):
        g.cylinder_x(0, 4, cy, cz, 1.1, 3)
        g.cylinder_x(0, 1.5, cy, cz, 0.85, 5)
        if boost: flame(g, 0, cy, cz, 1.0, flen(boost, 9))            # four short stubby thrusters

def flen(boost, n):
    """flame length: the car's own boost, or 35% longer on a boost pad / turbo start"""
    return n if boost in (True, 'boost') else int(round(n * 1.35))

FLAME0 = 100          # flame voxels use colour indices 100 + layer * 8 + band (layer 0 outer .. 2 core, band 0 at
FLAME_BANDS = 8       # the nozzle .. 7 at the tip); they get their own animated material (flame_material)
FLAME_X = 24          # room behind the hull for the longest flame

def flame(g, x0, cy, cz, r, length):
    """a boost flame: cones pointing backwards (negative x) from x0, outer / mid / core, each cut into bands along its
    length so the animated material can send bright pulses down it"""
    for k, (rr, ln) in enumerate(((r * 1.15, length), (r * 0.85, length * 0.75), (r * 0.5, length * 0.5))):
        t = np.clip((x0 - g.X) / max(ln, 0.1), 0, 1)
        m = (g.X < x0) & (g.X >= x0 - ln) & ((g.Y - cy) ** 2 + (g.Z - cz) ** 2 <= (rr * (1 - t * 0.85)) ** 2)
        band = np.clip(((x0 - g.X) / max(length, 0.1) * FLAME_BANDS).astype(int), 0, FLAME_BANDS - 1)
        for b in range(FLAME_BANDS):
            g.paint(m & (band == b), FLAME0 + k * FLAME_BANDS + b)

# flame colours, dark to bright, per style (each car's own boost, and the gold boost-pad flame)
FLAME_STYLES = {
    'hornet': [PURPLE, MAGENTA, PINK, PALE, WHITE],
    'meteor': [WINE, RED, ORANGE, GOLD, CREAM],
    'comet': [NAVY, BLUE, SKYBLUE, ICE, WHITE],
    'bastion': [DEEPTEAL, TEAL, GREEN, LIME, MINT],
    'pad': [RUST, ORANGE, GOLD, CREAM, WHITE],
}
FLAME_FRAMES, FLAME_CELL = 4, 24     # animation frames; texture pixels per frame (3 layers x 8 bands)
WAVE = [1.0, 0.8, 0.55, 0.35, 0.25, 0.35, 0.55, 0.8]

def flame_rgb(style, layer, band, frame):
    """the colour of one flame band in one frame: a bright pulse travels from the nozzle to the tip, the core is
    brighter than the outside, the tip fades"""
    grad = FLAME_STYLES[style]
    w = WAVE[(band - 2 * frame) % len(WAVE)]
    lvl = 0.6 + layer * 0.9 + w * 2.2 - band * 0.22
    return grad[int(np.clip(round(lvl), 0, len(grad) - 1))]

def flame_uv(c):
    k = c - FLAME0
    return (k + 0.5) / FLAME_CELL, 0.5

def flame_material(style):
    """4 frames side by side; CS2's texture animation (as on Valve's animated TV static) steps through them"""
    img = np.zeros((4, FLAME_FRAMES * FLAME_CELL, 3), np.uint8)
    for f in range(FLAME_FRAMES):
        for layer in range(3):
            for band in range(FLAME_BANDS):
                img[:, f * FLAME_CELL + layer * FLAME_BANDS + band] = flame_rgb(style, layer, band, f)
    img = np.repeat(np.repeat(img, 4, 0), 4, 1)          # 384 x 16: each colour a 4-pixel block
    rate = 0.045 if style == 'pad' else 0.07
    return s2.write_material(OUT, '%s/flame_%s' % (PAL_DIR, style), img, comment='animated boost flame ' + style,
                             extra=('F_TEXTURE_ANIMATION 1', 'g_nNumAnimationCells "%d"' % FLAME_FRAMES,
                                    'g_vAnimationGrid "[%d.000000 1.000000]"' % FLAME_FRAMES, 'g_flAnimationTimePerFrame "%.3f"' % rate))

CARS = {'hornet': car_hornet, 'meteor': car_meteor, 'comet': car_comet, 'bastion': car_bastion}
DIMS = {'hornet': (34, 24, 9), 'meteor': (32, 18, 9), 'comet': (36, 16, 12), 'bastion': (31, 17, 9)}

# ---------------------------------------------------------------- greedy mesher (voxels -> quads)
def mesh_voxels(occ, col, origin, scale):
    """occ: bool [L,W,H]; col: colour index per voxel; origin: world position of voxel (0,0,0) corner; returns tris"""
    nx, ny, nz = occ.shape
    pad = np.zeros((nx + 2, ny + 2, nz + 2), bool); pad[1:-1, 1:-1, 1:-1] = occ
    dirs = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    shade = [2, 2, 1, 1, 0, 3]      # end, end, side, side, top, bottom
    tris = []
    for fi, d in enumerate(dirs):
        neigh = pad[1 + d[0]:nx + 1 + d[0], 1 + d[1]:ny + 1 + d[1], 1 + d[2]:nz + 1 + d[2]]
        exposed = occ & ~neigh
        colr = np.where(exposed, col.astype(np.int32) * 4 + np.where(col >= FLAME0, 0, shade[fi]), -1)
        axis = [i for i in range(3) if d[i] != 0][0]
        ua, va = [i for i in range(3) if i != axis]
        for s in range(occ.shape[axis]):
            sl = np.take(colr, s, axis=axis)
            if (sl < 0).all(): continue
            used = np.zeros(sl.shape, bool)
            U, V = sl.shape
            for i in range(U):
                for j in range(V):
                    c = sl[i, j]
                    if c < 0 or used[i, j]: continue
                    w = 1
                    while i + w < U and sl[i + w, j] == c and not used[i + w, j]: w += 1
                    h = 1
                    while j + h < V and (sl[i:i + w, j + h] == c).all() and not used[i:i + w, j + h].any(): h += 1
                    used[i:i + w, j:j + h] = True
                    plane = s + (1 if d[axis] > 0 else 0)
                    def P(a, b):
                        p = [0.0, 0.0, 0.0]
                        p[axis] = plane; p[ua] = a; p[va] = b
                        return (origin[0] + p[0] * scale, origin[1] + p[1] * scale, origin[2] + p[2] * scale)
                    corners = [P(i, j), P(i + w, j), P(i + w, j + h), P(i, j + h)]
                    n = (float(d[0]), float(d[1]), float(d[2]))
                    e1 = np.subtract(corners[1], corners[0]); e2 = np.subtract(corners[2], corners[0])
                    if np.dot(np.cross(e1, e2), n) < 0: corners = corners[::-1]
                    ci = int(c) // 4
                    mat = 'spr_flame' if ci >= FLAME0 else 'spr_pal'
                    u, v = flame_uv(ci) if ci >= FLAME0 else pal_uv(int(c))
                    cv = [(p[0], p[1], p[2], u, v) for p in corners]
                    tris.append((mat, (cv[0], cv[1], cv[2]), n))
                    tris.append((mat, (cv[0], cv[2], cv[3]), n))
    return tris

def shadow_tris(L, W):
    """a soft dark ellipse under the car (translucent material), at ground level"""
    hx, hy = L * VOX * 0.5, W * VOX * 0.5
    tris = []
    a = (-hx, -hy, 0.6, 0.0, 1.0); b = (hx, -hy, 0.6, 1.0, 1.0); c = (hx, hy, 0.6, 1.0, 0.0); d = (-hx, hy, 0.6, 0.0, 0.0)
    tris.append(('spr_shadow', (a, b, c), (0, 0, 1))); tris.append(('spr_shadow', (a, c, d), (0, 0, 1)))
    return tris

def write_shadow_material():
    G = 16          # a stepped pixel shadow: three rings of darkness
    yy, xx = np.mgrid[0:G, 0:G]
    r = np.hypot((yy + 0.5 - G / 2) / (G / 2), (xx + 0.5 - G / 2) / (G / 2))
    alpha = (np.ceil(np.clip(1 - r, 0, 1) * 3) / 3 * 170).astype(np.uint8)
    col = np.zeros((G * 4, G * 4, 3), np.uint8)
    return s2.write_material(OUT, PAL_DIR + '/shadow', col, up(alpha, 4), blend=1, comment='hover shadow')

def build_car(key, boost, pal_paths, shadow_mat, flame_mats):
    """boost: False (no flames), 'boost' (the car's own Mouse 1 flames) or 'pad' (the longer gold boost-pad flames)"""
    L, W, H = DIMS[key]
    g = Grid(L + (FLAME_X if boost else 0), W, H)
    # the hull sits in the front part; flames extend behind x=0 of the hull -> shift the hull when boosting
    if boost:
        g2 = Grid(L, W, H); CARS[key](g2, False)
        g.occ[FLAME_X:, :, :] = g2.occ; g.col[FLAME_X:, :, :] = g2.col
        CARS[key](ShiftedGrid(g, FLAME_X), boost)
    else:
        CARS[key](g, False)
    if NEON: neon_edges(g)
    origin = (-(L / 2) * VOX - (FLAME_X * VOX if boost else 0), -(W / 2) * VOX, HOVER)
    tris = mesh_voxels(g.occ, g.col, origin, VOX) + shadow_tris(L, W)
    mats = {'spr_pal': pal_paths['neutral'], 'spr_shadow': shadow_mat}
    if boost: mats['spr_flame'] = flame_mats['pad' if boost == 'pad' else key]
    skins = [(name, [(pal_paths['neutral'], pal_paths[name])]) for name in SKIN_ORDER]
    name = key + ('_' + boost if boost else '')
    return s2.write_model(OUT, MDIR, name, tris, mats, skins), g

class ShiftedGrid:
    """paints only the flames into a bigger grid whose hull starts at x = shift"""
    def __init__(self, g, shift): self.g = g; self.shift = shift; self.L = g.L - shift
    def __getattr__(self, k): return getattr(self.g, k)
    def paint(self, mask, c): self.g.paint(mask, c)
    # the hull functions are no-ops here (hull already copied); only flame() paints, via g.X etc.
    def taper(self, *a, **k): pass
    def box(self, *a, **k): pass
    def ellipsoid(self, *a, **k): pass
    def cylinder_x(self, *a, **k): pass

def _flame_shift_wrapper():
    # flame() uses g.X directly; for the shifted grid the hull's rear (x=0) is at X = shift
    global flame
    orig = flame
    def wrapped(g, x0, cy, cz, r, length):
        if isinstance(g, ShiftedGrid): orig(g.g, x0 + g.shift, cy, cz, r, length)
        else: orig(g, x0, cy, cz, r, length)
    flame = wrapped
_flame_shift_wrapper()

# ---------------------------------------------------------------- effects
def fireball(S, frame):
    """pixel-art explosion frame (drawn at 16 x 16, upscaled to S): a white flash, a jagged fire ball, a broken
    ring with flying debris, then smoke puffs. Alpha is cut-out (crisp pixel edges)."""
    G = 16
    rng = np.random.RandomState(31 + frame)
    yy, xx = np.mgrid[0:G, 0:G]
    cx = cy = (G - 1) / 2
    ang = np.arctan2(yy - cy, xx - cx)
    jag = 1 + 0.22 * np.sin(ang * 7 + frame) + 0.12 * np.sin(ang * 13 + 2 * frame)
    r = np.hypot(xx - cx, yy - cy) / jag
    img = np.zeros((G, G, 4), np.uint8)
    def put(mask, col): img[mask, :3] = col; img[mask, 3] = 255
    if frame == 0:
        put(r < 5.5, ORANGE); put(r < 4.3, GOLD); put(r < 3.0, CREAM); put(r < 1.8, WHITE)
    elif frame == 1:
        put(r < 7.5, RED); put(r < 6.2, ORANGE); put(r < 4.5, GOLD); put(r < 2.5, CREAM)
    elif frame == 2:
        ring = (r > 4.0) & (r < 7.6)
        holes = rng.rand(G, G) < 0.3
        put(ring & ~holes, ORANGE); put(ring & ~holes & (r < 5.4), RED); put((r < 4.0) & (rng.rand(G, G) < 0.25), GOLD)
        for _ in range(7):
            x, y = rng.randint(G), rng.randint(G)
            put((xx == x) & (yy == y), GOLD)
    else:
        for _ in range(6):
            px, py, pr = rng.uniform(3, 12), rng.uniform(3, 12), rng.uniform(1.8, 3.4)
            d = np.hypot(xx - px, yy - py)
            put(d < pr, MAUVE); put(d < pr * 0.6, LILAC)
    return up(img, S // G)

def star_tris(mat, w, h, zoff=0.0):
    """three crossed vertical planes (both faces drawn by CS2), width w, height h, centred, bottom at zoff"""
    tris = []
    for k in range(3):
        th = k * math.pi / 3
        rx, ry = math.cos(th), math.sin(th)
        p = lambda u, z, uu, vv: (rx * u, ry * u, z, uu, vv)
        a = p(-w / 2, zoff, 0, 1); b = p(w / 2, zoff, 1, 1); c = p(w / 2, zoff + h, 1, 0); d = p(-w / 2, zoff + h, 0, 0)
        n = (-ry, rx, 0.0)
        tris.append((mat, (a, b, c), n)); tris.append((mat, (a, c, d), n))
    return tris

def write_effects():
    out = {}
    for f in range(4):
        img = fireball(64, f)
        mat = s2.write_material(OUT, '%s/boom%d' % (PAL_DIR, f), img[..., :3], img[..., 3], blend=2, backfaces=True, comment='wreck frame %d' % f)
        size = 70 + f * 40
        out['boom%d' % f] = s2.write_model(OUT, MDIR, 'boom%d' % f, star_tris('spr_fx', size, size, -size * 0.3), {'spr_fx': mat})
    # warp-out flash: a tall bright pillar, two frames
    for f in range(2):
        G = 16
        yy, xx = np.mgrid[0:G, 0:G]
        dx = np.abs(xx - (G - 1) / 2)
        img = np.zeros((G, G, 3), np.uint8); img[:] = ICE
        img[dx < 4.5] = FROST; img[dx < 2] = WHITE
        img[(yy % 4 == f * 2) & (dx < 6)] = SKYBLUE
        alpha = ((dx < (7 if f == 0 else 3.5)) & ~((yy % 3 == 0) & (dx > 4))).astype(np.uint8) * 255
        mat = s2.write_material(OUT, '%s/warp%d' % (PAL_DIR, f), up(img, 4), up(alpha, 4), blend=2, backfaces=True, comment='warp-out %d' % f)
        out['warp%d' % f] = s2.write_model(OUT, MDIR, 'warp%d' % f, star_tris('spr_fx', 90 if f == 0 else 50, 220 if f == 0 else 320, 0), {'spr_fx': mat})
    # the Pulse: a low pixel laser fence across the track (40 tall, so it slides under the chase camera instead of
    # washing out the screen like the first, 160-tall see-through sheet did) and a strip of forward chevrons on the road.
    # Alpha-tested pixels (crisp, nothing see-through), both faces drawn.
    W_, Hh = 32, 8
    img = np.zeros((Hh, W_, 3), np.uint8); a = np.zeros((Hh, W_), np.uint8)
    img[:] = ICE
    img[0] = WHITE; a[0] = 255                       # top rail
    img[1] = FROST; a[1] = 255
    for x in range(W_):
        if x % 4 in (0, 1): a[2:7, x] = 255; img[2:7, x] = SKYBLUE if x % 8 < 2 else ICE   # the laser bars
    img[7] = TEAL; a[7] = 255                        # bottom rail
    fence = s2.write_material(OUT, PAL_DIR + '/pulse', up(img, 4), up(a, 4), blend=2, backfaces=True, comment='the Pulse: laser fence')
    G = 16
    yy, xx = np.mgrid[0:G, 0:G]
    chev = np.abs(yy - (G - 1) / 2) * 0.8 + 2
    m = ((xx + chev) % 8 < 3)                         # chevrons pointing along +u = forward
    img2 = np.zeros((G, G, 3), np.uint8); img2[:] = ICE; img2[(xx + chev) % 8 < 1.5] = WHITE
    strip = s2.write_material(OUT, PAL_DIR + '/pulse_floor', up(img2, 4), up(m.astype(np.uint8) * 255, 4), blend=2, backfaces=True, comment='the Pulse: road chevrons')
    w, h, d, zf = 760, 40, 48, 3
    reps = 6                                         # the fence pattern repeats across the road
    p = [(0, -w / 2, 0, 0, 1), (0, w / 2, 0, reps, 1), (0, w / 2, h, reps, 0), (0, -w / 2, h, 0, 0)]
    tris = [('spr_fx', (p[0], p[1], p[2]), (1, 0, 0)), ('spr_fx', (p[0], p[2], p[3]), (1, 0, 0))]
    q = [(-d / 2, -w / 2, zf, 0, 0), (d / 2, -w / 2, zf, 1, 0), (d / 2, w / 2, zf, 1, w / d), (-d / 2, w / 2, zf, 0, w / d)]
    tris += [('spr_fl', (q[0], q[1], q[2]), (0, 0, 1)), ('spr_fl', (q[0], q[2], q[3]), (0, 0, 1))]
    out['pulse'] = s2.write_model(OUT, MDIR, 'pulse', tris, {'spr_fx': fence, 'spr_fl': strip})
    # SHOCKWAVE: a ring of light flat on the road, three frames growing to the blast radius (320)
    for f in range(3):
        G = 32
        yy, xx = np.mgrid[0:G, 0:G]
        r = np.hypot(xx + 0.5 - G / 2, yy + 0.5 - G / 2) / (G / 2)
        ring = (r > 0.82 - f * 0.08) & (r < 0.98)
        img = np.zeros((G, G, 3), np.uint8); img[:] = (ORANGE, GOLD, CREAM)[f]
        img[(r > 0.9) & ring] = (GOLD, CREAM, WHITE)[f]
        cracks = ((np.abs(xx - yy) < 1) | (np.abs(xx + yy - G) < 1) | (np.abs(xx - G / 2) < 0.6) | (np.abs(yy - G / 2) < 0.6)) & (r > 0.3) & (r < 0.85) & (f == 0)
        img[cracks] = RED
        mat = s2.write_material(OUT, '%s/quake%d' % (PAL_DIR, f), up(img, 4), up(((ring | cracks) * 255).astype(np.uint8), 4), blend=2, backfaces=True, comment='shockwave ring %d' % f)
        R = (140, 230, 320)[f]
        q = [(-R, -R, 6, 0, 1), (R, -R, 6, 1, 1), (R, R, 6, 1, 0), (-R, R, 6, 0, 0)]
        out['quake%d' % f] = s2.write_model(OUT, MDIR, 'quake%d' % f, [('spr_fx', (q[0], q[1], q[2]), (0, 0, 1)), ('spr_fx', (q[0], q[2], q[3]), (0, 0, 1))], {'spr_fx': mat})
    # NOVA BURN fire on the road: low pixel flames on three crossed planes, two frames that the script alternates
    for f in range(2):
        G = 16
        rng = np.random.RandomState(70 + f)
        yy, xx = np.mgrid[0:G, 0:G]
        h = (G - 1 - yy) / G                                   # 0 at the bottom .. 1 at the top
        tongue = 0.55 + 0.35 * np.sin(xx * 1.3 + f * 2.1) + rng.rand(G, G) * 0.12
        m = h < tongue * (1 - np.abs(xx + 0.5 - G / 2) / (G / 2) * 0.6)
        img = np.zeros((G, G, 3), np.uint8)
        img[:] = SKYBLUE; img[h < tongue * 0.75] = ICE; img[h < tongue * 0.4] = WHITE
        mat = s2.write_material(OUT, '%s/fire%d' % (PAL_DIR, f), up(img, 4), up((m * 255).astype(np.uint8), 4), blend=2, backfaces=True, comment='nova fire %d' % f)
        out['fire%d' % f] = s2.write_model(OUT, MDIR, 'fire%d' % f, star_tris('spr_fx', 150, 55 + f * 12, 0), {'spr_fx': mat})
    # AEGIS: a shell of light hexagons round the car (eight panels and a lid), see-through between the cells
    G = 32
    yy, xx = np.mgrid[0:G, 0:G]
    hx = (xx // 8 + (yy // 7) % 2 * 0.5)
    cell = ((xx + (yy // 7) % 2 * 4) % 8 == 0) | (yy % 7 == 0)
    img = np.zeros((G, G, 3), np.uint8); img[:] = ICE; img[cell] = WHITE
    alpha = (cell | ((xx + yy) % 5 == 0)).astype(np.uint8) * 255
    mat = s2.write_material(OUT, PAL_DIR + '/aegis', up(img, 4), up(alpha, 4), blend=2, backfaces=True, comment='aegis shell')
    tris = []
    Rs, Hs, K = 80, 64, 8
    for k in range(K):
        a0, a1 = 2 * math.pi * k / K, 2 * math.pi * (k + 1) / K
        p0 = (Rs * math.cos(a0), Rs * math.sin(a0)); p1 = (Rs * math.cos(a1), Rs * math.sin(a1))
        a = (p0[0], p0[1], 2, 0, 1); b = (p1[0], p1[1], 2, 1, 1); c = (p1[0] * 0.75, p1[1] * 0.75, Hs, 1, 0); d = (p0[0] * 0.75, p0[1] * 0.75, Hs, 0, 0)
        n = (math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0.3)
        tris += [('spr_fx', (a, b, c), n), ('spr_fx', (a, c, d), n)]
        tc = (0, 0, Hs + 16, 0.5, 0.5)
        tris.append(('spr_fx', (d, c, tc), (0, 0, 1)))
    out['aegis'] = s2.write_model(OUT, MDIR, 'aegis', tris, {'spr_fx': mat})
    # SEEKER BOLT: a glowing dart pointing along +x with a flickering exhaust tail, on two crossed planes (horizontal and
    # vertical, both faces drawn), two frames that the script alternates
    for f in range(2):
        W_, Hh = 32, 8
        yy, xx = np.mgrid[0:Hh, 0:W_]
        cy = np.abs(yy + 0.5 - Hh / 2)
        head = xx >= 22
        body = (xx >= 10) & (xx < 22) & (cy < 2.2)
        tip = head & (cy < (W_ - xx) * 0.45)
        tail_len = 10 if f == 0 else 7
        tail = (xx < 10) & (xx >= 10 - tail_len) & (cy < 1.2 + (10 - xx) * (0.18 if f == 0 else 0.28))
        m = body | tip | tail
        img = np.zeros((Hh, W_, 3), np.uint8); img[:] = SKYBLUE
        img[body | tip] = ICE; img[(body | tip) & (cy < 1.1)] = WHITE
        img[tail] = (GOLD, ORANGE)[f]; img[tail & (cy < 0.8)] = CREAM
        mat = s2.write_material(OUT, '%s/bolt%d' % (PAL_DIR, f), up(img, 4), up((m * 255).astype(np.uint8), 4), blend=2, backfaces=True, comment='seeker bolt %d' % f)
        L0, L1, H2 = -60, 36, 12
        hq = [(L0, -H2, 0, 0, 1), (L1, -H2, 0, 1, 1), (L1, H2, 0, 1, 0), (L0, H2, 0, 0, 0)]
        vq = [(L0, 0, -H2, 0, 1), (L1, 0, -H2, 1, 1), (L1, 0, H2, 1, 0), (L0, 0, H2, 0, 0)]
        tris = [('spr_fx', (hq[0], hq[1], hq[2]), (0, 0, 1)), ('spr_fx', (hq[0], hq[2], hq[3]), (0, 0, 1)),
                ('spr_fx', (vq[0], vq[1], vq[2]), (0, 1, 0)), ('spr_fx', (vq[0], vq[2], vq[3]), (0, 1, 0))]
        out['bolt%d' % f] = s2.write_model(OUT, MDIR, 'bolt%d' % f, tris, {'spr_fx': mat})
    # null model (nothing visible) for idle props and sound anchors
    tiny = [('spr_fx', ((0, 0, 0, 0, 0), (0.01, 0, 0, 0, 0), (0, 0.01, 0, 0, 0)), (0, 0, 1))]
    out['null'] = s2.write_model(OUT, 'models/spr', 'null', tiny, {'spr_fx': fence})
    return out

# ---------------------------------------------------------------- pictures (HUD car picker + preview)
def render_voxels(g, pal, size=256, az=200.0, el=24.0, fill=0.78, ss=3, style=None):
    """Shaded voxel render. az = where the camera stands around the car in degrees (180 = straight behind,
    0 = in front), el = degrees above the horizon. Exposed faces only, far to near, supersampled."""
    from PIL import ImageDraw
    occ, col = g.occ, g.col
    L, W, H = occ.shape
    a, e = math.radians(az), math.radians(el)
    cdir = np.array([math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)])   # object -> camera
    fwd = -cdir
    right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    light = np.array([-0.4, 0.5, 0.85]); light /= np.linalg.norm(light)
    ctr = np.array([L / 2, 0, H / 2])
    pad = np.zeros((L + 2, W + 2, H + 2), bool); pad[1:-1, 1:-1, 1:-1] = occ
    dirs = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    shade_of = [2, 2, 1, 1, 0, 3]
    faces = []
    for fi, d in enumerate(dirs):
        if np.dot(d, cdir) <= 0: continue
        nb = pad[1 + d[0]:L + 1 + d[0], 1 + d[1]:W + 1 + d[1], 1 + d[2]:H + 1 + d[2]]
        xs, ys, zs = np.where(occ & ~nb)
        for x, y, z in zip(xs, ys, zs):
            c = int(col[x, y, z])
            if c >= FLAME0:       # flames: frame 0 of the car's flame style (orange if none given)
                k = c - FLAME0
                base = np.array(flame_rgb(style, k // FLAME_BANDS, k % FLAME_BANDS, 0) if style else pal[(7, 5, 6)[k // FLAME_BANDS] * 4], np.float32)
            else:
                base = pal[c * 4 + shade_of[fi]].astype(np.float32)
            if c not in GLOW and c < FLAME0:
                base = base * (0.7 + 0.45 * max(0.0, float(np.dot(d, light))))
            # the face square (4 corners) in grid coordinates (y is centred)
            o = np.array([x, y - W / 2, z], float)
            ax = [i for i in range(3) if d[i] == 0]
            p0 = o.copy()
            if d[[i for i in range(3) if d[i] != 0][0]] > 0: p0[[i for i in range(3) if d[i] != 0][0]] += 1
            u = np.zeros(3); u[ax[0]] = 1; v = np.zeros(3); v[ax[1]] = 1
            quad = [p0, p0 + u, p0 + u + v, p0 + v]
            depth = float(np.dot(o + 0.5 - ctr, fwd))
            faces.append((depth, quad, tuple(int(t) for t in np.clip(base, 0, 255))))
    faces.sort(key=lambda f: -f[0])
    S = size * ss
    proj = [[(float(np.dot(q - ctr, right)), -float(np.dot(q - ctr, up))) for q in quad] for _, quad, _ in faces]
    allp = np.array([p for pp in proj for p in pp]) if proj else np.zeros((1, 2))
    mn, mx = allp.min(0), allp.max(0)
    sc = S * fill / max(mx[0] - mn[0], mx[1] - mn[1], 1e-6)
    cx, cy = (mn + mx) / 2
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    for (depth, quad, c), pp in zip(faces, proj):
        pts = [(S / 2 + (px - cx) * sc, S / 2 + (py - cy) * sc) for px, py in pp]
        dr.polygon(pts, fill=c + (255,), outline=tuple(max(0, v - 30) for v in c) + (255,))
    return img.resize((size, size), Image.LANCZOS)

def main():
    pal_paths = write_palettes()
    shadow_mat = write_shadow_material()
    models = {}
    grids = {}
    flame_mats = {style: flame_material(style) for style in FLAME_STYLES}
    for key in CARS:
        models[key] = {}
        for boost in (False, 'boost', 'pad'):
            path, g = build_car(key, boost, pal_paths, shadow_mat, flame_mats)
            models[key][boost or 'base'] = path
            grids[key + ('_' + boost if boost else '')] = g
        print(key, 'voxels', int(grids[key].occ.sum()))
    fx = write_effects()
    if DEPTH:                          # the sea creatures go with the effect models (the map caches them all)
        import creatures
        fx.update(creatures.build(OUT))
    os.makedirs(os.path.join(OUT, '_gen'), exist_ok=True)
    shades = {side: [dict(skin=k, name=nm, rgb=list(SKINS[k][0])) for k, nm in SHADES[side]] for side in SHADES}
    json.dump(dict(cars=models, fx=fx, skins=['neutral'] + SKIN_ORDER, shades=shades, hover=HOVER), open(os.path.join(OUT, '_gen/car_models.json'), 'w'), indent=1)
    # picker pictures: the view you get in the race (from behind, a little to the side and above)
    pdir = os.path.join(OUT, 'panorama/images/custom_game/spr'); os.makedirs(pdir, exist_ok=True)
    for key in CARS:
        for skin in ('neutral', 't', 'ct'):
            img = render_voxels(grids[key + '_boost'], palette(*SKINS[skin]), size=256, az=205, el=22, fill=0.86, style=key)
            img.save(os.path.join(pdir, 'car_%s_%s.png' % (key, skin)))
    # big renders for the loading screen
    for i, key in enumerate(CARS):
        sk = SKINS['t' if i % 2 == 0 else 'ct']
        img = render_voxels(grids[key + '_boost'], palette(*sk), size=420, az=200, el=18, fill=0.9, style=key)
        img.save(os.path.join(OUT, '_gen', 'big_%s.png' % key))
    if PREVIEW:
        # every car from 8 directions (the models are true 3D, so every angle is drawn correctly in game)
        cell = 200
        angles = [180, 225, 270, 315, 0, 45, 90, 135]
        names = ['REAR', 'REAR-RIGHT', 'RIGHT', 'FRONT-RIGHT', 'FRONT', 'FRONT-LEFT', 'LEFT', 'REAR-LEFT']
        sheet = Image.new('RGBA', (cell * 8, cell * 4 + 30), (14, 14, 22, 255))
        from PIL import ImageDraw
        dr = ImageDraw.Draw(sheet)
        for i, nm in enumerate(names): dr.text((i * cell + 8, 8), nm, fill=(200, 200, 210))
        for r, key in enumerate(CARS):
            skin = ('t', 'ct', 't', 'ct')[r]
            for i, az in enumerate(angles):
                im = render_voxels(grids[key + ('_boost' if i == 0 else '_pad' if i == 7 else '')], palette(*SKINS[skin]), size=cell, az=az, el=20, fill=0.8, style='pad' if i == 7 else key)
                sheet.alpha_composite(im, (i * cell, 30 + r * cell))
            dr.text((8, 30 + r * cell + 8), key.upper(), fill=(255, 220, 90))
        sheet.save(PREVIEW)
        rear = Image.new('RGBA', (4 * 300, 300), (14, 14, 22, 255))
        for i, key in enumerate(CARS):
            im = render_voxels(grids[key], palette(*SKINS['ct' if i % 2 else 't']), size=300, az=180, el=14, fill=0.8)
            rear.alpha_composite(im, (i * 300, 0))
        rear.save(PREVIEW.replace('.png', '_rear.png'))
        # every shade (!shade), on a Hornet and a Bastion
        cs = 180
        sh = Image.new('RGBA', (cs * 6, cs * 4 + 30), (14, 14, 22, 255))
        dr = ImageDraw.Draw(sh)
        for r, (side, key) in enumerate((('t', 'hornet'), ('t', 'bastion'), ('ct', 'hornet'), ('ct', 'bastion'))):
            for i, (sk, nm) in enumerate(SHADES[side]):
                im = render_voxels(grids[key + '_boost'], palette(*SKINS[sk]), size=cs, az=205, el=22, fill=0.8, style=key)
                sh.alpha_composite(im, (i * cs, 30 + r * cs))
                if r % 2 == 0: dr.text((i * cs + 8, 8 if r == 0 else 30 + r * cs + 4), '%d %s' % (i + 1, nm), fill=(230, 230, 240))
        sh.save(PREVIEW.replace('.png', '_shades.png'))
    print('car models written:', sum(len(v) for v in models.values()), 'fx', len(fx))

if __name__ == '__main__':
    main()
