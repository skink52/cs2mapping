"""Emplaced and door guns: M2 .50 cal on an M3 tripod, DShK on its wheeled Sokolov mount (AA configuration), quad .50 M55 mount,
M60 and PK door guns on pintles. Each weapon is two props: the mount (static) and the gun (`*_gun`, pivots at its origin = pintle;
the script aims it). Barrels point +x.
"""
import numpy as np
import geo
import mv_geo as MG
import mv_shaders as M
import shaders as S


def _barrel(m, x0, x1, r0, r1, p, sides, jacket=None):
    m.add(MG.cyl((x0, 0, 0), (x1, 0, 0), r0, 'gunsteel', p, sides=sides, r1=r1))
    if jacket:  # perforated barrel jacket (rings of holes as dark decal-less dents: boxes)
        jx0, jx1, jr = jacket
        m.add(MG.cyl((jx0, 0, 0), (jx1, 0, 0), jr, 'gunsteel', p, sides=sides))
        for k in range(int((jx1 - jx0) / 5)):
            for a in np.linspace(0, 2 * np.pi, 8, endpoint=False):
                xx = jx0 + 3 + k * 5
                m.add(geo.tube([(xx, (jr + 0.2) * np.cos(a), (jr + 0.2) * np.sin(a)), (xx, (jr - 0.6) * np.cos(a), (jr - 0.6) * np.sin(a))], 0.9, sides=6, mat='rust', part=p, caps=False))


def m2_gun(lod=0, seed=51):
    """M2HB: receiver, barrel with the perforated jacket, spade grips, ammo can on the left; origin at the pintle (under the receiver)"""
    p = geo.frame(seed=seed, soot=1.0, soot_x=20.0, soot_z=0.0)
    sides = 12 if lod == 0 else 8
    m = geo.Mesh()
    m.add(MG.box(-24, -5, 2, 18, 5, 10, 'gunsteel', p, r=0.8))                      # receiver
    m.add(MG.box(-10, -6, 10, 2, 6, 12, 'gunsteel', p, r=0.5))                        # top cover
    m.add(MG.box(-12, -3, 0, 12, 3, 2, 'gunsteel', p))                                 # pintle adapter
    _barrel(m, 18, 64, 2.0, 1.6, p, sides, jacket=(18, 38, 3.4) if lod == 0 else None)
    for s in (-1, 1):                                                                   # spade grips
        m.add(MG.cyl((-24, s * 3, 6), (-30, s * 5, 7), 1.0, 'gunsteel', p, sides=6))
        m.add(geo.tube([(-30, s * 5, 7), (-34, s * 5, 7)], 1.6, sides=8, mat='wood', part=p))
    m.add(MG.box(-26, -2, 10, -22, 2, 13, 'gunsteel', p))                               # trigger / backplate latch
    m.add(MG.box(-14, 5, 0, 2, 16, 9, 'od', p, r=0.6))                                  # ammo can on the feed side
    m.add(MG.cyl((-4, 5, 6), (-4, 11, 6), 0.6, 'brass', p, sides=6))                   # a bit of belt
    m.add(MG.cyl((14, 0, 10), (14, 0, 14), 0.6, 'gunsteel', p, sides=6))                # front sight
    m.recompute_normals(angle=50)
    return m


def m3_tripod(lod=0, seed=52):
    """M3 tripod with traverse bar; origin on the ground, pintle at z 30"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    head = (0, 0, 28)
    for (dx, dy) in ((-34, -30), (-34, 30), (40, 0)):
        m.add(MG.cyl(head, (dx, dy, 0), 1.6, 'gunsteel', p, sides=8))
        m.add(MG.box(dx - 3, dy - 3, 0, dx + 3, dy + 3, 2, 'gunsteel', p))
    m.add(MG.cyl((0, 0, 24), (0, 0, 31), 4.0, 'gunsteel', p, sides=10))
    m.add(MG.cyl((-20, -18, 14), (-20, 18, 14), 1.2, 'gunsteel', p, sides=6))          # traverse bar
    m.add(MG.box(-24, -2, 12, -16, 2, 16, 'gunsteel', p))
    m.recompute_normals(angle=50)
    return m


def dshk_gun(lod=0, seed=53):
    """DShK 12.7 mm: long finned barrel, round drum feed, spade grips; origin at the trunnion"""
    p = geo.frame(seed=seed, soot=1.0, soot_x=30.0, soot_z=0.0)
    sides = 12 if lod == 0 else 8
    m = geo.Mesh()
    m.add(MG.box(-26, -4.5, -4, 22, 4.5, 6, 'gunsteel', p, r=0.8))
    m.add(MG.cyl((-2, 0, 6), (-2, 0, 12), 7.0, 'gunsteel', p, sides=sides))             # drum feed on top
    _barrel(m, 22, 72, 2.4, 1.8, p, sides)
    for k in range(8 if lod == 0 else 0):                                                # cooling fins
        m.add(MG.cyl((26 + k * 4, 0, 0), (28 + k * 4, 0, 0), 3.6, 'gunsteel', p, sides=sides))
    m.add(MG.cyl((72, 0, 0), (82, 0, 0), 3.4, 'gunsteel', p, sides=sides, r1=4.0))      # muzzle brake
    for s in (-1, 1):
        m.add(MG.cyl((-26, s * 3, 2), (-34, s * 6, 3), 1.0, 'gunsteel', p, sides=6))
        m.add(geo.tube([(-34, s * 6, 3), (-39, s * 6, 3)], 1.6, sides=8, mat='wood', part=p))
    m.add(MG.cyl((-6, 0, 12), (-6, 0, 22), 0.8, 'gunsteel', p, sides=6))                # AA ring sight post
    m.add(geo.tube([(-6 + 6 * np.cos(a), 0, 22 + 6 * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 13)], 0.5, sides=6, mat='gunsteel', part=p, caps=False))
    m.recompute_normals(angle=50)
    return m


def dshk_mount(lod=0, seed=54):
    """Sokolov wheeled mount set up for AA: wheels removed, tripod legs up; origin on the ground, trunnion at z 58"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    for (dx, dy) in ((-40, -36), (-40, 36), (46, 0)):
        m.add(MG.cyl((0, 0, 52), (dx, dy, 0), 1.8, 'soviet', p, sides=8))
        m.add(MG.box(dx - 4, dy - 4, 0, dx + 4, dy + 4, 2, 'gunsteel', p))
    m.add(MG.cyl((0, 0, 48), (0, 0, 60), 5.0, 'soviet', p, sides=12))
    for s in (-1, 1): m.add(MG.box(-6, s * 5, 54, 6, s * 7, 64, 'soviet', p))
    # the two wheels leaning against a leg (removed for the AA role)
    for k, (dx, dy) in enumerate(((-46, -44), (-48, 44))):
        w = geo.tube([(-2, 0, 0), (2, 0, 0)], 14, sides=14, mat='rubber', part=p)
        w.transform(geo.rot('x', 70 if k == 0 else -70), (dx, dy, 14))
        m.add(w)
    m.add(MG.box(-8, -14, 0, 8, 14, 4, 'rust', p))                                      # ammo box at the foot
    m.recompute_normals(angle=50)
    return m


def quad50_mount(lod=0, seed=55):
    """M55 quad .50 turret: the trailer base with outriggers and the armoured gunner's tub; the four guns are the `quad50_gun` prop
    pivoting at z 66; origin on the ground under the turret axis"""
    p = geo.frame(seed=seed, panel_u=40.0, panel_v=30.0)
    sides = 16 if lod == 0 else 8
    m = geo.Mesh()
    m.add(MG.box(-60, -40, 10, 60, 40, 22, 'od', p, r=2))                               # trailer bed
    for (dx, dy) in ((-70, -60), (-70, 60), (70, -60), (70, 60)):
        m.add(MG.cyl((dx * 0.7, dy * 0.6, 16), (dx, dy, 2), 2.2, 'od', p, sides=8))
        m.add(MG.box(dx - 6, dy - 6, 0, dx + 6, dy + 6, 3, 'gunsteel', p))
    for s in (-1, 1):
        m.add(geo.tube([(0, s * 42, 16), (0, s * 52, 16)], 16, sides=sides, mat='rubber', part=p))
    m.add(MG.cyl((0, 0, 22), (0, 0, 40), 24, 'od', p, sides=sides))                     # turret ring / tub base
    tub = MG.loft([(0, MG.rrect_section(30, 40, 72, 2.4, n=16)), (24, MG.rrect_section(30, 40, 72, 2.4, n=16))], 'od', p, n=16, cap_front=False, cap_back=False)
    MG.remove_faces(tub, lambda c: c[:, 0] > 22)
    m.add(tub)
    m.add(MG.box(-30, -10, 40, 22, 10, 48, 'seat', p))                                    # gunner's seat
    for s in (-1, 1): m.add(MG.box(-10, s * 30, 40, 14, s * 34, 74, 'gunsteel', p))      # trunnion cheeks
    m.add(MG.box(-70, -14, 22, -52, 14, 46, 'od', p, r=1.5))                             # generator box at the rear
    m.recompute_normals(angle=50)
    return m


def quad50_gun(lod=0, seed=56):
    """four M2s in two pairs with the big ammo chests; origin at the trunnion"""
    p = geo.frame(seed=seed, soot=1.0, soot_x=20.0, soot_z=0.0)
    m = geo.Mesh()
    for (dy, dz) in ((-20, 10), (20, 10), (-20, -8), (20, -8)):
        g = m2_gun(lod, seed=seed + int(dy + dz))
        MG.remove_faces(g, lambda c: c[:, 1] > 5)  # drop the single ammo can; the chests feed them
        g.transform(None, (0, dy, dz))
        m.add(g)
    for s in (-1, 1):
        m.add(MG.box(-30, s * 34, -12, 6, s * 50, 16, 'od', p, r=1.0))                   # ammo chest
    m.add(MG.box(-30, -26, -14, 4, 26, -10, 'gunsteel', p))                              # cradle
    m.add(MG.cyl((-20, 0, -10), (-20, 0, 0), 2.0, 'gunsteel', p, sides=8))
    m.recompute_normals(angle=50)
    return m


def m60_gun(lod=0, seed=57):
    """M60 door gun: receiver, feed tray, barrel with bipod folded, buttstock; origin at the pintle under the receiver"""
    p = geo.frame(seed=seed, soot=1.0, soot_x=18.0, soot_z=0.0)
    sides = 10 if lod == 0 else 6
    m = geo.Mesh()
    m.add(MG.box(-18, -2.6, 1, 14, 2.6, 6.5, 'gunsteel', p, r=0.6))
    m.add(MG.box(-6, -3, 6.5, 8, 3, 8, 'gunsteel', p, r=0.5))                           # feed cover
    m.add(MG.cyl((14, 0, 4), (44, 0, 4), 1.3, 'gunsteel', p, sides=sides))
    m.add(MG.cyl((14, 0, 2), (30, 0, 2), 1.6, 'gunsteel', p, sides=sides))               # gas cylinder
    m.add(MG.cyl((40, 0, 4), (46, 0, 4), 1.8, 'gunsteel', p, sides=sides))               # flash hider
    m.add(MG.box(-30, -2, 0, -18, 2, 7, 'rubber', p, r=0.8))                             # buttstock
    m.add(MG.box(-10, -1.2, -3, -4, 1.2, 1, 'rubber', p, r=0.5))                         # pistol grip
    m.add(MG.box(-6, 2.6, 0, 6, 10, 5, 'od', p, r=0.5))                                  # ammo box (feed side)
    m.add(MG.cyl((0, 0, -3), (0, 0, 1), 1.2, 'gunsteel', p, sides=6))                   # pintle pin
    m.recompute_normals(angle=50)
    return m


def pk_gun(lod=0, seed=58):
    """PK door gun: fluted barrel, carry handle, skeleton stock; origin at the pintle"""
    p = geo.frame(seed=seed, soot=1.0, soot_x=18.0, soot_z=0.0)
    sides = 10 if lod == 0 else 6
    m = geo.Mesh()
    m.add(MG.box(-16, -2.4, 1, 12, 2.4, 6, 'gunsteel', p, r=0.6))
    m.add(MG.cyl((12, 0, 4), (44, 0, 4), 1.2, 'gunsteel', p, sides=sides, r1=1.0))
    m.add(MG.cyl((40, 0, 4), (46, 0, 4), 1.6, 'gunsteel', p, sides=sides))
    m.add(MG.cyl((2, 0, 6), (10, 0, 6), 0.8, 'gunsteel', p, sides=6))                   # carry handle
    m.add(geo.prism([(-30, 0), (-16, 1), (-16, 7), (-28, 7), (-30, 4)], -1.2, 1.2, 'wood', p))   # skeleton stock
    m.add(MG.box(-8, -1.2, -3, -3, 1.2, 1, 'wood', p, r=0.5))
    m.add(MG.box(-4, 2.4, 0, 8, 9, 4, 'soviet', p, r=0.5))
    m.add(MG.cyl((0, 0, -3), (0, 0, 1), 1.2, 'gunsteel', p, sides=6))
    m.recompute_normals(angle=50)
    return m


def _sh():
    return {'od': M.od_paint, 'soviet': M.soviet_paint, 'gunsteel': M.gun_steel, 'rubber': M.rubber, 'rust': M.rust, 'seat': M.seat_canvas,
            'brass': M.brass, 'wood': M.wood}


def _two(fn, size=1024, hulls=None, ground=0.0, thr=30.0, **kw):
    a = fn(lod=0, **kw); b = fn(lod=1, **kw)
    lo, hi = a.bounds()
    return dict(lods=[a, b], lod_thresholds=[0.0, thr], size=size, ground=ground, surface='metal', metal=True, shaders=_sh(), stock={},
                hulls=hulls or [MG.pts_box(lo[0], lo[1], lo[2], hi[0], hi[1], hi[2])])


def specs():
    return {
        'm2_gun': lambda: _two(m2_gun, 512, ground=None, hulls=[MG.pts_box(-34, -6, 0, 64, 16, 14)]),
        'm3_tripod': lambda: _two(m3_tripod, 512, hulls=[MG.pts_box(-36, -32, 0, 42, 32, 31)]),
        'dshk_gun': lambda: _two(dshk_gun, 512, ground=None, hulls=[MG.pts_box(-39, -8, -4, 82, 8, 14)]),
        'dshk_mount': lambda: _two(dshk_mount, 512, hulls=[MG.pts_box(-48, -46, 0, 50, 46, 64)]),
        'quad50_mount': lambda: _two(quad50_mount, 1024, hulls=[MG.pts_box(-76, -66, 0, 76, 66, 24), MG.pts_box(-32, -32, 22, 24, 32, 74)]),
        'quad50_gun': lambda: _two(quad50_gun, 1024, ground=None, hulls=[MG.pts_box(-30, -50, -14, 64, 50, 20)]),
        'm60_gun': lambda: _two(m60_gun, 512, ground=None, hulls=[MG.pts_box(-30, -3, -3, 46, 10, 8)]),
        'pk_gun': lambda: _two(pk_gun, 512, ground=None, hulls=[MG.pts_box(-30, -3, -3, 46, 9, 7)]),
    }
