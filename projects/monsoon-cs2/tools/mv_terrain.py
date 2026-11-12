"""mg_monsoon world geometry: terrain tiles (vmapgen.Terrain), karst towers, water sheets, sky shell, player-space lightmap shells.
Everything here writes Hammer meshes through vmesh/vmaplib into vmaplib.new_children under the given vis group.
"""
import math, os
import numpy as np
import vmaplib, vmesh, vmapgen as G
import layout as L
import terrain_img as TI
from noise import fbm, smoothstep

# Valve blend materials (A = layer at weight 0, B = layer at weight 1)
BLEND_VALLEY = 'materials/de_ancient/hr_ancient_blend_groundmud03-groundgrass_01_wet.vmat'     # A mud, B grass
BLEND_ROCK = 'materials/de_ancient/hr_ancient_blend_groundrock01-groundmoss02-wet-b.vmat'        # A rock, B moss
WATER = 'materials/de_nuke/hr_nuke/hr_river_water_001.vmat'
WATER_PADDY = 'materials/de_aztec/hr_aztec/hr_aztec_water_shallow.vmat'
NODRAW = 'materials/tools/toolsnodraw.vmat'
CLIP = 'materials/tools/toolsplayerclip.vmat'
SKYBOX = 'materials/tools/toolsskybox.vmat'
for m in (BLEND_VALLEY, BLEND_ROCK, WATER, WATER_PADDY): vmesh.TEX_SIZE[m] = (1024, 1024)
vmesh.TEX_SIZE[NODRAW] = (64, 64); vmesh.TEX_SIZE[CLIP] = (64, 64); vmesh.TEX_SIZE[SKYBOX] = (64, 64)


# ---------------------------------------------------------------- terrain
def tile_res(cx, cy):
    """cell size per 512 tile: 16 over the paddies, 32 around the flags and bases, 64 over the valley, 128 on the outer slopes"""
    gx, gy = np.meshgrid(cx + np.linspace(-256, 256, 9), cy + np.linspace(-256, 256, 9))
    if L.in_paddies(gx.ravel(), gy.ravel()).any(): return 16      # 12 Nov review: 32-u cells cut the 36-u dikes (water edges showed at the corners)
    near = min(math.hypot(cx - fx, cy - fy) for _, _, (fx, fy) in L.FLAGS)
    near = min(near, math.hypot(cx - L.CT_BASE[0], cy - L.CT_BASE[1]) - 300, math.hypot(cx - L.T_BASE[0], cy - L.T_BASE[1]) - 300)
    if near < 1150 or L.in_paddies(np.array([cx]), np.array([cy]))[0]: return 32
    if min(math.hypot(cx - px, cy - py) for px, py in L.TUNNEL_PORTALS) < 1000 or math.hypot(cx - L.FARM[0], cy - L.FARM[1]) < 700: return 32   # portal cuts are 32-u cells
    if abs(cx) <= L.MAP_X + 256 and abs(cy) <= L.MAP_Y + 256 and abs(cy - float(L.river_y(cx))) < 3300: return 64
    d = L.detail(*np.meshgrid(cx + np.linspace(-224, 224, 8), cy + np.linspace(-224, 224, 8)))      # eroded relief: ravines need 64-u cells
    if np.abs(d).max() > 10.0: return 64
    return 128


def karst_cut(CX, CY, r):
    """terrain cells fully under a karst tower are left out (the tower mesh closes the ground)"""
    cut = np.zeros(CX.shape, bool)
    for (kx, ky, kr, kh, ks) in L.KARST:
        d = np.hypot(CX - kx, CY - ky)
        cut |= d < kr * 0.78 - r * 0.72
    return cut


_IMG = {}


def img(name):
    """a 0..1 image from tools/data as a Field (rock, mud, grass, cavity, trees, undergrowth); None if make_detail.py has not run"""
    if name not in _IMG:
        base = L.detail_field()
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        f = os.path.join(d, ('density_%s.png' if name in ('trees', 'undergrowth') else 'splat_%s.png') % name)
        _IMG[name] = base.like(TI.load_mask(f, base)) if base is not None and os.path.isfile(f) else None
    return _IMG[name]


def img_at(name, x, y, default=1.0):
    """the image value at world points (default where make_detail.py has not run)"""
    f = img(name)
    return f(x, y) if f is not None else np.full(np.shape(x), float(default))


def paint(X, Y, Z):
    cell = float(X[1, 0] - X[0, 0]) if X.shape[0] > 1 else 32.0
    sl = L.grid_slope(Z, cell)
    w, tint = L.paint_weight(X, Y, Z, sl)
    if img('mud') is not None:
        free = np.abs(L.detail(X, Y)) > 0.5                       # only where the erosion worked: designed ground keeps its paint
        w = np.where(free, np.clip(w - 0.8 * img('mud')(X, Y) - 0.6 * img('rock')(X, Y), 0, 1), w)
        tint = np.where(free, np.clip(tint * (1.12 - 0.24 * img('cavity')(X, Y)), 0.55, 1.0), tint)
    pa = np.zeros(X.shape + (4,)); pa[..., 0] = w; pa[..., 2] = 0.35
    ti = np.ones(X.shape + (4,)); ti[..., 0] = ti[..., 1] = ti[..., 2] = tint
    return pa, ti


def build_terrain(group, holes_extra=None):
    """the whole valley floor; holes_extra(CX, CY, r) -> bool adds cells to leave out (tunnel portals)"""
    T = G.Terrain(L.height, -L.TERRAIN_X, -L.TERRAIN_Y, L.TERRAIN_X, L.TERRAIN_Y, tile=512, res=tile_res)
    def holes(CX, CY, r):
        cut = karst_cut(CX, CY, r)
        if holes_extra is not None: cut |= np.asarray(holes_extra(CX, CY, r), bool)
        return cut
    nq = T.build(BLEND_VALLEY, paint=paint, holes=holes, group=group, bake=True, shadows=True)
    print('terrain: %d tiles, %d quads' % (len(T.tiles), nq))
    return T


# ---------------------------------------------------------------- karst towers
def karst_mesh(kx, ky, r, h, seed, landable, group, n_th=44, n_t=22):
    """a limestone tower: polar sheet with fBm walls, an undercut base, a bulge and either a flat crown or jagged peaks.
    Walls carry the rock/moss blend painted by slope. The mesh starts 70 u below the ground so no gap can show."""
    rng = np.random.RandomState(seed)
    z0 = float(L.height(np.array([kx]), np.array([ky]))[0]) - 70.0
    th = np.linspace(0, 2 * np.pi, n_th, endpoint=False)
    t = np.linspace(0, 1, n_t + 1)
    TH, Tt = np.meshgrid(th, t, indexing='ij')
    # radius profile: a wide talus foot, nearly vertical fluted walls with a slight mid-height belly, narrowing to the rim
    prof = 1.0 - 0.14 * smoothstep(0.0, 0.18, Tt) + 0.07 * np.exp(-((Tt - 0.55) / 0.2) ** 2) - 0.13 * smoothstep(0.5, 1.0, Tt)
    lumps = fbm(np.cos(TH) * 1.6 + seed, np.sin(TH) * 1.6, Tt * 1.4, 3, seed=60 + seed)                 # slow lumps
    flutes = fbm(np.cos(TH) * 6.5, np.sin(TH) * 6.5 + seed, Tt * 1.2, 3, seed=65 + seed)                # vertical fluting
    nz = lumps; nz2 = fbm(np.cos(TH) * 5.0, np.sin(TH) * 5.0 + seed, Tt * 9.0, 3, seed=70 + seed)
    ledges = 0.05 * np.sin(Tt * 28.0 + 2.0 * lumps) * smoothstep(0.1, 0.3, Tt)                           # bedding ledges
    rad = r * prof * (1.0 + 0.11 * lumps + 0.10 * flutes + 0.04 * nz2 + ledges)
    rad = np.maximum(rad, r * 0.3)
    zz = z0 + (h + 70.0) * Tt + 18.0 * nz2 * (1 - Tt)
    # the rim: a flat crown (landable) or peaks
    if landable:
        rim_h = zz[:, -1].mean()
        zz[:, -1] = rim_h + 6.0 * nz[:, -1]
    else:
        zz[:, -1] = zz[:, -1] + 90.0 * (0.5 + 0.5 * np.sin(th * 3 + seed)) * (0.6 + 0.4 * nz[:, -1])
    X = kx + rad * np.cos(TH); Y = ky + rad * np.sin(TH)
    verts = []; idx = np.zeros((n_th, n_t + 1), np.int64)
    for i in range(n_th):
        for j in range(n_t + 1):
            idx[i, j] = len(verts); verts.append((X[i, j], Y[i, j], zz[i, j]))
    faces = []
    for i in range(n_th):
        i2 = (i + 1) % n_th
        for j in range(n_t):
            # outward facing: CCW seen from outside -> (i, j) (i2, j) (i2, j+1) (i, j+1) ... check with normal
            faces.append([idx[i, j], idx[i2, j], idx[i2, j + 1], idx[i, j + 1]])
    # crown: centre vertex + fan (landable gets a gentle dome; peaks get a sunken centre)
    cz = (zz[:, -1].mean() + (14.0 if landable else -40.0))
    ci = len(verts); verts.append((kx, ky, cz))
    for i in range(n_th):
        i2 = (i + 1) % n_th
        faces.append([idx[i, n_t], idx[i2, n_t], ci])
    verts = np.asarray(verts, float)
    # winding check on one side quad: normal should point away from the axis
    a, b, c = verts[faces[0][0]], verts[faces[0][1]], verts[faces[0][2]]
    nrm = np.cross(b - a, c - a); out = np.array([a[0] - kx, a[1] - ky, 0.0])
    if nrm @ out < 0: faces = [f[::-1] for f in faces]
    # paint: moss on the upward faces and in the lower third, bare rock on the overhangs
    # per-vertex "upness" from the profile slope: where the radius shrinks with height the wall faces down
    drad = np.gradient(rad, axis=1); dz = np.gradient(zz, axis=1)
    face_up = np.clip(0.5 - 0.5 * (drad / (np.abs(dz) + 1e-6)) * 6.0, 0, 1)      # radius decreasing fast -> overhang -> 0
    moss = 0.75 * face_up.ravel() * (0.55 + 0.45 * (fbm(X.ravel() / 90.0, Y.ravel() / 90.0, zz.ravel() / 90.0, 3, seed=80 + seed) * 0.5 + 0.5))
    moss = np.clip(moss + 0.35 * (1 - Tt.ravel()) * face_up.ravel(), 0, 1)
    moss = np.concatenate([moss, [0.9 if landable else 0.4]])
    pa = np.zeros((len(verts), 4)); pa[:, 0] = moss; pa[:, 2] = 0.35
    ti = np.ones((len(verts), 4)); ti[:, :3] = (0.82 + 0.18 * moss)[:, None]
    m = vmesh.polymesh_open(verts, faces, [BLEND_ROCK] * len(faces), scale=0.5, paint=pa, tint=ti)
    vmesh.mesh_node(m, group, bake=True, shadows=True, smoothing=70.0)
    top_z = float(cz)
    rim_r = np.hypot(X[:, -1] - kx, Y[:, -1] - ky)
    return dict(x=kx, y=ky, r=r, top=top_z, rim=float(zz[:, -1].mean()), z0=z0, rim_r=rim_r.tolist(), rim_z=zz[:, -1].tolist(), rim_min=float(rim_r.min()))


def crown_z(kk, x, y):
    """height of a tower's crown at a point (the fan from the centre vertex to the rim ring); None outside the rim"""
    dx, dy = x - kk['x'], y - kk['y']; d = math.hypot(dx, dy)
    n = len(kk['rim_r']); a = (math.atan2(dy, dx) % (2 * math.pi)) / (2 * math.pi) * n
    i = int(a) % n; j = (i + 1) % n; t = a - int(a)
    rr = kk['rim_r'][i] * (1 - t) + kk['rim_r'][j] * t; rz = kk['rim_z'][i] * (1 - t) + kk['rim_z'][j] * t
    rr = min(rr, kk['rim_r'][i], kk['rim_r'][j]) if d > 0.8 * rr else rr
    if d > rr: return None
    return kk['top'] + (rz - kk['top']) * d / max(rr, 1e-6)


def build_karst(group):
    out = []
    for (kx, ky, kr, kh, ks) in L.KARST:
        out.append(karst_mesh(kx, ky, kr, kh, ks, ks in L.KARST_LANDABLE, group))
    print('karst: %d towers' % len(out))
    return out


# ---------------------------------------------------------------- water
_TRES = {}


def mesh_low(x, y):
    """the lowest the terrain mesh can be at points (x, y): layout.height at the corners of the tile's cells (tile_res: 32 / 64 / 128 u),
    the lower of both triangle splits. Water edges are fitted against this, not the smooth field (12 Nov review: paddy edges 0.5-3 u
    over the 32-u mesh where the field had 8 u to spare)"""
    x = np.atleast_1d(np.asarray(x, float)); y = np.atleast_1d(np.asarray(y, float)); out = np.empty(x.shape)
    for n in range(len(x)):
        tx, ty = math.floor(x[n] / 512.0) * 512.0 + 256.0, math.floor(y[n] / 512.0) * 512.0 + 256.0
        if (tx, ty) not in _TRES: _TRES[(tx, ty)] = tile_res(tx, ty)
        cs = _TRES[(tx, ty)]; x0 = math.floor(x[n] / cs) * cs; y0 = math.floor(y[n] / cs) * cs; u = (x[n] - x0) / cs; v = (y[n] - y0) / cs
        h00, h10, h01, h11 = (float(q) for q in L.height(np.array([x0, x0 + cs, x0, x0 + cs]), np.array([y0, y0, y0 + cs, y0 + cs])))
        a_ = h00 + u * (h10 - h00) + v * (h11 - h10) if u >= v else h00 + v * (h01 - h00) + u * (h11 - h01)
        b_ = h00 + u * (h10 - h00) + v * (h01 - h00) if u + v <= 1 else h11 + (1 - u) * (h01 - h11) + (1 - v) * (h10 - h11)
        out[n] = min(a_, b_)
    return out


def strip_sheet(pts_xy, half_w, z, mat, group, step_t=None, cols=3, square=(), fit=False):
    """a flat water sheet along a polyline (centre line pts) of half width half_w. fit: each side widens (per vertex, up to 320 u more)
    until its edge lies 4 u under the ground (12 Nov review: a fixed width left edges hanging over the banks)"""
    P = np.asarray(pts_xy, float)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); cum = np.concatenate([[0], np.cumsum(seg)])
    n = len(P)
    nr = []
    for i in range(n):
        a = P[max(i - 1, 0)]; b = P[min(i + 1, n - 1)]
        d = b - a; d /= max(np.linalg.norm(d), 1e-9); nrm = np.array([-d[1], d[0]])
        if (i == 0 and 'start' in square) or (i == n - 1 and 'end' in square): nrm = np.array([0.0, 1.0]) / max(abs(d[0]), 0.5)    # cut along y: the next sheet starts on this line
        nr.append(nrm)
    Wd = np.full((n, 2), float(half_w))
    if fit:
        ws = half_w + np.arange(0.0, 321.0, 8.0)
        for i in range(n):
            for k, sg in enumerate((-1.0, 1.0)):
                ex_, ey_ = P[i, 0] + nr[i][0] * sg * ws, P[i, 1] + nr[i][1] * sg * ws
                # the mesh is 64 / 128-u cells on the outer reaches: the lowest of the point and four around it at 64 u
                g = np.min([L.height(ex_ + ox, ey_ + oy) for (ox, oy) in ((0, 0), (64, 0), (-64, 0), (0, 64), (0, -64))], axis=0)
                ok = np.nonzero(g >= z + 4.0)[0]
                Wd[i, k] = ws[ok[0]] + 8.0 if len(ok) else ws[-1]
        Wd = np.maximum(Wd, np.maximum(np.roll(Wd, 1, 0), np.roll(Wd, -1, 0)))       # the edge between two vertices dips: take the wider neighbour
    verts = []; idx = np.zeros((n, cols + 1), np.int64)
    for i in range(n):
        nrm = nr[i]
        for j in range(cols + 1):
            s = -1 + 2 * j / cols; w = Wd[i, 0] if s < 0 else Wd[i, 1]
            vx = P[i, 0] + nrm[0] * w * s
            if 'end' in square: vx = min(vx, P[-1, 0])            # a fitted (wider) strip must not reach past its square end into the next sheet
            if 'start' in square: vx = max(vx, P[0, 0])
            idx[i, j] = len(verts); verts.append((vx, P[i, 1] + nrm[1] * w * s, z))
    faces = []
    for i in range(n - 1):
        for j in range(cols):
            faces.append([idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1]])
    verts = np.asarray(verts, float)
    a, b, c = verts[faces[0][0]], verts[faces[0][1]], verts[faces[0][2]]
    if np.cross(b - a, c - a)[2] < 0: faces = [f[::-1] for f in faces]
    m = vmesh.polymesh_open(verts, faces, [mat] * len(faces), scale=0.5)
    vmesh.mesh_node(m, group, bake=False, shadows=False)
    return len(faces)


def rect_sheet(x0, y0, x1, y1, z, mat, group, cell=256.0):
    nx = max(1, int(round((x1 - x0) / cell))); ny = max(1, int(round((y1 - y0) / cell)))
    X, Y = np.meshgrid(np.linspace(x0, x1, nx + 1), np.linspace(y0, y1, ny + 1), indexing='ij')
    Z = np.full(X.shape, float(z))
    verts, faces, mats = vmesh.grid_sheet(X, Y, Z, lambda i, j: mat)
    vmesh.mesh_node(vmesh.polymesh_open(verts, faces, mats, scale=0.5), group, bake=False, shadows=False)
    return len(faces)


def build_water(group):
    n = 0
    # the river: lower reach from the fall to the marsh, the upper reach above the fall
    MX = L.MARSH_X0 - 8.0          # the river / marsh seam on a 16-u cell edge, not through cell centres (check_play read it as a z-fight)
    xs = np.arange(L.FALL_X + 4.0, MX + 1e-6, 96.0)
    pts = [(float(x), float(L.river_y(x))) for x in xs] + [(MX, float(L.river_y(MX)))]
    n += strip_sheet(pts, L.RIVER_HW + 50.0, L.WATER_Z, WATER, group, square=('end',), fit=True)        # 12 Nov review: its slanted end overlapped the marsh sheet (z-fight)
    xs = np.arange(-L.TERRAIN_X, L.FALL_X - 4.0, 96.0)
    pts = [(float(x), float(L.river_y(x))) for x in xs] + [(L.FALL_X - 4.0, float(L.river_y(L.FALL_X - 4.0)))]
    n += strip_sheet(pts, L.RIVER_HW + 50.0, L.UPPER_WATER_Z, WATER, group, fit=True)                   # fitted: a fixed +86 hung over the south bank
    # the marsh: one wide sheet, the ground pokes through as islands; each long edge moves out until the ground along it is 4 u over the water
    xm = np.linspace(MX, L.TERRAIN_X, 160)
    ry = L.river_y(xm); yr0 = float(ry.min()) - 1080.0; yr1 = float(ry.max()) + 1080.0
    while yr0 > -L.TERRAIN_Y and not (L.height(xm, np.full(xm.shape, yr0)) >= L.WATER_Z + 4.0).all(): yr0 -= 32.0
    while yr1 < L.TERRAIN_Y and not (L.height(xm, np.full(xm.shape, yr1)) >= L.WATER_Z + 4.0).all(): yr1 += 32.0
    yr0 -= 64.0; yr1 += 64.0                                      # one mesh cell more: the 64-u mesh dips between the samples
    n += rect_sheet(MX, yr0, L.TERRAIN_X, yr1, L.WATER_Z, WATER, group, cell=512.0)
    # the oxbow lake
    n += strip_sheet(L.OXBOW, 86.0, L.WATER_Z, WATER, group, cols=2)
    # paddies: one sheet per cell, inset past the dike foot so the edge is buried in the rising floor
    for (x0, x1, yr0_, yr1_, cx, cy, rows_up, z0) in ((L.PADDY_X0, L.PADDY_X1, L.PADDY_YR0, L.PADDY_YR1, L.PADDY_CELL_X, L.PADDY_CELL_Y, -1, 14.0),
                                                     (L.PADDY2_X0, L.PADDY2_X1, L.PADDY2_YR0, L.PADDY2_YR1, L.PADDY2_CELL_X, L.PADDY2_CELL_Y, 1, 16.0)):
        ncol = int(round((x1 - x0) / cx)); nrow = int(round((yr1_ - yr0_) / cy))
        for c in range(ncol):
            for r_ in range(nrow):
                ridx = (nrow - 1 - r_) if rows_up < 0 else r_
                floor = z0 + 8.0 * ridx + 1.5 * c
                # 12 Nov review: one inset for all four sides left edges 0.5 u over the ground (a few under it on the mesh): each side
                # moves out, up the dike flank, until the ground along it stands 4 u over the water
                ins = [L.PADDY_DIKE_HW + 16.0] * 4                 # west, east, south, north
                tt = np.linspace(0.0, 1.0, 48)
                for k in range(4):
                    best = None
                    while ins[k] > 4.0:
                        ax0, ax1 = x0 + c * cx + ins[0], x0 + (c + 1) * cx - ins[1]
                        by0, by1 = yr0_ + r_ * cy + ins[2], yr0_ + (r_ + 1) * cy - ins[3]
                        ex_ = [np.full(48, ax0), np.full(48, ax1), ax0 + (ax1 - ax0) * tt, ax0 + (ax1 - ax0) * tt][k]
                        ey_ = [by0 + (by1 - by0) * tt, by0 + (by1 - by0) * tt, np.full(48, by0), np.full(48, by1)][k]
                        gmin = float((np.minimum(L.height(ex_, ey_ + L.river_y(ex_)), mesh_low(ex_, ey_ + L.river_y(ex_))) - (floor - 1.0)).min())
                        if best is None or gmin > best[0]: best = (gmin, ins[k])
                        if gmin >= 6.0: break                        # measured on the mesh (mesh_low): 6 u to spare
                        ins[k] -= 4.0
                    if best is not None and best[0] < 6.0: ins[k] = best[1]      # never reached 6 u: the inset with the most clearance
                ax0, ax1 = x0 + c * cx + ins[0], x0 + (c + 1) * cx - ins[1]
                by0, by1 = yr0_ + r_ * cy + ins[2], yr0_ + (r_ + 1) * cy - ins[3]
                # cells follow the river: convert yr to y per column of vertices (the river only curves gently over one cell)
                X, Y = np.meshgrid(np.linspace(ax0, ax1, 3), np.linspace(by0, by1, 3), indexing='ij')
                Yw = Y + L.river_y(X)
                Z = np.full(X.shape, floor - 1.0)
                verts, faces, mats = vmesh.grid_sheet(X, Yw, Z, lambda i, j: WATER_PADDY)
                vmesh.mesh_node(vmesh.polymesh_open(verts, faces, mats, scale=0.5), group, bake=False, shadows=False)
                n += len(faces)
    print('water: %d faces' % n)
    return n


# ---------------------------------------------------------------- shells, clips
def build_sky_shell(group):
    v, faces = vmaplib.box_faces(-L.SKY_X, -L.SKY_Y, L.SKY_Z0, L.SKY_X, L.SKY_Y, L.SKY_Z1, inward=True)
    vmesh.mesh_node(vmesh.polymesh_open(v, faces, [SKYBOX] * 6, scale=1.0), group, bake=False, shadows=False, visexclude=False)


def clip_box(x0, y0, z0, x1, y1, z1, group):
    vmesh.mesh_node(vmesh.box_mesh(x0, y0, z0, x1, y1, z1, CLIP), group, bake=False, shadows=False, visexclude=True)


def clip_slab(p, q, z0, z1, group, t=4.0):
    """thin player clip between two xy points"""
    p = np.asarray(p, float); q = np.asarray(q, float)
    d = q - p; l = np.linalg.norm(d)
    if l < 1: return
    R = np.array([[d[0] / l, -d[1] / l, 0], [d[1] / l, d[0] / l, 0], [0, 0, 1.0]])
    c = ((p + q) / 2).tolist() + [(z0 + z1) / 2]
    vmesh.mesh_node(vmesh.oriented_box_mesh(c, (l / 2, t / 2, (z1 - z0) / 2), R, CLIP), group, bake=False, shadows=False, visexclude=True)


def build_edge_clips(group):
    """keep players inside the play space: tall clip walls just outside it (helicopters use the script's soft box)"""
    X, Y = L.MAP_X + 200.0, L.MAP_Y + 200.0
    zlo, zhi = -200.0, 1400.0
    clip_box(-X - 16, -Y, zlo, -X, Y, zhi, group); clip_box(X, -Y, zlo, X + 16, Y, zhi, group)
    clip_box(-X, -Y - 16, zlo, X, -Y, zhi, group); clip_box(-X, Y, zlo, X, Y + 16, zhi, group)


# ---------------------------------------------------------------- lightmap player space
def build_lmres(group, cell=64.0):
    """toolslightmapres shell over the walkable band: the valley within 3400 of the river plus the bases"""
    x0, y0 = -L.MAP_X, -L.MAP_Y
    nx, ny = int(2 * L.MAP_X / cell), int(2 * L.MAP_Y / cell)
    CX = x0 + (np.arange(nx) + 0.5) * cell; CY = y0 + (np.arange(ny) + 0.5) * cell
    CX, CY = np.meshgrid(CX, CY, indexing='ij')
    occ = np.abs(CY - L.river_y(CX)) < 3300.0
    occ |= np.hypot(CX - L.CT_BASE[0], CY - L.CT_BASE[1]) < L.CT_FOOT_R
    occ |= np.hypot(CX - L.T_BASE[0], CY - L.T_BASE[1]) < L.T_FOOT_R
    occ &= L.karst_dist(CX, CY) > -20.0
    G.lmres_terrain(occ, x0, y0, cell, L.height, below=8.0, above=160.0, samples=2, group=group)
    return int(occ.sum())
