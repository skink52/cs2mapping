"""Vectorised 3D value/gradient noise, fBm, ridged and cellular noise (numpy)."""
import numpy as np

_rng = np.random.RandomState(9173)
PERM = np.concatenate([_rng.permutation(256)] * 2).astype(np.int32)
GRAD = _rng.normal(size=(256, 3)).astype(np.float32)
GRAD /= np.linalg.norm(GRAD, axis=1, keepdims=True)
VALS = _rng.uniform(-1, 1, 256).astype(np.float32)


def _h(ix, iy, iz):
    return PERM[(PERM[(PERM[ix & 255] + iy) & 255] + iz) & 255]


def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def perlin(x, y, z, seed=0):
    """gradient noise, roughly -1..1"""
    x = np.asarray(x, np.float32) + seed * 17.13
    y = np.asarray(y, np.float32) + seed * 31.71
    z = np.asarray(z, np.float32) + seed * 7.77
    xi = np.floor(x).astype(np.int32); yi = np.floor(y).astype(np.int32); zi = np.floor(z).astype(np.int32)
    xf = x - xi; yf = y - yi; zf = z - zi
    u = _fade(xf); v = _fade(yf); w = _fade(zf)
    out = 0
    acc = []
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                g = GRAD[_h(xi + dx, yi + dy, zi + dz)]
                acc.append(g[..., 0] * (xf - dx) + g[..., 1] * (yf - dy) + g[..., 2] * (zf - dz))
    x00 = acc[0] + u * (acc[1] - acc[0]); x10 = acc[2] + u * (acc[3] - acc[2])
    x01 = acc[4] + u * (acc[5] - acc[4]); x11 = acc[6] + u * (acc[7] - acc[6])
    y0 = x00 + v * (x10 - x00); y1 = x01 + v * (x11 - x01)
    return (y0 + w * (y1 - y0)) * 1.6


def fbm(x, y, z, octaves=5, lac=2.03, gain=0.5, seed=0):
    x = np.asarray(x, np.float32); y = np.asarray(y, np.float32); z = np.asarray(z, np.float32)
    s = 0; a = 1.0; f = 1.0; norm = 0
    for o in range(octaves):
        s = s + a * perlin(x * f, y * f, z * f, seed + o * 13)
        norm += a; a *= gain; f *= lac
    return s / norm


def ridged(x, y, z, octaves=4, seed=0):
    s = 0; a = 1.0; f = 1.0; norm = 0
    for o in range(octaves):
        n = 1 - np.abs(perlin(x * f, y * f, z * f, seed + o * 7))
        s = s + a * n * n; norm += a; a *= 0.5; f *= 2.1
    return s / norm


def cells(x, y, z, seed=0):
    """Worley F1 / F2 distance and cell id (3x3x3 search)."""
    x = np.asarray(x, np.float32); y = np.asarray(y, np.float32); z = np.asarray(z, np.float32)
    xi = np.floor(x).astype(np.int32); yi = np.floor(y).astype(np.int32); zi = np.floor(z).astype(np.int32)
    f1 = np.full(x.shape, 9.0, np.float32); f2 = np.full(x.shape, 9.0, np.float32); cid = np.zeros(x.shape, np.int32)
    for dz in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                cx, cy, cz = xi + dx, yi + dy, zi + dz
                h = _h(cx + seed * 3, cy, cz)
                px = cx + (PERM[h] / 255.0); py = cy + (PERM[h + 1] / 255.0); pz = cz + (PERM[h + 7] / 255.0)
                d = np.sqrt((px - x) ** 2 + (py - y) ** 2 + (pz - z) ** 2)
                closer = d < f1
                f2 = np.where(closer, f1, np.minimum(f2, d))
                cid = np.where(closer, h, cid)
                f1 = np.where(closer, d, f1)
    return f1, f2, cid


def hash01(i, seed=0):
    i = np.asarray(i, np.int64)
    v = (i * 2654435761 + seed * 40503 + 12345) & 0xffffffff
    v = (v ^ (v >> 15)) * 2246822519 & 0xffffffff
    v = (v ^ (v >> 13)) * 3266489917 & 0xffffffff
    v = v ^ (v >> 16)
    return (v & 0xffffff) / float(0xffffff)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)
