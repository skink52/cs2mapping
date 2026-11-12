"""Before / after views of the terrain patch (remaster step 7), to look at: top-down hillshades of every area and eye-level views.

usage: python tools/terrain_views.py [--before V] [--after V] [--layers out/step7/terrain_layers.npz] [--out out/review] [--only name,...]
  defaults: --before out/mg_trenchwarfare_models.vmap, --after out/mg_trenchwarfare_terrain.vmap
Writes out/review/terrain_<area>.png (hillshade before | after | after with the protect mask in red and the frozen faces in blue)
and out/review/terrain_eye_<view>.png (eye level, before above after: the terrain surfaces of both maps on the 16-u lattice, lit from
the north-west, after tinted by the new mud / wet / dirt paint; terrain only, no props or water). Reads the layer file the patch writes
(both maps' terrain read back on the lattice); writes only the pictures.
"""
import argparse, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(PROJ, '..', '..'))
sys.path[:] = [os.path.join(REPO, 'tools')] + [p for p in sys.path if os.path.normcase(os.path.abspath(p or '.')) != os.path.normcase(HERE)]
import numpy as np                 # noqa: E402
from PIL import Image, ImageDraw   # noqa: E402
import vmapedit as V               # noqa: E402
import vmap_preview as VP          # noqa: E402
sys.path.append(os.path.join(REPO, 'create'))
import terrain_img as TI           # noqa: E402

CELL, X0, Y0 = 16.0, -7168.0, -6144.0
AREAS = {
    'nml_north': (-1550, 0, 1550, 2900), 'nml_south': (-1550, -3100, 1550, 0),
    't_rear': (-4400, -3400, -2200, 3400), 'ct_rear': (2200, -3400, 4400, 3400),
    't_airfield': (-7100, -1600, -4200, 1600), 'ct_airfield': (4200, -1600, 7100, 1600),
    'north_flank': (-2400, 3200, 2400, 5800), 'south_flank': (-2400, -5800, 2400, -3200),
    'whole': (-7168, -6144, 7168, 6144),
}
# (name, eye, look-at): a fire-step eye over the parapet, a tank's track, the airfield ruts, the rear
EYES = {
    't_firestep_east': ((-1560, 700, 40), (-200, 1000, -120)),
    'ct_firestep_west': ((1560, -1300, 40), (200, -1000, -120)),
    'ct_rear_mortars': ((2500, -2900, 260), (3300, -1800, -60)),
    't_rear': ((-2450, 2600, 200), (-3300, 1200, -60)),
    'nml_overview_s': ((0, -3300, 700), (0, -900, -80)),
    'nml_overview_n': ((0, 2900, 700), (0, 500, -80)),
}


def crop(A, box):
    x0, y0, x1, y1 = box
    i0, i1 = int((x0 - X0) / CELL), int((x1 - X0) / CELL) + 1; j0, j1 = int((y0 - Y0) / CELL), int((y1 - Y0) / CELL) + 1
    return A[max(0, i0):i1, max(0, j0):j1]


def shade(Z, extra=None, scale=1):
    img = TI.hillshade(Z, CELL / scale if scale else CELL, exaggerate=1.6, tint=False).astype(float)
    if extra is not None:
        for (M, col, a) in extra:
            Mv = M.T[::-1].astype(float)[..., None] * a
            img = img * (1 - Mv) + np.array(col, float) * Mv
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def topdown(L, out, only):
    for name, box in AREAS.items():
        if only and name not in only: continue
        H0, H1 = crop(L['H'], box), crop(L['Hnew'], box)
        k = 1 if name == 'whole' else max(1, int(560 / max(H0.shape)))
        from scipy import ndimage
        up = lambda A: (ndimage.zoom(A.astype(float), k, order=1) if k > 1 else A.astype(float))
        hard, R = crop(L['hard'], box), crop(L['R'], box)
        mud, wet = crop(L['mud'], box), crop(L['wet'], box)
        ims = [shade(up(H0), scale=k), shade(up(H1), [(up(mud), (95, 70, 45), 0.35), (up(wet), (40, 45, 60), 0.35)], scale=k),
               shade(up(H1), [(up(R & ~hard) > 0.5, (60, 90, 255), 0.35), (up(hard) > 0.5, (255, 40, 40), 0.45)], scale=k)]
        W, Hh = ims[0].size
        sheet = Image.new('RGB', (W * 3 + 20, Hh + 22), (20, 20, 24))
        d = ImageDraw.Draw(sheet)
        for n, (im, lab) in enumerate(zip(ims, ('before', 'after (mud / wet tint)', 'after: protect mask red, frozen faces blue'))):
            sheet.paste(im, (n * (W + 10), 22)); d.text((n * (W + 10) + 4, 4), '%s  %s' % (name, lab), fill=(255, 255, 255))
        p = os.path.join(out, 'terrain_%s.png' % name); sheet.save(p); print('->', p)


def heightfield_view(Z, tint, eye, look, W=960, Hh=420, fov=70.0, far=3200.0, step=6.0):
    """eye-level picture of a height lattice (Comanche-style column renderer): lambert light from the north-west, haze with distance;
    tint (NX, NY, 3) multiplies the ground colour (mud / wet paint)"""
    ex, ey, ez = eye
    yaw = math.atan2(look[1] - ey, look[0] - ex)
    pitch = math.atan2(look[2] - ez, math.hypot(look[0] - ex, look[1] - ey))
    f = (W / 2) / math.tan(math.radians(fov) / 2)
    hor = Hh / 2 + f * math.tan(pitch)
    gx = np.gradient(Z, CELL, axis=0); gy = np.gradient(Z, CELL, axis=1)
    n = np.stack([-gx, -gy, np.ones_like(Z)], -1); n /= np.linalg.norm(n, axis=-1, keepdims=True)
    sun = np.array([-0.62, 0.45, 0.55]); sun /= np.linalg.norm(sun)
    lit = np.clip(n @ sun, 0, 1) * 0.85 + 0.22
    base = np.array([118, 104, 82], float)
    col = base[None, None, :] * lit[..., None] * tint
    img = np.zeros((Hh, W, 3)); img[:] = (150, 160, 175)
    ds = np.arange(8.0, far, step)
    for c in range(W):
        a = yaw + math.atan2(W / 2 - c, f)
        k = math.cos(a - yaw)
        px = ex + np.cos(a) * ds; py = ey + np.sin(a) * ds
        fi = (px - X0) / CELL; fj = (py - Y0) / CELL
        ok = (fi >= 0) & (fi < Z.shape[0] - 1) & (fj >= 0) & (fj < Z.shape[1] - 1)
        if not ok.any(): continue
        fi, fj, d = fi[ok], fj[ok], ds[ok]
        i = fi.astype(int); j = fj.astype(int); u = fi - i; v = fj - j
        z = (Z[i, j] * (1 - u) + Z[i + 1, j] * u) * (1 - v) + (Z[i, j + 1] * (1 - u) + Z[i + 1, j + 1] * u) * v
        sy = hor - f * (z - ez) / (d * k)
        top = np.minimum.accumulate(sy)
        prev = np.concatenate([[Hh], top[:-1]])
        cc = col[i, j]
        haze = np.clip(d / far, 0, 1)[:, None] ** 1.3
        cc = cc * (1 - haze * 0.7) + np.array([150, 160, 175]) * haze * 0.7
        for kk in np.nonzero(top < prev)[0]:
            y0, y1 = int(max(0, math.ceil(top[kk]))), int(min(Hh, math.ceil(prev[kk])))
            if y1 > y0: img[y0:y1, c] = cc[kk]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def feature_eyes(report):
    """eye positions along the patch's own features: beside each tank track and airfield rut, looking along it"""
    out = {}
    if not report or not os.path.isfile(report): return out
    import json
    F = json.load(open(report)).get('features_detail', {})
    for k, t in enumerate(F.get('tracks', [])):
        P = np.array(t['pts'], float)
        if len(P) < 6: continue
        a, b = P[len(P) // 6], P[int(len(P) * 0.75)]
        d = (b - a) / max(np.linalg.norm(b - a), 1e-6); nrm = np.array([-d[1], d[0]])
        e = a - d * 260 + nrm * 120
        out['track_%d_%s' % (k + 1, t['model'])] = ((float(e[0]), float(e[1]), 110.0), (float(b[0]), float(b[1]), -40.0))
    for t in F.get('ruts', [])[:2]:
        P = np.array(t['pts'], float)
        a, b = P[0], P[len(P) // 2]
        d = (b - a) / max(np.linalg.norm(b - a), 1e-6); nrm = np.array([-d[1], d[0]])
        e = a - d * 200 + nrm * 60
        out['ruts_%s_%s' % (t['side'], t['edge'])] = ((float(e[0]), float(e[1]), 90.0), (float(b[0]), float(b[1]), -30.0))
    return out


def eyes(L, out, only, report=None):
    allv = dict(EYES); allv.update(feature_eyes(report))
    views = [(n, e) for n, e in allv.items() if not only or n in only]
    for name, (eye, look) in views:
        t0 = np.ones(L['H'].shape + (3,))
        mud, wet, dirt = L['mud'], L['wet'], L['dirt']
        t1 = np.ones(L['H'].shape + (3,))
        t1 *= (1 - 0.22 * mud)[..., None] * np.array([1.0, 0.93, 0.85])[None, None, :] ** mud[..., None]
        t1 *= (1 - 0.3 * wet)[..., None]
        t1 *= np.array([1.05, 0.95, 0.8])[None, None, :] ** dirt[..., None]
        Hb = np.where(np.isfinite(L['H']), L['H'], 0); Ha = np.where(np.isfinite(L['Hnew']), L['Hnew'], Hb)
        rows = [heightfield_view(Hb, t0, eye, look), heightfield_view(Ha, t1, eye, look)]
        sheet = Image.new('RGB', (960, 862), (0, 0, 0)); sheet.paste(rows[0], (0, 0)); sheet.paste(rows[1], (0, 442))
        d = ImageDraw.Draw(sheet)
        d.text((6, 4), '%s  before  (terrain only, from %s)' % (name, eye), fill=(0, 0, 0)); d.text((6, 446), '%s  after' % name, fill=(0, 0, 0))
        p = os.path.join(out, 'terrain_eye_%s.png' % name); sheet.save(p); print('->', p)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--before', default=os.path.join(PROJ, 'out', 'mg_trenchwarfare_models.vmap'))
    ap.add_argument('--after', default=os.path.join(PROJ, 'out', 'mg_trenchwarfare_terrain.vmap'))
    ap.add_argument('--layers', default=os.path.join(PROJ, 'out', 'step7', 'terrain_layers.npz'))
    ap.add_argument('--out', default=os.path.join(PROJ, 'out', 'review'))
    ap.add_argument('--only', default='')
    ap.add_argument('--no-eyes', action='store_true')
    a = ap.parse_args(argv)
    only = set(x for x in a.only.split(',') if x)
    os.makedirs(a.out, exist_ok=True)
    topdown(np.load(a.layers), a.out, only)
    if not a.no_eyes: eyes(np.load(a.layers), a.out, only, os.path.join(os.path.dirname(a.layers), 'patch_terrain.report.json'))


if __name__ == '__main__':
    main()
