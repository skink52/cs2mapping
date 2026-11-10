"""IRONFRAME death debris: six armour-chunk props (models/ifr/fx/gib_N), one dark burnt-metal material with a glowing hot edge.
All are ~60-110 u long (the script scales them by mech class), origin at the centre, built with create/geo.py, box-projected UVs
(each face is one UV tile, so the hot-edge texture glows around every face border). Recorded in out/addon/_gen/models.json#fx
as gib_1..gib_6 (other fx entries are kept). usage: python -I tools/gibs.py [--no-compile]
  gib_1 flat armour panel   gib_2 bent panel (two plates)   gib_3 limb segment (tube)   gib_4 thruster bell   gib_5 gear / joint   gib_6 armour wedge"""
import json, math, os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fx as FX                                              # noqa: E402  (sets up paths, geo, modelio, frames)
geo, FR, OUT, PROJ = FX.geo, FX.FR, FX.OUT, FX.PROJ
REL_M, REL_T = 'models/ifr/fx', 'materials/ifr/fx'


def gib_material():
    d = os.path.join(OUT, REL_T); os.makedirs(d, exist_ok=True)
    rng = np.random.default_rng(52); n = 128
    yy, xx = np.mgrid[0:n, 0:n] / (n - 1.0)
    edge = np.minimum.reduce([xx, yy, 1 - xx, 1 - yy])                      # 0 at the tile border
    glow = np.clip(1 - edge / 0.09, 0, 1) ** 2
    noise = np.asarray(Image.fromarray(rng.random((16, 16)).astype(np.float32), 'F').resize((n, n), Image.BICUBIC))
    fine = rng.random((n, n)).astype(np.float32)
    base = 0.07 + 0.10 * noise + 0.04 * fine                                # burnt, scratched dark metal
    scratch = (rng.random((n, n)) > 0.992).astype(np.float32) * 0.25
    rgb = np.stack([base + scratch, base * 0.95 + scratch, base * 0.9 + scratch], -1)
    hot = glow * (0.55 + 0.45 * noise)
    rgb = rgb * (1 - hot[..., None]) + hot[..., None] * np.array([1.0, 0.42, 0.08])
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(os.path.join(d, 'gib_color.png'))
    Image.fromarray((np.clip(glow * (0.6 + 0.4 * noise), 0, 1) * 255).astype(np.uint8), 'L').save(os.path.join(d, 'gib_illum.png'))
    Image.new('L', (4, 4), 190).save(os.path.join(d, 'gib_rough.png'))
    lines = ['// IRONFRAME mech debris: burnt metal, hot edges (generated)', 'Layer0', '{', '\tshader "csgo_complex.vfx"', '\tF_SPECULAR 1',
             '\tTextureColor "%s/gib_color.png"' % REL_T, '\tTextureNormal "materials/default/default_normal.tga"', '\tTextureRoughness "%s/gib_rough.png"' % REL_T,
             '\tg_flMetalness "0.350"', '\tF_SELF_ILLUM 1', '\tTextureSelfIllumMask "%s/gib_illum.png"' % REL_T,
             '\tg_flSelfIllumScale "1.000"', '\tg_flSelfIllumBrightness "3.000"', '\tg_flSelfIllumAlbedoFactor "1.000"', '}']
    open(os.path.join(d, 'gib.vmat'), 'w', newline='\n').write('\n'.join(lines) + '\n')
    return '%s/gib.vmat' % REL_T


def boxuv(m, scale=None):
    """per-vertex box projection: each face of the shape maps to one 0..1 tile (so the hot edge follows the face outline)"""
    lo, hi = m.V.min(0), m.V.max(0); ext = np.maximum(hi - lo, 1e-3); uv = np.zeros((len(m.V), 2))
    for i, (v, n) in enumerate(zip(m.V, m.N)):
        a = int(np.argmax(np.abs(n))); ax = [(1, 2), (0, 2), (0, 1)][a]
        uv[i] = ((v[ax[0]] - lo[ax[0]]) / ext[ax[0]], 1 - (v[ax[1]] - lo[ax[1]]) / ext[ax[1]])
    return uv


def shape(i):
    rbox, tube, lathe, merge = geo.rbox, geo.tube, geo.lathe, FX.merge
    if i == 1:                                                              # flat armour panel
        return rbox(104, 74, 7, r=2, seg=1, mat='m', jitter=None)
    if i == 2:                                                              # bent panel: two plates at an angle
        a = rbox(80, 66, 6, r=1.5, seg=1, mat='m', center=(0, -20, 0)); b = rbox(80, 52, 6, r=1.5, seg=1, mat='m')
        R = geo.rot('x', 38.0); b.V = b.V @ R.T + np.array([0, 14, 10]); b.N = b.N @ R.T
        return merge([a, b])
    if i == 3:                                                              # limb segment, sheared off at both ends
        return tube([(-48, 0, 0), (0, 3, 2), (48, 0, -2)], [17, 20, 15], sides=10, mat='m', rnoise=lambda th, s: 1 + 0.06 * np.sin(th * 3 + s * 0.1))
    if i == 4:                                                              # thruster bell
        return lathe([(11, -34), (17, -30), (24, -4), (36, 26), (38, 34), (31, 34), (28, 22), (14, -10), (8, -28)], sides=14, mat='m')
    if i == 5:                                                              # gear / joint
        ring = tube([(0, 0, -7), (0, 0, 7)], [30, 30], sides=12, mat='m'); hub = lathe([(0.01, -12), (11, -12), (11, 12), (0.01, 12)], sides=10, mat='m')
        teeth = []
        for k in range(8):
            t = rbox(12, 11, 13, r=0.5, seg=1, mat='m'); a = 0
            t.V = t.V + np.array([33, 0, 0]); R = geo.rot("z", 45.0 * k); t.V = t.V @ R.T; t.N = t.N @ R.T; teeth.append(t)
        return merge([ring, hub] + teeth)
    w = rbox(86, 52, 34, r=2, seg=1, mat='m')                               # 6: armour wedge, one corner cut off by squashing the top
    top = w.V[:, 2] > 0
    w.V[top, 0] *= 0.35; w.V[top, 1] *= 0.8
    w.recompute_normals(angle=60) if hasattr(w, 'recompute_normals') else None
    return w


def main():
    vmat = gib_material(); made = {}
    for i in range(1, 7):
        m = shape(i)
        m.V = m.V - (m.V.min(0) + m.V.max(0)) / 2                             # centred
        made['gib_%d' % i] = FX.write_model(REL_M + '/gib_%d' % i, 'gib_%d' % i, m, vmat, uv=boxuv(m))
        print('gib_%d %d tris %s' % (i, len(m.F), np.round(m.V.max(0) - m.V.min(0))))
    ok = {k: True for k in made}
    if '--no-compile' not in sys.argv:
        work = json.load(open(os.path.join(PROJ, 'data', 'frames.json'), encoding='utf-8'))['paths']['work']
        res = FR.compile_models(OUT, [REL_M + '/gib_%d' % i for i in range(1, 7)] + [REL_T], list(made.values()), os.path.join(work, 'logs', 'rc_gibs.log'))
        for k, v in made.items():
            ok[k] = res[v][0]; print('compile %-6s %s %.1fs %s' % (k, 'OK' if res[v][0] else 'FAIL', res[v][1], '; '.join(res[v][2])[:140]))
    mpath = os.path.join(OUT, '_gen', 'models.json'); data = json.load(open(mpath, encoding='utf-8'))
    data.setdefault('fx', {}).update({k: v for k, v in made.items() if ok[k]})
    json.dump(data, open(mpath, 'w', encoding='utf-8'), indent=1)
    print('models.json#fx gib entries:', sorted(k for k in data['fx'] if k.startswith('gib_')))
    return 0 if all(ok.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
