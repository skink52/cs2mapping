"""Preview renders of the objective dressing (tools/arenas/objectives.py, the map part) and the script's live markers
(tools/objective_fx.py models placed as src/cs2/45_features.js objTick places them) on the Dunes terrain, for skink52 to judge
before the map build. A small flat-shaded z-buffer software renderer with a glow pass for the self-lit parts; terrain from
tools/arenas/dunes.py height(); the arena's other structures (plateau cover walls, bridges, wreck, refinery) are NOT drawn.
Scene state shown: A held by T (orange), B being taken by CT at 60 % and contested (white flash frame), C neutral; CTF flags on
their stands. usage: python -I tools/objectives_preview.py [out dir = preview/objectives]
"""
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.normpath(os.path.join(PROJ, '..', '..', 'create')))
import arenas.objectives as OBJ
import arenas.dunes as D
import objective_fx as OFX

EMIT = {'n': (1.0, 0.9, 0.75), 't': (0.95, 0.45, 0.1), 'ct': (0.16, 0.78, 1.0), 'w': (1.0, 1.0, 0.96)}
BASE = {OBJ.MAT['concrete']: (0.55, 0.53, 0.5), OBJ.MAT['concrete_dark']: (0.3, 0.3, 0.3), OBJ.MAT['trim']: (0.22, 0.22, 0.24),
        OBJ.MAT['panel']: (0.16, 0.17, 0.2), OBJ.MAT['plate']: (0.42, 0.42, 0.44)}
SUN = np.array([math.cos(math.radians(14)) * math.cos(math.radians(60)), math.cos(math.radians(14)) * math.sin(math.radians(60)), math.sin(math.radians(14))])
POINTS = [('A', -3300.0, 2500.0, 760.0, 700.0), ('B', 0.0, 0.0, 580.0, 700.0), ('C', 3300.0, -2500.0, 760.0, 700.0)]


class Scene:
    def __init__(self): self.P, self.C, self.E = [], [], []          # triangles (3x3), colour, emissive flag

    def add(self, V, F, col, emit=False):
        V = np.asarray(V, float)
        for f in F:
            for k in range(1, len(f) - 1):
                self.P.append(V[[f[0], f[k], f[k + 1]]]); self.C.append(col); self.E.append(emit)

    def add_mesh(self, mesh, col, emit, scale=1.0, yaw=0.0, pos=(0, 0, 0), pitch=0.0):
        V = np.asarray(mesh.V, float) * scale
        if pitch:
            cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch)); V = V @ np.array([[cp, 0, -sp], [0, 1, 0], [sp, 0, cp]]).T
        ca, sa = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        V = V @ np.array([[ca, -sa, 0], [sa, ca, 0], [0, 0, 1]]).T + np.asarray(pos, float)
        self.add(V, [list(f) for f in mesh.F], col, emit)


def terrain(sc, x0, y0, x1, y1, step):
    xs = np.arange(x0, x1 + 1, step); ys = np.arange(y0, y1 + 1, step)
    X, Y = np.meshgrid(xs, ys); Z = D.height(X, Y)
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            q = [(X[j, i], Y[j, i], Z[j, i]), (X[j, i + 1], Y[j, i + 1], Z[j, i + 1]), (X[j + 1, i + 1], Y[j + 1, i + 1], Z[j + 1, i + 1]), (X[j + 1, i], Y[j + 1, i], Z[j + 1, i])]
            zc = (Z[j, i] + Z[j + 1, i + 1]) / 2
            sand = (0.72, 0.56, 0.38) if zc > 200 else (0.6, 0.45, 0.32)
            sc.add(q, [[0, 1, 2, 3]], sand)


def dressing(sc):
    L = OBJ.layout([(p[0], p[1], p[2], p[3], p[4]) for p in POINTS], OBJ.SITES['dunes']['flags'], D.ground_at)
    for V, F, mats, o in L['meshes']:
        for f, m in zip(F, mats):
            if '/fx/fx_obj_' in m:
                c = m.split('fx_obj_')[1].split('_')[0]; sc.add(V, [f], EMIT[c], True)
            else: sc.add(V, [f], BASE.get(m, (0.5, 0.5, 0.5)))
    return L


def markers(sc, L, flash=False):
    """the script's props as objTick places them"""
    ring, col = OFX.ring_mesh(), OFX.column_mesh()
    def zone(pid, x, y, z, r, own, cap, prog, contested=False):
        c_ring = 'w' if (contested and flash) else own
        sc.add_mesh(ring, EMIT[c_ring], True, r / 100 * (1.03 if contested and flash else 1), 0, (x, y, z + 4))
        if prog > 0.02 and cap != 'n':
            n = max(1, min(20, math.ceil(prog * 20 - 1e-6)))
            sc.add_mesh(OFX.arc_mesh(n / 20), EMIT[cap], True, r / 100, 0, (x, y, z + 6))
        cc = own if own != 'n' else (cap if prog > 0.02 else 'n'); f = prog if own != 'n' else (prog if prog > 0.02 else 1)
        sc.add_mesh(col, EMIT['w' if (contested and flash) else cc], True, 1, 0, (x, y, z - 3000 * (1 - max(0.08, f))))
        g, back = OFX.letter_meshes(pid)
        lc = own if own != 'n' else (cap if prog > 0.02 else 'n')
        sc.add_mesh(g, EMIT[lc], True, 2, 35, (x, y, z + 1300)); sc.add_mesh(back, (0.09, 0.09, 0.11), False, 2, 35, (x, y, z + 1300))
    zone('A', -3300, 2500, 760, 700, 't', 't', 1.0)
    zone('B', 0, 0, 580, 700, 'n', 'ct', 0.6, contested=True)
    zone('C', 3300, -2500, 760, 700, 'n', 'n', 0.0)
    flag = OFX.flag_mesh()
    for team, p in L['flags'].items():
        c = 't' if team == 't' else 'ct'
        sc.add_mesh(flag, EMIT[c], True, 1, 90 if team == 't' else -90, p)
        sc.add_mesh(col, EMIT[c], True, 1, 0, (p[0], p[1], p[2] + 470))
        sc.add_mesh(ring, EMIT[c], True, 2.6, 0, (p[0], p[1], p[2] + 4))


def render(sc, W, H, cam, look, fov=60, ortho=None, fog=(9000, 30000)):
    P = np.array(sc.P); Cc = np.array(sc.C, float); E = np.array(sc.E)
    N = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-9
    cam = np.asarray(cam, float); fwd = np.asarray(look, float) - cam; fwd /= np.linalg.norm(fwd)
    up0 = np.array([0, 0, 1.0]) if abs(fwd[2]) < 0.99 else np.array([0, 1.0, 0])
    right = np.cross(fwd, up0); right /= np.linalg.norm(right); up = np.cross(right, fwd)
    rel = P - cam
    xv, yv, zv = rel @ right, rel @ up, rel @ fwd
    if ortho:
        sx = W / 2 + xv / ortho * W / 2; sy = H / 2 - yv / ortho * W / 2
    else:
        fl = W / 2 / math.tan(math.radians(fov / 2)); zz = np.maximum(zv, 1)
        sx = W / 2 + xv / zz * fl; sy = H / 2 - yv / zz * fl
    nd = np.abs(N @ SUN); lam = np.clip(N @ SUN, 0, 1) * 0.0 + nd
    shade = Cc * (0.38 + 0.75 * lam[:, None]) * np.array([1.0, 0.86, 0.72])
    col = np.where(E[:, None], Cc, shade)
    img = np.zeros((H, W, 3)); img[:] = np.linspace([0.32, 0.22, 0.34], [0.95, 0.6, 0.38], H)[:, None, :]
    glow = np.zeros((H, W, 3)); zb = np.full((H, W), np.inf)
    dist = np.linalg.norm(rel.mean(1), axis=1); fogk = np.clip((dist - fog[0]) / (fog[1] - fog[0]), 0, 0.85)
    fogc = np.array([0.85, 0.6, 0.45])
    order = np.argsort(-zv.mean(1))
    for t in order:
        if not ortho and (zv[t] < 20).any(): continue
        x, y = sx[t], sy[t]
        x0, x1 = max(int(x.min()), 0), min(int(x.max()) + 1, W - 1); y0, y1 = max(int(y.min()), 0), min(int(y.max()) + 1, H - 1)
        if x0 > x1 or y0 > y1: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(d) < 1e-9: continue
        a = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
        b = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
        c = 1 - a - b
        m = (a >= -1e-4) & (b >= -1e-4) & (c >= -1e-4)
        if not m.any(): continue
        z = a * zv[t, 0] + b * zv[t, 1] + c * zv[t, 2]
        if E[t]: z = z - 3                               # inlays lie flush on their surface: draw them over it
        sub = zb[y0:y1 + 1, x0:x1 + 1]; m &= z < sub
        if not m.any(): continue
        sub[m] = z[m]
        cc = col[t] * (1 - fogk[t]) + fogc * fogk[t] if not E[t] else col[t] * (1 - fogk[t] * 0.4) + fogc * fogk[t] * 0.4
        img[y0:y1 + 1, x0:x1 + 1][m] = cc
        g = glow[y0:y1 + 1, x0:x1 + 1]; g[m] = cc if E[t] else 0
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    gl = Image.fromarray((np.clip(glow, 0, 1) * 255).astype(np.uint8))
    out = np.asarray(im, float) + 0.6 * np.asarray(gl.filter(ImageFilter.GaussianBlur(6)), float) + 0.45 * np.asarray(gl.filter(ImageFilter.GaussianBlur(18)), float)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def label(im, text):
    d = ImageDraw.Draw(im)
    try: f = ImageFont.truetype('arial.ttf', 18)
    except Exception: f = ImageFont.load_default()
    for i, line in enumerate(text.split('\n')):
        d.text((11, 9 + 22 * i), line, fill=(0, 0, 0), font=f); d.text((10, 8 + 22 * i), line, fill=(255, 255, 255), font=f)
    return im


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PROJ, 'preview', 'objectives')
    os.makedirs(out, exist_ok=True)
    shots = []
    # 1 top-down, the whole play area
    sc = Scene(); terrain(sc, -7000, -7000, 7000, 7000, 175); L = dressing(sc); markers(sc, L)
    im = render(sc, 1400, 1400, (0, 0, 9000), (0, 0.01, 0), ortho=7000)
    shots.append(('top_down.png', label(im, 'Dunes top-down: zones A (T held) B (CT taking 60 %, contested) C (neutral); flag stands T west, CT east\n'
                                         'map dressing (inlay rings, dais, letter masts, flag pads) + script markers; other structures not drawn')))
    # 2-4 ground level
    sc = Scene(); terrain(sc, -5600, -3600, 5600, 4200, 90); L = dressing(sc); markers(sc, L, flash=False)
    shots.append(('zone_B_ground.png', label(render(sc, 1600, 900, (-1900, -2300, 980), (0, 0, 760), fov=70),
                                             'Zone B from a mech camera 3 000 u out: CT taking it (cyan arc 60 %, cyan column at 60 % height), lit letter mast')))
    sc2 = Scene(); terrain(sc2, -5600, -3600, 5600, 4200, 90); L2 = dressing(sc2); markers(sc2, L2, flash=True)
    shots.append(('zone_B_contested.png', label(render(sc2, 1600, 900, (-1900, -2300, 980), (0, 0, 760), fov=70),
                                                'Zone B contested: ring and column flash white every 1/8 s')))
    shots.append(('zone_A_held.png', label(render(sc, 1600, 900, (-4700, 900, 1250), (-3300, 2500, 900), fov=70),
                                           'Zone A held by T: orange ring, full arc and full column, orange letter')))
    shots.append(('flag_T_stand.png', label(render(sc, 1600, 900, (-2600, -1300, 700), (-4200, 0, 450), fov=60),
                                            'T flag stand: raised pad, orange inlay rings, pylons with lit strips + lamps, the flag and its column')))
    shots.append(('from_T_base.png', label(render(sc, 1600, 900, (-5200, -400, 900), (0, 0, 900), fov=75, fog=(12000, 40000)),
                                           'From the T side toward the centre: how far the columns and letters read')))
    for name, im in shots: im.save(os.path.join(out, name)); print('wrote', os.path.join(out, name))
    # contact sheet
    th = [im.resize((800, int(800 * im.height / im.width))) for _, im in shots[1:]]
    sheet = Image.new('RGB', (1600, sum(t.height for t in th[::2]) + 0), (20, 20, 24))
    y = 0
    for i in range(0, len(th), 2):
        sheet.paste(th[i], (0, y))
        if i + 1 < len(th): sheet.paste(th[i + 1], (800, y))
        y += th[i].height
    sheet.save(os.path.join(out, 'sheet.png')); print('wrote', os.path.join(out, 'sheet.png'))


if __name__ == '__main__':
    main()
