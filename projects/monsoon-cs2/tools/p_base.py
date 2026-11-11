"""Firebase and camp structures: log-and-sandbag bunkers, the FDC bunker, PSP helipad, GP tents, CONEX, guard tower, fuel bladder,
55-gal drums, water trailer, latrine, TOC antenna mast, ammo cans and crates, cots, PRC-25, jerry cans, rucksacks, the arms rack
(kit station), signs (FSB, LZ, claymore, mines), a culvert bunker; T camp: thatched FDC hooch is in p_village.
Origins on the ground; doors / fronts face +x unless noted.
"""
import numpy as np
import geo
import mv_geo as MG
import mv_shaders as M
import shaders as S
from noise import fbm
import p_sandbag


def sandbag_row(length, courses, lod, seed, y=0.0, z=0.0, yaw=0.0):
    w, h = p_sandbag.wall(length=length, courses=courses, lod=lod, seed=seed, top=courses > 1)
    w.transform(geo.rot('z', yaw), (0, y, z))
    return w, h


def log_wall(x0, x1, y, z0, z1, mat, seed, r=4.2, lod=0):
    """stacked logs along x at y, from z0 to z1"""
    m = geo.Mesh(); rng = np.random.RandomState(seed)
    z = z0 + r
    k = 0
    while z < z1:
        pts = [(x0 + rng.uniform(-3, 3), y, z), ((x0 + x1) / 2, y + rng.uniform(-0.6, 0.6), z), (x1 + rng.uniform(-3, 3), y, z)]
        m.add(geo.tube(pts, r * rng.uniform(0.9, 1.08), sides=10 if lod == 0 else 6, mat=mat, part=geo.frame(seed=seed + k, tone=rng.rand())))
        z += 2 * r * 0.92; k += 1
    return m


def bunker(lod=0, seed=61, kind='large', gun=False):
    """log-and-sandbag fighting bunker: timber frame, log walls, firing slit to +x, sandbag parapet and roof layers under PSP + sandbags,
    an open back with a step down. Floor is 24 u below the ground (dug in): the terrain is left as is, the prop's floor sits at z -24."""
    L, W, H = (200, 150, 96) if kind == 'large' else (150, 120, 90)
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    floor_z = -24.0
    # floor (duckboards) and the dug walls (earth faces), rear step
    m.add(MG.box(-L / 2, -W / 2, floor_z - 2, L / 2, W / 2, floor_z, 'wood', p))
    # corner posts and beams
    for (sx, sy) in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        m.add(MG.cyl((sx * (L / 2 - 6), sy * (W / 2 - 6), floor_z), (sx * (L / 2 - 6), sy * (W / 2 - 6), H), 5.0, 'wood_dark', p, sides=8))
    for sy in (-1, 1):
        m.add(MG.cyl((-L / 2 + 2, sy * (W / 2 - 6), H - 4), (L / 2 - 2, sy * (W / 2 - 6), H - 4), 5.0, 'wood_dark', p, sides=8))
    for sx in (-1, 1):
        m.add(MG.cyl((sx * (L / 2 - 6), -W / 2 + 2, H - 4), (sx * (L / 2 - 6), W / 2 - 2, H - 4), 5.0, 'wood_dark', p, sides=8))
    # log walls: sides full height, front up to the slit and above it, back half height (entrance gap in the middle)
    for sy in (-1, 1):
        lw = log_wall(-L / 2, L / 2, sy * (W / 2), floor_z, H - 8, 'wood_dark', seed + 1 + sy, lod=lod)
        lw.transform(geo.rot('z', 0)); m.add(lw)
    fw = log_wall(-W / 2, W / 2, 0, floor_z, 40, 'wood_dark', seed + 5, lod=lod); fw.transform(geo.rot('z', 90), (L / 2, 0, 0)); m.add(fw)
    fw2 = log_wall(-W / 2, W / 2, 0, 64, H - 8, 'wood_dark', seed + 6, lod=lod); fw2.transform(geo.rot('z', 90), (L / 2, 0, 0)); m.add(fw2)
    for sy in (-1, 1):   # slit side posts
        m.add(MG.box(L / 2 - 6, sy * (W / 2 - 10) - 4, 40, L / 2 + 4, sy * (W / 2 - 10) + 4, 64, 'wood_dark', p))
    for sy in (-1, 1):   # back wall halves
        bw = log_wall(-W / 2 if sy < 0 else 26, -26 if sy < 0 else W / 2, 0, floor_z, H - 8, 'wood_dark', seed + 8 + sy, lod=lod)
        bw.transform(geo.rot('z', 90), (-L / 2, 0, 0)); m.add(bw)
    # roof: PSP sheet, then two layers of sandbags; a sandbag parapet around the slit
    m.add(MG.box(-L / 2 - 10, -W / 2 - 10, H - 4, L / 2 + 14, W / 2 + 10, H, 'psp', p))
    for row, zz in enumerate((H, H + 5)):
        for k in range(int((L + 20) / 64)):
            for yy in (-W / 2 + 8, -W / 2 + 32, 0, W / 2 - 32, W / 2 - 8):
                sb, hh = sandbag_row(64, 1, lod, seed + 20 + k + row * 7 + int(yy), y=yy + (10 if row else 0), z=zz, yaw=90)
                sb.transform(None, (-L / 2 + 32 + k * 64 + (16 if row else 0), 0, 0)); m.add(sb)
    sb, hh = sandbag_row(W + 20, 2, lod, seed + 40, yaw=90); sb.transform(None, (L / 2 + 20, 0, 0)); m.add(sb)   # parapet in front of the slit
    # interior: ammo cans, a bench, a lamp hook, the gun pintle post when it is an MG bunker
    m.add(MG.box(-L / 2 + 10, -W / 2 + 10, floor_z, -L / 2 + 40, -W / 2 + 60, floor_z + 20, 'wood', p))
    for k in range(3):
        m.add(MG.box(L / 2 - 60 + k * 14, W / 2 - 30, floor_z, L / 2 - 48 + k * 14, W / 2 - 12, floor_z + 10, 'od', p, r=0.5))
    if gun:
        m.add(MG.box(L / 2 - 30, -16, floor_z, L / 2 - 8, 16, floor_z + 2, 'gunsteel', p))
    # sand/earth berm around the outside up to the roof line
    bp = geo.frame(seed=seed + 50)
    berm = MG.loft([(-L / 2 - 40, MG.rrect_section(W / 2 + 44, -6, H - 30, 2.4, n=16)), (-L / 2 + 10, MG.rrect_section(W / 2 + 30, -6, H - 8, 2.8, n=16)),
                    (L / 2 - 10, MG.rrect_section(W / 2 + 30, -6, H - 8, 2.8, n=16)), (L / 2 + 30, MG.rrect_section(W / 2 + 40, -6, H - 34, 2.4, n=16))],
                   'earth', bp, n=16, cap_front=False, cap_back=False)
    MG.remove_faces(berm, lambda c: (c[:, 2] < 2) | ((np.abs(c[:, 1]) < W / 2 - 2) & (c[:, 2] > 10)) | ((c[:, 0] > L / 2 - 20) & (np.abs(c[:, 1]) < W / 2 - 20)) | ((c[:, 0] < -L / 2 + 20) & (np.abs(c[:, 1]) < 30)))
    m.add(berm)
    m.recompute_normals(angle=50)
    return m


def fdc_bunker(lod=0, seed=62):
    """FDC: a half-buried CONEX container with a sandbag-walled, PSP-roofed porch in front (the plotting table goes inside the porch);
    radio antennas on the roof; opening to +x"""
    p = geo.frame(seed=seed, panel_u=48.0, panel_v=48.0)
    m = geo.Mesh()
    cx0, cx1 = -120, 40; w = 50; h = 86
    m.add(MG.box(cx0, -w, 0, cx1, w, h, 'od', p, r=2.0))                                     # the CONEX box
    for xx in np.arange(cx0 + 12, cx1 - 6, 12):                                               # corrugations as ribs
        for sy in (-1, 1): m.add(MG.box(xx, sy * w, 4, xx + 4, sy * (w + 1.6), h - 4, 'od', p))
    m.add(MG.box(cx1 - 2, -22, 2, cx1 + 1, 22, 72, 'interior', p))                            # open doors: dark interior face
    for s in (-1, 1): m.add(MG.box(cx1 - 1, s * 22, 0, cx1 + 1.6, s * 50, h - 2, 'od', p, r=1.0))   # doors swung open flat against the wall
    # porch: sandbag walls both sides, PSP roof on posts, open front
    for s in (-1, 1):
        for k in range(2):
            sb, hh = sandbag_row(64, 3, lod, seed + 10 + k + s, yaw=0); sb.transform(None, (cx1 + 32 + k * 64, s * 58, 0)); m.add(sb)
    for (xx, yy) in ((cx1 + 12, -56), (cx1 + 12, 56), (cx1 + 124, -56), (cx1 + 124, 56)):
        m.add(MG.cyl((xx, yy, 0), (xx, yy, 92), 4.0, 'wood_dark', p, sides=8))
    m.add(MG.box(cx1 - 4, -66, 90, cx1 + 134, 66, 94, 'psp', p))
    for k in range(3):   # sandbag layer on the porch roof
        sb, hh = sandbag_row(120, 1, lod, seed + 30 + k, yaw=0); sb.transform(None, (cx1 + 66, -40 + k * 40, 94)); m.add(sb)
    # roof: sandbags on the CONEX, antenna mast and whip antennas, a field phone wire reel
    for k in range(4):
        sb, hh = sandbag_row(150, 1, lod, seed + 40 + k, yaw=0); sb.transform(None, (-40, -36 + k * 24, h)); m.add(sb)
    m.add(MG.cyl((-100, 30, h), (-100, 30, h + 160), 1.6, 'gunsteel', p, sides=6))
    m.add(MG.cyl((-100, 30, h + 160), (-100, 30, h + 200), 0.6, 'gunsteel', p, sides=6))
    m.add(MG.cyl((-60, -30, h), (-60, -30, h + 110), 0.8, 'gunsteel', p, sides=6))
    SIGN = MG.text_img(['FDC', 'B BTRY 1/21 ARTY'], 256, 96, color=(0.92, 0.9, 0.85), fonts=MG.STENCIL, size=34)
    m.add(geo.decal('fdc', (cx1 + 24, -62.2, 50), (1, 0, 0), (0, 0, 1), (64, 24)))
    m.recompute_normals(angle=50)
    return m, dict(fdc=SIGN)


def psp_pad(lod=0, seed=63, size=600):
    """pierced steel planking helipad with a painted H and a wind sock on a pole at a corner"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    n = int(size / 38)
    for i in range(n):
        for j in range(int(size / 120)):
            x0 = -size / 2 + i * 38 + (20 if j % 2 else 0)
            m.add(MG.box(x0, -size / 2 + j * 120, 0, x0 + 38, -size / 2 + (j + 1) * 120, 1.6, 'psp', p, r=0.2))
    hull = []
    m.add(MG.cyl((size / 2 - 20, size / 2 - 20, 0), (size / 2 - 20, size / 2 - 20, 130), 1.8, 'gunsteel', p, sides=6))
    sock = geo.tube([(size / 2 - 20, size / 2 - 20, 128), (size / 2 - 50, size / 2 - 30, 124), (size / 2 - 80, size / 2 - 44, 118)], [7, 6, 4], sides=10, mat='canvas_or', part=p, caps=False)
    m.add(sock)
    H = MG.text_img(['H'], 256, 256, color=(0.9, 0.88, 0.8), fonts=MG.SANS, size=230)
    m.add(geo.decal('H', (-110, -130, 1.6), (1, 0, 0), (0, 1, 0), (220, 260)))
    m.recompute_normals(angle=50)
    return m, dict(H=H)


def gp_tent(lod=0, seed=64):
    """GP medium tent (ridge tent) with a raised flap on +x, sandbag skirt; 640 x 400 x 160"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    L, W, H, wall = 320, 200, 150, 60
    # canvas: two slopes + two gable ends, as thin plates
    for s in (-1, 1):
        m.add(MG.plate((-L / 2, s * W / 2, wall), (L, 0, 0), (0, -s * W / 2, H - wall), 'tent', p, thick=1.0))
        m.add(MG.plate((-L / 2, s * W / 2, 0), (L, 0, 0), (0, 0, wall), 'tent', p, thick=1.0))
    # gable triangles
    for sx in (-1, 1):
        g = geo.Mesh()
        tri = geo.prism([(-W / 2, wall), (W / 2, wall), (0, H)], -0.6, 0.6, 'tent', p)
        tri.transform(geo.rot('z', 90), (sx * L / 2, 0, 0))
        m.add(tri)
        if sx > 0:
            # door flap rolled up: a roll above the opening; the opening is just the dark interior plate
            m.add(MG.plate((L / 2 + 0.7, -30, 0), (0, 60, 0), (0, 0, wall - 2), 'interior', p, thick=0.5))
            m.add(geo.tube([(L / 2 + 2, -34, wall + 2), (L / 2 + 2, 34, wall + 2)], 4.5, sides=10, mat='tent', part=p))
    # poles, guy ropes with pegs
    for xx in (-L / 2 + 4, 0, L / 2 - 4):
        m.add(MG.cyl((xx, 0, 0), (xx, 0, H + 6), 2.2, 'wood', p, sides=8))
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.add(MG.cyl((sx * L / 2, sy * W / 2, wall), (sx * (L / 2 + 50), sy * (W / 2 + 40), 0), 0.5, 'rope', p, sides=5))
            m.add(MG.cyl((sx * (L / 2 + 50), sy * (W / 2 + 40), -2), (sx * (L / 2 + 50), sy * (W / 2 + 40), 8), 1.2, 'wood', p, sides=6))
    for k in range(int(L / 64)):   # sandbag skirt both sides
        for s in (-1, 1):
            sb, hh = sandbag_row(64, 2, lod, seed + 10 + k + s); sb.transform(None, (-L / 2 + 32 + k * 64, s * (W / 2 + 14), 0)); m.add(sb)
    # cots inside (visible through the door)
    for yy in (-60, 60):
        m.add(cot(lod, seed + int(yy)).transform(None, (-40, yy, 0)))
    m.recompute_normals(angle=50)
    return m


def cot(lod=0, seed=65):
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    m.add(MG.box(-38, -14, 16, 38, 14, 18, 'canvas', p, r=0.5))
    for (sx, sy) in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        m.add(MG.cyl((sx * 34, sy * 13, 0), (sx * 34, -sy * 13, 17), 0.8, 'wood', p, sides=6))
    m.add(MG.box(-34, -10, 18, -20, 10, 22, 'canvas', p, r=1.5))    # rolled poncho liner
    return m


def conex(lod=0, seed=66):
    """CONEX shipping container (8 x 6 x 7 ft), doors on +x"""
    p = geo.frame(seed=seed, panel_u=48.0, panel_v=48.0)
    m = geo.Mesh()
    L, W, H = 96, 72, 84
    m.add(MG.box(-L / 2, -W / 2, 0, L / 2, W / 2, H, 'od', p, r=1.5))
    for xx in np.arange(-L / 2 + 8, L / 2 - 4, 10):
        for sy in (-1, 1): m.add(MG.box(xx, sy * W / 2, 3, xx + 3.5, sy * (W / 2 + 1.4), H - 3, 'od', p))
    for s in (-1, 1): m.add(MG.cyl((L / 2 + 1, s * 12, 10), (L / 2 + 1, s * 12, H - 10), 1.2, 'gunsteel', p, sides=6))   # door bars
    STEN = MG.text_img(['US ARMY', 'TRANSPORTATION CORPS'], 256, 64, color=(0.9, 0.9, 0.86), fonts=MG.STENCIL, size=22)
    m.add(geo.decal('sten', (-30, -W / 2 - 1.6, 50), (1, 0, 0), (0, 0, 1), (60, 16)))
    m.recompute_normals(angle=50)
    return m, dict(sten=STEN)


def guard_tower(lod=0, seed=67):
    """timber watch tower: four legs, cross braces, a sandbagged platform with a PSP roof, ladder on -x (toolsinvisibleladder in the map)"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    H = 260; s_ = 70
    for (sx, sy) in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        m.add(MG.cyl((sx * s_ * 1.25, sy * s_ * 1.25, 0), (sx * s_, sy * s_, H), 5.0, 'wood_dark', p, sides=8))
    for z in (80, 160):
        for sy in (-1, 1):
            m.add(MG.cyl((-s_ * (1.25 - z / H * 0.25), sy * s_ * (1.25 - z / H * 0.25), z), (s_ * (1.25 - z / H * 0.25), sy * s_ * (1.25 - z / H * 0.25), z), 2.6, 'wood_dark', p, sides=6))
            m.add(MG.cyl((-s_ * 1.22, sy * s_ * 1.22, z - 70), (s_ * 1.05, sy * s_ * 1.05, z + 60), 2.0, 'wood_dark', p, sides=6))
        for sx in (-1, 1):
            m.add(MG.cyl((sx * s_ * (1.25 - z / H * 0.25), -s_ * (1.25 - z / H * 0.25), z), (sx * s_ * (1.25 - z / H * 0.25), s_ * (1.25 - z / H * 0.25), z), 2.6, 'wood_dark', p, sides=6))
    m.add(MG.box(-s_ - 10, -s_ - 10, H, s_ + 10, s_ + 10, H + 6, 'wood', p))                 # platform
    for k in range(4):
        sb, hh = sandbag_row(2 * s_ + 20, 2, lod, seed + k, yaw=90 * k); sb.transform(None, ((s_ + 10) * (1 if k == 0 else -1 if k == 2 else 0), (s_ + 10) * (1 if k == 1 else -1 if k == 3 else 0), H + 6)); m.add(sb)
    for (sx, sy) in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        m.add(MG.cyl((sx * s_, sy * s_, H + 6), (sx * s_, sy * s_, H + 90), 3.0, 'wood_dark', p, sides=6))
    m.add(MG.box(-s_ - 16, -s_ - 16, H + 90, s_ + 16, s_ + 16, H + 93, 'psp', p))
    # ladder
    for s in (-1, 1): m.add(MG.cyl((-s_ * 1.25 - 8, s * 12, 0), (-s_ - 8, s * 12, H + 20), 2.0, 'wood', p, sides=6))
    for z in np.arange(20, H + 10, 24):
        xx = -s_ * 1.25 - 8 + (s_ * 0.25) * z / H
        m.add(MG.cyl((xx, -12, z), (xx, 12, z), 1.4, 'wood', p, sides=6))
    m.recompute_normals(angle=50)
    return m


def fuel_bladder(lod=0, seed=68):
    """500-gal collapsible fuel bladder in a sandbag berm, with a hand pump and hose"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    b = geo.rbox(150, 110, 34, r=14, seg=3, mat='rubber', part=p, div=(4, 3, 1), center=(0, 0, 17))
    n = fbm(b.V[:, 0] * 0.05, b.V[:, 1] * 0.05, 0.0, 3, seed=seed)
    b.V[:, 2] *= 1 - 0.18 * ((b.V[:, 0] / 75) ** 2 + (b.V[:, 1] / 55) ** 2).clip(0, 1) + 0.06 * n
    b.recompute_normals()
    m.add(b)
    for k, (yaw, pos) in enumerate(((0, (0, -72, 0)), (0, (0, 72, 0)), (90, (-92, 0, 0)), (90, (92, 0, 0)))):
        sb, hh = sandbag_row(170 if k < 2 else 120, 2, lod, seed + k, yaw=yaw); sb.transform(None, pos); m.add(sb)
    m.add(MG.cyl((70, 0, 14), (100, 0, 30), 2.0, 'gunsteel', p, sides=8))
    m.add(MG.box(96, -6, 26, 108, 6, 46, 'gunsteel', p, r=1.0))
    m.add(geo.tube([(108, 0, 40), (130, 8, 30), (150, 20, 4), (170, 30, 3)], 2.0, sides=8, mat='rubber', part=p))
    m.recompute_normals(angle=50)
    return m


def drum(lod=0, seed=69, mat='od', lying=False):
    """55-gallon drum, 34 tall, 23 wide"""
    p = geo.frame(seed=seed)
    sides = 16 if lod == 0 else 10
    prof = [(0, 0), (11.0, 0), (11.6, 1.5), (11.6, 10), (12.2, 11), (11.6, 12), (11.6, 22), (12.2, 23), (11.6, 24), (11.6, 32.5), (11.0, 34), (0, 34)]
    m = geo.lathe(prof, sides=sides, mat=mat, part=p)
    m.add(geo.disk((4, 4, 34.1), [(4 + 2 * np.cos(a), 4 + 2 * np.sin(a), 34.1) for a in np.linspace(0, 2 * np.pi, 8, endpoint=False)], (0, 0, 1), 'gunsteel', p))
    if lying:
        m.transform(geo.rot('y', 90), (0, 0, 11.6))
    m.recompute_normals(angle=40)
    return m


def drum_stack(lod=0, seed=70):
    m = geo.Mesh(); rng = np.random.RandomState(seed)
    for k, (x, y) in enumerate(((0, 0), (25, 2), (12, 22), (-13, 21), (2, 44))):
        d = drum(lod, seed + k, mat=('od', 'rust', 'od', 'khaki', 'rust')[k])
        d.transform(geo.rot('z', rng.uniform(0, 360)), (x, y, 0))
        m.add(d)
    d = drum(lod, seed + 9, mat='rust', lying=True); d.transform(geo.rot('z', 15), (40, 36, 0)); m.add(d)
    return m


def water_trailer(lod=0, seed=71):
    """400-gal water trailer ("water buffalo") on two wheels with a tow bar to +x"""
    p = geo.frame(seed=seed, panel_u=40.0, panel_v=30.0)
    m = geo.Mesh()
    sides = 18 if lod == 0 else 10
    tank = geo.tube([(-60, 0, 54), (60, 0, 54)], 32, sides=sides, mat='od', part=p)
    m.add(tank)
    m.add(MG.box(-70, -16, 18, 70, 16, 26, 'od', p, r=1.0))
    m.add(MG.cyl((70, 0, 22), (124, 0, 18), 2.4, 'od', p, sides=8))
    m.add(MG.box(118, -5, 10, 130, 5, 22, 'gunsteel', p))
    m.add(MG.cyl((-10, -48, 18), (-10, 48, 18), 2.4, 'gunsteel', p, sides=8))
    for s in (-1, 1):
        m.add(geo.tube([(-10, s * 40, 18), (-10, s * 50, 18)], 18, sides=sides, mat='rubber', part=p))
        m.add(geo.tube([(-10, s * 39, 18), (-10, s * 51, 18)], 9, sides=sides, mat='od', part=p))
        m.add(MG.cyl((30, s * 30, 36), (30, s * 30, 22), 1.4, 'gunsteel', p, sides=6))      # taps
    m.add(MG.cyl((0, 0, 86), (0, 0, 92), 8, 'od', p, sides=12))
    m.add(MG.cyl((110, 0, 0), (110, 0, 16), 1.6, 'gunsteel', p, sides=6))              # jack leg
    WB = MG.text_img(['POTABLE WATER'], 256, 48, color=(0.9, 0.9, 0.86), fonts=MG.STENCIL, size=30)
    m.add(geo.decal('wb', (-40, -32.2, 48), (1, 0, 0), (0, 0, 1), (80, 14)))
    m.recompute_normals(angle=50)
    return m, dict(wb=WB)


def latrine(lod=0, seed=72):
    """two-hole field latrine: plywood box with a screen of canvas on poles, a half-drum beside it"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    m.add(MG.box(-30, -22, 0, 30, 22, 34, 'wood', p, r=0.6))
    for xx in (-14, 14):
        m.add(geo.disk((xx, 0, 34.1), [(xx + 7 * np.cos(a), 0 + 5 * np.sin(a), 34.1) for a in np.linspace(0, 2 * np.pi, 12, endpoint=False)], (0, 0, 1), 'interior', p))
    for (x, y) in ((-44, -40), (44, -40), (-44, 40), (44, 40)):
        m.add(MG.cyl((x, y, 0), (x, y, 90), 1.6, 'wood', p, sides=6))
    for s in (-1, 1):
        m.add(MG.plate((-44, s * 40, 20), (88, 0, 0), (0, 0, 66), 'canvas', p, thick=0.8))
    m.add(MG.plate((-44, -40, 20), (0, 80, 0), (0, 0, 66), 'canvas', p, thick=0.8))
    hd = drum(lod, seed + 1, mat='rust'); hd.V[:, 2] *= 0.5; hd.transform(None, (60, 0, 0)); m.add(hd)
    m.recompute_normals(angle=50)
    return m


def antenna_mast(lod=0, seed=73):
    """RC-292 ground-plane antenna on a sectional mast with guys"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    H = 420
    m.add(MG.cyl((0, 0, 0), (0, 0, H), 1.8, 'gunsteel', p, sides=6))
    for k in range(3):
        a = np.radians(120 * k + 30)
        m.add(MG.cyl((0, 0, H), (60 * np.cos(a), 60 * np.sin(a), H - 30), 0.6, 'gunsteel', p, sides=5))
        m.add(MG.cyl((0, 0, H * 0.6), (150 * np.cos(a), 150 * np.sin(a), 0), 0.4, 'rope', p, sides=4))
        m.add(MG.cyl((150 * np.cos(a), 150 * np.sin(a), -2), (150 * np.cos(a), 150 * np.sin(a), 10), 1.4, 'gunsteel', p, sides=6))
    m.add(MG.cyl((0, 0, H), (0, 0, H + 70), 0.5, 'gunsteel', p, sides=5))
    m.add(MG.box(-4, -4, 0, 4, 4, 6, 'gunsteel', p))
    return m


def ammo_can(lod=0, seed=74):
    p = geo.frame(seed=seed)
    m = MG.box(-7.5, -3.5, 0, 7.5, 3.5, 10, 'od', p, r=0.5)
    m.add(MG.box(-7, -3.8, 9.5, 7, 3.8, 10.5, 'od', p, r=0.3))
    m.add(MG.cyl((-3, 0, 10.5), (3, 0, 10.5), 0.5, 'gunsteel', p, sides=6))
    return m


def ammo_crate(lod=0, seed=75, mat='od'):
    """wooden ammo crate with rope handles and stencils (small arms)"""
    p = geo.frame(seed=seed, tone=0.5)
    m = geo.Mesh()
    L, W, H = 36, 16, 14
    m.add(geo.plank(L, W, H, mat='wood', seed=seed, r=0.6, div=(3, 1, 1), t=(0, 0, H / 2)))
    for s in (-1, 1): m.add(MG.cyl((s * (L / 2 + 0.5), -4, H * 0.6), (s * (L / 2 + 0.5), 4, H * 0.6), 0.8, 'rope', p, sides=6))
    ST = MG.text_img(['840 CTGS 5.56MM', 'BALL M193  LOT LC'], 256, 64, color=(0.1, 0.1, 0.1), fonts=MG.STENCIL, size=20)
    m.add(geo.decal('st', (-14, -W / 2 - 0.2, 3), (1, 0, 0), (0, 0, 1), (28, 8)))
    return m, dict(st=ST)


def radio_prc25(lod=0, seed=76):
    p = geo.frame(seed=seed)
    m = MG.box(-5, -4, 0, 5, 4, 11, 'od', p, r=0.6)
    m.add(MG.cyl((-3, 0, 11), (-3, 0, 11.6), 1.5, 'gunsteel', p, sides=8))
    m.add(MG.cyl((3, 0, 11), (3, 0, 46), 0.3, 'gunsteel', p, sides=4))
    m.add(MG.box(-5, -3, 2, 5, 3, 8, 'canvas', p, r=0.3).transform(None, (0, 0, 0)))
    return m


def jerry_can(lod=0, seed=77):
    p = geo.frame(seed=seed)
    m = MG.box(-7, -3.4, 0, 7, 3.4, 17, 'od', p, r=1.0, seg=2)
    m.add(MG.cyl((-3, 0, 17), (3, 0, 17), 0.8, 'od', p, sides=6))
    m.add(MG.cyl((5, 0, 17), (5, 0, 19), 1.4, 'gunsteel', p, sides=8))
    return m


def rucksack(lod=0, seed=78):
    p = geo.frame(seed=seed)
    b = geo.rbox(14, 10, 18, r=3.5, seg=2, mat='canvas', part=p, div=(1, 1, 1), center=(0, 0, 9))
    b.add(geo.rbox(9, 5, 8, r=2, seg=1, mat='canvas', part=p, center=(0, -6, 7)))
    b.transform(geo.rot('y', -20) @ geo.rot('z', 15))
    b.V[:, 2] -= b.V[:, 2].min()
    return b


def arms_rack(lod=0, seed=79, side='ct'):
    """the kit station: an M16 / AK rifle rack (wooden frame, 6 slots, 4 rifles as simple shapes), ammo cans and a LAW / RPG crate"""
    p = geo.frame(seed=seed, tone=0.5)
    m = geo.Mesh()
    for s in (-1, 1):
        m.add(geo.plank(60, 4, 4, mat='wood', seed=seed + s, t=(0, s * 12, 2)))
        m.add(geo.plank(60, 4, 4, mat='wood', seed=seed + 3 + s, t=(0, s * 12, 44)))
    for xx in (-28, 28):
        m.add(geo.plank(44, 4, 4, mat='wood', seed=seed + 5 + xx, R=geo.rot('y', 90), t=(xx, -12, 24)))
        m.add(geo.plank(44, 4, 4, mat='wood', seed=seed + 7 + xx, R=geo.rot('y', 90), t=(xx, 12, 24)))
        m.add(geo.plank(24, 4, 4, mat='wood', seed=seed + 9 + xx, R=geo.rot('z', 90), t=(xx, 0, 46)))
    for k in range(4):   # rifles leaning in the rack
        xx = -18 + k * 12
        m.add(MG.cyl((xx, -2, 2), (xx + 1, -4, 40), 1.1, 'gunsteel', p, sides=6))
        m.add(MG.box(xx - 1.5, -4.5, 12, xx + 1.5, -1.5, 26, 'gunsteel' if side == 'ct' else 'wood', p, r=0.4))
        m.add(MG.box(xx - 1.2, -4, 4, xx + 1.2, 0, 11, 'gunsteel' if side == 'ct' else 'wood', p, r=0.4))
    for k in range(3):
        m.add(ammo_can(lod, seed + 20 + k).transform(geo.rot('z', 10 * k), (-20 + k * 16, 24, 0)))
    cr, imgs = ammo_crate(lod, seed + 30)
    cr.transform(geo.rot('z', 5), (14, 28, 0)); m.add(cr)
    if side == 'ct':
        for k in range(3):   # LAW tubes
            m.add(MG.cyl((-24 + k * 6, 30, 3 + k * 0), (-24 + k * 6, 56, 3), 2.6, 'od', p, sides=8))
    else:
        for k in range(2):   # RPG rounds in a rack
            m.add(MG.cyl((-24 + k * 8, 30, 4), (-24 + k * 8, 60, 4), 1.4, 'soviet', p, sides=8))
            m.add(MG.cyl((-24 + k * 8, 56, 4), (-24 + k * 8, 64, 4), 3.4, 'soviet', p, sides=10, r1=1.0))
    SIGN = MG.text_img(['ARMS' if side == 'ct' else 'VU KHI', 'E: RIFLE  MG  AT'], 256, 72, color=(0.92, 0.9, 0.85), fonts=MG.STENCIL, size=26)
    # sign board nailed to the front top rail (was a horizontal slab floating above the frame)
    m.add(geo.plank(40, 14, 2, mat='wood', seed=seed + 40, R=geo.rot('x', 90), t=(0, -15, 53)))
    m.add(geo.decal('sign', (-19, -16.1, 46.5), (1, 0, 0), (0, 0, 1), (38, 13)))
    m.recompute_normals(angle=50)
    return m, dict(imgs, sign=SIGN)      # child decal images (the ammo crate's stencil) merged in


def sign_post(lines, w=64, h=24, lod=0, seed=80, color=(0.92, 0.9, 0.85), bg='od', height=70, fonts=MG.STENCIL):
    p = geo.frame(seed=seed, tone=0.5)
    m = geo.Mesh()
    m.add(MG.cyl((0, 0, 0), (0, 0, height), 2.0, 'wood', p, sides=6))
    m.add(MG.box(-w / 2, -1.5, height - h, w / 2, 1.5, height, bg, p, r=0.4))
    img = MG.text_img(lines, 512, int(512 * h / w), color=color, fonts=fonts)
    m.add(geo.decal('txt', (-w / 2 + 1, -1.7, height - h + 1), (1, 0, 0), (0, 0, 1), (w - 2, h - 2)))
    m.recompute_normals(angle=50)
    return m, dict(txt=img)


def claymore_sign(lod=0, seed=81):
    return sign_post(['FRONT TOWARD ENEMY'], 30, 10, lod, seed, color=(0.9, 0.88, 0.8), bg='od', height=28)


def mines_sign(lod=0, seed=82):
    return sign_post(['DANGER', 'MINES'], 40, 30, lod, seed, color=(0.9, 0.15, 0.1), bg='paint_white', height=60)


def fsb_sign(lod=0, seed=83):
    """the big firebase sign at the gate: two posts and a painted board"""
    p = geo.frame(seed=seed, tone=0.5)
    m = geo.Mesh()
    for s in (-1, 1): m.add(MG.cyl((0, s * 80, 0), (0, s * 80, 130), 4.0, 'wood_dark', p, sides=8))
    m.add(MG.box(-3, -84, 60, 3, 84, 124, 'paint_white', p, r=0.5))
    img = MG.text_img(['FSB MONSOON', 'B BTRY 1/21 ARTY', 'WELCOME TO THE VALLEY'], 1024, 384, color=(0.1, 0.1, 0.1), fonts=MG.STENCIL)
    m.add(geo.decal('txt', (-3.2, 82, 62), (0, -1, 0), (0, 0, 1), (164, 60)))
    m.add(geo.decal('txt', (3.2, -82, 62), (0, 1, 0), (0, 0, 1), (164, 60)))
    m.recompute_normals(angle=50)
    return m, dict(txt=img)


def lz_sign(lod=0, seed=84):
    return sign_post(['LZ ROSE', 'NO SMOKING'], 60, 24, lod, seed, color=(0.9, 0.9, 0.86), bg='od', height=66)


def culvert_bunker(lod=0, seed=85):
    """half-culvert sleeping bunker: corrugated steel arch covered in sandbags, open ends to +-x"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    L = 180; R = 56
    arch = geo.Mesh()
    th = np.linspace(0, np.pi, 14)
    P = np.zeros((2, len(th), 3))
    for i, x in enumerate((-L / 2, L / 2)):
        P[i, :, 0] = x; P[i, :, 1] = R * np.cos(th); P[i, :, 2] = R * np.sin(th)
    s = geo.surface(P, 'galv', p); m.add(s)
    m.add(MG.box(-L / 2, -R, 0, L / 2, R, 2, 'wood', p))
    for k in range(int(L / 64)):
        for yy in (-R - 8, -R + 20, 0, R - 20, R + 8):
            zz = max(2.0, float(np.sqrt(max(R * R - yy * yy, 0))) + 2)
            sb, hh = sandbag_row(64, 1, lod, seed + k * 5 + int(yy), yaw=90); sb.transform(None, (-L / 2 + 32 + k * 64, yy, zz)); m.add(sb)
    for sx in (-1, 1):
        sb, hh = sandbag_row(2 * R + 40, 2, lod, seed + 50 + sx, yaw=90); sb.transform(None, (sx * (L / 2 + 30), 0, 0)); m.add(sb)
    m.recompute_normals(angle=50)
    return m


def _sh():
    return {'od': M.od_paint, 'soviet': M.soviet_paint, 'khaki': M.khaki_paint, 'gunsteel': M.gun_steel, 'rubber': M.rubber, 'rust': M.rust,
            'wood': M.wood, 'wood_dark': M.wood_dark, 'earth': M.earth, 'psp': M.psp, 'interior': M.interior, 'canvas': lambda c: S.canvas(c),
            'canvas_or': lambda c: S.canvas(c, base=S._c(0.85, 0.40, 0.10), mud_top=0.0, stains=0.3), 'tent': M.tarp, 'rope': M.rope,
            'brass': M.brass, 'galv': S.galvanised, 'paint_white': lambda c: S.painted_steel(c, S._c(0.8, 0.8, 0.76), chip=0.15), 'burlap': S.burlap,
            'seat': M.seat_canvas}


def _two(fn, size=1024, hulls=None, ground=0.0, thr=30.0, surface='default', metal=False, cut=False, **kw):
    a = fn(lod=0, **kw); b = fn(lod=1, **kw)
    imgs = {}
    if isinstance(a, tuple): a, imgs = a; b = b[0]
    lo, hi = a.bounds()
    spec = dict(lods=[a, b], lod_thresholds=[0.0, thr], size=size, decal_size=512, ground=ground, surface=surface, metal=metal, shaders=_sh(),
                decal_imgs=imgs, stock={}, hulls=hulls or [MG.pts_box(lo[0], lo[1], lo[2], hi[0], hi[1], hi[2])])
    return spec


def specs():
    return {
        'bunker_large': lambda: _two(bunker, 2048, hulls=[MG.pts_box(-100, -77, -26, 100, 77, 110), MG.pts_box(100, -85, -2, 142, 85, 40), MG.pts_box(-150, -126, -2, 150, 126, 24)], kind='large', gun=True),
        'bunker_small': lambda: _two(bunker, 2048, hulls=[MG.pts_box(-75, -62, -26, 75, 62, 104), MG.pts_box(75, -70, -2, 118, 70, 40), MG.pts_box(-120, -110, -2, 120, 110, 24)], kind='small', gun=False, seed=62),
        'fdc_bunker': lambda: _two(fdc_bunker, 2048, hulls=[MG.pts_box(-120, -52, 0, 44, 52, 92), MG.pts_box(40, -66, 0, 176, -50, 96), MG.pts_box(40, 50, 0, 176, 66, 96), MG.pts_box(36, -68, 88, 176, 68, 96)], metal=True),
        'psp_pad': lambda: _two(psp_pad, 2048, hulls=[MG.pts_box(-300, -300, 0, 300, 300, 1.6), MG.pts_box(276, 276, 0, 284, 284, 130)], metal=True),
        'gp_tent': lambda: _two(gp_tent, 2048, hulls=[MG.pts_box(-160, -100, 0, 160, 100, 60), MG.pts_box(-160, -60, 60, 160, 60, 150)]),
        'conex': lambda: _two(conex, 1024, metal=True),
        'guard_tower': lambda: _two(guard_tower, 2048, hulls=[MG.pts_box(-80, -80, 260, 80, 80, 300), MG.pts_box(-88, -88, 0, -84, 88, 8), MG.pts_box(84, -88, 0, 88, 88, 8), MG.pts_box(-88, -88, 0, 88, -84, 8), MG.pts_box(-88, 84, 0, 88, 88, 8), MG.pts_box(-86, -86, 350, 86, 86, 354)]),
        'fuel_bladder': lambda: _two(fuel_bladder, 1024, hulls=[MG.pts_box(-75, -55, 0, 75, 55, 34), MG.pts_box(-100, -84, 0, 100, 84, 12)]),
        'drum_od': lambda: _two(drum, 512, metal=True, mat='od'),
        'drum_rust': lambda: _two(drum, 512, metal=True, mat='rust', seed=70),
        'drum_stack': lambda: _two(drum_stack, 1024, metal=True, hulls=[MG.pts_box(-26, -12, 0, 38, 56, 34), MG.pts_box(28, 24, 0, 74, 48, 24)]),
        'water_trailer': lambda: _two(water_trailer, 1024, metal=True, hulls=[MG.pts_box(-70, -34, 18, 70, 34, 90), MG.pts_box(-30, -52, 0, 10, 52, 36), MG.pts_box(70, -6, 10, 130, 6, 26)]),
        'latrine': lambda: _two(latrine, 1024, hulls=[MG.pts_box(-30, -22, 0, 30, 22, 34), MG.pts_box(-46, -42, 0, 46, -38, 90), MG.pts_box(-46, 38, 0, 46, 42, 90), MG.pts_box(-46, -42, 0, -42, 42, 90)]),
        'antenna_mast': lambda: _two(antenna_mast, 512, metal=True, hulls=[MG.pts_box(-3, -3, 0, 3, 3, 420)]),
        'ammo_can': lambda: _two(ammo_can, 256, metal=True),
        'ammo_crate': lambda: _two(ammo_crate, 512),
        'radio_prc25': lambda: _two(radio_prc25, 256, metal=True, hulls=[MG.pts_box(-5, -4, 0, 5, 4, 12)]),
        'jerry_can': lambda: _two(jerry_can, 256, metal=True),
        'rucksack': lambda: _two(rucksack, 256),
        'arms_rack_ct': lambda: _two(arms_rack, 1024, hulls=[MG.pts_box(-32, -14, 0, 32, 14, 48), MG.pts_box(-30, 20, 0, 30, 60, 14)], side='ct'),
        'arms_rack_t': lambda: _two(arms_rack, 1024, hulls=[MG.pts_box(-32, -14, 0, 32, 14, 48), MG.pts_box(-30, 20, 0, 30, 64, 14)], side='t', seed=80),
        'claymore_sign': lambda: _two(claymore_sign, 256, hulls=[MG.pts_box(-2, -2, 0, 2, 2, 28)]),
        'mines_sign': lambda: _two(mines_sign, 256, hulls=[MG.pts_box(-2, -2, 0, 2, 2, 60)]),
        'fsb_sign': lambda: _two(fsb_sign, 1024, hulls=[MG.pts_box(-4, -84, 0, 4, 84, 130)]),
        'lz_sign': lambda: _two(lz_sign, 512, hulls=[MG.pts_box(-2, -2, 0, 2, 2, 66)]),
        'culvert_bunker': lambda: _two(culvert_bunker, 2048, hulls=[MG.pts_box(-90, -64, 0, 90, 64, 70), MG.pts_box(-120, -60, 0, -90, 60, 30), MG.pts_box(90, -60, 0, 120, 60, 30)]),
        'cot': lambda: _two(cot, 256),
    }
