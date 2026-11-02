"""Depth Racer track designs and themes: the deep sea (same format as trackdefs.py and trackdefs_neon.py, which document
every field; `flights` here are glides through the water, `rings` the glide rings).

Extra field (Depth Racer):
creatures: (kind, frac, h, period, phase, speed, span) giant sea creatures crossing the track at one spot on a cycle:
kind 'serpent' (a long eel-like chain), 'manta' (a huge ray) or 'whale'; frac where on the lap; h how high over the
track's centreline it swims (over a jump: about where the cars fly); period seconds between passes (each pass the
other way); phase offset; speed units a second; span how far to each side of the track a pass starts and ends.
Put them over glides and jumps: that's where a driver can see them coming and has to time it.
"""
import math
from trackdefs import stadium, arc, smoothstep
from trackdefs_neon import rounded

HALF = 6900

TEAL, CYAN, SEAGREEN, CORAL, AMBER, VIOLET, PINK = (0, 210, 190), (60, 220, 255), (70, 255, 150), (255, 110, 90), (255, 190, 60), (150, 90, 255), (255, 90, 200)
WHITE, ABYSS, DEEP = (235, 250, 255), (2, 8, 20), (6, 24, 48)

TRACKS = []
JV1, JV2, CV2 = 0.245, 0.745, 0.757      # Vent Field's jumps and whale (on the hexagon's straights; set from tracks.py's curvature check)

# 1. Kelp Canyon: a winding canyon road through a kelp forest. Halfway round it jumps a chasm, and a sea serpent
# swims through the gap.
kc = rounded([(-5200, -3900), (4500, -4300), (5300, -700), (1700, 500), (4900, 2700), (3500, 4700), (-2600, 4300), (-5100, 1300)], 900, 7)
def kc_z(x, y):
    return 220 * math.sin(x / 2600.0) + 160 * math.cos(y / 2100.0) + 200
TRACKS.append(dict(id='kelp', title='KELP CANYON', laps=3, theme='teal', bank=18, scenery='kelp',
    pts=[(x, y, kc_z(x, y), 320) for x, y in kc],
    feats=[('boost', 0.04, 0.06, -0.6, 0.6), ('charge', 0.16, 0.22, 0.45, 1.0), ('boost', 0.28, 0.30, -0.5, 0.5),
           ('slick', 0.55, 0.57, -1.0, 1.0), ('charge', 0.68, 0.74, -1.0, -0.45), ('boost', 0.90, 0.92, -0.6, 0.6)],
    gaps=[], tunnels=[(0.78, 0.84)], jumps=[(0.405, 6, 14, 120)],
    creatures=[('serpent', 0.42, 170, 9.0, 0.0, 760, 2300)],
    slogans=['KELP CANYON', 'MIND THE SERPENT', 'JUMP THE CHASM']))

# 2. Coral Crown: a big stadium round a giant coral ring. The back straight runs along a reef shelf and glides off
# it, under a huge manta ray, down onto the far bend.
cc = stadium(0, 0, 5500, 3500, 2000, n=7)
def cc_z(f):
    return 420 * smoothstep(0.18, 0.36, f) - 420 * smoothstep(0.60, 0.74, f)
TRACKS.append(dict(id='coral', title='CORAL CROWN', laps=3, theme='coral', bank=20, scenery='coral',
    pts=[(x, y, cc_z(k / len(cc)), 340) for k, (x, y) in enumerate(cc)],
    feats=[('boost', 0.04, 0.06, -0.6, 0.6), ('charge', 0.25, 0.30, 0.45, 1.0), ('boost', 0.38, 0.40, -0.5, 0.5),
           ('charge', 0.78, 0.84, -1.0, -0.45), ('slick', 0.86, 0.88, -1.0, 1.0), ('boost', 0.93, 0.95, -0.6, 0.6)],
    gaps=[], tunnels=[], jumps=[(0.235, 4, 0, 70)],
    flights=[(0.46, 0.62, 360)],
    rings=[(0.49, 0.0, 60, 120, 'ring'), (0.53, -0.5, -80, 110, 'cring'), (0.57, 0.45, 40, 120, 'ring')],
    creatures=[('manta', 0.515, 0, 11.0, 2.0, 620, 2200)],
    slogans=['CORAL CROWN', 'GLIDE THE SHELF', 'DUCK THE MANTA']))

# 3. The Wreck: a figure-8 round a sunken liner. One pass through the middle runs inside the hull (a tube), the other
# crosses over it; a jump off the bow has a serpent coiling past.
wr = []
a = 5500
n = 56
for k in range(n):
    t = 2 * math.pi * k / n + math.pi + 0.9
    den = 1 + math.sin(t) ** 2
    x = a * math.cos(t) / den; y = a * math.sin(t) * math.cos(t) / den * 1.5
    if x < 0: x *= 0.82; y *= 0.82
    tt = (t - math.pi / 2 + math.pi) % (2 * math.pi) - math.pi
    u = abs(tt)
    z = 880.0 if u < 0.25 else (880 * (0.5 - 0.5 * math.cos(math.pi * (1 - (u - 0.25) / 0.45))) if u < 0.7 else 0.0)
    wr.append((x, y, z, 300))
TRACKS.append(dict(id='wreck', title='THE WRECK', laps=3, theme='amber', bank=18, scenery='ruins',
    pts=wr,
    feats=[('boost', 0.035, 0.055, -0.6, 0.6), ('charge', 0.22, 0.28, 0.4, 1.0), ('boost', 0.36, 0.38, -0.5, 0.5),
           ('slick', 0.44, 0.46, -1.0, 1.0), ('charge', 0.64, 0.70, -1.0, -0.4), ('boost', 0.92, 0.94, -0.6, 0.6)],
    gaps=[], tunnels=[], crossing=True, undertube=True, jumps=[(0.615, 6, 13, 110)],
    creatures=[('serpent', 0.628, 160, 8.0, 3.0, 820, 2100)],
    slogans=['THE WRECK', 'THROUGH THE HULL', 'ABANDON SHIP']))

# 4. Vent Field: a rounded hexagon rolling over hot vents. Two jumps over vent chasms on the long straights; a whale
# lumbers across the second one.
hexa = rounded([(5200 * math.cos(math.radians(a_)), 4800 * math.sin(math.radians(a_))) for a_ in range(-90, 270, 60)], 1500, 7)
def vf_z(x, y):
    return 260 + 200 * math.sin(math.atan2(y, x) * 3 + 0.4)
TRACKS.append(dict(id='vents', title='VENT FIELD', laps=3, theme='seagreen', bank=18, scenery='coral',
    pts=[(x, y, vf_z(x, y), 300) for x, y in hexa],
    feats=[('boost', 0.03, 0.05, -0.6, 0.6), ('charge', 0.12, 0.18, 0.4, 1.0), ('slick', 0.40, 0.42, -1.0, 1.0),
           ('charge', 0.52, 0.58, -1.0, -0.4), ('boost', 0.66, 0.68, -0.5, 0.5), ('boost', 0.90, 0.92, -0.6, 0.6)],
    gaps=[], tunnels=[(0.44, 0.50)], jumps=[(JV1, 6, 12, 110), (JV2, 6, 13, 115)],
    creatures=[('whale', CV2, 190, 13.0, 4.0, 520, 2600)],
    slogans=['VENT FIELD', 'HOT WATER', 'WHALE CROSSING']))

# 5. Abyss Drop: up a spiral round a seamount, then the road ends at the summit and you glide down into the trench,
# past a whale and through a serpent's path, landing on the trench floor and racing home.
ad = [(-3800, -5000, 0), (1200, -5000, 0)]
ad += arc(1200, -3800, 1200, -math.pi / 2, 0, 5)[1:]
C, R, TURN, RISE = (1700, -800), 1900, 2.5 * math.pi, 1500
for k in range(0, 31):
    a_ = TURN * k / 30
    ad.append((C[0] + R * math.cos(a_), C[1] + R * math.sin(a_), RISE * a_ / TURN))
ad += [(-1100, 1600, 1400), (-2700, 2500, 1200), (-4300, 2500, 980), (-5400, 1500, 760), (-5500, 100, 560),
       (-5200, -1400, 360), (-4800, -2700, 200), (-4500, -3800, 80), (-4300, -4600, 10)]
TRACKS.append(dict(id='abyss', title='ABYSS DROP', laps=2, theme='violet', bank=20, scenery='rocks',
    pts=[(x, y, z, 300) for x, y, z in ad],
    feats=[('boost', 0.02, 0.04, -0.6, 0.6), ('charge', 0.10, 0.14, 0.4, 1.0), ('boost', 0.25, 0.265, -0.5, 0.5),
           ('charge', 0.40, 0.44, -1.0, -0.4), ('boost', 0.53, 0.545, -0.5, 0.5), ('boost', 0.965, 0.98, -0.6, 0.6)],
    gaps=[], tunnels=[], crossing=True,
    flights=[(0.66, 0.935, 380)],
    rings=[(0.69, 0.0, 0, 130, 'ring'), (0.74, -0.5, -110, 110, 'cring'), (0.80, 0.4, 100, 120, 'ring'),
           (0.86, -0.3, -80, 120, 'ring'), (0.90, 0.0, 60, 120, 'ring')],
    creatures=[('whale', 0.77, 0, 12.0, 0.0, 540, 2400), ('serpent', 0.885, 40, 9.5, 5.0, 800, 2100)],
    slogans=['ABYSS DROP', 'INTO THE TRENCH', 'SOMETHING BIG']))

# 6. Lantern Deep: a dark kidney loop lit by glowing lanterns. A rail-less ledge, then a short glide over a sinkhole
# with a manta sweeping through it.
ld = []
NL = 48
for i in range(NL):
    t = 2 * math.pi * i / NL
    rr = 4300 + 800 * math.cos(2 * t) - 500 * math.cos(3 * t)
    f = i / NL
    z = 0
    if 0.58 <= f <= 0.72: z = 460 * math.sin((f - 0.58) / 0.14 * math.pi)
    ld.append((rr * math.cos(t) * 1.05, rr * math.sin(t) * 0.9, z, 300 if not (0.24 < f < 0.38) else 240))
TRACKS.append(dict(id='lantern', title='LANTERN DEEP', laps=3, theme='cyan', bank=14, scenery='rocks',
    pts=ld,
    feats=[('boost', 0.035, 0.055, -0.5, 0.5), ('charge', 0.12, 0.17, -1.0, -0.45), ('boost', 0.50, 0.52, -0.5, 0.5),
           ('charge', 0.80, 0.85, 0.45, 1.0), ('boost', 0.92, 0.94, -0.6, 0.6)],
    gaps=[(0.25, 0.37)], tunnels=[],
    flights=[(0.585, 0.715, 340)],
    rings=[(0.61, 0.0, 100, 120, 'ring'), (0.66, -0.5, -60, 110, 'cring'), (0.69, 0.4, 40, 120, 'ring')],
    creatures=[('manta', 0.65, 0, 10.0, 6.0, 640, 2100)],
    slogans=['LANTERN DEEP', 'NO RAILS', 'LIGHTS IN THE DARK']))

# ---------------------------------------------------------------- themes (any RGB): dark water, glowing life
def T(main, alt, accent, sky_mid):
    return dict(road=ABYSS, road2=main, line=WHITE, rail=main, post=alt, gate=main, sky=((40, 120, 150), sky_mid, ABYSS),
                glow=main, win=(main, accent, WHITE), planet=(accent, 'surface'), floor=main, accent=accent)
THEMES = {
    'teal':     T(TEAL, SEAGREEN, AMBER, (6, 40, 60)),
    'coral':    T(CORAL, PINK, CYAN, (10, 34, 64)),
    'amber':    T(AMBER, CORAL, TEAL, (8, 28, 44)),
    'seagreen': T(SEAGREEN, TEAL, PINK, (4, 36, 40)),
    'violet':   T(VIOLET, PINK, CYAN, (10, 14, 50)),
    'cyan':     T(CYAN, VIOLET, AMBER, (4, 22, 52)),
}
