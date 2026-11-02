"""FreeDM level -> CS2 converter.

For every map: static geometry chunks + one rigid block model per moving floor/ceiling,
.vmat materials (unlit, tinted per Doom light level), 4x upscaled textures, and the level data
the cs_script game needs (vertices, lines, sectors, BSP nodes, things, movers).
"""
import os, sys, json, math
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import assets
from wad import load_map

ZS = 1.2            # Doom's tall pixels
UPS = 4             # texture upscale factor
CHUNK = 1024
ADDON_MAT = 'materials/fdm'
LEVELS = os.path.join(assets.FD, 'levels')

ML_BLOCKING, ML_TWOSIDED, ML_DONTPEGTOP, ML_DONTPEGBOTTOM = 1, 4, 8, 16

# ---------------------------------------------------------------- specials -> what moves
MANUAL_DOORS = {1, 26, 27, 28, 31, 32, 33, 34, 117, 118}
DOOR_TAG = {2, 3, 4, 16, 29, 42, 46, 50, 61, 63, 75, 76, 86, 90, 99, 103, 105, 106, 107, 108, 109, 110,
            111, 112, 113, 114, 115, 116, 133, 134, 135, 136, 137}
CEIL_TAG = {6, 25, 41, 43, 44, 49, 72, 73, 74, 77, 141, 40, 57}
LIFT_TAG = {10, 21, 62, 88, 120, 121, 122, 123, 53, 87, 54, 89, 14, 15, 20, 22, 47, 66, 67, 68, 95}
FLOOR_TAG = {5, 18, 19, 23, 24, 30, 36, 37, 38, 45, 55, 56, 58, 59, 60, 64, 65, 69, 70, 71, 82, 83, 84,
             91, 92, 93, 94, 96, 98, 101, 102, 119, 128, 129, 130, 131, 132, 140, 9}
RAISE_TO_CEIL = {5, 24, 64, 91, 101, 55, 56, 65, 94}
STAIRS = {7, 8, 100, 127}


# Doom's texture animations (P_InitPicAnims): every frame lasts 8 tics
ANIM_FLATS = [['NUKAGE1', 'NUKAGE2', 'NUKAGE3'], ['FWATER1', 'FWATER2', 'FWATER3', 'FWATER4'],
              ['SWATER1', 'SWATER2', 'SWATER3', 'SWATER4'], ['LAVA1', 'LAVA2', 'LAVA3', 'LAVA4'],
              ['BLOOD1', 'BLOOD2', 'BLOOD3'], ['RROCK05', 'RROCK06', 'RROCK07', 'RROCK08'],
              ['SLIME01', 'SLIME02', 'SLIME03', 'SLIME04'], ['SLIME05', 'SLIME06', 'SLIME07', 'SLIME08'],
              ['SLIME09', 'SLIME10', 'SLIME11', 'SLIME12']]
ANIM_WALLS = [['BLODGR1', 'BLODGR2', 'BLODGR3', 'BLODGR4'], ['SLADRIP1', 'SLADRIP2', 'SLADRIP3'],
              ['BLODRIP1', 'BLODRIP2', 'BLODRIP3', 'BLODRIP4'], ['FIREWALA', 'FIREWALB', 'FIREWALL'],
              ['GSTFONT1', 'GSTFONT2', 'GSTFONT3'], ['FIRELAV3', 'FIRELAVA'], ['FIREMAG1', 'FIREMAG2', 'FIREMAG3'],
              ['FIREBLU1', 'FIREBLU2'], ['ROCKRED1', 'ROCKRED2', 'ROCKRED3'], ['BFALL1', 'BFALL2', 'BFALL3', 'BFALL4'],
              ['SFALL1', 'SFALL2', 'SFALL3', 'SFALL4'], ['WFALL1', 'WFALL2', 'WFALL3', 'WFALL4'],
              ['DBRAIN1', 'DBRAIN2', 'DBRAIN3', 'DBRAIN4']]
ANIM_TICS = 8
ANIM = {}
for _kind, _groups in (('f', ANIM_FLATS), ('w', ANIM_WALLS)):
    for _frames in _groups:
        for _i, _n in enumerate(_frames):
            ANIM[(_kind, _n)] = (_frames[0], _frames, _i)


def anim_of(kind, name):
    """(group name, frames, index of this frame) for an animated texture, else None"""
    a = ANIM.get((kind, name.upper()))
    if not a: return None
    exists = assets.texture if kind == 'w' else assets.flat
    if any(exists(f) is None for f in a[1]): return None
    return a


def pot(n):
    k = 1
    while k < n: k *= 2
    return k


def classify_movers(m):
    nsec = len(m['sectors'])
    floor_mv, ceil_mv = set(), set()
    raise_ceil = set()
    tags = {}
    for i, s in enumerate(m['sectors']):
        tags.setdefault(s['tag'], []).append(i)
    for l in m['lines']:
        sp = l['special']
        if not sp: continue
        if sp in MANUAL_DOORS:
            if l['s2'] >= 0:
                ceil_mv.add(m['sides'][l['s2']]['sector'])
            continue
        tgt = tags.get(l['tag'], []) if l['tag'] else []
        if sp in DOOR_TAG or sp in CEIL_TAG:
            ceil_mv.update(tgt)
        elif sp in LIFT_TAG or sp in FLOOR_TAG or sp in STAIRS:
            floor_mv.update(tgt)
            if sp in RAISE_TO_CEIL: raise_ceil.update(tgt)
            if sp == 9:  # donut: also the surrounding ring
                pass
    # stairs: follow the chain (sectors sharing the same floor texture, front->back)
    return floor_mv, ceil_mv, raise_ceil


def neighbours(m):
    nb = [set() for _ in m['sectors']]
    for l in m['lines']:
        if l['s1'] >= 0 and l['s2'] >= 0:
            a = m['sides'][l['s1']]['sector']; b = m['sides'][l['s2']]['sector']
            if a != b: nb[a].add(b); nb[b].add(a)
    return nb


def height_ranges(m, floor_mv, ceil_mv, raise_ceil):
    S = m['sectors']; nb = neighbours(m)
    fr, cr = [], []
    for i, s in enumerate(S):
        f0, c0 = s['floor'], s['ceil']
        fmin = fmax = f0; cmin = cmax = c0
        if i in floor_mv:
            nf = [S[j]['floor'] for j in nb[i]] or [f0]
            nc = [S[j]['ceil'] for j in nb[i]] or [c0]
            fmin = min(f0, min(nf)); fmax = max(f0, max(nf))
            if i in raise_ceil: fmax = max(fmax, min(nc + [c0]), c0)
        if i in ceil_mv:
            nc = [S[j]['ceil'] for j in nb[i]] or [c0]
            cmin = min(c0, f0); cmax = max(c0, max(nc))
        fr.append((fmin, fmax)); cr.append((cmin, cmax))
    return fr, cr


# ---------------------------------------------------------------- geometry helpers
def clip(poly, a, b, c, eps=1e-6):
    """keep points where a*x + b*y + c <= eps"""
    out = []
    n = len(poly)
    for i in range(n):
        p = poly[i]; q = poly[(i + 1) % n]
        dp = a * p[0] + b * p[1] + c; dq = a * q[0] + b * q[1] + c
        if dp <= eps: out.append(p)
        if (dp <= eps) != (dq <= eps):
            t = dp / (dp - dq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def side_plane(x, y, dx, dy):
    # right side of direction (dx,dy) through (x,y): dx*(py-y) - dy*(px-x) <= 0
    # -> a*px + b*py + c <= 0 with a = -dy, b = dx, c = dy*x - dx*y
    return -dy, dx, dy * x - dx * y


def subsector_polys(m):
    V = m['verts']
    xs = [v[0] for v in V]; ys = [v[1] for v in V]
    B = 256
    box = [(min(xs) - B, min(ys) - B), (max(xs) + B, min(ys) - B), (max(xs) + B, max(ys) + B), (min(xs) - B, max(ys) + B)]
    polys = {}
    nodes = m['nodes']

    def rec(child, poly):
        if child & 0x8000:
            ss = child & 0x7FFF
            first, count = m['ssectors'][ss][1], m['ssectors'][ss][0]
            # SSECTORS lump: (numsegs, firstseg)
            p = poly
            for k in range(count):
                sg = m['segs'][first + k]
                x1, y1 = V[sg['v1']]; x2, y2 = V[sg['v2']]
                a, b, c = side_plane(x1, y1, x2 - x1, y2 - y1)
                p = clip(p, a, b, c, 0.01)
                if len(p) < 3: break
            polys[ss] = p
            return
        x, y, dx, dy = nodes[child][0:4]
        a, b, c = side_plane(x, y, dx, dy)
        rec(nodes[child][12], clip(poly, a, b, c, 0.5))
        rec(nodes[child][13], clip(poly, -a, -b, -c, 0.5))

    rec(len(nodes) - 1, box)
    ss_sector = []
    for i, (cnt, first) in enumerate(m['ssectors']):
        sg = m['segs'][first]
        ln = m['lines'][sg['line']]
        sd = ln['s1'] if sg['side'] == 0 else ln['s2']
        ss_sector.append(m['sides'][sd]['sector'])
    return polys, ss_sector


def area2(p):
    return sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))


# ---------------------------------------------------------------- mesh accumulation
class Bucket:
    def __init__(self, name, origin):
        self.name = name; self.origin = origin  # origin (x, y, zDoom) of the model in Doom coords
        self.tris = []  # (matkey, [(x,y,z,u,v)*3], normal)
        self.anim = None

    def add_poly(self, mat, pts, normal):
        # pts in Doom coords with uv; convex fan, assumed CCW from the visible side
        for i in range(1, len(pts) - 1):
            self.tris.append((mat, (pts[0], pts[i], pts[i + 1]), normal))

    def smd(self):
        ox, oy, oz = self.origin
        out = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0",
               "0 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000", "end", "triangles"]
        for mat, vs, n in self.tris:
            out.append(mat)
            nx, ny, nz = n
            for (x, y, z, u, v) in vs:
                X = x - ox; Y = y - oy; Z = (z - oz) * ZS
                # ModelDoc turns SMD imports 90 degrees: write (y, -x, z) to cancel it
                out.append("0 %.3f %.3f %.3f %.4f %.4f %.4f %.5f %.5f" % (Y, -X, Z, ny, -nx, nz, u, v))
        out.append("end")
        return "\n".join(out) + "\n"


VMDL = """<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:modeldoc41:version{12fc9d44-453a-4ae4-b4d9-7e2ac0bbd4e0} -->
{
	rootNode =
	{
		_class = "RootNode"
		children =
		[
			{
				_class = "MaterialGroupList"
				children =
				[
					{
						_class = "DefaultMaterialGroup"
						remaps =
						[
%(remaps)s
						]
						use_global_default = false
						global_default_material = ""
					},
%(skins)s
				]
			},
			{
				_class = "RenderMeshList"
				children =
				[
					{
						_class = "RenderMeshFile"
						name = "%(name)s"
						filename = "%(smd)s"
						import_scale = 1.0
						import_filter =
						{
							exclude_by_default = false
							exception_list = [  ]
						}
					},
				]
			},
		]
		model_archetype = ""
		primary_associated_entity = ""
		document_sub_type = "ModelDocSubType_None"
	}
}
"""


ANIM_GROUP = """					{
						_class = "MaterialGroup"
						name = "anim%d"
						remaps =
						[
%s
						]
					},
"""


def remap_pairs(pairs):
    # material group remaps: from a full material path (the default group's) to another
    return "\n".join('\t\t\t\t\t\t\t{\n\t\t\t\t\t\t\t\tfrom = "%s"\n\t\t\t\t\t\t\t\tto = "%s"\n\t\t\t\t\t\t\t},' % (k, v)
                     for k, v in sorted(pairs.items()))


def scroll_step(w):
    # pixels (= tics, at Doom's 1 pixel per tic) between a scrolling wall's frames: at most 32 frames a texture
    return max(2, w // 32)


def remap_block(mats):
    return "\n".join('\t\t\t\t\t\t\t{\n\t\t\t\t\t\t\t\tfrom = "%s.vmat"\n\t\t\t\t\t\t\t\tto = "%s"\n\t\t\t\t\t\t\t},' % (k, v)
                     for k, v in sorted(mats.items()))


# ---------------------------------------------------------------- materials
class Materials:
    def __init__(self, out):
        self.out = out
        self.mats = {}   # key -> (vmat path)
        self.tex_done = set()
        self.sizes = {}

    def texsize(self, kind, name):
        k = (kind, name)
        if k not in self.sizes:
            img = assets.texture(name) if kind == 'w' else assets.flat(name)
            self.sizes[k] = (img.shape[1], img.shape[0]) if img is not None else (64, 64)
        return self.sizes[k]

    def write_png(self, kind, name, shift=0):
        k = (kind, name, shift)
        if k in self.tex_done: return
        self.tex_done.add(k)
        img = assets.texture(name) if kind == 'w' else assets.flat(name)
        if shift: img = np.roll(img, -shift, axis=1)   # a scrolling wall's frame: the texture moved `shift` pixels left
        fname = name.lower() + ('_x%d' % shift if shift else '')
        d = os.path.join(self.out, ADDON_MAT, 'tex' if kind == 'w' else 'flat')
        os.makedirs(d, exist_ok=True)
        big = np.repeat(np.repeat(img, UPS, 0), UPS, 1)
        rgb = big.copy()
        # bleed colour into transparent pixels so filtering at mask edges stays clean
        if (big[..., 3] == 0).any():
            rgb[big[..., 3] == 0, :3] = 0
            # alpha-tested textures must be power-of-two or the material fails to compile; these tile, so stretch
            ph, pw = pot(big.shape[0]), pot(big.shape[1])
            if (ph, pw) != big.shape[:2]:
                rgb = np.array(Image.fromarray(rgb).resize((pw, ph), Image.NEAREST))
                big = np.array(Image.fromarray(big).resize((pw, ph), Image.NEAREST))
            Image.fromarray(big[..., 3]).save(os.path.join(d, fname + '_trans.png'))
        Image.fromarray(rgb[..., :3]).save(os.path.join(d, fname + '_color.png'))

    def get(self, kind, name, light, alpha=False, scroll=False, shift=0):
        step = max(0, min(15, light))
        key = '%s_%s_l%d%s%s%s' % (kind, name.lower(), step, 'a' if alpha else '', 's' if scroll else '', '_x%d' % shift if shift else '')
        key = key.replace('-', '_')
        if key not in self.mats:
            self.write_png(kind, name, shift)
            tname = name.lower() + ('_x%d' % shift if shift else '')
            sub = 'tex' if kind == 'w' else 'flat'
            path = '%s/m/%s.vmat' % (ADDON_MAT, key)
            b = brightness(step)
            w, h = self.texsize(kind, name)
            lines = ['// FreeDM generated material', 'Layer0', '{', '\tshader "csgo_unlitgeneric.vfx"']
            has_trans = alpha and os.path.exists(os.path.join(self.out, ADDON_MAT, sub, tname + '_trans.png'))
            lines.append('\tF_BLEND_MODE %d' % (2 if has_trans else 0))
            lines.append('\tTextureColor "%s/%s/%s_color.png"' % (ADDON_MAT, sub, tname))
            if has_trans:
                lines.append('\tTextureTranslucency "%s/%s/%s_trans.png"' % (ADDON_MAT, sub, tname))
                lines.append('\tg_flAlphaTestReference "0.500"')
            lines.append('\tg_vColorTint "[%.4f %.4f %.4f 0.000000]"' % (b, b, b))
            lines.append('\tg_flModelTintAmount "1.000"')
            if scroll:
                lines.append('\tg_vTexCoordScrollSpeed "[%.5f 0.00000]"' % (35.0 / w))
            lines.append('}')
            p = os.path.join(self.out, path)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'w', newline='\n').write('\n'.join(lines) + '\n')
            self.mats[key] = path
        return key


def brightness(step):
    # Doom light level step (0..15) -> tint; distance darkening comes from the map's fog
    return max(0.06, min(1.0, (step * 16 + 8) / 255.0))


# ---------------------------------------------------------------- converter
WALL_BACKING = 16.0    # how far behind a wall its hidden copy sits (Doom units), at most
STEP = 24              # a player steps up anything this high, so lower walls up to this never get pressed against
PASS = 64              # an opening lower than this (above the floor) can't be walked under: its upper wall gets pressed against

class Level:
    def __init__(self, idx, mats):
        self.idx = idx
        self.tag = 'm%02d' % idx
        self.m = load_map(os.path.join(LEVELS, 'dm%02d.wad' % idx))
        self.mats = mats
        m = self.m
        self.floor_mv, self.ceil_mv, raise_ceil = classify_movers(m)
        self.fr, self.cr = height_ranges(m, self.floor_mv, self.ceil_mv, raise_ceil)
        xs = [v[0] for v in m['verts']]; ys = [v[1] for v in m['verts']]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))
        self.center = ((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2)
        self.buckets = {}
        self.sec_bbox = {}
        self.backings = 0
        self.faces = {'one-sided': [0, 0], 'lower': [0, 0], 'upper': [0, 0]}   # walls you can press against: [count, given a copy]
        # every line as a segment, for measuring the empty space behind outer walls
        V = m['verts']
        self.segs = np.array([(V[l['v1']][0], V[l['v1']][1], V[l['v2']][0], V[l['v2']][1]) for l in m['lines']], dtype=np.float64)

    def crosses(self, ax, ay, cx, cy, skip):
        # does the segment (ax,ay)-(cx,cy) cross any line other than line `skip`?
        s = self.segs
        dx, dy = cx - ax, cy - ay
        ex, ey = s[:, 2] - s[:, 0], s[:, 3] - s[:, 1]
        den = dx * ey - dy * ex
        ok = np.abs(den) > 1e-9
        den = np.where(ok, den, 1.0)
        qx, qy = s[:, 0] - ax, s[:, 1] - ay
        t = (qx * ey - qy * ex) / den
        u = (qx * dy - qy * dx) / den
        hit = ok & (t > 1e-6) & (t < 1 - 1e-6) & (u > 1e-6) & (u < 1 - 1e-6)
        hit[skip] = False
        return bool(hit.any())

    def void_depth(self, x, y, dx, dy):
        # distance along (dx, dy) from (x, y) to the nearest line
        s = self.segs
        ex, ey = s[:, 2] - s[:, 0], s[:, 3] - s[:, 1]
        den = dx * ey - dy * ex
        ok = np.abs(den) > 1e-9
        den = np.where(ok, den, 1.0)
        qx, qy = s[:, 0] - x, s[:, 1] - y
        t = (qx * ey - qy * ex) / den
        u = (qx * dy - qy * dx) / den
        hit = ok & (t > 0.01) & (u >= 0) & (u <= 1)
        return float(t[hit].min()) if hit.any() else 1e9

    def backing(self, x1, y1, x2, y2, nx, ny):
        # where a wall's hidden copy can go: (depth behind the wall, how much shorter at each end). It goes into the
        # empty space (or the solid floor/ceiling column) behind the wall, 1.5 short of the next line; the copy and the
        # strips joining it to the wall must not cross any other line, so at slanted corners (octagonal pillars,
        # angled walls) it is made shorter before it is moved closer. (0, 0) = no room.
        ln = math.hypot(x2 - x1, y2 - y1); ux, uy = (x2 - x1) / ln, (y2 - y1) / ln
        depth = min(self.void_depth(x1 + (x2 - x1) * f - nx * 0.5, y1 + (y2 - y1) * f - ny * 0.5, -nx, -ny) for f in (0.1, 0.5, 0.9))
        back = min(WALL_BACKING, depth - 1.5)
        while back >= 2:
            for inset in (0.0, back * 0.5, back, back * 2.5):
                if ln - 2 * inset < 4: break
                ax, ay = x1 + ux * inset - nx * back, y1 + uy * inset - ny * back
                cx, cy = x2 - ux * inset - nx * back, y2 - uy * inset - ny * back
                if not any(self.crosses(*seg, self._li) for seg in (
                        (ax, ay, cx, cy), (x1 - nx * 0.5, y1 - ny * 0.5, ax, ay), (x2 - nx * 0.5, y2 - ny * 0.5, cx, cy))):
                    return back, inset
            back /= 2
        return 0, 0

    def sky(self, sec):
        return self.m['sectors'][sec]['ctex'] == 'F_SKY1'

    def static_bucket(self, x, y):
        cx = max(0, int((x - self.bbox[0]) // CHUNK)); cy = max(0, int((y - self.bbox[1]) // CHUNK))
        k = 's%d_%d' % (cx, cy)
        if k not in self.buckets:
            self.buckets[k] = Bucket(k, (self.center[0], self.center[1], 0))
        return self.buckets[k]

    def mover_bucket(self, sec, plane):
        k = '%s%d' % (plane, sec)
        if k not in self.buckets:
            s = self.m['sectors'][sec]
            bx = self.sec_bbox[sec]
            ox = (bx[0] + bx[2]) / 2.0; oy = (bx[1] + bx[3]) / 2.0
            oz = s['floor'] if plane == 'f' else s['ceil']
            self.buckets[k] = Bucket(k, (round(ox), round(oy), oz))
        return self.buckets[k]

    def anim_bucket(self, kind, group):
        k = 'a%s_%s' % (kind, group.lower())
        if k not in self.buckets:
            self.buckets[k] = Bucket(k, (self.center[0], self.center[1], 0))
            self.buckets[k].anim = (kind, group)
        return self.buckets[k]

    def bucket_for(self, sec, plane, x, y, tex=None):
        if sec is not None and ((plane == 'f' and sec in self.floor_mv) or (plane == 'c' and sec in self.ceil_mv)):
            return self.mover_bucket(sec, plane)
        if tex is not None:
            a = anim_of('f', tex)
            if a: return self.anim_bucket('f', a[0])
        return self.static_bucket(x, y)

    # a scrolling wall (Doom special 48): CS2's unlit shader doesn't scroll textures, so the wall is its own animated
    # prop whose frames are the texture shifted SCROLL_STEP(w) pixels at a time (the script steps the skins)
    def scroll_bucket(self, tex):
        k = 'as_' + tex.lower().replace('-', '_')
        if k not in self.buckets:
            self.buckets[k] = Bucket(k, (self.center[0], self.center[1], 0))
            self.buckets[k].anim = ('scroll', tex)
        return self.buckets[k]

    def wall_bucket(self, x, y, tex):
        a = anim_of('w', tex)
        return self.anim_bucket('w', a[0]) if a else self.static_bucket(x, y)

    def light_of(self, sec, contrast=0):
        return (self.m['sectors'][sec]['light'] >> 4) + contrast

    def build(self):
        m = self.m
        S = m['sectors']
        polys, ss_sector = subsector_polys(m)
        self.ss_sector = ss_sector
        # sector bboxes (from subsector polys)
        for ss, p in polys.items():
            if len(p) < 3: continue
            sec = ss_sector[ss]
            b = self.sec_bbox.get(sec, [1e9, 1e9, -1e9, -1e9])
            for x, y in p:
                b[0] = min(b[0], x); b[1] = min(b[1], y); b[2] = max(b[2], x); b[3] = max(b[3], y)
            self.sec_bbox[sec] = b
        for sec in range(len(S)):
            if sec not in self.sec_bbox:
                self.sec_bbox[sec] = [0, 0, 0, 0]
        # ---- floors and ceilings
        for ss, p in polys.items():
            if len(p) < 3 or abs(area2(p)) < 1.0: continue
            sec = ss_sector[ss]; s = S[sec]
            if area2(p) < 0: p = p[::-1]
            cx = sum(q[0] for q in p) / len(p); cy = sum(q[1] for q in p) / len(p)
            lt = self.light_of(sec)
            mat = self.mats.get('f', s['ftex'], lt)
            pts = [(x, y, s['floor'], x / 64.0, y / 64.0) for x, y in p]
            self.bucket_for(sec, 'f', cx, cy, s['ftex']).add_poly(mat, pts, (0, 0, 1))
            if not self.sky(sec):
                mat = self.mats.get('f', s['ctex'], lt)
                pts = [(x, y, s['ceil'], x / 64.0, y / 64.0) for x, y in p[::-1]]
                self.bucket_for(sec, 'c', cx, cy, s['ctex']).add_poly(mat, pts, (0, 0, -1))
        # ---- walls
        for li, l in enumerate(m['lines']):
            self._li = li
            for side in (0, 1):
                sd_i = l['s1'] if side == 0 else l['s2']
                if sd_i < 0: continue
                other_i = l['s2'] if side == 0 else l['s1']
                self.wall(l, side, m['sides'][sd_i], m['sides'][other_i] if other_i >= 0 else None)

    def wall(self, l, side, sd, osd):
        m = self.m; S = m['sectors']
        v1 = m['verts'][l['v1']]; v2 = m['verts'][l['v2']]
        if side == 1: v1, v2 = v2, v1
        x1, y1 = v1; x2, y2 = v2
        ln = math.hypot(x2 - x1, y2 - y1)
        if ln < 0.01: return
        nx, ny = (y2 - y1) / ln, -(x2 - x1) / ln   # right-hand normal (towards the viewer)
        contrast = -1 if y1 == y2 else (1 if x1 == x2 else 0)
        Y = sd['sector']; ys = S[Y]
        lt = self.light_of(Y, contrast)
        midx = (x1 + x2) / 2; midy = (y1 + y2) / 2
        flags = l['flags']
        xoff, yoff = sd['xoff'], sd['yoff']

        def quad(bucket, tex, zb, zt, top_ref, alpha=False, scroll=False, back=0.0, inset=0.0):
            if zt - zb < 0.01 or tex in ('-', ''): return
            if assets.texture(tex) is None: return
            w, h = self.mats.texsize('w', tex)
            if scroll and bucket.name.startswith('s'):
                bucket = self.scroll_bucket(tex); scroll = False   # frame 0 is the plain texture
            mat = self.mats.get('w', tex, lt, alpha, scroll)
            u1 = (xoff + inset) / w; u2 = (xoff + ln - inset) / w
            vb = 1 - (top_ref - zb + yoff) / h; vt = 1 - (top_ref - zt + yoff) / h
            ux, uy = (x2 - x1) / ln, (y2 - y1) / ln
            ax, ay = x1 + ux * inset - nx * back, y1 + uy * inset - ny * back
            cx, cy = x2 - ux * inset - nx * back, y2 - uy * inset - ny * back
            pts = [(ax, ay, zb, u1, vb), (cx, cy, zb, u2, vb), (cx, cy, zt, u2, vt), (ax, ay, zt, u1, vt)]
            bucket.add_poly(mat, pts, (nx, ny, 0))

        scroll = l['special'] == 48
        if osd is None:
            # one-sided: spans the full possible range of the sector's floor/ceiling
            fmin = self.fr[Y][0]; cmax = self.cr[Y][1]
            if flags & ML_DONTPEGBOTTOM:
                top = ys['floor'] + self.mats.texsize('w', sd['mid'])[1] if sd['mid'] not in ('-', '') else 0
            else:
                top = ys['ceil']
            quad(self.wall_bucket(midx, midy, sd['mid']), sd['mid'], fmin, cmax, top, scroll=scroll)
            # a copy of the wall a little way into the empty space behind it: when the camera is pressed against
            # the wall, CS2's near plane cuts the wall away and you'd look into the void; now you see this copy.
            # It stays 1.5 units short of whatever is behind (another room's wall), so it never shows from there.
            self.faces['one-sided'][0] += 1
            back, inset = self.backing(x1, y1, x2, y2, nx, ny)
            if back and sd['mid'] not in ('-', ''):
                quad(self.wall_bucket(midx, midy, sd['mid']), sd['mid'], fmin, cmax, top, scroll=scroll, back=back, inset=inset)
                self.backings += 1; self.faces['one-sided'][1] += 1
            return
        X = osd['sector']; xs_ = S[X]
        if X == Y and not (sd['mid'] not in ('-', '')):
            return
        # lower: face towards Y belongs to X's floor column (moves with X's floor)
        X_fmin, X_fmax = self.fr[X]; Y_fmin, Y_fmax = self.fr[Y]
        if X_fmax > Y_fmin and sd['lower'] not in ('-', ''):
            top = ys['ceil'] if flags & ML_DONTPEGBOTTOM else xs_['floor']
            depth_bottom = xs_['floor'] - (X_fmax - Y_fmin)   # in X-initial coordinates
            b = self.bucket_for(X, 'f', midx, midy)
            if b.name.startswith('s'): b = self.wall_bucket(midx, midy, sd['lower'])
            quad(b, sd['lower'], min(depth_bottom, xs_['floor']), xs_['floor'], top, scroll=scroll)
            # too high to step onto: same hidden copy, inside the solid column under X's floor (moves with it)
            if X_fmax - Y_fmin > STEP and assets.texture(sd['lower']) is not None:
                self.faces['lower'][0] += 1
                back, inset = self.backing(x1, y1, x2, y2, nx, ny)
                if back:
                    quad(b, sd['lower'], min(depth_bottom, xs_['floor']), xs_['floor'], top, scroll=scroll, back=back, inset=inset)
                    self.backings += 1; self.faces['lower'][1] += 1
        # upper: face towards Y belongs to X's ceiling column
        X_cmin, X_cmax = self.cr[X]; Y_cmin, Y_cmax = self.cr[Y]
        if X_cmin < Y_cmax and not (self.sky(X) and self.sky(Y)) and sd['upper'] not in ('-', ''):
            if flags & ML_DONTPEGTOP:
                top = ys['ceil']
            else:
                top = xs_['ceil'] + self.mats.texsize('w', sd['upper'])[1]
            height_top = xs_['ceil'] + (Y_cmax - X_cmin)
            b = self.bucket_for(X, 'c', midx, midy)
            if b.name.startswith('s'): b = self.wall_bucket(midx, midy, sd['upper'])
            quad(b, sd['upper'], xs_['ceil'], max(height_top, xs_['ceil']), top, scroll=scroll)
            # too low to walk under (closed doors, pillars): hidden copy inside the solid column above X's ceiling
            # (not under a sky, where nothing would hide it)
            if X_cmin - Y_fmax < PASS and not self.sky(X) and assets.texture(sd['upper']) is not None:
                self.faces['upper'][0] += 1
                back, inset = self.backing(x1, y1, x2, y2, nx, ny)
                if back:
                    quad(b, sd['upper'], xs_['ceil'], max(height_top, xs_['ceil']), top, scroll=scroll, back=back, inset=inset)
                    self.backings += 1; self.faces['upper'][1] += 1
        # middle (masked, drawn once, clipped to the opening)
        if sd['mid'] not in ('-', '') and assets.texture(sd['mid']) is not None:
            w, h = self.mats.texsize('w', sd['mid'])
            lo = max(ys['floor'], xs_['floor']); hi = min(ys['ceil'], xs_['ceil'])
            if flags & ML_DONTPEGBOTTOM:
                top = lo + h
            else:
                top = hi
            zt = min(hi, top + yoff); zb = max(lo, top + yoff - h)
            # (the texture covers [top - h, top] shifted by the row offset)
            quad(self.wall_bucket(midx, midy, sd['mid']), sd['mid'], zb, zt, top, alpha=True, scroll=scroll)

    # ------------------------------------------------------------ output
    def write(self, out, offset):
        mdir = os.path.join(out, 'models/fdm', self.tag)
        os.makedirs(mdir, exist_ok=True)
        props = []
        for k, b in sorted(self.buckets.items()):
            if not b.tris: continue
            name = '%s_%s' % (self.tag, k)
            open(os.path.join(mdir, name + '.smd'), 'w', newline='\n').write(b.smd())
            used = {mat: self.mats.mats[mat] for mat, _, _ in b.tris}
            skins = ''
            frames = 1; tics = ANIM_TICS
            if b.anim:
                # one material group per animation frame: every mesh material swaps to the same texture state of that
                # frame. A group remaps the default group's material (as the sprite models' colour skins do)
                kind, group = b.anim
                if kind == 'scroll':
                    w, _ = self.mats.texsize('w', group)
                    tics = scroll_step(w); frames = max(1, w // tics)
                else:
                    frames_list = ANIM[(kind, group)][1]
                    frames = len(frames_list)
                for fi in range(1, frames):
                    remaps = {}
                    for mat in used:
                        kind_, rest = mat.split('_', 1)
                        texname, tail = rest.rsplit('_l', 1)
                        step = int(''.join(ch for ch in tail if ch.isdigit()))
                        alpha = 'a' in tail; scroll = 's' in tail
                        if kind == 'scroll': to = self.mats.get('w', group, step, alpha, False, shift=fi * tics)
                        else: to = self.mats.get(kind, frames_list[fi], step, alpha, scroll)
                        remaps[used[mat]] = self.mats.mats[to]
                    skins += ANIM_GROUP % (fi, remap_pairs(remaps))
            vm = VMDL % dict(remaps=remap_block(used), skins=skins, name=name, smd='models/fdm/%s/%s.smd' % (self.tag, name))
            open(os.path.join(mdir, name + '.vmdl'), 'w', newline='\n').write(vm)
            ox, oy, oz = b.origin
            world = (offset[0] + ox - self.center[0], offset[1] + oy - self.center[1], offset[2] + oz * ZS)
            props.append(dict(model='models/fdm/%s/%s.vmdl' % (self.tag, name), origin=world,
                              mover=None if k.startswith('s') or k.startswith('a') else k, name='fdm_%s_%s' % (self.tag, k),
                              tris=len(b.tris), anim=frames if b.anim else 0, tics=tics))
        self.anim_props = [[q['name'], q['anim'], q['tics']] for q in props if q['anim']]
        return props

    def runtime(self, offset):
        m = self.m
        sec_of_side = lambda s: m['sides'][s]['sector'] if s >= 0 else -1
        d = dict(
            id=self.tag, title=self.title(),
            off=[offset[0] - self.center[0], offset[1] - self.center[1], offset[2]],
            v=[c for v in m['verts'] for c in v],
            l=[[l['v1'], l['v2'], l['flags'], l['special'], l['tag'], sec_of_side(l['s1']), sec_of_side(l['s2'])]
               for l in m['lines']],
            s=[[s['floor'], s['ceil'], s['light'], s['special'], s['tag'], 1 if s['ctex'] == 'F_SKY1' else 0]
               for s in m['sectors']],
            n=[[n[0], n[1], n[2], n[3], n[12], n[13]] for n in m['nodes']],
            ss=self.ss_sector,
            t=[[t['x'], t['y'], t['angle'], t['type'], t['flags']] for t in m['things']],
            mf=sorted(self.floor_mv), mc=sorted(self.ceil_mv),
            an=getattr(self, 'anim_props', []),
            bb=list(self.bbox),
        )
        return d

    def title(self):
        return 'MAP%02d' % self.idx


def pack(levels, lim=15600, gap=2048):
    """shelf-pack the level bounding boxes into the world; returns centre offset per level"""
    items = sorted(levels, key=lambda L: -(L.bbox[3] - L.bbox[1]))
    x = -lim; y = -lim; shelf = 0; res = {}
    for L in items:
        w = L.bbox[2] - L.bbox[0]; h = L.bbox[3] - L.bbox[1]
        if x + w > lim:
            x = -lim; y += shelf + gap; shelf = 0
        if y + h > lim:
            raise RuntimeError('levels do not fit')
        res[L.idx] = (x + w / 2, y + h / 2)
        x += w + gap; shelf = max(shelf, h)
    return res


if __name__ == '__main__':
    out = sys.argv[1]
    ids = [int(a) for a in sys.argv[2].split(',')] if len(sys.argv) > 2 else list(range(1, 33))
    mats = Materials(out)
    levels = [Level(i, mats) for i in ids]
    offs = pack(levels)
    allprops = []; rt = []
    for L in levels:
        L.build()
        ox, oy = offs[L.idx]
        off = (round(ox), round(oy), -2048)
        props = L.write(out, off)
        allprops += [dict(p, level=L.tag) for p in props]
        rt.append(L.runtime(off))
        print(L.tag, "backings", L.backings, ' '.join('%s %d/%d' % (k, v[1], v[0]) for k, v in L.faces.items()),
              "chunks", sum(1 for p in props if not p["mover"]), "movers", sum(1 for p in props if p["mover"]),
              'tris', sum(p['tris'] for p in props))
    os.makedirs(os.path.join(out, '_gen'), exist_ok=True)
    json.dump(allprops, open(os.path.join(out, '_gen/props.json'), 'w'))
    json.dump(rt, open(os.path.join(out, '_gen/levels.json'), 'w'), separators=(',', ':'))
    print('materials', len(mats.mats), 'textures', len(mats.tex_done))
