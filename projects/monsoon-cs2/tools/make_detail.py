"""mg_monsoon: export layout.height, erode it with create/terrain_img.py, write the detail layer + paint / foliage images.
  python make_detail.py [out_dir]      (run from anywhere; reads tools/layout.py, writes tools/data: detail.png + splat / density images + hillshades)"""
import json, os, sys, time
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(PROJ, '..', '..'))
sys.path.insert(0, os.path.join(PROJ, 'tools')); sys.path.append(os.path.join(REPO, 'create'))
import numpy as np
import layout as L
import terrain_img as TI

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'data')
CELL = 32.0
BOUNDS = (-L.TERRAIN_X, -L.TERRAIN_Y, L.TERRAIN_X, L.TERRAIN_Y)
RECIPE = json.load(open(os.path.join(HERE, 'recipe.json'))) if os.path.isfile(os.path.join(HERE, 'recipe.json')) else {}


def base_height(X, Y):
    """layout.height WITHOUT the detail layer (so re-running never erodes its own output)"""
    return (getattr(L, 'height_base', None) or L.height)(X, Y)


def protect_mask(X, Y, Z):
    """True where the ground must not change"""
    m = TI.discs(X, Y, [(fx, fy, 500.0) for _, _, (fx, fy) in L.FLAGS])
    m |= TI.discs(X, Y, [(L.CT_BASE[0], L.CT_BASE[1], L.CT_PLATEAU_R * 1.10 + 120.0), (L.T_BASE[0], L.T_BASE[1], L.T_PLATEAU_R * 1.14 + 120.0),
                         (L.VILLAGE[0], L.VILLAGE[1], L.VILLAGE_R * 1.12 + 60.0), (L.CRASH[0], L.CRASH[1], L.CRASH_R * 1.12 + 60.0),
                         (L.TEMPLE[0], L.TEMPLE[1], L.TEMPLE_R * 1.10 + 60.0)])
    m |= TI.discs(X, Y, [(fx, fy, r0 + 60.0) for fx, fy, r0, r1 in L.FLATS])
    m |= TI.along(X, Y, [(hw * 2.3 + 32.0, pts) for hw, pts in L.ROADS])
    yr = Y - L.river_y(X)
    for x0, x1, a, b in ((L.PADDY_X0, L.PADDY_X1, L.PADDY_YR0, L.PADDY_YR1), (L.PADDY2_X0, L.PADDY2_X1, L.PADDY2_YR0, L.PADDY2_YR1)):
        m |= (X >= x0 - 110) & (X <= x1 + 110) & (yr >= a - 110) & (yr <= b + 110)
    m |= L.water_dist(X, Y) <= L.BANK_W + 40.0                       # river and banks
    m |= TI.below(Z, L.WATER_Z + 12.0)                               # oxbow, marsh pools, anything at the water line
    m |= TI.along(X, Y, [(L.OXBOW_HW * 1.6, L.OXBOW)])
    m |= TI.discs(X, Y, [(kx, ky, kr + 100.0) for kx, ky, kr, kh, ks in L.KARST])      # the tower meshes sit on this ground
    m |= TI.discs(X, Y, [(cx, cy, r * 1.6) for cx, cy, r, dep in L.CRATERS])
    m |= TI.discs(X, Y, [(px, py, 300.0) for px, py in L.TUNNEL_PORTALS])
    m |= TI.along(X, Y, [(L.TUNNEL_HW + 80.0, g) for g in L.TUNNEL_GALLERIES])
    m |= (np.abs(X) >= L.TERRAIN_X - 64.0) | (np.abs(Y) >= L.TERRAIN_Y - 64.0)        # the edge meets the skybox terrain
    return m


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    F = TI.Field.from_fn(base_height, BOUNDS, CELL)
    F.save(os.path.join(OUT, 'height.png'))
    X, Y = F.XY
    hard = protect_mask(X, Y, F.Z)
    TI.save8(os.path.join(OUT, 'protect.png'), hard)
    print('export %.1fs: %s, z %.0f..%.0f, protected %.1f%%' % (time.time() - t0, F.Z.shape, F.Z.min(), F.Z.max(), 100 * hard.mean()))
    rep = TI.run_detail(os.path.join(OUT, 'height.png'), OUT, os.path.join(OUT, 'protect.png'), feather_px=8.0, recipe=RECIPE, water_z=L.WATER_Z, scale=2)
    # the check that matters: layout.height + detail == layout.height wherever the analytic mask says protected, sampled OFF the grid too
    D = TI.Field.load(os.path.join(OUT, 'detail.png'))
    rng = np.random.RandomState(5)
    xs = rng.uniform(BOUNDS[0], BOUNDS[2], 400000); ys = rng.uniform(BOUNDS[1], BOUNDS[3], 400000)
    inside = protect_mask(xs, ys, base_height(xs, ys))
    print('off-grid samples in the protected masks: %d, max |detail| there: %.6f' % (inside.sum(), np.abs(D(xs, ys))[inside].max()))
    play = L.in_play(X, Y)
    for name, Z in (('before', F.Z), ('after', F.Z + D.Z)):
        s = TI.slope_deg(Z, CELL)
        print('%s: play-space ground over 45 deg %.2f%%, over 35 deg %.2f%%' % (name, 100 * (s[play] > 45).mean(), 100 * (s[play] > 35).mean()))
    print('total %.1fs' % (time.time() - t0))


if __name__ == '__main__':
    main()
