"""Helicopters: UH-1 Huey (slick and gunship) and Mi-8 Hip (slick and gunship), rotors as separate props (origin on the hub),
burnt wrecks. Nose is +x, origin on the ground under the rotor mast (skids / wheels at z 0). Scale: 40 units per metre.
"""
import numpy as np
import geo
import mv_geo as MG
import mv_shaders as M
import shaders as S
from noise import fbm

U = 40.0   # units per metre

# ---------------------------------------------------------------- UH-1H
HUEY_SECTIONS = [   # (x, half width, z bottom, z top, squareness, flat bottom)
    (258, 3, 70, 78, 2.0, 0.0), (246, 14, 56, 94, 2.2, 0.0), (228, 26, 44, 108, 2.4, 0.1), (205, 37, 37, 120, 2.6, 0.2),
    (180, 45, 33, 130, 2.8, 0.3), (150, 50, 31, 136, 3.2, 0.5), (120, 52, 30, 140, 3.6, 0.7), (60, 52, 30, 141, 3.8, 0.8),
    (0, 52, 30, 141, 3.8, 0.8), (-60, 52, 30, 141, 3.8, 0.8), (-110, 51, 31, 140, 3.6, 0.7), (-135, 44, 36, 134, 3.0, 0.5),
    (-165, 31, 50, 122, 2.6, 0.3), (-195, 21, 62, 110, 2.4, 0.1), (-250, 18, 68, 106, 2.4, 0.0), (-320, 15, 74, 104, 2.4, 0.0),
    (-390, 13, 80, 104, 2.4, 0.0), (-440, 11, 86, 106, 2.4, 0.0), (-462, 9, 90, 106, 2.2, 0.0)]
DOOR_X = (-108, 36)       # cabin door opening along x (both sides)
DOOR_Z = (46, 128)
MAST = (-18.0, 0.0)       # rotor mast x, y
ROTOR_Z = 178.0
TAIL_ROTOR = (-466.0, -14.0, 150.0)   # hub (left side on the UH-1H... the H has it on the left; fine either way)
HUEY_ROTOR_R = 292.0


def hull_panel(sections, x0, x1, z0, z1, side, mat, part, n=28, off=2.5, k=1.0):
    """a thin panel following the hull sections (offset outward by off) on one side, between x0..x1 and z0..z1: slid-back doors"""
    secs = []
    xs = [s[0] * k for s in sections]
    for x in np.linspace(x0, x1, 4):
        # interpolate the section parameters at x
        i = int(np.clip(np.searchsorted(xs[::-1], x), 1, len(xs) - 1))
        xs_r = xs[::-1]; sec_r = sections[::-1]
        (xa, wa, za, zta, na, fa), (xb, wb, zb, ztb, nb, fb_) = sec_r[i - 1], sec_r[i]
        t_ = (x - xa * k) / max((xb - xa) * k, 1e-6)
        w = (wa + (wb - wa) * t_) * k + off; zlo = (za + (zb - za) * t_) * k - off; zhi = (zta + (ztb - zta) * t_) * k + off
        secs.append((x, MG.rrect_section(w, zlo, zhi, na + (nb - na) * t_, n=n, flat_bottom=fa + (fb_ - fa) * t_)))
    p = MG.loft(secs, mat, part, n=n, cap_front=False, cap_back=False)
    MG.remove_faces(p, lambda c: ~((c[:, 2] > z0) & (c[:, 2] < z1) & (np.sign(c[:, 1]) == side) & (np.abs(c[:, 1]) > 0.6 * (w - off))))
    return p


def huey_body(lod=0, gunship=False, seed=1):
    n = 28 if lod == 0 else 14
    paint = 'od'
    m = geo.Mesh()
    skin_part = geo.frame(seed=seed, soot=1.0, soot_x=-110.0, soot_z=150.0, panel_u=60.0, panel_v=40.0)
    secs = [(x, MG.rrect_section(w, zlo, zhi, npow, n=n, flat_bottom=fb)) for (x, w, zlo, zhi, npow, fb) in HUEY_SECTIONS[::-1]]
    skin = MG.loft(secs, paint, skin_part, n=n, cap_front=True, cap_back=True, seam_split=4 if lod == 0 else 1)
    # door openings: drop the side faces inside the door rectangle
    MG.remove_faces(skin, lambda c: (c[:, 0] > DOOR_X[0]) & (c[:, 0] < DOOR_X[1]) & (c[:, 2] > DOOR_Z[0]) & (c[:, 2] < DOOR_Z[1]) & (np.abs(c[:, 1]) > 40))
    m.add(skin)
    # cabin interior: floor, ceiling, rear bulkhead, transmission wall, door frames
    ip = geo.frame(seed=seed + 1)
    m.add(MG.box(DOOR_X[0] - 20, -49, 40, DOOR_X[1] + 30, 49, 46, 'interior', ip))                 # floor
    m.add(MG.box(DOOR_X[0] - 20, -49, 126, DOOR_X[1] + 30, 49, 132, 'interior', ip))                # ceiling
    m.add(MG.box(DOOR_X[0] - 22, -49, 40, DOOR_X[0] - 16, 49, 132, 'interior', ip))                 # rear bulkhead
    m.add(MG.box(DOOR_X[1] + 26, -49, 40, DOOR_X[1] + 34, 49, 132, 'interior', ip))                 # front wall (behind the pilots)
    for s in (-1, 1):   # door frames (posts) and the sliding door slid back along the tail boom side
        m.add(MG.box(DOOR_X[0] - 3, s * 46, DOOR_Z[0], DOOR_X[0] + 3, s * 53, DOOR_Z[1], paint, skin_part))
        m.add(MG.box(DOOR_X[1] - 3, s * 46, DOOR_Z[0], DOOR_X[1] + 3, s * 53, DOOR_Z[1], paint, skin_part))
        m.add(hull_panel(HUEY_SECTIONS, DOOR_X[0] - 76, DOOR_X[0] - 4, DOOR_Z[0] + 2, DOOR_Z[1] - 2, s, paint, skin_part, n=n, off=2.6))
        m.add(hull_panel(HUEY_SECTIONS, DOOR_X[0] - 66, DOOR_X[0] - 14, 76, 112, s, 'glass', ip, n=n, off=3.4))
        # troop bench seat (canvas) along the rear bulkhead and the door gunner's seat strap
        m.add(MG.box(DOOR_X[0] - 14, s * 6, 56, DOOR_X[0] + 24, s * 44, 60, 'seat', ip))
        m.add(MG.box(DOOR_X[0] - 14, s * 6, 60, DOOR_X[0] - 8, s * 44, 88, 'seat', ip))
        # door gun pintle post at the front door edge
        m.add(MG.cyl((DOOR_X[1] - 10, s * 44, 48), (DOOR_X[1] - 10, s * 44, 92), 2.2, 'gunsteel', ip, sides=8))
        m.add(MG.cyl((DOOR_X[1] - 10, s * 44, 92), (DOOR_X[1] + 6, s * 62, 96), 1.6, 'gunsteel', ip, sides=8))
    # pilot seats (two), armoured, and the instrument console between them
    for s in (-1, 1):
        m.add(MG.box(DOOR_X[1] + 40, s * 10, 54, DOOR_X[1] + 70, s * 34, 60, 'seat', ip))
        m.add(MG.box(DOOR_X[1] + 36, s * 10, 60, DOOR_X[1] + 44, s * 34, 104, 'seat', ip))
    m.add(MG.box(DOOR_X[1] + 44, -9, 48, DOOR_X[1] + 96, 9, 84, 'interior', ip))
    m.add(MG.box(DOOR_X[1] + 96, -36, 92, DOOR_X[1] + 118, 36, 104, 'interior', ip))                 # instrument panel glare shield
    # glazing: windshield (two panes), chin bubbles, pilot door windows, roof greenhouse, nose transparencies
    gp = geo.frame(seed=seed + 2)
    for s in (-1, 1):
        m.add(MG.plate((195, s * 2, 112), (-34, s * 38, 20), (-18, s * 3, 24), 'glass', gp, thick=0.8))        # windshield
        m.add(MG.plate((238, s * 2, 58), (-30, s * 26, -4), (-10, 0, 36), 'glass', gp, thick=0.8))             # chin bubble
        m.add(MG.plate((150, s * 52.6, 78), (-54, 0, 0), (0, 0, 48), 'glass', gp, thick=0.8))                   # pilot door window
        m.add(MG.plate((150, s * 46, 141.2), (-70, 0, 0), (0, -s * 30, 0), 'glass', gp, thick=0.8))             # roof greenhouse
        m.add(MG.plate((DOOR_X[1] + 2, s * 53.4, 96), (-30, 0, 0), (0, 0, 30), 'glass', gp, thick=0.6))        # small cabin window behind the pilot door
    # roof: doghouse (transmission cowl), engine cowl and exhaust, mast
    rp = geo.frame(seed=seed + 3, soot=1.0, soot_x=-110.0, soot_z=150.0)
    m.add(MG.box(-70, -30, 139, 30, 30, 162, paint, rp, r=6, seg=2))
    m.add(MG.loft([(-120, MG.rrect_section(26, 136, 160, 2.6, n=16)), (-95, MG.rrect_section(30, 137, 166, 2.8, n=16)),
                   (-50, MG.rrect_section(30, 138, 166, 2.8, n=16)), (-30, MG.rrect_section(28, 139, 160, 2.6, n=16))], paint, rp, n=16))
    m.add(MG.cyl((-135, 0, 152), (-160, 0, 158), 11, 'gunsteel', rp, sides=12, r1=9))            # exhaust
    m.add(MG.cyl((MAST[0], 0, 160), (MAST[0], 0, ROTOR_Z - 4), 4.5, 'gunsteel', rp, sides=10))     # mast
    m.add(MG.cyl((95, 0, 140), (95, 0, 150), 3.0, 'gunsteel', rp, sides=8))                          # roof antenna base
    m.add(MG.cyl((95, 0, 150), (95, 0, 186), 0.8, 'gunsteel', rp, sides=6))
    # tail: fin (swept, leaning), horizontal stabiliser, tail skid, tail rotor gearbox
    tp = geo.frame(seed=seed + 4, panel_u=50.0, panel_v=40.0)
    fin = geo.prism([(-400, 104), (-440, 104), (-470, 176), (-452, 180), (-430, 168)], -5, 5, paint, tp)
    m.add(fin)
    m.add(MG.box(-392, -62, 92, (-360), 62, 97, paint, tp, r=1.5))                                   # stabiliser
    m.add(MG.cyl((-455, 0, 88), (-468, 0, 70), 1.6, 'gunsteel', tp, sides=6))                        # tail skid
    m.add(MG.cyl((TAIL_ROTOR[0], 0, TAIL_ROTOR[2]), (TAIL_ROTOR[0], TAIL_ROTOR[1], TAIL_ROTOR[2]), 4.0, 'gunsteel', tp, sides=8))
    # skids: tubes with upturned fronts, cross tubes arched from the belly
    sp = geo.frame(seed=seed + 5)
    for s in (-1, 1):
        pts = [(-130, s * 50, 6), (-60, s * 50, 5), (60, s * 50, 5), (130, s * 50, 6), (160, s * 50, 14), (176, s * 48, 26)]
        m.add(geo.tube(pts, 3.2, sides=10, mat='aluminium', part=sp))
        for xx in (-78, 102):
            arc = [(xx, s * 50, 7), (xx, s * 52, 18), (xx, s * 44, 28), (xx, s * 30, 32)]
            m.add(geo.tube(arc, 2.6, sides=8, mat='aluminium', part=sp))
            m.add(MG.cyl((xx - 6, s * 50, 3), (xx + 6, s * 50, 3), 4.5, 'gunsteel', sp, sides=8))   # skid shoe clamps
    # nose: pitot, nose light, nav lights; belly: FM antenna, cargo hook
    m.add(MG.cyl((236, 24, 64), (262, 24, 66), 0.9, 'gunsteel', sp, sides=6))
    m.add(MG.cyl((60, 0, 30), (60, 0, 20), 1.2, 'gunsteel', sp, sides=6))
    m.add(MG.cyl((-30, 0, 30), (-30, 0, 24), 2.0, 'gunsteel', sp, sides=8))
    # markings (decals)
    ARMY = MG.text_img(['UNITED STATES ARMY'], 1024, 96, color=(0.08, 0.08, 0.08), fonts=MG.STENCIL)
    SERIAL = MG.text_img(['66-16428'], 256, 64, color=(0.92, 0.9, 0.85))
    DOOR = MG.text_img(['ARMY'], 256, 96, color=(0.08, 0.08, 0.08))
    for s in (-1, 1):
        # tail boom lettering, reading left to right on both sides
        if s > 0:
            m.add(geo.decal('army', (-200, s * 19.5, 80), (-1 * -1, 0, 0) if False else (-1, 0, 0), (0, 0, 1), (150, 15)).transform(None, (0, 0, 0)))
        else:
            m.add(geo.decal('army', (-350, s * 19.5, 80), (1, 0, 0), (0, 0, 1), (150, 15)))
        m.add(geo.decal('serial', (-430 if s > 0 else -392, s * 10.5 + s * 0.5, 112), (-1 if s > 0 else 1, 0, 0), (0, 0, 1), (38, 10)))
    m.add(geo.decal('army_r', (-420, 6, 150), (-1, 0, 0), (0, 0, 1), (30, 12)))
    if gunship:
        gun_part = geo.frame(seed=seed + 7)
        for s in (-1, 1):
            # outrigger pylon and a 7-tube M158 rocket pod per side
            m.add(MG.box(-40, s * 50, 60, -10, s * 92, 70, paint, gun_part, r=1.5))
            m.add(MG.cyl((-20, s * 92, 65), (-20, s * 92, 46), 3.0, 'gunsteel', gun_part, sides=8))
            pod = geo.tube([(40, s * 92, 46), (-70, s * 92, 46)], 13.0, sides=18, mat='gunsteel', part=gun_part)
            m.add(pod)
            for k in range(7):
                a = k * 2 * np.pi / 7
                m.add(geo.tube([(42, s * 92 + 7.5 * np.cos(a), 46 + 7.5 * np.sin(a)), (44, s * 92 + 7.5 * np.cos(a), 46 + 7.5 * np.sin(a))], 3.2, sides=10, mat='rust', part=gun_part, caps=False))
            # flex minigun on the pylon (XM134) instead of the door M60 pintle
            m.add(MG.cyl((10, s * 70, 72), (80, s * 70, 72), 3.0, 'gunsteel', gun_part, sides=10))
            m.add(MG.box(-10, s * 64, 64, 14, s * 76, 80, 'gunsteel', gun_part))
        # chin turret (TAT-102) with a grenade launcher barrel
        m.add(MG.loft([(220, MG.rrect_section(12, 36, 60, 2.2, n=14)), (236, MG.rrect_section(13, 36, 62, 2.2, n=14))], paint, gun_part, n=14))
        m.add(MG.cyl((236, 0, 48), (268, 0, 48), 3.2, 'gunsteel', gun_part, sides=10))
    m.recompute_normals(angle=48)
    return m, dict(army=ARMY, serial=SERIAL, army_r=DOOR)


def rotor(radius=HUEY_ROTOR_R, chord=21.0, blades=2, hub_r=9.0, flybar=True, seed=3, lod=0, root=22.0):
    """main rotor: blades along +-x (then rotated), origin on the hub"""
    m = geo.Mesh()
    bp = geo.frame(seed=seed)
    for k in range(blades):
        ang = 360.0 * k / blades
        b = geo.rbox(radius - root, chord, 2.4, r=1.0, seg=1, mat='od', part=bp, div=(6 if lod == 0 else 2, 1, 1), center=((radius + root) / 2, 0, 0))
        # twist and a little droop toward the tip
        x = (b.V[:, 0] - root) / (radius - root)
        b.V[:, 2] -= 10.0 * x ** 2
        tw = np.radians(-8.0 * x)
        y, z = b.V[:, 1].copy(), b.V[:, 2].copy() + 10.0 * x ** 2
        b.V[:, 1] = y * np.cos(tw) - z * np.sin(tw); b.V[:, 2] = y * np.sin(tw) + z * np.cos(tw) - 10.0 * x ** 2
        b.recompute_normals()
        # root grip and the blade tip stripe decal
        g = MG.box(hub_r - 2, -5, -4, root + 6, 5, 4, 'gunsteel', bp, r=1.0)
        b.add(g)
        b.transform(geo.rot('z', ang))
        m.add(b)
    m.add(MG.cyl((0, 0, -10), (0, 0, 8), hub_r, 'gunsteel', bp, sides=14))
    if flybar:  # Huey stabiliser bar with weights, perpendicular to the blades
        for s in (-1, 1):
            m.add(MG.cyl((0, 0, 7), (0, s * 112, 7), 1.6, 'gunsteel', bp, sides=8))
            m.add(MG.cyl((0, s * 104, 7), (0, s * 118, 7), 4.5, 'gunsteel', bp, sides=10))
    m.recompute_normals(angle=50)
    return m


def tail_rotor(radius=70.0, chord=9.0, seed=4, lod=0):
    m = geo.Mesh(); bp = geo.frame(seed=seed)
    for k in range(2):
        b = geo.rbox(radius - 8, chord, 1.4, r=0.6, seg=1, mat='od', part=bp, div=(3, 1, 1), center=((radius + 8) / 2, 0, 0))
        b.transform(geo.rot('z', 180 * k))
        m.add(b)
    m.add(MG.cyl((0, 0, -4), (0, 0, 4), 5.0, 'gunsteel', bp, sides=12))
    # spins in the x-z plane (axis = y): rotate the disc from the xy plane
    m.transform(geo.rot('x', 90))
    m.recompute_normals(angle=50)
    return m


# ---------------------------------------------------------------- Mi-8 Hip (at 0.82 scale: 18.2 m hull -> ~600 u)
HIP_K = 0.82
HIP_SECTIONS = [   # (x, half width, z bottom, z top, squareness, flat bottom) at full scale, multiplied by HIP_K
    (372, 6, 86, 100, 2.0, 0.0), (358, 24, 66, 128, 2.2, 0.0), (335, 40, 52, 150, 2.4, 0.1), (300, 52, 44, 166, 2.8, 0.3),
    (260, 56, 42, 174, 3.2, 0.5), (200, 58, 42, 178, 3.6, 0.7), (100, 58, 42, 180, 3.8, 0.8), (0, 58, 42, 180, 3.8, 0.8),
    (-100, 58, 44, 180, 3.8, 0.8), (-180, 56, 50, 176, 3.4, 0.6), (-230, 46, 70, 166, 2.8, 0.3), (-280, 30, 96, 154, 2.4, 0.1),
    (-340, 24, 104, 152, 2.4, 0.0), (-420, 20, 112, 154, 2.4, 0.0), (-500, 17, 122, 160, 2.4, 0.0), (-580, 15, 132, 168, 2.4, 0.0),
    (-640, 13, 142, 176, 2.3, 0.0), (-668, 10, 150, 178, 2.2, 0.0)]
HIP_DOOR_X = (120, 190)        # sliding door (left side, forward)
HIP_DOOR_Z = (52, 128)
HIP_MAST = (-30.0, 0.0)
HIP_ROTOR_Z = 212.0 * HIP_K
HIP_ROTOR_R = 420.0 * HIP_K
HIP_TAIL_ROTOR = (-660.0 * HIP_K, 16.0, 196.0 * HIP_K)


def hip_body(lod=0, gunship=False, seed=11):
    K = HIP_K
    n = 28 if lod == 0 else 14
    paint = 'soviet'
    m = geo.Mesh()
    skin_part = geo.frame(seed=seed, soot=1.0, soot_x=-60.0 * K, soot_z=176.0 * K, panel_u=70.0, panel_v=44.0)
    secs = [(x * K, MG.rrect_section(w * K, zlo * K, zhi * K, npow, n=n, flat_bottom=fb)) for (x, w, zlo, zhi, npow, fb) in HIP_SECTIONS[::-1]]
    skin = MG.loft(secs, paint, skin_part, n=n, seam_split=4 if lod == 0 else 1)
    dx0, dx1 = HIP_DOOR_X[0] * K, HIP_DOOR_X[1] * K; dz0, dz1 = HIP_DOOR_Z[0] * K, HIP_DOOR_Z[1] * K
    # left sliding door opening and the rear clamshell doors stand open: cut the skin at the rear end too
    MG.remove_faces(skin, lambda c: (c[:, 0] > dx0) & (c[:, 0] < dx1) & (c[:, 2] > dz0) & (c[:, 2] < dz1) & (c[:, 1] > 46 * K))
    m.add(skin)
    ip = geo.frame(seed=seed + 1)
    m.add(MG.box(-150 * K, -56 * K, 44 * K, 230 * K, 56 * K, 52 * K, 'interior', ip))              # floor
    m.add(MG.box(-150 * K, -56 * K, 168 * K, 230 * K, 56 * K, 174 * K, 'interior', ip))            # ceiling
    m.add(MG.box(226 * K, -56 * K, 44 * K, 236 * K, 56 * K, 174 * K, 'interior', ip))              # cockpit bulkhead
    m.add(MG.box(-156 * K, -56 * K, 44 * K, -148 * K, 56 * K, 174 * K, 'interior', ip))            # rear bulkhead
    for s in (-1, 1):   # fold-down bench seats along both walls
        m.add(MG.box(-140 * K, s * 30 * K, 66 * K, 110 * K, s * 54 * K, 70 * K, 'seat', ip))
        m.add(MG.box(-140 * K, s * 52 * K, 70 * K, 110 * K, s * 56 * K, 98 * K, 'seat', ip))
    # door posts and the slid-back door (left), a door gun pintle in the opening
    m.add(MG.box(dx0 - 3, 50 * K, dz0, dx0 + 3, 59 * K, dz1, paint, skin_part))
    m.add(MG.box(dx1 - 3, 50 * K, dz0, dx1 + 3, 59 * K, dz1, paint, skin_part))
    m.add(hull_panel(HIP_SECTIONS, dx0 - 78, dx0 - 4, dz0 + 2, dz1 - 2, 1, paint, skin_part, n=n, off=2.6, k=K))
    m.add(hull_panel(HIP_SECTIONS, dx0 - 62, dx0 - 20, 88 * K, 112 * K, 1, 'glass', ip, n=n, off=3.4, k=K))
    m.add(MG.cyl((dx1 - 10, 50 * K, dz0 + 2), (dx1 - 10, 50 * K, dz0 + 48), 2.2, 'gunsteel', ip, sides=8))
    # round cabin windows both sides, cockpit glazing (the Hip's big greenhouse), nose glazing
    gp = geo.frame(seed=seed + 2)
    for s in (-1, 1):
        for xx in (-110, -60, -10, 40):
            if s > 0 and dx0 - 30 < xx * K < dx1 + 10: continue
            m.add(geo.disk((xx * K, s * 58.5 * K, 118 * K), [(xx * K + 11 * np.cos(a), s * 58.5 * K, 118 * K + 11 * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 14, endpoint=False)],
                           (0, s, 0), 'glass', gp))
        m.add(MG.plate((330 * K, s * 2, 108 * K), (-56 * K, s * 48 * K, 36 * K), (-26 * K, s * 4, 40 * K), 'glass', gp, thick=0.8))      # windscreen
        m.add(MG.plate((268 * K, s * 56.6 * K, 96 * K), (-38 * K, 0, 0), (0, 0, 54 * K), 'glass', gp, thick=0.8))                        # cockpit side window
        m.add(MG.plate((350 * K, s * 6, 62 * K), (-40 * K, s * 36 * K, -8 * K), (-6 * K, 0, 34 * K), 'glass', gp, thick=0.8))           # lower nose glazing
    # roof: two engine nacelles with intakes and exhausts, gearbox fairing, mast
    rp = geo.frame(seed=seed + 3, soot=1.0, soot_x=-60.0 * K, soot_z=176.0 * K)
    for s in (-1, 1):
        m.add(MG.loft([(60 * K, MG.rrect_section(16 * K, 176 * K, 206 * K, 2.4, n=14, y_off=s * 22 * K)), (160 * K, MG.rrect_section(17 * K, 176 * K, 210 * K, 2.4, n=14, y_off=s * 22 * K)),
                       (210 * K, MG.rrect_section(15 * K, 178 * K, 206 * K, 2.2, n=14, y_off=s * 22 * K))], paint, rp, n=14))
        m.add(MG.cyl((70 * K, s * 36 * K, 192 * K), (30 * K, s * 48 * K, 188 * K), 9 * K, 'gunsteel', rp, sides=12, r1=8 * K))      # exhausts out to the sides
    m.add(MG.loft([(-90 * K, MG.rrect_section(30 * K, 176 * K, 200 * K, 2.6, n=16)), (-20 * K, MG.rrect_section(34 * K, 176 * K, 212 * K, 2.8, n=16)),
                   (40 * K, MG.rrect_section(34 * K, 176 * K, 212 * K, 2.8, n=16)), (70 * K, MG.rrect_section(30 * K, 176 * K, 200 * K, 2.6, n=16))], paint, rp, n=16))
    m.add(MG.cyl((HIP_MAST[0], 0, 210 * K), (HIP_MAST[0], 0, HIP_ROTOR_Z - 4), 5.5, 'gunsteel', rp, sides=10))
    # tail: boom end gearbox fairing, fin/pylon, stabilisers, the tail rotor on the right
    tp = geo.frame(seed=seed + 4, panel_u=60.0, panel_v=44.0)
    m.add(geo.prism([(-600 * K, 170 * K), (-650 * K, 176 * K), (-690 * K, 230 * K), (-672 * K, 236 * K), (-620 * K, 212 * K)], -6, 6, paint, tp))
    m.add(MG.box(-560 * K, -80 * K, 150 * K, -520 * K, 80 * K, 156 * K, paint, tp, r=1.5))
    m.add(MG.cyl((HIP_TAIL_ROTOR[0], 0, HIP_TAIL_ROTOR[2]), (HIP_TAIL_ROTOR[0], HIP_TAIL_ROTOR[1], HIP_TAIL_ROTOR[2]), 5.0, 'gunsteel', tp, sides=8))
    # tricycle gear: twin nose wheels, main wheels on outrigger struts
    wp = geo.frame(seed=seed + 5)
    m.add(MG.cyl((300 * K, 0, 44 * K), (300 * K, 0, 14 * K), 3.5, 'gunsteel', wp, sides=8))
    for s in (-1, 1):
        m.add(geo.tube([(300 * K, s * 9 * K, 14 * K), (300 * K, s * 13 * K, 14 * K)], 10 * K, sides=16, mat='rubber', part=wp))
        m.add(MG.cyl((-40 * K, s * 56 * K, 60 * K), (-60 * K, s * 112 * K, 20 * K), 3.6, 'gunsteel', wp, sides=8))      # main strut
        m.add(MG.cyl((20 * K, s * 56 * K, 48 * K), (-60 * K, s * 112 * K, 20 * K), 2.8, 'gunsteel', wp, sides=8))       # drag brace
        m.add(geo.tube([(-60 * K, s * 106 * K, 15 * K), (-60 * K, s * 118 * K, 15 * K)], 15 * K, sides=18, mat='rubber', part=wp))
    # external fuel tanks (the Hip's long side tanks) and antenna wires
    for s in (-1, 1):
        m.add(MG.loft([(-150 * K, MG.rrect_section(9 * K, 58 * K, 102 * K, 2.2, n=14, y_off=s * 60 * K)), (-60 * K, MG.rrect_section(11 * K, 54 * K, 106 * K, 2.6, n=14, y_off=s * 62 * K)),
                       (60 * K, MG.rrect_section(11 * K, 54 * K, 106 * K, 2.6, n=14, y_off=s * 62 * K)), (120 * K, MG.rrect_section(8 * K, 58 * K, 102 * K, 2.2, n=14, y_off=s * 60 * K))], paint, wp, n=14))
    # markings: red star on the boom, a tactical number on the nose
    STAR = MG.red_star_img(256)
    NUM = MG.text_img(['21'], 192, 128, color=(0.92, 0.88, 0.80), fonts=MG.SANS)
    for s in (-1, 1):
        m.add(geo.decal('star', (-470 * K if s > 0 else -430 * K, s * 21.5 * K, 118 * K), (-1 if s > 0 else 1, 0, 0), (0, 0, 1), (40 * K, 40 * K)))
        m.add(geo.decal('num', (250 * K if s < 0 else 300 * K, s * 58.6 * K, 70 * K), (1 if s < 0 else -1, 0, 0), (0, 0, 1), (50 * K, 34 * K)))
    if gunship:
        gun_part = geo.frame(seed=seed + 7)
        for s in (-1, 1):
            m.add(MG.box(-20 * K, s * 58 * K, 110 * K, 40 * K, s * 112 * K, 120 * K, paint, gun_part, r=1.5))          # outrigger
            for k, yy in enumerate((94, 120)):
                pod = geo.tube([(90 * K, s * yy * K, 98 * K), (-80 * K, s * yy * K, 98 * K)], 14 * K, sides=18, mat='gunsteel', part=gun_part)
                m.add(pod)
                m.add(MG.cyl((60 * K, s * yy * K, 98 * K + 14 * K), (60 * K, s * yy * K, 110 * K), 2.0, 'gunsteel', gun_part, sides=6))
                for q in range(16):
                    a = q * 2 * np.pi / 16; rr = 9.5 * K if q % 2 else 5.0 * K
                    m.add(geo.tube([(92 * K, s * yy * K + rr * np.cos(a), 98 * K + rr * np.sin(a)), (94 * K, s * yy * K + rr * np.cos(a), 98 * K + rr * np.sin(a))], 2.0, sides=8, mat='rust', part=gun_part, caps=False))
        m.add(MG.cyl((372 * K, 0, 92 * K), (400 * K, 0, 90 * K), 2.6, 'gunsteel', gun_part, sides=8))                     # nose machine gun
    m.recompute_normals(angle=48)
    return m, dict(star=STAR, num=NUM)


# ---------------------------------------------------------------- wrecks
def wreck(kind='huey', seed=21):
    """burnt hulk: the body loft crumpled, no glass, blades bent; dark burnt paint"""
    if kind == 'huey': m, imgs = huey_body(lod=1, seed=seed)
    else: m, imgs = hip_body(lod=1, seed=seed)
    rng = np.random.RandomState(seed)
    # crumple and twist
    V = m.V
    n = fbm(V[:, 0] * 0.02, V[:, 1] * 0.02, V[:, 2] * 0.02, 3, seed=seed)
    m.V = V + np.stack([n * 6, n * 10, -np.abs(n) * 14 * (V[:, 2] > 30)], 1)
    m.V[:, 2] = np.maximum(m.V[:, 2], 0.0)
    for c in m.charts:
        if c['mat'] in ('od', 'soviet', 'interior', 'seat', 'aluminium'): c['mat'] = 'burnt'
        if c['mat'] == 'glass': c['mat'] = 'gunsteel'
    m.recompute_normals(angle=48)
    # bent rotor on top
    r = rotor(HUEY_ROTOR_R if kind == 'huey' else HIP_ROTOR_R, flybar=kind == 'huey', seed=seed + 1, lod=1)
    x = r.V[:, 0]; r.V[:, 2] -= 0.0006 * x ** 2 * np.sign(x) * 0 + 0.0008 * (np.abs(x) - 40).clip(0) ** 2
    for c in r.charts: c['mat'] = 'burnt' if c['mat'] == 'od' else c['mat']
    r.transform(geo.rot('z', 25), (MAST[0] if kind == 'huey' else HIP_MAST[0], 0, ROTOR_Z if kind == 'huey' else HIP_ROTOR_Z))
    m.add(r)
    return m, imgs


# ---------------------------------------------------------------- specs
def _shaders():
    return {'od': M.od_paint, 'soviet': M.soviet_paint, 'interior': M.interior, 'seat': M.seat_canvas, 'glass': M.glass, 'gunsteel': M.gun_steel,
            'aluminium': M.aluminium, 'rubber': M.rubber, 'rust': M.rust, 'burnt': M.burnt_steel}


def _hulls_huey():
    return [MG.pts_box(-130, -52, 28, 150, 52, 142), MG.pts_box(-195, -24, 58, -130, 24, 136), MG.pts_box(-470, -20, 66, -195, 20, 112),
            MG.pts_box(150, -40, 34, 262, 40, 130), MG.pts_box(-470, -6, 104, -430, 6, 180), MG.pts_box(-392, -62, 90, -360, 62, 98),
            MG.pts_box(-130, -54, 0, 176, 54, 30), MG.pts_box(-70, -32, 139, 30, 32, 166)]


def _hulls_hip():
    K = HIP_K
    return [MG.pts_box(-180 * K, -58 * K, 42 * K, 240 * K, 58 * K, 180 * K), MG.pts_box(-280 * K, -40 * K, 70 * K, -180 * K, 40 * K, 170 * K),
            MG.pts_box(-668 * K, -20 * K, 104 * K, -280 * K, 20 * K, 176 * K), MG.pts_box(240 * K, -50 * K, 46 * K, 372 * K, 50 * K, 168 * K),
            MG.pts_box(-690 * K, -6, 170 * K, -600 * K, 6, 236 * K), MG.pts_box(-560 * K, -80 * K, 148 * K, -520 * K, 80 * K, 158 * K),
            MG.pts_box(-70 * K, -120 * K, 0, -50 * K, 120 * K, 44 * K), MG.pts_box(290 * K, -16 * K, 0, 310 * K, 16 * K, 44 * K),
            MG.pts_box(-90 * K, -36 * K, 176 * K, 70 * K, 36 * K, 212 * K)]


def _spec(body_fn, hulls, size=2048, **kw):
    m0, imgs = body_fn(lod=0, **kw)
    m1, _ = body_fn(lod=1, **kw)
    return dict(lods=[m0, m1], lod_thresholds=[0.0, 40.0], size=size, decal_size=1024, ground=0.0, surface='metal', metal=True,
                shaders=_shaders(), decal_imgs=imgs, hulls=hulls, stock={}, normal_strength=0.8)


def _rotor_spec(fn, r):
    m0 = fn(lod=0); m1 = fn(lod=1)
    lo, hi = m0.bounds()
    return dict(lods=[m0, m1], lod_thresholds=[0.0, 40.0], size=1024, ground=None, surface='metal', metal=True, shaders=_shaders(), stock={},
                hulls=[MG.pts_box(-r, -r, lo[2], r, r, hi[2])])


def specs():
    out = {}
    out['heli_huey'] = lambda: _spec(huey_body, _hulls_huey(), gunship=False)
    out['heli_huey_gun'] = lambda: _spec(huey_body, _hulls_huey(), gunship=True, seed=2)
    out['heli_hip'] = lambda: _spec(hip_body, _hulls_hip(), gunship=False)
    out['heli_hip_gun'] = lambda: _spec(hip_body, _hulls_hip(), gunship=True, seed=12)
    out['rotor_huey'] = lambda: _rotor_spec(lambda lod: rotor(HUEY_ROTOR_R, flybar=True, lod=lod), HUEY_ROTOR_R)
    out['rotor_hip'] = lambda: _rotor_spec(lambda lod: rotor(HIP_ROTOR_R, chord=24.0, blades=5, hub_r=12.0, flybar=False, seed=5, lod=lod, root=30.0), HIP_ROTOR_R)
    out['tailrotor_huey'] = lambda: _rotor_spec(lambda lod: tail_rotor(70.0, lod=lod), 70.0)
    out['tailrotor_hip'] = lambda: _rotor_spec(lambda lod: tail_rotor(76.0, chord=11.0, seed=6, lod=lod), 76.0)
    def wreck_spec(kind):
        m, imgs = wreck(kind)
        lo, hi = m.bounds()
        return dict(lods=[m], size=2048, decal_size=512, ground=0.0, surface='metal', metal=True, shaders=_shaders(), decal_imgs=imgs, stock={},
                    hulls=_hulls_huey() if kind == 'huey' else _hulls_hip(), single_lod=True)
    out['wreck_huey'] = lambda: wreck_spec('huey')
    out['wreck_hip'] = lambda: wreck_spec('hip')
    return {k: v for k, v in out.items()}
