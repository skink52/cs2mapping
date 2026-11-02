"""Fills a 3D skybox map with the world outside the playable map: a terrain ring at 1/16 scale that continues the main map's ground
past its edge into hills and a far ridge, with stock trees scattered on it (prop_static, baked light, no shadows).
Skybox content is drawn behind everything, so nothing players or vehicles can reach may be in it: the ring starts at the main
map's edge (half extents --half) and leaves the inside empty.

usage: make_skybox.py <skybox .vmap in> <skybox .vmap out> --half 7680 6912 [--edge-z 0] [--ring 30720] [--material <blend vmat>]
                      [--trees m1.vmdl,m2.vmdl] [--near-trees m3.vmdl] [--seed 1] [--group sky_gen]
Python: make_skybox.build(d, half=(EX, EY), edge_height=fn(x, y) -> z of the main map's ground at its edge, ...) then vmapgen.finish().

The skybox map (maps/<map>_3dskybox.vmap): mapUsageType "skybox" (set on its world node; this tool sets it), its own
light_environment + env_sky, and a sky_camera at the origin with scale 16 (added if missing; untick Editor only if the sky
doesn't render). The main map gets a skybox_reference (vmapgen.skybox_reference): origin (0,0,0), targetMapName
maps/<map>_3dskybox.vmap, fixupNames 1, worldGroupID skyboxWorldGroup0. Re-runs replace only the --group vis group.

Options added for project copies (CLI defaults also from toolkit.json "skybox" next to this file): --layout MODULE (half extents
MAP_X/MAP_Y and edge height ground_low(x, y) from a project module, instead of --half/--edge-z), --noise-seed N (terrain/forest
noise seeds 41+N.., default = --seed), --plain (no vmapgen: map left as is apart from the vis group swap and appended asset refs,
no pinch fix). build(noise_seed=None, plain=False).

From trenchwarfare-cs2/tools/make_skybox.py (MIT), made project-neutral.
"""
import os, sys, json, importlib, argparse
import numpy as np
import vmaplib, vmesh
from vmaplib import ent
from noise import fbm

K = 16.0          # sky_camera scale: skybox geometry is authored at world size / 16 around the origin
BLEND = 'materials/de_ancient/hr_ancient_blend_groundgrass01-grounddirt01-wet.vmat'
VISTA = ['models/foliage/trees/poplar/tree_poplar_mature_01_vista.vmdl', 'models/foliage/trees/poplar/tree_poplar_mature_02_vista.vmdl',
         'models/foliage/trees/poplar/tree_poplar_adult_01_vista.vmdl', 'models/foliage/trees/poplar/tree_poplar_adult_02_vista.vmdl']
FULL = ['models/foliage/trees/maple/maple_01/maple_tree_01.vmdl', 'models/foliage/trees/maple/maple_01/maple_tree_02.vmdl']


def make_height(half, edge_height, seed=41, hills=1.0, ridge=1.0, lerp=False):
    """world-unit height outside the map: meets edge_height at the edge, rises into rolling hills and a far ridge line"""
    EX, EY = half
    def edge_dist(x, y): return np.maximum(np.maximum(np.abs(x) - EX, np.abs(y) - EY), 0)
    def height(x, y):
        x = np.asarray(x, float); y = np.asarray(y, float)
        e = edge_dist(x, y)
        base = np.asarray(edge_height(np.clip(x, -EX, EX), np.clip(y, -EY, EY)), float) + 0 * x
        ramp = np.clip(e / 5000.0, 0, 1) ** 1.3
        h = hills * (520 * fbm(x / 7000.0, y / 7000.0, 0.7, 4, seed=seed) + 260 * fbm(x / 2400.0, y / 2400.0, 2.1, 3, seed=seed + 1) + 380)
        r = ridge * np.clip((e - 9000) / 9000.0, 0, 1) ** 1.5 * (900 + 500 * fbm(x / 9000.0, y / 9000.0, 3.3, 3, seed=seed + 2))
        hh = base * (1 - ramp) + (base + h) * ramp if lerp else base + h * ramp      # same value; lerp = the trench original's float rounding
        return hh + r - 6 * (e < 64)          # sink 6 units at the seam so no lip shows past the main ground
    return height, edge_dist


def ensure_skybox_map(d, group):
    """mapUsageType skybox on the world node, and a sky_camera (scale 16) at the origin if the map has none"""
    import vmapgen
    w = d.root.get('world')
    a = w.attr('mapUsageType')
    if a is not None and a[2] != 'skybox':
        print('skybox: mapUsageType %s -> skybox' % a[2]); a[2] = 'skybox'
    if not any(vmapgen.props_of(c).get('classname') == 'sky_camera' for c in vmapgen.entities(d)):
        ent('sky_camera', (0, 0, 0), group='', scale=str(int(K)))     # no vis group: it belongs to the map, re-runs keep it
        print('skybox: added sky_camera (scale 16) at the origin; add a light_environment and env_sky too')


def build(d, half, edge_height, ring=30720.0, step=512.0, material=BLEND, trees=VISTA, near_trees=FULL, seed=1, group='sky_gen',
          tree_spacing=420.0, noise_seed=None, plain=False):
    """terrain ring (open sheets with vertex paint, chunks of 16x16 cells) + trees; returns (meshes, trees, models used).
    seed: tree placement; noise_seed (default seed): terrain and forest noise; plain: the trench original exactly (no pinch fix)"""
    rng = np.random.RandomState(seed)
    ns = seed if noise_seed is None else noise_seed
    EX, EY = half
    height, edge_dist = make_height(half, edge_height, seed=41 + ns, lerp=plain)
    vmesh.TEX_SIZE[material] = (1024, 1024)
    xs = np.arange(-ring, ring + 1, step); ys = np.arange(-ring, ring + 1, step)
    X, Y = np.meshgrid(xs, ys, indexing='ij')
    Z = height(X, Y)
    inner = (np.abs(X) < EX - 1024) & (np.abs(Y) < EY - 1024)                  # cells well inside the map: left out
    valid = ~(inner[:-1, :-1] & inner[1:, :-1] & inner[:-1, 1:] & inner[1:, 1:])
    n1 = fbm(X / 3000.0, Y / 3000.0, 5.5, 3, seed=44 + ns)
    w = np.clip(0.35 + 0.8 * n1, 0, 1)
    PA = np.stack([w, np.zeros_like(w), np.full(w.shape, 0.35), np.zeros_like(w)], -1)            # blend A/B per vertex
    t = np.clip(0.8 + 0.15 * n1, 0.65, 1.0) * np.clip(1 - edge_dist(X, Y) / 60000.0, 0.7, 1)   # darker far away
    TI = np.stack([t, t, t, np.ones_like(t)], -1)
    CH = 16; nm = 0
    for i0 in range(0, len(xs) - 1, CH):
        for j0 in range(0, len(ys) - 1, CH):
            sl = (slice(i0, min(i0 + CH, len(xs) - 1) + 1), slice(j0, min(j0 + CH, len(ys) - 1) + 1))
            v = valid[sl[0].start:sl[0].stop - 1, sl[1].start:sl[1].stop - 1]
            if not v.any(): continue
            if not plain:
                import vmapgen
                v = vmapgen.fix_pinches(v)
            verts, faces, mats, (pa, ti) = vmesh.grid_sheet(X[sl] / K, Y[sl] / K, Z[sl] / K, lambda i, j: material, v, vert_attr=(PA[sl], TI[sl]))
            vmesh.mesh_node(vmesh.polymesh_open(verts, faces, mats, scale=0.25 / K, paint=pa, tint=ti), group, bake=True, shadows=True)
            nm += 1
    used = set(); nt = 0
    if trees:
        for gx in np.arange(-ring + 300, ring - 300, tree_spacing):
            for gy in np.arange(-ring + 300, ring - 300, tree_spacing):
                x = gx + rng.uniform(-180, 180); y = gy + rng.uniform(-180, 180)
                e = float(edge_dist(np.array([x]), np.array([y]))[0])
                if e < 120: continue
                dens = 0.95 if e < 3000 else (0.4 if e < 10000 else 0.12)
                if fbm(x / 4000.0, y / 4000.0, 9.1, 2, seed=45 + ns) < -0.3 or rng.rand() > dens: continue
                z = float(height(np.array([x]), np.array([y]))[0]) - 6
                model = near_trees[rng.randint(len(near_trees))] if (near_trees and e < 1500 and rng.rand() < 0.3) else trees[rng.randint(len(trees))]
                sc = rng.uniform(0.9, 1.35) / K
                e_ = ent('prop_static', (x / K, y / K, z / K), (0, rng.uniform(0, 360), 0), group=group, model=model, rendercolor='255 255 255',
                         skin='default', solid='0', bakelighting='1', disableshadows='1', lodlevel='-1', baketoworld='0', rendertocubemaps='1')
                e_.attr('scales')[2] = (sc, sc, sc)
                used.add(model); nt += 1
    return nm, nt, used


def plain_save(d, out, group, used):
    """swap the vis group's nodes for vmaplib.new_children, append new materials/models to map_asset_references, save"""
    kids = d.root.get('world').attr('children')
    kids[2] = [c for c in kids[2] if c.get('customVisGroup', '') != group] + vmaplib.new_children
    pre = {a[0]: a for a in d.prefix[0]}
    if 'map_asset_references' in pre:
        refs = pre['map_asset_references'][2]
        for m in list(vmaplib.materials_used) + sorted(used):
            if m not in refs: refs.append(m)
    d.elements = [d.root]
    d.save(out)
    return sum(1 for c in kids[2] if c.type == 'CMapMesh')


if __name__ == '__main__':
    _cp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'toolkit.json')
    conf = (json.load(open(_cp)) if os.path.exists(_cp) else {}).get('skybox', {})
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('src'); ap.add_argument('out')
    ap.add_argument('--layout', default=conf.get('layout'), help='module with MAP_X, MAP_Y, ground_low(x, y)')
    ap.add_argument('--half', nargs=2, type=float, help='main map half extents x y (world units); required without --layout')
    ap.add_argument('--edge-z', type=float, default=0.0, help='main ground height at the map edge (Python API takes a function)')
    ap.add_argument('--ring', type=float, default=conf.get('ring', 30720.0))
    ap.add_argument('--material', default=conf.get('material', BLEND))
    ap.add_argument('--trees', default=','.join(conf.get('trees', VISTA))); ap.add_argument('--near-trees', default=','.join(conf.get('near_trees', FULL)))
    ap.add_argument('--seed', type=int, default=conf.get('seed', 1)); ap.add_argument('--group', default=conf.get('group', 'sky_gen'))
    ap.add_argument('--noise-seed', type=int, default=conf.get('noise_seed'))
    ap.add_argument('--plain', action='store_true', default=conf.get('plain', False))
    a = ap.parse_args()
    if a.layout:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        LY = importlib.import_module(a.layout)
        half, edge = (a.half and tuple(a.half)) or (LY.MAP_X, LY.MAP_Y), LY.ground_low
    elif a.half:
        half, edge = tuple(a.half), lambda x, y: np.full(np.shape(x), a.edge_z)
    else:
        ap.error('--half is required (or --layout)')
    trees = [t for t in a.trees.split(',') if t]; near = [t for t in a.near_trees.split(',') if t]
    if a.plain:
        import dmx
        d = dmx.DMX.load(a.src)
        vmaplib.init(d, os.path.dirname(a.out))
        nm, nt, used = build(d, half, edge, ring=a.ring, material=a.material, trees=trees, near_trees=near, seed=a.seed, group=a.group,
                             noise_seed=a.noise_seed, plain=True)
        nmesh = plain_save(d, a.out, a.group, used)
        print('skybox: %d trees, %d meshes -> %s (%.1f MB)' % (nt, nmesh, a.out, os.path.getsize(a.out) / 1e6))
    else:
        import vmapgen
        d = vmapgen.open_map(a.src, os.path.dirname(os.path.abspath(a.out)))
        ensure_skybox_map(d, a.group)
        nm, nt, _ = build(d, half, edge, ring=a.ring, material=a.material, trees=trees, near_trees=near, seed=a.seed, group=a.group,
                          noise_seed=a.noise_seed)
        print('skybox: %d terrain meshes, %d trees' % (nm, nt))
        vmapgen.finish(d, a.out, group=a.group, first_run_cleanup=False)
