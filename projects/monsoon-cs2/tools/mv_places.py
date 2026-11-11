"""mg_monsoon places (stage 4): the firebase, the camp and its tunnels, the five flags, waterfall, marsh, karst nests, road and
crater dressing, then the jungle. Each place is its own function with its own seeded RandomState, so adding to one never
reshuffles another. Everything goes through prop() (placer footprints: optional dressing uses check=True and is skipped when it
would touch something already there).

Shared with mv_entities.py through the World object W (module global, made in build()):
  W.PL      the placer (footprints of every prop, keep-out discs for pads / pits / spawns / roads)
  W.sites   positions the script entities need (kit stations, flag poles, mounts, racks, boards, pads, tunnel mouths, walkable
            platform tops that are not terrain)
  W.exc     props whose origin is deliberately off the ground (stacked, hanging, in water, on a platform): check_world.py skips them

World geometry (not props) made here with create/primitives.py + meshedit.py: temple terraces and stairs, bridge abutments and
ramps, pit berms (swept rings), tunnel portal arches, waterfall boulders (noise-deformed), karst player clips. Weather: fxkit rain
tiles over the flags and bases only, one lightning timer.
"""
import os, sys, json, math, heapq
import numpy as np
import vmaplib, vmesh, vmapgen as G, placer
from vmaplib import ent
import layout as L
import mv_terrain as TER
import mv_stock as S
from noise import fbm, smoothstep

_CREATE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'create'))
if _CREATE not in sys.path: sys.path.append(_CREATE)       # appended: the project's own dmx / vmaplib / vmesh copies keep winning
import primitives as P
import meshedit as ME
import fxkit

DIRT = 'materials/de_ancient/hr_ancient_ground_dirt_02_wet.vmat'
MUD = 'materials/de_ancient/hr_ancient_ground_mud_03_wet.vmat'
STONE = 'materials/de_ancient/hr_ancient_wall_stone_03_moss_wet.vmat'
STONE_TOP = 'materials/de_ancient/hr_ancient_wall_stone_01_grey_wet.vmat'
CONCRETE = 'materials/concrete/hr_c/hr_concrete_wall_004.vmat'
LADDER = 'materials/tools/toolsinvisibleladder_wood.vmat'
for _m in (DIRT, MUD, STONE, STONE_TOP, CONCRETE): vmesh.TEX_SIZE[_m] = (1024, 1024)
vmesh.TEX_SIZE[LADDER] = (64, 64)
FIRE = 'particles/burning_fx/env_fire_small.vpcf'
SMOKE_DARK = 'particles/burning_fx/barrel_burning_engine_smoke_dark.vpcf'
SMOKESTACK = 'particles/ambient_fx/ambient_smokestack.vpcf'
PROBED_KEYS = ('foliage', 'palm', 'weeds', 'grass', 'rice_clump', 'reeds', 'bamboo_clump', 'rubber_tree', 'dead_tree', 'vine', 'root', 'camo_net',
               'parachute', 'sandbag')

W = None


def gz(x, y):
    return L.gz(float(x), float(y))


def rot(yaw):
    a = math.radians(yaw)
    return math.cos(a), math.sin(a)


def local(x, y, yaw, lx, ly):
    """world position of the local point (lx, ly) of something at (x, y) turned by yaw"""
    c, s = rot(yaw)
    return x + c * lx - s * ly, y + s * lx + c * ly


class World:
    def __init__(self, d, group, out, T, karst, clone):
        self.d, self.group, self.out, self.T, self.karst, self.clone = d, group, out, T, karst, clone
        pj = os.path.join(os.path.dirname(os.path.abspath(out)), 'props.json')
        table, self.built = S.bounds_table(pj)
        self.B = placer.Bounds(props_json=pj, out=out, prefix='mv', table=table)
        self.PL = placer.Placer(bounds=self.B)
        self.count = {}; self.skipped = {}; self.exc = []; self.missing = set()
        self.sites = dict(kit={}, flagpole={}, mounts=[], racks=dict(ct=[], t=[]), board={}, guns=dict(ct=[], t=[]), pads=dict(ct=[], t=[]),
                          tunnels=[], surfaces=[], fires=[], nonav=[], seeds=[])

    # ---------------------------------------------------------------- props
    def probed(self, model, scale):
        if any(k in model for k in PROBED_KEYS): return True
        lo, hi = self.B(model)
        return max((hi[i] - lo[i]) * abs(scale[i]) for i in range(3)) < 40.0

    def ground(self, model, x, y, yaw, scale, fit):
        """z for a prop: 'o' = the ground under its origin, 'min' = the lowest ground under its footprint (never floats)"""
        if fit == 'o': return gz(x, y)
        f = self.PL.footprint(model, x, y, 0.0, yaw, scale)
        c, s = math.cos(f['a']), math.sin(f['a']); hx, hy = f['h']
        xs = [f['c'][0]] + [f['c'][0] + c * sx * hx - s * sy * hy for sx in (-1, 1) for sy in (-1, 1)]
        ys = [f['c'][1]] + [f['c'][1] + s * sx * hx + c * sy * hy for sx in (-1, 1) for sy in (-1, 1)]
        return float(L.height(np.array(xs), np.array(ys)).min())

    def prop(self, name, x, y, z=None, yaw=0.0, pitch=0.0, roll=0.0, scale=1.0, stock=None, solid='6', reg=True, check=False, pad=0.0,
             dz=0.0, fit='o', tag=None, trunk=None, **kw):
        """prop_static. z None = on the ground (fit). reg: record the footprint; check: place only when it touches nothing recorded.
        trunk: footprint is a disc of this radius (trees). tag: why its origin is off the ground (check_world exception)."""
        model = stock or S.mv(name)
        sc = (scale,) * 3 if isinstance(scale, (int, float)) else tuple(scale)
        if z is None:
            z = self.ground(model, x, y, yaw, sc, fit)
            if fit != 'o' and abs(z - gz(x, y)) > 6.0 and tag is None: tag = 'slope'
        z += dz
        if dz and tag is None and abs(dz) > 6.0: tag = 'offset'
        if trunk is not None:
            lo, hi = self.B(model)
            f = dict(c=(x, y), h=(trunk * sc[0] + pad, trunk * sc[0] + pad), a=0.0, z=(z, z + hi[2] * sc[2]), model=model)
        else:
            f = self.PL.footprint(model, x, y, z, yaw, sc, pad)
        if check and self.PL.hits(f):
            self.skipped[model] = self.skipped.get(model, 0) + 1
            return None
        if reg:
            if pad:
                f = dict(f); f['h'] = (f['h'][0] - pad, f['h'][1] - pad)
            self.PL.add(f)
        e = ent('prop_static', (x, y, z), (pitch, yaw, roll), group=self.group, model=model, rendercolor='255 255 255', skin='default', solid=solid,
                bakelighting='0' if self.probed(model, sc) else '1', disableshadows='0', lodlevel='-1', baketoworld='0', rendertocubemaps='1', **kw)
        if sc != (1, 1, 1): e.attr('scales')[2] = tuple(float(v) for v in sc)
        self.count[model] = self.count.get(model, 0) + 1
        if stock is None and name not in self.built: self.missing.add(name)
        if tag: self.exc.append([model, round(x, 1), round(y, 1), round(z, 1), tag])
        return e

    def keep(self, x, y, r, z=None, h=260.0, name='zone'):
        """keep-out disc (a square footprint) for optional dressing and trees: pads, pits, spawns, paths"""
        if z is None: z = gz(x, y)
        self.PL.add(dict(c=(x, y), h=(r, r), a=0.0, z=(z - 60.0, z + h), model='keepout/%s.vmdl' % name))

    def keep_path(self, pts, hw, step=None, name='path'):
        step = step or hw
        for a, b in zip(pts[:-1], pts[1:]):
            n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
            for k in range(n + 1):
                self.keep(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n, hw, name=name)

    def free(self, x, y, r=18.0, z=None, h=72.0):
        if z is None: z = gz(x, y)
        return self.PL.hits(dict(c=(x, y), h=(r, r), a=0.0, z=(z + 1.0, z + h), model='probe')) is None

    # ---------------------------------------------------------------- world geometry
    def shape(self, shape, bake=True, shadows=True, visexclude=False, paint=None, smoothing=40.0):
        probs = P.check(shape)
        if probs: raise ValueError('bad shape: ' + '; '.join(probs[:3]))
        v, f, m = shape
        pa = ti = None
        if paint is not None:
            pa = np.array([[float(paint(p)), 0.0, 0.35, 0.0] for p in v]); ti = np.ones((len(v), 4))
        return vmesh.mesh_node(vmesh.polymesh_open(v, f, m, paint=pa, tint=ti), self.group, bake=bake, shadows=shadows, visexclude=visexclude,
                               smoothing=smoothing)

    def clip(self, shape):
        return self.shape(shape, bake=False, shadows=False, visexclude=True)

    def surface(self, x0, y0, x1, y1, z):
        """a walkable top that is not terrain (terrace, deck): spawns and props stand on it"""
        self.sites['surfaces'].append([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), z])

    def particle(self, x, y, z, effect, name=None, active=True):
        kw = dict(targetname=name) if name else {}
        return ent('info_particle_system', (x, y, z), group=self.group, effect_name=effect, start_active='1' if active else '0', **kw)

    def lamp(self, x, y, z, lumens, color='255 184 110', rng_=150.0):
        """unshadowed baked lamp (CS2 has 4 shadow slots per overlap)"""
        return ent('light_omni2', (x, y, z), (90, 0, 0), group=self.group, brightness_units='1', brightness_lumens=str(int(lumens)), brightness='1',
                   color=color, range='%.0f' % rng_, directlight='3', castshadows='0', colormode='0', enabled='1', bouncescale='1.0', shape='0')

    # ---------------------------------------------------------------- sandbags
    def bag_dims(self, model):
        lo, hi = self.B(S.mv(model))
        return (hi[0] - lo[0]), (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, hi[2] - 1.0

    def bag_arc(self, cx, cy, r, a0, a1, layers=2, model='sandbag_wall', z=None, seed_rng=None):
        """sandbag wall along a circle arc (degrees, a0 < a1), the bags' long axis tangential; layers stacked with a half-bag stagger"""
        ln, ox, oy, h = self.bag_dims(model)
        dth = math.degrees((ln - 4.0) / r)
        n = max(1, int(round((a1 - a0) / dth)))
        for k in range(layers):
            for i in range(n if k % 2 == 0 else max(1, n - 1)):
                th = a0 + (i + 0.5 + (0.5 if k % 2 else 0.0)) * (a1 - a0) / n
                c, s = rot(th); yaw = th + 90.0
                # origin so that the bag's centre sits on the circle: local x offset ox (tangent), local y offset oy (points inward)
                x = cx + r * c + ox * s + oy * c; y = cy + r * s - ox * c + oy * s
                zz = (gz(cx + r * c, cy + r * s) if z is None else z) + k * h
                self.prop(model, x, y, zz, yaw + (seed_rng.uniform(-2, 2) if seed_rng is not None else 0.0), tag='stack' if k else ('platform' if z is not None else None))

    def bag_line(self, p, q, layers=2, model='sandbag_wall', z=None):
        ln, ox, oy, h = self.bag_dims(model)
        d = math.hypot(q[0] - p[0], q[1] - p[1]); n = max(1, int(round(d / (ln - 4.0))))
        yaw = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])); c, s = rot(yaw)
        for k in range(layers):
            for i in range(n if k % 2 == 0 else max(1, n - 1)):
                t = (i + 0.5 + (0.5 if k % 2 else 0.0)) / n
                mx, my = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
                x, y = mx - ox * c + oy * s, my - ox * s - oy * c
                self.prop(model, x, y, (gz(mx, my) if z is None else z) + k * h, yaw, tag='stack' if k else ('platform' if z is not None else None))

    def berm_arc(self, cx, cy, r, a0, a1, base=56.0, top=20.0, h=34.0, mat=DIRT, seg=14.0):
        """earth bank swept along an arc (world geometry): a trapezoid section, ends capped"""
        n = max(3, int((a1 - a0) / seg))
        path = []
        for i in range(n + 1):
            c, s = rot(a0 + (a1 - a0) * i / n)
            path.append((cx + r * c, cy + r * s, gz(cx + r * c, cy + r * s)))
        sec = [(-base / 2, -10.0), (base / 2, -10.0), (top / 2, h), (-top / 2, h)]
        self.shape(P.sweep(path, sec, mat=mat), smoothing=60.0)

    def stack(self, name, x, y, yaw, n, z=None, check=True, jitter=None):
        """n of a prop on top of each other; returns how many were placed"""
        lo, hi = self.B(S.mv(name)); z0 = gz(x, y) if z is None else z; done = 0
        for k in range(n):
            e = self.prop(name, x, y, z0 + k * (hi[2] - lo[2] if lo[2] >= 0 else hi[2]), yaw + (jitter.uniform(-6, 6) if jitter is not None else 0.0),
                          check=check and k == 0, pad=1.0 if k == 0 else 0.0, tag='stack' if k else None)
            if e is None: break
            done += 1
        return done


def clutter(rng, items, cx, cy, r0, r1, tries=8, z=None, face=None):
    """optional small props in a ring around a point: items = [(name, count)]; each tries a few spots and is skipped when blocked"""
    n = 0
    for name, cnt in items:
        for _ in range(cnt):
            for _t in range(tries):
                a = rng.uniform(0, 2 * math.pi); r = rng.uniform(r0, r1)
                x, y = cx + r * math.cos(a), cy + r * math.sin(a)
                if z is None and float(L.slope(x, y)) > 16.0: continue
                e = W.prop(name, x, y, z, rng.uniform(0, 360) if face is None else face + rng.uniform(-25, 25), check=True, pad=3.0, fit='o')
                if e is not None: n += 1; break
    return n


# ================================================================ tunnels: the plan (also used for the terrain holes)
_TUN = None
TUN_H, TUN_CH_H, TUN_K = 104.0, 140.0, 0.47


def _dijkstra(n, adj, init, k=1.0):
    """lowest value reachable: val[j] = min(init[i] + k * path length i..j)"""
    val = list(init); heap = [(v, i) for i, v in enumerate(val) if v < 1e17]; heapq.heapify(heap)
    while heap:
        v, i = heapq.heappop(heap)
        if v > val[i] + 1e-9: continue
        for j, d in adj[i]:
            nv = v + k * d
            if nv < val[j] - 1e-9: val[j] = nv; heapq.heappush(heap, (nv, j))
    return np.array(val)


def tunnel_plan():
    """galleries on a 16-u grid: occupied cells, floor / roof heights per grid vertex, the cells cut open to the sky at the portals
    (32-u terrain cells left out of the terrain) and lamp spots. Depends on layout only."""
    global _TUN
    if _TUN is not None: return _TUN
    galleries_ext = []
    pts = []; adj = []; gal = []; ext = []
    def node(p, g):
        pts.append(p); adj.append([]); gal.append(g); ext.append(False); return len(pts) - 1
    for gi, g in enumerate(L.TUNNEL_GALLERIES):
        g = list(g)
        # a shallow lead-in trench 56 u beyond each portal, so the cut always ends in a step a player walks over
        if g[0] in L.TUNNEL_PORTALS:
            d = math.hypot(g[1][0] - g[0][0], g[1][1] - g[0][1]); g.insert(0, (g[0][0] - (g[1][0] - g[0][0]) / d * 56.0, g[0][1] - (g[1][1] - g[0][1]) / d * 56.0))
        if g[-1] in L.TUNNEL_PORTALS:
            d = math.hypot(g[-2][0] - g[-1][0], g[-2][1] - g[-1][1]); g.append((g[-1][0] - (g[-2][0] - g[-1][0]) / d * 56.0, g[-1][1] - (g[-2][1] - g[-1][1]) / d * 56.0))
        galleries_ext.append(g)
        prev = None; seg_i = -1
        for a, b in zip(g[:-1], g[1:]):
            seg_i += 1
            d = math.hypot(b[0] - a[0], b[1] - a[1]); n = max(1, int(round(d / 16.0)))
            for t in range(n + 1):
                if t == 0 and prev is not None: continue
                i = node((a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n), gi)
                if (seg_i == 0 and a not in L.TUNNEL_GALLERIES[gi] and t < n) or (b not in L.TUNNEL_GALLERIES[gi] and t > 0): ext[i] = True
                if prev is not None:
                    dd = math.hypot(pts[i][0] - pts[prev][0], pts[i][1] - pts[prev][1])
                    adj[i].append((prev, dd)); adj[prev].append((i, dd))
                prev = i
    Pn = np.array(pts); n = len(pts)
    for i in range(n):
        for j in range(i + 1, n):
            if gal[i] != gal[j] and abs(Pn[i, 0] - Pn[j, 0]) < 1.0 and abs(Pn[i, 1] - Pn[j, 1]) < 1.0:
                adj[i].append((j, 0.0)); adj[j].append((i, 0.0))
    portal_idx = [int(np.argmin(np.hypot(Pn[:, 0] - p[0], Pn[:, 1] - p[1]))) for p in L.TUNNEL_PORTALS]
    dp = _dijkstra(n, adj, [0.0 if i in portal_idx else 1e18 for i in range(n)])
    g = np.min([L.height(Pn[:, 0] + ox, Pn[:, 1] + oy) for ox, oy in ((0, 0), (40, 0), (-40, 0), (0, 40), (0, -40))], axis=0)
    cap = np.where(np.array(gal) == len(L.TUNNEL_GALLERIES) - 1, 240.0, 150.0)      # the stub runs on down so the chamber keeps its roof
    target = g - np.minimum(cap, 8.0 + TUN_K * dp)
    target = np.where(np.array(ext), g - 6.0, target)
    f = _dijkstra(n, adj, list(target), k=TUN_K)
    ch = np.array(L.TUNNEL_CHAMBER); f_ch = float(f[int(np.argmin(np.hypot(Pn[:, 0] - ch[0], Pn[:, 1] - ch[1])))])
    # grid
    R = L.TUNNEL_CHAMBER_R
    x0 = math.floor((min(Pn[:, 0].min(), ch[0] - R) - 96) / 32) * 32; x1 = math.ceil((max(Pn[:, 0].max(), ch[0] + R) + 96) / 32) * 32
    y0 = math.floor((min(Pn[:, 1].min(), ch[1] - R) - 96) / 32) * 32; y1 = math.ceil((max(Pn[:, 1].max(), ch[1] + R) + 96) / 32) * 32
    gx = np.arange(x0, x1 + 1, 16.0); gy = np.arange(y0, y1 + 1, 16.0)
    nx, ny = len(gx) - 1, len(gy) - 1
    CX, CY = np.meshgrid((gx[:-1] + gx[1:]) / 2, (gy[:-1] + gy[1:]) / 2, indexing='ij')
    occ = np.zeros((nx, ny), bool)
    for gl in galleries_ext:
        d, _ = L.seg_dist(CX, CY, gl); occ |= d <= L.TUNNEL_HW
    occ |= np.hypot(CX - ch[0], CY - ch[1]) <= R
    VX, VY = np.meshgrid(gx, gy, indexing='ij')
    near = np.zeros(VX.shape, np.int64); best = np.full(VX.shape, 1e18)
    for i in range(n):
        d2 = (VX - Pn[i, 0]) ** 2 + (VY - Pn[i, 1]) ** 2
        m = d2 < best; best[m] = d2[m]; near[m] = i
    FZ = np.round(f[near] * 2) / 2
    in_ch = np.hypot(VX - ch[0], VY - ch[1]) <= R + 12.0
    FZ[in_ch] = round(f_ch * 2) / 2
    CZ = FZ + np.where(in_ch, TUN_CH_H, TUN_H)
    # the terrain's 32 grid over the same box: where the roof would break the ground the 32-cell is cut open to the sky
    H32 = np.asarray(L.height(VX[::2, ::2], VY[::2, ::2]), float)
    nb = occ.reshape(nx // 2, 2, ny // 2, 2).any(axis=(1, 3))
    gmin = np.minimum(np.minimum(H32[:-1, :-1], H32[1:, :-1]), np.minimum(H32[:-1, 1:], H32[1:, 1:]))
    cmax = np.zeros(nb.shape)
    for bi, bj in zip(*np.nonzero(nb)): cmax[bi, bj] = CZ[2 * bi:2 * bi + 3, 2 * bj:2 * bj + 3].max()
    openb = nb & (cmax + 24.0 > gmin)
    openc = np.repeat(np.repeat(openb, 2, axis=0), 2, axis=1)
    occ = G.fix_pinches(occ | openc)
    # terrain height at the 16 grid: exactly the terrain mesh along its 32-cell edges (mid points are the mean of the two corners)
    TZ = np.zeros(VX.shape); TZ[::2, ::2] = H32
    TZ[1::2, ::2] = (H32[:-1, :] + H32[1:, :]) / 2; TZ[::2, 1::2] = (H32[:, :-1] + H32[:, 1:]) / 2
    TZ[1::2, 1::2] = (H32[:-1, :-1] + H32[1:, 1:] + H32[1:, :-1] + H32[:-1, 1:]) / 4
    ov = np.zeros(VX.shape, bool)
    for di in (0, 1):
        for dj in (0, 1): ov[di:nx + di, dj:ny + dj] |= openc
    FZ = np.where(ov, np.minimum(FZ, TZ - 6.0), FZ)
    holes = set()
    for bi, bj in zip(*np.nonzero(openb)):
        holes.add((int(round(gx[2 * bi] / 32)), int(round(gy[2 * bj] / 32))))
        bc = (gx[2 * bi] + 16, gy[2 * bj] + 16)
        if min(math.hypot(bc[0] - p[0], bc[1] - p[1]) for p in L.TUNNEL_PORTALS) > 520.0:
            print('WARNING tunnel breaks the surface away from a portal at (%.0f, %.0f)' % bc)
    # lamps: every ~210 u along each gallery where it is roofed
    lamps = []
    for gi, gl in enumerate(L.TUNNEL_GALLERIES):
        idx = [i for i in range(n) if gal[i] == gi]
        for i in idx[6::13]:
            ci = int((Pn[i, 0] - x0) // 16); cj = int((Pn[i, 1] - y0) // 16)
            if 0 <= ci < nx and 0 <= cj < ny and occ[ci, cj] and not openc[ci, cj]: lamps.append((Pn[i, 0], Pn[i, 1], float(f[i]) + TUN_H - 14.0))
    # per portal: the mouth (start of the gallery) and the first roofed sample (where the arch goes) with the gallery direction
    mouths = []
    for k, pi in enumerate(portal_idx):
        chain = [i for i in range(n) if gal[i] == gal[pi]]
        q = chain.index(pi); chain = chain[q:] if q < len(chain) / 2 else chain[:q + 1][::-1]
        arch = None
        for a, b in zip(chain[:-1], chain[1:]):
            ci = int((Pn[b, 0] - x0) // 16); cj = int((Pn[b, 1] - y0) // 16)
            if not openc[ci, cj]:
                arch = (Pn[b, 0], Pn[b, 1], float(f[b]), math.degrees(math.atan2(Pn[b, 1] - Pn[a, 1], Pn[b, 0] - Pn[a, 0]))); break
        j = chain[min(3, len(chain) - 1)]
        mouths.append(dict(pos=(Pn[pi, 0], Pn[pi, 1], float(f[pi])), inside=(Pn[j, 0], Pn[j, 1], float(f[j])), arch=arch))
    _TUN = dict(gx=gx, gy=gy, occ=occ, open=openc, FZ=FZ, CZ=CZ, TZ=TZ, holes=holes, lamps=lamps, mouths=mouths, f_ch=f_ch, samples=Pn, floor=f,
                box=(x0, y0, float(FZ[ov | True].min()), x1, y1, float(CZ.max())))
    return _TUN


def tunnel_floor(x, y):
    t = tunnel_plan(); i = int(np.argmin(np.hypot(t['samples'][:, 0] - x, t['samples'][:, 1] - y)))
    if math.hypot(x - L.TUNNEL_CHAMBER[0], y - L.TUNNEL_CHAMBER[1]) <= L.TUNNEL_CHAMBER_R + 12: return t['f_ch']
    return float(t['floor'][i])


def bunker_rects():
    """(x, y, yaw, interior half length, half width) of the dug-in firebase bunkers (their floors sit 24 u below the ground)"""
    fb = L.firebase(); out = []
    for i, (p, a) in enumerate(zip(fb['bunkers'], fb['bunker_angles'])):
        out.append((p[0], p[1], a, 90.0, 66.0) if i in fb['m2'] else (p[0], p[1], a, 66.0, 51.0))
    return out


def terrain_holes(CX, CY, r):
    """cells left out of the terrain: the open cuts at the tunnel portals and the dug floors inside the firebase bunkers"""
    cut = np.zeros(CX.shape, bool)
    t = tunnel_plan()
    if t['holes']:
        bx = np.floor(CX / 32.0).astype(np.int64); by = np.floor(CY / 32.0).astype(np.int64)
        x0, y0, _, x1, y1, _ = t['box']
        if CX.max() >= x0 and CX.min() <= x1 and CY.max() >= y0 and CY.min() <= y1:
            assert r <= 32, 'tunnel portal in a coarse terrain tile (see mv_terrain.tile_res)'
            for i, j in zip(*np.nonzero((CX >= x0) & (CX <= x1) & (CY >= y0) & (CY <= y1))):
                if (int(bx[i, j]), int(by[i, j])) in t['holes']: cut[i, j] = True
    for (x, y, yaw, hl, hw) in bunker_rects():
        if abs(CX - x).min() > 200 or abs(CY - y).min() > 200: continue
        c, s = rot(yaw)
        lx = (CX - x) * c + (CY - y) * s; ly = -(CX - x) * s + (CY - y) * c
        m = r * 0.71 + 2.0      # the whole cell (any orientation) inside the interior
        cut |= (np.abs(lx) < hl - m) & (np.abs(ly) < hw - m)
    return cut


def tunnels():
    rng = np.random.RandomState(4104)
    t = tunnel_plan()
    gx, gy, occ, openc, FZ, CZ, TZ = t['gx'], t['gy'], t['occ'], t['open'], t['FZ'], t['CZ'], t['TZ']
    nx, ny = occ.shape
    vid = {}; verts = []
    def V(i, j, lvl):
        k = (i, j, lvl)
        if k not in vid:
            vid[k] = len(verts); verts.append((gx[i], gy[j], (FZ, CZ, TZ)[lvl][i, j]))
        return vid[k]
    faces, mats = [], []
    for i, j in zip(*np.nonzero(occ)):
        op = openc[i, j]
        faces.append([V(i, j, 0), V(i + 1, j, 0), V(i + 1, j + 1, 0), V(i, j + 1, 0)]); mats.append(MUD)
        if not op:
            faces.append([V(i, j, 1), V(i, j + 1, 1), V(i + 1, j + 1, 1), V(i + 1, j, 1)]); mats.append(DIRT)
        for (a, b, ni, nj) in (((i, j), (i + 1, j), i, j - 1), ((i + 1, j), (i + 1, j + 1), i + 1, j),
                               ((i + 1, j + 1), (i, j + 1), i, j + 1), ((i, j + 1), (i, j), i - 1, j)):
            inside = 0 <= ni < nx and 0 <= nj < ny and occ[ni, nj]
            if inside and (not op or openc[ni, nj]): continue
            lo, hi = (1, 2) if inside else (0, 2 if op else 1)        # open cell next to a roofed one: a lintel from its roof to the ground
            faces.append([V(b[0], b[1], lo), V(a[0], a[1], lo), V(a[0], a[1], hi), V(b[0], b[1], hi)]); mats.append(DIRT)
    vmesh.mesh_node(vmesh.polymesh_open(verts, faces, mats), W.group, bake=True, shadows=True)
    for (x, y, z) in t['lamps']: W.lamp(x, y, z, 380, rng_=170.0)
    ch = L.TUNNEL_CHAMBER; fch = t['f_ch']
    for dx, dy in ((-50, 30), (50, -30)): W.lamp(ch[0] + dx, ch[1] + dy, fch + TUN_CH_H - 16, 620, '255 180 104', 190.0)
    # the chamber: caches, cots, a radio table; placed on the floor (z given: the terrain above is not their ground)
    def tp(name, dx, dy, yaw, n=1):
        x, y = ch[0] + dx, ch[1] + dy
        for k in range(n):
            lo, hi = W.B(S.mv(name))
            W.prop(name, x, y, fch + k * hi[2], yaw + rng.uniform(-5, 5), check=k == 0, pad=1.0, tag='tunnel')
    for (nm, dx, dy, yaw, n) in (('rocket_crate', -70, 60, 20, 2), ('rocket_crate', -78, 12, 95, 1), ('ammo_crate', 60, 70, 0, 3), ('ammo_crate', 84, 40, 80, 2),
                                 ('rice_basket', 20, 88, 0, 1), ('rice_basket', -14, 92, 0, 1), ('water_jar', -88, -30, 0, 1), ('cot', 70, -40, 60, 1),
                                 ('cot', 30, -78, 20, 1), ('plot_table_t', -30, -70, 200, 1), ('radio_prc25', 96, 0, 0, 1), ('rucksack', -50, -40, 0, 1),
                                 ('ammo_can', 40, 20, 30, 1), ('jerry_can', -96, 30, 0, 1)):
        tp(nm, dx, dy, yaw, n)
    # portals: an arch where the roof starts, vines over it, the leash target inside the mouth
    for k, m in enumerate(t['mouths']):
        W.sites['tunnels'].append(m['inside'])
        W.keep(m['pos'][0], m['pos'][1], 70.0, name='tunnel')
        if m['arch'] is not None:
            ax, ay, az, yaw = m['arch']
            a = P.arch((ax, ay, az - 2.0), 2 * L.TUNNEL_HW - 6.0, TUN_H - 2.0, 14.0, thickness=12.0, segments=8, axis='y', mat=DIRT)
            W.shape(P.rotate_z(a, yaw - 90.0, (ax, ay, 0.0)), smoothing=50.0)
            W.keep(ax, ay, 60.0, name='tunnel')
    # keep trees and dressing off the open cuts
    for i, j in zip(*np.nonzero(openc[::2, ::2])):
        W.keep(gx[2 * i] + 16, gy[2 * j] + 16, 30.0, z=float(TZ[2 * i, 2 * j]), name='tunnel')
    x0, y0, z0, x1, y1, z1 = t['box']
    W.clone('env_combined_light_probe_volume', ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), box_mins='%g %g %g' % (-(x1 - x0) / 2, -(y1 - y0) / 2, -(z1 - z0) / 2 - 8),
            box_maxs='%g %g %g' % ((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2 + 8), voxel_size='32.0', targetname='tunnel_probe', indoor_outdoor_level='2')
    G.hint((x0, y0, z0 - 16, x1, y1, z1 + 8), 'Low', W.group)
    print('tunnels: %d cells (%d open), %d faces, %d lamps, %d terrain holes' % (occ.sum(), openc.sum(), len(faces), len(t['lamps']) + 2, len(t['holes'])))


# ================================================================ CT firebase
def firebase():
    rng = np.random.RandomState(4101)
    fb = L.firebase(); c = fb['centre']; z = fb['z']; wr = fb['wire_r']
    ang = lambda p: math.degrees(math.atan2(p[1] - c[1], p[0] - c[0]))
    # keep-outs first: track, pads, pits, spawns
    W.keep_path(fb['road_in'], 62.0, name='track')
    for p in fb['pads']:
        W.keep(p[0], p[1], 225.0, name='pad')
        for t in range(-180, 401, 90): W.keep(*local(p[0], p[1], fb['pad_yaw'], -float(t), 0.0), 118.0, name='pad')      # the parked Apache, nose to tail
    for p in fb['guns']: W.keep(p[0], p[1], fb['pit_r'] - 12.0, name='pit')
    for p in fb['spawns']: W.keep(p[0], p[1], 26.0, name='spawn')
    W.keep(fb['fuel'][0], fb['fuel'][1], 185.0, name='fuel'); W.keep(fb['tower'][0], fb['tower'][1], 135.0, name='tower')
    rx, ry = fb['rack']
    W.prop('arms_rack_ct', rx, ry, None, 90.0); W.sites['kit']['ct'] = (rx, ry, gz(rx, ry))
    # ---- bunkers on the wall ring, an M2 nest beside three of them
    gaps = [(fb['gate_angle'], 6.2, 'gate'), (4.0, 3.3, 'sally'), (236.0, 3.3, 'sally')]
    for i, (p, a) in enumerate(zip(fb['bunkers'], fb['bunker_angles'])):
        big = i in fb['m2']
        W.prop('bunker_large' if big else 'bunker_small', p[0], p[1], gz(*p), a)
        gaps.append((a, 8.6 if big else 7.6, 'bunker'))
        if big:
            na = a + (13.5 if abs((a + 13.5 - fb['gate_angle'] + 180) % 360 - 180) > 14.0 else -13.5); nx_, ny_ = L.pol(c, wr - 6.0, na)
            gaps.append((na, 3.6, 'nest'))
            W.prop('m3_tripod', nx_, ny_, None, na)
            W.sites['mounts'].append(dict(kind='m2', team='ct', pos=(nx_, ny_, gz(nx_, ny_) + 30.0), yaw=na, seat=L.pol(c, wr - 62.0, na)))
            W.bag_arc(nx_, ny_, 52.0, na - 78, na + 78, layers=1, model='sandbag_low')
            W.keep(*L.pol(c, wr - 62.0, na), 24.0, name='seat')
            for k_ in range(2): W.prop('ammo_can', *L.pol((nx_, ny_), 30.0, na + 150 + 60 * k_), None, rng.uniform(0, 360), check=True)
    # ---- the perimeter: three layers of sandbags with a player clip above, open at the gate and two sally gaps
    gaps.sort()
    def in_gap(th):
        return any(abs((th - a + 180) % 360 - 180) < w for a, w, _ in gaps)
    step = 0.5; th = 0.0; runs = []; cur = None
    while th < 360.0:
        if not in_gap(th):
            if cur is None: cur = [th, th]
            cur[1] = th
        elif cur is not None: runs.append(cur); cur = None
        th += step
    if cur is not None: runs.append(cur)
    nb = 0
    for a0, a1 in runs:
        if a1 - a0 < 5.0: continue
        W.bag_arc(c[0], c[1], wr, a0, a1 + step, layers=3, model='sandbag_wall_128', seed_rng=rng); nb += 1
    # clip: everywhere except the gate and the sally gaps (the nests and bunkers are not ways in)
    th = 0.0
    while th < 360.0:
        mid = th + 2.0
        if not any(abs((mid - a + 180) % 360 - 180) < w + 0.4 for a, w, kind in gaps if kind in ('gate', 'sally')):
            p = L.pol(c, wr + 14.0, th); q = L.pol(c, wr + 14.0, th + 4.0)
            TER.clip_slab(p, q, z - 30.0, z + 132.0, W.group, t=8.0)
        th += 4.0
    # signs outside the wall
    for a in np.arange(8.0, 360.0, 24.0):
        if in_gap(a): continue
        x, y = L.pol(c, wr + 46.0, a); W.prop('claymore_sign', x, y, None, a + 90 + rng.uniform(-8, 8), check=True)
    for a in np.arange(20.0, 360.0, 45.0):
        x, y = L.pol(c, wr + 150.0, a + rng.uniform(-6, 6)); W.prop('mines_sign', x, y, None, a + 90 + rng.uniform(-10, 10), check=True)
    # ---- gate: the firebase sign, guard post, sandbag stubs
    ga = fb['gate_angle']
    W.prop('fsb_sign', *L.pol(c, wr + 60.0, ga + 7.2), None, ga)
    W.prop('culvert_bunker', *L.pol(c, wr - 170.0, ga - 10.5), None, ga + 90.0, check=True)
    for s in (-1, 1):
        p = L.pol(c, wr - 30.0, ga + s * 6.6); q = L.pol(c, wr - 110.0, ga + s * 7.0)
        W.bag_line(p, q, layers=2)
    for kind, a in (('sally', 4.0), ('sally', 236.0)):        # a blast wall inside each sally gap (walk round it)
        p = L.pol(c, wr - 80.0, a - 3.6); q = L.pol(c, wr - 80.0, a + 3.6); W.bag_line(p, q, layers=3)
    # ---- gun pits: sandbag ring with the entrance toward the base centre; racks and shells outside the entrance
    for k, g in enumerate(fb['guns']):
        ea = math.degrees(math.atan2(c[1] - g[1], c[0] - g[0]))
        W.bag_arc(g[0], g[1], fb['pit_r'], ea + 17.0, ea + 343.0, layers=2, seed_rng=rng)
        yaw = math.degrees(math.atan2(-g[1], -g[0]))           # laid on the middle of the valley
        W.sites['guns']['ct'].append((g[0], g[1], gz(*g), yaw))
        for rr, da in [(rr_, s * a) for rr_ in (66.0, 120.0, 180.0, 240.0) for a in range(26 if rr_ < 100 else 0, 181, 14) for s in (1, -1)]:
            rx, ry = L.pol(g, fb['pit_r'] + rr, ea + da)       # the rack station: the first clear spot outside the ring, nearest the entrance
            if W.prop('ammo_rack_105', rx, ry, None, ea + da + 90.0, check=True, pad=6.0) is not None: break
        else:
            print('WARNING no clear spot for the ammo rack of gun %d: placed at the entrance' % (k + 1)); da = 26.0
            rx, ry = L.pol(g, fb['pit_r'] + 66.0, ea + da); W.prop('ammo_rack_105', rx, ry, None, ea + da + 90.0)
        W.sites['racks']['ct'].append((rx, ry, gz(rx, ry)))
        W.prop('ammo_rack_105', *L.pol(g, fb['pit_r'] + 66.0, ea - da), None, ea - da + 90.0, check=True, pad=6.0)
        for j in range(4):
            sx, sy = L.pol(g, fb['pit_r'] + 52.0 + 9.0 * j, ea - da - 22.0)
            W.prop('shell_105', sx, sy, gz(sx, sy) + 3.0, ea + 38.0 + rng.uniform(-4, 4), check=True)
        clutter(rng, [('ammo_crate', 2), ('ammo_can', 2), ('jerry_can', 1)], *L.pol(g, fb['pit_r'] + 70.0, ea), 20.0, 90.0)
    # ---- FDC bunker, the plotting table in its porch, antennas
    fx, fy = fb['fdc']; fyaw = fb['fdc_yaw']
    W.prop('fdc_bunker', fx, fy, None, fyaw)
    tx, ty = local(fx, fy, fyaw, 106.0, 0.0)
    W.prop('plot_table', tx, ty, None, fyaw + 90.0, reg=False)
    W.sites['board']['ct'] = dict(pos=(tx, ty, gz(tx, ty)), yaw=fyaw, seats=[local(fx, fy, fyaw, 215.0 + 44.0 * (j // 3), -60.0 + 60.0 * (j % 3)) for j in range(6)])
    for s_ in W.sites['board']['ct']['seats']: W.keep(s_[0], s_[1], 22.0, name='seat')
    W.prop('antenna_mast', *local(fx, fy, fyaw, -40.0, 190.0), None, fyaw + 30.0, check=True)
    # ---- ammo point: CONEXes and crate stacks behind a low wall
    ax, ay = fb['ammo']
    W.prop('conex', ax, ay, None, 200.0); W.prop('conex', ax + 6, ay + 88, None, 196.0)
    for (dx, dy, n) in ((-90, 0, 3), (-92, 46, 2), (-88, 92, 3), (-140, 30, 2)): W.stack('ammo_crate', ax + dx, ay + dy, rng.uniform(-10, 10), n, jitter=rng)
    W.bag_line((ax - 180, ay - 90), (ax - 180, ay + 140), layers=2); W.bag_line((ax - 140, ay - 96), (ax + 70, ay - 96), layers=2)
    clutter(rng, [('ammo_can', 4), ('jerry_can', 2), ('drum_od', 2)], ax - 80, ay + 40, 30.0, 150.0)
    # ---- pads: PSP planking, the pad sign; helicopters come with the entities
    for k, (p, a) in enumerate(zip(fb['pads'], fb['pad_angles'])):
        W.prop('psp_pad', p[0], p[1], gz(*p) + 0.5, a, scale=fb['pad_scale'], reg=False)
        W.sites['pads']['ct'].append((p[0], p[1], gz(*p) + 2.0))
        W.prop('lz_sign', *L.pol(p, 300.0, a + 180.0 + 38.0), None, a + 90.0, check=True)
    # ---- TOC and crew tents, antennas, cots and kit
    tx, ty = fb['toc']
    W.prop('gp_tent', tx, ty, None, fb['toc_yaw'])
    W.prop('antenna_mast', *local(tx, ty, fb['toc_yaw'], -150.0, 240.0), None, 15.0, check=True)
    W.prop('antenna_mast', *local(tx, ty, fb['toc_yaw'], 120.0, 250.0), None, 70.0, check=True)
    for (p, yw) in zip(fb['tents'], fb['tent_yaws']):
        if W.prop('gp_tent', p[0], p[1], None, yw, check=True, pad=4.0) is None: continue
        fx_, fy_ = local(p[0], p[1], yw, 250.0, 0.0)
        clutter(rng, [('cot', 2), ('rucksack', 3), ('jerry_can', 2), ('ammo_can', 2), ('drum_od', 1)], fx_, fy_, 10.0, 110.0)
    # ---- tower with its ladder (the ladder side faces the base centre)
    tx, ty = fb['tower']; ta = ang((tx, ty))
    W.prop('guard_tower', tx, ty, None, ta)
    lx, ly = local(tx, ty, ta, -103.0, 0.0); c_, s_ = rot(ta)
    Rm = np.array([[c_, -s_, 0], [s_, c_, 0], [0, 0, 1.0]])
    vmesh.mesh_node(vmesh.oriented_box_mesh((lx, ly, z + 158.0), (9.0, 15.0, 156.0), Rm, LADDER), W.group, bake=False, shadows=False, visexclude=True)
    W.keep(*local(tx, ty, ta, -140.0, 0.0), 40.0, name='ladder')
    # ---- the quad .50 in its own sandbag ring (the gun part is an entity)
    qx, qy = fb['quad50']; qa = ang((qx, qy))
    W.prop('quad50_mount', qx, qy, None, qa)
    W.bag_arc(qx, qy, 118.0, qa + 200.0 + 0.0, qa + 520.0, layers=2, seed_rng=rng)           # open toward the centre
    W.sites['mounts'].append(dict(kind='quad50', team='ct', pos=(qx, qy, gz(qx, qy) + 66.0), yaw=qa, seat=local(qx, qy, qa, -150.0, 0.0)))
    W.keep(*local(qx, qy, qa, -150.0, 0.0), 24.0, name='seat')
    # ---- fuel point: two bladders in a sandbag revetment, drums
    ux, uy = fb['fuel']; ua = ang((ux, uy))
    W.prop('fuel_bladder', ux, uy, None, ua + 90.0)
    for (dx, dy) in ((-150, -110), (-160, 20), (-150, 110)):
        W.prop('drum_stack', *local(ux, uy, ua, dx, dy), None, ua + rng.uniform(-30, 30), check=True)
    clutter(rng, [('drum_od', 5), ('drum_rust', 3), ('jerry_can', 4)], *local(ux, uy, ua, -130.0, 0.0), 20.0, 150.0)
    # ---- arms rack (kit station) at the deploy point, water, latrine, odds and ends
    rx, ry = fb['rack']
    W.prop('water_trailer', *L.pol(c, 1010.0, 300.0), None, 30.0, check=True)
    W.prop('latrine', *L.pol(c, 1000.0, 228.0), None, 48.0, check=True)
    W.prop('latrine', *L.pol(c, 1000.0, 12.0), None, 190.0, check=True)
    for a in (70.0, 118.0, 200.0, 255.0, 345.0):
        clutter(rng, [('drum_od', 1), ('ammo_crate', 1), ('rucksack', 1), ('jerry_can', 1), ('drum_rust', 1)], *L.pol(c, 940.0, a), 10.0, 90.0)
    clutter(rng, [('ammo_crate', 3), ('rucksack', 4), ('ammo_can', 4), ('radio_prc25', 1)], rx, ry, 150.0, 260.0)
    W.particle(*L.pol(c, 1000.0, 228.0), z + 40.0, SMOKESTACK)        # the burn barrel behind the latrine
    W.sites['seeds'] += [(c[0], c[1]), fb['rack']]
    G.lmres_box((c[0] - 200, c[1] - 200, z, c[0] + 200, c[1] + 200, z + 160), W.group)
    print('firebase: %d wall runs, %d mounts' % (nb, len(W.sites['mounts'])))


# ================================================================ T camp
def camp():
    rng = np.random.RandomState(4102)
    cp = L.camp(); c = cp['centre']; z = cp['z']
    road = L.ROADS[1][1]
    W.keep_path([road[-2], road[-1]], 66.0, name='road')
    for p in cp['spawns']: W.keep(p[0], p[1], 26.0, name='spawn')
    rx, ry = cp['rack']
    W.prop('arms_rack_t', rx, ry, None, 0.0); W.sites['kit']['t'] = (rx, ry, gz(rx, ry))
    # ---- helicopter stands under camouflage nets (the nets are scaled to clear a Hip and its rotor)
    lo, hi = W.B(S.mv('heli_hip')); nlo, nhi = W.B(S.mv('camo_net'))
    for k, p in enumerate(cp['pads']):
        mx, my = local(p[0], p[1], cp['pad_yaw'], (lo[0] + hi[0]) / 2, 0.0)
        sx = 1040.0 / (nhi[0] - nlo[0]); sy = 760.0 / (nhi[1] - nlo[1]); sz = 236.0 / nhi[2]
        W.prop('camo_net', mx, my, None, cp['pad_yaw'], scale=(sx, sy, sz), reg=False)
        W.sites['pads']['t'].append((p[0], p[1], gz(*p) + 1.0))
        for dx in np.arange(lo[0] + 60, hi[0], 130.0): W.keep(*local(p[0], p[1], cp['pad_yaw'], dx, 0.0), 120.0, name='pad')
        W.keep(*local(p[0], p[1], cp['pad_yaw'], -30.0, 0.0), 400.0, name='pad')        # nothing tall under the rotor disc
        clutter(rng, [('drum_rust', 2), ('jerry_can', 2), ('rocket_crate', 1)], *local(p[0], p[1], cp['pad_yaw'], 120.0, 300.0), 10.0, 80.0)
    # ---- rocket pits: earth berm open toward the camp centre, crates at the entrance
    for k, g in enumerate(cp['rockets']):
        ea = math.degrees(math.atan2(c[1] - g[1], c[0] - g[0]))
        W.keep(g[0], g[1], cp['pit_r'] - 14.0, name='pit')
        W.berm_arc(g[0], g[1], cp['pit_r'] + 26.0, ea + 32.0, ea + 328.0)
        yaw = math.degrees(math.atan2(-g[1], -g[0]))
        W.sites['guns']['t'].append((g[0], g[1], gz(*g), yaw))
        rx, ry = L.pol(g, cp['pit_r'] + 66.0, ea + 44.0)
        W.stack('rocket_crate', rx, ry, ea + 100.0, 2, check=False)
        W.sites['racks']['t'].append((rx, ry, gz(rx, ry)))
        W.prop('rocket_crate', *L.pol(g, cp['pit_r'] + 70.0, ea - 44.0), None, ea + rng.uniform(40, 80), check=True)
    # ---- AA pits: DShK mount in a small berm
    for k, a in enumerate(cp['aa']):
        ea = math.degrees(math.atan2(c[1] - a[1], c[0] - a[0])); yaw = ea + 180.0
        W.berm_arc(a[0], a[1], 112.0, ea + 36.0, ea + 324.0, base=48.0, top=16.0, h=30.0)
        W.prop('dshk_mount', a[0], a[1], None, yaw)
        W.sites['mounts'].append(dict(kind='dshk', team='t', pos=(a[0], a[1], gz(*a) + 58.0), yaw=yaw, seat=local(a[0], a[1], yaw, -86.0, 0.0)))
        W.keep(a[0], a[1], 84.0, name='pit')
        clutter(rng, [('ammo_can', 2), ('ammo_crate', 1)], a[0], a[1], 120.0, 170.0)
    # ---- the FDC hut with the plotting table, hooches, the arms rack
    fx, fy = cp['fdc']; fyaw = cp['fdc_yaw']
    W.prop('camp_hut', fx, fy, None, fyaw)
    tx, ty = local(fx, fy, fyaw, -40.0, 0.0)
    W.prop('plot_table_t', tx, ty, None, fyaw + 90.0, reg=False)
    W.sites['board']['t'] = dict(pos=(tx, ty, gz(tx, ty)), yaw=fyaw, seats=[local(fx, fy, fyaw, 196.0 + 46.0 * (j // 4), -90.0 + 60.0 * (j % 4)) for j in range(8)])
    for s_ in W.sites['board']['t']['seats']: W.keep(s_[0], s_[1], 22.0, name='seat')
    for k, (hx, hy, hyaw) in enumerate(cp['hooches']):
        nm = ('hooch_a', 'hooch_c', 'hooch_b')[k % 3]
        if W.prop(nm, hx, hy, None, hyaw, fit='min', check=True, pad=4.0) is None: continue
        dx, dy = local(hx, hy, hyaw, 225.0, 0.0)
        clutter(rng, [('rice_basket', 2), ('water_jar', 1), ('rucksack', 1), ('ammo_crate', 1)], dx, dy, 10.0, 80.0)
    # ---- ammo point, cook fires, propaganda, caches
    ax, ay = cp['ammo']
    for (dx, dy, n) in ((0, 0, 3), (60, -30, 2), (-50, 40, 2), (20, 70, 1)): W.stack('rocket_crate', ax + dx, ay + dy, rng.uniform(0, 180), n, jitter=rng)
    clutter(rng, [('ammo_crate', 4), ('ammo_can', 3), ('rice_basket', 2)], ax, ay, 60.0, 130.0)
    for (dx, dy) in ((-20, 270), (420, 300), (-430, 560)):
        x, y = c[0] + dx, c[1] + dy
        if W.prop('cook_fire', x, y, None, rng.uniform(0, 360), check=True, pad=6.0) is None: continue
        W.particle(x, y, gz(x, y) + 10.0, FIRE); W.sites['fires'].append((x, y, gz(x, y) + 10.0))
        clutter(rng, [('rice_basket', 2), ('water_jar', 2), ('log_fallen', 1)], x, y, 60.0, 130.0)
    for (dx, dy, yaw) in ((150, -30, 80.0), (-300, 330, 20.0), (700, -80, 170.0)):
        W.prop('propaganda_board', c[0] + dx, c[1] + dy, None, yaw, check=True, pad=4.0)
    for a in (100.0, 200.0, 260.0, 330.0):
        clutter(rng, [('drum_rust', 1), ('rocket_crate', 1), ('rucksack', 2), ('rice_basket', 1), ('bamboo_fence', 1)], *L.pol(c, 520.0, a), 20.0, 120.0)
    # ---- punji stakes beside the approaches (never on the path itself)
    n = 0
    for pts in (L.ROADS[1][1][-3:], L.ROADS[6][1][:3]):
        Pp = np.array(pts, float)
        for a, b in zip(Pp[:-1], Pp[1:]):
            d = np.linalg.norm(b - a); u = (b - a) / d; nrm = np.array([-u[1], u[0]])
            for t in np.arange(120.0, d - 60.0, 210.0):
                q = a + u * t + nrm * rng.choice([-1, 1]) * rng.uniform(110, 190)
                if math.hypot(q[0] - c[0], q[1] - c[1]) < L.T_PLATEAU_R - 60.0 or float(L.slope(q[0], q[1])) > 18.0: continue
                if W.prop('punji_stakes', q[0], q[1], None, rng.uniform(0, 360), check=True, pad=10.0, solid='0') is not None: n += 1
    W.sites['seeds'] += [(c[0], c[1]), cp['rack']]
    print('camp: %d punji patches' % n)


# ================================================================ flags
def flag_site(letter, px, py, pz=None, crate=None, crate_yaw=0.0, yaw=0.0):
    """the flag pole spot (the pole itself is a prop_dynamic made with the entities) and the supply crate kit station"""
    pz = gz(px, py) if pz is None else pz
    W.sites['flagpole'][letter] = (px, py, pz, yaw)
    W.PL.add(W.PL.footprint(S.mv('flag_pole'), px, py, pz, yaw))
    if crate is not None:
        cz = gz(*crate) if len(crate) < 3 else crate[2]
        W.prop('supply_crate', crate[0], crate[1], cz, crate_yaw, tag='platform')
        W.sites['kit'][letter] = (crate[0], crate[1], cz)
    for p in L.flag_spawns(letter): W.keep(p[0], p[1], 26.0, z=surf_z(p[0], p[1]), name='spawn')


def surf_z(x, y):
    """the walkable surface at a point: a platform top if one covers it, else the ground"""
    z = gz(x, y)
    for (x0, y0, x1, y1, zt) in W.sites['surfaces']:
        if x0 <= x <= x1 and y0 <= y <= y1: z = max(z, zt)
    return z


def paddies():
    rng = np.random.RandomState(4111)
    fx, fy = L.FLAGS[0][2]
    flag_site('a', fx, fy, crate=(fx + 120.0, fy - 4.0), crate_yaw=0.0)
    clutter(rng, [('rice_basket', 3), ('ammo_crate', 1)], fx, fy, 60.0, 110.0)
    # the farm on its terrace south of the paddies
    c = L.FARM
    farm = ((-170, 90, -40.0, 'hooch_a'), (170, 110, 215.0, 'hooch_b'), (60, -230, 95.0, 'hooch_c'))
    for (dx, dy, yaw, nm) in farm: W.prop(nm, c[0] + dx, c[1] + dy, None, yaw, fit='min')
    for (dx, dy, yaw, nm) in farm:
        clutter(rng, [('rice_basket', 2), ('water_jar', 2)], *local(c[0] + dx, c[1] + dy, yaw, 225.0, 0.0), 10.0, 60.0)
    W.prop('pig_pen', c[0] - 230, c[1] - 150, None, 20.0, fit='min', check=True)
    W.prop('pig_pen', c[0] + 250, c[1] - 120, None, 100.0, fit='min', check=True)
    W.prop('ox_cart', c[0] + 40, c[1] + 40, None, 150.0, check=True)
    W.prop('well', c[0] - 20, c[1] + 220, None, 10.0, check=True)
    for (dx, dy) in ((-60, -60), (210, 0), (-260, 30), (120, 250)): W.prop('haystack', c[0] + dx, c[1] + dy, None, rng.uniform(0, 360), check=True, pad=4.0)
    for (dx, dy, yaw) in ((-110, 240, 10.0), (240, 230, 80.0), (-300, -40, 95.0)): W.prop('drying_rack', c[0] + dx, c[1] + dy, None, yaw, check=True, pad=4.0)
    for a in np.arange(200.0, 345.0, 24.0):                       # a fence round the south side of the yard
        x, y = L.pol(c, 318.0, a); W.prop('bamboo_fence', x, y, None, a + 90.0, fit='min', check=True)
    W.particle(c[0] + 40, c[1] + 130, gz(c[0] + 40, c[1] + 130) + 8.0, FIRE) if W.prop('cook_fire', c[0] + 40, c[1] + 130, None, 0.0, check=True, pad=4.0) else None
    clutter(rng, [('rice_basket', 5), ('water_jar', 4), ('fish_trap', 3)], c[0], c[1], 60.0, 300.0)
    # a sunken sampan in the oxbow, fish traps on the dikes, a sampan on the river bank north of A
    ox, oy = L.OXBOW[2]
    W.prop('sampan_open', ox, oy, L.WATER_Z - 20.0, 25.0, roll=24.0, pitch=6.0, tag='water')
    sx = fx + 240.0; sy = float(L.river_y(sx)) - L.RIVER_HW + 30.0
    W.prop('sampan', sx, sy, L.WATER_Z - 8.0, math.degrees(math.atan2(*L.river_dir(sx)[::-1])), tag='water')
    W.sites['seeds'] += [(fx, fy - 60.0), c]
    W.sites['nonav'] += []


def bridge():
    rng = np.random.RandomState(4112)
    bx, by = L.BRIDGE_X, L.BRIDGE_Y; dz = L.BRIDGE_DECK_Z; half = L.BRIDGE_LEN / 2; ramp = L.BRIDGE_RAMP
    lo, hi = W.B(S.mv('truss_span')); wdeck = min(hi[1] - lo[1], 200.0)
    for s in (-1, 1):
        W.prop('truss_span', bx, by + s * half / 2, dz, 90.0, tag='bridge')
        # abutment + approach ramp (world geometry): the ramp runs from the road up to the deck, a retaining block under it
        y_in = by + s * half; y_out = by + s * (half + ramp)
        g_out = gz(bx, y_out) - 3.0
        ya, yb = min(y_in, y_out), max(y_in, y_out)
        W.shape(P.wedge((bx - wdeck / 2, ya, g_out), (bx + wdeck / 2, yb, dz), rise='-y' if s > 0 else '+y', mat=DIRT))
        W.shape(P.box((bx - wdeck / 2, ya, g_out - 70.0), (bx + wdeck / 2, yb, g_out), mat=CONCRETE))
        W.shape(P.box((bx - wdeck / 2 - 16, min(y_in, y_in - s * 34), g_out - 70.0), (bx + wdeck / 2 + 16, max(y_in, y_in - s * 34), dz - 0.5), mat=CONCRETE))
        W.keep_path([(bx, y_in), (bx, y_out + s * 120.0)], wdeck / 2 + 10.0, name='ramp')
        # a sandbag chicane at the foot of the ramp
        if s < 0:
            W.bag_line((bx - 150, y_out + s * 40), (bx - 20, y_out + s * 40), layers=2)
            W.bag_line((bx + 20, y_out + s * 150), (bx + 150, y_out + s * 150), layers=2)
    W.surface(bx - wdeck / 2, by - half, bx + wdeck / 2, by + half, dz)
    W.prop('bridge_pier', bx, by, dz + lo[2], 90.0, tag='bridge')            # its origin is the bearing seat under the span ends
    flag_site('b', bx + 50.0, by, dz, crate=(bx - 34.0, by - 130.0, dz), crate_yaw=90.0, yaw=90.0)
    # the burnt truck is 135 wide and the deck 160: on the span it would close the bridge, so it sits run off the road at the south ramp
    tx_, ty_ = bx + 210.0, by - half - ramp + 40.0
    if W.prop('truck_wreck', tx_, ty_, None, 62.0, fit='min', check=True, pad=4.0) is not None: W.particle(tx_, ty_, gz(tx_, ty_) + 70.0, SMOKE_DARK)
    # south head: the French bunker and the neutral M2; north head: the shot-up checkpoint
    name, kind, (mx, my), myaw = L.mounted_guns()[0]
    W.prop('french_bunker', bx - 300.0, by - half - 150.0, None, 90.0, fit='min')
    W.prop('m3_tripod', mx, my, None, myaw)
    W.bag_arc(mx, my, 56.0, myaw - 80, myaw + 80, layers=1, model='sandbag_low')
    W.sites['mounts'].append(dict(kind='m2', team='any', pos=(mx, my, gz(mx, my) + 30.0), yaw=myaw, seat=local(mx, my, myaw, -58.0, 0.0)))
    W.keep(*local(mx, my, myaw, -58.0, 0.0), 24.0, name='seat')
    W.prop('checkpoint', bx, by + half + ramp + 150.0, None, 90.0, fit='min')
    W.prop('m113_hulk', bx - 300.0, by + half + 250.0, None, 35.0, fit='min', check=True)
    W.prop('mines_sign', bx + 130.0, by + half + ramp + 240.0, None, 0.0, check=True)
    for s in (-1, 1):
        clutter(rng, [('drum_rust', 2), ('ammo_crate', 2), ('log_fallen', 1), ('rice_basket', 1)], bx + s * 220.0, by + s * (half + ramp), 20.0, 150.0)
    W.sites['seeds'] += [(bx, by - half - ramp - 150.0), (bx, by + half + ramp + 150.0)]


def village():
    rng = np.random.RandomState(4113)
    c = L.VILLAGE
    for k in (1, 5): W.keep_path([c, L.ROADS[k][1][L.ROADS[k][1].index(c) - 1]] if k == 1 else [c, L.ROADS[k][1][1]], 70.0, name='road')
    W.keep_path([c, L.ROADS[1][1][3]], 70.0, name='road')
    flag_site('c', c[0] + 100.0, c[1] + 80.0, crate=(c[0] + 40.0, c[1] + 190.0), crate_yaw=30.0)
    W.prop('well', c[0] - 110.0, c[1] + 110.0, None, 20.0)
    W.prop('school', *L.pol(c, 480.0, 72.0), None, 252.0, fit='o')
    # huts: some face the yard from between the roads, the rest stand along the three roads, gable end to the road
    huts = [(x, y, a + 180.0, nm) for (r, a, nm) in ((450, 22, 'hooch_a'), (450, 114, 'hooch_c'), (450, 208, 'hooch_c'), (455, 236, 'hooch_b'))
            for (x, y) in (L.pol(c, r, a),)]
    legs = [L.ROADS[1][1][1], L.ROADS[1][1][3], L.ROADS[5][1][1]]
    for t, lat in ((350.0, 240.0), (560.0, 240.0), (300.0, 440.0), (470.0, 450.0)):
        for q in legs:
            dq = math.hypot(q[0] - c[0], q[1] - c[1]); ux, uy = (q[0] - c[0]) / dq, (q[1] - c[1]) / dq
            for sd in (1, -1):
                huts.append((c[0] + ux * t - uy * sd * lat, c[1] + uy * t + ux * sd * lat, math.degrees(math.atan2(ux * sd, -uy * sd)) + 180.0,
                             ('hooch_b', 'hooch_a', 'hooch_c')[len(huts) % 3]))
    nh = 0; placed = []
    for (x, y, yaw, nm) in huts:
        yaw += rng.uniform(-8, 8)
        if nh >= 10 or math.hypot(x - c[0], y - c[1]) > 700.0 or W.prop(nm, x, y, None, yaw, fit='min', check=True, pad=4.0) is None: continue
        nh += 1; placed.append((x, y, yaw))
    nh = 0
    for (x, y, yaw) in placed:
        nh += 1
        clutter(rng, [('rice_basket', 2), ('water_jar', 1)], *local(x, y, yaw, 215.0, 0.0), 10.0, 50.0)
        bx_, by_ = local(x, y, yaw, -210.0, 0.0)
        clutter(rng, [(('haystack', 'pig_pen', 'drying_rack')[nh % 3], 1)], bx_, by_, 0.0, 60.0, face=yaw)
        if nh == 3:      # the bombed east side: smoke from a burnt hut
            W.particle(x, y, gz(x, y) + 150.0, SMOKESTACK)
    W.prop('shrine', c[0] + 150.0, c[1] - 250.0, None, 100.0, check=True)
    for k, (dx, dy, yaw) in enumerate(((-120, -210, 80.0), (-150, -330, 85.0), (140, -110, 250.0))):
        W.prop('market_stall', c[0] + dx, c[1] + dy, None, yaw, check=True, pad=4.0)
    W.prop('ox_cart', c[0] - 200.0, c[1] - 40.0, None, 200.0, check=True)
    for a in (40.0, 170.0, 280.0):
        x, y = L.pol(c, 200.0, a)
        if W.prop('cook_fire', x, y, None, rng.uniform(0, 360), check=True, pad=6.0) is not None: W.particle(x, y, gz(x, y) + 10.0, FIRE)
    for a in np.arange(0.0, 360.0, 13.0):                         # broken fence ring at the edge of the terrace
        if rng.uniform() < 0.45: continue
        x, y = L.pol(c, 610.0 + rng.uniform(-14, 14), a)
        W.prop('bamboo_fence', x, y, None, a + 90.0 + rng.uniform(-6, 6), fit='min', check=True, pad=6.0)
    clutter(rng, [('rice_basket', 8), ('water_jar', 6), ('haystack', 3), ('drying_rack', 3), ('fish_trap', 2), ('log_fallen', 2)], c[0], c[1], 120.0, 560.0)
    for a in np.arange(15.0, 360.0, 40.0):                        # palms between the huts
        x, y = L.pol(c, rng.uniform(250, 600), a + rng.uniform(-12, 12)); m = S.PALMS[rng.randint(len(S.PALMS))]
        W.prop(None, x, y, gz(x, y) - 4.0, rng.uniform(0, 360), stock=m, trunk=S.TRUNK[m], check=True, pad=30.0, scale=rng.uniform(0.9, 1.15))
    W.sites['seeds'] += [c]
    print('village: %d hooches' % nh)


def temple():
    rng = np.random.RandomState(4114)
    c = L.TEMPLE; z0 = gz(*c)
    t1, t2 = 28.0, 64.0                                      # terrace tops above the knoll
    # world geometry: the lower terrace (courtyard), the upper terrace (tower base) and stairs on every side
    HT = 340.0
    W.shape(P.box((c[0] - HT, c[1] - HT, z0 - 120), (c[0] + HT, c[1] + HT, z0 + t1), mat=STONE))
    W.shape(P.box((c[0] - 200, c[1] - 76, z0 + t1), (c[0] + 200, c[1] + 316, z0 + t2), mat=STONE))
    W.surface(c[0] - HT, c[1] - HT, c[0] + HT, c[1] + HT, z0 + t1); W.surface(c[0] - 200, c[1] - 76, c[0] + 200, c[1] + 316, z0 + t2)
    run = 64.0
    for (mins, maxs, rise) in (((c[0] - 80, c[1] - HT - run, z0 - 70), (c[0] + 80, c[1] - HT, z0 + t1), '+y'), ((c[0] - 80, c[1] + HT, z0 - 70), (c[0] + 80, c[1] + HT + run, z0 + t1), '-y'),
                               ((c[0] - HT - run, c[1] - 80, z0 - 70), (c[0] - HT, c[1] + 80, z0 + t1), '+x'), ((c[0] + HT, c[1] - 80, z0 - 70), (c[0] + HT + run, c[1] + 80, z0 + t1), '-x')):
        W.shape(P.stairs(mins, maxs, 14, rise=rise, mat=STONE, tread_mat=STONE_TOP))      # 7-u risers; the lower ones are under the knoll
    W.shape(P.stairs((c[0] - 70, c[1] - 76 - 60, z0 + t1), (c[0] + 70, c[1] - 76, z0 + t2), 5, rise='+y', mat=STONE, tread_mat=STONE_TOP))
    W.shape(P.stairs((c[0] + 200, c[1] + 40, z0 + t1), (c[0] + 260, c[1] + 180, z0 + t2), 5, rise='-x', mat=STONE, tread_mat=STONE_TOP))
    for (x0, y0, x1, y1) in ((-80, -404, 80, -340), (-80, 340, 80, 404), (-404, -80, -340, 80), (340, -80, 404, 80), (-70, -136, 70, -76), (200, 40, 260, 180)):
        for x in np.arange(x0 + 20, x1, 40.0):
            for y in np.arange(y0 + 20, y1, 40.0): W.keep(c[0] + x, c[1] + y, 22.0, z=z0, name='stairs')
    zc = z0 + t1; zu = z0 + t2
    W.prop('khmer_tower', c[0], c[1] + 120.0, zu, -90.0, tag='platform')          # its doorway faces the courtyard (south)
    W.prop('khmer_gate', c[0], c[1] - 290.0, zc, -90.0, tag='platform')
    flag_site('d', c[0] - 150.0, c[1] - 180.0, zc, crate=(c[0] - 262.0, c[1] - 150.0, zc), crate_yaw=40.0)
    name, kind, (mx, my), myaw = L.mounted_guns()[1]
    W.prop('dshk_mount', mx, my, zc, myaw, tag='platform')
    W.bag_arc(mx, my, 76.0, myaw - 70, myaw + 70, layers=1, model='sandbag_low', z=zc)
    W.sites['mounts'].append(dict(kind='dshk', team='any', pos=(mx, my, zc + 58.0), yaw=myaw, seat=local(mx, my, myaw, -86.0, 0.0)))
    W.keep(*local(mx, my, myaw, -86.0, 0.0), 24.0, z=zc, name='seat')
    # balustrades along the courtyard edge (gaps at the stairs), guardians at the stairs
    nlo, nhi = W.B(S.mv('naga_balustrade')); bl = nhi[0] - nlo[0]
    nb = 0
    for side, (ux, uy) in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):      # the edge runs along (ux, uy); its outward normal is (uy, -ux)
        ex, ey = uy * (HT - 36.0), -ux * (HT - 36.0)
        for t in (-(HT - 72.0) + bl / 2, (HT - 72.0) - bl / 2):               # one length each side of the stair, up to the corner
            if W.prop('naga_balustrade', c[0] + ex + ux * t, c[1] + ey + uy * t, zc, math.degrees(math.atan2(uy, ux)) + (0.0 if t > 0 else 180.0),
                      tag='platform', check=True) is not None: nb += 1
        for s in (-1, 1):                                                     # lions flanking the head of each outer stair, looking out
            W.prop('guardian_statue', c[0] + ex * 0.84 + ux * s * 100.0, c[1] + ey * 0.84 + uy * s * 100.0, zc,
                   math.degrees(math.atan2(ey, ex)), tag='platform', check=True, pad=2.0)
    # ruin dressing: one fallen lintel in the west court, rubble piles at the foot of the platform outside
    W.prop('lintel_fallen', c[0] - 272.0, c[1] + 170.0, zc, 90.0 + rng.uniform(-8, 8), tag='platform', check=True, pad=2.0)
    for a in (20.0, 70.0, 110.0, 160.0, 200.0, 250.0, 290.0, 340.0):
        x, y = L.pol(c, 500.0 + rng.uniform(0, 40), a + rng.uniform(-8, 8))
        if float(L.slope(x, y)) > 22.0 or gz(x, y) < L.WATER_Z + 30.0: continue
        W.prop(('fallen_blocks', 'lintel_fallen', 'fallen_blocks')[int(a) % 3], x, y, None, rng.uniform(0, 360), fit='min', check=True, pad=4.0)
    for _ in range(26):
        a = rng.uniform(0, 360); r = rng.uniform(500.0, 620.0); x, y = L.pol(c, r, a)
        if gz(x, y) < L.WATER_Z + 20.0: continue
        m = (S.RUBBLE + S.ROCKS + S.ROCKS)[rng.randint(len(S.RUBBLE) + 2 * len(S.ROCKS))]
        lo, hi = W.B(m); sc = rng.uniform(1.0, 1.8)
        W.prop(None, x, y, gz(x, y) - lo[2] * sc * 0.55, rng.uniform(0, 360), stock=m, scale=sc, check=True, pad=4.0, tag='rock')
    for a in (38.0, 128.0, 218.0, 312.0):                         # banyans gripping the corners of the platform
        x, y = L.pol(c, 560.0, a + rng.uniform(-6, 6)); m = S.BANYAN_M[rng.randint(3)]
        if W.prop(None, x, y, gz(x, y) - 6.0, rng.uniform(0, 360), stock=m, trunk=S.TRUNK[m], check=True, pad=20.0) is not None:
            W.prop(None, x, y, gz(x, y) + 4.0, rng.uniform(0, 360), stock=S.ROOTS[0], solid='0', reg=False, tag='roots')
    for _ in range(30):
        a = rng.uniform(0, 360); x, y = L.pol(c, rng.uniform(490.0, 640.0), a); m = S.FERNS[rng.randint(len(S.FERNS))]
        if W.free(x, y, 14.0): W.prop(None, x, y, gz(x, y) - 1.0, rng.uniform(0, 360), stock=m, solid='0', reg=False, scale=rng.uniform(1.0, 1.6))
    W.sites['seeds'] += [(c[0], c[1] - 180.0)]
    W.sites['plat_seed'] = [(c[0] + 120.0, c[1] - 230.0, zc)]


def crash_site():
    rng = np.random.RandomState(4115)
    c = L.CRASH; z = gz(*c)
    road = L.ROADS[0][1]
    W.keep_path([road[4], c, road[6]], 72.0, name='road'); W.keep_path([c, L.ROADS[3][1][1]], 50.0, name='road')
    flag_site('e', c[0] + 60.0, c[1] - 130.0, crate=(c[0] + 190.0, c[1] - 190.0), crate_yaw=60.0)
    # the C-123: fuselage north of the road, a wing torn off behind it, an engine further along the slide, burning
    fx, fy, fyaw = c[0] + 480.0, c[1] + 390.0, 18.0
    W.prop('c123_fuselage', fx, fy, None, fyaw, fit='min')
    W.prop('c123_wing', *local(fx, fy, fyaw, -160.0, 330.0), None, fyaw + 64.0, fit='min', check=True)
    ex, ey = local(fx, fy, fyaw, 470.0, -150.0)
    if W.prop('c123_engine', ex, ey, None, fyaw + 30.0, fit='min', check=True) is not None:
        W.particle(ex, ey, gz(ex, ey) + 30.0, FIRE); W.particle(ex, ey, gz(ex, ey) + 60.0, SMOKE_DARK)
    W.particle(*local(fx, fy, fyaw, -300.0, 0.0), z + 120.0, SMOKESTACK)
    slide = [local(fx, fy, fyaw, t, 0.0) for t in (-900.0, -500.0, 0.0, 500.0)]      # the swath it cut through the trees
    for (dx, dy) in ((-160, -230), (200, -250), (-330, 40), (330, 60), (-60, 480), (420, 330)):
        if W.prop('cargo_pallet', c[0] + dx, c[1] + dy, None, rng.uniform(0, 360), check=True, pad=4.0) is not None and rng.uniform() < 0.7:
            W.prop('parachute_silk', c[0] + dx + rng.uniform(-90, 90), c[1] + dy + rng.uniform(60, 120), None, rng.uniform(0, 360), check=True, solid='0')
    clutter(rng, [('supply_crate', 3), ('ammo_crate', 3), ('drum_od', 2), ('rucksack', 3), ('jerry_can', 2)], c[0], c[1], 90.0, 420.0)
    # the rubber plantation: straight rows over the terrace, gapped along the road and the crash swath
    n = 0; ca, sa = rot(14.0)
    for i in np.arange(-840.0, 841.0, 128.0):
        for j in np.arange(-840.0, 841.0, 92.0):
            x = c[0] + ca * i - sa * j + rng.uniform(-7, 7); y = c[1] + sa * i + ca * j + rng.uniform(-7, 7)
            if math.hypot(x - c[0], y - c[1]) > L.CRASH_R + 200.0 or float(L.slope(x, y)) > 16.0: continue
            if float(L.seg_dist(np.array([x]), np.array([y]), slide)[0][0]) < 150.0: continue
            rd, hw = L.road_dist(np.array([x]), np.array([y]))
            if rd[0] < hw[0] + 60.0: continue
            if W.prop('rubber_tree', x, y, gz(x, y) - 3.0, rng.uniform(0, 360), trunk=S.TRUNK_MV['rubber_tree'], check=True, pad=14.0,
                      scale=rng.uniform(0.92, 1.1)) is not None: n += 1
    W.sites['seeds'] += [(c[0], c[1] - 60.0)]
    print('crash site: %d rubber trees' % n)


# ================================================================ waterfall, marsh, karst, roads, craters
def waterfall():
    rng = np.random.RandomState(4121)
    x = L.FALL_X; y = float(L.river_y(x)); wz = L.UPPER_WATER_Z
    lo, hi = W.B(S.WATER_WALL); wd = hi[0] - lo[0]
    sz = (wz - (L.WATER_Z - 26.0)) / (hi[2] - lo[2])
    for k in range(-3, 4):
        W.prop(None, x + 30.0, y + k * (wd * 1.6 - 4.0), wz - hi[2] * sz, 90.0, stock=S.WATER_WALL, scale=(1.6, 1.0, sz), solid='0', reg=False, tag='water')
    for dy in (-90.0, 90.0):
        W.particle(x + 70.0, y + dy, L.WATER_Z + 4.0, 'particles/water_fx/waterfall_base.vpcf')
    # boulders flanking the fall and in the pool: noise-deformed blocks with the rock / moss blend painted by height
    for (dx, dy, sx, sy, sh, seed) in ((-40, -300, 230, 190, 230, 1), (-30, 310, 250, 180, 260, 2), (120, -260, 150, 130, 120, 3), (150, 270, 140, 150, 110, 4),
                                       (260, -60, 90, 80, 60, 5), (330, 120, 80, 100, 50, 6), (-200, -340, 260, 200, 280, 7), (-210, 350, 240, 220, 300, 8)):
        cx, cy = x + dx, y + dy; zb = min(gz(cx - sx / 2, cy), gz(cx + sx / 2, cy), gz(cx, cy)) - 50.0
        b = ME.noise(ME.subdivide(P.box((cx - sx / 2, cy - sy / 2, zb), (cx + sx / 2, cy + sy / 2, zb + sh + 50.0), mat=TER.BLEND_ROCK), 3), min(sx, sy) * 0.11, 80.0, seed)
        zt = zb + sh + 50.0
        W.shape(b, paint=lambda p, zt=zt, sh=sh: max(0.0, min(1.0, 0.25 + 0.75 * (p[2] - (zt - sh * 0.5)) / (sh * 0.5))), smoothing=70.0)
        W.keep(cx, cy, max(sx, sy) * 0.6, name='boulder')
    for _ in range(40):
        fx, fy = x + rng.uniform(-300, 520), y + rng.choice([-1, 1]) * rng.uniform(230, 520)
        m = (S.FERNS + S.TROPICAL_M)[rng.randint(len(S.FERNS) + 2)]
        if float(L.slope(fx, fy)) < 38.0 and W.free(fx, fy, 14.0): W.prop(None, fx, fy, gz(fx, fy) - 2.0, rng.uniform(0, 360), stock=m, solid='0', reg=False, scale=rng.uniform(1.0, 1.7))
    TER.clip_box(x - 60.0, y - 260.0, L.WATER_Z - 40.0, x - 20.0, y + 260.0, wz + 200.0, W.group)      # nobody climbs the fall
    W.sites['nonav'].append((x - 400.0, y - 500.0, x + 60.0, y + 500.0))


def marsh():
    rng = np.random.RandomState(4122)
    x = 5450.0; y = float(L.river_y(x)) + 150.0
    W.prop('pbr_wreck', x, y, gz(x, y) - 2.0, 200.0)             # its origin is the river bed; the model already lists
    W.particle(x, y, L.WATER_Z + 60.0, SMOKESTACK)
    W.prop('sampan', 5180.0, float(L.river_y(5180.0)) - 190.0, L.WATER_Z - 8.0, 70.0, tag='water')
    n = 0
    for _ in range(900):
        px = rng.uniform(L.MARSH_X0 - 100.0, L.MAP_X - 40.0); py = float(L.river_y(px)) + rng.uniform(-1050, 1050); g = gz(px, py)
        if g < L.WATER_Z - 22.0 or g > L.WATER_Z + 26.0: continue
        if n < 330 and W.free(px, py, 12.0):
            W.prop('reeds', px, py, g - 2.0, rng.uniform(0, 360), solid='0', reg=False, scale=rng.uniform(0.9, 1.4)); n += 1
    nd = 0
    for _ in range(140):
        px = rng.uniform(L.MARSH_X0, L.MAP_X - 80.0); py = float(L.river_y(px)) + rng.uniform(-950, 950); g = gz(px, py)
        if not (L.WATER_Z - 14.0 < g < L.WATER_Z + 40.0) or nd >= 30: continue
        if W.prop('dead_tree', px, py, g - 5.0, rng.uniform(0, 360), trunk=S.TRUNK_MV['dead_tree'], check=True, pad=30.0, scale=rng.uniform(0.8, 1.2)) is not None: nd += 1
    for _ in range(8):
        px = rng.uniform(L.MARSH_X0, L.MAP_X - 200.0); py = float(L.river_y(px)) + rng.uniform(-600, 600)
        if abs(gz(px, py) - L.WATER_Z) < 16.0: W.prop('fish_trap', px, py, max(gz(px, py), L.WATER_Z - 6.0), rng.uniform(0, 360), check=True)
    print('marsh: %d reeds, %d dead trees' % (n, nd))


def karst_dressing():
    """player clips round every tower (cylinders: nobody climbs the walls; the landable crowns stay open) and the sniper nests"""
    rng = np.random.RandomState(4123)
    for kk, (kx, ky, kr, kh, ks) in zip(W.karst, L.KARST):
        land = ks in L.KARST_LANDABLE
        z0 = kk['z0'] + 110.0
        if land:
            W.clip(P.cylinder((kx, ky), kr * 1.13, z0, kk['z0'] + 70.0 + kh * 0.86, sides=16, mat=TER.CLIP))
            cz = kk['top']; rr = kr * 0.5
            zat = lambda d: cz - 20.0 * d / (kr * 0.7) - 1.0
            W.prop('supply_crate', kx, ky, zat(0) - 1.0, rng.uniform(0, 360), tag='karst')
            for a in np.arange(0.0, 360.0, 60.0):
                W.bag_arc(kx, ky, 140.0, a + 6.0, a + 36.0, layers=2, model='sandbag_low', z=zat(140) - 2.0)
            for (nm, dx, dy) in (('radio_prc25', -70, 60), ('rucksack', 80, 50), ('ammo_can', -70, -60), ('ammo_crate', 30, -95)):
                W.prop(nm, kx + dx, ky + dy, zat(math.hypot(dx, dy)), rng.uniform(0, 360), tag='karst')
        else:
            W.clip(P.cylinder((kx, ky), kr * 1.13, z0, kk['top'] + 260.0, sides=16, mat=TER.CLIP))
        W.keep(kx, ky, kr * 1.05, z=kk['z0'], h=kh + 200.0, name='karst')
        W.sites['nonav'].append((kx - kr * 1.3, ky - kr * 1.3, kx + kr * 1.3, ky + kr * 1.3))


def roads_and_craters():
    rng = np.random.RandomState(4124)
    for k, (hw, pts) in enumerate(L.ROADS):
        W.keep_path(pts, hw + 6.0, step=hw * 1.4, name='road')
        if k in (0, 1) and len(pts) > 2: W.sites['seeds'].append(pts[len(pts) // 2])
    # wrecks and signs beside the roads
    for (nm, k, t, off, yaw) in (('truck_wreck', 0, 0.42, 120.0, 30.0), ('m113_hulk', 0, 0.78, -130.0, 100.0), ('truck_wreck', 1, 0.62, 125.0, 200.0),
                                 ('ox_cart', 1, 0.2, -110.0, 80.0), ('m113_hulk', 2, 0.55, 110.0, 310.0)):
        Pp = np.array(L.ROADS[k][1], float); seg = np.linalg.norm(np.diff(Pp, axis=0), axis=1); cum = np.concatenate([[0], np.cumsum(seg)])
        s = t * cum[-1]; i = min(int(np.searchsorted(cum, s) - 1), len(seg) - 1); u = (Pp[i + 1] - Pp[i]) / seg[i]
        q = Pp[i] + u * (s - cum[i]) + np.array([-u[1], u[0]]) * off
        if float(L.slope(q[0], q[1])) < 14.0: W.prop(nm, q[0], q[1], None, yaw, fit='min', check=True, pad=6.0)
    for k, (hw, pts) in enumerate(L.ROADS):
        Pp = np.array(pts, float); seg = np.linalg.norm(np.diff(Pp, axis=0), axis=1)
        for a, b, d in zip(Pp[:-1], Pp[1:], seg):
            u = (b - a) / d; nrm = np.array([-u[1], u[0]])
            for t in np.arange(rng.uniform(150, 300), d, rng.uniform(420, 620)):
                q = a + u * t + nrm * rng.choice([-1, 1]) * (hw + rng.uniform(46, 110))
                if float(L.slope(q[0], q[1])) > 20.0 or gz(q[0], q[1]) < L.WATER_Z + 10.0: continue
                nm = ('log_fallen', 'root_tangle', 'log_fallen', 'drum_rust')[rng.randint(4)]
                W.prop(nm, q[0], q[1], None, rng.uniform(0, 360), check=True, pad=6.0)
    # craters: stones thrown out on the rim, a splintered log in some
    n = 0
    for (cx, cy, r, dep) in L.CRATERS:
        if not L.in_play(cx, cy): continue
        for j in range(3):
            a = rng.uniform(0, 360); x, y = L.pol((cx, cy), r * rng.uniform(1.0, 1.35), a)
            m = S.ROCKS[rng.randint(len(S.ROCKS))]; sc = rng.uniform(1.2, 2.4); lo, hi = W.B(m)
            if W.prop(None, x, y, gz(x, y) - lo[2] * sc * 0.5, rng.uniform(0, 360), stock=m, scale=sc, check=True, pad=4.0, tag='rock') is not None: n += 1
        if rng.uniform() < 0.4:
            x, y = L.pol((cx, cy), r * 1.5, rng.uniform(0, 360))
            if float(L.slope(x, y)) < 18.0: W.prop('log_fallen', x, y, None, rng.uniform(0, 360), check=True, pad=6.0)
    print('roads and craters: %d crater stones' % n)


# ================================================================ the jungle
def jungle():
    rng = np.random.RandomState(4131)
    cnt = dict(canopy=0, under=0, fern=0, grass=0, rice=0, palm=0, bamboo=0)
    XE, YE = L.MAP_X + 380.0, L.MAP_Y + 380.0

    def grid(step, jit=0.42):
        xs = np.arange(-XE, XE, step); ys = np.arange(-YE, YE, step)
        X, Y = np.meshgrid(xs, ys, indexing='ij')
        X = X + rng.uniform(-jit, jit, X.shape) * step; Y = Y + rng.uniform(-jit, jit, Y.shape) * step
        return X.ravel(), Y.ravel()

    def near_play(X, Y):
        d = np.minimum(np.hypot(X - L.CT_BASE[0], Y - L.CT_BASE[1]) - L.CT_FOOT_R, np.hypot(X - L.T_BASE[0], Y - L.T_BASE[1]) - L.T_FOOT_R)
        return (L.water_dist(X, Y) < 3300.0) | (d < 300.0)

    # ---- canopy trees: banyans, tiered: dense where people fight, thinner on the far slopes and beyond the edge
    X, Y = grid(200.0)
    dens = L.jungle(X, Y); sl = L.slope(X, Y); Z = L.height(X, Y)
    rd, hw = L.road_dist(X, Y)
    inside = L.in_play(X, Y)
    fill = 0.30 * (1.0 - L.clearing(X, Y)) * (fbm(X / 700.0, Y / 700.0, 7.7, 2, seed=36) * 0.5 + 0.75)
    p = np.maximum(dens, np.where(inside, fill, 0.0)) * np.where(near_play(X, Y) & inside, 0.95, 0.5)
    ok = (rng.uniform(size=X.shape) < p) & (sl < 30.0) & (Z > L.WATER_Z + 26.0) & (rd > hw + 120.0) & ~L.in_paddies(X, Y)
    for i in np.nonzero(ok)[0]:
        u = rng.uniform(); s_ = float(sl[i])
        if u < 0.13 and s_ < 13.0: m = S.BANYAN_L[0]; sc = rng.uniform(0.8, 1.0)
        elif u < 0.62 and s_ < 22.0: m = S.BANYAN_M[rng.randint(3)]; sc = rng.uniform(0.85, 1.2)
        else: m = S.BANYAN_S[rng.randint(2)]; sc = rng.uniform(0.9, 1.35)
        tr = S.TRUNK[m]
        sink = 5.0 + math.tan(math.radians(s_)) * tr * sc * 0.6
        if W.prop(None, float(X[i]), float(Y[i]), float(Z[i]) - min(sink, 8.0) if sink <= 8.0 else float(Z[i]) - sink, rng.uniform(0, 360), stock=m, trunk=tr,
                  check=True, pad=22.0, scale=sc, tag='tree' if sink > 8.0 else None) is not None: cnt['canopy'] += 1
    # ---- palms along the river banks
    for x in np.arange(-5400.0, 4950.0, 150.0):
        for s in (-1, 1):
            if rng.uniform() > 0.5 or abs(x - L.BRIDGE_X) < 420.0: continue
            px = x + rng.uniform(-60, 60); py = float(L.river_y(px)) + s * (L.BANK_W + rng.uniform(30, 190))
            if L.in_paddies(np.array([px]), np.array([py]))[0] or gz(px, py) < L.WATER_Z + 20.0 or float(L.slope(px, py)) > 18.0: continue
            r_, h_ = L.road_dist(np.array([px]), np.array([py]))
            if r_[0] < h_[0] + 50.0: continue
            m = S.PALMS[rng.randint(len(S.PALMS))]
            if W.prop(None, px, py, gz(px, py) - 4.0, rng.uniform(0, 360), stock=m, trunk=S.TRUNK[m], check=True, pad=24.0, scale=rng.uniform(0.85, 1.2)) is not None: cnt['palm'] += 1
            if rng.uniform() < 0.35:
                bx_, by_ = px + rng.uniform(-150, 150), py + s * rng.uniform(40, 160)
                if gz(bx_, by_) > L.WATER_Z + 20.0 and float(L.slope(bx_, by_)) < 16.0 and float(L.clearing(np.array([bx_]), np.array([by_]))[0]) < 0.9:
                    if W.prop('bamboo_clump', bx_, by_, gz(bx_, by_) - 3.0, rng.uniform(0, 360), trunk=S.TRUNK_MV['bamboo_clump'], check=True, pad=20.0,
                              scale=rng.uniform(0.85, 1.2)) is not None: cnt['bamboo'] += 1
    # ---- understorey: tall tropical plants, small palms, yucca and taro under the canopy (walk-through, no collision)
    X, Y = grid(150.0)
    m_ = near_play(X, Y) & L.in_play(X, Y)
    X, Y = X[m_], Y[m_]
    dens = np.maximum(L.jungle(X, Y), 0.25 * (1.0 - L.clearing(X, Y))); sl = L.slope(X, Y); Z = L.height(X, Y)
    ok = (rng.uniform(size=X.shape) < dens * 1.1) & (sl < 34.0) & (Z > L.WATER_Z + 14.0) & ~L.in_paddies(X, Y)
    under = S.TROPICAL_L * 3 + S.TROPICAL_M * 3 + S.PALMS_SMALL + S.YUCCA + S.TARO
    idx = np.nonzero(ok)[0]
    if len(idx) > 2100: idx = rng.choice(idx, 2100, replace=False)
    for i in idx:
        m = under[rng.randint(len(under))]
        if not W.free(float(X[i]), float(Y[i]), 10.0, float(Z[i])): continue
        W.prop(None, float(X[i]), float(Y[i]), float(Z[i]) - 3.0, rng.uniform(0, 360), stock=m, solid='0', reg=False, scale=rng.uniform(0.9, 1.5)); cnt['under'] += 1
    # ---- ferns and small plants: only near where people walk (roads, flags, bases)
    X, Y = grid(105.0)
    rd, hw = L.road_dist(X, Y)
    nf = np.full(X.shape, 1e9)
    for _, _, (fx, fy) in L.FLAGS: nf = np.minimum(nf, np.hypot(X - fx, Y - fy))
    nf = np.minimum(nf, np.minimum(np.hypot(X - L.CT_BASE[0], Y - L.CT_BASE[1]) - 900.0, np.hypot(X - L.T_BASE[0], Y - L.T_BASE[1]) - 300.0))
    m_ = ((rd < 420.0) | (nf < 950.0)) & L.in_play(X, Y)
    X, Y = X[m_], Y[m_]
    dens = L.jungle(X, Y) + 0.25 * (1.0 - L.clearing(X, Y)); sl = L.slope(X, Y); Z = L.height(X, Y)
    ok = (rng.uniform(size=X.shape) < dens * 1.1) & (sl < 36.0) & (Z > L.WATER_Z + 10.0) & ~L.in_paddies(X, Y)
    small = S.FERNS * 2 + S.TROPICAL_S + S.WEEDS
    idx = np.nonzero(ok)[0]
    if len(idx) > 1500: idx = rng.choice(idx, 1500, replace=False)
    for i in idx:
        m = small[rng.randint(len(small))]
        if not W.free(float(X[i]), float(Y[i]), 8.0, float(Z[i])): continue
        W.prop(None, float(X[i]), float(Y[i]), float(Z[i]) - 1.5, rng.uniform(0, 360), stock=m, solid='0', reg=False, scale=rng.uniform(1.0, 1.7)); cnt['fern'] += 1
    # ---- elephant grass fields on the floodplain and terraces (cover from the air)
    X, Y = grid(66.0, jit=0.48)
    m_ = L.in_play(X, Y) & (L.water_dist(X, Y) < 2900.0)
    X, Y = X[m_], Y[m_]
    g = L.grass(X, Y); sl = L.slope(X, Y); Z = L.height(X, Y); rd, hw = L.road_dist(X, Y)
    ok = (g > 0.12) & (rng.uniform(size=X.shape) < np.minimum(1.0, g * 1.7)) & (sl < 20.0) & (Z > L.WATER_Z + 14.0) & (rd > hw + 26.0)
    idx = np.nonzero(ok)[0]
    if len(idx) > 2300: idx = rng.choice(idx, 2300, replace=False)
    for i in idx:
        if not W.free(float(X[i]), float(Y[i]), 20.0, float(Z[i])): continue
        W.prop('elephant_grass_' + 'abc'[rng.randint(3)], float(X[i]), float(Y[i]), float(Z[i]) - 2.0, rng.uniform(0, 360), solid='0', reg=False,
               scale=(rng.uniform(0.9, 1.3),) * 2 + (rng.uniform(0.9, 1.25),)); cnt['grass'] += 1
    # ---- rice in the paddy cells (in the water, off the dikes)
    for (x0, x1, yr0, yr1, cx, cy) in ((L.PADDY_X0, L.PADDY_X1, L.PADDY_YR0, L.PADDY_YR1, L.PADDY_CELL_X, L.PADDY_CELL_Y),
                                       (L.PADDY2_X0, L.PADDY2_X1, L.PADDY2_YR0, L.PADDY2_YR1, L.PADDY2_CELL_X, L.PADDY2_CELL_Y)):
        for x in np.arange(x0 + 20.0, x1 - 19.0, 62.0):
            for yr in np.arange(yr0 + 20.0, yr1 - 19.0, 62.0):
                px = x + rng.uniform(-14, 14); pr = yr + rng.uniform(-14, 14)
                u = (px - x0) / cx % 1.0; v = (pr - yr0) / cy % 1.0
                if min(u, 1 - u) * cx < 56.0 or min(v, 1 - v) * cy < 56.0 or rng.uniform() < 0.12: continue
                py = pr + float(L.river_y(px))
                if not W.free(px, py, 10.0): continue
                W.prop('rice_clump_' + 'ab'[rng.randint(2)], px, py, gz(px, py) - 1.0, rng.uniform(0, 360), solid='0', reg=False, scale=rng.uniform(0.9, 1.25)); cnt['rice'] += 1
    print('jungle:', cnt)
    return cnt


def weather():
    """light rain over the flags and the two bases only (one particle system each), distant lightning as a faint screen flash"""
    spots = [c for _, _, c in L.FLAGS] + [L.CT_BASE, L.T_BASE]
    for k, c in enumerate(spots):
        z = surf_z(c[0], c[1]) + 420.0
        fxkit.weather_tiles(((c[0] - 400.0, c[1] - 400.0, z - 400.0), (c[0] + 400.0, c[1] + 400.0, z)), kind='particles/rain_fx/rain_storm_outer.vpcf' if False else 'rain',
                            name='mv_rain_%d' % (k + 1), tile=1024.0, start=True, group=W.group)
    fxkit.lightning('mv_lightning', (0.0, 0.0, 2600.0), interval=38.0, duration=0.35, thunder=None, start=True, group=W.group, alpha=26)


# ================================================================ build
def build(d, group, out, T, karst, clone):
    global W
    W = World(d, group, out, T, karst, clone)
    roads_keep_first = False
    tunnels()
    firebase()
    camp()
    temple()            # platforms before the flag keep-outs that stand on them
    paddies(); bridge(); village(); crash_site()
    waterfall(); marsh(); karst_dressing()
    roads_and_craters()
    cnt = jungle()
    weather()
    n = sum(W.count.values())
    print('places: %d prop_static (%d models), %d skipped for overlap, %d exceptions; props not built yet: %s' % (
        n, len(W.count), sum(W.skipped.values()), len(W.exc), ', '.join(sorted(W.missing)) or 'none'))
    return W
