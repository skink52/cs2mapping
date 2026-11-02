"""Software render of what a racer sees: the track model and a car from the chase camera (same maths as
src/cs2/40_players.js placeCamera). For checking framing and how far ahead the track reads, without CS2.
usage: chase_view.py <addon_out_dir> <track id> <lap fraction> <preset high|far|near|fly> <out.png> [car]
environment: SIZE=1920x1080, SKIN=t|ct|gold (our car), PACK="ds:lat:car:skin;..." (other cars: ds ahead of ours, lat to
the left; car may be e.g. meteor_boost), EYE=x,y,z AT=x,y,z (a free camera instead of the chase camera),
AIR=<units> (our car off the ground, mid-jump)"""
import os, sys, json, math
import numpy as np
from PIL import Image

OUT, TID, FRAC, PRESET, PNG = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4], sys.argv[5]
CARKEY = sys.argv[6] if len(sys.argv) > 6 else 'meteor'
W, H = (int(v) for v in os.environ.get('SIZE', '960x540').split('x'))     # SIZE=1920x1080 for bigger shots
FOV = 106.0   # CS2's 90 degrees at 4:3 is about 106 across a 16:9 screen
CAMS = {'high': (290, 165, 15, 60), 'far': (420, 260, 22, 80), 'near': (230, 100, 9, 30), 'fly': (290, 165, 15, 60)}

T = [t for t in json.load(open(os.path.join(OUT, '_gen/tracks.json'))) if t['id'] == TID][0]
tex_cache = {}
def load_vmdl_mats(vmdl):
    txt = open(vmdl).read()
    import re
    return dict(re.findall(r'from = "([^"]+)\.vmat"\s*to = "([^"]+)"', txt))
def car_mats(vmdl, skin=None):
    """a car model's materials, in a team skin (t / ct / gold) if asked"""
    m = load_vmdl_mats(vmdl)
    if skin and skin != 'neutral': m['spr_pal'] = 'materials/spr/cars/pal_%s.vmat' % skin
    return m
def tex(vmat):
    if vmat in tex_cache: return tex_cache[vmat]
    path = os.path.join(OUT, vmat.replace('.vmat', '_color.png'))
    a = np.array(Image.open(path).convert('RGB')).astype(np.float32) if os.path.exists(path) else np.full((4, 4, 3), 128, np.float32)
    tr = os.path.join(OUT, vmat.replace('.vmat', '_trans.png'))
    al = np.array(Image.open(tr).convert('L')).astype(np.float32) / 255 if os.path.exists(tr) else None
    tex_cache[vmat] = (a, al)
    return tex_cache[vmat]
def load_smd(path, mats, off=(0, 0, 0), yaw=0.0, pitch=0.0):
    lines = open(path).read().split('\n')
    i = lines.index('triangles') + 1
    tris = []
    cy, sy = math.cos(yaw), math.sin(yaw); cp, sp = math.cos(pitch), math.sin(pitch)
    while i + 3 < len(lines) and lines[i] != 'end':
        m = lines[i]; vs = []
        for k in range(3):
            f = lines[i + 1 + k].split()
            x, y, z = -float(f[2]), float(f[1]), float(f[3])     # the SMD holds (y, -x, z) for ModelDoc
            x, z = x * cp + z * sp, -x * sp + z * cp
            x, y = x * cy - y * sy, x * sy + y * cy
            vs.append((x + off[0], y + off[1], z + off[2], float(f[7]), float(f[8])))
        tris.append((mats.get(m, ''), vs)); i += 4
    return tris

def ramp_lift(i, t):
    """how far a jump ramp lifts the road at segment i, fraction t (the game's Track.rampLift)"""
    n = T['n']
    for f in T['feats']:
        if f['kind'] != 'ramp': continue
        span = (f['b'] - f['a']) % n + 1
        k = (i - f['a']) % n
        if k < span: return f['h'] * min(1.0, max(0.0, (k + t) / span))
    return 0.0
def point(s, lat=0.0):
    """centreline point at progress s, moved `lat` units to the left on the banked surface (ramps included)"""
    n, step = T['n'], T['step']; s %= T['length']; f = s / step; i = int(f) % n; j = (i + 1) % n; t = f - int(f)
    bk = T['bk'][i] + (T['bk'][j] - T['bk'][i]) * t
    return (T['x'][i] + (T['x'][j] - T['x'][i]) * t - T['ty'][i] * lat, T['y'][i] + (T['y'][j] - T['y'][i]) * t + T['tx'][i] * lat,
            T['z'][i] + (T['z'][j] - T['z'][i]) * t - lat * bk + ramp_lift(i, t), T['tx'][i], T['ty'][i])
def bank(s):
    n, step = T['n'], T['step']; s %= T['length']; i = int(s / step) % n
    return T['bk'][i]

s0 = FRAC * T['length']
LAT = float(os.environ.get('LAT', '0'))
cx, cy_, cz, tx, ty = point(s0, LAT)
cz += float(os.environ.get('AIR', '0'))       # AIR=150: our car in the air off a jump (the camera follows it up)
car_yaw = math.atan2(ty, tx)
back, up, pitch, sback = CAMS[PRESET]
ax, ay, az, _, _ = point(s0 + 500 + 900 * 0.5)
cam_yaw = car_yaw + math.atan2(math.sin(math.atan2(ay - cy_, ax - cx) - car_yaw), math.cos(math.atan2(ay - cy_, ax - cx) - car_yaw)) * 0.35
b = back + sback
cam = np.array([cx - math.cos(cam_yaw) * b, cy_ - math.sin(cam_yaw) * b, cz + up])
fwd = np.array([math.cos(cam_yaw) * math.cos(math.radians(pitch)), math.sin(cam_yaw) * math.cos(math.radians(pitch)), -math.sin(math.radians(pitch))])
right = np.cross(fwd, [0, 0, 1]); right /= np.linalg.norm(right); upv = np.cross(right, fwd)
roll = math.radians(-math.degrees(math.atan(bank(s0))) * 0.6)     # CS2 roll: positive = right side down
right, upv = right * math.cos(roll) - upv * math.sin(roll), upv * math.cos(roll) + right * math.sin(roll)
if PRESET == 'fly':
    # the grid flyover (40_players.js placeFlyover) at progress FRAC (0..1), with a grid of cars to look at
    e = 1 - (1 - FRAC) ** 3
    sc = 5000 * (1 - e) + 250
    px, py, pz, ptx, pty = point(sc); qx, qy, qz, _, _ = point(sc - 600)
    h = 160 + 520 * (1 - e)
    cam = np.array([px, py, pz + h])
    look = math.atan2(qy - py, qx - px); pt = math.atan2(h - 40, 900)
    fwd = np.array([math.cos(look) * math.cos(pt), math.sin(look) * math.cos(pt), -math.sin(pt)])
    right = np.cross(fwd, [0, 0, 1]); right /= np.linalg.norm(right); upv = np.cross(right, fwd)
if os.environ.get('EYE'):
    # a free camera for overview shots: EYE=x,y,z AT=x,y,z (track space)
    cam = np.array([float(v) for v in os.environ['EYE'].split(',')])
    at = np.array([float(v) for v in os.environ.get('AT', '0,0,0').split(',')])
    fwd = (at - cam) / np.linalg.norm(at - cam)
    right = np.cross(fwd, [0, 0, 1]); right /= np.linalg.norm(right); upv = np.cross(right, fwd)
f = (W / 2) / math.tan(math.radians(FOV / 2))

vmdl = os.path.join(OUT, 'models/spr/track/%s.vmdl' % TID)
tris = load_smd(vmdl.replace('.vmdl', '.smd'), load_vmdl_mats(vmdl))
cm = os.path.join(OUT, 'models/spr/cars/%s_boost.vmdl' % CARKEY)
if PRESET == 'fly':
    keys = ['hornet', 'meteor', 'comet', 'bastion']
    for k in range(16):
        row, col = k // 4, k % 4
        sg = -(190 + row * 160 + (row % 2) * 60)
        _, _, _, _, _ = point(sg)
        hw0 = T['hw'][int((sg % T['length']) / T['step']) % T['n']]
        gx, gy, gz, gtx, gty = point(sg, -(col - 1.5) * hw0 * 0.46)
        m = os.path.join(OUT, 'models/spr/cars/%s.vmdl' % keys[(k * 7) % 4])
        tris += load_smd(m.replace('.vmdl', '.smd'), car_mats(m, 't' if k % 2 == 0 else 'ct'), off=(gx, gy, gz), yaw=math.atan2(gty, gtx))
else:
    tris += load_smd(cm.replace('.vmdl', '.smd'), car_mats(cm, os.environ.get('SKIN')), off=(cx, cy_, cz), yaw=car_yaw)
# more cars: PACK="ds:lat:car:skin;..." (ds ahead of ours, lat to the left), else a few ahead in the default colours
pack = [tuple(c.split(':')) for c in os.environ['PACK'].split(';')] if os.environ.get('PACK') else \
    [(700, 120, 'hornet', ''), (1300, -100, 'bastion', ''), (2100, 60, 'comet', ''), (3000, -140, 'meteor', '')]
for ds, lat, key, skin in pack:
    ds, lat = float(ds), float(lat)
    px, py, pz, ptx, pty = point(s0 + ds, lat)
    m = os.path.join(OUT, 'models/spr/cars/%s.vmdl' % key)
    tris += load_smd(m.replace('.vmdl', '.smd'), car_mats(m, skin), off=(px, py, pz), yaw=math.atan2(pty, ptx))

img = np.zeros((H, W, 3), np.float32)
yy, xx = np.mgrid[0:H, 0:W]
# the sky panorama behind everything (equirectangular)
skyp = os.path.join(OUT, 'materials/spr/sky/sky_%s_color.png' % TID)
if os.path.exists(skyp):
    sky = np.array(Image.open(skyp).convert('RGB')).astype(np.float32)
    D = fwd[None, None, :] * f + right[None, None, :] * (xx[..., None] - W / 2) + upv[None, None, :] * (H / 2 - yy[..., None])
    D /= np.linalg.norm(D, axis=2)[..., None]
    lon = np.arctan2(D[..., 1], D[..., 0]); latr = np.arcsin(np.clip(D[..., 2], -1, 1))
    su = ((lon / (2 * math.pi)) % 1 * sky.shape[1]).astype(int) % sky.shape[1]
    sv = np.clip(((0.5 - latr / math.pi) * sky.shape[0]).astype(int), 0, sky.shape[0] - 1)
    img[:] = sky[sv, su]
else:
    img[:] = (8, 10, 22)
zb = np.full((H, W), 1e9, np.float32)
NEAR = 5.0
def clip_tri(vs):
    """clip a triangle against the near plane; returns a list of triangles (camera-relative points with uv)"""
    pts = [(np.array(v[:3]) - cam, v[3], v[4]) for v in vs]
    out = []
    for k in range(3):
        a, b = pts[k], pts[(k + 1) % 3]
        da, db = a[0] @ fwd, b[0] @ fwd
        if da >= NEAR: out.append(a)
        if (da >= NEAR) != (db >= NEAR):
            t = (NEAR - da) / (db - da)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t))
    return [(out[0], out[k], out[k + 1]) for k in range(1, len(out) - 1)]
def raster(vmat, tri):
    P = np.array([p[0] for p in tri])
    vs = [(0, 0, 0, p[1], p[2]) for p in tri]
    d = P @ fwd
    sx = W / 2 + (P @ right) / d * f; sy = H / 2 - (P @ upv) / d * f
    x0, x1 = int(max(0, math.floor(sx.min()))), int(min(W - 1, math.ceil(sx.max())))
    y0, y1 = int(max(0, math.floor(sy.min()))), int(min(H - 1, math.ceil(sy.max())))
    if x0 > x1 or y0 > y1: return
    X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    den = (sy[1] - sy[2]) * (sx[0] - sx[2]) + (sx[2] - sx[1]) * (sy[0] - sy[2])
    if abs(den) < 1e-9: return
    w0 = ((sy[1] - sy[2]) * (X - sx[2]) + (sx[2] - sx[1]) * (Y - sy[2])) / den
    w1 = ((sy[2] - sy[0]) * (X - sx[2]) + (sx[0] - sx[2]) * (Y - sy[2])) / den
    w2 = 1 - w0 - w1
    inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
    if not inside.any(): return
    # perspective-correct depth and uv
    iz = w0 / d[0] + w1 / d[1] + w2 / d[2]
    depth = 1 / np.maximum(iz, 1e-9)
    u = (w0 * vs[0][3] / d[0] + w1 * vs[1][3] / d[1] + w2 * vs[2][3] / d[2]) * depth
    v = (w0 * vs[0][4] / d[0] + w1 * vs[1][4] / d[1] + w2 * vs[2][4] / d[2]) * depth
    t, al = tex(vmat) if vmat else (np.full((4, 4, 3), 200, np.float32), None)
    th, tw = t.shape[:2]
    ui = (np.floor((u % 1) * tw).astype(int)) % tw; vi = (np.floor((1 - v % 1) * th).astype(int)) % th
    col = t[vi, ui]
    sub = zb[y0:y1 + 1, x0:x1 + 1]
    ok = inside & (depth < sub)
    if al is not None:
        a = al[vi, ui]
        if 'shadow' in vmat or 'pulse' in vmat: return
        ok &= a > 0.5
    sub[ok] = depth[ok]
    img[y0:y1 + 1, x0:x1 + 1][ok] = col[ok]
for vmat, vs in tris:
    for tri in clip_tri(vs): raster(vmat, tri)
Image.fromarray(img.clip(0, 255).astype(np.uint8)).save(PNG)
print('chase view', TID, PRESET, '->', PNG)
