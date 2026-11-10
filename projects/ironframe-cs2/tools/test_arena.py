"""Writes out/addon/_gen/arena.json for the core tests (docs/INTERFACES.md section 2): a 14000 x 14000 heightfield of gentle
hills with a few rock pillars (struct cells, so the trace paths get exercised), three capture points, 8 drops per team plus
16 free-for-all drops, and the 56 x 56 nav grid (height, walk, struct, cover). tools/vmap.py (the map generator) replaces this
file with the real arena; the core never depends on anything that is only in this one.

  python3 -I tools/test_arena.py [out-file]
"""
import json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'out', 'addon', '_gen', 'arena.json')

CELL, X0, Y0, W, H = 256, -7168, -7168, 56, 56
HALF, ZTOP = 7000, 5000
# rock pillars: (cell x, cell y, size in cells, height above the ground); walk 0 and struct 1 there and struct 1 one cell around
PILLARS = [(14, 20, 2, 700), (40, 34, 2, 700), (27, 10, 3, 500), (27, 44, 3, 500), (8, 42, 2, 600), (46, 12, 2, 600), (20, 30, 1, 900), (36, 24, 1, 900)]


def hills(x, y):
    """Gentle hills: 120..720 u, a few broad sine bumps plus a low saddle across the middle. Deterministic, smooth."""
    z = 320
    z += 160 * math.sin(x / 1900.0 + 0.4) * math.cos(y / 2300.0 - 0.7)
    z += 110 * math.sin((x + y) / 3100.0 + 1.3)
    z += 70 * math.cos((x - 1.6 * y) / 1700.0)
    z += 60 * math.sin(x / 820.0) * math.sin(y / 760.0)
    return max(120.0, min(720.0, z))


def main():
    height, walk, struct, cover = [], [], [], []
    pillar_at = {}
    for (cx, cy, s, h) in PILLARS:
        for j in range(cy, cy + s):
            for i in range(cx, cx + s):
                pillar_at[(i, j)] = h
    for j in range(H):
        for i in range(W):
            x = X0 + (i + 0.5) * CELL
            y = Y0 + (j + 0.5) * CELL
            z = hills(x, y)
            inside = abs(x) < HALF - CELL and abs(y) < HALF - CELL
            is_pillar = (i, j) in pillar_at
            near = any((i + di, j + dj) in pillar_at for di in (-1, 0, 1) for dj in (-1, 0, 1))
            if is_pillar:
                z += pillar_at[(i, j)]
            height.append(round(z, 1))
            walk.append(1 if inside and not is_pillar else 0)
            struct.append(1 if near else 0)
            # cover value: near a pillar (its foot), else a little from the slopes
            if near and not is_pillar:
                cover.append(200)
            else:
                dzdx = hills(x + CELL, y) - hills(x - CELL, y)
                dzdy = hills(x, y + CELL) - hills(x, y - CELL)
                slope = math.hypot(dzdx, dzdy) / (2 * CELL)
                cover.append(int(max(0, min(120, slope * 400))))

    def ground(x, y):
        fx = (x - X0) / CELL - 0.5
        fy = (y - Y0) / CELL - 0.5
        i = max(0, min(W - 2, int(math.floor(fx))))
        j = max(0, min(H - 2, int(math.floor(fy))))
        tx = max(0.0, min(1.0, fx - i))
        ty = max(0.0, min(1.0, fy - j))
        h00, h10, h01, h11 = height[j * W + i], height[j * W + i + 1], height[(j + 1) * W + i], height[(j + 1) * W + i + 1]
        return (h00 * (1 - tx) + h10 * tx) * (1 - ty) + (h01 * (1 - tx) + h11 * tx) * ty

    def drop(x, y, yaw):
        return [x, y, round(ground(x, y) + 1500, 1), yaw]

    drops_t = [drop(-6000 + (k % 2) * 500, -3500 + k * 1000, 0) for k in range(8)]
    drops_ct = [drop(6000 - (k % 2) * 500, -3500 + k * 1000, 180) for k in range(8)]
    ffa = []
    for k in range(16):
        a = k / 16.0 * 2 * math.pi
        ffa.append(drop(round(5200 * math.cos(a)), round(5200 * math.sin(a)), round((math.degrees(a) + 180) % 360)))
    points = [{'id': 'A', 'pos': [-3500, 0, round(ground(-3500, 0), 1)], 'radius': 700},
              {'id': 'B', 'pos': [0, 0, round(ground(0, 0), 1)], 'radius': 700},
              {'id': 'C', 'pos': [3500, 0, round(ground(3500, 0), 1)], 'radius': 700}]
    arena = {
        'id': 'test', 'name': 'Test Range', 'title': 'IRONFRAME: Test Range',
        'bounds': {'min': [-HALF, -HALF, 0], 'max': [HALF, HALF, ZTOP]},
        'drops': {'t': drops_t, 'ct': drops_ct, 'ffa': ffa},
        'points': points,
        'booth': [0, 0, -4000], 'cache': [2000, 0, -4000],
        'nav': {'cell': CELL, 'x0': X0, 'y0': Y0, 'w': W, 'h': H, 'height': height, 'walk': walk, 'struct': struct, 'cover': cover},
        'landmarks': [{'name': 'North Rocks', 'pos': [X0 + 27.5 * CELL, Y0 + 44.5 * CELL, 900]},
                      {'name': 'South Rocks', 'pos': [X0 + 27.5 * CELL, Y0 + 10.5 * CELL, 900]}],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(arena, f, separators=(',', ':'))
        f.write('\n')
    n_struct = sum(struct)
    n_walk = sum(walk)
    print('%s: %dx%d cells, ground %.0f..%.0f, walk %d, struct %d, %d+%d+%d drops, %d points' % (
        OUT, W, H, min(height), max(height), n_walk, n_struct, len(drops_t), len(drops_ct), len(ffa), len(points)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
