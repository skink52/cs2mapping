"""Procedural TILING materials for mg_monsoon's props (playtest 1, finding 16), where CS2 has no stock material that fits.
Each is generated once and shared by every prop that maps a chart material onto it (a stock.py key plus a stock.GENERATORS hook,
so build_prop writes it on first use in a run), at a fixed texel density:

  mv_bamboo                             1024 px over 32 u (0.8 m): 32 px/u = 1280 px/m. u round the culm, v along it; two
                                        internodes per tile. Posts, poles, fences, stakes.
  mv_sandstone_lichen / _moss / _dark / _laterite   2048 px over 128 u (3.2 m): 16 px/u = 640 px/m, box-projected. Khmer temple blocks (the
                                        joints are real geometry, so the texture has none).

Noise: periodic fractal value noise (tnoise), so every texture tiles in both directions. Normals from height with
bake.height_to_normal (np.roll: periodic), OpenGL +Y up like the baked atlases. AI-generated (Claude) for skink52.
"""
import os
import numpy as np
from PIL import Image
import stock, bake, modelio

PREFIX = stock.PREFIX
REL = 'materials/models/%s/tile' % PREFIX


def tnoise(res, fu, fv, octaves, seed, gain=0.5):
    """periodic fractal value noise (res x res): octave k is a random (fv*2^k, fu*2^k) lattice upsampled cubically with wrap-around,
    so it tiles in both directions; fu != fv stretches it (fv small = streaks running down the image). ~zero mean, unit std"""
    from scipy import ndimage
    rng = np.random.RandomState(seed)
    out = np.zeros((res, res)); amp = 1.0
    for k in range(octaves):
        gu, gv = max(1, int(fu * 2 ** k)), max(1, int(fv * 2 ** k))
        if gu > res or gv > res: break
        g = rng.rand(gv, gu)
        # cubic upsampling with wrap-around (grid_mode: pixel-edge aligned, so the result tiles exactly)
        big = ndimage.zoom(g, (res / gv, res / gu), order=3, mode='grid-wrap', grid_mode=True)
        out += amp * big[:res, :res]
        amp *= gain
    out -= out.mean()
    return out / (out.std() + 1e-9)


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def _save(name, color, rough, height, ao, d, strength=1.0, comment=''):
    def outdir_fn(outdir):
        dd = os.path.join(outdir, REL); os.makedirs(dd, exist_ok=True)
        nrm = bake.height_to_normal(height, d, strength)
        tex = {}
        for k, arr in (('color', color), ('normal', nrm * 0.5 + 0.5), ('rough', rough), ('ao', ao)):
            Image.fromarray(modelio.to8(arr)).save(os.path.join(dd, '%s_%s.png' % (name, k)), optimize=True)
            tex[k] = '%s/%s_%s.png' % (REL, name, k)
        modelio.write_vmat(outdir, '%s/%s.vmat' % (REL, name), tex, comment='mg_monsoon %s (procedural tiling material, AI-generated) %s' % (name, comment))
    return outdir_fn


def bamboo(res=1024, S=32.0, seed=11):
    """weathered dry bamboo culm: straw-grey to tan with a faint green-yellow cast, fine lengthwise fibres, two nodes per tile
    (raised ring, a dark sheath scar just above it, a paler band), grey lichen flecks, grime in the grooves"""
    y, x = np.mgrid[0:res, 0:res] / float(res)
    U, V = x, y                                                   # U round the culm, V along it (image rows)
    fib = tnoise(res, 64, 1, 4, seed + 1)                         # fibres: fine across, long along
    fib2 = tnoise(res, 128, 4, 3, seed + 2)
    blot = tnoise(res, 3, 2, 5, seed + 3)
    fleck = tnoise(res, 48, 48, 3, seed + 4)
    vn = (V * 2 + 0.02 * np.sin(2 * np.pi * U)) % 1.0
    dn = np.abs(vn - 0.5) * 2 * (S / 2)                           # distance to the node line in units
    ridge = np.exp(-(dn / 0.9) ** 2)
    groove = np.exp(-((dn - 1.4) / 0.45) ** 2) * (vn > 0.5)       # scar on one side of the ring only
    band = np.exp(-(dn / 2.0) ** 2)
    tan = np.array([0.62, 0.55, 0.38]); grey = np.array([0.52, 0.50, 0.44]); green = np.array([0.48, 0.50, 0.32])
    t1 = ss(-1.2, 1.2, blot)[..., None]
    col = grey * (1 - t1) + tan * t1
    col = col * (1 - 0.15 * ss(0.3, 1.8, -blot))[..., None] + green * 0.12 * ss(0.5, 2.0, blot)[..., None]
    col = col * (0.94 + 0.05 * fib[..., None] + 0.02 * fib2[..., None])
    col = col * (1 + 0.08 * band[..., None]) * (1 - 0.4 * groove[..., None]) * (1 - 0.1 * ridge[..., None])
    lichen = ss(1.9, 2.6, fleck + 0.3 * blot)
    col = col * (1 - 0.35 * lichen[..., None]) + np.array([0.62, 0.63, 0.58]) * 0.35 * lichen[..., None]
    col = np.clip(col, 0, 1)
    h = 0.05 * fib + 0.02 * fib2 + 0.5 * ridge - 0.3 * groove + 0.04 * lichen
    rough = np.clip(0.50 + 0.10 * ss(0, 2, -blot) + 0.25 * groove + 0.2 * lichen - 0.03 * fib, 0, 1)
    ao = np.clip(1 - 0.35 * groove - 0.06 * ss(0, 2, -fib), 0, 1)
    return _save('mv_bamboo', col, rough, h, ao, d=res / S, strength=1.0, comment='(culm, %d px over %g u)' % (res, S))


def sandstone(variant='lichen', res=2048, S=128.0, seed=21):
    """weathered Angkor sandstone surface without joints (the blocks are real geometry): grey-beige stone with a fine grain and
    faint bedding, eroded hollows, pores, patches of black lichen that run down in rain stains (image v = down on walls in box
    mode), white crustose lichen rosettes; 'moss' adds olive moss in the hollows, 'dark' is older, more stained stone"""
    grain = tnoise(res, 256, 256, 3, seed + 1)
    mid = tnoise(res, 8, 8, 6, seed + 2)
    big = tnoise(res, 2, 2, 4, seed + 3)
    bed = tnoise(res, 1, 24, 3, seed + 4)                        # bedding: bands across v
    drip = tnoise(res, 24, 2, 5, seed + 5)                       # long streaks down v
    pits = tnoise(res, 512, 512, 1, seed + 6)
    rose = tnoise(res, 32, 32, 3, seed + 7)
    patch = tnoise(res, 4, 4, 5, seed + 8)
    base = {'lichen': np.array([0.52, 0.50, 0.44]), 'moss': np.array([0.50, 0.49, 0.42]), 'dark': np.array([0.40, 0.40, 0.35]),
            'laterite': np.array([0.52, 0.36, 0.27])}[variant]
    warm = np.array([0.56, 0.49, 0.41]); cool = np.array([0.45, 0.47, 0.43])
    tw = ss(-1.5, 1.5, big)[..., None]
    col = cool * (1 - tw) + warm * tw
    col = (0.5 * col + 0.5 * base) if variant != 'laterite' else base * (0.9 + 0.2 * tw)
    col = col * (0.92 + 0.07 * grain[..., None] + 0.06 * mid[..., None] + 0.03 * bed[..., None])
    # black lichen: patches, and stains running down from them
    thr = {'lichen': 0.6, 'moss': 0.9, 'dark': 0.2, 'laterite': 0.8}[variant]
    black = np.maximum(ss(thr, thr + 0.8, patch + 0.35 * mid), 0.7 * ss(thr + 0.6, thr + 1.6, drip + 0.5 * patch))
    col = col * (1 - 0.42 * black[..., None])
    pit = ss(2.0, 2.8, pits) * ss(-0.5, 0.8, mid)
    if variant == 'laterite':      # laterite is vesicular: dense small holes everywhere
        pit = np.maximum(pit, ss(0.9, 1.6, tnoise(res, 160, 160, 2, seed + 9)))
    col = col * (1 - 0.4 * pit[..., None])
    white = ss(1.7, 2.3, rose + 0.3 * mid) * (1 - black)
    col = col * (1 - 0.5 * white[..., None]) + np.array([0.80, 0.80, 0.74]) * 0.5 * white[..., None]
    moss = np.zeros((res, res))
    if variant == 'moss':
        moss = ss(-0.2, 0.9, -mid * 0.7 - big * 0.3 + 0.35 * patch) * (0.75 + 0.25 * ss(-1, 1, grain))
        mcol = np.array([0.29, 0.33, 0.19]) * (0.85 + 0.15 * grain[..., None])
        col = col * (1 - moss[..., None]) + mcol * moss[..., None]
    col = np.clip(col, 0, 1)
    h = 0.09 * grain + 0.45 * mid + 0.3 * big + 0.06 * bed - 0.5 * pit + 0.25 * moss + 0.05 * white
    rough = np.clip(0.80 + 0.05 * grain + 0.08 * moss - 0.05 * black + 0.05 * pit, 0, 1)
    ao = np.clip(1 - 0.35 * pit - 0.18 * ss(0.0, 1.5, -mid), 0, 1)
    return _save('mv_sandstone_%s' % variant, col, rough, h, ao, d=res / S, strength=0.6, comment='(Khmer sandstone, %d px over %g u)' % (res, S))


def register():
    """add the generated tiles to stock.STOCK / stock.GENERATORS (idempotent)"""
    if 'mv_bamboo' not in stock.STOCK:
        vm = '%s/mv_bamboo.vmat' % REL
        stock.STOCK['mv_bamboo'] = dict(vmat=vm, mode='cyl', S=32.0)
        stock.GENERATORS[vm] = lambda outdir: bamboo()(outdir)
    for v in ('lichen', 'moss', 'dark', 'laterite'):
        key = 'mv_sandstone_' + v
        if key not in stock.STOCK:
            vm = '%s/%s.vmat' % (REL, key)
            stock.STOCK[key] = dict(vmat=vm, mode='box', S=128.0)
            stock.GENERATORS[vm] = (lambda vv: (lambda outdir: sandstone(vv)(outdir)))(v)


register()
