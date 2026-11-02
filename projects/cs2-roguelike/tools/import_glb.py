"""Tripo (or any) GLB -> a CS2 static prop for the guardian pool: models/nt/enemies/<name>/<name>.vmdl.

usage: python tools/import_glb.py <model.glb> <name> [--kind enemies|props] [--length L] [--yaw deg] [--glow cyan|magenta|amber] [--credit text]
  --length: longest horizontal side in units (default 64). The model's origin is the centre of its footprint at its lowest point.

Output goes to ref/models_src/ (not in git: Tripo output is binary); tools/build_all.sh copies it into out/addon, and tools/vmap.py's
POOL_MODELS must list the vmdl so the map compiles it (the cache room holds one of each pool model). Prints the bounds to put in
ENEMIES (src/core/20_classes.js): radius ~ half the horizontal extent, height = z extent.
"""
import sys, os, re, json, subprocess, argparse
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
CREATE = os.environ.get('CREATE', os.path.join(ROOT, '..', '..', 'create'))
ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('name')
ap.add_argument('--kind', default='enemies', help='enemies (default) or props: the models/nt/<kind>/<name> folder')
ap.add_argument('--credit', default='generated with Tripo3D for Nanite Temple')
ap.add_argument('--glow', default='', help="hue of the baked-in glow to turn into self-illum: cyan | magenta | amber | none")
ap.add_argument('--length', type=float, default=64); ap.add_argument('--yaw', type=float, default=0); ap.add_argument('--maxtex', type=int, default=2048)
A = ap.parse_args()
out = os.path.join(ROOT, 'ref', 'models_src'); os.makedirs(out, exist_ok=True)
sub = 'models/nt/%s/%s' % (A.kind, A.name)
cmd = [sys.executable, os.path.join(CREATE, 'glb2cs2_multi.py'), A.src, out, A.name, '--length', str(A.length), '--yaw', str(A.yaw),
       '--maxtex', str(A.maxtex), '--surface', 'concrete', '--sub', sub, '--credit', A.credit]
subprocess.check_call(cmd)
info = json.load(open(os.path.join(out, sub, A.name + '.json')))
mins, maxs = info['mins'], info['maxs']
print('model %s  footprint %.0f x %.0f  height %.0f  -> ENEMIES: radius %d, height %d' % (
    info['model'], maxs[0] - mins[0], maxs[1] - mins[1], maxs[2] - mins[2], round(max(maxs[0] - mins[0], maxs[1] - mins[1]) / 2), round(maxs[2] - mins[2])))

# Tripo bakes the glow into the albedo (no emissive channel): build a self-illum mask from the saturated pixels of that hue
if A.glow and A.glow != 'none':
    import numpy as np
    from PIL import Image
    HUE = {'cyan': 180, 'magenta': 300, 'amber': 40}[A.glow]
    tdir = os.path.join(out, 'materials', sub)
    for vm in [f for f in os.listdir(tdir) if f.endswith('.vmat')]:
        txt = open(os.path.join(tdir, vm)).read()
        m = re.search(r'TextureColor "materials/[^"]+/([^"/]+)"', txt)
        if not m: continue
        hsv = np.asarray(Image.open(os.path.join(tdir, m.group(1))).convert('RGB').convert('HSV')).astype(np.float32)
        h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
        dh = np.minimum(abs(h - HUE), 360 - abs(h - HUE))
        mask = np.clip((1 - dh / 30) * np.clip((s - 0.2) / 0.25, 0, 1) * np.clip((v - 0.3) / 0.25, 0, 1), 0, 1)   # thin lit channels: ~2% of texels on the guardian
        mf = m.group(1).replace('_c', '_e').replace('.png', '') + '.png'
        Image.fromarray((mask * 255).astype(np.uint8), 'L').save(os.path.join(tdir, mf), optimize=True)
        glow = ['\tF_SELF_ILLUM 1', '\tTextureSelfIllumMask "materials/%s/%s"' % (sub, mf), '\tg_flSelfIllumBrightness "6.000"',
                '\tg_flSelfIllumScale "1.000"', '\tg_flSelfIllumAlbedoFactor "1.000"', '\tg_vSelfIllumTint "[1.000000 1.000000 1.000000 0.000000]"', '}']
        txt = txt.rstrip()[:-1].rstrip() + '\n' + '\n'.join(glow) + '\n'
        open(os.path.join(tdir, vm), 'w', newline='\n').write(txt)
        print('glow mask %s: %.1f%% of texels lit' % (mf, 100 * (mask > 0.5).mean()))
