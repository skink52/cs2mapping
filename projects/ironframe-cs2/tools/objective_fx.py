"""IRONFRAME objective world markers (10 Nov 2026 playtest: "not much indication of what mode is playing ... make zones and capture
progress more obvious"). Self-lit props the script moves (src/cs2/45_features.js objTick), one pre-coloured model per team
because the self-lit material ignores SetColor (tools/fx.py iff_t / iff_ct). All lie in models/ifr/fx/obj/<name>.vmdl:
  obj_ring_<c>        flat ground ring, radius 100 (band 92-100, 8 chevrons out to 112): the script scales it to the zone radius
  obj_arc_<t|ct>_NN   capture progress: a flat annular sector at radius 76-88, NN/20 of the circle from north clockwise (NN 01..20)
  obj_col_<c>         a light column 3000 u tall, r 16, with a brighter 120 u cap band: the script sinks it into the ground to show
                      progress (visible height = progress), so it needs no scaling
  obj_letter_<ID>_<c> the zone letter A..E, 5 x 7 blocks of 26 u on both faces of a dark plate (151 x 203 x 26), each face reading the
                      right way round; it floats and turns over the zone
  obj_flag_<t|ct>     the flag: a 420 u pole with a 190 x 120 banner and a top ball, feet at z 0
c = n (neutral, warm white), t (orange 255 140 40), ct (cyan 40 200 255), w (white: the contested flash)
Writes out/addon/_gen/objectives.json {models: {key: vmdl}} for tools/patch_cache.py (the cache room props make CS2 load them).
Does not touch models.json (tools/fx.py owns it).
usage: python -I tools/objective_fx.py [--no-compile] [--only key,key]
"""
import json, math, os, sys
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fx as FX                                              # noqa: E402  (write_model, OUT, the create/ path setup)
import geo, fx_models                                        # noqa: E402
import frames as FR                                          # noqa: E402

REL_M, REL_T = 'models/ifr/fx/obj', 'materials/ifr/fx'
COLORS = {'n': (235, 225, 200), 't': (255, 140, 40), 'ct': (40, 200, 255), 'w': (255, 255, 245)}
ARC_STEPS = 20
NL = chr(10)
FONT = {   # 5 x 7, top row first
    'A': ['01110', '10001', '10001', '11111', '10001', '10001', '10001'],
    'B': ['11110', '10001', '10001', '11110', '10001', '10001', '11110'],
    'C': ['01111', '10000', '10000', '10000', '10000', '10000', '01111'],
    'D': ['11110', '10001', '10001', '10001', '10001', '10001', '11110'],
    'E': ['11111', '10000', '10000', '11110', '10000', '10000', '11111'],
}


def mat(c, bright):
    return fx_models.emissive(FX.OUT, REL_T, 'fx_obj_%s_%d' % (c, int(bright)), COLORS[c], float(bright) / 12.0, 'IRONFRAME objective marker material (generated)')   # / 12: the owner colour must not clip to white (see fx.py iff)


def ring_mesh():
    parts = [fx_models.ring(92, 100, n=72)]
    for k in range(8):                                   # chevrons pointing out, every 45 deg
        a = k * math.pi / 4; ca, sa = math.cos(a), math.sin(a)
        pts = [(100, -7), (112, 0), (100, 7), (103, 0)]
        V = [(x * ca - y * sa, x * sa + y * ca) for x, y in pts]
        parts.append(fx_models.quads(V, [(0, 1, 3), (1, 2, 3)], 0.0, 'z'))
    return fx_models.merge(parts)


def arc_mesh(frac, r0=76, r1=88):
    n = max(1, int(round(72 * frac)))
    th = [math.pi / 2 - 2 * math.pi * frac * k / n for k in range(n + 1)]     # north, clockwise seen from above
    V, F = [], []
    for k in range(n):
        a, b = th[k], th[k + 1]; i0 = len(V)
        V += [(r0 * math.cos(a), r0 * math.sin(a)), (r1 * math.cos(a), r1 * math.sin(a)), (r1 * math.cos(b), r1 * math.sin(b)), (r0 * math.cos(b), r0 * math.sin(b))]
        F += [(i0, i0 + 1, i0 + 2), (i0, i0 + 2, i0 + 3)]
    return fx_models.quads(V, F, 2.0, 'z')


def column_mesh(h=3000.0, r=16.0):
    return fx_models.merge([geo.tube([(0, 0, 0), (0, 0, h)], [r, r], sides=10, mat='m'),
                            geo.tube([(0, 0, h - 120), (0, 0, h)], [r * 2.2, r * 2.2], sides=10, mat='m')])


def letter_meshes(ch, px=26.0, depth=10.0, plate=6.0):
    """(glyphs, plate): the glyph on both faces of a dark plate in the YZ plane, each side reading the right way round
    (seen from +x the columns run +y; from -x they are mirrored), so the turning letter never shows a mirror image"""
    rows = FONT[ch]; glyph = []
    for j, row in enumerate(rows):
        for i, bit in enumerate(row):
            if bit != '1': continue
            zc = (6 - j) * px + px / 2
            glyph.append(geo.rbox(depth, px, px, r=1.0, seg=1, mat='m', center=(plate / 2 + depth / 2, (i - 2) * px, zc)))
            glyph.append(geo.rbox(depth, px, px, r=1.0, seg=1, mat='m', center=(-plate / 2 - depth / 2, (2 - i) * px, zc)))
    back = geo.rbox(plate, px * 5.8, px * 7.8, r=1.0, seg=1, mat='m', center=(0, 0, px * 3.5))
    return fx_models.merge(glyph), back


def write_two_mat(name, parts):
    """an SMD with one material per part [(mesh, vmat)], its vmdl (prop_dynamic, single LOD)"""
    d = os.path.join(FX.OUT, REL_M); os.makedirs(d, exist_ok=True)
    lines = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0", "0 0 0 0 0 0 0", "end", "triangles"]
    fmt = "0 %.4f %.4f %.4f %.4f %.4f %.4f %.5f %.5f"
    remaps = []
    for k, (mesh, vmat) in enumerate(parts):
        mn = '%s_%d.vmat' % (name, k); remaps.append((mn, vmat))
        for f in mesh.F:
            lines.append(mn)
            for i in f:
                x, y, z = mesh.V[i]; nx, ny, nz = mesh.N[i]
                lines.append(fmt % (y, -x, z, ny, -nx, nz, 0.0, 1.0))   # ModelDoc turns SMD 90 degrees (create/modelio.write_smd)
    lines.append("end")
    open(os.path.join(d, name + '.smd'), 'w', newline=NL).write(NL.join(lines) + NL)
    txt = FX.modelio.vmdl_text(name, REL_M, [name], remaps, [], surface='metal', archetype='', entity='prop_dynamic', single_lod=True)
    vp = '%s/%s.vmdl' % (REL_M, name)
    open(os.path.join(FX.OUT, vp.replace('/', os.sep)), 'w', newline=NL).write(txt)
    return vp


def flag_mesh():
    pole = geo.tube([(0, 0, 0), (0, 0, 420)], [6, 5], sides=8, mat='m')
    banner = geo.rbox(8, 190, 120, r=1.5, seg=1, mat='m', center=(0, 100, 350))
    ball = geo.lathe([(0.01, -14), (14, 0), (0.01, 14)], sides=10, mat='m'); ball.V = ball.V + np.array([0, 0, 434.0])
    foot = geo.tube([(0, 0, 0), (0, 0, 12)], [40, 34], sides=12, mat='m')
    return fx_models.merge([pole, banner, ball, foot])


def build(only=None):
    made = {}
    want = lambda k: (not only) or k in only
    for c in ('n', 't', 'ct', 'w'):
        if want('obj_ring_' + c): made['obj_ring_' + c] = FX.write_model(REL_M, 'obj_ring_' + c, ring_mesh(), mat(c, 16))
        if want('obj_col_' + c): made['obj_col_' + c] = FX.write_model(REL_M, 'obj_col_' + c, column_mesh(), mat(c, 24))
    for c in ('t', 'ct'):
        for k in range(1, ARC_STEPS + 1):
            key = 'obj_arc_%s_%02d' % (c, k)
            if want(key): made[key] = FX.write_model(REL_M, key, arc_mesh(k / ARC_STEPS), mat(c, 20))
        if want('obj_flag_' + c): made['obj_flag_' + c] = FX.write_model(REL_M, 'obj_flag_' + c, flag_mesh(), mat(c, 24))
    for ch in FONT:
        for c in ('n', 't', 'ct'):
            key = 'obj_letter_%s_%s' % (ch.lower(), c)
            if want(key):
                g, back = letter_meshes(ch)
                made[key] = write_two_mat(key, [(g, mat(c, 28)), (back, FX.flat_vmat('obj_sign_back', (22, 24, 28), 0.5, 0.6))])
    return made


def main():
    compile_ = '--no-compile' not in sys.argv
    only = None
    if '--only' in sys.argv: only = set(sys.argv[sys.argv.index('--only') + 1].split(','))
    made = build(only)
    print('objective_fx: %d models written' % len(made))
    results = {}
    if compile_:
        work = FR.json.load(open(os.path.join(PROJ, 'data', 'frames.json'), encoding='utf-8'))['paths']['work']
        cres = FR.compile_models(FX.OUT, [REL_M, REL_T], list(made.values()), os.path.join(work, 'logs', 'rc_objective_fx.log'))
        for k, v in made.items():
            ok, s, pr = cres[v]; results[k] = ok
            print('compile %-20s %s %5.1fs %s' % (k, 'OK ' if ok else 'FAIL', s, '; '.join(pr)[:160]), flush=True)
    path = os.path.join(FX.OUT, '_gen', 'objectives.json')
    data = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
    models = data.get('models', {})
    for k, v in made.items():
        if results.get(k, True): models[k] = v
        else: models.pop(k, None)
    data['models'] = dict(sorted(models.items())); data['arc_steps'] = ARC_STEPS
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, 'w', encoding='utf-8'), indent=1)
    bad = [k for k, ok in results.items() if not ok]
    print('objectives.json: %d models%s' % (len(data['models']), ('; FAILED: ' + ', '.join(bad)) if bad else ''))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
