"""Artillery: M102 105 mm howitzer (carriage + elevating gun as separate props), 122 mm single-rail rocket launcher (tripod + rail),
the rounds (105 mm shell, 122 mm rocket), ammo racks and crates, the FDC plotting tables for both sides.
Conventions: barrels point +x; the elevating part's origin is its trunnion pivot (the script sets its pitch and moves it back for recoil).
"""
import numpy as np
import geo
import mv_geo as MG
import mv_shaders as M
import shaders as S

# ---------------------------------------------------------------- M102 105 mm howitzer
TRUNNION = (0.0, 0.0, 44.0)        # pivot of the gun part, relative to the carriage origin (ground under the base plate centre)


def m102_carriage(lod=0, seed=31):
    """box trail with the round firing platform, roller, wheels (raised), spade, tow lunette; origin on the ground at the platform centre"""
    p = geo.frame(seed=seed, panel_u=40.0, panel_v=30.0)
    m = geo.Mesh()
    sides = 24 if lod == 0 else 12
    # firing platform (ring + spokes) the carriage pivots on
    m.add(MG.lathe_x([(0, 0), (62, 0), (62, 5), (58, 5), (58, 2), (0, 2)], 'od', sides=sides, part=p, x0=0.0).transform(geo.rot('y', -90)))
    for k in range(6):
        a = k * np.pi / 3
        m.add(MG.cyl((0, 0, 3), (56 * np.cos(a), 56 * np.sin(a), 3), 2.2, 'od', p, sides=8))
    # lower carriage: pivot drum and the box trail running back (-x)
    m.add(MG.cyl((0, 0, 4), (0, 0, 30), 16, 'od', p, sides=sides))
    m.add(MG.box(-150, -9, 22, -10, 9, 40, 'od', p, r=1.5, seg=1))
    m.add(MG.box(-176, -8, 24, -150, 8, 36, 'od', p, r=1.5))
    m.add(MG.cyl((-176, -11, 18), (-176, 11, 18), 9, 'rubber', p, sides=12))                    # trail roller
    m.add(MG.box(-186, -5, 26, -172, 5, 40, 'gunsteel', p))                                      # lunette block
    m.add(geo.tube([(-186, 0, 33) , (-200, 0, 33)], 2.2, sides=8, mat='gunsteel', part=p))
    # trunnion supports (two side frames) rising from the pivot
    for s in (-1, 1):
        m.add(geo.prism([(-26, 28), (22, 28), (12, 50), (-14, 50)], s * 18, s * 23, 'od', p))
        m.add(MG.cyl((0, s * 18, TRUNNION[2]), (0, s * 26, TRUNNION[2]), 5.0, 'gunsteel', p, sides=10))
    # axle and wheels, raised off the ground in the firing position
    m.add(MG.cyl((-40, -52, 30), (-40, 52, 30), 3.0, 'gunsteel', p, sides=10))
    for s in (-1, 1):
        m.add(MG.box(-46, s * 20, 28, -34, s * 48, 34, 'od', p))
        m.add(geo.tube([(-40, s * 50, 30), (-40, s * 62, 30)], 26, sides=sides, mat='rubber', part=p))
        m.add(geo.tube([(-40, s * 49, 30), (-40, s * 63, 30)], 14, sides=sides, mat='od', part=p))
        m.add(MG.cyl((-40, s * 50, 30), (-40, s * 64, 30), 5, 'gunsteel', p, sides=10))
    # gunner's seat and the traverse / elevation handwheels on the left
    m.add(MG.box(-70, 24, 40, -50, 42, 44, 'seat', p))
    m.add(MG.cyl((-60, 33, 26), (-60, 33, 40), 2.0, 'gunsteel', p, sides=8))
    for (x, y, z) in ((-20, 30, 48), (-34, 30, 44)):
        m.add(geo.tube([(x, y - 2, z), (x, y + 2, z)], 7, sides=12, mat='gunsteel', part=p, caps=False))
        m.add(MG.cyl((x, y - 3, z), (x, y + 3, z), 1.2, 'gunsteel', p, sides=6))
    # data plate decal on the trail
    PLATE = MG.text_img(['HOWITZER 105MM M102', 'US ARMY  NO. 2217'], 256, 64, color=(0.9, 0.9, 0.86), fonts=MG.SANS, size=22)
    m.add(geo.decal('plate', (-120, -9.6, 26), (1, 0, 0), (0, 0, 1), (40, 10)))
    m.recompute_normals(angle=50)
    return m, dict(plate=PLATE)


def m102_gun(lod=0, seed=32):
    """cradle, recoil system, breech, barrel with muzzle brake; origin at the trunnion"""
    p = geo.frame(seed=seed, soot=1.0, soot_x=150.0, soot_z=0.0)
    m = geo.Mesh()
    sides = 20 if lod == 0 else 10
    # cradle (U-channel) under the barrel, trunnion pins
    m.add(MG.box(-40, -11, -14, 40, 11, -6, 'od', p, r=1.5))
    for s in (-1, 1):
        m.add(MG.box(-40, s * 9, -14, 40, s * 11, 6, 'od', p, r=1.0))
        m.add(MG.cyl((0, s * 11, 0), (0, s * 18, 0), 4.6, 'gunsteel', p, sides=10))
    # recoil cylinders above the barrel
    for s in (-1, 1):
        m.add(geo.tube([(-30, s * 6.5, 12), (46, s * 6.5, 12)], 3.4, sides=10, mat='od', part=p))
    # barrel: 105 mm bore (4.2 u) -> tube ~ 8 u outer at the breech end tapering to 6 at the muzzle, 132 u long + muzzle brake
    prof = [(0, -38), (9.5, -38), (9.5, -26), (8.0, -20), (7.0, 20), (6.2, 80), (5.8, 118), (5.8, 122), (0, 122)]
    m.add(MG.lathe_x(prof, 'gunsteel', sides=sides, part=p, x0=0.0))
    # muzzle brake: a flat-sided block with side ports
    m.add(MG.box(122, -9, -8, 146, 9, 8, 'gunsteel', p, r=1.6))
    for s in (-1, 1):
        for xx in (128, 136):
            m.add(geo.tube([(xx, s * 9.1, 0), (xx, s * 5.5, 0)], 2.6, sides=8, mat='rust', part=p, caps=False))
    m.add(geo.tube([(146, 0, 0), (152, 0, 0)], 6.0, sides=sides, mat='gunsteel', part=p))
    # breech block (sliding wedge) and the breech ring, operating handle
    m.add(MG.box(-52, -10, -10, -36, 10, 10, 'gunsteel', p, r=1.2))
    m.add(MG.box(-50, 10, -9, -40, 16, -3, 'gunsteel', p))
    m.add(MG.cyl((-45, 16, -6), (-45, 24, -14), 1.3, 'gunsteel', p, sides=6))
    # panoramic sight bracket on the left
    m.add(MG.box(-12, 12, 4, 4, 18, 10, 'gunsteel', p))
    m.add(MG.cyl((-4, 15, 10), (-4, 15, 28), 2.4, 'gunsteel', p, sides=10))
    m.add(MG.box(-12, 12, 26, 4, 19, 32, 'gunsteel', p))
    m.recompute_normals(angle=50)
    return m


# ---------------------------------------------------------------- 122 mm single-rail launcher (DKB / "Grad-P" style)
RAIL_TRUNNION = (0.0, 0.0, 46.0)


def rocket_tripod(lod=0, seed=41):
    """tripod with spade feet, the traverse cradle; origin on the ground under the pivot"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    for k in range(3):
        a = np.radians(90 + 120 * k)
        foot = (64 * np.cos(a), 64 * np.sin(a), 0)
        m.add(MG.cyl((0, 0, 40), foot, 2.4, 'soviet', p, sides=8))
        m.add(MG.cyl((0, 0, 32), (foot[0] * 0.7, foot[1] * 0.7, 10), 1.4, 'soviet', p, sides=6))    # brace
        m.add(MG.box(foot[0] - 5, foot[1] - 5, 0, foot[0] + 5, foot[1] + 5, 3, 'gunsteel', p))      # foot plate
    m.add(MG.cyl((0, 0, 36), (0, 0, 44), 8, 'soviet', p, sides=14))
    for s in (-1, 1):
        m.add(MG.box(-8, s * 8, 40, 8, s * 11, RAIL_TRUNNION[2] + 6, 'soviet', p))
    # elevation quadrant and firing cable reel
    m.add(geo.prism([(-30, 30), (-6, 30), (-6, 60), (-16, 60)], 11, 13, 'gunsteel', p))
    m.add(MG.cyl((-20, -12, 12), (-20, -18, 12), 7, 'gunsteel', p, sides=12))
    m.recompute_normals(angle=50)
    return m


def rocket_rail(lod=0, seed=42):
    """the launch rail (channel + guide) pivoting at the trunnion; a rocket sits on it when loaded (separate prop)"""
    p = geo.frame(seed=seed, soot=1.0, soot_x=-30.0, soot_z=0.0)
    m = geo.Mesh()
    m.add(MG.box(-36, -7, -6, 100, 7, -2, 'soviet', p, r=0.8))
    for s in (-1, 1):
        m.add(MG.box(-36, s * 5.5, -2, 100, s * 7, 7, 'soviet', p, r=0.6))
        m.add(MG.cyl((0, s * 7, 0), (0, s * 10, 0), 3.4, 'gunsteel', p, sides=8))
    # spiral guide ribs along the channel, a blast deflector at the rear, a sight post
    for xx in range(-20, 100, 16):
        m.add(MG.box(xx, -5.5, -2, xx + 2, 5.5, 2.5, 'gunsteel', p))
    m.add(geo.prism([(-36, -6), (-30, -6), (-30, 14), (-36, 14)], -9, 9, 'gunsteel', p))
    m.add(MG.cyl((20, -8, 4), (20, -8, 16), 1.0, 'gunsteel', p, sides=6))
    m.recompute_normals(angle=50)
    return m


def rocket_122(lod=0, seed=43):
    """122 mm rocket: 76 u long, 5 u wide, folded fins at the tail; origin at the centre, nose +x"""
    p = geo.frame(seed=seed)
    sides = 16 if lod == 0 else 8
    prof = [(0, -38), (2.4, -38), (2.4, -34), (2.45, -10), (2.45, 18), (2.3, 30), (1.4, 36), (0, 38)]
    m = MG.lathe_x(prof, 'soviet', sides=sides, part=p, x0=0.0)
    for k in range(4):
        a = np.radians(45 + 90 * k)
        f = geo.prism([(-38, 2.3), (-27, 2.3), (-27, 5.2), (-36, 5.6)], -0.3, 0.3, 'gunsteel', p)
        f.transform(geo.rot('x', np.degrees(a)))
        m.add(f)
    BAND = MG.text_img(['122'], 64, 32, color=(0.9, 0.85, 0.2), fonts=MG.SANS)
    m.add(geo.decal('band', (10, -2.5, 2.6), (1, 0, 0), (0, 1, 0), (8, 5)))
    m.recompute_normals(angle=50)
    return m, dict(band=BAND)


def shell_105(lod=0, seed=44):
    """complete 105 mm round: brass case + OD projectile with a yellow band; 31 u long, origin at the centre, nose +x"""
    p = geo.frame(seed=seed)
    sides = 14 if lod == 0 else 8
    case = MG.lathe_x([(0, -16), (2.6, -16), (2.6, -15), (2.3, -14), (2.3, -2), (2.1, -1), (0, -1)], 'brass', sides=sides, part=p)
    proj = MG.lathe_x([(0, -1), (2.1, -1), (2.1, 6), (1.6, 11), (0.6, 14.5), (0, 15)], 'od', sides=sides, part=p)
    m = geo.Mesh(); m.add(case); m.add(proj)
    m.recompute_normals(angle=50)
    return m


def ammo_rack_105(lod=0, seed=45):
    """wooden rack of fibre shipping tubes (3 x 4) with two rounds lying on top; the loader's pick-up station"""
    p = geo.frame(seed=seed, tone=0.6)
    m = geo.Mesh()
    for z in (0, 24, 48):
        for yy in (-30, 30):
            m.add(geo.plank(70, 4, 4, mat='wood', seed=seed + int(z + yy), t=(0, yy, z + 2)))
    for xx in (-33, 33):
        m.add(geo.plank(66, 4, 4, mat='wood', seed=seed + 7 + xx, R=geo.rot('z', 90), t=(xx, 0, 2)))
        m.add(geo.plank(56, 4, 4, mat='wood', seed=seed + 9 + xx, R=geo.rot('y', 90), t=(xx, -30, 28)))
        m.add(geo.plank(56, 4, 4, mat='wood', seed=seed + 11 + xx, R=geo.rot('y', 90), t=(xx, 30, 28)))
    tp = geo.frame(seed=seed + 1)
    for z in (6, 30):
        for k in range(6):
            yy = -27 + k * 10.8
            m.add(geo.tube([(-34, yy, z + 6), (34, yy, z + 6)], 4.8, sides=10, mat='fibre', part=tp))
    s1 = shell_105(lod); s1.transform(geo.rot('z', 90), (-12, 0, 56)); m.add(s1)
    s2 = shell_105(lod); s2.transform(geo.rot('z', 86), (6, 2, 56)); m.add(s2)
    STENCIL = MG.text_img(['105MM HE M1', 'LOT ABC-12'], 256, 64, color=(0.1, 0.1, 0.1), fonts=MG.STENCIL, size=22)
    m.add(geo.decal('stencil', (-30, -32.2, 12), (1, 0, 0), (0, 0, 1), (30, 10)))
    m.recompute_normals(angle=50)
    return m, dict(stencil=STENCIL)


def rocket_crate(lod=0, seed=46):
    """open wooden crate with four 122 mm rockets, lid leaning against it; the T loader's pick-up station"""
    p = geo.frame(seed=seed, tone=0.55)
    m = geo.Mesh()
    L, W, H = 84, 30, 24
    for yy in (-W / 2 + 1, W / 2 - 1):
        m.add(geo.plank(L, H, 2, mat='wood', seed=seed + int(yy), R=geo.rot('x', 90), t=(0, yy, H / 2)))
    for xx in (-L / 2 + 1, L / 2 - 1):
        m.add(geo.plank(W - 4, H, 2, mat='wood', seed=seed + 5 + int(xx), R=geo.rot('z', 90) @ geo.rot('x', 90), t=(xx, 0, H / 2)))
    m.add(geo.plank(L, W, 2, mat='wood', seed=seed + 9, t=(0, 0, 1)))
    for k in range(4):
        r, imgs = rocket_122(lod, seed=seed + 20 + k)
        r.transform(None, (0, -10 + k * 6.6, 8 + (k % 2) * 4))
        m.add(r)
    lid = geo.plank(L, W, 2, mat='wood', seed=seed + 13, R=geo.rot('x', 70), t=(0, W / 2 + 10, 14))
    m.add(lid)
    m.recompute_normals(angle=50)
    return m, imgs


def plot_table(lod=0, seed=47, side='ct'):
    """FDC plotting table: folding table with the firing chart under acetate, protractor, dividers, field telephones, lamp.
    T version: bamboo trestle table with an oilcloth map and a Chinese field phone."""
    p = geo.frame(seed=seed, tone=0.5)
    m = geo.Mesh()
    if side == 'ct':
        m.add(MG.box(-48, -30, 34, 48, 30, 37, 'od', p, r=1.0))
        for s in (-1, 1):
            for t_ in (-1, 1):
                m.add(MG.cyl((s * 42, t_ * 26, 0), (s * 42, t_ * 26, 34), 1.3, 'gunsteel', p, sides=6))
            m.add(MG.cyl((s * 42, -26, 10), (s * 42, 26, 10), 0.9, 'gunsteel', p, sides=6))
        chart_mat = 'chart'
    else:
        for s in (-1, 1):
            m.add(geo.plank(96, 3.6, 3.6, mat='bamboo', seg=1, div=(2, 1, 1), seed=seed + s, t=(0, s * 24, 36), tone=0.4))
            for t_ in (-1, 1):
                m.add(geo.plank(38, 3.2, 3.2, mat='bamboo', seg=1, div=(2, 1, 1), seed=seed + 3 + s + t_, R=geo.rot('y', 90), t=(s * 40, t_ * 24, 18), tone=0.5))
                m.add(geo.plank(50, 3.0, 3.0, mat='bamboo', seg=1, div=(2, 1, 1), seed=seed + 7 + s + t_, R=geo.rot('x', 90), t=(s * 40, t_ * 0, 12), tone=0.5))
        for yy in np.arange(-22, 23, 4.4):
            m.add(geo.plank(92, 4.0, 2.0, mat='bamboo', seg=1, div=(3, 1, 1), seed=seed + 11 + int(yy), t=(0, yy, 38.5), tone=0.45))
        chart_mat = 'chart_t'
    # the chart (a decal panel), protractor, dividers, pencils
    m.add(MG.plate((-40, -24, 38.6 if side == 'ct' else 40.2), (80, 0, 0), (0, 48, 0), chart_mat, p, thick=0.3))
    m.add(geo.disk((10, 4, 39.3 if side == 'ct' else 40.9), [(10 + 14 * np.cos(a), 4 + 14 * np.sin(a), 39.3 if side == 'ct' else 40.9) for a in np.linspace(0, np.pi, 12)] + [(10 - 14, 4, 39.3 if side == 'ct' else 40.9)],
                   (0, 0, 1), 'glass', p))
    m.add(MG.cyl((-20, -10, 39.2), (-4, -2, 39.2), 0.5, 'gunsteel', p, sides=5))
    m.add(MG.cyl((-20, -10, 39.2), (-6, -14, 39.2), 0.5, 'gunsteel', p, sides=5))
    m.add(MG.cyl((20, -20, 39.2), (36, -16, 39.2), 0.5, 'wood', p, sides=5))
    # field telephones (two), a lamp on a gooseneck
    for xx in (-40, 40):
        m.add(MG.box(xx - 7, 20, 37, xx + 7, 29, 46, 'od' if side == 'ct' else 'soviet', p, r=1.0))
        m.add(MG.cyl((xx - 5, 24, 46), (xx + 5, 24, 46), 1.4, 'gunsteel', p, sides=6))
    m.add(MG.cyl((44, -26, 37), (44, -26, 62), 0.8, 'gunsteel', p, sides=6))
    m.add(MG.cyl((44, -26, 62), (34, -18, 66), 0.8, 'gunsteel', p, sides=6))
    m.add(MG.lathe_x([(0, 0), (5, 0), (6, 4), (3, 7), (0, 7)], 'gunsteel', sides=10, part=p).transform(geo.rot('y', 90) @ geo.rot('y', -90) @ geo.rot('y', 90), (34, -18, 60)))
    # chart image: a grid map of the valley (drawn by render_board.py later; here a placeholder grid so the decal exists)
    CHART = chart_img(side)
    m.recompute_normals(angle=50)
    return m, {'chart': CHART, 'chart_t': CHART}


def chart_img(side):
    from PIL import Image, ImageDraw
    import layout as L
    W, H = 512, 320
    im = Image.new('RGBA', (W, H), (226, 220, 196, 255)); d = ImageDraw.Draw(im)
    for k in range(0, W, 32): d.line([(k, 0), (k, H)], fill=(120, 140, 110, 255), width=1)
    for k in range(0, H, 32): d.line([(0, k), (W, k)], fill=(120, 140, 110, 255), width=1)
    pts = [((x + L.MAP_X) / (2 * L.MAP_X) * W, H - (float(L.river_y(x)) + L.MAP_Y) / (2 * L.MAP_Y) * H) for x in np.linspace(-L.MAP_X, L.MAP_X, 40)]
    d.line(pts, fill=(60, 90, 160, 255), width=4)
    for l, n, c in L.FLAGS:
        x, y = (c[0] + L.MAP_X) / (2 * L.MAP_X) * W, H - (c[1] + L.MAP_Y) / (2 * L.MAP_Y) * H
        d.ellipse([x - 7, y - 7, x + 7, y + 7], outline=(150, 30, 30, 255), width=2)
    return np.asarray(im, np.float32) / 255.0


# ---------------------------------------------------------------- specs
def _sh():
    return {'od': M.od_paint, 'soviet': M.soviet_paint, 'gunsteel': M.gun_steel, 'rubber': M.rubber, 'rust': M.rust, 'seat': M.seat_canvas,
            'brass': M.brass, 'wood': M.wood, 'bamboo': M.bamboo, 'fibre': lambda ctx: S.canvas(ctx, base=S._c(0.36, 0.30, 0.20), mud_top=4.0, stains=0.5),
            'glass': M.glass, 'chart': lambda ctx: dict(color=np.full((ctx.n, 3), 0.85, np.float32), rough=np.full(ctx.n, 0.5, np.float32)),
            'chart_t': lambda ctx: dict(color=np.full((ctx.n, 3), 0.8, np.float32), rough=np.full(ctx.n, 0.6, np.float32))}


def _two(fn, size=1024, hulls=None, ground=0.0, surface='metal', metal=True, thr=30.0, **kw):
    a = fn(lod=0, **kw); b = fn(lod=1, **kw)
    imgs = {}
    if isinstance(a, tuple): a, imgs = a; b = b[0]
    lo, hi = a.bounds()
    return dict(lods=[a, b], lod_thresholds=[0.0, thr], size=size, decal_size=512, ground=ground, surface=surface, metal=metal, shaders=_sh(),
                decal_imgs=imgs, stock={}, hulls=hulls or [MG.pts_box(lo[0], lo[1], lo[2], hi[0], hi[1], hi[2])])


def specs():
    return {
        'howitzer_m102': lambda: _two(m102_carriage, 2048, hulls=[MG.pts_box(-186, -12, 0, 24, 12, 50), MG.pts_box(-66, -64, 4, -14, 64, 56), MG.pts_box(-62, -62, 0, 62, 62, 6)]),
        'howitzer_m102_gun': lambda: _two(m102_gun, 1024, ground=None, hulls=[MG.pts_box(-52, -12, -14, 152, 12, 14)]),
        'rocket_tripod': lambda: _two(rocket_tripod, 1024, hulls=[MG.pts_box(-20, -20, 0, 20, 20, 54), MG.pts_box(-70, -62, 0, 70, 62, 8)]),
        'rocket_rail': lambda: _two(rocket_rail, 1024, ground=None, hulls=[MG.pts_box(-36, -10, -6, 100, 10, 14)]),
        'rocket_122': lambda: _two(rocket_122, 512, ground=None, hulls=[MG.pts_box(-38, -3, -3, 38, 3, 3)]),
        'shell_105': lambda: _two(shell_105, 512, ground=None, hulls=[MG.pts_box(-16, -3, -3, 15, 3, 3)]),
        'ammo_rack_105': lambda: _two(ammo_rack_105, 1024, surface='wood', hulls=[MG.pts_box(-36, -32, 0, 36, 32, 60)]),
        'rocket_crate': lambda: _two(rocket_crate, 1024, surface='wood', hulls=[MG.pts_box(-42, -15, 0, 42, 15, 24), MG.pts_box(-42, 14, 0, 42, 26, 30)]),
        'plot_table': lambda: _two(plot_table, 1024, surface='wood', hulls=[MG.pts_box(-48, -30, 0, 48, 30, 40)], side='ct'),
        'plot_table_t': lambda: _two(plot_table, 1024, surface='wood', hulls=[MG.pts_box(-48, -26, 0, 48, 26, 42)], side='t', seed=48),
    }
