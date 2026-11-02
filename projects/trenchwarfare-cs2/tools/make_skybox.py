"""Fills the 3D skybox map (sky_camera at the origin, scale 16) with the world outside the playable map: a rolling terrain ring that
continues the main terrain past the map edge, forest on it, and a far ridge line. Nothing inside the flight volume may live here
(skybox content is drawn behind everything), so the ring starts at the main map edge.
usage: make_skybox.py <skybox .vmap in> <skybox .vmap out>"""
import os, sys, math
import numpy as np
import dmx
from dmx import T_STRING
import vmaplib
from vmaplib import ent
import vmesh
import layout as LY
from noise import fbm

SRC, OUTPATH = sys.argv[1], sys.argv[2]
GROUP = 'tw_sky'
K = 16.0                                    # sky_camera scale
RING = 30720.0                              # world half extent of the ring
rng = np.random.RandomState(1918)

d = dmx.DMX.load(SRC)
world = d.root.get('world')
vmaplib.init(d, os.path.dirname(OUTPATH))
FOREST = 'materials/de_ancient/hr_ancient_blend_groundgrass01-grounddirt01-wet.vmat'
vmesh.TEX_SIZE[FOREST] = (1024, 1024)
EX, EY = LY.MAP_X, LY.MAP_Y


def edge_dist(x, y):
    return np.maximum(np.maximum(np.abs(x) - EX, np.abs(y) - EY), 0)


def height(x, y):
    """world-unit height outside the map: meets ground_low at the edge, rises into wooded hills and a far ridge"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    e = edge_dist(x, y)
    base = LY.ground_low(np.clip(x, -EX, EX), np.clip(y, -EY, EY))
    ramp = np.clip(e / 5000.0, 0, 1) ** 1.3
    hills = 520 * fbm(x / 7000.0, y / 7000.0, 0.7, 4, seed=41) + 260 * fbm(x / 2400.0, y / 2400.0, 2.1, 3, seed=42) + 380
    ridge = np.clip((e - 9000) / 9000.0, 0, 1) ** 1.5 * (900 + 500 * fbm(x / 9000.0, y / 9000.0, 3.3, 3, seed=43))
    return base * (1 - ramp) + (base + hills) * ramp + ridge - 6 * (e < 64)


# ---------------------------------------------------------------- terrain ring (in sky units)
STEP = 512.0
xs = np.arange(-RING, RING + 1, STEP); ys = np.arange(-RING, RING + 1, STEP)
X, Y = np.meshgrid(xs, ys, indexing='ij')
Z = height(X, Y)
inner = (np.abs(X) < EX - 1024) & (np.abs(Y) < EY - 1024)
valid = ~(inner[:-1, :-1] & inner[1:, :-1] & inner[:-1, 1:] & inner[1:, 1:])
n1 = fbm(X / 3000.0, Y / 3000.0, 5.5, 3, seed=44)
w = np.clip(0.35 + 0.8 * n1, 0, 1)
PA = np.stack([w, np.zeros_like(w), np.full(w.shape, 0.35), np.zeros_like(w)], -1)
t = np.clip(0.8 + 0.15 * n1, 0.65, 1.0) * np.clip(1 - edge_dist(X, Y) / 60000.0, 0.7, 1)
TI = np.stack([t, t, t, np.ones_like(t)], -1)
# split into chunks so each mesh stays small
CH = 16
for i0 in range(0, len(xs) - 1, CH):
    for j0 in range(0, len(ys) - 1, CH):
        sl = (slice(i0, min(i0 + CH, len(xs) - 1) + 1), slice(j0, min(j0 + CH, len(ys) - 1) + 1))
        v = valid[sl[0].start:sl[0].stop - 1, sl[1].start:sl[1].stop - 1]
        if not v.any(): continue
        verts, faces, mats, (pa, ti) = vmesh.grid_sheet(X[sl] / K, Y[sl] / K, Z[sl] / K, lambda i, j: FOREST, v, vert_attr=(PA[sl], TI[sl]))
        vmesh.mesh_node(vmesh.polymesh_open(verts, faces, mats, scale=0.25 / K, paint=pa, tint=ti), GROUP, bake=True, shadows=True)

# ---------------------------------------------------------------- forest (stock vista poplars / full maples near the edge)
VISTA = ['models/foliage/trees/poplar/tree_poplar_mature_01_vista.vmdl', 'models/foliage/trees/poplar/tree_poplar_mature_02_vista.vmdl',
         'models/foliage/trees/poplar/tree_poplar_adult_01_vista.vmdl', 'models/foliage/trees/poplar/tree_poplar_adult_02_vista.vmdl']
FULL = ['models/foliage/trees/maple/maple_01/maple_tree_01.vmdl', 'models/foliage/trees/maple/maple_01/maple_tree_02.vmdl']
used = set()
nt = 0
for gx in np.arange(-RING + 300, RING - 300, 420.0):
    for gy in np.arange(-RING + 300, RING - 300, 420.0):
        x = gx + rng.uniform(-180, 180); y = gy + rng.uniform(-180, 180)
        e = float(edge_dist(np.array([x]), np.array([y]))[0])
        if e < 120: continue
        dens = 0.95 if e < 3000 else (0.4 if e < 10000 else 0.12)
        if fbm(x / 4000.0, y / 4000.0, 9.1, 2, seed=45) < -0.3 or rng.rand() > dens: continue
        z = float(height(np.array([x]), np.array([y]))[0]) - 6
        model = FULL[rng.randint(2)] if (e < 1500 and rng.rand() < 0.3) else VISTA[rng.randint(4)]
        sc = rng.uniform(0.9, 1.35) / K
        e_ = ent('prop_static', (x / K, y / K, z / K), (0, rng.uniform(0, 360), 0), group=GROUP, model=model, rendercolor='255 255 255', skin='default',
                 solid='0', bakelighting='1', disableshadows='1', lodlevel='-1', baketoworld='0', rendertocubemaps='1')
        e_.attr('scales')[2] = (sc, sc, sc)
        used.add(model); nt += 1

# ---------------------------------------------------------------- swap into the world
kids = world.attr('children')
kids[2] = [c for c in kids[2] if c.get('customVisGroup', '') != GROUP] + vmaplib.new_children
pre = {a[0]: a for a in d.prefix[0]}
if 'map_asset_references' in pre:
    refs = pre['map_asset_references'][2]
    for m in list(vmaplib.materials_used) + sorted(used):
        if m not in refs: refs.append(m)
d.elements = [d.root]
d.save(OUTPATH)
print('skybox: %d trees, %d meshes -> %s (%.1f MB)' % (nt, sum(1 for c in kids[2] if c.type == 'CMapMesh'), OUTPATH, os.path.getsize(OUTPATH) / 1e6))
