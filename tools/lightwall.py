"""Lights pressed against a wall: moved out so they stop painting a hot spot on it.

  python lightwall.py <vmap in> <vmap out> [min distance, default 24]

CS:GO's lights often sat a few units off a wall (a torch's light inside the torch, a lamp's light against its fitting). CS2 bakes those as a
blown-out spot on the surface behind and uneven light around it (skink52: common on the course maps and both Minecraft maps). Each light that
sits in front of a large visible face (>= 512 sq units, so torch and lamp meshes themselves don't count) closer than the minimum is moved
straight out along that face's normal until it is the minimum away; in a corner the pushes from each wall add up. A move that would carry
the light through another face is halved until it doesn't. Lights inside geometry, behind a face, or with a parent are left alone.
"""
import collections, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmapedit as V, zfight, dmx

LIGHTS = ('light_omni2', 'light_spot', 'light_omni', 'light_rect', 'light_capsule')
MIN_AREA = 512.0
CELL = 128.0

def surfaces(m):
    out = []
    zfight.ORIGINS.clear()
    for node, f, mat, poly in zfight.faces(m):
        if len(poly) < 3 or zfight.transparent(mat, None): continue
        pl = zfight.plane(poly)
        if not pl: continue
        n, d = pl; q = zfight.to2d(poly, n); a = abs(zfight.area2(q))
        out.append((n, d, poly, q, a))
    return out

def inside(q, pt):
    """point in convex-ish polygon (2D, counter-clockwise), with a small margin"""
    for i in range(len(q)):
        a, b = q[i], q[(i + 1) % len(q)]
        if (b[0] - a[0]) * (pt[1] - a[1]) - (b[1] - a[1]) * (pt[0] - a[0]) < -1.0: return False
    return True

def proj2d(p, n):
    ax = max(range(3), key=lambda i: abs(n[i])); u, v = [i for i in range(3) if i != ax]
    return (p[u], p[v])

def run(m, mind=24.0):
    S = surfaces(m)
    grid = collections.defaultdict(list)
    for i, (n, d, poly, q, a) in enumerate(S):
        lo = [min(p[k] for p in poly) - mind for k in range(3)]; hi = [max(p[k] for p in poly) + mind for k in range(3)]
        for x in range(int(lo[0] // CELL), int(hi[0] // CELL) + 1):
            for y in range(int(lo[1] // CELL), int(hi[1] // CELL) + 1):
                for z in range(int(lo[2] // CELL), int(hi[2] // CELL) + 1): grid[(x, y, z)].append(i)
    def near(p):
        return grid.get(tuple(int(p[k] // CELL) for k in range(3)), [])
    moved = []; skipped = 0
    for e in m.entities():
        if m.cls(e) not in LIGHTS: continue
        if m.P(e, 'parentname', ''): continue
        p = m.origin(e); push = [0.0, 0.0, 0.0]; walls = 0
        for i in set(near(p)):
            n, d, poly, q, a = S[i]
            if a < MIN_AREA: continue
            s = sum(n[k] * p[k] for k in range(3)) - d
            if not (0 <= s < mind) or not in_poly(S[i], p): continue
            for k in range(3): push[k] += n[k] * (mind - s)
            walls += 1
        if not walls: continue
        step = 1.0
        for _ in range(4):
            np_ = [p[k] + push[k] * step for k in range(3)]
            if not crosses(S, near, p, np_): break
            step /= 2
        else:
            skipped += 1; continue
        dmx.set_(m.E[e], b'origin', dmx.T_V3, np_)
        moved.append((m.name(e) or m.cls(e), [round(x) for x in p], round(math.sqrt(sum((np_[k] - p[k]) ** 2 for k in range(3))), 1)))
    return moved, skipped

def in_poly(s, p):
    n, d, poly, q, a = s
    return inside(q, proj2d(p, n))

def crosses(S, near, a, b):
    """does the segment a->b pass through any surface (a face with a on one side and b on the other, the crossing point inside it)"""
    for i in set(near(a)) | set(near(b)):
        n, d, poly, q, area = S[i]
        sa = sum(n[k] * a[k] for k in range(3)) - d; sb = sum(n[k] * b[k] for k in range(3)) - d
        if (sa > 0.01) == (sb > 0.01) or abs(sa - sb) < 1e-6: continue
        t = sa / (sa - sb); x = [a[k] + (b[k] - a[k]) * t for k in range(3)]
        if inside(q, proj2d(x, n)): return True
    return False

if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    mp = V.Map(sys.argv[1]); mind = float(sys.argv[3]) if len(sys.argv) > 3 else 24.0
    moved, skipped = run(mp, mind); mp.save(sys.argv[2])
    for nm, at, dist in moved[:40]: print('moved\t%s at %s by %g' % (nm, ' '.join(map(str, at)), dist))
    print('summary\tmoved=%d skipped=%d' % (len(moved), skipped))
