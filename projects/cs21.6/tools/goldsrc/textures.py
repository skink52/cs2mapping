"""1.6 textures -> PNG + CS2 materials (materials/cs16/...)."""
import os, re
import numpy as np
from PIL import Image
from bsp import Wad

SKIP = {'aaatrigger', 'clip', 'origin', 'null', 'bevel', 'hint', 'skip', 'nodraw'}
SKY = 'sky'
INVISIBLE = {'{invisible'}
MAT_DIR = 'materials/cs16'


def safe(name):
    n = name.lower()
    n = n.replace('{', 'alpha_').replace('~', 'lit_').replace('+', 'anim').replace('-', 'rand').replace('!', 'water_')
    return re.sub(r'[^a-z0-9_]', '_', n)


def material_path(name):
    return '%s/%s.vmat' % (MAT_DIR, safe(name))


def pow2(n):
    p = 1
    while p < n: p *= 2
    return p


class TexturePool:
    def __init__(self, wad_paths):
        self.wads = []
        for p in wad_paths:
            if os.path.exists(p):
                self.wads.append(Wad(p))
        self.images = {}       # lower name -> rgba ndarray
        self.missing = set()

    def add_bsp(self, bsp):
        for name, w, h, rgba in bsp.textures:
            if rgba is not None and name.lower() not in self.images:
                self.images[name.lower()] = rgba

    def get(self, name):
        k = name.lower()
        if k in self.images: return self.images[k]
        for w in self.wads:
            r = w.get(k)
            if r and r[3] is not None:
                self.images[k] = r[3]
                return r[3]
        self.missing.add(k)
        return None

    def size(self, name):
        img = self.get(name)
        if img is None: return (64, 64)
        return (img.shape[1], img.shape[0])

    def average_color(self, name):
        img = self.get(name)
        if img is None: return (200, 200, 200)
        a = img[..., :3].reshape(-1, 3).astype(np.float64)
        if img.shape[2] == 4:
            keep = img[..., 3].reshape(-1) > 0
            if keep.any(): a = a[keep]
        c = a.mean(0)
        return tuple(int(x) for x in c)

    def write(self, name, out_root):
        """writes the PNG(s) and the vmat; returns the material path"""
        k = name.lower()
        rel = material_path(k)
        img = self.get(k)
        d = os.path.join(out_root, MAT_DIR)
        os.makedirs(d, exist_ok=True)
        base = safe(k)
        if img is None:
            img = np.zeros((64, 64, 4), np.uint8); img[..., 0] = 255; img[..., 2] = 255; img[..., 3] = 255
            img[::8, :, :3] = 0
        h, w = img.shape[:2]
        tw, th = min(1024, pow2(w * 2)), min(1024, pow2(h * 2))
        rgb = Image.fromarray(img[..., :3], 'RGB').resize((tw, th), Image.BICUBIC)
        alpha = k.startswith('{')
        lines = ['// CS 1.6 texture %s' % name, 'Layer0', '{', '\tshader "csgo_complex.vfx"']
        if alpha:
            # transparent pixels take the colour of their neighbours so filtering doesn't bleed the key colour in
            a = img[..., 3]
            src = img[..., :3].astype(np.float32)
            if (a > 0).any():
                from scipy import ndimage
                idx = ndimage.distance_transform_edt(a == 0, return_distances=False, return_indices=True)
                src = src[idx[0], idx[1]]
            rgb = Image.fromarray(src.astype(np.uint8), 'RGB').resize((tw, th), Image.BICUBIC)
            Image.fromarray(a, 'L').resize((tw, th), Image.NEAREST).save(os.path.join(d, base + '_trans.png'))
            lines += ['\tF_ALPHA_TEST 1', '\tTextureTranslucency "%s/%s_trans.png"' % (MAT_DIR, base), '\tg_flAlphaTestReference "0.500"']
        rgb.save(os.path.join(d, base + '_color.png'))
        lines += ['\tTextureColor "%s/%s_color.png"' % (MAT_DIR, base),
                  '\tTextureNormal "materials/default/default_normal.tga"',
                  '\tTextureRoughness "materials/default/default_rough.tga"',
                  '\tTextureMetalness "materials/default/default_metal.tga"', '}', '']
        open(os.path.join(out_root, rel), 'w', newline='\n').write('\n'.join(lines))
        return rel


def decal_rgba(wad_paths, name):
    """GoldSrc decals (decals.wad) are alpha gradients: every pixel has the last palette colour, the index is its opacity"""
    import struct
    for p in wad_paths:
        if not os.path.exists(p) or 'decals' not in os.path.basename(p).lower(): continue
        w = Wad(p)
        e = w.entries.get(name.lower())
        if not e: continue
        fp, _, _ = e; d = w.data
        wd, ht = struct.unpack_from('<II', d, fp + 16); offs = struct.unpack_from('<4I', d, fp + 24)
        idx = np.frombuffer(d, np.uint8, wd * ht, fp + offs[0]).reshape(ht, wd)
        pal_off = fp + offs[3] + (wd // 8) * (ht // 8)
        cnt = struct.unpack_from('<H', d, pal_off)[0]
        pal = np.frombuffer(d, np.uint8, cnt * 3, pal_off + 2).reshape(-1, 3)
        rgba = np.zeros((ht, wd, 4), np.uint8); rgba[..., :3] = pal[-1]; rgba[..., 3] = idx
        return rgba
    return None


def write_decal(out_root, wad_paths, name):
    """translucent material for a decal; returns (material path, width, height) or None"""
    rgba = decal_rgba(wad_paths, name)
    if rgba is None: return None
    d = os.path.join(out_root, MAT_DIR, 'decals'); os.makedirs(d, exist_ok=True)
    base = safe(name)
    h, w = rgba.shape[:2]
    tw, th = min(1024, pow2(w * 2)), min(1024, pow2(h * 2))
    Image.fromarray(rgba[..., :3], 'RGB').resize((tw, th), Image.BICUBIC).save(os.path.join(d, base + '_color.png'))
    Image.fromarray(rgba[..., 3], 'L').resize((tw, th), Image.BICUBIC).save(os.path.join(d, base + '_trans.png'))
    rel = '%s/decals/%s.vmat' % (MAT_DIR, base)
    open(os.path.join(out_root, rel), 'w', newline='\n').write('\n'.join([
        '// CS 1.6 decal %s' % name, 'Layer0', '{', '\tshader "csgo_complex.vfx"', '\tF_TRANSLUCENT 1',
        '\tF_DO_NOT_CAST_SHADOWS 1',
        '\tTextureTranslucency "%s/decals/%s_trans.png"' % (MAT_DIR, base),
        '\tTextureColor "%s/decals/%s_color.png"' % (MAT_DIR, base),
        '\tTextureNormal "materials/default/default_normal.tga"',
        '\tTextureRoughness "materials/default/default_rough.tga"',
        '\tTextureMetalness "materials/default/default_metal.tga"', '}', '']))
    return rel, w, h


def write_translucent(out_root, base_vmat, amount):
    """variant of a material drawn see-through (1.6 render mode 'texture' with renderamt < 255)"""
    d = os.path.join(out_root, MAT_DIR)
    white = os.path.join(d, 'white_trans.png')
    if not os.path.exists(white): Image.new('L', (4, 4), 255).save(white)
    src = open(os.path.join(out_root, base_vmat)).read()
    lines = [l for l in src.split('\n') if 'F_ALPHA_TEST' not in l and 'TextureTranslucency' not in l and 'g_flAlphaTestReference' not in l]
    i = next(k for k, l in enumerate(lines) if 'shader' in l)
    lines[i + 1:i + 1] = ['\tF_TRANSLUCENT 1', '\tTextureTranslucency "%s/white_trans.png"' % MAT_DIR, '\tg_flOpacityScale "%.3f"' % (amount / 255.0)]
    rel = base_vmat[:-5] + '_t%d.vmat' % amount
    open(os.path.join(out_root, rel), 'w', newline='\n').write('\n'.join(lines))
    return rel


def read_tga(path):
    return Image.open(path).convert('RGB')


FACES = ['rt', 'lf', 'bk', 'ft', 'up', 'dn']


def sample_dirs(faces, dx, dy, dz):
    ax, ay, az = np.abs(dx), np.abs(dy), np.abs(dz)
    res = np.zeros(dx.shape + (3,), np.float32)
    def put(mask, face, s, t):
        img = faces[face]; h, w = img.shape[:2]
        u = (s[mask] + 1) / 2; v = 1 - (t[mask] + 1) / 2
        x = np.clip((u * w).astype(int), 0, w - 1); y = np.clip((v * h).astype(int), 0, h - 1)
        res[mask] = img[y, x]
    mx = (ax >= ay) & (ax >= az); my = (ay > ax) & (ay >= az); mz = ~(mx | my)
    with np.errstate(divide='ignore', invalid='ignore'):
        m = mx & (dx > 0); put(m, 'rt', -dy / ax, dz / ax)
        m = mx & (dx <= 0); put(m, 'lf', dy / ax, dz / ax)
        m = my & (dy > 0); put(m, 'bk', dx / ay, dz / ay)
        m = my & (dy <= 0); put(m, 'ft', -dx / ay, dz / ay)
        m = mz & (dz > 0); put(m, 'up', -dy / az, -dx / az)
        m = mz & (dz <= 0); put(m, 'dn', -dy / az, dx / az)
    return res


def sky_panorama(env_dirs, name, width=2048):
    """six GoldSrc sky faces (gfx/env/<name><face>.tga, first folder that has them) -> 2:1 equirect image
    (u = 0.5 - yaw/360, v = 0 straight up)"""
    faces = {}
    for env_dir in env_dirs:
        if not os.path.isdir(env_dir): continue
        files = {f.lower(): f for f in os.listdir(env_dir)}
        if all((name + s + '.tga').lower() in files for s in FACES):
            for s in FACES:
                faces[s] = np.asarray(read_tga(os.path.join(env_dir, files[(name + s + '.tga').lower()])), np.float32) / 255.0
            break
    if not faces: raise FileNotFoundError('sky ' + name)
    h = width // 2
    u = (np.arange(width) + 0.5) / width; v = (np.arange(h) + 0.5) / h
    uu, vv = np.meshgrid(u, v)
    yaw = (0.5 - uu) * 2 * np.pi
    pitch = (0.5 - vv) * np.pi
    dx = np.cos(pitch) * np.cos(yaw); dy = np.cos(pitch) * np.sin(yaw); dz = np.sin(pitch)
    img = sample_dirs(faces, dx, dy, dz)
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), 'RGB')


def write_sky(out_root, env_dirs, name):
    """env_sky material + moondome material for one 1.6 sky; returns (sky_vmat, moondome_vmat)"""
    d = os.path.join(out_root, MAT_DIR, 'sky')
    os.makedirs(d, exist_ok=True)
    key = name.lower()
    pano = sky_panorama(env_dirs, name)
    pano.save(os.path.join(d, '%s_sky_color.png' % key))
    Image.new('RGB', (16, 16), (255, 255, 255)).save(os.path.join(d, 'moondome_color.png'))
    open(os.path.join(d, '%s_sky.vmat' % key), 'w', newline='\n').write(
        '// CS 1.6 sky %s\nLayer0\n{\n\tshader "sky.vfx"\n\tF_TEXTURE_FORMAT2 1\n\tSkyTexture "%s/sky/%s_sky_color.png"\n\tg_flBrightnessExposureBias "0.000"\n}\n' % (name, MAT_DIR, key))
    open(os.path.join(d, '%s_moondome.vmat' % key), 'w', newline='\n').write('''// CS 1.6 sky %s on the map's sky faces: shows the panorama, unlit, casts no shadows, no fog
Layer0
{
	shader "csgo_moondome.vfx"
	F_DO_NOT_CAST_SHADOWS 1
	g_vColorTint "[1.000000 1.000000 1.000000 0.000000]"
	TextureColor "%s/sky/moondome_color.png"
	g_flCubeParallax "0.000"
	g_bFogEnabled "0"
	TextureCubeMap "%s/sky/%s_sky_color.png"
}
''' % (name, MAT_DIR, MAT_DIR, key))
    return '%s/sky/%s_sky.vmat' % (MAT_DIR, key), '%s/sky/%s_moondome.vmat' % (MAT_DIR, key)
