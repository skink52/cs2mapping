"""Procedural weathered steel and brass textures (value-noise fbm + scratches) for scopes and fittings.

python3 weather.py   writes wsteel_*/wbrass_* colour/rough/metal PNGs to /tmp (steel(out=...) / brass(out=...) for another folder)"""
import numpy as np
from PIL import Image
def vnoise(n, cells, rng):
    g = rng.random((cells+1, cells+1)); 
    return np.asarray(Image.fromarray((g*255).astype(np.uint8)).resize((n, n), Image.BICUBIC)).astype(float)/255.0
def fbm(n, rng, octaves=(4, 8, 16, 32, 64), weights=(0.4, 0.25, 0.15, 0.12, 0.08)):
    return sum(w*vnoise(n, c, rng) for c, w in zip(octaves, weights)) / sum(weights)
def scratches(n, rng, count, length=(20, 120), strength=0.25):
    im = np.zeros((n, n))
    for _ in range(count):
        x, y = rng.random(2)*n; a = rng.random()*np.pi; L = rng.integers(*length)
        for t in range(L):
            xi, yi = int(x + t*np.cos(a)) % n, int(y + t*np.sin(a)) % n; im[yi, xi] = strength*(0.5+0.5*rng.random())
    return im
def steel(n=1024, seed=3, out='/tmp'):
    rng = np.random.default_rng(seed)
    m = fbm(n, rng); grain = vnoise(n, 256, rng); sc = scratches(n, rng, 160)
    rust = np.clip((fbm(n, rng, (3, 6, 12), (0.5, 0.3, 0.2)) - 0.62) * 6, 0, 1) * (0.5 + 0.5*vnoise(n, 128, rng))
    base = np.array([44, 46, 50], float)[None, None, :]
    col = base * (0.75 + 0.5*m[..., None]) + (grain[..., None]-0.5)*14 + sc[..., None]*110
    rustc = np.array([112, 68, 38], float)[None, None, :] * (0.8 + 0.4*grain[..., None])
    col = col*(1-rust[..., None]) + rustc*rust[..., None]
    rough = np.clip(0.38 + 0.25*m + 0.12*(grain-0.5) + 0.45*rust + sc*0.5, 0.2, 0.95)
    metal = np.clip(1.0 - 0.9*rust - sc*0.3, 0, 1)
    Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)).save(f'{out}/wsteel_color.png')
    Image.fromarray((rough*255).astype(np.uint8)).save(f'{out}/wsteel_rough.png'); Image.fromarray((metal*255).astype(np.uint8)).save(f'{out}/wsteel_metal.png')
def brass(n=1024, seed=7, out='/tmp'):
    rng = np.random.default_rng(seed)
    m = fbm(n, rng); grain = vnoise(n, 256, rng); sc = scratches(n, rng, 60, strength=0.15)
    tarn = np.clip((fbm(n, rng, (3, 6, 12, 24), (0.4, 0.3, 0.2, 0.1)) - 0.5) * 3, 0, 1)
    bright = np.array([178, 142, 72], float)[None, None, :]; dark = np.array([96, 72, 40], float)[None, None, :]
    col = bright*(1-tarn[..., None]) + dark*tarn[..., None]; col = col*(0.85 + 0.3*m[..., None]) + (grain[..., None]-0.5)*10 + sc[..., None]*60
    rough = np.clip(0.35 + 0.2*m + 0.35*tarn + 0.1*(grain-0.5), 0.2, 0.9); metal = np.clip(1.0 - 0.3*tarn, 0, 1)
    Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)).save(f'{out}/wbrass_color.png')
    Image.fromarray((rough*255).astype(np.uint8)).save(f'{out}/wbrass_rough.png'); Image.fromarray((metal*255).astype(np.uint8)).save(f'{out}/wbrass_metal.png')
if __name__ == '__main__': steel(); brass()
