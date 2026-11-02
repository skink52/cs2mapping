"""Footprints of placed props (oriented boxes with a z range) so optional dressing never interpenetrates anything, plus the model
bounds it needs: our props (out/props.json), converted glb models (their SMDs) and measured/estimated stock CS2 models."""
import os, json, math
import numpy as np

HERE = os.path.dirname(__file__)
OUTDIR = os.path.join(HERE, '..', 'out')

# stock CS2 models: (lo, hi) in model units, estimated from the game where unmeasured (kept conservative)
STOCK = {
    'models/generic/ammo_artillery_01/ammo_artillery_small_01.vmdl': ((-14, -10, 0), (14, 10, 14)),
    'models/generic/ammo_artillery_01/ammo_artillery_small_01b.vmdl': ((-14, -10, 0), (14, 10, 14)),
    'models/generic/barrel_kit_01/barrel_01_a.vmdl': ((-13, -13, 0), (13, 13, 44)),
    'models/generic/barrel_kit_01/barrel_02_a.vmdl': ((-13, -13, 0), (13, 13, 44)),
    'models/generic/barrel_kit_01/barrel_03_a.vmdl': ((-13, -13, 0), (13, 13, 44)),
    'models/de_inferno/wood_pallet_01/inferno_pallet_wood_01.vmdl': ((-24, -20, 0), (24, 20, 6)),
    'models/generic/crate_wooden_01/crate_wooden_01_a.vmdl': ((-16, -16, 0), (16, 16, 32)),
    'models/generic/crate_wooden_01/crate_wooden_01_b.vmdl': ((-16, -16, 0), (16, 16, 32)),
    'models/generic/crate_wooden_01/crate_wooden_01_c.vmdl': ((-16, -16, 0), (16, 16, 32)),
    'models/de_overpass/junk/wheelbarrow01a/wheelbarrow01a.vmdl': ((-30, -14, 0), (30, 14, 26)),
    'models/props/de_ancient/ancient_lighting/ancient_lighting_candle_cluster_01_lit.vmdl': ((-4, -4, 0), (4, 4, 6)),
}
TREE_R = {'maple': 14, 'poplar': 12, 'beech': 9, 'dogwood': 20, 'viburnum': 18, 'weed': 0, 'grass': 0, 'leaves': 0}

_props = None
_ext = {}


def bounds(model):
    global _props
    if _props is None:
        p = os.path.join(OUTDIR, 'props.json'); _props = json.load(open(p)) if os.path.exists(p) else {}
    name = model.split('/')[-1][:-5]
    if model.startswith('models/tw/') and not model.startswith('models/tw/ext/') and name in _props:
        return tuple(_props[name]['mins']), tuple(_props[name]['maxs'])
    if model.startswith('models/tw/ext/'):
        if model not in _ext:
            base = name[:-4] if name.endswith('_dyn') else name
            smd = os.path.join(OUTDIR, 'addon', 'models/tw/ext/%s/%s.smd' % (base, base))
            V = []
            if os.path.exists(smd):
                for l in open(smd):
                    q = l.split()
                    if len(q) >= 9 and q[0] == '0':
                        try: V.append((-float(q[2]), float(q[1]), float(q[3])))
                        except ValueError: pass
            V = np.array(V) if V else np.zeros((1, 3))
            _ext[model] = (tuple(V.min(0)), tuple(V.max(0)))
        return _ext[model]
    if model in STOCK: return STOCK[model]
    for k, r in TREE_R.items():
        if k in model: return (-r, -r, 0), (r, r, 300 if r > 10 else 60)
    return (-12, -12, 0), (12, 12, 24)


class Placer:
    def __init__(self, cell=192.0):
        self.cell = cell; self.grid = {}; self.items = []

    def footprint(self, model, x, y, z, yaw, scale=(1, 1, 1), pad=0.0):
        lo, hi = bounds(model)
        sx, sy, sz = scale
        cx, cy = (lo[0] + hi[0]) / 2 * sx, (lo[1] + hi[1]) / 2 * sy
        hx, hy = (hi[0] - lo[0]) / 2 * sx + pad, (hi[1] - lo[1]) / 2 * sy + pad
        a = math.radians(yaw); c, s = math.cos(a), math.sin(a)
        return dict(c=(x + c * cx - s * cy, y + s * cx + c * cy), h=(hx, hy), a=a, z=(z + lo[2] * sz, z + hi[2] * sz), model=model)

    @staticmethod
    def _axes(f):
        c, s = math.cos(f['a']), math.sin(f['a'])
        return (c, s), (-s, c)

    @staticmethod
    def overlap(f, g):
        if f['z'][1] <= g['z'][0] or g['z'][1] <= f['z'][0]: return False
        d = (g['c'][0] - f['c'][0], g['c'][1] - f['c'][1])
        fa, ga = Placer._axes(f), Placer._axes(g)
        for ax in fa + ga:
            rf = sum(abs(ax[0] * a[0] + ax[1] * a[1]) * h for a, h in zip(fa, f['h']))
            rg = sum(abs(ax[0] * a[0] + ax[1] * a[1]) * h for a, h in zip(ga, g['h']))
            if abs(d[0] * ax[0] + d[1] * ax[1]) > rf + rg: return False
        return True

    def _keys(self, f):
        r = math.hypot(*f['h'])
        x0, x1 = int(math.floor((f['c'][0] - r) / self.cell)), int(math.floor((f['c'][0] + r) / self.cell))
        y0, y1 = int(math.floor((f['c'][1] - r) / self.cell)), int(math.floor((f['c'][1] + r) / self.cell))
        return [(i, j) for i in range(x0, x1 + 1) for j in range(y0, y1 + 1)]

    def hits(self, f):
        seen = set()
        for k in self._keys(f):
            for idx in self.grid.get(k, ()):
                if idx in seen: continue
                seen.add(idx)
                if self.overlap(f, self.items[idx]): return self.items[idx]
        return None

    def add(self, f):
        self.items.append(f); idx = len(self.items) - 1
        for k in self._keys(f): self.grid.setdefault(k, []).append(idx)

    def audit(self, skip=lambda f: False):
        """pairs of registered footprints that interpenetrate"""
        out = []
        for i, f in enumerate(self.items):
            if skip(f): continue
            for k in self._keys(f):
                for j in self.grid.get(k, ()):
                    if j <= i or skip(self.items[j]): continue
                    if self.overlap(f, self.items[j]): out.append((i, j))
        return sorted(set(out))
