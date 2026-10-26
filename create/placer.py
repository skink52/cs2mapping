"""Footprints of placed props (oriented boxes with a z range) on a spatial-hash grid, so optional set dressing never
interpenetrates anything, plus an overlap audit of everything placed.

    import placer
    PL = placer.Placer()                       # bounds from props.json + converted SMDs + the STOCK table below
    f = PL.footprint(model, x, y, z, yaw, scale=(1, 1, 1), pad=2.0)
    if not PL.hits(f): PL.add(f); <place the prop>
    pairs = PL.audit(); PL.write_audit('overlaps.json')      # interpenetrating pairs, top model pairs printed

Model bounds come from, in order: the props.json written by build_all_props.py (our procedural props, models/<prefix>/<name>),
the SMD of a converted model (models/<prefix>/ext/<name>/<name>.smd, e.g. from glb2cs2_multi.py), the STOCK table (stock CS2
models; hand-entered example values from mg_trenchwarfare, estimated and kept conservative, so measure your own), then name rules
for trees (TREE_R), then a 24 x 24 x 24 default. Pass bounds_table={model: ((lo), (hi))} to add your own.

usage (audit of a vmap's props): placer.py <map.vmap> [props.json] [overlaps.json]

From trenchwarfare-cs2/tools/placer.py (MIT), made project-neutral.
"""
import os, sys, json, math
import numpy as np

OUT = os.environ.get('CS2_ADDON_OUT', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'addon'))
PREFIX = os.environ.get('CS2_MODEL_PREFIX', 'props')
PROPS_JSON = os.path.join(os.path.dirname(os.path.abspath(OUT)), 'props.json')

# stock CS2 models: (lo, hi) in model units. Example values (estimated, conservative), not measured from the compiled models.
STOCK = {
    'models/generic/barrel_kit_01/barrel_01_a.vmdl': ((-13, -13, 0), (13, 13, 44)),
    'models/generic/crate_wooden_01/crate_wooden_01_a.vmdl': ((-16, -16, 0), (16, 16, 32)),
    'models/de_inferno/wood_pallet_01/inferno_pallet_wood_01.vmdl': ((-24, -20, 0), (24, 20, 6)),
    'models/de_overpass/junk/wheelbarrow01a/wheelbarrow01a.vmdl': ((-30, -14, 0), (30, 14, 26)),
}
# trunk radius by name fragment (canopies overlap freely); 0 = no footprint (grass, weeds)
TREE_R = {'maple': 14, 'poplar': 12, 'beech': 9, 'dogwood': 20, 'viburnum': 18, 'weed': 0, 'grass': 0, 'leaves': 0}
DEFAULT = ((-12, -12, 0), (12, 12, 24))


class Bounds:
    def __init__(self, props_json=PROPS_JSON, out=OUT, prefix=PREFIX, table=None):
        self.out, self.prefix = out, prefix
        self.props = json.load(open(props_json)) if props_json and os.path.exists(props_json) else {}
        self.table = dict(STOCK); self.table.update(table or {})
        self.cache = {}

    def smd_bounds(self, path):
        """vertex bounds of an SMD in Hammer coordinates (SMD (x, y, z) -> Hammer (-y, x, z))"""
        V = []
        for l in open(path):
            q = l.split()
            if len(q) >= 9 and q[0] == '0':
                try: V.append((-float(q[2]), float(q[1]), float(q[3])))
                except ValueError: pass
        V = np.array(V) if V else np.zeros((1, 3))
        return tuple(V.min(0)), tuple(V.max(0))

    def __call__(self, model):
        if model in self.cache: return self.cache[model]
        r = self._find(model); self.cache[model] = r
        return r

    def _find(self, model):
        if model in self.table: return self.table[model]
        name = model.split('/')[-1][:-5]
        mine = 'models/%s/' % self.prefix
        if model.startswith(mine + 'ext/'):
            base = name[:-4] if name.endswith('_dyn') else name
            smd = os.path.join(self.out, mine + 'ext/%s/%s.smd' % (base, base))
            if os.path.exists(smd): return self.smd_bounds(smd)
        elif name in self.props:
            return tuple(self.props[name]['mins']), tuple(self.props[name]['maxs'])
        for k, r in TREE_R.items():
            if k in model: return (-r, -r, 0), (r, r, 300 if r > 10 else 60)
        return DEFAULT


class Placer:
    def __init__(self, cell=192.0, bounds=None):
        self.cell = cell; self.grid = {}; self.items = []
        self.bounds = bounds or Bounds()

    def footprint(self, model, x, y, z, yaw, scale=(1, 1, 1), pad=0.0):
        lo, hi = self.bounds(model)
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
        """oriented boxes in plan (separating axes) and their z ranges"""
        if f['z'][1] <= g['z'][0] or g['z'][1] <= f['z'][0]: return False
        if min(f['h']) <= 0 or min(g['h']) <= 0: return False
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
        """first registered footprint f overlaps, or None"""
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
        return idx

    def add_entities(self, nodes, pad=0.0):
        """register the props of existing map nodes (e.g. the user's own placements) as obstacles"""
        n = 0
        for c in nodes:
            if c.type != 'CMapEntity': continue
            m = c.get('entity_properties').get('model') or ''
            if not m.endswith('.vmdl'): continue
            o = c.get('origin'); self.add(self.footprint(m, o[0], o[1], o[2], c.get('angles')[1], tuple(c.get('scales') or (1, 1, 1)), pad)); n += 1
        return n

    def audit(self, skip=lambda f: False):
        """index pairs of registered footprints that interpenetrate"""
        out = set()
        for i, f in enumerate(self.items):
            if skip(f): continue
            for k in self._keys(f):
                for j in self.grid.get(k, ()):
                    if j <= i or skip(self.items[j]): continue
                    if self.overlap(f, self.items[j]): out.add((i, j))
        return sorted(out)

    def write_audit(self, path, top=25):
        from collections import Counter
        pairs = self.audit()
        short = lambda m: m.split('/')[-1][:-5]
        cnt = Counter(tuple(sorted((short(self.items[i]['model']), short(self.items[j]['model'])))) for i, j in pairs)
        print('overlaps: %d pairs' % len(pairs), cnt.most_common(top))
        json.dump([dict(a=self.items[i]['model'], b=self.items[j]['model'], ca=self.items[i]['c'], cb=self.items[j]['c']) for i, j in pairs],
                  open(path, 'w'), indent=0)
        return pairs


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    import dmx, vmapgen
    d = dmx.DMX.load(sys.argv[1])
    PL = Placer(bounds=Bounds(sys.argv[2] if len(sys.argv) > 2 else PROPS_JSON))
    n = PL.add_entities(vmapgen.entities(d))
    print('%d props registered' % n)
    PL.write_audit(sys.argv[3] if len(sys.argv) > 3 else 'overlaps.json')
