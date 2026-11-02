"""Space Racer track designs and themes (data only; tracks.py builds everything from these).

Track space: x east, y north, z up, CS2 units, centred on (0, 0). The centreline must stay within +-HALF - 600.

pts: control points (x, y, z, half-width) in driving order; the loop closes back to the first point, which is the
start/finish line, so keep the ~1500 units before it straight and flat (the grid sits there).
feats: (kind, from, to, lat0, lat1): from/to fractions of the lap, lat -1 (left edge) .. 1 (right edge).
gaps: (from, to) fractions with no rails.
jumps: (lip, ramp_samples, void_samples, ramp_height): a ramp ending at fraction `lip`, then open space (void 0: a
kicker - the road carries on under the car, it just flies).
tunnels: (from, to) fractions inside a tube.
bank: the most a bend leans, degrees (banking is worked out from the curvature).
"""
import math
from retro import *

HALF = 6900             # half the size of each track's box

def stadium(cx, cy, hx, hy, r, n=7):
    """control points of a rounded rectangle, counter-clockwise, starting mid-bottom (driving east)"""
    pts = []
    def arc_(ccx, ccy, a0, a1):
        for k in range(n + 1):
            a = a0 + (a1 - a0) * k / n
            pts.append((ccx + r * math.cos(a), ccy + r * math.sin(a)))
    pts.append((cx, cy - hy))
    pts.append((cx + hx - r, cy - hy))
    arc_(cx + hx - r, cy - hy + r, -math.pi / 2, 0)
    arc_(cx + hx - r, cy + hy - r, 0, math.pi / 2)
    pts.append((cx, cy + hy))
    pts.append((cx - hx + r, cy + hy))
    arc_(cx - hx + r, cy + hy - r, math.pi / 2, math.pi)
    arc_(cx - hx + r, cy - hy + r, math.pi, 3 * math.pi / 2)
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1: out.append(p)
    return out

def arc(cx, cy, r, a0, a1, n, z0=0.0, z1=0.0):
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n), z0 + (z1 - z0) * k / n)
            for k in range(n + 1)]

def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)

TRACKS = []

# 1. Solar Oval: a huge stadium. The east bend climbs onto an elevated back straight with a chicane, which ends in a
# tube; the west bend dives back down to the start. Easy, fast, draft-heavy.
p = stadium(0, 0, 5600, 3000, 2100, n=6)
oval = []
for x, y in p:
    if abs(y - 3000) < 1 and abs(x) < 1:
        oval += [(1700, 3000), (700, 2650), (-700, 2650), (-1700, 3000)]
        continue
    oval.append((x, y))
def oval_z(x, y):
    # 0 on the bottom straight, 520 on the top one, ramps through the bends
    return 520 * smoothstep(-2600, 2600, y)
TRACKS.append(dict(id='oval', title='SOLAR OVAL', laps=3, theme='oval', bank=16, scenery='city',
    pts=[(x, y, oval_z(x, y), 360) for x, y in oval],
    feats=[('boost', 0.05, 0.07, -0.6, 0.6), ('boost', 0.13, 0.15, -0.6, 0.6),
           ('charge', 0.23, 0.31, 0.45, 1.0), ('boost', 0.45, 0.47, -0.5, 0.5),
           ('slick', 0.50, 0.53, -1.0, 1.0), ('boost', 0.62, 0.64, -0.6, 0.6),
           ('charge', 0.74, 0.82, 0.45, 1.0), ('boost', 0.92, 0.94, -0.6, 0.6)],
    gaps=[], tunnels=[(0.55, 0.62)], jumps=[(0.401, 6, 14, 110)],
    slogans=['32 CARS 1 WINNER', 'SOLAR OVAL', 'DRAFT TO WIN']))

# 2. Hairpin Harbour: four long straights joined by three hairpins, climbing a terrace each time, then a wide
# loop round the west side and down through the harbour tube to the start.
S2 = 1.6
hp = []
X = 2000 * S2; y0 = -1800 * S2; r = 380 * S2
hp += [(-1100 * S2, y0, 0), (X, y0, 0)]
for i in range(3):
    yA = y0 + 2 * r * i; yB = yA + 2 * r; cy = yA + r
    zA, zB = 170 * i, 170 * (i + 1)
    if i % 2 == 0:
        hp += arc(X, cy, r, -math.pi / 2, math.pi / 2, 6, zA, zB)[1:-1]
        hp += [(X, yB, zB), (-X, yB, zB)]
    else:
        hp += arc(-X, cy, r, -math.pi / 2, -3 * math.pi / 2, 6, zA, zB)[1:-1]
        hp += [(-X, yB, zB), (X, yB, zB)]
hp += [(x, y, 510) for x, y, z in arc(-2500 * S2, 20 * S2, 460 * S2, math.pi / 2, math.pi, 4)[1:]]
hp += [(-2960 * S2, -400 * S2, 330), (-2960 * S2, -1000 * S2, 120)]
hp += arc(-2500 * S2, -1340 * S2, 460 * S2, math.pi, 3 * math.pi / 2, 4, 40, 0)[1:]
hp += [(-1900 * S2, y0, 0)]
TRACKS.append(dict(id='hairpin', title='HAIRPIN HARBOUR', laps=2, theme='hairpin', bank=22, scenery='city',
    pts=[(x, y, z, 290) for x, y, z in hp],
    feats=[('boost', 0.02, 0.04, -0.5, 0.5), ('boost', 0.175, 0.195, -0.5, 0.5), ('boost', 0.335, 0.355, -0.5, 0.5),
           ('boost', 0.495, 0.515, -0.5, 0.5),
           ('charge', 0.10, 0.125, -1.0, -0.35), ('charge', 0.26, 0.285, 0.35, 1.0), ('charge', 0.42, 0.445, -1.0, -0.35),
           ('charge', 0.58, 0.605, 0.35, 1.0),
           ('boost', 0.70, 0.72, -0.6, 0.6), ('charge', 0.80, 0.84, 0.4, 1.0), ('boost', 0.93, 0.95, -0.6, 0.6)],
    gaps=[], tunnels=[(0.775, 0.865)], jumps=[(0.2426, 6, 14, 110), (0.6804, 6, 15, 110)],
    slogans=['HAIRPIN HARBOUR', 'BRAKE LATE', 'DRIFT = CHARGE']))

def hermite_heights(cum, keys):
    """height at each distance in cum from keyframes (distance, height, slope): smooth cubic pieces between them"""
    out = []
    for s in cum:
        z = keys[-1][1]
        for (s0, z0, m0), (s1, z1, m1) in zip(keys, keys[1:]):
            if s0 <= s <= s1:
                h = s1 - s0; t = (s - s0) / h
                z = ((2 * t ** 3 - 3 * t ** 2 + 1) * z0 + (t ** 3 - 2 * t ** 2 + t) * h * m0 + (-2 * t ** 3 + 3 * t ** 2) * z1
                     + (t ** 3 - t ** 2) * h * m1)
                break
        out.append(z)
    return out

# 3. Crosswire: a giant figure-8. The first pass through the middle dives low; the second climbs into a full spiral
# loop round the crossing (the first pass threads through it, twice under it), comes out over the top of itself
# and dives round the east lobe back to the grid.
def lem(t, a):
    den = 1 + math.sin(t) ** 2
    return a * math.cos(t) / den, a * math.sin(t) * math.cos(t) / den * 1.35
CW_A, CW_R = 5000, 1100          # figure-8 size; loop radius
CW_H1, CW_HL = 650, 720          # loop height where it starts (over the crossing); how much it climbs in the circle
CW_ZA, CW_ZS = -100, 250         # the first pass at the crossing; the grid
(bx0, by0), (bx1, by1) = lem(1.5 * math.pi - 1e-4, CW_A), lem(1.5 * math.pi + 1e-4, CW_A)
hd = math.atan2(by1 - by0, bx1 - bx0)               # the second pass's heading through the middle (south-east)
lft = (math.cos(hd + math.pi / 2), math.sin(hd + math.pi / 2))
O = (CW_R * lft[0], CW_R * lft[1])                  # loop centre: on the second pass's left, so the loop touches the middle
ph0 = math.atan2(-lft[1], -lft[0])
cxy = []; mark = {}
for k in range(48):
    if k == 6: mark['c1'] = len(cxy)                # first pass through the middle
    if k == 30:                                     # second pass: the middle, a full left-hand circle round O, the middle
        mark['c2'] = len(cxy); cxy.append((0.0, 0.0))
        cxy += [(O[0] + CW_R * math.cos(ph0 + 2 * math.pi * j / 16), O[1] + CW_R * math.sin(ph0 + 2 * math.pi * j / 16)) for j in range(1, 16)]
        mark['c3'] = len(cxy); cxy.append((0.0, 0.0))
        continue
    cxy.append(lem(2 * math.pi * k / 48 + math.pi / 4, CW_A))
ccum = [0.0]
for (x0, y0), (x1, y1) in zip(cxy, cxy[1:] + cxy[:1]): ccum.append(ccum[-1] + math.hypot(x1 - x0, y1 - y0))
CL = ccum.pop()
s1, s2, s3 = ccum[mark['c1']], ccum[mark['c2']], ccum[mark['c3']]
m = CW_HL / (s3 - s2)                               # the loop's climb rate; the road climbs into it and out of it as fast,
cz = hermite_heights(ccum, [                        # so the decks stacked over the middle stay 600+ apart
    (0, CW_ZS, 0), (400, CW_ZS, 0), (s1 - 350, CW_ZA, 0), (s1 + 350, CW_ZA, 0), (s2, CW_H1, m), (s3, CW_H1 + CW_HL, m),
    (s3 + 1300, CW_H1 + CW_HL + m * 650, 0), (CL - 1700, CW_ZS, 0), (CL, CW_ZS, 0)])
TRACKS.append(dict(id='crosswire', title='CROSSWIRE', laps=3, theme='crosswire', bank=20, scenery='city',
    pts=[(x, y, z, 300) for (x, y), z in zip(cxy, cz)],
    feats=[('boost', 0.03, 0.05, -0.6, 0.6), ('slick', 0.15, 0.17, -1.0, 1.0), ('charge', 0.25, 0.31, 0.4, 1.0),
           ('boost', 0.42, 0.44, -0.5, 0.5), ('charge', 0.56, 0.62, -1.0, -0.4), ('slick', 0.76, 0.78, -1.0, 1.0),
           ('charge', 0.83, 0.88, -1.0, -0.4), ('boost', 0.935, 0.955, -0.6, 0.6)],
    gaps=[], tunnels=[], jumps=[(0.1204, 6, 15, 110)],
    slogans=['CROSSWIRE', 'THREAD THE LOOP', 'NO BRAKES']))

# 4. Null Gap: a kidney-shaped loop over the void; two long rail-less sections on narrow roads that roll up and
# down like a roller coaster.
ngz = []
NG = 44
for i in range(NG):
    t = 2 * math.pi * i / NG
    rr = 4300 + 840 * math.cos(2 * t) - 450 * math.cos(3 * t)
    f = i / NG
    hw = 330
    z = 0
    if 0.17 < f < 0.36 or 0.6 < f < 0.78:
        hw = 230
    if 0.19 < f < 0.345: z = 260 * math.sin((f - 0.19) / 0.155 * 2 * math.pi) ** 2 * (1 if (f - 0.19) < 0.08 else 0.7) + 120
    if 0.615 < f < 0.765: z = -280 * math.sin((f - 0.615) / 0.15 * math.pi)
    ngz.append((rr * math.cos(t) * 1.02, rr * math.sin(t) * 0.92, z, hw))
TRACKS.append(dict(id='nullgap', title='NULL GAP', laps=3, theme='nullgap', bank=14, scenery='asteroids',
    pts=ngz,
    feats=[('charge', 0.08, 0.13, -1.0, -0.45), ('charge', 0.52, 0.57, 0.45, 1.0),
           ('boost', 0.035, 0.055, -0.5, 0.5), ('boost', 0.46, 0.48, -0.5, 0.5),
           ('boost', 0.26, 0.275, -0.4, 0.4), ('boost', 0.68, 0.695, -0.4, 0.4),
           ('boost', 0.90, 0.92, -0.6, 0.6)],
    gaps=[(0.19, 0.345), (0.615, 0.765)], tunnels=[],
    slogans=['MIND THE GAP', 'NULL GAP', 'NO RAILS AHEAD']))

# 5. Switchback Spire: up four stacked switchbacks to 1200 units, then a long banked sweep and a dive back down.
S5 = 1.35
sp = [(-2200 * S5, -2300 * S5, 0), (900 * S5, -2300 * S5, 0)]
rows = [-2300 * S5, -1500 * S5, -700 * S5, 100 * S5, 900 * S5]
heights = [0, 300, 600, 900, 1200]
r = 400 * S5
for i in range(4):
    yA, yB = rows[i], rows[i + 1]
    zA, zB = heights[i], heights[i + 1]
    cy = (yA + yB) / 2
    if i % 2 == 0:
        sp += arc(900 * S5, cy, r, -math.pi / 2, math.pi / 2, 6, zA, zB)[1:-1]
        sp += [(900 * S5, yB, zB), (-900 * S5, yB, zB)]
    else:
        sp += arc(-900 * S5, cy, r, -math.pi / 2, -3 * math.pi / 2, 6, zA, zB)[1:-1]
        sp += [(-900 * S5, yB, zB), (900 * S5, yB, zB)]
sp += [(1800 * S5, 1050 * S5, 1200), (2500 * S5, 1500 * S5, 1180), (2900 * S5, 2150 * S5, 1120), (2700 * S5, 2650 * S5, 1040),
       (1900 * S5, 2900 * S5, 960), (0, 2950 * S5, 880),
       (-1900 * S5, 2800 * S5, 760), (-2750 * S5, 2300 * S5, 620), (-2950 * S5, 1500 * S5, 420), (-3000 * S5, 400 * S5, 200),
       (-2950 * S5, -800 * S5, 70), (-2780 * S5, -1700 * S5, 20), (-2500 * S5, -2200 * S5, 0)]
TRACKS.append(dict(id='spire', title='SWITCHBACK SPIRE', laps=2, theme='spire', bank=20, scenery='crystals',
    pts=[(x, y, z, 290) for x, y, z in sp],
    feats=[('boost', 0.015, 0.035, -0.5, 0.5), ('charge', 0.095, 0.125, 0.4, 1.0), ('charge', 0.265, 0.295, -1.0, -0.4),
           ('charge', 0.435, 0.465, 0.4, 1.0), ('boost', 0.56, 0.58, -0.5, 0.5), ('boost', 0.70, 0.72, -0.6, 0.6),
           ('boost', 0.84, 0.86, -0.6, 0.6), ('slick', 0.76, 0.79, -1.0, 1.0)],
    gaps=[], tunnels=[(0.885, 0.95)], jumps=[(0.180, 6, 14, 110), (0.5172, 6, 15, 110)],
    slogans=['SWITCHBACK SPIRE', 'GOING UP', 'HOLD MOUSE 1']))

# 6. Ringworld: a figure-8 with a big and a small lobe; one pass through the middle is a bridge 920 units up, the
# other runs under it through a tube.
rw = []
a = 5800
n = 52
for k in range(n):
    t = 2 * math.pi * k / n + math.pi + 0.9
    den = 1 + math.sin(t) ** 2
    x = a * math.cos(t) / den; y = a * math.sin(t) * math.cos(t) / den * 1.3
    if x > 0: x *= 0.74; y *= 0.74
    tt = (t - math.pi / 2 + math.pi) % (2 * math.pi) - math.pi
    u = abs(tt)
    z = 920.0 if u < 0.25 else (920 * (0.5 - 0.5 * math.cos(math.pi * (1 - (u - 0.25) / 0.45))) if u < 0.7 else 0.0)
    rw.append((x, y, z, 300))
TRACKS.append(dict(id='ringworld', title='RINGWORLD', laps=3, theme='ringworld', bank=18, scenery='rings',
    pts=rw,
    feats=[('boost', 0.035, 0.055, -0.6, 0.6), ('slick', 0.095, 0.115, -1.0, 1.0), ('charge', 0.20, 0.26, 0.4, 1.0),
           ('boost', 0.33, 0.35, -0.5, 0.5), ('charge', 0.42, 0.47, -1.0, -0.4), ('boost', 0.48, 0.50, -0.5, 0.5),
           ('boost', 0.70, 0.72, -0.5, 0.5), ('charge', 0.80, 0.86, 0.4, 1.0), ('boost', 0.92, 0.94, -0.6, 0.6)],
    gaps=[], tunnels=[], crossing=True, undertube=True,
    slogans=['RINGWORLD', 'OVER AND UNDER', 'STAY ON THE LINE']))

# 7. Skyway: a fast stadium high in the sky with a long downhill jump on each straight - boost pads feed the ramps
# and a slow car drops into the gap. The bends are steeply banked.
sk0 = stadium(0, 0, 5800, 3300, 2000, n=7)
def sky_zmod(f):
    """landings are 240 lower than the lips; the bend after each jump climbs back"""
    return -240 * (smoothstep(0.072, 0.09, f) - smoothstep(0.13, 0.30, f) + smoothstep(0.522, 0.54, f) - smoothstep(0.58, 0.75, f))
TRACKS.append(dict(id='skyway', title='SKYWAY', laps=3, theme='skyway', bank=26, scenery='clouds',
    pts=[(x, y, 0, 320) for x, y in sk0],
    feats=[('boost', 0.022, 0.045, -0.6, 0.6), ('boost', 0.47, 0.493, -0.6, 0.6),
           ('charge', 0.16, 0.22, 0.4, 1.0), ('charge', 0.33, 0.39, 0.4, 1.0), ('charge', 0.65, 0.71, 0.4, 1.0), ('charge', 0.83, 0.89, 0.4, 1.0),
           ('slick', 0.27, 0.29, -1.0, 1.0)],
    gaps=[], tunnels=[], jumps=[(0.07, 6, 15, 110), (0.52, 6, 15, 110), (0.41, 4, 0, 70), (0.76, 4, 0, 70)], zmod=sky_zmod,
    slogans=['SKYWAY', 'FULL SPEED OR FALL', 'BOOST = SPEED']))

# 8. Helix: up a stacked spiral (1.5 turns, 1300 units of climb), then off the west side and a banked dive home
# through a tube.
hx = [(-1200, -5200, 0), (2400, -5200, 0)]
hx += arc(2400, -4000, 1200, -math.pi / 2, 0, 5)[1:]
hx += [(3600, -2400, 0), (3600, -1300, 0)]
C, R, TURN, RISE = (1500, -300), 2100, 3.0 * math.pi, 1300
for k in range(0, 37):
    a_ = TURN * k / 36
    hx.append((C[0] + R * math.cos(a_), C[1] + R * math.sin(a_), RISE * a_ / TURN))
hx += [(-1100, -1700, 1220), (-2300, -2700, 1000), (-3600, -3300, 700), (-4500, -4100, 420)]
hx += arc(-3400, -4300, 1100, math.pi * 0.95, 1.5 * math.pi, 4, 260, 0)[1:]
TRACKS.append(dict(id='helix', title='HELIX', laps=3, theme='helix', bank=20, scenery='asteroids',
    pts=[(x, y, z, 290) for x, y, z in hx],
    feats=[('boost', 0.025, 0.045, -0.6, 0.6), ('charge', 0.09, 0.13, 0.4, 1.0), ('boost', 0.20, 0.215, -0.5, 0.5),
           ('charge', 0.33, 0.37, -1.0, -0.4), ('boost', 0.46, 0.475, -0.5, 0.5), ('charge', 0.55, 0.59, -1.0, -0.4),
           ('boost', 0.72, 0.74, -0.6, 0.6), ('slick', 0.80, 0.82, -1.0, 1.0), ('boost', 0.93, 0.95, -0.6, 0.6)],
    gaps=[], tunnels=[(0.83, 0.90)], crossing=True, jumps=[(0.1817, 6, 15, 110)],
    slogans=['HELIX', 'SPIN TO WIN', 'GOING DOWN']))

# ---------------------------------------------------------------- themes: all colours from the retro palette
# road / road2: road surface; line: road markings; rail: rail glow; post: pylons; gate: checkpoint gates;
# sky: (zenith, middle, horizon) for the pixel-art panorama; glow: neon accent for scenery; planet: big body in the sky
THEMES = {
    'oval':      dict(road=INK, road2=PLUM, line=GOLD, rail=ORANGE, post=RUST, gate=CREAM, sky=(BLACK, PURPLE, HOT),
                      glow=GOLD, win=(GOLD, CREAM, ORANGE), planet=(HOT, 'sun'), floor=MAGENTA),
    'hairpin':   dict(road=NAVY, road2=DEEPTEAL, line=MINT, rail=TEAL, post=DEEPTEAL, gate=MINT, sky=(BLACK, NAVY, DEEPTEAL),
                      glow=TEAL, win=(MINT, TEAL, ICE), planet=(SKYBLUE, 'ringed'), floor=TEAL),
    'crosswire': dict(road=INK, road2=PURPLE, line=PINK, rail=MAGENTA, post=PURPLE, gate=PINK, sky=(BLACK, PURPLE, MAGENTA),
                      glow=MAGENTA, win=(PINK, MAGENTA, ICE), planet=(SKYBLUE, 'banded'), floor=PINK),
    'nullgap':   dict(road=INK, road2=WINE, line=SALMON, rail=RED, post=WINE, gate=SALMON, sky=(BLACK, INK, WINE),
                      glow=RED, win=(RED, SALMON, GOLD), planet=(RED, 'cratered'), floor=RED),
    'spire':     dict(road=INK, road2=DARKGREEN, line=LIME, rail=GREEN, post=DARKGREEN, gate=LIME, sky=(BLACK, DARKGREEN, TEAL),
                      glow=LIME, win=(LIME, GREEN, MINT), planet=(LIME, 'banded'), floor=GREEN),
    'ringworld': dict(road=SOIL, road2=INK, line=CREAM, rail=GOLD, post=RUST, gate=CREAM, sky=(BLACK, SOIL, ORANGE),
                      glow=GOLD, win=(GOLD, CREAM, SAND), planet=(SAND, 'ringed'), floor=GOLD),
    'skyway':    dict(road=NAVY, road2=INK, line=ICE, rail=SKYBLUE, post=BLUE, gate=FROST, sky=(NAVY, BLUE, SKYBLUE),
                      glow=SKYBLUE, win=(ICE, FROST, WHITE), planet=(WHITE, 'moon'), floor=SKYBLUE),
    'helix':     dict(road=INK, road2=RUST, line=SALMON, rail=HOT, post=RUST, gate=CREAM, sky=(BLACK, WINE, HOT),
                      glow=HOT, win=(HOT, GOLD, SALMON), planet=(ORANGE, 'banded'), floor=HOT),
}
