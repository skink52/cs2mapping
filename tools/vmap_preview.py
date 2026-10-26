"""Flat-shaded preview of a .vmap (binary or the importer's keyvalues2) without Hammer: a top-down view plus four corner views.

python3 vmap_preview.py <map.vmap> <out.png> [x0,y0,z0,x1,y1,z1]
Meshes are coloured by material (radartex.guess_colour), tool materials and sky shells are skipped, point entities are dots
(spawns green/blue, lights yellow, triggers not drawn). The optional box limits the view to one area (one arena of a multi-arena map).
Use it to check a port or a generated map before opening it in Hammer.
"""
import sys, os, math
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmapedit as V, dmx, radartex

SKIP = ('materials/tools/', 'moondome', 'toolsskybox', 'skybox/')

def polygons(m, box=None):
    out = []
    for n, _ in m.walk():
        if m.type(n) != b'CMapMesh': continue
        md = m.g(n, b'meshData')
        if md is None or md < 0: continue
        mats = [x.decode().lower() for x in m.g(md, b'materials') or []]
        pos = vdi = None
        for st in m.g(m.g(md, b'vertexData'), b'streams') or []:
            if m.E[st]['name'].startswith(b'position'): pos = m.g(st, b'data')
        fd = m.g(md, b'faceData'); mi = None
        for st in m.g(fd, b'streams') or []:
            if m.E[st]['name'].startswith(b'materialindex'): mi = m.g(st, b'data')
        fei, evi, nxt, vdi, fdi = (m.g(md, k) for k in (b'faceEdgeIndices', b'edgeVertexIndices', b'edgeNextIndices', b'vertexDataIndices', b'faceDataIndices'))
        if pos is None or fei is None: continue
        o = m.g(n, b'origin', [0, 0, 0]); a = m.g(n, b'angles', [0, 0, 0]); sc = m.g(n, b'scales', [1, 1, 1])
        for f, he in enumerate(fei):
            fi = fdi[f] if fdi and f < len(fdi) else f
            mat = mats[mi[fi]] if mi is not None and fi < len(mi) and 0 <= mi[fi] < len(mats) else ''
            if any(s in mat for s in SKIP): continue
            loop, h = [], he
            for _ in range(256):
                p = pos[vdi[evi[h]]]; loop.append(V.xform([p[0] * sc[0], p[1] * sc[1], p[2] * sc[2]], o, a)); h = nxt[h]
                if h == he: break
            if box and not all(box[0][k] <= sum(q[k] for q in loop) / len(loop) <= box[1][k] for k in range(3)): continue
            out.append((np.array(loop, float), radartex.guess_colour(mat)))
    return out

def points(m, box=None):
    pts = []
    for e in m.entities():
        c = m.cls(e); o = m.origin(e)
        if box and not all(box[0][k] <= o[k] <= box[1][k] for k in range(3)): continue
        if c == 'info_player_terrorist': pts.append((o, (230, 160, 40)))
        elif c == 'info_player_counterterrorist': pts.append((o, (70, 130, 240)))
        elif c.startswith('light_'): pts.append((o, (255, 240, 120)))
        elif c in ('info_teleport_destination', 'point_script', 'prop_dynamic', 'prop_physics_multiplayer'): pts.append((o, (200, 90, 200)))
    return pts

def render(polys, pts, cam, look, W=640, H=400, fov=70, ortho=None, title=''):
    img = Image.new('RGB', (W, H), (18, 20, 26)); d = ImageDraw.Draw(img)
    cam = np.array(cam, float); look = np.array(look, float)
    f = look - cam; f /= np.linalg.norm(f)
    up = np.array([0, 1, 0.]) if abs(f[2]) > 0.99 else np.array([0, 0, 1.])
    r = np.cross(f, up); r /= np.linalg.norm(r); u = np.cross(r, f)
    k = (W / 2) / math.tan(math.radians(fov) / 2)
    def proj(P):
        v = P - cam; z = v @ f
        if ortho: return np.stack([W / 2 + (v @ r) * ortho, H / 2 - (v @ u) * ortho], -1), z
        return np.stack([W / 2 + (v @ r) * k / np.maximum(z, 1e-3), H / 2 - (v @ u) * k / np.maximum(z, 1e-3)], -1), z
    sun = np.array([0.35, -0.5, 0.79])
    items = []
    for loop, col in polys:
        P, z = proj(loop)
        if not ortho and (z < 2).any(): continue
        n = np.cross(loop[1] - loop[0], loop[2] - loop[0]); nl = np.linalg.norm(n)
        if nl == 0: continue
        n /= nl
        if (cam - loop[0]) @ n < 0 and not ortho: continue          # back faces
        s = 0.45 + 0.55 * abs(n @ sun)
        items.append((z.mean(), [tuple(p) for p in P], tuple(int(c * s) for c in col)))
    for _, P, c in sorted(items, key=lambda t: -t[0]):
        if len(P) >= 3: d.polygon(P, fill=c, outline=tuple(max(0, x - 25) for x in c))
    for o, c in pts:
        P, z = proj(np.array([o], float))
        if ortho or z[0] > 2: x, y = P[0]; d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=c)
    d.text((6, 6), title, fill=(255, 255, 255))
    return img

def main():
    src, dst = sys.argv[1], sys.argv[2]
    box = None
    if len(sys.argv) > 3:
        b = [float(x) for x in sys.argv[3].split(',')]; box = (b[:3], b[3:])
    m = V.Map(src)
    polys = polygons(m, box); pts = points(m, box)
    if not polys: print('no meshes'); return
    allp = np.vstack([p for p, _ in polys]); lo, hi = np.percentile(allp, 1, 0), np.percentile(allp, 99, 0)
    c = (lo + hi) / 2; ext = float(max(hi - lo)) or 1.0
    W, H = 640, 400
    views = [render(polys, pts, [c[0], c[1], hi[2] + ext], c, ortho=min(W, H) / ext * 0.95, title='top down')]
    for i, (sx, sy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        cam = [c[0] + sx * ext * 0.75, c[1] + sy * ext * 0.75, c[2] + ext * 0.55]
        views.append(render(polys, pts, cam, c, title='from %s%s' % ('N' if sy > 0 else 'S', 'E' if sx > 0 else 'W')))
    sheet = Image.new('RGB', (W * 3, H * 2), (0, 0, 0))
    sheet.paste(views[0].resize((W * 1, H * 2)), (0, 0))
    for i, v in enumerate(views[1:]): sheet.paste(v, (W + (i % 2) * W, (i // 2) * H))
    sheet.save(dst); print('saved', dst, len(polys), 'faces', len(pts), 'points')

if __name__ == '__main__':
    main()
