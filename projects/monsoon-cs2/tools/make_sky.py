"""3D skybox map for mg_monsoon: the valley sides carried on past the terrain edge into jungle hills and a far ridge (make_skybox.py,
"plain" mode), a front row of Aztec banyans on the near slopes, then jungle made of Valve's Aztec skybox tree cards with a few
small banyans and palms, and limestone towers on the horizon (the same karst as inside the map), all at 1/16 scale around the
sky_camera.

Triangle budget (docs/SKYBOX_PERF.md; measure with `python sky_review.py budget <vmap>`): about 2 M. The stock banyans have one LOD
of 4.5-25 k triangles each and a baked (bakelighting 1) prop becomes unique world geometry, so 1,650 of them were 16.1 M triangles
and 417 MB of vertex data. Full 3D banyans now stand only in the front band (shell distance < FRONT_E, seen from 500-2000 units),
small ones in the middle band only where a ground player can see their crown; everything else is 8-triangle tree cards.

usage: make_sky.py [<template skybox .vmap> [<out .vmap>]] [--no-check]
  template  default ../out/sky_template.vmap; if it is missing it is copied from the user's mg_trenchwarfare skybox map
            (C:/source1/links/content_addons/mg_trenchwarfare/maps/mg_trenchwarfare_3dskybox.vmap): that map already has
            mapUsageType skybox, the sky_camera (scale 16), a light_environment and an env_sky. Its generated ring (vis group
            tw_sky: terrain + poplars) is dropped; anything else in it is kept.
  out       default ../out/addon/maps/mg_monsoon_3dskybox.vmap  (the main map's skybox_reference points at this name)
Re-runs replace only the vis group mv_sky (toolkit.json "skybox"). Then runs check_mesh.py on the result and writes ../out/sky.json.

The ring starts under the main terrain's edge (layout TERRAIN_X / TERRAIN_Y, not the play space) so there is no gap between
the terrain mesh and the sky shell; trees and towers only stand beyond the sky shell (nothing a helicopter can reach is in
the skybox: skybox geometry draws behind everything).
"""
import os, sys, json, math, shutil, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dmx, vmaplib, vmesh
from vmaplib import ent
from dmx import T_STRING
import layout as LY
import make_skybox as MS
from noise import fbm

CONF = json.load(open(os.path.join(HERE, 'toolkit.json'))).get('skybox', {})
GROUP = CONF.get('group', 'mv_sky')
SEED = CONF.get('seed', 1968)
NS = CONF.get('noise_seed', 0) if CONF.get('noise_seed') is not None else SEED
K = MS.K
TRENCH_SKY = 'C:/source1/links/content_addons/mg_trenchwarfare/maps/mg_trenchwarfare_3dskybox.vmap'
OLD_GROUPS = ('tw_sky',)                                   # generated content of the template's own project
GROUND = 'materials/de_ancient/hr_ancient_blend_groundgrass01-groundgrass02-wet.vmat'      # all green: the far hills are jungle
ROCK = 'materials/de_ancient/hr_ancient_blend_groundrock01-groundmoss02-wet-b.vmat'        # the karst blend of the main map
AZ = 'models/props/de_aztec/hr_aztec/aztec_foliage/'
NEAR = [AZ + 'hr_aztec_banyan_medium_01.vmdl', AZ + 'hr_aztec_banyan_medium_02.vmdl', AZ + 'hr_aztec_banyan_medium_03.vmdl',
        AZ + 'hr_aztec_banyan_large_01.vmdl', AZ + 'hr_aztec_banyan_small_01.vmdl', AZ + 'hr_aztec_banyan_small_02.vmdl']
NEAR_W = [3, 3, 3, 1.5, 2, 2]                               # front band: mostly medium, a few large, some small
SMALL = [AZ + 'hr_aztec_banyan_small_01.vmdl', AZ + 'hr_aztec_banyan_small_02.vmdl']
SB = 'models/props/de_aztec/hr_aztec/aztec_skybox/'
# Aztec skybox tree cards: one alpha-tested plane each (8 triangles, world size 450-1200 tall, two-sided material), turned to face the play space
CARDS = [SB + 'aztec_skybox_tree_card_cluster_01.vmdl', SB + 'aztec_skybox_tree_card_cluster_02.vmdl', SB + 'aztec_skybox_tree_card_large_01.vmdl',
         SB + 'aztec_skybox_tree_card_med_01.vmdl', SB + 'aztec_skybox_tree_card_med_02.vmdl', SB + 'aztec_skybox_tree_card_med_03.vmdl',
         SB + 'aztec_skybox_tree_card_small_01.vmdl', SB + 'aztec_skybox_tree_card_small_02.vmdl']
CARDS_W = [2, 2, 2, 2, 1.5, 1.5, 1, 1]
CARD_H = [959.0, 976.0, 1212.0, 972.0, 687.0, 694.0, 454.0, 666.0]   # their heights: a card is scaled to a drawn height, not by a factor
# drawn tree heights (world units) the cards and small banyans keep to, so the tree line stays where the banyans had it and the karst
# bases stay in view: medium banyans (590-1075 x 0.9-1.35) up to MID_E, small ones (400-610 x 0.9-1.35) further out
CARD_HT_MID, CARD_HT_FAR = (600.0, 950.0), (380.0, 700.0)
CARD_TINT = '210 214 200'      # the cards' texture is lighter than the banyans' (mean 77 85 48 against 63 72 41) and their trunks pale
# Not used: Aztec's underbrush card clusters (aztec_skybox_underbrush_combined_*). They are scattered undergrowth draped over Aztec's own
# slopes (tilted lines and sheets, out/review/sky/underbrush_models.png); set on these hills, parts float, and seen edge-on they showed as
# a dark hedge line in mid-air (candidates v3-v5, CT view).
# skybox palms are modelled at skybox scale already (31 units = 500 world units): placed at scale ~0.7, not / 16 (they were 30 units tall before)
PALMS = ['models/props/de_dust/hr_dust/foliage/palm_tree_skybox_01.vmdl', 'models/props/de_dust/hr_dust/foliage/palm_tree_skybox_02.vmdl']
# bands by distance past the sky shell (world units)
FRONT_E, FRONT_STEP = 900.0, 560.0         # full banyans: seen from 500-2000 units, where their 10-25 k triangles are 5-40 px^2 each
MID_E = 2600.0                             # small banyans (crown visible from the ground) among the cards up to here
CARD_E0, CARD_E1, CARD_STEP = 450.0, 9000.0, 360.0   # the old tree grid and densities (CARD_DENS), from between the front banyans out
CARD_DENS = ((2200.0, 0.85), (5000.0, 0.42), (1e9, 0.16))
SMALL_SHARE = 0.10                         # share of middle-band card spots that get a small banyan instead (if seen from the ground)
HALF = (float(LY.TERRAIN_X), float(LY.TERRAIN_Y))          # the ring meets the terrain mesh, which runs past the play space
SHELL = (float(LY.SKY_X), float(LY.SKY_Y))                 # nothing of the skybox stands inside the sky shell
# the main map's sun and sky (make_map.py stage 2), so the horizon is lit like the valley
SUN = dict(angles=(28.0, 205.0, 0.0), color='255 232 196', brightness='1.9', skycolor='170 186 205', skyintensity='1.5')
SKY = dict(skyname='materials/skybox/sky_overcast_01.vmat', tint_color='226 206 180', brightnessscale='1.05')


def set_key(ep, k, v):
    a = ep.attr(k)
    if a is not None: a[2] = str(v)
    else: ep.attrs.append([k, T_STRING, str(v)])


def retune_lights(d):
    n = 0
    for c in d.root.get('world').get('children'):
        if c.type != 'CMapEntity': continue
        ep = c.get('entity_properties'); cls = ep.get('classname')
        if cls == 'light_environment':
            c.attr('angles')[2] = SUN['angles']
            for k in ('color', 'brightness', 'skycolor', 'skyintensity'): set_key(ep, k, SUN[k])
            n += 1
        elif cls == 'env_sky':
            for k, v in SKY.items(): set_key(ep, k, v)
            n += 1
    return n


def karst(kx, ky, r, h, seed, z0, n_th=28, n_t=10):
    """a far limestone tower at 1/16 scale: fluted polar sheet with a domed, mossy crown (mv_terrain.karst_mesh, simplified)"""
    th = np.linspace(0, 2 * np.pi, n_th, endpoint=False); t = np.linspace(0, 1, n_t + 1)
    TH, Tt = np.meshgrid(th, t, indexing='ij')
    prof = 1.0 - 0.20 * Tt + 0.08 * np.exp(-((Tt - 0.5) / 0.22) ** 2) - 0.22 * np.clip((Tt - 0.7) / 0.3, 0, 1) ** 2
    lumps = fbm(np.cos(TH) * 1.6 + seed, np.sin(TH) * 1.6, Tt * 1.4, 3, seed=60 + seed)
    flutes = fbm(np.cos(TH) * 6.5, np.sin(TH) * 6.5 + seed, Tt * 1.2, 3, seed=65 + seed)
    rad = np.maximum(r * prof * (1.0 + 0.13 * lumps + 0.10 * flutes), r * 0.3)
    zz = z0 + h * Tt
    zz[:, -1] += 0.10 * h * (0.5 + 0.5 * np.sin(th * 3 + seed)) * (0.6 + 0.4 * lumps[:, -1])
    X = kx + rad * np.cos(TH); Y = ky + rad * np.sin(TH)
    idx = np.arange(n_th * (n_t + 1)).reshape(n_th, n_t + 1)
    verts = np.stack([X.ravel(), Y.ravel(), zz.ravel()], 1)
    faces = []
    for i in range(n_th):
        i2 = (i + 1) % n_th
        for j in range(n_t):
            faces.append([idx[i, j], idx[i2, j], idx[i2, j + 1], idx[i, j + 1]])
    ci = len(verts); verts = np.vstack([verts, [kx, ky, zz[:, -1].mean() + 0.04 * h]])
    for i in range(n_th):
        faces.append([idx[i, n_t], idx[(i + 1) % n_th, n_t], ci])
    a, b, c = verts[faces[0][0]], verts[faces[0][1]], verts[faces[0][2]]
    if np.cross(b - a, c - a) @ np.array([a[0] - kx, a[1] - ky, 0.0]) < 0: faces = [f[::-1] for f in faces]
    moss = np.clip(0.35 + 0.5 * (1 - Tt.ravel()) + 0.3 * lumps.ravel(), 0, 1)
    moss[idx[:, -1]] = 0.95
    moss = np.concatenate([moss, [1.0]])
    faces = back_cull(verts, faces, n_th, n_t)
    used = sorted(set(v for f in faces for v in f)); remap = {v: i for i, v in enumerate(used)}
    verts = verts[used]; moss = moss[used]; faces = [[remap[v] for v in f] for f in faces]
    pa = np.zeros((len(verts), 4)); pa[:, 0] = moss; pa[:, 2] = 0.35
    ti = np.ones((len(verts), 4)); ti[:, :3] = (0.62 + 0.20 * moss)[:, None]              # hazy and dark: silhouettes
    m = vmesh.polymesh_open(verts / K, faces, [ROCK] * len(faces), scale=0.5 / K, paint=pa, tint=ti)
    vmesh.mesh_node(m, GROUP, bake=True, shadows=True, smoothing=70.0)
    return sum(len(f) - 2 for f in faces)


# where anyone can be: helicopters up to their hard wall (layout AIR_* + 600), players on the ground below
VIEW_BOX = np.array([[x, y, z] for x in (-(LY.AIR_X + 600), LY.AIR_X + 600) for y in (-(LY.AIR_Y + 600), LY.AIR_Y + 600) for z in (-200.0, LY.AIR_Z + 600)])


def back_cull(verts, faces, n_th, n_t):
    """drop the tower's back: the longest run of theta columns whose side quads all face away from every corner of VIEW_BOX (a convex
    box: a face no corner sees is seen from nowhere in it). The crown (seen from helicopters above) stays whole; one contiguous run keeps
    the mesh a single open sheet with no pinch vertex."""
    def seen(f):
        p = verts[f]; c = p.mean(0); n = np.cross(p[1] - p[0], p[2] - p[0])
        return bool(((VIEW_BOX - c) @ n > 0).any())
    hidden = [not any(seen(faces[i * n_t + j]) for j in range(n_t)) for i in range(n_th)]
    if all(hidden) or not any(hidden): return faces
    best, start = (0, 0), None
    for k in range(2 * n_th):                       # longest circular run of hidden columns
        if hidden[k % n_th]:
            if start is None: start = k
            if n_th > k - start + 1 > best[0]: best = (k - start + 1, start)
        else: start = None
    drop = set((best[1] + k) % n_th for k in range(best[0]))
    return [f for i in range(n_th) if i not in drop for f in faces[i * n_t:(i + 1) * n_t]] + faces[n_th * n_t:]


MS_RING = 30720.0


def ground_sight(height, step=128.0):
    """visible(x, y, z) -> bool array: is the point seen from any ground viewpoint (eye 64 over the ground on a ring 300 inside the
    play space and a 1600-unit grid) over the terrain (the main map's low ground inside the terrain edge, the skybox ring outside)?"""
    from scipy.ndimage import map_coordinates
    R = MS_RING + 512
    xs = np.arange(-R, R + 1, step); X, Y = np.meshgrid(xs, xs, indexing='ij')
    inside = (np.abs(X) <= HALF[0]) & (np.abs(Y) <= HALF[1])
    G = np.where(inside, LY.ground_low(np.clip(X, -HALF[0], HALF[0]), np.clip(Y, -HALF[1], HALF[1])), height(X, Y))
    vx = []
    for t in np.linspace(0, 1, 40, endpoint=False):
        for sx, sy in ((1, 1), (-1, -1)):
            vx.append((sx * (LY.MAP_X - 300) * (1 - 2 * t), sy * (LY.MAP_Y - 300)))
            vx.append((sx * (LY.MAP_X - 300), sy * (LY.MAP_Y - 300) * (1 - 2 * t)))
    gx = np.arange(-LY.MAP_X + 800, LY.MAP_X, 1600); gy = np.arange(-LY.MAP_Y + 800, LY.MAP_Y, 1600)
    vx += [(a, b) for a in gx for b in gy]
    V = np.array(vx, float)
    V = np.column_stack([V, LY.ground_low(V[:, 0], V[:, 1]) + 64.0])
    def g(px, py): return map_coordinates(G, [(px + R) / step, (py + R) / step], order=1, mode='nearest')
    def visible(x, y, z):
        x = np.atleast_1d(x); y = np.atleast_1d(y); z = np.atleast_1d(z)
        out = np.zeros(len(x), bool)
        t = np.linspace(0.04, 0.98, 48)[None, :]
        for i in range(len(x)):
            px = V[:, 0:1] + (x[i] - V[:, 0:1]) * t; py = V[:, 1:2] + (y[i] - V[:, 1:2]) * t; pz = V[:, 2:3] + (z[i] - V[:, 2:3]) * t
            out[i] = (pz > g(px.ravel(), py.ravel()).reshape(px.shape) + 8).all(1).any()
        return out
    return visible


def face_play(x, y):
    """yaw (deg) that turns a card's face (local +y; the card is the model's x-z plane) towards the nearest point of the play space"""
    qx = np.clip(x, -LY.MAP_X, LY.MAP_X); qy = np.clip(y, -LY.MAP_Y, LY.MAP_Y)
    return math.degrees(math.atan2(-(qx - x), qy - y))


def prop(model, x, y, z, yaw, sc, color='255 255 255'):
    t = ent('prop_static', (x / K, y / K, z / K), (0, yaw, 0), group=GROUP, model=model, rendercolor=color,
            skin='default', solid='0', bakelighting='1', disableshadows='1', lodlevel='-1', baketoworld='0', rendertocubemaps='1')
    t.attr('scales')[2] = (sc, sc, sc)


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    src = args[0] if len(args) > 0 else os.path.join(HERE, '..', 'out', 'sky_template.vmap')
    out = args[1] if len(args) > 1 else os.path.join(HERE, '..', 'out', 'addon', 'maps', 'mg_monsoon_3dskybox.vmap')
    if not os.path.exists(src):
        if not os.path.exists(TRENCH_SKY): sys.exit('no sky template: %s (and %s is not there to copy)' % (src, TRENCH_SKY))
        shutil.copyfile(TRENCH_SKY, src); print('sky: template copied from', TRENCH_SKY)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    d = dmx.DMX.load(src)
    vmaplib.init(d, os.path.dirname(out))
    kids = d.root.get('world').attr('children')
    before = len(kids[2])
    kids[2] = [c for c in kids[2] if c.get('customVisGroup', '') not in OLD_GROUPS]
    kept = [c for c in kids[2] if c.get('customVisGroup', '') != GROUP]
    print('sky: template had %d nodes, %d dropped (%s), %d kept: %s' % (before, before - len(kids[2]), ', '.join(OLD_GROUPS), len(kept),
          ', '.join(sorted(set((c.get('entity_properties').get('classname') if c.type == 'CMapEntity' else c.type) for c in kept)))))
    nl = retune_lights(d)
    w = d.root.get('world').attr('mapUsageType')
    assert w is not None and w[2] == 'skybox', 'the template is not a skybox map (mapUsageType %s)' % (w and w[2])
    assert any(c.type == 'CMapEntity' and c.get('entity_properties').get('classname') == 'sky_camera' for c in kept), 'no sky_camera in the template'

    nm, _, _ = MS.build(d, HALF, LY.ground_low, ring=CONF.get('ring', 30720.0), material=GROUND, trees=[], near_trees=[], seed=SEED,
                        group=GROUP, noise_seed=NS, plain=True)
    height, edge_dist = MS.make_height(HALF, LY.ground_low, seed=41 + NS, lerp=True)

    def shell_dist(x, y): return max(abs(x) - SHELL[0], abs(y) - SHELL[1])

    # ---- trees. Front band: full banyans on a 560 grid. Behind and between them: tree cards facing the play space,
    # small banyans where a ground player sees their crown, palms; nothing past CARD_E1. Clearings: the same fbm mask for all.
    global MS_RING
    ring = MS_RING = CONF.get('ring', 30720.0)
    def clearing(x, y): return fbm(x / 3000.0, y / 3000.0, 9.1, 2, seed=45 + NS) < -0.38
    def gz(x, y): return float(height(np.array([x]), np.array([y]))[0])
    def spots(step, e0, e1, rs, jit):
        for gx in np.arange(-ring + 300, ring - 300, step):
            for gy in np.arange(-ring + 300, ring - 300, step):
                x = gx + rs.uniform(-jit, jit); y = gy + rs.uniform(-jit, jit); r = rs.rand(4)
                e = shell_dist(x, y)
                if e0 <= e < e1 and not clearing(x, y): yield x, y, e, r
    used = set(); count = {}
    def put(kind, model, x, y, z, yaw, sc, color='255 255 255'):
        prop(model, x, y, z, yaw, sc, color); used.add(model); count[kind] = count.get(kind, 0) + 1
    wn = np.cumsum(NEAR_W) / sum(NEAR_W); wc = np.cumsum(CARDS_W) / sum(CARDS_W)
    for x, y, e, r in spots(FRONT_STEP, 90.0, FRONT_E, np.random.RandomState(SEED), 200):
        if r[0] > 0.92: continue
        put('banyan front', NEAR[int(np.searchsorted(wn, r[1] * 0.9999))], x, y, gz(x, y) - 10, r[2] * 360, (0.9 + 0.45 * r[3]) / K)
    cand = []
    for x, y, e, r in spots(CARD_STEP, CARD_E0, CARD_E1, np.random.RandomState(SEED + 11), 120):
        if r[0] <= next(dn for e1, dn in CARD_DENS if e < e1): cand.append((x, y, e, r))
    # small banyans: a share of the middle band's spots, kept only where the crown (ground + 400) shows over the hills from the ground
    mid = [i for i, (x, y, e, r) in enumerate(cand) if FRONT_E <= e < MID_E and r[1] < SMALL_SHARE]
    small = set()
    if mid:
        sight = ground_sight(height)
        vis = sight(np.array([cand[i][0] for i in mid]), np.array([cand[i][1] for i in mid]), np.array([gz(cand[i][0], cand[i][1]) + 400.0 for i in mid]))
        small = {i for i, v in zip(mid, vis) if v}
    hidden = len(mid) - len(small)
    for i, (x, y, e, r) in enumerate(cand):
        z = gz(x, y) - 12
        if i in small:
            put('banyan small', SMALL[int(r[2] * 2) % 2], x, y, z, r[3] * 360, (0.95 + 0.4 * r[2]) / K)
        elif e >= 2200 and r[1] > 0.88:
            put('palm', PALMS[int(r[2] * 2) % 2], x, y, z + 4, r[3] * 360, 0.62 + 0.25 * r[2])
        else:
            k = int(np.searchsorted(wc, r[2] * 0.9999)); lo, hi = CARD_HT_MID if e < MID_E else CARD_HT_FAR
            u = (r[1] * 7.31 + r[3] * 3.7) % 1.0                  # decorrelated from the share / palm draws on r[1]
            put('card', CARDS[k], x, y, z, face_play(x, y) + (r[3] - 0.5) * 40, (lo + (hi - lo) * u) / CARD_H[k] / K, CARD_TINT)
    nt = sum(count.values())
    print('sky trees: %s; %d small-banyan spots hidden from the ground got a card' % (', '.join('%s %d' % kv for kv in count.items()), hidden))

    # ---- karst on the horizon: groups of towers in the hills, taller with distance (they read as silhouettes in the haze)
    nk = 0; ktris = 0; krng = np.random.RandomState(SEED + 7)
    for g in range(11):
        ang = 2 * math.pi * (g + krng.uniform(-0.3, 0.3)) / 11
        dist = krng.uniform(1800, 11000)
        cx = (SHELL[0] + dist) * math.cos(ang) * 1.05; cy = (SHELL[1] + dist) * math.sin(ang) * 1.05
        for k in range(krng.randint(2, 5)):
            x = cx + krng.uniform(-1500, 1500); y = cy + krng.uniform(-1500, 1500)
            if shell_dist(x, y) < 900: continue
            r = krng.uniform(380, 760) * (1 + dist / 16000.0); h = krng.uniform(1100, 2300) * (1 + dist / 14000.0)
            z0 = float(height(np.array([x]), np.array([y]))[0]) - 160.0
            ktris += karst(x, y, r, h, 100 + nk, z0); nk += 1

    nmesh = MS.plain_save(d, out, GROUP, used)
    info = dict(out=os.path.abspath(out), terrain_meshes=nm, karst_towers=nk, karst_triangles=ktris, trees=nt, tree_counts=count,
                small_banyan_spots_hidden=hidden, models=sorted(used), group=GROUP,
                half=HALF, shell=SHELL, lights_retuned=nl, mb=round(os.path.getsize(out) / 1e6, 1))
    print('skybox: %d terrain sheets, %d karst towers (%d triangles), %d trees, %d meshes in the map -> %s (%.1f MB)' % (nm, nk, ktris, nt, nmesh, out, info['mb']))
    if '--no-check' not in argv:
        r = subprocess.run([sys.executable, os.path.join(HERE, 'check_mesh.py'), out], capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())
        info['check_mesh'] = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-300:]
        if ' 0 bad' not in info['check_mesh']:
            json.dump(info, open(os.path.join(HERE, '..', 'out', 'sky.json'), 'w'), indent=1); sys.exit('skybox: check_mesh failed')
    json.dump(info, open(os.path.join(HERE, '..', 'out', 'sky.json'), 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
