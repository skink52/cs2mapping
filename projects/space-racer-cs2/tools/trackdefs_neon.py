"""Neon Racer track designs and themes (same format as trackdefs.py, which documents every field).

Extra fields (Neon Racer):
flights: (from, to, radius) fractions of the lap flown instead of driven: no road, a round corridor of gates around the
centreline (its z is the corridor's middle); S climbs, W dives (like a plane); the corridor narrows onto the road at the end.
rings: (frac, lat, dz, radius, kind) inside a flight: kind 'ring' boosts like a pad, 'cring' charges; lat -1..1 across
the corridor (-1 left), dz up from its middle.
"""
import math
from trackdefs import stadium, arc, smoothstep, hermite_heights

HALF = 6900

CYAN, MAGENTA, ORANGE, LIME, VIOLET, RED, GOLD = (0, 235, 255), (255, 40, 200), (255, 140, 20), (110, 255, 60), (150, 80, 255), (255, 40, 70), (255, 210, 60)
WHITE, ICE, NIGHT, DEEP = (255, 255, 255), (190, 245, 255), (8, 10, 24), (20, 16, 48)

def rounded(corners, r, n=6):
    """a closed polygon (counter-clockwise or clockwise) with every corner rounded by radius r: [(x, y)]"""
    out = []
    m = len(corners)
    for k in range(m):
        p0, p1, p2 = corners[k - 1], corners[k], corners[(k + 1) % m]
        a = math.atan2(p0[1] - p1[1], p0[0] - p1[0]); b = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        da = (b - a + math.pi) % (2 * math.pi) - math.pi
        half = abs(da) / 2
        t = r / math.tan(half)                       # distance from the corner to the arc's ends
        bis = a + da / 2
        c = (p1[0] + math.cos(bis) * r / math.sin(half), p1[1] + math.sin(bis) * r / math.sin(half))
        s = (p1[0] + math.cos(a) * t, p1[1] + math.sin(a) * t); e = (p1[0] + math.cos(b) * t, p1[1] + math.sin(b) * t)
        a0 = math.atan2(s[1] - c[1], s[0] - c[0]); a1 = math.atan2(e[1] - c[1], e[0] - c[0])
        d = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        for j in range(n + 1):
            u = a0 + d * j / n
            out.append((c[0] + r * math.cos(u), c[1] + r * math.sin(u)))
    # start in the middle of the first edge (the grid wants a straight)
    mid = len(out) // m * 1
    return out[mid:] + out[:mid]

TRACKS = []

# 1. Grid Circuit: a long stadium with a chicane on the back straight and a kicker on the front one. The opener.
g = []
for x, y in stadium(0, 0, 5500, 3000, 1700, n=7):
    if abs(y - 3000) < 1 and abs(x) < 1:
        g += [(1900, 3000), (900, 2550), (-900, 2550), (-1900, 3000)]
        continue
    g.append((x, y))
TRACKS.append(dict(id='grid', title='GRID CIRCUIT', laps=3, theme='cyan', bank=18, scenery='city',
    pts=[(x, y, 260 * smoothstep(-2000, 2000, y), 340) for x, y in g],
    feats=[('boost', 0.05, 0.07, -0.6, 0.6), ('charge', 0.20, 0.27, 0.45, 1.0), ('boost', 0.36, 0.38, -0.5, 0.5),
           ('slick', 0.50, 0.52, -1.0, 1.0), ('charge', 0.70, 0.77, 0.45, 1.0), ('boost', 0.88, 0.90, -0.6, 0.6)],
    gaps=[], tunnels=[(0.56, 0.63)], jumps=[(0.13, 6, 0, 70)],
    slogans=['GRID CIRCUIT', 'RIDE THE LIGHT', 'NEON RACER']))

# 2. Pulse City: a block with a deep notch cut into its top: two hairpins round the notch, a climb onto the
# east side and a jump down off the west.
pc = rounded([(-4800, -4200), (4800, -4200), (4800, 4000), (1700, 4000), (1700, 300), (-1700, 300), (-1700, 4000), (-4800, 4000)], 950, 7)
def pc_z(x, y):
    return 380 * smoothstep(-3000, 1500, y) * smoothstep(0, 3500, x) + 380 * smoothstep(-3000, 1500, y) * (1 - smoothstep(-3500, 0, x))
TRACKS.append(dict(id='pulse', title='PULSE CITY', laps=3, theme='magenta', bank=22, scenery='city',
    pts=[(x, y, pc_z(x, y), 300) for x, y in pc],
    feats=[('boost', 0.03, 0.05, -0.6, 0.6), ('charge', 0.16, 0.21, -1.0, -0.4), ('boost', 0.33, 0.35, -0.5, 0.5),
           ('charge', 0.52, 0.57, 0.4, 1.0), ('boost', 0.66, 0.68, -0.5, 0.5), ('slick', 0.80, 0.82, -1.0, 1.0), ('boost', 0.92, 0.94, -0.6, 0.6)],
    gaps=[], tunnels=[], jumps=[(0.745, 6, 14, 110)],
    slogans=['PULSE CITY', 'TWO HAIRPINS', 'BRAKE LATE']))

# 3. Void Hop: a kidney loop over nothing. Halfway round the road ends: you fly an arcing hop through rings across the
# void and land on the far side. A rail-less stretch on the way back.
vh = []
NV = 46
for i in range(NV):
    t = 2 * math.pi * i / NV
    rr = 4200 + 900 * math.cos(2 * t) - 400 * math.cos(3 * t)
    f = i / NV
    z = 0
    if 0.40 <= f <= 0.56: z = 520 * math.sin((f - 0.40) / 0.16 * math.pi)
    vh.append((rr * math.cos(t) * 1.05, rr * math.sin(t) * 0.9, z, 300 if not (0.70 < f < 0.84) else 240))
TRACKS.append(dict(id='voidhop', title='VOID HOP', laps=3, theme='violet', bank=14, scenery='crystals',
    pts=vh,
    feats=[('boost', 0.035, 0.055, -0.5, 0.5), ('charge', 0.12, 0.17, -1.0, -0.45), ('boost', 0.36, 0.385, -0.5, 0.5),
           ('charge', 0.60, 0.65, 0.45, 1.0), ('boost', 0.90, 0.92, -0.6, 0.6)],
    gaps=[(0.71, 0.83)], tunnels=[],
    flights=[(0.405, 0.555, 330)],
    rings=[(0.43, 0.0, 120, 120, 'ring'), (0.47, -0.45, 210, 110, 'ring'), (0.47, 0.5, -60, 110, 'cring'), (0.51, 0.2, 60, 120, 'ring')],
    slogans=['VOID HOP', 'S CLIMB W DIVE', 'FLY THE RINGS']))

# 4. Data Stream: a three-lobed loop that rolls up and down all the way round, with a tube through one valley.
ds = []
ND = 60
for i in range(ND):
    t = 2 * math.pi * i / ND
    rr = 4700 + 800 * math.cos(3 * t)
    ds.append((rr * math.cos(t), rr * math.sin(t) * 0.92, 260 + 240 * math.sin(4 * t + 0.4), 300))
TRACKS.append(dict(id='stream', title='DATA STREAM', laps=3, theme='lime', bank=20, scenery='crystals',
    pts=ds,
    feats=[('boost', 0.03, 0.05, -0.6, 0.6), ('charge', 0.13, 0.19, 0.4, 1.0), ('boost', 0.30, 0.32, -0.5, 0.5),
           ('slick', 0.45, 0.47, -1.0, 1.0), ('charge', 0.55, 0.61, -1.0, -0.4), ('boost', 0.74, 0.76, -0.5, 0.5),
           ('boost', 0.91, 0.93, -0.6, 0.6)],
    gaps=[], tunnels=[(0.64, 0.71)], jumps=[(0.24, 6, 0, 70)],
    slogans=['DATA STREAM', 'ROLL WITH IT', 'DRIFT = CHARGE']))

# 5. Skyline Dive: up a spiral ramp to 1500, then the road ends and you dive through a long canyon of gates,
# weaving down to the ground and landing on the home straight.
sd = [(-3800, -5000, 0), (1200, -5000, 0)]
sd += arc(1200, -3800, 1200, -math.pi / 2, 0, 5)[1:]
C, R, TURN, RISE = (1700, -800), 1900, 2.5 * math.pi, 1500
for k in range(0, 31):
    a_ = TURN * k / 30
    sd.append((C[0] + R * math.cos(a_), C[1] + R * math.sin(a_), RISE * a_ / TURN))
# off the top (heading south-west), then the dive: west, a long left sweep south, and back east to the grid
dive = [(-1100, 1600, 1400), (-2600, 2400, 1250), (-4200, 2600, 1050), (-5300, 1800, 860), (-5600, 400, 660),
        (-5400, -1200, 460), (-4900, -2600, 280), (-4500, -3700, 120), (-4300, -4600, 20)]
sd += dive
TRACKS.append(dict(id='dive', title='SKYLINE DIVE', laps=2, theme='orange', bank=20, scenery='city',
    pts=[(x, y, z, 300) for x, y, z in sd],
    feats=[('boost', 0.02, 0.04, -0.6, 0.6), ('charge', 0.10, 0.14, 0.4, 1.0), ('boost', 0.25, 0.265, -0.5, 0.5),
           ('charge', 0.40, 0.44, -1.0, -0.4), ('boost', 0.53, 0.545, -0.5, 0.5), ('boost', 0.965, 0.98, -0.6, 0.6)],
    gaps=[], tunnels=[], crossing=True,
    flights=[(0.66, 0.935, 360)],
    rings=[(0.69, 0.0, 0, 130, 'ring'), (0.73, 0.5, 120, 110, 'ring'), (0.77, -0.5, -120, 110, 'cring'),
           (0.81, -0.3, 100, 120, 'ring'), (0.85, 0.4, -80, 110, 'ring'), (0.89, 0.0, 60, 120, 'ring')],
    slogans=['SKYLINE DIVE', 'NOSE DOWN', 'THE CITY IS BELOW']))

# 6. Overclock: a fast figure-8 with lobes of two sizes; one pass through the middle is a bridge, the other a tube.
oc = []
a = 5600
n = 54
for k in range(n):
    t = 2 * math.pi * k / n + math.pi + 0.9
    den = 1 + math.sin(t) ** 2
    x = a * math.cos(t) / den; y = a * math.sin(t) * math.cos(t) / den * 1.4
    if x > 0: x *= 0.8; y *= 0.8
    tt = (t - math.pi / 2 + math.pi) % (2 * math.pi) - math.pi
    u = abs(tt)
    z = 900.0 if u < 0.25 else (900 * (0.5 - 0.5 * math.cos(math.pi * (1 - (u - 0.25) / 0.45))) if u < 0.7 else 0.0)
    oc.append((x, y, z, 300))
TRACKS.append(dict(id='overclock', title='OVERCLOCK', laps=3, theme='red', bank=18, scenery='city',
    pts=oc,
    feats=[('boost', 0.035, 0.055, -0.6, 0.6), ('charge', 0.20, 0.26, 0.4, 1.0), ('boost', 0.33, 0.35, -0.5, 0.5),
           ('slick', 0.40, 0.42, -1.0, 1.0), ('charge', 0.62, 0.68, -1.0, -0.4), ('boost', 0.72, 0.74, -0.5, 0.5),
           ('boost', 0.92, 0.94, -0.6, 0.6)],
    gaps=[], tunnels=[], crossing=True, undertube=True,
    slogans=['OVERCLOCK', 'OVER AND UNDER', 'MAX SPEED']))

# ---------------------------------------------------------------- themes (any RGB; Neon Racer doesn't use the retro palette)
def T(main, alt, accent, sky_mid, planet_kind):
    return dict(road=NIGHT, road2=main, line=WHITE, rail=main, post=alt, gate=main, sky=((0, 0, 4), sky_mid, alt),
                glow=main, win=(main, accent, WHITE), planet=(accent, planet_kind), floor=main, accent=accent)
THEMES = {
    'cyan':    T(CYAN, VIOLET, MAGENTA, DEEP, 'sun'),
    'magenta': T(MAGENTA, VIOLET, CYAN, (30, 6, 40), 'ringed'),
    'violet':  T(VIOLET, MAGENTA, CYAN, (14, 6, 40), 'banded'),
    'lime':    T(LIME, CYAN, MAGENTA, (4, 24, 20), 'moon'),
    'orange':  T(ORANGE, MAGENTA, GOLD, (36, 10, 24), 'sun'),
    'red':     T(RED, ORANGE, CYAN, (30, 4, 12), 'cratered'),
}
