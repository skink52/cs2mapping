"""The bridge (flag B) and its defences: a riveted steel Warren truss span with a timber deck, a concrete river pier, a sandbagged
checkpoint (sentry hut, raised barrier pole, knife-rest), an old French concrete pillbox you can enter.

Origins: truss_span = centre of the span on the DECK TOP (z 0 is where you walk; the steel hangs 22 u below, the truss stands 158
above), span along x, 600 long, 160 clear between the curbs. bridge_pier = centre of its bearing seat (TOP): put it under each
span end at span z - 22; the shaft goes 280 down. checkpoint = on the ground in the middle of the road, road along x.
french_bunker = on the ground, main firing slit to +x, door on -x behind a blast wall.
"""
import numpy as np
import geo
import mv_geo as MG
import mv_shaders as M
import shaders as S
from noise import fbm, smoothstep
import p_sandbag


def beam(p0, p1, w, h, mat, seed=0, r=0.5, **pk):
    """box-section member between two points: w across (horizontal), h deep"""
    p0 = np.asarray(p0, float); p1 = np.asarray(p1, float)
    d = p1 - p0; L = float(np.linalg.norm(d)); R = geo.look_frame(d)
    m = geo.rbox(L, w, h, r=r, seg=1, mat=mat, part=geo.frame(seed=seed, **pk))
    m.transform(R, (p0 + p1) / 2)
    return m


# ---------------------------------------------------------------- truss span
def truss_span(lod=0, seed=121, L=600.0, W=160.0, Ht=150.0):
    m = geo.Mesh()
    ty = W / 2 + 8.0                                  # truss planes just outside the curbs
    xb = np.arange(-L / 2, L / 2 + 1, 100.0); xt = xb[:-1] + 50.0
    pk = dict(panel_u=50.0, panel_v=0.0)
    for s in (-1, 1):
        m.add(beam((-L / 2, s * ty, -8), (L / 2, s * ty, -8), 10, 16, 'truss', seed + 1 + s, **pk))
        m.add(beam((xt[0] - 6, s * ty, Ht), (xt[-1] + 6, s * ty, Ht), 11, 14, 'truss', seed + 3 + s, **pk))
        for j, x in enumerate(xt):
            m.add(beam((x - 50, s * ty, -2), (x, s * ty, Ht - 5), 8, 9, 'truss', seed + 10 + j + s * 20))
            m.add(beam((x + 50, s * ty, -2), (x, s * ty, Ht - 5), 8, 9, 'truss', seed + 30 + j + s * 20))
            m.add(MG.box(x - 21, s * ty - 6.4, Ht - 20, x + 21, s * ty + 6.4, Ht + 8.5, 'truss', geo.frame(seed=seed + 50 + j), r=0.6))       # gussets
        for j, x in enumerate(xb):
            w = 19 if 0 < j < len(xb) - 1 else 12
            m.add(MG.box(max(x - w, -L / 2), s * ty - 6.4, -17.5, min(x + w, L / 2), s * ty + 6.4, 15, 'truss', geo.frame(seed=seed + 60 + j), r=0.6))
        m.add(MG.box(-L / 2, s * (W / 2 - 6), 0, L / 2, s * (W / 2), 7, 'wood', geo.frame(seed=seed + 70 + s, tone=0.7), r=0.8))                # timber curb
        for z in (24, 42): m.add(MG.cyl((-L / 2, s * (ty - 6.5), z), (L / 2, s * (ty - 6.5), z), 1.5, 'truss', geo.frame(seed=seed + 72), sides=6))   # pipe rails
    for j, x in enumerate(xt):
        m.add(beam((x, -ty, Ht + 1), (x, ty, Ht + 1), 7, 9, 'truss', seed + 80 + j))                                                            # top struts
        if j < len(xt) - 1:
            m.add(beam((x, -ty, Ht + 1), (xt[j + 1], ty, Ht + 1), 3.6, 3.6, 'truss', seed + 90 + j)); m.add(beam((x, ty, Ht + 1), (xt[j + 1], -ty, Ht + 1), 3.6, 3.6, 'truss', seed + 100 + j))
    for s in (-1, 1):                                                                                                                           # portal knee braces at both ends
        for x in (xt[0], xt[-1]):
            m.add(beam((x, s * ty, Ht - 34), (x, s * (ty - 34), Ht), 4, 4, 'truss', seed + 110))
    for j, x in enumerate(xb):
        m.add(beam((x, -ty - 4, -14), (x, ty + 4, -14), 9, 16, 'truss', seed + 120 + j, **pk))                                                  # floor beams
    for k, y in enumerate(np.linspace(-60, 60, 5)):
        m.add(beam((-L / 2, y, -9), (L / 2, y, -9), 6, 10, 'truss', seed + 130 + k))                                                            # stringers
    rng = np.random.RandomState(seed)
    n = int(L / 12.5)
    for i in range(n):                                                                                                                          # deck planks across the span
        x = -L / 2 + (i + 0.5) * L / n
        m.add(geo.plank(W - 1 + rng.uniform(-3, 3), L / n - 0.7, 4.0, mat='wood', seed=seed + 200 + i, r=0.5, seg=1, div=(1, 1, 1), warp=0.5,
                        R=geo.rot('z', 90 + rng.uniform(-0.6, 0.6)), t=(x, rng.uniform(-1, 1), -2.0), tone=rng.rand()))
    for s in (-1, 1):                                                                                                                           # wheel-track running boards
        for k in range(3):
            for q in (-7.5, 7.5):
                m.add(geo.plank(199, 14, 2.2, mat='wood', seed=seed + 300 + k + s, r=0.4, seg=1, div=(2, 1, 1), warp=0.3, t=(-200 + k * 200, s * 38 + q, 1.0), tone=0.3 + 0.5 * rng.rand()))
    B = MG.pts_box
    hulls = [B(-L / 2, -ty - 6, -22, L / 2, ty + 6, 0), B(-L / 2, W / 2 - 6, 0, L / 2, ty + 6.5, 44), B(-L / 2, -ty - 6.5, 0, L / 2, -W / 2 + 6, 44),
             B(xt[0] - 8, -ty - 6, Ht - 8, xt[-1] + 8, ty + 6, Ht + 8)]
    return m, hulls


def bridge_pier(lod=0, seed=122, depth=280.0):
    m = geo.Mesh()
    p = geo.frame(seed=seed)
    m.add(MG.box(-36, -112, -26, 36, 112, 0, 'conc', p, r=2.5, seg=2))
    for s in (-1, 1):
        m.add(MG.box(-14, s * 88 - 12, 0, 14, s * 88 + 12, 2.0, 'steel', p, r=0.4))
        for q in (-9, 9): m.add(MG.cyl((q, s * 88 - 8, 2), (q, s * 88 - 8, 4.5), 1.4, 'steel', p, sides=6))
    def plan(hx, hy):
        nose = hx * 1.3
        return np.array([[hx, -hy + nose], [hx, hy - nose], [0, hy], [-hx, hy - nose], [-hx, -hy + nose], [0, -hy]], float)
    m.add(MG.vloft([(-depth + 30, plan(31, 114)), (-depth * 0.5, plan(26.5, 106)), (-26, plan(22, 98))], 'conc', p, cap_top=False))
    m.add(MG.box(-46, -128, -depth, 46, 128, -depth + 30, 'conc', p, r=2.0))
    B = MG.pts_box
    return m, [B(-36, -112, -26, 36, 112, 0), np.vstack([np.c_[plan(31, 114), np.full(6, -depth + 30)], np.c_[plan(22, 98), np.full(6, -26.0)]]), B(-46, -128, -depth, 46, 128, -depth + 30)]


# ---------------------------------------------------------------- checkpoint
def checkpoint(lod=0, seed=123):
    """road along x. +y side: a plank sentry hut with a tin roof and the barrier's pivot; the pole is raised. -y side: the rest post
    and a chest-high sandbag wall; a second wall beside the hut; a knife-rest pulled off the road; drums."""
    import p_base
    m = geo.Mesh(); H = []
    B = MG.pts_box
    p = geo.frame(seed=seed, tone=0.6)
    # hut: floor 72 x 64 at y 86..150
    m.add(MG.box(-38, 84, 0, 38, 152, 3, 'wood', p)); H.append(B(-38, 84, 0, 38, 152, 3))
    for a, b, op in (((36, 150), (-36, 150), []), ((-36, 150), (-36, 86), [(20, 46, 44, 72)]), ((36, 86), (36, 150), [(14, 50, 3, 78)]), ((-36, 86), (36, 86), [(8, 64, 42, 76)])):
        w, hs = MG.slab_wall(a, b, 3, 88, 2.6, 'plank', geo.frame(seed=seed + 3 + len(H), tone=0.5), openings=op, r=0.4)
        m.add(w); H += hs
    for (x, y) in ((-36, 86), (36, 86), (-36, 150), (36, 150)):
        m.add(MG.box(x - 2.5, y - 2.5, 0, x + 2.5, y + 2.5, 98 if y < 100 else 86, 'wood', p, r=0.5))
    m.add(MG.box(-36, 84, 40, 36, 92, 42.5, 'wood', p, r=0.4))                                      # counter shelf at the front opening
    roof = MG.plate((-46, 76, 100), (92, 0, 0), (0, 84, -15), 'tin', geo.frame(R=geo.rot('z', 90), seed=seed + 20), thick=1.2); m.add(roof)
    H.append(np.array([[-46, 76, 98], [46, 76, 98], [-46, 160, 83], [46, 160, 83], [-46, 76, 102], [46, 76, 102], [-46, 160, 87], [46, 160, 87]], float))
    m.add(MG.box(-30, 84.6, 78, 30, 86.2, 97, 'paint_white', p, r=0.3))
    SIGN = MG.text_img(['CHECKPOINT 4', 'TRAM KIEM SOAT'], 512, 160, color=(0.10, 0.10, 0.10), fonts=MG.STENCIL)
    m.add(geo.decal('sign', (-28, 84.4, 79.5), (1, 0, 0), (0, 0, 1), (56, 16), lift=0.1))
    m.add(MG.cyl((10, 120, 3), (10, 120, 19), 6.5, 'wood', p, sides=10))                             # stool
    m.add(MG.box(-24, 86, 42.5, -10, 93, 50, 'od', p, r=0.6))                                        # field telephone on the shelf
    # barrier: pivot posts at y 72, the pole raised 55 degrees toward -y, counterweight, rest post at y -72
    for q in (-5, 5): m.add(MG.box(q - 2, 70, 0, q + 2, 76, 52, 'wood', p, r=0.5))
    m.add(MG.cyl((-8, 73, 44), (8, 73, 44), 1.4, 'steel', p, sides=6))
    piv = np.array([0, 73, 44.0]); d = np.array([0, -np.cos(np.radians(55)), np.sin(np.radians(55))])
    bp = geo.frame(R=geo.look_frame(d), o=piv, seed=seed + 30)
    m.add(geo.tube([piv - d * 26, piv + d * 60, piv + d * 150], [3.0, 2.8, 2.2], sides=10, mat='stripe', part=bp))
    cw = geo.rbox(16, 12, 14, r=1.0, mat='steel', part=geo.frame(seed=seed + 31)); cw.transform(geo.look_frame(d), piv - d * 30); m.add(cw)
    m.add(geo.tube([piv + d * 148, piv + d * 142 + np.array([0, 0, -40]), piv + d * 140 + np.array([3, 2, -86])], 0.5, sides=4, mat='rope', part=p))   # pull rope
    m.add(MG.box(-2.5, -76, 0, 2.5, -70, 46, 'wood', p, r=0.5))
    for q in (-4, 4): m.add(MG.box(q - 1.2, -76, 44, q + 1.2, -70, 54, 'wood', p, r=0.4))
    H += [B(-8, 69, 0, 8, 77, 54), B(-5, -77, 0, 5, -69, 54)]
    # sandbag walls (chest high)
    for k, (cx, cy, yaw, ln) in enumerate(((70, -98, 180, 96), (-78, 104, 90, 80))):
        w, hgt = p_sandbag.wall(length=ln, courses=8, lod=1, seed=seed + 40 + k, top=True)
        lo, hi = w.bounds()
        R = geo.rot('z', yaw)
        w.transform(R, (cx, cy, 0)); m.add(w)
        H.append(MG.xform_pts(B(lo[0], lo[1] + 2, 0, hi[0], hi[1] - 1, hi[2] - 1.5), R, (cx, cy, 0)))
    # knife-rest (cheval de frise) pulled aside, drums
    kr = geo.Mesh()
    for x in (-44, 44):
        for a in (-40, 40):
            kr.add(geo.plank(62, 4, 4, mat='wood', seed=seed + 60 + x + a, R=geo.rot('x', 0) @ geo.rot('y', 90) @ geo.rot('x', a) if False else geo.rot('x', a) @ geo.rot('y', 90), t=(x, 0, 21)))
    kr.add(geo.plank(104, 5, 5, mat='wood', seed=seed + 66, t=(0, 0, 23)))
    for k in range(9):
        t = k / 8.0
        kr.add(geo.tube([(-48 + 96 * t, 16 * np.sin(k * 1.9), 30 + 9 * np.cos(k * 1.9)), (-48 + 96 * (t + 0.06), 16 * np.sin(k * 1.9 + 1.2), 26 + 9 * np.cos(k * 1.9 + 1.2)), (-48 + 96 * (t + 0.12), 16 * np.sin(k * 1.9 + 2.4), 30 + 9 * np.cos(k * 1.9 + 2.4))], 0.35, sides=4, mat='steel', part=geo.frame(seed=seed + 70 + k), caps=False))
    Rk = geo.rot('z', 24); tk = (-70, -112, 0)
    kr.transform(Rk, tk); m.add(kr); H.append(MG.xform_pts(B(-50, -18, 0, 50, 18, 40), Rk, tk))
    for k, (x, y, mat) in enumerate(((52, 82, 'rust'), (-56, -76, 'od'), (-80, -74, 'paint_red'))):
        dd = p_base.drum(lod, seed + 80 + k, mat=mat); dd.transform(geo.rot('z', 40 * k), (x, y, 0)); m.add(dd); H.append(B(x - 12, y - 12, 0, x + 12, y + 12, 34))
    return m, H, dict(sign=SIGN)


# ---------------------------------------------------------------- French pillbox
def french_bunker(lod=0, seed=124):
    """1950s concrete blockhouse: 200 x 170 x 116, walls 18 thick, slits (z 50..66) on +x, +y and -y, a 44 x 82 door on -x behind a
    free-standing blast wall, firing benches inside. Hulls: every wall piece, floor, roof, blast wall."""
    m = geo.Mesh(); H = []
    B = MG.pts_box
    p = geo.frame(seed=seed)
    m.add(MG.box(-104, -89, -5, 104, 89, 1, 'conc', p, r=0.8)); H.append(B(-104, -89, -5, 104, 89, 1))
    walls = (((91, -85), (91, 85), [(49, 121, 50, 66)]), ((-91, 85), (-91, -85), [(63, 107, 1, 83)]),
             ((82, 76), (-82, 76), [(52, 112, 50, 66)]), ((-82, -76), (82, -76), [(52, 112, 50, 66)]))
    for k, (a, b, op) in enumerate(walls):
        w, hs = MG.slab_wall(a, b, 1, 98, 18.0, 'conc', geo.frame(seed=seed + 1 + k), openings=op, r=1.0)
        m.add(w); H += hs
    m.add(MG.box(-108, -93, 98, 108, 93, 116, 'conc', geo.frame(seed=seed + 6), r=3.0, seg=2)); H.append(B(-108, -93, 98, 108, 93, 116))
    # visors over the slits, sills, benches
    m.add(MG.box(100, -42, 66, 107, 42, 73, 'conc', p, r=1.0))
    for s in (-1, 1):
        m.add(MG.box(-36, s * 85, 66, 36, s * 92, 73, 'conc', p, r=1.0))
        m.add(MG.box(-34, s * 67, 1, 34, s * 51, 15, 'conc', p, r=0.8)); H.append(B(-34, min(s * 67, s * 51), 1, 34, max(s * 67, s * 51), 15))
    m.add(MG.box(66, -40, 1, 82, 40, 15, 'conc', p, r=0.8)); H.append(B(66, -40, 1, 82, 40, 15))
    # blast wall covering the door, door leaf swung open, vent pipe, rebar where the roof corner has spalled
    m.add(MG.box(-150, -40, 0, -136, 40, 84, 'conc', geo.frame(seed=seed + 8), r=1.5)); H.append(B(-150, -40, 0, -136, 40, 84))
    door = MG.plate((-100.5, 22, 2), (-30, 22, 0), (0, 0, 78), 'rust', geo.frame(seed=seed + 9, panel_u=20.0, panel_v=26.0), thick=1.6); m.add(door)
    H.append(MG.pts_of(door))
    m.add(MG.cyl((40, 30, 116), (40, 30, 136), 4.0, 'rust', p, sides=10)); m.add(MG.cyl((40, 30, 136), (40, 30, 139), 7.0, 'rust', p, sides=10, r1=2.0))
    rng = np.random.RandomState(seed)
    for k in range(5):
        x0 = np.array([104 - rng.uniform(0, 14), -90 + rng.uniform(0, 14), 114.0])
        m.add(geo.tube([x0, x0 + np.array([rng.uniform(2, 8), -rng.uniform(2, 8), rng.uniform(6, 12)]), x0 + np.array([rng.uniform(6, 16), -rng.uniform(4, 14), rng.uniform(2, 10)])], 0.6, sides=4, mat='rust', part=p))
    for k in range(6):
        c = geo.rbox(rng.uniform(6, 16), rng.uniform(5, 12), rng.uniform(4, 9), r=1.2, mat='conc', part=geo.frame(seed=seed + 20 + k))
        c.transform(geo.euler(rng.uniform(0, 360), rng.uniform(-20, 20), rng.uniform(-20, 20)), (112 + rng.uniform(0, 26), -98 - rng.uniform(0, 26), rng.uniform(2, 5))); m.add(c)
    ST = MG.text_img(['P.K. 7', '1951'], 256, 128, color=(0.10, 0.10, 0.10), fonts=MG.STENCIL)
    m.add(geo.decal('st', (-100.1, 20, 86), (0, -1, 0), (0, 0, 1), (40, 11), lift=0.12))
    return m, H, dict(st=ST)


# ---------------------------------------------------------------- specs
def _formwork(ctx):
    """board-marked concrete: the shuttering boards left ridges every 11 u"""
    out = M.concrete(ctx, tone=S._c(0.50, 0.49, 0.44), damage=0.9)
    z = ctx.P[:, 2] / 11.0; f = z - np.floor(z)
    line = smoothstep(0.07, 0.0, np.minimum(f, 1 - f)) * (np.abs(ctx.N[:, 2]) < 0.6)
    out['height'] = out['height'] + 0.35 * line
    out['color'] = np.clip(out['color'] * (1 - 0.18 * line[:, None]), 0, 1)
    return out


def _sh():
    return {'truss': lambda c: S.rust_steel(c, paint=S._c(0.33, 0.37, 0.31), chip=0.44, rivets=True, mud_top=0.0), 'wood': M.wood_dark,
            'plank': lambda c: S.wood(c, weather=0.75, mud_top=14.0, wet=0.6), 'conc': _formwork, 'steel': M.steel, 'rust': M.rust, 'tin': lambda c: _tin(c),
            'stripe': M.stripes, 'rope': M.rope, 'od': M.od_paint, 'paint_white': lambda c: S.painted_steel(c, S._c(0.82, 0.80, 0.72), chip=0.2, mud_top=0.0),
            'paint_red': lambda c: S.painted_steel(c, S._c(0.62, 0.12, 0.10), chip=0.3), 'burlap': S.burlap, 'gunsteel': M.gun_steel}


def _tin(ctx):
    out = S.rust_steel(ctx, paint=S._c(0.55, 0.56, 0.54), chip=0.5, mud_top=0.0)
    out['height'] = out['height'] + 0.3 * np.sin(ctx.S[:, 0] * 1.4)
    return out


def _spec(fn, size=2048, surface='concrete', metal=False, ground=0.0, **kw):
    r = fn(lod=0, **kw)
    m, hulls = r[0], r[1]
    return dict(lods=[m], single_lod=True, size=size, decal_size=512, ground=ground, surface=surface, metal=metal, shaders=_sh(), stock={},
                decal_imgs=r[2] if len(r) > 2 else {}, hulls=hulls)


def specs():
    return {
        'truss_span': lambda: _spec(truss_span, 2048, surface='metal', metal=True, ground=None),
        'bridge_pier': lambda: _spec(bridge_pier, 1024, ground=None),
        'checkpoint': lambda: _spec(checkpoint, 2048, surface='wood', metal=True),
        'french_bunker': lambda: _spec(french_bunker, 2048),
    }
