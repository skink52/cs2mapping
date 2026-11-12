"""Look at the generated map without Hammer: props included (tools/vmap_preview.py draws world meshes only).

  view_world.py <map.vmap> top x0,y0,x1,y1 out.png          plan of a box: ground shade, walkable (check_play's graph), blocked cells red,
                                                            stuck pockets magenta, prop footprints with names, spawns / stations
  view_world.py <map.vmap> cam ex,ey,ez tx,ty,tz out.png [fov] [range]
                                                            flat-shaded perspective view (painter's algorithm): terrain, world meshes, the
                                                            props' own LOD meshes (stock foliage as trunk + crown stand-ins), water
  view_world.py <map.vmap> fp x,y yaw out.png [pitch]       the same from a player's eye (64 u over the surface at x, y)
Uses check_play.load_scene (cached per vmap). A review aid: colours are guessed from material and model names.
"""
import os, sys, math, glob, re
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_play as CP
import layout as L
import mv_stock as S
import mv_models as M

COL = [('thatch', (150, 128, 70)), ('straw', (170, 150, 80)), ('hay', (176, 156, 84)), ('bamboo', (150, 140, 80)), ('wicker', (150, 125, 80)), ('wattle', (128, 104, 70)),
       ('sandbag', (150, 136, 100)), ('burlap', (150, 136, 100)), ('canvas', (96, 104, 70)), ('tarp', (90, 100, 70)), ('od', (84, 92, 60)), ('olive', (84, 92, 60)),
       ('camo', (70, 86, 54)), ('rust', (120, 78, 52)), ('steel', (110, 112, 116)), ('metal', (112, 114, 118)), ('psp', (108, 104, 96)), ('concrete', (150, 148, 140)),
       ('stone', (128, 126, 112)), ('khmer', (120, 116, 96)), ('laterite', (150, 96, 70)), ('brick', (150, 90, 70)), ('wood', (116, 88, 58)), ('plank', (124, 96, 62)),
       ('log', (96, 76, 52)), ('bark', (84, 70, 52)), ('timber', (110, 86, 58)), ('leaf', (58, 110, 50)), ('frond', (62, 116, 52)), ('grass', (104, 136, 62)),
       ('rice', (128, 160, 70)), ('reed', (120, 136, 70)), ('vine', (56, 96, 48)), ('foliage', (60, 112, 52)), ('silk', (210, 205, 190)), ('cloth', (160, 60, 50)),
       ('flag', (170, 60, 50)), ('rubber', (40, 40, 40)), ('tire', (40, 40, 40)), ('glass', (120, 150, 160)), ('ash', (60, 58, 56)), ('burnt', (50, 46, 44)),
       ('dirt', (124, 100, 72)), ('mud', (104, 84, 62)), ('earth', (120, 98, 70)), ('paint', (90, 100, 70)), ('alu', (150, 152, 150)), ('skin', (140, 144, 140)),
       ('clay', (150, 100, 76)), ('ceramic', (140, 96, 72)), ('rope', (150, 130, 90)), ('sign', (190, 180, 150)), ('white', (210, 208, 200)), ('red', (160, 60, 50)),
       ('green', (70, 100, 60)), ('black', (40, 40, 42)), ('brass', (160, 130, 60)), ('water', (70, 110, 130))]
CAT = [('hooch', (150, 128, 70)), ('hut', (150, 128, 70)), ('school', (160, 140, 110)), ('sandbag', (150, 136, 100)), ('bunker', (130, 118, 90)), ('tent', (96, 104, 70)),
       ('conex', (84, 92, 60)), ('crate', (116, 96, 60)), ('drum', (84, 92, 60)), ('khmer', (120, 116, 96)), ('naga', (120, 116, 96)), ('guardian', (120, 116, 96)),
       ('lintel', (120, 116, 96)), ('fallen_blocks', (120, 116, 96)), ('truss', (110, 84, 64)), ('pier', (150, 148, 140)), ('c123', (140, 144, 140)), ('m113', (84, 92, 60)),
       ('m35', (84, 92, 60)), ('m151', (84, 92, 60)), ('ural', (70, 86, 54)), ('gaz', (70, 86, 54)), ('bm21', (70, 86, 54)), ('t54', (70, 86, 54)), ('zpu', (70, 86, 54)),
       ('hip', (84, 96, 70)), ('apache', (70, 80, 60)), ('pbr', (84, 96, 70)), ('m101', (84, 92, 60)), ('heli_wreck', (60, 56, 52)), ('aztec_wall', (128, 126, 112)),
       ('rock', (128, 126, 112)), ('haystack', (176, 156, 84)), ('fence', (150, 140, 80)), ('log', (96, 76, 52)), ('pallet', (124, 96, 62)), ('parachute', (210, 205, 190))]


def colour(name, default=(140, 130, 110)):
    n = name.lower()
    for k, c in COL:
        if k in n: return c
    return default


def model_colour(model):
    n = model.lower()
    for k, c in CAT:
        if k in n: return c
    return colour(n)


_MESH = {}


def smd_mesh(path, max_tris=6000):
    """(T (N,3,3), colours (N,3)) of an SMD, Hammer model space; decimated by skipping when huge"""
    if path in _MESH: return _MESH[path]
    T = []; C = []; cur = (140, 130, 110); buf = []
    intri = False
    for l in open(path, errors='ignore'):
        q = l.split()
        if not intri:
            if l.strip() == 'triangles': intri = True
            continue
        if len(q) >= 9 and q[0].lstrip('-').isdigit():
            try: buf.append((-float(q[2]), float(q[1]), float(q[3])))
            except ValueError: continue
            if len(buf) == 3: T.append(buf); C.append(cur); buf = []
        elif len(q) == 1 and q[0] != 'end':
            cur = colour(q[0], None); buf = []
    T = np.array(T, float).reshape(-1, 3, 3); C = np.array([c if c is not None else (-1, -1, -1) for c in C], float).reshape(-1, 3)
    if len(T) > max_tris:
        a = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1)
        keep = np.argsort(-a)[:max_tris]; T = T[keep]; C = C[keep]
    _MESH[path] = (T, C)
    return T, C


def blob(cx, cy, cz, rx, rz, n=7, m=4):
    """a low-poly ellipsoid as triangles"""
    T = []
    for i in range(m):
        t0 = math.pi * i / m - math.pi / 2; t1 = math.pi * (i + 1) / m - math.pi / 2
        for j in range(n):
            a0 = 2 * math.pi * j / n; a1 = 2 * math.pi * (j + 1) / n
            p = lambda t, a: (cx + rx * math.cos(t) * math.cos(a), cy + rx * math.cos(t) * math.sin(a), cz + rz * math.sin(t))
            q = [p(t0, a0), p(t0, a1), p(t1, a1), p(t1, a0)]
            T.append([q[0], q[1], q[2]]); T.append([q[0], q[2], q[3]])
    return T


def prism(cx, cy, z0, z1, r, n=6):
    T = []
    for j in range(n):
        a0 = 2 * math.pi * j / n; a1 = 2 * math.pi * (j + 1) / n
        p0 = (cx + r * math.cos(a0), cy + r * math.sin(a0)); p1 = (cx + r * math.cos(a1), cy + r * math.sin(a1))
        T.append([(p0[0], p0[1], z0), (p1[0], p1[1], z0), (p1[0], p1[1], z1)]); T.append([(p0[0], p0[1], z0), (p1[0], p1[1], z1), (p0[0], p0[1], z1)])
    return T


def visual(p):
    """triangles + colours of one prop in world space"""
    model = p['model']; name = CP.short(model); o = np.array(p['o']); sc = np.array(p['s'])
    path = None
    if model.startswith('models/mv/ext/'):
        if 'ext/rs_' not in model:
            d = os.path.dirname(os.path.join(CP.ADDON, model.replace('/', os.sep))); base = name[:-4] if name.endswith('_dyn') else name
            for suf in ('_lod4d', '_lod3d', '_lod2d', ''):
                if os.path.exists(os.path.join(d, base + suf + '.smd')): path = os.path.join(d, base + suf + '.smd'); break
    elif model.startswith('models/mv/'):
        d = os.path.join(CP.ADDON, 'models', 'mv', name)
        fs = sorted(glob.glob(os.path.join(d, name + '_lod*.smd')))
        if fs: path = fs[-1]
    if path is not None and not any(k in model for k in ('elephant_grass', 'rice_clump', 'reeds', 'rubber_tree', 'bamboo_clump', 'dead_tree', 'vine_curtain')):
        T, C = smd_mesh(path)
        R = CP.rot_matrix((0.0, p['yaw'], 0.0))
        W = (T * sc) @ R.T + o
        mc = np.array(model_colour(model), float)
        C = np.where(C[:, :1] < 0, mc[None], C)
        return W, C
    lo = np.array(p['lo']); hi = np.array(p['hi']); h = hi[2] - lo[2]; ex = max(hi[0] - lo[0], hi[1] - lo[1])
    cx, cy = p['o'][0], p['o'][1]
    if any(k in model for k in CP.TREES):
        tr = S.TRUNK.get(model, S.TRUNK_MV.get(name, M.TRUNK.get(model, 10.0))) * p['s'][0]
        if 'dead_tree' in model: T = prism(cx, cy, lo[2], lo[2] + h * 0.9, tr); C = [(90, 84, 76)] * len(T)
        elif 'bamboo' in model:
            T = blob(cx, cy, lo[2] + h * 0.55, ex * 0.3, h * 0.45); C = [(110, 140, 66)] * len(T)
        else:
            palm = 'palm' in model
            T = prism(cx, cy, lo[2], lo[2] + h * (0.8 if palm else 0.55), min(tr, 30) if palm else tr); C = [(84, 70, 52)] * len(T)
            T2 = blob(cx, cy, lo[2] + h * (0.88 if palm else 0.72), ex * (0.42 if palm else 0.40), h * (0.12 if palm else 0.28)); T += T2; C += [(52 + (hash(model) % 20), 104, 48)] * len(T2)
        return np.array(T, float), np.array(C, float)
    if any(k in model for k in CP.FOLIAGE):
        cxb, cyb = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
        g = (120, 150, 66) if 'grass' in model or 'rice' in model or 'reeds' in model else (64, 118, 54)
        T = blob(cxb, cyb, lo[2] + h * 0.45, ex * 0.36, h * 0.5, n=5, m=2); return np.array(T, float), np.array([g] * len(T), float)
    if 'water_wall' in model:
        T = CP.box_tris(lo, hi); return T, np.array([(200, 220, 230)] * len(T), float)
    T = CP.box_tris(lo, hi)
    return T, np.array([model_colour(model)] * len(T), float)


def scene_tris(sc, centre, rng):
    """world triangles + colours within rng of centre"""
    T = sc['tris']; k = sc['kinds']; src = sc['srcs']
    c = T.mean(1)
    near = (np.hypot(c[:, 0] - centre[0], c[:, 1] - centre[1]) < rng) & (k != CP.K_HULL) & (k != CP.K_CLIP)
    Tw = T[near]; kk = k[near]; ss = src[near]
    col = np.zeros((len(Tw), 3))
    n = np.cross(Tw[:, 1] - Tw[:, 0], Tw[:, 2] - Tw[:, 0]); nl = np.linalg.norm(n, axis=1); nz = np.abs(n[:, 2]) / np.maximum(nl, 1e-9)
    ter = kk == CP.K_TERRAIN
    cm = Tw.mean(1)
    rd, hw = L.road_dist(cm[:, 0], cm[:, 1])
    g = np.stack([86 + 0 * nz, 112 + 0 * nz, 60 + 0 * nz], 1); rock = np.array([118, 112, 100.0]); dirt = np.array([132, 106, 76.0]); mud = np.array([96, 86, 62.0])
    w = np.clip((0.86 - nz) / 0.22, 0, 1)[:, None]
    tc = g * (1 - w) + rock * w
    tc = np.where((rd < hw)[:, None], dirt[None], tc)
    tc = np.where((L.water_dist(cm[:, 0], cm[:, 1]) < L.BANK_W)[:, None] & (rd >= hw)[:, None], mud[None], tc)
    col[ter] = tc[ter]
    for mi, ms in enumerate(sc['meshes']):
        sel = ss == -1 - mi
        if not sel.any() or ms['kind'] == CP.K_TERRAIN: continue
        if ms['kind'] == CP.K_WATER: col[sel] = (70, 112, 132)
        else:
            base = np.array(colour(ms['mat'], (130, 124, 110)), float)
            if 'groundrock' in ms['mat']: base = np.array([112, 114, 104.0])
            col[sel] = base
    out_T = [Tw]; out_C = [col]
    for p in sc['props']:
        cx, cy = (p['lo'][0] + p['hi'][0]) / 2, (p['lo'][1] + p['hi'][1]) / 2
        if math.hypot(cx - centre[0], cy - centre[1]) > rng: continue
        t, c_ = visual(p)
        if len(t): out_T.append(np.asarray(t, float)); out_C.append(np.asarray(c_, float))
    return np.concatenate(out_T), np.concatenate(out_C)


def render(T, C, eye, target, W=1280, H=800, fov=80.0, fog=(4500.0, (176, 184, 180))):
    eye = np.array(eye, float); f = np.array(target, float) - eye; f /= np.linalg.norm(f)
    up = np.array([0, 0, 1.0]) if abs(f[2]) < 0.99 else np.array([0, 1.0, 0])
    r = np.cross(f, up); r /= np.linalg.norm(r); u = np.cross(r, f)
    k = (W / 2) / math.tan(math.radians(fov) / 2)
    V = T - eye
    z = V @ f; x = V @ r; y = V @ u
    ok = (z > 6.0).all(1)
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); nl = np.linalg.norm(n, axis=1); ok &= nl > 1e-9
    T = T[ok]; C = C[ok]; z = z[ok]; x = x[ok]; y = y[ok]; n = n[ok] / nl[ok][:, None]
    sx = W / 2 + x * k / z; sy = H / 2 - y * k / z
    vis = (sx.max(1) > 0) & (sx.min(1) < W) & (sy.max(1) > 0) & (sy.min(1) < H)
    sx = sx[vis]; sy = sy[vis]; zc = z[vis].mean(1); n = n[vis]; C = C[vis]
    sun = np.array([-0.45, -0.35, 0.82]); sun /= np.linalg.norm(sun)
    sh = 0.42 + 0.58 * np.abs(n @ sun)
    fg = np.clip(zc / fog[0], 0, 1)[:, None] ** 1.3
    col = C * sh[:, None] * (1 - fg) + np.array(fog[1], float) * fg
    order = np.argsort(-zc)
    img = Image.new('RGB', (W, H), fog[1]); d = ImageDraw.Draw(img)
    sx = sx[order]; sy = sy[order]; col = np.clip(col[order], 0, 255).astype(np.uint8)
    for i in range(len(order)):
        d.polygon([(sx[i, 0], sy[i, 0]), (sx[i, 1], sy[i, 1]), (sx[i, 2], sy[i, 2])], fill=tuple(col[i]))
    return img


def cam(path, eye, target, out, fov=80.0, rng=3200.0, W=1280, H=800):
    sc = CP.load_scene(path)
    T, C = scene_tris(sc, eye, rng)
    img = render(T, C, eye, target, W, H, fov, fog=(rng * 1.2, (176, 184, 180)))
    ImageDraw.Draw(img).text((6, 6), 'eye %s -> %s' % ([round(v) for v in eye], [round(v) for v in target]), fill=(255, 255, 255))
    img.save(out); print('saved', out, len(T), 'tris')


def top(path, box, out, Wd=1500):
    sc = CP.load_scene(path); G = CP.Grid(sc)
    from scipy.sparse import csgraph
    ents = sc['ents']
    start = sorted(set(sum((G.nodes_near(e['o'][0], e['o'][1], e['o'][2] - 8.0) for e in ents if re.fullmatch(r'mv_spawn_ct_\d+', e['name'])), [])))
    ncomp, lab = csgraph.connected_components(G.walk, directed=True, connection='strong')
    from collections import Counter
    home = Counter(lab[start].tolist()).most_common(1)[0][0]
    R = (lab == home)
    fwd = CP.reach(G.walk, np.nonzero(R)[0]); back = CP.reach(G.walk, np.nonzero(R)[0], reverse=True)
    stuck = (fwd & ~back).reshape(G.K, CP.NX, CP.NY).any(0); Rm = R.reshape(G.K, CP.NX, CP.NY).any(0); blk = (G.blocked & G.exists).reshape(G.K, CP.NX, CP.NY)[0]
    x0, y0, x1, y1 = box
    i0 = max(0, int((x0 - CP.X0) // CP.CELL)); i1 = min(CP.NX, int((x1 - CP.X0) // CP.CELL) + 1); j0 = max(0, int((y0 - CP.Y0) // CP.CELL)); j1 = min(CP.NY, int((y1 - CP.Y0) // CP.CELL) + 1)
    Z = G.Z[0].reshape(CP.NX, CP.NY)[i0:i1, j0:j1]; Zt = G.terr.reshape(CP.NX, CP.NY)[i0:i1, j0:j1]
    Zs = np.where(np.isfinite(Z), Z, np.nanmin(Z[np.isfinite(Z)]) if np.isfinite(Z).any() else 0.0)
    gx, gy = np.gradient(Zs, CP.CELL)
    sh = np.clip(0.8 + 0.7 * (gx * 0.5 + gy * 0.5), 0.35, 1.25)
    lo, hi = np.percentile(Zs, 2), np.percentile(Zs, 98); t = np.clip((Zs - lo) / max(hi - lo, 1), 0, 1)
    rgb = np.stack([80 + 80 * t, 100 + 60 * t, 62 + 50 * t], -1) * sh[..., None]
    wat = G.water.reshape(CP.NX, CP.NY)[i0:i1, j0:j1] > Zt + 0.5
    rgb[wat] = rgb[wat] * 0.4 + np.array([60, 100, 150]) * 0.6
    rm = Rm[i0:i1, j0:j1]; rgb[~rm] = rgb[~rm] * 0.62
    b = blk[i0:i1, j0:j1]; rgb[b] = rgb[b] * 0.4 + np.array([200, 50, 40]) * 0.6
    st = stuck[i0:i1, j0:j1]; rgb[st] = (255, 0, 255)
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8).transpose(1, 0, 2)[::-1])
    s = Wd / (x1 - x0); Hd = int((y1 - y0) * s)
    img = img.resize((Wd, Hd), Image.NEAREST); d = ImageDraw.Draw(img)
    X0b = CP.X0 + i0 * CP.CELL; Y1b = CP.Y0 + j1 * CP.CELL
    sx = Wd / ((i1 - i0) * CP.CELL); sy = Hd / ((j1 - j0) * CP.CELL)
    px = lambda x, y: ((x - X0b) * sx, (Y1b - y) * sy)
    for p in sc['props']:
        cx, cy = (p['lo'][0] + p['hi'][0]) / 2, (p['lo'][1] + p['hi'][1]) / 2
        if not (x0 - 200 < cx < x1 + 200 and y0 - 200 < cy < y1 + 200): continue
        nm = CP.short(p['model']); tree = any(k in p['model'] for k in CP.TREES); fol = any(k in p['model'] for k in CP.FOLIAGE)
        if tree:
            q = px(p['o'][0], p['o'][1]); rr = max(3, 0.3 * (p['hi'][0] - p['lo'][0]) * sx); d.ellipse((q[0] - rr, q[1] - rr, q[0] + rr, q[1] + rr), outline=(20, 90, 20)); continue
        if fol:
            q = px(p['o'][0], p['o'][1]); d.point(q, fill=(140, 240, 120)); continue
        col = (255, 220, 120) if 'sandbag' in nm else (255, 110, 70) if p['cls'] == 'prop_dynamic' else (245, 245, 245) if p['solid'] else (150, 200, 255)
        d.polygon([px(*q) for q in p['poly']], outline=col)
        if (x1 - x0) <= 2600 and 'sandbag' not in nm and max(p['hi'][0] - p['lo'][0], p['hi'][1] - p['lo'][1]) * sx > 14: d.text(px(*p['poly'][0]), nm[:16], fill=(255, 255, 0))
    for e in ents:
        if not (x0 < e['o'][0] < x1 and y0 < e['o'][1] < y1) or e['o'][2] < L.LOBBY_Z + 1500: continue
        q = px(e['o'][0], e['o'][1])
        if e['cls'] == 'info_teleport_destination': d.ellipse((q[0] - 3, q[1] - 3, q[0] + 3, q[1] + 3), fill=(80, 220, 255))
        elif e['cls'] == 'info_target': d.rectangle((q[0] - 3, q[1] - 3, q[0] + 3, q[1] + 3), fill=(255, 255, 0)); d.text((q[0] + 5, q[1] - 5), e['name'][3:], fill=(255, 255, 255))
        elif e['cls'] == 'info_particle_system': d.line((q[0] - 4, q[1], q[0] + 4, q[1]), fill=(255, 160, 0)); d.line((q[0], q[1] - 4, q[0], q[1] + 4), fill=(255, 160, 0))
    d.text((6, 6), 'box %s  bright = walkable, red = blocked, magenta = stuck' % [round(v) for v in box], fill=(255, 255, 255))
    img.save(out); print('saved', out)


if __name__ == '__main__':
    if len(sys.argv) < 5: print(__doc__); sys.exit(2)
    path, mode = sys.argv[1], sys.argv[2]
    f = lambda s: [float(v) for v in s.split(',')]
    if mode == 'top': top(path, f(sys.argv[3]), sys.argv[4])
    elif mode == 'cam':
        cam(path, f(sys.argv[3]), f(sys.argv[4]), sys.argv[5], float(sys.argv[6]) if len(sys.argv) > 6 else 80.0, float(sys.argv[7]) if len(sys.argv) > 7 else 3200.0)
    elif mode == 'fp':
        x, y = f(sys.argv[3]); yaw = math.radians(float(sys.argv[4])); pitch = math.radians(float(sys.argv[6])) if len(sys.argv) > 6 else 0.0
        sc = CP.load_scene(path); G = CP.Grid(sc); z = G.top(x, y) + 64.0
        cam(path, (x, y, z), (x + math.cos(yaw) * math.cos(pitch) * 100, y + math.sin(yaw) * math.cos(pitch) * 100, z - math.sin(pitch) * 100), sys.argv[5], 90.0, 3000.0)
