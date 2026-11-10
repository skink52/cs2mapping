"""Dunes detail pass (list item M4), as an ADDITIVE patch on skink52's hand-edited map: human-scale set dressing that makes the
mechs read as 15 m machines and the desert as a place people work in. Nothing of the map is moved or removed.

    python -I tools/patch_dunes_detail.py <the map as last saved in Hammer .vmap> <out .vmap> [addon out dir = out/addon] [--stats FILE]

Close Hammer, back up the map, run, then copy the output over the map. Re-runnable: everything is in vis group
`ifr_dunes_detail`, which a re-run replaces (so the whole pass can also be deleted in Hammer by that group).

What it adds, per arena copy (ifr_arena_N offsets are read from the map), all prop_static, solid 0, not lightmapped, stock CS2
models from tools/arenas/sprawl_kit.json (the ones whose materials are known to load) at 0.6 human scale:
  convoy        a wrecked supply column on the canyon floor north and south of the island (trucks, cars, trailers, containers,
                tarps, with tyres, barrels, cones and barriers round them)
  camps         container yards with stacks, trailers, generators, flood-light masts, fences: by the refinery, by the wreck,
                on the rims of plateaus A and C, behind both drop lines
  power lines   a row of poles from each rim toward its plateau
  scatter       half-buried wrecks, tyre piles, barrels, lone containers over the dune fields
  masts         relay towers near the rims, flood-light rings round the three objective plateaus
Where it does NOT put anything: within reach of a prop skink52 placed (radius by that prop's scale), on a structure footprint
of the generator (nav.struct of out/addon/_gen/arena.json), on steep ground, inside an objective ring's centre or a drop pad.
Ground height is the generator's (tools/arenas/dunes.py height): where the terrain was re-sculpted by hand a prop may float
or sink: look at the canyon floor and the plateaus in game. Tall things are thin (masts) or stand at the edges.
"""
import os, sys, json, math, random
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
CREATE = os.path.normpath(os.path.join(HERE, '..', '..', '..', 'create'))
sys.path.insert(0, CREATE); sys.path.insert(0, HERE)
import numpy as np
import vmapgen as G
import arenas.dunes as D

GROUP = 'ifr_dunes_detail'
S = 0.6
KIT = json.load(open(os.path.join(HERE, 'arenas', 'sprawl_kit.json')))
DUST = ['168 150 120', '146 128 100', '120 104 88', '150 108 76', '176 160 132', '104 100 92']
BOX = ['132 70 52', '74 96 110', '150 134 100', '96 100 70', '120 60 44', '160 150 138']
VEH = [('flatnose_truck_wrecked', 3), ('dust_flatbed_truck_body', 3), ('dust_car_wreck_body', 4), ('dust_hatchback_body', 3), ('dust_taxi_body', 2),
       ('car_tarp_cover_1', 2), ('semi_trailer_freestanding', 2), ('cargo_container_closed', 2), ('van', 2), ('dust_limo_lowpoly', 1), ('nuke_sedan01_low', 2)]
ALSO = {'dust_hatchback_body': ['dust_hatchback_wheels'], 'dust_taxi_body': []}
SMALL = [('car_tire', 5), ('barrel_group_tintable_01', 4), ('wood_pallet', 3), ('traffic_cone', 3), ('propane_tank_01_cluster_01', 2), ('nuke_concrete_barrier', 3),
         ('cable_spool', 2), ('sawhorse_1', 2), ('garbage_bag_1', 1)]


class Pass:
    def __init__(self, arena, keep):
        self.rnd = random.Random(52011)
        self.nav = arena['nav']; self.arena = arena
        self.keep = keep                       # [(x, y, r)] of the mapper's own props
        self.cells = {}                        # 128 u cells -> [(x, y, r)] of what this pass placed
        self._cell = {}
        self.out = []                          # (model, (x, y, z), (pitch, yaw, roll), scale, tint)
        self.n = {}; self.tris = 0

    # -- where
    def gz(self, x, y): return D.ground_at(x, y)

    def slope(self, x, y, h=40.0):
        return math.degrees(math.atan(math.hypot(self.gz(x + h, y) - self.gz(x - h, y), self.gz(x, y + h) - self.gz(x, y - h)) / (2 * h)))

    def struct(self, x, y, margin=60.0):
        """True where the generator built something: the nav cell (256 u) here, or one within `margin` of here, that a mech cannot
        walk or whose walking height is not the terrain's (a deck, a roof, a rock top). nav.struct itself is far wider (two cells
        round every footprint, the megastructure's approach lanes): it ruled out 39 % of the map."""
        n = self.nav; c = n['cell']
        for i in range(int((x - margin - n['x0']) // c), int((x + margin - n['x0']) // c) + 1):
            for j in range(int((y - margin - n['y0']) // c), int((y + margin - n['y0']) // c) + 1):
                if not (0 <= i < n['w'] and 0 <= j < n['h']): return True
                k = j * n['w'] + i
                if k not in self._cell:
                    cx, cy = n['x0'] + (i + 0.5) * c, n['y0'] + (j + 0.5) * c
                    # something stands on the cell (its walking height is above the terrain) or it is closed on flat ground (a tank, a
                    # rock: a steep dune cell is closed too, but the slope rule sees to that)
                    self._cell[k] = n['height'][k] - self.gz(cx, cy) > 80.0 or (not n['walk'][k] and self.slope(cx, cy, 100.0) < 18.0)
                if self._cell[k]: return True
        return False

    def free(self, x, y, r, max_slope=11.0, on_struct=False):
        if abs(x) > 6750 or abs(y) > 6750: return False
        if not on_struct and self.struct(x, y): return False
        for kx, ky, kr in self.keep:
            if (x - kx) ** 2 + (y - ky) ** 2 < (r + kr) ** 2: return False
        for p in self.arena['points']:
            if math.hypot(x - p['pos'][0], y - p['pos'][1]) < 430: return False
        for team in self.arena['drops'].values():
            for dp in team:
                if math.hypot(x - dp[0], y - dp[1]) < 330: return False
        ci, cj = int(x // 128), int(y // 128)
        for a in range(ci - 4, ci + 5):
            for b in range(cj - 4, cj + 5):
                for px, py, pr in self.cells.get((a, b), ()):
                    if (x - px) ** 2 + (y - py) ** 2 < (r + pr) ** 2: return False
        return self.slope(x, y) <= max_slope

    # -- what
    def put(self, key, x, y, yaw, scale=S, tint=None, sink=3.0, tilt=0.0, z=None, check=True, max_slope=11.0, on_struct=False, pad=6.0):
        k = KIT[key]; lo, hi = k['lo'], k['hi']
        r = 0.5 * math.hypot(hi[0] - lo[0], hi[1] - lo[1]) * scale * 0.8 + pad
        if check and not self.free(x, y, r, max_slope, on_struct): return False
        gz = self.gz(x, y) if z is None else z
        sl = math.tan(math.radians(min(self.slope(x, y), 20.0))) * r * 0.6 if z is None else 0.0
        zz = gz - lo[2] * scale - sink - sl
        ang = (self.rnd.uniform(-tilt, tilt), yaw % 360.0, self.rnd.uniform(-tilt, tilt)) if tilt else (0.0, yaw % 360.0, 0.0)
        for kk in [key] + ALSO.get(key, []):
            self.out.append((KIT[kk]['model'], (round(x, 1), round(y, 1), round(zz, 1)), ang, scale, tint if kk == key else None))
            self.n[kk] = self.n.get(kk, 0) + 1; self.tris += KIT[kk].get('tris', 0)
        self.cells.setdefault((int(x // 128), int(y // 128)), []).append((x, y, r))
        return True

    def pick(self, table):
        return self.rnd.choices([k for k, _ in table], [w for _, w in table])[0]

    def clutter(self, x, y, n, r0=70.0, r1=170.0):
        for _ in range(n):
            a = self.rnd.uniform(0, 2 * math.pi); r = self.rnd.uniform(r0, r1); key = self.pick(SMALL)
            flat = key in ('car_tire', 'wood_pallet')
            self.put(key, x + r * math.cos(a), y + r * math.sin(a), self.rnd.uniform(0, 360), tint=self.rnd.choice(DUST) if key != 'traffic_cone' else None,
                     sink=4.0 if flat else 2.0, tilt=10.0 if key == 'car_tire' else 3.0)

    # -- vignettes
    def convoy(self, y0, y1, x_of=None, spread=(40.0, 190.0)):
        """a supply column along y from y0 to y1, on the line x_of(y) (default: the canyon's centre line); what does not fit is left out"""
        rnd = self.rnd; y = y0; step = -1 if y1 < y0 else 1; side = 1
        x_of = x_of or (lambda yy: float(D.canyon_cx(np.array([yy]))[0]))
        while (y - y1) * step < 0:
            cx = x_of(y); cx2 = x_of(y + 60.0)
            heading = math.degrees(math.atan2(60.0, cx2 - cx))
            key = self.pick(VEH); wreck = rnd.random() < 0.45
            x = cx + side * rnd.uniform(*spread)
            longx = KIT[key]['hi'][0] - KIT[key]['lo'][0] > KIT[key]['hi'][1] - KIT[key]['lo'][1]
            yaw = heading + (rnd.uniform(25, 80) * rnd.choice((-1, 1)) if wreck else rnd.uniform(-7, 7)) + (0 if longx else -90)
            if self.put(key, x, y, yaw, tint=rnd.choice(BOX if 'container' in key or 'trailer' in key else DUST), sink=rnd.uniform(4, 14) if wreck else 3.0,
                        tilt=7.0 if wreck else 1.5, max_slope=14.0):
                self.clutter(x, y, rnd.randint(1, 4))
            if rnd.random() < 0.3: side = -side
            y += step * rnd.uniform(230, 420)

    def camp(self, cx, cy, yaw, rows=2, cols=4, masts=True):
        """a container yard: rows x cols lots along `yaw`, some stacked, trailers and a truck beside, generators, fence, masts at the corners"""
        rnd = self.rnd; c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        L = lambda u, v: (cx + u * c - v * s, cy + u * s + v * c)
        placed = 0
        for i in range(cols):
            for j in range(rows):
                u, v = (i - (cols - 1) / 2) * 110.0, (j - (rows - 1) / 2) * 270.0
                x, y = L(u + rnd.uniform(-6, 6), v + rnd.uniform(-10, 10))
                if rnd.random() < 0.18: continue
                tint = rnd.choice(BOX); y0 = yaw + 90 + rnd.uniform(-3, 3)
                if self.put('cargo_container_closed', x, y, y0, tint=tint, sink=2.0, max_slope=8.0):
                    placed += 1; gz = self.gz(x, y) - 2.0
                    for lvl in range(1, rnd.choice((1, 1, 2, 2, 3))):
                        self.put('cargo_container_closed', x, y, y0 + rnd.uniform(-4, 4), tint=rnd.choice(BOX), z=gz + lvl * 128 * S, sink=0.0, check=False)
        if not placed: return 0
        w, h = cols * 110.0 / 2 + 150, rows * 270.0 / 2 + 130
        for u, v, key, a in ((-w - 60, 0, 'semi_trailer_freestanding', 0), (w + 70, -60, 'flatnose_truck_wrecked', 90), (w + 60, 150, 'semi_trailer', 0),
                             (0, h + 40, 'overpass_generator', 90), (-120, h + 50, 'power_generator_1', 0), (140, h + 60, 'portapotty_closed', 180),
                             (200, h + 62, 'portapotty_closed', 180), (-w + 40, -h - 30, 'cementmixer', 30)):
            x, y = L(u, v)
            if self.put(key, x, y, yaw + a + rnd.uniform(-6, 6), tint=rnd.choice(BOX if 'trailer' in key else DUST), max_slope=9.0): self.clutter(x, y, rnd.randint(0, 2), 50, 120)
        for k in range(10):                                           # loose yard clutter
            x, y = L(rnd.uniform(-w, w), rnd.choice((-1, 1)) * (h + rnd.uniform(0, 90)))
            self.clutter(x, y, 1, 0, 30)
        for sx in (-1, 1):                                            # a broken fence line on the two long sides
            for q in range(int(2 * h // 80)):
                if rnd.random() < 0.25: continue
                x, y = L(sx * (w + 150), -h + q * 80.0 + 40)
                self.put('construction_fence_1', x, y, yaw + 90 + rnd.uniform(-3, 3), sink=1.0, max_slope=9.0, pad=0.0)
        if masts:
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                x, y = L(sx * (w + 110), sy * (h + 70))
                self.put('floodlight_pole_1', x, y, yaw + (45 if sx * sy > 0 else -45) + 90, sink=6.0, max_slope=12.0)
        return placed

    def camp_near(self, cx, cy, yaw, reach=700.0, **kw):
        """the camp at the flattest free spot within `reach` of (cx, cy)"""
        best = None
        for _ in range(140):
            a = self.rnd.uniform(0, 2 * math.pi); r = self.rnd.uniform(0, reach); x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            if not self.free(x, y, 260.0, 7.0): continue
            sc = max(self.slope(x + dx, y + dy) for dx in (-200, 0, 200) for dy in (-200, 0, 200))
            if best is None or sc < best[0]: best = (sc, x, y)
        return self.camp(best[1], best[2], yaw, **kw) if best else 0

    def poles(self, p0, p1, gap=520.0, key='dust_light_pole_01'):
        d = math.hypot(p1[0] - p0[0], p1[1] - p0[1]); n = int(d // gap); yaw = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
        for k in range(n + 1):
            t = k / max(n, 1); x, y = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t
            x += self.rnd.uniform(-25, 25); y += self.rnd.uniform(-25, 25)
            if self.put(key, x, y, yaw + 90 + self.rnd.uniform(-4, 4), sink=8.0, tilt=2.5, max_slope=16.0) and self.rnd.random() < 0.3: self.clutter(x, y, 1, 30, 70)

    def ring(self, cx, cy, r, n, key='floodlight_pole_1', a0=0.0):
        for k in range(n):
            a = math.radians(a0 + 360.0 * k / n); x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            if self.put(key, x, y, math.degrees(a) + 180 + 90, sink=6.0, max_slope=14.0, on_struct=True): self.clutter(x, y, self.rnd.randint(0, 2), 40, 90)

    def scatter(self, n):
        rnd = self.rnd; done = 0; tries = 0
        table = [('dust_car_wreck_body', 6), ('dust_hatchback_body', 3), ('car_tire', 5), ('barrel_group_tintable_01', 4), ('cargo_container_closed', 2),
                 ('nuke_sedan01_low', 2), ('wood_pallet', 2), ('propane_tank_01_cluster_01', 2), ('dust_limo_lowpoly', 1), ('cable_spool', 1), ('nuke_concrete_barrier', 2)]
        while done < n and tries < n * 40:
            tries += 1
            x, y = rnd.uniform(-6500, 6500), rnd.uniform(-6500, 6500)
            if not self.free(x, y, 240.0, 13.0): continue
            key = self.pick(table); big = KIT[key].get('tris', 0) > 2000 or 'container' in key
            if self.put(key, x, y, rnd.uniform(0, 360), tint=rnd.choice(BOX if 'container' in key else DUST), sink=rnd.uniform(8, 22) if big else 4.0, tilt=9.0 if big else 6.0,
                        max_slope=13.0):
                done += 1
                if big: self.clutter(x, y, rnd.randint(1, 4), 60, 150)
        return done

    def build(self):
        A, B, C = D.A_POS, D.B_POS, D.C_POS
        self.convoy(5300.0, 1500.0); self.convoy(-1500.0, -2900.0)        # the canyon: skink52's rocks and the wreck leave little room there
        # the supply tracks inside both rims, behind the drop lines
        self.convoy(-4600.0, 4600.0, lambda yy: -5050.0 + 140.0 * math.sin(yy / 900.0), (20.0, 120.0))
        self.convoy(4600.0, -4600.0, lambda yy: 5050.0 + 140.0 * math.sin(yy / 900.0), (20.0, 120.0))
        self.n_camps = 0
        for (cx, cy, yaw, kw) in ((D.REF[0] - 1750, D.REF[1] - 200, 0, dict(rows=2, cols=5)), (D.REF[0] + 300, D.REF[1] - 1750, 90, dict(rows=2, cols=4)),
                                  (D.WRECK[0] - 1900, D.WRECK[1] + 500, 20, dict(rows=2, cols=4)), (D.WRECK[0] + 1900, D.WRECK[1] + 400, -20, dict(rows=2, cols=3)),
                                  (A[0] - 780, A[1] + 420, 60, dict(rows=1, cols=4, masts=False)), (C[0] + 780, C[1] - 420, 60, dict(rows=1, cols=4, masts=False)),
                                  (-5000.0, -900.0, 90, dict(rows=2, cols=4, reach=1100.0)), (-5000.0, 2600.0, 90, dict(rows=1, cols=5, reach=1100.0)),
                                  (5000.0, 900.0, 90, dict(rows=2, cols=4, reach=1100.0)), (5000.0, -2600.0, 90, dict(rows=1, cols=5, reach=1100.0))):
            self.n_camps += 1 if self.camp_near(cx, cy, yaw, **dict(dict(reach=900.0), **kw)) else 0
        self.poles((-6500.0, 300.0), (A[0] - 1150, A[1] - 300)); self.poles((6500.0, -300.0), (C[0] + 1150, C[1] + 300))
        self.poles((-1200.0, 6300.0), (D.REF[0] - 1500, D.REF[1] + 900))
        self.ring(A[0], A[1], D.PLATEAU_R - 70, 6, a0=15); self.ring(C[0], C[1], D.PLATEAU_R - 70, 6, a0=45); self.ring(B[0], B[1], D.ISLAND_R - 50, 5, a0=10)
        for x, y in ((-6450, 4300), (-6450, -4600), (6450, 4500), (6450, -4300), (-2800, 6500), (2600, -6500)):
            self.put('tv_tower', x, y, self.rnd.uniform(0, 360), scale=1.4, sink=14.0, max_slope=18.0, pad=30.0)
        self.n_scatter = self.scatter(240)


def main(src, out, addon='out/addon', stats=None):
    arena = json.load(open(os.path.join(addon, '_gen', 'arena.json')))
    d = G.open_map(src, addon)
    keep, offsets = [], [(0.0, 0.0, 0.0)]
    for c in G.entities(d):
        p = G.props_of(c); grp = c.get('customVisGroup', '')
        o = [float(v) for v in c.get('origin')]
        if p.get('targetname', '').startswith('ifr_arena_'): offsets.append(tuple(o))
        if grp == GROUP or not (-1500 < o[2] < 6000): continue
        if p.get('classname') == 'prop_static':
            sc = float(c.get('scales')[0]) if c.get('scales') is not None else 1.0
            keep.append((o[0], o[1], max(180.0, min(1500.0, 150.0 * sc))))
        elif p.get('classname') in ('info_target', 'light_omni2', 'info_particle_system'):
            keep.append((o[0], o[1], 90.0))
    ps = Pass(arena, keep); ps.build()
    for off in offsets:
        for model, (x, y, z), ang, scale, tint in ps.out:
            keys = dict(model=model, solid='0', bakelighting='0')
            if tint: keys['rendercolor'] = tint
            e = G.ent('prop_static', (x + off[0], y + off[1], z + off[2]), angles=ang, group=GROUP, **keys)
            e.attr('scales')[2] = (scale, scale, scale)
    G.finish(d, out, group=GROUP, first_run_cleanup=False)
    rep = dict(props_per_copy=len(ps.out), copies=len(offsets), lod0_triangles_per_copy=ps.tris, camps=ps.n_camps, scatter=ps.n_scatter, kept_clear_of=len(keep),
               by_model=dict(sorted(ps.n.items(), key=lambda kv: -kv[1])), placed=[(m, p, a, s) for m, p, a, s, _ in ps.out])
    if stats: json.dump(rep, open(stats, 'w'), indent=0)
    print('dunes detail: %d props a copy x %d copies (%d k LOD0 triangles a copy), %d camps, %d scatter spots, clear of %d existing things -> %s'
          % (len(ps.out), len(offsets), ps.tris // 1000, ps.n_camps, ps.n_scatter, len(keep), out))
    print('  ' + ', '.join('%s %d' % kv for kv in list(rep['by_model'].items())[:14]))


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    st = a[a.index('--stats') + 1] if '--stats' in a else None
    pos = [x for i, x in enumerate(a) if not x.startswith('--') and (i == 0 or a[i - 1] != '--stats')]
    main(pos[0], pos[1], pos[2] if len(pos) > 2 else 'out/addon', st)
