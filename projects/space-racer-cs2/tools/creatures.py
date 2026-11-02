"""Depth Racer's giant sea creatures as voxel models, built like the cars (cars.Grid + cars.mesh_voxels, one palette
material): a sea serpent (head, body segment, tail), a manta ray (two wing-beat frames) and a whale (head, body,
tail). Forward is +x and each model is centred on its middle, so the script places every segment by its centre."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import s2
import cars as C

MDIR = 'models/spr/creatures'

def palette():
    """the creatures' 12 colour roles x 4 shades, same layout as the cars' palettes"""
    base = [(36, 84, 110), (170, 205, 200), (40, 150, 150), (16, 36, 56), (60, 80, 100), (255, 190, 60), (80, 240, 230),
            (255, 90, 200), (255, 60, 80), (235, 245, 240), (40, 160, 150), (4, 8, 14)]
    pal = np.zeros((64, 3), np.float32)
    for c, col in enumerate(base):
        for sh in range(4):
            k = C.SHADE[sh] if c not in C.GLOW else (1.0 if sh == 0 else 0.94)
            pal[c * 4 + sh] = np.array(col, np.float32) * k
    img = np.zeros((64, 32, 3), np.uint8)
    for c in range(64):
        y, x = (c // 8) * 8, (c % 8) * 4
        img[y:y + 8, x:x + 4] = pal[c]
    return img

# colour roles: 0 body, 1 belly, 2 fin, 3 dark, 5 eyes (amber glow), 6 spots (cyan glow), 7 stripe (pink glow), 9 teeth
BODY, BELLY, FIN, DARK, EYE, SPOT, STRIPE, TEETH = 0, 1, 2, 3, 5, 6, 7, 9

def model(out, name, g, scale, mat):
    origin = (-g.L / 2 * scale, -g.W / 2 * scale, -g.H / 2 * scale)
    tris = C.mesh_voxels(g.occ, g.col, origin, scale)
    return s2.write_model(out, MDIR, name, tris, {'spr_pal': mat})

def spots(g, mask, every=5):
    """glowing spots along both flanks of a shape"""
    side = mask & (np.abs(g.Y) > g.W * 0.25) & (g.Z > g.H * 0.4) & (g.Z < g.H * 0.65)
    g.col[side & ((g.X.astype(int) % every) == 0)] = SPOT

def serpent(out, mat):
    m = {}
    # head: a long snout, a jaw under it, a crest, glowing eyes and teeth
    g = C.Grid(30, 14, 14)
    g.taper(0, 30, 6.5, 3.0, 4, 6.5, 3.5, BODY)
    g.taper(8, 29, 5.0, 2.0, 2, 2.5, 1.5, BELLY)
    g.box(18, 29, -3, 3, 3, 4, TEETH)
    g.taper(2, 20, 1.0, 0.6, 9, 4.5, 2.0, FIN)
    for sy in (-1, 1):
        g.box(19, 22, sy * 4 - 1, sy * 4 + 1, 8, 10, EYE)
    m['cr_serpent_head'] = model(out, 'serpent_head', g, 7, mat)
    # body: a thick round segment with a spiked fin on top and glowing spots
    g = C.Grid(18, 20, 20)
    body = g.ellipsoid(9, 0, 10, 9.5, 9.5, 9, BODY)
    g.ellipsoid(9, 0, 6, 8, 7, 4, BELLY)
    g.paint(body & (g.Z < 4), BELLY)
    for x0 in (3, 9, 15):
        g.taper(x0 - 2, x0 + 2, 1.2, 0.3, 18, 1.0, 0.5, FIN)
        g.box(x0 - 1, x0 + 1, -1, 1, 18, 20, FIN)
    spots(g, body, 4)
    top = body & (np.abs(g.Y) <= 1.2) & (g.Z > 17)
    g.col[top] = STRIPE                                                        # a glowing line down the spine
    m['cr_serpent_body'] = model(out, 'serpent_body', g, 7, mat)
    # tail: tapering to a tall glowing fin
    g = C.Grid(24, 16, 22)
    g.taper(0, 24, 2.0, 7.5, 9, 2.5, 8, BODY)
    fin = (g.X < 10) & (np.abs(g.Y) <= 1) & (np.abs(g.Z - 11) <= (10 - g.X) * 0.9 + 1)
    g.paint(fin, FIN)
    g.paint(fin & (g.X < 2.5), STRIPE)
    g.paint((g.Z > 13) & (np.abs(g.Y) <= 1) & g.occ & (g.X > 10), STRIPE)
    m['cr_serpent_tail'] = model(out, 'serpent_tail', g, 7, mat)
    return m

def manta(out, mat):
    m = {}
    for f, lift in enumerate((3.5, -2.5)):
        g = C.Grid(32, 84, 16)
        # wings: a flat diamond, the tips raised or lowered by the beat
        span = np.abs(g.Y) / 42.0
        chord = (1 - span) * 30
        zc = 8 + lift * span ** 1.5
        wing = (g.X >= 16 - chord * 0.65) & (g.X <= 16 + chord * 0.35) & (np.abs(g.Z - zc) <= 1.3 + (1 - span) * 2.2) & (span <= 1)
        g.paint(wing, BODY)
        g.paint(wing & (g.Z < zc), BELLY)
        g.paint(wing & (span > 0.55) & ((g.X.astype(int) + g.Y.astype(int)) % 7 == 0), SPOT)
        g.paint(wing & (span > 0.92), STRIPE)
        # head lobes and a whip tail
        for sy in (-1, 1):
            g.box(26, 31, sy * 5 - 1, sy * 5 + 1, 7, 10, DARK)
            g.box(24, 26, sy * 4 - 1, sy * 4 + 1, 9, 11, EYE)
        g.box(0, 6, -1, 1, 7, 9, DARK)
        m['cr_manta%d' % f] = model(out, 'manta%d' % f, g, 7, mat)
    return m

def whale(out, mat):
    m = {}
    g = C.Grid(40, 34, 30)
    head = g.taper(0, 40, 16, 12, 6, 14, 10, BODY)
    g.taper(4, 38, 13, 9, 3, 5, 3, BELLY)
    for x0 in range(6, 38, 4): g.box(x0, x0 + 1, -11, 11, 3, 5, DARK)      # throat grooves
    for sy in (-1, 1): g.box(28, 31, sy * 12 - 1, sy * 12 + 1, 12, 15, EYE)
    spots(g, head, 6)
    m['cr_whale_head'] = model(out, 'whale_head', g, 13, mat)
    g = C.Grid(30, 36, 32)
    body = g.taper(0, 30, 12, 16.5, 7, 11, 15, BODY)
    g.taper(0, 30, 9, 12, 3, 4, 5, BELLY)
    for sy in (-1, 1): g.box(12, 24, sy * 16 - 1, sy * 16 + 1 + (6 if sy > 0 else -6), 6, 8, FIN)   # pectoral fins
    g.box(10, 16, -1, 1, 22, 26, FIN)                                          # dorsal fin
    spots(g, body, 5)
    g.col[body & (np.abs(g.Y) <= 1.2) & (g.Z > 20)] = SPOT
    m['cr_whale_body'] = model(out, 'whale_body', g, 13, mat)
    g = C.Grid(34, 44, 22)
    g.taper(10, 34, 3, 11, 9, 3, 9, BODY)
    flukes = (g.X < 12) & (np.abs(g.Z - 10) <= 1.2) & (np.abs(g.Y) <= 21) & (g.X > np.abs(g.Y) * 0.35)
    g.paint(flukes, FIN)
    g.paint(flukes & (np.abs(g.Y) > 17), STRIPE)
    m['cr_whale_tail'] = model(out, 'whale_tail', g, 13, mat)
    return m

def build(out):
    mat = s2.write_material(out, 'materials/spr/creatures/pal', palette(), comment='Depth Racer sea creatures palette')
    m = {}
    m.update(serpent(out, mat)); m.update(manta(out, mat)); m.update(whale(out, mat))
    return m
