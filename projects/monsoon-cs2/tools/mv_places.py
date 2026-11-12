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
import mv_models as M
import terrain_img as TI
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
WOOD = 'materials/de_ancient/hr_ancient_ceiling_wood_01_base.vmat'
BUILDING_KEYS = ('hooch', 'camp_hut', 'school', 'gp_tent', 'fdc_bunker', 'bunker_', 'guard_tower', 'checkpoint', 'french_bunker', 'khmer_tower', 'khmer_gate',
                 'c123_fuselage', 'conex', 'market_stall', 'latrine', 'shrine')       # tools/check_play.py BUILDINGS
LADDER_MODEL = 'models/props/de_aztec/hr_aztec/aztec_scaffolding/aztec_scaffold_ladder_128.vmdl'
for _m in (DIRT, MUD, STONE, STONE_TOP, CONCRETE, WOOD): vmesh.TEX_SIZE[_m] = (1024, 1024)
vmesh.TEX_SIZE[LADDER] = (64, 64)
FIRE = 'particles/burning_fx/env_fire_small.vpcf'
SMOKE_DARK = 'particles/burning_fx/barrel_burning_engine_smoke_dark.vpcf'
SMOKESTACK = 'particles/ambient_fx/ambient_smokestack.vpcf'
PROBED_KEYS = ('foliage', 'palm', 'weeds', 'grass', 'rice_clump', 'reeds', 'bamboo_clump', 'rubber_tree', 'dead_tree', 'vine', 'root', 'camo_net',
               'parachute', 'sandbag', 'ext/rs_')

W = None


def gz(x, y):
    return L.gz(float(x), float(y))


def relief(model, x, y, yaw, sc=1.0):
    """how uneven the ground is under a footprint (max - min at the centre and the four corners)"""
    f = W.PL.footprint(model, x, y, 0.0, yaw, (sc,) * 3)
    c, s_ = math.cos(f['a']), math.sin(f['a']); hx, hy = f['h']
    xs = [f['c'][0]] + [f['c'][0] + c * a * hx - s_ * b * hy for a in (-1, 1) for b in (-1, 1)]
    ys = [f['c'][1]] + [f['c'][1] + s_ * a * hx + c * b * hy for a in (-1, 1) for b in (-1, 1)]
    g = L.height(np.array(xs), np.array(ys)); return float(g.max() - g.min())


def rot(yaw):
    a = math.radians(yaw)
    return math.cos(a), math.sin(a)


def tri_box(T, lo, hi):
    """per triangle of T (N, 3, 3): does it intersect the box lo..hi (separating axis test: 3 box axes, the face normal, 9 edge
    crosses). The same test as tools/check_play.py check 10."""
    lo = np.asarray(lo, float); hi = np.asarray(hi, float)
    c = (lo + hi) / 2; h = (hi - lo) / 2
    V = np.asarray(T, float) - c
    out = np.ones(len(V), bool)
    for a in range(3): out &= ~((V[:, :, a].min(1) > h[a]) | (V[:, :, a].max(1) < -h[a]))
    E = (V[:, 1] - V[:, 0], V[:, 2] - V[:, 1], V[:, 0] - V[:, 2])
    n = np.cross(E[0], E[1])
    out &= np.abs((n * V[:, 0]).sum(1)) <= (np.abs(n) * h).sum(1)
    for e in E:
        for a in range(3):
            ax = np.zeros(3); ax[a] = 1.0
            Lx = np.cross(ax, e)
            p = (V * Lx[:, None, :]).sum(2); rr = (np.abs(Lx) * h).sum(1)
            out &= ~((p.min(1) > rr) | (p.max(1) < -rr))
    return out


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
        self.count = {}; self.skipped = {}; self.exc = []; self.missing = set(); self.big_skips = []; self.rotors = []; self.rotor_skips = {}; self.bld = []
        self.solids = []; self._solid_cat = None
        self.sites = dict(kit={}, flagpole={}, mounts=[], racks=dict(ct=[], t=[]), board={}, guns=dict(ct=[], t=[]), pads=dict(ct=[], t=[]),
                          tunnels=[], surfaces=[], fires=[], nonav=[], seeds=[], waypoints=[], landing=[])

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
        hit = self.PL.hits(f) if check else None
        tree_like = trunk is not None or any(k in model for k in ('banyan', 'palm', 'tree', 'bamboo', 'mangrove', 'nypa'))
        if hit is None and tree_like and '_roots' not in model and self.bld:
            lo_, hi_ = self.B(model); cr_ = 0.8 * 0.3 * max(hi_[0] - lo_[0], hi_[1] - lo_[1]) * sc[0]
            for b_ in self.bld:                                  # 12 Nov review: no crown through a roof (check_play check 6)
                if abs(b_['c'][0] - x) > cr_ + 400.0 or abs(b_['c'][1] - y) > cr_ + 400.0: continue
                c_, s_ = math.cos(b_['a']), math.sin(b_['a']); dx_, dy_ = x - b_['c'][0], y - b_['c'][1]
                u_, v_ = dx_ * c_ + dy_ * s_, -dx_ * s_ + dy_ * c_
                if math.hypot(max(abs(u_) - b_['h'][0], 0.0), max(abs(v_) - b_['h'][1], 0.0)) < cr_: hit = b_; break
        if hit is None and self.rotors and not model.endswith(('psp_pad.vmdl',)) and tag != 'heli':
            crown = None
            if tree_like:
                lo_, hi_ = self.B(model); crown = 0.3 * max(hi_[0] - lo_[0], hi_[1] - lo_[1]) * sc[0]
            r_ = self.in_rotor(f if crown is None else dict(f, c=(x, y)), f['z'][1], crown)
            if r_ is not None:                                  # 12 Nov review: nothing over 24 u in a rotor cylinder, required or not
                self.rotor_skips[model.split('/')[-1][:-5]] = self.rotor_skips.get(model.split('/')[-1][:-5], 0) + 1
                return None
        if hit is not None:
            self.skipped[model] = self.skipped.get(model, 0) + 1
            if max(f['h']) > 95.0 and trunk is None and not kw.get('_quiet'):       # a building or vehicle that did not fit: say what was in the way
                self.big_skips.append('%s at (%.0f, %.0f) blocked by %s at (%.0f, %.0f)' % (model.split('/')[-1][:-5], x, y, hit['model'].split('/')[-1][:-5], hit['c'][0], hit['c'][1]))
            return None
        kw.pop('_quiet', None)
        if any(k in model for k in BUILDING_KEYS): self.bld.append(f)
        if model.endswith('/pig_pen.vmdl'): self.clip_footprint(f)          # pass 2 review: the pens were stuck pockets (step in over the trough, no way out)
        if model.endswith(('/hooch_a.vmdl', '/hooch_b.vmdl', '/hooch_c.vmdl')): self.clip_footprint(f, h=320.0)    # pass 3 review: a hut roof was a stuck pocket
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
        self.last_z = z
        return e

    def sprop(self, logical, x, y, z=None, yaw=0.0, **kw):
        """a piece of dressing from the model table (mv_models.STATIC): the converted model when it is in the addon, else our prop,
        else nothing. Returns the entity or None."""
        model = M.static(logical)
        if model is None: return None
        return self.prop(None, x, y, z, yaw, stock=model, **kw)

    def park(self, logical, x, y, yaw, search=260.0, step=40.0, max_slope=6.0, within=None, **kw):
        """a parked vehicle at (x, y) or the nearest spot within `search` where it touches nothing (keep-outs included) and the ground
        is level; -> (x, y) or None"""
        n = int(search / step)
        spots = sorted(((i * step, j * step) for i in range(-n, n + 1) for j in range(-n, n + 1) if math.hypot(i, j) * step <= search), key=lambda q: q[0] * q[0] + q[1] * q[1])
        sl_ = L.slope(np.array([x + q[0] for q in spots]), np.array([y + q[1] for q in spots]))      # pass 2: one vectorised slope call
        for (dx, dy), slv in zip(spots, sl_):
            px, py = x + dx, y + dy
            if within is not None and math.hypot(px - within[0], py - within[1]) > within[2]: continue
            if slv > max_slope or self.taken(M.static(logical), px, py, yaw, 10.0): continue
            if self.sprop(logical, px, py, None, yaw, fit='min', check=True, pad=10.0, _quiet=True, **kw) is not None: return (px, py)
        self.big_skips.append('%s: no free level spot within %.0f of (%.0f, %.0f)' % (logical, search, x, y))
        return None

    def mount(self, kind, team, x, y, yaw, z=None, cover=True, tag=None):
        """an emplaced gun: the stand (static), the script's gun part on its pintle (W.sites), the gunner's spot behind it and a
        sandbag horseshoe in front (the converted sandbag_cover, else a one-course arc of ours)"""
        g = M.pick(kind); zz = gz(x, y) if z is None else z
        self.prop(None, x, y, zz, yaw, stock=g['stand'], tag=tag)
        px, py = local(x, y, yaw, g['pintle'][0], g['pintle'][1]); seat = local(x, y, yaw, -g['seat_back'], 0.0)
        self.sites['mounts'].append(dict(kind=kind, team=team, pos=(px, py, zz + g['pintle'][2]), yaw=yaw, seat=seat))
        self.keep(seat[0], seat[1], 24.0, z=zz, name='seat')
        if cover:
            cm = M.static('sandbag_cover')
            if cm is not None and g['variant'] == 'ext':
                cx, cy = local(x, y, yaw, 12.0, 0.0)
                self.prop(None, cx, cy, zz, yaw + 90.0, stock=cm, tag=tag)
            else:
                self.bag_arc(x, y, g['cover_r'], yaw - 78, yaw + 78, layers=1, model='sandbag_low', z=z)
        return g

    def trunk_clip(self, x, y, z, r, h=110.0):
        """player clip round the trunk of a tree whose own hull is one convex blob (placed non-solid)"""
        self.clip(P.cylinder((x, y), r, z - 8.0, z + h, sides=6, mat=TER.CLIP))

    def cap(self, pts, model, layers, z=None):
        """pass 2 review: a player clip over a sandbag wall, from 16 u up to 70 u over its top. The staggered courses made a stair at
        every wall end (18-u steps), so players walked along the wall tops and dropped into gaps they could not climb out of (the
        firebase pit corners in check_play's pocket list). Bullets and grenades are not stopped by a player clip."""
        lo, hi = self.B(S.mv(model)); hw = (hi[1] - lo[1]) / 2 - 1.0; top = 200.0      # inside the bags' own footprint (no gap gets narrower); 200 u up: no roof is a step onto it
        pts = [tuple(q) for q in pts]
        if len(pts) == 2:      # a straight run: resample so the clip follows the ground
            n_ = max(1, int(math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]) / 48.0))
            pts = [(pts[0][0] + (pts[1][0] - pts[0][0]) * j / n_, pts[0][1] + (pts[1][1] - pts[0][1]) * j / n_) for j in range(n_ + 1)]
        path = [(x, y, (gz(x, y) if z is None else z)) for (x, y) in pts]
        try: self.clip(P.sweep(path, [(-hw, 16.0), (hw, 16.0), (hw, top), (-hw, top)], mat=TER.CLIP))
        except ValueError: pass

    def clip_footprint(self, f, h=110.0, grow=2.0):
        """a player clip box over a placed footprint (an enclosure nobody should drop into: pig pens)"""
        hx, hy = f['h'][0] + grow, f['h'][1] + grow; cx, cy = f['c']; z0 = f['z'][0]
        b = P.box((cx - hx, cy - hy, z0 - 6.0), (cx + hx, cy + hy, z0 + h), mat=TER.CLIP)
        self.clip(P.rotate_z(b, math.degrees(f['a']), (cx, cy, 0.0)))

    def scan(self, name, cx, cy, rmax, yaws, stock=None, step=40.0, max_slope=10.0, pad=8.0, rmin=0.0, ok=None, **kw):
        """pass 2 review: the first free spot for a prop anywhere in a disc (nearest the centre first, every yaw in turn); -> (x, y, yaw) or None"""
        model = stock or S.mv(name); n = int(rmax / step)
        spots = sorted(((i * step, j * step) for i in range(-n, n + 1) for j in range(-n, n + 1) if rmin <= math.hypot(i, j) * step <= rmax), key=lambda q: q[0] * q[0] + q[1] * q[1])
        sl_ = L.slope(np.array([cx + q[0] for q in spots]), np.array([cy + q[1] for q in spots])) if spots else []     # one vectorised call (L.slope is slow per point)
        for (dx, dy), slv in zip(spots, sl_):
            px, py = cx + dx, cy + dy
            if slv > max_slope or (ok is not None and not ok(px, py)): continue
            free_ = [yw for yw in yaws if not self.taken(model, px, py, yw, pad)]
            if not free_: continue
            for yw in free_:
                if self.prop(name, px, py, None, yw, stock=stock, check=True, pad=pad, _quiet=True, **kw) is not None: return (px, py, yw)
        self.big_skips.append('%s: no free spot in the disc r %.0f round (%.0f, %.0f)' % (name or stock, rmax, cx, cy))
        return None

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

    def keep_disc(self, x, y, R, z=None, name='pad', h=260.0):
        """a round keep-out (the square keep() of radius R reaches 1.41 R at its corners): a centre square and twelve small ones on the rim"""
        self.keep(x, y, R * 0.70, z=z, name=name, h=h)
        for a in range(0, 360, 30): self.keep(*L.pol((x, y), R * 0.84, a), R * 0.20, z=z, name=name, h=h)

    def rotor_ok(self, model, x, y, sc=1.0, lanes=True):
        """may something tall stand here: outside every pad's rotor cylinder (rotor radius + 60, tools/check_play.py check 4) by its own
        crown radius, and off the pads' approach lanes"""
        lo, hi = self.B(model); ex = 0.3 * max(hi[0] - lo[0], hi[1] - lo[1]) * sc; top = None
        for (hx, hy, rr, dirs, pz) in self.rotors:
            d = math.hypot(x - hx, y - hy)
            if d < rr + ex + 12.0: return False
            if lanes and d < 1850.0:
                for a in dirs:
                    c, s_ = rot(a); t = (x - hx) * c + (y - hy) * s_
                    if t > 0 and abs(-(x - hx) * s_ + (y - hy) * c) < ex + 56.0:
                        # 12 Nov review: the lane is a 30-degree glide from 60 u over the pad (check_play check 4); a crown under it is fine
                        if top is None: top = gz(x, y) + hi[2] * sc
                        if top + 48.0 > pz + 60.0 + 0.577 * max(t - ex, 0.0): return False
        return True

    def in_rotor(self, f, top, crown=None):
        """the pad whose rotor cylinder (rotor radius + 60, up to 600 u) a footprint reaching `top` stands in, or None. crown: a tree,
        measured from its trunk by 0.3 of its crown width as check_play does"""
        for (hx, hy, rr, dirs, pz) in self.rotors:
            if top <= pz + 24.0 or abs(f['c'][0] - hx) > rr + 700.0 or abs(f['c'][1] - hy) > rr + 700.0: continue
            if crown is not None: d = math.hypot(f['c'][0] - hx, f['c'][1] - hy) - crown
            else:
                c, s_ = math.cos(f['a']), math.sin(f['a']); dx, dy = hx - f['c'][0], hy - f['c'][1]
                u, v = dx * c + dy * s_, -dx * s_ + dy * c
                d = math.hypot(max(abs(u) - f['h'][0], 0.0), max(abs(v) - f['h'][1], 0.0))
            if d < rr: return (hx, hy)
        return None

    def taken(self, model, x, y, yaw, pad=0.0):
        """quick test before the slow ground calls: does the model's footprint here touch anything recorded, at any height"""
        f = self.PL.footprint(model, x, y, 0.0, yaw, (1, 1, 1), pad); f['z'] = (-1e6, 1e6)
        return self.PL.hits(f) is not None

    def fit(self, name, x, y, yaw, search=200.0, step=40.0, max_slope=14.0, stock=None, within=None, **kw):
        """a prop at (x, y) or the nearest free spot within `search`; -> (x, y) or None (listed in big_skips)"""
        n = int(search / step)
        spots = sorted(((i * step, j * step) for i in range(-n, n + 1) for j in range(-n, n + 1) if math.hypot(i, j) * step <= search), key=lambda q: q[0] * q[0] + q[1] * q[1])
        kw.setdefault('pad', 6.0)
        for dx, dy in spots:
            px, py = x + dx, y + dy
            if within is not None and math.hypot(px - within[0], py - within[1]) > within[2]: continue
            if self.taken(stock or S.mv(name), px, py, yaw, kw.get('pad', 0.0)) or float(L.slope(px, py)) > max_slope: continue
            if self.prop(name, px, py, None, yaw, stock=stock, check=True, _quiet=True, **kw) is not None: return (px, py)
        self.big_skips.append('%s: no free spot within %.0f of (%.0f, %.0f)' % (name or stock, search, x, y))
        return None

    def ladder(self, x, y, z0, z1, yaw):
        """a climbable ladder at (x, y) from z0 to z1, its rungs facing yaw (the climber stands on that side): the stock wooden
        scaffold ladder (128 u pieces, not solid) and the invisible ladder volume"""
        c_, s_ = rot(yaw); Rm = np.array([[c_, -s_, 0], [s_, c_, 0], [0, 0, 1.0]])
        vmesh.mesh_node(vmesh.oriented_box_mesh((x + c_ * 6.0, y + s_ * 6.0, (z0 + z1) / 2 + 8.0), (8.0, 15.0, (z1 - z0) / 2 + 8.0), Rm, LADDER), self.group, bake=False,
                        shadows=False, visexclude=True)
        zz = z0
        while zz < z1 - 8.0:
            self.prop(None, x, y, zz, yaw, stock=LADDER_MODEL, solid='0', reg=False, tag='platform'); zz += 128.0
        self.keep(x + c_ * 34.0, y + s_ * 34.0, 22.0, z=z0, name='ladder')

    def hull_hits(self, x, y, z0, z1, r=16.0):
        """does a player-sized box (x +- r, y +- r, z0..z1) touch any solid world mesh or player clip made so far"""
        if self._solid_cat is None or self._solid_cat[1] != len(self.solids):
            T = np.concatenate(self.solids) if self.solids else np.zeros((0, 3, 3))
            self._solid_cat = (T, len(self.solids), T.min(1), T.max(1))
        T, _, tmin, tmax = self._solid_cat
        lo = np.array([x - r, y - r, z0]); hi = np.array([x + r, y + r, z1])
        c = np.nonzero((tmax >= lo).all(1) & (tmin <= hi).all(1))[0]
        return bool(len(c)) and bool(tri_box(T[c], lo, hi).any())

    def free(self, x, y, r=18.0, z=None, h=72.0):
        if z is None: z = gz(x, y)
        return self.PL.hits(dict(c=(x, y), h=(r, r), a=0.0, z=(z + 1.0, z + h), model='probe')) is None

    # ---------------------------------------------------------------- world geometry
    def solid_tris(self, verts, faces):
        """playtest 1 (T spawns in a rocket pit's berm clip): every solid world mesh and player clip is kept as triangles, so a spawn
        or seat can be tested with a real player hull (mv_entities.stand; tools/check_play.py check 10 does the same on the vmap)"""
        V = np.asarray(verts, float)
        tri = [(V[f[0]], V[f[k]], V[f[k + 1]]) for f in faces for k in range(1, len(f) - 1)]
        if tri: self.solids.append(np.array(tri, float))

    def shape(self, shape, bake=True, shadows=True, visexclude=False, paint=None, smoothing=40.0):
        probs = P.check(shape)
        if probs: raise ValueError('bad shape: ' + '; '.join(probs[:3]))
        v, f, m = shape
        self.solid_tris(v, f)
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
    # playtest 1 (p3): walls were 2-4 stacked 19-u props of loose pillows, each standing on the ground at its own centre (floating on
    # slopes, gaps between pieces). A wall is now a row of full-height segments (p_sandbag_mv: 80 u long, interlocking end to end,
    # battered, footing courses under z 0), each pitched along the ground and set on the lowest ground it covers.
    SB_HEIGHT = {'sandbag_low': 14.0, 'sandbag_low_128': 14.0}            # old per-layer heights: layers x this = the wall height asked for

    def sb_model(self, model, layers, radius=None):
        """the wall class for an old (model, layers) request: h1 27, h2 38, h3 57, h4 76 u; arcs r 118 / 232 (straight past r 500)"""
        ht = self.SB_HEIGHT.get(model, 19.0) * layers
        h = min(((27.0, 'h1'), (38.0, 'h2'), (57.0, 'h3'), (76.0, 'h4')), key=lambda q: abs(q[0] - ht))[1]
        if radius is None or radius >= 500.0: return 'sandbag_w_' + h
        rc = min((118.0, 232.0), key=lambda r_: abs(r_ - radius))
        if h in ('h3', 'h4'): h = 'h2'
        return 'sandbag_a%d_%s' % (int(rc), h)

    def sb_seg(self, name, x, y, yaw, z=None, sx=1.0, tag=None, length=80.0):
        """one segment centred at (x, y): on the ground (z None) pitched to the ground along it (up to 8 deg; the footing takes the
        rest) and set so its base is 1 u under the lowest ground of its footprint; or at z (a deck, a crown)"""
        c, s_ = rot(yaw); L2 = length * sx / 2.0
        pitch = 0.0
        if z is None:
            ss = np.linspace(-L2, L2, 7)
            pts = [(x + c * t_ - s_ * w_, y + s_ * t_ + c * w_, t_) for t_ in ss for w_ in (-15.0, 0.0, 15.0)]
            g = L.height(np.array([q[0] for q in pts]), np.array([q[1] for q in pts])); tt = np.array([q[2] for q in pts])
            k_ = float(np.clip(np.polyfit(tt, g, 1)[0], -0.14, 0.14))         # rise per unit along the wall
            z = float((g - tt * k_).min()) - 1.0
            pitch = -math.degrees(math.atan(k_))
            if tag is None and abs(z - gz(x, y)) > 6.0: tag = 'slope'
        return self.prop(name, x, y, z, yaw, pitch=pitch, scale=(sx, 1.0, 1.0), tag=tag)

    def bag_arc(self, cx, cy, r, a0, a1, layers=2, model='sandbag_wall', z=None, seed_rng=None):
        """sandbag wall along a circle arc (degrees, a0 < a1), its inner face toward the centre"""
        name = self.sb_model(model, layers, r)
        rc = None if name.startswith('sandbag_w_') else float(name.split('_a')[1].split('_')[0])
        span = math.radians(a1 - a0) * r; n = max(1, int(round(span / 80.0)))
        done = 0
        for i in range(n):
            th = a0 + (i + 0.5) * (a1 - a0) / n
            c, s_ = rot(th)
            sx = math.radians((a1 - a0) / n) * r / 80.0
            # a straight piece stands on the chord's middle; an arc piece's origin is on its own centre line (the arc at radius r)
            rr = r * math.cos(math.radians((a1 - a0) / n / 2.0)) if rc is None else r
            if self.sb_seg(name, cx + rr * c, cy + rr * s_, th + 90.0, z, sx=sx, tag=None if z is None else 'platform') is not None: done += 1
        if done:
            n_ = max(2, int(math.ceil((a1 - a0) / 4.0)))
            self.cap([(cx + r * math.cos(math.radians(a0 + (a1 - a0) * j / n_)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * j / n_))) for j in range(n_ + 1)],
                     name, layers, z)

    def bag_line(self, p, q, layers=2, model='sandbag_wall', z=None):
        name = self.sb_model(model, layers)
        d = math.hypot(q[0] - p[0], q[1] - p[1]); n = max(1, int(round(d / 80.0)))
        yaw = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))
        done = 0
        for i in range(n):
            t = (i + 0.5) / n
            if self.sb_seg(name, p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t, yaw, z, sx=d / (n * 80.0), tag=None if z is None else 'platform') is not None: done += 1
        if done: self.cap([p, q], name, layers, z)

    def berm_arc(self, cx, cy, r, a0, a1, base=56.0, top=20.0, h=34.0, mat=DIRT, seg=14.0):
        """earth bank swept along an arc (world geometry): a trapezoid section, ends capped"""
        n = max(3, int((a1 - a0) / seg))
        path = []
        for i in range(n + 1):
            c, s = rot(a0 + (a1 - a0) * i / n)
            path.append((cx + r * c, cy + r * s, gz(cx + r * c, cy + r * s)))
        sec = [(-base / 2, -10.0), (base / 2, -10.0), (top / 2, h), (-top / 2, h)]
        self.shape(P.sweep(path, sec, mat=mat), smoothing=60.0)
        try: self.clip(P.sweep(path, [(-base / 2, 14.0), (base / 2, 14.0), (base / 2, h + 70.0), (-base / 2, h + 70.0)], mat=TER.CLIP))   # pass 2 review: nobody walks the crest (cap())
        except ValueError: pass

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


def debris(rng, x, y, r0, r1, n=8, kit=(('ammo_can', 2), ('jerry_can', 1), ('drum_rust', 1), ('ammo_crate', 1))):
    """thrown-about small stuff and stones round a wreck"""
    k = clutter(rng, list(kit), x, y, r0, r1)
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi); r = rng.uniform(r0, r1); px, py = x + r * math.cos(a), y + r * math.sin(a)
        if float(L.slope(px, py)) > 20.0 or gz(px, py) < L.WATER_Z + 6.0: continue
        m = S.ROCKS[rng.randint(len(S.ROCKS))]; sc = rng.uniform(0.5, 1.0); lo, hi = W.B(m)
        if W.prop(None, px, py, gz(px, py) - lo[2] * sc * 0.5 - 2.0, rng.uniform(0, 360), stock=m, scale=sc, check=True, pad=2.0, tag='rock') is not None: k += 1
    return k


def rotor_plan():
    """every pad's rotor cylinder and its three approach lanes (compass directions nearest the way into the base), before anything is placed"""
    out = []
    for plan, kinds, base in ((L.firebase(), M.HELI_ON_PAD['ct'], L.CT_BASE), (L.camp(), M.HELI_ON_PAD['t'], L.T_BASE)):
        for p, kind in zip(plan['pads'], kinds):
            h = M.apache() if kind == 'apache' else M.pick(kind)
            if h is None: h = dict(rotor_r=303.0, hub=(0.0, 0.0, 156.0))
            hx, hy = local(p[0], p[1], plan['pad_yaw'], h['hub'][0], h['hub'][1])
            inward = math.degrees(math.atan2(base[1] - hy, base[0] - hx)) + (180.0 if plan is not None and base == L.CT_BASE else 0.0)   # the firebase is approached from outside, the camp across its clearing
            pz = gz(hx, hy); rr = float(h['rotor_r']) + 60.0
            # 12 Nov review: the three lanes are the compass directions nearest the way in whose ground stays under the glide
            # (30 degrees from 60 u over the pad, as check_play check 4 measures); trees are then kept off them (rotor_ok)
            d_ = np.arange(rr, 1800.0, 32.0); clear = []
            for k in range(8):
                a = k * 45.0; c_, s_ = rot(a)
                g = L.height(hx + c_ * d_, hy + s_ * d_)
                for (kx, ky, kr, kh, ks) in L.KARST:          # the towers are meshes, not in layout.height
                    g = np.where(np.hypot(hx + c_ * d_ - kx, hy + s_ * d_ - ky) < kr * 1.15, pz + 5000.0, g)
                if (g + 40.0 <= pz + 60.0 + 0.577 * d_).all(): clear.append(a)
            key = lambda a: abs((a - inward + 180.0) % 360.0 - 180.0)
            dirs = sorted(clear, key=key)[:3] or [round(inward / 45.0) * 45.0]
            out.append((hx, hy, rr, dirs, pz))
    return out


# ================================================================ tunnels: the plan (also used for the terrain holes)
_TUN = None
TUN_H, TUN_CH_H, TUN_K = 104.0, 140.0, 0.47
TUN_K_ENTRY, TUN_ENTRY = 0.8, 130.0          # the entrance shaft: 39 degrees (walkable: under 45) for its first 130 u


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
    """the gallery plan: samples every 16 u with their floors (graded from the portals), a 16-u grid of occupied cells with floor /
    roof heights (nav markup, checks); then tunnel_field() makes the mesh, the terrain cells it replaces, frames and lamps.
    Depends on layout only."""
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
    # playtest 1: the entrance is a steep stepped shaft (TUN_K_ENTRY for the first TUN_ENTRY u from each portal, log treads on it), so
    # the roof starts about 140 u in instead of 250 (the old 25-degree ramp made a 100-u deep open cut most of a gallery long)
    target = g - np.minimum(cap, 8.0 + np.minimum(dp, TUN_ENTRY) * TUN_K_ENTRY + np.maximum(dp - TUN_ENTRY, 0.0) * TUN_K)
    target = np.where(np.array(ext), g - 6.0, target)
    adj_k = [[(j, d * (TUN_K_ENTRY if max(dp[i], dp[j]) < TUN_ENTRY else TUN_K)) for j, d in adj[i]] for i in range(n)]
    f = _dijkstra(n, adj_k, list(target), k=1.0)
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
    # pass 2 review: the floor took each grid vertex from its nearest gallery sample, so where the stub leaves the junction two galleries
    # at different depths met in one cell (a 32-u drop over 16 u: a stuck pocket at (-3176, 2280)). Limit the floor's grade between
    # neighbouring vertices of the passages to 0.75 (lowering the higher side; the chamber stays flat)
    used = np.zeros(VX.shape, bool)
    for di in (0, 1):
        for dj in (0, 1): used[di:nx + di, dj:ny + dj] |= occ
    free_ = used & ~in_ch
    for _ in range(400):
        F0 = FZ.copy(); Fu = np.where(used, FZ, np.inf)
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            sh = np.full(FZ.shape, np.inf)
            sh[max(di, 0):FZ.shape[0] + min(di, 0), max(dj, 0):FZ.shape[1] + min(dj, 0)] = Fu[max(-di, 0):FZ.shape[0] + min(-di, 0), max(-dj, 0):FZ.shape[1] + min(-dj, 0)]
            FZ = np.where(free_, np.minimum(FZ, sh + 0.75 * 16.0 * math.hypot(di, dj)), FZ)
        if np.abs(FZ - F0).max() < 0.01: break
    FZ = np.round(FZ * 2) / 2
    CZ = FZ + np.where(in_ch, TUN_CH_H, TUN_H)
    # playtest 1 (p1, p6): the galleries, the chamber and the three mouths are one smooth field now (tunnel_field), meshed by surface
    # nets; the plan above (samples, floors, the 16-u grid) is kept for the floors, the nav markup and the checks
    CZ = FZ + np.where(in_ch, TUN_CH_H, TUN_TOP)
    _TUN = dict(gx=gx, gy=gy, occ=occ, FZ=FZ, CZ=CZ, f_ch=f_ch, samples=Pn, floor=f, gal=np.array(gal), galleries=galleries_ext, portal_idx=portal_idx,
                in_ch=in_ch)
    tunnel_field(_TUN)
    return _TUN


# ---------------------------------------------------------------- the tunnel field (playtest 1)
# Cu Chi-style hand-dug galleries: an ovoid section (44 u half width at 46 u over the floor, roof at 102 over it, a 50-u flat floor),
# walls displaced by noise, the floor nearly flat; a domed chamber; where the ground comes within ~14 u of the void the two blend
# (smooth union), which opens the mouths as rounded cuts with a lip instead of square holes. Timber frames (posts touching the floor
# and the wall, a cap beam against the roof) stand where the section is cut flat to fit them: three with lagging boards at each mouth,
# single frames along the galleries and at the chamber door. Spoil heaps beside the mouths. One mesh for the earth under the ground
# (dirt walls, mud floor, uvs that follow the gallery), one for the ground around the mouths (the valley blend material, painted).
TUN_A, TUN_B, TUN_VC = 44.0, 56.0, 46.0
TUN_TOP = TUN_VC + TUN_B
CH_R, CH_B, CH_VC = 138.0, 104.0, 40.0
FR_U, FR_TOP = 35.0, 94.0
SN_H, SN_K = 8.0, 14.0
TIMBER = 'materials/de_train/hr_train_s2/wood/hrts2_wood_timber_framing_01_wet.vmat'
vmesh.TEX_SIZE[TIMBER] = (1024, 1024)


def _smax(a, b, k):
    h = np.clip(k - np.abs(a - b), 0.0, None) / k
    return np.maximum(a, b) + h * h * k * 0.25


def _gal_tables(t):
    """per gallery: its polyline, the arc length and floor of its plan samples, where its frames stand"""
    out = []
    for gi, g in enumerate(t['galleries']):
        idx = np.nonzero(t['gal'] == gi)[0]
        P = t['samples'][idx]; seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        poly = np.asarray(g, float); pl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(poly, axis=0), axis=1))])
        out.append(dict(gi=gi, idx=idx, P=P, cum=np.concatenate([[0.0], np.cumsum(seg)]), f=t['floor'][idx], poly=poly, pl=pl, frames=[], spans=[]))
    return out


def _gal_cols(G, X, Y):
    """distance to the gallery's centre line, signed side, arc length, floor, the unit direction there"""
    d, tn = L.seg_dist(X, Y, G['poly'])
    s = tn * G['pl'][-1]
    F = np.interp(s, G['cum'], G['f'])
    k = np.clip(np.searchsorted(G['pl'], s) - 1, 0, len(G['poly']) - 2)
    a = G['poly'][k]; b = G['poly'][k + 1]; dv = b - a; dv = dv / np.linalg.norm(dv, axis=-1, keepdims=True)
    px = a[..., 0] + dv[..., 0] * (s - G['pl'][k]); py = a[..., 1] + dv[..., 1] * (s - G['pl'][k])
    side = np.sign(dv[..., 0] * (Y - py) - dv[..., 1] * (X - px)); side = np.where(side == 0, 1.0, side)
    return d, d * side, s, F, dv


def _frame_w(G, s):
    """1 at a timber frame (the section cut flat to it), 0 a little way off"""
    w = np.zeros(np.shape(s))
    for (sa, sb) in G['spans']:
        dd = np.maximum(np.maximum(sa - s, s - sb), 0.0)
        w = np.maximum(w, 1.0 - smoothstep(4.0, 20.0, dd))
    for sc in G['frames']:
        w = np.maximum(w, 1.0 - smoothstep(7.0, 22.0, np.abs(s - sc)))
    return w


def tunnel_field(t):
    from scipy import ndimage
    import snets
    G_ = _gal_tables(t); t['gtab'] = G_
    ch = np.array(L.TUNNEL_CHAMBER, float); fch = t['f_ch']
    Pn = t['samples']
    # terrain mesh heights (bilinear in its 32-u cells: the tiles round the portals are 32-u grids of layout.height)
    gx0, gy0 = float(Pn[:, 0].min() - 320), float(Pn[:, 1].min() - 320)
    gx32 = np.arange(math.floor(gx0 / 32) * 32, math.ceil((Pn[:, 0].max() + 320) / 32) * 32 + 1, 32.0)
    gy32 = np.arange(math.floor(gy0 / 32) * 32, math.ceil((Pn[:, 1].max() + 320) / 32) * 32 + 1, 32.0)
    H32 = np.asarray(L.height(*np.meshgrid(gx32, gy32, indexing='ij')), float)
    def Hm(x, y):
        u = (np.asarray(x, float) - gx32[0]) / 32.0; v = (np.asarray(y, float) - gy32[0]) / 32.0
        i = np.clip(np.floor(u).astype(int), 0, len(gx32) - 2); j = np.clip(np.floor(v).astype(int), 0, len(gy32) - 2); fu = u - i; fv = v - j
        return H32[i, j] * (1 - fu) * (1 - fv) + H32[i + 1, j] * fu * (1 - fv) + H32[i, j + 1] * (1 - fu) * fv + H32[i + 1, j + 1] * fu * fv
    t['Hm'] = Hm
    # ---- the mouths: where the roof starts (16 u of cover over the ovoid), the framed entrance from there 72 u in
    juncs = []
    for G in G_:
        for q in G['poly']:
            if sum(1 for H_ in G_ for r in H_['poly'] if abs(r[0] - q[0]) < 1 and abs(r[1] - q[1]) < 1) > 1: juncs.append(q)
    mouths = []
    for k, pi in enumerate(t['portal_idx']):
        gi = int(t['gal'][pi]); G = G_[gi]; pos = int(np.nonzero(G['idx'] == pi)[0][0])
        inward = 1 if pos < len(G['idx']) / 2 else -1
        order = range(pos, len(G['idx'])) if inward > 0 else range(pos, -1, -1)
        cover = Hm(G['P'][:, 0], G['P'][:, 1]) - (G['f'] + TUN_TOP)
        sm = None
        for q in order:
            if cover[q] >= 16.0: sm = q; break
        sm = pos if sm is None else sm
        s_m = float(G['cum'][sm]); s_p = float(G['cum'][pos])
        span = (s_m - 4.0, s_m + 72.0) if inward > 0 else (s_m - 72.0, s_m + 4.0)
        G['spans'].append(span)
        frames = [s_m + inward * o for o in (0.0, 36.0, 72.0)]
        # inside: the leash target (mv_tunnel_N) stays where it was, 3 samples (48 u) in from the portal; its z stands clear of the shaft
        # floor and the treads under a player there (the highest floor within 24 u along the gallery)
        ins = min(max(pos + 3 * inward, 0), len(G['idx']) - 1)
        near_ = np.abs(G['cum'] - G['cum'][ins]) <= 18.0
        f_ins = float(G['f'][near_].max()) + 1.5            # a standing hull's uphill edge clears the shaft floor (check_play 10)
        dvec = G['P'][min(max(sm + inward, 0), len(G['idx']) - 1)] - G['P'][sm]; dvec = dvec / max(np.linalg.norm(dvec), 1e-9)
        mouths.append(dict(k=k, gi=gi, inward=inward, s_m=s_m, s_p=s_p, frames=frames, pos=(float(Pn[pi, 0]), float(Pn[pi, 1]), float(t['floor'][pi])),
                           mouth=(float(G['P'][sm, 0]), float(G['P'][sm, 1]), float(G['f'][sm])), dir=(float(dvec[0]), float(dvec[1])),
                           inside=(float(G['P'][ins, 0]), float(G['P'][ins, 1]), f_ins), arch=None))
    # single frames along the galleries (every ~190 u, clear of the entrances, junctions and the lead-in), one at the chamber door
    for G in G_:
        Lg = float(G['cum'][-1])
        for s in np.arange(120.0, Lg - 60.0, 120.0):
            p = np.array([np.interp(s, G['cum'], G['P'][:, 0]), np.interp(s, G['cum'], G['P'][:, 1])])
            if any(sa - 70.0 < s < sb + 70.0 for sa, sb in G['spans']): continue
            if any(math.hypot(p[0] - q[0], p[1] - q[1]) < 150.0 for q in juncs): continue      # build 1: a post stood in the next gallery's mouth
            k_ = np.clip(np.searchsorted(G['pl'], s) - 1, 0, len(G['poly']) - 2); dv_ = G['poly'][k_ + 1] - G['poly'][k_]; dv_ = dv_ / np.linalg.norm(dv_)
            posts_ = [p + np.array([-dv_[1], dv_[0]]) * sg_ * FR_U for sg_ in (-1.0, 1.0)]
            if any(_gal_cols(H_, np.array([q_[0]]), np.array([q_[1]]))[0][0] < TUN_A + 20.0 for H_ in G_ if H_ is not G for q_ in posts_): continue
            if math.hypot(p[0] - ch[0], p[1] - ch[1]) < CH_R + 40.0: continue
            if Hm(p[0], p[1]) - (float(np.interp(s, G['cum'], G['f'])) + TUN_TOP) < 20.0: continue     # only under a roof
            G['frames'].append(float(s))
    stub = G_[-1]; Ls = float(stub['cum'][-1])
    stub['frames'].append(Ls - CH_R * 0.93 - 6.0)
    # spoil: the earth dug out, heaped beside each mouth (a larger heap on one side, a smaller one across)
    heaps = []
    for m in mouths:
        ox, oy = -m['dir'][0], -m['dir'][1]                      # outward
        nx_, ny_ = -oy, ox
        sd_ = 1.0 if m['k'] % 2 == 0 else -1.0
        for (lat, out, along, across, hh) in ((96.0, 30.0, 70.0, 40.0, 13.0), (-88.0, 70.0, 46.0, 30.0, 7.0)):
            cx_ = m['pos'][0] + nx_ * lat * sd_ + ox * out; cy_ = m['pos'][1] + ny_ * lat * sd_ + oy * out
            heaps.append((cx_, cy_, ox, oy, along, across, hh))
    def spoil(X, Y):
        s_ = np.zeros(np.shape(X))
        for (cx_, cy_, ox, oy, along, across, hh) in heaps:
            dx, dy = X - cx_, Y - cy_
            r2 = ((dx * ox + dy * oy) / along) ** 2 + ((-dx * oy + dy * ox) / across) ** 2
            n_ = 1.0 + 0.18 * fbm(X / 30.0, Y / 30.0, 4.4, 2, seed=91)
            s_ = np.maximum(s_, hh * n_ * np.clip(1 - r2, 0, 1) ** 2)
        return s_
    t['spoil'] = spoil
    # ---- the sampling box (corners at 8k + 4 in x and y: cell centres fall on the 8-u lattice, so the terrain's 32-u lines are cell centres)
    x0 = math.floor((Pn[:, 0].min() - 240) / 8) * 8 + 4.0; x1 = math.ceil((Pn[:, 0].max() + 240) / 8) * 8 + 4.0
    y0 = math.floor((Pn[:, 1].min() - 240) / 8) * 8 + 4.0; y1 = math.ceil((Pn[:, 1].max() + 240) / 8) * 8 + 4.0
    xs = np.arange(x0, x1 + 0.1, SN_H); ys = np.arange(y0, y1 + 0.1, SN_H)
    XC, YC = np.meshgrid(xs, ys, indexing='ij')
    Hc = Hm(XC, YC) + spoil(XC, YC)
    z0 = math.floor((min(float(t['floor'].min()), fch) - 30.0) / 8) * 8 + 2.0; z1 = math.ceil((float(Hc.max()) + 30.0) / 8) * 8 + 2.0
    zs = np.arange(z0, z1 + 0.1, SN_H)
    Z = zs[None, None, :]
    # ---- the void: each gallery's ovoid (or the frame's flat-sided section), the chamber's dome, smooth union, noise on the walls
    sds = []; vv = []; ww = []
    for G in G_:
        d, ds_, s, F, _ = _gal_cols(G, XC, YC)
        a = TUN_A * (1.0 + 0.07 * fbm(s / 160.0, G['gi'] * 3.1, 0.5, 2, seed=93))
        v = Z - F[:, :, None]
        e = (np.sqrt((d[:, :, None] / a[:, :, None]) ** 2 + ((v - TUN_VC) / TUN_B) ** 2) - 1.0) * min(TUN_A, TUN_B) * 0.92
        sg = np.maximum(e, -v)
        fr = np.maximum(np.maximum(np.abs(d)[:, :, None] - FR_U, v - FR_TOP), -v)
        w = _frame_w(G, s)[:, :, None]
        sds.append(sg * (1 - w) + fr * w); vv.append(v); ww.append(np.broadcast_to(w, v.shape))
    rc = np.hypot(XC - ch[0], YC - ch[1])[:, :, None]; vc = Z - fch
    e = (np.sqrt((rc / CH_R) ** 2 + ((vc - CH_VC) / CH_B) ** 2) - 1.0) * CH_B * 0.92
    sds.append(np.maximum(e, -vc)); vv.append(np.broadcast_to(vc, e.shape)); ww.append(np.zeros(e.shape))
    S_ = np.stack(sds, 0); sel = S_.argmin(0)
    sd = S_[0]
    for k_ in range(1, len(sds)): sd = -_smax(-sd, -S_[k_], 10.0)
    vsel = np.take_along_axis(np.stack(vv, 0), sel[None], 0)[0]; wsel = np.take_along_axis(np.stack(ww, 0), sel[None], 0)[0]
    near = np.abs(sd) < 26.0
    X3 = np.broadcast_to(XC[:, :, None], sd.shape)[near]; Y3 = np.broadcast_to(YC[:, :, None], sd.shape)[near]; Z3 = np.broadcast_to(Z, sd.shape)[near]
    nz_ = fbm(X3 / 30.0, Y3 / 30.0, Z3 / 30.0, 3, seed=88) + 0.7 * fbm(X3 / 95.0, Y3 / 95.0, Z3 / 95.0, 2, seed=89)
    amp = 1.0 + 6.0 * smoothstep(3.0, 24.0, vsel[near])
    sd[near] += amp * nz_ * (1.0 - wsel[near])
    phi_t = Z - Hc[:, :, None]
    phi = _smax(phi_t, -sd, SN_K)
    # ---- the terrain cells the field changes near the surface (+ the spoil): cut from the terrain, meshed here instead
    infl = (np.abs(phi - phi_t) > 0.02) & (np.abs(phi_t) < 20.0)          # the void (or its blend) changes the ground's own surface here
    flag_col = (infl & (np.abs(phi_t) < 14.0)).any(2) | (spoil(XC, YC) > 0.01)
    bx0 = int(math.floor(x0 / 32)); by0 = int(math.floor(y0 / 32))
    nbx = int(math.floor(x1 / 32)) - bx0 + 1; nby = int(math.floor(y1 / 32)) - by0 + 1
    hb = np.zeros((nbx, nby), bool)
    ii = (np.floor(XC / 32).astype(int) - bx0)[flag_col]; jj = (np.floor(YC / 32).astype(int) - by0)[flag_col]
    hb[ii, jj] = True
    hb = ndimage.binary_dilation(hb, np.ones((3, 3), bool))
    import vmapgen as VG
    hb = VG.fix_pinches(hb)
    holes = set((int(i + bx0), int(j + by0)) for i, j in zip(*np.nonzero(hb)))
    # cell centres on the 8-u lattice; a centre on a 32-u line belongs to the region when either side of it does (closed region)
    cxs = xs[:-1] + SN_H / 2; cys = ys[:-1] + SN_H / 2
    def in_region(cx, cy):
        out = np.zeros(np.broadcast(cx, cy).shape, bool)
        for ex in (0, 1):
            for ey in (0, 1):
                bi = np.floor(cx / 32).astype(int) - ex * (np.mod(cx, 32) == 0); bj = np.floor(cy / 32).astype(int) - ey * (np.mod(cy, 32) == 0)
                ok = (bi - bx0 >= 0) & (bi - bx0 < nbx) & (bj - by0 >= 0) & (bj - by0 < nby)
                out |= ok & hb[np.clip(bi - bx0, 0, nbx - 1), np.clip(bj - by0, 0, nby - 1)]
        return out
    CXc, CYc = np.meshgrid(cxs, cys, indexing='ij')
    reg = in_region(CXc, CYc)
    Hcc = Hm(CXc, CYc) + spoil(CXc, CYc)
    include = reg[:, :, None] | (zs[None, None, 1:] < Hcc[:, :, None] - 12.0)
    phi, n_amb = snets.fix_ambiguous(phi)
    V, Q, cell = snets.surface_nets(phi, x0, y0, z0, SN_H, include=include)
    # ---- inside the region, where nothing but the ground is (the field equals the terrain's in the whole column), every vertex of a
    # column collapses to one at the cell centre on the terrain mesh: there the patch is the terrain's own grid, and on its edge (a 32-u
    # line of the terrain) its vertices lie exactly on the terrain's edges
    pc = ~infl.any(2)
    pure = pc[:-1, :-1] & pc[1:, :-1] & pc[:-1, 1:] & pc[1:, 1:] & reg
    colv = {}
    vmap = np.arange(len(V))
    newV = list(map(tuple, V))
    for vi, (ci, cj, ck) in enumerate(cell):
        if not pure[ci, cj] or abs(V[vi, 2] - Hcc[ci, cj]) > 16.0: continue          # only the ground sheet (a gallery deep under it stays)
        key = (int(ci), int(cj))
        if key not in colv:
            colv[key] = len(newV); newV.append((float(cxs[ci]), float(cys[cj]), float(Hcc[ci, cj])))
        vmap[vi] = colv[key]
    V = np.array(newV, float)
    faces = []
    for q in vmap[Q]:
        lp = [int(q[0])]
        for x_ in q[1:]:
            if int(x_) != lp[-1]: lp.append(int(x_))
        if len(lp) > 1 and lp[-1] == lp[0]: lp.pop()
        if len(set(lp)) == len(lp) >= 3: faces.append(lp)
    used = np.zeros(len(V), bool)
    for lp in faces: used[lp] = True
    remap = -np.ones(len(V), np.int64); remap[used] = np.arange(int(used.sum())); V = V[used]
    faces = [[int(remap[i]) for i in lp] for lp in faces]
    # manifold check (Hammer refuses a non-manifold edge; a pinched vertex hangs the compile: vmesh splits those)
    E = {}
    for lp in faces:
        for k_ in range(len(lp)):
            a_, b_ = lp[k_], lp[(k_ + 1) % len(lp)]
            E[(a_, b_)] = E.get((a_, b_), 0) + 1
    bad = [e_ for e_, c_ in E.items() if c_ > 1 or E.get((e_[1], e_[0]), 0) > 1]
    t.update(holes=holes, region=hb, reg_origin=(bx0, by0), mesh=(V, faces), n_amb=n_amb, n_bad_edges=len(bad), mouths=mouths, heaps=heaps,
             box=(float(Pn[:, 0].min() - 240), float(Pn[:, 1].min() - 240), float(z0), float(Pn[:, 0].max() + 240), float(Pn[:, 1].max() + 240), float(z1)),
             sn=dict(xs=xs, ys=ys, zs=zs, x0=x0, y0=y0, z0=z0))
    # the plan's 16-u cells open to the sky (the nav markup keeps those open): roof within 14 u of the ground
    gx, gy, occ = t['gx'], t['gy'], t['occ']
    CXp, CYp = np.meshgrid((gx[:-1] + gx[1:]) / 2, (gy[:-1] + gy[1:]) / 2, indexing='ij')
    czc = np.maximum(np.maximum(t['CZ'][:-1, :-1], t['CZ'][1:, :-1]), np.maximum(t['CZ'][:-1, 1:], t['CZ'][1:, 1:]))
    t['open'] = occ & (czc + 14.0 > Hm(CXp, CYp))
    # lamps: every ~210 u along each gallery where it is roofed, hung 18 u under the roof
    lamps = []
    for G in G_:
        for q in range(6, len(G['idx']), 13):
            x_, y_ = G['P'][q]
            if Hm(x_, y_) - (G['f'][q] + TUN_TOP) > 20.0 and math.hypot(x_ - ch[0], y_ - ch[1]) > CH_R: lamps.append((float(x_), float(y_), float(G['f'][q]) + TUN_TOP - 18.0))
    t['lamps'] = lamps
    if bad: print('WARNING tunnel mesh: %d non-manifold edges, e.g. at %s' % (len(bad), [tuple(round(float(c)) for c in V[e_[0]]) for e_ in bad[:4]]))
    print('tunnel field: %d x %d x %d samples, %d ambiguous faces fixed, %d terrain cells cut, %d verts, %d faces, %d bad edges' %
          (len(xs), len(ys), len(zs), n_amb, len(holes), len(V), len(faces), len(bad)))


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
    """cells left out of the terrain: the ground round the tunnel mouths (the tunnel mesh carries it) and the dug floors inside the
    firebase bunkers"""
    cut = np.zeros(CX.shape, bool)
    t = tunnel_plan()
    if t['holes']:
        bx = np.floor(CX / 32.0).astype(np.int64); by = np.floor(CY / 32.0).astype(np.int64)
        x0, y0, _, x1, y1, _ = t['box']
        if CX.max() >= x0 and CX.min() <= x1 and CY.max() >= y0 and CY.min() <= y1:
            sel = (CX >= x0) & (CX <= x1) & (CY >= y0) & (CY <= y1)
            if sel.any():
                hit = np.array([(int(a), int(b)) in t['holes'] for a, b in zip(bx[sel], by[sel])])
                if hit.any(): assert r <= 32, 'tunnel portal in a coarse terrain tile (see mv_terrain.tile_res)'
                cut[sel] = hit
    for (x, y, yaw, hl, hw) in bunker_rects():
        if abs(CX - x).min() > 200 or abs(CY - y).min() > 200: continue
        c, s = rot(yaw)
        lx = (CX - x) * c + (CY - y) * s; ly = -(CX - x) * s + (CY - y) * c
        m = r * 0.71 + 2.0      # the whole cell (any orientation) inside the interior
        cut |= (np.abs(lx) < hl - m) & (np.abs(ly) < hw - m)
    return cut


def _log(p0, p1, r, mat=TIMBER, sides=7):
    """a round log between two points (a closed prism)"""
    sec = [(r * math.cos(2 * math.pi * k / sides), r * math.sin(2 * math.pi * k / sides)) for k in range(sides)]
    up = (0.0, 0.0, 1.0) if abs(p1[2] - p0[2]) < 0.9 * math.dist(p0, p1) else (1.0, 0.0, 0.0)
    return P.sweep([p0, p1], sec, mat=mat, up=up)


def _beam(c, along, half, mat=TIMBER):
    """a squared timber centred at c: half = (half length along `along`, half width across, half height)"""
    b = P.box((c[0] - half[0], c[1] - half[1], c[2] - half[2]), (c[0] + half[0], c[1] + half[1], c[2] + half[2]), mat=mat)
    return P.rotate_z(b, math.degrees(math.atan2(along[1], along[0])), (c[0], c[1], 0.0))


def tunnels():
    rng = np.random.RandomState(4104)
    t = tunnel_plan()
    V, faces = t['mesh']; Hm = t['Hm']; spoil = t['spoil']; G_ = t['gtab']
    ch = np.array(L.TUNNEL_CHAMBER, float); fch = t['f_ch']
    # ---- per face: ground round the mouths (valley blend, painted) or the dug earth (dirt walls / roof, mud floor, uvs along the gallery)
    Vf = [V[lp] for lp in faces]
    cen = np.array([p.mean(0) for p in Vf])
    nrm = np.array([np.cross(p[1] - p[0], p[2] - p[0]) + (np.cross(p[2] - p[0], p[3] - p[0]) if len(p) > 3 else 0.0) for p in Vf])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    Hf = Hm(cen[:, 0], cen[:, 1]) + spoil(cen[:, 0], cen[:, 1])
    depth = Hf - cen[:, 2]
    ground = (depth < 10.0) & (nrm[:, 2] > -0.2)
    floor_ = ~ground & (nrm[:, 2] > 0.55)
    # nearest gallery / chamber of each face (for its uv)
    best = np.full(len(cen), 1e9); bk = np.full(len(cen), -1); cols = []
    for k, G in enumerate(G_):
        d, ds_, s, F, _ = _gal_cols(G, cen[:, 0], cen[:, 1]); cols.append((ds_, s, F))
        m = d < best; best[m] = d[m]; bk[m] = k
    rch = np.hypot(cen[:, 0] - ch[0], cen[:, 1] - ch[1]); in_chm = rch - CH_R * 0.85 < best
    TS = 160.0                                                                              # u per texture repeat in the tunnel
    def corner_uv(fi, lp):
        p = V[lp]
        if floor_[fi]: return [(q[0] / TS, q[1] / TS) for q in p]
        if in_chm[fi]:
            az = np.arctan2(p[:, 1] - ch[1], p[:, 0] - ch[0])
            if az.max() - az.min() > math.pi: az = np.where(az < 0, az + 2 * math.pi, az)
            return [(a_ * CH_R * 0.8 / TS, -q[2] / TS) for a_, q in zip(az, p)]
        G = G_[int(bk[fi])]
        d, ds_, s, F, _ = _gal_cols(G, p[:, 0], p[:, 1])
        th = np.arctan2(ds_, p[:, 2] - F - TUN_VC)
        if th.max() - th.min() > math.pi: th = np.where(th < 0, th + 2 * math.pi, th)
        return [(s_ / TS, a_ * 52.0 / TS) for s_, a_ in zip(s, th)]
    nb = 0
    for part, sel in (('earth', ~ground), ('ground', ground)):
        idx = np.nonzero(sel)[0]
        if not len(idx): continue
        used = sorted(set(i for fi in idx for i in faces[fi])); rm = {v: k for k, v in enumerate(used)}
        pv = V[used]; pf = [[rm[i] for i in faces[fi]] for fi in idx]
        if part == 'earth':
            mats = [MUD if floor_[fi] else DIRT for fi in idx]
            uvs = [corner_uv(fi, faces[fi]) for fi in idx]
            m_ = vmesh.polymesh_open(pv, pf, mats, uvs=uvs)
            vmesh.mesh_node(m_, W.group, bake=True, shadows=True, smoothing=70.0)
            W.solid_tris(pv, pf)
        else:
            # the valley's own paint (mv_terrain.paint per point), turned to mud toward the cut and on the spoil, back to the terrain's
            # own values over the last 40 u before the edge of the cut-out (where the patch meets the terrain mesh)
            x_, y_, z_ = pv[:, 0], pv[:, 1], pv[:, 2]
            w_, tint_ = L.paint_weight(x_, y_, z_, L.slope(x_, y_))
            if TER.img('mud') is not None:
                fr_ = np.abs(L.detail(x_, y_)) > 0.5
                w_ = np.where(fr_, np.clip(w_ - 0.8 * TER.img('mud')(x_, y_) - 0.6 * TER.img('rock')(x_, y_), 0, 1), w_)
                tint_ = np.where(fr_, np.clip(tint_ * (1.12 - 0.24 * TER.img('cavity')(x_, y_)), 0.55, 1.0), tint_)
            reg = t['region']; bx0, by0 = t['reg_origin']
            fine = np.kron(reg, np.ones((4, 4), bool))                                     # the cut-out on an 8-u grid
            edt = ndimage_edt(fine) * 8.0
            fi_ = np.clip(((x_ / 8.0) - bx0 * 4).astype(int), 0, fine.shape[0] - 1); fj_ = np.clip(((y_ / 8.0) - by0 * 4).astype(int), 0, fine.shape[1] - 1)
            keep_ = smoothstep(8.0, 44.0, edt[fi_, fj_])                                   # 0 at the edge: the terrain's paint
            dax = np.min([_gal_cols(G, x_, y_)[0] for G in G_], axis=0)
            mud = np.maximum(1.0 - smoothstep(48.0, 120.0, dax), np.clip(spoil(x_, y_) / 9.0, 0, 1)) * keep_
            w_ = w_ * (1.0 - 0.95 * mud); tint_ = tint_ * (1.0 - 0.08 * mud)
            pa = np.zeros((len(pv), 4)); pa[:, 0] = w_; pa[:, 2] = 0.35
            ti = np.ones((len(pv), 4)); ti[:, 0] = ti[:, 1] = ti[:, 2] = tint_
            m_ = vmesh.polymesh_open(pv, pf, [TER.BLEND_VALLEY] * len(pf), paint=pa, tint=ti)        # scale 0.25 as the terrain tiles
            vmesh.mesh_node(m_, W.group, bake=True, shadows=True, smoothing=60.0)
            W.solid_tris(pv, pf)
        nb += len(pf)
    # ---- timber: frames (two posts on the floor against the walls, a cap beam against the roof, ends set into the earth), lagging boards
    # on the walls and over the caps through each framed entrance, half-buried log treads down the ramps
    tim = []
    def frame_at(G, s, lag=False):
        p = np.array([np.interp(s, G['cum'], G['P'][:, 0]), np.interp(s, G['cum'], G['P'][:, 1])])
        F = float(np.interp(s, G['cum'], G['f']))
        _, _, _, _, dv = _gal_cols(G, np.array([p[0]]), np.array([p[1]])); dv = dv[0]
        nx_, ny_ = -dv[1], dv[0]
        for sg in (-1.0, 1.0):
            cx_, cy_ = p[0] + nx_ * sg * (FR_U - 4.2), p[1] + ny_ * sg * (FR_U - 4.2)       # 4.5-u log: its outer side 0.3 u into the wall
            tim.append(_log((cx_, cy_, F - 3.0), (cx_ + rng.uniform(-0.6, 0.6), cy_ + rng.uniform(-0.6, 0.6), F + FR_TOP - 8.0), 4.5))
        tim.append(_beam((p[0], p[1], F + FR_TOP - 4.0), (nx_, ny_), (FR_U + 5.0, 4.5, 4.2)))
        return p, F, dv
    for G in G_:
        for s in G['frames']: frame_at(G, s)
    for m in t['mouths']:
        G = G_[m['gi']]; ps = []
        for s in m['frames']: ps.append(frame_at(G, s))
        for (pa_, Fa, dv), (pb_, Fb, _) in zip(ps[:-1], ps[1:]):                          # lagging between neighbouring frames
            nx_, ny_ = -dv[1], dv[0]
            for sg in (-1.0, 1.0):
                for hz in np.arange(10.0, FR_TOP - 12.0, 9.5):
                    a_ = (pa_[0] + nx_ * sg * (FR_U - 0.6), pa_[1] + ny_ * sg * (FR_U - 0.6), Fa + hz); b_ = (pb_[0] + nx_ * sg * (FR_U - 0.6), pb_[1] + ny_ * sg * (FR_U - 0.6), Fb + hz)
                    mid = ((a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2, (a_[2] + b_[2]) / 2 + rng.uniform(-0.6, 0.6))
                    ln = math.hypot(b_[0] - a_[0], b_[1] - a_[1]) / 2 + 3.0
                    bm = P.box((mid[0] - ln, mid[1] - 1.1, mid[2] - 4.2), (mid[0] + ln, mid[1] + 1.1, mid[2] + 4.2), mat=TIMBER)
                    tim.append(P.rotate_z(bm, math.degrees(math.atan2(dv[1], dv[0])), (mid[0], mid[1], 0.0)))
            for off in np.arange(-FR_U + 4.0, FR_U - 3.0, 8.6):                            # roof boards across the caps
                mid = ((pa_[0] + pb_[0]) / 2 + nx_ * off, (pa_[1] + pb_[1]) / 2 + ny_ * off, (Fa + Fb) / 2 + FR_TOP + 0.6)
                ln = math.hypot(pb_[0] - pa_[0], pb_[1] - pa_[1]) / 2 + 4.0
                bm = P.box((mid[0] - ln, mid[1] - 4.0, mid[2] - 1.1), (mid[0] + ln, mid[1] + 4.0, mid[2] + 1.1), mat=TIMBER)
                tim.append(P.rotate_z(bm, math.degrees(math.atan2(dv[1], dv[0])), (mid[0], mid[1], 0.0)))
        # treads: from the outer end of the cut to the framed entrance, a log every ~26 u where the floor climbs
        inw = m['inward']; s0 = m['s_p'] - inw * 56.0; s1 = m['s_m'] + inw * 72.0
        s_leash = float(m['s_p']) + inw * 48.0
        for s in np.arange(min(s0, s1) + 10.0, max(s0, s1) - 6.0, 26.0):
            if abs(s - s_leash) < 22.0: continue                    # no tread under the leash target (mv_tunnel_N) and its standing hull
            F0 = float(np.interp(s - 8, G['cum'], G['f'])); F1 = float(np.interp(s + 8, G['cum'], G['f']))
            if abs(F1 - F0) / 16.0 < 0.18: continue
            p = np.array([np.interp(s, G['cum'], G['P'][:, 0]), np.interp(s, G['cum'], G['P'][:, 1])]); F = float(np.interp(s, G['cum'], G['f']))
            _, _, _, _, dv = _gal_cols(G, np.array([p[0]]), np.array([p[1]])); dv = dv[0]; nx_, ny_ = -dv[1], dv[0]
            hw = 26.0 if any(sa <= s <= sb for sa, sb in G['spans']) else 22.0
            tim.append(_log((p[0] - nx_ * hw, p[1] - ny_ * hw, F + 0.6), (p[0] + nx_ * hw, p[1] + ny_ * hw, F + 0.6 + rng.uniform(-0.8, 0.8)), 3.4))
    # one mesh per mouth area and one for the rest (closed shells)
    if tim:
        sh = P.merge(*tim)
        W.shape(sh, smoothing=35.0)
    # ---- lamps (unshadowed, baked): along the galleries, two in the chamber, one under each entrance's inner cap
    for (x, y, z) in t['lamps']: W.lamp(x, y, z, 380, rng_=170.0)
    for dx, dy in ((-50, 30), (50, -30)): W.lamp(ch[0] + dx, ch[1] + dy, fch + TUN_CH_H - 16, 620, '255 180 104', 190.0)
    for m in t['mouths']:
        G = G_[m['gi']]; s = m['frames'][-1]
        W.lamp(float(np.interp(s, G['cum'], G['P'][:, 0])), float(np.interp(s, G['cum'], G['P'][:, 1])), float(np.interp(s, G['cum'], G['f'])) + FR_TOP - 16.0, 300, rng_=150.0)
    # the chamber: caches, cots, a radio table; placed on the floor (z given: the terrain above is not their ground)
    def tp(name, dx, dy, yaw, n=1):
        x, y = ch[0] + dx, ch[1] + dy
        for k in range(n):
            lo, hi = W.B(S.mv(name))
            if W.prop(name, x, y, fch + k * hi[2], yaw + rng.uniform(-5, 5), check=k == 0, pad=1.0, tag='tunnel') is None: break     # no crate on thin air (playtest 1)
    for (nm, dx, dy, yaw, n) in (('rocket_crate', -70, 60, 20, 2), ('rocket_crate', -78, 12, 95, 1), ('ammo_crate', 60, 70, 0, 3), ('ammo_crate', 84, 40, 80, 2),
                                 ('rice_basket', 20, 88, 0, 1), ('rice_basket', -14, 92, 0, 1), ('water_jar', -88, -30, 0, 1), ('cot', 70, -40, 60, 1),
                                 ('cot', 30, -78, 20, 1), ('plot_table_t', -30, -70, 200, 1), ('radio_prc25', 96, 0, 0, 1), ('rucksack', -50, -40, 0, 1),
                                 ('ammo_can', 40, 20, 30, 1), ('jerry_can', -96, 30, 0, 1)):
        tp(nm, dx, dy, yaw, n)
    # ---- the mouths: leash targets, keep-outs; vines and roots hanging over the earth lip above each entrance frame; ferns on the lip;
    # a root tangle half buried in the bigger spoil heap
    for k, m in enumerate(t['mouths']):
        W.sites['tunnels'].append(m['inside'])
        W.keep(m['pos'][0], m['pos'][1], 70.0, name='tunnel')
        G = G_[m['gi']]; s = m['frames'][0] - m['inward'] * 4.6
        mx_, my_ = float(np.interp(s, G['cum'], G['P'][:, 0])), float(np.interp(s, G['cum'], G['P'][:, 1]))
        ox, oy = -m['dir'][0], -m['dir'][1]
        zl = float(Hm(np.array([mx_ + ox * 2]), np.array([my_ + oy * 2]))[0])
        if zl - (float(np.interp(s, G['cum'], G['f'])) + FR_TOP) > 6.0:
            W.prop('vine_drape', mx_ + ox * 1.0, my_ + oy * 1.0, zl - 1.0, math.degrees(math.atan2(oy, ox)) - 90.0, scale=(0.62, 1.0, (zl - float(np.interp(s, G['cum'], G['f'])) - 76.0) / 153.0),
                   solid='0', reg=False, tag='hanging')
        for j in range(5):
            a_ = rng.uniform(0, 2 * math.pi); r_ = rng.uniform(70.0, 120.0); fx_, fy_ = m['pos'][0] + r_ * math.cos(a_), m['pos'][1] + r_ * math.sin(a_)
            dax = min(_gal_cols(G2, np.array([fx_]), np.array([fy_]))[0][0] for G2 in G_)
            if dax < 62.0: continue
            dv_ = np.hypot(V[:, 0] - fx_, V[:, 1] - fy_); nv_ = dv_ < 9.0                # on the cut-out's own mesh (the lip is rounded below the terrain)
            zf_ = float(V[nv_, 2].max()) if nv_.any() else float(Hm(np.array([fx_]), np.array([fy_]))[0])
            W.prop(None, fx_, fy_, zf_ - 1.5, rng.uniform(0, 360), stock=S.FERNS[rng.randint(len(S.FERNS))], solid='0', reg=False, scale=rng.uniform(0.9, 1.3),
                   tag='tunnel lip' if abs(zf_ - gz(fx_, fy_)) > 6.0 else None)
    for (cx_, cy_, ox, oy, along, across, hh) in t['heaps'][::2]:
        W.prop('root_tangle', cx_ - ox * 20.0, cy_ - oy * 20.0, float(Hm(np.array([cx_]), np.array([cy_]))[0]) + hh * 0.6 - 30.0, math.degrees(math.atan2(oy, ox)),
               solid='0', reg=False, tag='roots')
    # keep trees and dressing off the cut-out
    hb = t['region']; bx0, by0 = t['reg_origin']
    for i, j in zip(*np.nonzero(hb)):
        x_, y_ = (i + bx0) * 32.0 + 16.0, (j + by0) * 32.0 + 16.0
        W.keep(x_, y_, 18.0, z=float(Hm(np.array([x_]), np.array([y_]))[0]), name='tunnel')
    x0, y0, z0, x1, y1, z1 = t['box']
    W.clone('env_combined_light_probe_volume', ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), box_mins='%g %g %g' % (-(x1 - x0) / 2, -(y1 - y0) / 2, -(z1 - z0) / 2 - 8),
            box_maxs='%g %g %g' % ((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2 + 8), voxel_size='32.0', targetname='tunnel_probe', indoor_outdoor_level='2')
    import vmapgen as VG
    VG.hint((x0, y0, z0 - 16, x1, y1, z1 + 8), 'Low', W.group)
    print('tunnels: %d mesh faces (%d terrain cells cut), %d timber pieces, %d lamps, %d frames' % (nb, len(t['holes']), len(tim), len(t['lamps']) + 5,
                                                                                                   sum(len(G2['frames']) for G2 in G_) + 3 * len(t['mouths'])))


def ndimage_edt(mask):
    """distance (in cells) from each cell inside the mask to the nearest cell outside it"""
    from scipy import ndimage
    return ndimage.distance_transform_edt(np.pad(mask, 1))[1:-1, 1:-1]


# ================================================================ CT firebase
def firebase():
    rng = np.random.RandomState(4101)
    fb = L.firebase(); c = fb['centre']; z = fb['z']; wr = fb['wire_r']
    ang = lambda p: math.degrees(math.atan2(p[1] - c[1], p[0] - c[0]))
    # keep-outs first: track, pads, pits, spawns
    W.keep_path(fb['road_in'], 62.0, name='track')
    for p in fb['pads']: W.keep_disc(p[0], p[1], fb['pad_clear'] + 14.0)             # the whole rotor cylinder: nothing optional stands in it
    for p in fb['guns']: W.keep(p[0], p[1], fb['pit_r'] - 12.0, name='pit')
    for p in fb['spawns']: W.keep(p[0], p[1], 26.0, name='spawn')
    W.keep(fb['fuel'][0], fb['fuel'][1], 185.0, name='fuel'); W.keep(fb['tower'][0], fb['tower'][1], 135.0, name='tower')
    rx, ry = fb['rack']
    W.prop('arms_rack_ct', rx, ry, None, 90.0); W.sites['kit']['ct'] = (rx, ry, gz(rx, ry))
    # ---- bunkers on the wall ring, an M2 nest beside three of them
    gaps = [(fb['gate_angle'], 6.2, 'gate')] + [(a_, 3.3, 'sally') for a_ in fb['sally']]
    for i, (p, a) in enumerate(zip(fb['bunkers'], fb['bunker_angles'])):
        big = i in fb['m2']
        W.prop('bunker_large' if big else 'bunker_small', p[0], p[1], gz(*p), a)
        gaps.append((a, 8.6 if big else 7.6, 'bunker'))
        if big:
            na = a + (13.5 if abs((a + 13.5 - fb['gate_angle'] + 180) % 360 - 180) > 14.0 else -13.5); nx_, ny_ = L.pol(c, wr - 6.0, na)
            gaps.append((na, 3.6, 'nest'))
            W.mount('m2', 'ct', nx_, ny_, na)
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
    # pass 2 review: the signs stood every 24 / 45 degrees on exact rings (read as a pattern from the air): uneven spacing, a few missing,
    # each a little in or out and leaning off square
    a = 8.0
    while a < 360.0:
        if not in_gap(a) and rng.uniform() > 0.2:
            x, y = L.pol(c, wr + 46.0 + rng.uniform(-10, 18), a); W.prop('claymore_sign', x, y, None, a + 90 + rng.uniform(-14, 14), check=True)
        a += rng.uniform(16.0, 34.0)
    a = rng.uniform(10.0, 30.0)
    while a < 360.0:
        x, y = L.pol(c, wr + 150.0 + rng.uniform(-30, 40), a); W.prop('mines_sign', x, y, None, a + 90 + rng.uniform(-18, 18), check=True)
        a += rng.uniform(32.0, 62.0)
    # ---- gate: the firebase sign, guard post, sandbag stubs
    ga = fb['gate_angle']
    W.prop('fsb_sign', *L.pol(c, wr + 60.0, ga + 7.2), None, ga)
    # 12 Nov review: the culvert bunker (266 x 201) is dropped: the gate track, the pits and pad 3's rotor cylinder leave no spot for it inside
    # the wall (40-u grid scan); the gate keeps its sandbag stubs and guard post
    for s in (-1, 1):
        p = L.pol(c, wr - 30.0, ga + s * 6.6); q = L.pol(c, wr - 110.0, ga + s * 7.0)
        W.bag_line(p, q, layers=2)
    for kind, a in [('sally', a_) for a_ in fb['sally']]:        # a blast wall inside each sally gap (walk round it)
        da0, da1 = (-6.0, -1.2) if abs(a - 236.0) < 1.0 else (-3.6, 3.6)        # the south-west one stops short of the guard tower
        p = L.pol(c, wr - 80.0, a + da0); q = L.pol(c, wr - 80.0, a + da1); W.bag_line(p, q, layers=3)
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
            sx, sy = L.pol(g, fb['pit_r'] + 100.0 + 9.0 * j, ea - da - 22.0)          # clear of the pit berm (12 Nov review: one lay half in it)
            if float(L.slope(sx, sy)) < 8.0: W.prop('shell_105', sx, sy, gz(sx, sy) + 3.0, ea + 38.0 + rng.uniform(-4, 4), check=True)
        clutter(rng, [('ammo_crate', 2), ('ammo_can', 2), ('jerry_can', 1)], *L.pol(g, fb['pit_r'] + 70.0, ea), 20.0, 90.0)
    # ---- FDC bunker, the plotting table in its porch, antennas
    fx, fy = fb['fdc']; fyaw = fb['fdc_yaw']
    W.prop('fdc_bunker', fx, fy, None, fyaw)
    tx, ty = local(fx, fy, fyaw, 106.0, 0.0)
    W.prop('plot_table', tx, ty, None, fyaw + 90.0, reg=False)
    W.sites['board']['ct'] = dict(pos=(tx, ty, gz(tx, ty)), yaw=fyaw, seats=[local(fx, fy, fyaw, 215.0 + 44.0 * (j // 3), -60.0 + 60.0 * (j % 3)) for j in range(6)])
    for s_ in W.sites['board']['ct']['seats']: W.keep(s_[0], s_[1], 22.0, name='seat')
    # 12 Nov review: no antenna masts. Their guy anchors span 262 x 227 u and no such spot is left between the rotor cylinders, the pits
    # and the track (scanned on a 40-u grid); the converted comm stations at the TOC and the FDC carry the whip antennas instead
    # ---- ammo point: CONEXes and crate stacks behind a low wall
    ax, ay = fb['ammo']
    W.prop('conex', ax, ay, None, 200.0); W.prop('conex', ax + 6, ay + 88, None, 196.0)
    for (dx, dy, n) in ((-90, 0, 3), (-92, 46, 2), (-88, 92, 3), (-132, 30, 2)): W.stack('ammo_crate', ax + dx, ay + dy, rng.uniform(-10, 10), n, jitter=rng)     # playtest 1: the last stack 8 u east, against the new battered wall, not in it
    W.bag_line((ax - 176, ay - 90), (ax - 176, ay + 140), layers=2); W.bag_line((ax - 140, ay - 96), (ax + 70, ay - 96), layers=2)      # playtest 1: 4 u east (the new wall is 30 thick at its base): ~8 u clear of the FDC bunker and the crates
    clutter(rng, [('ammo_can', 6), ('jerry_can', 2), ('drum_od', 2), ('ammo_crate', 3)], ax - 80, ay + 40, 30.0, 150.0)
    # ---- pads: PSP planking, the pad sign; helicopters come with the entities
    for k, (p, a) in enumerate(zip(fb['pads'], fb['pad_angles'])):
        W.prop('psp_pad', p[0], p[1], gz(*p) + 0.5, a, scale=fb['pad_scale'], reg=False)
        W.sites['pads']['ct'].append((p[0], p[1], gz(*p) + 2.0))
        W.fit('lz_sign', *L.pol(p, fb['pad_clear'] + 40.0, a + 180.0 + 30.0), a + 90.0, search=120.0, step=30.0)
    # ---- TOC and crew tents, antennas, cots and kit
    tx, ty = fb['toc']
    W.prop('gp_tent', tx, ty, None, fb['toc_yaw'], scale=0.85)        # a smaller GP tent: the full size touched the north-west bunker
    clutter(rng, [('cot', 2), ('rucksack', 3), ('jerry_can', 2), ('ammo_can', 2), ('radio_prc25', 1), ('drum_od', 1)], tx + 130.0, ty, 10.0, 90.0)
    # 12 Nov review: no crew tents besides the TOC: a GP tent needs 422 x 282 u and none is free inside the wire once the three rotor
    # cylinders (r 363 + 14), the gun pits and the track are kept clear (40-u grid scan, every yaw). Cots and kit stand by the TOC instead.
    clutter(rng, [('cot', 3), ('rucksack', 3), ('jerry_can', 1), ('ammo_can', 2)], tx - 140.0, ty - 140.0, 10.0, 110.0)
    # ---- tower with its ladder (the ladder side faces the base centre)
    tx, ty = fb['tower']; ta = ang((tx, ty))
    W.prop('guard_tower', tx, ty, None, ta)
    lx, ly = local(tx, ty, ta, -103.0, 0.0); c_, s_ = rot(ta)
    Rm = np.array([[c_, -s_, 0], [s_, c_, 0], [0, 0, 1.0]])
    vmesh.mesh_node(vmesh.oriented_box_mesh((lx, ly, z + 158.0), (9.0, 15.0, 156.0), Rm, LADDER), W.group, bake=False, shadows=False, visexclude=True)
    W.keep(*local(tx, ty, ta, -140.0, 0.0), 40.0, name='ladder')
    # ---- the quad .50 in its own sandbag ring (the gun part is an entity)
    qx, qy = fb['quad50']; qa = ang((qx, qy))
    f_ = W.PL.footprint(S.mv('quad50_mount'), qx, qy, gz(qx, qy), qa)
    W.prop('quad50_mount', qx, qy, None, qa)
    # pass 2 review: the mount's 24-u base was the step players dropped off into the gaps round the ring (build 4 pockets); the gunner
    # works it from the seat behind, so its top is clipped (from 20 u up; bullets pass)
    W.clip(P.rotate_z(P.box((f_['c'][0] - f_['h'][0], f_['c'][1] - f_['h'][1], gz(qx, qy) + 20.0), (f_['c'][0] + f_['h'][0], f_['c'][1] + f_['h'][1], gz(qx, qy) + 200.0), mat=TER.CLIP), math.degrees(f_['a']), (f_['c'][0], f_['c'][1], 0.0)))
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
    W.fit('water_trailer', *L.pol(c, 935.0, 230.0), 135.0, search=300.0, step=30.0, within=(c[0], c[1], wr - 70.0))     # the one free corner (south-west, between pit 3 and pad 1)
    W.fit('latrine', *L.pol(c, 1000.0, 228.0), 48.0, search=120.0, within=(c[0], c[1], wr - 60.0))
    # pass 2 review: the wind sock for the pads, beside the pad cluster but outside every rotor cylinder and off the approach lanes
    pc = (sum(p[0] for p in fb['pads']) / 3.0, sum(p[1] for p in fb['pads']) / 3.0)
    ws_ = W.scan('windsock', pc[0], pc[1], 760.0, (200.0,), step=30.0, max_slope=8.0, pad=10.0, ok=lambda x, y: W.rotor_ok(S.mv('windsock'), x, y) and math.hypot(x - c[0], y - c[1]) < wr - 60.0)
    # pass 2 review: the items world review 1 dropped inside the wire, re-tried with a scan of the whole wire disc (30-u grid, four yaws,
    # nearest the base centre first); whatever still finds no spot is listed in big_skips
    inside = lambda x, y: math.hypot(x - c[0], y - c[1]) < wr - 90.0
    yaws4 = tuple(ang((0, 0)) + d_ for d_ in (0.0, 90.0, 45.0, 135.0))
    got_ = {}
    # pass 4 review: the deploy point moved west (layout.firebase), which frees the ground between the FDC, pit 3 and pad 1's cylinder.
    # The culvert bunker and the M113 stand at the gate since pass 3 (placed below), so they are no longer tried inside; the second
    # latrine is tried only away from the wall (pass 2: its roof by the wall was the step onto the wall caps)
    # (build 2: nearest the centre first, it stood against the FDC bunker's back wall; now with a 40-u pad and 450 u out at least)
    inner = lambda x, y: 450.0 < math.hypot(x - c[0], y - c[1]) < wr - 280.0
    # Build 1 of pass 4: the water trailer (first in the scan) took the freed strip by the FDC (190 u wide between the spawn ring and the
    # wind sock: the mast needs 248 with its pad, a crew tent 260), so the latrine goes first and the trailer back to its pass 3 spot
    for nm_, yw_, kw_, ok_ in (('antenna_mast', yaws4, {}, inside), ('gp_tent', yaws4, dict(scale=0.85), inside), ('latrine', yaws4, {}, inner),
                               ('water_trailer', yaws4, {}, inside)):
        if nm_ in ('water_trailer', 'latrine') and W.count.get(S.mv(nm_), 0) >= (1 if nm_ == 'water_trailer' else 2): continue
        got_[nm_] = W.scan(nm_, c[0], c[1], wr - 90.0, yw_, step=30.0, max_slope=9.0, pad=40.0 if nm_ == 'latrine' else 10.0, ok=ok_, **kw_)
        if nm_ == 'gp_tent' and got_[nm_] is not None:
            clutter(rng, [('cot', 3), ('rucksack', 2), ('ammo_can', 1)], got_[nm_][0], got_[nm_][1], 10.0, 80.0)
    print('firebase pass 2: wind sock %s; %s' % ('placed' if ws_ else 'NOT placed', ', '.join('%s %s' % (k, 'placed' if v else 'no spot') for k, v in got_.items())))
    for a in (70.0, 118.0, 200.0, 255.0, 345.0):
        clutter(rng, [('drum_od', 1), ('ammo_crate', 1), ('rucksack', 1), ('jerry_can', 1), ('drum_rust', 1)], *L.pol(c, 940.0, a), 10.0, 90.0)
    clutter(rng, [('ammo_crate', 3), ('rucksack', 4), ('ammo_can', 4), ('radio_prc25', 1)], rx, ry, 150.0, 260.0)
    W.particle(*L.pol(c, 1000.0, 228.0), z + 40.0, SMOKESTACK)        # the burn barrel behind the latrine
    # ---- radios at the TOC and the FDC, vehicles parked beside the track (converted models; skipped when not in the addon)
    tx, ty = fb['toc']
    if M.is_ext(M.static('comm_station')):
        W.park('comm_station', *local(tx, ty, fb['toc_yaw'], 250.0, 70.0), fb['toc_yaw'] + 180.0, search=300.0, step=20.0, max_slope=11.0, within=(c[0], c[1], wr - 80.0))
        W.park('comm_station', *local(fx, fy, fyaw, 60.0, 112.0), fyaw + 90.0, search=300.0, step=20.0, max_slope=11.0, within=(c[0], c[1], wr - 80.0))     # 12 Nov review: the FDC radio did not fit at 160 / 6 deg
    n_v = 0
    # the M113 has no room inside the wire: it stands at the bridge and on the roads
    # 12 Nov review: no jeeps inside the wire either. The only free corner (south-west, between pit 3 and pad 1) holds the water trailer
    # and the latrine; one M151 is parked beside the spur road below the gate
    W.keep_path(L.ROADS[0][1][:3], L.ROADS[0][0] + 6.0, name='road')
    if M.is_ext(M.static('jeep_us') or '') and W.park('jeep_us', 2800.0, -2520.0, 200.0, search=360.0, max_slope=8.0) is not None: n_v += 1
    # weeds along the foot of the wall outside (the wire is never mown), ration boxes and cans in the lee of the bunkers
    for a in np.arange(3.0, 360.0, 5.0):
        if in_gap(a) or rng.uniform() < 0.3: continue
        x, y = L.pol(c, wr + 30.0 + rng.uniform(-4, 14), a); m = (S.WEEDS + S.FERNS[:2])[rng.randint(len(S.WEEDS) + 2)]
        if W.free(x, y, 8.0): W.prop(None, x, y, gz(x, y) - 1.5, rng.uniform(0, 360), stock=m, solid='0', reg=False, scale=rng.uniform(1.0, 1.6))
    for (p, a) in zip(fb['bunkers'], fb['bunker_angles']):
        clutter(rng, [('ammo_can', 2), ('ammo_crate', 1), ('rucksack', 1), ('jerry_can', 1)], *L.pol(p, 190.0, a + 180.0), 10.0, 70.0)
    # pass 2 review: dead-end gaps nobody walks into, only drops into (from the parapet of the south-west bunker, over the drums between
    # the quad .50 ring and pit 2, behind the sally blast wall) are clipped off: check_play's stuck cells of build 3 as column runs, each
    # inset 6 u so the clip never reaches a walkable neighbour. The firebase is laid out from its own RandomState: these stay put while
    # firebase() itself is unchanged; re-derive them (check_play pocket list) after any change here.
    # pass 4 review: re-derived after the deploy point moved (layout.firebase), on build 2 of pass 4 (check_play's stuck cells inside the
    # wire with the old fill taken out of the scene) and joined with the pass 2 cells (build 3: the new cells alone left the pass 2 remnant
    # pockets open again in the south-west yard). New cells: the ammo point's yard behind its crate stacks, the foot of the tower ladder,
    # one cell by pit 3 and two by the east bunker; build 4's three remnant cells (two in the south-west yard, one at the ladder foot)
    POCKET_FILL = [[2880, -3056, 2896, -3040, 620], [2896, -3280, 2912, -3264, 620], [2896, -3056, 2912, -3040, 620], [2912, -3312, 2928, -3264, 620], [2912, -3216, 2928, -3200, 620], [2912, -3040, 2928, -3024, 620], [2928, -3360, 2944, -3264, 620], [2928, -3216, 2944, -3200, 620], [2928, -3040, 2944, -3024, 620], [2944, -3392, 2960, -3264, 620], [2944, -3040, 2960, -3024, 620], [2960, -3408, 2976, -3264, 620], [2960, -3216, 2976, -3200, 620], [2976, -3392, 2992, -3264, 620], [2992, -3376, 3008, -3296, 620], [2992, -3264, 3008, -3248, 620], [2992, -3200, 3008, -3184, 620], [3008, -3376, 3024, -3248, 620], [3024, -3360, 3040, -3232, 620], [3040, -3344, 3056, -3232, 620], [3056, -3344, 3072, -3248, 620], [3056, -3216, 3072, -3184, 620], [3072, -3328, 3088, -3216, 620], [3088, -3632, 3104, -3616, 620], [3088, -3328, 3104, -3216, 620], [3104, -3360, 3120, -3296, 620], [3120, -3376, 3136, -3344, 620], [3136, -3408, 3152, -3376, 620], [3152, -3424, 3168, -3408, 620], [3200, -3552, 3216, -3536, 620], [3600, -3776, 3616, -3744, 620], [3616, -3760, 3632, -3744, 620], [3632, -3760, 3648, -3744, 620], [3664, -3776, 3680, -3760, 620], [3968, -2928, 3984, -2848, 620], [3984, -2928, 4000, -2912, 620], [3984, -2880, 4000, -2848, 620], [4000, -2928, 4016, -2912, 620], [4016, -2928, 4032, -2880, 620], [4016, -2800, 4032, -2784, 620], [4032, -2928, 4048, -2880, 620], [4032, -2800, 4048, -2784, 620], [4048, -2928, 4064, -2880, 620], [4048, -2800, 4064, -2784, 620], [4064, -2928, 4080, -2912, 620], [4096, -3536, 4112, -3520, 620], [4864, -3136, 4880, -3104, 620], [2944, -3216, 2960, -3200, 620], [2976, -3200, 2992, -3184, 620], [3648, -3776, 3664, -3760, 620], [3040, -3232, 3056, -3216, 620], [3056, -3248, 3072, -3232, 620], [3056, -3232, 3072, -3216, 620], [2992, -3296, 3008, -3280, 620], [2992, -3280, 3008, -3264, 620], [3104, -3616, 3120, -3600, 620], [3120, -3600, 3136, -3584, 620], [3504, -3472, 3520, -3456, 620]]
    # playtest 1: the new full-height sandbag walls (thicker, battered) left 4 small pockets by the quad .50's ammo stack, its drum, the
    # latrine and pit 2's ring end (check_play pocket_list cells, build 1); their cells are filled too
    for (x0_, y0_, x1_, y1_, z_) in POCKET_FILL:
        W.clip(P.box((x0_ + 6.0, y0_ + 6.0, z_ - 6.0), (x1_ - 6.0, y1_ - 6.0, z_ + 200.0), mat=TER.CLIP))
    # pass 3 review: the gate. Two of the items the wire has no room for stand outside it, on the flat apron south of the road where it
    # leaves the gate (the plateau runs 110-240 u past the wire there, z 620): the culvert bunker as the gate's guard bunker and the
    # M113 parked beside the road. Both stay south of the road: the routes out of the gate (check_play 1b) turn north-west. Placed last,
    # so nothing above (the firebase's RandomState, the POCKET_FILL cells) moves.
    def apron(x, y, lo=10.0, hi=48.0):
        r_ = math.hypot(x - c[0], y - c[1]); da_ = (ang((x, y)) - ga + 180.0) % 360.0 - 180.0
        return 1140.0 <= r_ <= 1330.0 and lo <= da_ <= hi
    gate_ = {}
    gate_['culvert_bunker'] = W.scan('culvert_bunker', *L.pol(c, 1220.0, ga + 16.0), 240.0, (ga + 90.0, ga - 90.0, ga, ga + 180.0), step=20.0, max_slope=8.0, pad=10.0, ok=apron)
    if M.is_ext(M.static('apc') or ''):
        gate_['m113'] = W.scan(None, *L.pol(c, 1240.0, ga + 30.0), 260.0, (ga, ga + 180.0, ga + 90.0), stock=M.static('apc'), step=20.0, max_slope=7.0, pad=40.0, ok=apron)
        if gate_['m113']:          # build 1 of pass 3: its roof was a stuck pocket (nobody climbs the APC): a clip over its footprint
            q_ = gate_['m113']; W.clip_footprint(W.PL.footprint(M.static('apc'), q_[0], q_[1], gz(q_[0], q_[1]), q_[2]), h=150.0)
    print('firebase gate (pass 3): %s' % ', '.join('%s %s' % (k, 'placed' if v else 'no spot') for k, v in gate_.items()))
    W.sites['seeds'] += [(c[0], c[1]), fb['rack']]
    G.lmres_box((c[0] - 200, c[1] - 200, z, c[0] + 200, c[1] + 200, z + 160), W.group)
    print('firebase: %d wall runs, %d mounts, %d parked vehicles' % (nb, len(W.sites['mounts']), n_v))


# ================================================================ T camp
def camp():
    rng = np.random.RandomState(4102)
    cp = L.camp(); c = cp['centre']; z = cp['z']
    road = L.ROADS[1][1]
    W.keep_path([road[-2], road[-1]], 66.0, name='road')
    for p in cp['spawns']: W.keep(p[0], p[1], 26.0, name='spawn')
    rx, ry = cp['rack']
    W.prop('arms_rack_t', rx, ry, None, 0.0); W.sites['kit']['t'] = (rx, ry, gz(rx, ry))
    # ---- helicopter stands: bare swept earth (no net over a pad: nothing may stand under the rotor disc), drums and cans beside them
    hip = M.pick('hip'); rr = hip['rotor_r']; hlen = hip['length']
    for k, p in enumerate(cp['pads']):
        W.sites['pads']['t'].append((p[0], p[1], gz(*p) + 1.0))
        for dx in np.arange(-hlen * 0.7 + 60.0, hlen * 0.3 + 1.0, 110.0): W.keep(*local(p[0], p[1], cp['pad_yaw'], dx, 0.0), 120.0, name='pad')
        hx, hy = local(p[0], p[1], cp['pad_yaw'], hip['hub'][0], hip['hub'][1])
        W.keep_disc(hx, hy, rr + 74.0)                                                # the whole rotor cylinder (rotor radius + 60): nothing optional stands in it
        clutter(rng, [('drum_rust', 2), ('jerry_can', 2), ('rocket_crate', 1)], *local(p[0], p[1], cp['pad_yaw'], 120.0, rr + 170.0), 10.0, 80.0)
    # ---- keep-outs of everything fixed first (pits, AA pits, the trail south), then the FDC hut, so optional dressing sees them all
    W.keep_path(L.ROADS[6][1][:2], 44.0, name='road')
    for g in cp['rockets']: W.keep(g[0], g[1], cp['pit_r'] + 30.0, name='pit')
    for a in cp['aa']: W.keep(a[0], a[1], 116.0, name='pit')
    fx, fy = cp['fdc']; fyaw = cp['fdc_yaw']
    W.prop('camp_hut', fx, fy, None, fyaw)
    tx, ty = local(fx, fy, fyaw, -40.0, 0.0)
    W.prop('plot_table_t', tx, ty, None, fyaw + 90.0, reg=False)
    W.sites['board']['t'] = dict(pos=(tx, ty, gz(tx, ty)), yaw=fyaw, seats=[local(fx, fy, fyaw, 196.0 + 46.0 * (j // 4), -90.0 + 60.0 * (j % 4)) for j in range(8)])
    for s_ in W.sites['board']['t']['seats']: W.keep(s_[0], s_[1], 22.0, name='seat')
    # ---- rocket pits: earth berm open toward the camp centre, the rocket crates (rack station) outside the entrance
    for k, g in enumerate(cp['rockets']):
        ea = math.degrees(math.atan2(c[1] - g[1], c[0] - g[0]))
        W.berm_arc(g[0], g[1], cp['pit_r'] + 26.0, ea + 32.0, ea + 328.0)
        yaw = math.degrees(math.atan2(-g[1], -g[0]))
        W.sites['guns']['t'].append((g[0], g[1], gz(*g), yaw))
        for rr_, da in [(rr0, sgn * a_) for rr0 in (96.0, 130.0, 170.0, 210.0) for a_ in (0.0, 25.0, 50.0, 75.0, 100.0) for sgn in (1, -1)]:      # the first clear spot at the entrance
            rx, ry = L.pol(g, cp['pit_r'] + rr_, ea + da)
            if W.stack('rocket_crate', rx, ry, ea + da + 90.0, 2, check=True) > 0: break
        else:
            print('WARNING no clear spot for the rocket crates of pit %d' % (k + 1)); rx, ry = L.pol(g, cp['pit_r'] + 96.0, ea)
        W.sites['racks']['t'].append((rx, ry, gz(rx, ry)))
        W.prop('rocket_crate', *L.pol(g, cp['pit_r'] + 100.0, ea - da - 40.0), None, ea + rng.uniform(40, 80), check=True)
    # ---- AA pits: DShK on its stand in a small berm
    for k, a in enumerate(cp['aa']):
        ea = math.degrees(math.atan2(c[1] - a[1], c[0] - a[0])); yaw = ea + 180.0
        W.berm_arc(a[0], a[1], 112.0, ea + 36.0, ea + 324.0, base=48.0, top=16.0, h=30.0)
        W.mount('dshk', 't', a[0], a[1], yaw, cover=False)
    # ---- hooches on the north-west side
    nh = 0
    for k, (hx, hy, hyaw) in enumerate(cp['hooches']):
        nm = ('hooch_a', 'hooch_c', 'hooch_b')[k % 3]
        if W.prop(nm, hx, hy, None, hyaw, fit='min', check=True, pad=4.0) is None: continue
        nh += 1
        dx, dy = local(hx, hy, hyaw, 225.0, 0.0)
        clutter(rng, [('rice_basket', 2), ('water_jar', 1), ('rucksack', 1), ('ammo_crate', 1)], dx, dy, 10.0, 80.0)
    # more huts under the trees on the north side wherever one fits, a fenced garden plot and a cook corner beside every hut
    for (dx_, dy_, hyaw) in ((-330.0, 1010.0, -80.0), (420.0, 880.0, -120.0), (-1010.0, 560.0, 20.0), (640.0, 1010.0, -100.0)):
        if nh >= 8: break
        q = W.fit(('hooch_b', 'hooch_a', 'hooch_c')[nh % 3], c[0] + dx_, c[1] + dy_, hyaw, search=160.0, max_slope=12.0, fit='min', pad=8.0, within=(c[0], c[1], L.T_PLATEAU_R - 60.0))
        if q is None: continue
        nh += 1
        clutter(rng, [('rice_basket', 2), ('water_jar', 1), ('rucksack', 1)], *local(q[0], q[1], hyaw, 225.0, 0.0), 10.0, 80.0)
    for k, (hx, hy, hyaw) in enumerate(cp['hooches']):
        gx_, gy_ = local(hx, hy, hyaw, -40.0, 250.0 if k % 2 else -250.0)
        for (ox, oy, fyaw) in ((-70, 0, 90.0), (70, 0, 90.0), (0, 64, 0.0)):
            fx_, fy_ = local(gx_, gy_, hyaw, ox, oy)
            W.prop('bamboo_fence', fx_, fy_, None, hyaw + fyaw, fit='min', check=True, pad=3.0)
        for _ in range(4):
            px_, py_ = local(gx_, gy_, hyaw, rng.uniform(-50, 50), rng.uniform(-40, 40)); m = (S.TARO + S.TROPICAL_S)[rng.randint(len(S.TARO) + len(S.TROPICAL_S))]
            if W.free(px_, py_, 10.0): W.prop(None, px_, py_, gz(px_, py_) - 1.0, rng.uniform(0, 360), stock=m, solid='0', reg=False, scale=rng.uniform(0.5, 0.8))
        clutter(rng, [('drying_rack', 1), ('fish_trap', 1), ('haystack', 1)], *local(hx, hy, hyaw, -230.0, 0.0), 10.0, 70.0, face=hyaw)
    for a in cp['aa']: clutter(rng, [('ammo_can', 2), ('ammo_crate', 1)], a[0], a[1], 140.0, 190.0)
    # ---- ammo point: rocket crates, PAVN ammunition cases; the radio by the FDC hut; cook fires; parked vehicles
    ax, ay = cp['ammo']
    for (dx, dy, n) in ((0, 0, 3), (60, -30, 2), (-50, 40, 2), (20, 70, 1)): W.stack('rocket_crate', ax + dx, ay + dy, rng.uniform(0, 180), n, jitter=rng)
    case = M.static('ammo_case_nva')
    for (dx, dy, n) in ((-120, -60, 3), (-150, 20, 2), (110, 60, 2), (130, -80, 3)):
        lo_, hi_ = W.B(case); yw = rng.uniform(0, 180)
        for q in range(n):
            if W.prop(None, ax + dx, ay + dy, gz(ax + dx, ay + dy) + q * (hi_[2] - 0.5), yw + rng.uniform(-5, 5), stock=case, check=q == 0, pad=1.0,
                      tag='stack' if q else None) is None: break
    W.sprop('ammo_case_nva_open', ax + 40.0, ay - 110.0, None, rng.uniform(0, 360), check=True, pad=2.0)
    W.sprop('ammo_case_nva_open', ax - 60.0, ay + 120.0, None, rng.uniform(0, 360), check=True, pad=2.0)
    if M.is_ext(M.static('comm_station')): W.park('comm_station', *local(fx, fy, fyaw, 30.0, 150.0), fyaw + 180.0, search=300.0, step=20.0, max_slope=11.0)
    clutter(rng, [('ammo_crate', 3), ('ammo_can', 3), ('rice_basket', 2)], ax, ay, 60.0, 190.0)
    for (x, y) in cp['fires']:
        if W.prop('cook_fire', x, y, None, rng.uniform(0, 360), check=True, pad=6.0) is None: continue
        W.particle(x, y, gz(x, y) + 10.0, FIRE); W.sites['fires'].append((x, y, gz(x, y) + 10.0))
        clutter(rng, [('rice_basket', 2), ('water_jar', 2), ('log_fallen', 1)], x, y, 60.0, 130.0)
    n_v = 0
    for nm, dx, dy, yw in (('bm21', 760.0, 60.0, 187.0), ('truck_nva', 900.0, -230.0, 172.0), ('jeep_nva', -560.0, 60.0, 20.0), ('jeep_nva', 260.0, -140.0, 172.0),
                           ('zpu4', -450.0, -700.0, 250.0)):
        if M.is_ext(M.static(nm) or '') and W.park(nm, c[0] + dx, c[1] + dy, yw, search=700.0, within=(c[0], c[1], L.T_PLATEAU_R - 220.0)) is not None: n_v += 1
    for (dx, dy, yaw) in ((170, 70, 80.0), (-620, 300, 20.0), (780, 70, 170.0)):
        W.prop('propaganda_board', c[0] + dx, c[1] + dy, None, yaw, check=True, pad=4.0)
    for a in (100.0, 200.0, 260.0, 330.0):
        clutter(rng, [('drum_rust', 1), ('rocket_crate', 1), ('rucksack', 2), ('rice_basket', 1), ('bamboo_fence', 1)], *L.pol(c, 520.0, a), 20.0, 120.0)
    for a in (20.0, 65.0, 140.0, 180.0, 230.0, 295.0):                # the lived-in look: more of everything between the pits
        clutter(rng, [('rice_basket', 2), ('water_jar', 1), ('rucksack', 2), ('ammo_can', 2), ('cot', 1), ('log_fallen', 1), ('jerry_can', 1)], *L.pol(c, rng.uniform(250.0, 760.0), a), 20.0, 130.0)
    if cp['fires']: W.particle(cp['fires'][0][0], cp['fires'][0][1], gz(*cp['fires'][0]) + 40.0, SMOKESTACK)
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
    print('camp: %d hooches, %d punji patches, %d parked vehicles' % (nh, n, n_v))


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
    # the threshing floor (layout.ISLAND): a field hut, haystacks, a cart; 12 Nov review: flag A had 4 pieces of head-height cover
    # 12 Nov review (final): no field hut here. At (fx - 36, fy + 78) its south wall stood 18 u from the pole and, with the stacks and
    # baskets round it, closed the flag in (check_play 1: flag A unreachable). The flag stands in the open middle of the floor.
    W.keep(fx, fy, 70.0, name='flag'); W.keep(fx, fy - 60.0, 30.0, name='seed')
    for (dx, dy) in ((108.0, -78.0), (-112.0, -70.0), (118.0, 84.0), (-150.0, 60.0)):
        W.fit('haystack', fx + dx, fy + dy, rng.uniform(0, 360), search=60.0, step=20.0, pad=2.0, within=(fx, fy, L.ISLAND[2] + 10.0))
    W.stack('ammo_crate', fx + 150.0, fy + 10.0, rng.uniform(0, 180), 4, jitter=rng)
    # rice-straw stacks standing in the cells round the island (head-height cover in the open water; the flag itself stays reachable
    # from every side: the second review build closed it in with a crate stack beside the pole)
    for (dx, dy) in ((-212.0, -151.0), (212.0, 151.0), (212.0, -151.0), (-212.0, 151.0), (-212.0, -454.0), (212.0, -454.0), (-212.0, 454.0), (212.0, 454.0)):      # the middle of the cells round the junction
        dx += rng.uniform(-40, 40); dy += rng.uniform(-36, 36)                                # pass 2 review: not on the exact cell centres
        x_, y_ = fx + dx, fy + dy + float(L.river_y(fx + dx)) - float(L.river_y(fx))
        if L.in_paddies(np.array([x_]), np.array([y_]))[0] and W.free(x_, y_, 60.0):
            W.prop('haystack', x_, y_, gz(x_, y_) - 3.0, rng.uniform(0, 360), check=True, pad=4.0, tag='water')
    W.prop('ox_cart', fx + 6.0, fy - 108.0, None, 168.0, check=True)
    W.prop('drying_rack', fx - 128.0, fy + 6.0, None, 84.0, check=True, pad=2.0)
    clutter(rng, [('rice_basket', 4), ('ammo_crate', 1), ('water_jar', 2), ('fish_trap', 1)], fx, fy, 110.0, 150.0)
    for i in range(0, 5):                                  # bamboo on the dike junctions round the flag (wade round them)
        for j in range(0, 4):
            jx = L.PADDY_X0 + i * L.PADDY_CELL_X; jy = float(L.river_y(jx)) + L.PADDY_YR0 + j * L.PADDY_CELL_Y
            d_ = math.hypot(jx - fx, jy - fy)
            if d_ < 220.0 or d_ > 620.0: continue
            W.prop('bamboo_clump', jx + rng.uniform(-6, 6), jy + rng.uniform(-6, 6), gz(jx, jy) - 3.0, rng.uniform(0, 360), trunk=S.TRUNK_MV['bamboo_clump'], scale=rng.uniform(0.8, 1.0), tag='tree')     # rooted in the dike crest
    # the farm on its terrace south of the paddies
    c = L.FARM
    farm = ((-170, 90, -40.0, 'hooch_a'), (170, 110, 215.0, 'hooch_b'), (60, -230, 95.0, 'hooch_c'))
    for (dx, dy, yaw, nm) in farm: W.prop(nm, c[0] + dx, c[1] + dy, None, yaw, fit='min')
    for (dx, dy, yaw, nm) in farm:
        clutter(rng, [('rice_basket', 2), ('water_jar', 2)], *local(c[0] + dx, c[1] + dy, yaw, 225.0, 0.0), 10.0, 60.0)
    W.prop('pig_pen', c[0] - 230, c[1] - 150, None, 20.0, fit='min', check=True)
    W.prop('pig_pen', c[0] + 250, c[1] - 120, None, 100.0, fit='min', check=True)
    W.keep(c[0], c[1] + 300.0, 40.0, name='seed')                                     # the farm's nav seed
    W.fit('ox_cart', c[0] + 40, c[1] + 40, 150.0, search=260.0, step=30.0)          # 12 Nov review: re-fitted (blocked by a hooch)
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
    W.sites['seeds'] += [(fx, fy - 60.0), (c[0], c[1] + 300.0)]           # the farm seed on the open ground north of the huts (their yard is a 40-u gap)
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
            W.bag_line((bx - 150, y_out + s * 40), (bx - 20, y_out + s * 40), layers=4)
            W.bag_line((bx + 20, y_out + s * 150), (bx + 150, y_out + s * 150), layers=4)
    W.surface(bx - wdeck / 2, by - half, bx + wdeck / 2, by + half, dz)
    W.prop('bridge_pier', bx, by, dz + lo[2], 90.0, tag='bridge')            # its origin is the bearing seat under the span ends
    flag_site('b', bx + 50.0, by, dz, crate=(bx - 34.0, by - 130.0, dz), crate_yaw=90.0, yaw=90.0)
    # 12 Nov review: the deck was a 1200-u shooting gallery (3 pieces of head-height cover). Staggered four-course sandbag blocks from
    # alternate trusses, at least 150 u apart, and a CONEX: one side of the deck always stays open (check_play 1b: the first try put an ox
    # cart beside a block and closed the deck, so CT walked round by the north ramp, 1500 u further than T)
    for (sy, side) in ((-470.0, -1), (-320.0, 1), (250.0, -1), (430.0, 1), (560.0, -1)):
        W.bag_line((bx + side * 68.0, by + sy), (bx + side * 2.0, by + sy), layers=4, z=dz)
    W.prop('conex', bx - 30.0, by + 110.0, dz, 92.0, tag='bridge')
    for (dx, dy, n) in ((44.0, 330.0, 2), (-48.0, -210.0, 2)): W.stack('ammo_crate', bx + dx, by + dy, rng.uniform(0, 180), n, z=dz, check=False)
    # and fighting positions on both banks beside the piers (four-course bags), the fight under the span
    for s_ in (-1, 1):
        for sx_ in (-1, 1):
            yb_ = by + s_ * (L.BANK_W + 70.0); x0_ = bx + sx_ * 170.0
            if gz(x0_, yb_) > L.WATER_Z + 12.0 and float(L.slope(x0_, yb_)) < 18.0: W.bag_line((x0_, yb_), (x0_ + sx_ * 96.0, yb_), layers=4)
    for s_ in (-1, 1):
        for (dx, dyb) in ((-230.0, 60.0), (250.0, 90.0), (-380.0, 150.0), (400.0, 40.0)):
            px_ = bx + dx; py_ = by + s_ * (L.BANK_W + dyb)
            if gz(px_, py_) > L.WATER_Z + 16.0 and float(L.slope(px_, py_)) < 20.0:
                W.prop('bamboo_clump', px_, py_, gz(px_, py_) - 3.0, rng.uniform(0, 360), trunk=S.TRUNK_MV['bamboo_clump'], check=True, pad=20.0, scale=rng.uniform(0.85, 1.05))
    # the burnt truck is 135 wide and the deck 160: on the span it would close the bridge, so it sits run off the road at the south ramp
    # south head: the French bunker and the neutral M2; north head: the shot-up checkpoint
    name, kind, (mx, my), myaw = L.mounted_guns()[0]
    W.prop('french_bunker', bx - 300.0, by - half - 150.0, None, 90.0, fit='min')
    W.mount('m2', 'any', mx, my, myaw)
    # the burnt truck: run off the road south of the ramp (too wide for the deck), clear of the gun pit and the spawns
    tp_ = W.park('truck_us', bx + 330.0, by - half - ramp - 220.0, 62.0, search=320.0, max_slope=10.0)
    if tp_ is not None:
        W.particle(tp_[0], tp_[1], gz(*tp_) + 70.0, SMOKE_DARK); debris(rng, tp_[0], tp_[1], 150.0, 260.0)
    W.prop('checkpoint', bx, by + half + ramp + 150.0, None, 90.0, fit='min', dz=2.0)        # 12 Nov review: the ramp's blend poked 1.5 u through its floor
    W.sprop('apc', bx - 300.0, by + half + 250.0, None, 35.0, fit='min', check=True)
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
    road_huts = []
    for t, lat in ((350.0, 240.0), (560.0, 240.0), (300.0, 440.0), (470.0, 450.0)):
        for q in legs:
            dq = math.hypot(q[0] - c[0], q[1] - c[1]); ux, uy = (q[0] - c[0]) / dq, (q[1] - c[1]) / dq
            for sd in (1, -1):
                road_huts.append((c[0] + ux * t - uy * sd * lat, c[1] + uy * t + ux * sd * lat, math.degrees(math.atan2(ux * sd, -uy * sd)) + 180.0,
                                  ('hooch_b', 'hooch_a', 'hooch_c')[(len(huts) + len(road_huts)) % 3]))
    nh = 0; placed = []
    def put_huts(lst):
        nonlocal nh
        for (x, y, yaw, nm) in lst:
            yaw += rng.uniform(-8, 8)
            if nh >= 10 or math.hypot(x - c[0], y - c[1]) > 700.0 or W.prop(nm, x, y, None, yaw, fit='min', check=True, pad=4.0) is None: continue
            nh += 1; placed.append((x, y, yaw))
    put_huts(huts)
    # pass 2 review: the yard re-planned. Its own pieces go right after the designed huts (before the extra huts take the room), at
    # designed spots: the spirit house on the open north side between the school and the west road, the market stalls along the
    # road edges (a market street on the temple road, one stall on the south road), the ox cart by the west road
    # pass 3 review: the road-side huts came before the stalls and took the lane edges (the third stall never fitted): now the market
    # lane on the temple road is laid out first, three stalls facing each other across it with their baskets round them, then the
    # road-side huts fill in behind and around it; the spirit house gets its offerings
    def road_pt(q, t, lat):
        dq = math.hypot(q[0] - c[0], q[1] - c[1]); ux, uy = (q[0] - c[0]) / dq, (q[1] - c[1]) / dq
        return c[0] + ux * t - uy * lat, c[1] + uy * t + ux * lat, math.degrees(math.atan2(uy, ux))
    leg_s, leg_w, leg_e = L.ROADS[1][1][1], L.ROADS[1][1][3], L.ROADS[5][1][1]
    sh_ = W.fit('shrine', *L.pol(c, 250.0, 112.0), 292.0, search=150.0, step=20.0, pad=6.0, within=(c[0], c[1], 700.0))
    if sh_ is not None:          # offerings on the ground in front of the spirit house (it faces 292 deg: its front is local +x)
        for (fw_, lt_, nm_) in ((52.0, -18.0, 'rice_basket'), (50.0, 20.0, 'water_jar')):
            W.prop(nm_, *local(sh_[0], sh_[1], 292.0, fw_, lt_), None, rng.uniform(0, 360), check=True, pad=2.0)
    nst = 0
    for (q, t, lat, flip) in ((leg_e, 240.0, 132.0, 0.0), (leg_e, 300.0, -132.0, 180.0), (leg_e, 380.0, 132.0, 0.0), (leg_e, 440.0, -132.0, 180.0),
                              (leg_s, 250.0, -132.0, 180.0), (leg_w, 250.0, 132.0, 0.0)):
        if nst >= 3: break
        x_, y_, yw_ = road_pt(q, t, lat)
        if W.fit('market_stall', x_, y_, yw_ + flip + 180.0, search=60.0, step=15.0, pad=4.0, within=(c[0], c[1], 700.0)) is not None:
            nst += 1
            clutter(rng, [('rice_basket', 3), ('water_jar', 1), ('fish_trap', 1)], *road_pt(q, t, lat + (40.0 if lat > 0 else -40.0))[:2], 20.0, 70.0)
    x_, y_, yw_ = road_pt(leg_w, 330.0, -150.0)
    W.fit('ox_cart', x_, y_, yw_ + 170.0, search=200.0, step=30.0, within=(c[0], c[1], 760.0))
    # two drying platforms at eave height beside huts (posts, a deck, a ladder, a rail): the "roof access" of the design. A hut's own
    # roof is a pitched thatch with a box hull: standing on that floats, a deck does not.
    npl = 0
    # pass 2 review: beside a hut first; else a free-standing platform on the yard ring (the second one never found a hut-side spot)
    # pass 3 review: beside the designed huts before the road-side huts take their flanks; a ring spot only after all the huts
    def platforms(cands):
      nonlocal npl
      for (x, y, yaw, *fr) in cands:
        if npl >= 2: break
        for (sd, fwd, lat) in ([(1, 0.0, 0.0), (-1, 0.0, 0.0)] if fr[0] else [(sd_, f_, l_) for l_ in (190.0, 240.0, 290.0) for f_ in (20.0, -70.0, 100.0, -150.0, 170.0) for sd_ in (1, -1)]):
            px, py = local(x, y, yaw, fwd, sd * lat)
            if math.hypot(px - c[0], py - c[1]) > 730.0 or float(L.slope(px, py)) > (12.0 if fr[0] else 8.0): continue
            if not all(W.free(*local(px, py, yaw, ox, oy), 26.0) for ox in (-60, 0, 60) for oy in (-50, 0, 50)) or not W.free(*local(px, py, yaw, 100.0, 0.0), 30.0): continue
            g0 = min(gz(*local(px, py, yaw, ox, oy)) for ox in (-60, 60) for oy in (-48, 48)); zt = max(gz(*local(px, py, yaw, ox, oy)) for ox in (-60, 60) for oy in (-48, 48)) + 92.0
            parts = [P.box((-64, -52, zt - 6.0), (64, 52, zt), mat=WOOD)] + [P.box((ox - 5, oy - 5, g0 - 12.0), (ox + 5, oy + 5, zt - 6.0), mat=WOOD) for ox in (-56, 56) for oy in (-44, 44)]
            parts += [P.box((-64, sd * 46 - 3, zt), (64, sd * 46 + 3, zt + 4.0), mat=WOOD)]
            for sh in parts:
                sh = P.translate(sh, (px, py, 0.0)); W.shape(P.rotate_z(sh, yaw, (px, py, 0.0)))
            for ox in (-40.0, 40.0):                        # a rail on the outer side
                W.prop('bamboo_fence_64', *local(px, py, yaw, ox, sd * 47.0), zt, yaw, tag='platform', reg=False)
            lx, ly = local(px, py, yaw, 70.0, 0.0)
            W.ladder(lx, ly, gz(lx, ly), zt, yaw)
            for ox in (-56, 0, 56):
                for oy in (-44, 0, 44): W.keep(*local(px, py, yaw, ox, oy), 30.0, name='platform')
            rng.uniform(0, 360)       # (keeps the village's random sequence) pass 3: the basket stood in the rack and the rail on a turned deck (check_world): it waits at the ladder's foot now
            W.prop('rice_basket', *local(px, py, yaw, 112.0, sd * 34.0), None, yaw + 20.0, check=True, pad=2.0)
            W.prop('drying_rack', *local(px, py, yaw, -10.0, -sd * 30.0), zt, yaw, tag='platform', reg=False)
            W.sites['waypoints'].append(('village platform %d' % (npl + 1), px, py, zt))
            npl += 1; break
    platforms([tuple(q) + (False,) for q in placed])
    put_huts(road_huts)
    # pass 3 review: the road-side and extra huts come after the market lane and the two platforms; the extras stay on the terrace
    # (r 620 at most: at 680-700 they took the knocked-out T-54's and a bamboo thicket's spots below it)
    # 12 Nov review: 6 of the 9 designed huts stood. The rest go wherever one fits on the terrace (smallest first)
    for (r_, a_) in ((330.0, 300.0), (360.0, 160.0), (560.0, 330.0), (300.0, 250.0), (585.0, 275.0), (560.0, 150.0), (590.0, 40.0), (360.0, 5.0),
                     (600.0, 210.0), (610.0, 120.0), (600.0, 300.0), (620.0, 20.0), (520.0, 60.0), (620.0, 170.0), (620.0, 340.0),
                     (680.0, 300.0), (680.0, 100.0), (680.0, 0.0), (700.0, 150.0), (700.0, 50.0), (700.0, 350.0)):      # (not 200-280 deg below the terrace: T-54, thicket)
        if len(placed) >= 9: break
        x, y = L.pol(c, r_, a_); yaw = a_ + 180.0 + rng.uniform(-10, 10)
        q = None
        for yw_ in (yaw, yaw + 90.0):        # gable end or eave to the yard, whichever fits
            q = W.fit('hooch_b', x, y, yw_, search=180.0, step=30.0, max_slope=12.0, fit='min', pad=8.0, within=(c[0], c[1], 780.0))
            if q is not None: yaw = yw_; break
        if q is not None: placed.append((q[0], q[1], yaw))
    # pass 4 review: the 9th hut. The list above leaves 8 since pass 3 (the market lane and the second platform took one hut's room);
    # one more ring of spots on the terrace edge (not 195-285 deg: T-54, thicket), each at least 300 u from every hut already standing
    # (the huts here stand 300-400 apart) and fitted with a 24-u pad, so it stands in its own yard rather than wedged between neighbours
    for r_ in (620.0, 660.0, 700.0, 740.0):
        for a_ in np.arange(0.0, 360.0, 10.0):
            if len(placed) >= 9: break
            if 195.0 < a_ < 285.0: continue
            x, y = L.pol(c, r_, a_)
            if min(math.hypot(x - p[0], y - p[1]) for p in placed) < 300.0: continue
            yaw = a_ + 180.0
            q = None
            for yw_ in (yaw, yaw + 90.0):
                q = W.fit('hooch_b', x, y, yw_, search=60.0, step=30.0, max_slope=14.0, fit='min', pad=24.0, within=(c[0], c[1], 790.0))
                if q is not None: yaw = yw_; break
            if q is not None: placed.append((q[0], q[1], yaw)); print('village: 9th hut at (%.0f, %.0f), r %.0f' % (q[0], q[1], math.hypot(q[0] - c[0], q[1] - c[1])))
    platforms([(c[0] + r_ * math.cos(math.radians(a_)), c[1] + r_ * math.sin(math.radians(a_)), a_ + 90.0, True) for r_ in (330.0, 400.0, 470.0, 540.0, 610.0)
               for a_ in np.arange(5.0, 360.0, 12.0) if not 195.0 < a_ < 285.0])
    # pass 2 review: three cook fires in front of huts (the yard ones were crowded out), each with its pots and a smoke column on one
    nfire = 0
    for (x, y, yaw) in placed:
        if nfire >= 3: break
        for (fw_, lt_) in ((200.0, 70.0), (200.0, -70.0), (230.0, 0.0), (-200.0, 60.0), (-200.0, -60.0)):
            q = W.fit('cook_fire', *local(x, y, yaw, fw_, lt_), rng.uniform(0, 360), search=60.0, step=20.0, pad=8.0, within=(c[0], c[1], 760.0))
            if q is not None:
                W.particle(q[0], q[1], gz(*q) + 10.0, FIRE); W.sites['fires'].append((q[0], q[1], gz(*q) + 10.0))
                if nfire == 1: W.particle(q[0], q[1], gz(*q) + 40.0, SMOKESTACK)
                clutter(rng, [('water_jar', 1), ('rice_basket', 1), ('log_fallen', 1)], q[0], q[1], 50.0, 90.0)
                nfire += 1; break
    nh = 0
    for (x, y, yaw) in placed:
        nh += 1
        # a fenced garden on one side of the hut: taro and greens in rows
        sd0 = 1 if nh % 2 else -1; spot = None
        for (sd, lat, fw) in ((sd0, 185.0, -70.0), (-sd0, 185.0, -70.0), (sd0, 230.0, 0.0), (-sd0, 230.0, 0.0), (sd0, 185.0, 60.0), (-sd0, 185.0, 60.0)):
            gx_, gy_ = local(x, y, yaw, fw, sd * lat)
            if all(W.free(*local(gx_, gy_, yaw, ox, oy), 26.0) for ox in (-50, 0, 50) for oy in (-36, 0, 36)) and math.hypot(gx_ - c[0], gy_ - c[1]) < 760.0: spot = (gx_, gy_, sd); break
        if spot is not None:
            gx_, gy_, sd = spot
            for (ox, oy, fyaw) in ((-62, 0, 90.0), (0, sd * 56, 0.0)):         # two sides only: three and the hut wall made a pen (a stuck pocket)
                W.prop('bamboo_fence', *local(gx_, gy_, yaw, ox, oy), None, yaw + fyaw, fit='min', check=True, pad=3.0)
            for _ in range(5):
                px_, py_ = local(gx_, gy_, yaw, rng.uniform(-48, 48), rng.uniform(-40, 40)); m = (S.TARO + S.TROPICAL_S)[rng.randint(len(S.TARO) + len(S.TROPICAL_S))]
                if W.free(px_, py_, 10.0): W.prop(None, px_, py_, gz(px_, py_) - 1.0, rng.uniform(0, 360), stock=m, solid='0', reg=True, scale=rng.uniform(0.5, 0.8))     # registered: later clutter keeps out of the beds
        clutter(rng, [('rice_basket', 2), ('water_jar', 1)], *local(x, y, yaw, 215.0, 0.0), 10.0, 50.0)
        bx_, by_ = local(x, y, yaw, -210.0, 0.0)
        clutter(rng, [(('haystack', 'pig_pen', 'drying_rack')[nh % 3], 1)], bx_, by_, 0.0, 60.0, face=yaw)
        if nh == 3:      # the bombed east side: smoke from a burnt hut
            W.particle(x, y, gz(x, y) + 150.0, SMOKESTACK)
    for a in np.arange(15.0, 360.0, 45.0):                  # 12 Nov review: the yard read empty between the huts
        clutter(rng, [('rice_basket', 2), ('water_jar', 2), ('fish_trap', 1), ('drying_rack', 1), ('haystack', 1)], *L.pol(c, rng.uniform(260.0, 520.0), a), 20.0, 110.0)
    # ---- hedge banks and bamboo thickets round the outside of the terrace (converted foliage; walk-through), wherever one fits
    nx_ = 0
    for logical, want, a0 in (('hedge', 5, 6.0), ('bamboo_thicket', 8, 0.0)):
        model = M.static(logical); got = 0
        if not M.is_ext(model): continue
        for a in np.arange(a0, 360.0 + a0, 12.0):
            if got >= want: break
            for rr_ in (690.0, 730.0, 770.0):
                x, y = L.pol(c, rr_, a)
                rd_, hw_ = L.road_dist(np.array([x]), np.array([y]))
                if rd_[0] < hw_[0] + 100.0 or float(L.slope(x, y)) > 22.0: continue
                if W.prop(None, x, y, None, a + (0.0 if logical == 'hedge' else rng.uniform(0, 360)), stock=model, solid='0', fit='min', check=True, pad=30.0,
                          _quiet=True) is not None: got += 1; break
        nx_ += got
    for a in np.arange(0.0, 360.0, 13.0):                         # broken fence ring at the edge of the terrace
        if rng.uniform() < 0.45: continue
        x, y = L.pol(c, 610.0 + rng.uniform(-14, 14), a)
        W.prop('bamboo_fence', x, y, None, a + 90.0 + rng.uniform(-6, 6), fit='min', check=True, pad=6.0)
    clutter(rng, [('rice_basket', 8), ('water_jar', 6), ('haystack', 3), ('drying_rack', 3), ('fish_trap', 2), ('log_fallen', 2)], c[0], c[1], 120.0, 560.0)
    for a in np.arange(15.0, 360.0, 40.0):                        # palms between the huts
        x, y = L.pol(c, rng.uniform(250, 600), a + rng.uniform(-12, 12)); m = S.PALMS[rng.randint(len(S.PALMS))]
        W.prop(None, x, y, gz(x, y) - 4.0, rng.uniform(0, 360), stock=m, trunk=S.TRUNK[m], check=True, pad=30.0, scale=rng.uniform(0.9, 1.15))
    W.sites['seeds'] += [c]
    print('village: %d hooches, %d platforms, %d market stalls, %d cook fires, shrine %s, %d hedges / thickets' % (nh, npl, nst, nfire, 'yes' if sh_ else 'NO', nx_))


def temple():
    rng = np.random.RandomState(4114)
    c = L.TEMPLE; z0 = gz(*c)
    def drape(x, y, z, yaw, width, hang):
        """playtest 1: a vine drape whose top lies on a real edge at z (vine_drape: 96 wide, hangs 153 u at scale 1; its local +y is the
        way the face looks, so yaw = the face's outward direction - 90)"""
        return W.prop('vine_drape', x, y, z, yaw, scale=(width / 96.0, 1.0, hang / 153.0), solid='0', reg=False, tag='hanging')
    t1, t2 = 28.0, 64.0                                      # terrace tops above the knoll
    # world geometry: the lower terrace (courtyard), the upper terrace (tower base) and stairs on every side
    HT = 340.0
    W.shape(P.box((c[0] - HT, c[1] - HT, z0 - 120), (c[0] + HT, c[1] + HT, z0 + t1), mat=STONE))
    W.shape(P.box((c[0] - 200, c[1] - 76, z0 + t1), (c[0] + 200, c[1] + 316, z0 + t2), mat=STONE))
    W.surface(c[0] - HT, c[1] - HT, c[0] + HT, c[1] + HT, z0 + t1); W.surface(c[0] - 200, c[1] - 76, c[0] + 200, c[1] + 316, z0 + t2)
    run = 150.0                                              # 12 Nov review: 64 made 57-degree stairs (7-u risers on 4.6-u treads)
    for (mins, maxs, rise) in (((c[0] - 80, c[1] - HT - run, z0 - 70), (c[0] + 80, c[1] - HT, z0 + t1), '+y'), ((c[0] - 80, c[1] + HT, z0 - 70), (c[0] + 80, c[1] + HT + run, z0 + t1), '-y'),
                               ((c[0] - HT - run, c[1] - 80, z0 - 70), (c[0] - HT, c[1] + 80, z0 + t1), '+x'), ((c[0] + HT, c[1] - 80, z0 - 70), (c[0] + HT + run, c[1] + 80, z0 + t1), '-x')):
        W.shape(P.stairs(mins, maxs, 14, rise=rise, mat=STONE, tread_mat=STONE_TOP))      # 7-u risers; the lower ones are under the knoll
    W.shape(P.stairs((c[0] - 70, c[1] - 76 - 60, z0 + t1), (c[0] + 70, c[1] - 76, z0 + t2), 5, rise='+y', mat=STONE, tread_mat=STONE_TOP))
    W.shape(P.stairs((c[0] + 200, c[1] + 40, z0 + t1), (c[0] + 260, c[1] + 180, z0 + t2), 5, rise='-x', mat=STONE, tread_mat=STONE_TOP))
    # pass 3 review: the river ghat. The south stair's lowest step hung 140 u over the river (the knoll's south face drops into the
    # water): a grand stair that ended in a drop. A landing at its foot and two flights down to the water along the bank, west and east,
    # built out from the cliff (their back half buried in it); the river approach to the gate (the CT side) now climbs it
    zl = z0 - 70.0; gy0_, gy1_ = c[1] - HT - run - 54.0, c[1] - HT - run + 60.0; frun = 265.0
    W.shape(P.box((c[0] - 110.0, gy0_, -70.0), (c[0] + 110.0, gy1_, zl), mat=STONE))                       # the landing
    W.shape(P.box((c[0] - 80.0, gy1_ - 4.0, -70.0), (c[0] + 80.0, c[1] - HT - run + 90.0, zl), mat=STONE))   # under the stair's lower steps
    W.shape(P.stairs((c[0] - 110.0 - frun, gy0_, -70.0), (c[0] - 110.0, gy1_, zl), 25, rise='+x', mat=STONE, tread_mat=STONE_TOP))
    W.shape(P.stairs((c[0] + 110.0, gy0_, -70.0), (c[0] + 110.0 + frun, gy1_, zl), 25, rise='-x', mat=STONE, tread_mat=STONE_TOP))
    # playtest 1: the river channel is CHANNEL_D deep now: the ghat stands on stone footings down to under the bed (at -70 it floated)
    zf_ = L.WATER_Z - L.CHANNEL_D - 40.0
    W.shape(P.box((c[0] - 110.0 - frun, gy0_, zf_), (c[0] + 110.0 + frun, gy1_, -70.0), mat=STONE))
    W.surface(c[0] - 110.0, gy0_, c[0] + 110.0, gy1_, zl)
    for x in np.arange(-110.0 - frun + 20.0, 110.0 + frun, 40.0):
        for y in (gy0_ + 20.0, gy0_ + 60.0, gy0_ + 100.0): W.keep(c[0] + x, y, 22.0, z=zl, name='stairs')
    zc = z0 + t1; zu = z0 + t2
    W.prop('khmer_tower', c[0], c[1] + 120.0, zu, -90.0, tag='platform')          # its doorway faces the courtyard (south)
    W.prop('khmer_gate', c[0], c[1] - 290.0, zc, -90.0, tag='platform')
    # pass 3 review: the flag's supply crate stood at the head of the west stair's south side and took the spot of a balustrade and a
    # lion; it is placed after the statuary now, in the south court between the gate's west wing and the corner balustrade
    flag_site('d', c[0] - 150.0, c[1] - 180.0, zc)
    name, kind, (mx, my), myaw = L.mounted_guns()[1]
    W.mount('dshk', 'any', mx, my, myaw, z=zc, tag='platform')
    nlion = 0
    for s_ in (-1, 1):          # a lion each side of the tower stair's foot (pass 3: 14 u further north, clear of the flag pole)
        for dx_ in (104.0, 112.0):
            if W.prop('guardian_statue', c[0] + s_ * dx_, c[1] - 126.0, zc, -90.0 + s_ * 6.0, tag='platform', check=True, pad=2.0) is not None: nlion += 1; break
    # balustrades along the courtyard edge (gaps at the stairs), guardians at the stairs
    nlo, nhi = W.B(S.mv('naga_balustrade')); bl = nhi[0] - nlo[0]
    # the collapsed gallery in the west court (world geometry): two walls, a roof fallen in over the middle, a doorway into the court.
    # 12 Nov review: the design's "gallery as a tunnel through the knoll" was missing; this is a roofed passage ON the terrace (a bored
    # tunnel under the platform would need the terrain cut and a second floor level: left for a later pass)
    gx0, gx1, gy0, gy1 = c[0] - 330.0, c[0] - 244.0, c[1] + 100.0, c[1] + 330.0
    for (a_, b_) in (((gx0, gy0, zc), (gx0 + 12.0, gy1, zc + 100.0)), ((gx1 - 12.0, gy0, zc), (gx1, gy0 + 70.0, zc + 100.0)), ((gx1 - 12.0, gy0 + 132.0, zc), (gx1, gy1, zc + 100.0)),
                     ((gx0 + 12.0, gy1 - 12.0, zc), (gx1 - 12.0, gy1, zc + 100.0)), ((gx1 - 12.0, gy0 + 70.0, zc + 78.0), (gx1, gy0 + 132.0, zc + 100.0)),
                     ((gx0 - 6.0, gy0 - 4.0, zc + 100.0), (gx1 + 6.0, gy0 + 86.0, zc + 113.0)), ((gx0 - 6.0, gy1 - 70.0, zc + 100.0), (gx1 + 6.0, gy1 + 4.0, zc + 113.0))):
        W.shape(P.box(a_, b_, mat=STONE))
    W.shape(P.box((gx0 + 12.0, gy0 + 150.0, zc - 4.0), (gx0 + 30.0, gy0 + 172.0, zc + 62.0), mat=STONE))       # a roof slab fallen on end against the west wall
    W.shape(ME.noise(ME.subdivide(P.box((gx0 + 12.0, gy0 + 176.0, zc - 2.0), (gx0 + 40.0, gy0 + 236.0, zc + 16.0), mat=STONE), 1), 2.0, 30.0, 9))
    for x in np.arange(gx0 + 20, gx1, 40.0):
        for y in np.arange(gy0 - 30.0, gy1, 40.0): W.keep(x, y, 24.0, z=zc, name='gallery')
    W.sites['waypoints'].append(('temple gallery', (gx0 + gx1) / 2, gy0 + 40.0, zc))
    nb = 0
    for side, (ux, uy) in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):      # the edge runs along (ux, uy); its outward normal is (uy, -ux)
        ex, ey = uy * (HT - 16.0), -ux * (HT - 16.0)
        # 12 Nov review: one length each side of the stair, as near the corner as it fits (the gate's wings reach 196 along the south
        # edge, the upper terrace 200 along the north); the earlier four positions were two pairs on the same spot and all failed
        for sg in (-1, 1):
            for tt_ in ((262.0, 270.0) if side in (0, 2) else (262.0, 210.0)):
                t = sg * tt_; x, y = c[0] + ex + ux * t, c[1] + ey + uy * t
                if gx0 - 30.0 < x < gx1 + 30.0 and y > gy0 - 30.0: continue                       # the gallery stands there
                if W.prop('naga_balustrade', x, y, zc, math.degrees(math.atan2(uy, ux)) + (0.0 if t > 0 else 180.0), tag='platform', check=True) is not None: nb += 1; break
        if side in (1, 3):                                                    # lions flanking the head of the east and west stairs, looking out
            for s in (-1, 1):
                for tt_ in (100.0, 118.0):
                    if W.prop('guardian_statue', c[0] + ex * 0.86 + ux * s * tt_, c[1] + ey * 0.86 + uy * s * tt_, zc,
                              math.degrees(math.atan2(ey, ex)), tag='platform', check=True, pad=2.0) is not None: nlion += 1; break
    # the flag's supply crate (kit station): the south court, nearest the flag, after the statuary (pass 3 review)
    spots = sorted(((dx_, dy_) for dx_ in np.arange(-300.0, -199.0, 10.0) for dy_ in np.arange(-300.0, -199.0, 10.0)), key=lambda q: math.hypot(q[0] + 250.0, q[1] + 240.0))
    for (dx_, dy_) in spots + [(dx_, dy_) for dx_ in np.arange(210.0, 301.0, 10.0) for dy_ in np.arange(-300.0, -199.0, 10.0)]:
        yw_ = next((y_ for y_ in (40.0, 0.0, 90.0) if W.prop('supply_crate', c[0] + dx_, c[1] + dy_, zc, y_, tag='platform', check=True, pad=3.0) is not None), None)
        if yw_ is not None: W.sites['kit']['d'] = (c[0] + dx_, c[1] + dy_, zc); break
    else:
        print('WARNING temple: no room for the flag crate, placed at the old spot'); W.prop('supply_crate', c[0] - 262.0, c[1] - 150.0, zc, 40.0, tag='platform')
        W.sites['kit']['d'] = (c[0] - 262.0, c[1] - 150.0, zc)
    print('temple court: %d balustrades, %d lions, crate at (%.0f, %.0f)' % (nb, nlion, W.sites['kit']['d'][0] - c[0], W.sites['kit']['d'][1] - c[1]))
    # fallen blocks where a corner is left free, two fallen lintels in the court (the court is small: balustrades, lions, the DShK,
    # the flag and its crate come first)
    for (dx, dy, yw) in ((288.0, -286.0, 30.0), (-290.0, -290.0, 140.0), (290.0, 290.0, 250.0), (-290.0, 40.0, 80.0), (-280.0, 300.0, 200.0), (230.0, -230.0, 60.0), (-230.0, -250.0, 120.0)):
        for (ox_, oy_) in ((0.0, 0.0), (-20.0, 0.0), (0.0, 20.0), (20.0, 0.0), (0.0, -20.0)):
            if W.prop('fallen_blocks', c[0] + dx + ox_, c[1] + dy + oy_, zc, yw + rng.uniform(-8, 8), tag='platform', check=True, pad=4.0) is not None: break
    nl_ = 0
    for (dx, dy, yw) in ((40.0, -150.0, 8.0), (296.0, 150.0, 82.0), (-280.0, -40.0, 95.0), (280.0, -40.0, 85.0), (120.0, -200.0, 170.0), (-60.0, -200.0, 10.0), (300.0, -200.0, 92.0)):
        if nl_ < 2 and W.prop('lintel_fallen', c[0] + dx, c[1] + dy, zc, yw + rng.uniform(-8, 8), tag='platform', check=True, pad=4.0) is not None: nl_ += 1
    # ---- pass 2 review: a grand overgrown ruin, not a box with a tower on it
    # mossy paving over the court and the upper terrace (walk-over slabs, gaps where they are missing; not under the props)
    # (tiles stretched to the strips round the upper terrace, never into it; 1.5 u up so the slabs sit on the stone, not in it)
    tiles = [(gx_, -208.0, 170.0, 264.0, zc) for gx_ in (-255.0, -85.0, 85.0, 255.0)] + [(sx_ * 270.0, gy_, 140.0, 208.0, zc) for sx_ in (-1, 1) for gy_ in (28.0, 236.0)]
    tiles += [(gx_, gy_, 192.0, 192.0, zu) for gx_ in (-100.0, 100.0) for gy_ in (22.0, 218.0)]
    for (gx_, gy_, wx_, wy_, zz_) in tiles:
        k_ = rng.randint(2); sx_, sy_ = (wx_ / 192.0, wy_ / 192.0) if k_ == 0 else (wy_ / 192.0, wx_ / 192.0)
        W.prop('paving_slabs', c[0] + gx_, c[1] + gy_, zz_ + 1.5, 90.0 * k_ + 180.0 * rng.randint(2), scale=(sx_, sy_, 1.0), solid='0', reg=False, tag='platform')
    # the east gallery: a row of square pillars along the court edge, a stone architrave still lying across three of them, the rest
    # broken off; the west gallery is the roofed passage above
    px_ = c[0] + 300.0; npil = 0; arch = []
    for k, gy_ in enumerate((-40.0, 26.0, 92.0, 196.0, 262.0)):
        nm_ = 'khmer_pillar' if k in (0, 1, 2, 4) else 'khmer_pillar_broken'
        if W.prop(nm_, px_, c[1] + gy_, zc, rng.choice([0.0, 90.0, 180.0, 270.0]) + (rng.uniform(-3, 3) if 'broken' in nm_ else 0.0), tag='platform', check=True, pad=2.0) is not None:
            npil += 1
            if k < 3: arch.append(gy_)
    if len(arch) == 3:
        W.shape(ME.noise(ME.subdivide(P.box((px_ - 17.0, c[1] + arch[0] - 18.0, zc + 146.0), (px_ + 17.0, c[1] + arch[-1] + 18.0, zc + 168.0), mat=STONE_TOP), 1), 1.5, 30.0, 31))
        # playtest 1 (p7): vines hang over both faces of the architrave between the pillars (they start on its top, zc + 168)
        for (gy_, hang_) in (((arch[0] + arch[1]) / 2, 96.0), ((arch[1] + arch[2]) / 2, 70.0)):
            drape(px_ + 17.0, c[1] + gy_, zc + 168.0, -90.0, 54.0, hang_)
            drape(px_ - 17.0, c[1] + gy_ + 6.0, zc + 168.0, 90.0, 46.0, hang_ * 0.8)
    # statuary: lions at the head of the tower stair; a lion pair at the foot of the north, east and west stairs looking out; naga
    # balustrades flanking the north causeway down the knoll
    nst_ = 0
    for (ax_, ay_, face) in ((0.0, 1.0, 90.0), (1.0, 0.0, 0.0), (-1.0, 0.0, 180.0)):
        for s_ in (-1, 1):
            r_ = HT + run - 14.0; lat = 126.0
            x_, y_ = c[0] + ax_ * r_ - ay_ * s_ * lat, c[1] + ay_ * r_ + ax_ * s_ * lat
            if float(L.slope(x_, y_)) > 26.0: continue
            if W.prop('guardian_statue', x_, y_, None, face + rng.uniform(-4, 4), fit='min', check=True, pad=4.0) is not None: nst_ += 1
    nn_ = 0
    for s_ in (-1, 1):
        for t_ in (HT + run + 150.0, HT + run + 290.0):
            x_, y_ = c[0] + s_ * 104.0, c[1] + t_
            if float(L.slope(x_, y_)) > 18.0: continue
            if W.prop('naga_balustrade', x_, y_, None, -90.0, fit='min', check=True, pad=4.0) is not None: nn_ += 1
    # the outer enclosure: laterite walls on the knoll round the west, north and east sides (the river closes the south), open on the
    # axes, half of it collapsed; strangler figs splitting it in places; rubble fields where it fell
    nw_ = 0; nroot = 0; falls = []
    R_ = 402.0                          # the knoll falls at 26-40 degrees past r 420: the enclosure stands on its flat top
    # porticos: four pillars at each opening of the enclosure (the processional way passes between them), an architrave on each pair
    for (ux_, uy_) in ((0.0, 1.0), (1.0, 0.0), (-1.0, 0.0)):
        for s_ in (-1, 1):
            pp_ = []
            for rr_ in (R_ + 6.0, R_ + 76.0):
                x_, y_ = c[0] + ux_ * rr_ - uy_ * s_ * 150.0, c[1] + uy_ * rr_ + ux_ * s_ * 150.0
                if gz(x_, y_) < L.WATER_Z + 20.0 or float(L.slope(x_, y_)) > 30.0: continue
                nm_ = 'khmer_pillar_broken' if rng.uniform() < 0.35 else 'khmer_pillar'
                if W.prop(nm_, x_, y_, None, rng.choice([0.0, 90.0]) + rng.uniform(-2, 2), fit='min', check=True, pad=3.0, tag='slope') is not None:
                    npil += 1; pp_.append((x_, y_, gz(x_, y_), nm_))
            if len(pp_) == 2 and all(q[3] == 'khmer_pillar' for q in pp_):
                zt_ = min(q[2] for q in pp_) + 146.0; (x0_, y0_), (x1_, y1_) = pp_[0][:2], pp_[1][:2]
                b_ = P.box((min(x0_, x1_) - 17.0, min(y0_, y1_) - 17.0, zt_), (max(x0_, x1_) + 17.0, max(y0_, y1_) + 17.0, zt_ + 22.0), mat=STONE_TOP)
                W.shape(ME.noise(ME.subdivide(b_, 1), 1.5, 30.0, 33 + s_))
    for side, (ux, uy) in enumerate(((1, 0), (0, 1), (-1, 0))):      # north edge runs along x; east / west edges along y
        nrm = {0: (0, 1), 1: (1, 0), 2: (-1, 0)}[side]
        tdir = {0: (1, 0), 1: (0, 1), 2: (0, 1)}[side]
        ts = (-278.0, 278.0)
        for k, t in enumerate(ts):
            yw0_ = math.degrees(math.atan2(tdir[1], tdir[0])) + (180.0 if rng.uniform() < 0.5 else 0.0)
            # pass 3 review: the north edge has no balustrades (the upper terrace fills it), so the two north pieces are the fallen ones:
            # a strangler fig splitting the wall (roots to the outside) and a collapsed run with its rubble; 8 u further out than the
            # others so their inner face stays off the platform wall. Elsewhere (balustrades on the court edge) the plain wall.
            kinds = (('root_wall', 410.0, 0.0), ('enclosure_wall', R_, yw0_)) if (side, k) == (0, 0) else \
                    (('enclosure_wall_ruin', 410.0, yw0_), ('enclosure_wall', R_, yw0_)) if (side, k) == (0, 1) else (('enclosure_wall', R_, yw0_),)
            for kind, rr_, yw_ in kinds:
                x_, y_ = c[0] + nrm[0] * rr_ + tdir[0] * t, c[1] + nrm[1] * rr_ + tdir[1] * t
                if gz(x_, y_) < L.WATER_Z + 20.0 or float(L.slope(x_, y_)) > 30.0: continue
                if relief(S.mv(kind), x_, y_, yw_) > (52.0 if kind != 'enclosure_wall' else 40.0): continue
                if W.prop(kind, x_, y_, None, yw_, fit='min', dz=-6.0, check=True, pad=2.0, tag='slope') is not None: break
            else:
                continue
            nw_ += 1; nroot += kind == 'root_wall'
            if kind != 'enclosure_wall': falls.append((x_ + nrm[0] * 70.0, y_ + nrm[1] * 70.0))
            if kind == 'root_wall':
                W.prop(None, x_, y_, gz(x_, y_) - 2.0, rng.uniform(0, 360), stock=S.ROOTS[rng.randint(2)], solid='0', reg=False, tag='roots')
            elif rng.uniform() < 0.6:
                # playtest 1 (p7): over the outer face of the wall's coping (laterite body +-15, coping block +-18 from z 104 to 110
                # over the prop's origin), hanging to the footing
                zw_ = W.last_z + 110.0; t_ = rng.uniform(-50.0, 50.0)
                drape(x_ + nrm[0] * 18.0 + tdir[0] * t_, y_ + nrm[1] * 18.0 + tdir[1] * t_, zw_, math.degrees(math.atan2(nrm[1], nrm[0])) - 90.0,
                      rng.uniform(50.0, 80.0), rng.uniform(70.0, 98.0))
    for (fx_, fy_) in falls:      # rubble fields: clusters, not a scatter
        for j in range(rng.randint(3, 6)):
            a_ = rng.uniform(0, 2 * math.pi); r_ = rng.uniform(10.0, 90.0); x_, y_ = fx_ + r_ * math.cos(a_), fy_ + r_ * math.sin(a_)
            if gz(x_, y_) < L.WATER_Z + 20.0 or float(L.slope(x_, y_)) > 26.0: continue
            m_ = (S.RUBBLE + S.ROCKS)[rng.randint(len(S.RUBBLE) + len(S.ROCKS))]; lo_, hi_ = W.B(m_); sc_ = rng.uniform(0.7, 1.5)
            W.prop(None, x_, y_, gz(x_, y_) - lo_[2] * sc_ * 0.55, rng.uniform(0, 360), stock=m_, scale=sc_, check=True, pad=2.0, tag='rock')
    # strangler figs splitting fallen temple walls on the gentler parts of the knoll foot (the platform faces and the enclosure line have
    # the balustrades and porticos too close: build 3 had roots through a pillar)
    # pass 3 review: none of these ever stood (the 24-degree steps hit the stair lions and the causeway nagas; one orientation only):
    # the outer enclosure that slid off the knoll is now a ring of fallen pieces at its foot, a strangler-fig wall and a collapsed run
    # in turn, tried every 12 degrees north and east of the knoll, at its foot, three turns each, wherever the relief under the piece is under 44 u
    nruin = 0; last_a = -99.0
    for a_ in np.arange(6.0, 360.0, 12.0):
        if nroot + nruin >= 4: break
        if a_ - last_a < 50.0: continue                                  # spread round the knoll, not a row
        if a_ > 140.0: continue                      # west (the T and CT approaches to the west stair) and south (river) stay clear
        kind = 'root_wall' if nroot <= nruin else 'enclosure_wall_ruin'
        done_ = False
        for rr_ in (700.0, 740.0, 780.0, 820.0):                       # the knoll foot (the slope above is 26-40 deg)
            x_, y_ = L.pol(c, rr_, a_)
            if min(abs(rr_ * math.sin(math.radians(a_ - ax_))) for ax_ in (0.0, 90.0)) < 210.0: continue   # off the north and east stair approaches
            if gz(x_, y_) < L.WATER_Z + 24.0 or float(L.slope(x_, y_)) > 26.0: continue
            for yw_ in (a_ + 90.0, a_ + 70.0, a_ + 110.0):
                if relief(S.mv(kind), x_, y_, yw_) > 44.0: continue
                if W.prop(kind, x_, y_, None, yw_, fit='min', dz=-4.0, check=True, pad=4.0, tag='slope', _quiet=True) is not None:
                    if kind == 'root_wall':
                        nroot += 1; W.prop(None, x_, y_, gz(x_, y_) + 2.0, a_ * 3.0, stock=S.ROOTS[int(a_) % 2], solid='0', reg=False, tag='roots')
                    else:
                        nruin += 1
                        for j in range(3):                                # its blocks spilled down the slope
                            px_, py_ = L.pol((x_, y_), rng.uniform(90.0, 150.0), a_ + rng.uniform(-40, 40)); m_ = S.RUBBLE[rng.randint(len(S.RUBBLE))]
                            lo_, hi_ = W.B(m_); sc_ = rng.uniform(0.7, 1.2)
                            if float(L.slope(px_, py_)) < 28.0 and gz(px_, py_) > L.WATER_Z + 20.0:
                                W.prop(None, px_, py_, gz(px_, py_) - lo_[2] * sc_ * 0.55, rng.uniform(0, 360), stock=m_, scale=sc_, check=True, pad=2.0, tag='rock')
                    done_ = True; last_a = a_; break
            if done_: break
    print('temple knoll foot (pass 3): %d strangler-fig walls, %d collapsed enclosure runs' % (nroot, nruin))
    print('temple pass 2: %d pillars, %d stair lions, %d causeway nagas, %d enclosure pieces (%d split by roots)' % (npil, nst_, nn_, nw_, nroot))
    # ruin dressing on the terrace: fallen lintels and block piles against the upper terrace and in the corners (cover), vines on the
    # tower and the gate, roots over the terrace edge
    # playtest 1 (p7): the lianas round the tower and the gate hung from their own bent bar in mid air (vine_curtain 40-160 u off the
    # stone). They now hang from real edges of the two props (p_temple.khmer_tower / khmer_gate, measured from their generators):
    # tower (at c + (0, 120), yaw -90): the cella cornice top at z 186 (edge 116 out) on the north, east and west faces, over the corner
    # piers and clear of the false-door pediments (+-55 about each face centre) and the strangler-fig roots on the north-east corner
    tx_, ty_ = c[0], c[1] + 120.0
    for (ax_, ay_, yw_, lat_) in ((0.0, 1.0, 0.0, -80.0), (0.0, 1.0, 0.0, 74.0), (1.0, 0.0, -90.0, -80.0), (-1.0, 0.0, 90.0, 80.0), (-1.0, 0.0, 90.0, -76.0)):
        if (ax_, ay_, lat_) == (0.0, 1.0, 74.0): continue                     # the roots run down that corner
        x_ = tx_ + ax_ * 116.5 + (lat_ if ay_ else 0.0); y_ = ty_ + ay_ * 116.5 + (lat_ if ax_ else 0.0)
        drape(x_, y_, zu + 186.0, yw_, rng.uniform(40.0, 52.0), rng.uniform(110.0, 150.0))
    # gate (at c + (0, -290), yaw -90 = its build frame: spans x, faces +-y): the cornice top at z 172 (37 u out) over both piers, both
    # faces; the laterite wall stubs' coping at z 105 (18 u out)
    gx_, gy_ = c[0], c[1] - 290.0
    for sy_ in (1.0, -1.0):
        for sx_ in (1.0, -1.0):
            drape(gx_ + sx_ * rng.uniform(70.0, 90.0), gy_ + sy_ * 37.5, zc + 172.0, 0.0 if sy_ > 0 else 180.0, rng.uniform(36.0, 46.0), rng.uniform(96.0, 134.0))
        drape(gx_ + 132.0, gy_ + sy_ * 18.5, zc + 105.0, 0.0 if sy_ > 0 else 180.0, 38.0, rng.uniform(60.0, 88.0))
        drape(gx_ - 131.0, gy_ + sy_ * 18.5, zc + 105.0, 0.0 if sy_ > 0 else 180.0, 36.0, rng.uniform(60.0, 88.0))
    # the courtyard platform's outer face (top zc, faces at c +- 340): over the edge wherever the ground below is at least 50 u down,
    # clear of the stairs (+-80 about each axis) and the corner roots
    for side, (ux, uy) in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):
        nx_, ny_ = uy, -ux                                                    # outward normal of that edge
        for t in (-230.0, -150.0, 150.0, 235.0):
            if rng.uniform() < 0.35: continue
            t_ = t + rng.uniform(-20.0, 20.0)
            x_, y_ = c[0] + nx_ * HT + ux * t_, c[1] + ny_ * HT + uy * t_
            drop_ = zc - gz(x_ + nx_ * 12.0, y_ + ny_ * 12.0)
            if drop_ < 50.0: continue
            drape(x_ + nx_ * 0.5, y_ + ny_ * 0.5, zc, math.degrees(math.atan2(ny_, nx_)) - 90.0, rng.uniform(56.0, 84.0), min(drop_ - 8.0, rng.uniform(90.0, 150.0)))
    for (dx, dy) in ((-HT, -HT), (HT, -HT), (HT, HT), (-HT, HT), (-HT, 180.0), (HT, -200.0), (120.0, HT), (-200.0, -HT)):   # roots gripping the platform edge
        W.prop(None, c[0] + dx, c[1] + dy, zc - 26.0, rng.uniform(0, 360), stock=S.ROOTS[rng.randint(2)], solid='0', reg=False, tag='roots')
    for a in (20.0, 70.0, 110.0, 160.0, 200.0, 250.0, 290.0, 340.0):
        x, y = L.pol(c, 520.0 + rng.uniform(0, 40), a + rng.uniform(-8, 8))
        if float(L.slope(x, y)) > 15.0 or gz(x, y) < L.WATER_Z + 30.0: continue      # 12 Nov review: on a steeper slope fit='min' buried them to the top
        W.prop(('fallen_blocks', 'lintel_fallen', 'fallen_blocks')[int(a) % 3], x, y, gz(x, y) - 3.0, rng.uniform(0, 360), check=True, pad=4.0)
    for _ in range(26):
        a = rng.uniform(0, 360); r = rng.uniform(500.0, 620.0); x, y = L.pol(c, r, a)
        if gz(x, y) < L.WATER_Z + 20.0: continue
        m = (S.RUBBLE + S.ROCKS + S.ROCKS)[rng.randint(len(S.RUBBLE) + 2 * len(S.ROCKS))]
        lo, hi = W.B(m); sc = rng.uniform(1.0, 1.8)
        W.prop(None, x, y, gz(x, y) - lo[2] * sc * 0.55, rng.uniform(0, 360), stock=m, scale=sc, check=True, pad=4.0, tag='rock')
    for a in (38.0, 128.0, 218.0, 312.0):                         # banyans gripping the corners of the platform
        x, y = L.pol(c, 560.0, a + rng.uniform(-6, 6)); m = S.BANYAN_M[rng.randint(3)]
        if gz(x, y) < L.WATER_Z + 12.0: continue                 # 12 Nov review: the south-east one stood in the river
        if W.prop(None, x, y, gz(x, y) - 6.0, rng.uniform(0, 360), stock=m, trunk=S.TRUNK[m], check=True, pad=20.0) is not None:
            W.prop(None, x, y, gz(x, y) + 4.0, rng.uniform(0, 360), stock=S.ROOTS[0], solid='0', reg=False, tag='roots')
    for _ in range(30):
        a = rng.uniform(0, 360); x, y = L.pol(c, rng.uniform(490.0, 640.0), a); m = S.FERNS[rng.randint(len(S.FERNS))]
        if gz(x, y) < L.WATER_Z + 12.0: continue                 # 12 Nov review: three stood on the river bed
        if W.free(x, y, 14.0): W.prop(None, x, y, gz(x, y) - 1.0, rng.uniform(0, 360), stock=m, solid='0', reg=False, scale=rng.uniform(1.0, 1.6))
    for side, (ux, uy) in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):      # ferns along the foot of the platform wall
        for t in np.arange(-HT + 30.0, HT, 44.0):
            if abs(t) < 100.0 or rng.uniform() < 0.25: continue
            x, y = c[0] + uy * (HT + 16.0) + ux * t, c[1] - ux * (HT + 16.0) + uy * t
            if gz(x, y) > zc - 2.0 or gz(x, y) < L.WATER_Z + 12.0 or not W.free(x, y, 14.0): continue      # pass 2: not inside a wall at the foot
            W.prop(None, x, y, gz(x, y) - 1.0, rng.uniform(0, 360), stock=S.FERNS[rng.randint(len(S.FERNS))], solid='0', reg=False, scale=rng.uniform(1.1, 1.7))
    W.sites['seeds'] += [(c[0], c[1] - 180.0)]
    W.sites['plat_seed'] = [(c[0] + 120.0, c[1] - 230.0, zc)]


def crash_site():
    rng = np.random.RandomState(4115)
    c = L.CRASH; z = gz(*c)
    road = L.ROADS[0][1]
    W.keep_path([road[2], c, road[4]], 72.0, name="road"); W.keep_path([c, L.ROADS[3][1][1]], 50.0, name='road')
    flag_site('e', c[0] + 60.0, c[1] - 130.0, crate=(c[0] + 190.0, c[1] - 190.0), crate_yaw=60.0)
    # the C-123: fuselage north of the road, a wing torn off behind it, an engine further along the slide, burning
    fx, fy, fyaw = L.C123                                   # layout flattens the ground under its cargo floor
    W.prop('c123_fuselage', fx, fy, None, fyaw, fit='min')
    # the torn wing: on the flattest free spot of the slide (12 Nov review: on a slope fit='min' buried half of it; a wing is 20 u thick)
    cand = sorted(((relief(S.mv('c123_wing'), *local(fx, fy, fyaw, wx_, wy_), fyaw + 64.0), wx_, wy_) for wx_ in (-360.0, -260.0, -160.0, -60.0) for wy_ in (480.0, 560.0, 640.0, 720.0, 800.0)))
    for (rl_, wx_, wy_) in cand:
        if rl_ > 12.0: break
        if W.prop('c123_wing', *local(fx, fy, fyaw, wx_, wy_), None, fyaw + 64.0, fit='min', check=True, _quiet=True) is not None: break
    else: W.big_skips.append('c123_wing: no free spot with under 12 u of relief')
    ex, ey = local(fx, fy, fyaw, 470.0, -150.0)
    if W.prop('c123_engine', ex, ey, None, fyaw + 30.0, fit='min', check=True) is not None:
        W.particle(ex, ey, gz(ex, ey) + 30.0, FIRE); W.particle(ex, ey, gz(ex, ey) + 60.0, SMOKE_DARK)
    W.particle(*local(fx, fy, fyaw, -300.0, 0.0), z + 120.0, SMOKESTACK)
    slide = [local(fx, fy, fyaw, t, 0.0) for t in (-900.0, -500.0, 0.0, 500.0)]      # the swath it cut through the trees
    for (dx, dy) in ((-160, -230), (200, -250), (-330, 40), (330, 60), (-60, 480), (420, 330)):
        if W.prop('cargo_pallet', c[0] + dx, c[1] + dy, None, rng.uniform(0, 360), check=True, pad=4.0) is not None and rng.uniform() < 0.7:
            W.prop('parachute_silk', c[0] + dx + rng.uniform(-90, 90), c[1] + dy + rng.uniform(60, 120), None, rng.uniform(0, 360), check=True, solid='0')
    clutter(rng, [('supply_crate', 3), ('ammo_crate', 3), ('drum_od', 2), ('rucksack', 3), ('jerry_can', 2)], c[0], c[1], 90.0, 420.0)
    debris(rng, fx, fy, 200.0, 420.0, n=14, kit=(('ammo_can', 3), ('ammo_crate', 2), ('drum_od', 1), ('rucksack', 2), ('jerry_can', 2)))
    debris(rng, ex, ey, 60.0, 170.0, n=8, kit=(('drum_rust', 1), ('ammo_can', 1)))
    for t_ in (-380.0, -620.0, -840.0):                      # the swath: splintered trunks along the slide
        lx_, ly_ = local(fx, fy, fyaw, t_, rng.uniform(-90, 90))
        if float(L.slope(lx_, ly_)) < 16.0: W.prop(('log_fallen', 'root_tangle')[int(t_) % 2], lx_, ly_, None, fyaw + rng.uniform(-30, 30), check=True, pad=6.0)
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
    # 12 Nov review: the designed path behind the fall was missing. The river now leaves the cliff over a rock lip and falls 112 u out from
    # it; a shelf 10 u over the pool runs behind the curtain from bank to bank (80 u of headroom under the lip).
    CUR = 112.0
    for k in range(-3, 4):
        W.prop(None, x + CUR, y + k * (wd * 1.6 - 4.0), wz - hi[2] * sz, 90.0, stock=S.WATER_WALL, scale=(1.6, 1.0, sz), solid='0', reg=False, tag='water')
    for dy in (-90.0, 90.0):
        W.particle(x + CUR + 40.0, y + dy, L.WATER_Z + 4.0, 'particles/water_fx/waterfall_base.vpcf')
    W.shape(P.box((x - 30.0, y - 222.0, wz - 18.0), (x + CUR + 4.0, y + 222.0, wz - 2.0), mat=TER.BLEND_ROCK), paint=lambda p: 0.15)
    TER.rect_sheet(x + 2.0, y - 216.0, x + CUR, y + 216.0, wz, TER.WATER, W.group, cell=128.0)
    for sg in (-1, 1):                     # rock curbs along both sides of the lip: the sheet's long edges end in them, not in the air
        W.shape(ME.noise(ME.subdivide(P.box((x - 30.0, y + sg * 206.0 - 18.0, wz - 18.0), (x + CUR + 4.0, y + sg * 206.0 + 18.0, wz + 12.0), mat=TER.BLEND_ROCK), 1), 2.5, 40.0, 21 + sg), paint=lambda p: 0.2)
    shelf_z = L.WATER_Z + 10.0
    # playtest 1: down to under the plunge pool's new bed (the channel is CHANNEL_D deep now; at WATER_Z - 60 the shelf floated over it)
    W.shape(P.box((x + 22.0, y - 240.0, L.WATER_Z - L.CHANNEL_D - 50.0), (x + 100.0, y + 240.0, shelf_z), mat=TER.BLEND_ROCK), paint=lambda p: 0.3)
    W.surface(x + 22.0, y - 240.0, x + 100.0, y + 240.0, shelf_z)
    W.sites['waypoints'].append(('behind the waterfall', x + 62.0, y, shelf_z))
    for dy in (-280.0, 280.0): W.prop(None, x + 60.0, y + dy, gz(x + 60.0, y + dy) - 1.0, rng.uniform(0, 360), stock=S.FERNS[rng.randint(len(S.FERNS))], solid='0', reg=False, scale=1.3)      # at the shelf ends, not under the lip
    # boulders flanking the fall and in the pool: noise-deformed blocks with the rock / moss blend painted by height
    for (dx, dy, sx, sy, sh, seed) in ((-40, -372, 230, 190, 230, 1), (-30, 382, 250, 180, 260, 2), (200, -330, 150, 130, 120, 3), (210, 340, 140, 150, 110, 4),
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
    TER.clip_box(x - 60.0, y - 260.0, wz - 24.0, x - 34.0, y + 260.0, wz + 200.0, W.group)      # nobody walks up the river from the lip
    W.sites['nonav'].append((x - 400.0, y - 500.0, x + 60.0, y + 500.0))


def marsh():
    rng = np.random.RandomState(4122)
    x = 5450.0; y = float(L.river_y(x)) + 150.0
    pm = M.static('pbr')
    if M.is_ext(pm):      # the intact PBR floats in the channel, nosed toward the south bank
        x = 5560.0; y = float(L.river_y(x)) - 40.0
        W.prop(None, x, y, L.WATER_Z - M.PBR_DRAFT, 172.0, stock=pm, tag='water')
        W.keep(x, y, 150.0, z=L.WATER_Z - 30.0, name='boat')
    else:
        W.prop('pbr_wreck', x, y, gz(x, y) - 2.0, 200.0)             # its origin is the river bed; the model already lists
        W.particle(x, y, L.WATER_Z + 60.0, SMOKESTACK)
    W.prop('sampan', 5180.0, float(L.river_y(5180.0)) - 190.0, L.WATER_Z - 8.0, 70.0, tag='water')
    nd = 0
    for _ in range(140):
        px = rng.uniform(L.MARSH_X0, L.MAP_X - 80.0); py = float(L.river_y(px)) + rng.uniform(-950, 950); g = gz(px, py)
        if not (L.WATER_Z - 14.0 < g < L.WATER_Z + 40.0) or nd >= 30: continue
        if W.prop('dead_tree', px, py, g - 5.0, rng.uniform(0, 360), trunk=S.TRUNK_MV['dead_tree'], check=True, pad=30.0, scale=rng.uniform(0.8, 1.2)) is not None: nd += 1
    for _ in range(8):                  # fish traps before the reeds, so the reeds keep off them (12 Nov review)
        px = rng.uniform(L.MARSH_X0, L.MAP_X - 200.0); py = float(L.river_y(px)) + rng.uniform(-600, 600)
        if abs(gz(px, py) - L.WATER_Z) < 16.0: W.prop('fish_trap', px, py, max(gz(px, py), L.WATER_Z - 6.0), rng.uniform(0, 360), check=True, tag='water')      # staked in the water
    n = 0
    for _ in range(900):
        px = rng.uniform(L.MARSH_X0 - 100.0, L.MAP_X - 40.0); py = float(L.river_y(px)) + rng.uniform(-1050, 1050); g = gz(px, py)
        if g < L.WATER_Z - 22.0 or g > L.WATER_Z + 26.0: continue
        if n < 330 and W.free(px, py, 22.0):
            W.prop('reeds', px, py, g - 2.0, rng.uniform(0, 360), solid='0', reg=False, scale=rng.uniform(0.9, 1.4)); n += 1
    nm_ = 0
    for logical, cnt, sc0, sc1, zlo, zhi in (('mangrove', 26, 0.8, 1.15, -16.0, 14.0), ('palm_nypa', 46, 0.9, 1.4, -6.0, 30.0)):
        model = M.static(logical)
        if not M.is_ext(model): continue
        k = 0
        for _ in range(cnt * 14):
            if k >= cnt: break
            px = rng.uniform(L.MARSH_X0 - 300.0, L.MAP_X - 120.0); py = float(L.river_y(px)) + rng.uniform(-1000, 1000); g = gz(px, py)
            if not (L.WATER_Z + zlo < g < L.WATER_Z + zhi): continue
            tr = M.TRUNK.get(model)
            # playtest 1: the banks are steeper since the channel is deeper: stand on the coarse terrain mesh's low side (as the nypa
            # palms of the understorey since pass 4), never on the smooth field over it
            zt_ = min(g, float(TER.mesh_low(px, py)[0])) - 3.0
            if W.prop(None, px, py, zt_, rng.uniform(0, 360), stock=model, solid='0', scale=rng.uniform(sc0, sc1), trunk=tr if tr is not None else 36.0, check=True, pad=20.0,
                      reg=tr is not None, tag='rooted in slope' if zt_ < g - 7.5 else None) is not None: k += 1
        nm_ += k
    print('marsh: %d reeds, %d dead trees, %d mangroves / nypa palms' % (n, nd, nm_))


def karst_dressing():
    """player clips round every tower (cylinders: nobody climbs the walls; the landable crowns stay open) and the sniper nests"""
    rng = np.random.RandomState(4123)
    for kk, (kx, ky, kr, kh, ks) in zip(W.karst, L.KARST):
        land = ks in L.KARST_LANDABLE
        z0 = kk['z0'] + 110.0
        if land:
            W.clip(P.cylinder((kx, ky), kr * 1.13, z0, kk['z0'] + 70.0 + kh * 0.86, sides=16, mat=TER.CLIP))
            # 12 Nov review: the nest ringed the middle of the crown (a crate at the centre, bags at 140 u, four of them past the rim in
            # the air): a helicopter had nowhere to put down. The nest is a crescent at the rim on the valley side; the landing disc
            # (150 u) is the rest of the crown.
            rm = kk['rim_min']; face = math.degrees(math.atan2(-ky, -kx)); fc, fs = rot(face)
            cz_ = lambda x_, y_: (TER.crown_z(kk, x_, y_) or kk['rim']) - 1.0
            ra = rm - 30.0
            for a0_ in (-44.0, -14.0, 16.0):
                zs_ = [cz_(*L.pol((kx, ky), ra + 12.0, face + a_)) for a_ in (a0_, a0_ + 14.0, a0_ + 28.0)]
                W.bag_arc(kx, ky, ra, face + a0_, face + a0_ + 28.0, layers=2, model='sandbag_low', z=min(zs_) - 1.5)
            cx_, cy_ = kx + fc * (rm - 120.0), ky + fs * (rm - 120.0)         # clear of the bag crescent (check_world: crate in the bags)
            W.prop('supply_crate', cx_, cy_, cz_(cx_, cy_) - 1.0, face + 90.0, tag='karst')
            for (nm, df, dl) in (('radio_prc25', -8.0, 84.0), ('rucksack', 4.0, -84.0), ('ammo_can', -20.0, 104.0), ('ammo_crate', -24.0, -104.0)):
                px_, py_ = cx_ + fc * df - fs * dl, cy_ + fs * df + fc * dl
                W.prop(nm, px_, py_, cz_(px_, py_), rng.uniform(0, 360), tag='karst')
            dl_ = max(0.0, min(rm - 156.0, 60.0))
            W.sites['landing'].append((kx - fc * dl_, ky - fs * dl_, kk['top'], ks))
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
    for (nm, k, t, off, yaw) in (('truck_us', 0, 0.42, 120.0, 30.0), ('apc', 0, 0.78, -130.0, 100.0), ('truck_nva', 1, 0.62, 125.0, 200.0),
                                 ('ox_cart', 1, 0.2, -150.0, 80.0), ('apc', 2, 0.55, 110.0, 310.0), ('t54', 1, 0.12, 150.0, None)):
        Pp = np.array(L.ROADS[k][1], float); seg = np.linalg.norm(np.diff(Pp, axis=0), axis=1); cum = np.concatenate([[0], np.cumsum(seg)])
        if nm in M.STATIC:         # the converted vehicles are bigger than the hulks they replace: stand clear of the road by their own size
            lo_, hi_ = W.B(M.static(nm)); off = math.copysign(max(abs(off), L.ROADS[k][0] + 30.0 + math.hypot(hi_[0] - lo_[0], hi_[1] - lo_[1]) / 2), off)
        for t_ in [t + d_ for d_ in (0.0, 0.03, -0.03, 0.06, -0.06, 0.09, -0.09, 0.12, -0.12, 0.15, -0.15, 0.18, -0.18, 0.21, -0.21)] + [t + 0.5 * d_ for d_ in (0.03, -0.03, 0.09, -0.09)]:       # slide along the road until the spot is level and free
            placed_ = False
            for offk in (1.0, 1.4, -1.0, -1.4):                      # either side of the road, nearer or further off it
                s_ = t_ * cum[-1]; i = max(0, min(int(np.searchsorted(cum, s_) - 1), len(seg) - 1)); u = (Pp[i + 1] - Pp[i]) / seg[i]
                q = Pp[i] + u * (s_ - cum[i]) + np.array([-u[1], u[0]]) * off * offk
                yw = math.degrees(math.atan2(u[1], u[0])) + 168.0 if yaw is None else yaw      # the knocked-out tank, slewed off the road, still pointing down it
                if float(L.slope(q[0], q[1])) >= 12.0: continue              # burial is judged by the relief under the footprint below
                if relief(M.static(nm) if nm in M.STATIC else S.mv(nm), q[0], q[1], yw) > 26.0: continue      # (14 lost all four wrecks)
                e = W.sprop(nm, q[0], q[1], None, yw, fit='min', check=True, pad=6.0, _quiet=True) if nm in M.STATIC else W.prop(nm, q[0], q[1], None, yw, fit='min', check=True, pad=6.0, _quiet=True)
                if e is None: continue
                if nm == 't54': W.particle(q[0], q[1], gz(q[0], q[1]) + 110.0, SMOKE_DARK)
                if nm != 'ox_cart': debris(rng, q[0], q[1], 130.0, 230.0, n=7)
                placed_ = True; break
            if placed_: break
        else: print('  road wreck %s on road %d: no level free spot' % (nm, k))
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
            # pass 4 review: pad 4 -> 40. A stone 20 u from a hut's corner left a one-cell gap between them that a player could drop into
            # off the stone and only jump out of (the 256 u2 village pocket at (-1064, 1976)); 40 u is a gap a player walks through
            if W.prop(None, x, y, gz(x, y) - lo[2] * sc * 0.5, rng.uniform(0, 360), stock=m, scale=sc, check=True, pad=40.0, tag='rock') is not None: n += 1
        if rng.uniform() < 0.4:
            x, y = L.pol((cx, cy), r * 1.5, rng.uniform(0, 360))
            if float(L.slope(x, y)) < 18.0: W.prop('log_fallen', x, y, None, rng.uniform(0, 360), check=True, pad=6.0)
    k_ = 0
    for (cx, cy, r, dep) in L.CRATERS:                       # two fresh craters still smoke
        if k_ >= 2 or not L.in_play(cx, cy) or abs(cy - float(L.river_y(cx))) > 2600.0: continue
        if rng.uniform() < 0.35: W.particle(cx, cy, gz(cx, cy) + 20.0, SMOKESTACK); k_ += 1
    print('roads and craters: %d crater stones' % n)


# ================================================================ the jungle
def jungle():
    rng = np.random.RandomState(4131)
    cnt = dict(canopy=0, under=0, fern=0, grass=0, rice=0, palm=0, bamboo=0, small_tree=0, ravine=0)
    # what the eroded ground suggests (tools/data images, docs/IMAGE_TERRAIN.md): fewer trees in stream beds and on rock, more beside the
    # streams, undergrowth where it is damp. The design (clearings, groves, farms) stays in layout.jungle / layout.grass; these multiply it.
    i_tree = lambda x, y: (0.35 + 0.65 * TER.img_at('trees', x, y)) * 1.3
    i_under = lambda x, y: 0.4 + 1.5 * TER.img_at('undergrowth', x, y, 0.4)
    i_grass = lambda x, y: 0.5 + 0.75 * TER.img_at('grass', x, y, 0.67)
    X_ = {k: M.static(k) for k in ('bamboo', 'palm_jungle', 'palm_coconut', 'tree_small', 'palm_nypa', 'taro', 'ferns', 'bush', 'grass_tall', 'grass_low')}
    X_ = {k: v for k, v in X_.items() if M.is_ext(v)}                # the converted Rising Storm foliage that is in the addon
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
    dens = np.clip(L.jungle(X, Y) * i_tree(X, Y), 0, 1); sl = L.slope(X, Y); Z = L.height(X, Y)
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
        if float(Z[i]) < L.WATER_Z + 8.0: continue                 # 12 Nov review: one banyan stood in the river at the temple
        if not W.rotor_ok(m, float(X[i]), float(Y[i]), sc): continue
        sink = 7.0 + math.tan(math.radians(s_)) * tr * sc * 0.6
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
            xp = [X_[k] for k in ('palm_coconut', 'palm_jungle') if k in X_]
            if not W.rotor_ok(S.PALMS[0], px, py, 1.2): continue
            if xp and rng.uniform() < 0.45:
                m = xp[rng.randint(len(xp))]; sc = rng.uniform(1.0, 1.35)
                if W.prop(None, px, py, gz(px, py) - 4.0, rng.uniform(0, 360), stock=m, trunk=M.TRUNK[m], check=True, pad=24.0, scale=sc, solid='0') is not None:
                    W.trunk_clip(px, py, gz(px, py), M.TRUNK[m] * sc); cnt['palm'] += 1
            else:
                m = S.PALMS[rng.randint(len(S.PALMS))]
                if W.prop(None, px, py, gz(px, py) - 4.0, rng.uniform(0, 360), stock=m, trunk=S.TRUNK[m], check=True, pad=24.0, scale=rng.uniform(0.85, 1.2)) is not None: cnt['palm'] += 1
            if rng.uniform() < 0.35:
                bx_, by_ = px + rng.uniform(-150, 150), py + s * rng.uniform(40, 160)
                if gz(bx_, by_) > L.WATER_Z + 20.0 and float(L.slope(bx_, by_)) < 16.0 and float(L.clearing(np.array([bx_]), np.array([by_]))[0]) < 0.9:
                    if 'bamboo' in X_ and rng.uniform() < 0.6:     # a grove you walk through: the canes are thin, the model is not solid
                        if W.prop(None, bx_, by_, gz(bx_, by_) - 3.0, rng.uniform(0, 360), stock=X_['bamboo'], trunk=M.TRUNK[X_['bamboo']], check=True, pad=20.0,
                                  scale=rng.uniform(0.9, 1.25), solid='0') is not None: cnt['bamboo'] += 1
                    elif W.prop('bamboo_clump', bx_, by_, gz(bx_, by_) - 3.0, rng.uniform(0, 360), trunk=S.TRUNK_MV['bamboo_clump'], check=True, pad=20.0,
                                scale=rng.uniform(0.85, 1.2)) is not None: cnt['bamboo'] += 1
    # ---- bamboo groves on the floodplain and the terraces (the converted grove is the best foliage piece: walk-through canes)
    if 'bamboo' in X_:
        for _ in range(260):
            if cnt['bamboo'] >= 46: break
            bx_ = rng.uniform(-L.MAP_X + 300.0, L.MARSH_X0); by_ = float(L.river_y(bx_)) + rng.choice([-1, 1]) * rng.uniform(L.BANK_W + 120.0, 2300.0)
            if not L.in_play(bx_, by_) or L.in_paddies(np.array([bx_]), np.array([by_]))[0] or float(L.slope(bx_, by_)) > 14.0: continue
            if float(L.clearing(np.array([bx_]), np.array([by_]))[0]) > 0.5 or gz(bx_, by_) < L.WATER_Z + 24.0: continue
            if not W.rotor_ok(X_['bamboo'], bx_, by_, 1.3): continue
            if W.prop(None, bx_, by_, gz(bx_, by_) - 3.0, rng.uniform(0, 360), stock=X_['bamboo'], trunk=M.TRUNK[X_['bamboo']], check=True, pad=30.0,
                      scale=rng.uniform(0.9, 1.3), solid='0') is not None: cnt['bamboo'] += 1
    # ---- understorey: tall tropical plants, small palms, yucca and taro under the canopy (walk-through, no collision)
    X, Y = grid(150.0)
    m_ = near_play(X, Y) & L.in_play(X, Y)
    X, Y = X[m_], Y[m_]
    dens = np.maximum(L.jungle(X, Y), 0.25 * (1.0 - L.clearing(X, Y))) * i_under(X, Y); sl = L.slope(X, Y); Z = L.height(X, Y)
    ok = (rng.uniform(size=X.shape) < dens * 1.1) & (sl < 34.0) & (Z > L.WATER_Z + 14.0) & ~L.in_paddies(X, Y)
    under = S.TROPICAL_L * 3 + S.TROPICAL_M * 3 + S.PALMS_SMALL + S.YUCCA + S.TARO + [X_[k] for k in ('bush', 'bush', 'palm_nypa', 'taro') if k in X_]
    idx = np.nonzero(ok)[0]
    if len(idx) > 2100: idx = rng.choice(idx, 2100, replace=False)
    for i in idx:
        m = under[rng.randint(len(under))]
        if not W.free(float(X[i]), float(Y[i]), 10.0, float(Z[i])): continue
        if 'tree_small' in X_ and cnt['small_tree'] < 160 and float(sl[i]) < 20.0 and rng.uniform() < 0.1:      # a slim tree: non-solid model, clipped trunk
            m = X_['tree_small']; sc = rng.uniform(1.0, 1.5)
            if not W.rotor_ok(m, float(X[i]), float(Y[i]), sc): continue
            if W.prop(None, float(X[i]), float(Y[i]), float(Z[i]) - 4.0, rng.uniform(0, 360), stock=m, trunk=M.TRUNK[m], check=True, pad=16.0, scale=sc, solid='0') is not None:
                W.trunk_clip(float(X[i]), float(Y[i]), float(Z[i]), M.TRUNK[m] * sc); cnt['small_tree'] += 1
            continue
        z_ = float(Z[i]) - 3.0
        if 'nypa' in m:         # pass 4 review: a nypa stood 7.4 u over a slope (check_play 6 reads it as a tree on a 36-u trunk footprint over
            # the coarse terrain mesh): sink it to the mesh's low side under that footprint
            # (listed as rooted in the slope when that is more than 8 u under the smooth field: check_world's ground test)
            z_ = min(float(Z[i]), float(TER.mesh_low(float(X[i]), float(Y[i]))[0])) - 3.0 - 18.0 * math.tan(math.radians(float(sl[i])))
        W.prop(None, float(X[i]), float(Y[i]), z_, rng.uniform(0, 360), stock=m, solid='0', reg=False,
               scale=rng.uniform(0.9, 1.3) if M.is_ext(m) else rng.uniform(0.9, 1.5), tag='rooted in slope' if z_ < float(Z[i]) - 7.5 else None); cnt['under'] += 1
    # ---- ferns and small plants: only near where people walk (roads, flags, bases)
    X, Y = grid(105.0)
    rd, hw = L.road_dist(X, Y)
    nf = np.full(X.shape, 1e9)
    for _, _, (fx, fy) in L.FLAGS: nf = np.minimum(nf, np.hypot(X - fx, Y - fy))
    nf = np.minimum(nf, np.minimum(np.hypot(X - L.CT_BASE[0], Y - L.CT_BASE[1]) - 900.0, np.hypot(X - L.T_BASE[0], Y - L.T_BASE[1]) - 300.0))
    m_ = ((rd < 420.0) | (nf < 950.0)) & L.in_play(X, Y)
    X, Y = X[m_], Y[m_]
    dens = (L.jungle(X, Y) + 0.25 * (1.0 - L.clearing(X, Y))) * i_under(X, Y); sl = L.slope(X, Y); Z = L.height(X, Y)
    ok = (rng.uniform(size=X.shape) < dens * 1.1) & (sl < 36.0) & (Z > L.WATER_Z + 10.0) & ~L.in_paddies(X, Y)
    small = S.FERNS * 2 + S.TROPICAL_S + S.WEEDS + [X_[k] for k in ('ferns', 'ferns', 'grass_low') if k in X_]
    idx = np.nonzero(ok)[0]
    if len(idx) > 1500: idx = rng.choice(idx, 1500, replace=False)
    for i in idx:
        m = small[rng.randint(len(small))]
        if not W.free(float(X[i]), float(Y[i]), 8.0, float(Z[i])): continue
        W.prop(None, float(X[i]), float(Y[i]), float(Z[i]) - 1.5, rng.uniform(0, 360), stock=m, solid='0', reg=False,
               scale=rng.uniform(0.8, 1.1) if M.is_ext(m) else rng.uniform(1.0, 1.7)); cnt['fern'] += 1
    # ---- ferns and bushes along the eroded ravines: points straight from the undergrowth image (the same every run)
    F = TER.img('undergrowth')
    if F is not None and ('ferns' in X_ or 'bush' in X_):
        FX_, FY_ = F.XY
        damp = F.Z * L.in_play(FX_, FY_) * (np.abs(L.detail(FX_, FY_)) > 6.0) * (L.water_dist(FX_, FY_) < 3300.0)
        rav = [X_[k] for k in ('ferns', 'ferns', 'bush') if k in X_]
        for (x, y) in TI.scatter_density(F.like(damp), spacing=110.0, seed=7, limit=700):
            if float(L.slope(x, y)) > 36.0 or gz(x, y) < L.WATER_Z + 10.0 or not W.free(x, y, 10.0): continue
            m = rav[rng.randint(len(rav))]
            z_ = min(gz(x, y), float(TER.mesh_low(x, y)[0])) - 2.5        # on the terrain mesh's low side (the ravine banks are steep)
            W.prop(None, float(x), float(y), z_, rng.uniform(0, 360), stock=m, solid='0', reg=False, scale=rng.uniform(0.8, 1.15),
                   tag='rooted in slope' if z_ < gz(x, y) - 7.5 else None); cnt['ravine'] += 1
    # ---- elephant grass fields on the floodplain and terraces (cover from the air)
    X, Y = grid(66.0, jit=0.48)
    m_ = L.in_play(X, Y) & (L.water_dist(X, Y) < 2900.0)
    X, Y = X[m_], Y[m_]
    g = np.clip(L.grass(X, Y) * i_grass(X, Y), 0, 1); sl = L.slope(X, Y); Z = L.height(X, Y); rd, hw = L.road_dist(X, Y)
    ok = (g > 0.12) & (rng.uniform(size=X.shape) < np.minimum(1.0, g * 1.7)) & (sl < 20.0) & (Z > L.WATER_Z + 14.0) & (rd > hw + 26.0)
    idx = np.nonzero(ok)[0]
    if len(idx) > 2300: idx = rng.choice(idx, 2300, replace=False)
    for i in idx:
        if not W.free(float(X[i]), float(Y[i]), 20.0, float(Z[i])): continue
        if 'grass_tall' in X_ and rng.uniform() < 0.3:        # the converted patch is 48 u high: 2 - 2.5 x makes it elephant grass
            hs = rng.uniform(2.0, 2.5)
            W.prop(None, float(X[i]), float(Y[i]), float(Z[i]) - 4.0, rng.uniform(0, 360), stock=X_['grass_tall'], solid='0', reg=False,
                   scale=(rng.uniform(1.0, 1.3),) * 2 + (hs,)); cnt['grass'] += 1
            continue
        W.prop('elephant_grass_' + 'abc'[rng.randint(3)], float(X[i]), float(Y[i]), float(Z[i]) - 2.0, rng.uniform(0, 360), solid='0', reg=False,
               scale=(rng.uniform(0.9, 1.3),) * 2 + (rng.uniform(0.9, 1.25),)); cnt['grass'] += 1
    # ---- reeds along both river banks, at the water line (12 Nov review: the banks were bare mud from the gorge to the marsh)
    cnt['reeds'] = 0
    for x in np.arange(-5450.0, L.MARSH_X0, 44.0):
        for s in (-1, 1):
            if rng.uniform() < 0.3 or abs(x - L.BRIDGE_X) < 130.0: continue
            px = x + rng.uniform(-18, 18); py = float(L.river_y(px)) + s * (L.RIVER_HW + rng.uniform(-22.0, 34.0)); g_ = gz(px, py)
            if not (L.WATER_Z - 14.0 < g_ < L.WATER_Z + 12.0) or not W.free(px, py, 14.0): continue
            W.prop('reeds', px, py, g_ - 2.0, rng.uniform(0, 360), solid='0', reg=False, scale=rng.uniform(0.9, 1.35)); cnt['reeds'] += 1
    # ---- rice in the paddy cells (in the water, off the dikes)
    for (x0, x1, yr0, yr1, cx, cy) in ((L.PADDY_X0, L.PADDY_X1, L.PADDY_YR0, L.PADDY_YR1, L.PADDY_CELL_X, L.PADDY_CELL_Y),
                                       (L.PADDY2_X0, L.PADDY2_X1, L.PADDY2_YR0, L.PADDY2_YR1, L.PADDY2_CELL_X, L.PADDY2_CELL_Y)):
        for x in np.arange(x0 + 20.0, x1 - 19.0, 50.0):
            for yr in np.arange(yr0 + 20.0, yr1 - 19.0, 50.0):
                px = x + rng.uniform(-12, 12); pr = yr + rng.uniform(-12, 12)
                u = (px - x0) / cx % 1.0; v = (pr - yr0) / cy % 1.0
                if min(u, 1 - u) * cx < 52.0 or min(v, 1 - v) * cy < 52.0 or rng.uniform() < 0.08: continue
                py = pr + float(L.river_y(px))
                if not W.free(px, py, 10.0) or gz(px, py) > 14.0 + 8.0 * 3 + 1.5 * 4 + 6.0: continue      # not on the island or a dike
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
    W.rotors = rotor_plan()
    for kk, (kx, ky, kr, kh, ks) in zip(W.karst, L.KARST):      # 12 Nov review: the towers before anything else (a camp hut stood inside karst 1)
        W.keep_disc(kx, ky, kr * 1.12, z=kk['z0'], name='karst', h=kh + 400.0)
    M.ensure_dyn(out)                                # the prop_dynamic twin of the converted crash hulk
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
    for b in W.big_skips: print('  did not fit: ' + b)
    if W.rotor_skips: print('  kept out of the rotor cylinders: ' + ', '.join('%s %d' % kv for kv in sorted(W.rotor_skips.items(), key=lambda kv: -kv[1])))
    print('places: %d prop_static (%d models), %d skipped for overlap, %d exceptions; props not built yet: %s' % (
        n, len(W.count), sum(W.skipped.values()), len(W.exc), ', '.join(sorted(W.missing)) or 'none'))
    return W
