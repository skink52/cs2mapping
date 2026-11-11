"""3D skybox map for mg_monsoon: the valley sides carried on past the terrain edge into jungle hills and a far ridge (make_skybox.py,
"plain" mode), Aztec banyans on the near slopes, skybox palms and small banyans further out, and limestone towers on the horizon
(the same karst as inside the map), all at 1/16 scale around the sky_camera.

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
FAR = [AZ + 'hr_aztec_banyan_small_01.vmdl', AZ + 'hr_aztec_banyan_small_02.vmdl',
       'models/props/de_dust/hr_dust/foliage/palm_tree_skybox_01.vmdl', 'models/props/de_dust/hr_dust/foliage/palm_tree_skybox_02.vmdl']
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
    pa = np.zeros((len(verts), 4)); pa[:, 0] = moss; pa[:, 2] = 0.35
    ti = np.ones((len(verts), 4)); ti[:, :3] = (0.62 + 0.20 * moss)[:, None]              # hazy and dark: silhouettes
    m = vmesh.polymesh_open(verts / K, faces, [ROCK] * len(faces), scale=0.5 / K, paint=pa, tint=ti)
    vmesh.mesh_node(m, GROUP, bake=True, shadows=True, smoothing=70.0)


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

    # ---- trees: banyans crowd the first slopes, thinning into palms and small banyans, none on the far ridge
    rng = np.random.RandomState(SEED)
    used = set(); nt = 0; ring = CONF.get('ring', 30720.0)
    for gx in np.arange(-ring + 300, ring - 300, 360.0):
        for gy in np.arange(-ring + 300, ring - 300, 360.0):
            x = gx + rng.uniform(-150, 150); y = gy + rng.uniform(-150, 150)
            e = shell_dist(x, y)
            r1, r2, r3 = rng.rand(), rng.rand(), rng.rand()
            if e < 90 or e > 9000: continue
            dens = 0.92 if e < 2200 else (0.42 if e < 5000 else 0.16)
            if r1 > dens or fbm(x / 3000.0, y / 3000.0, 9.1, 2, seed=45 + NS) < -0.38: continue
            z = float(height(np.array([x]), np.array([y]))[0]) - 10
            near = e < 2200 or (e < 3800 and r2 < 0.35)
            pool = NEAR if near else FAR
            model = pool[int(r3 * len(pool)) % len(pool)]
            sc = rng.uniform(0.9, 1.35) / K
            t = ent('prop_static', (x / K, y / K, z / K), (0, rng.uniform(0, 360), 0), group=GROUP, model=model, rendercolor='255 255 255',
                    skin='default', solid='0', bakelighting='1', disableshadows='1', lodlevel='-1', baketoworld='0', rendertocubemaps='1')
            t.attr('scales')[2] = (sc, sc, sc)
            used.add(model); nt += 1

    # ---- karst on the horizon: groups of towers in the hills, taller with distance (they read as silhouettes in the haze)
    nk = 0; krng = np.random.RandomState(SEED + 7)
    for g in range(11):
        ang = 2 * math.pi * (g + krng.uniform(-0.3, 0.3)) / 11
        dist = krng.uniform(1800, 11000)
        cx = (SHELL[0] + dist) * math.cos(ang) * 1.05; cy = (SHELL[1] + dist) * math.sin(ang) * 1.05
        for k in range(krng.randint(2, 5)):
            x = cx + krng.uniform(-1500, 1500); y = cy + krng.uniform(-1500, 1500)
            if shell_dist(x, y) < 900: continue
            r = krng.uniform(380, 760) * (1 + dist / 16000.0); h = krng.uniform(1100, 2300) * (1 + dist / 14000.0)
            z0 = float(height(np.array([x]), np.array([y]))[0]) - 160.0
            karst(x, y, r, h, 100 + nk, z0); nk += 1

    nmesh = MS.plain_save(d, out, GROUP, used)
    info = dict(out=os.path.abspath(out), terrain_meshes=nm, karst_towers=nk, trees=nt, models=sorted(used), group=GROUP,
                half=HALF, shell=SHELL, lights_retuned=nl, mb=round(os.path.getsize(out) / 1e6, 1))
    print('skybox: %d terrain sheets, %d karst towers, %d trees, %d meshes in the map -> %s (%.1f MB)' % (nm, nk, nt, nmesh, out, info['mb']))
    if '--no-check' not in argv:
        r = subprocess.run([sys.executable, os.path.join(HERE, 'check_mesh.py'), out], capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())
        info['check_mesh'] = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-300:]
        if ' 0 bad' not in info['check_mesh']:
            json.dump(info, open(os.path.join(HERE, '..', 'out', 'sky.json'), 'w'), indent=1); sys.exit('skybox: check_mesh failed')
    json.dump(info, open(os.path.join(HERE, '..', 'out', 'sky.json'), 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
