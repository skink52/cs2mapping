"""Materials for original maps: patterns, photo -> seamless PBR set, colour variants, glass / emissive / water / decal / sign materials.

  python matkit.py pattern <addon content> <name> <solid|noise|bricks|tiles|planks|checker|stripes|plaster|cobbles> [--color #rrggbb] [--color2 ..] [--size 512]
  python matkit.py image   <addon content> <name> <photo.jpg> [--region x0,y0,x1,y1] [--no-tile] [--no-delight]
  python matkit.py variant <addon content> <name> <source _color.png> [--tint #rrggbb] [--saturation 1] [--brightness 1]
  python matkit.py sign    <addon content> <name> "TEXT" [--color #rrggbb] [--ink #rrggbb] [--size 512x128]
  python matkit.py decal   <addon content> <name> <image.png | "TEXT">
Options for every kind: --kind complex|glass|emissive|water|decal, --roughness R, --metalness M, --surface <physics surface>, --dir materials/<sub>
Writes <content>/materials/<dir>/<name>_{color,normal,rough,ao}.png (+ extra maps per kind) and <name>.vmat; prints the material path.
Normal maps are OpenGL style (+Y), which Source 2 uses (docs/creation/models.md). Library: generate(), from_image(), make_tileable(),
variant(), text_image(), write_material(albedo, height=None, ...).

Ported from materials.py / textures.py of cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT): the same pattern set, the
photo pipeline (crop, delight, seamless, normal / roughness / AO from height) and their glass / water / decal shader parameter sets
(which they checked against Valve's materials). Fresh code; numpy + Pillow only.
"""
import argparse, math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

PATTERNS = ('solid', 'noise', 'bricks', 'tiles', 'planks', 'checker', 'stripes', 'plaster', 'cobbles')


def rgb(c, default=(128, 128, 128)):
    if c is None: return np.array(default, float)
    if isinstance(c, str):
        c = c.lstrip('#')
        return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], float)
    return np.array(c[:3], float)


def fbm(size, cells, seed=1, octaves=4):
    """tileable value-noise fBm in 0..1 (size x size), `cells` lattice cells across at the first octave"""
    rnd = np.random.default_rng(seed)
    out = np.zeros((size, size)); amp, total = 1.0, 0.0
    for o in range(octaves):
        n = max(1, int(cells * 2 ** o))
        lat = rnd.random((n, n))
        x = np.arange(size) * n / size; i0 = np.floor(x).astype(int); f = x - i0
        f = f * f * (3 - 2 * f); i1 = (i0 + 1) % n; i0 %= n
        rows = lat[i0][:, i0] * (1 - f)[None, :] + lat[i0][:, i1] * f[None, :]
        rows2 = lat[i1][:, i0] * (1 - f)[None, :] + lat[i1][:, i1] * f[None, :]
        out += amp * (rows * (1 - f)[:, None] + rows2 * f[:, None]); total += amp; amp *= 0.5
    return out / total


def _mix(c1, c2, t): return c1[None, None, :] * (1 - t[..., None]) + c2[None, None, :] * t[..., None]


def generate(pattern, size=512, color=None, color2=None, mortar=None, seed=1, count=None):
    """-> (albedo uint8 HxWx3, height float 0..1). count: (columns, rows) of bricks / tiles / planks / checks / stripes"""
    if pattern not in PATTERNS: raise ValueError('pattern must be one of %s' % ', '.join(PATTERNS))
    c1 = rgb(color, (150, 140, 130)); c2 = rgb(color2, c1 * 0.75); cm = rgb(mortar, (95, 92, 88))
    n = fbm(size, 8, seed); fine = fbm(size, 32, seed + 1, 3)
    y, x = np.mgrid[0:size, 0:size] / size
    height = n * 0.3
    if pattern == 'solid':
        alb = _mix(c1, c1 * 0.92, fine)
    elif pattern in ('noise', 'plaster'):
        k = 4 if pattern == 'noise' else 2
        alb = _mix(c1, c2, np.clip(n * 1.4 - 0.2, 0, 1)); height = n * 0.6 + fine * 0.2 * k / 4
    elif pattern in ('bricks', 'tiles'):
        cols, rows = count or ((4, 8) if pattern == 'bricks' else (4, 4))
        r = np.floor(y * rows); off = (r % 2) * 0.5 if pattern == 'bricks' else 0
        u = (x * cols + off) % 1.0; v = (y * rows) % 1.0
        gap = 0.04 if pattern == 'bricks' else 0.03
        edge = np.minimum(np.minimum(u, 1 - u) * rows / cols * (cols / rows), np.minimum(v, 1 - v))
        joint = (np.minimum(u, 1 - u) < gap * rows / cols) | (np.minimum(v, 1 - v) < gap)
        cell = (np.floor(x * cols + off) * 7.31 + r * 3.17) % 1.0
        body = _mix(c1, c2, np.clip(cell * 0.6 + fine * 0.4, 0, 1))
        alb = np.where(joint[..., None], cm[None, None, :] * (0.9 + 0.2 * fine[..., None]), body)
        height = np.where(joint, 0.1, 0.75 + 0.15 * fine) + 0.0 * edge
    elif pattern == 'planks':
        cols, rows = count or (1, 6)
        r = np.floor(y * rows); v = (y * rows) % 1.0
        grain = np.sin((x * 40 + n * 6 + r * 1.7) * math.pi) * 0.5 + 0.5
        joint = np.minimum(v, 1 - v) < 0.03
        body = _mix(c1, c2, np.clip(grain * 0.5 + ((r * 0.37) % 1.0) * 0.3 + fine * 0.2, 0, 1))
        alb = np.where(joint[..., None], c2[None, None, :] * 0.5, body); height = np.where(joint, 0.15, 0.7 + grain * 0.1)
    elif pattern == 'checker':
        cols, rows = count or (8, 8)
        t = ((np.floor(x * cols) + np.floor(y * rows)) % 2).astype(float)
        alb = _mix(c1, c2, t); height = 0.5 + 0.05 * fine
    elif pattern == 'stripes':
        cols, _ = count or (8, 1)
        t = (np.floor(x * cols * 2) % 2).astype(float)
        alb = _mix(c1, c2, t); height = 0.5 + 0.05 * fine
    else:   # cobbles: Voronoi stones with mortar
        rnd = np.random.default_rng(seed)
        k = (count or (8, 8))[0]
        pts = (rnd.random((k * k, 2)) * 0.8 + 0.1 + np.stack(np.mgrid[0:k, 0:k], -1).reshape(-1, 2)) / k
        P = np.concatenate([pts + [dx, dy] for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
        d = np.sqrt((x[..., None] - P[:, 1]) ** 2 + (y[..., None] - P[:, 0]) ** 2)
        d.sort(axis=-1)
        edge = d[..., 1] - d[..., 0]
        stone = np.clip(edge * k * 2.5, 0, 1)
        alb = np.where((stone < 0.15)[..., None], cm[None, None, :] * (0.85 + 0.3 * fine[..., None]), _mix(c1, c2, fine))
        height = stone * 0.8 + fine * 0.2
    alb = alb * (0.92 + 0.16 * fine[..., None])
    return np.clip(alb, 0, 255).astype(np.uint8), np.clip(height, 0, 1)


def make_tileable(img, border=0.12):
    """seamless by blending each edge band with the band wrapped from the opposite side (offset-and-blend)"""
    a = np.asarray(img, float); h, w = a.shape[:2]
    out = a.copy()
    for axis, n in ((1, w), (0, h)):
        b = max(2, int(n * border))
        rolled = np.roll(out, n // 2, axis=axis)
        t = np.ones(n); ramp = np.linspace(0, 1, b)
        t[:b] = ramp; t[-b:] = ramp[::-1]
        t = t.reshape((1, n) + (1,) * (out.ndim - 2)) if axis == 1 else t.reshape((n, 1) + (1,) * (out.ndim - 2))
        out = out * t + rolled * (1 - t)
    return out.astype(a.dtype) if np.issubdtype(np.asarray(img).dtype, np.floating) else np.clip(out, 0, 255).astype(np.uint8)


def seam_error(img):
    a = np.asarray(img, float)
    return float((np.abs(a[:, 0] - a[:, -1]).mean() + np.abs(a[0] - a[-1]).mean()) / 2)


def delight(img, radius=None):
    """remove large-scale lighting: divide by a heavy blur of the luminance, keep the mean"""
    a = np.asarray(img, float)
    r = radius or max(8, a.shape[1] // 8)
    lum = np.asarray(Image.fromarray(np.clip(a.mean(-1), 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)), float) + 1.0
    out = a / lum[..., None] * lum.mean()
    return np.clip(out, 0, 255).astype(np.uint8)


def height_from(albedo):
    lum = np.asarray(albedo, float).mean(-1) / 255.0
    return (lum - lum.min()) / max(1e-6, lum.max() - lum.min())


def normal_from(height, strength=2.0):
    """tangent-space normal map (OpenGL, +Y up) from a tileable height field"""
    dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * strength
    dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * strength
    n = np.stack([-dx, dy, np.ones_like(height)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return ((n * 0.5 + 0.5) * 255).astype(np.uint8)


def ao_from(height, radius=6):
    blur = np.asarray(Image.fromarray((height * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius)), float) / 255
    return (np.clip(1 - np.maximum(0, blur - height) * 2.5, 0, 1) * 255).astype(np.uint8)


def roughness_from(albedo, base=0.7, contrast=0.25):
    lum = np.asarray(albedo, float).mean(-1) / 255.0
    return (np.clip(base - (lum - lum.mean()) * contrast, 0.05, 1) * 255).astype(np.uint8)


def from_image(path, region=None, tile=True, do_delight=True, max_size=1024):
    img = Image.open(path).convert('RGB')
    if region: img = img.crop(tuple(int(v) for v in region))
    side = 2 ** int(math.log2(min(max_size, max(img.size))))
    img = img.resize((side, side), Image.LANCZOS)
    a = np.asarray(img)
    if do_delight: a = delight(a)
    if tile: a = make_tileable(a)
    return a, height_from(a)


def variant(src_png, tint=None, saturation=1.0, brightness=1.0):
    a = np.asarray(Image.open(src_png).convert('RGB'), float)
    grey = a.mean(-1, keepdims=True)
    a = grey + (a - grey) * saturation
    if tint is not None: a = a * rgb(tint) / 255.0
    return np.clip(a * brightness, 0, 255).astype(np.uint8)


def _font(px):
    for name in ('arialbd.ttf', 'arial.ttf', 'DejaVuSans-Bold.ttf'):
        try: return ImageFont.truetype(name, px)
        except OSError: pass
    return ImageFont.load_default()


def text_image(text, size=(512, 128), color='#203040', ink='#f0f0e8', transparent=False, border=True):
    """a sign plate (or, transparent=True, ink only for a decal) with the text fitted"""
    w, h = size
    im = Image.new('RGBA', size, (0, 0, 0, 0) if transparent else tuple(int(v) for v in rgb(color)) + (255,))
    d = ImageDraw.Draw(im)
    px = int(h * 0.7)
    while px > 8:
        f = _font(px); box = d.textbbox((0, 0), text, font=f)
        if box[2] - box[0] <= w * 0.9 and box[3] - box[1] <= h * 0.8: break
        px -= 2
    box = d.textbbox((0, 0), text, font=f)
    d.text(((w - (box[2] - box[0])) / 2 - box[0], (h - (box[3] - box[1])) / 2 - box[1]), text, font=f, fill=tuple(int(v) for v in rgb(ink)) + (255,))
    if border and not transparent:
        d.rectangle([3, 3, w - 4, h - 4], outline=tuple(int(v) for v in rgb(ink)) + (255,), width=max(2, h // 32))
    return np.asarray(im)


def _layer(shader, params, surface, extra=()):
    lines = ['// Generated by create/matkit.py', 'Layer0', '{', '\tshader "%s.vfx"' % shader, '\tg_bFogEnabled "1"']
    lines += ['\t%s "%s"' % (k, v) for k, v in params.items()] + list(extra)
    lines += ['\tSystemAttributes', '\t{', '\t\tPhysicsSurfaceProperties "%s"' % surface, '\t}', '}', '']
    return '\n'.join(lines)


def write_material(content, rel_dir, name, albedo, height=None, kind='complex', roughness=None, metalness=0.0, surface='default',
                   alpha='none', glow=1.0, opacity=0.5, water_color='#3a8d9a'):
    """write PNGs + <name>.vmat under <content>/<rel_dir>; -> material path relative to the content root"""
    if not rel_dir.startswith('materials/'): rel_dir = 'materials/' + rel_dir.strip('/')
    out = os.path.join(content, *rel_dir.split('/')); os.makedirs(out, exist_ok=True)
    a = np.asarray(albedo)
    path = lambda sfx: '%s/%s_%s.png' % (rel_dir, name, sfx)
    save = lambda arr, sfx: Image.fromarray(np.asarray(arr)).save(os.path.join(out, '%s_%s.png' % (name, sfx)))
    rgb_a = a[..., :3] if a.ndim == 3 else np.stack([a] * 3, -1)
    h = height if height is not None else height_from(rgb_a)
    save(rgb_a.astype(np.uint8), 'color'); save(normal_from(h), 'normal'); save(ao_from(h), 'ao')
    rough = np.full(h.shape, int(roughness * 255), np.uint8) if roughness is not None else roughness_from(rgb_a)
    save(rough, 'rough')
    if kind == 'complex' or kind == 'emissive':
        p = {'g_flModelTintAmount': '1.000', 'TextureColor': path('color'), 'TextureNormal': path('normal'),
             'TextureRoughness': path('rough'), 'TextureAmbientOcclusion': path('ao'), 'F_METALNESS_TEXTURE': 0,
             'g_flMetalness': '%.3f' % metalness}
        if alpha == 'test' and a.ndim == 3 and a.shape[2] == 4:
            save(a[..., 3], 'alpha'); p.update({'F_ALPHA_TEST': 1, 'TextureTranslucency': path('alpha'), 'g_flAlphaTestReference': '0.500'})
        elif alpha == 'translucent' and a.ndim == 3 and a.shape[2] == 4:
            save(a[..., 3], 'alpha'); p.update({'F_TRANSLUCENT': 1, 'TextureTranslucency': path('alpha')})
        if kind == 'emissive':
            mask = a[..., 3] if a.ndim == 3 and a.shape[2] == 4 else rgb_a.mean(-1).astype(np.uint8)
            save(mask, 'illum')
            p.update({'F_SELF_ILLUM': 1, 'g_flSelfIllumScale': '1.000', 'g_flSelfIllumBrightness': '%.4f' % glow,
                      'g_flSelfIllumAlbedoFactor': '1', 'g_vSelfIllumTint': '[1 1 1 0]', 'TextureSelfIllumMask': path('illum')})
        text = _layer('csgo_complex', p, surface)
    elif kind == 'glass':
        save(np.full(h.shape, 30, np.uint8), 'dust')
        text = _layer('csgo_glass', {'F_RENDER_BACKFACES': 1, 'F_DO_NOT_CAST_SHADOWS': 1,
                                     'GlassMaskTranslucency': '[%g %g %g 0]' % ((opacity,) * 3), 'GlassMaskTransmission': '[255 255 255 0]',
                                     'GlassTintColor': path('color'), 'GlassMaskColor': path('dust'),
                                     'TextureNormal': path('normal'), 'TextureRoughness': path('rough')}, 'glass')
    elif kind == 'water':
        waves = fbm(256, 8, 23)
        nrm = normal_from(waves, 18); rgba = np.concatenate([nrm, (waves * 255).astype(np.uint8)[..., None]], -1)
        save(rgba, 'waves'); save((waves * 255).astype(np.uint8), 'waveheight')
        c = rgb(water_color) / 255
        vec = '[%.4f %.4f %.4f 0]' % tuple(c)
        text = _layer('csgo_water_fancy', {'F_REFLECTION_TYPE': 2, 'F_REFRACTION': 1, 'g_flWaterFogStrength': 0.5, 'g_flWaterDecayStrength': 0.5,
                                           'g_vWaterFogColor': vec, 'g_vWaterDecayColor': vec, 'g_flWavesSpeed': 0.5, 'g_vWaveScale': '[15 15 0 0]',
                                           'g_nWaveIterations': 3, 'g_flWavesNormalStrength': 1, 'g_flWavesHeightOffset': 0.1,
                                           'g_flWaterMaxDepth': 128, 'g_flWaterPlaneOffset': 0, 'g_flEnvironmentMapBrightness': 1,
                                           'g_flGlossiness': 1, 'g_flFresnelExponent': 7, 'g_flRefractionLimit': 0.4,
                                           'TextureWavesNormal': path('waves'), 'TextureWavesHeight': path('waveheight')}, 'water',
                      ['\tAttributes', '\t{', '\t\t"mapbuilder.water" "1"', '\t\t"mapbuilder.nonsolid" "1"', '\t}'])
    elif kind == 'decal':
        alpha_ch = a[..., 3] if a.ndim == 3 and a.shape[2] == 4 else np.full(h.shape, 255, np.uint8)
        save(alpha_ch, 'alpha')
        text = _layer('csgo_lightmappedgeneric', {'F_OVERLAY': 1, 'F_TRANSLUCENT': 1, 'F_LAYERS': 0, 'F_VERTEX_COLOR': 1,
                                                  'g_flAlphaTestReference': 0, 'TextureLayer1Color': path('color'),
                                                  'TextureLayer1Translucency': path('alpha'), 'TextureLayer1Normal': path('normal'),
                                                  'TextureLayer1Roughness': path('rough'), 'g_vLayer1Tint': '[1 1 1 0]'}, surface)
    else:
        raise ValueError('kind must be complex, emissive, glass, water or decal')
    with open(os.path.join(out, name + '.vmat'), 'w', encoding='utf-8') as f: f.write(text)
    return '%s/%s.vmat' % (rel_dir, name)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Materials for original maps')
    ap.add_argument('cmd', choices=['pattern', 'image', 'variant', 'sign', 'decal'])
    ap.add_argument('content'); ap.add_argument('name'); ap.add_argument('arg')
    ap.add_argument('--color'); ap.add_argument('--color2'); ap.add_argument('--ink'); ap.add_argument('--size', default='512')
    ap.add_argument('--region'); ap.add_argument('--no-tile', action='store_true'); ap.add_argument('--no-delight', action='store_true')
    ap.add_argument('--tint'); ap.add_argument('--saturation', type=float, default=1.0); ap.add_argument('--brightness', type=float, default=1.0)
    ap.add_argument('--kind', default=None); ap.add_argument('--roughness', type=float); ap.add_argument('--metalness', type=float, default=0.0)
    ap.add_argument('--surface', default='default'); ap.add_argument('--dir', default='materials/gen'); ap.add_argument('--seed', type=int, default=1)
    a = ap.parse_args(argv)
    h = None; kind = a.kind or 'complex'
    if a.cmd == 'pattern':
        alb, h = generate(a.arg, int(a.size.split('x')[0]), a.color, a.color2, seed=a.seed)
    elif a.cmd == 'image':
        alb, h = from_image(a.arg, [float(v) for v in a.region.split(',')] if a.region else None, not a.no_tile, not a.no_delight)
    elif a.cmd == 'variant':
        alb = variant(a.arg, a.tint, a.saturation, a.brightness)
    else:
        w, hh = (int(v) for v in (a.size + 'x128').split('x')[:2]) if 'x' in a.size else (512, 128)
        if a.cmd == 'decal' and os.path.isfile(a.arg): alb = np.asarray(Image.open(a.arg).convert('RGBA'))
        else: alb = text_image(a.arg, (w, hh), a.color or '#203040', a.ink or ('#101010' if a.cmd == 'decal' else '#f0f0e8'), transparent=a.cmd == 'decal')
        kind = a.kind or ('decal' if a.cmd == 'decal' else 'complex')
    print(write_material(a.content, a.dir, a.name, alb, h, kind, a.roughness, a.metalness, a.surface,
                         alpha='test' if kind == 'complex' and alb.ndim == 3 and alb.shape[2] == 4 and a.cmd != 'sign' else 'none'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
