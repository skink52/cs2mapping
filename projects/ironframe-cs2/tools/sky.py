"""IRONFRAME skies: one 4096 x 2048 equirectangular panorama per arena (smooth gradients, not pixel art), written as the
moondome material + the env_sky material through vmapgen.sky_files / sky_vmat.

    python -I tools/sky.py <addon out dir> [dunes|sprawl|orbital]      (default: IF_ARENA)
    import sky; img = sky.make('dunes'); sky.SUN['dunes'] -> (elevation deg, yaw deg of the sun in the sky)

Layers: elevation gradient (zenith / mid / horizon / below), sun disc + glow (Dunes, Orbital), fbm clouds (streaky cirrus lit
from below at dusk; a low overcast deck for Sprawl; a cloud sea below the horizon for Orbital), dust haze (Dunes), neon city
glow on the overcast (Sprawl), stars + nebula + a planet (Orbital). Panorama convention: column 0 = yaw 0 (+x), yaw grows with
the column; row 0 = straight up. Whether CS2 maps yaw 0 to +x is unverified: the sun position is cosmetic (light_environment
is the real sun), so a mismatch only moves the painted disc.
"""
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
CREATE = os.environ.get('CREATE', os.path.join(HERE, '..', '..', '..', 'create'))
sys.path.insert(0, CREATE); sys.path.insert(0, HERE)
import numpy as np
from PIL import Image
from noise import fbm, smoothstep

W, H = 4096, 2048
# sun in the sky: (elevation deg, yaw deg). light_environment angles are (pitch down, yaw of travel): travel yaw = sun yaw + 180.
SUN = {'dunes': (14.0, 60.0), 'sprawl': None, 'orbital': (48.0, 135.0)}


def dirs(w=W, h=H):
    u = (np.arange(w) + 0.5) / w; v = (np.arange(h) + 0.5) / h
    yaw = np.deg2rad(u * 360.0)[None, :]; el = np.deg2rad(90.0 - v * 180.0)[:, None]
    ce = np.cos(el)
    return np.broadcast_arrays(ce * np.cos(yaw), ce * np.sin(yaw), np.sin(el) + 0 * yaw)


def elev(h=H):
    return np.deg2rad(90.0 - (np.arange(h) + 0.5) / h * 180.0)[:, None]


def lerp(a, b, t):
    t = np.asarray(t, np.float32)[..., None]
    return np.asarray(a, np.float32) * (1 - t) + np.asarray(b, np.float32) * t


def grad(stops, el_deg):
    """stops: [(elevation deg, (r,g,b)), ...] sorted descending by elevation; piecewise-linear colour over the sky"""
    out = np.zeros(el_deg.shape + (3,), np.float32)
    e = np.asarray(el_deg, np.float32)
    for (e0, c0), (e1, c1) in zip(stops[:-1], stops[1:]):
        t = np.clip((e0 - e) / (e0 - e1), 0, 1)
        sel = (e <= e0) & (e > e1)
        seg = lerp(c0, c1, t)
        out[sel] = seg[sel]
    out[e > stops[0][0]] = stops[0][1]
    out[e <= stops[-1][0]] = stops[-1][1]
    return out


def upsample(a, w=W, h=H):
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)) if a.ndim == 3 else Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8))
    return np.asarray(im.resize((w, h), Image.BICUBIC), np.float32) / (1.0 if a.ndim == 3 else 255.0)


def cloud_field(scale=3.0, octaves=5, seed=11, w=1024, h=512, z=0.3):
    """fbm sampled on the sphere directions (so there is no seam at the wrap) at a lower resolution, 0..1"""
    x, y, zz = dirs(w, h)
    n = fbm(x * scale, y * scale, zz * scale + z, octaves, seed=seed)
    return upsample((n * 0.5 + 0.5))


def sun_layer(x, y, z, el_deg, yaw_deg, disc=0.55, glow=14.0, color=(255, 240, 210), glow_color=(255, 190, 120), glow_power=2.4):
    s = np.array([math.cos(math.radians(el_deg)) * math.cos(math.radians(yaw_deg)), math.cos(math.radians(el_deg)) * math.sin(math.radians(yaw_deg)),
                  math.sin(math.radians(el_deg))], np.float32)
    cosang = np.clip(x * s[0] + y * s[1] + z * s[2], -1, 1)
    ang = np.degrees(np.arccos(cosang))
    d = 1 - smoothstep(disc * 0.8, disc * 1.15, ang)
    g = np.clip(1 - ang / glow, 0, 1) ** glow_power
    return d[..., None] * np.asarray(color, np.float32), g[..., None] * np.asarray(glow_color, np.float32)


def stars(rng, n=6000, w=W, h=H):
    img = np.zeros((h, w, 3), np.float32)
    v = rng.uniform(-1, 1, n); u = rng.uniform(0, 1, n)       # uniform on the sphere: v = sin(elevation)
    el = np.degrees(np.arcsin(v)); row = ((90 - el) / 180 * h).astype(int) % h; col = (u * w).astype(int)
    b = rng.uniform(80, 255, n) * (rng.uniform(0, 1, n) ** 2.2)
    tint = np.stack([1 + rng.uniform(-0.1, 0.05, n), 1 + rng.uniform(-0.08, 0.05, n), 1 + rng.uniform(-0.05, 0.15, n)], 1)
    img[row, col] = np.maximum(img[row, col], b[:, None] * tint)
    big = rng.choice(n, n // 40, replace=False)
    for k in big:
        r, c = row[k], col[k]
        for dr, dc, f in ((0, 1, 0.55), (0, -1, 0.55), (1, 0, 0.55), (-1, 0, 0.55)):
            img[(r + dr) % h, (c + dc) % w] = np.maximum(img[(r + dr) % h, (c + dc) % w], b[k] * f * tint[k])
    return img


def make_dunes():
    x, y, z = dirs(); E = np.degrees(elev()) + 0 * x
    sky = grad([(90, (34, 30, 78)), (45, (72, 58, 110)), (22, (150, 100, 110)), (9, (232, 150, 100)), (2, (255, 185, 120)),
                (0, (236, 180, 130)), (-3, (160, 120, 95)), (-20, (88, 66, 50)), (-90, (40, 30, 24))], E)
    # dust haze: a warm band hugging the horizon, thicker toward the sun
    sel, syaw = SUN['dunes']
    yaw = np.degrees(np.arctan2(y, x)) % 360
    toward = 0.5 + 0.5 * np.cos(np.radians(yaw - syaw))
    haze = np.exp(-np.abs(E - 1.5) / 6.0) * (0.55 + 0.45 * toward)
    sky = lerp(sky, (238, 196, 150), haze * 0.7)
    # cirrus streaks, stretched along yaw, lit orange from below near the horizon and bluish higher up
    c1 = cloud_field(scale=2.2, octaves=5, seed=21, z=0.1); c2 = cloud_field(scale=7.0, octaves=4, seed=22, z=0.7)
    streak = np.clip((c1 - 0.48) * 3.2, 0, 1) * np.clip((c2 - 0.3) * 1.6, 0, 1)
    band = smoothstep(2, 10, E) * (1 - smoothstep(30, 55, E))
    cloud_col = lerp((255, 170, 120), (170, 150, 190), smoothstep(8, 40, E))
    sky = lerp(sky, cloud_col, streak * band * 0.85)
    disc, glow = sun_layer(x, y, z, sel, syaw, disc=0.6, glow=22.0, color=(255, 246, 220), glow_color=(255, 170, 90), glow_power=2.0)
    sky = sky + glow * 0.75 + disc
    # ground below the horizon: dark sand with a faint bounce
    below = smoothstep(-1, -8, E)
    sky = lerp(sky, (70, 52, 40), below * 0.6)
    return np.clip(sky, 0, 255)


def make_sprawl():
    x, y, z = dirs(); E = np.degrees(elev()) + 0 * x
    sky = grad([(90, (6, 7, 14)), (40, (14, 14, 28)), (12, (36, 26, 52)), (3, (70, 44, 78)), (0, (58, 40, 66)), (-4, (26, 22, 30)), (-90, (8, 8, 10))], E)
    # low overcast deck: dense fbm, lit from below by the city (magenta / cyan / amber patches around the horizon)
    deck = cloud_field(scale=3.5, octaves=6, seed=31, z=0.2); fine = cloud_field(scale=12.0, octaves=4, seed=32, z=0.9)
    dens = np.clip((deck - 0.35) * 2.0, 0, 1) * (0.7 + 0.3 * fine)
    yaw = np.degrees(np.arctan2(y, x)) % 360
    glow_patches = fbm(np.cos(np.radians(yaw)) * 2.5, np.sin(np.radians(yaw)) * 2.5, 0.0 * yaw + 0.4, 3, seed=33) * 0.5 + 0.5
    hue = fbm(np.cos(np.radians(yaw)) * 1.3, np.sin(np.radians(yaw)) * 1.3, 0.0 * yaw + 2.0, 2, seed=34) * 0.5 + 0.5
    neon = lerp((255, 70, 200), (60, 220, 255), hue)
    neon = lerp(neon, (255, 160, 60), np.clip((glow_patches - 0.6) * 3, 0, 1))
    low = np.exp(-np.maximum(E, 0) / 9.0) * (E > -1)
    lit = low * (0.35 + 0.65 * glow_patches)
    cloud_col = lerp((22, 20, 32), neon, lit * 0.8)
    sky = lerp(sky, cloud_col, dens * (0.95 - 0.6 * smoothstep(50, 80, E)))
    # rain streaks: faint vertical fbm modulation above the horizon
    rain = cloud_field(scale=40.0, octaves=2, seed=35, z=1.3)
    sky = sky * (0.92 + 0.08 * rain[..., None]) * (1 - 0.0 * E[..., None])
    below = smoothstep(-1, -10, E)
    sky = lerp(sky, (10, 9, 12), below * 0.8)
    return np.clip(sky, 0, 255)


def make_orbital():
    rng = np.random.RandomState(77)
    x, y, z = dirs(); E = np.degrees(elev()) + 0 * x
    sky = grad([(90, (3, 4, 10)), (30, (6, 8, 20)), (8, (24, 30, 60)), (0, (90, 100, 140)), (-2, (200, 205, 220)), (-90, (120, 130, 160))], E)
    st = stars(rng) * smoothstep(1, 6, E)[..., None]
    neb1 = cloud_field(scale=1.6, octaves=6, seed=41, z=0.5); neb2 = cloud_field(scale=4.0, octaves=5, seed=42, z=1.5)
    neb = np.clip((neb1 - 0.45) * 2.4, 0, 1) * np.clip((neb2 - 0.25) * 1.5, 0, 1) * smoothstep(3, 12, E)
    nebcol = lerp((90, 40, 140), (30, 110, 160), neb2)
    sky = lerp(sky, nebcol, neb * 0.55) + st
    # cloud sea below the horizon: bright, dense, with deep canyons; fades to the tops of distant cloud mountains at the horizon
    sea1 = cloud_field(scale=3.0, octaves=6, seed=43, z=0.0); sea2 = cloud_field(scale=9.0, octaves=5, seed=44, z=0.8)
    sea = np.clip(sea1 * 0.7 + sea2 * 0.3, 0, 1)
    sel, syaw = SUN['orbital']
    yaw = np.degrees(np.arctan2(y, x)) % 360
    toward = 0.5 + 0.5 * np.cos(np.radians(yaw - syaw))
    seacol = lerp((150, 150, 175), (250, 240, 235), sea ** 1.3 * (0.7 + 0.3 * toward))
    seacol = lerp(seacol, (255, 215, 180), np.clip((sea - 0.62) * 3, 0, 1) * toward * 0.6)
    under = smoothstep(0.5, -3.0, E)
    sky = lerp(sky, seacol, under)
    horizon_haze = np.exp(-np.abs(E) / 2.5)
    sky = lerp(sky, (205, 210, 230), horizon_haze * 0.6)
    # a big ringed gas giant low in the opposite sky
    pel, pyaw = 22.0, syaw + 160.0
    p = np.array([math.cos(math.radians(pel)) * math.cos(math.radians(pyaw)), math.cos(math.radians(pel)) * math.sin(math.radians(pyaw)), math.sin(math.radians(pel))], np.float32)
    ang = np.degrees(np.arccos(np.clip(x * p[0] + y * p[1] + z * p[2], -1, 1)))
    R = 9.0
    inside = 1 - smoothstep(R * 0.97, R * 1.01, ang)
    # bands: latitude on the planet = component along the sky's up projected
    up = np.array([0, 0, 1.0]) - p * p[2]; up /= np.linalg.norm(up)
    lat = (x * up[0] + y * up[1] + z * up[2]) / math.radians(R) * 1.0
    bands = fbm(lat * 6.0 + 0 * x, 0 * x + 0.2, 0 * x + 0.5, 4, seed=45) * 0.5 + 0.5
    pcol = lerp((160, 120, 90), (230, 200, 160), bands)
    limb = np.clip(1 - (ang / R) ** 2, 0, 1) ** 0.4
    lit_side = 0.45 + 0.55 * np.clip((x * (-p[0]) * 0 + (x * math.cos(math.radians(syaw)) + y * math.sin(math.radians(syaw))) * 0.5 + 0.5), 0, 1)
    sky = lerp(sky, pcol * limb[..., None] * lit_side[..., None], inside * smoothstep(-1, 3, E))
    disc, glow = sun_layer(x, y, z, sel, syaw, disc=0.5, glow=10.0, color=(255, 255, 250), glow_color=(255, 240, 220), glow_power=3.0)
    sky = sky + glow * 0.5 + disc
    return np.clip(sky, 0, 255)


MAKERS = {'dunes': make_dunes, 'sprawl': make_sprawl, 'orbital': make_orbital}


def make(arena):
    """the painted sky, then the far scenery (tools/sky_vista.py, drawn at 8192 x 4096); saved IF_SKY_W wide (default 8192)"""
    import sky_vista
    a = sky_vista.apply(arena, MAKERS[arena]())
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    ow = int(os.environ.get('IF_SKY_W', '8192'))
    if arena in sky_vista.VISTAS and im.width != ow: im = im.resize((ow, ow // 2), Image.LANCZOS)
    return im


def write(out, arena):
    """moondome vmat + sky vmat + PNG under materials/ifr/sky; returns (moondome vmat, sky vmat)"""
    import vmapgen as G
    img = make(arena)
    rel = 'materials/ifr/sky'
    dome = G.sky_files(out, arena, img, rel_dir=rel)
    skym = G.sky_vmat(out, img, name='sky_%s' % arena, rel_dir=rel)        # same PNG name as the moondome's: saved once more, not copied onto itself
    return dome, skym


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    arena = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('IF_ARENA', 'dunes')
    dome, skym = write(sys.argv[1], arena)
    print('sky %s -> %s, %s' % (arena, dome, skym))
