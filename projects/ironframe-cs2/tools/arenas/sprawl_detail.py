"""IRONFRAME Sprawl: the detail pass (skink52, 10 Nov 2026: "it lacks any real detail beyond the colours of lights in the buildings.
far more small scale props etc can be applied to it ... improve areas such as the central square"). References and what they
showed: docs/SPRAWL_NOTES.md "Detail pass"; the images are in C:\\source1\\ironframe_work\\refs\\sprawl (never in git).

usage: python -I tools/arenas/sprawl_detail.py <map.vmap> <addon content dir> [--dry-run] [--stats out.json]
Run after sprawl_ops.py and before objectives.py / copies.py (build_sprawl.sh does). Vis group ifr_detail, replaced on every run.

Scale. A storey is 76.8 u (sprawl_ops.FACADE_UV) and human things are S = 0.6 of CS2's size (a car 140 u long and 42 u tall, a
person 43 u), so a 240-336 u mech stands 3-4 storeys = 13-15 m over them.

Gameplay contract (docs/ARENAS.md, DESIGN: mech movement sweeps the world):
  * every stock prop is prop_static with solid 0;
  * every detail mesh uses a d_* material carrying mapbuilder.nonsolid (sprawl_detail_mats.py): no collision for mechs or bullets;
  * the only solid additions: the plaza's rim steps (within 16 u of the old ground), the dais steps (in the water, not walkable
    before either) and the broadcast arch (four legs in the water at (+-700, +-700), everything else of it above z 860);
  * nothing here touches sprawl.py's SOLIDS / STRUCT, so arena.json's nav grid is unchanged.
Cost: one merged mesh per kind and 1024-u cell (not one per object); props are instances of ~40 stock models, the many-of-a-kind
ones (cars, cones, tables) picked from the low-polygon variants. prop_static has no fade distance key in CS2: distance cost is the
models' own LODs. The script prints mesh / face / prop / LOD0-triangle / light counts (--stats writes them).
"""
import json, math, os, random, sys
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
CREATE = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..', 'create'))
sys.path.insert(0, CREATE); sys.path.insert(0, HERE); sys.path.append(os.path.join(os.path.dirname(CREATE), 'tools'))
import primitives as P, meshedit as M, vmapgen, vmaplib, placer
import sprawl_detail_mats as DM
import sprawl_ops as SO

GROUP = 'ifr_detail'
S = 0.6
FL = SO.FLOOR_H
LINES = [-4800.0, -2400.0, 0.0, 2400.0, 4800.0]
ROAD, SW, AV = 560.0, 170.0, 450.0           # road width, sidewalk width, half an avenue (block edge)
RZ, SZ = 2.0, 12.0                           # road and sidewalk surface z
PLAZA = 1950.0
DECK = 760.0
HW_END, HW_FOOT, HW_PIERS = 3600.0, 5035.0, [-3000.0, -1800.0, -600.0, 600.0, 1800.0, 3000.0]      # set from the plan in main (sprawl.py HW_*)
KIT = json.load(open(os.path.join(HERE, 'sprawl_kit.json')))
BYMODEL = {v['model']: v for v in KIT.values()}
# car004b, van001a and concretebags are in pak01 without their materials (the map compile reports them missing): not used
# (props_vehicles/van_glass too: its car_glass.vmat is not in pak01, so no van)
CARS = [('nuke_sedan01_low', 50), ('dust_limo_lowpoly', 28), ('nuke_sedan02', 9), ('taxi_city', 6), ('cara_82hatchback', 7)]
ALSO = {'taxi_city': ['taxi_city_glass'], 'cara_82hatchback': ['cara_82hatchback_glass'], 'overpass_bus_station': ['overpass_bus_station_glass', 'overpass_bus_station_seat']}
TINTS = ['255 255 255', '215 215 220', '70 70 76', '150 34 30', '44 64 116', '214 204 176', '96 106 96', '30 30 34', '170 170 176']
LIVE_EVERY, LIVE_MAX = 3, 64                               # destructible cars: one in three of the one-piece cars, at most this many an arena
BAKED = ('plaza_solid',)                                  # mesh kinds that are lightmapped
SHADOWS = ('screen', 'tram', 'pier', 'gantry')            # unbaked kinds that still cast baked shadows
SMALL = (4200.0, 5200.0); TINY = (3000.0, 3800.0)         # fade start / end distances (u) for small and tiny kinds
FADE = dict(furn=SMALL, rail=SMALL, bollard=SMALL, signal=SMALL, pole=SMALL, lamp=SMALL, escape=SMALL, roof=SMALL, wall=SMALL, mark=SMALL,
            ac=TINY, pipe=TINY, stud=TINY, puddle=TINY, wire=TINY)
LIGHT = dict(sodium='255 160 80', white='215 232 255', warm='255 210 160', cyan='60 220 255', magenta='255 60 200', amber='255 170 40')


# ------------------------------------------------------------------------------------------------ shapes
def bx(lo, hi, mat, **faces):
    """box; faces: px / nx / py / ny / top / bottom = another material for that side"""
    lo2 = [min(a, b) for a, b in zip(lo, hi)]; hi2 = [max(a, b) for a, b in zip(lo, hi)]
    s = P.box(lo2, hi2, mat)
    if faces:
        def rule(i, n):
            k = ('px' if n[0] > 0.7 else 'nx' if n[0] < -0.7 else 'py' if n[1] > 0.7 else 'ny' if n[1] < -0.7 else 'top' if n[2] > 0.7 else 'bottom')
            return faces.get(k)
        s = P.materials(s, rule)
    return s


def cyl(x, y, r, z0, z1, mat, sides=6):
    return P.cylinder((x, y), r, z0, z1, sides, mat)


def tube(path, r, mat, sides=4):
    return P.sweep(path, P.circle(r, sides), mat=mat)


def bar(path, w, h, mat):
    return P.sweep(path, P.rect(w, h), mat=mat)


def sag(a, b, drop, n=7):
    return [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t - drop * 4 * t * (1 - t)) for t in [i / (n - 1) for i in range(n)]]


def xf(shape, x, y, z, yaw):
    return P.translate(P.rotate_z(shape, yaw) if yaw else shape, (x, y, z))


def fit_spec(shape, k):
    n = M.face_normal(shape, k)
    if abs(n[2]) > 0.7: return M.uv(fit=(1, 1))
    L = math.hypot(n[0], n[1]) or 1.0
    return M.uv(axis_u=(-n[1] / L, n[0] / L, 0.0), axis_v=(0.0, 0.0, -1.0), fit=(1, 1))


def top_spec(v, ru=1.0, rv=1.0):
    """a road marking: image up = -v (v = the direction the image's rows run), not mirrored seen from above"""
    return M.uv(axis_u=(-v[1], v[0], 0.0), axis_v=(v[0], v[1], 0.0), fit=(ru, rv))


class Out:
    def __init__(self, mats, plan):
        self.m = mats; self.plan = plan
        self.buckets = defaultdict(list); self.props = []; self.lights = []; self.fx = []
        self.live = []; self.ncar = 0
        self.PL = placer.Placer(cell=256.0, bounds=lambda model: (tuple(BYMODEL[model]['lo']), tuple(BYMODEL[model]['hi'])))
        self.n = Counter(); self.tris = Counter(); self.faces = Counter()

    # meshes ---------------------------------------------------------------------------------------
    def put(self, cat, parts, x=0.0, y=0.0, z=0.0, yaw=0.0):
        """parts: [(shape, uv)] with uv None | 'fit' | a uv spec; local coordinates when x / y / z / yaw are given"""
        moved = x or y or z or yaw
        for shape, uv in parts:
            if moved: shape = xf(shape, x, y, z, yaw)
            v0 = shape[0][0]
            self.buckets[(cat, int(v0[0] // 1024), int(v0[1] // 1024))].append((shape, uv)); self.faces[cat] += len(shape[1])
        self.n[cat] += 1

    def flush(self):
        faces = 0
        for key in sorted(self.buckets):
            verts, loops, fm, specs = [], [], [], {}
            for shape, uv in self.buckets[key]:
                v, f, m = shape; o = len(verts); fo = len(loops)
                verts += list(v); loops += [[i + o for i in loop] for loop in f]; fm += list(m)
                if uv is not None:
                    for k in range(len(f)): specs[fo + k] = fit_spec(shape, k) if uv == 'fit' else uv
            # Only the solid plaza pieces take lightmap space. Everything else is lit by the light probes (bakelighting off): with it on,
            # the 230 000 small faces of three arena copies made 687 428 lightmap charts and the bake stopped ("Too many charts").
            big = key[0] in BAKED
            node = M.write((verts, loops, fm), specs or None, group=GROUP, bake=big, shadows=big or key[0] in SHADOWS)
            if key[0] in FADE: node.attr('fademindist')[2] = FADE[key[0]][0]; node.attr('fademaxdist')[2] = FADE[key[0]][1]
            faces += len(loops)
        return len(self.buckets), faces

    # props ----------------------------------------------------------------------------------------
    def claim(self, x, y, hx, hy, yaw=0.0, z0=0.0, z1=100.0, check=True, name='mesh'):
        f = dict(c=(x, y), h=(hx, hy), a=math.radians(yaw), z=(z0, z1), model='detail/%s.vmdl' % name)
        if check and self.PL.hits(f): return False
        self.PL.add(f); return True

    def prop(self, key, x, y, z, yaw=0.0, scale=S, tint=None, check=True, pad=3.0, pitch=0.0, roll=0.0):
        k = KIT[key]
        f = self.PL.footprint(k['model'], x, y, z, yaw, (scale, scale, scale), pad)
        if check:
            if self.PL.hits(f): return False
            self.PL.add(f)
        for kk in [key] + ALSO.get(key, []):
            self.props.append((KIT[kk]['model'], (x, y, z), (pitch, yaw, roll), scale, tint if kk == key else None))
            self.n['prop:' + kk] += 1; self.tris[kk] += KIT[kk]['tris']
        return True

    def ground_prop(self, key, x, y, z, yaw=0.0, scale=S, **kw):
        return self.prop(key, x, y, z - KIT[key]['lo'][2] * scale, yaw, scale, **kw)

    def car(self, rnd, x, y, z, heading, key=None, **kw):
        key = key or rnd.choices([c for c, _ in CARS], [w for _, w in CARS])[0]
        k = KIT[key]; longy = (k['hi'][1] - k['lo'][1]) > (k['hi'][0] - k['lo'][0])
        ok = self.ground_prop(key, x, y, z, heading - (90.0 if longy else 0.0) + (180.0 if rnd.random() < 0.5 else 0.0), tint=rnd.choice(TINTS), **kw)
        # every LIVE_EVERY-th one-piece car is a destructible prop (core 88_props.js: shot, blown up or walked over; it explodes and
        # burns): a named prop_dynamic_override instead of a prop_static, and an entry of arena.cars. No random draw is spent on the
        # choice, so the rest of the pass comes out as before.
        if ok and key not in ALSO:
            self.ncar += 1
            if self.ncar % LIVE_EVERY == 0 and len(self.live) < LIVE_MAX:
                model, org, ang, scale, tint = self.props[-1]
                big = key in ('bus01_2', 'semi_trailer')
                r = 0.45 * max(k['hi'][0] - k['lo'][0], k['hi'][1] - k['lo'][1]) * scale
                self.live.append([round(org[0], 1), round(org[1], 1), round(org[2], 1), round(r, 1), 1 if big else 0, round(ang[1], 1), round(ang[0], 1), round(ang[2], 1), tint or '255 255 255'])
                self.props[-1] = (model, org, ang, scale, tint, True)
        return ok

    def light(self, x, y, z, lumens, rng, color):
        self.lights.append(((x, y, z), lumens, rng, color))

    def write_entities(self):
        for model, origin, angles, scale, tint, *live in self.props:
            if live:                                                     # a destructible car: the script recolours and tips it over (48_props.js)
                keys = dict(model=model, solid='0', targetname='ifr_car', rendercolor=tint or '255 255 255', disableshadows='1')
                e = P.entity('prop_dynamic_override', origin, angles, group=GROUP, strict=False, **keys)
                e.attr('scales')[2] = (scale, scale, scale)
                continue
            keys = dict(model=model, solid='0', bakelighting='0')       # probe-lit: no lightmap charts for 2 000 small props
            if tint: keys['rendercolor'] = tint
            e = P.entity('prop_static', origin, angles, group=GROUP, strict=False, **keys)
            e.attr('scales')[2] = (scale, scale, scale)
        for origin, lumens, rng, color in self.lights:               # baked only (directlight 1): no runtime cost
            P.entity('light_omni2', origin, (90, 0, 0), group=GROUP, strict=False, brightness_units='1', brightness_lumens=str(int(lumens)), brightness='1',
                     color=color, range='%.0f' % rng, directlight='1', castshadows='0', colormode='0', enabled='1', bouncescale='1.0', shape='0')
        for i, origin in enumerate(self.fx):
            P.entity('info_particle_system', origin, (-90, 0, 0), group=GROUP, strict=False, targetname='ifr_steam_%02d' % i,
                     effect_name='particles/maps/de_train/train_steam_leak.vpcf', start_active='1')


# ------------------------------------------------------------------------------------------------ street furniture (local: +x = front)
def lamp(m, glow='e_sodium', h=232.0, reach=44.0, banner=None):
    parts = [(cyl(0, 0, 5.0, 0, 14, m['metal_dark']), None), (tube([(0, 0, 14), (0, 0, h - 12), (reach * 0.25, 0, h), (reach, 0, h + 4)], 2.6, m['metal_grey'], 5), None),
             (bx((reach - 14, -6, h + 1), (reach + 14, 6, h + 6), m['metal_grey'], bottom=m[glow]), None)]
    if banner: parts.append((bx((-1, 4, h * 0.55), (1, 26, h * 0.55 + 48), m['metal_dark'], px=m[banner], nx=m[banner]), 'fit'))
    return parts


def utility_pole(m, rnd, h=250.0):
    parts = [(cyl(0, 0, 4.2, 0, h, m['conc_dark'], 6), None), (bx((-2, -24, h - 16), (2, 24, h - 12), m['metal_grey']), None), (bx((-2, -18, h - 38), (2, 18, h - 34), m['metal_grey']), None)]
    if rnd.random() < 0.6: parts.append((cyl(7.5, 0, 6.5, h - 78, h - 52, m['metal_grey'], 8), None))
    if rnd.random() < 0.5: parts.append((bx((4, -5, 44), (9, 5, 62), m['metal_grey'], px=m['yellow']), None))
    return parts


def vend_cluster(m, rnd):
    n = rnd.randint(2, 3); w = 25.0; parts = [(bx((-13, -n * w / 2 - 8, 0), (13, n * w / 2 + 8, 2), m['conc']), None)]
    for i in range(n):
        y0 = -n * w / 2 + i * w + 0.8
        parts.append((bx((-11, y0, 2), (9, y0 + w - 1.6, 46), m[rnd.choice(['white', 'red', 'blue', 'metal_grey'])], px=m['vend_%d' % rnd.randrange(4)]), 'fit'))
    parts.append((bx((-4, n * w / 2 + 1, 2), (5, n * w / 2 + 7, 20), m[rnd.choice(['red', 'blue', 'green'])]), None))
    return parts


def bench(m):
    return [(bx((-6, -22, 9), (6, 22, 11), m['wood']), None), (bx((-7, -22, 11), (-5, 22, 21), m['wood']), None),
            (bx((-5, -20, 0), (5, -18, 9), m['metal_dark']), None), (bx((-5, 18, 0), (5, 20, 9), m['metal_dark']), None)]


def planter(m, w=80.0, d=26.0, h=13.0):
    return [(bx((-d / 2, -w / 2, 0), (d / 2, w / 2, h), m['stone']), None), (bx((-d / 2 + 2.5, -w / 2 + 2.5, h), (d / 2 - 2.5, w / 2 - 2.5, h + 13), m['hedge']), None)]


def kiosk(m, rnd):
    k = rnd.randrange(6)
    return [(bx((-22, -35, 0), (22, 35, 56), m['metal_dark'], px=m['kiosk_%d' % k]), 'fit'), (bx((-27, -40, 56), (34, 40, 59), m['metal_grey']), None),
            (P.extrude([(0, 0), (20, -9), (20, -11), (0, -2)], 70, 'xz', (22, -35, 56), m[rnd.choice(['red', 'green', 'blue', 'tarp', 'orange'])]), None),
            (bx((-20, -30, 59), (-16, 30, 73), m['metal_dark'], px=m['led_amber']), 'fit'), (bx((23, -30, 50), (25, 30, 52), m['e_warm']), None)]


def phone_booth(m):
    return [(bx((-10, -10, 0), (10, 10, 50), m['glass']), None), (bx((-11, -11, 50), (11, 11, 55), m['metal_grey'], bottom=m['e_white']), None),
            (bx((-10.5, -10.5, 0), (-9, 10.5, 50), m['metal_grey']), None), (bx((-4, -3, 18), (-9, 3, 34), m['metal_dark'], px=m['green']), None)]


def cabinet(m, rnd):
    w = rnd.choice([18, 26, 34]); h = rnd.choice([26, 34])
    return [(bx((-5, -w / 2, 0), (5, w / 2, h), m['metal_grey'], px=m[rnd.choice(['metal_grey', 'beige', 'metal_galv'])]), None), (bx((5, -3, h * 0.55), (5.4, 3, h * 0.55 + 5), m['yellow']), None)]


def aboard(m, rnd):
    p = m['poster_%d' % rnd.randrange(8)]
    return [(bx((-1.2, -8, 0), (1.2, 8, 27), m['metal_dark'], px=p, nx=p), 'fit')]


def newsboxes(m, rnd):
    parts = []
    for i in range(rnd.randint(2, 4)):
        parts += [(bx((-4.5, -20 + i * 11, 5), (4.5, -10.5 + i * 11, 26), m[rnd.choice(['red', 'blue', 'yellow', 'green', 'white'])], px=m['glass']), None),
                  (bx((-1, -16.5 + i * 11, 0), (1, -14 + i * 11, 5), m['metal_dark']), None)]
    return parts


def bin_(m, rnd):
    return [(cyl(0, 0, 5.5, 0, 19, m[rnd.choice(['metal_dark', 'green', 'metal_grey'])], 6), None), (cyl(0, 0, 6.2, 19, 21, m['metal_dark'], 6), None)]


def hydrant(m):
    return [(cyl(0, 0, 3.2, 0, 13, m['red'], 6), None), (bx((-4.5, -1.5, 8), (4.5, 1.5, 11), m['red']), None), (cyl(0, 0, 2.2, 13, 16, m['metal_galv'], 6), None)]


def bollard(m, cap='e_amber', h=24.0):
    return [(P.materials(cyl(0, 0, 3.2, 0, h, m['metal_grey'], 5), lambda i, n: m[cap] if n[2] > 0.7 else None), None)]


def signal_mast(m, rnd, reach=150.0):
    """a Japanese-style mast: the arm reaches along local +x over the road, two horizontal 3-lamp heads face local -y (the stop line)"""
    go = rnd.random() < 0.5
    parts = [(cyl(0, 0, 4.0, 0, 150, m['metal_grey'], 6), None), (tube([(0, 0, 138), (reach, 0, 146)], 2.4, m['metal_grey'], 4), None),
             (bx((-5, -9, 52), (5, -5, 70), m['metal_dark'], ny=m['e_red' if go else 'e_green']), None), (bx((-5, -5, 30), (5, -9, 36), m['yellow']), None)]
    for hx in (reach * 0.5, reach - 14):
        parts.append((bx((hx - 15, -5, 136), (hx + 15, 1, 148), m['metal_dark']), None))
        for i, c in enumerate(('green', 'amber', 'red')):
            on = (c == 'green') == go and c != 'amber'
            parts.append((bx((hx - 13 + i * 9.5, -6.2, 138), (hx - 6 + i * 9.5, -5, 146), m['e_' + c] if on else m['rubber']), None))
    return parts


def ac_box(m, w=22.0, d=11.0, h=15.0):
    return [(bx((0, -w / 2, 0), (d, w / 2, h), m['beige'], px=m['ac']), 'fit')]


def awning(m, rnd, w=58.0):
    return [(P.extrude([(0, 0), (24, -9), (24, -11), (0, -2)], w, 'xz', (0, -w / 2, 0), m[rnd.choice(['red', 'green', 'blue', 'tarp', 'orange', 'white', 'yellow'])]), None)]


def tram(m):
    parts = []
    for c0 in (0.0, 196.0):
        parts += [(bx((c0, -27, 9), (c0 + 190, 27, 78), m['yellow'], py=m['tram'], ny=m['tram']), 'fit'), (bx((c0 + 6, -24, 78), (c0 + 184, 24, 82), m['metal_grey']), None),
                  (bx((c0 + 60, -14, 82), (c0 + 120, 14, 89), m['metal_galv']), None), (bx((c0 + 14, -25, 3), (c0 + 176, 25, 9), m['rubber']), None)]
    parts += [(bx((190, -20, 16), (196, 20, 74), m['rubber']), None), (bx((386, -22, 40), (387.5, 22, 70), m['glass']), None), (bx((-1.5, -22, 40), (0, 22, 70), m['glass']), None)]
    for x in (387.6, -1.6):
        for y in (-20, 14): parts.append((bx((x - 0.8, y, 16), (x + 0.8, y + 6, 22), m['e_warm']), None))
    parts += [(tube([(40, 0, 89), (70, 0, 128), (100, 0, 89)], 1.2, m['metal_dark'], 3), None), (bx((62, -14, 128), (78, 14, 130), m['metal_dark']), None)]
    return parts


def tram_stop(m, rnd):
    """local +x = toward the track; a 220-u canopy on four columns, glass back, bench, a lit board"""
    parts = [(bx((-22, -110, 62), (24, 110, 65), m['white'], bottom=m['e_white']), None), (bx((-21, -100, 0), (-19.5, 100, 52), m['glass']), None)]
    for y in (-104, -36, 36, 104): parts.append((cyl(-18, y, 2.2, 0, 62, m['metal_grey'], 5), None))
    parts += [(s, u) for s, u in bench(m)]
    parts += [(bx((-14, 112, 0), (-6, 136, 64), m['metal_dark'], px=m['poster_%d' % rnd.randrange(8)], nx=m['poster_%d' % rnd.randrange(8)]), 'fit'),
              (bx((-20, -40, 66), (-16, 40, 78), m['metal_dark'], px=m['led_amber']), 'fit')]
    return parts


# ------------------------------------------------------------------------------------------------ layout
class Seg:
    """one avenue stretch between two crossings; s runs along it (0 .. 1500), t across (+ = left of the direction of s)"""
    def __init__(self, axis, c, s0, s1):
        self.axis, self.c, self.s0, self.s1 = axis, c, s0, s1; self.len = s1 - s0
        self.yaw = 0.0 if axis == 'x' else 90.0
        self.dir = (1.0, 0.0) if axis == 'x' else (0.0, 1.0)
        self.left = (0.0, 1.0) if axis == 'x' else (-1.0, 0.0)
        mid = (s0 + s1) / 2
        self.hw = (axis == 'x' and c == 2400.0) or (axis == 'y' and c == -2400.0)
        self.plaza = 0
        if abs(c) == 2400.0 and abs(mid) < 2400.0:
            self.plaza = (-1 if c > 0 else 1) if axis == 'x' else (1 if c > 0 else -1)

    def w(self, s, t):
        return (self.s0 + s, self.c + t) if self.axis == 'x' else (self.c - t, self.s0 + s)

    def usable(self, s):
        """False under a highway ramp"""
        return not (self.hw and abs(self.s0 + s) > HW_END - 60.0)

    def face(self, side):
        """yaw of something on the `side` sidewalk looking at the road"""
        return math.degrees(math.atan2(-side * self.left[1], -side * self.left[0]))


def segments():
    out = []
    for axis in 'xy':
        for c in LINES:
            for a, b in zip(LINES, LINES[1:]):
                mid = (a + b) / 2; px, py = (mid, c) if axis == 'x' else (c, mid)
                if abs(px) < PLAZA and abs(py) < PLAZA: continue
                out.append(Seg(axis, c, a + AV, b - AV))
    return out


def mark(o, seg, s0, s1, t0, t1, kind, ru=1.0, rv=1.0, along=1.0, z=RZ, cat='mark'):
    a = seg.w(s0, t0); b = seg.w(s1, t1)
    v = (seg.dir[0] * along, seg.dir[1] * along)
    o.put(cat, [(bx((a[0], a[1], z + 0.05), (b[0], b[1], z + 0.9), o.m['mk_' + kind]), top_spec(v, ru, rv))])


def static_obstacles(o):
    plan = o.plan
    for t in plan['towers']:
        x0, y0, z0, x1, y1, top = t['box']; pad = 78.0 if z0 <= 210 else 4.0
        o.claim((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 + pad, (y1 - y0) / 2 + pad, 0, z0 - 30, top + 400, check=False, name='tower')
    for cx, cy, yaw in plan['containers']: o.claim(cx, cy, 360, 360, 0, 0, 360, check=False, name='container')
    for ax, at in plan['highways']:
        for q in HW_PIERS:
            x, y = (q, at) if ax == 'x' else (at, q)
            o.claim(x, y, 250, 135, 0 if ax == 'x' else 90, 0, DECK - 60, check=False, name='pier')
        for e in (-1, 1):                                               # the ramps
            mid = e * (HW_END + HW_FOOT) / 2
            x, y = (mid, at) if ax == 'x' else (at, mid)
            o.claim(x, y, (HW_FOOT - HW_END) / 2 + 40, 400, 0 if ax == 'x' else 90, 0, DECK, check=False, name='ramp')
    for x, y in plan['lamps']: o.claim(x + 365, y + 365, 26, 26, 0, 0, 600, check=False, name='mast')
    for x in (-3600, 3600): o.claim(x, 0, 300, 300, 0, 0, 500, check=False, name='flag')


# ------------------------------------------------------------------------------------------------ avenues
def dress_segment(o, seg, rnd, idx):
    m = o.m; L = seg.len
    ok = [s for s in range(0, int(L) + 1, 10) if seg.usable(s)]
    if not ok: return
    u0, u1 = ok[0], ok[-1]                                              # the stretch not under a ramp
    ends = [(u0 == 0), (u1 >= L - 1)]
    # --- paint
    a, b = u0 + (100 if ends[0] else 0), u1 - (100 if ends[1] else 0)
    if b - a > 200:
        if not seg.hw:
            for t in (-8, 3): mark(o, seg, a, b, t, t + 5, 'yellow', 1, (b - a) / 256)
        for t in (-186, -93, 93, 186): mark(o, seg, a + 10, b - 10, t - 2.5, t + 2.5, 'dash', 1, (b - a - 20) / 150)
        for t in (-277, 272): mark(o, seg, a, b, t, t + 5, 'solid', 1, (b - a) / 256)
    if ends[0]:
        mark(o, seg, 20, 76, -270, 270, 'zebra', 540 / 96, 1); mark(o, seg, 86, 96, -270, -10, 'stop')
        for t, kind in ((-46, 'arrow'), (-140, 'arrow'), (-232, 'turn')): mark(o, seg, 130, 215, t - 17, t + 17, kind, along=1.0)
    if ends[1]:
        mark(o, seg, L - 76, L - 20, -270, 270, 'zebra', 540 / 96, 1); mark(o, seg, L - 96, L - 86, 10, 270, 'stop')
        for t, kind in ((46, 'arrow'), (140, 'arrow'), (232, 'turn')): mark(o, seg, L - 215, L - 130, t - 17, t + 17, kind, along=-1.0)
    for k in range(2):                                                  # manholes (one in four steams), puddles
        s = rnd.uniform(u0 + 150, u1 - 150); t = rnd.choice([-140, -46, 46, 140]) + rnd.uniform(-12, 12)
        if b - a > 200:
            mark(o, seg, s - 10, s + 10, t - 10, t + 10, 'manhole', z=RZ + 0.25)
            if rnd.random() < 0.22: x, y = seg.w(s, t); o.fx.append((x, y, RZ + 2))
    for k in range(3):
        s = rnd.uniform(u0 + 120, u1 - 120); t = rnd.uniform(-240, 240); hs, ht = rnd.uniform(50, 130), rnd.uniform(35, 80)
        p0 = seg.w(s - hs, t - ht); p1 = seg.w(s + hs, t + ht)
        pz = RZ + 1.0 + 0.12 * k
        o.put('puddle', [(bx((p0[0], p0[1], pz), (p1[0], p1[1], pz + 0.4), m['puddle_%d' % rnd.randrange(3)]), M.uv(fit=(1, 1)))])
    # --- vehicles: parked along the kerbs, a few left in the lanes, a bus or a road block now and then
    for side in (-1, 1):
        if seg.plaza == side: continue
        for s in range(200, int(L) - 190, 168):
            if not seg.usable(s) or rnd.random() > 0.27: continue
            x, y = seg.w(s + rnd.uniform(-12, 12), side * (249 + rnd.uniform(-3, 3)))
            o.car(rnd, x, y, RZ, seg.yaw + rnd.uniform(-3, 3))
    for k in range(rnd.choice([0, 1, 1, 2])):
        s = rnd.uniform(u0 + 220, u1 - 220); t = rnd.uniform(-170, 170)
        x, y = seg.w(s, t); o.car(rnd, x, y, RZ, seg.yaw + rnd.uniform(-40, 40), pad=14)
    if idx % 5 == 2 and b - a > 600:
        s = rnd.uniform(a + 260, b - 260); side = seg.plaza and -seg.plaza or rnd.choice([-1, 1])
        x, y = seg.w(s, side * 232)
        o.car(rnd, x, y, RZ, seg.yaw, key='bus01_2', pad=10)
    if idx % 6 == 4 and b - a > 600:                                    # a road block across one carriageway
        s = rnd.uniform(a + 300, b - 300); side = rnd.choice([-1, 1])
        for i in range(3):
            x, y = seg.w(s + rnd.uniform(-6, 6), side * (55 + i * 84)); o.ground_prop('nuke_concrete_barrier', x, y, RZ, seg.yaw + rnd.uniform(-6, 6))
        for i in range(5):
            x, y = seg.w(s - 46 - i * 5, side * (20 + i * 62)); o.ground_prop('traffic_cone', x, y, RZ, rnd.uniform(0, 360))
        x, y = seg.w(s - 30, side * 150)
        o.put('furn', [(bx((-1.5, -34, 22), (1.5, 34, 40), m['metal_dark'], px=m['led_red'], nx=m['led_red']), 'fit'), (bx((-9, -28, 0), (9, -24, 22), m['orange']), None),
                       (bx((-9, 24, 0), (9, 28, 22), m['orange']), None)], x, y, RZ, seg.yaw + 180)
    # --- kerb side: guard rail, lamps, utility poles and their wires
    for side in (-1, 1):
        if seg.plaza == side: continue
        t = side * 287.0
        for s0, s1 in ((112, 610), (800, L - 112)):
            s0, s1 = max(s0, u0), min(s1, u1)
            if s1 - s0 < 100: continue
            p0 = seg.w(s0, t); p1 = seg.w(s1, t)
            parts = [(bar([(p0[0], p0[1], SZ + z), (p1[0], p1[1], SZ + z)], 1.6, 2.2, m['white']), None) for z in (11, 19)]
            n = max(1, int((s1 - s0) // 124))
            for i in range(n + 1):
                x, y = seg.w(s0 + (s1 - s0) * i / n, t); parts.append((bx((x - 1.3, y - 1.3, SZ), (x + 1.3, y + 1.3, SZ + 21), m['white']), None))
            o.put('rail', parts)
        for s in ((200, 1000) if side > 0 else (600, 1400)):
            if not seg.usable(s): continue
            x, y = seg.w(s, side * 296)
            if not o.claim(x, y, 6, 6, 0, SZ, 240, name='lamp'): continue
            o.put('lamp', lamp(m, banner=('poster_%d' % rnd.randrange(8)) if rnd.random() < 0.4 else None), x, y, SZ, seg.face(side))
            lx, ly = seg.w(s, side * 250); o.light(lx, ly, 205, 7000, 560, LIGHT['sodium'])
    side = -1 if seg.plaza != -1 else 1
    if seg.plaza != side:
        poles = []
        for s in (150, 480, 810, 1140, 1400):
            if not seg.usable(s): continue
            x, y = seg.w(s, side * 438)
            if not o.claim(x, y, 6, 6, 0, SZ, 260, name='pole'): continue
            o.put('pole', utility_pole(m, rnd), x, y, SZ, seg.face(side)); poles.append((x, y))
        for (x0, y0), (x1, y1) in zip(poles, poles[1:]):
            for off, z in ((-20, 236), (20, 236), (0, 214)):
                dx, dy = seg.left[0] * off, seg.left[1] * off
                o.put('wire', [(tube(sag((x0 + dx, y0 + dy, SZ + z), (x1 + dx, y1 + dy, SZ + z), rnd.uniform(10, 22), 5), 0.9, m['rubber'], 3), None)])
        for (x0, y0) in poles[::2]:                                     # a span across the avenue to the far kerb
            x1, y1 = x0 + seg.left[0] * -side * 860, y0 + seg.left[1] * -side * 860
            o.put('wire', [(tube(sag((x0, y0, SZ + 232), (x1, y1, SZ + 232), rnd.uniform(18, 34), 7), 0.9, m['rubber'], 3), None)])
    # --- the back of the sidewalk: what a city leaves there
    for side in (-1, 1):
        if seg.plaza == side: continue
        face = seg.face(side)
        if idx % 3 == (0 if side > 0 else 1) and seg.usable(750):       # a bus stop
            x, y = seg.w(750, side * 404)
            if o.ground_prop('overpass_bus_station', x, y, SZ, face, pad=8):
                sx, sy = seg.w(880, side * 300); o.ground_prop('overpass_bus_station_sign', sx, sy, SZ, face)
                mark(o, seg, 700, 800, side * 215, side * 250, 'bus', along=side)
        s = 130.0
        while s < L - 130:
            s += rnd.uniform(60, 120)
            if not seg.usable(s) or s > L - 120: continue
            kind = rnd.choices(['vend', 'bench', 'kiosk', 'planter', 'mailbox', 'phone', 'dumpster', 'bags', 'cabinet', 'aboard', 'news', 'hydrant', 'cones', 'pallet', 'can', 'none'],
                               [13, 9, 3, 10, 3, 3, 2, 2, 7, 9, 4, 4, 2, 3, 7, 19])[0]
            tw = side * 436.0
            if kind == 'vend':
                x, y = seg.w(s, tw - side * 6)
                if o.claim(x, y, 14, 46, face, SZ, 60, name='vend'):
                    o.put('furn', vend_cluster(m, rnd), x, y, SZ, face)
                    if rnd.random() < 0.6: lx, ly = seg.w(s, tw - side * 50); o.light(lx, ly, SZ + 34, 2200, 230, LIGHT['white'])
            elif kind == 'bench':
                x, y = seg.w(s, tw - side * 4)
                if o.claim(x, y, 8, 24, face, SZ, 40, name='bench'): o.put('furn', bench(m), x, y, SZ, face)
            elif kind == 'kiosk':
                x, y = seg.w(s, tw - side * 22)
                if o.claim(x, y, 36, 42, face, SZ, 80, name='kiosk'):
                    o.put('furn', kiosk(m, rnd), x, y, SZ, face); lx, ly = seg.w(s, tw - side * 80); o.light(lx, ly, SZ + 40, 3200, 260, LIGHT['warm'])
            elif kind == 'planter':
                x, y = seg.w(s, side * 312)
                if o.claim(x, y, 14, 42, face, SZ, 40, name='planter'): o.put('furn', planter(m), x, y, SZ, face)
            elif kind == 'mailbox': x, y = seg.w(s, tw - side * 8); o.ground_prop('overpass_mailbox', x, y, SZ, face)
            elif kind == 'phone':
                x, y = seg.w(s, tw - side * 10)
                if o.claim(x, y, 12, 12, face, SZ, 60, name='phone'): o.put('furn', phone_booth(m), x, y, SZ, face)
            elif kind == 'dumpster':
                x, y = seg.w(s, tw - side * 14); o.ground_prop('italy_dumpster_1', x, y, SZ, face + rnd.uniform(-8, 8), tint=rnd.choice(['255 255 255', '120 150 120', '110 120 160']))
            elif kind == 'bags':
                for i in range(rnd.randint(1, 2)):
                    x, y = seg.w(s + rnd.uniform(-22, 22), tw - side * rnd.uniform(4, 26)); o.ground_prop('garbage_bag_1', x, y, SZ, rnd.uniform(0, 360), pad=0)
            elif kind == 'cabinet':
                x, y = seg.w(s, tw - side * 3)
                if o.claim(x, y, 6, 18, face, SZ, 40, name='cab'): o.put('furn', cabinet(m, rnd), x, y, SZ, face)
            elif kind == 'aboard':
                x, y = seg.w(s, tw - side * rnd.uniform(20, 60))
                if o.claim(x, y, 4, 9, face, SZ, 30, name='ab'): o.put('furn', aboard(m, rnd), x, y, SZ, face + 90 + rnd.uniform(-20, 20))
            elif kind == 'news':
                x, y = seg.w(s, side * 306)
                if o.claim(x, y, 6, 24, face, SZ, 30, name='news'): o.put('furn', newsboxes(m, rnd), x, y, SZ, face + 180)
            elif kind == 'hydrant':
                x, y = seg.w(s, side * 300)
                if o.claim(x, y, 5, 5, 0, SZ, 20, name='hyd'): o.put('furn', hydrant(m), x, y, SZ, face)
            elif kind == 'cones':
                for i in range(rnd.randint(2, 4)):
                    x, y = seg.w(s + i * rnd.uniform(14, 30), side * rnd.uniform(300, 420)); o.ground_prop('traffic_cone', x, y, SZ, rnd.uniform(0, 360))
            elif kind == 'pallet':
                x, y = seg.w(s, tw - side * 22)
                for i in range(rnd.randint(1, 3)): o.ground_prop('wood_pallet', x, y, SZ + i * 4.4, face + rnd.uniform(-12, 12), check=(i == 0))
            elif kind == 'can':
                x, y = seg.w(s, side * 304)
                if o.claim(x, y, 7, 7, 0, SZ, 30, name='bin'): o.put('furn', bin_(m, rnd), x, y, SZ)


def dress_junction(o, x, y, rnd, hw):
    m = o.m
    for i, (sx, sy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        cx, cy = x + sx * 294, y + sy * 294
        if abs(cx) < PLAZA + 180 and abs(cy) < PLAZA + 180: continue     # the plaza's own corners
        yaw = [180, 270, 0, 90][i]                                      # the arm reaches over the road it controls
        if o.claim(cx, cy, 6, 6, 0, SZ, 160, name='signal'): o.put('signal', signal_mast(m, rnd), cx, cy, SZ, yaw)
        for k in range(3):                                              # bollards round the corner
            a = math.radians([225, 315, 45, 135][i] + (k - 1) * 28)
            bx_, by_ = x + sx * 300 + 14 * math.cos(a), y + sy * 300 + 14 * math.sin(a)
            o.put('bollard', bollard(m), bx_ + sx * 6, by_ + sy * 6, SZ)
        kind = rnd.choice(['vend', 'planter', 'kiosk', 'none', 'cab'])
        px, py = x + sx * 400, y + sy * 400; face = math.degrees(math.atan2(-sy, -sx))
        if kind == 'vend' and o.claim(px, py, 46, 46, 0, SZ, 60, name='vend'): o.put('furn', vend_cluster(m, rnd), px, py, SZ, face)
        elif kind == 'kiosk' and o.claim(px, py, 46, 46, 0, SZ, 80, name='kiosk'): o.put('furn', kiosk(m, rnd), px, py, SZ, face); o.light(px - sx * 60, py - sy * 60, SZ + 40, 3200, 260, LIGHT['warm'])
        elif kind == 'planter' and o.claim(px, py, 42, 42, 0, SZ, 40, name='planter'): o.put('furn', planter(m, 60, 60), px, py, SZ, 0)
        elif kind == 'cab' and o.claim(px, py, 20, 20, 0, SZ, 40, name='cab'): o.put('furn', cabinet(m, rnd), px, py, SZ, face)
    if not hw and rnd.random() < 0.6:
        o.put('mark', [(bx((x - 150, y - 150, RZ + 0.05), (x + 150, y + 150, RZ + 0.9), m['mk_hatch']), top_spec((0.0, 1.0), 3, 3))])


# ------------------------------------------------------------------------------------------------ blocks and towers
def wall_run(o, rnd, p0, p1, normal, z0, z1, tile_rows):
    """dress one street wall (a block slab's side) from p0 to p1 (xy), facing `normal`: pilasters on the 256-u tile seams, awnings over
    shop bays, small blade lightboxes, AC units under the upper windows, drain pipes, a cornice and a roof rail"""
    m = o.m; ax = 0 if abs(p1[0] - p0[0]) > 1 else 1
    a, b = sorted((p0[ax], p1[ax])); fixed = p0[1 - ax]
    yaw = math.degrees(math.atan2(normal[1], normal[0]))
    pt = lambda u, out=0.0: ((u, fixed + normal[1] * out) if ax == 0 else (fixed + normal[0] * out, u))
    k = math.ceil((a + 20) / 256.0)
    while k * 256 < b - 20:
        x, y = pt(k * 256.0, 2.5); h = 5.0; w = 7.0
        lo = (x - (w if ax == 0 else h / 2), y - (h / 2 if ax == 0 else w), z0); hi = (x + (w if ax == 0 else h / 2), y + (h / 2 if ax == 0 else w), z1 - 4)
        o.put('wall', [(bx(lo, hi, m['conc_dark']), None)])
        if rnd.random() < 0.7:
            px, py = pt(k * 256.0 + 11, 4.5); o.put('wall', [(tube([(px, py, z0 + 2), (px, py, z1 + 6)], 2.2, m['metal_galv'], 4), None)])
        k += 1
    for row in range(tile_rows):
        zb = z0 + row * 256.0
        if zb + 80 > z1: break
        u = math.ceil((a + 12) / 64.0) * 64.0
        while u + 64 < b - 12:                                           # shop bays are 64 u wide on the tile
            r = rnd.random()
            if r < 0.3: x, y = pt(u + 32, 0.5); o.put('wall', awning(m, rnd), x, y, zb + 80, yaw)
            elif r < 0.5:
                x, y = pt(u + rnd.choice([2, 62]), 9); p = m['poster_%d' % rnd.randrange(8)]
                o.put('wall', [(bx((-7, -1.5, 0), (7, 1.5, 46), m['metal_dark'], py=p, ny=p), 'fit'), (bx((-9, -0.8, 40), (-7, 0.8, 42), m['metal_dark']), None)], x, y, zb + rnd.choice([84, 96, 110]), yaw)
            u += 64.0
        for zc in (zb + 131.0,):                                         # under the second-storey windows (their sill is at 148 on the tile)
            if zc + 16 > z1: continue
            u = math.ceil((a + 20) / 32.0) * 32.0 + 16.0
            while u < b - 20:
                if rnd.random() < 0.22: x, y = pt(u, 0.4); o.put('ac', ac_box(m), x, y, zc, yaw)
                u += 32.0
    # cornice and roof rail
    c0 = pt(a + 2, 0); c1 = pt(b - 2, 9)
    o.put('wall', [(bx((c0[0], c0[1], z1 - 6), (c1[0], c1[1], z1 + 4), m['conc_dark']), None)])
    r0 = pt(a + 6, -6); r1 = pt(b - 6, -6)
    parts = [(bar([(r0[0], r0[1], z1 + z), (r1[0], r1[1], z1 + z)], 1.4, 1.8, m['metal_grey']), None) for z in (12, 21)]
    n = int((b - a) // 90)
    for i in range(n + 1):
        x, y = pt(a + 6 + (b - a - 12) * i / n, -6); parts.append((bx((x - 1.2, y - 1.2, z1), (x + 1.2, y + 1.2, z1 + 22), m['metal_grey']), None))
    o.put('rail', parts)


def condensers(o, rnd, x, y, z, yaw, n):
    """a row of n roof condensers (fan on top), the row running along yaw + 90"""
    dx, dy = -math.sin(math.radians(yaw)) * 36, math.cos(math.radians(yaw)) * 36
    for i in range(n):
        o.put('roof', [(bx((-11, -15, 0), (11, 15, 24), o.m['beige'], top=o.m['ac'], px=o.m['metal_grey']), 'fit'), (bx((-9, -13, -3), (9, 13, 0), o.m['metal_dark']), None)],
              x + dx * i, y + dy * i, z + 3, yaw)


def aerial(o, rnd, x, y, z):
    m = o.m; h = rnd.uniform(70, 150); parts = [(tube([(x, y, z), (x, y, z + h)], 1.4, m['metal_grey'], 4), None)]
    for k in range(rnd.randint(2, 4)):
        zz = z + h * (0.5 + 0.12 * k); w = rnd.uniform(8, 20)
        parts.append((bx((x - w, y - 0.6, zz), (x + w, y + 0.6, zz + 1.2), m['metal_grey']), None) if k % 2 else (bx((x - 0.6, y - w, zz), (x + 0.6, y + w, zz + 1.2), m['metal_grey']), None))
    o.put('roof', parts)


def water_tank(o, x, y, z, r=34.0, h=46.0):
    m = o.m; parts = [(cyl(x, y, r, z + 22, z + 22 + h, m['metal_galv'], 12), None), (cyl(x, y, r * 0.55, z + 22 + h, z + 30 + h, m['metal_galv'], 12), None)]
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)): parts.append((bx((x + dx * r * 0.62 - 2, y + dy * r * 0.62 - 2, z), (x + dx * r * 0.62 + 2, y + dy * r * 0.62 + 2, z + 22), m['rust']), None))
    parts.append((tube([(x + r + 2, y, z), (x + r + 2, y, z + 22 + h - 6), (x + r - 4, y, z + 22 + h - 6)], 1.6, m['metal_dark'], 4), None))
    o.put('roof', parts)


def dress_block(o, blk, rnd):
    m = o.m; cx, cy = blk['centre']; kind = blk['kind']; h = 750.0
    towers = [t for t in o.plan['towers'] if abs((t['box'][0] + t['box'][3]) / 2 - cx) < h and abs((t['box'][1] + t['box'][4]) / 2 - cy) < h]
    if kind in ('tall', 'podium'):
        top = 200.0 if kind == 'tall' else 400.0
        for (p0, p1, nrm) in (((cx - h, cy - h), (cx + h, cy - h), (0, -1)), ((cx - h, cy + h), (cx + h, cy + h), (0, 1)),
                              ((cx - h, cy - h), (cx - h, cy + h), (-1, 0)), ((cx + h, cy - h), (cx + h, cy + h), (1, 0))):
            if kind == 'podium' and nrm[0] == (-1 if cx > 0 else 1): continue          # the ramp side
            wall_run(o, rnd, p0, p1, nrm, 0.0, top, 2 if kind == 'podium' else 1)
        if kind == 'tall':                                               # the slab roof round the towers: plant, tanks, skylights (all under 60 u)
            for k in range(26):
                x, y = cx + rnd.uniform(-h + 60, h - 60), cy + rnd.uniform(-h + 60, h - 60)
                what = rnd.choice(['cond', 'cond', 'sky', 'tank', 'vent', 'vent2', 'hedge', 'cond'])
                size = dict(cond=(60, 60), sky=(50, 34), tank=(40, 40), vent=(26, 26), vent2=(24, 50), hedge=(46, 16))[what]
                if what in ('vent', 'vent2'):
                    o.ground_prop('acvent03' if what == 'vent' else 'acvent04', x, y, top, rnd.choice([0, 90, 180, 270]), pad=6); continue
                if not o.claim(x, y, size[0], size[1], 0, top, top + 80, name='slab'): continue
                if what == 'cond': condensers(o, rnd, x - 36, y, top, 90, rnd.randint(2, 3))
                elif what == 'sky': o.put('roof', [(bx((x - 40, y - 26, top), (x + 40, y + 26, top + 9), m['metal_dark'], top=m['e_warm' if rnd.random() < 0.6 else 'e_white']), None)])
                elif what == 'tank': water_tank(o, x, y, top, 26, 30)
                else: o.put('roof', planter(m, 80, 22), x, y, top, 0)
    else:                                                               # a low block: a car park and yard clutter between the buildings
        x0, y0 = cx - h + 70, cy - h + 70
        for row in range(4):
            yy = y0 + 110 + row * 330
            placed = 0
            for i in range(20):
                xx = x0 + 30 + i * 66
                if xx > cx + h - 100: break
                f = o.PL.footprint(KIT['nuke_sedan01_low']['model'], xx, yy, RZ, 90, (S, S, S), 12)
                if o.PL.hits(f): continue
                o.put('mark', [(bx((xx - 33.5, yy - 80, 0.3), (xx - 30.5, yy + 80, 1.1), m['mk_solid']), top_spec((0.0, 1.0), 1, 0.6))])
                if rnd.random() < 0.4 and placed < 7: o.car(rnd, xx, yy + rnd.uniform(-8, 8), 0.5, 90 + rnd.uniform(-3, 3), pad=4); placed += 1
        for k in range(22):
            x, y = cx + rnd.uniform(-h + 40, h - 40), cy + rnd.uniform(-h + 40, h - 40)
            what = rnd.choice(['italy_dumpster_1', 'garbage_bag_1', 'wood_pallet', 'barrel_group_tintable_01', 'wood_pallet', 'traffic_cone', 'nuke_concrete_barrier', 'traffic_cone'])
            o.ground_prop(what, x, y, 0.5, rnd.uniform(0, 360), pad=6)


def fire_escape(o, x, y, z0, floors, yaw):
    """local: +x = out from the wall, runs along y; a landing per storey and a flight between"""
    m = o.m; parts = []; w = 56.0; d = 20.0
    for f in range(floors):
        z = f * FL
        parts += [(bx((0, -w / 2, z - 1.5), (d, w / 2, z), m['metal_dark']), None), (bar([(d, -w / 2, z + 18), (d, w / 2, z + 18)], 1.2, 1.6, m['metal_dark']), None),
                  (bar([(d, -w / 2, z + 9), (d, w / 2, z + 9)], 1.0, 1.2, m['metal_dark']), None)]
        for yy in (-w / 2, 0, w / 2): parts.append((bx((d - 0.8, yy - 0.8, z), (d + 0.8, yy + 0.8, z + 18), m['metal_dark']), None))
        if f < floors - 1:
            a, b = (-w / 2 + 6, w / 2 - 6) if f % 2 == 0 else (w / 2 - 6, -w / 2 + 6)
            parts.append((bar([(d * 0.45, a, z), (d * 0.45, b, z + FL - 1.5)], 9.0, 1.6, m['metal_grey']), None))
            parts.append((bar([(d * 0.45 + 5, a, z + 17), (d * 0.45 + 5, b, z + FL + 15)], 1.0, 1.4, m['metal_dark']), None))
    parts.append((bar([(d * 0.5, 0, -FL * 0.6), (d * 0.5, 0, -2)], 8.0, 1.4, m['metal_dark']), None))                  # the drop ladder
    o.put('escape', parts, x, y, z0, yaw)


def dress_tower(o, t, rnd, ti):
    m = o.m; x0, y0, z0, x1, y1, top = t['box']; zs = t['_zs']; tl = t['_top_line']
    faces = [((x0, y0), (x1, y0), (0, -1)), ((x0, y1), (x1, y1), (0, 1)), ((x0, y0), (x0, y1), (-1, 0)), ((x1, y0), (x1, y1), (1, 0))]
    f0 = math.ceil((zs + 20) / FL)                                       # first storey line above the street band
    nfl = int((tl - 40) // FL) - f0
    # AC units under the windows of the lower storeys (bays and storeys are FL wide on the facade tile, anchored at the world origin)
    for (p0, p1, nrm) in rnd.sample(faces, 3):
        ax = 0 if nrm[0] == 0 else 1; a, b = sorted((p0[ax], p1[ax])); yaw = math.degrees(math.atan2(nrm[1], nrm[0]))
        for f in range(f0, f0 + min(7, nfl)):
            u = math.ceil((a + 30) / FL) * FL - FL / 2
            while u < b - 30:
                if rnd.random() < 0.2:
                    x, y = (u, p0[1] + nrm[1] * 0.4) if ax == 0 else (p0[0] + nrm[0] * 0.4, u)
                    o.put('ac', ac_box(m), x, y, f * FL - 9.5, yaw)
                u += FL
    for (cx, cy, sx, sy) in ((x0, y0, -1, -1), (x1, y0, 1, -1), (x0, y1, -1, 1), (x1, y1, 1, 1)):       # down pipes by the corner pilasters
        if rnd.random() < 0.75:
            px, py = cx + sx * 4 + (-sx * 44), cy + sy * 4.5
            o.put('pipe', [(tube([(px, py, zs + 6), (px, py, tl - 30)], 3.0, m['metal_galv'], 4), None)])
    if nfl >= 6 and rnd.random() < 0.6:                                  # a fire escape up 5-9 storeys
        p0, p1, nrm = rnd.choice(faces); ax = 0 if nrm[0] == 0 else 1; a, b = sorted((p0[ax], p1[ax]))
        u = rnd.uniform(a + 120, b - 120)
        x, y = (u, p0[1] + nrm[1] * 0.5) if ax == 0 else (p0[0] + nrm[0] * 0.5, u)
        fire_escape(o, x, y, f0 * FL + 9.5, min(nfl - 1, rnd.randint(5, 9)), math.degrees(math.atan2(nrm[1], nrm[0])))
    if t['lit'] and nfl >= 8:                                            # a tall lightbox banner near a corner
        for k in range(rnd.randint(1, 2)):
            p0, p1, nrm = rnd.choice(faces); ax = 0 if nrm[0] == 0 else 1; a, b = sorted((p0[ax], p1[ax]))
            u = rnd.choice([a + 110, b - 110]); zb = (f0 + rnd.randint(1, 2)) * FL; hh = min(300.0, (nfl - 3) * FL); p = rnd.randrange(8)
            x, y = (u, p0[1] + nrm[1] * 5) if ax == 0 else (p0[0] + nrm[0] * 5, u)
            o.put('screen', [(bx((-4, -60, 0), (4, 60, hh), m['metal_dark'], px=m['poster_%d' % p]), 'fit')], x, y, zb, math.degrees(math.atan2(nrm[1], nrm[0])))
            o.light(x + nrm[0] * 150, y + nrm[1] * 150, zb + hh / 2, 16000, 620, '%d %d %d' % DM.PAL[(p * 3 + 1) % len(DM.PAL)][0])
    roof = t.get('_roof')
    if not roof: return
    rx0, ry0, rx1, ry1 = roof; rz = top + 14
    ix0, iy0, ix1, iy1 = rx0 + 100, ry0 + 100, rx1 - 100, ry1 - 100
    if ix1 - ix0 > 160 and iy1 - iy0 > 160:
        used = []
        if t.get('roof_box'): used.append((t['roof_box'][0] + 120, t['roof_box'][1] + 100, 170))
        def spot(r):
            for _ in range(20):
                x, y = rnd.uniform(ix0 + r, ix1 - r), rnd.uniform(iy0 + r, iy1 - r)
                if all(math.hypot(x - a, y - b) > r + c + 8 for a, b, c in used): used.append((x, y, r)); return x, y
            return None
        if ix1 - ix0 > 560 and iy1 - iy0 > 560 and not t.get('walk_roof') and top - z0 < 1900:
            p = spot(150)
            if p: o.put('mark', [(bx((p[0] - 150, p[1] - 150, rz + 0.05), (p[0] + 150, p[1] + 150, rz + 0.9), m['mk_helipad']), top_spec((0.0, 1.0)))]); o.n['helipads'] += 1
        if rnd.random() < 0.6:
            p = spot(40)
            if p: water_tank(o, p[0], p[1], rz)
        for k in range(rnd.randint(1, 3)):
            p = spot(70)
            if p: condensers(o, rnd, p[0], p[1] - 50, rz, 0, rnd.randint(2, 4))
        for k in range(rnd.randint(1, 3)):
            p = spot(30)
            if p: o.ground_prop(rnd.choice(['acvent03', 'acvent04', 'acunit2']), p[0], p[1], rz, rnd.choice([0, 90, 180, 270]), check=False)
        for k in range(rnd.randint(1, 3)):
            p = spot(12)
            if p: aerial(o, rnd, p[0], p[1], rz)
    if not t.get('walk_roof') and rnd.random() < 0.6 and top < 2700:      # a billboard on a steel frame over the parapet
        rfaces = [((rx0 + rx1) / 2, ry0, (0, -1), rx1 - rx0), ((rx0 + rx1) / 2, ry1, (0, 1), rx1 - rx0), (rx0, (ry0 + ry1) / 2, (-1, 0), ry1 - ry0), (rx1, (ry0 + ry1) / 2, (1, 0), ry1 - ry0)]
        mx, my, nrm, wf = min(rfaces, key=lambda f: abs(f[0]) + abs(f[1])) if rnd.random() < 0.65 else rnd.choice(rfaces)
        bw = min(400.0, wf * 0.6); bh = bw * 0.5; zb = top + 228.0
        parts = [(bx((-5, -bw / 2, zb), (3, bw / 2, zb + bh), m['metal_dark'], px=m['billboard_%d' % rnd.randrange(4)]), 'fit')]
        for yy in (-bw * 0.36, 0, bw * 0.36):
            parts += [(bx((-11, yy - 2.5, top + 196), (-6, yy + 2.5, zb + bh), m['rust']), None), (bar([(-9, yy, zb + bh * 0.8), (-74, yy, top + 20)], 3, 3, m['rust']), None)]
        for yy in (-bw * 0.3, bw * 0.3):
            parts += [(bar([(3, yy, zb + bh), (26, yy, zb + bh + 10)], 1.6, 1.6, m['metal_dark']), None), (bx((22, yy - 5, zb + bh + 7), (30, yy + 5, zb + bh + 11), m['metal_dark'], bottom=m['e_white']), None)]
        o.put('screen', parts, mx - nrm[0] * 40, my - nrm[1] * 40, 0, math.degrees(math.atan2(nrm[1], nrm[0])))
        o.n['billboards'] += 1


def cranes(o, rnd):
    ruins = [t for t in o.plan['towers'] if t.get('_ruin')]
    for t in ruins[:2]:
        x0, y0, z0, x1, y1, top = t['box']
        sx = -1 if (x0 + x1) / 2 > 0 else 1; sy = -1 if (y0 + y1) / 2 > 0 else 1
        x, y = ((x1 + 110) if sx > 0 else (x0 - 110)), ((y1 + 110) if sy > 0 else (y0 - 110))
        yaw = rnd.uniform(0, 360)
        for k in ('constructioncrane01', 'constructioncrane01_top'): o.prop(k, x, y, z0, yaw, 1.0, check=False)
        o.n['cranes'] += 1


# ------------------------------------------------------------------------------------------------ the elevated roads
def dress_highway(o, axis, at, cross, rnd):
    m = o.m; z = DECK
    W = lambda a, t: (a, at + t) if axis == 'x' else (at - t, a)
    yaw = 0.0 if axis == 'x' else 90.0; d = (1.0, 0.0) if axis == 'x' else (0.0, 1.0)
    def mk(a0, a1, t0, t1, kind, ru=1.0, rv=1.0, along=1.0):
        p0 = W(a0, t0); p1 = W(a1, t1)
        o.put('mark', [(bx((p0[0], p0[1], z + 0.05), (p1[0], p1[1], z + 0.9), m['mk_' + kind]), top_spec((d[0] * along, d[1] * along), ru, rv))])
    spans = [(-(HW_END - 10.0), cross - 400.0), (cross + 400.0, HW_END - 10.0)]
    for a0, a1 in spans:
        L = a1 - a0
        for t in (-8, 3): mk(a0, a1, t, t + 5, 'yellow', 1, L / 256)
        for t in (-160, 160): mk(a0 + 20, a1 - 20, t - 2.5, t + 2.5, 'dash', 1, (L - 40) / 150)
        for t in (-316, 311): mk(a0, a1, t, t + 5, 'solid', 1, L / 256)
    # the flat junction: stop lines and arrows (left-hand traffic: heading +a keeps to t > 0)
    mk(cross - 416, cross - 404, 10, 310, 'stop'); mk(cross + 404, cross + 416, -310, -10, 'stop')
    for t in (80, 240):
        mk(cross - 560, cross - 470, t - 17, t + 17, 'arrow', along=-1.0); mk(cross + 470, cross + 560, -t - 17, -t + 17, 'arrow', along=1.0)
    p0 = W(cross - 150, -150); p1 = W(cross + 150, 150)
    o.put('mark', [(bx((min(p0[0], p1[0]), min(p0[1], p1[1]), z + 0.05), (max(p0[0], p1[0]), max(p0[1], p1[1]), z + 0.9), m['mk_hatch']), top_spec((0.0, 1.0), 3, 3))])
    for q in range(-2400, 2401, 600):                                    # expansion joints
        if abs(q - cross) < 420: continue
        p0 = W(q - 3, -320); p1 = W(q + 3, 320)
        o.put('mark', [(bx((p0[0], p0[1], z + 0.02), (p1[0], p1[1], z + 0.7), m['rubber']), None)])
    for a in range(-int(HW_END) + 60, int(HW_END) - 59, 177):            # amber reflector studs on the parapets
        if abs(a - cross) < 400: continue
        for t in (-360, 360):
            x, y = W(a, t); o.put('stud', [(bx((x - 2, y - 2, z + 132), (x + 2, y + 2, z + 135.5), m['e_amber']), None)])
    for i, a in enumerate(range(-2700, 2701, 600)):                      # lamp masts on the parapets, alternating sides
        if abs(a - cross) < 420: continue
        side = 1 if i % 2 else -1
        x, y = W(a, side * 360)
        o.put('lamp', lamp(m, 'e_white', 250.0, 90.0), x, y, z + 132, yaw + (-90 if side > 0 else 90))
        lx, ly = W(a, side * 250); o.light(lx, ly, z + 330, 15000, 760, LIGHT['white'])
    for gi, a in enumerate((-1300.0 if cross < 0 else -2700.0, 1500.0 if cross < 0 else 300.0)):       # sign gantries over the deck
        parts = []
        for t in (-360, 360):
            x, y = W(a, t); parts.append((bx((x - 9, y - 9, z + 132), (x + 9, y + 9, z + 800), m['metal_grey']), None))
        for zz in (z + 740, z + 790):
            p0 = W(a, -360); p1 = W(a, 360); parts.append((bar([(p0[0], p0[1], zz), (p1[0], p1[1], zz)], 7, 7, m['metal_grey']), None))
        for k in range(8):
            p0 = W(a, -360 + k * 90); p1 = W(a, -270 + k * 90)
            parts.append((bar([(p0[0], p0[1], z + (740 if k % 2 else 790)), (p1[0], p1[1], z + (790 if k % 2 else 740))], 3, 3, m['metal_grey']), None))
        o.put('gantry', parts)
        for k, t in enumerate((-190, 150)):
            x, y = W(a, t); s1 = m['hwsign_%d' % ((gi * 2 + k) % 4)]; s2 = m['hwsign_%d' % ((gi * 2 + k + 1) % 4)]
            o.put('gantry', [(bx((-3, -130, 0), (3, 130, 130), m['metal_dark'], px=s1, nx=s2), 'fit')], x, y, z + 600, yaw)
        x, y = W(a, -20); o.put('gantry', [(bx((-3, -70, 0), (3, 70, 34), m['metal_dark'], px=m['led_amber'], nx=m['led_red']), 'fit')], x, y, z + 556, yaw)
        o.n['gantries'] += 1
    # stranded traffic
    for a0, a1 in spans:
        for c in range(2):
            ac = rnd.uniform(a0 + 250, a1 - 250)
            for k in range(rnd.randint(3, 5)):
                lane = rnd.choice([-240, -80, 80, 240]); a = ac + rnd.uniform(-260, 260)
                x, y = W(a, lane + rnd.uniform(-20, 20)); o.car(rnd, x, y, z, yaw + rnd.uniform(-14, 14), pad=10)
        a = rnd.uniform(a0 + 300, a1 - 300); x, y = W(a, rnd.choice([-235, 235]))
        o.car(rnd, x, y, z, yaw + rnd.uniform(-5, 5), key=rnd.choice(['bus01_2', 'semi_trailer']), pad=10)
    for e in (-1, 1):                                                    # ramp heads: cones and a warning board
        for k in range(6):
            x, y = W(e * (HW_END - 40 - k * 16), -300 + k * 34); o.ground_prop('traffic_cone', x, y, z, rnd.uniform(0, 360))
        x, y = W(e * (HW_END - 100), 250)
        o.put('furn', [(bx((-1.5, -34, 22), (1.5, 34, 40), m['metal_dark'], px=m['led_amber'], nx=m['led_amber']), 'fit'), (bx((-9, -28, 0), (9, -24, 22), m['orange']), None),
                       (bx((-9, 24, 0), (9, 28, 22), m['orange']), None)], x, y, z, yaw)
    # under the deck: piers
    piers = [int(q) for q in HW_PIERS]
    for q in piers:
        x, y = W(q, 0); parts = []
        for zz in (46, 600): parts.append((bx((x - 116, y - 116, zz), (x + 116, y + 116, zz + 14), m['conc_dark']), None))
        for sgn in (-1, 1):                                              # chevron boards facing the traffic, a number plate, soffit lamps
            cx, cy = W(q + sgn * 113, 0)
            o.put('pier', [(bx((-1.5, -34, 0), (1.5, 34, 56), m['metal_dark'], px=m['mk_chevron']), 'fit')], cx, cy, 70, yaw + (0 if sgn > 0 else 180))
            px, py = W(q + sgn * 30, 112 * sgn); parts.append((bx((px - 9, py - 1.2, 84), (px + 9, py + 1.2, 96), m['white']), None) if axis == 'x' else (bx((px - 1.2, py - 9, 84), (px + 1.2, py + 9, 96), m['white']), None))
            lx, ly = W(q + sgn * 230, 0); l0 = W(q + sgn * 230 - 40, -5); l1 = W(q + sgn * 230 + 40, 5)
            parts.append((bx((l0[0], l0[1], 694), (l1[0], l1[1], 699.6), m['metal_dark'], bottom=m['e_white']), None))
            o.light(lx, ly, 600, 13000, 820, LIGHT['white'])
        dx, dy = W(q + 115, 115); parts.append((tube([(dx, dy, 640), (dx, dy, 10)], 4.0, m['metal_galv'], 5), None))
        i0 = W(q - 250, -128); i1 = W(q + 250, 128)                       # the median island round the pier
        parts.append((bx((i0[0], i0[1], RZ), (i1[0], i1[1], RZ + 8), m['conc'], top=m['conc_dark']), None))
        o.put('pier', parts)
        for sgn in (-1, 1):
            h0 = W(q + sgn * 250, -128); h1 = W(q + sgn * 390, 128)
            o.put('mark', [(bx((h0[0], h0[1], RZ + 0.15), (h1[0], h1[1], RZ + 1.05), m['mk_hatch']), top_spec(d, 256 / 96, 140 / 96))])
    if axis == 'x':                                                      # cars parked between the piers, under the deck
        for q0, q1 in zip(piers, piers[1:]):
            for a in range(q0 + 430, q1 - 420, 62):
                l0 = W(a - 31.5, -80); l1 = W(a - 28.5, 80)
                o.put('mark', [(bx((l0[0], l0[1], RZ + 0.05), (l1[0], l1[1], RZ + 0.9), m['mk_solid']), top_spec((0.0, 1.0), 1, 0.6))])
                if rnd.random() < 0.38: x, y = W(a, rnd.uniform(-10, 10)); o.car(rnd, x, y, RZ, yaw + 90 + rnd.uniform(-3, 3), pad=3)


# ------------------------------------------------------------------------------------------------ the central square
def ring(o, cat, r_out, r_in, z0, z1, mat, **faces):
    o.put(cat, [(bx((-r_out, r_in, z0), (r_out, r_out, z1), mat, **faces), None), (bx((-r_out, -r_out, z0), (r_out, -r_in, z1), mat, **faces), None),
                (bx((r_in, -r_in, z0), (r_out, r_in, z1), mat, **faces), None), (bx((-r_out, -r_in, z0), (-r_in, r_in, z1), mat, **faces), None)])


def dress_plaza(o, rnd):
    m = o.m; FLOORM, CONC2, STEEL, TRIM = SO.FLOOR, SO.CONCRETE2, SO.STEEL, SO.TRIM
    # --- rim: three broad steps down into the water (solid, within 16 u of the old slope), a pale nosing and inlay bands on the dry one
    for r_out, r_in, zt in ((1949.0, 1863.0, 6.0), (1863.0, 1776.0, -6.0), (1776.0, 1690.0, -20.0)):
        ring(o, 'plaza_solid', r_out, r_in, -62.0, zt, CONC2, top=FLOORM)
    ring(o, 'plaza', 1866.0, 1862.0, 5.0, 6.5, m['stone'])
    for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for a in range(-1800, 1801, 240):
            if abs(a) < 200: continue
            c = (sx * 1906 + (a if sx == 0 else 0), sy * 1906 + (a if sy == 0 else 0))
            hx, hy = (42, 5) if sx else (5, 42)
            o.put('plaza', [(bx((c[0] - hx, c[1] - hy, 6.02), (c[0] + hx, c[1] + hy, 6.6), m['stone']), None)])
        for a in range(-1824, 1825, 96):                                 # lit bollards along the top step
            if abs(a) < 190: continue
            x, y = sx * 1936 + (a if sx == 0 else 0), sy * 1936 + (a if sy == 0 else 0)
            o.put('bollard', bollard(m, 'e_warm', 22.0), x, y, 6.0)
        # duckboards on trestles from the landing to the dais (Venice's passerelle)
        r0, r1 = 1905.0, (452.0 if sy > 0 else 410.0); n = int((r0 - r1) // 86)          # the north run stops at the letter mast's plinth
        parts = [(bx((min(sx * r0, sx * r1) - (13 if sx == 0 else 0), min(sy * r0, sy * r1) - (13 if sy == 0 else 0), 6.8),
                     (max(sx * r0, sx * r1) + (13 if sx == 0 else 0), max(sy * r0, sy * r1) + (13 if sy == 0 else 0), 8.0), m['wood']), None)]
        for i in range(n + 1):
            r = r1 + (r0 - r1) * i / n
            for w in (-11, 11):
                x, y = sx * r + (w if sx == 0 else 0), sy * r + (w if sy == 0 else 0)
                if i % 2 == 0: parts.append((bx((x - 1.2, y - 1.2, -40), (x + 1.2, y + 1.2, 5), m['metal_galv']), None))
                if w > 0: parts.append((bx((x - 0.9, y - 0.9, 8), (x + 0.9, y + 0.9, 28), m['metal_galv']), None))
        a0 = (sx * r0 + (11 if sx == 0 else 0), sy * r0 + (11 if sy == 0 else 0), 28.0); a1 = (sx * r1 + (11 if sx == 0 else 0), sy * r1 + (11 if sy == 0 else 0), 28.0)
        parts.append((bar([a0, a1], 1.4, 1.4, m['metal_galv']), None))
        o.put('plaza', parts)
        # cafe tables standing in the shallow water of the second step
        for a in (-1250, -640, 640, 1250):
            cx, cy = sx * 1820 + (a if sx == 0 else 0), sy * 1820 + (a if sy == 0 else 0)
            for k in range(3):
                tx, ty = cx + (0 if sx else (k - 1) * 64), cy + ((k - 1) * 64 if sx else 0)
                o.ground_prop('patio_table_01_low', tx, ty, -6.0, rnd.uniform(0, 90), check=False)
                for j in range(rnd.randint(2, 3)):
                    ang = rnd.uniform(0, 6.28); o.ground_prop('patio_chair_01_low', tx + 19 * math.cos(ang), ty + 19 * math.sin(ang), -6.0, math.degrees(ang) + 180 + rnd.uniform(-30, 30), check=False)
            if rnd.random() < 0.6: o.ground_prop('patio_umbrella_closed', cx + rnd.uniform(-20, 20), cy + rnd.uniform(-20, 20), -6.0, 0, check=False)
    for k in range(11):                                                  # the flood: wrecks caught in the basin, half out of the water
        ang = rnd.uniform(0, 6.283); r = rnd.uniform(900, 1620)
        x, y = max(-1650, min(1650, r * math.cos(ang))), max(-1650, min(1650, r * math.sin(ang)))
        if abs(x) < 60 or abs(y) < 60: continue
        # wrecks, not parked cars (skink52, 11 Nov 2026: "they'd be destroyed if they were there irl"): burnt-out and stripped bodies, rusted,
        # lying at an angle where the flood left them, a little deeper in the silt
        rust = rnd.choice(['74 52 40', '58 50 46', '96 70 52', '40 40 42', '84 60 44'])
        if k == 0: o.ground_prop('bus01_2', x, y, -47.0, rnd.uniform(0, 360), tint=rust, pad=20, pitch=rnd.uniform(-3, 3), roll=rnd.choice((-1, 1)) * rnd.uniform(5, 9))
        else:
            key = rnd.choice(['dust_car_wreck_body', 'dust_car_wreck_body', 'dust_hatchback_body', 'flatnose_truck_wrecked', 'car_tarp_cover_1', 'dust_limo_lowpoly'])
            o.ground_prop(key, x, y, -45.0 + rnd.uniform(0, 5), rnd.uniform(0, 360), tint=rust, pad=20, pitch=rnd.uniform(-7, 7), roll=rnd.uniform(-9, 9))
    # --- the dais: two steps into the water (solid) and a lit edge
    ring(o, 'plaza_solid', 372.0, 340.0, -50.0, 14.0, CONC2, top=FLOORM); ring(o, 'plaza_solid', 404.0, 372.0, -50.0, -12.0, CONC2, top=FLOORM)
    ring(o, 'plaza', 341.5, 340.0, 33.0, 37.0, m['e_cyan'])
    # --- the centrepiece: a broadcast arch over the dais. Four legs out of the water at (+-700, +-700), a ring at z 1195, four
    #     double-sided screens between the legs (z 860-1120), a news ticker round the ring, a mast to z 2250. Sized round the
    #     objective's letter mast (tools/arenas/objectives.py: 330 u north of the centre, its sign cube z 700-1060, 320 u wide)
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        o.put('plaza_solid', [(bar([(700 * sx, 700 * sy, -48), (640 * sx, 640 * sy, 450), (438 * sx, 438 * sy, 1195)], 66, 66, STEEL), None),
                              (bx((700 * sx - 90, 700 * sy - 90, -48), (700 * sx + 90, 700 * sy + 90, 24), CONC2), None),
                              (bar([(438 * sx, 438 * sy, 1212), (0, 0, 1570)], 36, 36, STEEL), None)])
        o.put('plaza', [(bx((700 * sx - 92, 700 * sy - 92, 24), (700 * sx + 92, 700 * sy + 92, 29), m['e_cyan' if sx * sy > 0 else 'e_magenta']), None)])
    RR = 620.0; RM = RR * math.cos(math.radians(22.5))
    pts = [(RR * math.cos(math.radians(45 * k + 45)), RR * math.sin(math.radians(45 * k + 45)), 1195.0) for k in range(8)]
    o.put('plaza_solid', [(P.sweep(pts, P.rect(54, 54), closed=True, mat=STEEL), None)])
    for k in range(8):                                                   # the ticker, and down lights under the ring
        a = math.radians(45 * k + 67.5); r = RM + 35; t = m['ticker_%d' % (k % 3)]
        o.put('screen', [(bx((-3, -232, 0), (3, 232, 84), m['metal_dark'], px=t, nx=t), 'fit')], r * math.cos(a), r * math.sin(a), 1228, math.degrees(a))
        o.put('plaza', [(bx((-18, -18, 0), (18, 18, 4), m['e_white']), None)], (r - 35) * math.cos(a), (r - 35) * math.sin(a), 1163.5)
    for k, (sx, sy) in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):    # the four screens
        yaw = k * 90.0; s1 = m['screen_%d' % k]; s2 = m['screen_%d' % (k + 4)]
        o.put('screen', [(bx((-7, -330, 0), (7, 330, 260), m['metal_dark'], px=s1, nx=s2), 'fit'), (bx((-10, -336, -9), (10, 336, -0.5), m['metal_dark']), None),
                         (bx((-10, -336, 260.5), (10, 336, 269), m['metal_dark']), None)], sx * 560, sy * 560, 860, yaw)
        c = '%d %d %d' % DM.PAL[k][0]
        o.light(sx * 1000, sy * 1000, 760, 60000, 1600, c); o.light(sx * 260, sy * 260, 700, 26000, 800, '%d %d %d' % DM.PAL[k + 4][0])
    o.light(0, -120, 1000, 60000, 1300, LIGHT['white'])
    o.put('plaza_solid', [(cyl(0, 0, 18, 1560, 2250, STEEL, 8), None)])
    for z, c in ((1720, 'e_cyan'), (1900, 'e_magenta'), (2080, 'e_cyan')): o.put('plaza', [(cyl(0, 0, 38, z, z + 12, m[c], 10), None)])
    o.put('plaza', [(bx((-14, -14, 2250), (14, 14, 2276), m['e_red']), None)])
    # --- festoon cables from the ring to the eight rim pylons, the pylons dressed as advert towers
    pillars = [(-1400, -1400), (1400, -1400), (-1400, 1400), (1400, 1400), (0, -1500), (0, 1500), (-1500, 0), (1500, 0)]
    for i, (px, py) in enumerate(pillars):
        ang = math.atan2(py, px); a = (640 * math.cos(ang), 640 * math.sin(ang), 1215.0); b = (px - 80 * math.cos(ang), py - 80 * math.sin(ang), 424.0)
        path = sag(a, b, 150.0, 13); parts = [(tube(path, 1.5, m['rubber'], 3), None)]
        for j in range(1, 12):
            for f in (0.25, 0.75):
                p = [path[j][q] + (path[j + 1][q] - path[j][q]) * f if j < 12 else path[j][q] for q in range(3)]
                parts.append((bx((p[0] - 2.4, p[1] - 2.4, p[2] - 7), (p[0] + 2.4, p[1] + 2.4, p[2] - 2), m['e_warm' if (j + i) % 3 else 'e_magenta']), None))
        o.put('wire', parts)
        col = 'e_cyan' if i % 2 else 'e_magenta'
        for k, (nx, ny) in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):
            p = m['poster_%d' % ((i * 3 + k) % 8)]
            o.put('screen', [(bx((0, -76, 0), (5, 76, 304), m['metal_dark'], px=p), 'fit')], px + nx * 90.5, py + ny * 90.5, 90, k * 90.0)
        o.put('plaza', [(bx((px - 98, py - 98, 420), (px + 98, py + 98, 428), m[col]), None)])
        o.light(px - 230 * math.cos(ang), py - 230 * math.sin(ang), 260, 20000, 760, LIGHT['cyan' if i % 2 else 'magenta'])
    # --- the promenades (the sidewalk between the rim and the ring avenues, z 12)
    for k, (sx, sy) in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):
        W = lambda a, r: (sx * r + (a if sx == 0 else 0), sy * r + (a if sy == 0 else 0))
        inward = math.degrees(math.atan2(-sy, -sx)); outward = inward + 180
        for a in range(-1900, 1901, 100):
            if abs(a) < 470: continue
            slot = (a // 100) % 6
            if slot == 0:                                                # a lamp at the kerb, lighting the promenade
                x, y = W(a, 2108)
                if o.claim(x, y, 6, 6, 0, SZ, 240, name='lamp'):
                    o.put('lamp', lamp(m, 'e_warm', 210.0, 40.0, 'poster_%d' % rnd.randrange(8)), x, y, SZ, inward)
                    lx, ly = W(a, 2040); o.light(lx, ly, 190, 9000, 600, LIGHT['warm'])
            elif slot in (1, 4):
                x, y = W(a, 1966)
                if o.claim(x, y, 8, 24, inward, SZ, 40, name='bench'): o.put('furn', bench(m), x, y, SZ, inward)
            elif slot == 2:
                x, y = W(a, 2030)
                if o.claim(x, y, 34, 34, 0, SZ, 300, name='tree'):
                    o.put('furn', [(bx((-32, -32, 0), (32, 32, 13), m['stone']), None), (bx((-28, -28, 13), (28, 28, 16), m['hedge']), None)], x, y, SZ)
                    if (a // 100) % 12 == 2: o.ground_prop('generic_tree_large_1', x, y, SZ + 14, rnd.uniform(0, 360), check=False)
            elif slot == 3:
                what = rnd.choice(['vend', 'kiosk', 'pylon', 'phone'])
                x, y = W(a, 2086)
                if what == 'vend' and o.claim(x, y, 14, 46, inward, SZ, 60, name='vend'): o.put('furn', vend_cluster(m, rnd), x, y, SZ, inward); lx, ly = W(a, 2040); o.light(lx, ly, SZ + 34, 2400, 240, LIGHT['white'])
                elif what == 'kiosk' and o.claim(x, y - 0, 36, 42, inward, SZ, 80, name='kiosk'): xx, yy = W(a, 2072); o.put('furn', kiosk(m, rnd), xx, yy, SZ, inward); lx, ly = W(a, 2010); o.light(lx, ly, SZ + 40, 3600, 280, LIGHT['warm'])
                elif what == 'pylon' and o.claim(x, y, 6, 14, inward, SZ, 90, name='pylon'):
                    p1 = m['poster_%d' % rnd.randrange(8)]; p2 = m['poster_%d' % rnd.randrange(8)]
                    o.put('furn', [(bx((-2.5, -13, 0), (2.5, 13, 74), m['metal_dark'], px=p1, nx=p2), 'fit')], x, y, SZ, inward)
                elif what == 'phone' and o.claim(x, y, 12, 12, 0, SZ, 60, name='phone'): o.put('furn', phone_booth(m), x, y, SZ, inward)
            elif slot == 5 and (a // 100) % 12 == 5:                      # a market corner: an open umbrella, tables, a stall
                x, y = W(a, 2010)
                o.ground_prop('patio_umbrella_open', x, y, SZ, 0, pad=0)
                for j in range(3):
                    ang = j * 2.1 + 0.4; o.ground_prop('patio_table_01_low' if j == 0 else 'patio_chair_01_low', x + (0 if j == 0 else 22 * math.cos(ang)), y + (0 if j == 0 else 22 * math.sin(ang)), SZ, math.degrees(ang) + 180, check=False)
            elif slot == 5:
                x, y = W(a, 1962); o.put('furn', bin_(m, rnd), x, y, SZ)
        for a in (-1930, -1680, -1430, -1180, -930, -680, 680, 930, 1180, 1430, 1680, 1930):   # puddles on the paving
            x, y = W(a + rnd.uniform(-60, 60), 2030 + rnd.uniform(-40, 40)); hs = rnd.uniform(40, 90)
            o.put('puddle', [(bx((x - hs, y - hs * 0.6, SZ + 0.2), (x + hs, y + hs * 0.6, SZ + 0.6), m['puddle_%d' % rnd.randrange(3)]), M.uv(fit=(1, 1)))])
    # --- the tram: a track in the east avenue's plaza-side lane, catenary, a stop, a tram standing at it; a bus stop under each deck
    tx = 2204.0
    for dx in (-14, 14): o.put('tram', [(bx((tx + dx - 1.6, -2330, RZ + 0.05), (tx + dx + 1.6, 2330, RZ + 1.6), m['metal_galv']), None)])
    for y in (-2330, 2330): o.put('tram', [(bx((tx - 24, y - 6, RZ), (tx + 24, y + 6, RZ + 26), m['conc'], px=m['mk_chevron']), None)])
    prev = None
    for y in range(-2250, 2251, 300):
        if abs(y) < 0: continue
        px = 2112.0
        if abs(y) > PLAZA: px = 2112.0
        if o.claim(px, y, 5, 5, 0, SZ, 200, name='cat'):
            o.put('pole', [(cyl(px, y, 3.4, SZ, SZ + 176, m['metal_dark'], 6), None), (bar([(px, y, SZ + 158), (tx + 6, y, SZ + 150)], 2.2, 2.2, m['metal_dark']), None)])
        if prev is not None: o.put('wire', [(tube(sag((tx, prev, 137.0), (tx, y, 137.0), 3.0, 5), 0.9, m['rubber'], 3), None), (tube(sag((tx, prev, 160.0), (tx, y, 160.0), 14.0, 5), 0.8, m['rubber'], 3), None)])
        prev = y
    o.put('tram', tram(m), tx, -640, RZ + 1.6, 90.0); o.claim(tx, -447, 30, 200, 0, 0, 100, check=False, name='tram')
    o.light(tx - 60, -450, 60, 7000, 360, LIGHT['warm'])
    if o.claim(2070, -450, 26, 140, 0, SZ, 90, check=False, name='stop'): o.put('tram', tram_stop(m, rnd), 2062, -450, SZ, 0.0)
    o.light(2070, -450, 60, 9000, 420, LIGHT['white'])
    for (x, y, yaw) in ((-900, 2052, 90.0), (900, -2052, -90.0), (-2052, 900, 180.0)):    # bus shelters on the other three sides
        if o.ground_prop('overpass_bus_station', x, y, SZ, yaw, pad=6): o.light(x, y, 70, 5000, 300, LIGHT['white'])


def plaza_screens(o, rnd):
    """big LED walls on the towers that face the square, with a ticker under each and their light on the street"""
    m = o.m; n = 0
    for t in o.plan['towers']:
        x0, y0, z0, x1, y1, top = t['box']; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if t['_top_line'] - t['_zs'] < 560: continue
        if abs(cy) < 2000 and abs(cx) > 2000: nrm = (-1 if cx > 0 else 1, 0)
        elif abs(cx) < 2000 and abs(cy) > 2000: nrm = (0, -1 if cy > 0 else 1)
        else: continue
        wface = (y1 - y0) if nrm[0] else (x1 - x0); w = min(wface * 0.72, 600.0); h = w * 0.5
        over_deck = (nrm[0] == 1) or (nrm[1] == -1)                      # west and north towers look over a highway deck
        zb = max(t['_zs'] + 150, 980.0 if over_deck else 380.0)
        if zb + h + 60 > t['_top_line']: zb = t['_top_line'] - h - 60
        fx, fy = (x0 if nrm[0] < 0 else x1) if nrm[0] else cx, (y0 if nrm[1] < 0 else y1) if nrm[1] else cy
        if any(u is not t and u['box'][0] - 20 < fx < u['box'][3] + 20 and u['box'][1] - 20 < fy < u['box'][4] + 20 for u in o.plan['towers']): continue
        yaw = math.degrees(math.atan2(nrm[1], nrm[0])); k = n % 8
        o.put('screen', [(bx((0, -w / 2 - 8, -8), (9, w / 2 + 8, h + 8), m['metal_dark']), None), (bx((9, -w / 2, 0), (11, w / 2, h), m['metal_dark'], px=m['screen_%d' % ((k + 2) % 8)]), 'fit'),
                         (bx((0, -w / 2 - 8, -64), (9, w / 2 + 8, -14), m['metal_dark'], px=m['ticker_%d' % (k % 3)]), 'fit')], fx, fy, zb, yaw)
        o.light(fx + nrm[0] * 330, fy + nrm[1] * 330, zb + h / 2, 60000, 1500, '%d %d %d' % DM.PAL[(k + 2) % 8][0]); n += 1
    o.n['plaza_screens'] = n


# ------------------------------------------------------------------------------------------------ main
def build(o):
    rnd = random.Random(2099)
    plan = o.plan
    static_obstacles(o)
    dress_plaza(o, rnd); plaza_screens(o, rnd)
    for ax, at in plan['highways']: dress_highway(o, ax, at, -2400.0 if ax == 'x' else 2400.0, rnd)
    for x in LINES:
        for y in LINES:
            if abs(x) < PLAZA and abs(y) < PLAZA: continue
            dress_junction(o, x, y, rnd, hw=(y == 2400.0 or x == -2400.0))
    for i, seg in enumerate(segments()): dress_segment(o, seg, rnd, i)
    for blk in plan.get('blocks', []): dress_block(o, blk, rnd)
    for i, t in enumerate(plan['towers']): dress_tower(o, t, rnd, i)
    cranes(o, rnd)


def main(argv):
    if len(argv) < 3: sys.exit(__doc__)
    vmap, content = argv[1], argv[2]
    plan = json.load(open(os.path.join(content, '_gen', 'sprawl_plan.json')))
    global HW_END, HW_FOOT, HW_PIERS
    HW_END, HW_FOOT, HW_PIERS = float(plan.get('hw_end', HW_END)), float(plan.get('hw_foot', HW_FOOT)), list(plan.get('hw_piers', HW_PIERS))
    stub = defaultdict(str)
    SO.build_job(vmap, content, plan, stub, dry_run=True)                 # the same per-tower decisions as the city layer (ruin, roof, street band)
    mats = DM.materials(content)
    d = vmapgen.open_map(vmap, content)
    o = Out(mats, plan)
    build(o)
    meshes, faces = o.flush(); o.write_entities()
    tris = sum(o.tris.values())
    stats = dict(meshes=meshes, faces=faces, props=len(o.props), prop_models=len(set(p[0] for p in o.props)), prop_tris_lod0=tris, baked_lights=len(o.lights),
                 particle_systems=len(o.fx), faces_by_kind=dict(o.faces.most_common()), objects={k: v for k, v in sorted(o.n.items()) if not k.startswith('prop:')},
                 props_by_model={k[5:]: v for k, v in sorted(o.n.items()) if k.startswith('prop:')}, tris_by_model=dict(o.tris.most_common()))
    print('sprawl detail: %d meshes (%d faces), %d props of %d models (%d LOD0 triangles), %d baked lights, %d particle systems'
          % (meshes, faces, len(o.props), stats['prop_models'], tris, len(o.lights), len(o.fx)))
    if '--stats' in argv: json.dump(stats, open(argv[argv.index('--stats') + 1], 'w'), indent=1)
    if '--dry-run' in argv: return 0
    ap = os.path.join(content, '_gen', 'arena.json')                      # the script's list of the destructible cars
    if os.path.exists(ap):
        A = json.load(open(ap)); A['cars'] = o.live; json.dump(A, open(ap, 'w'))
        print('sprawl detail: %d destructible cars (ifr_car) -> %s' % (len(o.live), ap))
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        vmapgen.finish(d, vmap, group=GROUP, first_run_cleanup=False)
    print('sprawl detail -> %s (vis group %s)' % (vmap, GROUP))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
