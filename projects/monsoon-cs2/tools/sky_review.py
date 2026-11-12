"""Measure and look at mg_monsoon's 3D skybox offline: where its triangles go, and how the skyline looks from the play space.

usage: sky_review.py budget <skybox .vmap> [--json out.json]
         triangles by category (terrain ring, karst towers, each tree model) and by band (distance past the sky shell), with the
         screen size of each band from the nearest player; totals comparable with the compile log's "Building render clusters" line
       sky_review.py render <skybox .vmap> <out dir> <tag> [--views a,b,..] [--ss 2] [--w 1280]
         per viewpoint a wide view (90 deg 4:3 = 106 deg on 16:9, CS2's default) and a zoomed one (4x) of the skyline:
         <out dir>/<view>_<wide|zoom>_<tag>.png
       sky_review.py compare <out dir> <tagA> <tagB>
         <out dir>/<view>_<wide|zoom>_compare.png: A above B, and a difference picture
       sky_review.py views
         list the viewpoints

The renders are a software z-buffer (numpy) of the skybox map as the engine places it (x 16 around the sky_camera), in front of the
main map's ground (layout.height) and its karst towers (layout.KARST, simplified); the main map's props are not drawn. Stock models
come from the game's pak01 through sky_meshes.mjs (cached in ../out/sky_cache), alpha tested at 0.5 with coverage-preserving mips.
Light is a flat sun + sky term and an aerial haze, the same for every tag: use it to compare two versions, not to judge the lighting.
"""
import os, sys, json, math, glob, subprocess
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dmx
import layout as LY

OUT = os.path.join(HERE, '..', 'out')
CACHE = os.path.join(OUT, 'sky_cache')
K = 16.0
# reference screen for "screen size": 2560 x 1440, CS2 fov 90 (4:3) = 73.74 deg vertical on 16:9
PX_RAD = 2 * math.tan(math.radians(73.74 / 2)) / 1440.0
SUN_ANG = (28.0, 205.0)                     # make_sky.SUN angles (pitch, yaw)
SKY_TOP, SKY_HZN = np.array([150, 166, 184.]), np.array([206, 204, 196.])
HAZE = np.array([196, 196, 190.])
HAZE_D = 26000.0                            # aerial haze: 1/e distance (world units)
# g_flAlphaTestReference of the stock foliage materials (tools/vmatc.py on their vmat_c); others 0.5
ALPHA_REF = {'ancient_skybox_tree_cards_01_color': 0.502, 'ancient_skybox_underbrush_cards_01': 0.081, 'hr_ancient_banyan_leaves_01': 0.658}

# viewpoints: (name, x, y, eye height over the ground or absolute z if 'z' given, yaw deg, pitch deg, zoom yaw offset)
VIEWS = [
    dict(name='ct_firebase_se', x=3900, y=-2900, dz=72, yaw=-35, pitch=2),
    dict(name='t_camp_nw', x=-3900, y=2900, dz=72, yaw=172, pitch=2),
    dict(name='bridge_west', x=0, y=None, dz=72, yaw=180, pitch=3),
    dict(name='temple_ne', x=2600, y=900, dz=72, yaw=35, pitch=3),
    dict(name='karst_top_north', x=-5000, y=3700, z=None, karst=0, yaw=95, pitch=-2),
    dict(name='heli_south', x=0, y=-3000, z=3600, yaw=-90, pitch=-12),
]


# ---------------------------------------------------------------- stock models
def model_file(model):
    return os.path.join(CACHE, model.replace('/', '__') + '.json')


def ensure_models(models):
    miss = [m for m in models if not os.path.exists(model_file(m))]
    if miss:
        r = subprocess.run(['node', os.path.join(HERE, 'sky_meshes.mjs'), CACHE] + miss, capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode: sys.exit(r.stderr)


_MODELS = {}
def model(m):
    if m not in _MODELS:
        d = json.load(open(model_file(m)))
        draws = []
        for dr in d['draws']:
            P = np.array(dr['P'], np.float32).reshape(-1, 3); UV = np.array(dr['UV'], np.float32).reshape(-1, 2)
            I = np.array(dr['I'], np.int32).reshape(-1, 3)
            draws.append(dict(material=dr['material'], P=P, UV=UV, I=I))
        lo = np.min([dw['P'].min(0) for dw in draws], 0); hi = np.max([dw['P'].max(0) for dw in draws], 0)
        _MODELS[m] = dict(draws=draws, tris=int(sum(len(dw['I']) for dw in draws)), lo=lo, hi=hi)
    return _MODELS[m]


# ---------------------------------------------------------------- textures
_TEX = {}
def texture(material):
    """(mips [RGBA float arrays], alpha thresholds per mip) or None for an untextured material"""
    if material in _TEX: return _TEX[material]
    png = os.path.join(CACHE, 'tex', material.replace('/', '__') + '.png')
    if not os.path.exists(png):
        try:
            import vtexread as T
            refs = T.refs(T.vpk_read(material + '_c'))
            col = [r for r in refs if '_color' in r and not r.startswith('materials/default/')]
            if not col: _TEX[material] = None; return None
            im = T.decode_vtex(T.vpk_read(col[0] + '_c'), mip=1).convert('RGBA')
            os.makedirs(os.path.dirname(png), exist_ok=True); im.save(png)
        except Exception as e:
            print('texture %s: %s' % (material, e)); _TEX[material] = None; return None
    a = np.asarray(Image.open(png).convert('RGBA'), np.float32) / 255.0
    ref = ALPHA_REF.get(material.split('/')[-1].replace('.vmat', ''), 0.5)
    cover = (a[..., 3] >= ref).mean()
    mips, thr = [a], [ref]
    while min(mips[-1].shape[:2]) > 2:
        b = mips[-1]; h, w = b.shape[0] // 2 * 2, b.shape[1] // 2 * 2; b = b[:h, :w]
        b = 0.25 * (b[0::2, 0::2] + b[1::2, 0::2] + b[0::2, 1::2] + b[1::2, 1::2])
        mips.append(b)
        al = b[..., 3].ravel()
        t = np.quantile(al, 1 - cover) if 0 < cover < 1 else 0.5        # keep the alpha-tested coverage of mip 0
        thr.append(float(min(max(t, 0.02), 0.98)))
    _TEX[material] = (mips, thr)
    return _TEX[material]


# ---------------------------------------------------------------- scene
def rot(ang):
    p, y, r = [math.radians(v) for v in ang]
    cp, sp, cy, sy, cr, sr = math.cos(p), math.sin(p), math.cos(y), math.sin(y), math.cos(r), math.sin(r)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]]); Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def walk(children):
    for c in children or []:
        yield c
        yield from walk(c.get('children'))


def load_sky(path):
    """{'cam': origin, 'scale', 'meshes': [dict(material(s), tris (N,3,3) world, color (N,3), cls)], 'props': [dict(model, pos, R, s)]}"""
    d = dmx.DMX.load(path)
    nodes = list(walk(d.root.get('world').get('children')))
    cam = np.zeros(3); scale = K
    for c in nodes:
        if c.type == 'CMapEntity' and c.get('entity_properties').get('classname') == 'sky_camera':
            cam = np.array(c.get('origin'), float); scale = float(c.get('entity_properties').get('scale') or K)
    meshes, props = [], []
    for c in nodes:
        if c.type == 'CMapMesh':
            md = c.get('meshData')
            pos = np.array(md.get('vertexData').get('streams')[0].get('data'), float)
            vdi = np.array(md.get('vertexDataIndices')); ev = np.array(md.get('edgeVertexIndices')); en = np.array(md.get('edgeNextIndices'))
            fe = md.get('faceEdgeIndices'); mats = md.get('materials') or ['']
            fvd = {s.name.split(':')[0]: s.get('data') for s in md.get('faceVertexData').get('streams')}
            evd = np.array(md.get('edgeVertexDataIndices'))
            tint = np.array(fvd['VertexPaintTintColor'])[:, :3] if 'VertexPaintTintColor' in fvd else None
            blend = np.array(fvd['VertexPaintBlendParams'])[:, 0] if 'VertexPaintBlendParams' in fvd else None
            fdi = md.get('faceDataIndices'); mi = None
            for s in md.get('faceData').get('streams'):
                if s.name.startswith('materialindex'): mi = s.get('data')
            o = np.array(c.get('origin'), float); R = rot(c.get('angles')); sc = np.array(c.get('scales'), float)
            P = (pos[vdi] * sc) @ R.T + o
            tris, mat_of, tn, bl = [], [], [], []
            for f, he in enumerate(fe):
                loop = [he]; h = en[he]
                while h != he and len(loop) < 64: loop.append(h); h = en[h]
                m = mats[mi[fdi[f]]] if mi is not None else mats[0]
                for k in range(1, len(loop) - 1):
                    hs = (loop[0], loop[k], loop[k + 1])
                    tris.append([P[ev[x]] for x in hs]); mat_of.append(m)
                    tn.append(tint[evd[list(hs)]].mean(0) if tint is not None else (1, 1, 1))
                    bl.append(blend[evd[list(hs)]].mean() if blend is not None else 0.0)
            meshes.append(dict(material=mats[0], tris=(np.array(tris) - cam) * scale, tint=np.array(tn), blend=np.array(bl),
                               cls='karst' if 'rock' in mats[0] else 'terrain', faces=len(fe)))
        elif c.type == 'CMapEntity':
            ep = c.get('entity_properties')
            if ep.get('classname') not in ('prop_static', 'prop_dynamic'): continue
            sc = c.get('scales') or (1, 1, 1)
            try: rc = np.array([float(v) for v in (ep.get('rendercolor') or '255 255 255').split()[:3]]) / 255.0
            except ValueError: rc = np.ones(3)
            props.append(dict(model=ep.get('model'), pos=(np.array(c.get('origin'), float) - cam) * scale, R=rot(c.get('angles')),
                              s=float(sc[0]) * scale, rc=rc))
    return dict(cam=cam, scale=scale, meshes=meshes, props=props)


def shell_dist(x, y):
    return np.maximum(np.abs(x) - LY.SKY_X, np.abs(y) - LY.SKY_Y)


def family(m):
    b = m.split('/')[-1].replace('.vmdl', '')
    for k in ('banyan_large', 'banyan_medium', 'banyan_small', 'palm_tree_skybox', 'palm_tree_card', 'tree_card', 'underbrush'):
        if k in b: return k
    return b


# ---------------------------------------------------------------- budget
BANDS = [(0, 1000), (1000, 2200), (2200, 5000), (5000, 9000), (9000, 1e9)]


def budget(path, out_json=None):
    S = load_sky(path)
    ensure_models(sorted(set(p['model'] for p in S['props'])))
    rows = {}
    def add(cat, band, tris, n=1, px=0.0):
        r = rows.setdefault((cat, band), [0, 0, 0.0]); r[0] += n; r[1] += tris; r[2] = max(r[2], px)
    nearest = lambda x, y: np.hypot(np.maximum(np.abs(x) - LY.MAP_X, 0), np.maximum(np.abs(y) - LY.MAP_Y, 0))
    for m in S['meshes']:
        c = m['tris'].mean(1); e = shell_dist(c[:, 0], c[:, 1])
        for b in BANDS:
            sel = (e >= b[0]) & (e < b[1])
            if sel.any(): add(m['cls'], b, int(sel.sum()), n=0)
        add(m['cls'] + ' (meshes)', None, 0, n=1)
    for p in S['props']:
        md = model(p['model']); x, y = p['pos'][:2]; e = float(shell_dist(x, y))
        b = next(b for b in BANDS if b[0] <= e < b[1])
        h = (md['hi'][2] - md['lo'][2]) * p['s']
        px = h / max(float(nearest(x, y)), 1.0) / PX_RAD
        add(family(p['model']), b, md['tris'], px=px)
    tot = sum(r[1] for r in rows.values())
    print('%-26s %-12s %7s %11s %7s %9s' % ('category', 'band (u)', 'count', 'triangles', '%', 'max px'))
    out = []
    for (cat, b), (n, t, px) in sorted(rows.items(), key=lambda kv: (kv[0][0], kv[0][1] or (0, 0))):
        bs = '-' if b is None else ('%d-%d' % b if b[1] < 1e8 else '%d+' % b[0])
        print('%-26s %-12s %7d %11d %7.2f %9.0f' % (cat, bs, n, t, 100.0 * t / max(tot, 1), px))
        out.append(dict(category=cat, band=bs, count=n, triangles=t, max_px=round(px)))
    cats = {}
    for (cat, b), (n, t, px) in rows.items(): cats.setdefault(cat, [0, 0]); cats[cat][0] += n; cats[cat][1] += t
    print('--- by category')
    for cat, (n, t) in sorted(cats.items(), key=lambda kv: -kv[1][1]):
        print('%-26s %7d %11d %7.2f' % (cat, n, t, 100.0 * t / max(tot, 1)))
    print('TOTAL triangles %d  (props %d, meshes %d; meshes %d faces)' % (tot, len(S['props']), len(S['meshes']), sum(m['faces'] for m in S['meshes'])))
    if out_json:
        json.dump(dict(vmap=os.path.abspath(path), total=tot, rows=out, by_category={k: dict(count=v[0], triangles=v[1]) for k, v in cats.items()}),
                  open(out_json, 'w'), indent=1)
    return tot


# ---------------------------------------------------------------- main-map stand-ins (same for every tag)
def main_ground(cell=64.0):
    xs = np.arange(-LY.TERRAIN_X, LY.TERRAIN_X + 1, cell); ys = np.arange(-LY.TERRAIN_Y, LY.TERRAIN_Y + 1, cell)
    X, Y = np.meshgrid(xs, ys, indexing='ij'); Z = LY.height(X, Y)
    W = np.abs(Y - LY.river_y(X)) < LY.RIVER_HW
    Z = np.where(W, np.maximum(Z, LY.WATER_Z), Z)
    P = np.stack([X, Y, Z], -1)
    a, b, c, d = P[:-1, :-1], P[1:, :-1], P[1:, 1:], P[:-1, 1:]
    tris = np.concatenate([np.stack([a, b, c], -2).reshape(-1, 3, 3), np.stack([a, c, d], -2).reshape(-1, 3, 3)])
    wat = W[:-1, :-1].ravel(); wat = np.concatenate([wat, wat])
    col = np.where(wat[:, None], np.array([82, 104, 112.]), np.array([84, 98, 58.]))
    return tris, col


def main_karst():
    out = []
    for i, (kx, ky, r, h, seed) in enumerate(LY.KARST):
        z0 = float(LY.ground_low(kx, ky)) - 40
        th = np.linspace(0, 2 * np.pi, 24, endpoint=False); t = np.linspace(0, 1, 9)
        TH, T = np.meshgrid(th, t, indexing='ij')
        rad = r * (1.0 - 0.25 * T) * (1 + 0.08 * np.sin(TH * 5 + seed))
        P = np.stack([kx + rad * np.cos(TH), ky + rad * np.sin(TH), z0 + (h + 40) * T], -1)
        for a in range(24):
            a2 = (a + 1) % 24
            for j in range(8):
                out.append([P[a, j], P[a2, j], P[a2, j + 1]]); out.append([P[a, j], P[a2, j + 1], P[a, j + 1]])
            out.append([P[a, 8], P[a2, 8], [kx, ky, z0 + h + 40 + 0.06 * h]])
    tris = np.array(out)
    return tris, np.tile(np.array([112, 116, 98.]), (len(tris), 1))


# ---------------------------------------------------------------- rasteriser
class Raster:
    def __init__(s, W, H, eye, yaw, pitch, hfov):
        s.W, s.H = W, H
        s.eye = np.asarray(eye, float)
        cy, sy, cp, sp = math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
        f = np.array([cy * cp, sy * cp, sp]); r = np.cross(f, [0, 0, 1.]); r /= np.linalg.norm(r); u = np.cross(r, f)
        s.M = np.stack([r, u, f])
        s.f = 0.5 * W / math.tan(math.radians(hfov) / 2)
        s.tanx, s.tany = 0.5 * W / s.f, 0.5 * H / s.f
        s.z = np.full(W * H, np.inf, np.float32)
        s.c = np.zeros((W * H, 3), np.float32)
        s.drawn = 0
        sun_p, sun_y = [math.radians(v) for v in SUN_ANG]
        s.sun = -np.array([math.cos(sun_y) * math.cos(sun_p), math.sin(sun_y) * math.cos(sun_p), -math.sin(sun_p)])

    def visible_sphere(s, c, rad):
        v = (np.asarray(c, float) - s.eye) @ s.M.T
        if v[2] < -rad: return False
        zz = max(v[2], 1.0)
        return abs(v[0]) - rad <= s.tanx * zz + rad and abs(v[1]) - rad <= s.tany * zz + rad

    def background(s):
        y = (np.arange(s.H) + 0.5) / s.H
        el = np.degrees(np.arctan((0.5 - y) * 2 * s.tany)) + 0                    # elevation of each row (pitch ignored for the sky)
        t = np.clip(el / 25.0, 0, 1)[:, None]
        rowcol = SKY_HZN * (1 - t) + SKY_TOP * t
        return np.repeat(rowcol[:, None, :], s.W, 1).reshape(-1, 3)

    def draw(s, tris, col, uv=None, mat=None, foliage=False):
        """tris (N,3,3) world; col (N,3) 0..255 base colour (multiplied by the texture when mat has one); uv (N,3,2)"""
        if len(tris) == 0: return
        V = (tris.reshape(-1, 3) - s.eye) @ s.M.T
        V = V.reshape(-1, 3, 3).astype(np.float32)
        keep = (V[:, :, 2] > 2.0).all(1)
        if not keep.any(): return
        V, tris, col = V[keep], tris[keep], col[keep]
        if uv is not None: uv = uv[keep]
        sx = s.W * 0.5 + s.f * V[:, :, 0] / V[:, :, 2]; sy = s.H * 0.5 - s.f * V[:, :, 1] / V[:, :, 2]
        x0 = np.floor(sx.min(1) - 0.5).astype(np.int64) + 1; x1 = np.floor(sx.max(1) - 0.5).astype(np.int64)
        y0 = np.floor(sy.min(1) - 0.5).astype(np.int64) + 1; y1 = np.floor(sy.max(1) - 0.5).astype(np.int64)
        x0 = np.maximum(x0, 0); y0 = np.maximum(y0, 0); x1 = np.minimum(x1, s.W - 1); y1 = np.minimum(y1, s.H - 1)
        ok = (x1 >= x0) & (y1 >= y0)
        idx = np.nonzero(ok)[0]
        if not len(idx): return
        # shading per triangle: flat normal (two sided), sun + sky, then haze by distance
        n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]); n /= np.maximum(np.linalg.norm(n, axis=1), 1e-9)[:, None]
        view = tris.mean(1) - s.eye; dist = np.linalg.norm(view, axis=1)
        n = np.where(((n * view).sum(1) > 0)[:, None], -n, n)
        nd = np.clip(n @ s.sun, 0, 1)
        shade = (0.42 + 0.20 * np.clip(n[:, 2], 0, 1) + 0.62 * nd) if not foliage else (0.55 + 0.10 * np.clip(n[:, 2], 0, 1) + 0.35 * nd)
        fog = 1 - np.exp(-dist / HAZE_D)
        tex = texture(mat) if mat else None
        if tex is not None:
            mips, thr = tex
            th, tw = mips[0].shape[:2]
            a2 = np.abs((sx[:, 1] - sx[:, 0]) * (sy[:, 2] - sy[:, 0]) - (sx[:, 2] - sx[:, 0]) * (sy[:, 1] - sy[:, 0]))
            ua = np.abs((uv[:, 1, 0] - uv[:, 0, 0]) * (uv[:, 2, 1] - uv[:, 0, 1]) - (uv[:, 2, 0] - uv[:, 0, 0]) * (uv[:, 1, 1] - uv[:, 0, 1])) * tw * th
            lod = np.clip(np.round(0.5 * np.log2(np.maximum(ua, 1e-6) / np.maximum(a2, 1e-6))), 0, len(mips) - 1).astype(int)
        w = (x1 - x0 + 1)[idx]; h = (y1 - y0 + 1)[idx]; size = np.maximum(w, h)
        classes = [1, 2, 4, 8, 16, 32, 64]
        for ci, cs in enumerate(classes):
            sel = idx[(size <= cs) & ((size > classes[ci - 1]) if ci else True)]
            if not len(sel): continue
            step = max(1, 3000000 // (cs * cs))
            for k in range(0, len(sel), step):
                s._fill(sel[k:k + step], cs, sx, sy, V, x0, y0, x1, y1, col, shade, fog, uv, tex, lod if tex is not None else None)
        big = idx[size > 64]
        for t in big:
            s._fill(np.array([t]), None, sx, sy, V, x0, y0, x1, y1, col, shade, fog, uv, tex, lod if tex is not None else None)
        s.drawn += len(idx)

    def _fill(s, sel, cs, sx, sy, V, x0, y0, x1, y1, col, shade, fog, uv, tex, lod):
        if cs is None:
            t = sel[0]; gx, gy = np.meshgrid(np.arange(x0[t], x1[t] + 1), np.arange(y0[t], y1[t] + 1), indexing='ij')
            PX = gx.ravel()[None, :]; PY = gy.ravel()[None, :]
        else:
            o = np.arange(cs)
            PX = x0[sel][:, None] + np.repeat(o, cs)[None, :]; PY = y0[sel][:, None] + np.tile(o, cs)[None, :]
        cx = PX + 0.5; cy = PY + 0.5
        X = sx[sel]; Y = sy[sel]
        valid = (PX <= x1[sel][:, None]) & (PY <= y1[sel][:, None])
        area = (X[:, 1] - X[:, 0]) * (Y[:, 2] - Y[:, 0]) - (X[:, 2] - X[:, 0]) * (Y[:, 1] - Y[:, 0])
        area = np.where(np.abs(area) < 1e-12, 1e-12, area)[:, None]
        l0 = ((X[:, 1, None] - cx) * (Y[:, 2, None] - cy) - (X[:, 2, None] - cx) * (Y[:, 1, None] - cy)) / area
        l1 = ((X[:, 2, None] - cx) * (Y[:, 0, None] - cy) - (X[:, 0, None] - cx) * (Y[:, 2, None] - cy)) / area
        l2 = 1 - l0 - l1
        inside = valid & (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        if not inside.any(): return
        ti, pj = np.nonzero(inside)
        L0, L1, L2 = l0[ti, pj], l1[ti, pj], l2[ti, pj]
        Z = V[sel][:, :, 2]
        iz = L0 / Z[ti, 0] + L1 / Z[ti, 1] + L2 / Z[ti, 2]
        depth = (1.0 / iz).astype(np.float32)
        tri = sel[ti]
        c = col[tri].astype(np.float32)
        if tex is not None:
            mips, thr = tex
            U = uv[sel]
            pu = (L0 * U[ti, 0, 0] / Z[ti, 0] + L1 * U[ti, 1, 0] / Z[ti, 1] + L2 * U[ti, 2, 0] / Z[ti, 2]) / iz
            pv = (L0 * U[ti, 0, 1] / Z[ti, 0] + L1 * U[ti, 1, 1] / Z[ti, 1] + L2 * U[ti, 2, 1] / Z[ti, 2]) / iz
            lv = lod[tri]
            keep = np.ones(len(tri), bool); rgb = np.zeros((len(tri), 3), np.float32)
            for L in np.unique(lv):
                m = lv == L; img = mips[L]; hh, ww = img.shape[:2]
                ii = np.clip((np.mod(pv[m], 1.0) * hh).astype(int), 0, hh - 1); jj = np.clip((np.mod(pu[m], 1.0) * ww).astype(int), 0, ww - 1)
                px = img[ii, jj]
                keep[m] = px[:, 3] >= thr[L]; rgb[m] = px[:, :3] * 255.0
            c = c * rgb / 255.0
            ti, pj, depth, tri, c = ti[keep], pj[keep], depth[keep], tri[keep], c[keep]
            if not len(ti): return
        pix = PY[ti, pj] * s.W + PX[ti, pj]
        sh = shade[tri][:, None]; fg = fog[tri][:, None]
        c = (c * sh) * (1 - fg) + HAZE[None, :] * fg
        np.minimum.at(s.z, pix, depth)
        win = depth <= s.z[pix]
        s.c[pix[win]] = c[win]

    def image(s, ss):
        bg = s.background()
        img = np.where(np.isinf(s.z)[:, None], bg, s.c).reshape(s.H, s.W, 3)
        if ss > 1:
            img = img.reshape(s.H // ss, ss, s.W // ss, ss, 3).mean((1, 3))
        return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def view_eye(v):
    x = v['x']; y = v['y'] if v['y'] is not None else float(LY.river_y(v['x'])) + 220
    if v.get('karst') is not None:
        kx, ky, r, h, seed = LY.KARST[v['karst']]; x, y = kx, ky
        return (x, y, float(LY.ground_low(kx, ky)) + h + 140)
    if v.get('z') is not None: return (x, y, v['z'])
    return (x, y, max(float(LY.height(x, y)), LY.WATER_Z) + v['dz'])


def render(path, out_dir, tag, views=None, ss=2, W=1280):
    S = load_sky(path)
    ensure_models(sorted(set(p['model'] for p in S['props'])))
    os.makedirs(out_dir, exist_ok=True)
    g_tris, g_col = main_ground(); k_tris, k_col = main_karst()
    grass = np.array([86, 86, 63.]); grass2 = np.array([86, 83, 60.]); rock = np.array([130, 129, 123.]); moss = np.array([95, 93, 44.])
    mesh_draw = []
    for m in S['meshes']:
        a, b = (rock, moss) if m['cls'] == 'karst' else (grass, grass2)
        bl = m['blend'][:, None]
        mesh_draw.append((m['tris'], (a * (1 - bl) + b * bl) * m['tint'] * 1.15))
    # props grouped per model
    by_model = {}
    for p in S['props']: by_model.setdefault(p['model'], []).append(p)
    H = W * 9 // 16
    for v in VIEWS:
        if views and v['name'] not in views: continue
        eye = view_eye(v)
        for kind, fov in (('wide', 106.26), ('zoom', 106.26 / 4)):
            R = Raster(W * ss, H * ss, eye, v['yaw'], v['pitch'] if kind == 'wide' else v['pitch'] * 0.25 + 1.5, fov)
            R.draw(g_tris, g_col); R.draw(k_tris, k_col)
            for tris, col in mesh_draw: R.draw(tris, col)
            nt = 0
            for mname, plist in by_model.items():
                md = model(mname)
                rad0 = float(np.linalg.norm(np.maximum(np.abs(md['lo']), np.abs(md['hi']))))
                vis = [p for p in plist if R.visible_sphere(p['pos'], rad0 * p['s'])]
                if not vis: continue
                for dw in md['draws']:
                    P = dw['P'].astype(np.float64); I = dw['I']; UVt = dw['UV'][I]
                    tex = texture(dw['material'])
                    foli = 'trunk' not in dw['material']
                    base = np.ones(3) * 255.0 if tex is not None else np.array([70, 100, 50.])
                    batch, bu, bc = [], [], []
                    def flush():
                        if not batch: return
                        T = np.concatenate(batch); U = np.concatenate(bu); C = np.concatenate(bc)
                        R.draw(T, C, uv=U, mat=dw['material'] if tex is not None else None, foliage=foli)
                        batch.clear(); bu.clear(); bc.clear()
                    cnt = 0
                    for p in vis:
                        Wp = (P * p['s']) @ p['R'].T + p['pos']
                        batch.append(Wp[I]); bu.append(UVt); bc.append(np.tile(base * p['rc'], (len(I), 1))); cnt += len(I)
                        if cnt > 1500000: flush(); cnt = 0
                    flush()
                nt += len(vis)
            img = R.image(ss)
            fn = os.path.join(out_dir, '%s_%s_%s.png' % (v['name'], kind, tag))
            img.save(fn)
            print('%s: %d trees in view, %d triangles rasterised -> %s' % (v['name'] + '/' + kind, nt, R.drawn, fn), flush=True)


def compare(out_dir, a, b):
    from PIL import ImageDraw
    for fa in sorted(glob.glob(os.path.join(out_dir, '*_%s.png' % a))):
        fb = fa[:-len(a) - 4] + b + '.png'
        if not os.path.exists(fb): continue
        A = Image.open(fa).convert('RGB'); B = Image.open(fb).convert('RGB')
        d = np.abs(np.asarray(A, np.int16) - np.asarray(B, np.int16)).sum(2)
        D = Image.fromarray(np.clip(d * 3, 0, 255).astype(np.uint8)).convert('RGB')
        w, h = A.size
        sheet = Image.new('RGB', (w, h * 3 + 60), (30, 30, 30)); dr = ImageDraw.Draw(sheet)
        for i, (im, lab) in enumerate(((A, a), (B, b), (D, 'difference x3 (mean %.1f / 765)' % d.mean()))):
            sheet.paste(im, (0, i * (h + 20) + 20)); dr.text((6, i * (h + 20) + 4), lab, fill=(255, 255, 255))
        out = fa[:-len(a) - 4] + 'compare.png'
        sheet.save(out); print(out, 'mean abs diff %.2f' % d.mean())


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if not a: sys.exit(__doc__)
    if a[0] == 'budget': budget(a[1], opt('--json'))
    elif a[0] == 'render':
        vs = opt('--views'); render(a[1], a[2], a[3], vs.split(',') if vs else None, int(opt('--ss', 2)), int(opt('--w', 1280)))
    elif a[0] == 'compare': compare(a[1], a[2], a[3])
    elif a[0] == 'views':
        for v in VIEWS: print(v['name'], view_eye(v), 'yaw', v['yaw'], 'pitch', v['pitch'])
    else: sys.exit(__doc__)
