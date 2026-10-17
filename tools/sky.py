"""CS:GO six-face skybox -> 2:1 equirectangular panorama for CS2 sky.vfx / csgo_moondome."""
import re
import numpy as np
import vtf
from PIL import Image

# Source R_DrawSkyBox: axis -> face suffix, direction = f(s, t); tex u=(s+1)/2, v=1-(t+1)/2
FACES = ['rt', 'lf', 'bk', 'ft', 'up', 'dn']

def face_arrays(faces, half_height):
    out = {}
    for k, im in faces.items():
        a = np.asarray(im.convert('RGB'), np.float32) / 255.0
        out[k] = a
    return out

def sample_dirs(faces, half, dx, dy, dz):
    ax, ay, az = np.abs(dx), np.abs(dy), np.abs(dz)
    res = np.zeros(dx.shape + (3,), np.float32)
    def put(mask, face, s, t):
        img = faces[face]; h, w = img.shape[:2]
        u = (s[mask] + 1) / 2; v = 1 - (t[mask] + 1) / 2
        if half.get(face): v = v * 2           # "$basetexturetransform scale 1 2": side texture covers the top half
        x = np.clip((u * w).astype(int), 0, w - 1); y = np.clip((v * h).astype(int), 0, h - 1)
        res[mask] = img[y, x]
    mx = (ax >= ay) & (ax >= az); my = (ay > ax) & (ay >= az); mz = ~(mx | my)
    # +X rt: v=(1,-s,t)   -X lf: (-1,s,t)   +Y bk: (s,1,t)   -Y ft: (-s,-1,t)   +Z up: (-t,-s,1)   -Z dn: (t,-s,-1)
    with np.errstate(divide='ignore', invalid='ignore'):
        m = mx & (dx > 0); put(m, 'rt', -dy / ax, dz / ax)
        m = mx & (dx <= 0); put(m, 'lf', dy / ax, dz / ax)
        m = my & (dy > 0); put(m, 'bk', dx / ay, dz / ay)
        m = my & (dy <= 0); put(m, 'ft', -dx / ay, dz / ay)
        m = mz & (dz > 0); put(m, 'up', -dy / az, -dx / az)
        m = mz & (dz <= 0); put(m, 'dn', -dy / az, dx / az)
    return res

def equirect(faces, half, width=2048, yaw0=0.0, mirror=False):
    """faces: dict suffix -> PIL image. u = 0.5 - (yaw - yaw0)/360 (left in the image = turning left), v=0 straight up"""
    f = face_arrays(faces, half)
    h = width // 2
    u = (np.arange(width) + 0.5) / width; v = (np.arange(h) + 0.5) / h
    uu, vv = np.meshgrid(u, v)
    yaw = np.radians(yaw0) + (0.5 - uu) * 2 * np.pi * (-1 if mirror else 1)
    pitch = (0.5 - vv) * np.pi
    if any(half.values()): pitch = np.maximum(pitch, -0.01)   # half-height sides: below the horizon = clamped bottom row, like CS:GO
    dx = np.cos(pitch) * np.cos(yaw); dy = np.cos(pitch) * np.sin(yaw); dz = np.sin(pitch)
    img = sample_dirs(f, half, dx, dy, dz)
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), 'RGB')

def load_faces(src, name):
    """src: assets.Source. Returns (faces, half) or (None, reason). HDR-compressed faces are tone mapped."""
    raws = {}; half = {}; hdr = False
    for f in FACES:
        vmt = 'materials/skybox/%s%s.vmt' % (name, f)
        if not src.has(vmt): return None, 'no CS:GO sky face %s' % vmt
        txt = src.read(vmt)
        if txt is None: return None, 'need'
        t = txt.decode('utf-8', 'replace').lower()
        m = re.search(r'\$hdrcompressedtexture"?\s+"?([^"\s]+)', t)
        tex = m.group(1) if m else (re.search(r'\$basetexture"?\s+"?([^"\s]+)', t) or [None, None])[1]
        if m: hdr = True
        if not tex: return None, 'face %s has no texture' % vmt
        data = src.read('materials/' + tex.replace('\\', '/') + '.vtf')
        if data is None: return None, 'need' if src.has('materials/' + tex + '.vtf') else 'missing texture ' + tex
        raws[f] = np.asarray(vtf.decode(data), np.float32) / 255.0
        half[f] = 'scale 1 2' in t
    if hdr:
        lin = {f: a[..., :3] * a[..., 3:4] * 16 for f, a in raws.items()}
        p = np.percentile(np.concatenate([x.reshape(-1, 3) for x in lin.values()]).max(1), 99.5)
        faces = {f: Image.fromarray((np.clip(x / p, 0, 1) * 255).astype(np.uint8)) for f, x in lin.items()}
    else:
        faces = {f: Image.fromarray((a[..., :3] * 255).astype(np.uint8)) for f, a in raws.items()}
    return faces, half
