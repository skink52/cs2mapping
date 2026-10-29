"""voxel.py: voxel models for CS2. Paint a 3D grid with palette colours, mesh it into quads (greedy, a few hundred
triangles for a vehicle), write SMD + vmdl with unlit palette materials, and render a picture of it for a HUD or a
preview. Skins (team colours etc.) are material groups that swap the palette texture; a script picks one with
EntFireAtTarget({ target, input: 'Skin', value: n }), n = 0 for the default group, then the skins in order.

Palette: NCOL colours x 4 shades (top, side, end, bottom face) in one small texture, so a whole model is one material
and lighting is baked into the colours (unlit). Colour indices >= FX0 belong to an effect material (e.g. a flame strip
animated with F_TEXTURE_ANIMATION) and are not shaded.

usage (import it):
    import voxel as V
    g = V.Grid(24, 12, 8)                          # x along the model (0 = rear), y across (centred), z up
    g.box(0, 24, -5, 5, 0, 3, 0); g.ellipsoid(14, 0, 4, 5, 3, 3, 1); g.cylinder_x(0, 4, 0, 2, 1.5, 3)
    pal = V.palette([(70, 150, 255), (30, 70, 170), (225, 228, 235), (52, 56, 66)])
    mat = V.write_palette(out, 'materials/mygame/pal_blue', pal)
    red = V.write_palette(out, 'materials/mygame/pal_red', V.palette([(240, 60, 60), (140, 20, 40), (225, 228, 235), (52, 56, 66)]))
    V.write_model(out, 'models/mygame', 'ship', g, scale=3.0, pal_mat=mat, skins={'red': red})
    V.render_voxels(g, pal).save('ship.png')
    voxel.py <addon_out> [preview.png]     builds a small demo model (models/voxel_demo/*) with a skin, a flame,
                                           an effect star and the null model

From space-racer-cs2/tools/cars.py (MIT), made project-neutral.
"""
import os, sys, math
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s2

SHADE = [1.0, 0.78, 0.64, 0.45]     # top, side, end, bottom
FACE_SHADE = [2, 2, 1, 1, 0, 3]      # +x, -x (ends), +y, -y (sides), +z (top), -z (bottom)
DIRS = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
FX0 = 100                            # colour indices from here on use the effect material


# ---------------------------------------------------------------- palette
def palette(colors, glow=(), shade=SHADE):
    """(len(colors)*4, 3) uint8: each colour in 4 face shades; colours whose index is in `glow` barely shade"""
    pal = np.zeros((len(colors) * 4, 3), np.float32)
    for c, col in enumerate(colors):
        for sh in range(4):
            k = shade[sh]
            if c in glow: k = 1.0 if sh == 0 else 0.94
            pal[c * 4 + sh] = np.array(col, np.float32) * k
    return pal.clip(0, 255).astype(np.uint8)


def palette_image(pal):
    """palette entries as 4 x 8 px cells, 8 to a row (32 px wide); rows padded to a power of two"""
    rows = s2.pot(max(1, (len(pal) + 7) // 8))
    img = np.zeros((rows * 8, 32, 3), np.uint8)
    for c in range(len(pal)):
        y, x = (c // 8) * 8, (c % 8) * 4
        img[y:y + 8, x:x + 4] = pal[c]
    return img


def pal_uv(c, n_entries):
    """uv of the centre of palette entry c"""
    rows = s2.pot(max(1, (n_entries + 7) // 8))
    return ((c % 8) * 4 + 2) / 32.0, 1 - ((c // 8) * 8 + 4) / (rows * 8.0)


def write_palette(out, rel_path, pal, comment='voxel palette'):
    """an unlit opaque material with the palette texture; returns its .vmat path"""
    return s2.write_material(out, rel_path, palette_image(pal), comment=comment)


# ---------------------------------------------------------------- the grid
class Grid:
    """occ: bool [L, W, H]; col: colour index per voxel. X runs 0..L (0 = rear), Y is centred across, Z 0..H up.
    Every shape paints voxels whose centre is inside it and returns the mask."""

    def __init__(self, L, W, H):
        self.L, self.W, self.H = L, W, H
        self.occ = np.zeros((L, W, H), bool)
        self.col = np.zeros((L, W, H), np.int16)
        self.X, self.Y, self.Z = np.meshgrid(np.arange(L) + 0.5, np.arange(W) + 0.5 - W / 2, np.arange(H) + 0.5, indexing='ij')

    def paint(self, mask, c):
        self.occ |= mask; self.col[mask] = c; return mask

    def cut(self, mask):
        self.occ &= ~mask; return mask

    def ellipsoid(self, cx, cy, cz, rx, ry, rz, c):
        return self.paint(((self.X - cx) / rx) ** 2 + ((self.Y - cy) / ry) ** 2 + ((self.Z - cz) / rz) ** 2 <= 1, c)

    def box(self, x0, x1, y0, y1, z0, z1, c):
        return self.paint((self.X >= x0) & (self.X < x1) & (self.Y >= y0) & (self.Y < y1) & (self.Z >= z0) & (self.Z < z1), c)

    def taper(self, x0, x1, w0, w1, z0, h0, h1, c, yoff=0):
        """a hull slab from x0 to x1 whose half width goes w0 -> w1 and height h0 -> h1 (rounded cross-section)"""
        t = np.clip((self.X - x0) / max(x1 - x0, 1e-6), 0, 1)
        w = w0 + (w1 - w0) * t; h = h0 + (h1 - h0) * t
        m = (self.X >= x0) & (self.X < x1) & (((self.Y - yoff) / np.maximum(w, 0.01)) ** 2 + ((self.Z - z0) / np.maximum(h, 0.01)) ** 2 <= 1) & (self.Z >= z0)
        return self.paint(m, c)

    def cylinder_x(self, x0, x1, cy, cz, r, c):
        return self.paint((self.X >= x0) & (self.X < x1) & ((self.Y - cy) ** 2 + (self.Z - cz) ** 2 <= r * r), c)

    def cylinder_z(self, cx, cy, z0, z1, r, c):
        return self.paint((self.Z >= z0) & (self.Z < z1) & ((self.X - cx) ** 2 + (self.Y - cy) ** 2 <= r * r), c)

    def flame(self, x0, cy, cz, r, length, bands=8, layers=3):
        """a flame: cones pointing backwards (-x) from x0, outer / mid / core, cut into bands along the length.
        Colours FX0 + layer * bands + band, for flame_frames() / flame_uv()."""
        for k, (rr, ln) in enumerate(((r * 1.15, length), (r * 0.85, length * 0.75), (r * 0.5, length * 0.5))[:layers]):
            t = np.clip((x0 - self.X) / max(ln, 0.1), 0, 1)
            m = (self.X < x0) & (self.X >= x0 - ln) & ((self.Y - cy) ** 2 + (self.Z - cz) ** 2 <= (rr * (1 - t * 0.85)) ** 2)
            band = np.clip(((x0 - self.X) / max(length, 0.1) * bands).astype(int), 0, bands - 1)
            for b in range(bands):
                self.paint(m & (band == b), FX0 + k * bands + b)

    def count(self):
        return int(self.occ.sum())


# ---------------------------------------------------------------- greedy mesher (voxels -> quads)


def edge_trim(g, trim, only=None):
    """neon look (from Neon Racer): voxels on the body's top outline (open above, open to a side, outermost across in
    their column) take colour index `trim`. Use a dark hull colour and put `trim` in palette(glow=...) so the lines glow.
    only: colour indices that may become trim (default all)"""
    o = np.pad(g.occ, 1)
    up_ = ~o[1:-1, 1:-1, 2:]
    lat = ~o[1:-1, 2:, 1:-1] | ~o[1:-1, :-2, 1:-1]
    ys = np.arange(g.W)[None, :, None]
    outer = (ys == np.where(g.occ, ys, -1).max(1, keepdims=True)) | (ys == np.where(g.occ, ys, 999).min(1, keepdims=True))
    edge = g.occ & up_ & lat & outer
    if only is not None: edge &= np.isin(g.col, only)
    g.col[edge] = trim
    return edge


def mesh_voxels(occ, col, origin, scale, n_entries, mat='pal', fx_mat='fx', fx_uv=None):
    """exposed faces merged into rectangles of one colour. origin: world position of voxel (0,0,0)'s corner;
    returns s2 triangles [(material, ((x,y,z,u,v) x3), normal)]. Colours >= FX0 use fx_mat with fx_uv(c)."""
    nx, ny, nz = occ.shape
    pad = np.zeros((nx + 2, ny + 2, nz + 2), bool); pad[1:-1, 1:-1, 1:-1] = occ
    fx_uv = fx_uv or flame_uv
    tris = []
    for fi, d in enumerate(DIRS):
        neigh = pad[1 + d[0]:nx + 1 + d[0], 1 + d[1]:ny + 1 + d[1], 1 + d[2]:nz + 1 + d[2]]
        exposed = occ & ~neigh
        colr = np.where(exposed, col.astype(np.int32) * 4 + np.where(col >= FX0, 0, FACE_SHADE[fi]), -1)
        axis = [i for i in range(3) if d[i] != 0][0]
        ua, va = [i for i in range(3) if i != axis]
        for s in range(occ.shape[axis]):
            sl = np.take(colr, s, axis=axis)
            if (sl < 0).all(): continue
            used = np.zeros(sl.shape, bool)
            U, V = sl.shape
            for i in range(U):
                for j in range(V):
                    c = sl[i, j]
                    if c < 0 or used[i, j]: continue
                    w = 1
                    while i + w < U and sl[i + w, j] == c and not used[i + w, j]: w += 1
                    h = 1
                    while j + h < V and (sl[i:i + w, j + h] == c).all() and not used[i:i + w, j + h].any(): h += 1
                    used[i:i + w, j:j + h] = True
                    plane = s + (1 if d[axis] > 0 else 0)
                    def P(a, b):
                        p = [0.0, 0.0, 0.0]
                        p[axis] = plane; p[ua] = a; p[va] = b
                        return (origin[0] + p[0] * scale, origin[1] + p[1] * scale, origin[2] + p[2] * scale)
                    corners = [P(i, j), P(i + w, j), P(i + w, j + h), P(i, j + h)]
                    n = (float(d[0]), float(d[1]), float(d[2]))
                    e1 = np.subtract(corners[1], corners[0]); e2 = np.subtract(corners[2], corners[0])
                    if np.dot(np.cross(e1, e2), n) < 0: corners = corners[::-1]
                    ci = int(c) // 4
                    m_ = fx_mat if ci >= FX0 else mat
                    u, v = fx_uv(ci) if ci >= FX0 else pal_uv(int(c), n_entries)
                    cv = [(p[0], p[1], p[2], u, v) for p in corners]
                    tris.append((m_, (cv[0], cv[1], cv[2]), n))
                    tris.append((m_, (cv[0], cv[2], cv[3]), n))
    return tris


def write_model(out, rel_dir, name, g, scale, pal_mat, n_entries=None, skins=None, origin=None, fx_mat=None, extra_tris=(), extra_mats=None):
    """mesh the grid and write <rel_dir>/<name>.smd + .vmdl. skins: {skin name: palette vmat} (material groups in
    that order, after the default = skin 1, 2 ...). origin defaults to centred in x / y, bottom at z 0.
    Returns (vmdl path, triangle count)."""
    if n_entries is None: n_entries = int(g.col[g.occ & (g.col < FX0)].max(initial=0) + 1) * 4
    if origin is None: origin = (-g.L / 2 * scale, -g.W / 2 * scale, 0.0)
    tris = mesh_voxels(g.occ, g.col, origin, scale, n_entries) + list(extra_tris)
    mats = {'pal': pal_mat}
    if fx_mat: mats['fx'] = fx_mat
    mats.update(extra_mats or {})
    groups = [(sk, [(pal_mat, vm)]) for sk, vm in (skins or {}).items()]
    return s2.write_model(out, rel_dir, name, tris, mats, groups), len(tris)


# ---------------------------------------------------------------- effects
def flame_uv(c, bands=8, layers=3):
    """uv of flame colour c inside one animation cell (layers * bands texels wide)"""
    return (c - FX0 + 0.5) / (layers * bands), 0.5


WAVE = [1.0, 0.8, 0.55, 0.35, 0.25, 0.35, 0.55, 0.8]


def flame_frames(grad, frames=4, bands=8, layers=3):
    """a (4, frames*cell*... ) strip image: per frame a bright pulse travels from the nozzle to the tip; grad =
    5 colours dark -> bright. Returns (frames side by side, upscaled 4x) as uint8 RGB."""
    cell = layers * bands
    img = np.zeros((4, frames * cell, 3), np.uint8)
    for f in range(frames):
        for layer in range(layers):
            for band in range(bands):
                w = WAVE[(band - 2 * f) % len(WAVE)]
                lvl = 0.6 + layer * 0.9 + w * 2.2 - band * 0.22
                img[:, f * cell + layer * bands + band] = grad[int(np.clip(round(lvl), 0, len(grad) - 1))]
    return np.repeat(np.repeat(img, 4, 0), 4, 1)


def animated_material(out, rel_path, strip, frames, seconds_per_frame=0.07, comment='animated strip'):
    """frames side by side in one texture; CS2's texture animation steps through them (untested in CS2 so far)"""
    return s2.write_material(out, rel_path, strip, comment=comment,
                             extra=('F_TEXTURE_ANIMATION 1', 'g_nNumAnimationCells "%d"' % frames,
                                    'g_vAnimationGrid "[%d.000000 1.000000]"' % frames, 'g_flAnimationTimePerFrame "%.3f"' % seconds_per_frame))


def star_tris(mat, w, h, zoff=0.0):
    """three crossed vertical planes (width w, height h, centred, bottom at zoff) for sprites and effects;
    give the material backfaces=True so both sides draw"""
    tris = []
    for k in range(3):
        th = k * math.pi / 3
        rx, ry = math.cos(th), math.sin(th)
        p = lambda u, z, uu, vv: (rx * u, ry * u, z, uu, vv)
        a = p(-w / 2, zoff, 0, 1); b = p(w / 2, zoff, 1, 1); c = p(w / 2, zoff + h, 1, 0); d = p(-w / 2, zoff + h, 0, 0)
        n = (-ry, rx, 0.0)
        tris.append((mat, (a, b, c), n)); tris.append((mat, (a, c, d), n))
    return tris


def null_model(out, rel_dir, mat, name='null'):
    """an invisible model (one 0.01-unit triangle) for idle script props and sound anchors"""
    tiny = [('fx', ((0, 0, 0, 0, 0), (0.01, 0, 0, 0, 0), (0, 0.01, 0, 0, 0)), (0, 0, 1))]
    return s2.write_model(out, rel_dir, name, tiny, {'fx': mat})


# ---------------------------------------------------------------- pictures
def render_voxels(g, pal, size=256, az=200.0, el=24.0, fill=0.78, ss=3, glow=(), fx_color=None):
    """shaded picture of the grid (RGBA). az = where the camera stands around it in degrees (180 = straight behind,
    0 = in front), el = degrees above the horizon. Exposed faces only, far to near, supersampled ss times.
    fx_color(c) -> (r, g, b) colours effect voxels (default: the palette's first colour)."""
    occ, col = g.occ, g.col
    L, W, H = occ.shape
    a, e = math.radians(az), math.radians(el)
    cdir = np.array([math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)])   # object -> camera
    fwd = -cdir
    right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    light = np.array([-0.4, 0.5, 0.85]); light /= np.linalg.norm(light)
    ctr = np.array([L / 2, 0, H / 2])
    pad = np.zeros((L + 2, W + 2, H + 2), bool); pad[1:-1, 1:-1, 1:-1] = occ
    faces = []
    for fi, d in enumerate(DIRS):
        if np.dot(d, cdir) <= 0: continue
        nb = pad[1 + d[0]:L + 1 + d[0], 1 + d[1]:W + 1 + d[1], 1 + d[2]:H + 1 + d[2]]
        xs, ys, zs = np.where(occ & ~nb)
        ax_n = [i for i in range(3) if d[i] != 0][0]
        ax = [i for i in range(3) if d[i] == 0]
        for x, y, z in zip(xs, ys, zs):
            c = int(col[x, y, z])
            if c >= FX0:
                base = np.array(fx_color(c) if fx_color else pal[0], np.float32)
            else:
                base = pal[min(c * 4 + FACE_SHADE[fi], len(pal) - 1)].astype(np.float32)
                if c not in glow: base = base * (0.7 + 0.45 * max(0.0, float(np.dot(d, light))))
            o = np.array([x, y - W / 2, z], float)
            p0 = o.copy()
            if d[ax_n] > 0: p0[ax_n] += 1
            u = np.zeros(3); u[ax[0]] = 1; v = np.zeros(3); v[ax[1]] = 1
            quad = [p0, p0 + u, p0 + u + v, p0 + v]
            faces.append((float(np.dot(o + 0.5 - ctr, fwd)), quad, tuple(int(t) for t in np.clip(base, 0, 255))))
    faces.sort(key=lambda f: -f[0])
    S = size * ss
    proj = [[(float(np.dot(q - ctr, right)), -float(np.dot(q - ctr, up))) for q in quad] for _, quad, _ in faces]
    allp = np.array([p for pp in proj for p in pp]) if proj else np.zeros((1, 2))
    mn, mx = allp.min(0), allp.max(0)
    sc = S * fill / max(mx[0] - mn[0], mx[1] - mn[1], 1e-6)
    cx, cy = (mn + mx) / 2
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    for (depth, quad, c), pp in zip(faces, proj):
        pts = [(S / 2 + (px - cx) * sc, S / 2 + (py - cy) * sc) for px, py in pp]
        dr.polygon(pts, fill=c + (255,), outline=tuple(max(0, v - 30) for v in c) + (255,))
    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- demo
def demo(out, preview=None, rel='models/voxel_demo', mat_dir='materials/voxel_demo'):
    """a small hover ship with a flame, a red skin, an effect star and the null model"""
    trim, dark, glass, glow_c = (225, 228, 235), (52, 56, 66), (120, 220, 255), (255, 200, 90)
    blue = palette([(70, 150, 255), (30, 70, 170), trim, dark, glass, glow_c], glow=(5,))
    red = palette([(240, 60, 60), (140, 20, 40), trim, dark, glass, glow_c], glow=(5,))
    m_blue = write_palette(out, mat_dir + '/pal_blue', blue)
    m_red = write_palette(out, mat_dir + '/pal_red', red)
    grad = [(110, 30, 120), (220, 60, 200), (255, 150, 240), (200, 180, 210), (255, 255, 255)]
    m_fx = animated_material(out, mat_dir + '/flame', flame_frames(grad), 4)
    g = Grid(36, 18, 9)
    g.taper(14, 34, 5.5, 1.2, 1.5, 3.2, 1.6, 0)                  # hull, narrowing to the nose
    g.taper(20, 30, 3.0, 2.2, 3.0, 2.6, 1.8, 4)                  # canopy
    g.box(16, 26, -8.5, 8.5, 1.8, 2.6, 1)                        # wings
    g.box(14, 18, -0.7, 0.7, 3.0, 7.5, 1)                        # fin
    g.cylinder_x(12, 17, 0, 2.6, 1.7, 3)                         # engine
    g.cylinder_x(12, 13.5, 0, 2.6, 1.3, 5)                       # engine glow
    g.flame(12, 0, 2.6, 1.3, 12)                                 # flame out the back
    path, n = write_model(out, rel, 'ship', g, 3.0, m_blue, len(blue), skins={'red': m_red}, origin=(-18 * 3.0, -9 * 3.0, 8.0), fx_mat=m_fx)
    m_star = s2.write_material(out, mat_dir + '/star', np.full((16, 16, 3), 255, np.uint8),
                               (np.hypot(*np.mgrid[-7.5:8.5, -7.5:8.5]) < 7).astype(np.uint8) * 255, blend=2, backfaces=True)
    star = s2.write_model(out, rel, 'star', star_tris('fx', 60, 60), {'fx': m_star})
    nul = null_model(out, rel, m_star)
    if preview:
        fxc = lambda c: grad[min(4, 1 + (c - FX0) // 8)]
        sheet = Image.new('RGBA', (3 * 256, 256), (14, 14, 22, 255))
        for i, (az, p) in enumerate(((200, blue), (135, blue), (300, red))):
            sheet.alpha_composite(render_voxels(g, p, 256, az, 22, glow=(5,), fx_color=fxc), (i * 256, 0))
        sheet.save(preview)
    return dict(ship=path, tris=n, voxels=g.count(), star=star, null=nul)


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    r = demo(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print('voxel demo: %s (%d voxels, %d triangles), %s, %s' % (r['ship'], r['voxels'], r['tris'], r['star'], r['null']))
