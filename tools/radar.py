"""Radar / minimap from the map geometry: upward-facing surfaces shaded by height (higher = lighter, drawn on top),
wall edges outlined, transparent outside. Writes the png + vtex (content) and resource/overviews/<map>.txt (game)."""
import io
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import lighting

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
SKIP = ('materials/tools/', 'moondome', 'skybox')

def run(m, c, size=1024, ss=2, pct=0.5):   # pct: percentile trimmed off each edge of the floor extent (0 = keep every floor)
    polys = list(lighting.world_polys(m))
    for e in m.entities():                         # solid brush entities (doors, func_brush, breakables...) count too
        if m.cls(e).startswith(('trigger_', 'func_buyzone', 'func_bomb_target', 'func_water', 'visibility')): continue
        for ch in m.children(e):
            if m.type(ch) == b'CMapMesh': polys.extend(lighting.mesh_polys(m, ch))
    floors, walls = [], []
    for mat, loop in polys:
        if any(s in mat for s in SKIP) or len(loop) < 3: continue
        P = np.array(loop)
        n = np.cross(P[1] - P[0], P[2] - P[0]); ln = np.linalg.norm(n)
        if ln < 1e-6: continue
        n /= ln
        if n[2] > 0.6: floors.append(P)
        elif abs(n[2]) < 0.3: walls.append(P)
    if not floors: return
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
            kept = [P for P in floors if ok(lab_at(P.mean(0) + [0, 0, 40]))]
            if kept: floors = kept
    allp = np.concatenate(floors)
    lo = np.percentile(allp, pct, axis=0); hi = np.percentile(allp, 100 - pct, axis=0)
    span = max(hi[0] - lo[0], hi[1] - lo[1]) * 1.06 + 256
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    px, py = cx - span / 2, cy + span / 2
    scale = span / size
    S = size * ss
    def to_img(P): return [((x - px) / scale * ss, (py - y) / scale * ss) for x, y in P[:, :2]]
    zlo, zhi = np.percentile(allp[:, 2], 2), np.percentile(allp[:, 2], 98)
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    for P in sorted(floors, key=lambda P: P[:, 2].mean()):
        t = float(np.clip((P[:, 2].mean() - zlo) / max(zhi - zlo, 1), 0, 1))
        col = (int(70 + 120 * t), int(80 + 120 * t), int(95 + 125 * t), 255)
        d.polygon(to_img(P), fill=col)
    edge = Image.new('RGBA', (S, S), (0, 0, 0, 0)); de = ImageDraw.Draw(edge)
    for P in walls:
        if P[:, 2].max() - P[:, 2].min() < 40: continue        # skip low lips and steps
        pts = to_img(P)
        de.line(pts + [pts[0]], fill=(20, 22, 28, 255), width=max(1, ss))
    img = Image.alpha_composite(img, edge).resize((size, size), Image.LANCZOS)
    b = io.BytesIO(); img.save(b, 'PNG')
    c.write('panorama/images/overheadmaps/%s_radar_psd.png' % c.addon, b.getvalue())
    c.write('panorama/images/overheadmaps/%s_radar_psd.vtex' % c.addon, VTEX % dict(map=c.addon))
    def frac(cls):
        es = m.by_class(cls)
        if not es: return 0.5, 0.5
        o = np.mean([m.origin(e)[:2] for e in es], axis=0)
        return float(np.clip((o[0] - px) / span, 0, 1)), float(np.clip((py - o[1]) / span, 0, 1))
    ctx, cty = frac('info_player_counterterrorist'); tx, ty = frac('info_player_terrorist')
    c.game_files['resource/overviews/%s.txt' % c.addon] = (OVERVIEW % dict(map=c.addon, px=px, py=py, scale=scale, ctx=ctx, cty=cty, tx=tx, ty=ty)).encode()
    c.log.append('radar: rendered from geometry (%d floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/%s_radar_psd.png + game resource/overviews/%s.txt (pos %d %d, scale %.2f)'
                 % (len(floors), c.addon, c.addon, px, py, scale))
