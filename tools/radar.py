"""Radar / minimap from the map geometry: upward-facing surfaces painted with their material (source texture tiled every 128 units,
or a colour guessed from the material name), darker towards the bottom of the map, higher floors drawn on top, wall edges outlined,
glass translucent, transparent outside. Writes the png + vtex (content) and resource/overviews/<map>.txt (game)."""
import io
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import lighting
import radartex
import dmx

VTEX = '''<!-- dmx encoding keyvalues2_noids 1 format vtex 1 -->
"CDmeVtex"
{
    "m_inputTextureArray" "element_array"
    [
        "CDmeInputTexture"
        {
            "m_name" "string" "SheetTexture"
            "m_fileName" "string" "panorama/images/overheadmaps/%(map)s_radar_psd.png"
            "m_colorSpace" "string" "srgb"
            "m_typeString" "string" "2D"
            "m_imageProcessorArray" "element_array"
            [
            ]
        }
    ]
    "m_outputTypeString" "string" "2D"
    "m_outputFormat" "string" "BC7"
    "m_outputClearColor" "vector4" "0 0 0 0"
    "m_nOutputMinDimension" "int" "0"
    "m_nOutputMaxDimension" "int" "1024"
    "m_textureOutputChannelArray" "element_array"
    [
        "CDmeTextureOutputChannel"
        {
            "m_inputTextureArray" "string_array"
            [
                "SheetTexture"
            ]
            "m_srcChannels" "string" "rgba"
            "m_dstChannels" "string" "rgba"
            "m_mipAlgorithm" "CDmeImageProcessor"
            {
                "m_algorithm" "string" ""
                "m_stringArg" "string" ""
                "m_vFloat4Arg" "vector4" "0 0 0 0"
            }
            "m_outputColorSpace" "string" "srgb"
        }
    ]
    "m_vClamp" "vector3" "0 0 0"
    "m_bNoLod" "bool" "1"
}
'''
OVERVIEW = '''// Overview (radar) description for %(map)s: rendered from the map geometry (floors shaded by height)
// Radar image: content\\csgo_addons\\%(map)s\\panorama\\images\\overheadmaps\\%(map)s_radar_psd.png

"%(map)s"
{
	"material"	"overviews/%(map)s_radar"	// texture file
	"pos_x"		"%(px)d"	// upper left world coordinate
	"pos_y"		"%(py)d"
	"scale"		"%(scale).2f"
	"rotate"	"0"
	"zoom"		"1.0"

	// loading screen icons and positions
	"CTSpawn_x"	"%(ctx).2f"
	"CTSpawn_y"	"%(cty).2f"
	"TSpawn_x"	"%(tx).2f"
	"TSpawn_y"	"%(ty).2f"
}
'''
SKIP = ('materials/tools/', 'moondome', 'skybox', 'materials/spotlights/', 'materials/lasers/')   # beams aren't floors or walls

def cs2_vpks(c=None):
    """CS2's pak01 directories for stock textures: <root>/vpk/cs2_pak01_dir.vpk (cloud workspace), else the CS2 install
    (CS2_ROOT or the default Steam path) game/csgo and game/core."""
    import os
    out = []
    if c is not None: out.append(os.path.join(c.root, 'vpk', 'cs2_pak01_dir.vpk'))
    root = os.environ.get('CS2_ROOT') or r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
    out += [os.path.join(root, 'game', 'csgo', 'pak01_dir.vpk'), os.path.join(root, 'game', 'core', 'pak01_dir.vpk')]
    return [v for v in out if os.path.isfile(v)]

def textures_for(c, tile_units=128.0):
    """Textures from the addon's own source images (content/<addon>/materials, <root>/embedded/<addon>/materials), then
    stock CS2 textures from the VPKs (cs2_vpks); anything unreadable is painted with a colour guessed from its name."""
    import os
    return radartex.Textures([os.path.join(c.content, 'materials'), os.path.join(c.root, 'embedded', c.addon, 'materials')], tile_units, cs2_vpks(c))

def mesh_faces(m, node):
    """[(material, [p0, ...], corners)] for a CMapMesh in world space, like lighting.mesh_polys plus each corner's face-vertex
    data: corners = {'uv': Nx2, 'blend': Nx4 or None, 'tint': Nx3 or None}. A half-edge's face-vertex data belongs to the
    vertex it points to (edgeVertexIndices), the same corner the position loop uses (checked on ba_jail_seaside, 10 Nov 2026)."""
    md = m.g(node, b'meshData')
    if md is None: return []
    E = m.E
    get = lambda k: dmx.get(E[md], k)
    vdi, evi, eni, fei, fdi, evd = (get(k) for k in (b'vertexDataIndices', b'edgeVertexIndices', b'edgeNextIndices', b'faceEdgeIndices', b'faceDataIndices', b'edgeVertexDataIndices'))
    mats = [x.decode().lower() for x in get(b'materials') or []]
    pos = matidx = None; fv = {}
    for st in dmx.get(E[get(b'vertexData')], b'streams'):
        if E[st]['name'].startswith(b'position'): pos = dmx.get(E[st], b'data')
    for st in dmx.get(E[get(b'faceData')], b'streams'):
        if E[st]['name'].startswith(b'materialindex'): matidx = dmx.get(E[st], b'data')
    if get(b'faceVertexData') is not None:
        for st in dmx.get(E[get(b'faceVertexData')], b'streams'):
            fv[E[st]['name']] = dmx.get(E[st], b'data')
    if pos is None or not fei: return []
    uvs, bps, tcs = fv.get(b'texcoord:0'), fv.get(b'VertexPaintBlendParams:0'), fv.get(b'VertexPaintTintColor:0')
    o = m.g(node, b'origin', [0, 0, 0])
    out = []
    for f, e0 in enumerate(fei):
        loop = []; es = []; e = e0
        for _ in range(4096):
            v = evi[e]; p = pos[vdi[v]]; loop.append((p[0] + o[0], p[1] + o[1], p[2] + o[2])); es.append(e)
            e = eni[e]
            if e == e0: break
        mi = matidx[fdi[f]] if matidx else 0
        corners = None
        if uvs is not None and evd:
            ix = [evd[k] for k in es]
            corners = {'uv': np.array([uvs[i] for i in ix], np.float64),
                       'blend': np.array([bps[i] for i in ix], np.float64) if bps is not None else None,
                       'tint': np.array([tcs[i][:3] for i in ix], np.float64) if tcs is not None else None}
        out.append((mats[mi] if mi < len(mats) else '', loop, corners))
    return out

def world_faces(m):
    out = []
    def walk(n):
        for ch in m.children(n):
            t = m.type(ch)
            if t == b'CMapMesh': out.extend(mesh_faces(m, ch))
            elif t == b'CMapGroup': walk(ch)
    walk(m.world)
    return out

def raster_z(Z, pts, zs):
    """Raise the height map Z (pixels) to the face's interpolated height wherever the face covers a pixel (fan triangles)."""
    H, W = Z.shape
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[0], pts[i], pts[i + 1]
        z0, z1, z2 = zs[0], zs[i], zs[i + 1]
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(d) < 1e-9: continue
        bx0, bx1 = max(int(min(x0, x1, x2)), 0), min(int(max(x0, x1, x2)) + 1, W)
        by0, by1 = max(int(min(y0, y1, y2)), 0), min(int(max(y0, y1, y2)) + 1, H)
        if bx0 >= bx1 or by0 >= by1: continue
        X, Y = np.meshgrid(np.arange(bx0, bx1) + 0.5, np.arange(by0, by1) + 0.5)
        a = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / d
        b = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / d
        g = 1 - a - b
        ins = (a >= -1e-3) & (b >= -1e-3) & (g >= -1e-3)
        if not ins.any(): continue
        z = a * z0 + b * z1 + g * z2
        blk = Z[by0:by1, bx0:bx1]
        np.maximum(blk, np.where(ins, z, -1e9), out=blk)

def run(m, c, size=1024, ss=2, pct=0.5, tex=None, extra_polys=None, slopes=False, open_water=False, keep_mats=()):   # keep_mats: material name parts whose floors are drawn even when they fail the standable test (scenery such as ba_jail_seaside's beach); they never widen the radar extent   # slopes: also paint steep ground (0.15 < n.z <= 0.6: cliffs between terrain levels) under the floors; open_water: draw water where nothing is under it (open sea), not only over a floor below the water line   # extra_polys: [(material, Nx3 loop)] drawn as floors too (radar_props.py: prop tops)   # pct: percentile trimmed off each edge of the floor extent (0 = keep every floor); tex: radartex.Textures to paint floors with their materials
    polys = world_faces(m); water = []
    for e in m.entities():                         # solid brush entities (doors, func_brush, breakables...) count too
        if m.cls(e) == 'func_water':               # water surfaces go on as see-through floors (pools show their bottom)
            for ch in m.children(e):
                if m.type(ch) == b'CMapMesh': water.extend(mesh_faces(m, ch))
            continue
        if m.cls(e).startswith(('trigger_', 'func_buyzone', 'func_bomb_target', 'visibility')): continue
        for ch in m.children(e):
            if m.type(ch) == b'CMapMesh': polys.extend(mesh_faces(m, ch))
    nworld = len(polys)
    if extra_polys: polys.extend((mat, loop, None) for mat, loop in extra_polys)
    floors, walls, steep = [], [], []
    for k, (mat, loop, corners) in enumerate(polys):
        if (any(s in mat for s in SKIP) and not any(k in mat for k in keep_mats)) or len(loop) < 3: continue   # keep_mats beats SKIP (hr_sand_skybox_beach is sand, not sky)
        P = np.array(loop)
        Q = np.roll(P, -1, axis=0)                     # Newell normal: right for concave faces and collinear first vertices
        n = np.array([((P[:, 1] - Q[:, 1]) * (P[:, 2] + Q[:, 2])).sum(), ((P[:, 2] - Q[:, 2]) * (P[:, 0] + Q[:, 0])).sum(), ((P[:, 0] - Q[:, 0]) * (P[:, 1] + Q[:, 1])).sum()])
        ln = np.linalg.norm(n)
        if ln < 1e-6: continue
        n /= ln
        if n[2] > 0.6: floors.append((mat, P, corners))
        elif slopes and n[2] > 0.15: steep.append((mat, P, corners))
        elif abs(n[2]) < 0.3 and k < nworld: walls.append(P)
    if not floors: return
    if tex is None and getattr(c, 'textures', None): tex = c.textures
    forced = []
    # keep only floors you can stand on: the space just above them must be a room with lights / spawns / teleports in it
    # (stops the outside tops of roofs and the sky shell covering the floors underneath)
    wp = lighting.world_polys(m)
    if wp:
        vs = 32.0
        solid, vlo = lighting.voxelise(wp, vs); lab, n = lighting.label_empty(solid)
        shape = np.array(solid.shape)
        def lab_at(p):
            i = np.floor((np.array(p) - vlo) / vs).astype(int)
            if (i < 0).any() or (i >= shape).any(): return 0
            return lab[tuple(i)]
        def lab_near(p):
            for dz in (0, 32, -32, 64):
                l = lab_at([p[0], p[1], p[2] + dz])
                if l: return l
            return 0
        play = set()
        for e in m.by_class(*lighting.LIGHT_CLASSES) + m.by_class('info_player_terrorist', 'info_player_counterterrorist', 'info_teleport_destination', 'info_deathmatch_spawn'):
            l = lab_near(m.origin(e))
            if l: play.add(l)
        from scipy import ndimage
        ext = set(np.unique(np.concatenate([lab[0].ravel(), lab[-1].ravel(), lab[:, 0].ravel(), lab[:, -1].ravel(), lab[:, :, 0].ravel(), lab[:, :, -1].ravel()])))
        skyl = set(np.unique(lab[ndimage.binary_dilation(solid == 2) & (lab > 0)]))
        ok = lambda l: l in play or (l and l not in ext and l not in skyl)
        if play:
            def face_ok(P):                        # the centroid alone misses faces with a prop or wall on that one spot
                c0 = P.mean(0)
                return any(ok(lab_at(q + [0, 0, 40])) for q in [c0] + [(c0 + v) / 2 for v in P])
            kept = [f for f in floors if face_ok(f[1])]
            if kept:
                ids = set(map(id, kept))
                forced = [f for f in floors if id(f) not in ids and any(k in f[0] for k in keep_mats)]
                floors = kept
    # water: func_water tops and floors with a water material. Their meshes are usually boxes far bigger than the water you
    # can see, so they're drawn only where the top floor under them (terrain, pool bottom, props) is below the water line.
    wfaces = [f for f in floors if 'water' in f[0].lower()]
    floors = [f for f in floors if 'water' not in f[0].lower()]
    for mat, loop, _ in water:
        if len(loop) < 3: continue
        P = np.array(loop); Q = np.roll(P, -1, axis=0)
        nz = ((P[:, 0] - Q[:, 0]) * (P[:, 1] + Q[:, 1])).sum()
        if abs(nz) / 2 > 1 and nz > 0 and not any(x in mat for x in SKIP): wfaces.append(('water:' + mat, P, None))   # a nodraw top is no visible surface
    land = floors or wfaces                        # a sea plane shouldn't set the map extent
    allp = np.concatenate([f[1] for f in land])
    lo = np.percentile(allp, pct, axis=0); hi = np.percentile(allp, 100 - pct, axis=0)
    span = max(hi[0] - lo[0], hi[1] - lo[1]) * 1.06 + 256
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    px, py = cx - span / 2, cy + span / 2
    scale = span / size
    S = size * ss
    def to_img(P): return [((x - px) / scale * ss, (py - y) / scale * ss) for x, y in P[:, :2]]
    zlo, zhi = np.percentile(allp[:, 2], 2), np.percentile(allp[:, 2], 98)
    floors = floors + forced                       # kept scenery: drawn, but after the extent is set
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    Zb = np.full((S, S), -1e9, np.float32)        # height of the top surface at each pixel (interpolated across each face), for the water line
    for mat, P, cn in sorted(steep, key=lambda f: f[1][:, 2].mean()):   # steep ground first: the floors cover it where they overlap
        t = float(np.clip((P[:, 2].mean() - zlo) / max(zhi - zlo, 1), 0, 1))
        if wfaces: raster_z(Zb, to_img(P), P[:, 2])
        if tex is None: d.polygon(to_img(P), fill=(int(60 + 100 * t), int(65 + 100 * t), int(75 + 105 * t), 255)); continue
        paint_face(img, to_img(P), P, mat, t * 0.8, tex, px, py, scale, ss, cn)
    for mat, P, cn in sorted(floors, key=lambda f: f[1][:, 2].mean()):
        t = float(np.clip((P[:, 2].mean() - zlo) / max(zhi - zlo, 1), 0, 1))
        if wfaces: raster_z(Zb, to_img(P), P[:, 2])
        if tex is None:
            col = (int(70 + 120 * t), int(80 + 120 * t), int(95 + 125 * t), 255)
            d.polygon(to_img(P), fill=col); continue
        paint_face(img, to_img(P), P, mat, t, tex, px, py, scale, ss, cn)
    wstat = []
    if wfaces:
        Z = Zb
        for mat, P, _ in sorted(wfaces, key=lambda f: f[1][:, 2].mean()):
            wz = float(P[:, 2].max())
            area = Image.new('L', (S, S), 0); ImageDraw.Draw(area).polygon(to_img(P), fill=255)
            inside = np.asarray(area) > 0
            vis = inside & (Z <= wz + 2) & ((Z > -1e8) | open_water)    # a floor under it (or open sea), nothing standing above the water line
            wstat.append('%s z%d %d%%' % (mat.split('/')[-1].replace('.vmat', ''), wz, 100 * vis.sum() / max(inside.sum(), 1)))
            if not vis.any(): continue
            ys, xs = np.nonzero(vis); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            t = float(np.clip((wz - zlo) / max(zhi - zlo, 1), 0, 1))
            tile, _ = (tex.get(mat, 4) if tex is not None else (np.array([[[40, 90, 130]]], np.uint8), False))
            col = np.clip(tile.reshape(-1, 3).mean(0) * (0.55 + 0.5 * t), 0, 255).astype(np.uint8)
            patch = Image.new('RGBA', (int(x1 - x0), int(y1 - y0)), tuple(int(v) for v in col) + (255,))
            mask = Image.fromarray((vis[y0:y1, x0:x1] * 190).astype(np.uint8), 'L')
            img.paste(patch, (int(x0), int(y0)), mask)
    edge = Image.new('RGBA', (S, S), (0, 0, 0, 0)); de = ImageDraw.Draw(edge)
    for P in walls:
        if P[:, 2].max() - P[:, 2].min() < 40: continue        # skip low lips and steps
        pts = to_img(P)
        de.line(pts + [pts[0]], fill=(20, 22, 28, 255), width=max(1, ss))
    img = Image.alpha_composite(img, edge).resize((size, size), Image.LANCZOS)
    b = io.BytesIO(); img.save(b, 'PNG')
    c.write('panorama/images/overheadmaps/%s_radar_psd.png' % c.addon, b.getvalue())
    c.write('panorama/images/overheadmaps/%s_radar_psd.vtex' % c.addon, VTEX.replace('"int" "1024"', '"int" "%d"' % max(1024, size)) % dict(map=c.addon))
    def frac(cls):
        es = m.by_class(cls)
        if not es: return 0.5, 0.5
        o = np.mean([m.origin(e)[:2] for e in es], axis=0)
        return float(np.clip((o[0] - px) / span, 0, 1)), float(np.clip((py - o[1]) / span, 0, 1))
    ctx, cty = frac('info_player_counterterrorist'); tx, ty = frac('info_player_terrorist')
    c.game_files['resource/overviews/%s.txt' % c.addon] = (OVERVIEW % dict(map=c.addon, px=px, py=py, scale=scale, ctx=ctx, cty=cty, tx=tx, ty=ty)).encode()
    if wstat: c.log.append('radar water (share of each water face drawn): ' + ', '.join(wstat))
    c.log.append('radar: rendered from geometry (%d floor faces shaded by height, ' % len(floors) + ('%d steep faces under them, ' % len(steep) if slopes else '') + 'walls outlined) -> panorama/images/overheadmaps/%s_radar_psd.png + game resource/overviews/%s.txt (pos %d %d, scale %.2f)'
                 % (c.addon, c.addon, px, py, scale))

def paint_face(img, pts, P, mat, t, tex, px, py, scale, ss, corners=None):
    """Fill one floor polygon with its material, darkened towards the bottom of the map (0.55..1.05 by height).
    With the face's corner data (texcoords) and a readable texture, the texture is mapped by the face's own UVs; a blend
    material mixes its layers by the painted blend weights (layer 2 by x, 3 by y, 4 by z, in turn) and the painted tint
    multiplies it. Otherwise: the source texture tiled every tex.tile world units (world-aligned), or a flat guessed colour."""
    if corners is not None and paint_face_uv(img, pts, mat, t, tex, corners): return
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, y0 = int(np.floor(min(xs))), int(np.floor(min(ys))); x1, y1 = int(np.ceil(max(xs))) + 1, int(np.ceil(max(ys))) + 1
    x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, img.width), min(y1, img.height)
    if x1 <= x0 or y1 <= y0: return
    ppt = tex.tile / scale * ss                       # pixels per texture tile
    tile, is_tex = tex.get(mat, ppt)
    w, h = x1 - x0, y1 - y0
    if is_tex:
        n = tile.shape[0]
        # world x -> pixel column; tile origin at world 0 so faces share the pattern
        ox = ((-px) / scale * ss) % n; oy = ((py) / scale * ss) % n
        ix = ((np.arange(x0, x1) + ox) % n).astype(int); iy = ((np.arange(y0, y1) + oy) % n).astype(int)
        fill = tile[iy][:, ix].astype(np.float32)
    else:
        fill = np.broadcast_to(tile.astype(np.float32), (h, w, 3)).copy()
    fill *= 0.55 + 0.5 * t
    fill = np.clip(fill, 0, 255).astype(np.uint8)
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).polygon([(x - x0, y - y0) for x, y in pts], fill=90 if 'glass' in mat.lower() else 255)   # glass: see the floor below
    patch = Image.fromarray(fill, 'RGB').convert('RGBA')
    img.paste(patch, (x0, y0), mask)

def _area(Q):
    Q = np.asarray(Q, np.float64)
    return 0.5 * abs(np.dot(Q[:, 0], np.roll(Q[:, 1], -1)) - np.dot(Q[:, 1], np.roll(Q[:, 0], -1)))

def paint_face_uv(img, pts, mat, t, tex, corners):
    """paint_face by texcoords and blend paint; False when the face can't be painted this way (no texture, degenerate UVs)."""
    uv = corners['uv']
    apx, auv = _area(pts), _area(uv)
    if apx < 1 or auv < 1e-9: return False
    ppu = float(np.sqrt(apx / auv))                    # image pixels per texture repeat
    n = int(2 ** np.clip(np.round(np.log2(max(ppu, 4))), 2, 9))
    tiles = tex.get_layers(mat, n)
    if not tiles: return False
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, y0 = max(int(np.floor(min(xs))), 0), max(int(np.floor(min(ys))), 0)
    x1, y1 = min(int(np.ceil(max(xs))) + 1, img.width), min(int(np.ceil(max(ys))) + 1, img.height)
    if x1 <= x0 or y1 <= y0: return True
    w, h = x1 - x0, y1 - y0
    X, Y = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
    inside = np.zeros((h, w), bool); U = np.zeros((h, w)); V = np.zeros((h, w))
    B = corners['blend']; T = corners['tint']
    nb = min(len(tiles) - 1, 3) if B is not None else 0
    W = np.zeros((h, w, max(nb, 1))); TT = np.ones((h, w, 3))
    for i in range(1, len(pts) - 1):                   # fan triangles, barycentric interpolation of every corner value
        (ax, ay), (bx, by), (cx, cy) = pts[0], pts[i], pts[i + 1]
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-9: continue
        a = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / d
        b = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / d
        g = 1 - a - b
        ins = (a >= -1e-3) & (b >= -1e-3) & (g >= -1e-3) & ~inside
        if not ins.any(): continue
        k = (0, i, i + 1)
        U[ins] = (a * uv[k[0], 0] + b * uv[k[1], 0] + g * uv[k[2], 0])[ins]
        V[ins] = (a * uv[k[0], 1] + b * uv[k[1], 1] + g * uv[k[2], 1])[ins]
        for j in range(nb): W[..., j][ins] = (a * B[k[0], j] + b * B[k[1], j] + g * B[k[2], j])[ins]
        if T is not None:
            for j in range(3): TT[..., j][ins] = (a * T[k[0], j] + b * T[k[1], j] + g * T[k[2], j])[ins]
        inside |= ins
    if not inside.any(): return True
    iu = np.floor(U * n).astype(np.int64) % n; iv = np.floor(V * n).astype(np.int64) % n
    fill = tiles[0][iv, iu].astype(np.float32)
    for j in range(nb):
        wj = np.clip(W[..., j], 0, 1)[..., None].astype(np.float32)
        fill = fill * (1 - wj) + tiles[j + 1][iv, iu].astype(np.float32) * wj
    fill *= TT.astype(np.float32)
    fill *= 0.55 + 0.5 * t
    fill = np.clip(fill, 0, 255).astype(np.uint8)
    mask = Image.fromarray((inside * (90 if 'glass' in mat.lower() else 255)).astype(np.uint8), 'L')
    img.paste(Image.fromarray(fill, 'RGB').convert('RGBA'), (x0, y0), mask)
    return True
