# mg_monsoon: terrain detail from images

Status: **run on a height export, looked at as hillshades; not applied to the map, not compiled.** The generic part is
`create/terrain_img.py` ([guide section 10](../../../docs/creation/guide.md#10-image-driven-terrain-11-nov-2026-unit-tested-not-yet-compiled-into-a-map));
this file is the monsoon glue. Nothing in `tools/` was changed by this work: sections 2 and 3 are listings to apply.

What it does: exports `layout.height(x, y)` over x +-7168, y +-6144 as a 16-bit image (32-unit cells, 449 x 385), cuts a stream
network into the valley sides (6 gully passes + droplet erosion + scree + rock outcrops), and returns the difference as a
**detail layer** that `layout.height` adds. Flags (radius 500), both bases, the village / crash / temple terraces, the farm flat, roads,
paddies, the river and its banks, the oxbow, everything at the water line, karst feet, craters, tunnel portals and galleries and the
terrain edge are masked: the layer is exactly 0 there.

Result of the run on 11 Nov 2026 (layout as of that evening; rerun after any layout change, it takes about 30 s):

| | |
|---|---|
| detail layer | -48.9 .. +36.2 units, rms 9.5; 32 % of cells move more than 6 units, 7 % more than 20 |
| protected | 26 % of the grid; largest change inside the masks 0.0 on the grid, 0.0 at 100 269 random off-grid points, 0.0 after the PNG round trip |
| play-space ground steeper than 45 degrees | 1.07 % before, 1.01 % after (over 35 degrees: 2.56 % -> 2.90 %) |

Pictures (in the gitignored `out/terrain_detail/`, made by the script below): `hillshade_before.png`, `hillshade_after.png`,
`hillshade_after_masks.png` (protect outline in red), `sheet_paint.png`. Before: smooth noise slopes with the designed features on
them. After: branching ravines run down both valley sides to the floodplain; the floodplain and every designed feature read exactly
as before. Open them again after a rerun: that look is the acceptance test, the numbers only guard the masks.

## 1. Make the images (a, b, c in one script)

Save as `tools/make_detail.py` (it is `out/terrain_detail/make_detail.py` now; when moved to `tools/`, change `PROJ` to one
`..` and `OUT` to `tools/data`). It reads `layout.py` and writes only into its output folder.

```python
"""mg_monsoon: export layout.height, erode it with create/terrain_img.py, write the detail layer + paint / foliage images.
  python make_detail.py [out_dir]      (run from anywhere; reads tools/layout.py, writes only into out/terrain_detail)"""
import json, os, sys, time
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, '..', '..'))
REPO = os.path.abspath(os.path.join(PROJ, '..', '..'))
sys.path.insert(0, os.path.join(PROJ, 'tools')); sys.path.append(os.path.join(REPO, 'create'))
import numpy as np
import layout as L
import terrain_img as TI

OUT = sys.argv[1] if len(sys.argv) > 1 else HERE
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
```

Outputs: `height.png` (+ `.json`: bounds, cell, z = lo + step * pixel; row 0 = south), `protect.png`, `detail.png`, `eroded.png`,
the hillshades, `splat_rock / mud / grass / cavity.png`, `density_trees / undergrowth.png`, `report.json`.

Tuning: put overrides in `recipe.json` beside the script (keys and defaults: `RECIPE` in `create/terrain_img.py`). The ones that
matter here: `gully_depth` (48; deeper ravines), `gully_area1` (2500 cells; lower = more, smaller streams), `drops` (1 per cell;
0 = gullies only, much calmer), `outcrop_height` (26), `terrace_step` (0 = off; 48 gives hillside farm terraces), `max_cut` / `max_fill`
(60 / 40), `seed`. Generic one-liners for the same steps:
`python create/terrain_img.py export projects/monsoon-cs2/tools/layout.py:height --bounds=-7168,-6144,7168,6144 --cell 32 --out height.png`,
then `python create/terrain_img.py detail height.png --protect protect.png --feather 8 --water-z -30 --out <dir>`.

## 2. Feed it back: `tools/layout.py`

`terrain_img.py` must be importable from `tools/`: `python create/libsync.py add create/terrain_img.py monsoon-cs2 tools/terrain_img.py`
then `push` (the tools here are libsync copies). Keep `detail.png` + `detail.png.json` (206 KB) in `tools/data/` so every stage
that imports layout sees the same ground; it is generated data of ours, not map content.

```python
# layout.py, replacing height(): the eroded detail is a layer on top of the designed ground
import os
_DETAIL = None


def detail_field():
    """the Field from tools/data/detail.png (docs/IMAGE_TERRAIN.md), or None if make_detail.py has not run"""
    global _DETAIL
    if _DETAIL is None:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'detail.png')
        if os.path.isfile(p):
            import terrain_img
            _DETAIL = terrain_img.Field.load(p)
        else:
            _DETAIL = False
    return _DETAIL or None


def detail(x, y):
    """eroded relief added to the designed ground; exactly 0 on flags, bases, roads, paddies and water"""
    f = detail_field()
    return f(x, y) if f is not None else np.zeros(np.shape(x))


def height_base(x, y):
    """the designed ground (what make_detail.py erodes; never includes the detail layer)"""
    return carved(x, y, roads=True)


def height(x, y):
    """final ground height"""
    return height_base(x, y) + detail(x, y)
```

What follows from that, checked against the layout as read on 11 Nov:
- `make_detail.py` already calls `height_base` when it exists, so a rerun never erodes its own output.
- `_road_profile` samples `carved(roads=False)` and roads are masked, so road grades, `flag_z`, the bridge ramps, pads and gun pits
  do not move. `slope()` and `gz()` go through `height`, so props, spawns and the rock paint follow the new ground by themselves.
- `ground_low` (the skybox terrain) is `base_terrain`: unchanged, and the detail fades to 0 over the last cells before the terrain edge.
- Anything added to the layout later that needs designed ground (a new pad, a trail) must be added to `protect_mask` and the
  script rerun, or the old ravines stay under it.
- If the script is run before this edit, `height_base` does not exist and it erodes `height`: correct the first time only.

## 3. Use it in `tools/mv_terrain.py`

Mesh density: the outer slopes are 128-unit tiles, which keep the layer's size (rms 9.47 of 9.53) but turn ravine beds into
zigzags. Give tiles with real relief 64-unit cells:

```python
# mv_terrain.py, in tile_res() before the final `return 128`
    d = L.detail(*np.meshgrid(cx + np.linspace(-224, 224, 8), cy + np.linspace(-224, 224, 8)))
    if np.abs(d).max() > 10.0: return 64
```

Paint and foliage (c): load the images once, sample them per vertex. Rock and mud lower the grass weight of `BLEND_VALLEY`
(A mud, B grass); cavity darkens hollows through the tint.

```python
# mv_terrain.py
import terrain_img as TI
_IMG = {}


def img(name):
    """a 0..1 image from tools/data as a Field (rock, mud, grass, cavity, trees, undergrowth); None if make_detail.py has not run"""
    if name not in _IMG:
        base = L.detail_field()
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        f = os.path.join(d, ('density_%s.png' if name in ('trees', 'undergrowth') else 'splat_%s.png') % name)
        _IMG[name] = base.like(TI.load_mask(f, base)) if base is not None and os.path.isfile(f) else None
    return _IMG[name]


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
```

Foliage density: the images only say what the eroded shape suggests (no trees in stream beds or on rock, thicker beside
streams, undergrowth where it is damp); the design (clearings, groves, farms) stays in `layout.jungle` / `layout.grass`. Multiply:

```python
# wherever trees and undergrowth are placed (p_jungle / mv_places): density at candidate points x, y
dens_trees = L.jungle(x, y) * (0.35 + 0.65 * mv_terrain.img('trees')(x, y))
dens_ferns = np.maximum(L.grass(x, y), 0.5 * L.jungle(x, y)) * mv_terrain.img('undergrowth')(x, y)
# or, for a new layer (ferns along the ravines), points straight from an image, the same every run:
F = mv_terrain.img('undergrowth')
pts = TI.scatter_density(F.like(F.Z * L.in_play(*F.XY)), spacing=96.0, seed=7, limit=1500)
```

Copy `splat_*.png` and `density_*.png` to `tools/data/` with `detail.png` (make_detail.py's `OUT`).

## 4. Order of work and checks

1. `python tools/make_detail.py`; open both hillshades; check that the "max |detail| there" line prints 0.
2. Apply sections 2 and 3; `python create/libsync.py check`.
3. Rebuild the terrain stage; `python create/check_mesh.py` on the map; the quad count rises (64-unit tiles on the slopes).
4. Not judged yet, needs Hammer / the game: ravine depth at player scale (a 49-unit cut is waist to chest deep), helicopter
   landing spots outside the masks, the blend material in the beds, nav on the ravine sides. Ravines also give infantry covered
   approaches down the valley sides that the design did not have; if that is unwanted near a flag, widen its mask.

The listings in sections 2 and 3 were written against the files as read, not run.

## Where the method comes from

The heightmap image route and the terrain ops are ported from [cs2-map-mcp](https://github.com/Rmgs123/cs2-map-mcp) (Rmgs123, MIT).
That project has no erosion, splat or density images; those parts of `create/terrain_img.py` are our own (droplet erosion, flow
accumulation, pit filling and scree relaxation as published; see the file header).
