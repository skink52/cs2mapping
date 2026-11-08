"""Radar / minimap from the map geometry: upward-facing surfaces painted with their material (source texture tiled every 128 units,
or a colour guessed from the material name), darker towards the bottom of the map, higher floors drawn on top, wall edges outlined,
glass translucent, transparent outside. Writes the png + vtex (content) and resource/overviews/<map>.txt (game)."""
import io
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import lighting
import radartex

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

def textures_for(c, tile_units=128.0):
    """Textures from the addon's own source images (content/<addon>/materials, <root>/embedded/<addon>/materials);
    anything else (stock CS2 materials) is painted with a colour guessed from its name."""
    import os
    return radartex.Textures([os.path.join(c.content, 'materials'), os.path.join(c.root, 'embedded', c.addon, 'materials')], tile_units)

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

def run(m, c, size=1024, ss=2, pct=0.5, tex=None, extra_polys=None, slopes=False, open_water=False):   # slopes: also paint steep ground (0.15 < n.z <= 0.6: cliffs between terrain levels) under the floors; open_water: draw water where nothing is under it (open sea), not only over a floor below the water line   # extra_polys: [(material, Nx3 loop)] drawn as floors too (radar_props.py: prop tops)   # pct: percentile trimmed off each edge of the floor extent (0 = keep every floor); tex: radartex.Textures to paint floors with their materials
    polys = list(lighting.world_polys(m)); water = []
    for e in m.entities():                         # solid brush entities (doors, func_brush, breakables...) count too
        if m.cls(e) == 'func_water':               # water surfaces go on as see-through floors (pools show their bottom)
            for ch in m.children(e):
                if m.type(ch) == b'CMapMesh': water.extend(lighting.mesh_polys(m, ch))
            continue
        if m.cls(e).startswith(('trigger_', 'func_buyzone', 'func_bomb_target', 'visibility')): continue
        for ch in m.children(e):
            if m.type(ch) == b'CMapMesh': polys.extend(lighting.mesh_polys(m, ch))
    nworld = len(polys)
    if extra_polys: polys.extend(extra_polys)
    floors, walls, steep = [], [], []
    for k, (mat, loop) in enumerate(polys):
        if any(s in mat for s in SKIP) or len(loop) < 3: continue
        P = np.array(loop)
        Q = np.roll(P, -1, axis=0)                     # Newell normal: right for concave faces and collinear first vertices
        n = np.array([((P[:, 1] - Q[:, 1]) * (P[:, 2] + Q[:, 2])).sum(), ((P[:, 2] - Q[:, 2]) * (P[:, 0] + Q[:, 0])).sum(), ((P[:, 0] - Q[:, 0]) * (P[:, 1] + Q[:, 1])).sum()])
        ln = np.linalg.norm(n)
        if ln < 1e-6: continue
        n /= ln
        if n[2] > 0.6: floors.append((mat, P))
        elif slopes and n[2] > 0.15: steep.append((mat, P))
        elif abs(n[2]) < 0.3 and k < nworld: walls.append(P)
    if not floors: return
    if tex is None and getattr(c, 'textures', None): tex = c.textures
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
            if kept: floors = kept
    # water: func_water tops and floors with a water material. Their meshes are usually boxes far bigger than the water you
    # can see, so they're drawn only where the top floor under them (terrain, pool bottom, props) is below the water line.
    wfaces = [f for f in floors if 'water' in f[0].lower()]
    floors = [f for f in floors if 'water' not in f[0].lower()]
    for mat, loop in water:
        if len(loop) < 3: continue
        P = np.array(loop); Q = np.roll(P, -1, axis=0)
        nz = ((P[:, 0] - Q[:, 0]) * (P[:, 1] + Q[:, 1])).sum()
        if abs(nz) / 2 > 1 and nz > 0 and not any(x in mat for x in SKIP): wfaces.append(('water:' + mat, P))   # a nodraw top is no visible surface
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
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    Zb = np.full((S, S), -1e9, np.float32)        # height of the top surface at each pixel (interpolated across each face), for the water line
    for mat, P in sorted(steep, key=lambda f: f[1][:, 2].mean()):   # steep ground first: the floors cover it where they overlap
        t = float(np.clip((P[:, 2].mean() - zlo) / max(zhi - zlo, 1), 0, 1))
        if wfaces: raster_z(Zb, to_img(P), P[:, 2])
        if tex is None: d.polygon(to_img(P), fill=(int(60 + 100 * t), int(65 + 100 * t), int(75 + 105 * t), 255)); continue
        paint_face(img, to_img(P), P, mat, t * 0.8, tex, px, py, scale, ss)
    for mat, P in sorted(floors, key=lambda f: f[1][:, 2].mean()):
        t = float(np.clip((P[:, 2].mean() - zlo) / max(zhi - zlo, 1), 0, 1))
        if wfaces: raster_z(Zb, to_img(P), P[:, 2])
        if tex is None:
            col = (int(70 + 120 * t), int(80 + 120 * t), int(95 + 125 * t), 255)
            d.polygon(to_img(P), fill=col); continue
        paint_face(img, to_img(P), P, mat, t, tex, px, py, scale, ss)
    wstat = []
    if wfaces:
        Z = Zb
        for mat, P in sorted(wfaces, key=lambda f: f[1][:, 2].mean()):
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

def paint_face(img, pts, P, mat, t, tex, px, py, scale, ss):
    """Fill one floor polygon with its material: the source texture tiled every tex.tile world units (world-aligned, so
    neighbouring faces line up), or a flat guessed colour, darkened towards the bottom of the map (0.55..1.05 by height)."""
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
