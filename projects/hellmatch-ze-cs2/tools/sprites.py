"""Freedoom sprites -> CS2 models.

  rot8  : voxel figure carved from the 8 sprite rotations (players, rockets)
  lathe : voxel solid of revolution (lamps, columns, barrels, spheres)
  slab  : voxel extrusion (boxes, weapons, armour)
  star  : three crossed, alpha-tested sprite planes (effects, corpses, gore)

Voxel models share one palette material (16 player colour skins + a fuzz skin).
"""
import os, sys, json, math, re
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import assets

OUT = sys.argv[1]
FRAMES = json.load(open(sys.argv[2]))
SPR_DIR = os.path.join(assets.FD, 'sprites')
ZS = 1.2
FORWARD_LIMIT = 13   # Doom units in front of the thing centre that a carved model may reach
PAL = assets.PAL.astype(np.int32)

SHAPE = {}
for s in 'PLAY MISL'.split(): SHAPE[s] = 'rot8'
# monsters: carved from their 8 rotations like the players (death and gib frames have no rotations and become stars)
for s in 'POSS SPOS CPOS TROO SARG HEAD SKUL BOSS BOS2 SKEL FATT BSPI PAIN VILE CYBR SPID'.split(): SHAPE[s] = 'rot8'
for s in 'BAR1 SOUL MEGA PINV PINS BON1 BON2 CAND CBRA COLU TLMP TLP2 ELEC COL1 COL5 CEYE FSKU TRE1 TRE2 TBLU TGRN TRED SMBT SMGT SMRT SMIT POL3'.split(): SHAPE[s] = 'lathe'
for s in 'ARM1 ARM2 PSTR STIM MEDI CLIP AMMO ROCK BROK CELL CELP SHEL SBOX BPAK'.split(): SHAPE[s] = 'box'
for s in 'SHOT SGN2 MGUN LAUN PLAS BFUG CSAW'.split(): SHAPE[s] = 'weapon'
# everything else -> star

# ---------------------------------------------------------------- sprite lookup
FILES = os.listdir(SPR_DIR)
def rotations(sprite, frame):
    """returns dict rot -> (rgba, (leftoff, topoff), mirrored); rot 0 = no rotations"""
    s = sprite.lower(); f = frame.lower()
    f = {'0': '[', '1': '^', '2': ']'}.get(f, f)   # frames past Z: Doom's [ \ ] are keyed 0 1 2 (Freedoom names the \ one ^)
    out = {}
    for fn in FILES:
        name = fn[:-4]
        if not name.startswith(s): continue
        rest = name[4:]
        parts = re.findall(r'([a-z\[\]\^])(\d)', rest)
        for i, (fr, rot) in enumerate(parts):
            if fr != f: continue
            img, off = assets.sprite(name)
            out[int(rot)] = (img, off, i == 1)
    return out

def shrink(idx, off, s):
    """palette-index image at 1/s resolution: a cell is opaque if any pixel in it is, coloured by its first opaque pixel"""
    if s == 1: return idx, off
    h, w = idx.shape
    H, W = -(-h // s), -(-w // s)
    pad = np.full((H * s, W * s), -1, idx.dtype); pad[:h, :w] = idx
    blocks = pad.reshape(H, s, W, s).transpose(0, 2, 1, 3).reshape(H, W, s * s)
    opaque = blocks >= 0
    first = opaque.argmax(-1)
    out = np.where(opaque.any(-1), np.take_along_axis(blocks, first[..., None], -1)[..., 0], -1)
    return out, (off[0] / s, off[1] / s)

def voxel_scale(rots):
    """voxel size for a sprite: 1 unit up to the marine's size, 2 for the big creatures, 4 for the huge ones.
    Keeps every model near the players' triangle count (a 1-unit spider mastermind would be 50 MB)."""
    m = max(max(img.shape) for img, _, _ in rots.values())
    return 1 if m <= 60 else 2 if m <= 130 else 4

def pal_index_image(rgba):
    rgb = rgba[..., :3].astype(np.int32)
    d = ((rgb[:, :, None, :] - PAL[None, None, :, :]) ** 2).sum(-1)
    idx = d.argmin(-1)
    idx[rgba[..., 3] == 0] = -1
    return idx

# ---------------------------------------------------------------- voxel building
def view_dir(rot):
    th = math.radians((rot - 1) * 45)
    return math.cos(th), math.sin(th)

def carve_rot8(rots, limit=None):
    """rots: rot -> (idx image, (lo, to), mirrored)"""
    views = []
    for r in range(1, 9):
        img, off, mir = rots[r]
        h, w = img.shape
        if mir:
            img = img[:, ::-1]
            lo = w - off[0]
        else:
            lo = off[0]
        views.append((img, lo, off[1], view_dir(r)))
    R = max(max(v[0].shape[1] - v[1], v[1]) for v in views) + 1
    H = max(v[2] for v in views) + 1
    xs = np.arange(-R, R) + 0.5
    ys = np.arange(-R, R) + 0.5
    zs = np.arange(0, H) + 0.5
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
    votes = np.zeros(X.shape, np.int32)
    samples = []
    for img, lo, to, (dx, dy) in views:
        u = -X * dy + Y * dx       # screen-right coordinate
        col = np.floor(u + lo).astype(int)
        row = np.floor(to - Z).astype(int)
        h, w = img.shape
        inside = (col >= 0) & (col < w) & (row >= 0) & (row < h)
        op = np.zeros(X.shape, bool)
        cc = np.clip(col, 0, w - 1); rr = np.clip(row, 0, h - 1)
        mask = img >= 0
        # 1-pixel dilation of the silhouette tolerates small artist inconsistencies
        dil = mask.copy()
        dil[1:, :] |= mask[:-1, :]; dil[:-1, :] |= mask[1:, :]; dil[:, 1:] |= mask[:, :-1]; dil[:, :-1] |= mask[:, 1:]
        op = inside & dil[rr, cc]
        votes += op
        samples.append((img, lo, to, (dx, dy)))
    occ = votes >= 8
    # nothing further forward than the collision radius: a player's camera sits just ahead of the chest, and the
    # outstretched gun arm of the firing frames would otherwise pass straight through it
    if limit is not None: occ &= (X <= limit)
    return occ, (xs, ys, zs), samples

def colour_rot8(occ, axes, samples):
    """per-face colour index: [6] arrays shaped like occ (face normals +x,-x,+y,-y,+z,-z)"""
    xs, ys, zs = axes
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
    normals = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    faces = []
    proj = []
    for img, lo, to, (dx, dy) in samples:
        u = -X * dy + Y * dx
        col = np.clip(np.floor(u + lo).astype(int), 0, img.shape[1] - 1)
        row = np.clip(np.floor(to - Z).astype(int), 0, img.shape[0] - 1)
        proj.append(img[row, col])
    proj = np.stack(proj)  # [8, ...]
    ang = np.arctan2(Y, X)
    for n in normals:
        if n[2] == 0:
            score = np.array([n[0] * d[0] + n[1] * d[1] for _, _, _, d in samples])
            order = np.argsort(-score)
            col = np.full(occ.shape, -1, np.int64)
            for r in order:
                fill = (col < 0) & (proj[r] >= 0)
                col[fill] = proj[r][fill]
        else:
            # top/bottom faces: the view facing the voxel's horizontal direction
            col = np.full(occ.shape, -1, np.int64)
            best = np.round(ang / (math.pi / 4)).astype(int) % 8
            for r in range(8):
                fill = (best == r) & (proj[r] >= 0)
                col[fill] = proj[r][fill]
            for r in range(8):
                fill = (col < 0) & (proj[r] >= 0)
                col[fill] = proj[r][fill]
        faces.append(col)
    return faces

def build_lathe(img, off):
    h, w = img.shape
    lo, to = off
    R = max(w - lo, lo) + 1
    xs = np.arange(-R, R) + 0.5; ys = xs.copy(); zs = np.arange(0, max(to, 1) + 1) + 0.5
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
    r = np.sqrt(X * X + Y * Y)
    row = np.floor(to - Z).astype(int)
    ok_row = (row >= 0) & (row < h)
    rr = np.clip(row, 0, h - 1)
    # a voxel at radius r is solid if the sprite is opaque at both +r and -r from the axis on that row
    cp = np.floor(lo + r).astype(int); cn = np.floor(lo - r).astype(int)
    okp = (cp >= 0) & (cp < w); okn = (cn >= 0) & (cn < w)
    mp = np.where(okp, img[rr, np.clip(cp, 0, w - 1)] >= 0, False)
    mn = np.where(okn, img[rr, np.clip(cn, 0, w - 1)] >= 0, False)
    occ = ok_row & (mp | mn) & (mp | ~okp) & (mn | ~okn)
    occ = ok_row & (mp & mn)
    # colour: project along the view direction onto the front sprite
    faces = []
    for n in [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]:
        # u = signed horizontal distance across the sprite as seen from the face direction
        if n[2]:
            u = np.where(np.abs(X) > np.abs(Y), np.sign(X) * r, np.sign(Y) * r)
        elif n[0]:
            u = Y * n[0]
        else:
            u = -X * n[1]
        col = np.clip(np.floor(lo + u).astype(int), 0, w - 1)
        c = img[rr, col]
        # fall back to the mirrored column when the projected one is empty
        col2 = np.clip(np.floor(lo - u).astype(int), 0, w - 1)
        c2 = img[rr, col2]
        c = np.where(c >= 0, c, c2)
        c3 = img[rr, np.clip(np.floor(lo + np.sign(u + 1e-6) * r).astype(int), 0, w - 1)]
        c = np.where(c >= 0, c, c3)
        faces.append(np.where(occ, c, -1))
    return occ, (xs, ys, zs), faces

def build_slab(img, off, depth):
    h, w = img.shape
    lo, to = off
    D = max(2, int(depth))
    xs = np.arange(-D / 2, D / 2) + 0.5
    ys = np.arange(-lo, w - lo) + 0.5
    zs = np.arange(0, max(to, 1) + 1) + 0.5
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
    # the sprite is seen from +x (viewer at rotation 1): screen right = +y
    col = np.floor(Y + lo).astype(int)
    row = np.floor(to - Z).astype(int)
    ok = (col >= 0) & (col < w) & (row >= 0) & (row < h)
    c = np.where(ok, img[np.clip(row, 0, h - 1), np.clip(col, 0, w - 1)], -1)
    occ = c >= 0
    faces = []
    for n in [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]:
        if n[0] == -1:
            # back face: mirror of the front
            colb = np.floor(lo - Y).astype(int)
            okb = ok & (colb >= 0) & (colb < w)
            cb = np.where(okb, img[np.clip(row, 0, h - 1), np.clip(colb, 0, w - 1)], -1)
            faces.append(np.where(occ, np.where(cb >= 0, cb, c), -1))
        else:
            faces.append(np.where(occ, c, -1))
    return occ, (xs, ys, zs), faces

# ---------------------------------------------------------------- greedy mesher
def mesh_voxels(occ, axes, faces):
    xs, ys, zs = axes
    x0, y0, z0 = xs[0] - 0.5, ys[0] - 0.5, zs[0] - 0.5
    nx, ny, nz = occ.shape
    quads = []
    pad = np.zeros((nx + 2, ny + 2, nz + 2), bool); pad[1:-1, 1:-1, 1:-1] = occ
    dirs = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    for fi, d in enumerate(dirs):
        neigh = pad[1 + d[0]:nx + 1 + d[0], 1 + d[1]:ny + 1 + d[1], 1 + d[2]:nz + 1 + d[2]]
        exposed = occ & ~neigh
        colr = np.where(exposed, faces[fi], -1)
        colr = np.where(exposed & (colr < 0), 0, colr)
        axis = [i for i in range(3) if d[i] != 0][0]
        ua, va = [i for i in range(3) if i != axis]
        n_axis = occ.shape[axis]
        for s in range(n_axis):
            sl = np.take(colr, s, axis=axis)   # 2D [ua, va]
            if (sl < 0).all(): continue
            used = np.zeros(sl.shape, bool)
            U, V = sl.shape
            # only rows/cells with an exposed voxel are worth visiting (a big monster is a thin shell in a large box)
            rows = np.nonzero((sl >= 0).any(axis=1))[0]
            for i in rows:
                cols = np.nonzero(sl[i] >= 0)[0]
                for j in cols:
                    c = sl[i, j]
                    if c < 0 or used[i, j]: continue
                    w = 1
                    while i + w < U and sl[i + w, j] == c and not used[i + w, j]: w += 1
                    h = 1
                    while j + h < V and (sl[i:i + w, j + h] == c).all() and not used[i:i + w, j + h].any(): h += 1
                    used[i:i + w, j:j + h] = True
                    quads.append((fi, axis, s, ua, i, w, va, j, h, int(c)))
    tris = []
    origin = [x0, y0, z0]
    for fi, axis, s, ua, i, w, va, j, h, c in quads:
        d = dirs[fi]
        plane = s + (1 if d[axis] > 0 else 0)
        def P(a, b):
            p = [0, 0, 0]
            p[axis] = plane + origin[axis]
            p[ua] = a + origin[ua]
            p[va] = b + origin[va]
            return p
        corners = [P(i, j), P(i + w, j), P(i + w, j + h), P(i, j + h)]
        n = [float(d[0]), float(d[1]), float(d[2])]
        # winding: counter-clockwise seen from outside
        e1 = np.subtract(corners[1], corners[0]); e2 = np.subtract(corners[2], corners[0])
        if np.dot(np.cross(e1, e2), n) < 0: corners = corners[::-1]
        tris.append((corners[0], corners[1], corners[2], n, c))
        tris.append((corners[0], corners[2], corners[3], n, c))
    return tris

# ---------------------------------------------------------------- output helpers
def pal_uv(c):
    return ((c % 16) * 4 + 2) / 64.0, 1 - ((c // 16) * 4 + 2) / 64.0

def smd_lines(tris_xyz):
    out = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0",
           "0 0.000000 0.000000 0.000000 0.000000 0.000000 0.000000", "end", "triangles"]
    for mat, verts, n in tris_xyz:
        out.append(mat)
        for (x, y, z, u, v) in verts:
            out.append("0 %.3f %.3f %.3f %.4f %.4f %.4f %.5f %.5f" % (y, -x, z * ZS, n[1], -n[0], n[2], u, v))
    out.append("end")
    return "\n".join(out) + "\n"

VMDL_HEAD = """<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:modeldoc41:version{12fc9d44-453a-4ae4-b4d9-7e2ac0bbd4e0} -->
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
%s
				]
			},
			{
				_class = "RenderMeshList"
				children =
				[
					{
						_class = "RenderMeshFile"
						name = "%s"
						filename = "%s"
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

def group(cls, name, remaps):
    rm = "\n".join('\t\t\t\t\t\t\t{\n\t\t\t\t\t\t\t\tfrom = "%s"\n\t\t\t\t\t\t\t\tto = "%s"\n\t\t\t\t\t\t\t},' % r for r in remaps)
    if cls == 'DefaultMaterialGroup':
        return '\t\t\t\t\t{\n\t\t\t\t\t\t_class = "DefaultMaterialGroup"\n\t\t\t\t\t\tremaps =\n\t\t\t\t\t\t[\n%s\n\t\t\t\t\t\t]\n\t\t\t\t\t\tuse_global_default = false\n\t\t\t\t\t\tglobal_default_material = ""\n\t\t\t\t\t},' % rm
    return '\t\t\t\t\t{\n\t\t\t\t\t\t_class = "MaterialGroup"\n\t\t\t\t\t\tname = "%s"\n\t\t\t\t\t\tremaps =\n\t\t\t\t\t\t[\n%s\n\t\t\t\t\t\t]\n\t\t\t\t\t},' % (name, rm)

def write_model(key, tris, mats_default, skins=None):
    d = os.path.join(OUT, 'models/fdm/spr'); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, key + '.smd'), 'w', newline='\n').write(smd_lines(tris))
    groups = [group('DefaultMaterialGroup', None, [(k + '.vmat', v) for k, v in mats_default.items()])]
    for name, remaps in (skins or []):
        groups.append(group('MaterialGroup', name, remaps))
    open(os.path.join(d, key + '.vmdl'), 'w', newline='\n').write(VMDL_HEAD % ("\n".join(groups), key, 'models/fdm/spr/%s.smd' % key))

# ---------------------------------------------------------------- palettes / skins
GREEN = list(range(0x70, 0x80))
SKIN_RAMPS = [None,
              (60, 90, 255), (150, 100, 50), (230, 30, 30), (200, 200, 200), (250, 220, 40), (40, 220, 220), (220, 60, 220),
              (255, 140, 30), (120, 60, 200), (90, 160, 40), (255, 120, 170), (100, 100, 100), (30, 120, 120), (180, 140, 90), (255, 255, 255)]

def write_palettes():
    d = os.path.join(OUT, 'materials/fdm/pal'); os.makedirs(d, exist_ok=True)
    base = assets.PAL.astype(np.float64)
    lum = base[GREEN].mean(1)
    lum = lum / lum.max()
    paths = []
    for k, ramp in enumerate(SKIN_RAMPS):
        pal = base.copy()
        if ramp:
            for i, gi in enumerate(GREEN):
                pal[gi] = np.clip(np.array(ramp) * (0.15 + 0.95 * lum[i]), 0, 255)
        img = np.zeros((64, 64, 3), np.uint8)
        for c in range(256):
            y, x = (c // 16) * 4, (c % 16) * 4
            img[y:y + 4, x:x + 4] = pal[c]
        Image.fromarray(img).save(os.path.join(d, 'pal%d_color.png' % k))
        vm = ['// FreeDM palette skin %d' % k, 'Layer0', '{', '\tshader "csgo_unlitgeneric.vfx"', '\tF_BLEND_MODE 0',
              '\tTextureColor "materials/fdm/pal/pal%d_color.png"' % k, '\tg_vColorTint "[1.000000 1.000000 1.000000 0.000000]"',
              '\tg_flModelTintAmount "1.000"', '}']
        open(os.path.join(d, 'pal%d.vmat' % k), 'w', newline='\n').write('\n'.join(vm) + '\n')
        paths.append('materials/fdm/pal/pal%d.vmat' % k)
    # fuzz: dark, translucent
    Image.fromarray(np.full((16, 16, 3), 8, np.uint8)).save(os.path.join(d, 'fuzz_color.png'))
    Image.fromarray(np.full((16, 16), 90, np.uint8)).save(os.path.join(d, 'fuzz_trans.png'))
    vm = ['// FreeDM invisibility', 'Layer0', '{', '\tshader "csgo_unlitgeneric.vfx"', '\tF_BLEND_MODE 1',
          '\tTextureColor "materials/fdm/pal/fuzz_color.png"', '\tTextureTranslucency "materials/fdm/pal/fuzz_trans.png"',
          '\tg_vColorTint "[1.000000 1.000000 1.000000 0.000000]"', '\tg_flModelTintAmount "0.000"', '}']
    open(os.path.join(d, 'fuzz.vmat'), 'w', newline='\n').write('\n'.join(vm) + '\n')
    paths.append('materials/fdm/pal/fuzz.vmat')
    return paths

def pot(n):
    k = 1
    while k < n: k *= 2
    return k

def write_star_material(key, rgba):
    d = os.path.join(OUT, 'materials/fdm/spr'); os.makedirs(d, exist_ok=True)
    big = np.repeat(np.repeat(rgba, 4, 0), 4, 1)
    # alpha-tested textures must be power-of-two or the material fails to compile: pad with transparent pixels
    ph, pw = pot(big.shape[0]), pot(big.shape[1])
    pad = np.zeros((ph, pw, 4), np.uint8); pad[:big.shape[0], :big.shape[1]] = big; big = pad
    rgb = big[..., :3].copy(); rgb[big[..., 3] == 0] = 0
    Image.fromarray(rgb).save(os.path.join(d, key + '_color.png'))
    Image.fromarray(big[..., 3]).save(os.path.join(d, key + '_trans.png'))
    vm = ['// FreeDM sprite ' + key, 'Layer0', '{', '\tshader "csgo_unlitgeneric.vfx"', '\tF_BLEND_MODE 2', '\tF_RENDER_BACKFACES 1',
          '\tTextureColor "materials/fdm/spr/%s_color.png"' % key, '\tTextureTranslucency "materials/fdm/spr/%s_trans.png"' % key,
          '\tg_flAlphaTestReference "0.500"', '\tg_vColorTint "[1.000000 1.000000 1.000000 0.000000]"', '\tg_flModelTintAmount "1.000"', '}']
    open(os.path.join(d, key + '.vmat'), 'w', newline='\n').write('\n'.join(vm) + '\n')
    return 'materials/fdm/spr/%s.vmat' % key

def star_tris(key, rgba, off):
    h, w = rgba.shape[:2]
    su, sv = w * 4 / pot(w * 4), h * 4 / pot(h * 4)      # the texture is padded to power-of-two
    lo, to = off
    tris = []
    for k in range(3):
        th = math.radians(90 + k * 60)   # first plane faces +x (rotation 1 view)
        rx, ry = -math.sin(th - math.pi / 2), math.cos(th - math.pi / 2)
        # plane spanned by the right vector and up; u along right
        right = (math.cos(th), math.sin(th))
        left_u = -lo; right_u = w - lo
        top = to; bottom = to - h
        def P(u, z):
            return (right[0] * u, right[1] * u, z)
        a = P(left_u, bottom) + (0.0, sv)
        b = P(right_u, bottom) + (su, sv)
        c = P(right_u, top) + (su, 0.0)
        dd = P(left_u, top) + (0.0, 0.0)
        n = (right[1], -right[0], 0.0)
        verts = [(a[0], a[1], a[2], a[3], 1 - a[4]), (b[0], b[1], b[2], b[3], 1 - b[4]), (c[0], c[1], c[2], c[3], 1 - c[4]), (dd[0], dd[1], dd[2], dd[3], 1 - dd[4])]
        tris.append(('fdm_spr', (verts[0], verts[1], verts[2]), n))
        tris.append(('fdm_spr', (verts[0], verts[2], verts[3]), n))
    return tris

def voxel_tris(vt):
    out = []
    for c0, c1, c2, n, c in vt:
        u, v = pal_uv(c)
        out.append(('fdm_pal', tuple((p[0], p[1], p[2], u, v) for p in (c0, c1, c2)), n))
    return out

def main():
    pal_paths = write_palettes()
    skins = [('skin%d' % k, [(pal_paths[0], pal_paths[k])]) for k in range(1, 16)] + [('fuzz', [(pal_paths[0], pal_paths[16])])]
    models = {}
    stats = {}
    for key, bright in FRAMES:
        sprite, frame = key.split('_')
        rots = rotations(sprite, frame)
        if not rots:
            print('no sprite for', key); continue
        shape = SHAPE.get(sprite, 'star')
        if shape == 'rot8' and not all(r in rots for r in range(1, 9)):
            shape = 'star'
        mkey = key.lower()
        if shape == 'star':
            img, off, _ = rots.get(0) or rots.get(1)
            mat = write_star_material(mkey, img)
            write_model(mkey, star_tris(mkey, img, off), {'fdm_spr': mat})
        else:
            vs = 1
            if shape == 'rot8':
                vs = voxel_scale(rots)
                ri = {}
                for r in range(1, 9):
                    idx, off = shrink(pal_index_image(rots[r][0]), rots[r][1], vs)
                    ri[r] = (idx, off, rots[r][2])
                occ, axes, samples = carve_rot8(ri, FORWARD_LIMIT if sprite == 'PLAY' else None)
                faces = colour_rot8(occ, axes, samples)
            else:
                img, off, _ = rots.get(0) or rots.get(1)
                idx = pal_index_image(img)
                if shape == 'lathe':
                    occ, axes, faces = build_lathe(idx, off)
                elif shape == 'box':
                    occ, axes, faces = build_slab(idx, off, min(24, max(4, img.shape[1] * 0.55)))
                else:
                    occ, axes, faces = build_slab(idx, off, 6)
            vt = mesh_voxels(occ, axes, faces)
            if vs != 1: vt = [(np.multiply(c0, vs), np.multiply(c1, vs), np.multiply(c2, vs), n, c) for c0, c1, c2, n, c in vt]
            write_model(mkey, voxel_tris(vt), {'fdm_pal': pal_paths[0]}, skins)
        models[key] = shape
        stats[shape] = stats.get(shape, 0) + 1
    # invisible model for idle props and sound anchors
    d = os.path.join(OUT, 'models/fdm'); os.makedirs(d, exist_ok=True)
    tiny = [('fdm_pal', ((0, 0, 0, 0.03, 0.97), (0.01, 0, 0, 0.03, 0.97), (0, 0.01, 0, 0.03, 0.97)), (0, 0, 1))]
    open(os.path.join(d, 'null.smd'), 'w', newline='\n').write(smd_lines(tiny))
    open(os.path.join(d, 'null.vmdl'), 'w', newline='\n').write(
        VMDL_HEAD % (group('DefaultMaterialGroup', None, [('fdm_pal.vmat', 'materials/fdm/pal/fuzz.vmat')]), 'null', 'models/fdm/null.smd'))
    os.makedirs(os.path.join(OUT, '_gen'), exist_ok=True)
    json.dump(models, open(os.path.join(OUT, '_gen/sprite_models.json'), 'w'))
    print('models', len(models), stats)

main()
